from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ClusterConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("kube_config", models.TextField(blank=True, default="")),
                ("prometheus_url", models.URLField(blank=True, default="")),
                ("tempo_url", models.URLField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="LoadTestReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="default", max_length=100)),
                ("service_name", models.CharField(max_length=200)),
                ("test_id", models.CharField(db_index=True, max_length=100)),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField()),
                ("max_qps_reached", models.IntegerField(default=0)),
                ("qps_per_core", models.FloatField(default=0.0)),
                ("cpu_limit_cores", models.FloatField(default=0.0)),
                ("recommended_cpu_cores", models.FloatField(default=0.0)),
                ("confidence", models.FloatField(default=0.0)),
                ("ai_suggestions", models.TextField(blank=True, default="")),
                ("report_markdown", models.TextField(blank=True, default="")),
                ("raw_metrics", models.JSONField(default=dict)),
                ("raw_traces", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cluster", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="load_test_reports", to="perf.clusterconfig")),
            ],
        ),
        migrations.CreateModel(
            name="ServiceProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="default", max_length=100)),
                ("service_name", models.CharField(max_length=200)),
                ("qps_per_core", models.FloatField(default=0.0)),
                ("recommended_cpu_cores", models.FloatField(default=0.0)),
                ("bottleneck_type", models.CharField(default="unknown", max_length=20)),
                ("confidence", models.FloatField(default=0.0)),
                ("ai_suggestions", models.TextField(blank=True, default="")),
                ("analysis_meta", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cluster", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_profiles", to="perf.clusterconfig")),
            ],
            options={"unique_together": {("cluster", "namespace", "service_name")}},
        ),
    ]

