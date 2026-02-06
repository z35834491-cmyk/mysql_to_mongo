<template>
  <div class="perf-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">Performance</h1>
        <p class="page-subtitle">容量分析 / Trace 查询 / HPA 联动</p>
      </div>
    </div>

    <el-card class="main-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Clusters" name="clusters">
          <div class="toolbar">
            <el-button type="primary" @click="openClusterDialog()">New Cluster</el-button>
            <el-button @click="fetchClusters">Refresh</el-button>
          </div>

          <el-table :data="clusters" style="width: 100%" v-loading="loadingClusters">
            <el-table-column prop="name" label="Name" width="220" />
            <el-table-column prop="prometheus_url" label="Prometheus/VM URL" />
            <el-table-column prop="tempo_url" label="Tempo URL" />
            <el-table-column label="Actions" width="220">
              <template #default="{ row }">
                <el-button size="small" @click="openClusterDialog(row)">Edit</el-button>
                <el-button size="small" type="danger" @click="deleteCluster(row)">Delete</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Capacity" name="capacity">
          <div class="form-grid">
            <el-form :model="capForm" label-width="130px" class="form-left">
              <el-form-item label="Cluster">
                <el-select v-model="capForm.cluster_id" placeholder="Select cluster" style="width: 100%" @change="onSelectCluster">
                  <el-option v-for="c in clusters" :key="c.id" :label="c.name" :value="c.id!" />
                </el-select>
              </el-form-item>
              <el-form-item label="Namespace">
                <el-input v-model="capForm.namespace" placeholder="default" />
              </el-form-item>
              <el-form-item label="Service Name">
                <el-select v-model="capForm.service_name" placeholder="Select service" style="width: 100%" filterable @change="onSelectService">
                  <el-option v-for="s in services" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item label="PromQL Template">
                <el-select v-model="selectedTemplateId" placeholder="Select template" style="width: 100%" @change="applyTemplate">
                  <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="Test ID">
                <el-input v-model="capForm.test_id" placeholder="optional" />
              </el-form-item>
              <el-form-item label="Time Range">
                <el-date-picker
                  v-model="capTimeRange"
                  type="datetimerange"
                  range-separator="to"
                  start-placeholder="Start"
                  end-placeholder="End"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="Step (sec)">
                <el-input-number v-model="capForm.step_sec" :min="1" :max="600" />
              </el-form-item>
              <el-form-item label="CPU Limit (cores)">
                <el-input v-model="capForm.cpu_limit_cores" placeholder="optional, override" />
              </el-form-item>
              <el-form-item label="Workload Name">
                <el-input v-model="capForm.workload_name" placeholder="deployment name (optional)" />
              </el-form-item>
              <el-form-item label="Enable AI">
                <el-switch v-model="capForm.enable_ai" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="analyzing" @click="runAnalyze">Analyze</el-button>
              </el-form-item>
            </el-form>

            <div class="form-right">
              <el-form label-width="120px">
                <el-form-item label="QPS Query">
                  <el-input v-model="capForm.qps_query" type="textarea" :rows="5" placeholder="PromQL for QPS (sum(rate(...)))" />
                </el-form-item>
                <el-form-item label="CPU Query">
                  <el-input v-model="capForm.cpu_query" type="textarea" :rows="5" placeholder="PromQL for CPU cores usage (sum(rate(container_cpu_usage_seconds_total...)))" />
                </el-form-item>
              </el-form>
            </div>
          </div>

          <div v-if="capResult" class="result">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="QPS / Core">{{ capResult.qps_per_core.toFixed(3) }}</el-descriptions-item>
              <el-descriptions-item label="Confidence">{{ capResult.confidence.toFixed(3) }}</el-descriptions-item>
              <el-descriptions-item label="CPU Limit (cores)">{{ capResult.cpu_limit_cores.toFixed(3) }}</el-descriptions-item>
              <el-descriptions-item label="Max QPS Reached">{{ capResult.max_qps_reached }}</el-descriptions-item>
            </el-descriptions>
            <div class="md">
              <div class="md-title">AI Suggestions</div>
              <pre class="md-body">{{ capResult.ai_suggestions || capResult.report_markdown }}</pre>
            </div>
          </div>

          <div class="reports">
            <div class="toolbar">
              <el-button @click="fetchReports">Refresh Reports</el-button>
            </div>
            <el-table :data="reports" style="width: 100%" v-loading="loadingReports">
              <el-table-column prop="created_at" label="Created" width="190" />
              <el-table-column prop="cluster" label="Cluster" width="90" />
              <el-table-column prop="namespace" label="NS" width="120" />
              <el-table-column prop="service_name" label="Service" />
              <el-table-column prop="max_qps_reached" label="Max QPS" width="120" />
              <el-table-column prop="confidence" label="Conf" width="100">
                <template #default="{ row }">{{ Number(row.confidence).toFixed(3) }}</template>
              </el-table-column>
              <el-table-column label="View" width="100">
                <template #default="{ row }">
                  <el-button size="small" @click="openReport(row)">Open</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Traces" name="traces">
          <el-form :model="traceForm" label-width="120px" style="max-width: 900px">
            <el-form-item label="Cluster">
              <el-select v-model="traceForm.cluster_id" placeholder="Select cluster" style="width: 100%">
                <el-option v-for="c in clusters" :key="c.id" :label="c.name" :value="c.id!" />
              </el-select>
            </el-form-item>
            <el-form-item label="Trace ID">
              <el-input v-model="traceForm.trace_id" placeholder="trace id" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loadingTrace" @click="fetchTrace">Fetch</el-button>
            </el-form-item>
          </el-form>
          <div v-if="traceChartOption" class="trace-chart">
            <v-chart :option="traceChartOption" autoresize />
          </div>
          <div v-if="traceInsights" class="trace-insights">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="Duration (ms)">{{ traceInsights.trace?.duration_ms }}</el-descriptions-item>
              <el-descriptions-item label="Span Count">{{ traceInsights.trace?.span_count }}</el-descriptions-item>
              <el-descriptions-item label="Services" :span="2">{{ (traceInsights.trace?.services || []).join(', ') }}</el-descriptions-item>
            </el-descriptions>
            <el-table :data="traceInsights.metrics || []" style="width: 100%; margin-top: 12px">
              <el-table-column prop="namespace" label="NS" width="140" />
              <el-table-column prop="pod" label="Pod" min-width="260" />
              <el-table-column prop="service" label="Service" min-width="180" />
              <el-table-column prop="cpu_cores_avg" label="CPU Avg" width="110" />
              <el-table-column prop="cpu_cores_max" label="CPU Max" width="110" />
              <el-table-column prop="mem_mb_avg" label="Mem Avg(MB)" width="130" />
              <el-table-column prop="mem_mb_max" label="Mem Max(MB)" width="130" />
            </el-table>
          </div>
          <pre class="json">{{ traceJson }}</pre>
        </el-tab-pane>

        <el-tab-pane label="HPA" name="hpa">
          <el-form :model="hpaForm" label-width="120px" style="max-width: 900px">
            <el-form-item label="Cluster">
              <el-select v-model="hpaForm.cluster_id" placeholder="Select cluster" style="width: 100%">
                <el-option v-for="c in clusters" :key="c.id" :label="c.name" :value="c.id!" />
              </el-select>
            </el-form-item>
            <el-form-item label="Namespace">
              <el-input v-model="hpaForm.namespace" placeholder="default" />
            </el-form-item>
            <el-form-item>
              <el-button :loading="loadingHpa" @click="fetchHpa">List</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="hpaItems" style="width: 100%" v-loading="loadingHpa">
            <el-table-column prop="name" label="Name" width="260" />
            <el-table-column label="Min" width="80">
              <template #default="{ row }">{{ row.spec?.min_replicas ?? row.spec?.minReplicas }}</template>
            </el-table-column>
            <el-table-column label="Max" width="80">
              <template #default="{ row }">{{ row.spec?.max_replicas ?? row.spec?.maxReplicas }}</template>
            </el-table-column>
            <el-table-column label="Target CPU" width="140">
              <template #default="{ row }">{{ row.spec?.target_cpu_utilization_percentage ?? row.spec?.targetCPUUtilizationPercentage }}</template>
            </el-table-column>
            <el-table-column label="Apply" width="260">
              <template #default="{ row }">
                <el-button size="small" @click="openApplyHpa(row)">Apply Suggestion</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="clusterDialogVisible" title="Cluster" width="800px">
      <el-form :model="clusterForm" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="clusterForm.name" />
        </el-form-item>
        <el-form-item label="Prometheus URL">
          <el-input v-model="clusterForm.prometheus_url" />
        </el-form-item>
        <el-form-item label="Tempo URL">
          <el-input v-model="clusterForm.tempo_url" />
        </el-form-item>
        <el-form-item label="Kubeconfig">
          <el-input v-model="clusterForm.kube_config" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clusterDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="savingCluster" @click="saveCluster">Save</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportDialogVisible" title="Load Test Report" width="900px">
      <el-descriptions :column="2" border v-if="activeReport">
        <el-descriptions-item label="Test ID">{{ activeReport.test_id }}</el-descriptions-item>
        <el-descriptions-item label="Service">{{ activeReport.namespace }}/{{ activeReport.service_name }}</el-descriptions-item>
        <el-descriptions-item label="Max QPS">{{ activeReport.max_qps_reached }}</el-descriptions-item>
        <el-descriptions-item label="Confidence">{{ Number(activeReport.confidence).toFixed(3) }}</el-descriptions-item>
      </el-descriptions>
      <pre class="md-body" v-if="activeReport">{{ activeReport.report_markdown || activeReport.ai_suggestions }}</pre>
    </el-dialog>

    <el-dialog v-model="applyDialogVisible" title="Apply HPA" width="600px">
      <el-form :model="applyForm" label-width="140px">
        <el-form-item label="HPA Name">
          <el-input v-model="applyForm.name" disabled />
        </el-form-item>
        <el-form-item label="Min Replicas">
          <el-input-number v-model="applyForm.minReplicas" :min="0" />
        </el-form-item>
        <el-form-item label="Max Replicas">
          <el-input-number v-model="applyForm.maxReplicas" :min="1" />
        </el-form-item>
        <el-form-item label="Target CPU">
          <el-input-number v-model="applyForm.targetCPUUtilization" :min="1" :max="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="applyingHpa" @click="submitApplyHpa">Apply</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { perfApi, type ClusterConfig, type LoadTestReport } from '@/api/perf'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, DataZoomComponent])

const activeTab = ref('clusters')

const clusters = ref<ClusterConfig[]>([])
const loadingClusters = ref(false)

const clusterDialogVisible = ref(false)
const savingCluster = ref(false)
const clusterForm = ref<Partial<ClusterConfig>>({})

const capForm = ref<any>({
  cluster_id: undefined,
  namespace: 'default',
  service_name: '',
  test_id: '',
  step_sec: 30,
  qps_query: '',
  cpu_query: '',
  cpu_limit_cores: '',
  workload_name: '',
  enable_ai: true,
})
const capTimeRange = ref<any[]>([])
const analyzing = ref(false)
const capResult = ref<LoadTestReport | null>(null)
const services = ref<string[]>([])
const templates = ref<any[]>([])
const selectedTemplateId = ref<string>('')

const reports = ref<LoadTestReport[]>([])
const loadingReports = ref(false)
const reportDialogVisible = ref(false)
const activeReport = ref<LoadTestReport | null>(null)

const traceForm = ref<any>({ cluster_id: undefined, trace_id: '' })
const loadingTrace = ref(false)
const traceJson = ref('')
const traceChartOption = ref<any>(null)
const traceInsights = ref<any>(null)

const hpaForm = ref<any>({ cluster_id: undefined, namespace: 'default' })
const loadingHpa = ref(false)
const hpaItems = ref<any[]>([])
const applyDialogVisible = ref(false)
const applyingHpa = ref(false)
const applyForm = ref<any>({ cluster_id: undefined, namespace: 'default', name: '', minReplicas: 1, maxReplicas: 3, targetCPUUtilization: 60 })

const fetchClusters = async () => {
  loadingClusters.value = true
  try {
    clusters.value = await perfApi.listClusters()
  } finally {
    loadingClusters.value = false
  }
}

const openClusterDialog = (row?: ClusterConfig) => {
  clusterForm.value = row ? { ...row } : { name: '', kube_config: '', prometheus_url: '', tempo_url: '' }
  clusterDialogVisible.value = true
}

const saveCluster = async () => {
  savingCluster.value = true
  try {
    if (!clusterForm.value.name) {
      ElMessage.error('Name required')
      return
    }
    if (clusterForm.value.id) {
      await perfApi.updateCluster(clusterForm.value.id, clusterForm.value)
    } else {
      await perfApi.createCluster(clusterForm.value)
    }
    clusterDialogVisible.value = false
    fetchClusters()
  } finally {
    savingCluster.value = false
  }
}

const deleteCluster = async (row: ClusterConfig) => {
  try {
    await ElMessageBox.confirm(`Delete cluster ${row.name}?`, 'Warning', { type: 'warning' })
    await perfApi.deleteCluster(row.id!)
    fetchClusters()
  } catch {}
}

const onSelectCluster = () => {
  capResult.value = null
  templates.value = []
  selectedTemplateId.value = ''
  services.value = []
  if (capForm.value.cluster_id) {
    refreshServices()
  }
}

const refreshServices = async () => {
  try {
    const res = await perfApi.listServices(Number(capForm.value.cluster_id), String(capForm.value.namespace || 'default'))
    services.value = res.items || []
  } catch {
    services.value = []
  }
}

const onSelectService = async () => {
  templates.value = []
  selectedTemplateId.value = ''
  if (!capForm.value.cluster_id || !capForm.value.service_name) return
  try {
    const res = await perfApi.listPromqlTemplates(
      Number(capForm.value.cluster_id),
      String(capForm.value.namespace || 'default'),
      String(capForm.value.service_name)
    )
    templates.value = res.items || []
    if (templates.value.length > 0) {
      selectedTemplateId.value = templates.value[0].id
      applyTemplate()
    }
  } catch {
    templates.value = []
  }
}

const applyTemplate = () => {
  const t = templates.value.find((x) => x.id === selectedTemplateId.value)
  if (!t) return
  capForm.value.qps_query = t.qps_query || capForm.value.qps_query
  capForm.value.cpu_query = t.cpu_query || capForm.value.cpu_query
}

const runAnalyze = async () => {
  if (!capForm.value.cluster_id) return ElMessage.error('Select cluster')
  if (!capForm.value.service_name) return ElMessage.error('Service name required')
  if (!capTimeRange.value || capTimeRange.value.length !== 2) return ElMessage.error('Time range required')
  if (!capForm.value.qps_query || !capForm.value.cpu_query) return ElMessage.error('PromQL required')

  analyzing.value = true
  try {
    const [start, end] = capTimeRange.value
    const payload = {
      ...capForm.value,
      start_time: new Date(start).toISOString(),
      end_time: new Date(end).toISOString(),
    }
    const res: any = await perfApi.analyzeCapacity(payload)
    const jobId = Number(res?.job_id)
    if (!jobId) {
      throw new Error('job_id missing')
    }
    const startedAt = Date.now()
    while (Date.now() - startedAt < 10 * 60 * 1000) {
      const job = await perfApi.getJob(jobId)
      if (job.status === 'success') {
        capResult.value = job.result?.report || null
        activeTab.value = 'capacity'
        fetchReports()
        return
      }
      if (job.status === 'failed') {
        throw new Error(job.error || 'Job failed')
      }
      await new Promise((r) => setTimeout(r, 1500))
    }
    throw new Error('Job timeout')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Analyze failed')
  } finally {
    analyzing.value = false
  }
}

const fetchReports = async () => {
  loadingReports.value = true
  try {
    reports.value = await perfApi.listReports({ cluster_id: capForm.value.cluster_id })
  } finally {
    loadingReports.value = false
  }
}

const openReport = async (row: LoadTestReport) => {
  try {
    activeReport.value = await perfApi.getReport(row.id)
    reportDialogVisible.value = true
  } catch {
    ElMessage.error('Load failed')
  }
}

const fetchTrace = async () => {
  if (!traceForm.value.cluster_id) return ElMessage.error('Select cluster')
  if (!traceForm.value.trace_id) return ElMessage.error('Trace ID required')
  loadingTrace.value = true
  try {
    const data = await perfApi.getTrace(traceForm.value.cluster_id, traceForm.value.trace_id)
    traceJson.value = JSON.stringify(data, null, 2)
    traceChartOption.value = buildTraceWaterfallOption(data)
    traceInsights.value = await perfApi.getTraceInsights(traceForm.value.cluster_id, traceForm.value.trace_id)
  } catch (e: any) {
    traceChartOption.value = null
    traceInsights.value = null
    traceJson.value = e?.response?.data?.detail || e?.response?.data?.error || 'Failed'
  } finally {
    loadingTrace.value = false
  }
}

const normalizeAttrs = (attrs: any): Record<string, any> => {
  const out: Record<string, any> = {}
  const list = attrs?.attributes || attrs || []
  if (Array.isArray(list)) {
    for (const a of list) {
      const k = a?.key
      if (!k) continue
      const v = a?.value
      out[k] = v?.stringValue ?? v?.intValue ?? v?.doubleValue ?? v?.boolValue ?? v ?? null
    }
  }
  return out
}

const extractTempoSpans = (data: any) => {
  const spans: any[] = []
  const batches = data?.batches
  if (Array.isArray(batches)) {
    for (const b of batches) {
      const resAttrs = normalizeAttrs(b?.resource?.attributes || [])
      const service = resAttrs['service.name'] || resAttrs['service'] || ''
      const ils = b?.instrumentationLibrarySpans || b?.scopeSpans || []
      for (const s of ils) {
        const sl = s?.spans || []
        for (const sp of sl) spans.push({ ...sp, __service: service })
      }
    }
  }
  const trace = data?.trace
  if (trace?.resourceSpans && Array.isArray(trace.resourceSpans)) {
    for (const rs of trace.resourceSpans) {
      const resAttrs = normalizeAttrs(rs?.resource?.attributes || [])
      const service = resAttrs['service.name'] || resAttrs['service'] || ''
      const scopeSpans = rs?.scopeSpans || rs?.instrumentationLibrarySpans || []
      for (const ss of scopeSpans) {
        const sl = ss?.spans || []
        for (const sp of sl) spans.push({ ...sp, __service: service })
      }
    }
  }
  return spans
}

const toNano = (v: any) => {
  if (v == null) return null
  if (typeof v === 'number') return v
  if (typeof v === 'string') {
    const s = v.trim()
    if (!s) return null
    const n = Number(s)
    return isFinite(n) ? n : null
  }
  return null
}

const buildTraceWaterfallOption = (data: any) => {
  const spans = extractTempoSpans(data)
  if (!spans || spans.length === 0) return null

  let minStart = Number.POSITIVE_INFINITY
  for (const sp of spans) {
    const start = toNano(sp.startTimeUnixNano ?? sp.startTime ?? sp.start_time_unix_nano)
    const end = toNano(sp.endTimeUnixNano ?? sp.endTime ?? sp.end_time_unix_nano)
    if (!start || !end || end <= start) continue
    if (start < minStart) minStart = start
  }
  if (!isFinite(minStart)) return null

  const items: any[] = []
  for (const sp of spans) {
    const start = toNano(sp.startTimeUnixNano ?? sp.startTime ?? sp.start_time_unix_nano)
    const end = toNano(sp.endTimeUnixNano ?? sp.endTime ?? sp.end_time_unix_nano)
    if (!start || !end || end <= start) continue
    items.push({
      name: sp.name || sp.operationName || 'span',
      service: sp.__service || 'unknown',
      offsetMs: (start - minStart) / 1e6,
      durationMs: (end - start) / 1e6,
    })
  }

  items.sort((a, b) => (a.offsetMs - b.offsetMs) || (b.durationMs - a.durationMs))
  const limited = items.slice(0, 200)
  const categories = limited.map((x) => `${x.service} :: ${x.name}`)
  const offsets = limited.map((x) => x.offsetMs)
  const durations = limited.map((x) => x.durationMs)

  const serviceSet = Array.from(new Set(limited.map((x) => x.service)))
  const palette = ['#3b82f6', '#22c55e', '#f97316', '#a855f7', '#14b8a6', '#eab308', '#ef4444', '#64748b']
  const colorMap: Record<string, string> = {}
  serviceSet.forEach((s, idx) => (colorMap[s] = palette[idx % palette.length]))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        const idx = arr?.[0]?.dataIndex ?? 0
        const it = limited[idx]
        if (!it) return ''
        return `${categories[idx]}<br/>offset=${it.offsetMs.toFixed(2)}ms<br/>duration=${it.durationMs.toFixed(2)}ms`
      },
    },
    grid: { left: 260, right: 20, top: 20, bottom: 50 },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 10 },
      { type: 'inside', yAxisIndex: 0 },
    ],
    xAxis: { type: 'value', name: 'ms' },
    yAxis: { type: 'category', data: categories, axisLabel: { width: 240, overflow: 'truncate' } },
    series: [
      { type: 'bar', stack: 't', data: offsets, itemStyle: { color: 'transparent' }, emphasis: { disabled: true } },
      {
        type: 'bar',
        stack: 't',
        data: durations.map((d, i) => ({ value: d, itemStyle: { color: colorMap[limited[i].service] } })),
      },
    ],
  }
}

const fetchHpa = async () => {
  if (!hpaForm.value.cluster_id) return ElMessage.error('Select cluster')
  loadingHpa.value = true
  try {
    const res = await perfApi.listHpa(hpaForm.value.cluster_id, hpaForm.value.namespace)
    hpaItems.value = res.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Failed')
  } finally {
    loadingHpa.value = false
  }
}

const openApplyHpa = (row: any) => {
  applyForm.value = {
    cluster_id: hpaForm.value.cluster_id,
    namespace: hpaForm.value.namespace,
    name: row.name,
    minReplicas: row.spec?.minReplicas ?? 1,
    maxReplicas: row.spec?.maxReplicas ?? 3,
    targetCPUUtilization: row.spec?.targetCPUUtilizationPercentage ?? 60,
  }
  applyDialogVisible.value = true
}

const submitApplyHpa = async () => {
  applyingHpa.value = true
  try {
    await perfApi.applyHpa(applyForm.value)
    applyDialogVisible.value = false
    fetchHpa()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Apply failed')
  } finally {
    applyingHpa.value = false
  }
}

onMounted(async () => {
  await fetchClusters()
})
</script>

<style scoped>
.perf-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: calc(100vh - 100px);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.main-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  overflow: hidden;
  flex-direction: column;
}

.toolbar {
  display: flex;
  gap: 10px;
  padding: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 16px;
  padding: 12px;
}

.form-left {
  padding-right: 12px;
  border-right: 1px solid var(--app-border-color);
}

.form-right {
  padding-left: 12px;
}

.result {
  padding: 12px;
}

.md {
  margin-top: 12px;
}

.md-title {
  font-weight: 700;
  margin-bottom: 8px;
}

.md-body {
  background: #0b1220;
  color: #cbd5e1;
  padding: 12px;
  border-radius: 8px;
  max-height: 340px;
  overflow: auto;
  white-space: pre-wrap;
}

.reports {
  padding: 12px;
}

.json {
  background: #0b1220;
  color: #cbd5e1;
  padding: 12px;
  border-radius: 8px;
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
}

.trace-chart {
  height: 520px;
  margin-bottom: 12px;
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  overflow: hidden;
}

.trace-insights {
  margin-bottom: 12px;
}
</style>
