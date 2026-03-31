from django.db import models


class TrafficDashboardConfig(models.Model):
    """Singleton (pk=1): Nginx log paths, GeoIP, Prometheus for Blackbox."""

    enabled = models.BooleanField(default=True)
    access_log_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Nginx access log file path (JSON or combined). Empty = env TRAFFIC_NGINX_ACCESS_LOG.",
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
        help_text="Max bytes read from end of access log per request.",
    )
    geoip_db_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="MaxMind GeoLite2-City.mmdb or GeoIP2-City.mmdb. Empty = env TRAFFIC_GEOIP_DB or no GeoIP.",
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
