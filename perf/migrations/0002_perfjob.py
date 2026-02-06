from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("perf", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerfJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_type", models.CharField(max_length=50)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("success", "Success"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("params", models.JSONField(default=dict)),
                ("result", models.JSONField(default=dict)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]

