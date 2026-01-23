import { defineStore } from 'pinia'
import { ref } from 'vue'
import { systemApi } from '@/api/system'
import type { MonitorConfig, InspectionReport } from '@/types/system'
import { ElMessage } from 'element-plus'

export const useSystemStore = defineStore('system', () => {
  // Monitor State
  const monitorTasks = ref<any[]>([])
  const monitorLogs = ref<any[]>([])
  
  // Inspection State
  const reports = ref<string[]>([])
  const currentReport = ref<any | null>(null)
  const inspectionConfig = ref<any>({
    prometheus_url: '',
    ark_base_url: '',
    ark_api_key: '',
    ark_model_id: ''
  })
  
  const loading = ref(false)
  
  // Monitor Actions
  const fetchMonitorTasks = async () => {
    loading.value = true
    try {
      monitorTasks.value = await systemApi.getMonitorTasks()
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const saveMonitorTask = async (task: any) => {
    try {
      if (task.id) {
        await systemApi.updateMonitorTask(task.id, task)
      } else {
        await systemApi.saveMonitorTask(task)
      }
      ElMessage.success('Task saved')
      await fetchMonitorTasks()
    } catch (e) {
      console.error(e)
    }
  }

  const deleteMonitorTask = async (id: number) => {
    try {
      await systemApi.deleteMonitorTask(id)
      ElMessage.success('Task deleted')
      await fetchMonitorTasks()
    } catch (e) {
      console.error(e)
    }
  }
  
  const fetchMonitorLogs = async (taskId: string) => {
    loading.value = true
    try {
      monitorLogs.value = await systemApi.getMonitorLogs({ task_id: taskId })
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const getLogContent = async (taskId: string, filename: string, keyword?: string) => {
    try {
      const res = await systemApi.getLogContent({ task_id: taskId, filename, keyword })
      return res.content
    } catch (e) {
      console.error(e)
      return ''
    }
  }
  
  // Inspection Actions
  const fetchReports = async () => {
    loading.value = true
    try {
      reports.value = await systemApi.getReports()
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }
  
  const runInspection = async (config?: any) => {
    try {
      await systemApi.runInspection(config)
      ElMessage.success('Inspection started')
      await fetchReports()
    } catch (e) {
      console.error(e)
    }
  }

  const fetchReportDetail = async (id: string) => {
    try {
      currentReport.value = await systemApi.getReportDetail(id)
    } catch (e) {
      console.error(e)
    }
  }

  const fetchInspectionConfig = async () => {
    try {
      inspectionConfig.value = await systemApi.getInspectionConfig()
    } catch (e) {
      console.error(e)
    }
  }

  const saveInspectionConfig = async (config: any) => {
    try {
      await systemApi.saveInspectionConfig(config)
      ElMessage.success('Configuration saved')
      inspectionConfig.value = config
    } catch (e) {
      console.error(e)
    }
  }
  
  return {
    monitorTasks,
    monitorLogs,
    reports,
    currentReport,
    inspectionConfig,
    loading,
    fetchMonitorTasks,
    saveMonitorTask,
    deleteMonitorTask,
    fetchMonitorLogs,
    getLogContent,
    fetchReports,
    runInspection,
    fetchReportDetail,
    fetchInspectionConfig,
    saveInspectionConfig
  }
})
