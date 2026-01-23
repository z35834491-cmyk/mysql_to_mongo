<template>
  <div class="inspection-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">System Inspection</h2>
        <p class="page-subtitle">AI-powered system health analysis and performance auditing</p>
      </div>
      <div class="header-actions">
        <el-button @click="showLogs" :icon="Document">Inspection Logs</el-button>
        <el-button @click="configVisible = true" :icon="Setting">Configure AI</el-button>
        <el-button type="primary" size="large" @click="handleRun" :loading="loading" class="action-btn shadow-btn">
          <el-icon><Search /></el-icon> Run New Inspection
        </el-button>
      </div>
    </div>
    
    <el-card shadow="never" class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="report_id" label="Report Timestamp" width="220">
          <template #default="{ row }">
            <div class="report-id-cell">
              <el-icon class="report-icon"><Calendar /></el-icon>
              <span>{{ formatIdToDate(row.report_id) }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="Health Status" width="160">
          <template #default="{ row }">
            <div class="score-wrapper">
              <template v-if="row.score !== undefined">
                <el-progress 
                  type="circle" 
                  :percentage="row.score" 
                  :width="40" 
                  :stroke-width="4"
                  :status="getProgressStatus(row.score)"
                />
                <el-tag :type="getScoreType(row.score)" size="small" effect="plain" class="score-tag">
                  {{ row.score }}
                </el-tag>
              </template>
              <template v-else>
                <el-icon class="status-icon-placeholder"><CircleCheck /></el-icon>
                <el-tag type="info" size="small" effect="plain" class="score-tag">N/A</el-tag>
              </template>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="summary" label="Analysis Summary">
          <template #default="{ row }">
            <span class="summary-text">{{ row.summary || 'Awaiting full report analysis...' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" plain size="small" @click="viewReport(row)">
              View Details
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Report Detail Dialog -->
    <el-dialog 
      v-model="dialogVisible" 
      title="Inspection Report Analysis" 
      width="800px"
      class="report-dialog"
    >
      <div v-if="currentReport" class="report-content">
        <div class="report-meta">
          <div class="meta-item">
            <span class="label">TIMESTAMP</span>
            <span class="value">{{ formatIdToDate(currentReport.report_id) }}</span>
          </div>
          <div class="meta-item">
            <span class="label">HEALTH SCORE</span>
            <div class="score-display">
              <span :class="['score-value', getScoreType(currentReport.score)]">{{ currentReport.score }}</span>
              <span class="score-total">/100</span>
            </div>
          </div>
        </div>

        <el-divider />

        <div class="analysis-section">
          <div class="section-header">
            <el-icon><MagicStick /></el-icon>
            <span>AI Diagnostic Insights</span>
          </div>
          <div class="analysis-card">
            <div class="markdown-body">
              {{ currentReport.ai_analysis || 'No detailed analysis available for this report.' }}
            </div>
          </div>
        </div>

        <div class="analysis-section" v-if="currentReport.metrics_summary && currentReport.metrics_summary.length > 0">
          <div class="section-header">
            <el-icon><Histogram /></el-icon>
            <span>Resource Utilization Analysis</span>
          </div>
          <el-row :gutter="20" class="metrics-row">
            <el-col :span="12" v-if="getChartOption('cpu').series">
              <div class="chart-card">
                <div class="chart-title">CPU Usage Top 5 (%)</div>
                <v-chart class="report-chart" :option="getChartOption('cpu')" autoresize />
              </div>
            </el-col>
            <el-col :span="12" v-if="getChartOption('memory').series">
              <div class="chart-card">
                <div class="chart-title">Memory Usage Top 5 (%)</div>
                <v-chart class="report-chart" :option="getChartOption('memory')" autoresize />
              </div>
            </el-col>
          </el-row>
          <el-row :gutter="20" class="metrics-row" style="margin-top: 20px;">
            <el-col :span="12" v-if="getChartOption('disk').series">
              <div class="chart-card">
                <div class="chart-title">Disk Usage Top 5 (%)</div>
                <v-chart class="report-chart" :option="getChartOption('disk')" autoresize />
              </div>
            </el-col>
          </el-row>
        </div>
      </div>
    </el-dialog>

    <!-- Config Dialog -->
    <el-dialog v-model="configVisible" title="Inspection Configuration" width="540px" class="custom-dialog">
      <el-form :model="configForm" label-width="140px" label-position="top" class="config-form">
        <div class="form-section">
          <h3 class="section-title">Monitoring Data</h3>
          <el-form-item label="Prometheus Endpoint">
            <el-input v-model="configForm.prometheus_url" placeholder="http://prometheus:9090" />
            <div class="form-tip">The inspection engine pulls real-time metrics from this source</div>
          </el-form-item>
        </div>

        <div class="form-section">
          <h3 class="section-title">AI Analysis Engine (Ark/Doubao)</h3>
          <el-form-item label="Ark Base URL">
            <el-input v-model="configForm.ark_base_url" placeholder="https://ark.cn-beijing.volces.com/api/v3" />
          </el-form-item>
          <el-form-item label="Ark API Key">
            <el-input v-model="configForm.ark_api_key" type="password" show-password />
          </el-form-item>
          <el-form-item label="Ark Model Endpoint ID">
            <el-input v-model="configForm.ark_model_id" placeholder="ep-202xxxxxxxx-xxxxx" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="configVisible = false">Cancel</el-button>
          <el-button type="primary" @click="saveConfig" class="shadow-btn">Save Configuration</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Logs Dialog -->
    <el-dialog v-model="logDialogVisible" title="System Inspection Logs" width="900px" top="5vh">
      <div class="log-viewer-container">
        <div class="log-header">
           <span class="log-filename">inspection.log</span>
           <div class="log-controls">
             <el-pagination 
               small
               layout="prev, pager, next"
               :total="logTotal"
               :page-size="logPageSize"
               v-model:current-page="logPage"
               @current-change="fetchLogs"
             />
             <el-button size="small" :icon="Refresh" circle @click="fetchLogs(logPage)" />
           </div>
        </div>
        <div class="log-content" v-loading="logLoading">
          <pre>{{ logContent || 'No logs available.' }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, provide } from 'vue'
import { useSystemStore } from '@/stores/system'
import type { InspectionReport } from '@/types/system'
import { 
  Setting, Search, Calendar, 
  MagicStick, Warning, CircleCheck,
  DataLine, Histogram, Document, Refresh, Download
} from '@element-plus/icons-vue'
import { taskApi } from '@/api/task'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const systemStore = useSystemStore()
// ... existing refs and computed ...

const getChartOption = (category: string) => {
  if (!currentReport.value || !currentReport.value.metrics_summary) return {}
  
  const metrics = currentReport.value.metrics_summary.filter((m: any) => m.category === category)
  if (metrics.length === 0) return {}

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: metrics.map((m: any) => m.labels.instance || m.display),
      axisLabel: { interval: 0, rotate: 30 }
    },
    yAxis: { type: 'value', name: metrics[0].unit },
    series: [{
      data: metrics.map((m: any) => m.value),
      type: 'bar',
      itemStyle: {
        color: category === 'cpu' ? '#3b82f6' : category === 'memory' ? '#8b5cf6' : '#f59e0b'
      }
    }]
  }
}
const reports = computed(() => systemStore.reports)
const loading = computed(() => systemStore.loading)
const inspectionConfig = computed(() => systemStore.inspectionConfig)

const tableData = computed(() => {
  return reports.value || []
})

const formatIdToDate = (id: string) => {
  if (!id) return '-'
  try {
    const d = new Date(id.replace(/-/g, '/'))
    return isNaN(d.getTime()) ? id : d.toLocaleString()
  } catch (e) {
    return id
  }
}

const dialogVisible = ref(false)
const configVisible = ref(false)
const currentReport = ref<InspectionReport | null>(null)

const configForm = ref({
  prometheus_url: '',
  ark_base_url: '',
  ark_api_key: '',
  ark_model_id: ''
})

watch(inspectionConfig, (newVal) => {
  if (newVal) {
    configForm.value = { ...newVal }
  }
}, { immediate: true })

onMounted(() => {
  systemStore.fetchReports()
  systemStore.fetchInspectionConfig()
})

const handleRun = () => {
  systemStore.runInspection()
}

const saveConfig = async () => {
  await systemStore.saveInspectionConfig(configForm.value)
  configVisible.value = false
}

const getScoreType = (score: number) => {
  if (!score) return 'info'
  if (score >= 90) return 'success'
  if (score >= 70) return 'warning'
  return 'danger'
}

const getProgressStatus = (score: number) => {
  if (!score) return ''
  if (score >= 90) return 'success'
  if (score >= 70) return 'warning'
  return 'exception'
}

const viewReport = async (row: any) => {
  await systemStore.fetchReportDetail(row.report_id)
  currentReport.value = systemStore.currentReport
  dialogVisible.value = true
}

// Log Viewer Logic
const logDialogVisible = ref(false)
const logLoading = ref(false)
const logContent = ref('')
const logPage = ref(1)
const logPageSize = ref(1000)
const logTotal = ref(0)

const showLogs = () => {
  logDialogVisible.value = true
  fetchLogs(1)
}

const fetchLogs = async (page = 1) => {
  logPage.value = page
  logLoading.value = true
  try {
    // Assuming inspection.log exists in logs/inspection.log or just inspection
    // taskApi.getTaskLogs takes a task_id and appends .log
    // So 'inspection' -> 'logs/inspection.log'
    const res = await taskApi.getTaskLogs('inspection', { 
      page, 
      page_size: logPageSize.value,
      reverse: true 
    })
    logContent.value = res.lines.join('')
    logTotal.value = res.total
  } catch (e) {
    logContent.value = `Error loading logs: ${e}`
  } finally {
    logLoading.value = false
  }
}
</script>

<style scoped>
/* Log Viewer Styles */
.log-viewer-container {
  display: flex;
  flex-direction: column;
  height: 600px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  color: #e2e8f0;
}

.log-filename {
  font-weight: 600;
  font-size: 14px;
}

.log-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  color: #cbd5e1;
  font-family: 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.5;
}

.log-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Existing Styles */
.inspection-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
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
  margin: 0 0 4px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.table-card {
  border: 1px solid #f1f5f9 !important;
  border-radius: 12px !important;
}

.report-id-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  color: #334155;
}

.report-icon {
  color: #3b82f6;
}

.score-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-tag {
  font-weight: 700;
  font-size: 12px;
  min-width: 36px;
  text-align: center;
}

.status-icon-placeholder {
  font-size: 24px;
  color: #94a3b8;
}

.summary-text {
  font-size: 13px;
  color: #64748b;
}

.report-content {
  padding: 8px;
}

.report-meta {
  display: flex;
  gap: 48px;
  margin-bottom: 24px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-item .label {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 0.5px;
}

.meta-item .value {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.score-display {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-value {
  font-size: 32px;
  font-weight: 800;
}

.score-value.success { color: #10b981; }
.score-value.warning { color: #f59e0b; }
.score-value.danger { color: #ef4444; }

.score-total {
  font-size: 14px;
  color: #94a3b8;
  font-weight: 600;
}

.analysis-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  color: #1e293b;
  font-size: 16px;
}

.section-header .el-icon {
  color: #8b5cf6;
}

.analysis-card {
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 24px;
}

.markdown-body {
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 14px;
  color: #334155;
}

.metrics-row {
  margin-top: 10px;
}

.chart-card {
  background: white;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  padding: 16px;
}

.chart-title {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.report-chart {
  height: 200px;
}

.form-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 16px;
  border-left: 3px solid #3b82f6;
  padding-left: 8px;
}

.form-tip {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.shadow-btn {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #475569;
  font-size: 13px;
}
</style>
