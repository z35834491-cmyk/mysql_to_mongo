<template>
  <el-container class="app-wrapper">
    <AppSidebar />
    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <div class="page-info">
            <h2 class="page-title">{{ currentRouteName }}</h2>
            <el-breadcrumb separator="/" class="custom-breadcrumb">
              <el-breadcrumb-item :to="{ path: '/' }">Home</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentRouteName }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
        </div>
        
        <div class="header-right">
          <div class="system-status">
            <div class="status-item">
              <span class="status-label">CPU</span>
              <el-progress :percentage="12" :show-text="false" :stroke-width="6" class="mini-progress" />
              <span class="status-value">12%</span>
            </div>
            <div class="status-item">
              <span class="status-label">RAM</span>
              <el-progress :percentage="30" :show-text="false" :stroke-width="6" class="mini-progress" color="#8b5cf6" />
              <span class="status-value">2.4G / 8G</span>
            </div>
          </div>
          
          <el-divider direction="vertical" />
          
          <div class="action-icons">
            <el-color-picker 
              v-model="themeColor" 
              size="small" 
              @change="updateThemeColor"
              :predefine="['#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981']"
            />
            <div class="header-icon-wrapper" @click="toggleDark()">
              <el-icon class="header-icon">
                <Moon v-if="!isDark" />
                <Sunny v-else />
              </el-icon>
            </div>
          </div>
          
          <el-divider direction="vertical" />
          
          <el-dropdown>
            <div class="user-profile">
              <el-avatar :size="32" :src="sharkAvatar" />
              <div class="user-info">
                <span class="username">{{ currentUser?.username || 'Administrator' }}</span>
                <span class="user-role">{{ isAdmin ? 'System Admin' : 'User' }}</span>
              </div>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout" divided>
                  <el-icon><SwitchButton /></el-icon>Logout
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import sharkAvatar from '@/assets/images/brand.png'
import { 
  ArrowDown, Bell, Moon, Sunny, Cpu, PieChart, 
  User, Setting, SwitchButton 
} from '@element-plus/icons-vue'
import { useDark, useToggle } from '@vueuse/core'
import { useSystemStore } from '@/stores/system'
import { storeToRefs } from 'pinia'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const systemStore = useSystemStore()
const { currentUser, isAdmin } = storeToRefs(systemStore)

const currentRouteName = computed(() => {
  return route.name as string || 'Dashboard'
})

// Dark Mode
const isDark = useDark()
const toggleDark = useToggle(isDark)

// Theme Color
const themeColor = ref('#3b82f6')
const updateThemeColor = (color: string | null) => {
  if (color) {
    // 1. Set Element Plus Primary Color
    document.documentElement.style.setProperty('--el-color-primary', color)
    
    // 2. Generate shades for Element Plus components
    for (let i = 1; i <= 9; i++) {
      const lightColor = mixColor('#ffffff', color, i * 10)
      document.documentElement.style.setProperty(`--el-color-primary-light-${i}`, lightColor)
    }
    const darkColor = mixColor('#000000', color, 20)
    document.documentElement.style.setProperty('--el-color-primary-dark-2', darkColor)
  }
}

// Helper to mix colors
const mixColor = (color1: string, color2: string, weight: number) => {
  const p = weight / 100
  const w = p * 2 - 1
  const a = 0
  const w1 = ((w * a === -1 ? w : (w + a) / (1 + w * a)) + 1) / 2
  const w2 = 1 - w1

  const hex = (c: string) => parseInt(c.replace('#', ''), 16)
  const r1 = (hex(color1) >> 16) & 0xff
  const g1 = (hex(color1) >> 8) & 0xff
  const b1 = hex(color1) & 0xff
  const r2 = (hex(color2) >> 16) & 0xff
  const g2 = (hex(color2) >> 8) & 0xff
  const b2 = hex(color2) & 0xff

  const r = Math.round(r1 * w1 + r2 * w2)
  const g = Math.round(g1 * w1 + g2 * w2)
  const b = Math.round(b1 * w1 + b2 * w2)

  return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)
}

// Logout
const handleLogout = async () => {
  try {
    await request.post('/auth/logout')
    ElMessage.success('Logged out')
    router.push('/login')
  } catch (e) {
    console.error(e)
    // Even if api fails, redirect to login
    router.push('/login')
  }
}
</script>

<style>
:root {
  --app-main-bg: #f8fafc;
  --app-sidebar-bg: #0f172a;
  --app-header-bg: #ffffff;
  --app-card-bg: #ffffff;
  --app-text-main: #1e293b;
  --app-text-muted: #64748b;
  --app-border-color: #e2e8f0;
}

html.dark {
  --app-main-bg: #0f172a;
  --app-sidebar-bg: #0f172a;
  --app-header-bg: #0f172a;
  --app-card-bg: #1e293b;
  --app-text-main: #f8fafc;
  --app-text-muted: #94a3b8;
  --app-border-color: #334155;
}
</style>

<style scoped>
.app-wrapper {
  height: 100vh;
  width: 100%;
}

.main-container {
  flex-direction: column;
}

.app-header {
  background-color: var(--app-header-bg);
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  border-bottom: 1px solid var(--app-border-color);
  z-index: 9;
  transition: all 0.3s;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--app-text-main);
  letter-spacing: -0.5px;
}

.custom-breadcrumb {
  font-size: 12px;
}

:deep(.el-breadcrumb__inner) {
  color: var(--app-text-muted) !important;
  font-weight: 400 !important;
}

:deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--app-text-muted) !important;
  opacity: 0.7;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.system-status {
  display: flex;
  gap: 24px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--app-text-muted);
}

.mini-progress {
  width: 60px;
}

.status-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-main);
  min-width: 60px;
}

.action-icons {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--app-text-muted);
}

.header-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  transition: all 0.2s;
}

.header-icon-wrapper:hover {
  background-color: rgba(var(--el-color-primary-rgb, 59, 130, 246), 0.1);
  color: var(--el-color-primary);
}

.header-icon {
  font-size: 18px;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 8px;
  transition: background 0.2s;
}

.user-profile:hover {
  background-color: var(--app-main-bg);
}

.user-info {
  display: flex;
  flex-direction: column;
}

.username {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text-main);
  line-height: 1.2;
}

.user-role {
  font-size: 11px;
  color: var(--app-text-muted);
}

.app-main {
  flex: 1;
  padding: 24px;
  background-color: var(--app-main-bg);
  overflow-y: auto;
  transition: background-color 0.3s;
}

.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
