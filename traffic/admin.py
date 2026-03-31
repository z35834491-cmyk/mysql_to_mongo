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
    fields = (
        "enabled",
        "access_log_mode",
        "access_log_path",
        "log_sources",
        "error_log_path",
        "log_format",
        "max_tail_bytes",
        "redis_log_key",
        "redis_max_lines",
        "geoip_db_path",
        "use_inspection_prometheus",
        "prometheus_url_override",
        "blackbox_promql",
        "updated_at",
    )
    readonly_fields = ("updated_at",)
