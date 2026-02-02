import datetime
import os
import base64
import hashlib
from django.utils import timezone
from django.conf import settings
import requests

from .models import PhoneAlertConfig, PhoneAlert, Schedule


def load_phone_alert_config():
    return PhoneAlertConfig.load()


def _parse_time(value):
    try:
        parts = [int(x) for x in value.split(':')]
        while len(parts) < 3:
            parts.append(0)
        return datetime.time(parts[0], parts[1], parts[2])
    except Exception:
        return None


def find_current_oncall(now=None):
    now = now or timezone.localtime()
    today = now.date()
    current_time = now.time()

    schedules = Schedule.objects.filter(shift_date=today)
    for s in schedules:
        st = _parse_time(s.start_time)
        et = _parse_time(s.end_time)
        if not st or not et:
            continue

        in_range = False
        if et >= st:
            in_range = st <= current_time <= et
        else:
            in_range = current_time >= st or current_time <= et

        if not in_range:
            continue

        if not s.staff_list:
            continue

        mentions = []
        for staff in s.staff_list:
            mention = staff.get('slack') or staff.get('slack_id') or staff.get('slackUserId') or staff.get('slack_user_id') or ''
            name = staff.get('name') or ''
            if mention:
                m = str(mention).strip()
                if m.startswith('<@') and m.endswith('>'):
                    mentions.append(m)
                    continue
                if m.startswith('U') and len(m) > 3:
                    mentions.append(f"<@{m}>")
                    continue
                cleaned = m.lstrip('@').strip()
                if cleaned:
                    mentions.append(cleaned)
                    continue
            if name:
                cleaned = str(name).lstrip('@').strip()
                if cleaned:
                    mentions.append(cleaned)

        if mentions:
            seen = set()
            uniq = []
            for m in mentions:
                if m in seen:
                    continue
                seen.add(m)
                uniq.append(m)
            return ' '.join(uniq)
    return ''


def build_public_url(config: PhoneAlertConfig):
    url = (config.public_url or '').strip()
    if url:
        return url.rstrip('/')
    env_url = os.environ.get('PUBLIC_URL')
    if env_url:
        return env_url.rstrip('/')
    setting_url = getattr(settings, 'PUBLIC_URL', '')
    if setting_url:
        return str(setting_url).rstrip('/')
    return 'http://localhost:5173'


def post_slack_blocks(config: PhoneAlertConfig, blocks):
    webhook = (config.slack_webhook_url or '').strip()
    if not webhook:
        return False, 'missing webhook'
    try:
        resp = requests.post(webhook, json={"blocks": blocks}, timeout=5)
        return resp.ok, f"{resp.status_code}"
    except Exception as e:
        return False, str(e)


def post_external_action(config: PhoneAlertConfig, alert: PhoneAlert, action: str):
    url = (config.external_api_url or '').strip().strip('"').strip("'").replace('`', '').strip()
    if not url:
        print(f"[phone_alert] external callback skipped: missing external_api_url alert_id={alert.id} action={action}", flush=True)
        return None, 'missing external_api_url'
    headers = {"Content-Type": "application/json"}
    username = (config.external_api_username or '').strip()
    password = (config.external_api_password or '').strip()
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    status = "PROCESSING" if action == "processing" else "COMPLETED"
    payload = {"status": status}

    auth_header = headers.get("Authorization", "")
    auth_fingerprint = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:12] if auth_header else ""
    print(
        f"[phone_alert] external callback request: url={url} method=POST alert_id={alert.id} action={action} "
        f"payload={payload} auth_user={username} auth_present={bool(auth_header)} auth_fp={auth_fingerprint}",
        flush=True,
    )
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        body_preview = (resp.text or "")[:500]
        effective_status = resp.status_code
        app_code = None
        try:
            data = resp.json()
            if isinstance(data, dict) and 'code' in data:
                app_code = data.get('code')
                if isinstance(app_code, int) and app_code and resp.status_code == 200:
                    effective_status = app_code
        except Exception:
            pass
        print(
            f"[phone_alert] external callback response: alert_id={alert.id} action={action} http_status={resp.status_code} "
            f"app_code={app_code} effective_status={effective_status} body_preview={body_preview}",
            flush=True,
        )
        return effective_status, body_preview
    except Exception as e:
        print(f"[phone_alert] external callback exception: alert_id={alert.id} action={action} url={url} err={e}", flush=True)
        return None, str(e)
