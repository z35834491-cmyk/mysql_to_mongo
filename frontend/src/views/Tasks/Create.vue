<template>
  <div class="create-task-container">
    <el-page-header @back="goBack" content="Create New Sync Task" class="page-header" />
    
    <el-card shadow="never" class="form-card">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="150px" v-loading="submitting">
        <el-form-item label="Task ID" prop="task_id">
          <el-input v-model="form.task_id" placeholder="e.g. sync_users_order" />
        </el-form-item>
        
        <el-divider content-position="left">Source (MySQL)</el-divider>
        
        <el-form-item label="MySQL Connection" prop="source_conn_id">
          <el-select v-model="form.source_conn_id" placeholder="Select MySQL Connection" @change="handleSourceChange">
            <el-option
              v-for="item in mysqlConnections"
              :key="item.id"
              :label="`${item.id} (${item.host})`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Database" prop="mysql_database">
          <el-select 
            v-model="form.mysql_database" 
            placeholder="Select Database" 
            :disabled="!form.source_conn_id"
            @change="handleDatabaseChange"
          >
            <el-option
              v-for="db in databaseList"
              :key="db"
              :label="db"
              :value="db"
            />
          </el-select>
        </el-form-item>
        
        <el-divider content-position="left">Target (MongoDB)</el-divider>
        
        <el-form-item label="Mongo Connection" prop="target_conn_id">
          <el-select v-model="form.target_conn_id" placeholder="Select Mongo Connection">
            <el-option
              v-for="item in mongoConnections"
              :key="item.id"
              :label="`${item.id} (${item.hosts || item.host})`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Target Database" prop="mongo_database">
          <el-input v-model="form.mongo_database" placeholder="e.g. sync_db" />
        </el-form-item>
        
        <el-divider content-position="left">Table Mapping</el-divider>
        
        <el-form-item label="Tables to Sync">
          <div class="table-selector">
            <el-checkbox-group v-model="selectedTables">
              <el-checkbox v-for="table in tableList" :key="table" :label="table">{{ table }}</el-checkbox>
            </el-checkbox-group>
            <div v-if="!form.mysql_database" class="text-gray">Please select database first</div>
            <div v-else-if="tableList.length === 0" class="text-gray">No tables found</div>
          </div>
        </el-form-item>
        
        <el-form-item label="Sync Options">
          <el-checkbox v-model="form.auto_discover_new_tables">Auto Discover New Tables</el-checkbox>
          <el-checkbox v-model="form.update_insert_new_doc">Update Inserts New Doc (Versioning)</el-checkbox>
          <el-checkbox v-model="form.use_pk_as_mongo_id">Use MySQL PK as Mongo _id</el-checkbox>
        </el-form-item>

        <el-divider content-position="left">Binlog Start Position (Optional)</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Filename" prop="binlog_filename">
              <el-input v-model="form.binlog_filename" placeholder="e.g. mysql-bin.000001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Position" prop="binlog_position">
               <el-input-number v-model="form.binlog_position" :min="4" placeholder="e.g. 154" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item>
          <el-button type="primary" @click="onSubmit">Create & Start</el-button>
          <el-button @click="goBack">Cancel</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectionStore } from '@/stores/connection'
import { useTaskStore } from '@/stores/task'
import { storeToRefs } from 'pinia'

const router = useRouter()
const connectionStore = useConnectionStore()
const taskStore = useTaskStore()
const { connections } = storeToRefs(connectionStore)

const formRef = ref()
const submitting = ref(false)
const databaseList = ref<string[]>([])
const tableList = ref<string[]>([])
const selectedTables = ref<string[]>([])

const form = reactive({
  task_id: '',
  source_conn_id: '',
  target_conn_id: '',
  mysql_database: '',
  mongo_database: '',
  auto_discover_new_tables: true,
  update_insert_new_doc: true,
  use_pk_as_mongo_id: true,
  pk_field: 'id',
  binlog_filename: '',
  binlog_position: undefined as number | undefined
})

const rules = {
  task_id: [{ required: true, message: 'Please input task ID', trigger: 'blur' }],
  source_conn_id: [{ required: true, message: 'Please select source connection', trigger: 'change' }],
  target_conn_id: [{ required: true, message: 'Please select target connection', trigger: 'change' }],
  mysql_database: [{ required: true, message: 'Please select source database', trigger: 'change' }],
  mongo_database: [{ required: true, message: 'Please input target database', trigger: 'blur' }]
}

const mysqlConnections = computed(() => connections.value.filter(c => c.type === 'mysql'))
const mongoConnections = computed(() => connections.value.filter(c => c.type === 'mongo'))

onMounted(() => {
  connectionStore.fetchConnections()
})

const goBack = () => {
  router.back()
}

const handleSourceChange = async (val: string) => {
  form.mysql_database = ''
  databaseList.value = []
  tableList.value = []
  selectedTables.value = []
  
  if (val) {
    try {
      databaseList.value = await connectionStore.fetchDatabases(val)
    } catch (e) {
      console.error(e)
    }
  }
}

const handleDatabaseChange = async (val: string) => {
  tableList.value = []
  selectedTables.value = []
  
  if (val && form.source_conn_id) {
    try {
      tableList.value = await connectionStore.fetchTables(form.source_conn_id, val)
    } catch (e) {
      console.error(e)
    }
  }
}

const onSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      if (selectedTables.value.length === 0 && !form.auto_discover_new_tables) {
        ElMessage.warning('Please select at least one table or enable auto discovery')
        return
      }
      
      const tableMap: Record<string, string> = {}
      if (selectedTables.value.length > 0) {
        selectedTables.value.forEach(t => {
          tableMap[t] = t
        })
      } else {
        tableMap['*'] = '*'
      }
      
      submitting.value = true
      try {
        await taskStore.createTask({
          ...form,
          table_map: tableMap
        })
        router.push('/tasks')
      } catch (e) {
        console.error(e)
      } finally {
        submitting.value = false
      }
    }
  })
}
</script>

<style scoped>
.create-task-container {
  /* padding: 20px; */
}
.page-header {
  margin-bottom: 20px;
}
.form-card {
  max-width: 800px;
  margin: 0 auto;
}
.table-selector {
  border: 1px solid #dcdfe6;
  padding: 10px;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}
.text-gray {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 20px;
}
</style>
