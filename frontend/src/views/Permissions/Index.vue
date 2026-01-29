<template>
  <div class="permissions-container">
    <div class="page-header header-info">
      <h2 class="page-title">Access Control & Permissions</h2>
      <p class="page-subtitle">Manage users, roles, and feature-level permissions</p>
    </div>

    <el-tabs v-model="activeTab" class="custom-tabs">
      <!-- Users Tab -->
      <el-tab-pane label="Users" name="users">
        <el-card shadow="never" class="content-card">
          <div class="toolbar">
            <el-input
              v-model="searchQuery"
              placeholder="Search users..."
              class="search-input"
              :prefix-icon="Search"
              clearable
            />
            <el-button type="primary" :icon="Plus" @click="handleAddUser">Add User</el-button>
          </div>

          <el-table :data="paginatedUsers" v-loading="loading" style="width: 100%">
            <el-table-column prop="username" label="Username" min-width="150">
              <template #default="{ row }">
                <div class="user-cell">
                  <el-avatar :size="24" :src="sharkAvatar" />
                  <span>{{ row.username }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="Email" min-width="200" />
            <el-table-column label="Role/Groups" min-width="200">
              <template #default="{ row }">
                <el-tag 
                  v-for="group in row.groups" 
                  :key="group" 
                  size="small" 
                  class="group-tag"
                  :type="getGroupTagType(group)"
                >
                  {{ group }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ row }">
                <el-switch v-model="row.is_active" @change="toggleUserStatus(row)" />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleEditPermissions(row)">Edit</el-button>
                <el-button link type="danger" @click="handleDeleteUser(row)">Delete</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="filteredUsers.length"
              layout="total, prev, pager, next"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Roles & Permissions Tab -->
      <el-tab-pane label="Roles & Permissions" name="roles">
        <el-card shadow="never" class="content-card">
          <div class="toolbar">
            <div class="section-title-box">
              <el-icon><Lock /></el-icon>
              <span>Role Definitions</span>
            </div>
            <el-button type="primary" plain :icon="Plus" @click="handleAddRole">Add Role</el-button>
          </div>

          <el-table :data="roles" v-loading="loading" style="width: 100%">
            <el-table-column prop="name" label="Role Name" width="150" />
            <el-table-column label="Permissions" min-width="300">
              <template #default="{ row }">
                <el-tag 
                  v-for="perm in row.permissions" 
                  :key="perm" 
                  size="small" 
                  effect="plain"
                  class="perm-tag"
                >
                  {{ perm }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleEditRole(row)">Configure</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- User Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editMode ? 'Edit User Permissions' : 'Add New User'" width="500px">
      <el-form :model="userForm" label-position="top">
        <el-form-item label="Username" required v-if="!editMode">
          <el-input v-model="userForm.username" />
        </el-form-item>
        <el-form-item label="Groups / Roles">
          <el-select v-model="userForm.groups" multiple placeholder="Select roles" style="width: 100%">
            <el-option v-for="role in roles" :key="role.name" :label="role.name" :value="role.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="Password" required v-if="!editMode">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="submitUserForm">Save</el-button>
      </template>
    </el-dialog>

    <!-- Role Edit Dialog -->
    <el-dialog v-model="roleDialogVisible" title="Configure Role" width="600px">
      <el-form :model="roleForm" label-position="top">
        <el-form-item label="Role Name" required>
          <el-input v-model="roleForm.name" :disabled="roleForm.name === 'Admin'" />
        </el-form-item>
        <el-form-item label="Functional Permissions">
          <el-checkbox-group v-model="roleForm.permissions">
            <el-row :gutter="20">
              <el-col :span="12" v-for="p in allPermissions" :key="p.codename">
                <el-checkbox :label="p.codename">{{ p.name }}</el-checkbox>
              </el-col>
            </el-row>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="submitRoleForm">Save Changes</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Search, Plus, Lock } from '@element-plus/icons-vue'
import sharkAvatar from '@/assets/images/brand.png'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('users')
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const users = ref<any[]>([])
const roles = ref<any[]>([])
const allPermissions = ref<any[]>([])

const dialogVisible = ref(false)
const editMode = ref(false)
const userForm = ref({
  id: null,
  username: '',
  password: '',
  groups: [] as string[]
})

const roleDialogVisible = ref(false)
const roleForm = ref({
  id: null,
  name: '',
  permissions: [] as string[]
})

const fetchData = async () => {
  loading.value = true
  try {
    const [uRes, rRes, pRes] = await Promise.all([
      request.get<any>('/users'),
      request.get<any>('/roles'),
      request.get<any>('/permissions')
    ])
    users.value = uRes.users
    roles.value = rRes.roles
    allPermissions.value = pRes.permissions
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

const filteredUsers = computed(() => {
  return users.value.filter(u => 
    u.username.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
    u.email?.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const paginatedUsers = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredUsers.value.slice(start, start + pageSize.value)
})

const getGroupTagType = (group: string) => {
  if (group === 'Admin') return 'danger'
  if (group === 'Developer') return 'primary'
  return 'info'
}

const handleAddUser = () => {
  editMode.value = false
  userForm.value = { id: null, username: '', password: '', groups: [] }
  dialogVisible.value = true
}

const handleEditPermissions = (user: any) => {
  editMode.value = true
  userForm.value = { ...user, password: '' }
  dialogVisible.value = true
}

const submitUserForm = async () => {
  try {
    if (editMode.value) {
      await request.put(`/users/${userForm.value.id}`, userForm.value)
      ElMessage.success('Permissions updated')
    } else {
      await request.post('/users', userForm.value)
      ElMessage.success('User created')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    console.error(e)
  }
}

const toggleUserStatus = async (user: any) => {
  try {
    await request.put(`/users/${user.id}`, { is_active: user.is_active })
    ElMessage.success('Status updated')
  } catch (e) {
    user.is_active = !user.is_active
  }
}

const handleDeleteUser = (user: any) => {
  ElMessageBox.confirm(`Are you sure you want to delete user ${user.username}?`, 'Warning', {
    type: 'warning'
  }).then(async () => {
    await request.delete(`/users/${user.id}`)
    ElMessage.success('User deleted')
    fetchData()
  })
}

// Role methods
const handleAddRole = () => {
  roleForm.value = { id: null, name: '', permissions: [] }
  roleDialogVisible.value = true
}

const handleEditRole = async (role: any) => {
  // Deep copy permissions to ensure reactivity and break references
  const rolePermissions = role.permissions ? [...role.permissions] : []
  
  roleForm.value = { 
    id: role.id,
    name: role.name,
    permissions: rolePermissions
  }
  await nextTick()
  roleDialogVisible.value = true
}

const submitRoleForm = async () => {
  try {
    await request.post('/roles', roleForm.value)
    ElMessage.success('Role configured')
    roleDialogVisible.value = false
    fetchData()
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped>
.permissions-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  margin-bottom: 8px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #475569;
}

.search-input {
  width: 300px;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-tag {
  margin-right: 5px;
}

.perm-tag {
  margin: 2px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.custom-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
</style>
