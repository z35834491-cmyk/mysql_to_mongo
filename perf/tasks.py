from celery import shared_task
from django.utils import timezone
from .models import PerfJob, ClusterConfig
from .views import _run_capacity_analysis

@shared_task
def analyze_capacity_task(job_id: int):
    try:
        job = PerfJob.objects.get(pk=job_id)
    except PerfJob.DoesNotExist:
        return
    if job.status not in ("pending", "running"):
        return
    try:
        job.status = "running"
        job.started_at = timezone.now()
        job.error = ""
        job.save(update_fields=["status", "started_at", "error"])
        result = _run_capacity_analysis(job.params or {})
        job.status = "success"
        job.result = result or {}
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "result", "finished_at"])
    except Exception as e:
        job.status = "failed"
        job.error = str(e)[:2000]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
