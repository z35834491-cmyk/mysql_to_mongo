<template>
  <div class="traffic-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Traffic Dashboard</h2>
        <p class="page-subtitle">Monitor and analyze traffic trends, latency, error rate and geo distribution</p>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="range" size="small" class="range-group" @change="loadAll">
          <el-radio-button label="1h">1H</el-radio-button>
          <el-radio-button label="6h">6H</el-radio-button>
          <el-radio-button label="24h">24H</el-radio-button>
          <el-radio-button label="7d">7D</el-radio-button>
          <el-radio-button label="30d">30D</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="trafficSource"
          size="small"
          class="source-select"
          style="width: 168px"
          placeholder="日志源"
          :disabled="sourceOptions.length <= 1"
          @change="loadAll"
        >
          <el-option v-for="s in sourceOptions" :key="s.id" :label="s.label" :value="s.id" />
        </el-select>
        <el-select v-model="pollSec" size="small" class="poll-select" style="width: 110px">
          <el-option :value="0" label="手动刷新" />
          <el-option :value="5" label="5s" />
          <el-option :value="15" label="15s" />
          <el-option :value="30" label="30s" />
        </el-select>
        <div class="refresh-status">
          <span class="refresh-dot" :class="{ active: pollSec > 0 }" />
          <span>{{ refreshLabel }}</span>
        </div>
        <el-button :icon="Setting" size="small" class="toolbar-btn" @click="onOpenTrafficConfig">设置</el-button>
        <el-button :icon="Refresh" size="small" type="primary" class="toolbar-btn shadow-btn" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="mainTab" class="main-tabs">
      <el-tab-pane label="流量趋势" name="trend">
        <div v-if="!overview.log_configured" class="warn-banner page-panel">
          <el-icon><WarningFilled /></el-icon>
          <span>未配置 Nginx access 日志路径。请在设置中填写或通过环境变量 <code>TRAFFIC_NGINX_ACCESS_LOG</code> 指定。</span>
        </div>

        <div class="kpi-row">
          <div v-for="card in kpiCards" :key="card.key" class="page-panel kpi-card">
            <div class="kpi-head">
              <div>
                <div class="kpi-label">{{ card.label }}</div>
                <div class="kpi-value">{{ card.value }}</div>
                <div class="kpi-src">{{ card.source }}</div>
              </div>
              <div :ref="(el) => setKpiRef(card.key, el)" class="kpi-spark" />
            </div>
          </div>
        </div>

        <el-row :gutter="16" class="chart-row">
          <el-col :xs="24" :xl="16" :lg="15">
            <div class="page-panel chart-wrap">
              <div class="chart-title">QPS / 请求量</div>
              <div ref="chartQps" class="echart" />
            </div>
            <div class="page-panel chart-wrap">
              <div class="chart-title">P50 / P95 / P99 响应时间 (ms)</div>
              <div ref="chartLat" class="echart" />
            </div>
            <div class="page-panel chart-wrap">
              <div class="chart-title">状态码吞吐 (req/s)</div>
              <div ref="chartErr" class="echart" />
            </div>
          </el-col>
          <el-col :xs="24" :xl="8" :lg="9">
            <div class="page-panel chart-wrap globe-wrap">
              <div class="chart-title">全球流量分布</div>
              <div ref="chartGlobe" class="echart globe" />
            </div>
            <div class="page-panel chart-wrap">
              <div class="chart-title">国家 / 地区分布</div>
              <div ref="chartMap" class="echart map-h" />
            </div>
            <div class="page-panel chart-wrap">
              <div class="chart-title">Top 国家请求量</div>
              <div ref="chartCountry" class="echart country-h" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="16" class="bottom-row">
          <el-col :xs="24" :md="8">
            <div class="page-panel chart-wrap">
              <div class="chart-title">状态码分布</div>
              <div ref="chartPie" class="echart pie-h" />
            </div>
          </el-col>
          <el-col :xs="24" :md="16">
            <div class="page-panel chart-wrap table-wrap">
              <div class="chart-title">Top 请求路径</div>
              <el-table :data="pathsRows" size="small" class="dark-table" max-height="280">
                <el-table-column prop="path" label="Path" min-width="160" show-overflow-tooltip />
                <el-table-column prop="requests" label="Req" width="80" />
                <el-table-column prop="p95_ms" label="P95 ms" width="90" />
                <el-table-column prop="errors_5xx" label="5xx" width="60" />
                <el-table-column prop="share_pct" label="%" width="60" />
              </el-table>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="24">
            <div class="page-panel chart-wrap table-wrap">
              <div class="chart-title">慢接口 Top · Top IP</div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="12">
                  <el-table :data="slowRows" size="small" class="dark-table" max-height="220">
                    <el-table-column prop="path" label="Path" min-width="140" show-overflow-tooltip />
                    <el-table-column prop="p95_ms" label="P95" width="80" />
                    <el-table-column prop="p99_ms" label="P99" width="80" />
                  </el-table>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-table :data="ipRows" size="small" class="dark-table" max-height="220">
                    <el-table-column prop="ip" label="IP" width="140" />
                    <el-table-column prop="country" label="Region" width="100" />
                    <el-table-column prop="requests" label="Req" width="80" />
                  </el-table>
                </el-col>
              </el-row>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="请求流转（Jaeger 预留）" name="flow">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          class="jaeger-alert"
          title="当前为模拟数据，后续接入 Jaeger Query API 替换。"
        />
        <el-row :gutter="16" class="flow-row">
          <el-col :xs="24" :lg="16" :md="14">
            <div class="page-panel flow-placeholder">
              <div class="ph-title">服务依赖拓扑</div>
              <p class="ph-desc">将基于 Jaeger 依赖图 / service map 渲染。现展示占位骨架。</p>
              <div class="ph-grid">
                <div class="ph-node">gateway</div>
                <div class="ph-edge" />
                <div class="ph-node dim">api</div>
                <div class="ph-edge" />
                <div class="ph-node dim">worker</div>
              </div>
            </div>
          </el-col>
          <el-col :xs="24" :lg="8" :md="10">
            <div class="page-panel chart-wrap table-wrap">
              <div class="chart-title">最近 Trace（模拟）</div>
              <el-table :data="traceRows" size="small" class="dark-table" max-height="360">
                <el-table-column prop="trace_id" label="Trace ID" min-width="120" show-overflow-tooltip />
                <el-table-column prop="root_service" label="Service" width="110" />
                <el-table-column prop="duration_ms" label="ms" width="70" />
                <el-table-column prop="status" label="Status" width="72" />
              </el-table>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="configOpen" title="Traffic 数据源配置" width="640px" class="traffic-dialog">
      <el-form :model="cfgForm" label-width="150px">
        <el-form-item label="启用采集">
          <el-switch v-model="cfgForm.enabled" />
        </el-form-item>
        <el-form-item label="采集模式">
          <el-select v-model="cfgForm.access_log_mode" style="width: 100%">
            <el-option label="本地文件（Pod/共享卷）" value="file" />
            <el-option label="远程推送 → Redis（独立 Nginx）" value="redis" />
          </el-select>
          <div v-if="cfgForm.access_log_mode === 'redis'" class="form-hint">
            K8s 内设置环境变量 <code>TRAFFIC_REDIS_URL</code>；Nginx 侧用 cron/filebeat 等向
            <code>POST /api/traffic/ingest</code> 推送 NDJSON（Bearer <code>TRAFFIC_INGEST_TOKEN</code>）。Redis 已连通：
            <el-tag :type="cfgForm.redis_env_configured ? 'success' : 'danger'" size="small" class="ml-6">
              {{ cfgForm.redis_env_configured ? '已配置' : '未配置 URL' }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item v-if="cfgForm.access_log_mode === 'file'" label="Access log 路径">
          <el-input v-model="cfgForm.access_log_path" placeholder="/var/log/nginx/access.json.log" />
        </el-form-item>
        <template v-if="cfgForm.access_log_mode === 'redis'">
          <el-form-item label="Redis List Key">
            <el-input v-model="cfgForm.redis_log_key" placeholder="traffic:access:lines" />
          </el-form-item>
          <el-form-item label="Redis 最大行数">
            <el-input-number v-model="cfgForm.redis_max_lines" :min="5000" :max="2000000" style="width: 100%" />
          </el-form-item>
        </template>
        <el-form-item label="日志格式">
          <el-select v-model="cfgForm.log_format">
            <el-option label="JSON 行" value="json" />
            <el-option label="Combined" value="combined" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="cfgForm.access_log_mode === 'file'" label="尾部读取字节">
          <el-input-number v-model="cfgForm.max_tail_bytes" :min="65536" :max="52428800" />
        </el-form-item>
        <el-form-item label="多站点 / 域名">
          <div class="form-hint">
            留空表示只用上方「单路径」或「单 Redis Key」。按域名拆日志时添加多行：唯一
            <code>id</code>、显示名、以及文件模式填 <code>file_path</code>，Redis 模式填 <code>redis_key</code>。
            远程推送使用 <code>POST /api/traffic/ingest?source=&lt;id&gt;</code> 或请求头
            <code>X-Traffic-Source: &lt;id&gt;</code>。
          </div>
          <el-table :data="cfgForm.log_sources" border size="small" class="log-src-table">
            <el-table-column label="ID" width="120">
              <template #default="{ row }">
                <el-input v-model="row.id" size="small" placeholder="api" />
              </template>
            </el-table-column>
            <el-table-column label="显示名" min-width="120">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" placeholder="API" />
              </template>
            </el-table-column>
            <el-table-column v-if="cfgForm.access_log_mode === 'file'" label="文件路径" min-width="220">
              <template #default="{ row }">
                <el-input
                  v-model="row.file_path"
                  size="small"
                  placeholder="/var/log/nginx/access_api.json.log"
                />
              </template>
            </el-table-column>
            <el-table-column v-if="cfgForm.access_log_mode === 'redis'" label="Redis List Key" min-width="220">
              <template #default="{ row }">
                <el-input v-model="row.redis_key" size="small" placeholder="traffic:access:lines:api" />
              </template>
            </el-table-column>
            <el-table-column label="" width="72" fixed="right">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="removeLogSource($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button class="mt-8" size="small" @click="addLogSource">添加一行</el-button>
        </el-form-item>
        <el-form-item label="MaxMind mmdb">
          <el-input
            v-model="cfgForm.geoip_db_path"
            placeholder="/usr/share/GeoIP/GeoLite2-City.mmdb 或 GeoIP2-City.mmdb"
          />
          <div class="form-hint">MaxMind GeoIP2 / GeoLite2 城市库；可与环境变量 TRAFFIC_GEOIP_DB 二选一（后台优先）。</div>
        </el-form-item>
        <el-form-item label="使用巡检 Prometheus">
          <el-switch v-model="cfgForm.use_inspection_prometheus" />
        </el-form-item>
        <el-form-item label="Prometheus 覆盖">
          <el-input v-model="cfgForm.prometheus_url_override" placeholder="留空则走巡检配置" />
        </el-form-item>
        <el-form-item label="Blackbox PromQL">
          <el-input v-model="cfgForm.blackbox_promql" placeholder="默认 probe_success" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configOpen = false">取消</el-button>
        <el-button type="primary" @click="saveCfg">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { Refresh, Setting, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { trafficApi, type TrafficLogSourceRow } from '@/api/traffic'

echarts.registerTheme('shark-traffic', {
  backgroundColor: 'transparent',
  color: ['#3b82f6', '#60a5fa', '#93c5fd', '#38bdf8', '#2563eb', '#0284c7'],
  textStyle: {
    color: '#475569',
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#cbd5e1' } },
    axisTick: { show: false },
    axisLabel: { color: '#64748b' },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#64748b' },
    splitLine: { lineStyle: { color: 'rgba(203,213,225,0.55)' } },
  },
  timeAxis: {
    axisLine: { lineStyle: { color: '#cbd5e1' } },
    axisTick: { show: false },
    axisLabel: { color: '#64748b' },
  },
})

const range = ref('24h')
const pollSec = ref(5)
const loading = ref(false)
const mainTab = ref('trend')
const configOpen = ref(false)
const trafficSource = ref('all')
const sourceOptions = ref<{ id: string; label: string }[]>([])

const overview = ref<any>({ series: { qps: [], error_rate: [] }, log_configured: true })
const timeseries = ref<any>({})
const geoItems = ref<any[]>([])
const pathsRows = ref<any[]>([])
const slowRows = ref<any[]>([])
const ipRows = ref<any[]>([])
const statusPie = ref<any[]>([])
const traceRows = ref<any[]>([])

const cfgForm = reactive({
  enabled: true,
  access_log_mode: 'file' as 'file' | 'redis',
  access_log_path: '',
  error_log_path: '',
  log_format: 'json',
  max_tail_bytes: 5242880,
  redis_log_key: 'traffic:access:lines',
  redis_max_lines: 200000,
  redis_env_configured: false,
  log_sources: [] as TrafficLogSourceRow[],
  geoip_db_path: '',
  use_inspection_prometheus: true,
  prometheus_url_override: '',
  blackbox_promql: '',
})

const kpiRefs: Record<string, HTMLElement | null> = {}
function setKpiRef(key: string, el: unknown) {
  kpiRefs[key] = (el as HTMLElement) || null
}

const chartQps = ref<HTMLElement | null>(null)
const chartLat = ref<HTMLElement | null>(null)
const chartErr = ref<HTMLElement | null>(null)
const chartGlobe = ref<HTMLElement | null>(null)
const chartMap = ref<HTMLElement | null>(null)
const chartCountry = ref<HTMLElement | null>(null)
const chartPie = ref<HTMLElement | null>(null)

const kpiCharts: Record<string, echarts.ECharts | null> = {}
const charts: Record<string, echarts.ECharts | null> = {}
let pollId: ReturnType<typeof setInterval> | null = null
let glTried = false

const refreshLabel = computed(() => (pollSec.value > 0 ? `${pollSec.value}s 自动刷新` : '手动刷新'))

const kpiCards = ref([
  { key: 'total', label: '窗口内请求', value: '—', source: '' },
  {
    key: 'qps',
    label: 'QPS (请求时间·近60s)',
    value: '—',
    source: '按日志内请求时刻，非推送时刻',
  },
  { key: 'lat', label: '平均响应', value: '—', source: '' },
  { key: 'err', label: '错误率', value: '—', source: '' },
  { key: 'up', label: '可用性', value: '—', source: '' },
])

function disposeChart(c?: echarts.ECharts | null) {
  if (c) {
    c.dispose()
  }
}

function disposeAllMain() {
  Object.keys(charts).forEach((k) => {
    disposeChart(charts[k])
    charts[k] = null
  })
  Object.keys(kpiCharts).forEach((k) => {
    disposeChart(kpiCharts[k])
    kpiCharts[k] = null
  })
}

function sparkOption(series: number[][], color: string) {
  const xs = series.map((_, i) => i)
  const ys = series.map((x) => x[1])
  const areaColorMap: Record<string, string> = {
    'rgb(0,191,255)': 'rgba(0,191,255,0.12)',
    'rgb(61,165,255)': 'rgba(61,165,255,0.12)',
    'rgb(94,200,255)': 'rgba(94,200,255,0.12)',
    'rgb(47,127,209)': 'rgba(47,127,209,0.12)',
    'rgb(76,201,240)': 'rgba(76,201,240,0.12)',
  }
  return {
    backgroundColor: 'transparent',
    animationDuration: 280,
    grid: { left: 2, right: 2, top: 2, bottom: 2 },
    xAxis: { type: 'category', show: false, data: xs },
    yAxis: { type: 'value', show: false, min: 'dataMin' },
    series: [
      {
        type: 'line',
        data: ys,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: areaColorMap[color] || 'rgba(0,191,255,0.12)' },
            { offset: 1, color: 'rgba(0,191,255,0)' },
          ]),
        },
      },
    ],
  }
}

const axisTooltip = {
  trigger: 'axis',
  backgroundColor: 'rgba(15, 23, 42, 0.94)',
  borderColor: '#cbd5e1',
  borderWidth: 1,
  textStyle: { color: '#f8fafc', fontSize: 12 },
  extraCssText: 'box-shadow:none;border-radius:10px;padding:10px 12px;',
}

const itemTooltip = {
  trigger: 'item',
  backgroundColor: 'rgba(15, 23, 42, 0.94)',
  borderColor: '#cbd5e1',
  borderWidth: 1,
  textStyle: { color: '#f8fafc', fontSize: 12 },
  extraCssText: 'box-shadow:none;border-radius:10px;padding:10px 12px;',
}

/** 地图 / 地球贴图走同源 public，避免内网无法访问 jsDelivr、echarts.apache.org */
function trafficMapAsset(relPath: string): string {
  const base = import.meta.env.BASE_URL || '/'
  const p = relPath.replace(/^\//, '')
  return base.endsWith('/') ? `${base}${p}` : `${base}/${p}`
}

async function loadWorldGeoJson(): Promise<unknown> {
  const localUrl = trafficMapAsset('traffic-maps/world.json')
  const tryFetch = async (url: string) => {
    const res = await fetch(url, { credentials: 'same-origin' })
    if (!res.ok) throw new Error(String(res.status))
    return res.json()
  }
  try {
    return await tryFetch(localUrl)
  } catch {
    /* 构建遗漏或旧部署：再试公网镜像（部分环境仍不可达） */
    const mirror =
      'https://raw.githubusercontent.com/apache/echarts/master/test/data/map/json/world.json'
    return tryFetch(mirror)
  }
}

function lineSeries(name: string, data: number[][], color: string, extra: Record<string, any> = {}) {
  return {
    name,
    type: 'line',
    smooth: true,
    showSymbol: false,
    symbol: 'none',
    data,
    lineStyle: { color, width: 2 },
    emphasis: { focus: 'series' },
    animationDuration: 320,
    ...extra,
  }
}

function updateKpiCharts() {
  const q = overview.value?.series?.qps || []
  const e = overview.value?.series?.error_rate || []
  const rq = timeseries.value?.requests || []
  const keys = ['total', 'qps', 'lat', 'err', 'up']
  const dataMap: Record<string, number[][]> = {
    total: rq.length ? rq : q,
    qps: q,
    lat: q,
    err: e.length ? e : q,
    up: q,
  }
  const colors = ['rgb(59,130,246)', 'rgb(96,165,250)', 'rgb(147,197,253)', 'rgb(56,189,248)', 'rgb(37,99,235)']
  keys.forEach((key, i) => {
    const el = kpiRefs[key]
    if (!el) return
    let c = kpiCharts[key]
    if (!c) {
      c = echarts.init(el, 'shark-traffic')
      kpiCharts[key] = c
    }
    c.setOption(sparkOption(dataMap[key] || [], colors[i % colors.length]), true)
  })
}

async function renderMainCharts() {
  disposeAllMain()
  const ts = timeseries.value
  if (chartQps.value) {
    const c = echarts.init(chartQps.value, 'shark-traffic')
    charts.qps = c
    c.setOption({
      animationDuration: 320,
      tooltip: axisTooltip,
      legend: { top: 8, left: 'center', textStyle: { color: '#64748b' }, data: ['QPS', 'Requests/min'] },
      grid: { left: 48, right: 20, top: 48, bottom: 28 },
      xAxis: { type: 'time' },
      yAxis: [{ type: 'value', name: 'QPS' }, { type: 'value', name: 'Req', splitLine: { show: false } }],
      series: [
        lineSeries('QPS', ts.qps || [], '#3b82f6', {
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(59,130,246,0.12)' },
              { offset: 1, color: 'rgba(59,130,246,0.02)' },
            ]),
          },
        }),
        {
          name: 'Requests/min',
          type: 'bar',
          yAxisIndex: 1,
          barWidth: 10,
          data: (ts.requests || []).map((x: number[]) => [x[0], x[1] / Math.max((ts.bucket_sec || 60) / 60, 1)]),
          itemStyle: { color: 'rgba(96,165,250,0.45)', borderRadius: [3, 3, 0, 0] },
          animationDuration: 320,
        },
      ],
    })
  }

  if (chartLat.value) {
    const c = echarts.init(chartLat.value, 'shark-traffic')
    charts.lat = c
    const lat = ts.latency || {}
    c.setOption({
      animationDuration: 320,
      tooltip: {
        ...axisTooltip,
        valueFormatter: (v: number) => `${v} ms`,
      },
      legend: { top: 8, left: 'center', textStyle: { color: '#64748b' } },
      grid: { left: 48, right: 20, top: 48, bottom: 28 },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', name: 'ms' },
      series: [
        lineSeries('P50', lat.p50 || [], '#93c5fd'),
        lineSeries('P95', lat.p95 || [], '#60a5fa'),
        lineSeries('P99', lat.p99 || [], '#3b82f6'),
      ],
    })
  }

  if (chartErr.value) {
    const c = echarts.init(chartErr.value, 'shark-traffic')
    charts.err = c
    const st = ts.status_stack || {}
    c.setOption({
      animationDuration: 320,
      tooltip: axisTooltip,
      legend: { top: 8, left: 'center', textStyle: { color: '#64748b' } },
      grid: { left: 48, right: 20, top: 48, bottom: 28 },
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      series: [
        { name: '2xx', type: 'line', stack: 's', smooth: true, showSymbol: false, areaStyle: { color: 'rgba(147,197,253,0.18)' }, lineStyle: { width: 0, color: '#93c5fd' }, data: st['2xx'] || [] },
        { name: '4xx', type: 'line', stack: 's', smooth: true, showSymbol: false, areaStyle: { color: 'rgba(96,165,250,0.18)' }, lineStyle: { width: 0, color: '#60a5fa' }, data: st['4xx'] || [] },
        { name: '5xx', type: 'line', stack: 's', smooth: true, showSymbol: false, areaStyle: { color: 'rgba(59,130,246,0.22)' }, lineStyle: { width: 0, color: '#3b82f6' }, data: st['5xx'] || [] },
      ],
    })
  }

  if (chartCountry.value) {
    const c = echarts.init(chartCountry.value, 'shark-traffic')
    charts.country = c
    const items = [...geoItems.value].sort((a, b) => b.requests - a.requests).slice(0, 10)
    c.setOption({
      animationDuration: 320,
      tooltip: itemTooltip,
      grid: { left: 92, right: 16, top: 12, bottom: 12 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: items.map((i) => i.name || i.code).reverse(), axisLabel: { color: '#475569' } },
      series: [
        {
          type: 'bar',
          data: items.map((i) => i.requests).reverse(),
          barWidth: 12,
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: 'rgba(96,165,250,0.24)' },
              { offset: 1, color: '#3b82f6' },
            ]),
          },
        },
      ],
    })
  }

  if (chartPie.value) {
    const c = echarts.init(chartPie.value, 'shark-traffic')
    charts.pie = c
    c.setOption({
      animationDuration: 320,
      tooltip: itemTooltip,
      legend: { bottom: 8, left: 'center', textStyle: { color: '#64748b', fontSize: 12 } },
      series: [
        {
          type: 'pie',
          radius: ['52%', '74%'],
          center: ['50%', '44%'],
          itemStyle: { borderRadius: 4, borderColor: '#ffffff', borderWidth: 2 },
          label: { color: '#475569', fontSize: 12 },
          labelLine: { lineStyle: { color: '#94a3b8' } },
          data: statusPie.value.length ? statusPie.value : [{ name: '无数据', value: 1 }],
        },
      ],
    })
  }

  await initGlobeAndMap()
}

async function initGlobeAndMap() {
  if (chartGlobe.value && !charts.globe) {
    try {
      if (!glTried) {
        await import('echarts-gl')
        glTried = true
      }
      const c = echarts.init(chartGlobe.value, 'shark-traffic')
      charts.globe = c
      const scatter = geoItems.value
        .filter((g) => g.lat && g.lng && g.requests > 0)
        .map((g) => [g.lng, g.lat, g.requests])
      c.setOption({
        animationDuration: 320,
        globe: {
          baseTexture: trafficMapAsset('traffic-maps/globe-texture.jpg'),
          shading: 'lambert',
          environment: '#f8fafc',
          light: { ambient: { intensity: 0.95 }, main: { intensity: 0.2 } },
          viewControl: { autoRotate: false, distance: 160, alpha: 24, beta: 160 },
          itemStyle: { color: '#dbeafe', borderColor: '#cbd5e1', borderWidth: 0.5 },
        },
        series: [
          {
            type: 'scatter3D',
            coordinateSystem: 'globe',
            symbolSize: (val: number[]) => Math.min(18, 5 + Math.log1p(val[2]) * 2),
            itemStyle: { color: '#3b82f6', opacity: 0.82 },
            data: scatter,
          },
        ],
      })
    } catch {
      if (chartGlobe.value) {
        const c = echarts.init(chartGlobe.value, 'shark-traffic')
        charts.globe = c
        c.setOption({
          title: { text: 'echarts-gl 未加载', left: 'center', top: 'center', textStyle: { color: '#64748b', fontSize: 12 } },
        })
      }
    }
  }

  if (chartMap.value && !charts.map) {
    const c = echarts.init(chartMap.value, 'shark-traffic')
    charts.map = c
    try {
      const worldJson = await loadWorldGeoJson()
      try {
        echarts.registerMap('world', worldJson as any)
      } catch {
        /* already registered */
      }
      const data = geoItems.value.map((g) => [g.lng, g.lat, g.requests, g.name || g.code])
      const reqVals = geoItems.value.map((g) => Number(g.requests) || 0)
      const vmax = reqVals.length ? Math.max(1, ...reqVals) : 1
      c.setOption({
        animationDuration: 320,
        tooltip: {
          ...itemTooltip,
          formatter: (p: any) => {
            const v = p.value as number[]
            const n = v?.[2]
            const name = v?.[3] || p.name || ''
            return `${name}<br/>请求: ${n ?? '-'}`
          },
        },
        geo: {
          map: 'world',
          roam: true,
          itemStyle: { areaColor: '#e2e8f0', borderColor: '#cbd5e1', borderWidth: 0.8 },
          emphasis: { itemStyle: { areaColor: '#bfdbfe' }, label: { color: '#1e293b' } },
        },
        visualMap: {
          min: 0,
          max: vmax,
          calculable: false,
          inRange: { color: ['#dbeafe', '#bfdbfe', '#93c5fd', '#60a5fa', '#3b82f6'] },
          textStyle: { color: '#64748b' },
          left: 8,
          bottom: 20,
        },
        series: [
          {
            type: 'scatter',
            coordinateSystem: 'geo',
            data,
            symbolSize: (val: number[]) => Math.min(18, 5 + Math.sqrt((val[2] as number) || 0)),
            itemStyle: { color: '#3b82f6', opacity: 0.85 },
          },
        ],
      })
    } catch {
      c.setOption({
        title: {
          text: '地图数据加载失败（请确认已部署 frontend/public/traffic-maps/world.json）',
          left: 'center',
          top: 'center',
          textStyle: { color: '#64748b', fontSize: 11 },
        },
      })
    }
  }
}

function updateKpiText() {
  const o = overview.value || {}
  kpiCards.value = [
    { key: 'total', label: '窗口内请求', value: fmtNum(o.total_requests), source: '' },
    {
      key: 'qps',
      label: 'QPS (请求时间·近60s)',
      value: fmtNum(o.qps),
      source: '按日志内请求时刻，非推送时刻',
    },
    { key: 'lat', label: '平均响应', value: `${o.latency_avg_ms ?? 0} ms`, source: '' },
    { key: 'err', label: '错误率', value: `${o.error_rate_pct ?? 0}%`, source: '' },
    {
      key: 'up',
      label: '可用性',
      value: o.availability_pct != null ? `${o.availability_pct}%` : '—',
      source: '',
    },
  ]
}

function fmtNum(n: unknown) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function currentSourceParam(): string | undefined {
  const s = trafficSource.value
  if (!s || s === 'all') return 'all'
  return s
}

async function refreshSourceOptions() {
  try {
    const data = await trafficApi.sources()
    const items = data.items || []
    sourceOptions.value = items
    const ids = new Set(items.map((i) => i.id))
    if (!trafficSource.value || !ids.has(trafficSource.value)) {
      trafficSource.value = items[0]?.id || 'all'
    }
  } catch {
    sourceOptions.value = []
  }
}

function addLogSource() {
  cfgForm.log_sources.push({ id: '', label: '', file_path: '', redis_key: '' })
}

function removeLogSource(index: number) {
  cfgForm.log_sources.splice(index, 1)
}

async function loadAll() {
  loading.value = true
  try {
    const r = range.value
    const src = currentSourceParam()
    const [ov, ts, geo, paths, slow, status, ip, tr] = await Promise.all([
      trafficApi.overview(r, src) as Promise<any>,
      trafficApi.timeseries(r, src) as Promise<any>,
      trafficApi.geo(r, 'country', '', src) as Promise<any>,
      trafficApi.top(r, 'paths', 10, src) as Promise<any>,
      trafficApi.top(r, 'slow', 10, src) as Promise<any>,
      trafficApi.top(r, 'status', 20, src) as Promise<any>,
      trafficApi.top(r, 'ip', 10, src) as Promise<any>,
      trafficApi.jaegerTraces() as Promise<any>,
    ])
    overview.value = ov
    timeseries.value = ts
    geoItems.value = geo.items || []
    pathsRows.value = paths.items || []
    slowRows.value = slow.items || []
    ipRows.value = ip.items || []
    statusPie.value = status.items || []
    traceRows.value = tr.traces || []
    updateKpiText()
    await nextTick()
    disposeAllMain()
    updateKpiCharts()
    await renderMainCharts()
  } catch {
    /* request interceptor */
  } finally {
    loading.value = false
  }
}

async function onOpenTrafficConfig() {
  try {
    const c = (await trafficApi.getConfig()) as any
    const ls = Array.isArray(c.log_sources) ? c.log_sources : []
    cfgForm.log_sources.splice(
      0,
      cfgForm.log_sources.length,
      ...ls.map((row: Record<string, string>) => ({
        id: String(row.id || ''),
        label: String(row.label || ''),
        file_path: String(row.file_path || ''),
        redis_key: String(row.redis_key || ''),
      }))
    )
    Object.assign(cfgForm, { ...c, log_sources: cfgForm.log_sources })
    configOpen.value = true
  } catch {
    ElMessage.error('读取配置失败')
  }
}

async function saveCfg() {
  try {
    const rows = cfgForm.log_sources.filter((x) => String(x.id || '').trim())
    const ids = rows.map((x) => String(x.id).trim())
    if (new Set(ids).size !== ids.length) {
      ElMessage.error('日志源 ID 不能重复')
      return
    }
    await trafficApi.saveConfig({ ...cfgForm, log_sources: rows })
    ElMessage.success('已保存')
    configOpen.value = false
    await refreshSourceOptions()
    loadAll()
  } catch {
    /* */
  }
}

function setupPoll() {
  if (pollId) clearInterval(pollId)
  if (pollSec.value > 0) {
    pollId = setInterval(() => {
      if (mainTab.value === 'trend') loadAll()
    }, pollSec.value * 1000)
  }
}

watch(pollSec, setupPoll)

onMounted(async () => {
  await refreshSourceOptions()
  loadAll()
  setupPoll()
  window.addEventListener('resize', onResize)
})

function onResize() {
  Object.values(charts).forEach((c) => c?.resize())
  Object.values(kpiCharts).forEach((c) => c?.resize())
}

onUnmounted(() => {
  if (pollId) clearInterval(pollId)
  disposeAllMain()
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.traffic-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header,
.main-tabs,
.kpi-row,
.chart-row,
.bottom-row,
.flow-row {
  position: relative;
  z-index: 1;
}

.page-panel {
  background: #ffffff;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  box-shadow: none;
}
.page-panel:hover {
  border-color: #e2e8f0;
}

.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 14px;
  color: #64748b;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.refresh-status {
  height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
}
.refresh-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #94a3b8;
}
.refresh-dot.active {
  background: #3b82f6;
  animation: dashboardPulse 1.6s ease-in-out infinite;
}
.toolbar-btn {
  border-radius: 8px;
}
.shadow-btn {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}
.source-select :deep(.el-input__wrapper) {
  background: #ffffff;
  box-shadow: none;
  border: 1px solid #dbe2ea;
  color: #334155;
}
.log-src-table {
  width: 100%;
  margin-top: 8px;
}
.mt-8 {
  margin-top: 8px;
}
.poll-select :deep(.el-input__wrapper) {
  background: #ffffff;
  box-shadow: none;
  border: 1px solid #dbe2ea;
  color: #334155;
}
.range-group :deep(.el-radio-button__inner) {
  background: #ffffff;
  border-color: #dbe2ea;
  color: #64748b;
  box-shadow: none;
}
.range-group :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
}

.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
.main-tabs :deep(.el-tabs__nav-wrap::after) {
  background: #e2e8f0;
}
.main-tabs :deep(.el-tabs__item) {
  color: #64748b;
  font-weight: 600;
}
.main-tabs :deep(.el-tabs__item.is-active) {
  color: #3b82f6;
}
.main-tabs :deep(.el-tabs__active-bar) {
  background: #3b82f6;
  height: 2px;
}

.warn-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #b45309;
  border-color: #fcd34d;
  background: #fffbeb;
}
.warn-banner code {
  font-size: 11px;
  color: #92400e;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 1439px) {
  .kpi-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 1023px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 767px) {
  .kpi-row {
    grid-template-columns: 1fr;
  }
}
.kpi-card {
  padding: 14px 16px;
  min-height: 132px;
}
.kpi-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.kpi-label {
  font-size: 12px;
  line-height: 16px;
  color: #64748b;
}
.kpi-value {
  margin: 10px 0 8px;
  color: #3b82f6;
  font-size: 30px;
  line-height: 1;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.kpi-src {
  font-size: 12px;
  line-height: 16px;
  color: #94a3b8;
}
.kpi-spark {
  width: 88px;
  height: 40px;
  flex-shrink: 0;
}

.chart-wrap {
  padding: 12px 14px 10px;
  margin-bottom: 16px;
}
.chart-title {
  margin-bottom: 10px;
  color: #475569;
  font-size: 14px;
  font-weight: 600;
}
.echart {
  width: 100%;
  height: 260px;
}
.globe-wrap .globe {
  height: 280px;
}
.map-h {
  height: 260px;
}
.country-h {
  height: 240px;
}
.pie-h {
  height: 280px;
}

.jaeger-alert {
  margin-bottom: 16px;
}
.jaeger-alert :deep(.el-alert__content) {
  color: #475569;
}
.jaeger-alert :deep(.el-alert) {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}
.flow-placeholder {
  padding: 24px;
  min-height: 360px;
}
.ph-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}
.ph-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 24px;
}
.ph-grid {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ph-node {
  padding: 16px 24px;
  border-radius: 10px;
  border: 1px solid #dbe2ea;
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
}
.ph-node.dim {
  opacity: 0.72;
}
.ph-edge {
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #60a5fa, transparent);
}

.dark-table {
  --el-table-bg-color: #ffffff;
  --el-table-tr-bg-color: #ffffff;
  --el-table-row-hover-bg-color: #f8fafc;
  --el-table-header-bg-color: #f8fafc;
  --el-table-text-color: #334155;
  --el-table-header-text-color: #64748b;
  --el-table-border-color: #f1f5f9;
}
.dark-table :deep(.el-table__inner-wrapper::before) {
  background-color: #f1f5f9;
}
.dark-table :deep(th.el-table__cell),
.dark-table :deep(td.el-table__cell) {
  background: transparent;
}
@keyframes dashboardPulse {
  0%, 100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}
</style>

<style>
.traffic-dialog .el-dialog {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: none;
}
.traffic-dialog .el-dialog__title {
  color: #1e293b;
}
.traffic-dialog .el-form-item__label,
.traffic-dialog .el-input__inner,
.traffic-dialog .el-select__placeholder,
.traffic-dialog .el-dialog__body {
  color: #475569;
}
.traffic-dialog .el-input__wrapper,
.traffic-dialog .el-select__wrapper,
.traffic-dialog .el-textarea__inner {
  background: #ffffff;
  box-shadow: none;
}
.traffic-dialog .el-textarea__inner,
.traffic-dialog .el-input__wrapper,
.traffic-dialog .el-select__wrapper {
  border: 1px solid #dbe2ea;
}
.traffic-dialog .form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.traffic-dialog .form-hint code {
  font-size: 11px;
  padding: 1px 4px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 4px;
}
.traffic-dialog .ml-6 {
  margin-left: 6px;
  vertical-align: middle;
}
</style>
