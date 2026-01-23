from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # API Routes
    path('api/', include('api.urls')),
    path('api/deploy/', include('deploy.urls')),
    path('api/', include('tasks.urls')), 
    path('api/monitor/', include('monitor.urls')),
    path('api/inspection/', include('inspection.urls')),

    # Frontend SPA Support
    re_path(r'^.*$', core_views.index, name='index'),
]
