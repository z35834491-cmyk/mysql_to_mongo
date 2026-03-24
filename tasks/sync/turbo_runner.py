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
    def _state_pvc_name(self) -> str:
        return (os.getenv("SYNC_RUNNER_STATE_PVC") or "").strip() or "shark-platform-state-pvc"

    def _state_host_path(self) -> str:
        return (os.getenv("SYNC_RUNNER_STATE_HOST_PATH") or "").strip()

    def _build_state_volume(self):
        hp = self._state_host_path()
        if hp:
            return client.V1Volume(
                name="app-state",
                host_path=client.V1HostPathVolumeSource(path=hp, type="DirectoryOrCreate"),
            )
        return client.V1Volume(
            name="app-state",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=self._state_pvc_name()
            ),
        )

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

    def _pod_name_for_shard(self, task_id: str, shard_index: int, shard_total: int) -> str:
        if shard_total <= 1:
            return self._pod_name(task_id)
        base = self._pod_name(task_id)
        return f"{base}-s{shard_index}"[:63]

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
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        selector = f"component=sync-turbo,task_id={task.task_id}"
        pods = v1.list_namespaced_pod(namespace=ns, label_selector=selector).items
        if not pods:
            return "NotFound"
        phases = {}
        for p in pods:
            ph = getattr(getattr(p, "status", None), "phase", "Unknown") or "Unknown"
            phases[ph] = phases.get(ph, 0) + 1
        # e.g. "Running(2),Pending(1)"
        return ",".join([f"{k}({v})" for k, v in sorted(phases.items())])

    def stop_task_pod(self, task: SyncTask):
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        selector = f"component=sync-turbo,task_id={task.task_id}"
        pods = v1.list_namespaced_pod(namespace=ns, label_selector=selector).items
        for p in pods:
            name = getattr(getattr(p, "metadata", None), "name", "")
            if not name:
                continue
            try:
                v1.delete_namespaced_pod(name=name, namespace=ns, grace_period_seconds=0)
            except ApiException as e:
                if getattr(e, "status", None) != 404:
                    raise

    def start_task_pod(self, task: SyncTask) -> str:
        names = self.start_task_pods(task)
        return names[0] if names else ""

    def start_task_pods(self, task: SyncTask):
        v1 = self._get_core_api()
        ns = self._namespace_for_task(task)
        shard_total = int(getattr(task, "turbo_shard_count", 1) or 1)
        if shard_total not in (1, 2, 4, 8):
            shard_total = 1

        # Ensure only one turbo pod group per task.
        self.stop_task_pod(task)

        resources = self._resources(task)
        service_account = (os.getenv("SYNC_RUNNER_SERVICE_ACCOUNT") or "").strip() or None
        node_name = (os.getenv("SYNC_RUNNER_NODE_NAME") or "").strip()
        if not node_name and (os.getenv("SYNC_RUNNER_PIN_TO_MAIN_NODE") or "").strip() in ("1", "true", "True"):
            node_name = (os.getenv("MY_NODE_NAME") or "").strip()

        created = []
        for shard_index in range(shard_total):
            pod_name = self._pod_name_for_shard(task.task_id, shard_index, shard_total)
            container = client.V1Container(
                name="sync-worker",
                image=self._runner_image(),
                image_pull_policy=(os.getenv("SYNC_RUNNER_IMAGE_PULL_POLICY") or "IfNotPresent"),
                command=[
                    "python",
                    "manage.py",
                    "run_sync_task",
                    "--task-id",
                    task.task_id,
                    "--shard-total",
                    str(shard_total),
                    "--shard-index",
                    str(shard_index),
                ],
                env=[
                    client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
                    client.V1EnvVar(name="RUN_SYNC_TASK_ONLY", value="1"),
                ],
                resources=resources,
                volume_mounts=[
                    client.V1VolumeMount(name="app-state", mount_path="/app/state"),
                ],
            )
            metadata = client.V1ObjectMeta(
                name=pod_name,
                labels={
                    "app": "shark-sync-turbo",
                    "component": "sync-turbo",
                    "task_id": task.task_id,
                    "shard_index": str(shard_index),
                    "shard_total": str(shard_total),
                },
            )
            spec = client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                service_account_name=service_account,
                volumes=[self._build_state_volume()],
                node_name=node_name or None,
            )
            body = client.V1Pod(metadata=metadata, spec=spec)
            v1.create_namespaced_pod(namespace=ns, body=body)
            created.append(pod_name)
        return created
