<template>
  <div class="login-container">
    <div class="login-card">
      <div class="brand">
        <img src="@/assets/images/brand.png" alt="Shark Platform" class="logo" />
        <h1 class="title">Shark Platform</h1>
      </div>
      
      <el-form :model="form" @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input 
            v-model="form.username" 
            placeholder="Username" 
            prefix-icon="User" 
            size="large"
          />
        </el-form-item>
        
        <el-form-item>
          <el-input 
            v-model="form.password" 
            type="password" 
            placeholder="Password" 
            prefix-icon="Lock" 
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-button type="primary" size="large" :loading="loading" class="login-btn" @click="handleLogin">
          Sign In
        </el-button>
      </el-form>
      
      <div class="footer">
        &copy; 2026 Shark Platform
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useSystemStore } from '@/stores/system'

const router = useRouter()
const route = useRoute()
const systemStore = useSystemStore()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const handleLogin = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('Please enter username and password')
    return
  }
  
  loading.value = true
  try {
    await request.post('/auth/login', form)
    ElMessage.success('Login successful')
    await systemStore.fetchCurrentUser()
    
    const next = route.query.next as string
    if (next && next.startsWith('/')) {
        router.push(next)
    } else {
        router.push('/')
    }
  } catch (e) {
    // Error handled by request interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f8fafc;
  background-image: radial-gradient(#e2e8f0 1px, transparent 1px);
  background-size: 20px 20px;
}

.login-card {
  width: 400px;
  background: #fff;
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
}

.logo {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.login-form {
  width: 100%;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  font-weight: 600;
}

.footer {
  margin-top: 32px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
