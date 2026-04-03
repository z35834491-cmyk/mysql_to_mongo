from django.db import migrations, models


def _backfill_last_received(apps, schema_editor):
    Incident = apps.get_model("ai_ops", "Incident")
    for inc in Incident.objects.filter(last_received_at__isnull=True).iterator(chunk_size=500):
        ts = inc.last_analyzed_at or inc.created_at
        if ts:
            Incident.objects.filter(pk=inc.pk).update(last_received_at=ts)


class Migration(migrations.Migration):

    dependencies = [
        ("ai_ops", "0008_incident_agent_trace_aiconfig_agent_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="last_received_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="最近一次 Alertmanager 推送 firing 的时间（用于列表排序，与 created_at 解耦）",
                null=True,
            ),
        ),
        migrations.RunPython(_backfill_last_received, migrations.RunPython.noop),
    ]
