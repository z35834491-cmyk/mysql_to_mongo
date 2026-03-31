import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_reader = None
_reader_path = None


def _geoip_path(configured: str) -> str:
    return (
        (configured or "").strip()
        or os.environ.get("TRAFFIC_GEOIP_DB", "").strip()
    )


def _get_reader(path: str):
    global _reader, _reader_path
    if not path:
        return None
    if _reader is not None and _reader_path == path:
        return _reader
    try:
        import geoip2.database
    except ImportError:
        logger.debug("geoip2 not installed; GeoIP disabled")
        return None
    try:
        _reader = geoip2.database.Reader(path)
        _reader_path = path
        return _reader
    except OSError as e:
        logger.warning("GeoIP Reader open failed %s: %s", path, e)
        _reader = None
        _reader_path = None
        return None


def lookup_ip(ip: str, geoip_db_path: str) -> Dict[str, Optional[str]]:
    """Return country_code, country_name, subdivision, lat, lng hints."""
    result = {
        "country_code": None,
        "country_name": None,
        "subdivision": None,
        "lat": None,
        "lng": None,
    }
    if not ip:
        result["country_code"] = "??"
        return result
    if ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168."):
        result["country_code"] = "LAN"
        result["country_name"] = "Private"
        return result
    parts = ip.split(".")
    if len(parts) == 4 and parts[0] == "172":
        try:
            second = int(parts[1])
            if 16 <= second <= 31:
                result["country_code"] = "LAN"
                result["country_name"] = "Private"
                return result
        except ValueError:
            pass
    path = _geoip_path(geoip_db_path)
    reader = _get_reader(path)
    if reader is None:
        result["country_code"] = "??"
        result["country_name"] = "Unknown"
        return result
    try:
        r = reader.city(ip)
        iso = r.country.iso_code
        result["country_code"] = iso
        result["country_name"] = r.country.name or iso
        if r.subdivisions:
            result["subdivision"] = r.subdivisions[0].name
        if r.location.latitude is not None:
            result["lat"] = float(r.location.latitude)
        if r.location.longitude is not None:
            result["lng"] = float(r.location.longitude)
    except Exception:
        result["country_code"] = "??"
        result["country_name"] = "Unknown"
    return result


def enrich_records(records, geoip_db_path: str):
    from .geo_centroids import centroid_for_country

    for rec in records:
        geo = lookup_ip(rec.get("remote_addr") or "", geoip_db_path)
        rec["country_code"] = geo["country_code"]
        rec["country_name"] = geo["country_name"]
        rec["subdivision"] = geo["subdivision"]
        if geo.get("lat") is not None:
            rec["lat"] = geo["lat"]
            rec["lng"] = geo["lng"]
        else:
            c = centroid_for_country(geo["country_code"] or "")
            if c:
                rec["lat"], rec["lng"] = c[0], c[1]
            else:
                rec["lat"], rec["lng"] = 0.0, 0.0
