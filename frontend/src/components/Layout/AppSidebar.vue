<template>
  <el-aside :width="isCollapsed ? '64px' : '220px'" class="sidebar">
    <div class="logo-container">
      <div class="logo-wrapper">
        <img src="@/assets/images/brand.png" alt="Logo" class="logo" />
      </div>
      <span v-if="!isCollapsed" class="title">Shark Platform</span>
    </div>
    
    <div class="menu-wrapper">
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical"
        :collapse="isCollapsed"
        background-color="transparent"
        text-color="rgba(255,255,255,0.7)"
        active-text-color="#ffffff"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>Dashboard</template>
        </el-menu-item>
        
        <div class="menu-group-title" v-if="!isCollapsed">DATA PIPELINE</div>
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <template #title>Sync Tasks</template>
        </el-menu-item>
        <el-menu-item index="/connections">
          <el-icon><Link /></el-icon>
          <template #title>Data Sources</template>
        </el-menu-item>
        
        <div class="menu-group-title" v-if="!isCollapsed">MAINTENANCE</div>
        <el-menu-item index="/logs">
          <el-icon><Monitor /></el-icon>
          <template #title>Log Monitor</template>
        </el-menu-item>
        <el-menu-item index="/system">
          <el-icon><Setting /></el-icon>
          <template #title>System Inspect</template>
        </el-menu-item>
        <el-menu-item index="/deploy">
          <el-icon><Upload /></el-icon>
          <template #title>Server Deploy</template>
        </el-menu-item>
        <el-menu-item index="/permissions" v-if="isAdmin">
          <el-icon><Lock /></el-icon>
          <template #title>Permissions</template>
        </el-menu-item>
      </el-menu>
    </div>

    <div class="sidebar-footer" @click="isCollapsed = !isCollapsed">
      <el-icon>
        <component :is="isCollapsed ? 'Expand' : 'Fold'" />
      </el-icon>
    </div>
  </el-aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Odometer, List, Link, Monitor, Setting, Upload, Fold, Expand, Lock } from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'

const route = useRoute()
const systemStore = useSystemStore()
const isCollapsed = ref(false)

const isAdmin = computed(() => systemStore.isAdmin)

onMounted(() => {
  systemStore.fetchCurrentUser()
})

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/tasks')) return '/tasks'
  return path
})
</script>

<style scoped>
.sidebar {
  height: 100vh;
  background-color: var(--app-sidebar-bg);
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 10px rgba(0,0,0,0.1);
  z-index: 1000;
  border-right: 1px solid var(--app-border-color);
  transition: width 0.3s;
}

.logo-container {
  height: 70px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  color: white;
  border-bottom: 1px solid var(--app-border-color);
  overflow: hidden;
}

.logo-wrapper {
  min-width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo {
  width: 28px;
  height: 28px;
}

.title {
  margin-left: 12px;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: -0.5px;
  white-space: nowrap;
}

.menu-wrapper {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
  background-color: transparent;
}

.menu-group-title {
  padding: 24px 20px 8px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,0.3);
  letter-spacing: 1px;
}

:deep(.el-menu) {
  background-color: transparent;
  border-right: none;
}

:deep(.el-menu-item) {
  height: 48px;
  margin: 4px 12px;
  border-radius: 8px;
  line-height: 48px;
  color: #94a3b8;
}

:deep(.el-menu-item.is-active) {
  background-color: var(--el-color-primary) !important;
  color: #fff;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  color: #fff;
}

.sidebar-footer {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  border-top: 1px solid rgba(255,255,255,0.05);
  transition: color 0.3s;
}

.sidebar-footer:hover {
  color: white;
  background-color: rgba(255,255,255,0.02);
}
</style>
