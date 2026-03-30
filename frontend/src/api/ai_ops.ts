import request from '@/utils/request'

export const aiOpsApi = {
  getIncidents: () => request.get('/ai_ops/incidents'),
  getIncidentDetail: (id: number) => request.get(`/ai_ops/incidents/${id}`),
  submitIncidentEvidence: (id: number, evidence: Record<string, string>) =>
    request.post(`/ai_ops/incidents/${id}/submit_evidence`, { evidence }),
  getConfig: () => request.get('/ai_ops/config'),
  updateConfig: (data: any) => request.post('/ai_ops/config', data),
}
