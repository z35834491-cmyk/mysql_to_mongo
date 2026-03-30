<template>
  <div class="dbm-pro-page">
    <div class="summary-grid">
      <el-card v-for="card in summaryCards" :key="card.label" shadow="never" class="summary-card">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value">{{ card.value }}</div>
        <div class="summary-extra">{{ card.extra }}</div>
      </el-card>
    </div>

    <div class="content-grid">
      <el-card shadow="never" class="instance-panel">
        <template #header>
          <div class="panel-header">
            <span>实例管理</span>
            <el-button type="primary" size="small" @click="openCreateDrawer">新增实例</el-button>
          </div>
        </template>
        <el-input v-model="filters.keyword" placeholder="搜索实例 / Host" clearable class="mb-12" @change="loadInstances" />
        <el-select v-model="filters.environment" placeholder="环境" clearable class="mb-12" @change="loadInstances">
          <el-option label="开发" value="dev" />
          <el-option label="测试" value="test" />
          <el-option label="预发" value="staging" />
          <el-option label="生产" value="prod" />
        </el-select>
        <el-table :data="instances" height="560" @row-click="selectInstance">
          <el-table-column prop="name" label="实例" min-width="140" />
          <el-table-column prop="db_type" label="类型" width="110" />
          <el-table-column prop="environment" label="环境" width="100" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="testInstance(row)">测试</el-button>
              <el-button link @click.stop="editInstance(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <div class="workspace-panel">
        <el-card shadow="never" class="workspace-card">
          <template #header>
            <div class="panel-header">
              <div>
                <div class="workspace-title">SQL 工作台</div>
                <div class="workspace-subtitle">{{ activeInstanceTitle }}</div>
              </div>
              <div class="toolbar-group">
                <el-button @click="formatSqlAction">格式化</el-button>
                <el-button @click="explainSqlAction" :disabled="!canRun">执行计划</el-button>
                <el-button type="warning" @click="reviewSqlAction" :disabled="!canRun">AI 分析</el-button>
                <el-button type="primary" @click="executeSqlAction" :disabled="!canRun">执行 SQL</el-button>
              </div>
            </div>
          </template>
          <div class="editor-topbar">
            <el-tag v-if="selectedInstance" type="info">{{ selectedInstance.db_type }}</el-tag>
            <el-input v-model="workbench.database" placeholder="Database / Schema" class="database-input" />
            <el-select v-model="workbench.executeMode" class="mode-select">
              <el-option label="自动提交" value="auto_commit" />
              <el-option label="事务模式" value="transaction" />
              <el-option label="Dry Run" value="dry_run" />
            </el-select>
          </div>
          <monaco-sql-editor
            v-model="workbench.sql"
            :suggestions="completionItems"
            @keyword-change="handleCompletionKeywordChange"
          />
        </el-card>

        <div class="workspace-bottom">
          <el-card shadow="never" class="analysis-card">
            <template #header>
              <div class="panel-header">
                <span>AI 分析 / 执行计划</span>
                <el-tag v-if="aiReview?.risk_level" :type="riskTagType(aiReview.risk_level)">{{ aiReview.risk_level }}</el-tag>
              </div>
            </template>
            <el-empty v-if="!aiReview && !explainResult.rows?.length" description="先执行 AI 分析或执行计划预览" />
            <template v-else>
              <el-alert
                v-if="aiReview"
                :title="`决策：${aiReview.decision || '-'} / SQL 类型：${aiReview.sql_type || '-'}`"
                :type="alertType(aiReview?.decision)"
                :closable="false"
                show-icon
                class="mb-12"
              />
              <el-descriptions v-if="aiReview" :column="1" border>
                <el-descriptions-item label="摘要">{{ aiReview.sql_summary || '-' }}</el-descriptions-item>
                <el-descriptions-item label="执行计划摘要">{{ aiReview.explain_summary || '-' }}</el-descriptions-item>
                <el-descriptions-item label="安全风险">
                  <div v-for="item in aiReview.security_findings || []" :key="item">{{ item }}</div>
                </el-descriptions-item>
                <el-descriptions-item label="性能建议">
                  <div v-for="item in aiReview.optimization_suggestions || []" :key="item">{{ item }}</div>
                </el-descriptions-item>
              </el-descriptions>
              <explain-visualizer v-if="explainResult.rows?.length" :headers="explainResult.headers" :rows="explainResult.rows" class="mt-12" />
              <el-table v-if="explainResult.rows?.length" :data="explainResult.rows" max-height="220" class="mt-12">
                <el-table-column v-for="header in explainResult.headers" :key="header" :prop="header" :label="header" min-width="140" />
              </el-table>
            </template>
          </el-card>

          <el-card shadow="never" class="result-card">
            <template #header>
              <div class="panel-header">
                <span>执行结果</span>
                <div class="toolbar-group">
                  <el-button v-if="activeJob?.status === 'running'" size="small" @click="pauseJobAction">暂停</el-button>
                  <el-button v-if="activeJob?.status === 'running'" size="small" type="danger" @click="cancelJobAction">取消</el-button>
                  <el-button v-if="activeJob?.status === 'paused'" size="small" type="primary" @click="resumeJobAction">恢复</el-button>
                </div>
              </div>
            </template>
            <el-tabs v-model="activePane">
              <el-tab-pane label="结果集" name="result">
                <el-table v-if="jobResult.rows_json?.length" :data="jobResult.rows_json" max-height="260">
                  <el-table-column v-for="header in jobResult.columns_json || []" :key="header" :prop="header" :label="header" min-width="140" />
                </el-table>
                <el-empty v-else description="暂无结果集" />
              </el-tab-pane>
              <el-tab-pane label="执行日志" name="logs">
                <div class="log-stream">
                  <div v-for="item in jobLogs" :key="`${item.seq}-${item.created_at}`" class="log-line" :class="item.level">
                    [{{ item.level }}] {{ item.message }}
                  </div>
                </div>
              </el-tab-pane>
              <el-tab-pane label="作业记录" name="jobs">
                <el-table :data="jobs" max-height="260" @row-click="loadJobDetail">
                  <el-table-column prop="id" label="Job" width="90" />
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="sql_type" label="类型" width="100" />
                  <el-table-column prop="status" label="状态" width="110" />
                  <el-table-column prop="duration_ms" label="耗时" width="100" />
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="审批中心" name="approvals">
                <el-table :data="approvals" max-height="260">
                  <el-table-column prop="id" label="审批单" width="90" />
                  <el-table-column prop="applicant" label="申请人" width="120" />
                  <el-table-column prop="status" label="状态" width="100" />
                  <el-table-column prop="reason" label="原因" min-width="180" />
                  <el-table-column label="操作" width="150">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="approve(row)" :disabled="row.status !== 'pending'">通过</el-button>
                      <el-button link type="danger" @click="reject(row)" :disabled="row.status !== 'pending'">拒绝</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="审计日志" name="audit">
                <div class="toolbar-group mb-12">
                  <el-button size="small" @click="exportAuditAction">导出 CSV</el-button>
                  <el-button size="small" @click="createRollbackFromSelectedAudit" :disabled="!auditLogs.length">生成回滚任务</el-button>
                </div>
                <el-table :data="auditLogs" max-height="260">
                  <el-table-column prop="id" label="审计ID" width="90" />
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="username" label="执行人" width="120" />
                  <el-table-column prop="sql_type" label="类型" width="100" />
                  <el-table-column prop="risk_level" label="风险" width="100" />
                  <el-table-column prop="success" label="成功" width="90" />
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="审批策略" name="policies">
                <div class="toolbar-group mb-12">
                  <el-button type="primary" size="small" @click="openPolicyDrawer">新增策略</el-button>
                </div>
                <el-table :data="approvalPolicies" max-height="260">
                  <el-table-column prop="name" label="策略名称" min-width="140" />
                  <el-table-column prop="environment_scope" label="环境" min-width="120" />
                  <el-table-column prop="db_type_scope" label="数据库类型" min-width="120" />
                  <el-table-column prop="sql_type_scope" label="SQL 类型" min-width="120" />
                  <el-table-column prop="risk_scope" label="风险级别" min-width="120" />
                  <el-table-column prop="enabled" label="启用" width="90" />
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="访问控制" name="access">
                <div class="toolbar-group mb-12">
                  <el-button type="primary" size="small" @click="openAccessRuleDrawer">新增访问规则</el-button>
                </div>
                <el-table :data="accessRules" max-height="260">
                  <el-table-column prop="name" label="规则名称" min-width="140" />
                  <el-table-column prop="username" label="用户" width="120" />
                  <el-table-column prop="group_name" label="角色组" width="120" />
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="database_pattern" label="库范围" width="120" />
                  <el-table-column prop="table_pattern" label="表范围" width="120" />
                  <el-table-column prop="actions" label="动作" min-width="160" />
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="备份恢复" name="backup">
                <div class="toolbar-group mb-12">
                  <el-button type="primary" size="small" @click="createBackupPlanAction" :disabled="!selectedInstance">新增备份计划</el-button>
                  <el-button size="small" @click="createRestoreJobAction" :disabled="!selectedInstance">创建恢复任务</el-button>
                  <el-button size="small" type="warning" @click="createRollbackFromSelectedAudit" :disabled="!auditLogs.length">创建回滚任务</el-button>
                </div>
                <el-table :data="backupPlans" max-height="120">
                  <el-table-column prop="name" label="计划" min-width="140" />
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="backup_type" label="类型" width="100" />
                  <el-table-column prop="retention_days" label="保留天数" width="100" />
                  <el-table-column label="操作" width="100">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="runBackup(row)">立即执行</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-divider content-position="left">备份记录</el-divider>
                <el-table :data="backupRecords" max-height="120">
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="file_uri" label="文件" min-width="220" />
                  <el-table-column prop="status" label="状态" width="100" />
                </el-table>
                <el-divider content-position="left">恢复任务</el-divider>
                <el-table :data="restoreJobs" max-height="120">
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="restore_mode" label="模式" width="110" />
                  <el-table-column prop="status" label="状态" width="100" />
                  <el-table-column prop="target_txn_id" label="事务 / 时间点" min-width="160" />
                </el-table>
                <el-divider content-position="left">回滚任务</el-divider>
                <el-table :data="rollbackJobs" max-height="120">
                  <el-table-column prop="instance_name" label="实例" min-width="120" />
                  <el-table-column prop="status" label="状态" width="100" />
                  <el-table-column prop="source_audit" label="来源审计" width="120" />
                  <el-table-column label="操作" width="120">
                    <template #default="{ row }">
                      <el-button link type="danger" @click="runRollback(row)">执行回滚</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="实例诊断" name="diagnostics">
                <div class="toolbar-group mb-12">
                  <el-button size="small" type="primary" @click="runDiagnosticsAction" :disabled="!selectedInstance">重新诊断</el-button>
                </div>
                <el-descriptions v-if="diagnosticsReport" :column="2" border>
                  <el-descriptions-item label="Schema 数">{{ diagnosticsReport.summary?.schema_count ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="表数量">{{ diagnosticsReport.summary?.table_count ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="备份计划">{{ diagnosticsReport.summary?.backup_plan_count ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="最近备份状态">{{ diagnosticsReport.summary?.latest_backup_status ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="SQL 作业">{{ diagnosticsReport.summary?.sql_job_count ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="失败作业">{{ diagnosticsReport.summary?.failed_sql_jobs ?? '-' }}</el-descriptions-item>
                </el-descriptions>
                <el-timeline class="mt-12">
                  <el-timeline-item v-for="item in diagnosticsReport?.checks || []" :key="`${item.name}-${item.message}`" :type="item.status === 'failed' ? 'danger' : item.status === 'warning' ? 'warning' : 'primary'">
                    <div class="diag-title">{{ item.name }}</div>
                    <div class="diag-desc">{{ item.message }}</div>
                  </el-timeline-item>
                </el-timeline>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </div>
      </div>
    </div>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="520px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="实例名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="数据库类型">
          <el-select v-model="form.db_type">
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="Redis" value="redis" />
            <el-option label="MongoDB" value="mongo" />
            <el-option label="RabbitMQ" value="rabbitmq" />
          </el-select>
        </el-form-item>
        <el-form-item label="环境">
          <el-select v-model="form.environment">
            <el-option label="开发" value="dev" />
            <el-option label="测试" value="test" />
            <el-option label="预发" value="staging" />
            <el-option label="生产" value="prod" />
          </el-select>
        </el-form-item>
        <el-form-item label="Host"><el-input v-model="form.host" /></el-form-item>
        <el-form-item label="Port"><el-input-number v-model="form.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="默认库"><el-input v-model="form.default_database" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="所属团队"><el-input v-model="form.owner_team" /></el-form-item>
        <el-form-item label="只读实例"><el-switch v-model="form.read_only" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" @click="submitInstance">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="policyDrawerVisible" title="审批策略配置" size="560px">
      <el-form :model="policyForm" label-width="120px">
        <el-form-item label="策略名称"><el-input v-model="policyForm.name" /></el-form-item>
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
        <el-form-item label="启用"><el-switch v-model="policyForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDrawerVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPolicy">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="accessDrawerVisible" title="访问控制规则" size="560px">
      <el-form :model="accessRuleForm" label-width="120px">
        <el-form-item label="规则名称"><el-input v-model="accessRuleForm.name" /></el-form-item>
        <el-form-item label="用户 ID"><el-input-number v-model="accessRuleForm.user_id" :min="1" /></el-form-item>
        <el-form-item label="角色组"><el-input v-model="accessRuleForm.group_name" placeholder="可选，填写 Group 名称" /></el-form-item>
        <el-form-item label="实例">
          <el-select v-model="accessRuleForm.instance" clearable>
            <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库范围"><el-input v-model="accessRuleForm.database_pattern" placeholder="* 或具体库名" /></el-form-item>
        <el-form-item label="表范围"><el-input v-model="accessRuleForm.table_pattern" placeholder="* 或 order_*" /></el-form-item>
        <el-form-item label="SQL 类型">
          <el-select v-model="accessRuleForm.sql_types" multiple>
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
          <el-select v-model="accessRuleForm.actions" multiple>
            <el-option label="查看" value="view" />
            <el-option label="查询" value="query" />
            <el-option label="DML" value="dml" />
            <el-option label="DDL" value="ddl" />
            <el-option label="审批" value="approve" />
            <el-option label="管理" value="manage" />
            <el-option label="备份恢复" value="backup" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="accessRuleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accessDrawerVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAccessRule">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dbManagerProApi, type DBInstancePayload } from '@/api/db_manager_pro'
import MonacoSqlEditor from './components/MonacoSqlEditor.vue'
import ExplainVisualizer from './components/ExplainVisualizer.vue'

const filters = reactive({ keyword: '', environment: '' })
const instances = ref<any[]>([])
const approvals = ref<any[]>([])
const auditLogs = ref<any[]>([])
const approvalPolicies = ref<any[]>([])
const accessRules = ref<any[]>([])
const backupPlans = ref<any[]>([])
const backupRecords = ref<any[]>([])
const restoreJobs = ref<any[]>([])
const rollbackJobs = ref<any[]>([])
const jobs = ref<any[]>([])
const selectedInstance = ref<any>(null)
const drawerVisible = ref(false)
const drawerTitle = ref('新增实例')
const activePane = ref('result')
const aiReview = ref<any>(null)
const explainResult = ref<any>({ headers: [], rows: [] })
const activeJob = ref<any>(null)
const jobLogs = ref<any[]>([])
const jobResult = ref<any>({ columns_json: [], rows_json: [] })
const completionItems = ref<any[]>([])
const diagnosticsReport = ref<any>(null)
const policyDrawerVisible = ref(false)
const accessDrawerVisible = ref(false)
const form = reactive<DBInstancePayload>({
  name: '',
  db_type: 'mysql',
  environment: 'dev',
  host: '',
  port: 3306,
  default_database: '',
  username: '',
  password: '',
  read_only: false,
  owner_team: '',
  tags: [],
  extra_config: {}
})
const workbench = reactive({
  database: '',
  sql: '',
  executeMode: 'auto_commit'
})
const policyForm = reactive({
  name: '',
  environment_scope: ['prod'],
  db_type_scope: [] as string[],
  sql_type_scope: ['ALTER', 'DROP', 'TRUNCATE', 'UPDATE', 'DELETE', 'INSERT'],
  risk_scope: ['high', 'critical'],
  enabled: true
})
const accessRuleForm = reactive({
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

let pollTimer: number | undefined

const summaryCards = computed(() => {
  const online = instances.value.filter(item => item.status === 'online').length
  const running = jobs.value.filter(item => item.status === 'running').length
  const pending = approvals.value.filter(item => item.status === 'pending').length
  const risky = auditLogs.value.filter(item => ['high', 'critical'].includes(item.risk_level)).length
  return [
    { label: '实例总数', value: instances.value.length, extra: `${online} 在线` },
    { label: '执行作业', value: jobs.value.length, extra: `${running} 运行中` },
    { label: '待审批', value: pending, extra: '高风险 SQL 进入审批' },
    { label: '高风险审计', value: risky, extra: `备份计划 ${backupPlans.value.length} 条` }
  ]
})

const activeInstanceTitle = computed(() => {
  if (!selectedInstance.value) return '请选择实例并输入 SQL'
  return `${selectedInstance.value.name} · ${selectedInstance.value.environment} · ${selectedInstance.value.db_type}`
})

const canRun = computed(() => Boolean(selectedInstance.value?.id && workbench.sql.trim()))

const resetForm = () => {
  Object.assign(form, {
    id: undefined,
    name: '',
    db_type: 'mysql',
    environment: 'dev',
    host: '',
    port: 3306,
    default_database: '',
    username: '',
    password: '',
    read_only: false,
    owner_team: '',
    tags: [],
    extra_config: {}
  })
}

const openCreateDrawer = () => {
  drawerTitle.value = '新增实例'
  resetForm()
  drawerVisible.value = true
}

const editInstance = (row: any) => {
  drawerTitle.value = '编辑实例'
  resetForm()
  Object.assign(form, row, { password: '' })
  drawerVisible.value = true
}

const submitInstance = async () => {
  const payload = { ...form }
  if (payload.id) {
    await dbManagerProApi.updateInstance(payload.id, payload)
    ElMessage.success('实例已更新')
  } else {
    await dbManagerProApi.createInstance(payload)
    ElMessage.success('实例已创建')
  }
  drawerVisible.value = false
  await loadInstances()
}

const loadInstances = async () => {
  const data = await dbManagerProApi.listInstances({ keyword: filters.keyword || undefined, environment: filters.environment || undefined })
  instances.value = Array.isArray(data) ? data : []
  if (!selectedInstance.value && instances.value.length) {
    selectInstance(instances.value[0])
  }
}

const loadJobs = async () => {
  const data = await dbManagerProApi.listJobs()
  jobs.value = Array.isArray(data) ? data : []
}

const loadApprovals = async () => {
  const data = await dbManagerProApi.listApprovals()
  approvals.value = Array.isArray(data) ? data : []
}

const loadAudit = async () => {
  const data = await dbManagerProApi.listAudit()
  auditLogs.value = Array.isArray(data) ? data : []
}

const loadPolicies = async () => {
  const data = await dbManagerProApi.listApprovalPolicies()
  approvalPolicies.value = Array.isArray(data) ? data : []
}

const loadAccessRules = async () => {
  const data = await dbManagerProApi.listAccessRules()
  accessRules.value = Array.isArray(data) ? data : []
}

const loadBackupData = async () => {
  const [plans, records, restores, rollbacks] = await Promise.all([
    dbManagerProApi.listBackupPlans(),
    dbManagerProApi.listBackupRecords(),
    dbManagerProApi.listRestoreJobs(),
    dbManagerProApi.listRollbackJobs()
  ])
  backupPlans.value = Array.isArray(plans) ? plans : []
  backupRecords.value = Array.isArray(records) ? records : []
  restoreJobs.value = Array.isArray(restores) ? restores : []
  rollbackJobs.value = Array.isArray(rollbacks) ? rollbacks : []
}

const selectInstance = async (row: any) => {
  selectedInstance.value = row
  workbench.database = row.default_database || ''
  await loadCompletion()
  await runDiagnosticsAction()
}

const testInstance = async (row: any) => {
  const res = await dbManagerProApi.testInstance(row.id)
  ElMessage.success(res.msg || '测试完成')
  await loadInstances()
}

const formatSqlAction = async () => {
  if (!workbench.sql.trim()) return
  const res = await dbManagerProApi.formatSql(workbench.sql)
  workbench.sql = res.formatted_sql || workbench.sql
}

const explainSqlAction = async () => {
  if (!selectedInstance.value) return
  explainResult.value = await dbManagerProApi.explainSql(selectedInstance.value.id, workbench.database, workbench.sql)
}

const loadCompletion = async (keyword = '') => {
  if (!selectedInstance.value?.id) return
  const res = await dbManagerProApi.completion(selectedInstance.value.id, workbench.database, keyword)
  completionItems.value = Array.isArray(res.items) ? res.items : []
}

const handleCompletionKeywordChange = async (keyword: string) => {
  await loadCompletion(keyword)
}

const reviewSqlAction = async () => {
  if (!selectedInstance.value) return
  const res = await dbManagerProApi.reviewSql(selectedInstance.value.id, workbench.database, workbench.sql)
  aiReview.value = res.report
}

const executeSqlAction = async () => {
  if (!selectedInstance.value) return
  const res = await dbManagerProApi.createJob(selectedInstance.value.id, workbench.database, workbench.sql, workbench.executeMode)
  activeJob.value = res.job
  aiReview.value = res.report
  activePane.value = 'logs'
  await loadJobs()
  if (activeJob.value?.id) {
    await loadJobDetail(activeJob.value)
  }
}

const loadJobDetail = async (row: any) => {
  const detail = await dbManagerProApi.getJobDetail(row.id)
  activeJob.value = detail
  jobLogs.value = await dbManagerProApi.getJobLogs(row.id)
  try {
    jobResult.value = await dbManagerProApi.getJobResult(row.id)
  } catch {
    jobResult.value = { columns_json: [], rows_json: [] }
  }
}

const cancelJobAction = async () => {
  if (!activeJob.value?.id) return
  await dbManagerProApi.cancelJob(activeJob.value.id)
  await loadJobDetail(activeJob.value)
  await loadAudit()
}

const pauseJobAction = async () => {
  if (!activeJob.value?.id) return
  await dbManagerProApi.pauseJob(activeJob.value.id)
  await loadJobDetail(activeJob.value)
}

const resumeJobAction = async () => {
  if (!activeJob.value?.id) return
  await dbManagerProApi.resumeJob(activeJob.value.id)
  await loadJobDetail(activeJob.value)
}

const approve = async (row: any) => {
  await dbManagerProApi.approve(row.id)
  ElMessage.success('审批已通过')
  await Promise.all([loadApprovals(), loadJobs()])
}

const reject = async (row: any) => {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝审批', { confirmButtonText: '确认', cancelButtonText: '取消' })
  await dbManagerProApi.reject(row.id, value)
  ElMessage.success('审批已拒绝')
  await Promise.all([loadApprovals(), loadJobs()])
}

const openPolicyDrawer = () => {
  Object.assign(policyForm, {
    name: '',
    environment_scope: ['prod'],
    db_type_scope: selectedInstance.value ? [selectedInstance.value.db_type] : [],
    sql_type_scope: ['ALTER', 'DROP', 'TRUNCATE', 'UPDATE', 'DELETE', 'INSERT'],
    risk_scope: ['high', 'critical'],
    enabled: true
  })
  policyDrawerVisible.value = true
}

const submitPolicy = async () => {
  await dbManagerProApi.createApprovalPolicy({ ...policyForm })
  policyDrawerVisible.value = false
  ElMessage.success('审批策略已创建')
  await loadPolicies()
}

const openAccessRuleDrawer = () => {
  Object.assign(accessRuleForm, {
    name: '',
    user_id: undefined,
    group_name: '',
    instance: selectedInstance.value?.id,
    database_pattern: workbench.database || '*',
    table_pattern: '*',
    sql_types: [],
    actions: ['view', 'query'],
    enabled: true
  })
  accessDrawerVisible.value = true
}

const submitAccessRule = async () => {
  await dbManagerProApi.createAccessRule({ ...accessRuleForm })
  accessDrawerVisible.value = false
  ElMessage.success('访问规则已创建')
  await loadAccessRules()
}

const createBackupPlanAction = async () => {
  if (!selectedInstance.value) return
  const { value } = await ElMessageBox.prompt('请输入备份计划名称', '新增备份计划', { confirmButtonText: '创建', cancelButtonText: '取消' })
  await dbManagerProApi.createBackupPlan({
    instance: selectedInstance.value.id,
    name: value,
    backup_type: 'logical',
    schedule_expr: '0 2 * * *',
    retention_days: 7,
    storage_uri: 's3://shark-platform-backup',
    enabled: true
  })
  ElMessage.success('备份计划已创建')
  await loadBackupData()
}

const runBackup = async (row: any) => {
  await dbManagerProApi.runBackupPlan(row.id)
  ElMessage.success('已生成备份记录')
  await loadBackupData()
}

const createRestoreJobAction = async () => {
  if (!selectedInstance.value) return
  await dbManagerProApi.createRestoreJob({
    instance: selectedInstance.value.id,
    restore_mode: 'point_in_time',
    target_txn_id: `manual-${Date.now()}`
  })
  ElMessage.success('恢复任务已创建')
  await loadBackupData()
}

const createRollbackFromSelectedAudit = async () => {
  const audit = auditLogs.value[0]
  if (!audit) return
  await dbManagerProApi.createRollbackJob({ source_audit: audit.id })
  ElMessage.success('已生成回滚任务')
  await loadBackupData()
}

const runRollback = async (row: any) => {
  await dbManagerProApi.executeRollbackJob(row.id)
  ElMessage.success('回滚任务已启动')
  await loadBackupData()
}

const runDiagnosticsAction = async () => {
  if (!selectedInstance.value?.id) return
  diagnosticsReport.value = await dbManagerProApi.getDiagnostics(selectedInstance.value.id)
}

const exportAuditAction = async () => {
  const blob = await dbManagerProApi.exportAudit()
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'db_audit_export.csv'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

const riskTagType = (risk: string) => {
  if (risk === 'low') return 'success'
  if (risk === 'medium') return 'warning'
  return 'danger'
}

const alertType = (decision: string) => {
  if (decision === 'allow') return 'success'
  if (decision === 'warn') return 'warning'
  return 'error'
}

const refreshAll = async () => {
  await Promise.all([loadInstances(), loadJobs(), loadApprovals(), loadAudit(), loadPolicies(), loadAccessRules(), loadBackupData()])
  if (activeJob.value?.id) {
    await loadJobDetail(activeJob.value)
  }
}

onMounted(async () => {
  await refreshAll()
  pollTimer = window.setInterval(refreshAll, 5000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.dbm-pro-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.summary-card {
  border-radius: 12px;
}
.summary-label {
  color: #8c8c8c;
  font-size: 13px;
}
.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #1d2129;
  margin-top: 8px;
}
.summary-extra {
  margin-top: 8px;
  color: #1677ff;
  font-size: 12px;
}
.content-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 12px;
  min-height: calc(100vh - 240px);
}
.instance-panel,
.workspace-card,
.analysis-card,
.result-card {
  border-radius: 12px;
}
.workspace-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.workspace-bottom {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 12px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.workspace-title {
  font-size: 18px;
  font-weight: 600;
}
.workspace-subtitle {
  color: #8c8c8c;
  font-size: 12px;
  margin-top: 4px;
}
.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.editor-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.database-input {
  max-width: 260px;
}
.mode-select {
  width: 160px;
}
.sql-editor :deep(textarea) {
  font-family: Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
.log-stream {
  min-height: 240px;
  max-height: 260px;
  overflow: auto;
  background: #0f172a;
  color: #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  font-family: Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}
.log-line {
  margin-bottom: 6px;
  line-height: 1.5;
}
.log-line.error {
  color: #f87171;
}
.log-line.warning {
  color: #fbbf24;
}
.log-line.success {
  color: #4ade80;
}
.diag-title {
  font-weight: 600;
  color: #1d2129;
}
.diag-desc {
  margin-top: 4px;
  color: #4b5563;
}
.mb-12 {
  margin-bottom: 12px;
}
.mt-12 {
  margin-top: 12px;
}
</style>
