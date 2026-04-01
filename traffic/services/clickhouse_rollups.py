"""
ClickHouse：分钟聚合长期存储（与 Postgres 双写：flush 后写入）。

Env（CLICKHOUSE_HOST 未设置则整模块不启用）：
  CLICKHOUSE_HOST, CLICKHOUSE_PORT (8123), CLICKHOUSE_USER, CLICKHOUSE_PASSWORD,
  CLICKHOUSE_DATABASE (traffic), CLICKHOUSE_ROLLUP_TABLE (traffic_minute_rollup)

DDL：infra/clickhouse/traffic_minute_rollup.sql
K8s：infra/kubernetes/middleware-system/clickhouse-traffic.yaml
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def clickhouse_configured() -> bool:
    return bool((os.environ.get("CLICKHOUSE_HOST") or "").strip())


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _ch_client():
    import clickhouse_connect

    host = os.environ.get("CLICKHOUSE_HOST", "").strip()
    port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    user = (os.environ.get("CLICKHOUSE_USER") or "default").strip()
    password = os.environ.get("CLICKHOUSE_PASSWORD") or ""
    return clickhouse_connect.get_client(host=host, port=port, username=user, password=password)


def insert_traffic_minute_rollup_from_model(obj: Any) -> None:
    """flush 落库 Postgres 后调用；失败只打日志，不影响主流程。"""
    if not clickhouse_configured():
        return
    table = (os.environ.get("CLICKHOUSE_ROLLUP_TABLE") or "traffic_minute_rollup").strip()
    database = (os.environ.get("CLICKHOUSE_DATABASE") or "traffic").strip()
    if not _TABLE_RE.match(table) or not _TABLE_RE.match(database):
        return
    try:
        client = _ch_client()
    except Exception as e:
        logger.warning("ClickHouse client failed: %s", e)
        return

    bt = _utc_naive(obj.bucket_start)
    ver = datetime.now(timezone.utc).replace(tzinfo=None)
    geo_s = json.dumps(obj.geo_counts or {}, ensure_ascii=False)
    paths_s = json.dumps(obj.top_paths or [], ensure_ascii=False)

    row = [
        bt,
        str(obj.source_id or ""),
        int(obj.requests or 0),
        int(obj.sum_latency_ms or 0),
        int(obj.count_latency or 0),
        int(obj.status_2xx or 0),
        int(obj.status_4xx or 0),
        int(obj.status_5xx or 0),
        obj.p50_ms,
        obj.p95_ms,
        obj.p99_ms,
        geo_s,
        paths_s,
        ver,
    ]
    cols = [
        "bucket_start",
        "source_id",
        "requests",
        "sum_latency_ms",
        "count_latency",
        "status_2xx",
        "status_4xx",
        "status_5xx",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "geo_counts",
        "top_paths",
        "ver",
    ]
    try:
        client.insert(table, [row], database=database, column_names=cols)
    except Exception as e:
        logger.warning("ClickHouse insert traffic_minute_rollup failed: %s", e)


def query_minute_rollups_clickhouse(
    start: datetime, end: datetime, source_id: str
) -> Optional[List[Any]]:
    """
    None = 未配置或查询异常；[] = 已配置但无行。
    使用 ReplacingMergeTree FINAL 折叠同键多版本。
    """
    if not clickhouse_configured():
        return None

    table = (os.environ.get("CLICKHOUSE_ROLLUP_TABLE") or "traffic_minute_rollup").strip()
    database = (os.environ.get("CLICKHOUSE_DATABASE") or "traffic").strip()
    if not _TABLE_RE.match(table) or not _TABLE_RE.match(database):
        logger.warning("Invalid CLICKHOUSE database/table")
        return None

    sid = (source_id or "").strip()
    start_n = _utc_naive(start)
    end_n = _utc_naive(end)
    start_s = start_n.strftime("%Y-%m-%d %H:%M:%S")
    end_s = end_n.strftime("%Y-%m-%d %H:%M:%S")

    sql = f"""
        SELECT bucket_start, source_id, requests, sum_latency_ms, count_latency,
               status_2xx, status_4xx, status_5xx,
               p50_ms, p95_ms, p99_ms, geo_counts, top_paths
        FROM `{database}`.`{table}` FINAL
        WHERE bucket_start >= toDateTime('{start_s}')
          AND bucket_start < toDateTime('{end_s}')
    """
    if sid and sid != "all":
        sid_esc = sid.replace("\\", "\\\\").replace("'", "''")
        sql += f" AND source_id = '{sid_esc}'"
    sql += " ORDER BY bucket_start, source_id"

    try:
        client = _ch_client()
    except ImportError:
        logger.warning("clickhouse-connect not installed")
        return None
    except Exception as e:
        logger.warning("ClickHouse client failed: %s", e)
        return None
    try:
        result = client.query(sql)
    except Exception as e:
        logger.warning("ClickHouse rollup query failed: %s", e)
        return None

    rows: List[Any] = []
    for tup in result.result_rows:
        (
            bucket_start,
            src,
            requests,
            sum_latency_ms,
            count_latency,
            s2,
            s4,
            s5,
            p50,
            p95,
            p99,
            geo_raw,
            paths_raw,
        ) = tup
        geo_counts: dict = {}
        top_paths: List[dict] = []
        try:
            if isinstance(geo_raw, str) and geo_raw.strip():
                geo_counts = json.loads(geo_raw)
            elif isinstance(geo_raw, dict):
                geo_counts = geo_raw
        except json.JSONDecodeError:
            pass
        try:
            if isinstance(paths_raw, str) and paths_raw.strip():
                top_paths = json.loads(paths_raw)
            elif isinstance(paths_raw, list):
                top_paths = paths_raw
        except json.JSONDecodeError:
            pass
        bt = bucket_start
        if isinstance(bt, datetime) and bt.tzinfo is None:
            bt = bt.replace(tzinfo=timezone.utc)
        rows.append(
            SimpleNamespace(
                bucket_start=bt,
                source_id=str(src or ""),
                requests=int(requests or 0),
                sum_latency_ms=int(sum_latency_ms or 0),
                count_latency=int(count_latency or 0),
                status_2xx=int(s2 or 0),
                status_4xx=int(s4 or 0),
                status_5xx=int(s5 or 0),
                p50_ms=float(p50) if p50 is not None else None,
                p95_ms=float(p95) if p95 is not None else None,
                p99_ms=float(p99) if p99 is not None else None,
                geo_counts=geo_counts,
                top_paths=top_paths,
            )
        )
    return rows
