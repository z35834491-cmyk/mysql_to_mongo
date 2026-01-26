from django.db import models

class MonitorTask(models.Model):
    name = models.CharField(max_length=100, default="New Monitor")
    enabled = models.BooleanField(default=False)
    
    # K8s Config
    k8s_namespace = models.CharField(max_length=255, default="default", help_text="K8s Namespace to watch")
    k8s_kubeconfig = models.TextField(blank=True, null=True, help_text="Kubeconfig content (YAML). If empty, use in-cluster config or default.")
    
    # S3 Config
    s3_archive_enabled = models.BooleanField(default=False, help_text="Enable archiving logs to S3")
    s3_bucket = models.CharField(max_length=255, blank=True, null=True)
    s3_region = models.CharField(max_length=50, default="us-east-1")
    s3_access_key = models.CharField(max_length=255, blank=True, null=True)
    s3_secret_key = models.CharField(max_length=255, blank=True, null=True)
    s3_endpoint = models.CharField(max_length=255, blank=True, null=True, help_text="Optional custom endpoint")
    
    retention_days = models.IntegerField(default=3, help_text="Days to keep logs locally before S3 upload")
    
    # Alerting
    alert_enabled = models.BooleanField(default=True, help_text="Global switch to enable/disable alert sending")
    slack_webhook_url = models.CharField(max_length=1024, blank=True, null=True)
    poll_interval_seconds = models.IntegerField(default=60)
    
    # Keyword Configs
    alert_keywords = models.JSONField(default=list, help_text="Threshold Alert: Error > Threshold in Window")
    immediate_keywords = models.JSONField(default=list, help_text="Immediate Alert: Alert on first occurrence")
    ignore_keywords = models.JSONField(default=list, help_text="Ignore: Do not process or alert")
    record_only_keywords = models.JSONField(default=list, help_text="Record Only: Log but do not alert")
    
    # Threshold Config
    alert_threshold_count = models.IntegerField(default=5, help_text="Count of errors to trigger alert")
    alert_threshold_window = models.IntegerField(default=60, help_text="Window in seconds for threshold counting")
    alert_silence_minutes = models.IntegerField(default=60, help_text="Silence duplicate alerts for N minutes")

    # Runtime State
    last_run = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    alerts_sent_count = models.IntegerField(default=0)
    alert_state = models.JSONField(default=dict, blank=True, help_text="Runtime state for alert silencing")

    def __str__(self):
        return self.name
