from django.db import models


class TrafficDashboardConfig(models.Model):
    """Singleton (pk=1): Nginx log paths, GeoIP, Prometheus for Blackbox."""

    ACCESS_LOG_MODE_FILE = "file"
    ACCESS_LOG_MODE_REDIS = "redis"
    ACCESS_LOG_MODE_CHOICES = [
        (ACCESS_LOG_MODE_FILE, "Local file (pod / shared volume)"),
        (ACCESS_LOG_MODE_REDIS, "Remote ingest → Redis buffer (separate Nginx host)"),
    ]

    enabled = models.BooleanField(default=True)
    access_log_mode = models.CharField(
        max_length=16,
        default=ACCESS_LOG_MODE_FILE,
        choices=ACCESS_LOG_MODE_CHOICES,
        help_text="file = read access_log_path on Shark; redis = read lines pushed via POST /api/traffic/ingest (needs TRAFFIC_REDIS_URL).",
    )
    access_log_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Nginx access log file path (JSON or combined). Empty = env TRAFFIC_NGINX_ACCESS_LOG. Used when access_log_mode=file.",
    )
    error_log_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Optional: Nginx error log path (for future use).",
    )
    log_format = models.CharField(
        max_length=32,
        default="json",
        choices=[("json", "JSON lines"), ("combined", "Nginx combined")],
    )
    max_tail_bytes = models.PositiveIntegerField(
        default=5_242_880,
        help_text="Max bytes read from end of access log per request (file mode only).",
    )
    redis_log_key = models.CharField(
        max_length=256,
        default="traffic:access:lines",
        blank=True,
        help_text="Redis list key for buffered access log lines (redis mode).",
    )
    redis_max_lines = models.PositiveIntegerField(
        default=200_000,
        help_text="Max lines kept in Redis list (RPUSH + LTRIM keeps the most recent N lines).",
    )
    dashboard_fetch_max_lines = models.PositiveIntegerField(
        default=35_000,
        help_text="Traffic dashboard: max lines read from Redis list tail per snapshot (lower = faster; ingest cap unchanged).",
    )
    log_sources = models.JSONField(
        default=list,
        blank=True,
        help_text='Multi-site: [{"id":"api","label":"API","file_path":"/var/log/nginx/access_api.json.log","redis_key":""}, ...]. '
        "Redis mode: set redis_key per id; push with POST .../ingest?source=<id>. Empty = single legacy path / redis_log_key.",
    )
    geoip_db_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="MaxMind GeoIP2 / GeoLite2 City database path (.mmdb). Empty = env TRAFFIC_GEOIP_DB or no GeoIP.",
    )
    use_inspection_prometheus = models.BooleanField(
        default=True,
        help_text="Use Inspection → Prometheus URL for Blackbox metrics.",
    )
    prometheus_url_override = models.CharField(
        max_length=1024,
        blank=True,
        help_text="If set, overrides Inspection Prometheus for Blackbox queries only.",
    )
    blackbox_promql = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Optional instant vector query for probes, e.g. probe_success. Empty = auto probe_success.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Traffic Dashboard Config"
