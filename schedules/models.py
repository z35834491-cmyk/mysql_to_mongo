from django.db import models
import uuid

class Schedule(models.Model):
    rule_id = models.BigIntegerField(null=True, blank=True, help_text="Source Rule ID")
    shift_date = models.DateField(help_text="Date of the shift")
    start_time = models.CharField(max_length=20, default="09:00:00", help_text="Start Time")
    end_time = models.CharField(max_length=20, default="18:00:00", help_text="End Time")
    staff_ids = models.CharField(max_length=255, blank=True, help_text="Staff IDs string")
    staff_list = models.JSONField(default=list, blank=True, help_text="List of staff info objects")
    
    # Keep legacy fields just in case or for compatibility, but maybe mapped
    # staff_name can be derived from staff_list for display if needed
    
    create_time = models.CharField(max_length=50, blank=True, help_text="Creation Time from source")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-shift_date', 'start_time']
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'

    def __str__(self):
        return f"{self.shift_date} {self.start_time}-{self.end_time}"


class PhoneAlertConfig(models.Model):
    public_url = models.CharField(max_length=255, blank=True, default='')
    slack_webhook_url = models.CharField(max_length=500, blank=True, default='')
    external_api_url = models.CharField(max_length=500, blank=True, default='')
    external_api_username = models.CharField(max_length=255, blank=True, default='')
    external_api_password = models.CharField(max_length=255, blank=True, default='')
    incoming_token = models.CharField(max_length=255, blank=True, default='')
    auto_complete_minutes = models.IntegerField(default=30)
    oncall_slack_map = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PhoneAlert(models.Model):
    STATUS_NEW = 'new'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_AUTO_DONE = 'auto_done'

    status = models.CharField(max_length=20, default=STATUS_NEW)
    action_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    oncall = models.CharField(max_length=255, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)

    processing_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    external_last_action = models.CharField(max_length=50, blank=True, default='')
    external_last_http_status = models.IntegerField(null=True, blank=True)
    external_last_error = models.TextField(blank=True, default='')
    external_last_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
