import threading
import time
from django.utils import timezone
from .models import PerfJob


class PerfEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        with self._lock:
            if self._thread:
                self._thread.join(timeout=3)
                self._thread = None

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self):
        from .views import _run_capacity_analysis

        while not self._stop_event.is_set():
            job = None
            try:
                job = PerfJob.objects.filter(status="pending").order_by("id").first()
            except Exception:
                job = None

            if not job:
                time.sleep(1)
                continue

            try:
                job.status = "running"
                job.started_at = timezone.now()
                job.error = ""
                job.save(update_fields=["status", "started_at", "error"])

                if job.job_type == "capacity_analysis":
                    result = _run_capacity_analysis(job.params or {})
                else:
                    raise RuntimeError(f"unknown job_type={job.job_type}")

                job.status = "success"
                job.result = result or {}
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "result", "finished_at"])
            except Exception as e:
                try:
                    job.status = "failed"
                    job.error = str(e)[:2000]
                    job.finished_at = timezone.now()
                    job.save(update_fields=["status", "error", "finished_at"])
                except Exception:
                    pass


perf_engine = PerfEngine()

