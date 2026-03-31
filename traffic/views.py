import os
from typing import Tuple

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from inspection.models import InspectionConfig

from .models import TrafficDashboardConfig
from .services.aggregator import (
    aggregate_timeseries,
    geo_aggregate,
    overview_kpis,
    top_lists,
)
from .services.blackbox import fetch_blackbox_summary
from .services.geoip_lookup import enrich_records
from .services.log_sources import (
    load_raw_records,
    log_source_configured,
    redis_key_for_ingest,
    sources_for_api,
)
from .services.redis_log_buffer import is_configured as redis_buffer_configured, push_raw_lines


def _access_log_mode(cfg: TrafficDashboardConfig) -> str:
    m = (cfg.access_log_mode or os.environ.get("TRAFFIC_ACCESS_LOG_MODE", "file") or "file").strip()
    return m if m in ("file", "redis") else "file"


def _redis_cap(cfg: TrafficDashboardConfig) -> int:
    try:
        n = int(cfg.redis_max_lines or 200_000)
    except (TypeError, ValueError):
        n = 200_000
    return max(1_000, min(n, 2_000_000))


def _dashboard_fetch_limits(cfg: TrafficDashboardConfig) -> Tuple[int, int]:
    """UI 拉取上限：行数来自后台配置；文件尾部字节可选环境变量覆盖。"""
    try:
        rl = int(cfg.dashboard_fetch_max_lines)
    except (TypeError, ValueError):
        rl = 35_000
    rl = max(5000, min(rl, 500_000))
    try:
        tb = int(os.environ.get("TRAFFIC_DASHBOARD_MAX_TAIL_BYTES", str(4 * 1024 * 1024)))
    except ValueError:
        tb = 4 * 1024 * 1024
    tb = max(262_144, min(tb, 52_428_800))
    return rl, tb


def _load_enriched(source_id: str = ""):
    cfg = TrafficDashboardConfig.load()
    if not cfg.enabled:
        return cfg, []
    rl, tb = _dashboard_fetch_limits(cfg)
    recs = load_raw_records(
        cfg, source_id, redis_line_cap=rl, max_tail_bytes_override=tb
    )
    enrich_records(recs, cfg.geoip_db_path)
    return cfg, recs


def _query_source(request) -> str:
    return (request.GET.get("source") or "").strip()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_overview(request):
    range_key = request.GET.get("range", "24h")
    cfg, recs = _load_enriched(_query_source(request))
    inspection = InspectionConfig.load()
    data = overview_kpis(recs, range_key)
    bb = fetch_blackbox_summary(cfg, inspection)
    data["blackbox"] = bb
    if bb.get("availability_pct") is not None:
        data["availability_pct"] = bb["availability_pct"]
    data["log_configured"] = log_source_configured(cfg, redis_buffer_configured())
    data["access_log_mode"] = _access_log_mode(cfg)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_timeseries(request):
    range_key = request.GET.get("range", "24h")
    _, recs = _load_enriched(_query_source(request))
    return Response(aggregate_timeseries(recs, range_key))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_geo(request):
    range_key = request.GET.get("range", "24h")
    granularity = request.GET.get("granularity", "country")
    country = request.GET.get("country", "")
    _, recs = _load_enriched(_query_source(request))
    return Response(geo_aggregate(recs, range_key, granularity, country))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_top(request):
    range_key = request.GET.get("range", "24h")
    top_type = request.GET.get("type", "paths")
    limit = int(request.GET.get("limit", "10"))
    _, recs = _load_enriched(_query_source(request))
    return Response(top_lists(recs, range_key, top_type, limit))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_snapshot(request):
    """
    一次返回大盘所需数据，只解析 / GeoIP 一遍，避免 7 路并行把 Redis 与 CPU 打满导致 503/超时。
    """
    range_key = request.GET.get("range", "24h")
    source = _query_source(request)
    cfg, recs = _load_enriched(source)
    inspection = InspectionConfig.load()
    ov = overview_kpis(recs, range_key)
    bb = fetch_blackbox_summary(cfg, inspection)
    ov["blackbox"] = bb
    if bb.get("availability_pct") is not None:
        ov["availability_pct"] = bb["availability_pct"]
    ov["log_configured"] = log_source_configured(cfg, redis_buffer_configured())
    ov["access_log_mode"] = _access_log_mode(cfg)
    return Response(
        {
            "overview": ov,
            "timeseries": aggregate_timeseries(recs, range_key),
            "geo": geo_aggregate(recs, range_key, "country", ""),
            "top_paths": top_lists(recs, range_key, "paths", 10),
            "top_slow": top_lists(recs, range_key, "slow", 10),
            "top_status": top_lists(recs, range_key, "status", 20),
            "top_ip": top_lists(recs, range_key, "ip", 10),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_sources(request):
    cfg = TrafficDashboardConfig.load()
    return Response({"items": sources_for_api(cfg)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_blackbox(request):
    cfg = TrafficDashboardConfig.load()
    inspection = InspectionConfig.load()
    return Response(fetch_blackbox_summary(cfg, inspection))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_jaeger_traces_mock(request):
    """Placeholder until Jaeger Query API is wired."""
    return Response(
        {
            "note": "当前为模拟数据，后续接入 Jaeger Query API 替换。",
            "traces": [
                {
                    "trace_id": "7a3f9c2e1d8b4a6f0e5c3d2b1a987654",
                    "root_service": "shark-gateway",
                    "span_count": 14,
                    "duration_ms": 128,
                    "started_at": "2026-03-30T06:15:00Z",
                    "status": "ok",
                },
                {
                    "trace_id": "8b4e0d3f2c9a5b7e1f6d4c3b2a098765",
                    "root_service": "api-core",
                    "span_count": 22,
                    "duration_ms": 890,
                    "started_at": "2026-03-30T06:14:42Z",
                    "status": "error",
                },
                {
                    "trace_id": "9c5f1e4a3d0b6c8f2e7d5c4b3a109876",
                    "root_service": "sync-worker",
                    "span_count": 6,
                    "duration_ms": 45,
                    "started_at": "2026-03-30T06:14:30Z",
                    "status": "ok",
                },
            ],
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def traffic_dashboard_config(request):
    cfg = TrafficDashboardConfig.load()
    if request.method == "GET":
        return Response(
            {
                "enabled": cfg.enabled,
                "access_log_mode": cfg.access_log_mode or TrafficDashboardConfig.ACCESS_LOG_MODE_FILE,
                "access_log_path": cfg.access_log_path,
                "error_log_path": cfg.error_log_path,
                "log_format": cfg.log_format,
                "max_tail_bytes": cfg.max_tail_bytes,
                "redis_log_key": cfg.redis_log_key or "traffic:access:lines",
                "redis_max_lines": cfg.redis_max_lines,
                "dashboard_fetch_max_lines": cfg.dashboard_fetch_max_lines,
                "log_sources": cfg.log_sources if isinstance(cfg.log_sources, list) else [],
                "geoip_db_path": cfg.geoip_db_path,
                "use_inspection_prometheus": cfg.use_inspection_prometheus,
                "prometheus_url_override": cfg.prometheus_url_override,
                "blackbox_promql": cfg.blackbox_promql,
                "redis_env_configured": redis_buffer_configured(),
                "ingest_path": "/api/traffic/ingest",
            }
        )
    data = request.data
    cfg.enabled = bool(data.get("enabled", cfg.enabled))
    mode = data.get("access_log_mode", cfg.access_log_mode) or "file"
    cfg.access_log_mode = mode if mode in ("file", "redis") else "file"
    cfg.access_log_path = data.get("access_log_path", cfg.access_log_path) or ""
    cfg.error_log_path = data.get("error_log_path", cfg.error_log_path) or ""
    cfg.log_format = data.get("log_format", cfg.log_format) or "json"
    cfg.max_tail_bytes = int(data.get("max_tail_bytes", cfg.max_tail_bytes))
    cfg.redis_log_key = (data.get("redis_log_key", cfg.redis_log_key) or "traffic:access:lines").strip()[
        :256
    ]
    try:
        cfg.redis_max_lines = int(data.get("redis_max_lines", cfg.redis_max_lines))
    except (TypeError, ValueError):
        pass
    try:
        dml = int(data.get("dashboard_fetch_max_lines", cfg.dashboard_fetch_max_lines))
        cfg.dashboard_fetch_max_lines = max(5000, min(dml, 500_000))
    except (TypeError, ValueError):
        pass
    raw_ls = data.get("log_sources", cfg.log_sources)
    if raw_ls is None:
        cfg.log_sources = []
    elif isinstance(raw_ls, list):
        cfg.log_sources = raw_ls
    else:
        cfg.log_sources = []
    cfg.geoip_db_path = data.get("geoip_db_path", cfg.geoip_db_path) or ""
    cfg.use_inspection_prometheus = bool(
        data.get("use_inspection_prometheus", cfg.use_inspection_prometheus)
    )
    cfg.prometheus_url_override = (
        data.get("prometheus_url_override", cfg.prometheus_url_override) or ""
    )
    cfg.blackbox_promql = data.get("blackbox_promql", cfg.blackbox_promql) or ""
    cfg.save()
    return Response({"msg": "saved"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def traffic_ingest(request):
    """
    Push NDJSON lines (or JSON {"lines": [...]}) into Redis buffer.
    Auth: Authorization: Bearer <TRAFFIC_INGEST_TOKEN>
    """
    token = os.environ.get("TRAFFIC_INGEST_TOKEN", "").strip()
    if not token:
        return Response({"error": "TRAFFIC_INGEST_TOKEN is not set"}, status=503)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        return Response({"error": "unauthorized"}, status=403)

    try:
        max_batch = int(os.environ.get("TRAFFIC_INGEST_MAX_BODY_LINES", "20000"))
    except ValueError:
        max_batch = 20_000
    max_batch = max(100, min(max_batch, 100_000))

    lines = []
    ct = (request.content_type or "").lower()
    if "application/json" in ct:
        body = request.data
        if isinstance(body, dict):
            raw = body.get("lines")
            if isinstance(raw, list):
                lines = [str(x) for x in raw if x is not None]
            elif isinstance(raw, str):
                lines = [ln for ln in raw.splitlines() if ln.strip()]
        elif isinstance(body, list):
            lines = [str(x) for x in body]
    else:
        raw = request.body.decode("utf-8", errors="replace")
        lines = [ln for ln in raw.splitlines() if ln.strip()]

    truncated = False
    if len(lines) > max_batch:
        lines = lines[:max_batch]
        truncated = True

    if not redis_buffer_configured():
        return Response({"error": "TRAFFIC_REDIS_URL not configured"}, status=503)

    cfg = TrafficDashboardConfig.load()
    ingest_source = (
        (request.GET.get("source") or "").strip()
        or (request.headers.get("X-Traffic-Source") or "").strip()
    )
    key = redis_key_for_ingest(cfg, ingest_source)
    n = push_raw_lines(lines, key, _redis_cap(cfg))
    return Response({"accepted": n, "truncated": truncated})
