from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0002_alter_trafficdashboardconfig_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="trafficdashboardconfig",
            name="access_log_mode",
            field=models.CharField(
                choices=[
                    ("file", "Local file (pod / shared volume)"),
                    ("redis", "Remote ingest → Redis buffer (separate Nginx host)"),
                ],
                default="file",
                help_text="file = read access_log_path on Shark; redis = read lines pushed via POST /api/traffic/ingest (needs TRAFFIC_REDIS_URL).",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="trafficdashboardconfig",
            name="redis_log_key",
            field=models.CharField(
                blank=True,
                default="traffic:access:lines",
                help_text="Redis list key for buffered access log lines (redis mode).",
                max_length=256,
            ),
        ),
        migrations.AddField(
            model_name="trafficdashboardconfig",
            name="redis_max_lines",
            field=models.PositiveIntegerField(
                default=200000,
                help_text="Max lines kept in Redis list (RPUSH + LTRIM keeps the most recent N lines).",
            ),
        ),
        migrations.AlterField(
            model_name="trafficdashboardconfig",
            name="access_log_path",
            field=models.CharField(
                blank=True,
                help_text="Nginx access log file path (JSON or combined). Empty = env TRAFFIC_NGINX_ACCESS_LOG. Used when access_log_mode=file.",
                max_length=1024,
            ),
        ),
        migrations.AlterField(
            model_name="trafficdashboardconfig",
            name="max_tail_bytes",
            field=models.PositiveIntegerField(
                default=5242880,
                help_text="Max bytes read from end of access log per request (file mode only).",
            ),
        ),
        migrations.AlterField(
            model_name="trafficdashboardconfig",
            name="geoip_db_path",
            field=models.CharField(
                blank=True,
                help_text="MaxMind GeoIP2 / GeoLite2 City database path (.mmdb). Empty = env TRAFFIC_GEOIP_DB or no GeoIP.",
                max_length=1024,
            ),
        ),
    ]
