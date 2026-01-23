import request from '@/utils/request'
import type { Task, TaskLog } from '@/types/task'

export const taskApi = {
  // Get all tasks status
  getTasks: () => request.get<{tasks: Task[]}>('/tasks/status').then(res => res.tasks),
  
  // Create task using connection IDs
  createTask: (data: any) => request.post('/tasks/start_with_conn_ids', data),
  
  // Start existing task (resume)
  startTask: (id: string) => request.post(`/tasks/start_existing/${id}`),
  
  // Stop task
  stopTask: (id: string) => request.post(`/tasks/stop/${id}`),
  
  // Reset and start task
  resetTask: (id: string) => request.post(`/tasks/reset_and_start/${id}`),
  
  // Delete task
  deleteTask: (id: string) => request.post(`/tasks/delete/${id}`),
  
  // Get task logs
  getTaskLogs: (id: string, params?: any) => request.get<TaskLog>(`/tasks/logs/${id}`, { params }),
  
  // Download logs
  downloadLogs: (id: string) => `/api/tasks/logs/${id}/download`,

  // Global Log Monitoring
  getLogFiles: (params?: any) => request.get<{files: any[], total: number}>('/logs/files', { params }).then(res => res),
  getLogStats: () => request.get<any>('/logs/stats'),
  searchLogs: (q: string) => request.get<{matches: any[]}>('/logs/search', { params: { q } }).then(res => res.matches),
  downloadLog: (filename: string) => `/api/logs/download/${filename}`,

  // K8s Logs
  getK8sNamespaces: () => request.get<{namespaces: string[], error?: string}>('/k8s/namespaces'),
  getK8sPods: (namespace: string) => request.get<{pods: any[], error?: string}>('/k8s/pods', { params: { namespace } }),
  getK8sLogs: (params: any) => request.get<{logs: string}>('/k8s/logs', { params }).then(res => res.logs)
}
