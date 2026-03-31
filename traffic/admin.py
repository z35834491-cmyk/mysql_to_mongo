from django.contrib import admin

from .models import TrafficDashboardConfig, TrafficMinuteRollup


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
        "dashboard_fetch_max_lines",
        "geoip_db_path",
        "use_inspection_prometheus",
        "prometheus_url_override",
        "blackbox_promql",
        "updated_at",
    )
    readonly_fields = ("updated_at",)


@admin.register(TrafficMinuteRollup)
class TrafficMinuteRollupAdmin(admin.ModelAdmin):
    list_display = ("bucket_start", "source_id", "requests", "updated_at")
    list_filter = ("source_id",)
    ordering = ("-bucket_start",)
    readonly_fields = (
        "bucket_start",
        "source_id",
        "requests",
        "sum_latency_ms",
        "count_latency",
        "status_2xx",
        "status_4xx",
        "status_5xx",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "geo_counts",
        "top_paths",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
