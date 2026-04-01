"""
Buffer per-minute traffic counters in Redis during ingest; flush to TrafficMinuteRollup via management command / cron.

Requires TRAFFIC_REDIS_URL. Enable ingest-side append with TRAFFIC_ROLLUP_ENABLED=1.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from ..models import TrafficMinuteRollup
from .redis_log_buffer import traffic_redis_client

logger = logging.getLogger(__name__)

ROLLUP_DIRTY = "traffic:rollup:dirty"
ROLLUP_PREFIX = "traffic:rollup:"
# Flush only minutes strictly older than (now_floor - lag) so late-arriving lines land in the same Redis bucket.
FLUSH_LAG_MINUTES = 2
MAX_LAT_SAMPLES = 25_000
MAX_PATH_KEYS = 4_000


def _norm_source(source_id: str) -> str:
    s = (source_id or "").strip() or "default"
    return s[:64]


def _esc(s: str) -> str:
    return s.replace(":", "_")


def _hkey(epoch: int, src: str) -> str:
    return f"{ROLLUP_PREFIX}h:{epoch}:{_esc(src)}"


def _latkey(epoch: int, src: str) -> str:
    return f"{ROLLUP_PREFIX}lat:{epoch}:{_esc(src)}"


def _urikey(epoch: int, src: str) -> str:
    return f"{ROLLUP_PREFIX}uri:{epoch}:{_esc(src)}"


def _geokey(epoch: int, src: str) -> str:
    return f"{ROLLUP_PREFIX}geo:{epoch}:{_esc(src)}"


def _dirty_member(epoch: int, src: str) -> str:
    return f"{epoch}\x1f{src}"


def rollup_enabled() -> bool:
    return os.environ.get("TRAFFIC_ROLLUP_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def rollup_ingest_append(records: List[Dict[str, Any]], source_id: str) -> None:
    """Called from traffic_ingest after lines are accepted. Best-effort; never raises."""
    if not rollup_enabled():
        return
    r = traffic_redis_client()
    if not r or not records:
        return
    src = _norm_source(source_id)
    by_min: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        try:
            ts = float(rec.get("ts") or 0)
        except (TypeError, ValueError):
            continue
        if ts <= 0:
            continue
        ep = int(ts // 60)
        by_min[ep].append(rec)

    try:
        for ep, group in by_min.items():
            hk, lk, uk, gk = _hkey(ep, src), _latkey(ep, src), _urikey(ep, src), _geokey(ep, src)
            s2 = s4 = s5 = 0
            sl = 0.0
            nl = 0
            pipe = r.pipeline(transaction=False)
            pipe.sadd(ROLLUP_DIRTY, _dirty_member(ep, src))
            for rec in group:
                st = int(rec.get("status") or 0)
                if 200 <= st < 400:
                    s2 += 1
                elif 400 <= st < 500:
                    s4 += 1
                elif st >= 500:
                    s5 += 1
                lat = rec.get("request_time_ms")
                if lat is not None:
                    try:
                        lf = float(lat)
                        pipe.rpush(lk, str(lf))
                        sl += lf
                        nl += 1
                    except (TypeError, ValueError):
                        pass
                uri = (rec.get("request_uri") or "/")[:512]
                pipe.hincrby(uk, uri, 1)
                cc = (rec.get("country_code") or "??")[:8]
                pipe.hincrby(gk, cc, 1)
            n = len(group)
            pipe.hincrby(hk, "req", n)
            pipe.hincrby(hk, "s2", s2)
            pipe.hincrby(hk, "s4", s4)
            pipe.hincrby(hk, "s5", s5)
            pipe.hincrby(hk, "sum_lat", int(sl))
            pipe.hincrby(hk, "n_lat", nl)
            pipe.ltrim(lk, -MAX_LAT_SAMPLES, -1)
            pipe.execute()
    except Exception as e:
        logger.warning("rollup_ingest_append failed: %s", e)


def _parse_dirty(m: str) -> Optional[Tuple[int, str]]:
    try:
        a, _, b = m.partition("\x1f")
        return int(a), b
    except (ValueError, TypeError):
        return None


def _flush_one_redis(r, epoch: int, src: str) -> bool:
    hk, lk, uk, gk = _hkey(epoch, src), _latkey(epoch, src), _urikey(epoch, src), _geokey(epoch, src)
    h = r.hgetall(hk)
    if not h:
        for k in (hk, lk, uk, gk):
            r.delete(k)
        return False
    try:
        req = int(h.get("req") or 0)
        s2 = int(h.get("s2") or 0)
        s4 = int(h.get("s4") or 0)
        s5 = int(h.get("s5") or 0)
        sum_lat = int(h.get("sum_lat") or 0)
        n_lat = int(h.get("n_lat") or 0)
    except (TypeError, ValueError):
        req = s2 = s4 = s5 = sum_lat = n_lat = 0
    raw_lats = r.lrange(lk, 0, -1)
    lats: List[float] = []
    for x in raw_lats:
        try:
            lats.append(float(x))
        except (TypeError, ValueError):
            pass
    p50 = p95 = p99 = None
    if lats:
        try:
            import numpy as np

            arr = np.array(lats, dtype=float)
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))
            p99 = float(np.percentile(arr, 99))
        except Exception:
            pass

    uri_h = r.hgetall(uk) or {}
    path_counts = sorted(
        ((k, int(v)) for k, v in uri_h.items() if v),
        key=lambda x: -x[1],
    )[:20]
    top_paths = [{"path": p, "requests": n} for p, n in path_counts]

    geo_h = r.hgetall(gk) or {}
    geo_counts = {k: int(v) for k, v in geo_h.items() if v}

    bt = datetime.fromtimestamp(epoch * 60, tz=timezone.utc)

    with transaction.atomic():
        obj, _created = TrafficMinuteRollup.objects.select_for_update().get_or_create(
            bucket_start=bt,
            source_id=src,
            defaults={
                "requests": 0,
                "sum_latency_ms": 0,
                "count_latency": 0,
                "status_2xx": 0,
                "status_4xx": 0,
                "status_5xx": 0,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "geo_counts": {},
                "top_paths": [],
            },
        )
        obj.requests += req
        obj.status_2xx += s2
        obj.status_4xx += s4
        obj.status_5xx += s5
        obj.sum_latency_ms += max(0, sum_lat)
        obj.count_latency += max(0, n_lat)
        # Percentiles from one Redis flush only; later flushes for the same minute (late lines) update counts/paths/geo only.
        if p50 is not None and obj.p50_ms is None:
            obj.p50_ms = p50
            obj.p95_ms = p95
            obj.p99_ms = p99
        gc = dict(obj.geo_counts or {})
        for k, v in geo_counts.items():
            gc[k] = gc.get(k, 0) + v
        obj.geo_counts = gc
        tp_m = {p["path"]: p["requests"] for p in (obj.top_paths or [])}
        for p, n in path_counts:
            tp_m[p] = tp_m.get(p, 0) + n
        merged_paths = sorted(tp_m.items(), key=lambda x: -x[1])[:20]
        obj.top_paths = [{"path": a, "requests": b} for a, b in merged_paths]
        obj.save()

    try:
        from .clickhouse_rollups import insert_traffic_minute_rollup_from_model

        insert_traffic_minute_rollup_from_model(obj)
    except Exception as e:
        logger.warning("ClickHouse mirror after rollup flush skipped: %s", e)

    pipe = r.pipeline(transaction=False)
    pipe.delete(hk, lk, uk, gk)
    pipe.srem(ROLLUP_DIRTY, _dirty_member(epoch, src))
    pipe.execute()
    return True


def flush_closed_rollups() -> int:
    """Flush Redis buffers for completed minutes into Postgres. Safe to run every minute (cron/Celery)."""
    r = traffic_redis_client()
    if not r:
        return 0
    now_m = int(time.time()) // 60
    cutoff = now_m - FLUSH_LAG_MINUTES
    try:
        members = list(r.smembers(ROLLUP_DIRTY))
    except Exception as e:
        logger.warning("flush_closed_rollups smembers: %s", e)
        return 0
    flushed = 0
    for m in members:
        parsed = _parse_dirty(m)
        if not parsed:
            try:
                r.srem(ROLLUP_DIRTY, m)
            except Exception:
                pass
            continue
        ep, src = parsed
        if ep > cutoff:
            continue
        try:
            if _flush_one_redis(r, ep, src):
                flushed += 1
        except Exception as e:
            logger.warning("flush rollup ep=%s src=%s: %s", ep, src, e)
    return flushed
