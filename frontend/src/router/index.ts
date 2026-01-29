import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/Layout/AppLayout.vue'
import { useSystemStore } from '@/stores/system'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: 'Login', hidden: true }
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard/Index.vue'),
        meta: { title: 'Dashboard', icon: 'Odometer', viewPerm: 'view_dashboard' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/Tasks/Index.vue'),
        meta: { title: 'Tasks', icon: 'List', viewPerm: 'view_tasks' }
      },
      {
        path: 'tasks/create',
        name: 'CreateTask',
        component: () => import('@/views/Tasks/Create.vue'),
        meta: { title: 'Create Task', hidden: true }
      },
      {
        path: 'tasks/logs/:id',
        name: 'TaskLogs',
        component: () => import('@/views/Tasks/Logs.vue'),
        meta: { title: 'Task Logs', hidden: true }
      },
      {
        path: 'connections',
        name: 'Connections',
        component: () => import('@/views/Connections/Index.vue'),
        meta: { title: 'Connections', icon: 'Link', viewPerm: 'view_tasks' }
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogMonitor/Index.vue'),
        meta: { title: 'Log Monitor', icon: 'Monitor', viewPerm: 'view_logs' }
      },
      {
        path: 'ai-ops',
        name: 'AIOps',
        component: () => import('@/views/AIOps/Index.vue'),
        meta: { title: 'AI Fault Analysis', icon: 'Cpu' }
      },
      {
        path: 'schedules',
        name: 'Schedules',
        component: () => import('@/views/Schedules/Index.vue'),
        meta: { title: 'Schedules', icon: 'Calendar' }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/System/Index.vue'),
        meta: { title: 'System', icon: 'Setting', viewPerm: 'view_inspection' }
      },
      {
        path: 'deploy',
        name: 'Deploy',
        component: () => import('@/views/Deploy/Index.vue'),
        meta: { title: 'Deploy', icon: 'Upload', viewPerm: 'view_deploy' }
      },
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/Permissions/Index.vue'),
        meta: { title: 'Permissions', icon: 'Lock' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to, from, next) => {
  const systemStore = useSystemStore()
  if (!systemStore.currentUser) {
    try {
      await systemStore.fetchCurrentUser()
    } catch {}
  }
  const perm = (to.meta as any)?.viewPerm as string | undefined
  if (perm && !(systemStore.isAdmin || systemStore.hasPermission(perm))) {
    return next('/logs')
  }
  next()
})

export default router
