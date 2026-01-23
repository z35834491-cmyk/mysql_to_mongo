from django.urls import path
from . import views

urlpatterns = [
    path('connections', views.connection_list),
    path('connections/test', views.connection_test),
    path('connections/<str:conn_id>', views.connection_detail),
    
    path('tasks/list', views.task_list),
    path('tasks/status', views.task_status_list),
    path('tasks/status/<str:task_id>', views.task_status_detail),
    path('tasks/start', views.start_task),
    path('tasks/start_with_conn_ids', views.start_with_conn_ids),
    path('tasks/start_existing/<str:task_id>', views.start_existing),
    path('tasks/reset_and_start/<str:task_id>', views.reset_and_start),
    path('tasks/stop/<str:task_id>', views.stop_task),
    path('tasks/stop_soft/<str:task_id>', views.stop_task_soft),
    path('tasks/delete/<str:task_id>', views.delete_task),
    path('tasks/logs/<str:task_id>', views.task_logs),
    
    # Global Log APIs
    path('logs/files', views.log_files_list),
    path('logs/download/<str:filename>', views.download_log_file),
    path('logs/stats', views.log_stats),
    path('logs/search', views.log_global_search),
    
    # K8s Logs APIs
    path('k8s/namespaces', views.k8s_namespaces),
    path('k8s/pods', views.k8s_pods),
    path('k8s/logs', views.k8s_pod_logs),
    
    path('mysql/databases', views.mysql_databases),
    path('mysql/databases_by_id/<str:conn_id>', views.mysql_databases_by_id),
    path('mysql/tables', views.mysql_tables),
    path('mysql/tables_by_id/<str:conn_id>', views.mysql_tables_by_id),
]
