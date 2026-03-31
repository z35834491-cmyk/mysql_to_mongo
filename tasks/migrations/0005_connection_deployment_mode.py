from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0004_synctask_turbo_shard_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="connection",
            name="deployment_mode",
            field=models.CharField(
                choices=[("single", "Single"), ("cluster", "Cluster")],
                default="single",
                max_length=16,
            ),
        ),
    ]
