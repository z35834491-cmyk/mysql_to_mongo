import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


def _prom_base(cfg, inspection) -> str:
    if (cfg.prometheus_url_override or "").strip():
        return cfg.prometheus_url_override.strip().rstrip("/")
    if cfg.use_inspection_prometheus and inspection and (inspection.prometheus_url or "").strip():
        return inspection.prometheus_url.strip().rstrip("/")
    return ""


def query_instant(base: str, promql: str, timeout: float = 8.0) -> List[Dict[str, Any]]:
    if not base or not promql:
        return []
    try:
        r = requests.get(
            f"{base}/api/v1/query",
            params={"query": promql},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json().get("data", {}).get("result", [])
        return data
    except requests.RequestException as e:
        logger.warning("Prometheus query failed: %s", e)
        return []


def fetch_blackbox_summary(cfg, inspection) -> Dict[str, Any]:
    base = _prom_base(cfg, inspection)
    promql = (cfg.blackbox_promql or "").strip() or "probe_success"
    vectors = query_instant(base, promql)
    targets = []
    up_count = 0
    for v in vectors:
        m = v.get("metric", {})
        val = v.get("value", [0, "0"])[1]
        try:
            up = float(val) >= 1.0
        except (TypeError, ValueError):
            up = False
        if up:
            up_count += 1
        inst = m.get("instance") or m.get("target") or m.get("probe") or "unknown"
        name = m.get("job") or m.get("service") or inst
        targets.append(
            {
                "name": name,
                "instance": inst,
                "up": up,
                "raw_value": val,
            }
        )

    lat_vecs = query_instant(base, "probe_duration_seconds") if base else []
    lat_by_inst = {}
    for v in lat_vecs:
        m = v.get("metric", {})
        inst = m.get("instance") or ""
        try:
            lat_by_inst[inst] = float(v.get("value", [0, "0"])[1]) * 1000.0
        except (TypeError, ValueError):
            pass
    for t in targets:
        t["avg_latency_ms"] = round(lat_by_inst.get(t["instance"], 0.0), 2)

    n = len(targets)
    avail = (up_count / n * 100.0) if n else None

    return {
        "refreshed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prometheus_configured": bool(base),
        "targets": targets,
        "availability_pct": round(avail, 3) if avail is not None else None,
    }
