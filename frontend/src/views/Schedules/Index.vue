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
        <el-button @click="openPhoneAlertConfig" class="action-btn">
          Phone Alert Config
        </el-button>
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
                :class="getShiftClass(shift)"
                @click.stop="showShiftDetail(shift)"
              >
                <span class="shift-time-dot"></span>
                <span class="shift-time">{{ formatTime(shift.startTime) }}</span>
                <span class="shift-staff">{{ getStaffNames(shift) }}</span>
              </div>
            </div>
          </div>
        </template>
      </el-calendar>
    </div>

    <el-card v-else shadow="never" class="table-card">
      <el-table :data="schedules" v-loading="loading" style="width: 100%">
        <el-table-column label="Staff Members" min-width="200">
          <template #default="{ row }">
            <div class="staff-info">
              <el-avatar size="small" :icon="UserFilled" />
              <span class="staff-name">{{ getStaffNames(row) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="shiftDate" label="Date" width="150" sortable />
        
        <el-table-column label="Time" width="180">
          <template #default="{ row }">
            {{ row.startTime }} - {{ row.endTime }}
          </template>
        </el-table-column>

        <el-table-column label="Raw Data" min-width="100">
          <template #default="{ row }">
            <el-popover placement="top" :width="300" trigger="hover">
              <template #reference>
                <el-tag size="small" type="info">View JSON</el-tag>
              </template>
              <pre class="json-preview">{{ JSON.stringify(row, null, 2) }}</pre>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="dialogVisible" title="Shift Details" width="450px">
      <div v-if="currentShift" class="shift-detail">
        <div class="detail-row">
          <label>Date:</label>
          <span>{{ currentShift.shiftDate }}</span>
        </div>
        <div class="detail-row">
          <label>Time:</label>
          <span>{{ currentShift.startTime }} - {{ currentShift.endTime }}</span>
        </div>
        <div class="detail-row">
          <label>Staff:</label>
          <span>{{ getStaffNames(currentShift) }}</span>
        </div>
        <div class="detail-divider"></div>
        <div class="detail-json">
          <h4>Raw Data</h4>
          <pre>{{ JSON.stringify(currentShift, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="phoneAlertDialogVisible" title="Phone Alert Config" width="600px">
      <el-form :model="phoneAlertForm" label-position="top" v-loading="phoneAlertLoading">
        <el-form-item label="Public URL (for Slack links)">
          <el-input v-model="phoneAlertForm.public_url" placeholder="https://ubest-ops.test.exc888.org" />
        </el-form-item>
        <el-form-item label="Slack Webhook URL">
          <el-input v-model="phoneAlertForm.slack_webhook_url" placeholder="https://hooks.slack.com/services/..." />
        </el-form-item>
        <el-form-item label="External API URL">
          <el-input v-model="phoneAlertForm.external_api_url" placeholder="https://example.com/api/alert/status" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="External API Username">
              <el-input v-model="phoneAlertForm.external_api_username" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="External API Password">
              <el-input v-model="phoneAlertForm.external_api_password" type="password" show-password placeholder="Leave blank to keep existing" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="Incoming Token (optional, X-Phone-Alert-Token)">
          <el-input v-model="phoneAlertForm.incoming_token" placeholder="Optional shared secret" />
        </el-form-item>
        <el-form-item label="Auto Complete Minutes">
          <el-input-number v-model="phoneAlertForm.auto_complete_minutes" :min="1" :max="240" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="phoneAlertDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="phoneAlertSaving" @click="savePhoneAlert">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { UserFilled, Refresh } from '@element-plus/icons-vue'
import { getSchedules, getPhoneAlertConfig, savePhoneAlertConfig, type BizShiftRespVO, type PhoneAlertConfig } from '@/api/schedules'
import { ElMessage } from 'element-plus'

const schedules = ref<BizShiftRespVO[]>([])
const loading = ref(false)
const viewMode = ref('calendar')
const dialogVisible = ref(false)
const currentShift = ref<BizShiftRespVO | null>(null)

const phoneAlertDialogVisible = ref(false)
const phoneAlertLoading = ref(false)
const phoneAlertSaving = ref(false)
const phoneAlertForm = ref<PhoneAlertConfig>({
  public_url: '',
  slack_webhook_url: '',
  external_api_url: '',
  external_api_username: '',
  external_api_password: '',
  incoming_token: '',
  auto_complete_minutes: 30
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getSchedules()
    if (res.code === 0 && res.data) {
      schedules.value = res.data
    } else {
      schedules.value = []
    }
  } catch (error) {
    console.error(error)
    schedules.value = []
  } finally {
    loading.value = false
  }
}

// Calendar Logic
const getShiftsForDate = (dateStr: string) => {
  return schedules.value.filter(s => s.shiftDate === dateStr)
}

const isToday = (date: Date) => {
  const today = new Date()
  return date.toDateString() === today.toDateString()
}

const formatTime = (timeStr: string) => {
  // Assuming HH:mm:ss, return HH:mm
  return timeStr?.slice(0, 5) || ''
}

const getStaffNames = (shift: BizShiftRespVO) => {
  if (!shift.staffList || shift.staffList.length === 0) return 'No Staff'
  return shift.staffList.map(s => s.name).join(', ')
}

const getShiftClass = (shift: BizShiftRespVO) => {
  // Simple heuristic based on start time
  const hour = parseInt(shift.startTime.split(':')[0])
  if (hour < 12) return 'shift-morning'
  if (hour < 18) return 'shift-afternoon'
  return 'shift-night'
}

const showShiftDetail = (shift: BizShiftRespVO) => {
  currentShift.value = shift
  dialogVisible.value = true
}

onMounted(() => {
  fetchData()
})

const openPhoneAlertConfig = async () => {
  phoneAlertDialogVisible.value = true
  phoneAlertLoading.value = true
  try {
    const cfg = await getPhoneAlertConfig()
    phoneAlertForm.value = {
      public_url: cfg.public_url || '',
      slack_webhook_url: cfg.slack_webhook_url || '',
      external_api_url: cfg.external_api_url || '',
      external_api_username: cfg.external_api_username || '',
      external_api_password: '',
      incoming_token: cfg.incoming_token || '',
      auto_complete_minutes: cfg.auto_complete_minutes || 30,
      has_external_api_password: cfg.has_external_api_password
    }
  } catch (e) {
    console.error(e)
  } finally {
    phoneAlertLoading.value = false
  }
}

const savePhoneAlert = async () => {
  phoneAlertSaving.value = true
  try {
    await savePhoneAlertConfig(phoneAlertForm.value)
    ElMessage.success('Saved')
    phoneAlertDialogVisible.value = false
  } catch (e) {
    console.error(e)
    ElMessage.error('Save failed')
  } finally {
    phoneAlertSaving.value = false
  }
}
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
  background: var(--app-card-bg);
  border-radius: 12px;
  border: 1px solid var(--app-border-color);
  padding: 16px;
  /* Removed min-height to allow fit-content */
  height: auto;
  transition: background-color 0.3s;
}

:deep(.el-calendar) {
  background-color: transparent;
  --el-calendar-bg-color: transparent;
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
