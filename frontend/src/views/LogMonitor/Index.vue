<template>
  <div class="monitor-container">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">Log Monitor</h2>
        <p class="page-subtitle">K8s Log Monitoring & Local Logs</p>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="viewMode" size="small" style="margin-right: 12px">
          <el-radio-button label="k8s">Monitor Tasks (K8s)</el-radio-button>
          <el-radio-button label="local">Local Log Files</el-radio-button>
        </el-radio-group>
        <el-button v-if="viewMode === 'k8s'" type="primary" :icon="Plus" @click="createNewTask">New Task</el-button>
        <el-button @click="handleRefresh" :icon="Refresh" circle />
      </div>
    </div>

    <!-- Mode: K8s Monitor Tasks -->
    <el-card shadow="never" class="main-card" v-if="viewMode === 'k8s'">
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

                  <el-divider>Archiving & Retention</el-divider>

                  <el-row :gutter="20">
                    <el-col :span="6">
                      <el-form-item label="Retention Days">
                         <el-input-number v-model="form.retention_days" :min="1" :max="365" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item label="Enable S3 Archive">
                         <el-switch v-model="form.s3_archive_enabled" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
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

            <!-- Tab 2: Saved Logs (Archived) -->
            <el-tab-pane label="Log Files" name="saved">
              <div class="saved-container">
                <!-- File List -->
                <div class="saved-file-list">
                  <div class="list-header">
                    <span>Task Logs</span>
                    <el-select v-model="savedFilePageSize" size="small" style="width: 70px" @change="fetchSavedLogs(1)">
                      <el-option :value="10" label="10" />
                      <el-option :value="20" label="20" />
                      <el-option :value="50" label="50" />
                    </el-select>
                  </div>
                  <div v-loading="savedLoading" class="list-content">
                    <div 
                      v-for="file in savedLogFiles" 
                      :key="file.name"
                      class="file-item"
                      :class="{ active: savedLogFile === file.name }"
                      @click="selectSavedFile(file.name)"
                    >
                      <div class="file-icon"><el-icon><Document /></el-icon></div>
                      <div class="file-info">
                        <div class="file-name" :title="file.name">{{ file.name }}</div>
                        <div class="file-meta">{{ (file.size / 1024 / 1024).toFixed(2) }} MB • {{ new Date(file.mtime * 1000).toLocaleString() }}</div>
                      </div>
                    </div>
                    <div v-if="savedLogFiles.length === 0" class="empty-list">No saved logs</div>
                  </div>
                  <div class="list-pagination">
                     <el-pagination 
                       small 
                       layout="prev, next" 
                       :total="savedFileTotal" 
                       :page-size="savedFilePageSize"
                       v-model:current-page="savedFilePage"
                       @current-change="fetchSavedLogs"
                     />
                  </div>
                </div>

                <!-- Log Viewer -->
                <div class="saved-log-viewer" v-loading="savedContentLoading">
                  <div class="viewer-header">
                    <div class="header-left">
                      <span v-if="savedLogFile">{{ savedLogFile }}</span>
                      <span v-else>Select a log file</span>
                    </div>
                    <div class="header-right" v-if="savedLogFile">
                       <el-select v-model="savedLogPageSize" size="small" style="width: 100px; margin-right: 8px" @change="fetchSavedLogContent(1)">
                        <el-option :value="500" label="500 lines" />
                        <el-option :value="1000" label="1k lines" />
                        <el-option :value="5000" label="5k lines" />
                      </el-select>
                      <el-pagination 
                         small
                         layout="prev, pager, next"
                         :total="savedLogTotal"
                         :page-size="savedLogPageSize"
                         v-model:current-page="savedLogPage"
                         @current-change="fetchSavedLogContent"
                         style="display: inline-flex; margin-right: 12px"
                      />
                      <el-button size="small" :icon="Download" circle @click="downloadSavedFile" title="Download" />
                      <el-button size="small" :icon="Refresh" circle @click="fetchSavedLogContent(savedLogPage)" />
                    </div>
                    <div class="header-right" v-else>
                       <el-input 
                          v-model="savedSearchQuery" 
                          placeholder="Search in current file..." 
                          size="small" 
                          style="width: 200px"
                          @keyup.enter="handleSavedSearch"
                       >
                          <template #append><el-button :icon="Search" @click="handleSavedSearch"/></template>
                       </el-input>
                    </div>
                  </div>

                  <div class="log-lines" v-if="savedLogFile">
                    <pre class="log-raw">{{ savedLogContent }}</pre>
                  </div>
                  <div v-else class="empty-viewer">
                    <el-empty description="Select a saved log file to view" />
                  </div>
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

    <!-- Mode: Local Log Explorer -->
    <el-card shadow="never" class="main-card" v-else>
      <div class="main-body">
        <!-- File List (Left) -->
        <div class="file-list">
          <div class="list-header">
            <span>Local Files</span>
            <el-select v-model="filePageSize" size="small" style="width: 70px" @change="fetchLocalFiles(1)">
              <el-option :value="10" label="10" />
              <el-option :value="20" label="20" />
              <el-option :value="50" label="50" />
            </el-select>
          </div>
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
          <div class="list-pagination">
             <el-pagination 
               small 
               layout="prev, next" 
               :total="fileTotal" 
               :page-size="filePageSize"
               v-model:current-page="filePage"
               @current-change="fetchLocalFiles"
             />
          </div>
        </div>

        <!-- Log Content (Right) -->
        <div class="log-viewer" v-loading="contentLoading">
          <div class="viewer-header">
            <div class="header-left">
              <span v-if="selectedFile">{{ selectedFile }}</span>
              <span v-else>No File Selected</span>
            </div>
            <div class="header-right" v-if="selectedFile">
               <el-select v-model="logPageSize" size="small" style="width: 90px; margin-right: 8px" @change="fetchLogContent(1)">
                <el-option :value="500" label="500 lines" />
                <el-option :value="1000" label="1k lines" />
                <el-option :value="5000" label="5k lines" />
              </el-select>
              <el-pagination 
                 small
                 layout="prev, pager, next"
                 :total="logTotal"
                 :page-size="logPageSize"
                 v-model:current-page="logPage"
                 @current-change="fetchLogContent"
                 style="display: inline-flex; margin-right: 12px"
              />
              <el-button size="small" :icon="Download" circle @click="downloadFile" title="Download" />
              <el-button size="small" :icon="Refresh" circle @click="fetchLogContent(logPage)" />
            </div>
            <div class="header-right" v-else>
               <el-input 
                  v-model="globalSearchQuery" 
                  placeholder="Global Search..." 
                  size="small" 
                  style="width: 200px"
                  @keyup.enter="handleGlobalSearch"
               >
                  <template #append><el-button :icon="Search" @click="handleGlobalSearch"/></template>
               </el-input>
            </div>
          </div>

          <div class="log-lines" v-if="selectedFile">
            <div v-for="(line, i) in logContent" :key="i" class="log-line">{{ line }}</div>
          </div>
          
          <div class="search-results" v-else-if="searchResults.length > 0">
             <div class="results-header">Found {{ searchResults.length }} matches</div>
             <div class="results-list">
              <div v-for="(match, idx) in searchResults" :key="idx" class="result-item" @click="jumpToLog(match.file)">
                <div class="result-meta">
                  <span class="res-file">{{ match.file }}</span>
                  <span class="res-line">L{{ match.line }}</span>
                </div>
                <div class="result-content">{{ match.content }}</div>
              </div>
            </div>
          </div>

          <div v-else class="empty-viewer">
            <el-empty description="Select a file or use Global Search" />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { monitorApi, type MonitorTask } from '@/api/monitor'
import { taskApi } from '@/api/task'
import { Refresh, Plus, VideoPlay, VideoPause, Document, Search, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const viewMode = ref('k8s') // 'k8s' | 'local'

// --- K8s Mode State ---
const tasks = ref<MonitorTask[]>([])
const selectedTaskId = ref<number | null>(null)
const selectedTask = ref<MonitorTask | null>(null)
const activeTab = ref('config')
const form = ref<Partial<MonitorTask>>({})
const k8sPods = ref<any[]>([])
const selectedPod = ref('')
const k8sLogContent = ref('')
const logLoading = ref(false)

// --- Saved Logs State ---
const savedLoading = ref(false)
const savedContentLoading = ref(false)
const savedLogFiles = ref<any[]>([])
const savedLogFile = ref('')
const savedLogContent = ref('')
const savedFilePage = ref(1)
const savedFilePageSize = ref(10)
const savedFileTotal = ref(0)
const savedLogPage = ref(1)
const savedLogPageSize = ref(1000)
const savedLogTotal = ref(0)
const savedSearchQuery = ref('')

const keywordsStr = computed({
  get: () => form.value.alert_keywords?.join('\n') || '',
  set: (val) => {
    form.value.alert_keywords = val.split('\n').filter(k => k.trim())
  }
})

// --- Local Mode State ---
const logFiles = ref<any[]>([])
const selectedFile = ref('')
const logContent = ref<string[]>([])
const filePage = ref(1)
const filePageSize = ref(10)
const fileTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(1000)
const logTotal = ref(0)
const contentLoading = ref(false)
const globalSearchQuery = ref('')
const searchResults = ref<any[]>([])

// --- Actions ---

const handleRefresh = () => {
  if (viewMode.value === 'k8s') fetchTasks()
  else fetchLocalFiles(1)
}

// Monitor Tasks
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
  selectedTask.value = { ...task }
  form.value = { ...task }
  activeTab.value = 'config'
  if (task.k8s_namespace) fetchPods()
}

const createNewTask = () => {
  selectedTaskId.value = null
  selectedTask.value = { 
    name: 'New Monitor Task', 
    enabled: true,
    k8s_namespace: 'default',
    alert_keywords: ['ERROR'],
    s3_archive_enabled: false,
    retention_days: 7
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
  } catch (e) {}
}

const fetchPods = async () => {
  const ns = form.value.k8s_namespace || 'default'
  try {
    const res = await taskApi.getK8sPods(ns)
    k8sPods.value = res.pods || []
  } catch (e) { console.error(e) }
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

// Saved Logs Actions
const fetchSavedLogs = async (page = 1) => {
  if (!selectedTaskId.value) return
  savedFilePage.value = page
  savedLoading.value = true
  try {
    const res = await monitorApi.getLogs(selectedTaskId.value, { page, page_size: savedFilePageSize.value })
    savedLogFiles.value = res.files
    savedFileTotal.value = res.total
  } catch (e) {
    savedLogFiles.value = []
    savedFileTotal.value = 0
  } finally {
    savedLoading.value = false
  }
}

const selectSavedFile = (name: string) => {
  savedLogFile.value = name
  savedLogContent.value = ''
  fetchSavedLogContent(1)
}

const fetchSavedLogContent = async (page = 1) => {
  if (!selectedTaskId.value || !savedLogFile.value) return
  savedLogPage.value = page
  savedContentLoading.value = true
  try {
    const res = await monitorApi.viewLog(selectedTaskId.value, savedLogFile.value, { page, page_size: savedLogPageSize.value })
    savedLogContent.value = res.content
    savedLogTotal.value = res.total
  } catch (e) {
    savedLogContent.value = `Error loading file: ${e}`
  } finally {
    savedContentLoading.value = false
  }
}

const downloadSavedFile = () => {
  if (!selectedTaskId.value || !savedLogFile.value) return
  window.open(monitorApi.downloadLog(selectedTaskId.value, savedLogFile.value), '_blank')
}

const handleSavedSearch = async () => {
  if (!selectedTaskId.value || !savedLogFile.value || !savedSearchQuery.value) return
  savedContentLoading.value = true
  try {
    const res = await monitorApi.viewLog(selectedTaskId.value, savedLogFile.value, { keyword: savedSearchQuery.value })
    savedLogContent.value = res.content
  } catch (e) {
    savedLogContent.value = `Search failed: ${e}`
  } finally {
    savedContentLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'saved' && selectedTaskId.value) {
    fetchSavedLogs(1)
  }
})

// Local Logs
const fetchLocalFiles = async (page = 1) => {
  filePage.value = page
  loading.value = true
  try {
    const res = await taskApi.getLogFiles({ page, page_size: filePageSize.value })
    logFiles.value = res.files
    fileTotal.value = res.total
  } finally {
    loading.value = false
  }
}

const selectFile = (name: string) => {
  selectedFile.value = name
  searchResults.value = []
  fetchLogContent(1)
}

const fetchLogContent = async (page = 1) => {
  if (!selectedFile.value) return
  logPage.value = page
  contentLoading.value = true
  try {
    const taskId = selectedFile.value.replace('.log', '')
    const res = await taskApi.getTaskLogs(taskId, { page, page_size: logPageSize.value })
    logContent.value = res.lines
    logTotal.value = res.total // Ensure backend returns total lines
  } finally {
    contentLoading.value = false
  }
}

const downloadFile = () => {
  if (!selectedFile.value) return
  window.open(taskApi.downloadLog(selectedFile.value), '_blank')
}

const handleGlobalSearch = async () => {
  if (!globalSearchQuery.value) return
  contentLoading.value = true
  selectedFile.value = ''
  try {
    const res = await taskApi.searchLogs(globalSearchQuery.value)
    searchResults.value = res
  } finally {
    contentLoading.value = false
  }
}

const jumpToLog = (filename: string) => {
  selectFile(filename)
}

watch(viewMode, (val) => {
  if (val === 'k8s') fetchTasks()
  else fetchLocalFiles(1)
})

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

/* Task List / File List */
.task-list, .file-list {
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 50px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
}

.list-pagination {
  padding: 8px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: center;
}

.task-item, .file-item {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  gap: 12px;
  border-bottom: 1px solid #f1f5f9;
  transition: all 0.2s;
  align-items: center;
}

.task-item:hover, .file-item:hover { background: #fff; }
.task-item.active, .file-item.active { background: #fff; border-left: 3px solid #3b82f6; }

.task-info, .file-info { flex: 1; overflow: hidden; }
.task-name, .file-name { font-weight: 500; color: #334155; margin-bottom: 2px; font-size: 13px; }
.task-meta, .file-meta { font-size: 11px; color: #94a3b8; }
.empty-list { padding: 20px; text-align: center; color: #94a3b8; font-size: 13px; }

/* Detail / Viewer */
.task-detail, .log-viewer {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}

.detail-tabs { height: 100%; display: flex; flex-direction: column; }
.detail-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 20px; border-bottom: 1px solid #e2e8f0; }
.detail-tabs :deep(.el-tabs__content) { flex: 1; overflow-y: auto; padding: 20px; }

.config-form { max-width: 800px; }
.form-actions { margin-top: 30px; display: flex; gap: 12px; }

/* Log Viewer Specific */
.log-viewer { background: #1e293b; }
.viewer-header {
  padding: 8px 16px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #334155;
  height: 50px;
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
.log-line { white-space: pre-wrap; word-break: break-all; }

.search-results { flex: 1; overflow-y: auto; background: #fff; }
.results-header { padding: 12px 16px; background: #f1f5f9; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #475569; }
.result-item { padding: 12px 16px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
.result-item:hover { background: #f8fafc; }
.result-meta { display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-bottom: 4px; }
.res-file { font-weight: 600; color: #3b82f6; }
.result-content { font-family: monospace; font-size: 12px; color: #334155; white-space: pre-wrap; }

.empty-detail, .empty-viewer { flex: 1; display: flex; align-items: center; justify-content: center; background: #f8fafc; }

/* Live Logs */
.live-container { display: flex; flex-direction: column; height: 100%; }
.live-controls { display: flex; gap: 12px; margin-bottom: 16px; }
.log-raw { margin: 0; white-space: pre-wrap; word-break: break-all; font-family: 'Menlo', monospace; font-size: 12px; line-height: 1.5; color: #e2e8f0; }
</style>
