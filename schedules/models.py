from django.db import models

class Schedule(models.Model):
    staff_name = models.CharField(max_length=100, help_text="Name of the staff member")
    shift_date = models.DateField(help_text="Date of the shift")
    shift_type = models.CharField(max_length=50, help_text="Type of shift (e.g., Morning, Night)")
    extra_info = models.JSONField(default=dict, blank=True, help_text="Additional JSON data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-shift_date', 'staff_name']
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'

    def __str__(self):
        return f"{self.staff_name} - {self.shift_date} ({self.shift_type})"
