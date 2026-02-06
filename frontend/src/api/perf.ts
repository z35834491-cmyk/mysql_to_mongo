import request from '@/utils/request'

export interface ClusterConfig {
  id?: number
  name: string
  kube_config: string
  prometheus_url: string
  tempo_url: string
}

export interface ServiceProfile {
  id: number
  cluster: number
  namespace: string
  service_name: string
  qps_per_core: number
  recommended_cpu_cores: number
  bottleneck_type: string
  confidence: number
  ai_suggestions: string
  updated_at: string
}

export interface LoadTestReport {
  id: number
  cluster: number
  namespace: string
  service_name: string
  test_id: string
  start_time: string
  end_time: string
  max_qps_reached: number
  qps_per_core: number
  cpu_limit_cores: number
  recommended_cpu_cores: number
  confidence: number
  ai_suggestions: string
  report_markdown: string
  created_at: string
  derived?: any
}

export const perfApi = {
  listClusters: () => request.get<ClusterConfig[]>('/perf/clusters'),
  createCluster: (data: Partial<ClusterConfig>) => request.post<ClusterConfig>('/perf/clusters', data),
  updateCluster: (id: number, data: Partial<ClusterConfig>) => request.put<ClusterConfig>(`/perf/clusters/${id}`, data),
  deleteCluster: (id: number) => request.delete(`/perf/clusters/${id}`),

  listProfiles: (params?: any) => request.get<ServiceProfile[]>('/perf/profiles', { params }),
  listReports: (params?: any) => request.get<LoadTestReport[]>('/perf/reports', { params }),
  getReport: (id: number) => request.get<LoadTestReport>(`/perf/reports/${id}`),

  analyzeCapacity: (data: any) => request.post<{ job_id: number, status: string }>('/perf/analyze/capacity', data),
  getJob: (id: number) => request.get<any>(`/perf/jobs/${id}`),
  listServices: (clusterId: number, namespace: string) => request.get<{ items: string[] }>('/perf/services', { params: { cluster_id: clusterId, namespace } }),
  listPromqlTemplates: (clusterId: number, namespace: string, serviceName: string) =>
    request.get<{ items: any[] }>('/perf/promql/templates', { params: { cluster_id: clusterId, namespace, service_name: serviceName } }),

  getTrace: (clusterId: number, traceId: string) => request.get<any>(`/perf/traces/${traceId}`, { params: { cluster_id: clusterId } }),
  getTraceInsights: (clusterId: number, traceId: string) =>
    request.get<any>(`/perf/traces/${traceId}/insights`, { params: { cluster_id: clusterId } }),

  listHpa: (clusterId: number, namespace: string) => request.get<{ items: any[] }>('/perf/hpa', { params: { cluster_id: clusterId, namespace } }),
  applyHpa: (data: any) => request.post('/perf/hpa/apply', data),
}
