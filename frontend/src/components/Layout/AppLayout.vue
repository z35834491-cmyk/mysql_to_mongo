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
            <el-badge :value="3" is-dot class="badge-item">
              <el-icon class="header-icon"><Bell /></el-icon>
            </el-badge>
            <el-icon class="header-icon"><Moon /></el-icon>
          </div>
          
          <el-divider direction="vertical" />
          
          <el-dropdown>
            <div class="user-profile">
              <el-avatar :size="32" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
              <div class="user-info">
                <span class="username">Administrator</span>
                <span class="user-role">System Admin</span>
              </div>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item><el-icon><User /></el-icon>Profile</el-dropdown-item>
                <el-dropdown-item><el-icon><Setting /></el-icon>Settings</el-dropdown-item>
                <el-dropdown-item divided><el-icon><SwitchButton /></el-icon>Logout</el-dropdown-item>
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import { 
  ArrowDown, Bell, Moon, Cpu, PieChart, 
  User, Setting, SwitchButton 
} from '@element-plus/icons-vue'

const route = useRoute()
const currentRouteName = computed(() => {
  return route.name as string || 'Dashboard'
})
</script>

<style scoped>
.app-wrapper {
  height: 100vh;
  width: 100%;
}

.main-container {
  flex-direction: column;
}

.app-header {
  background-color: #fff;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  border-bottom: 1px solid #f1f5f9;
  z-index: 9;
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
  color: #0f172a;
  letter-spacing: -0.5px;
}

.custom-breadcrumb {
  font-size: 12px;
}

:deep(.el-breadcrumb__inner) {
  color: #64748b !important;
  font-weight: 400 !important;
}

:deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: #94a3b8 !important;
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
  color: #94a3b8;
}

.mini-progress {
  width: 60px;
}

.status-value {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  min-width: 60px;
}

.action-icons {
  display: flex;
  gap: 16px;
  color: #64748b;
}

.header-icon {
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
}

.header-icon:hover {
  color: #3b82f6;
  transform: translateY(-1px);
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
  background-color: #f8fafc;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.username {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.2;
}

.user-role {
  font-size: 11px;
  color: #94a3b8;
}

.app-main {
  padding: 32px;
  background-color: #f8fafc;
  overflow-y: auto;
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
