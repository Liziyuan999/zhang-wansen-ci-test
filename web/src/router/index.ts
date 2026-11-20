/**
 * 路由配置 + 守卫（未登录 -> /login；admin 路由校验 role）
 */
// ===== 逐行注释：前端路由与导航守卫 =====
// 1. createWebHistory：HTML5 History 模式（无 # 号），需要后端/开发服务器支持 history 回退。
// 2. 路由表：懒加载（() => import(...)）按需分包，减小首屏体积；meta 携带
//    title（浏览器标题）、requiresAuth（需登录）、requiresAdmin（需管理员角色）。
// 3. 公共路由 /login 不设 requiresAuth；/ 重定向到 /document（文档库首页）。
// 4. scrollBehavior：路由切换后回到页面顶部，避免保留上一页滚动位置造成错位跳动。
// 5. beforeEach 守卫：登录校验（未登录携带 redirect 回跳参数跳登录页）、管理员校验、
//    已登录访问 /login 时反跳回 /document，构成完整导航闭环。
// ===== 逐行注释：路由守卫（beforeEach 执行顺序） =====
// 1. 更新 document.title：带产品前缀"知寻 KnowSeek · 页面名"，无 meta.title 时用默认名。
// 2. requiresAuth && !isLoggedIn：未登录拦截，跳 /login 并携带 redirect=原路径，
//    登录成功后可回跳原页面（LoginView 登录逻辑读取该 query）。
// 3. requiresAdmin && !isAdmin：非管理员访问管理页（/admin、/audit-logs）弹无权限提示并回文档页。
// 4. 已登录访问 /login：直接送回 /document，避免重复登录表单。
// 5. 其余情况放行（return true）。
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    redirect: '/document',
  },
  {
    path: '/document',
    name: 'document',
    component: () => import('@/views/DocumentView.vue'),
    meta: { title: '文档库', requiresAuth: true },
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { title: '对话', requiresAuth: true },
  },
  {
    path: '/knowledge-graph',
    name: 'knowledge-graph',
    component: () => import('@/views/KnowledgeGraphView.vue'),
    meta: { title: '知识图谱', requiresAuth: true },
  },
  {
    path: '/agent-task',
    name: 'agent-task',
    component: () => import('@/views/AgentTaskView.vue'),
    meta: { title: 'Agent 任务', requiresAuth: true },
  },
  {
    path: '/team',
    name: 'team',
    component: () => import('@/views/TeamView.vue'),
    meta: { title: '组织中心', requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { title: '个人中心', requiresAuth: true },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '数据看板', requiresAuth: true },
  },
  {
    path: '/demo',
    name: 'demo',
    component: () => import('@/views/DemoModeView.vue'),
    meta: { title: '演示模式', requiresAuth: true },
  },
  {
    path: '/audit-logs',
    name: 'audit-logs',
    component: () => import('@/views/AuditLogView.vue'),
    meta: { title: '审计日志', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/report/weekly',
    name: 'report-weekly',
    component: () => import('@/views/WeeklyReportView.vue'),
    meta: { title: 'AI 周报', requiresAuth: true },
  },
  {
    path: '/team/accept',
    name: 'team-accept',
    component: () => import('@/views/TeamAcceptView.vue'),
    meta: { title: '接受邀请', requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/AdminView.vue'),
    meta: { title: '管理后台', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/document',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 路由切换后回到页面顶部：避免保留上一页滚动位置造成的内容错位跳动
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  document.title = to.meta.title ? `知寻 KnowSeek · ${to.meta.title}` : '知寻 KnowSeek'

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    ElMessage?.error?.('无权限：需要管理员身份')
    return { path: '/document' }
  }
  if (to.path === '/login' && userStore.isLoggedIn) {
    return { path: '/document' }
  }
  return true
})

export default router
