import threading
import time
from django.utils import timezone

from .models import PhoneAlert
from .phone_alert import load_phone_alert_config, post_external_action, post_slack_blocks


class PhoneAlertEngine:
    def __init__(self):
        self._started = False
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(60)

    def _tick(self):
        cfg = load_phone_alert_config()
        minutes = int(cfg.auto_complete_minutes or 30)
        if minutes <= 0:
            return
        cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
        due = PhoneAlert.objects.filter(status=PhoneAlert.STATUS_PROCESSING, processing_at__lt=cutoff, done_at__isnull=True)[:100]
        for alert in due:
            alert.status = PhoneAlert.STATUS_AUTO_DONE
            alert.done_at = timezone.now()
            alert.save(update_fields=['status', 'done_at', 'updated_at'])

            code, detail = post_external_action(cfg, alert, 'auto_done')
            alert.external_last_action = 'auto_done'
            alert.external_last_http_status = code
            alert.external_last_error = '' if code is not None else (detail or '')
            alert.external_last_at = timezone.now()
            alert.save(update_fields=['external_last_action', 'external_last_http_status', 'external_last_error', 'external_last_at', 'updated_at'])

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ Auto completed alert #{alert.id} after {minutes} minutes. ({alert.oncall})"
                    }
                }
            ]
            post_slack_blocks(cfg, blocks)


phone_alert_engine = PhoneAlertEngine()

