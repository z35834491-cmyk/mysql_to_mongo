<template>
  <div class="monitor-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Log Monitor</h2>
        <p class="page-subtitle">K8s Log Monitoring & Alerting</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="createNewTask">New Monitor Task</el-button>
        <el-button @click="fetchTasks" :icon="Refresh" circle />
      </div>
    </div>

    <el-card shadow="never" class="main-card">
      <div class="main-body">
        <!-- Task List (Left) -->
        <div class="task-list">
          <div class="list-header">Monitor Tasks</div>
          <div v-loading="loading" class="list-content">
            <div 
              v-for="task in tasks" 
              :key="task.id"
              class="task-item"
              :class="{ active: selectedTaskId === task.id }"
              @click="selectTask(task)"
            >
              <div class="task-icon">
                <el-icon v-if="task.enabled" color="#10b981"><VideoPlay /></el-icon>
                <el-icon v-else color="#94a3b8"><VideoPause /></el-icon>
              </div>
              <div class="task-info">
                <div class="task-name">{{ task.name }}</div>
                <div class="task-meta">{{ task.k8s_namespace }} • {{ task.alert_keywords?.length || 0 }} Keywords</div>
              </div>
            </div>
            <div v-if="tasks.length === 0" class="empty-list">
              No tasks found
            </div>
          </div>
        </div>

        <!-- Task Detail (Right) -->
        <div class="task-detail" v-if="selectedTask">
          <el-tabs v-model="activeTab" class="detail-tabs">
            
            <!-- Tab 1: Configuration -->
            <el-tab-pane label="Configuration" name="config">
              <div class="config-form">
                <el-form :model="form" label-position="top">
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="Task Name">
                        <el-input v-model="form.name" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="K8s Namespace">
                        <el-input v-model="form.k8s_namespace" placeholder="default" />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <el-form-item label="Kubeconfig (YAML)">
                    <el-input v-model="form.k8s_kubeconfig" type="textarea" :rows="4" placeholder="Leave empty to use in-cluster config" />
                  </el-form-item>

                  <el-divider>Alerting</el-divider>
                  
                  <el-form-item label="Alert Keywords (One per line)">
                    <el-input v-model="keywordsStr" type="textarea" :rows="3" placeholder="ERROR&#10;Exception&#10;Critical" />
                  </el-form-item>

                  <el-form-item label="Slack Webhook URL">
                    <el-input v-model="form.slack_webhook_url" placeholder="https://hooks.slack.com/services/..." />
                  </el-form-item>

                  <el-divider>Archiving (S3)</el-divider>

                  <el-row :gutter="20">
                    <el-col :span="6">
                      <el-form-item label="Enable Archive">
                         <el-switch v-model="form.s3_archive_enabled" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="18">
                      <el-form-item label="S3 Bucket">
                        <el-input v-model="form.s3_bucket" :disabled="!form.s3_archive_enabled" />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <div class="form-actions">
                    <el-button type="primary" @click="saveTask">Save Changes</el-button>
                    <el-button type="danger" plain @click="deleteTask">Delete Task</el-button>
                  </div>
                </el-form>
              </div>
            </el-tab-pane>

            <!-- Tab 2: Live Logs -->
            <el-tab-pane label="Live Logs" name="live">
              <div class="live-container">
                <div class="live-controls">
                  <el-select v-model="selectedPod" placeholder="Select Pod" style="width: 300px" @change="fetchK8sLogs">
                    <el-option v-for="pod in k8sPods" :key="pod.name" :label="pod.name" :value="pod.name">
                      <span style="float: left">{{ pod.name }}</span>
                      <span style="float: right; color: #8492a6; font-size: 12px">{{ pod.status }}</span>
                    </el-option>
                  </el-select>
                  <el-button :icon="Refresh" @click="fetchPods">Refresh Pods</el-button>
                  <el-button type="primary" :icon="VideoPlay" @click="fetchK8sLogs">Tail Logs</el-button>
                </div>
                <div class="log-viewer" v-loading="logLoading">
                  <pre class="log-raw">{{ k8sLogContent || 'Select a pod to start streaming logs...' }}</pre>
                </div>
              </div>
            </el-tab-pane>

          </el-tabs>
        </div>

        <div class="empty-detail" v-else>
          <el-empty description="Select a task or create a new one" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { monitorApi, type MonitorTask } from '@/api/monitor'
import { taskApi } from '@/api/task' // Reuse K8s API
import { Refresh, Plus, VideoPlay, VideoPause, Delete, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tasks = ref<MonitorTask[]>([])
const selectedTaskId = ref<number | null>(null)
const selectedTask = ref<MonitorTask | null>(null)
const activeTab = ref('config')

// Form State
const form = ref<Partial<MonitorTask>>({})
const keywordsStr = computed({
  get: () => form.value.alert_keywords?.join('\n') || '',
  set: (val) => {
    form.value.alert_keywords = val.split('\n').filter(k => k.trim())
  }
})

// Live Logs State
const k8sPods = ref<any[]>([])
const selectedPod = ref('')
const k8sLogContent = ref('')
const logLoading = ref(false)

const fetchTasks = async () => {
  loading.value = true
  try {
    tasks.value = await monitorApi.getTasks()
  } finally {
    loading.value = false
  }
}

const selectTask = (task: MonitorTask) => {
  selectedTaskId.value = task.id!
  selectedTask.value = { ...task } // Clone
  form.value = { ...task } // Clone to form
  activeTab.value = 'config'
  
  // Pre-load pods if K8s info is present
  if (task.k8s_namespace) {
    fetchPods()
  }
}

const createNewTask = () => {
  selectedTaskId.value = null
  selectedTask.value = { 
    name: 'New Monitor Task', 
    enabled: true,
    k8s_namespace: 'default',
    alert_keywords: ['ERROR'],
    s3_archive_enabled: false
  } as any
  form.value = { ...selectedTask.value }
  activeTab.value = 'config'
}

const saveTask = async () => {
  try {
    if (selectedTaskId.value) {
      await monitorApi.updateTask(selectedTaskId.value, form.value)
      ElMessage.success('Task updated')
    } else {
      await monitorApi.createTask(form.value)
      ElMessage.success('Task created')
    }
    fetchTasks()
  } catch (e) {
    ElMessage.error('Failed to save task')
  }
}

const deleteTask = async () => {
  if (!selectedTaskId.value) return
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this task?', 'Warning', { type: 'warning' })
    await monitorApi.deleteTask(selectedTaskId.value)
    ElMessage.success('Task deleted')
    selectedTaskId.value = null
    selectedTask.value = null
    fetchTasks()
  } catch (e) {
    // Cancelled
  }
}

// Live Logs Logic
const fetchPods = async () => {
  const ns = form.value.k8s_namespace || 'default'
  try {
    // Note: This relies on backend using the kubeconfig from the DB or fallback
    // Since we haven't saved the form yet, this might use old config if we use backend's "getPods".
    // Ideal: backend getPods should accept kubeconfig override, OR we save first.
    // For now, let's assume user saves config first.
    const res = await taskApi.getK8sPods(ns)
    k8sPods.value = res.pods || []
  } catch (e) {
    console.error(e)
  }
}

const fetchK8sLogs = async () => {
  if (!selectedPod.value) return
  logLoading.value = true
  try {
    const logs = await taskApi.getK8sLogs({
      namespace: form.value.k8s_namespace || 'default',
      pod_name: selectedPod.value,
      tail_lines: 100
    })
    k8sLogContent.value = logs
  } catch (e) {
    k8sLogContent.value = `Error: ${e}`
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  fetchTasks()
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
}

.main-body {
  display: flex;
  width: 100%;
  height: 100%;
}

/* Task List */
.task-list {
  width: 280px;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.list-header {
  padding: 16px;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
}

.list-content {
  flex: 1;
  overflow-y: auto;
}

.task-item {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  gap: 12px;
  border-bottom: 1px solid #f1f5f9;
  transition: all 0.2s;
  align-items: center;
}

.task-item:hover { background: #fff; }
.task-item.active { background: #fff; border-left: 3px solid #3b82f6; }

.task-info { flex: 1; overflow: hidden; }
.task-name { font-weight: 500; color: #334155; margin-bottom: 2px; }
.task-meta { font-size: 11px; color: #94a3b8; }
.empty-list { padding: 20px; text-align: center; color: #94a3b8; font-size: 13px; }

/* Detail */
.task-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}

.detail-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 20px; border-bottom: 1px solid #e2e8f0; }
.detail-tabs :deep(.el-tabs__content) { flex: 1; overflow-y: auto; padding: 20px; }

.config-form { max-width: 800px; }
.form-actions { margin-top: 30px; display: flex; gap: 12px; }

/* Live Logs */
.live-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.live-controls {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.log-viewer {
  flex: 1;
  background: #1e293b;
  border-radius: 6px;
  padding: 16px;
  overflow-y: auto;
}

.log-raw {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #e2e8f0;
}

.empty-detail {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}
</style>
