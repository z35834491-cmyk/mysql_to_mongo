from django.db import models


class ClusterConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    kube_config = models.TextField(blank=True, default="")
    prometheus_url = models.URLField(blank=True, default="")
    tempo_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ServiceProfile(models.Model):
    cluster = models.ForeignKey(ClusterConfig, on_delete=models.CASCADE, related_name="service_profiles")
    namespace = models.CharField(max_length=100, default="default")
    service_name = models.CharField(max_length=200)

    qps_per_core = models.FloatField(default=0.0)
    recommended_cpu_cores = models.FloatField(default=0.0)
    bottleneck_type = models.CharField(max_length=20, default="unknown")
    confidence = models.FloatField(default=0.0)
    ai_suggestions = models.TextField(blank=True, default="")
    analysis_meta = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("cluster", "namespace", "service_name")

    def __str__(self):
        return f"{self.cluster.name}:{self.namespace}/{self.service_name}"


class LoadTestReport(models.Model):
    cluster = models.ForeignKey(ClusterConfig, on_delete=models.CASCADE, related_name="load_test_reports")
    namespace = models.CharField(max_length=100, default="default")
    service_name = models.CharField(max_length=200)
    test_id = models.CharField(max_length=100, db_index=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    max_qps_reached = models.IntegerField(default=0)

    qps_per_core = models.FloatField(default=0.0)
    cpu_limit_cores = models.FloatField(default=0.0)
    recommended_cpu_cores = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)

    ai_suggestions = models.TextField(blank=True, default="")
    report_markdown = models.TextField(blank=True, default="")
    raw_metrics = models.JSONField(default=dict)
    raw_traces = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.test_id} {self.cluster.name}:{self.namespace}/{self.service_name}"


class PerfJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    job_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    params = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.job_type}:{self.id}({self.status})"
