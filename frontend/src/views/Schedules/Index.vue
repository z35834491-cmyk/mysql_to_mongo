<template>
  <div class="schedules-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Schedule Management</h2>
        <p class="page-subtitle">Shift Calendar & Roster</p>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="viewMode" size="small" class="view-switch">
          <el-radio-button label="calendar">Calendar</el-radio-button>
          <el-radio-button label="list">List</el-radio-button>
        </el-radio-group>
        <el-button @click="fetchData" :loading="loading" class="action-btn">
          <el-icon><Refresh /></el-icon> Refresh
        </el-button>
      </div>
    </div>
    
    <div v-if="viewMode === 'calendar'" class="calendar-view">
      <el-calendar ref="calendar" v-loading="loading">
        <template #date-cell="{ data }">
          <div class="calendar-cell">
            <div class="cell-date" :class="{ 'is-today': isToday(data.date) }">
              {{ data.day.split('-').slice(2).join('') }}
            </div>
            <div class="shifts-container">
              <div 
                v-for="shift in getShiftsForDate(data.day)" 
                :key="shift.id"
                class="shift-item"
                :class="getShiftClass(shift.shift_type)"
                @click.stop="showShiftDetail(shift)"
              >
                <span class="shift-time-dot"></span>
                <span class="shift-staff">{{ shift.staff_name }}</span>
              </div>
            </div>
          </div>
        </template>
      </el-calendar>
    </div>

    <el-card v-else shadow="never" class="table-card">
      <el-table :data="schedules" v-loading="loading" style="width: 100%">
        <el-table-column prop="staff_name" label="Staff Name" min-width="150" sortable>
          <template #default="{ row }">
            <div class="staff-info">
              <el-avatar size="small" :icon="UserFilled" />
              <span class="staff-name">{{ row.staff_name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="shift_date" label="Date" width="150" sortable />
        
        <el-table-column prop="shift_type" label="Shift" width="150">
          <template #default="{ row }">
            <el-tag :type="getShiftTagType(row.shift_type)" effect="light">
              {{ row.shift_type }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="extra_info" label="Original Data (JSON)" min-width="200">
          <template #default="{ row }">
            <el-popover placement="top" :width="300" trigger="hover">
              <template #reference>
                <el-tag size="small" type="info">View JSON</el-tag>
              </template>
              <pre class="json-preview">{{ JSON.stringify(row.extra_info, null, 2) }}</pre>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="dialogVisible" title="Shift Details" width="400px">
      <div v-if="currentShift" class="shift-detail">
        <div class="detail-row">
          <label>Staff:</label>
          <span>{{ currentShift.staff_name }}</span>
        </div>
        <div class="detail-row">
          <label>Date:</label>
          <span>{{ currentShift.shift_date }}</span>
        </div>
        <div class="detail-row">
          <label>Shift:</label>
          <el-tag :type="getShiftTagType(currentShift.shift_type)">{{ currentShift.shift_type }}</el-tag>
        </div>
        <div class="detail-divider"></div>
        <div class="detail-json">
          <h4>Raw Data</h4>
          <pre>{{ JSON.stringify(currentShift.extra_info, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { UserFilled, Refresh } from '@element-plus/icons-vue'
import { getSchedules, type Schedule } from '@/api/schedules'

const schedules = ref<Schedule[]>([])
const loading = ref(false)
const viewMode = ref('calendar')
const dialogVisible = ref(false)
const currentShift = ref<Schedule | null>(null)

const fetchData = async () => {
  loading.value = true
  try {
    const data = await getSchedules()
    schedules.value = data
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Calendar Logic
const getShiftsForDate = (dateStr: string) => {
  return schedules.value.filter(s => s.shift_date === dateStr)
}

const isToday = (date: Date) => {
  const today = new Date()
  return date.toDateString() === today.toDateString()
}

const getShiftClass = (type: string) => {
  const t = (type || '').toLowerCase()
  if (t.includes('morning')) return 'shift-morning'
  if (t.includes('afternoon')) return 'shift-afternoon'
  if (t.includes('night')) return 'shift-night'
  return 'shift-default'
}

const showShiftDetail = (shift: Schedule) => {
  currentShift.value = shift
  dialogVisible.value = true
}

// Table Logic
const getShiftTagType = (type: string) => {
  const t = (type || '').toLowerCase()
  if (t.includes('morning')) return 'warning'
  if (t.includes('night')) return 'info'
  if (t.includes('afternoon')) return 'success'
  return ''
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.schedules-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
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

.header-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}

/* Calendar Styles */
.calendar-view {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f1f5f9;
  padding: 16px;
  min-height: 600px;
}

:deep(.el-calendar-table .el-calendar-day) {
  height: 120px;
  padding: 8px;
  transition: background-color 0.2s;
}

:deep(.el-calendar-table .el-calendar-day:hover) {
  background-color: #f8fafc;
}

.calendar-cell {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cell-date {
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.cell-date.is-today {
  background-color: #3b82f6;
  color: #fff;
}

.shifts-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.shift-item {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #334155;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 3px solid transparent;
  transition: transform 0.1s;
}

.shift-item:hover {
  transform: translateX(2px);
  filter: brightness(0.95);
}

.shift-time-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

/* Shift Colors */
.shift-morning {
  background: #fff7ed;
  color: #c2410c;
  border-left-color: #f97316;
}
.shift-morning .shift-time-dot { background: #f97316; }

.shift-afternoon {
  background: #f0fdf4;
  color: #15803d;
  border-left-color: #22c55e;
}
.shift-afternoon .shift-time-dot { background: #22c55e; }

.shift-night {
  background: #eff6ff;
  color: #1d4ed8;
  border-left-color: #3b82f6;
}
.shift-night .shift-time-dot { background: #3b82f6; }

.shift-default {
  background: #f8fafc;
  border-left-color: #94a3b8;
}

.staff-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.json-preview {
  font-family: monospace;
  font-size: 11px;
  max-height: 200px;
  overflow: auto;
}

/* Detail Dialog */
.shift-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-row label {
  font-weight: 600;
  width: 60px;
  color: #64748b;
}

.detail-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 8px 0;
}

.detail-json h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #475569;
}

.detail-json pre {
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  font-size: 11px;
  max-height: 200px;
  overflow: auto;
  border: 1px solid #e2e8f0;
}
</style>
