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
  getLogFiles: () => request.get<{files: any[]}>('/logs/files').then(res => res.files),
  getLogStats: () => request.get<any>('/logs/stats'),
  searchLogs: (q: string) => request.get<{matches: any[]}>('/logs/search', { params: { q } }).then(res => res.matches)
}
