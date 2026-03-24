import os
import re
from typing import Optional, Dict

from tasks.models import SyncTask

try:
    from kubernetes import client, config as k8s_config
    from kubernetes.client.rest import ApiException
except Exception:  # pragma: no cover - import guard for environments without kubernetes package
    client = None
    k8s_config = None
    ApiException = Exception


def _read_incluster_namespace() -> Optional[str]:
    p = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    try:
        with open(p, "r", encoding="utf-8") as f:
            return (f.read() or "").strip() or None
    except Exception:
        return None


class TurboPodRunner:
    def _get_core_api(self):
        if client is None or k8s_config is None:
            raise RuntimeError("kubernetes package not installed")

        try:
            k8s_config.load_incluster_config()
            return client.CoreV1Api()
        except Exception:
            pass

        try:
            k8s_config.load_kube_config()
            return client.CoreV1Api()
        except Exception as e:
            raise RuntimeError(f"Failed to load kube config: {e}")

    def _namespace_for_task(self, task: SyncTask) -> str:
        return (
            (task.turbo_pod_namespace or "").strip()
            or (os.getenv("SYNC_RUNNER_NAMESPACE") or "").strip()
            or _read_incluster_namespace()
            or "default"
        )

    def _runner_image(self) -> str:
        return (
            (os.getenv("SYNC_RUNNER_IMAGE") or "").strip()
            or (os.getenv("SHARK_PLATFORM_IMAGE") or "").strip()
            or "shark-platform:latest"
        )

    def _pod_name(self, task_id: str) -> str:
        base = re.sub(r"[^a-z0-9-]+", "-", task_id.lower()).strip("-")
        if not base:
            base = "task"
        return f"sync-turbo-{base}"[:63]

    def _resources(self, task: SyncTask):
        if task.turbo_no_limit:
            return None

        req: Dict[str, str] = {}
        lim: Dict[str, str] = {}
        if task.turbo_cpu_request:
            req["cpu"] = task.turbo_cpu_request
        if task.turbo_mem_request:
            req["memory"] = task.turbo_mem_request
        if task.turbo_cpu_limit:
            lim["cpu"] = task.turbo_cpu_limit
        if task.turbo_mem_limit:
            lim["memory"] = task.turbo_mem_limit
        if not req and not lim:
            return None
        return client.V1ResourceRequirements(requests=req or None, limits=lim or None)

    def get_pod_phase(self, task: SyncTask) -> Optional[str]:
        pod_name = (task.turbo_pod_name or "").strip()
        if not pod_name:
            return None
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        try:
            pod = v1.read_namespaced_pod(name=pod_name, namespace=ns)
            return getattr(getattr(pod, "status", None), "phase", None)
        except ApiException as e:
            if getattr(e, "status", None) == 404:
                return "NotFound"
            raise

    def stop_task_pod(self, task: SyncTask):
        pod_name = (task.turbo_pod_name or "").strip()
        if not pod_name:
            return
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        try:
            v1.delete_namespaced_pod(name=pod_name, namespace=ns, grace_period_seconds=0)
        except ApiException as e:
            if getattr(e, "status", None) != 404:
                raise

    def start_task_pod(self, task: SyncTask) -> str:
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        pod_name = self._pod_name(task.task_id)

        # Ensure only one turbo pod per task.
        try:
            v1.delete_namespaced_pod(name=pod_name, namespace=ns, grace_period_seconds=0)
        except ApiException as e:
            if getattr(e, "status", None) != 404:
                raise

        resources = self._resources(task)
        service_account = (os.getenv("SYNC_RUNNER_SERVICE_ACCOUNT") or "").strip() or None

        container = client.V1Container(
            name="sync-worker",
            image=self._runner_image(),
            image_pull_policy=(os.getenv("SYNC_RUNNER_IMAGE_PULL_POLICY") or "IfNotPresent"),
            command=["python", "manage.py", "run_sync_task", "--task-id", task.task_id],
            env=[client.V1EnvVar(name="PYTHONUNBUFFERED", value="1")],
            resources=resources,
        )
        metadata = client.V1ObjectMeta(
            name=pod_name,
            labels={
                "app": "shark-platform",
                "component": "sync-turbo",
                "task_id": task.task_id,
            },
        )
        spec = client.V1PodSpec(
            restart_policy="Never",
            containers=[container],
            service_account_name=service_account,
        )
        body = client.V1Pod(metadata=metadata, spec=spec)
        v1.create_namespaced_pod(namespace=ns, body=body)
        return pod_name
