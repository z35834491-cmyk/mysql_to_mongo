from django.apps import AppConfig
import os

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    def ready(self):
        # Prevent double execution in runserver with auto-reload
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn') is False:
             return
             
        try:
            from .sync.task_manager import task_manager
            # Auto start tasks that were marked as running
            task_manager.restore_from_disk()
        except Exception as e:
            # Avoid breaking startup if DB not ready or other issues
            print(f"Failed to restore sync tasks: {e}")
