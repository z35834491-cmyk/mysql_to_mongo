import json
import logging
from ..models import Incident, AnalysisReport
import datetime
from django.utils import timezone
import requests
from inspection.models import InspectionConfig

try:
    from kubernetes import client, config
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

logger = logging.getLogger(__name__)

class DiagnosticStrategy:
    """
    Defines how to collect diagnostic data for different types of alerts
    """
    @staticmethod
    def get_queries(alert_name, labels):
        """
        Returns a dict of {metric_name: promql_query} based on alert type
        """
        queries = {}
        instance = labels.get('instance')
        node = labels.get('node') or labels.get('nodename')
        namespace = labels.get('namespace')
        pod = labels.get('pod')

        # Base filter
        # Prefer 'node' label if available for cAdvisor/Kubelet metrics, otherwise try instance
        # Note: instance in node_exporter is usually IP:Port, in cAdvisor it might be NodeName
        node_filter_cadvisor = f'node="{node}"' if node else (f'instance="{instance}"' if instance else "")
        node_filter_nodeexp = f'instance="{instance}"' if instance else (f'node="{node}"' if node else "")
        
        pod_filter = f'namespace="{namespace}", pod="{pod}"' if namespace and pod else ""

        if 'CPU' in alert_name:
            if pod_filter:
                # Pod level CPU
                queries['pod_cpu_usage'] = f'rate(container_cpu_usage_seconds_total{{{pod_filter}}}[5m])'
            else:
                # Node level CPU
                if node_filter_nodeexp:
                    queries['node_cpu_usage'] = f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle", {node_filter_nodeexp}}}[5m])) * 100)'
                
                # Top 5 Processes/Containers on the node
                # We use a broad regex for instance if we only have IP, or just rely on node label if present
                filter_str = node_filter_cadvisor if node_filter_cadvisor else 'id="/"' # Fallback
                queries['top10_cpu_containers'] = f'topk(10, sort_desc(rate(container_cpu_usage_seconds_total{{{filter_str}}}[5m])))'

        elif 'Memory' in alert_name:
            if pod_filter:
                queries['pod_memory_usage'] = f'container_memory_usage_bytes{{{pod_filter}}}'
            else:
                if node_filter_nodeexp:
                    queries['node_memory_usage'] = f'100 * (1 - node_memory_MemFree_bytes{{{node_filter_nodeexp}}} / node_memory_MemTotal_bytes{{{node_filter_nodeexp}}})'
                
                filter_str = node_filter_cadvisor if node_filter_cadvisor else 'id="/"'
                queries['top10_mem_containers'] = f'topk(10, sort_desc(container_memory_usage_bytes{{{filter_str}}}))'

        elif 'IO' in alert_name or 'Disk' in alert_name:
            if pod_filter:
                queries['pod_io_read'] = f'rate(container_fs_reads_bytes_total{{{pod_filter}}}[5m])'
                queries['pod_io_write'] = f'rate(container_fs_writes_bytes_total{{{pod_filter}}}[5m])'
            else:
                if node_filter_nodeexp:
                    queries['node_disk_read'] = f'rate(node_disk_read_bytes_total{{{node_filter_nodeexp}}}[5m])'
                    queries['node_disk_write'] = f'rate(node_disk_written_bytes_total{{{node_filter_nodeexp}}}[5m])'
                    queries['node_disk_util'] = f'rate(node_disk_io_time_seconds_total{{{node_filter_nodeexp}}}[5m])'
                
                filter_str = node_filter_cadvisor if node_filter_cadvisor else 'id="/"'
                queries['top10_io_containers'] = f'topk(10, sort_desc(rate(container_fs_writes_bytes_total{{{filter_str}}}[5m]) + rate(container_fs_reads_bytes_total{{{filter_str}}}[5m])))'

        return queries

class FaultAnalyzer:
    def __init__(self, incident: Incident):
        self.incident = incident
        self.config = InspectionConfig.load()

    def analyze(self):
        logger.info(f"Starting analysis for incident {self.incident.id}")
        self.incident.status = 'analyzing'
        self.incident.save(update_fields=['status'])

        try:
            # 1. Parse Alert & Gather Context
            context_data = self._gather_context()
            
            # 2. Call AI
            ai_result = self._call_ai_service(context_data)
            
            # 3. Save Report
            AnalysisReport.objects.create(
                incident=self.incident,
                phenomenon=ai_result.get('phenomenon', 'Unknown phenomenon'),
                root_cause=ai_result.get('root_cause', 'Unknown root cause'),
                mitigation=ai_result.get('mitigation', 'No immediate mitigation'),
                prevention=ai_result.get('prevention', 'No prevention strategy'),
                refactoring=ai_result.get('refactoring', 'No refactoring needed'),
                solutions=ai_result.get('solutions', []),
                related_metrics=context_data.get('metrics', {}),
                diagnosis_logs=context_data.get('logs', []),
                raw_ai_response=json.dumps(ai_result)
            )
            
            self.incident.status = 'analyzed'
            self.incident.save(update_fields=['status'])
            logger.info(f"Analysis completed for incident {self.incident.id}")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.incident.status = 'open'
            self.incident.save(update_fields=['status'])

    def _gather_context(self):
        raw = self.incident.raw_alert_data
        labels = raw.get('labels', {})
        alert_name = self.incident.alert_name
        
        context = {
            "alert": raw,
            "metrics": {},
            "logs": [] # Placeholder for future command outputs (e.g. top/iotop)
        }

        # 1. Metric Collection Strategy
        queries = DiagnosticStrategy.get_queries(alert_name, labels)
        
        # Execute queries
        if self.config.prometheus_url:
            for name, query in queries.items():
                try:
                    context['metrics'][name] = self._query_prometheus(query)
                except Exception as e:
                    logger.warning(f"Failed to query metric {name}: {e}")

        # 2. Log Collection Strategy (K8s)
        if K8S_AVAILABLE:
            try:
                k8s_info = self._collect_k8s_info(labels)
                if k8s_info:
                    context['logs'].append(f"--- K8s Diagnosis ---\n{k8s_info}")
            except Exception as e:
                logger.warning(f"Failed to fetch K8s info: {e}")

        return context

    def _collect_k8s_info(self, labels):
        try:
            config.load_incluster_config()
        except:
            try:
                config.load_kube_config()
            except:
                logger.warning("No K8s config found")
                return None
        
        v1 = client.CoreV1Api()
        namespace = labels.get('namespace', 'default')
        pod_name = labels.get('pod')
        
        # If pod is not directly in labels, try to find it via deployment
        if not pod_name:
            deployment = labels.get('deployment')
            if deployment:
                try:
                    pods = v1.list_namespaced_pod(namespace)
                    for p in pods.items:
                        if p.metadata.name.startswith(deployment):
                            pod_name = p.metadata.name
                            break
                except Exception as e:
                    logger.warning(f"Failed to list pods for deployment {deployment}: {e}")

        if not pod_name:
            return None

        info_lines = []
        try:
            # 1. Get Pod Status
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            info_lines.append(f"Pod Status: {pod.status.phase}")
            
            # Add Conditions
            if pod.status.conditions:
                info_lines.append("Conditions:")
                for cond in pod.status.conditions:
                    status_symbol = "✔" if cond.status == 'True' else "✖"
                    info_lines.append(f"  [{status_symbol}] {cond.type}: {cond.reason or ''} {cond.message or ''}")

            # Analyze container statuses
            is_unhealthy = False
            container_statuses = pod.status.container_statuses or []
            for cs in container_statuses:
                status_str = "Running"
                if cs.state.waiting:
                    status_str = f"Waiting ({cs.state.waiting.reason}: {cs.state.waiting.message})"
                    is_unhealthy = True
                elif cs.state.terminated:
                    status_str = f"Terminated ({cs.state.terminated.reason}: {cs.state.terminated.message}, ExitCode: {cs.state.terminated.exit_code})"
                    if cs.state.terminated.exit_code != 0:
                        is_unhealthy = True
                elif not cs.ready:
                    status_str = "Running (Not Ready)"
                    is_unhealthy = True
                
                info_lines.append(f"Container {cs.name}: {status_str}")
                
                # Restart count check
                if cs.restart_count > 0:
                     info_lines.append(f"  Restarts: {cs.restart_count}")
                     is_unhealthy = True

            # 2. Collect Events (if unhealthy or not Running)
            # Events are useful for scheduling issues, image pull errors, probe failures
            if is_unhealthy or pod.status.phase != 'Running':
                try:
                    events = v1.list_namespaced_event(namespace, field_selector=f'involvedObject.name={pod_name}')
                    if events.items:
                        info_lines.append("\n--- K8s Events ---")
                        for e in events.items:
                            info_lines.append(f"[{e.type}] {e.reason}: {e.message}")
                except Exception as e:
                    info_lines.append(f"Failed to get events: {e}")

            # 3. Collect Logs (if likely to contain info)
            # Skip logs if ImagePullBackOff or ContainerCreating (logs usually empty)
            should_fetch_logs = True
            for cs in container_statuses:
                if cs.state.waiting and cs.state.waiting.reason in ['ImagePullBackOff', 'ErrImagePull', 'ContainerCreating', 'CreateContainerConfigError']:
                    should_fetch_logs = False
            
            if should_fetch_logs:
                try:
                    # Fetch logs (limit 50 lines)
                    logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=50)
                    if logs:
                        info_lines.append("\n--- K8s Logs ---")
                        info_lines.append(logs)
                    
                    # If previous instance failed, try to get previous logs
                    for cs in container_statuses:
                        if cs.restart_count > 0:
                             prev_logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=20, previous=True)
                             if prev_logs:
                                 info_lines.append("\n--- Previous Instance Logs ---")
                                 info_lines.append(prev_logs)
                             break # Only fetch for one container to avoid spam
                except Exception as e:
                    info_lines.append(f"Failed to fetch logs: {e}")

            return "\n".join(info_lines)

        except Exception as e:
            return f"Error analyzing pod {pod_name}: {e}"

    def _query_prometheus(self, query):
        if not self.config.prometheus_url:
            return []
        
        url = f"{self.config.prometheus_url}/api/v1/query_range"
        now = timezone.now()
        start = now - datetime.timedelta(hours=1)
        
        try:
            response = requests.get(url, params={
                "query": query,
                "start": start.timestamp(),
                "end": now.timestamp(),
                "step": "60s"
            }, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get('data', {}).get('result', [])
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return []

    def _call_ai_service(self, context):
        """
        Mock implementation of calling AI Service (ChatGPT/DeepSeek)
        """
        from ..models import AIConfig
        config = AIConfig.get_active_config()
        
        alert_name = self.incident.alert_name
        labels = self.incident.raw_alert_data.get('labels', {})
        
        # Build prompt using stored template
        # Use replace instead of format to avoid KeyError on JSON braces in the template
        prompt = config.prompt_template
        prompt = prompt.replace("{alert_name}", str(alert_name))
        prompt = prompt.replace("{raw_data}", json.dumps(self.incident.raw_alert_data, ensure_ascii=False))
        prompt = prompt.replace("{metrics}", json.dumps(context.get('metrics', {}), ensure_ascii=False))
        prompt = prompt.replace("{logs}", "\n".join(context.get('logs', [])))
        
        logger.info(f"AI Prompt: {prompt}")

        if config.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json"
                }
                
                # Adjust for different providers if needed, but OpenAI format is standard
                payload = {
                    "model": config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens
                }

                response = requests.post(
                    f"{config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Attempt to parse JSON from content (it might be wrapped in ```json ... ```)
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].strip()
                    
                return json.loads(content)
            except Exception as e:
                logger.error(f"AI Service Call Failed: {e}. Falling back to rule-based mock.")
        
        # Fallback / Mock Chinese response based on alert type
        if 'IO' in alert_name or 'Disk' in alert_name:
            return {
                "phenomenon": f"节点 {labels.get('instance', 'unknown')} 的磁盘 I/O 延迟飙升至 500ms。",
                "root_cause": "容器 'mysql-0' 内的进程 'mysql-backup' (PID 1234) 正在进行全量数据备份，且未设置 I/O 限制。",
                "mitigation": "1. 暂时使用 `ionice` 限制备份进程的 I/O 优先级。\n2. 如果严重影响生产业务，建议终止备份任务。",
                "prevention": "为所有备份 CronJob 配置 `ionice`。在备份容器上设置 IOPS 限制 (Docker/K8s limits)。",
                "refactoring": "架构优化：启用专用的只读从库 (Read-Replica) 进行备份，避免影响主库性能。",
                "solutions": ["kill 1234", "ionice -c3 -p 1234"]
            }
        
        if 'CPU' in alert_name:
            return {
                "phenomenon": f"节点 {labels.get('instance', 'unknown')} CPU 使用率超过 90%。",
                "root_cause": "Java 应用 'payment-service' 发生死循环，导致 CPU 满载。",
                "mitigation": "重启该 Pod。",
                "prevention": "设置 CPU Limit，防止单应用耗尽节点资源。",
                "refactoring": "优化代码逻辑，修复死循环 Bug。",
                "solutions": ["kubectl delete pod payment-service-xxx"]
            }

        return {
            "phenomenon": "检测到未知异常。",
            "root_cause": "需要进一步人工排查。",
            "mitigation": "检查系统日志。",
            "prevention": "完善监控指标。",
            "refactoring": "暂无建议。",
            "solutions": []
        }

    def _build_prompt(self, context):
        return f"""
        You are a Site Reliability Engineer (SRE). Analyze the following system alert and context data.
        
        Alert: {json.dumps(context['alert'])}
        Metrics (Top Consumers): {json.dumps(context['metrics'])}
        Logs: {json.dumps(context['logs'])}
        
        Please provide a structured analysis in JSON format with the following keys:
        - phenomenon: What is happening?
        - root_cause: Specifically which process/pod is responsible? Why?
        - mitigation: How to fix it immediately?
        - prevention: How to prevent recurrence (config changes)?
        - refactoring: Long-term architectural fixes?
        - solutions: A list of short command-like actions.
        """
