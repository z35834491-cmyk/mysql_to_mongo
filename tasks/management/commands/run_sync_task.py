from django.core.management.base import BaseCommand, CommandError

from tasks.models import SyncTask
from tasks.schemas import SyncTaskRequest
from tasks.sync.worker import SyncWorker


class Command(BaseCommand):
    help = "Run one sync task in foreground (for turbo pod runner)."

    def add_arguments(self, parser):
        parser.add_argument("--task-id", required=True, help="Task id to run")

    def handle(self, *args, **options):
        task_id = options["task_id"]
        try:
            task = SyncTask.objects.get(task_id=task_id)
        except SyncTask.DoesNotExist:
            raise CommandError(f"Task not found: {task_id}")

        cfg = SyncTaskRequest(**(task.config or {}))
        task.status = "running"
        task.save(update_fields=["status", "updated_at"])

        worker = SyncWorker(cfg)
        worker.run()

        # Keep DB status aligned with worker lifecycle.
        if getattr(worker, "_status", "") == "error":
            task.status = "error"
        else:
            task.status = "stopped"
        task.save(update_fields=["status", "updated_at"])
