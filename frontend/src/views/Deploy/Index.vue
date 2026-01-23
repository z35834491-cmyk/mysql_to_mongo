<template>
  <div class="deploy-container">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="Servers" name="servers">
        <div class="toolbar">
          <el-button type="primary" @click="handleAddServer">Add Server</el-button>
        </div>
        <el-table :data="servers" v-loading="loading" style="width: 100%">
          <el-table-column prop="host" label="Host" />
          <el-table-column prop="user" label="User" width="120" />
          <el-table-column prop="port" label="Port" width="100" />
          <el-table-column label="Auth Type" width="150">
            <template #default="{ row }">
              <el-tag size="small">{{ row.key_path ? 'SSH Key' : 'Password' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="150">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="handleDeleteServer(row.id)">Delete</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      
      <el-tab-pane label="Deploy Task" name="deploy">
        <el-card shadow="never" class="deploy-card">
          <el-form :model="deployForm" label-width="120px">
            <el-form-item label="Target Servers">
              <el-select v-model="deployForm.server_ids" multiple placeholder="Select servers">
                <el-option
                  v-for="server in servers"
                  :key="server.id"
                  :label="`${server.host} (${server.user})`"
                  :value="server.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="Script">
              <el-input 
                v-model="deployForm.script_content" 
                type="textarea" 
                :rows="10" 
                placeholder="#!/bin/bash\necho 'Hello World'"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleDeploy" :disabled="!canDeploy">Execute</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="serverDialogVisible" :title="editMode ? 'Edit Server' : 'Add Server'" width="500px">
      <el-form :model="serverForm" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="serverForm.name" placeholder="Web Server 01" />
        </el-form-item>
        <el-form-item label="Host">
          <el-input v-model="serverForm.host" placeholder="1.2.3.4" />
        </el-form-item>
        <el-form-item label="Port">
          <el-input-number v-model="serverForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="User">
          <el-input v-model="serverForm.user" />
        </el-form-item>
        <el-form-item label="Auth Method">
          <el-radio-group v-model="serverForm.auth_method">
            <el-radio label="password">Password</el-radio>
            <el-radio label="key">SSH Key</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="serverForm.auth_method === 'password'" label="Password">
          <el-input v-model="serverForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item v-else label="Key Path">
          <el-input v-model="serverForm.key_path" placeholder="~/.ssh/id_rsa" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="serverDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveServer">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useDeployStore } from '@/stores/deploy'
import { storeToRefs } from 'pinia'
import { ElMessageBox, ElMessage } from 'element-plus'

const activeTab = ref('servers')
const deployStore = useDeployStore()
const { servers, loading } = storeToRefs(deployStore)

const serverDialogVisible = ref(false)
const editMode = ref(false)
const serverForm = reactive({
  id: '',
  name: '',
  host: '',
  port: 22,
  user: 'root',
  auth_method: 'password',
  password: '',
  key_path: ''
})

const deployForm = reactive({
  server_ids: [],
  script_content: '#!/bin/bash\n'
})

const canDeploy = computed(() => deployForm.server_ids.length > 0 && deployForm.script_content.trim().length > 0)

onMounted(() => {
  deployStore.fetchServers()
})

const handleAddServer = () => {
  editMode.value = false
  Object.assign(serverForm, {
    id: `server_${Date.now()}`,
    name: '',
    host: '',
    port: 22,
    user: 'root',
    auth_method: 'password',
    password: '',
    key_path: ''
  })
  serverDialogVisible.value = true
}

const saveServer = async () => {
  try {
    await deployStore.saveServer({ ...serverForm })
    ElMessage.success('Server saved')
    serverDialogVisible.value = false
  } catch (e) {
    console.error(e)
  }
}

const handleDeleteServer = (id: string) => {
  ElMessageBox.confirm('Are you sure?', 'Warning', {
    type: 'warning'
  }).then(() => {
    deployStore.deleteServer(id)
  })
}

const handleDeploy = async () => {
  try {
    await deployStore.runDeploy(deployForm)
    ElMessage.success('Deployment started')
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped>
.deploy-container {
  /* padding: 20px; */
}
.toolbar {
  margin-bottom: 20px;
}
.deploy-card {
  max-width: 800px;
}
</style>
