import { createRouter, createWebHistory } from 'vue-router'
import { getUser } from '@/utils/auth'

const routes = [
  // 公开路由（不需要登录）
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { title: '登录', icon: 'Lock' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/login/Register.vue'),
    meta: { title: '注册', icon: 'User' },
  },
  // 受保护路由（需要登录）
  {
    path: '/',
    component: () => import('@/views/layout/Manage.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'agent',
        name: 'AgentWorkspace',
        component: () => import('@/views/agent/AgentWorkspace.vue'),
        meta: { title: '线索研判', icon: 'Operation' },
      },
      {
        path: 'detect',
        name: 'Detect',
        redirect: '/detect/text',
        meta: { title: '多模态检测', icon: 'Monitor' },
        children: [
          {
            path: 'text',
            name: 'TextDetect',
            component: () => import('@/views/detect/TextDetect.vue'),
            meta: { title: '文本检测', icon: 'Document' },
          },
          {
            path: 'voice',
            name: 'VoiceDetect',
            component: () => import('@/views/detect/VoiceDetect.vue'),
            meta: { title: '语音检测', icon: 'Microphone' },
          },
          {
            path: 'image',
            name: 'ImageDetect',
            component: () => import('@/views/detect/ImageDetect.vue'),
            meta: { title: '图片检测', icon: 'Picture' },
          },
        ],
      },
      {
        path: 'records',
        name: 'DetectRecords',
        component: () => import('@/views/records/DetectRecords.vue'),
        meta: { title: '检测记录', icon: 'List' },
      },
      {
        path: 'blockchain',
        name: 'BlockchainCert',
        component: () => import('@/views/blockchain/BlockchainCert.vue'),
        meta: { title: '区块链存证', icon: 'Link' },
      },
      {
        path: 'watermark',
        name: 'WatermarkTool',
        component: () => import('@/views/watermark/WatermarkTool.vue'),
        meta: { title: '水印工具', icon: 'Stamp' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/Profile.vue'),
        meta: { title: '个人中心', icon: 'UserFilled' },
      },
      {
        path: 'password',
        name: 'Password',
        component: () => import('@/views/profile/Password.vue'),
        meta: { title: '修改密码', icon: 'Key' },
      },
      {
        path: 'system',
        name: 'System',
        redirect: '/system/user',
        meta: { title: '系统管理', icon: 'Setting' },
        children: [
          {
            path: 'user',
            name: 'UserManage',
            component: () => import('@/views/system/UserManage.vue'),
            meta: { title: '用户管理', icon: 'User' },
          },
          {
            path: 'role',
            name: 'RoleManage',
            component: () => import('@/views/system/RoleManage.vue'),
            meta: { title: '角色管理', icon: 'Avatar' },
          },
          {
            path: 'menu',
            name: 'MenuManage',
            component: () => import('@/views/system/MenuManage.vue'),
            meta: { title: '菜单管理', icon: 'Menu' },
          },
          {
            path: 'log',
            name: 'OpLog',
            component: () => import('@/views/system/OpLog.vue'),
            meta: { title: '操作日志', icon: 'Notebook' },
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫
router.beforeEach((to) => {
  const user = getUser()
  const isLoggedIn = !!user

  // 访问受保护路由但未登录 → 重定向登录页
  if (!isLoggedIn && to.path !== '/login' && to.path !== '/register') {
    return '/login'
  }

  // 已登录访问登录/注册页 → 重定向仪表盘
  if (isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    return '/dashboard'
  }

  // 设置页面标题
  document.title = to.meta.title || 'AI反诈骗检测系统'

  return true
})

export default router
