<template>
  <div class="monitor-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">System Logs</h2>
        <p class="page-subtitle">Centralized log monitoring and analysis</p>
      </div>
      <div class="header-actions">
        <el-button @click="fetchData" :icon="Refresh" circle />
      </div>
    </div>

    <!-- Stats Dashboard -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <div class="stat-card error">
          <div class="stat-label">ERRORS (Today)</div>
          <div class="stat-value">{{ stats.summary.error }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card warning">
          <div class="stat-label">WARNINGS</div>
          <div class="stat-value">{{ stats.summary.warning }}</div>
        </div>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <div ref="chartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Search & Explorer -->
    <el-card shadow="never" class="explorer-card">
      <template #header>
        <div class="explorer-header">
          <el-input
            v-model="globalSearchQuery"
            placeholder="Global Search (grep all logs)..."
            class="global-search"
            clearable
            @keyup.enter="handleGlobalSearch"
          >
            <template #prepend>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button @click="handleGlobalSearch">Search</el-button>
            </template>
          </el-input>
        </div>
      </template>

      <div class="explorer-body">
        <!-- File List (Left) -->
        <div class="file-list">
          <div class="list-header">Log Files</div>
          <div v-loading="loading" class="list-content">
            <div 
              v-for="file in logFiles" 
              :key="file.name"
              class="file-item"
              :class="{ active: selectedFile === file.name }"
              @click="selectFile(file.name)"
            >
              <div class="file-icon"><el-icon><Document /></el-icon></div>
              <div class="file-info">
                <div class="file-name" :title="file.name">{{ file.name }}</div>
                <div class="file-meta">{{ file.size }} • {{ file.mtime }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Log Content (Right) -->
        <div class="log-viewer" v-loading="contentLoading">
          <div v-if="searchResults.length > 0" class="search-results">
            <div class="results-header">
              Found {{ searchResults.length }} matches for "{{ globalSearchQuery }}"
              <el-button link size="small" @click="clearSearch">Clear</el-button>
            </div>
            <div class="results-list">
              <div 
                v-for="(match, idx) in searchResults" 
                :key="idx" 
                class="result-item"
                @click="jumpToLog(match.file)"
              >
                <div class="result-meta">
                  <span class="res-file">{{ match.file }}</span>
                  <span class="res-line">L{{ match.line }}</span>
                </div>
                <div class="result-content">{{ match.content }}</div>
              </div>
            </div>
          </div>

          <div v-else-if="selectedFile" class="file-viewer">
            <div class="viewer-header">
              <span>{{ selectedFile }}</span>
              <el-button size="small" :icon="Refresh" circle @click="fetchLogContent" />
            </div>
            <div class="log-lines">
              <div v-for="(line, i) in logContent" :key="i" class="log-line">{{ line }}</div>
            </div>
          </div>

          <div v-else class="empty-viewer">
            <el-empty description="Select a file to view logs or search globally" />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import { taskApi } from '@/api/task'
import { Refresh, Search, Document } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const loading = ref(false)
const contentLoading = ref(false)
const stats = ref({ summary: { error: 0, warning: 0 }, trend: { hours: [], errors: [] } })
const logFiles = ref<any[]>([])
const selectedFile = ref('')
const logContent = ref<string[]>([])
const globalSearchQuery = ref('')
const searchResults = ref<any[]>([])

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const fetchData = async () => {
  loading.value = true
  try {
    const [statsRes, filesRes] = await Promise.all([
      taskApi.getLogStats(),
      taskApi.getLogFiles()
    ])
    stats.value = statsRes
    logFiles.value = filesRes
    updateChart()
  } finally {
    loading.value = false
  }
}

const selectFile = (name: string) => {
  selectedFile.value = name
  searchResults.value = [] // Clear search results to show file content
  fetchLogContent()
}

const fetchLogContent = async () => {
  if (!selectedFile.value) return
  contentLoading.value = true
  try {
    // Extract task_id from filename (assuming task_id.log)
    const taskId = selectedFile.value.replace('.log', '')
    const res = await taskApi.getTaskLogs(taskId, { page: -1, page_size: 1000 })
    logContent.value = res.lines
  } finally {
    contentLoading.value = false
  }
}

const handleGlobalSearch = async () => {
  if (!globalSearchQuery.value) return
  contentLoading.value = true
  try {
    const res = await taskApi.searchLogs(globalSearchQuery.value)
    searchResults.value = res
    selectedFile.value = '' // Deselect file to show results
  } finally {
    contentLoading.value = false
  }
}

const clearSearch = () => {
  searchResults.value = []
  globalSearchQuery.value = ''
}

const jumpToLog = (filename: string) => {
  selectFile(filename)
}

// Chart
const updateChart = () => {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top: '10%', bottom: '10%', left: '3%', right: '4%', containLabel: true },
    xAxis: { type: 'category', data: stats.value.trend.hours },
    yAxis: { type: 'value' },
    series: [{
      data: stats.value.trend.errors,
      type: 'line',
      smooth: true,
      areaStyle: { color: 'rgba(239, 68, 68, 0.1)' },
      lineStyle: { color: '#ef4444' },
      itemStyle: { color: '#ef4444' }
    }]
  })
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.monitor-container {
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

/* Stats */
.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.stat-card.error { border-left: 4px solid #ef4444; }
.stat-card.warning { border-left: 4px solid #f59e0b; }

.stat-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
}

.chart-card {
  height: 120px;
  padding: 0;
}
.chart-card :deep(.el-card__body) { padding: 0; height: 100%; }
.chart-container { width: 100%; height: 100%; }

/* Explorer */
.explorer-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.explorer-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.explorer-header {
  padding: 0;
}

.explorer-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* File List */
.file-list {
  width: 280px;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.list-header {
  padding: 12px 16px;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
}

.file-item {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  gap: 12px;
  border-bottom: 1px solid #f1f5f9;
  transition: all 0.2s;
}

.file-item:hover { background: #fff; }
.file-item.active { background: #fff; border-left: 3px solid #3b82f6; }

.file-icon { color: #64748b; margin-top: 2px; }
.file-name { font-weight: 500; font-size: 13px; color: #334155; margin-bottom: 2px; word-break: break-all; }
.file-meta { font-size: 11px; color: #94a3b8; }

/* Log Viewer */
.log-viewer {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #1e293b;
  overflow: hidden;
}

.viewer-header {
  padding: 8px 16px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #334155;
}

.log-lines {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  font-family: 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #cbd5e1;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.empty-viewer {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}

/* Search Results */
.search-results {
  flex: 1;
  overflow-y: auto;
  background: #fff;
}

.results-header {
  padding: 12px 16px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  color: #475569;
  display: flex;
  justify-content: space-between;
}

.result-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
}
.result-item:hover { background: #f8fafc; }

.result-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.res-file { font-weight: 600; color: #3b82f6; }
.result-content {
  font-family: monospace;
  font-size: 12px;
  color: #334155;
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
