import datetime
import os
import base64
import logging
import hashlib
from django.utils import timezone
from django.conf import settings
import requests

from .models import PhoneAlertConfig, PhoneAlert, Schedule

logger = logging.getLogger(__name__)

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

        staff = s.staff_list[0]
        mention = staff.get('slack') or staff.get('slack_id') or staff.get('slackUserId') or staff.get('slack_user_id') or ''
        name = staff.get('name') or ''
        if mention:
            if mention.startswith('<@') and mention.endswith('>'):
                return mention
            if mention.startswith('U') and len(mention) > 3:
                return f"<@{mention}>"
            return mention
        if name:
            return name
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
    url = (config.external_api_url or '').strip().strip('`').strip('"').strip("'")
    if not url:
        logger.info("phone_alert external callback skipped: missing external_api_url (alert_id=%s action=%s)", alert.id, action)
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
    logger.info(
        "phone_alert external callback request: url=%s method=POST alert_id=%s action=%s payload=%s auth_user=%s auth_present=%s auth_fp=%s",
        url,
        alert.id,
        action,
        payload,
        username,
        bool(auth_header),
        auth_fingerprint,
    )
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        body_preview = (resp.text or "")[:500]
        logger.info(
            "phone_alert external callback response: alert_id=%s action=%s http_status=%s body_preview=%s",
            alert.id,
            action,
            resp.status_code,
            body_preview,
        )
        return resp.status_code, body_preview
    except Exception as e:
        logger.exception("phone_alert external callback exception: alert_id=%s action=%s url=%s", alert.id, action, url)
        return None, str(e)
