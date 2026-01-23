<template>
  <div class="dashboard-container">
    <!-- Top Stats Row -->
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in topStats" :key="item.name">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">{{ item.label }}</div>
              <div class="stat-value">{{ item.value }}</div>
              <div class="stat-desc">{{ item.desc }}</div>
            </div>
            <div class="stat-chart">
              <el-progress 
                type="circle" 
                :percentage="item.percentage" 
                :width="80" 
                :stroke-width="8"
                :color="getProgressColor(item.percentage)"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Overview Row -->
    <el-card shadow="never" class="overview-card">
      <template #header>
        <div class="card-header">
          <span>Overview</span>
          <el-icon class="more-icon"><MoreFilled /></el-icon>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6" v-for="stat in overviewStats" :key="stat.name">
          <div class="overview-item">
            <div class="overview-label">{{ stat.name }}</div>
            <div class="overview-val-box">
              <span class="overview-value" :class="{ 'danger': stat.danger }">{{ stat.value }}</span>
              <el-icon class="arrow-icon"><ArrowRight /></el-icon>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16">
      <!-- Traffic Chart -->
      <el-col :span="16">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span class="active">Traffic</span>
                <span>Disk IO</span>
              </div>
              <el-select v-model="networkCard" size="small" style="width: 100px">
                <el-option label="All" value="all" />
              </el-select>
            </div>
          </template>
          <div class="traffic-toolbar">
            <div class="toolbar-item">
              <span class="dot up"></span> Up: 10.8 KB
            </div>
            <div class="toolbar-item">
              <span class="dot down"></span> Down: 4.5 KB
            </div>
            <div class="toolbar-item">Total Sent: 133.2 MB</div>
            <div class="toolbar-item">Total Recv: 20.1 MB</div>
          </div>
          <div ref="chartRef" class="main-chart"></div>
        </el-card>
      </el-col>

      <!-- Software Grid -->
      <el-col :span="8">
        <el-card shadow="never" class="software-card">
          <template #header>
            <div class="card-header">
              <span>Software</span>
              <el-icon class="more-icon"><MoreFilled /></el-icon>
            </div>
          </template>
          <div class="software-grid">
            <div class="software-item" v-for="s in softwareList" :key="s.name">
              <div class="sw-icon-box">
                <el-icon :size="24" :color="s.color"><component :is="s.icon" /></el-icon>
              </div>
              <div class="sw-name">{{ s.name }}</div>
              <div class="sw-ver">{{ s.version }} <el-icon class="play-icon"><CaretRight /></el-icon></div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { MoreFilled, ArrowRight, CaretRight, Monitor, Connection, Cpu, Management, Setting } from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'
import { storeToRefs } from 'pinia'

const systemStore = useSystemStore()
const { systemStats } = storeToRefs(systemStore)
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
const networkCard = ref('all')

const topStats = computed(() => [
  { 
    label: 'Load', 
    value: 'Running Smoothly', 
    desc: 'Load Status', 
    percentage: 4, 
    name: 'load' 
  },
  { 
    label: 'CPU', 
    value: '2 Cores', 
    desc: systemStats.value?.resources?.cpu?.value || '0%', 
    percentage: systemStats.value?.resources?.cpu?.percentage || 0, 
    name: 'cpu' 
  },
  { 
    label: 'Memory', 
    value: systemStats.value?.resources?.memory?.value || '0.0GB / 0.0GB', 
    desc: 'Total Memory', 
    percentage: systemStats.value?.resources?.memory?.percentage || 0, 
    name: 'memory' 
  },
  { 
    label: 'Storage', 
    value: systemStats.value?.resources?.disk?.value || '0.0GB / 0.0GB', 
    desc: 'Root Partition', 
    percentage: systemStats.value?.resources?.disk?.percentage || 0, 
    name: 'disk' 
  }
])

const overviewStats = [
  { name: 'Websites', value: 1, danger: false },
  { name: 'Databases', value: 0, danger: false },
  { name: 'Security Risks', value: 9, danger: true },
  { name: 'System Notes', value: 'Click to edit', danger: false }
]

const softwareList = [
  { name: 'Nginx Firewall', version: '9.8.1', icon: 'Monitor', color: '#67c23a' },
  { name: 'Log Monitor', version: '4.1.8', icon: 'Connection', color: '#409eff' },
  { name: 'Nginx', version: '1.24.0', icon: 'Cpu', color: '#67c23a' },
  { name: 'MySQL', version: '5.7.44', icon: 'Management', color: '#e6a23c' },
  { name: 'phpMyAdmin', version: '5.2', icon: 'Setting', color: '#f56c6c' },
  { name: 'PHP', version: '8.2.28', icon: 'Cpu', color: '#409eff' }
]

const getProgressColor = (p: number) => {
  if (p < 70) return '#20a53a'
  if (p < 90) return '#e6a23c'
  return '#f56c6c'
}

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  const option = {
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true, top: '10%' },
    xAxis: { type: 'category', boundaryGap: false, data: ['10:00', '10:10', '10:20', '10:30', '10:40', '10:50', '11:00'], axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        name: 'Traffic',
        type: 'line',
        smooth: true,
        data: [120, 132, 101, 134, 90, 230, 210],
        lineStyle: { color: '#20a53a', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(32, 165, 58, 0.2)' },
            { offset: 1, color: 'rgba(32, 165, 58, 0)' }
          ])
        },
        symbol: 'none'
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
  gap: 16px;
}

.stat-card {
  border-radius: 4px;
  border: none;
}

.stat-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 13px;
  color: var(--app-text-muted);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text-main);
  margin-bottom: 4px;
}

.stat-desc {
  font-size: 12px;
  color: var(--primary-green);
}

.overview-card {
  border-radius: 4px;
  border: none;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
}

.more-icon {
  color: var(--app-text-muted);
  cursor: pointer;
}

.overview-item {
  padding: 10px 0;
}

.overview-label {
  font-size: 12px;
  color: var(--app-text-muted);
  margin-bottom: 8px;
}

.overview-val-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.overview-value {
  font-size: 18px;
  font-weight: 500;
}

.overview-value.danger {
  color: #f56c6c;
}

.arrow-icon {
  color: #ddd;
  font-size: 14px;
}

.header-left {
  display: flex;
  gap: 20px;
}

.header-left span {
  cursor: pointer;
  color: var(--app-text-muted);
}

.header-left span.active {
  color: var(--primary-green);
  border-bottom: 2px solid var(--primary-green);
  padding-bottom: 2px;
}

.traffic-toolbar {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.up { background: #20a53a; }
.dot.down { background: #e6a23c; }

.main-chart {
  height: 250px;
}

.software-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.software-item {
  text-align: center;
  padding: 10px;
}

.sw-icon-box {
  width: 48px;
  height: 48px;
  background: #f8fafc;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
}

.sw-name {
  font-size: 12px;
  color: var(--app-text-main);
  margin-bottom: 4px;
}

.sw-ver {
  font-size: 11px;
  color: var(--app-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.play-icon {
  color: var(--primary-green);
  font-size: 12px;
}
</style>
