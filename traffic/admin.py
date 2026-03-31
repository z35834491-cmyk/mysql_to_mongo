from django.contrib import admin

from .models import TrafficDashboardConfig


@admin.register(TrafficDashboardConfig)
class TrafficDashboardConfigAdmin(admin.ModelAdmin):
    list_display = (
        "enabled",
        "access_log_mode",
        "access_log_path",
        "redis_log_key",
        "log_format",
        "updated_at",
    )
