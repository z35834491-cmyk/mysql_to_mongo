import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Task } from '@/types/task'
import { taskApi } from '@/api/task'
import { ElMessage } from 'element-plus'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<Task[]>([])
  const loading = ref(false)
  
  const taskStats = computed(() => ({
    total: tasks.value.length,
    running: tasks.value.filter(t => t.status === 'running').length,
    stopped: tasks.value.filter(t => t.status === 'stopped').length,
    error: tasks.value.filter(t => t.status === 'error').length
  }))

  const fetchTasks = async () => {
    loading.value = true
    try {
      tasks.value = await taskApi.getTasks()
    } catch (error) {
      console.error(error)
    } finally {
      loading.value = false
    }
  }
  
  const createTask = async (data: any) => {
    await taskApi.createTask(data)
    ElMessage.success('Task created successfully')
    await fetchTasks()
  }
  
  const startTask = async (id: string) => {
    await taskApi.startTask(id)
    ElMessage.success('Task started')
    await fetchTasks()
  }
  
  const stopTask = async (id: string) => {
    await taskApi.stopTask(id)
    ElMessage.success('Task stopped')
    await fetchTasks()
  }
  
  const resetTask = async (id: string) => {
    await taskApi.resetTask(id)
    ElMessage.success('Task reset and started')
    await fetchTasks()
  }
  
  const deleteTask = async (id: string) => {
    await taskApi.deleteTask(id)
    ElMessage.success('Task deleted')
    await fetchTasks()
  }
  
  return {
    tasks,
    loading,
    taskStats,
    fetchTasks,
    createTask,
    startTask,
    stopTask,
    resetTask,
    deleteTask
  }
})
