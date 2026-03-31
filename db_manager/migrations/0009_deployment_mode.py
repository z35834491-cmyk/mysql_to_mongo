from django.db import migrations, models


def forwards_redis_extra(apps, schema_editor):
    DatabaseConnection = apps.get_model("db_manager", "DatabaseConnection")
    for c in DatabaseConnection.objects.filter(type="redis"):
        extra = dict(c.extra_config or {})
        if extra.get("mode") == "cluster":
            c.deployment_mode = "cluster"
            c.save(update_fields=["deployment_mode"])
    DBInstance = apps.get_model("db_manager", "DBInstance")
    for inst in DBInstance.objects.filter(db_type="redis"):
        extra = dict(inst.extra_config or {})
        if extra.get("mode") == "cluster":
            inst.deployment_mode = "cluster"
            inst.save(update_fields=["deployment_mode"])


class Migration(migrations.Migration):

    dependencies = [
        ("db_manager", "0008_sqlexecutionpolicy_sqlapprovalorder_cc_users_json_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="databaseconnection",
            name="deployment_mode",
            field=models.CharField(
                choices=[("single", "Single"), ("cluster", "Cluster")],
                default="single",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="dbinstance",
            name="deployment_mode",
            field=models.CharField(
                choices=[("single", "Single"), ("cluster", "Cluster")],
                default="single",
                max_length=16,
            ),
        ),
        migrations.RunPython(forwards_redis_extra, migrations.RunPython.noop),
    ]
