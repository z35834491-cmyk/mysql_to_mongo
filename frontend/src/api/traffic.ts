import request from '@/utils/request'

export const trafficApi = {
  overview: (range: string) =>
    request.get('/traffic/overview', { params: { range } }),
  timeseries: (range: string) =>
    request.get('/traffic/timeseries', { params: { range } }),
  geo: (range: string, granularity = 'country', country = '') =>
    request.get('/traffic/geo', { params: { range, granularity, country } }),
  top: (range: string, type: string, limit = 10) =>
    request.get('/traffic/top', { params: { range, type, limit } }),
  blackbox: () => request.get('/traffic/blackbox'),
  jaegerTraces: () => request.get('/traffic/jaeger/traces'),
  getConfig: () => request.get('/traffic/config'),
  saveConfig: (data: Record<string, unknown>) => request.post('/traffic/config', data),
}
