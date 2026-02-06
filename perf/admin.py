from django.contrib import admin
from .models import ClusterConfig, ServiceProfile, LoadTestReport


@admin.register(ClusterConfig)
class ClusterConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "prometheus_url", "tempo_url", "updated_at")
    search_fields = ("name", "prometheus_url", "tempo_url")


@admin.register(ServiceProfile)
class ServiceProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "cluster", "namespace", "service_name", "qps_per_core", "recommended_cpu_cores", "confidence", "updated_at")
    list_filter = ("cluster", "namespace")
    search_fields = ("service_name",)


@admin.register(LoadTestReport)
class LoadTestReportAdmin(admin.ModelAdmin):
    list_display = ("id", "test_id", "cluster", "namespace", "service_name", "max_qps_reached", "confidence", "created_at")
    list_filter = ("cluster", "namespace", "service_name")
    search_fields = ("test_id", "service_name")

