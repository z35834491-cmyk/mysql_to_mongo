from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_ops", "0006_analysisreport_k8s_events_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiconfig",
            name="evidence_first_workflow",
            field=models.BooleanField(
                default=True,
                help_text="Phase 1: metrics + checklist only; final LLM after user pastes command outputs.",
            ),
        ),
        migrations.AddField(
            model_name="aiconfig",
            name="final_prompt_template",
            field=models.TextField(
                blank=True,
                default="",
                help_text="User pasted evidence pass; placeholders: {alert_name},{raw_data},{metrics},{logs},{evidence_checklist},{user_evidence}",
            ),
        ),
        migrations.AddField(
            model_name="analysisreport",
            name="platform_linkage",
            field=models.TextField(
                default="",
                help_text="与监控/发布/容量等平台动作的联动建议",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="evidence_checklist",
            field=models.JSONField(
                default=list,
                help_text="Suggested commands and hints; operators paste outputs in UI.",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="prefetched_metrics",
            field=models.JSONField(
                default=dict,
                help_text="Prometheus snapshot from phase-1 for charts before final report.",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="user_evidence",
            field=models.JSONField(
                default=dict,
                help_text="Map step_id -> pasted command output from operator.",
            ),
        ),
        migrations.AlterField(
            model_name="incident",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("analyzing", "Analyzing"),
                    ("awaiting_evidence", "Awaiting user evidence"),
                    ("analyzed", "Analyzed"),
                    ("resolved", "Resolved"),
                ],
                default="open",
                max_length=50,
            ),
        ),
    ]
