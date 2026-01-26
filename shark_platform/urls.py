from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
# from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    # path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # API Routes
    path('api/', include('api.urls')),
    path('api/deploy/', include('deploy.urls')),
    path('api/', include('tasks.urls')), 
    path('api/monitor/', include('monitor.urls')),
    path('api/inspection/', include('inspection.urls')),
    path('api/', include('schedules.urls')),

    # Frontend SPA Support - Serve index.html from static or similar
    # Since we removed templates, we should serve the Vue built index.html if it exists,
    # OR if in dev mode, we might not need this catch-all if running separately.
    # But usually for production we serve static.
    
    # For now, let's remove the catch-all re_path to core_views.index as it fails.
    # We can rely on Django serving static files or Nginx.
    # If we want to support history mode routing, we need a view that serves index.html from STATIC_ROOT.
    
    # re_path(r'^.*$', core_views.index, name='index'),
]
