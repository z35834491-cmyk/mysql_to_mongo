from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import Schedule
from .serializers import ScheduleSerializer
from .models import PhoneAlertConfig, PhoneAlert
from .phone_alert import load_phone_alert_config, find_current_oncall, build_public_url, post_slack_blocks, post_external_action
from django.utils import timezone
from django.http import HttpResponse

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "code": 0,
            "data": serializer.data,
            "msg": "success"
        })

    def create(self, request, *args, **kwargs):
        # Check if input is wrapped in {code, data: [], msg}
        data = request.data
        input_data = data
        
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            input_data = data['data']
        
        is_many = isinstance(input_data, list)
        
        serializer = self.get_serializer(data=input_data, many=is_many)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response({
            "code": 0,
            "data": serializer.data,
            "msg": "success"
        }, status=status.HTTP_201_CREATED)


def _is_admin_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='Admin').exists()


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def phone_alert_config(request):
    if not _is_admin_user(request.user):
        return Response({"detail": "forbidden"}, status=403)
    cfg = PhoneAlertConfig.load()
    if request.method == 'GET':
        return Response({
            "public_url": cfg.public_url,
            "slack_webhook_url": cfg.slack_webhook_url,
            "external_api_url": cfg.external_api_url,
            "external_api_username": cfg.external_api_username,
            "incoming_token": cfg.incoming_token,
            "auto_complete_minutes": cfg.auto_complete_minutes,
            "oncall_slack_map": cfg.oncall_slack_map or {},
            "has_external_api_password": bool(cfg.external_api_password),
        })
    data = request.data or {}
    for key in ["public_url", "slack_webhook_url", "external_api_url", "external_api_username", "incoming_token", "auto_complete_minutes", "oncall_slack_map"]:
        if key in data:
            if key == 'oncall_slack_map':
                cfg.oncall_slack_map = data.get(key) or {}
            else:
                setattr(cfg, key, data.get(key) or '')
    if 'external_api_password' in data and data.get('external_api_password'):
        cfg.external_api_password = data.get('external_api_password')
    cfg.save()
    return Response({"msg": "saved"})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def phone_alert_receive(request):
    cfg = load_phone_alert_config()
    token = (cfg.incoming_token or '').strip()
    if token:
        incoming = request.headers.get('X-Phone-Alert-Token') or request.headers.get('x-phone-alert-token')
        if incoming != token:
            return Response({"detail": "unauthorized"}, status=401)

    payload = request.data or {}
    oncall = payload.get('oncall') or ''
    if not oncall:
        oncall = find_current_oncall()
    else:
        raw = str(oncall).strip()
        if raw.startswith('<@') and raw.endswith('>'):
            oncall = raw
        else:
            cleaned = raw.lstrip('@').strip()
            if cleaned.startswith('U') and len(cleaned) > 3:
                oncall = f"<@{cleaned}>"
            else:
                oncall = cleaned

    if oncall and not (str(oncall).startswith('<@') and str(oncall).endswith('>')):
        key = str(oncall).lstrip('@').strip()
        mapped = (cfg.oncall_slack_map or {}).get(key)
        if mapped:
            mapped_str = str(mapped).strip()
            if mapped_str.startswith('<@') and mapped_str.endswith('>'):
                oncall = mapped_str
            else:
                mapped_clean = mapped_str.lstrip('@').strip()
                if mapped_clean.startswith('U') and len(mapped_clean) > 3:
                    oncall = f"<@{mapped_clean}>"
                else:
                    oncall = mapped_clean

    alert = PhoneAlert.objects.create(
        status=PhoneAlert.STATUS_NEW,
        oncall=oncall,
        payload=payload,
    )

    public_url = build_public_url(cfg)
    processing_url = f"{public_url}/api/schedules/phone-alert/{alert.id}/processing?token={alert.action_token}"
    done_url = f"{public_url}/api/schedules/phone-alert/{alert.id}/done?token={alert.action_token}"

    title = payload.get('title') or payload.get('name') or 'Phone Alert'
    message = payload.get('message') or payload.get('content') or ''
    severity = payload.get('severity') or ''

    header_text = f"☎️ {title}"
    if severity:
        header_text = f"{header_text} ({severity})"

    mention_line = f"*Oncall:* {oncall}" if oncall else "*Oncall:* (not found)"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header_text}},
        {"type": "section", "text": {"type": "mrkdwn", "text": mention_line}},
    ]
    if message:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"```{str(message)[:2000]}```"}})
    blocks.append({
        "type": "actions",
        "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "处理中"}, "style": "primary", "url": processing_url},
            {"type": "button", "text": {"type": "plain_text", "text": "处理完成"}, "style": "danger", "url": done_url},
        ]
    })

    post_slack_blocks(cfg, blocks)
    return Response({"ok": True, "id": alert.id})


def _render_action_result(text):
    return HttpResponse(f"<html><body><h3>{text}</h3></body></html>", content_type="text/html")


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def phone_alert_processing(request, alert_id: int):
    token = request.query_params.get('token', '')
    try:
        alert = PhoneAlert.objects.get(id=alert_id)
    except PhoneAlert.DoesNotExist:
        return _render_action_result("Alert not found")
    print(f"[phone_alert] processing endpoint hit: alert_id={alert_id} status={alert.status}", flush=True)
    if str(alert.action_token) != str(token):
        print(f"[phone_alert] processing invalid token: alert_id={alert_id}", flush=True)
        return _render_action_result("Invalid token")
    if alert.status in [PhoneAlert.STATUS_DONE, PhoneAlert.STATUS_AUTO_DONE]:
        print(f"[phone_alert] processing ignored (already completed): alert_id={alert_id} status={alert.status}", flush=True)
        return _render_action_result("Already completed")
    if alert.status != PhoneAlert.STATUS_PROCESSING:
        alert.status = PhoneAlert.STATUS_PROCESSING
        alert.processing_at = timezone.now()
        alert.save(update_fields=['status', 'processing_at', 'updated_at'])
        cfg = load_phone_alert_config()
        print(f"[phone_alert] processing -> calling external: alert_id={alert_id}", flush=True)
        code, detail = post_external_action(cfg, alert, 'processing')
        print(f"[phone_alert] processing external done: alert_id={alert_id} http_status={code} detail={detail}", flush=True)
        alert.external_last_action = 'processing'
        alert.external_last_http_status = code
        alert.external_last_error = '' if code is not None else (detail or '')
        alert.external_last_at = timezone.now()
        alert.save(update_fields=['external_last_action', 'external_last_http_status', 'external_last_error', 'external_last_at', 'updated_at'])
        post_slack_blocks(cfg, [{"type": "section", "text": {"type": "mrkdwn", "text": f"🟦 Alert #{alert.id} marked as processing. ({alert.oncall})"}}])
    else:
        print(f"[phone_alert] processing skipped (already processing): alert_id={alert_id}", flush=True)
    return _render_action_result("Marked as processing")


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def phone_alert_done(request, alert_id: int):
    token = request.query_params.get('token', '')
    try:
        alert = PhoneAlert.objects.get(id=alert_id)
    except PhoneAlert.DoesNotExist:
        return _render_action_result("Alert not found")
    print(f"[phone_alert] done endpoint hit: alert_id={alert_id} status={alert.status}", flush=True)
    if str(alert.action_token) != str(token):
        print(f"[phone_alert] done invalid token: alert_id={alert_id}", flush=True)
        return _render_action_result("Invalid token")
    if alert.status in [PhoneAlert.STATUS_DONE, PhoneAlert.STATUS_AUTO_DONE]:
        print(f"[phone_alert] done ignored (already completed): alert_id={alert_id} status={alert.status}", flush=True)
        return _render_action_result("Already completed")
    alert.status = PhoneAlert.STATUS_DONE
    alert.done_at = timezone.now()
    if not alert.processing_at:
        alert.processing_at = alert.done_at
    alert.save(update_fields=['status', 'done_at', 'processing_at', 'updated_at'])
    cfg = load_phone_alert_config()
    print(f"[phone_alert] done -> calling external: alert_id={alert_id}", flush=True)
    code, detail = post_external_action(cfg, alert, 'done')
    print(f"[phone_alert] done external done: alert_id={alert_id} http_status={code} detail={detail}", flush=True)
    alert.external_last_action = 'done'
    alert.external_last_http_status = code
    alert.external_last_error = '' if code is not None else (detail or '')
    alert.external_last_at = timezone.now()
    alert.save(update_fields=['external_last_action', 'external_last_http_status', 'external_last_error', 'external_last_at', 'updated_at'])
    post_slack_blocks(cfg, [{"type": "section", "text": {"type": "mrkdwn", "text": f"✅ Alert #{alert.id} completed. ({alert.oncall})"}}])
    return _render_action_result("Marked as done")
