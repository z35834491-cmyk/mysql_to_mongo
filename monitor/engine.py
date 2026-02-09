import time
import os
import threading
import datetime
import glob
import logging
import json
import re
from urllib.parse import quote
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
        self._index_lock = threading.Lock()
        self._index_entries = {}
        self._index_last_window_start = {}

    def _get_s3_client(self, task):
        if not boto3:
            return None
        if not getattr(task, 's3_archive_enabled', False):
            return None
        if not getattr(task, 's3_bucket', ''):
            return None
        try:
            return boto3.client(
                's3',
                region_name=task.s3_region,
                aws_access_key_id=task.s3_access_key,
                aws_secret_access_key=task.s3_secret_key,
                endpoint_url=task.s3_endpoint or None
            )
        except Exception:
            return None

    def _get_s3_prefix(self, task):
        return f"logs/monitor/{task.id}/"

    def _get_4h_window_start(self, dt):
        local_dt = timezone.localtime(dt)
        hour = (local_dt.hour // 4) * 4
        return local_dt.replace(hour=hour, minute=0, second=0, microsecond=0)

    def _get_latest_completed_window_start(self, now):
        return self._get_4h_window_start(now) - datetime.timedelta(hours=4)

    def _get_index_s3_key(self, task, log_type: str, window_start):
        ws = timezone.localtime(window_start)
        date_str = ws.date().isoformat()
        start_h = ws.hour
        end_h = (start_h + 3) % 24
        return f"{self._get_s3_prefix(task)}indexes/{log_type}/{date_str}/{start_h:02d}00-{end_h:02d}59.json"

    def _record_index_entry(self, task, log_type: str, key: str, size_bytes: int, ts: float):
        try:
            if not key:
                return
            now = timezone.now()
            ws = self._get_4h_window_start(now)
            tid = str(task.id)
            with self._index_lock:
                by_task = self._index_entries.setdefault(tid, {})
                by_window = by_task.setdefault(ws.isoformat(), {"raw": {}, "error": {}})
                by_type = by_window.setdefault(log_type, {})
                by_type[key] = {"name": key, "size": int(size_bytes or 0), "mtime": float(ts or now.timestamp())}
                self._index_last_window_start[tid] = ws.isoformat()
        except Exception:
            pass

    def _finalize_due_indexes(self, task):
        s3_client = self._get_s3_client(task)
        if not s3_client:
            return
        now = timezone.now()
        latest_completed_ws = self._get_latest_completed_window_start(now)
        tid = str(task.id)

        to_finalize = []
        with self._index_lock:
            by_task = self._index_entries.get(tid) or {}
            for ws_iso in list(by_task.keys()):
                try:
                    ws = datetime.datetime.fromisoformat(ws_iso)
                except Exception:
                    continue
                if timezone.is_naive(ws):
                    ws = timezone.make_aware(ws, timezone.get_current_timezone())
                if ws <= latest_completed_ws:
                    to_finalize.append(ws)

        for ws in sorted(to_finalize):
            self._upload_index_file(task, s3_client, 'raw', ws)
            self._upload_index_file(task, s3_client, 'error', ws)
            with self._index_lock:
                by_task = self._index_entries.get(tid) or {}
                by_task.pop(ws.isoformat(), None)
                if not by_task:
                    self._index_entries.pop(tid, None)

    def _upload_index_file(self, task, s3_client, log_type: str, window_start):
        tid = str(task.id)
        ws = timezone.localtime(window_start)
        we = ws + datetime.timedelta(hours=4) - datetime.timedelta(seconds=1)
        ws_iso = ws.isoformat()
        items = []
        with self._index_lock:
            by_task = self._index_entries.get(tid) or {}
            by_window = by_task.get(ws_iso) or {}
            items_map = by_window.get(log_type) or {}
            items = list(items_map.values())

        items.sort(key=lambda x: x.get('name') or '')
        payload = {
            "task_id": tid,
            "task_name": getattr(task, 'name', ''),
            "log_type": log_type,
            "window_start": ws_iso,
            "window_end": we.isoformat(),
            "generated_at": timezone.now().isoformat(),
            "total": len(items),
            "files": items,
        }
        key = self._get_index_s3_key(task, log_type, ws)
        try:
            s3_client.put_object(
                Bucket=task.s3_bucket,
                Key=key,
                Body=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                ContentType='application/json; charset=utf-8'
            )
        except Exception:
            pass

    def _cleanup_s3(self, task, s3_client, retention_days=90, max_delete=1000):
        try:
            cutoff = timezone.now() - datetime.timedelta(days=retention_days)
            prefix = self._get_s3_prefix(task)
            keys_to_delete = []
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=task.s3_bucket, Prefix=prefix):
                for obj in page.get('Contents', []) or []:
                    lm = obj.get('LastModified')
                    if lm and lm < cutoff:
                        keys_to_delete.append({'Key': obj['Key']})
                        if len(keys_to_delete) >= max_delete:
                            break
                if len(keys_to_delete) >= max_delete:
                    break

            if keys_to_delete:
                for i in range(0, len(keys_to_delete), 1000):
                    s3_client.delete_objects(
                        Bucket=task.s3_bucket,
                        Delete={'Objects': keys_to_delete[i:i + 1000], 'Quiet': True}
                    )
        except Exception:
            pass

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

                    try:
                        self._finalize_due_indexes(task)
                    except Exception:
                        pass
                
                # Global sleep - maybe shorter to check for new tasks/schedule
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(10)

    def _process_task(self, task):
        try:
            task.refresh_from_db(fields=[
                'enabled',
                'k8s_namespace',
                'k8s_kubeconfig',
                'alert_enabled',
                'slack_webhook_url',
                'poll_interval_seconds',
                'alert_keywords',
                'immediate_keywords',
                'ignore_keywords',
                'record_only_keywords',
                'alert_threshold_count',
                'alert_threshold_window',
                'alert_silence_minutes',
            ])
        except Exception:
            pass
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
        s3_client = self._get_s3_client(task)
        s3_only = bool(s3_client)

        task_log_dir = os.path.join(self.LOG_DIR, str(task.id))
        if not s3_only:
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
                log_file_path = os.path.join(task_log_dir, f"{unique_name}_{today_str}.log") if not s3_only else ""
                
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
                    if s3_only:
                        stamp = timezone.now().strftime("%H%M%S_%f")
                        base_prefix = self._get_s3_prefix(task).rstrip('/')
                        raw_s3_key = f"{base_prefix}/raw/{namespace}/{pod_name}/{today_str}/{stamp}.log"
                        error_s3_key = f"{base_prefix}/error/{namespace}/{pod_name}/{today_str}/{stamp}.log"
                        self._process_log_stream(
                            response,
                            task,
                            unique_name,
                            task_log_dir,
                            log_file_path,
                            s3_client=s3_client,
                            s3_bucket=task.s3_bucket,
                            raw_s3_key=raw_s3_key,
                            error_s3_key=error_s3_key
                        )
                    else:
                        self._process_log_stream(response, task, unique_name, task_log_dir, log_file_path)
                        
                except Exception as e:
                    # logger.warning(f"Failed to read log for {pod_name}: {e}")
                    pass

    def _process_log_stream(self, stream, task, source_name, log_dir, log_file_path, s3_client=None, s3_bucket=None, raw_s3_key=None, error_s3_key=None):
        alerts = [] # List of dicts: { 'type': str, 'keyword': str, 'msg': str }
        error_lines = [] # List of strings for aggregated error log
        namespace = source_name.split('_', 1)[0] if source_name else ''
        s3_only = bool(s3_client and s3_bucket and raw_s3_key)
        raw_buffer = []
        error_output = []
        
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
        
        CONTEXT_LINES = 20
        context_buffer = [] # list of strings
        
        # When an error occurs, we need to record:
        # 1. The context (previous N lines)
        # 2. The error line
        # 3. The following N lines (future)
        # To handle multiple errors close to each other, we use a counter "lines_to_record_counter"
        
        after_context_counter = 0
        stack_capture_active = False

        def _strip_ansi(s: str) -> str:
            try:
                return re.sub(r'\x1b\[[0-9;]*m', '', s)
            except Exception:
                return s

        def _strip_k8s_timestamp(s: str) -> str:
            try:
                payload = s.lstrip()
                m = re.match(r'^\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})\s+(.*)$', payload)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return s

        def _extract_level(s: str):
            try:
                payload = s.lstrip()
                m = re.match(r'^\[(ERROR|WARN|INFO|DEBUG|TRACE|FATAL)\]\b', payload)
                return m.group(1) if m else None
            except Exception:
                return None

        def _drop_bracket_tags(s: str) -> str:
            try:
                return re.sub(r'^(\[[^\]]+\]\s+)+', '', s.lstrip())
            except Exception:
                return s

        def _strip_leading_timestamp(s: str) -> str:
            try:
                payload = _strip_k8s_timestamp(_strip_ansi(s)).lstrip()
                for prefix in ('[ERROR]', '[WARN]', '[INFO]', '[DEBUG]', '[TRACE]', '[FATAL]'):
                    if payload.startswith(prefix):
                        payload = payload[len(prefix):].lstrip()
                        break

                if len(payload) >= 21 and payload[4] == '-' and payload[7] == '-' and ('T' in payload[:12]):
                    parts = payload.split(None, 1)
                    if len(parts) == 2 and parts[0].count(':') >= 2:
                        return parts[1]
            except Exception:
                pass
            return payload if 'payload' in locals() else s

        def _strip_level_prefix(s: str) -> str:
            try:
                payload = _strip_k8s_timestamp(_strip_ansi(s)).lstrip()
                for prefix in ('[ERROR]', '[WARN]', '[INFO]', '[DEBUG]', '[TRACE]', '[FATAL]'):
                    if payload.startswith(prefix):
                        return payload[len(prefix):].lstrip()
            except Exception:
                pass
            return s

        def _looks_like_java_frame(s: str) -> bool:
            t = s.strip()
            if not t:
                return False
            return bool(re.match(r'^[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+\([A-Za-z0-9_$.]+:\d+\)$', t))

        def _format_stack_line(raw_line: str) -> str:
            payload = _strip_leading_timestamp(raw_line).rstrip('\n')
            payload = _drop_bracket_tags(payload).rstrip()
            if not payload:
                return "\n"
            if payload.startswith('at '):
                return f"    {payload}\n"
            if payload.startswith('Caused by') or payload.startswith('Suppressed:'):
                return f"{payload}\n"
            if payload.startswith('...') and payload.endswith('more'):
                return f"    {payload}\n"
            if _looks_like_java_frame(payload):
                return f"    at {payload}\n"
            return f"    {payload}\n"

        def _format_main_line(raw_line: str) -> str:
            payload = _strip_leading_timestamp(raw_line).rstrip('\n')
            payload = payload.rstrip()
            return f"{payload}\n" if payload else "\n"

        def _format_ctx_line(raw_line: str) -> str:
            payload = _strip_leading_timestamp(raw_line).rstrip('\n').rstrip()
            return payload

        def _is_stack_line(s: str) -> bool:
            payload = _strip_leading_timestamp(s).rstrip('\n')
            t = _drop_bracket_tags(payload).lstrip()
            if not t:
                return True
            if t.startswith('at '):
                return True
            if t.startswith('Caused by') or t.startswith('Suppressed:'):
                return True
            if t.startswith('...') and t.endswith('more'):
                return True
            if t.startswith('Traceback (most recent call last):'):
                return True
            if t.startswith('During handling of the above exception') or t.startswith('The above exception was the direct cause'):
                return True
            if t.startswith('goroutine ') or t.startswith('panic:'):
                return True
            if t.startswith('File "') or t.startswith('File '):
                return True
            if t.startswith('###') or t.startswith(';'):
                return True
            if 'nested exception is ' in t:
                return True
            if _looks_like_java_frame(t):
                return True
            return False
        
        # Separate file for errors: pod_name_YYYY-MM-DD_error.log
        today_str = datetime.date.today().isoformat()
        error_file_path = os.path.join(log_dir, f"{source_name}_{today_str}_error.log")
        
        error_file_handle = None
        log_file_handle = None
        try:
            if not s3_only:
                error_file_handle = open(error_file_path, "a", encoding="utf-8")
            
            for line_bytes in stream:
                if not line_bytes:
                    continue
                    
                # Decode bytes to string
                line_raw = line_bytes.decode('utf-8', errors='replace')
                line = _strip_ansi(line_raw)
                
                # Write to raw log
                if s3_only:
                    raw_buffer.append(line)
                else:
                    pass

                # --- Analysis Logic Per Line ---
                if any(k in line for k in clean_ignore_keywords):
                    continue

                app_level = _extract_level(line)
                payload_lower = _strip_leading_timestamp(line).lower()
                line_lower = payload_lower
                is_stack_line = _is_stack_line(line)

                if stack_capture_active and is_stack_line:
                    formatted = _format_stack_line(line)
                    error_lines.append(formatted.rstrip('\n'))
                    if s3_only:
                        error_output.append(formatted)
                    else:
                        error_file_handle.write(formatted)

                    context_buffer.append(line)
                    if len(context_buffer) > CONTEXT_LINES:
                        context_buffer.pop(0)

                    if not s3_only:
                        error_file_handle.flush()
                    continue
                
                # Simple counting
                if app_level in ('ERROR', 'FATAL') or ('error' in line_lower or 'fail' in line_lower or 'exception' in line_lower):
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
                is_error = app_level in ('ERROR', 'FATAL') or any(k in line_lower for k in default_error_keywords)
                
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

                if stack_capture_active and not is_stack_line:
                    stack_capture_active = False
                    after_context_counter = CONTEXT_LINES

                should_trigger_context = is_alert or is_error or is_record
                capture_active = stack_capture_active or after_context_counter > 0

                if should_trigger_context:
                    if not capture_active:
                        if s3_only:
                            error_output.append("-" * 40 + "\n")
                        else:
                            error_file_handle.write("-" * 40 + "\n")
                        error_lines.append("-" * 40)
                        for ctx_line in context_buffer:
                            ctx_payload = _format_ctx_line(ctx_line)
                            if s3_only:
                                error_output.append(f"{ctx_payload}\n")
                            else:
                                error_file_handle.write(f"{ctx_payload}\n")
                            error_lines.append(ctx_payload)

                    main_formatted = _format_main_line(line)
                    if s3_only:
                        error_output.append(main_formatted)
                    else:
                        error_file_handle.write(main_formatted)
                    error_lines.append(main_formatted.rstrip('\n'))

                    stack_capture_active = bool(is_error)
                    after_context_counter = 0

                else:
                    if not stack_capture_active and after_context_counter > 0:
                        ctx_payload = _format_ctx_line(line)
                        if s3_only:
                            error_output.append(f"{ctx_payload}\n")
                        else:
                            error_file_handle.write(f"{ctx_payload}\n")
                        error_lines.append(ctx_payload)
                        after_context_counter -= 1
                
                # Update context buffer (always keep last N lines)
                context_buffer.append(line)
                if len(context_buffer) > CONTEXT_LINES:
                    context_buffer.pop(0)
                    
                # Flush error file periodically or on write? 
                # Python's file object is buffered, let's flush on trigger to be safe
                if not s3_only and (should_trigger_context or stack_capture_active):
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

        if s3_only:
            try:
                if raw_buffer:
                    raw_body = "".join(raw_buffer).encode('utf-8')
                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=raw_s3_key,
                        Body=raw_body,
                        ContentType='text/plain; charset=utf-8'
                    )
                    self._record_index_entry(task, 'raw', raw_s3_key, len(raw_body), time.time())
            except Exception:
                pass

            uploaded_error_key = None
            try:
                if error_output:
                    err_body = "".join(error_output).encode('utf-8')
                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=error_s3_key,
                        Body=err_body,
                        ContentType='text/plain; charset=utf-8'
                    )
                    uploaded_error_key = error_s3_key
                    self._record_index_entry(task, 'error', error_s3_key, len(err_body), time.time())
            except Exception:
                pass

            if alerts:
                self._send_slack_alert(alerts, task, source_name, log_dir, uploaded_error_key)
            return

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
                    f.write(f"===== {source_name} =====\n")
                    for l in error_lines:
                        f.write(l)
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
        try:
            task.refresh_from_db(fields=['alert_enabled', 'slack_webhook_url', 'alert_silence_minutes', 'alert_state'])
        except Exception:
            pass
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
            log_url = f"{base_url}/logs?taskId={task.id}&filename={quote(str(error_filename), safe='')}"
            
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
        s3_client = self._get_s3_client(task)
        if s3_client:
            self._cleanup_s3(task, s3_client, retention_days=90)
            return
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
