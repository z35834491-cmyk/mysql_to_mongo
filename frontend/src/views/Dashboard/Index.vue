<template>
  <div class="dashboard-container">
    <!-- Top Stats Row -->
    <el-row :gutter="24">
      <el-col :span="6" v-for="item in topStats" :key="item.name">
        <div class="stat-card">
          <div class="stat-header">
            <span class="stat-label">{{ item.label }}</span>
            <el-icon class="stat-icon" :class="item.name"><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-footer">
            <el-progress :percentage="item.percentage" :show-text="false" :color="item.color" />
            <span class="stat-desc">{{ item.desc }}</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="24">
      <!-- Data Pipeline Performance (ECharts) -->
      <el-col :span="18">
        <div class="chart-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><PieChart /></el-icon>
              <span>Data Pipeline Performance</span>
            </div>
            <div class="header-actions">
              <el-radio-group v-model="timeRange" size="small">
                <el-radio-button label="1h">1H</el-radio-button>
                <el-radio-button label="6h">6H</el-radio-button>
                <el-radio-button label="24h">24H</el-radio-button>
              </el-radio-group>
              <el-button :icon="Refresh" circle size="small" />
            </div>
          </div>
          
          <div class="pipeline-metrics">
            <div class="metric-item" v-for="m in pipelineMetrics" :key="m.label">
              <el-icon :style="{ backgroundColor: m.bg, color: m.color }"><component :is="m.icon" /></el-icon>
              <div class="metric-info">
                <span class="metric-val">{{ m.value }}</span>
                <span class="metric-label">{{ m.label }}</span>
              </div>
            </div>
          </div>

          <div ref="chartRef" class="main-chart"></div>
        </div>
      </el-col>

      <!-- System Health -->
      <el-col :span="6">
        <div class="health-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><CircleCheck /></el-icon>
              <span>System Health</span>
            </div>
          </div>
          
          <div class="health-list">
            <div class="health-item" v-for="h in systemHealth" :key="h.name">
              <div class="health-info">
                <span class="status-dot" :class="h.status"></span>
                <div class="health-text">
                  <div class="health-name">{{ h.name }}</div>
                  <div class="health-desc">{{ h.desc }}</div>
                </div>
              </div>
              <el-tag :type="h.status === 'online' ? 'success' : 'warning'" size="small" effect="plain">
                {{ h.status.toUpperCase() }}
              </el-tag>
            </div>
          </div>

          <el-divider />
          <div class="quick-actions">
            <div class="action-title">QUICK ACTIONS</div>
            <div class="action-buttons">
              <el-button size="small" class="action-btn" plain @click="$router.push('/system')">Run Inspection</el-button>
              <el-button size="small" class="action-btn" plain @click="$router.push('/tasks')">New Sync Task</el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { 
  Cpu, PieChart, Refresh, CircleCheck, 
  DataAnalysis, Connection, Link, Warning 
} from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'
import { storeToRefs } from 'pinia'

const systemStore = useSystemStore()
const { systemStats } = storeToRefs(systemStore)

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
const timeRange = ref('1h')

const topStats = computed(() => [
  { 
    label: 'SYSTEM LOAD', 
    value: systemStats.value?.resources?.load || 'Optimal', 
    desc: 'Stable', 
    percentage: 30, 
    icon: 'Cpu', 
    color: 'var(--el-color-primary)',
    name: 'load' 
  },
  { 
    label: 'CPU USAGE', 
    value: systemStats.value?.resources?.cpu?.value || '0%', 
    desc: 'Realtime', 
    percentage: systemStats.value?.resources?.cpu?.percentage || 0, 
    icon: 'Cpu', 
    color: '#8b5cf6',
    name: 'cpu' 
  },
  { 
    label: 'MEMORY', 
    value: systemStats.value?.resources?.memory?.value || '0.0GB', 
    desc: `of ${systemStats.value?.resources?.memory?.total || '0.0GB'}`, 
    percentage: systemStats.value?.resources?.memory?.percentage || 0, 
    icon: 'PieChart', 
    color: '#f59e0b',
    name: 'memory' 
  },
  { 
    label: 'STORAGE', 
    value: systemStats.value?.resources?.disk?.value || '0.0GB', 
    desc: `${systemStats.value?.resources?.disk?.percentage || 0}%`, 
    percentage: systemStats.value?.resources?.disk?.percentage || 0, 
    icon: 'PieChart', 
    color: '#ef4444',
    name: 'disk' 
  }
])

const pipelineMetrics = [
  { label: 'Total Tasks', value: 0, icon: 'DataAnalysis', color: 'var(--el-color-primary)', bg: 'rgba(var(--el-color-primary-rgb), 0.1)' },
  { label: 'Syncing', value: 0, icon: 'Connection', color: '#10b981', bg: '#ecfdf5' },
  { label: 'Data Sources', value: 12, icon: 'Link', color: '#f59e0b', bg: '#fffbeb' },
  { label: 'Errors', value: 0, icon: 'Warning', color: '#ef4444', bg: '#fef2f2' }
]

const systemHealth = computed(() => systemStats.value?.health || [])

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '10%' },
    xAxis: { type: 'category', boundaryGap: false, data: ['10:00', '10:10', '10:20', '10:30', '10:40', '10:50', '11:00'], axisLine: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        name: 'Performance',
        type: 'line',
        smooth: true,
        data: [120, 132, 101, 134, 90, 230, 210],
        lineStyle: { color: '#409EFF', width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.2)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0)' }
          ])
        },
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#409EFF' }
      }
    ]
  }
  chart.setOption(option)
}

onMounted(() => {
  systemStore.fetchSystemStats()
  initChart()
  window.addEventListener('resize', () => chart?.resize())
  const timer = setInterval(() => systemStore.fetchSystemStats(), 5000)
  onUnmounted(() => {
    clearInterval(timer)
    chart?.dispose()
  })
})
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stat-card {
  background-color: var(--app-card-bg);
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  padding: 24px;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.chart-card {
  background-color: var(--app-card-bg);
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  padding: 24px;
}

.health-card {
  background-color: var(--app-card-bg);
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  padding: 24px;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stat-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--app-text-muted);
  letter-spacing: 0.05em;
}

.stat-icon {
  font-size: 20px;
  padding: 8px;
  border-radius: 10px;
}

.stat-icon.load { background: rgba(var(--el-color-primary-rgb), 0.1); color: var(--el-color-primary); }
.stat-icon.cpu { background: #f5f3ff; color: #8b5cf6; }
.stat-icon.memory { background: #fffbeb; color: #f59e0b; }
.stat-icon.disk { background: #fef2f2; color: #ef4444; }

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--app-text-main);
  margin-bottom: 16px;
}

.stat-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-desc {
  font-size: 12px;
  color: var(--app-text-muted);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  color: var(--app-text-main);
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.pipeline-metrics {
  display: flex;
  justify-content: space-between;
  margin-bottom: 32px;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-item .el-icon {
  font-size: 20px;
  padding: 12px;
  border-radius: 12px;
}

.metric-info {
  display: flex;
  flex-direction: column;
}

.metric-val {
  font-size: 18px;
  font-weight: 700;
  color: var(--app-text-main);
}

.metric-label {
  font-size: 12px;
  color: var(--app-text-muted);
}

.main-chart {
  height: 350px;
}

.health-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.health-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.online { background: #10b981; box-shadow: 0 0 8px #10b981; }
.status-dot.warning { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }

.health-name {
  font-weight: 700;
  color: var(--app-text-main);
  font-size: 14px;
}

.health-desc {
  font-size: 12px;
  color: var(--app-text-muted);
}

.quick-actions {
  padding-top: 8px;
}

.action-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--app-text-muted);
  letter-spacing: 0.1em;
  margin-bottom: 16px;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-btn {
  justify-content: flex-start;
  padding: 10px 16px;
  border-radius: 8px;
}
</style>
