<template>
  <div class="db-manager-layout">
    <!-- Left Sidebar -->
    <div class="sidebar">
      <div class="sidebar-toolbar">
        <span class="sidebar-title">Database Manager</span>
        <div class="toolbar-actions">
          <el-tooltip content="Refresh" placement="bottom">
            <el-button text circle size="small" @click="loadConnections">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="New Query Console" placement="bottom">
            <el-button type="info" text circle size="small" @click="showQuerySelector = true">
              <el-icon><Monitor /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="New Connection" placement="bottom">
            <el-button type="primary" text circle size="small" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
      
      <div class="tree-container">
        <el-tree
          :data="treeData"
          :props="defaultProps"
          node-key="id"
          highlight-current
          :load="loadNode"
          lazy
          @node-click="handleNodeClick"
          :expand-on-click-node="false"
          :indent="24"
        >
          <template #default="{ node, data }">
            <div 
              class="custom-tree-item" 
              :class="{ 
                'is-conn': data.type === 'conn', 
                'is-active': data.type === 'conn' && (node.expanded || node.isCurrent),
                'is-db': data.type === 'db' 
              }"
            >
              <!-- Icons based on type -->
              <div class="tree-icon-container">
                <template v-if="data.type === 'conn'">
                   <!-- MySQL Icon -->
                   <div v-if="data.dbType === 'mysql'" class="db-icon mysql" :class="{ 'active': node.expanded || node.isCurrent }">
                      <img src="@/assets/images/mysql-logo.svg" alt="MySQL" />
                   </div>
                   <!-- Redis Icon -->
                   <div v-else-if="data.dbType === 'redis'" class="db-icon redis" :class="{ 'active': node.expanded || node.isCurrent }">
                      <img src="@/assets/images/redis-logo.svg" alt="Redis" />
                   </div>
                   <!-- Mongo Icon -->
                   <div v-else-if="data.dbType === 'mongo'" class="db-icon mongo" :class="{ 'active': node.expanded || node.isCurrent }">
                      <img src="@/assets/images/mongo-logo.svg" alt="Mongo" />
                   </div>
                   <!-- RabbitMQ Icon -->
                   <div v-else-if="data.dbType === 'rabbitmq'" class="db-icon rabbitmq" :class="{ 'active': node.expanded || node.isCurrent }">
                      <img src="@/assets/images/rabbitmq-logo.svg" alt="RabbitMQ" />
                   </div>
                   <!-- Default Icon -->
                   <div v-else class="db-icon default" :class="{ 'active': node.expanded || node.isCurrent }">
                      <el-icon><Connection /></el-icon>
                   </div>
                </template>
                
                <!-- Database Icon -->
                <div v-else-if="data.type === 'db'" class="sub-icon db">
                   <el-icon><Coin /></el-icon>
                </div>
                
                <!-- Table Icon -->
              <div v-else-if="data.type === 'table'" class="sub-icon table">
                 <!-- Special Icon for Redis "Folders" -->
                 <el-icon v-if="data.dbType === 'redis' && data.label.endsWith(':*')"><Folder /></el-icon>
                 <el-icon v-else><Grid /></el-icon>
              </div>
              </div>
              
              <span class="custom-tree-label" :title="node.label">{{ node.label }}</span>
              
              <!-- Database Type Badge (Only for Connections) -->
              <div v-if="data.type === 'conn'" class="conn-badge" :class="data.dbType">
                {{ data.dbType.toUpperCase() }}
              </div>
              
              <!-- Hover Actions -->
              <div class="custom-tree-actions" @click.stop>
                <template v-if="data.type === 'conn' || data.type === 'db'">
                  <el-tooltip content="Query Console" placement="top" :show-after="500">
                    <el-button link type="primary" size="small" @click="openQueryTab(data)">
                      <el-icon><Monitor /></el-icon>
                    </el-button>
                  </el-tooltip>
                </template>
                <template v-if="data.type === 'conn'">
                  <el-tooltip content="Delete Connection" placement="top" :show-after="500">
                    <el-button link type="danger" size="small" @click="handleDeleteConn(data)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </el-tooltip>
                </template>
              </div>
            </div>
          </template>
        </el-tree>
      </div>
    </div>

    <!-- Right Workspace -->
    <div class="workspace">
      <!-- LEVEL 1: Connection Tabs -->
      <el-tabs
        v-if="openConnections.length > 0"
        v-model="activeConnectionId"
        type="card"
        class="connection-tabs"
        @tab-remove="handleConnectionClose"
      >
        <el-tab-pane
          v-for="conn in openConnections"
          :key="conn.id"
          :name="conn.id"
        >
          <template #label>
             <div class="conn-tab-label">
                <span class="conn-indicator" :class="conn.dbType"></span>
                <!-- Synced SVG Icons for Right Tabs -->
                <div class="conn-tab-icon" :class="conn.dbType">
                  <img v-if="conn.dbType === 'mysql'" src="@/assets/images/mysql-logo.svg" alt="MySQL" />
                  <img v-else-if="conn.dbType === 'redis'" src="@/assets/images/redis-logo.svg" alt="Redis" />
                  <img v-else-if="conn.dbType === 'mongo'" src="@/assets/images/mongo-logo.svg" alt="Mongo" />
                  <img v-else-if="conn.dbType === 'rabbitmq'" src="@/assets/images/rabbitmq-logo.svg" alt="RabbitMQ" />
                  <el-icon v-else><Connection /></el-icon>
                </div>
                <span class="conn-name">{{ conn.name }}</span>
             </div>
          </template>

          <!-- LEVEL 2: Page Tabs (Tables, Queries, etc.) -->
          <el-tabs 
            v-model="connActiveTabs[conn.id]" 
            type="border-card" 
            editable 
            class="main-tabs"
            @edit="(target, action) => handleTabEdit(target, action, conn.id)"
          >
            <el-tab-pane
              v-for="item in getConnTabs(conn.id)"
              :key="item.name"
              :label="item.title"
              :name="item.name"
            >
              <template #label>
                <div class="custom-tab-label">
                  <div class="tab-icon-wrapper">
                    <el-icon v-if="item.type === 'query'"><Monitor /></el-icon>
                    <el-icon v-else-if="item.type === 'overview'"><Coin /></el-icon>
                    <el-icon v-else><Grid /></el-icon>
                  </div>
                  <span class="tab-title-text">{{ item.title }}</span>
                </div>
              </template>

              <!-- VIEW: DB OVERVIEW -->
              <div v-if="item.type === 'overview'" class="tab-view overview-view">
                <!-- Context Breadcrumb -->
                <div class="context-breadcrumb">
                   <el-tag size="small" type="info" effect="plain">{{ item.connName }}</el-tag>
                   <span class="breadcrumb-separator">/</span>
                   <span class="breadcrumb-current">{{ item.dbName }}</span>
                </div>

                <div class="view-toolbar">
                   <div class="editor-info">
                      <el-icon><Coin /></el-icon>
                      <span class="editor-title" style="margin-left: 8px">{{ item.dbName }} Overview</span>
                   </div>
                   <div class="right-tools">
                     <el-tag type="info">{{ item.data.length }} Tables / Collections</el-tag>
                   </div>
                </div>
                
                <div class="overview-content">
                  <!-- Charts Section -->
                  <div class="charts-row" v-if="item.chartRowOption && item.chartSizeOption">
                    <el-card shadow="never" class="chart-card">
                       <template #header><span class="chart-title">{{ item.rowChartTitle || 'Top Tables by Rows' }}</span></template>
                       <v-chart class="chart" :option="item.chartRowOption" autoresize />
                    </el-card>
                    <el-card shadow="never" class="chart-card">
                       <template #header><span class="chart-title">{{ item.sizeChartTitle || 'Storage Distribution' }}</span></template>
                       <v-chart class="chart" :option="item.chartSizeOption" autoresize />
                    </el-card>
                  </div>

                  <!-- Table Section -->
                  <div class="table-section">
                    <el-table
                      :data="item.data"
                      border
                      stripe
                      height="100%"
                      style="width: 100%"
                      size="default"
                    >
                      <el-table-column prop="name" label="Name" min-width="200" sortable>
                        <template #default="{ row }">
                           <div style="display: flex; align-items: center; gap: 8px;">
                              <el-icon><Grid /></el-icon>
                              <span style="font-weight: 500">{{ row.name }}</span>
                           </div>
                        </template>
                      </el-table-column>
                      <el-table-column prop="rows" label="Rows" width="120" sortable align="right" />
                      <el-table-column prop="size" label="Size" width="120" sortable align="right" />
                      <el-table-column prop="engine" label="Engine" width="120" />
                      <el-table-column prop="created" label="Created" width="180" />
                      <el-table-column prop="updated" label="Modified" width="180" />
                    </el-table>
                  </div>
                </div>
              </div>

              <!-- VIEW: TABLE DATA -->
              <div v-if="item.type === 'table'" class="tab-view table-view">
                <div class="view-toolbar">
                  <div class="left-tools">
                    <el-input 
                      v-model="item.searchQuery" 
                      :placeholder="getSearchPlaceholder(item.dbType)" 
                      style="width: 350px" 
                      clearable
                      @keyup.enter="refreshTab(item)"
                      @clear="refreshTab(item)"
                    >
                      <template #prefix><el-icon><Search /></el-icon></template>
                    </el-input>
                    <el-button type="primary" plain @click="refreshTab(item)">
                      <el-icon><Refresh /></el-icon> Refresh
                    </el-button>
                    <div class="divider-vertical"></div>
                    <el-tooltip content="Toggle Details View" placement="bottom">
                      <el-button 
                        :type="item.showDetails ? 'primary' : 'info'" 
                        text 
                        bg
                        @click="item.showDetails = !item.showDetails"
                      >
                        <el-icon><View /></el-icon>
                      </el-button>
                    </el-tooltip>
                  </div>
                  <div class="right-tools">
                    <el-tag type="info" effect="plain">Total: {{ item.total }}</el-tag>
                  </div>
                </div>
                
                <div class="data-view-container">
                  <div class="table-wrapper">
                    <el-table
                      v-loading="item.loading"
                      :data="item.data"
                      border
                      stripe
                      height="100%"
                      style="width: 100%"
                      size="small"
                      class="data-table"
                      highlight-current-row
                      @current-change="(val) => handleRowSelect(val, item)"
                      :cell-style="{ padding: '4px 0' }"
                      :header-cell-style="{ background: '#f5f7fa', color: '#606266', padding: '6px 0' }"
                    >
                      <el-table-column type="index" width="60" label="#" fixed align="center" />
                      <el-table-column
                        v-for="col in item.headers"
                        :key="col"
                        :prop="col"
                        :label="col"
                        :min-width="getColumnWidth(col, item.data)"
                        show-overflow-tooltip
                        sortable
                        :fixed="isIdColumn(col) ? 'left' : false"
                      >
                        <template #default="{ row }">
                          <!-- Status/Level Tags -->
                          <el-tag 
                            v-if="isStatusColumn(col) && row[col]" 
                            :type="getStatusColor(row[col])" 
                            size="small" 
                            effect="plain"
                            class="status-tag"
                          >
                            {{ row[col] }}
                          </el-tag>
                          
                          <!-- JSON/Object formatting -->
                          <span v-else-if="typeof row[col] === 'object' && row[col] !== null" class="code-font">
                            {{ JSON.stringify(row[col]) }}
                          </span>
                          
                          <!-- ID/Key formatting -->
                          <span v-else-if="isIdColumn(col)" class="code-font id-text">
                            {{ row[col] }}
                          </span>
                          
                          <!-- Standard Text -->
                          <span v-else>{{ row[col] }}</span>
                        </template>
                      </el-table-column>
                      
                      <!-- Fixed Actions Column for Rightmost Visibility -->
                      <el-table-column label="Action" width="70" align="center" fixed="right">
                        <template #default="{ row }">
                          <el-tooltip content="View Details" placement="top" :enterable="false">
                            <el-button 
                              link 
                              type="primary" 
                              size="small" 
                              @click.stop="handleRowSelect(row, item); item.showDetails = true"
                            >
                              <el-icon><View /></el-icon>
                            </el-button>
                          </el-tooltip>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>

                  <!-- Right Details Panel -->
                  <div class="details-panel" v-if="item.showDetails">
                    <div class="details-header">
                      <span class="details-title">Row Details</span>
                      <el-button link @click="item.showDetails = false"><el-icon><Close /></el-icon></el-button>
                    </div>
                    <div class="details-body">
                      <el-empty v-if="!item.selectedRow" description="Select a row to view details" :image-size="60" />
                      <div v-else class="details-list">
                        <div v-for="(val, key) in item.selectedRow" :key="key" class="detail-item">
                          <div class="detail-key">{{ key }}</div>
                          <div class="detail-value">
                            <span v-if="typeof val === 'object' && val !== null" class="code-font">{{ JSON.stringify(val, null, 2) }}</span>
                            <span v-else>{{ val }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div class="pagination-bar">
                  <el-pagination
                    background
                    small
                    v-model:current-page="item.page"
                    v-model:page-size="item.pageSize"
                    :page-sizes="[10, 20, 50, 100, 500]"
                    layout="total, sizes, prev, pager, next, jumper"
                    :total="item.total"
                    @size-change="refreshTab(item)"
                    @current-change="refreshTab(item)"
                  />
                </div>
              </div>

              <div v-if="item.type === 'query'" class="tab-view query-view">
                <div class="query-editor-container">
                  <div class="editor-toolbar">
                    <div class="editor-info">
                      <el-icon><Monitor /></el-icon>
                      <div style="display: flex; flex-direction: column;">
                        <span class="editor-title">{{ item.dbName || 'Global Console' }}</span>
                        <span class="editor-subtitle">{{ item.connName }} ({{ item.dbType }})</span>
                      </div>
                    </div>
                    <el-button type="success" size="small" @click="runQuery(item)" :loading="item.loading">
                      <el-icon><VideoPlay /></el-icon> Run Query
                    </el-button>
                  </div>
                  <div class="editor-wrapper">
                    <el-input 
                      v-model="item.queryInput" 
                      type="textarea" 
                      resize="none" 
                      :placeholder="getQueryPlaceholder(item.dbType)" 
                      class="code-editor-input"
                      spellcheck="false"
                      @keydown.ctrl.enter.prevent="runQuery(item)"
                      @keydown.meta.enter.prevent="runQuery(item)"
                    />
                  </div>
                  <div class="editor-footer">
                    <el-icon><InfoFilled /></el-icon>
                    <small class="hint">{{ getQueryHint(item.dbType) }}</small>
                  </div>
                </div>
                
                <div class="result-area">
                  <div class="result-header">
                    <span>Execution Result</span>
                    <el-tag v-if="item.total >= 0" size="small" type="success">{{ item.total }} rows</el-tag>
                  </div>
                  <el-table
                    v-loading="item.loading"
                    :data="item.data"
                    border
                    stripe
                    height="100%"
                    style="width: 100%"
                    size="small"
                    empty-text="No result or query not executed"
                  >
                    <el-table-column
                      v-for="col in item.headers"
                      :key="col"
                      :prop="col"
                      :label="col"
                      min-width="120"
                      show-overflow-tooltip
                    >
                      <template #default="{ row, column }">
                        <span v-if="typeof row[column.property] === 'object' && row[column.property] !== null">
                          {{ JSON.stringify(row[column.property]) }}
                        </span>
                        <span v-else>{{ row[column.property] }}</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>

            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
      
      <div v-else class="empty-workspace">
        <el-empty description="No Active Connections">
          <template #image>
            <el-icon :size="60" color="#909399"><DataBoard /></el-icon>
          </template>
          <template #description>
            <p>Select a table or connection from the sidebar to start.</p>
          </template>
          <el-button type="primary" @click="showQuerySelector = true">Open Query Console</el-button>
        </el-empty>
      </div>
    </div>

    <!-- Connection Dialog -->
    <el-dialog v-model="showAddDialog" title="New Connection" width="500px" destroy-on-close>
      <el-form :model="form" label-width="100px" class="conn-form">
        <el-form-item label="Name">
          <el-input v-model="form.name" placeholder="My Connection" />
        </el-form-item>
        <el-form-item label="Type">
          <el-select v-model="form.type" placeholder="Select type" style="width: 100%">
            <el-option label="MySQL" value="mysql" />
            <el-option label="Redis" value="redis" />
            <el-option label="MongoDB" value="mongo" />
            <el-option label="RabbitMQ" value="rabbitmq" />
          </el-select>
        </el-form-item>
        
        <template v-if="form.type === 'redis'">
          <el-form-item label="Mode">
            <el-radio-group v-model="formMode">
              <el-radio label="standalone">Standalone</el-radio>
              <el-radio label="cluster">Cluster</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>
        
        <template v-if="form.type === 'mongo'">
          <el-form-item label="Mode">
             <el-switch v-model="useUri" active-text="URI String" inactive-text="Standard" />
          </el-form-item>
        </template>

        <el-form-item :label="useUri ? 'URI' : 'Host'">
          <el-input v-model="form.host" :placeholder="getHostPlaceholder" />
        </el-form-item>
        
        <el-form-item label="Port" v-if="!useUri">
          <el-input v-model.number="form.port" type="number" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Username" v-if="!useUri">
          <el-input v-model="form.user" />
        </el-form-item>
        <el-form-item label="Password" v-if="!useUri">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        
        <el-form-item :label="form.type === 'rabbitmq' ? 'Virtual Host' : 'Database'" v-if="!useUri">
          <el-input v-model="form.database" :placeholder="form.type === 'rabbitmq' ? 'Default: /' : 'Optional default DB'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testConnection" :loading="testing">Test Connection</el-button>
        <el-button @click="showAddDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveConnection" :loading="saving">Save</el-button>
      </template>
    </el-dialog>

    <!-- Query Selector Dialog -->
    <el-dialog v-model="showQuerySelector" title="Select Connection for Query" width="400px">
       <el-form>
         <el-form-item label="Connection">
           <el-select v-model="selectedQueryConn" placeholder="Select a connection" style="width: 100%" value-key="id">
             <el-option v-for="c in connections" :key="c.id" :label="c.name" :value="c" />
           </el-select>
         </el-form-item>
       </el-form>
       <template #footer>
         <el-button @click="showQuerySelector = false">Cancel</el-button>
         <el-button type="primary" @click="startGlobalQuery" :disabled="!selectedQueryConn">Open Console</el-button>
       </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed, nextTick } from 'vue'
import { dbApi, type DBConnection } from '@/api/db_manager'
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { PieChart, BarChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from "echarts/components";
import VChart, { THEME_KEY } from "vue-echarts";

use([
  CanvasRenderer,
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
]);

// ... existing code ...


// --- State ---
const showAddDialog = ref(false)
const showQuerySelector = ref(false)
const testing = ref(false)
const saving = ref(false)
const treeData = ref<any[]>([])
const tabs = ref<any[]>([])
const connections = ref<any[]>([])
const selectedQueryConn = ref<any>(null)

const activeConnectionId = ref('')
const connActiveTabs = reactive<Record<string, string>>({}) // { connId: activeTabName }

// Form State
const form = reactive<DBConnection>({
  name: '',
  type: 'mysql',
  host: 'localhost',
  port: 3306,
  user: 'root',
  password: '',
  database: ''
})
const formMode = ref('standalone')
const useUri = ref(false)
const useSSL = ref(false)

// Watch type change to reset defaults
watch(() => form.type, (newType) => {
  formMode.value = 'standalone'
  useUri.value = false
  useSSL.value = false
  
  if (newType === 'mysql') form.port = 3306
  if (newType === 'redis') form.port = 6379
  if (newType === 'mongo') form.port = 27017
  if (newType === 'rabbitmq') form.port = 5672
  
  // Clear name, but keep other fields like host/user/pass if useful
  form.name = '' 
})

// --- Computed ---
const openConnections = computed(() => {
  const connMap = new Map()
  tabs.value.forEach(t => {
    if (!connMap.has(t.connId)) {
      // Find connection details
      const connNode = connections.value.find(c => c.id === t.connId)
      connMap.set(t.connId, {
        id: t.connId,
        name: t.connName || (connNode ? connNode.name : 'Unknown'),
        dbType: t.dbType || (connNode ? connNode.dbType : 'mysql')
      })
    }
  })
  return Array.from(connMap.values())
})

const getConnTabs = (connId: string) => {
  return tabs.value.filter(t => t.connId === connId)
}

const getHostPlaceholder = computed(() => {
  if (useUri.value) return 'mongodb://user:pass@host:port/db'
  if (form.type === 'redis' && formMode.value === 'cluster') return 'node1:6379,node2:6379'
  return 'localhost'
})

const defaultProps = {
  children: 'children',
  label: 'label',
  isLeaf: 'leaf'
}

// --- Persistence ---
watch([tabs, activeConnectionId, connActiveTabs], () => {
  try {
    const tabsToSave = tabs.value.map((t: any) => ({
      ...t,
      data: t.data.length > 500 ? [] : t.data, // Limit saved data
      loading: false
    }))
    localStorage.setItem('db_manager_tabs_v4', JSON.stringify(tabsToSave))
    localStorage.setItem('db_manager_active_conn_v4', activeConnectionId.value)
    localStorage.setItem('db_manager_conn_active_tabs_v4', JSON.stringify(connActiveTabs))
  } catch (e) {
    // Ignore storage errors
  }
}, { deep: true })

// --- Methods ---

const loadConnections = async () => {
  try {
    const res = await dbApi.listConnections()
    // @ts-ignore
    const data = Array.isArray(res) ? res : (res.data || [])
    const list = data.map((c: any) => ({
      id: c.id,
      label: c.name,
      name: c.name,
      type: 'conn',
      dbType: c.type,
      database: c.database,
      leaf: false
    }))
    treeData.value = list
    connections.value = list
    
    // Restore tabs after connections loaded
    restoreTabs()
  } catch (e) {
    console.error('Failed to load connections', e)
    // Clear list on error to remove ghost items
    treeData.value = []
    connections.value = []
  }
}

const restoreTabs = () => {
  const savedTabs = localStorage.getItem('db_manager_tabs_v4')
  if (savedTabs) {
    try {
      tabs.value = JSON.parse(savedTabs)
      // Enforce minimum pageSize of 50 for legacy tabs
      tabs.value.forEach(t => {
          if (!t.pageSize || t.pageSize < 50) t.pageSize = 50
      })
    } catch {}
  }
  
  const savedActiveConn = localStorage.getItem('db_manager_active_conn_v4')
  if (savedActiveConn) activeConnectionId.value = savedActiveConn
  
  const savedConnTabs = localStorage.getItem('db_manager_conn_active_tabs_v4')
  if (savedConnTabs) {
    try {
      Object.assign(connActiveTabs, JSON.parse(savedConnTabs))
    } catch {}
  }

  // Auto-refresh tabs that were saved without data (lazy reload)
  nextTick(() => {
    tabs.value.forEach(tab => {
       if (!tab.loading && (!tab.data || (Array.isArray(tab.data) && tab.data.length === 0))) {
          if (tab.type === 'table' || tab.type === 'overview') {
             refreshTab(tab)
          }
       }
    })
  })
}

onMounted(() => {
  loadConnections()
})

const loadNode = async (node: any, resolve: any) => {
  if (node.level === 0) {
    return resolve(treeData.value)
  }
  
  if (node.data.type === 'conn') {
    try {
      const res = await dbApi.getStructure(node.data.id)
      const dbs = Object.keys(res).map(dbName => ({
        id: `${node.data.id}:${dbName}`,
        label: dbName,
        type: 'db',
        connId: node.data.id,
        leaf: false,
        tables: res[dbName]
      }))
      resolve(dbs)
    } catch (e: any) {
      // If 404, the connection is gone, remove it from tree
      if (e.response && e.response.status === 404) {
        ElMessage.error('Connection not found, refreshing list...')
        loadConnections()
      } else {
        ElMessage.error(e.message || 'Failed to load structure')
      }
      resolve([])
    }
  } else if (node.data.type === 'db') {
    // Check if we have table details or just strings
    const tables = node.data.tables.map((t: any) => {
       if (typeof t === 'string') {
          return {
            id: `${node.data.id}:${t}`,
            label: t,
            type: 'table',
            connId: node.data.connId,
            dbName: node.label,
            leaf: true
          }
       } else {
          // It's a detailed object
          return {
            id: `${node.data.id}:${t.name}`,
            label: t.name,
            type: 'table',
            connId: node.data.connId,
            dbName: node.label,
            leaf: true,
            // Pass details along
            details: t
          }
       }
    })
    resolve(tables)
  } else {
    resolve([])
  }
}

const handleNodeClick = (data: any) => {
  if (data.type === 'table') {
    openTab(data)
  } else if (data.type === 'db') {
    openDbOverviewTab(data)
  }
}

const openDbOverviewTab = (data: any) => {
  const tabName = `overview_${data.id}`
  const existing = tabs.value.find(t => t.name === tabName)
  
  // Set Active Connection
  activeConnectionId.value = data.connId
  connActiveTabs[data.connId] = tabName

  if (existing) {
    // If the existing tab has no data (e.g. from a previous failed load), refresh it
    if (!existing.data || existing.data.length === 0) {
       refreshOverview(existing)
    }
    return
  }

  const connNode = treeData.value.find((c: any) => c.id === data.connId)
  const connName = connNode ? connNode.name : ''
  // Use data.dbType if available (it was added to the node), otherwise fallback to connection type
  const dbType = data.dbType || (connNode ? connNode.dbType : 'mysql')

  // ... data processing ...
  const tableList = (data.tables || []).map((t: any) => {
    if (typeof t === 'string') return { name: t }
    return t
  })

  // Normalize dbType for checking
  const isRedis = dbType && dbType.toLowerCase().includes('redis')

  const newTab = reactive({
    name: tabName,
    title: `Overview: ${data.label}`,
    type: 'overview',
    connId: data.connId,
    connName: connName,
    dbName: data.label,
    dbType: dbType, // Important for icon
    data: tableList,
    loading: false,
    chartRowOption: getRowChartOption(tableList),
    chartSizeOption: getSizeChartOption(tableList, isRedis ? 'rows' : 'size'),
    rowChartTitle: isRedis ? 'Top Prefixes by Count' : 'Top Tables by Rows',
    sizeChartTitle: isRedis ? 'Key Distribution' : 'Storage Distribution'
  })
  
  tabs.value.push(newTab)
  connActiveTabs[data.connId] = tabName
  
  // If data is empty (initial load failed or just empty), try to fetch fresh structure
  if (tableList.length === 0 || (tableList.length === 1 && tableList[0].name.includes('Enter Queue Name'))) {
      refreshOverview(newTab)
  }
}

const refreshOverview = async (tab: any) => {
  tab.loading = true
  try {
    // Re-fetch structure for the connection
    const res = await dbApi.getStructure(tab.connId)
    
    // Extract specific DB data
    let newTables = []
    if (res[tab.dbName]) {
        newTables = res[tab.dbName]
    } else if (tab.dbType.includes('redis') || tab.dbType === 'rabbitmq') {
        // Redis/RabbitMQ often return single keys like 'db0' or 'Queues'
        // If tab.dbName matches, use it.
        newTables = res[tab.dbName] || []
    }

    // Process data
    const tableList = newTables.map((t: any) => {
        if (typeof t === 'string') return { name: t }
        return t
    })
    
    tab.data = tableList
    
    // Update charts
    const isRedis = tab.dbType && tab.dbType.toLowerCase().includes('redis')
    tab.chartRowOption = getRowChartOption(tableList)
    tab.chartSizeOption = getSizeChartOption(tableList, isRedis ? 'rows' : 'size')
    
  } catch (e: any) {
    ElMessage.error(e.message || 'Failed to refresh overview')
  } finally {
    tab.loading = false
  }
}

// --- Chart Helpers ---
const parseSize = (sizeStr: string) => {
  if (!sizeStr || sizeStr === '-') return 0
  const num = parseFloat(sizeStr.split(' ')[0])
  if (sizeStr.includes('MB')) return num * 1024 * 1024
  if (sizeStr.includes('KB')) return num * 1024
  return num
}

const getRowChartOption = (data: any[]) => {
  // Top 10 tables by rows
  const sorted = [...data]
    .filter(t => t.rows !== '-' && t.rows > 0)
    .sort((a, b) => b.rows - a.rows)
    .slice(0, 10)
    
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', name: 'Rows' },
    yAxis: { type: 'category', data: sorted.map(t => t.name).reverse(), axisLabel: { width: 100, overflow: 'truncate' } },
    series: [
      {
        name: 'Row Count',
        type: 'bar',
        data: sorted.map(t => t.rows).reverse(),
        itemStyle: { color: '#409EFF' },
        barWidth: '60%'
      }
    ]
  }
}

const getSizeChartOption = (data: any[]) => {
  // Top tables by size
  const sorted = [...data]
    .map(t => ({ ...t, sizeBytes: parseSize(t.size) }))
    .filter(t => t.sizeBytes > 0)
    .sort((a, b) => b.sizeBytes - a.sizeBytes)
    .slice(0, 8)

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} Bytes ({d}%)' },
    legend: { 
      orient: 'vertical', 
      left: '0', 
      top: 'middle', 
      align: 'left',
      itemGap: 10,
      type: 'scroll',
      width: '45%', // Restrict width to avoid overlap
      formatter: (name: string) => {
         // Truncate long names in legend
         return name.length > 20 ? name.substring(0, 18) + '...' : name
      },
      tooltip: { show: true } // Show full name on hover
    },
    series: [
      {
        name: 'Storage Size',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['75%', '50%'], // Move pie chart further right
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: '14', fontWeight: 'bold' }
        },
        labelLine: { show: false },
        data: sorted.map(t => ({ value: t.value, name: t.name }))
      }
    ]
  }
}

const handleDeleteConn = async (data: any) => {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this connection?', 'Warning', {
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
      type: 'warning'
    })
    await dbApi.deleteConnection(data.id)
    ElMessage.success('Deleted')
    loadConnections()
  } catch {}
}

const openTab = (data: any) => {
  const tabName = data.id
  const existing = tabs.value.find(t => t.name === tabName)
  
  // Always switch to the target connection first
  activeConnectionId.value = data.connId
  // Then activate the tab within that connection
  connActiveTabs[data.connId] = tabName
  
  if (existing) {
    // If tab exists but has no data (and not loading), refresh it
    // This solves the "manual refresh" issue if a previous load failed
    if (!existing.loading && (!existing.data || existing.data.length === 0)) {
       refreshTab(existing)
    }
    return
  }
  
  const connNode = treeData.value.find((c: any) => c.id === data.connId)
  const dbType = connNode ? connNode.dbType : 'mysql'
  const connName = connNode ? connNode.name : ''

  const newTab = {
    name: tabName,
    title: `${data.label}`,
    type: 'table',
    connId: data.connId,
    connName: connName,
    dbName: data.dbName,
    tableName: data.label,
    dbType: dbType,
    searchQuery: '', 
    data: [],
    headers: [],
    loading: false,
    page: 1,
    pageSize: 50,
    total: 0,
    showDetails: false, // Default to hidden
    selectedRow: null
  }
  
  tabs.value.push(newTab)
  refreshTab(newTab)
}

const openQueryTab = (data: any) => {
  const connId = data.type === 'conn' ? data.id : data.connId
  const dbName = data.type === 'db' ? data.label : (data.database || '')
  
  let dbType = 'mysql'
  let connName = ''
  if (data.type === 'conn') {
    dbType = data.dbType
    connName = data.name
  } else {
    const connNode = treeData.value.find((c: any) => c.id === connId)
    if (connNode) {
      dbType = connNode.dbType
      connName = connNode.name
    }
  }
  
  activeConnectionId.value = connId

  const tabName = `query_${connId}_${Date.now()}`
  const newTab = {
    name: tabName,
    title: `Query: ${dbName || 'Console'}`,
    type: 'query',
    connId: connId,
    connName: connName,
    dbName: dbName, 
    dbType: dbType,
    queryInput: '',
    data: [],
    headers: [],
    loading: false,
    total: 0
  }
  tabs.value.push(newTab)
  connActiveTabs[connId] = tabName
}

const startGlobalQuery = () => {
  if (selectedQueryConn.value) {
    openQueryTab(selectedQueryConn.value)
    showQuerySelector.value = false
  }
}

const refreshTab = async (tab: any) => {
  tab.loading = true
  try {
    const params: any = {
      page: tab.page,
      pageSize: tab.pageSize
    }
    
    if (tab.searchQuery) {
      if (tab.dbType === 'mysql') params.where = tab.searchQuery
      else if (tab.dbType.includes('redis')) params.pattern = tab.searchQuery
      else if (tab.dbType === 'mongo') params.filter = tab.searchQuery
      else if (tab.dbType === 'rabbitmq') params.where = tab.searchQuery
    }
    
    const res = await dbApi.query(tab.connId, tab.dbName, tab.tableName, params)
    // @ts-ignore
    tab.data = res.rows
    // @ts-ignore
    tab.headers = res.headers
    // @ts-ignore
    tab.total = res.total
  } catch (e: any) {
    ElMessage.error(e.message || 'Query failed')
  } finally {
    tab.loading = false
  }
}

const runQuery = async (tab: any) => {
  if (!tab.queryInput) {
    ElMessage.warning('Please enter a query')
    return
  }
  
  tab.loading = true
  try {
    const params: any = {}
    if (tab.dbType === 'mysql') params.sql = tab.queryInput
    else if (tab.dbType.includes('redis')) params.command = tab.queryInput
    else if (tab.dbType === 'mongo') params.filter = tab.queryInput
    else if (tab.dbType === 'rabbitmq') params.where = tab.queryInput
    
    // @ts-ignore
    const res = await dbApi.query(tab.connId, tab.dbName, '', params)
    // @ts-ignore
    tab.data = res.rows
    // @ts-ignore
    tab.headers = res.headers
    // @ts-ignore
    tab.total = res.total
  } catch (e: any) {
    if (e.response && e.response.status === 404) {
      ElMessage.error('Connection not found. Please close this tab and open a new console.')
    } else {
      ElMessage.error(e.message || 'Execution failed')
    }
  } finally {
    tab.loading = false
  }
}

const getQueryPlaceholder = (type: string) => {
  if (type === 'mysql') return 'SELECT * FROM table WHERE id = 1;'
  if (type.includes('redis')) return 'GET mykey\nHGETALL user:1'
  if (type === 'mongo') return '{"name": "John"}'
  if (type === 'rabbitmq') return 'Enter Queue Name (e.g. my_queue)'
  return ''
}

const getQueryHint = (type: string) => {
  if (type === 'mysql') return 'Enter standard SQL statements. Supports multiple lines.'
  if (type.includes('redis')) return 'Enter Redis command (e.g., SET key val).'
  if (type === 'mongo') return 'Enter JSON filter for find() operation.'
  if (type === 'rabbitmq') return 'Enter the name of the queue to peek at messages.'
  return ''
}

const getSearchPlaceholder = (type: string) => {
  if (type.includes('redis')) return 'Key Pattern (e.g. user:*)'
  if (type === 'mongo') return 'JSON Filter (e.g. {"age": 20})'
  if (type === 'mysql') return 'WHERE clause (e.g. id > 5)'
  if (type === 'rabbitmq') return 'Queue Name'
  return 'Search'
}

const getStatusColor = (val: any) => {
  const v = String(val).toUpperCase()
  if (['ERROR', 'FAIL', 'FAILED', 'CRITICAL', 'NO'].includes(v)) return 'danger'
  if (['WARN', 'WARNING', 'PENDING', 'BUSY'].includes(v)) return 'warning'
  if (['INFO', 'SUCCESS', 'OK', 'COMPLETED', 'DONE', 'YES', 'TRUE'].includes(v)) return 'success'
  return 'info'
}

const isStatusColumn = (col: string) => {
  const c = col.toLowerCase()
  return ['status', 'state', 'level', 'type', 'active', 'enabled'].some(k => c.includes(k)) && !c.includes('id')
}

const isIdColumn = (col: string) => {
  const c = col.toLowerCase()
  return c === 'id' || c.endsWith('_id') || c === 'key' || c === '_id'
}

const getColumnWidth = (col: string, data: any[]) => {
  const c = col.toLowerCase()
  // ID columns
  if (c === 'id' || c === '_id') return 80
  if (c.endsWith('_id')) return 100
  
  // Status/Boolean columns
  if (isStatusColumn(col)) return 100
  
  // Time columns
  if (c.includes('time') || c.includes('date') || c.includes('at')) return 160
  
  // Long text columns
  if (c.includes('description') || c.includes('message') || c.includes('content') || c.includes('json') || c.includes('data')) return 300
  
  // Name/Email/Title
  if (c.includes('name') || c.includes('email') || c.includes('title')) return 180
  
  // Default dynamic calculation based on content length (simple heuristic)
  if (data && data.length > 0) {
    const firstVal = data[0][col]
    if (typeof firstVal === 'string' && firstVal.length > 50) return 250
  }
  
  return 140
}

const handleRowSelect = (row: any, tab: any) => {
  tab.selectedRow = row
  // Auto-open details if not open? Optional. 
  // For now let's keep it manual toggle or maybe auto open if it was already open.
}

const handleTabEdit = (targetName: string, action: 'remove' | 'add', connId: string) => {
  if (action === 'remove') {
    const connTabs = getConnTabs(connId)
    let activeName = connActiveTabs[connId]
    
    if (activeName === targetName) {
      connTabs.forEach((tab, index) => {
        if (tab.name === targetName) {
          const nextTab = connTabs[index + 1] || connTabs[index - 1]
          if (nextTab) {
            activeName = nextTab.name
          }
        }
      })
    }
    
    connActiveTabs[connId] = activeName
    tabs.value = tabs.value.filter((tab) => tab.name !== targetName)
    
    // If no tabs left for this connection, close connection tab?
    // Optional: currently we keep the connection tab open even if empty, 
    // but maybe better to auto-close or let user close manually.
    // User requested "separate lines", so keeping it open allows them to open new query console easily.
  }
}

const handleConnectionClose = (connId: string) => {
  // Remove all tabs for this connection
  tabs.value = tabs.value.filter(t => t.connId !== connId)
  
  // If active connection was closed, switch to another
  if (activeConnectionId.value === connId) {
    const remaining = openConnections.value.filter(c => c.id !== connId)
    if (remaining.length > 0) {
      activeConnectionId.value = remaining[remaining.length - 1].id
    } else {
      activeConnectionId.value = ''
    }
  }
}

const testConnection = async () => {
  testing.value = true
  try {
    const payload: any = { ...form }
    payload.extra_config = {}
    if (form.type === 'redis') payload.extra_config.mode = formMode.value
    
    const res = await dbApi.testConnection(payload)
    
    // @ts-ignore
    if (res.ok) ElMessage.success(res.msg)
    else ElMessage.error(res.msg)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    testing.value = false
  }
}

const saveConnection = async () => {
  saving.value = true
  try {
    const payload: any = { ...form }
    payload.extra_config = {}
    if (form.type === 'redis') payload.extra_config.mode = formMode.value
    if (form.type === 'mysql' && useSSL.value) {
       payload.extra_config.ssl = true
    }

    await dbApi.createConnection(payload)
    ElMessage.success('Connection saved')
    showAddDialog.value = false
    loadConnections()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.db-manager-layout {
  display: flex;
  height: calc(100vh - 130px); /* Adjusted for AppLayout header (70px) + padding (48px) */
  background-color: #f0f2f5;
  padding: 12px;
  gap: 12px;
}

.sidebar {
  width: 320px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.sidebar-toolbar {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.sidebar-title {
  font-weight: 700;
  color: #303133;
  font-size: 14px;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #fcfcfc;
}

/* Tree Styling Refinement */
.custom-tree-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
  overflow: hidden;
  height: 40px; /* Comfortable height */
  border-radius: 4px;
  transition: background-color 0.2s;
}

.custom-tree-item:hover {
  background-color: #f5f7fa;
}

:deep(.el-tree-node__content) {
  height: 40px; /* Match item height */
}

:deep(.el-tree--highlight-current .el-tree-node.is-current > .el-tree-node__content) {
  background-color: #ecf5ff;
  color: #409EFF;
  font-weight: 500;
}

/* Tree Icon Container */
.tree-icon-container {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

/* Database Connection Icons - Clean & Lightweight */
.db-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s ease;
  margin-right: 8px;
}

.db-icon img {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

/* Specific scale adjustments for visual balance */
.db-icon.mongo img {
  transform: scale(1.3); /* Mongo leaf is naturally thin, needs boost */
}

.db-icon.rabbitmq img {
  transform: scale(0.9); /* Rabbit is naturally blocky, needs slight reduction */
}

.db-icon.redis img {
  transform: scale(1.05); /* Redis cube benefits from tiny boost */
}

/* Active States - High Contrast Colors */
/* No heavy filters or transforms for better performance and cleaner look */
.db-icon.active {
  opacity: 1;
}

/* Tree Selection Styles - Brand Colors */
.custom-tree-item.is-active.is-conn {
  background-color: transparent !important; /* Reset default background */
}

/* Specific Active Backgrounds for Connections */
/* MySQL */
.custom-tree-item.is-active:has(.mysql) {
  background-color: #E6F7FF !important;
  color: #00758F !important;
  border-right: 3px solid #00758F;
}

/* Redis */
.custom-tree-item.is-active:has(.redis) {
  background-color: #FFF1F0 !important;
  color: #DC382D !important;
  border-right: 3px solid #DC382D;
}

/* Mongo */
.custom-tree-item.is-active:has(.mongo) {
  background-color: #F6FFED !important;
  color: #47A248 !important;
  border-right: 3px solid #47A248;
}

/* RabbitMQ */
.custom-tree-item.is-active:has(.rabbitmq) {
  background-color: #FFF7E6 !important;
  color: #FF6600 !important;
  border-right: 3px solid #FF6600;
}

/* Right Tab Icons */
.conn-tab-icon {
  width: 20px;
  height: 20px;
  margin-right: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conn-tab-icon img {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

/* Same scaling for tab icons */
.conn-tab-icon.mongo img { transform: scale(1.3); }
.conn-tab-icon.rabbitmq img { transform: scale(0.9); }
.conn-tab-icon.redis img { transform: scale(1.05); }

/* Sub-icons (DB & Table) */
.sub-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #909399;
}

.sub-icon.table { color: #606266; }

/* Override old icon styles */
.custom-tree-icon {
  display: none;
}

/* Tree Item Layout Tweaks */
.custom-tree-item {
  height: 40px;
  padding-left: 4px;
  border-radius: 4px; /* Rounded corners for row */
  margin: 1px 4px; /* Spacing between rows */
}

.is-active {
  background-color: #d9ecff; /* Darker blue for better visibility */
  color: #409EFF; /* Text color change */
  font-weight: 500;
}

.custom-tree-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  line-height: 1.5;
  color: #606266;
}



.is-conn .custom-tree-label {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.is-db .custom-tree-label {
  color: #303133;
}

/* Badge Styling */
.conn-badge {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 10px; /* Pill shape */
  margin-left: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* Official Brand Colors for Badges */
.conn-badge.mysql { background-color: #E6F7FF; color: #00758F; border: 1px solid rgba(0, 117, 143, 0.2); }
.conn-badge.redis { background-color: #FFF1F0; color: #DC382D; border: 1px solid rgba(220, 56, 45, 0.2); }
.conn-badge.mongo { background-color: #F6FFED; color: #47A248; border: 1px solid rgba(71, 162, 72, 0.2); }
.conn-badge.rabbitmq { background-color: #FFF7E6; color: #FF6600; border: 1px solid rgba(255, 102, 0, 0.2); }

.custom-tree-actions {
  display: none;
  align-items: center;
  gap: 2px;
  padding-left: 8px;
}

.custom-tree-item:hover .custom-tree-actions {
  display: flex;
}


.workspace {
  flex: 1;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
  border: 1px solid #e4e7ed;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Connection Tabs (Top Level) */
.connection-tabs {
  background: #f5f7fa;
}

:deep(.el-tabs__header) {
  margin: 0;
}

.conn-tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  opacity: 0.7; /* Default dim */
  transition: opacity 0.2s, font-weight 0.2s;
}

.conn-tab-label.is-conn-active {
  opacity: 1;
}

.conn-tab-label.is-conn-active .conn-name {
  font-weight: 800; /* Bolder text for active */
  color: #000;
  text-decoration: underline; /* Underline for emphasis */
  text-underline-offset: 4px;
}

.conn-name {
  font-weight: 600;
  color: #303133;
}

/* Indicator dot for top tabs */
.conn-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #909399;
}
.conn-indicator.mysql { background-color: #00758F; box-shadow: 0 0 4px rgba(0, 117, 143, 0.4); }
.conn-indicator.redis { background-color: #DC382D; box-shadow: 0 0 4px rgba(220, 56, 45, 0.4); }
.conn-indicator.mongo { background-color: #47A248; box-shadow: 0 0 4px rgba(71, 162, 72, 0.4); }
.conn-indicator.rabbitmq { background-color: #FF6600; box-shadow: 0 0 4px rgba(255, 102, 0, 0.4); }


.main-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: none;
  box-shadow: none;
}

:deep(.el-tabs__content) {
  flex: 1;
  padding: 0 !important;
  overflow: hidden;
}

:deep(.el-tab-pane) {
  height: 100%;
}

/* Tab Styling */
.custom-tab-label {
  display: flex;
  align-items: center;
  height: 100%;
  position: relative;
  padding-left: 8px; /* Space for indicator */
}

.tab-conn-indicator {
  position: absolute;
  left: 0;
  top: 15%;
  bottom: 15%;
  width: 4px; /* Thicker */
  border-radius: 4px;
  background-color: #909399; /* Default */
}

.tab-conn-indicator.mysql { background-color: #00758F; }
.tab-conn-indicator.redis { background-color: #DC382D; }
.tab-conn-indicator.mongo { background-color: #47A248; }
.tab-conn-indicator.rabbitmq { background-color: #FF6600; }

.tab-conn-badge {
  width: 16px;
  height: 16px;
  margin-right: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  padding: 2px;
}
.tab-conn-badge img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
.tab-conn-badge.mysql { background-color: #E6F7FF; border: 1px solid rgba(0, 117, 143, 0.2); }
.tab-conn-badge.redis { background-color: #FFF1F0; border: 1px solid rgba(220, 56, 45, 0.2); }
.tab-conn-badge.mongo { background-color: #F6FFED; border: 1px solid rgba(71, 162, 72, 0.2); }
.tab-conn-badge.rabbitmq { background-color: #FFF7E6; border: 1px solid rgba(255, 102, 0, 0.2); }

.tab-icon-wrapper {
  display: flex;
  align-items: center;
  margin-right: 8px;
  color: #606266;
  font-size: 16px;
}

.tab-text-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.2;
  text-align: left;
}

.tab-title-text {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.tab-sub-text {
  font-size: 10px;
  color: #909399;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Ensure Tabs Header has enough height */
:deep(.el-tabs__item) {
  height: 48px !important;
  padding: 0 16px !important;
  display: flex;
  align-items: center;
}

.tab-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Table View Styles */
.table-view .view-toolbar {
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.left-tools {
  display: flex;
  gap: 12px;
}

.table-wrapper {
  flex: 1;
  overflow: hidden;
}

.pagination-bar {
  padding: 8px 12px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: flex-end;
  background: #fafafa;
}

/* Query View Styles */
.query-view .query-editor-container {
  height: 300px;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid #dcdfe6;
}

.editor-toolbar {
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}

.editor-title {
  font-weight: 700;
  font-size: 13px;
}

.editor-subtitle {
  font-size: 12px;
  color: #909399;
}

.editor-wrapper {
  flex: 1;
  background: #282c34; /* Dark theme */
  padding: 0;
  overflow: hidden;
}

.code-editor-input {
  height: 100%;
  width: 100%;
}

.code-editor-input :deep(.el-textarea) {
  height: 100%;
}

.code-editor-input :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  background: #282c34;
  color: #abb2bf;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  padding: 16px;
  height: 100% !important;
  box-shadow: none;
  resize: none;
}

.code-editor-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.editor-footer {
  padding: 6px 12px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 12px;
}

.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

/* Overview Styling */
.overview-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f5f7fa; /* Light gray background */
}

.overview-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  overflow-y: auto;
}

.charts-row {
  display: flex;
  gap: 16px;
  height: 320px;
  flex-shrink: 0;
}

.chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.chart-card :deep(.el-card__body) {
  flex: 1;
  padding: 12px;
  min-height: 0;
}

.chart-title {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.chart {
  height: 100%;
  width: 100%;
}

.table-section {
  flex: 1;
  background: white;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  min-height: 300px; /* Ensure table has space */
}

.result-header {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  color: #303133;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-workspace {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
/* Table & Data Styling */
.data-table {
  font-size: 13px;
}

.code-font {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}

.id-text {
  color: #909399;
}

.status-tag {
  font-weight: 600;
  border: none;
}

/* Data View Container (Table + Details) */
.data-view-container {
  flex: 1;
  display: flex;
  overflow: hidden; /* Important for scroll */
  /* height: 100%; REMOVED to prevent flex overflow */
  min-height: 0; /* Important: Ensures container doesn't grow beyond flex parent, allowing children to scroll */
}

.table-wrapper {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0; /* Important for horizontal scroll in flex items */
}

/* Details Panel */
.details-panel {
  width: 350px;
  border-left: 1px solid #e4e7ed;
  background: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  box-shadow: -2px 0 8px rgba(0,0,0,0.05);
  z-index: 10;
  height: 100%; /* Ensure it matches parent height to enable internal scrolling */
  overflow: hidden;
}

.details-header {
  height: 40px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #fcfcfc;
  flex-shrink: 0; /* Prevent header from shrinking */
}

.details-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.details-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  min-height: 0; /* Important for flex child scroll */
}

.details-list {
  display: flex;
  flex-direction: column;
}

.detail-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f2f5;
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-key {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
  font-weight: 500;
}

.detail-value {
  font-size: 13px;
  color: #303133;
  word-break: break-all;
  line-height: 1.4;
}

/* Vertical Divider in Toolbar */
.divider-vertical {
  width: 1px;
  height: 16px;
  background: #dcdfe6;
  margin: 0 8px;
}

/* Breadcrumb Styling */
.context-breadcrumb {
  padding: 6px 12px;
  background: #fdfdfd;
  border-bottom: 1px solid #f0f2f5;
  display: flex;
  align-items: center;
  font-size: 12px;
}

.breadcrumb-separator {
  margin: 0 6px;
  color: #c0c4cc;
}

.breadcrumb-current {
  color: #606266;
  font-weight: 500;
}

.breadcrumb-active {
  color: #303133;
  font-weight: 700;
}
</style>
