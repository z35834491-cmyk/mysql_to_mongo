import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Connection } from '@/types/connection'
import { connectionApi } from '@/api/connection'
import { ElMessage } from 'element-plus'

export const useConnectionStore = defineStore('connection', () => {
  const connections = ref<Connection[]>([])
  const loading = ref(false)
  
  const fetchConnections = async () => {
    loading.value = true
    try {
      connections.value = await connectionApi.getConnections()
    } catch (error) {
      console.error(error)
    } finally {
      loading.value = false
    }
  }
  
  const saveConnection = async (data: Connection) => {
    await connectionApi.saveConnection(data)
    ElMessage.success('Connection saved')
    await fetchConnections()
  }
  
  const deleteConnection = async (id: string) => {
    await connectionApi.deleteConnection(id)
    ElMessage.success('Connection deleted')
    await fetchConnections()
  }
  
  const testConnection = async (data: Connection) => {
    const res = await connectionApi.testConnection(data)
    if (res.ok) {
      ElMessage.success(`Connection OK (${res.latency_ms}ms)`)
    } else {
      ElMessage.error('Connection failed')
    }
    return res
  }
  
  const fetchDatabases = async (connId: string) => {
    const res = await connectionApi.getDatabases(connId)
    return res.databases
  }

  const fetchTables = async (connId: string, database: string) => {
    const res = await connectionApi.getTables(connId, database)
    return res.tables
  }

  return {
    connections,
    loading,
    fetchConnections,
    saveConnection,
    deleteConnection,
    testConnection,
    fetchDatabases,
    fetchTables
  }
})
