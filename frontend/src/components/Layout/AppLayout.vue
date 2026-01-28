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
            <!-- MODIFIED_BY_AGENT_START: Add settings button -->
            <div class="header-icon-wrapper" @click="showSettings = true">
              <el-icon class="header-icon"><Setting /></el-icon>
            </div>
            <!-- MODIFIED_BY_AGENT_END -->
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
      
      <el-main class="app-main" :style="mainStyle">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <!-- MODIFIED_BY_AGENT_START: Theme Settings Drawer -->
  <el-drawer v-model="showSettings" title="Theme Settings" size="300px">
    <div class="settings-section">
      <h3>Presets</h3>
      <div class="preset-list">
        <div 
          v-for="preset in themePresets" 
          :key="preset.name" 
          class="preset-item"
          :style="{ background: preset.color }"
          @click="applyPreset(preset)"
        >
          {{ preset.name }}
        </div>
      </div>
    </div>

    <el-divider />

    <div class="settings-section">
      <h3>Background Color</h3>
      <div class="color-picker-row">
        <span>Main Background</span>
        <el-color-picker v-model="backgroundColor" show-alpha @change="updateBackground" />
      </div>
    </div>

    <el-divider />

    <div class="settings-section">
      <h3>Background Image</h3>
      <div class="bg-input-group">
        <el-input 
          v-model="backgroundImage" 
          placeholder="Image URL..." 
          clearable
          class="url-input"
        >
          <template #prefix><el-icon><Link /></el-icon></template>
        </el-input>
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="handleFileChange"
          accept="image/*"
        >
          <el-button :icon="Upload" circle />
        </el-upload>
      </div>
      
      <div class="bg-preview" v-if="backgroundImage" :style="{ backgroundImage: `url(${backgroundImage})` }">
        <el-button circle size="small" :icon="Close" class="remove-bg" @click="backgroundImage = ''" />
      </div>
    </div>

    <el-divider />

    <div class="settings-section">
      <h3>Glass Effect (透视与羽化)</h3>
      <div class="slider-group">
        <span class="slider-label">Transparency</span>
        <el-slider v-model="glassOpacity" :min="0" :max="100" :format-tooltip="(val) => `${val}%`" @input="updateGlassEffect" />
      </div>
      <div class="slider-group">
        <span class="slider-label">Blur (Feather)</span>
        <el-slider v-model="glassBlur" :min="0" :max="40" :format-tooltip="(val) => `${val}px`" @input="updateGlassEffect" />
      </div>
    </div>
  </el-drawer>
  <!-- MODIFIED_BY_AGENT_END -->
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import sharkAvatar from '@/assets/images/brand.png'
import { 
  ArrowDown, Bell, Moon, Sunny, Cpu, PieChart, 
  User, Setting, SwitchButton, Picture, Upload, Link, Close
} from '@element-plus/icons-vue'
import { useDark, useToggle } from '@vueuse/core'
import { useSystemStore } from '@/stores/system'
import { storeToRefs } from 'pinia'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'

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

// MODIFIED_BY_AGENT_START: Background & Presets Logic
const showSettings = ref(false)
const backgroundColor = ref('#f8fafc')
const backgroundImage = ref('')
// Glass Effect State
const glassOpacity = ref(0) // 0 means fully opaque (no transparency) by default for compatibility, user can increase
const glassBlur = ref(0)

const mainStyle = computed(() => {
  const style: any = {
    backgroundColor: backgroundColor.value
  }
  if (backgroundImage.value) {
    style.backgroundImage = `url(${backgroundImage.value})`
    style.backgroundSize = 'cover'
    style.backgroundPosition = 'center'
    style.backgroundAttachment = 'fixed'
  }
  return style
})

const updateBackground = () => {
  // Logic handled by computed mainStyle binding
}

const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    const reader = new FileReader()
    reader.onload = (e) => {
      if (e.target?.result) {
        backgroundImage.value = e.target.result as string
        ElMessage.success('Background image loaded')
      }
    }
    reader.readAsDataURL(file.raw)
  }
}

const themePresets = [
  { name: 'Default', color: '#3b82f6', bg: '#f8fafc', bgImg: '' },
  { name: 'Ocean', color: '#0ea5e9', bg: '#f0f9ff', bgImg: '' },
  { name: 'Forest', color: '#10b981', bg: '#ecfdf5', bgImg: '' },
  { name: 'Sunset', color: '#f59e0b', bg: '#fffbeb', bgImg: '' },
  { name: 'Night', color: '#6366f1', bg: '#1e1b4b', bgImg: 'https://images.unsplash.com/photo-1534796636912-3b95b3ab5980?auto=format&fit=crop&w=2000&q=80' },
]

const applyPreset = (preset: any) => {
  themeColor.value = preset.color
  updateThemeColor(preset.color)
  backgroundColor.value = preset.bg
  backgroundImage.value = preset.bgImg
  ElMessage.success(`Applied ${preset.name} theme`)
}

// Glass Effect Logic
const updateGlassEffect = () => {
  const alpha = 1 - (glassOpacity.value / 100)
  const blur = glassBlur.value
  
  document.documentElement.style.setProperty('--app-glass-alpha', alpha.toString())
  document.documentElement.style.setProperty('--app-glass-blur', `${blur}px`)
  
  // Apply glass class to body/html if effect is active
  if (glassOpacity.value > 0 || glassBlur.value > 0) {
    document.documentElement.classList.add('glass-active')
  } else {
    document.documentElement.classList.remove('glass-active')
  }
}

// Watch dark mode to re-apply correct glass colors
watch(isDark, () => {
  updateGlassEffect()
})

// Persistence Logic
onMounted(() => {
  // Restore settings from localStorage
  const savedBgColor = localStorage.getItem('app_bg_color')
  if (savedBgColor) backgroundColor.value = savedBgColor

  const savedBgImg = localStorage.getItem('app_bg_image')
  if (savedBgImg) backgroundImage.value = savedBgImg

  const savedOpacity = localStorage.getItem('app_glass_opacity')
  if (savedOpacity) glassOpacity.value = Number(savedOpacity)

  const savedBlur = localStorage.getItem('app_glass_blur')
  if (savedBlur) glassBlur.value = Number(savedBlur)

  // Apply initial glass effect
  updateGlassEffect()
})

watch(backgroundColor, (val) => localStorage.setItem('app_bg_color', val))
watch(backgroundImage, (val) => localStorage.setItem('app_bg_image', val))
watch(glassOpacity, (val) => {
  localStorage.setItem('app_glass_opacity', val.toString())
  updateGlassEffect()
})
watch(glassBlur, (val) => {
  localStorage.setItem('app_glass_blur', val.toString())
  updateGlassEffect()
})
// MODIFIED_BY_AGENT_END

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

/* MODIFIED_BY_AGENT_START: Glass Effect Global Styles (Moved to Global Scope) */
html.glass-active {
  --app-glass-border: 1px solid rgba(255, 255, 255, 0.1);
  /* Override global card bg variable to be transparent */
  --app-card-bg: rgba(255, 255, 255, var(--app-glass-alpha));
}

html.glass-active.dark {
  --app-card-bg: rgba(30, 41, 59, var(--app-glass-alpha));
}

/* Force transparency and blur on Header */
html.glass-active .app-header {
  /* Use a lower base alpha to make blur visible, user control overrides */
  background-color: rgba(255, 255, 255, var(--app-glass-alpha)) !important;
  backdrop-filter: blur(var(--app-glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--app-glass-blur)) !important;
  border-bottom: var(--app-glass-border) !important;
}

html.glass-active.dark .app-header {
  background-color: rgba(15, 23, 42, var(--app-glass-alpha)) !important;
}

/* Force transparency and blur on Sidebar */
html.glass-active .sidebar, 
html.glass-active .el-aside {
  background-color: rgba(255, 255, 255, var(--app-glass-alpha)) !important; 
  backdrop-filter: blur(var(--app-glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--app-glass-blur)) !important;
  border-right: var(--app-glass-border) !important;
  box-shadow: none !important; /* Remove shadow to clean up edges */
}

html.glass-active.dark .sidebar,
html.glass-active.dark .el-aside {
  background-color: rgba(15, 23, 42, var(--app-glass-alpha)) !important;
}

/* Ensure Menu is transparent */
html.glass-active .sidebar .el-menu {
  background-color: transparent !important;
}

/* Sidebar Text & Icon Adaptation for Light Glass Mode */
html.glass-active:not(.dark) .sidebar .title {
  background: transparent !important;
  -webkit-text-fill-color: initial !important;
  color: var(--app-text-main) !important;
}

html.glass-active:not(.dark) .sidebar .el-menu-item {
  color: var(--app-text-main) !important;
}

html.glass-active:not(.dark) .sidebar .el-menu-item .el-icon {
  color: var(--app-text-muted) !important;
}

html.glass-active:not(.dark) .sidebar .el-menu-item:hover {
  background-color: rgba(0, 0, 0, 0.05) !important;
  color: var(--el-color-primary) !important;
}

html.glass-active:not(.dark) .sidebar .el-menu-item.is-active {
  background: var(--el-color-primary) !important;
  color: #fff !important;
}

html.glass-active:not(.dark) .sidebar .menu-group-title {
  color: var(--app-text-muted) !important;
}

html.glass-active:not(.dark) .sidebar .sidebar-footer {
  color: var(--app-text-main) !important;
  border-top: 1px solid rgba(0, 0, 0, 0.05) !important;
}

/* Force transparency on Cards inside Main (including Dashboard custom cards & Calendar) */
html.glass-active .app-main .el-card,
html.glass-active .app-main .stat-card,
html.glass-active .app-main .chart-card,
html.glass-active .app-main .health-card,
html.glass-active .calendar-view {
  background-color: var(--app-card-bg) !important;
  backdrop-filter: blur(var(--app-glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--app-glass-blur)) !important;
  border: var(--app-glass-border) !important;
}

/* MODIFIED_BY_AGENT_START: Global Overlay Components Glass Effect (Dialog, Drawer, Dropdown, Popover) */
html.glass-active .el-dialog,
html.glass-active .el-drawer,
html.glass-active .el-dropdown-menu,
html.glass-active .el-popover,
html.glass-active .el-select-dropdown {
  background-color: rgba(255, 255, 255, var(--app-glass-alpha)) !important;
  backdrop-filter: blur(var(--app-glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--app-glass-blur)) !important;
  border: var(--app-glass-border) !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
}

html.glass-active.dark .el-dialog,
html.glass-active.dark .el-drawer,
html.glass-active.dark .el-dropdown-menu,
html.glass-active.dark .el-popover,
html.glass-active.dark .el-select-dropdown {
  background-color: rgba(30, 41, 59, var(--app-glass-alpha)) !important;
}

/* Fix arrow colors for popovers/dropdowns */
html.glass-active .el-popper__arrow::before {
  background: transparent !important;
  border: var(--app-glass-border) !important;
}
/* MODIFIED_BY_AGENT_END */

/* MODIFIED_BY_AGENT_START: Fix Element Plus Table & Calendar Transparency */
html.glass-active .el-table,
html.glass-active .el-table__expanded-cell,
html.glass-active .el-table th.el-table__cell,
html.glass-active .el-table tr,
html.glass-active .el-calendar {
  background-color: transparent !important;
  --el-table-bg-color: transparent !important;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.1) !important;
  --el-table-row-hover-bg-color: rgba(var(--el-color-primary-rgb), 0.1) !important;
  --el-calendar-bg-color: transparent !important;
  --el-calendar-selected-bg-color: rgba(0, 0, 0, 0.25) !important; /* Soft dark selection */
}

/* Enhanced hover and selection states for calendar */
html.glass-active .el-calendar-table .el-calendar-day:hover {
  background-color: rgba(255, 255, 255, 0.2) !important; /* Lighter hover */
}

html.glass-active .el-calendar-table td.is-selected .el-calendar-day {
  background-color: rgba(0, 0, 0, 0.25) !important; /* Soft dark selection */
  color: #fff !important;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.3);
}

/* MODIFIED_BY_AGENT_START: Enhance Calendar Date Visibility in Glass Mode */
/* Make all dates look like subtle bubbles to improve readability on complex backgrounds */
html.glass-active .cell-date {
  background-color: rgba(255, 255, 255, 0.5); /* Subtle white bubble */
  color: #1e293b; /* Dark text for contrast */
  font-weight: 700;
  backdrop-filter: blur(4px); /* Mini blur inside the bubble for extra readability */
  -webkit-backdrop-filter: blur(4px);
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

/* "Today" style overrides */
html.glass-active .cell-date.is-today {
  background-color: var(--el-color-primary) !important;
  color: #fff !important;
  box-shadow: 0 2px 4px rgba(var(--el-color-primary-rgb), 0.4);
}

/* Dark mode adaptation */
html.glass-active.dark .cell-date {
  background-color: rgba(0, 0, 0, 0.5);
  color: #fff;
}

/* Fix Element Plus Tabs Visibility in Glass Mode - Add Glass Background Strip */
html.glass-active .el-tabs__header {
  background: rgba(255, 255, 255, 0.35); /* Visible glass strip */
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 8px 16px;
  border-radius: 10px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border: 1px solid rgba(255,255,255,0.3);
  width: fit-content; /* Only wrap the tabs */
  min-width: 200px; /* Minimum width */
}

/* Remove default tab bottom line */
html.glass-active .el-tabs__nav-wrap::after {
  display: none !important;
}

html.glass-active .el-tabs__item {
  color: #1e293b !important; /* Dark text */
  font-weight: 700 !important;
  text-shadow: none !important;
  padding: 0 16px !important;
}
html.glass-active .el-tabs__item.is-active {
  color: var(--el-color-primary) !important;
  font-weight: 800 !important;
  text-shadow: none !important;
}

/* Fix Table Header Visibility */
html.glass-active .el-table th.el-table__cell {
  background-color: rgba(255, 255, 255, 0.4) !important; /* Semi-transparent white header */
  color: #0f172a !important; /* Dark text */
  font-weight: 700 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.5) !important;
}

/* Enhance Calendar Header (Weekdays) Visibility - Final Polish */
html.glass-active .el-calendar-table thead th {
  background-color: transparent !important; /* No background strip */
  color: #000000 !important; /* Pure black for maximum clarity */
  opacity: 1 !important;
  
  font-weight: 700 !important;
  font-size: 13px !important;
  text-transform: capitalize !important;
  letter-spacing: 0.5px !important;
  padding: 12px 0 !important;
  
  text-shadow: none !important; /* No cheap glow */
  
  /* Divider - Made more visible */
  border-right: 1px solid rgba(255, 255, 255, 0.6) !important; 
  border-bottom: 1px solid rgba(255, 255, 255, 0.6) !important;
}

/* Remove right border for the last header cell */
html.glass-active .el-calendar-table thead th:last-child {
  border-right: none !important;
}

/* Force all children to be dark */
html.glass-active .el-calendar-table thead th * {
  color: #000000 !important;
  font-weight: 700 !important;
  text-shadow: none !important;
  text-transform: capitalize !important;
}

/* Stronger vertical & horizontal dividers for calendar cells */
html.glass-active .el-calendar-table td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.6) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.6) !important;
}

html.glass-active .el-calendar-table tr td:last-child {
  border-right: none !important;
}

/* Ensure the header text isn't overridden by specific element styles */
html.glass-active .el-calendar-table thead th div {
  color: #000000 !important;
}

/* Enhance Page Title & Subtitle Visibility - Premium Glass Style */
html.glass-active .header-info {
  background: rgba(255, 255, 255, 0.3); /* Subtle frosted glass container */
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 12px 20px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px; /* Space below the header */
}

html.glass-active .page-title,
html.glass-active .header-info h2 {
  color: #0f172a !important; /* Sharp dark text */
  font-weight: 700 !important;
  text-shadow: none !important; /* Remove cheap glow */
  margin: 0 !important;
  font-size: 20px !important;
  letter-spacing: -0.5px;
}

html.glass-active .page-subtitle,
html.glass-active .header-info p {
  color: #475569 !important; /* Muted dark text */
  font-weight: 500 !important;
  text-shadow: none !important;
  margin: 0 !important;
  opacity: 1 !important;
  font-size: 13px !important;
}

/* Dark mode adaptation for the header pill */
html.glass-active.dark .header-info {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

html.glass-active.dark .page-title,
html.glass-active.dark .header-info h2 {
  color: #fff !important;
}

html.glass-active.dark .page-subtitle,
html.glass-active.dark .header-info p {
  color: #cbd5e1 !important;
}

/* MODIFIED_BY_AGENT_END */

html.glass-active .el-calendar-table tr:first-child td {
  border-top: 1px solid rgba(255,255,255,0.3);
}

html.glass-active .el-calendar-table td {
  border-bottom: 1px solid rgba(255,255,255,0.3);
  border-right: 1px solid rgba(255,255,255,0.3);
}

html.glass-active.dark .el-table th.el-table__cell {
  --el-table-header-bg-color: rgba(0, 0, 0, 0.2) !important;
}

/* Fix pagination background */
html.glass-active .el-pagination button,
html.glass-active .el-pagination .el-pager li {
  background-color: transparent !important;
}
/* MODIFIED_BY_AGENT_END */

/* Make main container transparent to show body background */
html.glass-active .app-main {
  background-color: transparent !important;
}
/* MODIFIED_BY_AGENT_END */
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

/* MODIFIED_BY_AGENT_START: Settings Drawer Styles */
.settings-section {
  margin-bottom: 20px;
}

.settings-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--app-text-main);
}

.preset-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.preset-item {
  height: 40px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  transition: transform 0.2s;
}

.preset-item:hover {
  transform: scale(1.05);
}

.color-picker-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bg-preview {
  margin-top: 10px;
  width: 100%;
  height: 100px;
  border-radius: 8px;
  background-size: cover;
  background-position: center;
  border: 1px solid var(--app-border-color);
  position: relative;
}

.bg-input-group {
  display: flex;
  gap: 10px;
}

.url-input {
  flex: 1;
}

.remove-bg {
  position: absolute;
  top: 5px;
  right: 5px;
  opacity: 0.8;
}

.remove-bg:hover {
  opacity: 1;
}

/* MODIFIED_BY_AGENT_START: Slider Styles */
.slider-group {
  margin-bottom: 15px;
}

.slider-label {
  font-size: 12px;
  color: var(--app-text-muted);
  display: block;
  margin-bottom: 4px;
}
/* MODIFIED_BY_AGENT_END */
</style>
