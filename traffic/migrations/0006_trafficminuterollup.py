from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0005_trafficdashboardconfig_dashboard_fetch_max_lines"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrafficMinuteRollup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "bucket_start",
                    models.DateTimeField(db_index=True, help_text="UTC minute start (inclusive)."),
                ),
                (
                    "source_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        help_text="Matches ingest ?source= / X-Traffic-Source; empty = default.",
                        max_length=64,
                    ),
                ),
                ("requests", models.PositiveIntegerField(default=0)),
                ("sum_latency_ms", models.PositiveBigIntegerField(default=0)),
                ("count_latency", models.PositiveIntegerField(default=0)),
                ("status_2xx", models.PositiveIntegerField(default=0)),
                ("status_4xx", models.PositiveIntegerField(default=0)),
                ("status_5xx", models.PositiveIntegerField(default=0)),
                ("p50_ms", models.FloatField(blank=True, null=True)),
                ("p95_ms", models.FloatField(blank=True, null=True)),
                ("p99_ms", models.FloatField(blank=True, null=True)),
                ("geo_counts", models.JSONField(blank=True, default=dict)),
                ("top_paths", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["bucket_start", "source_id"],
                "unique_together": {("bucket_start", "source_id")},
            },
        ),
    ]
