import request from '@/utils/request'
import type { Connection } from '@/types/connection'

export const connectionApi = {
  getConnections: () => request.get<{connections: Connection[]}>('/connections').then(res => res.connections),
  saveConnection: (data: Connection) => request.post('/connections', data),
  deleteConnection: (id: string) => request.delete(`/connections/${id}`),
  testConnection: (data: Connection) => request.post<{ok: boolean, latency_ms: number}>('/connections/test', data),
  getDatabases: (connId: string) => request.post<{databases: string[]}>(`/mysql/databases_by_id/${connId}`),
  getTables: (connId: string, database: string) => request.post<{tables: string[]}>(`/mysql/tables_by_id/${connId}`, { database })
}
