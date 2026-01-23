<template>
  <div class="monitor-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Log Monitoring</h2>
        <p class="page-subtitle">Centralized log aggregation and alert configuration for K8s clusters</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="custom-tabs">
      <el-tab-pane name="files">
        <template #label>
          <div class="tab-label">
            <el-icon><Files /></el-icon>
            <span>Log Files</span>
          </div>
        </template>
        
        <el-card shadow="never" class="content-card">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-select 
                v-model="selectedTaskId" 
                placeholder="Select Monitor Task" 
                @change="refreshLogs" 
                class="task-select"
              >
                <el-option v-for="task in monitorTasks" :key="task.id" :label="task.name" :value="task.id" />
              </el-select>
              <el-button :icon="Refresh" @click="refreshLogs">Refresh List</el-button>
            </div>
          </div>

          <el-table :data="logFiles" v-loading="loading" style="width: 100%">
            <el-table-column label="Log File Name" min-width="400">
              <template #default="{ row }">
                <div class="log-file-cell">
                  <el-icon class="file-icon"><Document /></el-icon>
                  <span class="file-name">{{ typeof row === 'string' ? row : row.name }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column label="Actions" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" plain size="small" :icon="Download" @click="downloadLog(row)">
                  Download
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane name="config">
        <template #label>
          <div class="tab-label">
            <el-icon><Setting /></el-icon>
            <span>Configuration</span>
          </div>
        </template>

        <el-card shadow="never" class="content-card">
          <div class="toolbar">
            <div class="toolbar-right">
              <el-button type="primary" :icon="Plus" @click="showAddTask" class="shadow-btn">
                Add Monitor Task
              </el-button>
            </div>
          </div>

          <el-table :data="monitorTasks" v-loading="loading" style="width: 100%">
            <el-table-column prop="name" label="Task Name" min-width="180">
              <template #default="{ row }">
                <div class="task-name-cell">
                  <el-icon class="task-icon"><Monitor /></el-icon>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column prop="k8s_namespace" label="K8s Namespace" width="180">
              <template #default="{ row }">
                <el-tag size="small" plain>{{ row.k8s_namespace }}</el-tag>
              </template>
            </el-table-column>

            <el-table-column label="Status" width="120">
              <template #default="{ row }">
                <div class="status-wrapper">
                  <span :class="['status-dot', row.enabled ? 'enabled' : 'disabled']"></span>
                  <el-tag :type="row.enabled ? 'success' : 'info'" size="small" effect="light">
                    {{ row.enabled ? 'ENABLED' : 'DISABLED' }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="Actions" width="220" fixed="right">
              <template #default="{ row }">
                <div class="action-group">
                  <el-button size="small" @click="editTask(row)" plain>
                    <el-icon><Edit /></el-icon> Edit
                  </el-button>
                  <el-button size="small" type="danger" text @click="deleteTask(row.id)">
                    Delete
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Task Dialog -->
    <el-dialog 
      v-model="taskDialogVisible" 
      :title="editMode ? 'Edit Monitor Task' : 'New Monitor Task'" 
      width="640px"
      class="custom-dialog"
    >
      <el-form :model="taskForm" label-width="140px" label-position="top" class="monitor-form">
        <div class="form-section">
          <h3 class="section-title">Source Configuration</h3>
          <el-row :gutter="20">
            <el-col :span="14">
              <el-form-item label="Task Display Name" required>
                <el-input v-model="taskForm.name" placeholder="e.g. Payment Service Logs" />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="K8s Namespace" required>
                <el-input v-model="taskForm.k8s_namespace" placeholder="default" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="Monitoring Status">
            <el-switch v-model="taskForm.enabled" active-text="Active Monitoring Enabled" />
          </el-form-item>
        </div>

        <div class="form-section">
          <h3 class="section-title">Alerting & Keywords</h3>
          <el-form-item label="Slack Webhook URL">
            <el-input v-model="taskForm.slack_webhook_url" placeholder="https://hooks.slack.com/services/..." />
          </el-form-item>
          <el-form-item label="Critical Keywords (Auto-Alert)">
            <el-select 
              v-model="taskForm.alert_keywords" 
              multiple 
              filterable 
              allow-create 
              default-first-option 
              placeholder="e.g. ERROR, CRITICAL, Timeout"
              class="w-full"
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <div class="section-header-row">
            <h3 class="section-title">Cloud Archive (S3)</h3>
            <el-switch v-model="taskForm.s3_archive_enabled" />
          </div>
          
          <template v-if="taskForm.s3_archive_enabled">
            <el-form-item label="S3 Endpoint">
              <el-input v-model="taskForm.s3_endpoint" placeholder="s3.amazonaws.com" />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="Bucket Name">
                  <el-input v-model="taskForm.s3_bucket" placeholder="my-log-archive" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="S3 Region">
                  <el-input v-model="taskForm.s3_region" placeholder="us-east-1" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="Access Key ID">
                  <el-input v-model="taskForm.s3_access_key" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Secret Access Key">
                  <el-input v-model="taskForm.s3_secret_key" type="password" show-password />
                </el-form-item>
              </el-col>
            </el-row>
          </template>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="taskDialogVisible = false">Cancel</el-button>
          <el-button type="primary" @click="saveTask" class="shadow-btn">Save Monitor Task</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useSystemStore } from '@/stores/system'
import { 
  Document, Files, Setting, Refresh, 
  Download, Plus, Monitor, Edit, 
  Delete 
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const activeTab = ref('files')
const selectedTaskId = ref<number | null>(null)
const systemStore = useSystemStore()

const logFiles = computed(() => systemStore.monitorLogs)
const monitorTasks = computed(() => systemStore.monitorTasks)
const loading = computed(() => systemStore.loading)

const taskDialogVisible = ref(false)
const editMode = ref(false)
const taskForm = reactive({
  id: null,
  name: '',
  enabled: true,
  k8s_namespace: 'default',
  slack_webhook_url: '',
  alert_keywords: [],
  s3_archive_enabled: false,
  s3_endpoint: '',
  s3_bucket: '',
  s3_access_key: '',
  s3_secret_key: '',
  s3_region: ''
})

onMounted(async () => {
  await systemStore.fetchMonitorTasks()
  if (monitorTasks.value.length > 0) {
    selectedTaskId.value = monitorTasks.value[0].id
    systemStore.fetchMonitorLogs(String(selectedTaskId.value))
  }
})

const refreshLogs = () => {
  if (selectedTaskId.value) {
    systemStore.fetchMonitorLogs(String(selectedTaskId.value))
  }
}

const showAddTask = () => {
  editMode.value = false
  Object.assign(taskForm, {
    id: null,
    name: '',
    enabled: true,
    k8s_namespace: 'default',
    slack_webhook_url: '',
    alert_keywords: [],
    s3_archive_enabled: false,
    s3_endpoint: '',
    s3_bucket: '',
    s3_access_key: '',
    s3_secret_key: '',
    s3_region: ''
  })
  taskDialogVisible.value = true
}

const editTask = (task: any) => {
  editMode.value = true
  Object.assign(taskForm, task)
  taskDialogVisible.value = true
}

const saveTask = async () => {
  await systemStore.saveMonitorTask({ ...taskForm })
  taskDialogVisible.value = false
}

const deleteTask = (id: number) => {
  ElMessageBox.confirm('Are you sure you want to permanently remove this monitor task?', 'Delete Task', {
    confirmButtonText: 'Remove',
    cancelButtonText: 'Cancel',
    type: 'error'
  }).then(() => {
    systemStore.deleteMonitorTask(id)
  })
}

const downloadLog = (filename: any) => {
  const name = typeof filename === 'string' ? filename : filename.name
  if (!selectedTaskId.value) return
  window.open(`/api/monitor/logs/download?filename=${name}&task_id=${selectedTaskId.value}`, '_blank')
}
</script>

<style scoped>
.monitor-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  margin-bottom: 8px;
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

.custom-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
}

.content-card {
  border: 1px solid #f1f5f9 !important;
  border-radius: 12px !important;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.task-select {
  width: 240px;
}

.log-file-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-icon {
  font-size: 18px;
  color: #64748b;
}

.file-name {
  font-family: ui-monospace, monospace;
  font-size: 13px;
  color: #334155;
}

.task-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #1e293b;
}

.task-icon {
  color: #3b82f6;
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

.status-dot.enabled { background: #10b981; box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1); }
.status-dot.disabled { background: #94a3b8; }

.action-group {
  display: flex;
  align-items: center;
  gap: 12px;
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

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-header-row .section-title {
  margin-bottom: 0;
}

.shadow-btn {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.w-full { width: 100%; }

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #475569;
  font-size: 13px;
  padding-bottom: 4px !important;
}

:deep(.el-input__inner) {
  font-family: ui-monospace, monospace;
}
</style>
