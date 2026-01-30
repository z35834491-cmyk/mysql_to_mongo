import time
import os
import threading
import datetime
import glob
import logging
import json
import requests
from django.conf import settings
from django.utils import timezone
from .models import MonitorTask
try:
    from kubernetes import client, config as k8s_config
    from kubernetes.client.rest import ApiException
except ImportError:
    client = None
    k8s_config = None

try:
    import boto3
    from botocore.exceptions import NoCredentialsError
except ImportError:
    boto3 = None

logger = logging.getLogger("monitor")

class MonitorEngine:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self.LOG_DIR = os.path.join(settings.BASE_DIR, "logs", "monitor_logs")
        os.makedirs(self.LOG_DIR, exist_ok=True)

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Monitor engine started (v2-patched)")

    def stop(self):
        self._stop_event.set()
        with self._lock:
            if self._thread:
                self._thread.join(timeout=5)
                self._thread = None
        logger.info("Monitor engine stopped")

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                # Iterate over all enabled tasks
                tasks = MonitorTask.objects.filter(enabled=True)
                if not tasks:
                    time.sleep(5)
                    continue

                for task in tasks:
                    if self._stop_event.is_set():
                        break
                        
                    # Basic scheduling: run if last_run is older than interval
                    # Or just run every loop and let loop sleep handle it?
                    # Better: Check timestamp.
                    now = timezone.now()
                    
                    # Convert last_run to offset-naive if needed, or handle timezone
                    # Simplified: if last_run is None or (now - last_run).total_seconds() > poll_interval
                    should_run = False
                    if not task.last_run:
                        should_run = True
                    else:
                        # Assuming naive or matching tz
                        try:
                            delta = now.timestamp() - task.last_run.timestamp()
                            if delta >= task.poll_interval_seconds:
                                should_run = True
                        except:
                            should_run = True # Fallback
                            
                    if should_run:
                        try:
                            self._process_task(task)
                            task.last_run = now
                            task.last_error = "" # clear error on success
                            task.save(update_fields=['last_run', 'last_error', 'alerts_sent_count'])
                        except Exception as e:
                            logger.error(f"Error processing task {task.name}: {e}")
                            task.last_error = str(e)
                            task.save(update_fields=['last_error'])
                
                # Global sleep - maybe shorter to check for new tasks/schedule
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(10)

    def _process_task(self, task):
        # 1. Fetch Logs
        self._fetch_k8s_logs(task)
        
        # 2. Rotate & Archive
        self._rotate_and_archive(task)

    def _get_k8s_client(self, task):
        if not client:
            raise ImportError("kubernetes package not installed")
            
        if task.k8s_kubeconfig:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
                tf.write(task.k8s_kubeconfig)
                tf.flush()
                k8s_config.load_kube_config(config_file=tf.name)
                os.unlink(tf.name)
        else:
            try:
                k8s_config.load_incluster_config()
            except:
                k8s_config.load_kube_config()
        
        return client.CoreV1Api()

    def _fetch_k8s_logs(self, task):
        api = self._get_k8s_client(task)
        # Support multiple namespaces comma-separated
        raw_namespaces = task.k8s_namespace.split(',')
        namespaces = [n.strip() for n in raw_namespaces if n.strip()]
        if not namespaces:
            namespaces = ['default']
        
        today_str = datetime.date.today().isoformat()
        
        # Task specific log dir
        task_log_dir = os.path.join(self.LOG_DIR, str(task.id))
        os.makedirs(task_log_dir, exist_ok=True)

        for namespace in namespaces:
            try:
                pods = api.list_namespaced_pod(namespace)
            except Exception as e:
                logger.error(f"Failed to list pods in namespace {namespace}: {e}")
                continue
            
            for pod in pods.items:
                pod_name = pod.metadata.name
                if not pod.spec.containers:
                    continue
                container_name = pod.spec.containers[0].name
                
                unique_name = f"{namespace}_{pod_name}"
                log_file_path = os.path.join(task_log_dir, f"{unique_name}_{today_str}.log")
                
                since_seconds = task.poll_interval_seconds + 10
                
                try:
                    # Use streaming to avoid loading huge logs into memory
                    response = api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container_name,
                        since_seconds=since_seconds,
                        timestamps=True,
                        _preload_content=False # Enable streaming
                    )
                    
                    self._process_log_stream(response, task, unique_name, task_log_dir, log_file_path)
                        
                except Exception as e:
                    # logger.warning(f"Failed to read log for {pod_name}: {e}")
                    pass

    def _process_log_stream(self, stream, task, source_name, log_dir, log_file_path):
        alerts = [] # List of dicts: { 'type': str, 'keyword': str, 'msg': str }
        error_lines = [] # List of strings for aggregated error log
        
        # Load persistent threshold state from task if available, or init new
        threshold_state = task.threshold_state or {}
        threshold_window = task.alert_threshold_window # e.g. 60
        threshold_count = task.alert_threshold_count # e.g. 5
        threshold_updated = False
        
        # Keywords
        # Model fields are JSONField (list of strings), e.g. ["error", "exception"]
        # We need to handle them as lists, not splitlines() on text.
        
        def parse_keywords(field_value):
            if not field_value:
                return []
            if isinstance(field_value, list):
                return [str(k).strip() for k in field_value if str(k).strip()]
            if isinstance(field_value, str):
                return [k.strip() for k in field_value.splitlines() if k.strip()]
            return []

        clean_immediate_keywords = [k.lower() for k in parse_keywords(task.immediate_keywords)]
        clean_alert_keywords = [k.lower() for k in parse_keywords(task.alert_keywords)]
        clean_record_keywords = parse_keywords(task.record_only_keywords)
        clean_ignore_keywords = parse_keywords(task.ignore_keywords)
        
        # Add 'fata' to default errors (common in Go apps)
        default_error_keywords = ['error', 'exception', 'fail', 'fatal', 'panic', 'fata']
        
        # Stats
        count_error = 0
        count_warn = 0
        count_info = 0
        count_other = 0
        
        # Context Management
        # Keep last N lines for context
        CONTEXT_LINES = 5
        context_buffer = [] # list of strings
        
        # When an error occurs, we need to record:
        # 1. The context (previous N lines)
        # 2. The error line
        # 3. The following N lines (future)
        # To handle multiple errors close to each other, we use a counter "lines_to_record_counter"
        
        lines_to_record_counter = 0
        
        # Separate file for errors: pod_name_YYYY-MM-DD_error.log
        today_str = datetime.date.today().isoformat()
        error_file_path = os.path.join(log_dir, f"{source_name}_{today_str}_error.log")
        
        error_file_handle = None
        log_file_handle = None
        try:
            error_file_handle = open(error_file_path, "a", encoding="utf-8")
            log_file_handle = open(log_file_path, "a", encoding="utf-8")
            
            for line_bytes in stream:
                if not line_bytes:
                    continue
                    
                # Decode bytes to string
                line = line_bytes.decode('utf-8', errors='replace')
                
                # Write to raw log
                log_file_handle.write(line)

                # --- Analysis Logic Per Line ---
                if any(k in line for k in clean_ignore_keywords):
                    continue

                line_lower = line.lower()
                
                # Simple counting
                if 'error' in line_lower or 'fail' in line_lower or 'exception' in line_lower:
                    count_error += 1
                elif 'warn' in line_lower:
                    count_warn += 1
                elif 'info' in line_lower:
                    count_info += 1
                else:
                    count_other += 1

                # Check for "Trigger" conditions (Alerts, Errors, Record Only)
                
                # 1. Immediate Alerts
                is_alert = False
                if clean_immediate_keywords:
                    for k in clean_immediate_keywords:
                        if k.lower() in line_lower:
                            alerts.append({
                                'type': 'IMMEDIATE',
                                'keyword': k,
                                'msg': f"[IMMEDIATE] {line}"
                            })
                            is_alert = True
                            break # Match first keyword only per line to avoid dupes
                
                # 2. Threshold Alerts
                current_ts = time.time()
                try:
                    ts_str = line[:19]
                    dt = datetime.datetime.fromisoformat(ts_str)
                    current_ts = dt.timestamp()
                except:
                    pass

                if clean_alert_keywords:
                    for k in clean_alert_keywords:
                        if k.lower() in line_lower:
                            if k not in threshold_state:
                                threshold_state[k] = []
                            threshold_state[k].append(current_ts)
                            # Cleanup old timestamps
                            threshold_state[k] = [t for t in threshold_state[k] if current_ts - t <= threshold_window]
                            threshold_updated = True
                            
                            if len(threshold_state[k]) >= threshold_count:
                                alerts.append({
                                    'type': 'THRESHOLD',
                                    'keyword': k,
                                    'msg': f"[THRESHOLD {len(threshold_state[k])}/{threshold_window}s] Keyword: '{k}' | Last: {line}"
                                })
                                is_alert = True
                                threshold_state[k] = [] # Reset state after alert to avoid spamming every line?
                                # User requirement: "Same alert sent once per hour".
                                # If we reset state, next error will start counting from 0.
                                # If we don't reset, next error will be 6th, 7th... and trigger alert again?
                                # Yes, we should reset state here so we don't trigger on 6th, 7th, 8th.
                                # The "Silence" logic in `_send_slack_alert` handles the 1 hour cooldown.
                                # So here we just need to detect the BURST (e.g. 5 errors in 60s).
                                # Once burst detected, we fire alert.
                                # Then we reset burst counter.
                                pass
                
                # 3. Generic Errors (for context recording)
                is_error = any(k in line_lower for k in default_error_keywords)
                
                # 4. Record Only (and Suppress Alert)
                is_record = False
                if clean_record_keywords:
                     if any(k in line for k in clean_record_keywords):
                         is_record = True
                         
                         # CRITICAL FIX: If matched Record Only, remove any alerts generated by this line
                         # This allows "muting" specific errors that match general Alert keywords (like 'error')
                         # but shouldn't trigger Slack notifications.
                         if is_alert:
                             # Remove alerts added in step 1 & 2 for this line
                             # We can check the last added alerts or filter the whole list?
                             # Since we are processing line by line, the alerts for THIS line are added just now.
                             # But 'alerts' is a list for the whole stream/batch.
                             # We need to know which alerts correspond to THIS line.
                             # The alert dict has 'msg' which contains the line.
                             # Let's filter out alerts that contain this line text AND were just added?
                             # Simpler: Filter alerts list at the end of loop iteration? 
                             # No, alerts is accumulated for the whole pod stream.
                             
                             # Let's remove alerts where msg contains this line content.
                             # Be careful not to remove duplicates if same line appeared before?
                             # But here we are inside the loop for THIS line.
                             
                             # Actually, simpler way:
                             # Don't add to alerts if it matches record keywords?
                             # But we already added them in Step 1 & 2.
                             
                             # So let's remove them now.
                             alerts = [a for a in alerts if a['msg'].find(line) == -1]
                             is_alert = False # Reset flag so it doesn't prefix [ALERT] in log file

                # --- Context Recording Logic ---
                # Trigger condition: Alert OR Error OR Record
                should_trigger_context = is_alert or is_error or is_record
                
                if should_trigger_context:
                    # Add to error_lines for aggregated log
                    error_lines.append(line.strip())

                    # If we are not already recording, dump context first
                    if lines_to_record_counter <= 0:
                        # Write separator if needed
                        error_file_handle.write("-" * 40 + "\n")
                        # Write context buffer
                        for ctx_line in context_buffer:
                            error_file_handle.write(f"[CTX] {ctx_line}")
                            if not ctx_line.endswith('\n'): error_file_handle.write('\n')
                    
                    # Reset counter to capture next N lines
                    lines_to_record_counter = CONTEXT_LINES
                    
                    # Write current line with prefix
                    prefix = ""
                    if is_alert: prefix += "[ALERT]"
                    if is_error: prefix += "[ERROR]"
                    if is_record: prefix += "[RECORD]"
                    error_file_handle.write(f"{prefix} {line}")
                    if not line.endswith('\n'): error_file_handle.write('\n')
                    
                else:
                    # Normal line
                    if lines_to_record_counter > 0:
                        # We are in the "after" window
                        error_file_handle.write(f"[CTX] {line}")
                        if not line.endswith('\n'): error_file_handle.write('\n')
                        lines_to_record_counter -= 1
                
                # Update context buffer (always keep last N lines)
                context_buffer.append(line)
                if len(context_buffer) > CONTEXT_LINES:
                    context_buffer.pop(0)
                    
                # Flush error file periodically or on write? 
                # Python's file object is buffered, let's flush on trigger to be safe
                if should_trigger_context:
                    error_file_handle.flush()

        finally:
            if error_file_handle:
                error_file_handle.close()
            if log_file_handle:
                log_file_handle.close()
                
            # Save threshold state if updated
            if threshold_updated:
                task.threshold_state = threshold_state
                task.save(update_fields=['threshold_state'])

        # --- Post-processing after stream ends ---
        
        # 1. Write scan history
        scan_history_path = os.path.join(log_dir, "scan_history.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (f"[{timestamp}] [monitor] Pod: {source_name} | "
                     f"counts error={count_error} warn={count_warn} info={count_info} other={count_other} alerts={len(alerts)}\n")
        try:
            with open(scan_history_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write scan history: {e}")

        # 2. Write aggregated error/alert/record lines
        if error_lines:
            today_str = datetime.date.today().isoformat()
            task_err_filename = f"task_errors_{today_str}.log"
            task_err_path = os.path.join(log_dir, task_err_filename)
            try:
                with open(task_err_path, "a", encoding="utf-8") as f:
                    for l in error_lines:
                        f.write(f"[{source_name}] {l}")
                        if not l.endswith('\n'):
                            f.write('\n')
            except Exception as e:
                logger.error(f"Failed to write aggregated error log: {e}")

        # 3. Send Slack Alerts
        # CRITICAL FIX: The previous silence logic was filtering too aggressively or incorrectly.
        # User reported "I have a line that met condition, why no alert?"
        # The logs show "alerts=0" in scan history for the pod.
        # This means `alerts` list was empty or cleared.
        
        # Possible reasons:
        # 1. It matched Record Only and was removed (intended).
        # 2. It matched Threshold but didn't reach count?
        # 3. Silence logic was applied prematurely? 
        #    Wait, silence logic is applied inside `_send_slack_alert`.
        #    The `alerts` list passed to `_send_slack_alert` comes from the loop above.
        
        # If scan history says alerts=0, it means `alerts` list was empty BEFORE calling `_send_slack_alert`.
        # So it must be Logic in the loop.
        
        # Logic in loop:
        # 1. Immediate -> add to alerts
        # 2. Threshold -> add to alerts IF count >= threshold_count
        # 3. Record Only -> remove from alerts
        
        # User says "I have a line that met condition".
        # If it's a Threshold Alert (e.g. "error"), did it meet the count?
        # Screenshot shows: "counts error=2". 
        # If threshold_count is default (e.g. 5), then 2 < 5, so no alert.
        # Check task config for threshold_count. Default is usually 1 or 5.
        # If user expects alert on FIRST error, they should use Immediate Alert or set Threshold Count to 1.
        
        # However, user says "相同告警在一个小时内只发送一次，除非是图中配置的告警(Immediate Alert)才是出现就发送。"
        # This implies they want Threshold logic (with silence) but maybe the count threshold is preventing it?
        
        # Wait, if `alerts` is empty in `scan_history`, it means it never entered the list.
        # If it's a Threshold Alert, it only enters list if `len(threshold_state[k]) >= threshold_count`.
        # If count is 2 and threshold is 5, it won't alert. This is correct behavior for Threshold.
        
        # BUT, if user thinks it SHOULD alert, maybe they set threshold to 1?
        # Or maybe they think "Immediate Alert" logic is broken?
        # If they configured keywords in "Immediate Alert", it should trigger immediately (count=1).
        
        # Let's verify the logic for Immediate Alert again.
        # if k.lower() in line_lower: alerts.append(...)
        
        # If the keyword was "error" and it was in Immediate, it should alert.
        # If "error" was in Threshold, it waits for count.
        
        # If the screenshot shows "counts error=2" and "alerts=0", and the user expects an alert,
        # then either:
        # A) The keyword "error" is in Threshold list, and count threshold > 2.
        # B) The keyword "error" is NOT in any list (maybe case sensitivity?).
        # C) It matched Record Only and was removed.
        
        # To debug/fix, we should ensure that if user wants "Appear then send" (Frequency Control), 
        # they are using Threshold Alert with Count=1.
        
        # Also, check the Silence Logic in `_send_slack_alert`.
        # The user's complaint "My silence function is gone" suggests they might have seen spam before?
        # Or they mean "Why is it NOT alerting now?".
        # "我有一条达到我条件的了，为什么没有告警了" -> "I have one that met condition, why no alert?"
        # And screenshot shows alerts=0.
        
        # This strongly suggests the Threshold Count condition wasn't met.
        # If user wants 1 error to trigger alert, they must set Threshold Count to 1.
        
        # However, there is a potential bug in `threshold_state` persistence.
        # `threshold_state` is a local variable in `_run_loop` or `MonitorEngine`.
        # Wait, `threshold_state` is initialized inside the loop `threshold_state = {}`? 
        # No, it should be persistent across loops for the same task.
        # In `_process_log_stream`, `threshold_state` is passed in? No, it's local.
        # `_process_log_stream` is called once per stream.
        # If stream stays open (streaming mode), `threshold_state` persists for the duration of connection.
        # If connection drops and reconnects, state is lost.
        
        # In `_fetch_k8s_logs`, we call `_process_log_stream`.
        # `threshold_state` is defined inside `_process_log_stream`:
        # `threshold_state = {}`
        
        # If `_process_log_stream` processes a batch of lines and returns? 
        # No, `api.read_namespaced_pod_log(..., _preload_content=False)` returns a generator/stream.
        # The loop `for line in stream:` runs until stream ends.
        # For `follow=True` (which we aren't using explicitly, we use `since_seconds` polling?),
        # Wait, `read_namespaced_pod_log` without `follow=True` returns existing logs and closes.
        # We are using `since_seconds=task.poll_interval_seconds + 10`.
        # This means we are polling.
        # So `_process_log_stream` runs for a short batch and exits.
        # **THEREFORE, `threshold_state` IS LOST between polls!**
        
        # This is the BUG.
        # If Threshold Count is 5, and we get 2 errors in this poll, and 3 errors in next poll,
        # We never trigger alert because `threshold_state` is reset every poll.
        # We need to persist `threshold_state` in the Task object or Engine instance.
        
        if alerts:
            error_filename = os.path.basename(error_file_path)
            self._send_slack_alert(alerts, task, source_name, log_dir, error_filename)

    def _analyze_logs(self, log_content, task, source_name, log_dir):
        # DEPRECATED: Kept only if needed for non-streaming fallback, 
        # but _fetch_k8s_logs now uses _process_log_stream.
        pass

    def _send_slack_alert(self, alerts, task, source, log_dir, error_filename=None):
        if not task.alert_enabled:
            return
            
        webhook_url = task.slack_webhook_url
        if not webhook_url:
            return
            
        # --- Deduplication Logic (Alert Silence) ---
        # 1. Group alerts by keyword
        # 2. Check silence period for each keyword
        # 3. Filter out silenced alerts
        
        now = time.time()
        silence_seconds = task.alert_silence_minutes * 60
        alert_state = task.alert_state or {}
        
        # Filter alerts
        filtered_alerts = []
        updated_state = False
        
        # Helper to get keyword from alert
        # Alert dict: {'type': 'IMMEDIATE'|'THRESHOLD', 'keyword': 'xxx', 'msg': '...'}
        
        # We process alerts in order. 
        # For IMMEDIATE alerts, we might want to respect silence too? User said "unless it is configured in the graph (Immediate) then send immediately"
        # The user input says: "相同告警在一个小时内只发送一次，除非是图中配置的告警(Immediate Alert)才是出现就发送。"
        # This implies:
        # - THRESHOLD alerts: Apply silence logic (deduplication).
        # - IMMEDIATE alerts: Do NOT apply silence logic (always send).
        
        for alert in alerts:
            atype = alert.get('type')
            keyword = alert.get('keyword')
            
            if atype == 'IMMEDIATE':
                # Immediate alerts always pass through
                filtered_alerts.append(alert)
            else:
                # Threshold alerts check silence
                last_sent = alert_state.get(keyword, 0)
                if now - last_sent > silence_seconds:
                    filtered_alerts.append(alert)
                    alert_state[keyword] = now
                    updated_state = True
                else:
                    logger.info(f"Silenced alert for '{keyword}' (Last sent: {datetime.datetime.fromtimestamp(last_sent)})")

        if updated_state:
            task.alert_state = alert_state
            task.save(update_fields=['alert_state'])
            
        if not filtered_alerts:
            return

        # Use filtered alerts for display
        shown_alerts = filtered_alerts[:10]
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Alert in {source} (Task: {task.name})",
                    "emoji": True
                }
            }
        ]
        
        # Add Link Button if error file is available
        if error_filename:
            # Base URL should be configured in settings or task, fallback to localhost for now
            # User requested to configure domain in frontend? 
            # Actually link is generated here in backend. 
            # Let's use a standard placeholder or settings.FRONTEND_URL if available.
            # But user said "域名改成在前端配置" (Domain configured in frontend).
            # This likely means the frontend will handle the link construction if we pass relative path?
            # Or maybe we just use a placeholder that user can override?
            # Let's try to find where FRONTEND_URL is defined or use window.location logic (impossible in backend).
            # We will use a generic relative path or a hardcoded base that matches the screenshot context.
            # Wait, if user says "configure in frontend", maybe they mean the link in Slack should just be a path?
            # Slack requires valid URL.
            # Let's use a standard Env Var or Setting for PUBLIC_URL.
            
            base_url = os.environ.get('PUBLIC_URL') or getattr(settings, 'PUBLIC_URL', None) or 'http://localhost:5173'
            base_url = base_url.rstrip('/')
            log_url = f"{base_url}/logs?taskId={task.id}&filename={error_filename}"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👉 <{log_url}|View Detailed Logs>"
                }
            })

        for alert in shown_alerts:
            # Truncate msg
            msg = alert['msg'][:2000] 
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{msg}```"
                }
            })
            
        if len(filtered_alerts) > 10:
             blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"... and {len(filtered_alerts) - 10} more alerts."
                    }
                ]
            })

        try:
            payload = {"blocks": blocks}
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send slack alert: {e}")

    def _rotate_and_archive(self, task):
        retention = task.retention_days
        cutoff_date = datetime.date.today() - datetime.timedelta(days=retention)
        
        task_log_dir = os.path.join(self.LOG_DIR, str(task.id))
        if not os.path.exists(task_log_dir):
            return
            
        files = glob.glob(os.path.join(task_log_dir, "*.log"))
        
        s3 = None
        if task.s3_archive_enabled and task.s3_bucket and boto3:
            try:
                s3 = boto3.client(
                    's3',
                    region_name=task.s3_region,
                    aws_access_key_id=task.s3_access_key,
                    aws_secret_access_key=task.s3_secret_key,
                    endpoint_url=task.s3_endpoint
                )
            except Exception as e:
                logger.error(f"Failed to init S3: {e}")
                return

        for fp in files:
            fname = os.path.basename(fp)
            try:
                parts = fname.rsplit('_', 1)
                if len(parts) != 2:
                    continue
                date_part = parts[1].replace('.log', '')
                file_date = datetime.date.fromisoformat(date_part)
                
                if file_date <= cutoff_date:
                    if s3 and task.s3_archive_enabled:
                        s3_key = f"logs/{task.name}/{file_date.year}/{file_date.month}/{file_date.day}/{fname}"
                        try:
                            s3.upload_file(fp, task.s3_bucket, s3_key)
                            logger.info(f"Uploaded {fname} to S3")
                        except Exception as e:
                            logger.error(f"Failed to upload {fname}: {e}")
                            continue 
                    
                    try:
                        os.remove(fp)
                        logger.info(f"Deleted old log {fname}")
                    except Exception as e:
                        logger.error(f"Failed to delete {fname}: {e}")
                        
            except ValueError:
                continue


monitor_engine = MonitorEngine()
