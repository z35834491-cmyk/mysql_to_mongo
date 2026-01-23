from django.urls import path
from . import views

urlpatterns = [
    path('system/stats', views.system_stats, name='system_stats'),
    path('users', views.user_list, name='user_list'),
    path('users/<int:pk>', views.user_detail, name='user_detail'),
    path('me', views.me, name='me'),
]
