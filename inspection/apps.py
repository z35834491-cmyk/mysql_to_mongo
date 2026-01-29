from django.apps import AppConfig
import os
import logging

logger = logging.getLogger("inspection")

class InspectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inspection'

    def ready(self):
        # Prevent double execution in runserver with auto-reload
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn') is False:
             return
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            # from django_apscheduler.jobstores import DjangoJobStore
            from .engine import inspection_engine
            
            def run_inspection_task():
                try:
                    logger.info("Starting daily inspection task...")
                    inspection_engine.run()
                    logger.info("Daily inspection task completed.")
                except Exception as e:
                    logger.error(f"Daily inspection task failed: {e}")

            scheduler = BackgroundScheduler()
            # If using django_apscheduler, we can use DjangoJobStore, but memory is fine for now
            # scheduler.add_jobstore(DjangoJobStore(), "default")
            
            # Add job to run at 8:00 AM every day
            scheduler.add_job(
                run_inspection_task,
                trigger=CronTrigger(hour=8, minute=0),
                id='daily_inspection',
                max_instances=1,
                replace_existing=True
            )

            
            scheduler.start()
            logger.info("Inspection scheduler started: Daily at 08:00")
            
        except ImportError:
            logger.warning("APScheduler not installed. Daily inspection disabled.")
        except Exception as e:
            logger.error(f"Failed to start inspection scheduler: {e}")

# Helper wrapper for the task since we can't import views at top level inside AppConfig easily?
# Actually we can import inside ready()
