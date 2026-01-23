import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/Layout/AppLayout.vue'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard/Index.vue'),
        meta: { title: 'Dashboard', icon: 'Odometer' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/Tasks/Index.vue'),
        meta: { title: 'Tasks', icon: 'List' }
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
        meta: { title: 'Connections', icon: 'Link' }
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogMonitor/Index.vue'),
        meta: { title: 'Log Monitor', icon: 'Monitor' }
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
        meta: { title: 'System', icon: 'Setting' }
      },
      {
        path: 'deploy',
        name: 'Deploy',
        component: () => import('@/views/Deploy/Index.vue'),
        meta: { title: 'Deploy', icon: 'Upload' }
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

export default router
