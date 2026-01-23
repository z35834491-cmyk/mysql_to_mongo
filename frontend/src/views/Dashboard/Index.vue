<template>
  <div class="dashboard-container">
    <!-- Top Metrics -->
    <el-row :gutter="24" class="stat-row">
      <el-col :span="6" v-for="item in resourceStats" :key="item.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-header">
            <span class="stat-label">{{ item.label }}</span>
            <el-icon :class="['stat-icon', item.type]"><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-main">
              <span class="stat-value">{{ item.value }}</span>
              <span :class="['stat-badge', item.statusType]">{{ item.statusText }}</span>
            </div>
            <el-progress 
              :percentage="item.percentage" 
              :color="item.color" 
              :stroke-width="4" 
              :show-text="false"
              class="stat-progress"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Pipeline Overview -->
    <el-row :gutter="24" class="content-row">
      <el-col :span="18">
        <el-card shadow="never" class="main-card">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <el-icon class="header-icon"><DataLine /></el-icon>
                <span class="header-title">Data Pipeline Performance</span>
              </div>
              <div class="header-right">
                <el-radio-group v-model="chartTimeRange" size="small" class="custom-radio">
                  <el-radio-button label="1h">1H</el-radio-button>
                  <el-radio-button label="6h">6H</el-radio-button>
                  <el-radio-button label="24h">24H</el-radio-button>
                </el-radio-group>
                <el-button :icon="Refresh" circle size="small" @click="taskStore.fetchTasks" />
              </div>
            </div>
          </template>
          
          <div class="pipeline-metrics">
            <div class="pipeline-item" v-for="metric in pipelineMetrics" :key="metric.label">
              <div :class="['icon-box', metric.colorClass]">
                <el-icon><component :is="metric.icon" /></el-icon>
              </div>
              <div class="metric-info">
                <div class="metric-value">{{ metric.value }}</div>
                <div class="metric-label">{{ metric.label }}</div>
              </div>
            </div>
          </div>

          <div class="chart-container">
            <v-chart class="chart" :option="chartOption" autoresize />
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="never" class="side-card">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <el-icon class="header-icon"><CircleCheck /></el-icon>
                <span class="header-title">System Health</span>
              </div>
            </div>
          </template>
          <div class="health-list">
            <div class="health-item" v-for="h in healthItems" :key="h.name">
              <div :class="['health-dot', h.status]"></div>
              <div class="health-info">
                <div class="health-name">{{ h.name }}</div>
                <div class="health-desc">{{ h.desc }}</div>
              </div>
              <el-tag size="small" :type="h.status === 'online' ? 'success' : 'warning'" effect="plain">
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
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, provide, onUnmounted } from 'vue'
import { useTaskStore } from '@/stores/task'
import { useSystemStore } from '@/stores/system'
import { storeToRefs } from 'pinia'
import { 
  List, VideoPlay, Link, WarnTriangleFilled, 
  Refresh, MoreFilled, CircleCheckFilled, WarningFilled,
  Cpu, PieChart, Box, DataLine, CircleCheck
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart as ECPieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  ECPieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const taskStore = useTaskStore()
const systemStore = useSystemStore()
const { taskStats } = storeToRefs(taskStore)
const { systemStats } = storeToRefs(systemStore)
const chartTimeRange = ref('1h')

const resourceStats = computed(() => {
  const stats = systemStats.value?.resources
  return [
    { label: 'System Load', value: stats?.load || 'Optimal', percentage: stats?.cpu?.percentage || 0, icon: Cpu, type: 'blue', color: '#3b82f6', statusType: 'success', statusText: 'Stable' },
    { label: 'CPU Usage', value: stats?.cpu?.value || '0%', percentage: stats?.cpu?.percentage || 0, icon: Box, type: 'purple', color: '#8b5cf6', statusType: 'info', statusText: 'Realtime' },
    { label: 'Memory', value: stats?.memory?.value || '0 GB', percentage: stats?.memory?.percentage || 0, icon: PieChart, type: 'orange', color: '#f59e0b', statusType: 'info', statusText: `of ${stats?.memory?.total || '8GB'}` },
    { label: 'Storage', value: stats?.disk?.value || '0 GB', percentage: stats?.disk?.percentage || 0, icon: Box, type: 'red', color: '#ef4444', statusType: 'warning', statusText: `${stats?.disk?.percentage || 0}%` }
  ]
})

const pipelineMetrics = computed(() => [
  { label: 'Total Tasks', value: taskStats.value.total, icon: List, colorClass: 'blue' },
  { label: 'Syncing', value: taskStats.value.running, icon: VideoPlay, colorClass: 'green' },
  { label: 'Data Sources', value: 12, icon: Link, colorClass: 'orange' },
  { label: 'Errors', value: taskStats.value.error, icon: WarnTriangleFilled, colorClass: 'red' }
])

const healthItems = computed(() => systemStats.value?.health || [
  { name: 'MySQL Master', desc: 'Latency 2ms', status: 'online' },
  { name: 'MongoDB rs0', desc: '3 Nodes Active', status: 'online' },
  { name: 'Worker Node 01', desc: 'Syncing...', status: 'online' },
  { name: 'Worker Node 02', desc: 'High Load', status: 'warning' }
])

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#fff',
    borderColor: '#e2e8f0',
    borderWidth: 1,
    textStyle: { color: '#1e293b' },
    padding: [8, 12]
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '5%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['10:00', '10:10', '10:20', '10:30', '10:40', '10:50', '11:00'],
    axisLine: { lineStyle: { color: '#e2e8f0' } },
    axisLabel: { color: '#64748b' }
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#f1f5f9' } },
    axisLabel: { color: '#64748b' }
  },
  series: [
    {
      name: 'Throughput',
      type: 'line',
      smooth: true,
      data: [120, 132, 101, 134, 90, 230, 210],
      itemStyle: { color: '#3b82f6' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.2)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ]
        }
      }
    }
  ]
}))

let timer: any = null

onMounted(() => {
  taskStore.fetchTasks()
  systemStore.fetchSystemStats()
  timer = setInterval(() => {
    systemStore.fetchSystemStats()
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  background-color: var(--app-content-bg);
  padding: 20px;
  border-radius: 8px;
}

.stat-card {
  border: 1px solid #f1f5f9 !important;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.stat-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-icon {
  font-size: 18px;
  padding: 8px;
  border-radius: 8px;
}

.stat-icon.blue { color: #3b82f6; background: #eff6ff; }
.stat-icon.purple { color: #8b5cf6; background: #f5f3ff; }
.stat-icon.orange { color: #f59e0b; background: #fffbeb; }
.stat-icon.red { color: #ef4444; background: #fef2f2; }

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.stat-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 99px;
}

.stat-badge.success { background: #dcfce7; color: #166534; }
.stat-badge.info { background: #f1f5f9; color: #475569; }
.stat-badge.warning { background: #fef3c7; color: #92400e; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 18px;
  color: #3b82f6;
}

.header-title {
  font-weight: 700;
  font-size: 16px;
  color: #1e293b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.pipeline-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 32px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 12px;
}

.pipeline-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: white;
}

.icon-box.blue { background: #3b82f6; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); }
.icon-box.green { background: #10b981; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }
.icon-box.orange { background: #f59e0b; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3); }
.icon-box.red { background: #ef4444; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3); }

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.metric-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.chart-container {
  height: 320px;
}

.health-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.health-dot.online { background: #10b981; box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1); }
.health-dot.warning { background: #f59e0b; box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1); }

.health-info {
  flex: 1;
}

.health-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.health-desc {
  font-size: 11px;
  color: #94a3b8;
}

.quick-actions {
  padding-top: 8px;
}

.action-title {
  font-size: 10px;
  font-weight: 800;
  color: #94a3b8;
  margin-bottom: 12px;
  letter-spacing: 1px;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-btn {
  width: 100%;
  justify-content: flex-start;
  border-color: #e2e8f0;
}

.custom-radio :deep(.el-radio-button__inner) {
  background: #f1f5f9;
  border: none;
  color: #64748b;
}

.custom-radio :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #fff;
  color: #3b82f6;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
</style>
