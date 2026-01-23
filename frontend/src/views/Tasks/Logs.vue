<template>
  <div class="task-logs-container">
    <el-page-header @back="goBack" :content="`Logs: ${taskId}`" class="page-header">
      <template #extra>
        <el-button type="primary" link @click="fetchLogs">Refresh</el-button>
        <el-button type="primary" @click="handleDownload">Download Logs</el-button>
      </template>
    </el-page-header>
    
    <div class="logs-wrapper" ref="logsContainer">
      <div v-if="loading && logs.length === 0" class="loading-state">
        <el-skeleton :rows="10" animated />
      </div>
      <div v-else-if="logs.length === 0" class="empty-state">
        <el-empty description="No logs found" />
      </div>
      <div v-else class="log-lines">
        <div v-for="(line, index) in logs" :key="index" class="log-line">
          {{ line }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { taskApi } from '@/api/task'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const logs = ref<string[]>([])
const loading = ref(false)
const page = ref(1)
const logsContainer = ref<HTMLElement>()
let timer: any = null

const fetchLogs = async () => {
  loading.value = true
  try {
    // Fetch last 1000 lines (page -1 usually gets last page, but API might need adjustment for full tail)
    // For now, let's just get the last page
    const res = await taskApi.getTaskLogs(taskId, { page: -1, page_size: 2000 })
    logs.value = res.lines
    
    // Auto scroll to bottom
    nextTick(() => {
      if (logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }
    })
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchLogs()
  // Poll logs every 3 seconds
  timer = setInterval(fetchLogs, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const goBack = () => {
  router.back()
}

const handleDownload = () => {
  const url = taskApi.downloadLogs(taskId)
  window.open(url, '_blank')
}
</script>

<style scoped>
.task-logs-container {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}
.page-header {
  margin-bottom: 20px;
  flex-shrink: 0;
}
.logs-wrapper {
  flex: 1;
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 4px;
  overflow-y: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}
.loading-state {
  padding: 20px;
  background-color: white;
}
.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: white;
}
</style>
