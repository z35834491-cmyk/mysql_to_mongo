import os

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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
from .services.nginx_log import load_records


def _access_path(cfg: TrafficDashboardConfig) -> str:
    return (cfg.access_log_path or os.environ.get("TRAFFIC_NGINX_ACCESS_LOG", "") or "").strip()


def _load_enriched():
    cfg = TrafficDashboardConfig.load()
    if not cfg.enabled:
        return cfg, []
    path = _access_path(cfg)
    if not path:
        return cfg, []
    recs = load_records(path, cfg.log_format, cfg.max_tail_bytes)
    enrich_records(recs, cfg.geoip_db_path)
    return cfg, recs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_overview(request):
    range_key = request.GET.get("range", "24h")
    cfg, recs = _load_enriched()
    inspection = InspectionConfig.load()
    data = overview_kpis(recs, range_key)
    bb = fetch_blackbox_summary(cfg, inspection)
    data["blackbox"] = bb
    if bb.get("availability_pct") is not None:
        data["availability_pct"] = bb["availability_pct"]
    data["log_configured"] = bool(_access_path(cfg))
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_timeseries(request):
    range_key = request.GET.get("range", "24h")
    _, recs = _load_enriched()
    return Response(aggregate_timeseries(recs, range_key))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_geo(request):
    range_key = request.GET.get("range", "24h")
    granularity = request.GET.get("granularity", "country")
    country = request.GET.get("country", "")
    _, recs = _load_enriched()
    return Response(geo_aggregate(recs, range_key, granularity, country))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def traffic_top(request):
    range_key = request.GET.get("range", "24h")
    top_type = request.GET.get("type", "paths")
    limit = int(request.GET.get("limit", "10"))
    _, recs = _load_enriched()
    return Response(top_lists(recs, range_key, top_type, limit))


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
                "access_log_path": cfg.access_log_path,
                "error_log_path": cfg.error_log_path,
                "log_format": cfg.log_format,
                "max_tail_bytes": cfg.max_tail_bytes,
                "geoip_db_path": cfg.geoip_db_path,
                "use_inspection_prometheus": cfg.use_inspection_prometheus,
                "prometheus_url_override": cfg.prometheus_url_override,
                "blackbox_promql": cfg.blackbox_promql,
            }
        )
    data = request.data
    cfg.enabled = bool(data.get("enabled", cfg.enabled))
    cfg.access_log_path = data.get("access_log_path", cfg.access_log_path) or ""
    cfg.error_log_path = data.get("error_log_path", cfg.error_log_path) or ""
    cfg.log_format = data.get("log_format", cfg.log_format) or "json"
    cfg.max_tail_bytes = int(data.get("max_tail_bytes", cfg.max_tail_bytes))
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
