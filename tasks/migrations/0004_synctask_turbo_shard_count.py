from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0003_synctask_turbo_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="synctask",
            name="turbo_shard_count",
            field=models.IntegerField(default=1),
        ),
    ]
