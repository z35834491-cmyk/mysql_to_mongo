import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Nginx combined-ish (request_time at end is common custom format)
_COMBINED_RE = re.compile(
    r'^(?P<remote_addr>\S+) \S+ \S+ \[(?P<time_local>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<request_uri>\S+)(?: HTTP/[^"]+)?" (?P<status>\d{3}) (?P<body_bytes>\S+)'
    r'(?: "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"(?: (?P<request_time>[\d.]+))?)?'
)

_TIME_LOCAL_FMT = "%d/%b/%Y:%H:%M:%S %z"


def read_log_tail(path: str, max_bytes: int) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            start = max(0, size - max_bytes)
            f.seek(start)
            raw = f.read()
        text = raw.decode("utf-8", errors="replace")
        if start > 0 and text:
            text = text.split("\n", 1)[-1]
        return [ln for ln in text.splitlines() if ln.strip()]
    except OSError as e:
        logger.warning("read_log_tail %s: %s", path, e)
        return []


def _parse_time_local(s: str) -> Optional[float]:
    try:
        dt = datetime.strptime(s, _TIME_LOCAL_FMT)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def parse_log_line(line: str, log_format: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    if log_format == "json":
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        return normalize_json_record(obj)
    m = _COMBINED_RE.match(line)
    if not m:
        return None
    gd = m.groupdict()
    ts = _parse_time_local(gd["time_local"] or "")
    if ts is None:
        ts = datetime.now(timezone.utc).timestamp()
    try:
        status = int(gd["status"])
    except (TypeError, ValueError):
        status = 0
    rt = gd.get("request_time")
    request_time_ms = float(rt) * 1000 if rt else 0.0
    return {
        "ts": ts,
        "status": status,
        "request_time_ms": request_time_ms,
        "request_uri": gd.get("request_uri") or "/",
        "remote_addr": gd.get("remote_addr") or "",
    }


def normalize_json_record(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map common Nginx JSON log keys to internal shape."""
    ts = None
    if "msec" in obj:
        try:
            ts = float(str(obj["msec"]).split(".")[0])
        except (TypeError, ValueError):
            pass
    if ts is None and "time" in obj:
        v = obj["time"]
        if isinstance(v, (int, float)):
            ts = float(v)
        elif isinstance(v, str):
            try:
                ts = float(v)
            except ValueError:
                if "T" in v:
                    try:
                        ts = datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        pass
    if ts is None and "time_local" in obj:
        ts = _parse_time_local(str(obj["time_local"]))
    if ts is None and "@timestamp" in obj:
        try:
            ts = datetime.fromisoformat(
                str(obj["@timestamp"]).replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    if ts is None:
        ts = datetime.now(timezone.utc).timestamp()

    status = obj.get("status") or obj.get("response_status") or 0
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0

    rt = obj.get("request_time") or obj.get("request_time_ms")
    if rt is not None:
        try:
            request_time_ms = float(rt) * 1000 if float(rt) < 1000 else float(rt)
        except (TypeError, ValueError):
            request_time_ms = 0.0
    else:
        request_time_ms = 0.0

    uri = (
        obj.get("request_uri")
        or obj.get("uri")
        or obj.get("path")
        or "/"
    )
    if isinstance(uri, str) and "?" in uri:
        uri = uri.split("?", 1)[0]

    addr = (
        obj.get("remote_addr")
        or obj.get("client_ip")
        or obj.get("http_x_forwarded_for", "").split(",")[0].strip()
        or ""
    )

    return {
        "ts": float(ts),
        "status": status,
        "request_time_ms": request_time_ms,
        "request_uri": str(uri)[:2048],
        "remote_addr": str(addr).strip()[:64],
    }


def records_from_lines(lines: List[str], log_format: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ln in lines:
        rec = parse_log_line(ln, log_format)
        if rec:
            out.append(rec)
    return out


def load_records(
    access_path: str, log_format: str, max_tail_bytes: int
) -> List[Dict[str, Any]]:
    lines = read_log_tail(access_path, max_tail_bytes)
    return records_from_lines(lines, log_format)
