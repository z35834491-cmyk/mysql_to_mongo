from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("traffic", "0003_access_log_redis_buffer"),
    ]

    operations = [
        migrations.AddField(
            model_name="trafficdashboardconfig",
            name="log_sources",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Multi-site: [{"id":"api","label":"API","file_path":"/path/access_api.json.log","redis_key":""}, ...]. '
                "Redis mode: set redis_key per id; push with POST .../ingest?source=<id>. Empty = single legacy path / redis_log_key.",
            ),
        ),
    ]
