import hashlib
import json
import logging
import threading

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import AIConfig, Incident
from .services.analyzer import FaultAnalyzer

logger = logging.getLogger(__name__)


def get_alert_fingerprint(alert):
    if "fingerprint" in alert:
        return alert["fingerprint"]

    labels = alert.get("labels", {})
    label_str = json.dumps(labels, sort_keys=True)
    return hashlib.md5(label_str.encode("utf-8")).hexdigest()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ai_config(request):
    if request.method == "GET":
        config = AIConfig.get_active_config()
        return Response(
            {
                "provider": config.provider,
                "api_base": config.api_base,
                "api_key": config.api_key,
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "prompt_template": config.prompt_template,
                "final_prompt_template": config.final_prompt_template,
                "enable_ai_analysis": config.enable_ai_analysis,
                "evidence_first_workflow": config.evidence_first_workflow,
            }
        )
    config = AIConfig.get_active_config()
    data = request.data
    config.provider = data.get("provider", config.provider)
    config.api_base = data.get("api_base", config.api_base)
    config.api_key = data.get("api_key", config.api_key)
    config.model = data.get("model", config.model)
    config.max_tokens = int(data.get("max_tokens", config.max_tokens))
    config.temperature = float(data.get("temperature", config.temperature))
    config.prompt_template = data.get("prompt_template", config.prompt_template)
    config.final_prompt_template = data.get(
        "final_prompt_template", config.final_prompt_template
    )
    if "enable_ai_analysis" in data:
        config.enable_ai_analysis = bool(data.get("enable_ai_analysis"))
    if "evidence_first_workflow" in data:
        config.evidence_first_workflow = bool(data.get("evidence_first_workflow"))
    config.save()
    return Response({"msg": "Configuration updated"})


@api_view(["POST"])
@permission_classes([AllowAny])
def prometheus_webhook(request):
    """
    Receiver for Prometheus Alertmanager Webhook
    """
    try:
        data = request.data
        alerts = data.get("alerts", [])

        for alert in alerts:
            status = alert.get("status")
            labels = alert.get("labels", {})
            alert_name = labels.get("alertname", "Unknown Alert")
            severity = labels.get("severity", "warning")
            fingerprint = get_alert_fingerprint(alert)

            if status == "resolved":
                Incident.objects.filter(
                    fingerprint=fingerprint,
                    status__in=["open", "analyzing", "analyzed", "awaiting_evidence"],
                ).update(status="resolved", resolved_at=timezone.now())
                logger.info(f"Alert resolved: {alert_name} ({fingerprint})")
                continue

            if status != "firing":
                continue

            incident = Incident.objects.filter(fingerprint=fingerprint).exclude(
                status="resolved"
            ).first()

            should_analyze = False

            if incident:
                incident.occurrence_count += 1
                if incident.last_analyzed_at:
                    time_since_analysis = timezone.now() - incident.last_analyzed_at
                    if time_since_analysis.total_seconds() > 3600:
                        should_analyze = True
                else:
                    should_analyze = True
                incident.save()
                logger.info(
                    f"Alert duplicated: {alert_name} ({fingerprint}), count: {incident.occurrence_count}"
                )
            else:
                incident = Incident.objects.create(
                    alert_name=alert_name,
                    severity=severity,
                    started_at=alert.get("startsAt", timezone.now()),
                    description=alert.get("annotations", {}).get("description", ""),
                    raw_alert_data=alert,
                    fingerprint=fingerprint,
                    occurrence_count=1,
                )
                should_analyze = True
                logger.info(f"New incident created: {alert_name} ({fingerprint})")

            if should_analyze:
                incident.last_analyzed_at = timezone.now()
                incident.save(update_fields=["last_analyzed_at"])

                def run_analysis(inc):
                    analyzer = FaultAnalyzer(inc)
                    analyzer.analyze()

                threading.Thread(target=run_analysis, args=(incident,)).start()

        return Response({"msg": "Alerts received", "count": len(alerts)})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def incident_list(request):
    cutoff = timezone.now() - timezone.timedelta(days=7)
    Incident.objects.filter(
        status="resolved", resolved_at__isnull=False, resolved_at__lt=cutoff
    ).delete()

    incidents = Incident.objects.exclude(status="resolved").order_by("-created_at")
    data = []
    for inc in incidents:
        data.append(
            {
                "id": inc.id,
                "alert_name": inc.alert_name,
                "severity": inc.severity,
                "status": inc.status,
                "started_at": inc.started_at,
                "created_at": inc.created_at,
            }
        )
    return Response({"incidents": data})


def _report_payload(report):
    return {
        "phenomenon": report.phenomenon,
        "root_cause": report.root_cause,
        "mitigation": report.mitigation,
        "prevention": report.prevention,
        "refactoring": report.refactoring,
        "platform_linkage": report.platform_linkage,
        "solutions": report.solutions,
        "related_metrics": report.related_metrics,
        "diagnosis_logs": report.diagnosis_logs,
        "k8s_events": report.k8s_events,
        "k8s_pod_status": report.k8s_pod_status,
        "created_at": report.created_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def incident_detail(request, pk):
    try:
        incident = Incident.objects.get(pk=pk)
        report = None
        if hasattr(incident, "report"):
            report = _report_payload(incident.report)

        chart_metrics = None
        if report and report.get("related_metrics"):
            chart_metrics = report["related_metrics"]
        elif incident.prefetched_metrics:
            chart_metrics = incident.prefetched_metrics

        return Response(
            {
                "id": incident.id,
                "alert_name": incident.alert_name,
                "severity": incident.severity,
                "status": incident.status,
                "description": incident.description,
                "raw_alert_data": incident.raw_alert_data,
                "evidence_checklist": incident.evidence_checklist,
                "user_evidence": incident.user_evidence,
                "prefetched_metrics": incident.prefetched_metrics,
                "chart_metrics": chart_metrics,
                "report": report,
            }
        )
    except Incident.DoesNotExist:
        return Response({"error": "Incident not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_incident_evidence(request, pk):
    try:
        incident = Incident.objects.get(pk=pk)
    except Incident.DoesNotExist:
        return Response({"error": "Incident not found"}, status=404)

    if incident.status != "awaiting_evidence":
        return Response(
            {"error": "Incident is not waiting for evidence"},
            status=400,
        )

    evidence = request.data.get("evidence")
    if not isinstance(evidence, dict):
        return Response({"error": "evidence must be a JSON object"}, status=400)

    non_empty = {k: v for k, v in evidence.items() if str(v or "").strip()}
    if not non_empty:
        return Response({"error": "At least one non-empty evidence field is required"}, status=400)

    def run_finalize(inc_id, ev):
        try:
            inc = Incident.objects.get(pk=inc_id)
            FaultAnalyzer(inc).finalize_with_user_evidence(ev)
        except Exception as e:
            logger.error(f"finalize_with_user_evidence failed: {e}", exc_info=True)

    threading.Thread(target=run_finalize, args=(incident.id, non_empty)).start()
    return Response({"msg": "Evidence submitted; analysis started"})
