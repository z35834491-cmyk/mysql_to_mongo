from django.db import models

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
