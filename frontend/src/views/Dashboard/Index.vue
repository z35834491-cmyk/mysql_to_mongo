<template>
  <div class="traffic-page">
    <canvas ref="particleCanvas" class="particles" aria-hidden="true" />

    <header class="traffic-header glass-bar">
      <div class="header-left">
        <h1>Traffic Dashboard</h1>
        <p class="tagline">Nginx access · Blackbox · GeoIP</p>
      </div>
      <div class="header-right">
        <el-radio-group v-model="range" size="small" class="range-group" @change="loadAll">
          <el-radio-button label="1h">1H</el-radio-button>
          <el-radio-button label="6h">6H</el-radio-button>
          <el-radio-button label="24h">24H</el-radio-button>
          <el-radio-button label="7d">7D</el-radio-button>
          <el-radio-button label="30d">30D</el-radio-button>
        </el-radio-group>
        <el-select v-model="pollSec" size="small" class="poll-select" style="width: 110px">
          <el-option :value="0" label="手动刷新" />
          <el-option :value="5" label="5s" />
          <el-option :value="15" label="15s" />
          <el-option :value="30" label="30s" />
        </el-select>
        <el-button :icon="Setting" circle size="small" @click="onOpenTrafficConfig" />
        <el-button :icon="Refresh" circle size="small" :loading="loading" @click="loadAll" />
      </div>
    </header>

    <el-tabs v-model="mainTab" class="main-tabs">
      <el-tab-pane label="流量趋势" name="trend">
        <div v-if="!overview.log_configured" class="warn-banner glass">
          <el-icon><WarningFilled /></el-icon>
          <span>未配置 Nginx access 日志路径。请在设置中填写或通过环境变量 <code>TRAFFIC_NGINX_ACCESS_LOG</code> 指定。</span>
        </div>

        <div class="kpi-row">
          <div v-for="card in kpiCards" :key="card.key" class="glass kpi-card">
            <div class="kpi-label">{{ card.label }}</div>
            <div class="kpi-value">{{ card.value }}</div>
            <div class="kpi-src">{{ card.source }}</div>
            <div :ref="(el) => setKpiRef(card.key, el)" class="kpi-spark" />
          </div>
        </div>

        <el-row :gutter="16" class="chart-row">
          <el-col :xs="24" :lg="15">
            <div class="glass chart-wrap">
              <div class="chart-title">QPS / 请求量</div>
              <div ref="chartQps" class="echart" />
            </div>
            <div class="glass chart-wrap">
              <div class="chart-title">P50 / P95 / P99 响应时间 (ms)</div>
              <div ref="chartLat" class="echart" />
            </div>
            <div class="glass chart-wrap">
              <div class="chart-title">状态码吞吐 (req/s)</div>
              <div ref="chartErr" class="echart" />
            </div>
          </el-col>
          <el-col :xs="24" :lg="9">
            <div class="glass chart-wrap globe-wrap">
              <div class="chart-title">全球流量 (3D · echarts-gl)</div>
              <div ref="chartGlobe" class="echart globe" />
            </div>
            <div class="glass chart-wrap">
              <div class="chart-title">国家 / 地区分布</div>
              <div ref="chartMap" class="echart map-h" />
            </div>
            <div class="glass chart-wrap">
              <div class="chart-title">Top 国家请求量</div>
              <div ref="chartCountry" class="echart country-h" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="16" class="bottom-row">
          <el-col :xs="24" :md="8">
            <div class="glass chart-wrap">
              <div class="chart-title">状态码分布</div>
              <div ref="chartPie" class="echart pie-h" />
            </div>
          </el-col>
          <el-col :xs="24" :md="16">
            <div class="glass chart-wrap table-wrap">
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
            <div class="glass chart-wrap table-wrap">
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
          <el-col :xs="24" :md="14">
            <div class="glass flow-placeholder">
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
          <el-col :xs="24" :md="10">
            <div class="glass chart-wrap table-wrap">
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

    <el-dialog v-model="configOpen" title="Traffic 数据源配置" width="560px" class="traffic-dialog">
      <el-form :model="cfgForm" label-width="140px">
        <el-form-item label="启用采集">
          <el-switch v-model="cfgForm.enabled" />
        </el-form-item>
        <el-form-item label="Access log 路径">
          <el-input v-model="cfgForm.access_log_path" placeholder="/var/log/nginx/access.json.log" />
        </el-form-item>
        <el-form-item label="日志格式">
          <el-select v-model="cfgForm.log_format">
            <el-option label="JSON 行" value="json" />
            <el-option label="Combined" value="combined" />
          </el-select>
        </el-form-item>
        <el-form-item label="尾部读取字节">
          <el-input-number v-model="cfgForm.max_tail_bytes" :min="65536" :max="52428800" />
        </el-form-item>
        <el-form-item label="GeoIP mmdb">
          <el-input v-model="cfgForm.geoip_db_path" placeholder="/usr/share/GeoIP/GeoLite2-City.mmdb" />
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
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { Refresh, Setting, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { trafficApi } from '@/api/traffic'

echarts.registerTheme('shark-traffic', {
  backgroundColor: 'transparent',
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(0,191,255,0.25)' } },
    axisLabel: { color: '#8FB8D9' },
    splitLine: { lineStyle: { color: 'rgba(0,191,255,0.08)' } },
  },
  valueAxis: {
    axisLine: { show: true, lineStyle: { color: 'rgba(0,191,255,0.25)' } },
    axisLabel: { color: '#8FB8D9' },
    splitLine: { lineStyle: { color: 'rgba(0,191,255,0.08)' } },
  },
  timeAxis: {
    axisLine: { lineStyle: { color: 'rgba(0,191,255,0.25)' } },
    axisLabel: { color: '#8FB8D9' },
  },
})

const particleCanvas = ref<HTMLCanvasElement | null>(null)
const range = ref('24h')
const pollSec = ref(5)
const loading = ref(false)
const mainTab = ref('trend')
const configOpen = ref(false)

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
  access_log_path: '',
  error_log_path: '',
  log_format: 'json',
  max_tail_bytes: 5242880,
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
let particleRaf = 0
let glTried = false

const kpiCards = ref([
  { key: 'total', label: '窗口内请求', value: '—', source: 'Nginx access · 聚合' },
  { key: 'qps', label: 'QPS (近60s)', value: '—', source: 'Nginx access' },
  { key: 'lat', label: '平均响应', value: '—', source: 'request_time' },
  { key: 'err', label: '错误率', value: '—', source: '4xx+5xx' },
  { key: 'up', label: '可用性', value: '—', source: 'Blackbox / 日志' },
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
  const top = color === '#00E5A8' ? 'rgba(0,229,168,0.35)' : 'rgba(0,191,255,0.35)'
  return {
    backgroundColor: 'transparent',
    grid: { left: 2, right: 2, top: 4, bottom: 2 },
    xAxis: { type: 'category', show: false, data: xs },
    yAxis: { type: 'value', show: false, min: 'dataMin' },
    series: [
      {
        type: 'line',
        data: ys,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color, shadowBlur: 6, shadowColor: color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: top },
            { offset: 1, color: 'rgba(0,191,255,0)' },
          ]),
        },
      },
    ],
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
  const colors = ['#00E5A8', '#00BFFF', '#A78BFA', '#FF6B6B', '#66FFFF']
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
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10,37,64,0.92)',
        borderColor: 'rgba(0,191,255,0.45)',
        textStyle: { color: '#E8F4FF' },
      },
      legend: { textStyle: { color: '#8FB8D9' }, data: ['QPS', 'Requests/min'] },
      xAxis: { type: 'time' },
      yAxis: [{ type: 'value', name: 'QPS' }, { type: 'value', name: 'Req', splitLine: { show: false } }],
      series: [
        {
          name: 'QPS',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: ts.qps || [],
          lineStyle: { color: '#00BFFF', width: 2, shadowBlur: 10, shadowColor: 'rgba(0,191,255,0.4)' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(0,191,255,0.35)' },
              { offset: 1, color: 'rgba(0,191,255,0.02)' },
            ]),
          },
        },
        {
          name: 'Requests/min',
          type: 'bar',
          yAxisIndex: 1,
          data: (ts.requests || []).map((x: number[]) => [x[0], x[1] / Math.max((ts.bucket_sec || 60) / 60, 1)]),
          itemStyle: { color: 'rgba(0,229,168,0.35)', borderRadius: [2, 2, 0, 0] },
        },
      ],
    })
  }

  if (chartLat.value) {
    const c = echarts.init(chartLat.value, 'shark-traffic')
    charts.lat = c
    const lat = ts.latency || {}
    c.setOption({
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: number) => `${v} ms`,
        backgroundColor: 'rgba(10,37,64,0.92)',
        borderColor: 'rgba(0,191,255,0.45)',
      },
      legend: { textStyle: { color: '#8FB8D9' } },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', name: 'ms' },
      color: ['#00BFFF', '#00E5A8', '#A78BFA'],
      series: ['p50', 'p95', 'p99'].map((name) => ({
        name: name.toUpperCase(),
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: lat[name] || [],
      })),
    })
  }

  if (chartErr.value) {
    const c = echarts.init(chartErr.value, 'shark-traffic')
    charts.err = c
    const st = ts.status_stack || {}
    c.setOption({
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,37,64,0.92)', borderColor: 'rgba(0,191,255,0.45)' },
      legend: { textStyle: { color: '#8FB8D9' } },
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      series: [
        { name: '2xx', type: 'line', stack: 's', areaStyle: { opacity: 0.35 }, lineStyle: { width: 0 }, itemStyle: { color: '#00E5A8' }, data: st['2xx'] || [] },
        { name: '4xx', type: 'line', stack: 's', areaStyle: { opacity: 0.4 }, lineStyle: { width: 0 }, itemStyle: { color: '#FBBF24' }, data: st['4xx'] || [] },
        { name: '5xx', type: 'line', stack: 's', areaStyle: { opacity: 0.45 }, lineStyle: { width: 0 }, itemStyle: { color: '#FF6B6B' }, data: st['5xx'] || [] },
      ],
    })
  }

  if (chartCountry.value) {
    const c = echarts.init(chartCountry.value, 'shark-traffic')
    charts.country = c
    const items = [...geoItems.value].sort((a, b) => b.requests - a.requests).slice(0, 10)
    c.setOption({
      grid: { left: 88, right: 16, top: 8, bottom: 8 },
      xAxis: { type: 'value', axisLabel: { color: '#8FB8D9' }, splitLine: { lineStyle: { color: 'rgba(0,191,255,0.08)' } } },
      yAxis: { type: 'category', data: items.map((i) => i.name || i.code).reverse(), axisLabel: { color: '#E8F4FF' } },
      series: [
        {
          type: 'bar',
          data: items.map((i) => i.requests).reverse(),
          barWidth: 12,
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: 'rgba(0,191,255,0.2)' },
              { offset: 1, color: '#00BFFF' },
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
      tooltip: { trigger: 'item', backgroundColor: 'rgba(10,37,64,0.92)', borderColor: 'rgba(0,191,255,0.45)' },
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          itemStyle: { borderRadius: 6, borderColor: '#0a1628', borderWidth: 2 },
          label: { color: '#E8F4FF' },
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
        globe: {
          baseTexture:
            'https://echarts.apache.org/examples/data-gl/asset/world.topo.bathy.200401.jpg',
          shading: 'lambert',
          light: { ambient: { intensity: 0.6 }, main: { intensity: 0.15 } },
          viewControl: { autoRotate: true, autoRotateSpeed: 3, distance: 150 },
        },
        series: [
          {
            type: 'scatter3D',
            coordinateSystem: 'globe',
            blendMode: 'lighter',
            symbolSize: (val: number[]) => Math.min(26, 5 + Math.log1p(val[2]) * 3),
            itemStyle: { color: '#00BFFF', opacity: 0.9 },
            data: scatter,
          },
        ],
      })
    } catch {
      if (chartGlobe.value) {
        const c = echarts.init(chartGlobe.value, 'shark-traffic')
        charts.globe = c
        c.setOption({
          title: { text: 'echarts-gl 未加载', left: 'center', top: 'center', textStyle: { color: '#8FB8D9', fontSize: 12 } },
        })
      }
    }
  }

  if (chartMap.value && !charts.map) {
    const c = echarts.init(chartMap.value, 'shark-traffic')
    charts.map = c
    try {
      const res = await fetch('https://cdn.jsdelivr.net/npm/echarts@5.4.3/map/json/world.json')
      const worldJson = await res.json()
      try {
        echarts.registerMap('world', worldJson as any)
      } catch {
        /* already registered */
      }
      const data = geoItems.value.map((g) => [g.lng, g.lat, g.requests, g.name || g.code])
      c.setOption({
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(10,37,64,0.92)',
          borderColor: 'rgba(0,191,255,0.45)',
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
          itemStyle: { areaColor: 'rgba(10,37,64,0.92)', borderColor: 'rgba(0,191,255,0.35)' },
          emphasis: { itemStyle: { areaColor: 'rgba(0,191,255,0.25)' } },
        },
        visualMap: {
          min: 0,
          max: Math.max(...geoItems.value.map((g) => g.requests), 1),
          calculable: true,
          inRange: { color: ['#0A2540', '#0066CC', '#00BFFF'] },
          textStyle: { color: '#8FB8D9' },
          left: 8,
          bottom: 24,
        },
        series: [
          {
            type: 'scatter',
            coordinateSystem: 'geo',
            data,
            symbolSize: (val: number[]) => Math.min(28, 6 + Math.sqrt((val[2] as number) || 0)),
            itemStyle: { color: '#00BFFF', shadowBlur: 10, shadowColor: 'rgba(0,191,255,0.5)' },
          },
        ],
      })
    } catch {
      c.setOption({
        title: { text: '地图数据加载失败', left: 'center', top: 'center', textStyle: { color: '#8FB8D9', fontSize: 12 } },
      })
    }
  }
}

function updateKpiText() {
  const o = overview.value || {}
  kpiCards.value = [
    { key: 'total', label: '窗口内请求', value: fmtNum(o.total_requests), source: 'Nginx access · 聚合' },
    { key: 'qps', label: 'QPS (近60s)', value: fmtNum(o.qps), source: 'Nginx access' },
    { key: 'lat', label: '平均响应', value: `${o.latency_avg_ms ?? 0} ms`, source: 'request_time' },
    { key: 'err', label: '错误率', value: `${o.error_rate_pct ?? 0}%`, source: '4xx+5xx' },
    {
      key: 'up',
      label: '可用性',
      value: o.availability_pct != null ? `${o.availability_pct}%` : '—',
      source: 'Blackbox Exporter',
    },
  ]
}

function fmtNum(n: unknown) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

async function loadAll() {
  loading.value = true
  try {
    const r = range.value
    const [ov, ts, geo, paths, slow, status, ip, tr] = await Promise.all([
      trafficApi.overview(r) as Promise<any>,
      trafficApi.timeseries(r) as Promise<any>,
      trafficApi.geo(r) as Promise<any>,
      trafficApi.top(r, 'paths', 10) as Promise<any>,
      trafficApi.top(r, 'slow', 10) as Promise<any>,
      trafficApi.top(r, 'status', 20) as Promise<any>,
      trafficApi.top(r, 'ip', 10) as Promise<any>,
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
    Object.assign(cfgForm, c)
    configOpen.value = true
  } catch {
    ElMessage.error('读取配置失败')
  }
}

async function saveCfg() {
  try {
    await trafficApi.saveConfig({ ...cfgForm })
    ElMessage.success('已保存')
    configOpen.value = false
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

function particles() {
  const c = particleCanvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  const w = (c.width = c.offsetWidth * dpr)
  const h = (c.height = c.offsetHeight * dpr)
  c.style.width = `${c.offsetWidth}px`
  c.style.height = `${c.offsetHeight}px`
  const dots = Array.from({ length: 48 }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: Math.random() * 1.5 + 0.3,
    vx: (Math.random() - 0.5) * 0.25,
    vy: (Math.random() - 0.5) * 0.25,
    a: Math.random() * 0.5 + 0.15,
  }))
  const tick = () => {
    ctx.clearRect(0, 0, w, h)
    dots.forEach((d) => {
      d.x += d.vx * dpr
      d.y += d.vy * dpr
      if (d.x < 0) d.x = w
      if (d.x > w) d.x = 0
      if (d.y < 0) d.y = h
      if (d.y > h) d.y = 0
      ctx.beginPath()
      ctx.fillStyle = `rgba(0,191,255,${d.a})`
      ctx.arc(d.x, d.y, d.r * dpr, 0, Math.PI * 2)
      ctx.fill()
    })
    particleRaf = requestAnimationFrame(tick)
  }
  tick()
}

onMounted(() => {
  loadAll()
  setupPoll()
  nextTick(() => particles())
  window.addEventListener('resize', onResize)
})

function onResize() {
  Object.values(charts).forEach((c) => c?.resize())
  Object.values(kpiCharts).forEach((c) => c?.resize())
}

onUnmounted(() => {
  if (pollId) clearInterval(pollId)
  cancelAnimationFrame(particleRaf)
  disposeAllMain()
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.traffic-page {
  min-height: calc(100vh - 80px);
  position: relative;
  padding: 16px 20px 32px;
  background: radial-gradient(ellipse 120% 80% at 50% -20%, rgba(0, 191, 255, 0.12), transparent),
    linear-gradient(180deg, #050810 0%, #0a1628 45%, #050810 100%);
  color: #e8f4ff;
}

.particles {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  opacity: 0.55;
}

.traffic-header,
.main-tabs,
.kpi-row,
.chart-row,
.bottom-row,
.flow-row {
  position: relative;
  z-index: 1;
}

.glass-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  margin-bottom: 16px;
  border-radius: 14px;
  background: rgba(10, 37, 64, 0.45);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(0, 191, 255, 0.28);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.header-left h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #00bfff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.tagline {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.range-group :deep(.el-radio-button__inner) {
  background: rgba(0, 191, 255, 0.08);
  border-color: rgba(0, 191, 255, 0.25);
  color: #8fb8d9;
}
.range-group :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(90deg, #00bfff, #0088cc);
  color: #fff;
  box-shadow: 0 0 12px rgba(0, 191, 255, 0.45);
}

.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
.main-tabs :deep(.el-tabs__item) {
  color: #8fb8d9;
  font-weight: 600;
}
.main-tabs :deep(.el-tabs__item.is-active) {
  color: #00bfff;
}
.main-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(90deg, #00bfff, transparent);
  height: 3px;
}

.warn-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: 10px;
  font-size: 13px;
  color: #fcd34d;
  border: 1px solid rgba(251, 191, 36, 0.35);
  background: rgba(251, 191, 36, 0.08);
}
.warn-banner code {
  font-size: 11px;
  color: #fde68a;
}

.glass {
  background: rgba(10, 37, 64, 0.42);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(0, 191, 255, 0.22);
  border-radius: 14px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.glass:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 36px rgba(0, 191, 255, 0.12);
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
@media (max-width: 1200px) {
  .kpi-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 768px) {
  .kpi-row {
    grid-template-columns: 1fr 1fr;
  }
}
.kpi-card {
  padding: 12px 14px 8px;
  min-height: 118px;
}
.kpi-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #00bfff;
  margin: 4px 0;
  text-shadow: 0 0 20px rgba(0, 191, 255, 0.35);
}
.kpi-src {
  font-size: 10px;
  color: #475569;
  margin-bottom: 4px;
}
.kpi-spark {
  height: 36px;
  width: 100%;
}

.chart-wrap {
  padding: 12px 14px 8px;
  margin-bottom: 16px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 6px;
}
.echart {
  width: 100%;
  height: 260px;
}
.globe-wrap .globe {
  height: 300px;
}
.map-h {
  height: 260px;
}
.country-h {
  height: 220px;
}
.pie-h {
  height: 280px;
}

.jaeger-alert {
  margin-bottom: 16px;
  background: rgba(0, 191, 255, 0.08);
  border: 1px solid rgba(0, 191, 255, 0.25);
}
.flow-placeholder {
  padding: 24px;
  min-height: 360px;
}
.ph-title {
  font-size: 16px;
  font-weight: 700;
  color: #00bfff;
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
  border-radius: 12px;
  border: 1px solid rgba(0, 191, 255, 0.45);
  color: #00bfff;
  box-shadow: 0 0 16px rgba(0, 191, 255, 0.15);
  font-weight: 600;
}
.ph-node.dim {
  opacity: 0.55;
}
.ph-edge {
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #00bfff, transparent);
}

.dark-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: rgba(0, 191, 255, 0.04);
  --el-table-header-bg-color: rgba(0, 191, 255, 0.1);
  --el-table-text-color: #e8f4ff;
  --el-table-border-color: rgba(0, 191, 255, 0.15);
}
</style>

<style>
.traffic-dialog .el-dialog {
  background: #0a1628;
  border: 1px solid rgba(0, 191, 255, 0.3);
}
.traffic-dialog .el-dialog__title {
  color: #e8f4ff;
}
</style>
