from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduleViewSet, phone_alert_config, phone_alert_receive, phone_alert_processing, phone_alert_done

router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet)

urlpatterns = [
    path('schedules/phone-alert/config', phone_alert_config),
    path('schedules/phone-alert', phone_alert_receive),
    path('schedules/phone-alert/<int:alert_id>/processing', phone_alert_processing),
    path('schedules/phone-alert/<int:alert_id>/done', phone_alert_done),
    path('', include(router.urls)),
]
