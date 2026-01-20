from django.urls import path
from . import views

urlpatterns = [
    path('tasks', views.monitor_tasks),
    path('tasks/<int:pk>', views.monitor_task_detail),
    path('logs', views.monitor_logs),
    path('logs/view', views.monitor_log_view),
    path('logs/download', views.monitor_log_download),
    path('logs/multi_search', views.monitor_log_multi_search),
]
