from django.urls import path
from . import views

urlpatterns = [
    path('clusters', views.cluster_list),
    path('clusters/<int:pk>', views.cluster_detail),
    path('profiles', views.service_profiles),
    path('reports', views.load_test_reports),
    path('reports/<int:pk>', views.load_test_report_detail),
    path('analyze/capacity', views.analyze_capacity),
    path('jobs/<int:pk>', views.job_detail),
    path('services', views.list_services),
    path('promql/templates', views.promql_templates),
    path('traces/<str:trace_id>', views.get_trace),
    path('traces/<str:trace_id>/insights', views.trace_insights),
    path('traces', views.search_traces),
    path('hpa', views.list_hpa),
    path('hpa/apply', views.apply_hpa),
]
