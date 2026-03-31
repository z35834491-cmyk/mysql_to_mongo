from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("traffic", "0004_trafficdashboardconfig_log_sources"),
    ]

    operations = [
        migrations.AddField(
            model_name="trafficdashboardconfig",
            name="dashboard_fetch_max_lines",
            field=models.PositiveIntegerField(
                default=35000,
                help_text="Traffic dashboard: max lines read from Redis list tail per snapshot (lower = faster; ingest cap unchanged).",
            ),
        ),
    ]
