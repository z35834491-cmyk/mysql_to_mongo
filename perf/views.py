import datetime
import json
import math
import os
import tempfile

import requests
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import logging
from django.http import HttpResponse

from ai_ops.models import AIConfig
from api.views import HasRolePermission
from .engine import perf_engine
from .tasks import analyze_capacity_task
from .models import ClusterConfig, ServiceProfile, LoadTestReport, PerfJob

try:
    from kubernetes import client, config as k8s_config
except ImportError:
    client = None
    k8s_config = None


def _parse_rfc3339(s: str):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None


def _prom_query_range(base_url: str, query: str, start_ts: float, end_ts: float, step_sec: int):
    url = base_url.rstrip("/") + "/api/v1/query_range"
    params = {
        "query": query,
        "start": start_ts,
        "end": end_ts,
        "step": max(1, int(step_sec)),
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(json.dumps(data))
    return data.get("data", {}).get("result", []) or []


def _series_to_points(series_list):
    points = {}
    for s in series_list:
        for ts, val in s.get("values", []) or []:
            try:
                t = float(ts)
                v = float(val)
            except Exception:
                continue
            points.setdefault(t, 0.0)
            points[t] += v
    items = sorted(points.items(), key=lambda x: x[0])
    return items


def _linregress(xs, ys):
    try:
        import numpy as np
        from scipy import stats
        n = min(len(xs), len(ys))
        if n < 2:
            return None
        x = np.array(xs[:n], dtype=float)
        y = np.array(ys[:n], dtype=float)
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return float(slope), float(intercept), float(abs(r_value))
    except Exception:
        n = min(len(xs), len(ys))
        if n < 2:
            return None
        x = xs[:n]
        y = ys[:n]
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        sxx = sum((xi - x_mean) ** 2 for xi in x)
        if sxx == 0:
            return None
        sxy = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        slope = sxy / sxx
        intercept = y_mean - slope * x_mean
        syy = sum((yi - y_mean) ** 2 for yi in y)
        if syy <= 0:
            r = 0.0
        else:
            r = sxy / math.sqrt(sxx * syy)
        return slope, intercept, r


def _load_kube_config(kube_config_text: str):
    if not k8s_config:
        raise RuntimeError("kubernetes package not installed")
    if kube_config_text:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write(kube_config_text)
            tf.flush()
            k8s_config.load_kube_config(config_file=tf.name)
            os.unlink(tf.name)
    else:
        k8s_config.load_incluster_config()


def _parse_cpu_to_cores(v: str):
    if v is None:
        return None
    try:
        s = str(v).strip()
        if s.endswith("m"):
            return float(s[:-1]) / 1000.0
        return float(s)
    except Exception:
        return None


def _get_workload_cpu_limit(cluster: ClusterConfig, namespace: str, workload_kind: str, workload_name: str, container_name: str = ""):
    if not client:
        return None
    try:
        _load_kube_config(cluster.kube_config)
    except Exception:
        return None

    kind = (workload_kind or "").lower()
    if kind in ("deploy", "deployment"):
        api = client.AppsV1Api()
        dep = api.read_namespaced_deployment(name=workload_name, namespace=namespace)
        containers = dep.spec.template.spec.containers or []
        target = None
        if container_name:
            for c in containers:
                if c.name == container_name:
                    target = c
                    break
        if not target and containers:
            target = containers[0]
        if not target:
            return None
        limits = (target.resources.limits or {}) if target.resources else {}
        return _parse_cpu_to_cores(limits.get("cpu"))
    return None


def _call_ai_capacity_advisor(summary: dict):
    cfg = AIConfig.get_active_config()
    if not cfg or not cfg.api_key:
        return ""
    prompt = f"""你是一个 Kubernetes 性能分析助手。请基于以下压测/指标信息输出中文建议（Markdown）。

服务: {summary.get('service_name')}
命名空间: {summary.get('namespace')}
时间范围: {summary.get('start_time')} ~ {summary.get('end_time')}

拟合结果:
- 单核极限 QPS(估算): {summary.get('qps_per_core')}
- 置信度 r: {summary.get('confidence')}
- 当前 CPU Limit(核): {summary.get('cpu_limit_cores')}
- 理论单实例极限 QPS: {summary.get('max_qps_per_pod')}

请给出：
1) 可能瓶颈类型（CPU/IO/Network/DB/Unknown）
2) HPA 建议（target/最小/最大）
3) 代码/SQL/缓存/重试等优化方向（按优先级）
"""
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    try:
        resp = requests.post(f"{cfg.api_base.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return ""


@api_view(["GET", "POST"])
@permission_classes([HasRolePermission])
def cluster_list(request):
    if request.method == "GET":
        clusters = ClusterConfig.objects.all().order_by("id")
        return Response([model_to_dict(c) for c in clusters])
    data = request.data or {}
    c = ClusterConfig.objects.create(
        name=data.get("name", ""),
        kube_config=data.get("kube_config", ""),
        prometheus_url=data.get("prometheus_url", ""),
        tempo_url=data.get("tempo_url", ""),
    )
    return Response(model_to_dict(c))


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([HasRolePermission])
def cluster_detail(request, pk: int):
    try:
        c = ClusterConfig.objects.get(pk=pk)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    if request.method == "GET":
        return Response(model_to_dict(c))
    if request.method == "DELETE":
        c.delete()
        return Response({"msg": "deleted"})
    data = request.data or {}
    for f in ["name", "kube_config", "prometheus_url", "tempo_url"]:
        if f in data:
            setattr(c, f, data.get(f) or "")
    c.save()
    return Response(model_to_dict(c))


@api_view(["GET"])
@permission_classes([HasRolePermission])
def service_profiles(request):
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace")
    service_name = request.query_params.get("service_name")
    qs = ServiceProfile.objects.all().order_by("-updated_at")
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if namespace:
        qs = qs.filter(namespace=namespace)
    if service_name:
        qs = qs.filter(service_name=service_name)
    return Response([model_to_dict(x) for x in qs[:200]])


@api_view(["GET"])
@permission_classes([HasRolePermission])
def load_test_reports(request):
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace")
    service_name = request.query_params.get("service_name")
    qs = LoadTestReport.objects.all().order_by("-created_at")
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if namespace:
        qs = qs.filter(namespace=namespace)
    if service_name:
        qs = qs.filter(service_name=service_name)
    return Response([model_to_dict(x) for x in qs[:200]])


@api_view(["GET"])
@permission_classes([HasRolePermission])
def load_test_report_detail(request, pk: int):
    try:
        r = LoadTestReport.objects.get(pk=pk)
    except LoadTestReport.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    return Response(model_to_dict(r))

@api_view(["GET"])
@permission_classes([HasRolePermission])
def load_test_report_pdf(request, pk: int):
    try:
        r = LoadTestReport.objects.get(pk=pk)
    except LoadTestReport.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    html = f"""
    <html><head><meta charset="utf-8"><style>
    body {{ font-family: Arial, sans-serif; }}
    h1 {{ font-size: 20px; }}
    pre {{ white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }}
    </style></head><body>
    <h1>Load Test Report: {r.test_id}</h1>
    <p>Service: {r.namespace}/{r.service_name}</p>
    <p>Time: {r.start_time} ~ {r.end_time}</p>
    <p>Max QPS: {r.max_qps_reached} | QPS/Core: {r.qps_per_core:.3f} | Confidence: {r.confidence:.3f}</p>
    <h2>AI Suggestions</h2>
    <pre>{r.report_markdown or r.ai_suggestions}</pre>
    </body></html>
    """
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="report_{r.id}.pdf"'
        return resp
    except Exception as e:
        return Response({"error": f"pdf_failed: {e}"}, status=500)

def _run_capacity_analysis(params: dict):
    data = params or {}
    cluster_id = data.get("cluster_id")
    namespace = data.get("namespace") or "default"
    service_name = data.get("service_name") or ""
    test_id = data.get("test_id") or f"test_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    start_time = _parse_rfc3339(data.get("start_time") or "")
    end_time = _parse_rfc3339(data.get("end_time") or "")
    if not cluster_id or not service_name or not start_time or not end_time:
        raise RuntimeError("cluster_id/service_name/start_time/end_time required")
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        raise RuntimeError("cluster not found")
    if not cluster.prometheus_url:
        raise RuntimeError("prometheus_url missing in cluster config")

    qps_query = data.get("qps_query") or ""
    cpu_query = data.get("cpu_query") or ""
    if not qps_query or not cpu_query:
        raise RuntimeError("qps_query and cpu_query required")

    step_sec = int(data.get("step_sec") or 30)
    start_ts = start_time.timestamp()
    end_ts = end_time.timestamp()

    qps_series = _prom_query_range(cluster.prometheus_url, qps_query, start_ts, end_ts, step_sec)
    cpu_series = _prom_query_range(cluster.prometheus_url, cpu_query, start_ts, end_ts, step_sec)
    qps_pts = _series_to_points(qps_series)
    cpu_pts = _series_to_points(cpu_series)
    if not qps_pts or not cpu_pts:
        raise RuntimeError("no data points")

    cpu_map = {t: v for t, v in cpu_pts}
    xs = []
    ys = []
    for t, qps in qps_pts:
        cpu = cpu_map.get(t)
        if cpu is None:
            continue
        if qps is None or cpu is None:
            continue
        xs.append(float(qps))
        ys.append(float(cpu))
    reg = _linregress(xs, ys)
    if not reg:
        raise RuntimeError("regression failed")
    slope, intercept, r = reg
    if slope <= 0:
        raise RuntimeError("invalid slope")
    qps_per_core = 1.0 / slope
    confidence = float(abs(r))

    cpu_limit_cores = data.get("cpu_limit_cores")
    cpu_limit = None
    if cpu_limit_cores is not None and str(cpu_limit_cores).strip() != "":
        cpu_limit = float(cpu_limit_cores)
    else:
        workload_kind = data.get("workload_kind") or "deployment"
        workload_name = data.get("workload_name") or ""
        container_name = data.get("container_name") or ""
        if workload_name:
            cpu_limit = _get_workload_cpu_limit(cluster, namespace, workload_kind, workload_name, container_name)

    max_qps_per_pod = 0.0
    if cpu_limit and cpu_limit > 0:
        max_qps_per_pod = max(0.0, (cpu_limit - intercept) / slope)

    observed_max_qps = 0.0
    try:
        observed_max_qps = max(xs) if xs else 0.0
    except Exception:
        observed_max_qps = 0.0

    recommended_cpu = 0.0
    if observed_max_qps and observed_max_qps > 0:
        recommended_cpu = max(0.0, slope * observed_max_qps + intercept)

    bottleneck = data.get("bottleneck_type") or ("cpu" if confidence >= 0.6 else "unknown")

    summary = {
        "service_name": service_name,
        "namespace": namespace,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "qps_per_core": round(qps_per_core, 3),
        "confidence": round(confidence, 3),
        "cpu_limit_cores": cpu_limit or 0.0,
        "max_qps_per_pod": round(max_qps_per_pod, 2),
    }
    ai_md = ""
    if bool(data.get("enable_ai", True)):
        ai_md = _call_ai_capacity_advisor(summary)

    ServiceProfile.objects.update_or_create(
        cluster=cluster,
        namespace=namespace,
        service_name=service_name,
        defaults={
            "qps_per_core": float(qps_per_core),
            "recommended_cpu_cores": float(recommended_cpu),
            "bottleneck_type": bottleneck,
            "confidence": confidence,
            "ai_suggestions": ai_md,
            "analysis_meta": {
                "qps_query": qps_query,
                "cpu_query": cpu_query,
                "slope": slope,
                "intercept": intercept,
                "r": r,
            },
        },
    )

    rep = LoadTestReport.objects.create(
        cluster=cluster,
        namespace=namespace,
        service_name=service_name,
        test_id=str(test_id),
        start_time=start_time,
        end_time=end_time,
        max_qps_reached=int(observed_max_qps or 0),
        qps_per_core=float(qps_per_core),
        cpu_limit_cores=float(cpu_limit or 0.0),
        recommended_cpu_cores=float(recommended_cpu),
        confidence=confidence,
        ai_suggestions=ai_md,
        report_markdown=ai_md,
        raw_metrics={"qps": qps_series, "cpu": cpu_series},
        raw_traces={},
    )

    out = model_to_dict(rep)
    out["derived"] = summary
    return {"report_id": rep.id, "report": out}

@api_view(["POST"])
@permission_classes([HasRolePermission])
def analyze_capacity(request):
    data = request.data or {}
    job = PerfJob.objects.create(job_type="capacity_analysis", params=data, status="pending")
    try:
        analyze_capacity_task.delay(job.id)
    except Exception:
        perf_engine.start()
    return Response({"job_id": job.id, "status": job.status})


@api_view(["GET"])
@permission_classes([HasRolePermission])
def job_detail(request, pk: int):
    try:
        job = PerfJob.objects.get(pk=pk)
    except PerfJob.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    try:
        perf_engine.start()
    except Exception:
        pass
    payload = {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
    }
    return Response(payload)

@api_view(["POST"])
@permission_classes([HasRolePermission])
def set_ebpf_sampling(request):
    if not client:
        return Response({"error": "kubernetes package not installed"}, status=500)
    data = request.data or {}
    cluster_id = data.get("cluster_id")
    namespace = data.get("namespace") or "trace-system"
    ds_name = data.get("daemonset") or "beyla"
    ratio = data.get("ratio")
    if not cluster_id or ratio is None:
        return Response({"error": "cluster_id and ratio required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    try:
        _load_kube_config(cluster.kube_config)
    except Exception as e:
        return Response({"error": f"kubeconfig invalid: {e}"}, status=400)
    try:
        api = client.AppsV1Api()
        body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "beyla",
                                "env": [
                                    {"name": "OTEL_TRACES_SAMPLER", "value": "traceidratio"},
                                    {"name": "OTEL_TRACES_SAMPLER_ARG", "value": str(ratio)},
                                ]
                            }
                        ]
                    }
                }
            }
        }
        # First attempt: user-provided namespace
        try:
            api.patch_namespaced_daemon_set(name=ds_name, namespace=namespace, body=body)
            return Response({"msg": "patched", "ratio": ratio, "namespace": namespace, "daemonset": ds_name})
        except Exception as e1:
            err_msg = str(e1)
            # NotFound fallback: locate daemonset across all namespaces
            if "NotFound" in err_msg or "404" in err_msg:
                try:
                    dss = api.list_daemon_set_for_all_namespaces().items
                    found_ns = None
                    for ds in dss:
                        if getattr(ds, "metadata", None) and ds.metadata.name == ds_name:
                            found_ns = ds.metadata.namespace
                            break
                    if found_ns and found_ns != namespace:
                        api.patch_namespaced_daemon_set(name=ds_name, namespace=found_ns, body=body)
                        return Response({"msg": "patched", "ratio": ratio, "namespace": found_ns, "daemonset": ds_name})
                except Exception as e2:
                    pass
            # RBAC hint for 403
            if "Forbidden" in err_msg or "403" in err_msg:
                return Response({
                    "error": "RBAC forbidden",
                    "detail": err_msg,
                    "hint": "Grant patch permission on apps/daemonsets. See k8s/rbac-perf-editor.yaml or clusterrole variant."
                }, status=403)
            return Response({"error": err_msg}, status=500)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([HasRolePermission])
def list_services(request):
    if not client:
        return Response({"error": "kubernetes package not installed"}, status=500)
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace") or "default"
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    try:
        _load_kube_config(cluster.kube_config)
    except Exception as e:
        return Response({"error": f"kubeconfig invalid: {e}"}, status=400)
    try:
        api = client.CoreV1Api()
        svcs = api.list_namespaced_service(namespace=namespace).items
        names = sorted({s.metadata.name for s in svcs if getattr(s, "metadata", None) and s.metadata.name})
        return Response({"items": names})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([HasRolePermission])
def promql_templates(request):
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace") or "default"
    service_name = request.query_params.get("service_name") or ""
    if not cluster_id or not service_name:
        return Response({"error": "cluster_id and service_name required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    if not cluster.prometheus_url:
        return Response({"error": "prometheus_url missing in cluster config"}, status=400)

    ns = namespace
    svc = service_name
    cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{ns}",pod=~"{svc}.*",container!=""}}[1m]))'

    templates = [
        {
            "id": "istio",
            "name": "Istio QPS + Pod CPU",
            "qps_query": f'sum(rate(istio_requests_total{{destination_workload_namespace="{ns}",destination_service_name="{svc}"}}[1m]))',
            "cpu_query": cpu_query,
        },
        {
            "id": "nginx_ingress",
            "name": "Nginx Ingress QPS + Pod CPU",
            "qps_query": f'sum(rate(nginx_ingress_controller_requests{{namespace="{ns}",service="{svc}"}}[1m]))',
            "cpu_query": cpu_query,
        },
        {
            "id": "spring_actuator",
            "name": "Spring Actuator QPS + Pod CPU",
            "qps_query": f'sum(rate(http_server_requests_seconds_count{{namespace="{ns}",service="{svc}"}}[1m]))',
            "cpu_query": cpu_query,
        },
        {
            "id": "generic_http",
            "name": "Generic HTTP QPS + Pod CPU",
            "qps_query": f'sum(rate(http_requests_total{{namespace="{ns}",service="{svc}"}}[1m]))',
            "cpu_query": cpu_query,
        },
    ]
    return Response({"items": templates})


@api_view(["GET"])
@permission_classes([HasRolePermission])
def get_trace(request, trace_id: str):
    cluster_id = request.query_params.get("cluster_id")
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    if not cluster.tempo_url:
        return Response({"error": "tempo_url missing in cluster config"}, status=400)
    url = cluster.tempo_url.rstrip("/") + f"/api/traces/{trace_id}"
    try:
        resp = requests.get(url, timeout=30)
        if not resp.ok:
            return Response({"error": f"tempo {resp.status_code}", "detail": resp.text[:2000]}, status=502)
        return Response(resp.json())
    except Exception as e:
        return Response({"error": str(e)}, status=502)


def _decode_otlp_any(v):
    if v is None:
        return None
    if isinstance(v, dict):
        for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if k in v:
                return v.get(k)
    return v


def _attrs_to_dict(attrs):
    out = {}
    if not attrs:
        return out
    if isinstance(attrs, dict) and "attributes" in attrs:
        attrs = attrs.get("attributes")
    if isinstance(attrs, list):
        for a in attrs:
            if not isinstance(a, dict):
                continue
            k = a.get("key")
            if not k:
                continue
            out[k] = _decode_otlp_any(a.get("value"))
    return out


def _extract_tempo_spans_with_resource(trace_json):
    spans = []
    batches = trace_json.get("batches")
    if isinstance(batches, list):
        for b in batches:
            res_attrs = _attrs_to_dict(((b.get("resource") or {}).get("attributes")) if isinstance(b, dict) else None)
            service = res_attrs.get("service.name") or res_attrs.get("service") or ""
            namespace = res_attrs.get("k8s.namespace.name") or res_attrs.get("k8s.namespace") or ""
            pod = res_attrs.get("k8s.pod.name") or res_attrs.get("k8s.pod") or ""
            container = res_attrs.get("k8s.container.name") or res_attrs.get("k8s.container") or ""
            scopes = (b.get("scopeSpans") or b.get("instrumentationLibrarySpans") or []) if isinstance(b, dict) else []
            for s in scopes:
                ss = s.get("spans") if isinstance(s, dict) else None
                if not isinstance(ss, list):
                    continue
                for sp in ss:
                    if not isinstance(sp, dict):
                        continue
                    spans.append({**sp, "__service": service, "__namespace": namespace, "__pod": pod, "__container": container})

    trace = trace_json.get("trace")
    rs_list = trace.get("resourceSpans") if isinstance(trace, dict) else None
    if isinstance(rs_list, list):
        for rs in rs_list:
            res = rs.get("resource") if isinstance(rs, dict) else None
            res_attrs = _attrs_to_dict(res.get("attributes") if isinstance(res, dict) else None)
            service = res_attrs.get("service.name") or res_attrs.get("service") or ""
            namespace = res_attrs.get("k8s.namespace.name") or res_attrs.get("k8s.namespace") or ""
            pod = res_attrs.get("k8s.pod.name") or res_attrs.get("k8s.pod") or ""
            container = res_attrs.get("k8s.container.name") or res_attrs.get("k8s.container") or ""
            scopes = rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []
            if not isinstance(scopes, list):
                continue
            for ss in scopes:
                sp_list = ss.get("spans") if isinstance(ss, dict) else None
                if not isinstance(sp_list, list):
                    continue
                for sp in sp_list:
                    if not isinstance(sp, dict):
                        continue
                    spans.append({**sp, "__service": service, "__namespace": namespace, "__pod": pod, "__container": container})

    return spans


def _to_int(v):
    try:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _summarize_prom_series(series_list):
    pts = _series_to_points(series_list)
    if not pts:
        return {"avg": 0.0, "max": 0.0}
    vals = [v for _, v in pts if v is not None]
    if not vals:
        return {"avg": 0.0, "max": 0.0}
    return {"avg": float(sum(vals) / len(vals)), "max": float(max(vals))}


@api_view(["GET"])
@permission_classes([HasRolePermission])
def trace_insights(request, trace_id: str):
    cluster_id = request.query_params.get("cluster_id")
    lookback_sec = int(request.query_params.get("lookback_sec") or 300)
    step_sec = int(request.query_params.get("step_sec") or 15)
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    if not cluster.tempo_url:
        return Response({"error": "tempo_url missing in cluster config"}, status=400)
    if not cluster.prometheus_url:
        return Response({"error": "prometheus_url missing in cluster config"}, status=400)

    url = cluster.tempo_url.rstrip("/") + f"/api/traces/{trace_id}"
    try:
        resp = requests.get(url, timeout=30)
        if not resp.ok:
            return Response({"error": f"tempo {resp.status_code}", "detail": resp.text[:2000]}, status=502)
        trace_json = resp.json()
    except Exception as e:
        return Response({"error": str(e)}, status=502)

    spans = _extract_tempo_spans_with_resource(trace_json if isinstance(trace_json, dict) else {})
    if not spans:
        return Response({"trace": {"trace_id": trace_id, "span_count": 0}, "resources": [], "metrics": {}}, status=200)

    min_start = None
    max_end = None
    items = []
    services = set()
    resources = {}
    for sp in spans:
        start = _to_int(sp.get("startTimeUnixNano") or sp.get("startTime") or sp.get("start_time_unix_nano"))
        end = _to_int(sp.get("endTimeUnixNano") or sp.get("endTime") or sp.get("end_time_unix_nano"))
        if start is None or end is None or end <= start:
            continue
        if min_start is None or start < min_start:
            min_start = start
        if max_end is None or end > max_end:
            max_end = end
        svc = sp.get("__service") or ""
        if svc:
            services.add(str(svc))

        ns = sp.get("__namespace") or ""
        pod = sp.get("__pod") or ""
        container = sp.get("__container") or ""
        key = f"{ns}|{pod}|{container}|{svc}"
        if key not in resources:
            resources[key] = {"namespace": ns, "pod": pod, "container": container, "service": svc}

        name = sp.get("name") or sp.get("operationName") or "span"
        dur_ms = (end - start) / 1e6
        off_ms = 0.0
        items.append({"service": svc, "name": name, "duration_ms": dur_ms, "start_ns": start, "end_ns": end, "offset_ms": off_ms})

    if min_start is None or max_end is None:
        return Response({"trace": {"trace_id": trace_id, "span_count": 0}, "resources": [], "metrics": {}}, status=200)

    for it in items:
        it["offset_ms"] = (it["start_ns"] - min_start) / 1e6
        it.pop("start_ns", None)
        it.pop("end_ns", None)

    items.sort(key=lambda x: (-float(x.get("duration_ms") or 0.0), float(x.get("offset_ms") or 0.0)))
    top_spans = items[:20]

    start_ts = (min_start / 1e9) - max(0, lookback_sec)
    end_ts = (max_end / 1e9) + max(0, lookback_sec)

    metrics = []
    for r in list(resources.values())[:50]:
        ns = str(r.get("namespace") or "")
        pod = str(r.get("pod") or "")
        container = str(r.get("container") or "")
        if not ns or not pod:
            continue
        cpu_q = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{ns}",pod="{pod}",container!=""}}[1m]))'
        mem_q = f'sum(container_memory_working_set_bytes{{namespace="{ns}",pod="{pod}",container!=""}})'
        cpu_series = _prom_query_range(cluster.prometheus_url, cpu_q, start_ts, end_ts, step_sec)
        mem_series = _prom_query_range(cluster.prometheus_url, mem_q, start_ts, end_ts, step_sec)
        cpu_s = _summarize_prom_series(cpu_series)
        mem_s = _summarize_prom_series(mem_series)
        metrics.append({
            "namespace": ns,
            "pod": pod,
            "container": container,
            "service": r.get("service") or "",
            "cpu_cores_avg": round(cpu_s["avg"], 4),
            "cpu_cores_max": round(cpu_s["max"], 4),
            "mem_mb_avg": round(mem_s["avg"] / 1024 / 1024, 2),
            "mem_mb_max": round(mem_s["max"] / 1024 / 1024, 2),
        })

    out = {
        "trace": {
            "trace_id": trace_id,
            "span_count": len(items),
            "duration_ms": round((max_end - min_start) / 1e6, 2),
            "services": sorted(services),
            "top_spans": top_spans,
        },
        "resources": list(resources.values()),
        "metrics": metrics,
        "window": {"start_ts": start_ts, "end_ts": end_ts, "step_sec": step_sec},
    }
    return Response(out)


@api_view(["GET"])
@permission_classes([HasRolePermission])
def search_traces(request):
    cluster_id = request.query_params.get("cluster_id")
    limit = int(request.query_params.get("limit") or 20)
    service_name = request.query_params.get("service_name") or ""
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    if not cluster.tempo_url:
        return Response({"error": "tempo_url missing in cluster config"}, status=400)

    base = cluster.tempo_url.rstrip("/")
    url = base + f"/api/search?limit={limit}"
    urls = [url]
    if service_name:
        urls = [
            base + f"/api/search?limit={limit}&tags=service.name={service_name}",
            base + f"/api/search?limit={limit}&tags=rootServiceName={service_name}",
        ]
    try:
        traces = []
        last_err = None
        for u in urls:
            logging.getLogger("perf").info(f"tempo_search url={u} cluster_id={cluster_id} service={service_name}")
            resp = requests.get(u, timeout=10)
            if not resp.ok:
                last_err = {"error": f"tempo {resp.status_code}", "detail": (resp.text or "")[:2000]}
                continue
            data = resp.json()
            traces = data.get("traces") or []
            if traces:
                break
        if last_err and not traces:
            return Response(last_err, status=502)
        items = []
        for t in traces:
            items.append({
                "traceID": t.get("traceID"),
                "rootServiceName": t.get("rootServiceName"),
                "rootTraceName": t.get("rootTraceName"),
                "startTimeUnixNano": t.get("startTimeUnixNano"),
                "durationMs": t.get("durationMs"),
            })
        logging.getLogger("perf").info(f"tempo_search result_count={len(items)}")
        return Response({"items": items})
    except Exception as e:
        logging.getLogger("perf").error(f"tempo_search error={e}")
        return Response({"error": str(e)}, status=502)

@api_view(["GET"])
@permission_classes([HasRolePermission])
def tempo_diagnostics(request):
    cluster_id = request.query_params.get("cluster_id")
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    url = (cluster.tempo_url or "").rstrip("/")
    if not url:
        return Response({"ok": False, "reason": "tempo_url missing in cluster config"})
    results = {"base": url, "checks": [], "metrics": {}}
    def _check(path):
        full = f"{url}{path}"
        try:
            r = requests.get(full, timeout=10)
            results["checks"].append({"url": full, "status": r.status_code, "ok": bool(r.ok), "len": len(r.text or ""), "preview": (r.text or "")[:300]})
        except Exception as e:
            results["checks"].append({"url": full, "error": str(e)})
    _check("/api/search?limit=1")
    _check("/api/search?limit=1&tags=service.name=*")
    _check("/api/search?limit=1&tags=rootServiceName=*")
    _check("/ready")
    _check("/metrics")
    try:
        import re
        metrics_url = f"{url}/metrics"
        r = requests.get(metrics_url, timeout=10)
        if r.ok:
            text = r.text or ""
            def _find(name: str):
                m = re.search(rf"(?m)^{re.escape(name)}\{{[^}}]*\}}\s+([0-9eE\+\.-]+)$", text)
                if m:
                    return float(m.group(1))
                m2 = re.search(rf"(?m)^{re.escape(name)}\s+([0-9eE\+\.-]+)$", text)
                if m2:
                    return float(m2.group(1))
                return None
            keys = [
                "tempo_distributor_spans_received_total",
                "tempo_distributor_spans_dropped_total",
                "tempo_distributor_traces_received_total",
                "tempo_distributor_traces_dropped_total",
                "tempo_ingester_traces_created_total",
                "tempo_ingester_spans_created_total",
            ]
            for k in keys:
                v = _find(k)
                if v is not None:
                    results["metrics"][k] = v
    except Exception:
        pass
    ok = any(c.get("ok") for c in results["checks"])
    results["ok"] = ok
    return Response(results)


@api_view(["GET"])
@permission_classes([HasRolePermission])
def discover_trace_services(request):
    cluster_id = request.query_params.get("cluster_id")
    limit = int(request.query_params.get("limit") or 200)
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    if not cluster.tempo_url:
        return Response({"error": "tempo_url missing in cluster config"}, status=400)
    base = cluster.tempo_url.rstrip("/")
    url = base + f"/api/search?limit={limit}"
    try:
        resp = requests.get(url, timeout=15)
        if not resp.ok:
            return Response({"error": f"tempo {resp.status_code}", "detail": (resp.text or "")[:2000]}, status=502)
        data = resp.json() if resp.text else {}
        traces = (data or {}).get("traces") or []
        names = []
        for t in traces:
            n = (t or {}).get("rootServiceName") or ""
            if n:
                names.append(str(n))
        uniq = sorted(list(set(names)))
        return Response({"items": uniq})
    except Exception as e:
        return Response({"error": str(e)}, status=502)

@api_view(["GET"])
@permission_classes([HasRolePermission])
def beyla_diagnostics(request):
    if not client:
        return Response({"error": "kubernetes package not installed"}, status=500)
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace") or "trace-system"
    ds_name = request.query_params.get("daemonset") or "beyla"
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    try:
        _load_kube_config(cluster.kube_config)
    except Exception as e:
        return Response({"error": f"kubeconfig invalid: {e}"}, status=400)
    try:
        api = client.AppsV1Api()
        ds = api.read_namespaced_daemon_set(name=ds_name, namespace=namespace)
        containers = ds.spec.template.spec.containers or []
        env = []
        for c in containers:
            if c.name == "beyla":
                for e in (c.env or []):
                    env.append({"name": e.name, "value": e.value})
        out = {
            "namespace": namespace,
            "daemonset": ds_name,
            "env": env,
        }
        return Response(out)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([HasRolePermission])
def list_hpa(request):
    if not client:
        return Response({"error": "kubernetes package not installed"}, status=500)
    cluster_id = request.query_params.get("cluster_id")
    namespace = request.query_params.get("namespace") or "default"
    if not cluster_id:
        return Response({"error": "cluster_id required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    try:
        _load_kube_config(cluster.kube_config)
    except Exception as e:
        return Response({"error": f"kubeconfig invalid: {e}"}, status=400)
    try:
        try:
            api = client.AutoscalingV2Api()
            hpas = api.list_namespaced_horizontal_pod_autoscaler(namespace=namespace).items
        except Exception:
            api = client.AutoscalingV1Api()
            hpas = api.list_namespaced_horizontal_pod_autoscaler(namespace=namespace).items
        out = []
        for h in hpas:
            out.append({
                "name": h.metadata.name,
                "namespace": h.metadata.namespace,
                "spec": h.spec.to_dict() if getattr(h, "spec", None) else {},
                "status": h.status.to_dict() if getattr(h, "status", None) else {},
            })
        return Response({"items": out})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([HasRolePermission])
def apply_hpa(request):
    if not client:
        return Response({"error": "kubernetes package not installed"}, status=500)
    data = request.data or {}
    cluster_id = data.get("cluster_id")
    namespace = data.get("namespace") or "default"
    name = data.get("name")
    if not cluster_id or not name:
        return Response({"error": "cluster_id and name required"}, status=400)
    try:
        cluster = ClusterConfig.objects.get(pk=cluster_id)
    except ClusterConfig.DoesNotExist:
        return Response({"error": "cluster not found"}, status=404)
    try:
        _load_kube_config(cluster.kube_config)
    except Exception as e:
        return Response({"error": f"kubeconfig invalid: {e}"}, status=400)

    min_replicas = data.get("minReplicas")
    max_replicas = data.get("maxReplicas")
    target_cpu = data.get("targetCPUUtilization")

    patch_v2 = {"spec": {}}
    if min_replicas is not None:
        patch_v2["spec"]["minReplicas"] = int(min_replicas)
    if max_replicas is not None:
        patch_v2["spec"]["maxReplicas"] = int(max_replicas)
    if target_cpu is not None:
        patch_v2["spec"]["metrics"] = [{
            "type": "Resource",
            "resource": {
                "name": "cpu",
                "target": {"type": "Utilization", "averageUtilization": int(target_cpu)},
            }
        }]

    try:
        api = client.AutoscalingV2Api()
        api.patch_namespaced_horizontal_pod_autoscaler(name=name, namespace=namespace, body=patch_v2)
        return Response({"msg": "patched"})
    except Exception:
        patch_v1 = {"spec": {}}
        if min_replicas is not None:
            patch_v1["spec"]["minReplicas"] = int(min_replicas)
        if max_replicas is not None:
            patch_v1["spec"]["maxReplicas"] = int(max_replicas)
        if target_cpu is not None:
            patch_v1["spec"]["targetCPUUtilizationPercentage"] = int(target_cpu)
        try:
            api = client.AutoscalingV1Api()
            api.patch_namespaced_horizontal_pod_autoscaler(name=name, namespace=namespace, body=patch_v1)
            return Response({"msg": "patched"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)
