import { defineStore } from 'pinia'
import { ref } from 'vue'
import { systemApi } from '@/api/system'
import type { Server, DeployPlan } from '@/types/deploy'
import { ElMessage } from 'element-plus'

export const useDeployStore = defineStore('deploy', () => {
  const servers = ref<Server[]>([])
  const loading = ref(false)
  const currentPlan = ref<DeployPlan | null>(null)
  
  const fetchServers = async () => {
    loading.value = true
    try {
      const res = await systemApi.getServers()
      servers.value = res.servers
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }
  
  const saveServer = async (server: Server) => {
    await systemApi.saveServer(server)
    ElMessage.success('Server saved')
    await fetchServers()
  }
  
  const deleteServer = async (id: string) => {
    await systemApi.deleteServer(id)
    ElMessage.success('Server deleted')
    await fetchServers()
  }
  
  const runDeploy = async (plan: any) => {
    const res = await systemApi.runDeploy(plan)
    ElMessage.success(`Deploy started: ${res.plan_id}`)
    return res.plan_id
  }
  
  const fetchPlan = async (id: string) => {
    const res = await systemApi.getPlan(id)
    currentPlan.value = res
    return res
  }
  
  return {
    servers,
    loading,
    currentPlan,
    fetchServers,
    saveServer,
    deleteServer,
    runDeploy,
    fetchPlan
  }
})
