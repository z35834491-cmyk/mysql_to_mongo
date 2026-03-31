import request from '@/utils/request'

export type TrafficLogSourceRow = {
  id: string
  label: string
  file_path: string
  redis_key: string
}

export const trafficApi = {
  sources: () => request.get('/traffic/sources') as Promise<{ items: { id: string; label: string }[] }>,
  overview: (range: string, source?: string) =>
    request.get('/traffic/overview', { params: { range, ...(source ? { source } : {}) } }),
  timeseries: (range: string, source?: string) =>
    request.get('/traffic/timeseries', { params: { range, ...(source ? { source } : {}) } }),
  geo: (range: string, granularity = 'country', country = '', source?: string) =>
    request.get('/traffic/geo', {
      params: { range, granularity, country, ...(source ? { source } : {}) },
    }),
  top: (range: string, type: string, limit = 10, source?: string) =>
    request.get('/traffic/top', {
      params: { range, type, limit, ...(source ? { source } : {}) },
    }),
  blackbox: () => request.get('/traffic/blackbox'),
  jaegerTraces: () => request.get('/traffic/jaeger/traces'),
  getConfig: () => request.get('/traffic/config'),
  saveConfig: (data: Record<string, unknown>) => request.post('/traffic/config', data),
}
