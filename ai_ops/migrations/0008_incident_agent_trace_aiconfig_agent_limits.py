from django.db import migrations, models


def _clear_awaiting_evidence(apps, schema_editor):
    Incident = apps.get_model("ai_ops", "Incident")
    Incident.objects.filter(status="awaiting_evidence").update(status="open")


class Migration(migrations.Migration):

    dependencies = [
        ("ai_ops", "0007_evidence_first_and_platform_linkage"),
    ]

    operations = [
        migrations.RunPython(_clear_awaiting_evidence, migrations.RunPython.noop),
        migrations.AddField(
            model_name="incident",
            name="agent_trace",
            field=models.JSONField(
                default=list,
                help_text="SRE Agent iterations, tool calls and observations for UI/debug.",
            ),
        ),
        migrations.AddField(
            model_name="aiconfig",
            name="max_agent_iterations",
            field=models.IntegerField(
                default=12,
                help_text="Max ReAct LLM rounds per incident (cap 24).",
            ),
        ),
        migrations.AddField(
            model_name="aiconfig",
            name="max_tool_calls_per_incident",
            field=models.IntegerField(
                default=36,
                help_text="Max tool invocations per incident (cap 80).",
            ),
        ),
        migrations.AlterField(
            model_name="aiconfig",
            name="evidence_first_workflow",
            field=models.BooleanField(
                default=False,
                help_text="Deprecated: kept for DB compatibility; agent flow ignores this.",
            ),
        ),
        migrations.AlterField(
            model_name="incident",
            name="prefetched_metrics",
            field=models.JSONField(
                default=dict,
                help_text="Legacy: optional Prometheus snapshot; agent may leave empty.",
            ),
        ),
    ]
