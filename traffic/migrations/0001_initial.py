from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TrafficDashboardConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                (
                    "access_log_path",
                    models.CharField(
                        blank=True,
                        help_text="Nginx access log file path (JSON or combined). Empty = env TRAFFIC_NGINX_ACCESS_LOG.",
                        max_length=1024,
                    ),
                ),
                (
                    "error_log_path",
                    models.CharField(
                        blank=True,
                        help_text="Optional: Nginx error log path (for future use).",
                        max_length=1024,
                    ),
                ),
                (
                    "log_format",
                    models.CharField(
                        choices=[("json", "JSON lines"), ("combined", "Nginx combined")],
                        default="json",
                        max_length=32,
                    ),
                ),
                (
                    "max_tail_bytes",
                    models.PositiveIntegerField(
                        default=5242880,
                        help_text="Max bytes read from end of access log per request.",
                    ),
                ),
                (
                    "geoip_db_path",
                    models.CharField(
                        blank=True,
                        help_text="MaxMind GeoLite2-City.mmdb or GeoIP2-City.mmdb. Empty = env TRAFFIC_GEOIP_DB or no GeoIP.",
                        max_length=1024,
                    ),
                ),
                (
                    "use_inspection_prometheus",
                    models.BooleanField(
                        default=True,
                        help_text="Use Inspection → Prometheus URL for Blackbox metrics.",
                    ),
                ),
                (
                    "prometheus_url_override",
                    models.CharField(
                        blank=True,
                        help_text="If set, overrides Inspection Prometheus for Blackbox queries only.",
                        max_length=1024,
                    ),
                ),
                (
                    "blackbox_promql",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional instant vector query for probes, e.g. probe_success. Empty = auto probe_success.",
                        max_length=512,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Traffic Dashboard Config",
            },
        ),
    ]
