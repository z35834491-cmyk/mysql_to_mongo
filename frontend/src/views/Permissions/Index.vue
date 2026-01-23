<template>
  <div class="permissions-container">
    <div class="page-header">
      <h2 class="page-title">Access Control & Permissions</h2>
      <p class="page-subtitle">Manage users, roles, and feature-level permissions</p>
    </div>

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
            <el-button link type="primary" @click="handleEditPermissions(row)">Edit Permissions</el-button>
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

    <!-- User Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editMode ? 'Edit User Permissions' : 'Add New User'" width="500px">
      <el-form :model="userForm" label-position="top">
        <el-form-item label="Username" required v-if="!editMode">
          <el-input v-model="userForm.username" />
        </el-form-item>
        <el-form-item label="Groups / Roles">
          <el-select v-model="userForm.groups" multiple placeholder="Select roles" style="width: 100%">
            <el-option label="Admin" value="Admin" />
            <el-option label="Developer" value="Developer" />
            <el-option label="Viewer" value="Viewer" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Lock } from '@element-plus/icons-vue'
import sharkAvatar from '@/assets/images/brand.png'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const users = ref<any[]>([])

const dialogVisible = ref(false)
const editMode = ref(false)
const userForm = ref({
  id: null,
  username: '',
  password: '',
  groups: [] as string[]
})

const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await request.get<any>('/api/users')
    users.value = res.users
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchUsers)

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
      await request.put(`/api/users/${userForm.value.id}`, userForm.value)
      ElMessage.success('Permissions updated')
    } else {
      await request.post('/api/users', userForm.value)
      ElMessage.success('User created')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch (e) {
    console.error(e)
  }
}

const toggleUserStatus = async (user: any) => {
  try {
    await request.put(`/api/users/${user.id}`, { is_active: user.is_active })
    ElMessage.success('Status updated')
  } catch (e) {
    user.is_active = !user.is_active
  }
}

const handleDeleteUser = (user: any) => {
  ElMessageBox.confirm(`Are you sure you want to delete user ${user.username}?`, 'Warning', {
    type: 'warning'
  }).then(async () => {
    await request.delete(`/api/users/${user.id}`)
    ElMessage.success('User deleted')
    fetchUsers()
  })
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
  margin-bottom: 20px;
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

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
