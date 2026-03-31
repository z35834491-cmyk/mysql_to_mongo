<template>
  <div class="db-permissions-page">
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <div>
            <div class="page-title">Database 权限管理</div>
            <div class="page-subtitle">平台统一建账号，这里只做实例 / 库 / 表 / SQL 类型权限配置与 SQL 策略配置</div>
          </div>
          <div class="toolbar-actions">
            <el-button @click="policyDrawerVisible = true; resetPolicyForm()">新增 SQL 策略</el-button>
            <el-button type="primary" @click="openDrawer()">新增权限规则</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="访问规则" name="rules">
          <div class="preview-panel">
            <el-form :inline="true" :model="previewForm">
              <el-form-item label="实例">
                <el-select v-model="previewForm.instance_id" filterable clearable class="w-220">
                  <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="用户">
                <el-select v-model="previewForm.user_id" filterable clearable class="w-220">
                  <el-option v-for="item in users" :key="item.id" :label="item.username" :value="item.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="角色组">
                <el-select v-model="previewForm.group_name" filterable clearable class="w-220">
                  <el-option v-for="item in roles" :key="item.name" :label="item.name" :value="item.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="库">
                <el-input v-model="previewForm.database" class="w-180" />
              </el-form-item>
              <el-form-item label="SQL">
                <el-input v-model="previewForm.sql" class="w-420" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="runPreview">命中预览</el-button>
              </el-form-item>
            </el-form>
            <div v-if="previewResult" class="preview-result">
              <el-tag :type="previewResult.allowed ? 'success' : 'danger'">{{ previewResult.allowed ? '允许执行' : '未命中权限' }}</el-tag>
              <span>动作：{{ previewResult.action }} / SQL 类型：{{ previewResult.sql_type }}</span>
              <span>命中规则：{{ previewResult.matched_rules?.map((item: any) => item.name).join('、') || '-' }}</span>
              <span>冲突候选：{{ previewResult.conflicts?.join('、') || '-' }}</span>
            </div>
          </div>

          <el-table :data="rules" height="540" :row-class-name="ruleRowClassName">
            <el-table-column prop="name" label="规则名称" min-width="160" />
            <el-table-column prop="username" label="用户" width="120" />
            <el-table-column prop="group_name" label="角色组" width="120" />
            <el-table-column prop="instance_name" label="实例" min-width="140" />
            <el-table-column prop="database_pattern" label="库范围" width="140" />
            <el-table-column prop="table_pattern" label="表范围" width="140" />
            <el-table-column prop="actions" label="动作" min-width="180" />
            <el-table-column prop="match_explanation" label="命中解释" min-width="240" />
            <el-table-column label="冲突规则" min-width="180">
              <template #default="{ row }">
                <el-tag v-for="item in row.conflicts || []" :key="item" type="danger" class="mr-4">{{ item }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDrawer(row)">编辑</el-button>
                <el-button link type="danger" @click="removeRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="SQL 策略中心" name="policies">
          <el-table :data="executionPolicies" height="620">
            <el-table-column prop="priority" label="优先级" width="100" />
            <el-table-column prop="name" label="策略名称" min-width="160" />
            <el-table-column prop="sql_type_scope" label="SQL 类型" min-width="160" />
            <el-table-column prop="risk_scope" label="风险级别" min-width="140" />
            <el-table-column prop="auto_execute_mode" label="自动模式" width="120" />
            <el-table-column prop="require_approval" label="需要审批" width="100" />
            <el-table-column prop="allow_direct_execute" label="允许直跑" width="100" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button link type="primary" @click="openPolicyDrawer(row)">编辑</el-button>
                <el-button link type="danger" @click="removePolicy(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-drawer v-model="drawerVisible" title="Database 权限规则" size="560px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="规则名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="用户">
          <el-select v-model="form.user_id" clearable filterable>
            <el-option v-for="item in users" :key="item.id" :label="item.username" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色组">
          <el-select v-model="form.group_name" clearable filterable>
            <el-option v-for="item in roles" :key="item.name" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="实例">
          <el-select v-model="form.instance" clearable>
            <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库范围"><el-input v-model="form.database_pattern" placeholder="* 或 db_*" /></el-form-item>
        <el-form-item label="表范围"><el-input v-model="form.table_pattern" placeholder="* 或 order_*" /></el-form-item>
        <el-form-item label="SQL 类型">
          <el-select v-model="form.sql_types" multiple>
            <el-option label="SELECT" value="SELECT" />
            <el-option label="INSERT" value="INSERT" />
            <el-option label="UPDATE" value="UPDATE" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="ALTER" value="ALTER" />
            <el-option label="DROP" value="DROP" />
            <el-option label="CREATE" value="CREATE" />
            <el-option label="TRUNCATE" value="TRUNCATE" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作权限">
          <el-select v-model="form.actions" multiple>
            <el-option label="查看" value="view" />
            <el-option label="查询" value="query" />
            <el-option label="DML" value="dml" />
            <el-option label="DDL" value="ddl" />
            <el-option label="审批" value="approve" />
            <el-option label="管理" value="manage" />
            <el-option label="备份恢复" value="backup" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRule">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="policyDrawerVisible" title="SQL 策略" size="560px">
      <el-form :model="policyForm" label-width="120px">
        <el-form-item label="策略名称"><el-input v-model="policyForm.name" /></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="policyForm.priority" :min="1" :max="9999" /></el-form-item>
        <el-form-item label="环境范围">
          <el-select v-model="policyForm.environment_scope" multiple>
            <el-option label="开发" value="dev" />
            <el-option label="测试" value="test" />
            <el-option label="预发" value="staging" />
            <el-option label="生产" value="prod" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据库类型">
          <el-select v-model="policyForm.db_type_scope" multiple>
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="Redis" value="redis" />
            <el-option label="MongoDB" value="mongo" />
          </el-select>
        </el-form-item>
        <el-form-item label="SQL 类型">
          <el-select v-model="policyForm.sql_type_scope" multiple>
            <el-option label="SELECT" value="SELECT" />
            <el-option label="INSERT" value="INSERT" />
            <el-option label="UPDATE" value="UPDATE" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="ALTER" value="ALTER" />
            <el-option label="DROP" value="DROP" />
            <el-option label="CREATE" value="CREATE" />
            <el-option label="TRUNCATE" value="TRUNCATE" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险级别">
          <el-select v-model="policyForm.risk_scope" multiple>
            <el-option label="low" value="low" />
            <el-option label="medium" value="medium" />
            <el-option label="high" value="high" />
            <el-option label="critical" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="库范围"><el-input v-model="policyForm.database_pattern" /></el-form-item>
        <el-form-item label="自动模式">
          <el-select v-model="policyForm.auto_execute_mode">
            <el-option label="自动提交" value="auto_commit" />
            <el-option label="事务执行" value="transaction" />
            <el-option label="Dry Run" value="dry_run" />
          </el-select>
        </el-form-item>
        <el-form-item label="需要审批"><el-switch v-model="policyForm.require_approval" /></el-form-item>
        <el-form-item label="允许直跑"><el-switch v-model="policyForm.allow_direct_execute" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="policyForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDrawerVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPolicy">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dbManagerProApi } from '@/api/db_manager_pro'

const activeTab = ref('rules')
const rules = ref<any[]>([])
const executionPolicies = ref<any[]>([])
const users = ref<any[]>([])
const roles = ref<any[]>([])
const instances = ref<any[]>([])
const drawerVisible = ref(false)
const policyDrawerVisible = ref(false)
const previewResult = ref<any>(null)
const previewForm = reactive({
  instance_id: undefined as number | undefined,
  user_id: undefined as number | undefined,
  group_name: '',
  database: '',
  sql: 'SELECT * FROM demo_table LIMIT 1'
})
const form = reactive({
  id: undefined as number | undefined,
  name: '',
  user_id: undefined as number | undefined,
  group_name: '',
  instance: undefined as number | undefined,
  database_pattern: '*',
  table_pattern: '*',
  sql_types: [] as string[],
  actions: ['view', 'query'] as string[],
  enabled: true
})
const policyForm = reactive({
  id: undefined as number | undefined,
  name: '',
  priority: 100,
  environment_scope: [] as string[],
  db_type_scope: [] as string[],
  sql_type_scope: [] as string[],
  risk_scope: [] as string[],
  database_pattern: '*',
  auto_execute_mode: 'auto_commit',
  require_approval: false,
  allow_direct_execute: true,
  enabled: true
})

const resetForm = () => {
  Object.assign(form, {
    id: undefined,
    name: '',
    user_id: undefined,
    group_name: '',
    instance: undefined,
    database_pattern: '*',
    table_pattern: '*',
    sql_types: [],
    actions: ['view', 'query'],
    enabled: true
  })
}

const resetPolicyForm = () => {
  Object.assign(policyForm, {
    id: undefined,
    name: '',
    priority: 100,
    environment_scope: [],
    db_type_scope: [],
    sql_type_scope: [],
    risk_scope: [],
    database_pattern: '*',
    auto_execute_mode: 'auto_commit',
    require_approval: false,
    allow_direct_execute: true,
    enabled: true
  })
}

const loadData = async () => {
  const [ruleData, subjectData, instanceData, policyData] = await Promise.all([
    dbManagerProApi.listAccessRules(),
    dbManagerProApi.listPermissionSubjects(),
    dbManagerProApi.listInstances(),
    dbManagerProApi.listExecutionPolicies()
  ])
  rules.value = Array.isArray(ruleData) ? ruleData : []
  users.value = Array.isArray(subjectData.users) ? subjectData.users : []
  roles.value = Array.isArray(subjectData.roles) ? subjectData.roles : []
  instances.value = Array.isArray(instanceData) ? instanceData : []
  executionPolicies.value = Array.isArray(policyData) ? policyData : []
}

const openDrawer = (row?: any) => {
  resetForm()
  if (row) {
    Object.assign(form, {
      id: row.id,
      name: row.name,
      user_id: row.user_id,
      group_name: row.group_name,
      instance: row.instance,
      database_pattern: row.database_pattern,
      table_pattern: row.table_pattern,
      sql_types: row.sql_types || [],
      actions: row.actions || [],
      enabled: row.enabled
    })
  }
  drawerVisible.value = true
}

const openPolicyDrawer = (row?: any) => {
  resetPolicyForm()
  if (row) {
    Object.assign(policyForm, {
      id: row.id,
      name: row.name,
      priority: row.priority,
      environment_scope: row.environment_scope || [],
      db_type_scope: row.db_type_scope || [],
      sql_type_scope: row.sql_type_scope || [],
      risk_scope: row.risk_scope || [],
      database_pattern: row.database_pattern || '*',
      auto_execute_mode: row.auto_execute_mode || 'auto_commit',
      require_approval: !!row.require_approval,
      allow_direct_execute: !!row.allow_direct_execute,
      enabled: !!row.enabled
    })
  }
  policyDrawerVisible.value = true
}

const submitRule = async () => {
  const payload = { ...form }
  if (payload.id) {
    await dbManagerProApi.updateAccessRule(payload.id, payload)
  } else {
    await dbManagerProApi.createAccessRule(payload)
  }
  drawerVisible.value = false
  ElMessage.success('权限规则已保存')
  await loadData()
}

const removeRule = async (row: any) => {
  await ElMessageBox.confirm(`确认删除规则「${row.name}」吗？`, '提示', { type: 'warning' })
  await dbManagerProApi.deleteAccessRule(row.id)
  ElMessage.success('权限规则已删除')
  await loadData()
}

const runPreview = async () => {
  if (!previewForm.instance_id) return
  previewResult.value = await dbManagerProApi.previewAccessRule({ ...previewForm })
}

const submitPolicy = async () => {
  const payload = { ...policyForm }
  if (payload.id) {
    await dbManagerProApi.updateExecutionPolicy(payload.id, payload)
  } else {
    await dbManagerProApi.createExecutionPolicy(payload)
  }
  policyDrawerVisible.value = false
  ElMessage.success('SQL 策略已保存')
  await loadData()
}

const removePolicy = async (row: any) => {
  await ElMessageBox.confirm(`确认删除策略「${row.name}」吗？`, '提示', { type: 'warning' })
  await dbManagerProApi.deleteExecutionPolicy(row.id)
  ElMessage.success('SQL 策略已删除')
  await loadData()
}

const ruleRowClassName = ({ row }: any) => {
  return row.conflicts?.length ? 'conflict-row' : ''
}

onMounted(loadData)
</script>

<style scoped>
.db-permissions-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
}
.page-subtitle {
  margin-top: 4px;
  color: #8c8c8c;
  font-size: 12px;
}
.preview-panel {
  margin-bottom: 12px;
}
.preview-result {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  color: #4b5563;
}
.w-220 {
  width: 220px;
}
.w-180 {
  width: 180px;
}
.w-420 {
  width: 420px;
}
.mr-4 {
  margin-right: 4px;
}
:deep(.conflict-row) {
  --el-table-tr-bg-color: #fff1f0;
}
</style>
