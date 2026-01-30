from django.apps import AppConfig


class SchedulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'schedules'

    def ready(self):
        import os
        import sys

        is_runserver = 'runserver' in sys.argv
        should_start = False

        if is_runserver:
            if os.environ.get('RUN_MAIN') == 'true':
                should_start = True
        else:
            should_start = True

        if should_start:
            from .engine import phone_alert_engine
            phone_alert_engine.start()
