from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_synctask_state_alter_synctask_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="synctask",
            name="turbo_cpu_limit",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_cpu_request",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_mem_limit",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_mem_request",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_no_limit",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_phase",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_pod_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="synctask",
            name="turbo_pod_namespace",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
