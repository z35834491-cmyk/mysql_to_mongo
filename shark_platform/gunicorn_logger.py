"""
Gunicorn access logger: skip high-frequency endpoints so container stdout stays readable.
"""
from gunicorn.glogging import Logger


def _quiet_path(path: str) -> bool:
    if path == "/api/system/health":
        return True
    if path.startswith("/api/traffic/ingest"):
        return True
    if path.startswith("/api/tasks/status"):
        return True
    return False


class FilteredAccessLogger(Logger):
    def access(self, resp, req, environ, request_time):
        path = environ.get("PATH_INFO") or ""
        if _quiet_path(path):
            return
        super().access(resp, req, environ, request_time)
