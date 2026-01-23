<template>
  <div class="tasks-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Task Management</h2>
        <p class="page-subtitle">Monitor and control your data synchronization pipelines</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="handleCreate" class="action-btn shadow-btn">
          <el-icon><Plus /></el-icon> New Pipeline Task
        </el-button>
      </div>
    </div>

    <!-- Dashboard Charts -->
    <div class="charts-row">
      <el-card shadow="never" class="chart-card">
        <template #header>
          <div class="card-header">
            <span>Task Status Distribution</span>
          </div>
        </template>
        <div ref="statusChartRef" class="chart-container"></div>
      </el-card>
      
      <el-card shadow="never" class="chart-card">
        <template #header>
          <div class="card-header">
            <span>Total Events Processed</span>
          </div>
        </template>
        <div ref="eventsChartRef" class="chart-container"></div>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="tasks" v-loading="loading" style="width: 100%">
        <el-table-column prop="task_id" label="Task Identifier" min-width="180">
          <template #default="{ row }">
            <div class="task-id-cell">
              <el-icon class="task-icon"><DataLine /></el-icon>
              <span class="task-id">{{ row.task_id }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="Status" width="140">
          <template #default="{ row }">
            <div class="status-wrapper">
              <span :class="['status-dot', row.status]"></span>
              <el-tag :type="getStatusType(row.status)" size="small" effect="light" class="status-tag">
                {{ row.status.toUpperCase() }}
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Sync Progress" min-width="240">
          <template #default="{ row }">
            <div v-if="row.metrics" class="progress-details">
              <div class="progress-stats">
                <span class="stat-item">
                  <span class="label">Processed:</span>
                  <span class="value">{{ row.metrics.processed_count?.toLocaleString() || 0 }}</span>
                </span>
                <span class="stat-item" v-if="row.metrics.phase">
                  <span class="label">Phase:</span>
                  <el-tag size="small" plain>{{ row.metrics.phase }}</el-tag>
                </span>
              </div>
              
              <div class="binlog-info" v-if="row.metrics.binlog_file">
                <el-icon><Monitor /></el-icon>
                <span>{{ row.metrics.binlog_file }} : {{ row.metrics.binlog_pos }}</span>
              </div>
              
              <div class="error-msg" v-if="row.metrics.error">
                <el-icon><Warning /></el-icon>
                <span>{{ row.metrics.error }}</span>
              </div>
            </div>
            <div v-else class="text-gray text-xs italic">No metrics available</div>
          </template>
        </el-table-column>

        <el-table-column label="Operations" width="320" fixed="right">
          <template #default="{ row }">
            <div class="action-group">
              <el-tooltip content="Start Task" v-if="row.status === 'stopped' || row.status === 'error'">
                <el-button circle size="small" type="success" @click="handleStart(row.task_id)">
                  <el-icon><VideoPlay /></el-icon>
                </el-button>
              </el-tooltip>
              
              <el-tooltip content="Stop Task" v-if="row.status === 'running'">
                <el-button circle size="small" type="warning" @click="handleStop(row.task_id)">
                  <el-icon><VideoPause /></el-icon>
                </el-button>
              </el-tooltip>

              <el-tooltip content="View Logs">
                <el-button circle size="small" type="primary" plain @click="handleLogs(row.task_id)">
                  <el-icon><Document /></el-icon>
                </el-button>
              </el-tooltip>

              <el-tooltip content="Reset Task State" v-if="row.status === 'stopped' || row.status === 'error'">
                <el-button circle size="small" type="danger" plain @click="handleReset(row.task_id)">
                  <el-icon><RefreshRight /></el-icon>
                </el-button>
              </el-tooltip>

              <el-divider direction="vertical" />

              <el-button size="small" type="danger" text @click="handleDelete(row.task_id)">
                Delete
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useTaskStore } from '@/stores/task'
import { storeToRefs } from 'pinia'
import { 
  Plus, VideoPlay, VideoPause, Document, 
  RefreshRight, DataLine, Monitor, Warning 
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'

const router = useRouter()
const taskStore = useTaskStore()
const { tasks, taskStats } = storeToRefs(taskStore)
const loading = ref(false)

const statusChartRef = ref<HTMLElement>()
const eventsChartRef = ref<HTMLElement>()
let statusChart: echarts.ECharts | null = null
let eventsChart: echarts.ECharts | null = null

let timer: any = null

onMounted(async () => {
  loading.value = true
  await taskStore.fetchTasks()
  loading.value = false
  
  initCharts()
  
  timer = setInterval(() => {
    taskStore.fetchTasks()
  }, 5000)
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', handleResize)
  statusChart?.dispose()
  eventsChart?.dispose()
})

const handleResize = () => {
  statusChart?.resize()
  eventsChart?.resize()
}

watch(tasks, () => {
  updateCharts()
}, { deep: true })

const initCharts = () => {
  if (statusChartRef.value) {
    statusChart = echarts.init(statusChartRef.value)
  }
  if (eventsChartRef.value) {
    eventsChart = echarts.init(eventsChartRef.value)
  }
  // Ensure DOM is ready and charts are initialized before updating
  if (statusChart && eventsChart) {
    updateCharts()
  }
}

const updateCharts = () => {
  if (!statusChart || !eventsChart) return

  // 1. Status Chart
  const stats = taskStats.value
  statusChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: '0%', left: 'center' },
    series: [
      {
        name: 'Task Status',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: 20, fontWeight: 'bold' }
        },
        labelLine: { show: false },
        data: [
          { value: stats.running, name: 'Running', itemStyle: { color: '#10b981' } },
          { value: stats.stopped, name: 'Stopped', itemStyle: { color: '#94a3b8' } },
          { value: stats.error, name: 'Error', itemStyle: { color: '#ef4444' } }
        ]
      }
    ]
  })

  // 2. Events Chart
  // Aggregate metrics
  let totalInsert = 0
  let totalUpdate = 0
  let totalDelete = 0
  
  tasks.value.forEach(t => {
    if (t.metrics) {
      totalInsert += (t.metrics.inc_insert_count || 0) + (t.metrics.full_insert_count || 0)
      totalUpdate += (t.metrics.update_count || 0)
      totalDelete += (t.metrics.delete_count || 0)
    }
  })

  eventsChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: [
      {
        type: 'category',
        data: ['Insert', 'Update', 'Delete'],
        axisTick: { alignWithLabel: true }
      }
    ],
    yAxis: [{ type: 'value' }],
    series: [
      {
        name: 'Events',
        type: 'bar',
        barWidth: '60%',
        data: [
          { value: totalInsert, itemStyle: { color: '#3b82f6' } },
          { value: totalUpdate, itemStyle: { color: '#f59e0b' } },
          { value: totalDelete, itemStyle: { color: '#ef4444' } }
        ]
      }
    ]
  })
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'running': return 'success'
    case 'stopped': return 'info'
    case 'error': return 'danger'
    default: return 'info'
  }
}

const handleCreate = () => {
  router.push('/tasks/create')
}

const handleStart = (id: string) => {
  taskStore.startTask(id)
}

const handleStop = (id: string) => {
  taskStore.stopTask(id)
}

const handleDelete = (id: string) => {
  ElMessageBox.confirm('Are you sure you want to delete this task? This action cannot be undone.', 'Delete Task', {
    confirmButtonText: 'Delete',
    cancelButtonText: 'Cancel',
    type: 'error',
    buttonSize: 'default'
  }).then(() => {
    taskStore.deleteTask(id)
  })
}

const handleReset = (id: string) => {
  ElMessageBox.confirm('Warning: This will clear the sync state (e.g., binlog position) and trigger a fresh full sync. Proceed?', 'Reset Task', {
    confirmButtonText: 'Reset & Sync',
    cancelButtonText: 'Cancel',
    type: 'warning',
  }).then(() => {
    taskStore.resetTask(id)
  })
}

const handleLogs = (id: string) => {
  router.push(`/tasks/logs/${id}`)
}
</script>

<style scoped>
.tasks-container {
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

/* Charts Area */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.chart-card {
  border: 1px solid #f1f5f9 !important;
  border-radius: 12px !important;
}

.card-header {
  font-weight: 600;
  font-size: 14px;
  color: #475569;
}

.chart-container {
  height: 250px;
  width: 100%;
}

.table-card {
  border: 1px solid #f1f5f9 !important;
  border-radius: 12px !important;
}

.task-id-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-icon {
  font-size: 18px;
  color: #3b82f6;
}

.task-id {
  font-weight: 600;
  color: #334155;
}

.status-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.running { background: #10b981; box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1); }
.status-dot.stopped { background: #94a3b8; }
.status-dot.error { background: #ef4444; box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1); }

.status-tag {
  border-radius: 6px;
  font-weight: 600;
  font-size: 10px;
}

.progress-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-stats {
  display: flex;
  gap: 16px;
  align-items: center;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-item .label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-item .value {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.binlog-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #64748b;
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 4px;
  width: fit-content;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #ef4444;
}

.action-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.shadow-btn {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.text-xs { font-size: 12px; }
.text-gray { color: #94a3b8; }
</style>
