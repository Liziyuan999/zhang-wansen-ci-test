<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Bell, Check, Fold, Expand, Document, ChatDotRound, Promotion, OfficeBuilding, User, Setting, DataAnalysis, Connection, MagicStick } from '@element-plus/icons-vue'
import { listNotices, markNoticeRead, getUnreadCount, markAllRead as markAllReadApi, openNoticeSSE } from '@/api/notice'
import type { UserNotificationItem } from '@/types'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const showTopbar = computed(() => route.path !== '/login')
const showDynamicBg = computed(() => route.path !== '/login')
const isAdmin = computed(() => userStore.isAdmin)
const userName = computed(() => userStore.userInfo?.username || '用户')
const deptName = computed(() => userStore.deptName)
const avatarChar = computed(() => (userStore.userInfo?.username || '知').charAt(0).toUpperCase())

/* ---------------- 通知中心（分类/分页/已读/SSE 实时） ---------------- */
const noticeDrawer = ref(false)
const notices = ref<UserNotificationItem[]>([])
const noticeLoading = ref(false)
const noticeUnread = ref(0)
const noticeCategoryUnread = ref({ team: 0, approval: 0, system: 0 })
const noticeCategory = ref('')
const noticePage = ref(1)
const noticePageSize = 10
const noticeTotal = ref(0)
let noticeTimer: ReturnType<typeof setInterval> | null = null
let closeNoticeSSE: (() => void) | null = null

async function refreshUnread() {
  try {
    const data = await getUnreadCount()
    noticeUnread.value = data?.count ?? 0
    noticeCategoryUnread.value = {
      team: data?.team ?? 0,
      approval: data?.approval ?? 0,
      system: data?.system ?? 0,
    }
  } catch {
    // 未登录或网络异常时静默
  }
}

async function refreshNotices() {
  if (!noticeDrawer.value) return
  noticeLoading.value = true
  try {
    const data = await listNotices({
      category: noticeCategory.value,
      page: noticePage.value,
      page_size: noticePageSize,
    })
    notices.value = data?.items ?? []
    noticeTotal.value = data?.total ?? 0
    await refreshUnread()
  } catch {
    // 拦截器已提示
  } finally {
    noticeLoading.value = false
  }
}

function openNoticeDrawer() {
  noticeDrawer.value = true
  refreshNotices()
}

function switchNoticeCategory(category: string) {
  noticeCategory.value = category
  noticePage.value = 1
  refreshNotices()
}

function handleNoticePageChange(page: number) {
  noticePage.value = page
  refreshNotices()
}

async function handleMarkRead(item: UserNotificationItem) {
  if (item.read) return
  try {
    await markNoticeRead(item.id)
    item.read = true
    noticeUnread.value = Math.max(0, noticeUnread.value - 1)
    const key = item.category as 'team' | 'approval' | 'system'
    if (key in noticeCategoryUnread.value) {
      noticeCategoryUnread.value[key] = Math.max(0, noticeCategoryUnread.value[key] - 1)
    }
  } catch {
    // 拦截器已提示
  }
}

async function markAllRead() {
  if (!noticeUnread.value) {
    ElMessage.info('暂无未读通知')
    return
  }
  try {
    await markAllReadApi()
    notices.value.forEach((n) => (n.read = true))
    noticeUnread.value = 0
    noticeCategoryUnread.value = { team: 0, approval: 0, system: 0 }
    ElMessage.success('已全部标记为已读')
  } catch {
    // 拦截器已提示
  }
}

const noticeCategoryMeta: Record<string, { label: string; type: 'primary' | 'success' | 'warning' | 'info' }> = {
  team: { label: '团队动态', type: 'primary' },
  approval: { label: '审批消息', type: 'warning' },
  system: { label: '系统消息', type: 'success' },
}

function noticeCategoryTag(category: string) {
  return noticeCategoryMeta[category] || { label: category || '通知', type: 'info' as const }
}

function handleNoticeSSEEvent(evt: { unread: number; latest_id: number | null }) {
  noticeUnread.value = evt.unread ?? 0
  if (noticeDrawer.value) {
    refreshNotices()
  } else {
    refreshUnread()
  }
}

onMounted(() => {
  if (showTopbar.value) {
    refreshUnread()
    closeNoticeSSE = openNoticeSSE(handleNoticeSSEEvent)
    // SSE 断线兜底：30s 轮询未读数，保证实时性
    noticeTimer = setInterval(refreshUnread, 30000)
  }
})

onUnmounted(() => {
  if (noticeTimer) clearInterval(noticeTimer)
  if (closeNoticeSSE) closeNoticeSSE()
})

const navItems = computed(() => {
  const items = [
    { path: '/document', label: '文档库' },
    { path: '/chat', label: 'AI对话' },
    { path: '/agent-task', label: 'Agent 任务' },
    { path: '/dashboard', label: '数据看板' },
    { path: '/demo', label: '演示模式' },
  ]
  if (isAdmin.value) {
    items.push({ path: '/admin', label: '管理后台' })
  }
  return items
})

/** 移动端导航抽屉 */
const mobileNavOpen = ref(false)
const mobileNavItems = computed(() => {
  const items = [
    { path: '/document', label: '文档库', icon: Document },
    { path: '/chat', label: 'AI对话', icon: ChatDotRound },
    { path: '/knowledge-graph', label: '知识图谱', icon: Connection },
    { path: '/agent-task', label: 'Agent 任务', icon: Promotion },
    { path: '/dashboard', label: '数据看板', icon: DataAnalysis },
    { path: '/demo', label: '演示模式', icon: MagicStick },
    { path: '/report/weekly', label: 'AI 周报', icon: Document },
    { path: '/team', label: '组织中心', icon: OfficeBuilding },
    { path: '/profile', label: '个人中心', icon: User },
  ]
  if (isAdmin.value) {
    items.push({ path: '/audit-logs', label: '审计日志', icon: Setting })
    items.push({ path: '/admin', label: '管理后台', icon: Setting })
  }
  return items
})

function goMobileNav(path: string) {
  mobileNavOpen.value = false
  if (route.path !== path) router.push(path)
}

/** 退出登录：确认后展示加载态动效，短暂过渡后跳转登录页 */
const loggingOut = ref(false)

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  loggingOut.value = true
  try {
    await new Promise((r) => setTimeout(r, 1200))
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <!-- 退出登录过渡遮罩 -->
    <transition name="ks-logout">
      <div v-if="loggingOut" class="logout-overlay">
        <div class="logout-halo"></div>
        <div class="logout-badge">知</div>
        <div class="logout-name">知寻 <em>KnowSeek</em></div>
        <div class="logout-spinner">
          <i></i>
        </div>
        <div class="logout-tip">正在安全退出…</div>
      </div>
    </transition>

    <header v-if="showTopbar" class="ks-topbar">
      <router-link to="/document" class="ks-logo">
        <span class="ks-logo-badge">知</span>
        <span class="ks-logo-name">知寻 KnowSeek</span>
        <span class="ks-logo-sub">让企业知识触手可及</span>
      </router-link>

      <nav class="ks-nav">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path">
          {{ item.label }}
        </router-link>
      </nav>

      <div class="ks-user">
        <el-tooltip content="团队通知" placement="bottom" :show-after="300">
          <button class="ks-bell" type="button" @click="openNoticeDrawer">
            <el-icon class="ks-bell-icon"><Bell /></el-icon>
            <span v-if="noticeUnread > 0" class="ks-bell-badge">{{ noticeUnread > 99 ? '99+' : noticeUnread }}</span>
          </button>
        </el-tooltip>

        <button class="ks-nav-toggle" type="button" @click="mobileNavOpen = true" aria-label="打开导航">
          <el-icon><Fold /></el-icon>
        </button>

        <el-dropdown trigger="hover" popper-class="ks-user-popper">
          <span class="ks-user-info">
            <span class="ks-avatar">{{ avatarChar }}</span>
            <span class="ks-user-name">{{ userName }}</span>
            <span v-if="deptName" class="ks-user-dept">{{ deptName }}</span>
            <el-icon class="ks-user-arrow"><Expand /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled class="ks-user-mail">{{ userStore.userInfo?.email }}</el-dropdown-item>
              <el-dropdown-item divided @click="router.push('/profile')">
                <el-icon class="ks-user-menu-icon"><User /></el-icon>个人中心
              </el-dropdown-item>
              <el-dropdown-item @click="router.push('/team')">
                <el-icon class="ks-user-menu-icon"><OfficeBuilding /></el-icon>组织中心
              </el-dropdown-item>
              <el-dropdown-item @click="router.push('/dashboard')">
                <el-icon class="ks-user-menu-icon"><DataAnalysis /></el-icon>数据看板
              </el-dropdown-item>
              <el-dropdown-item @click="router.push('/report/weekly')">
                <el-icon class="ks-user-menu-icon"><Document /></el-icon>AI 周报
              </el-dropdown-item>
              <el-dropdown-item v-if="isAdmin" @click="router.push('/audit-logs')">
                <el-icon class="ks-user-menu-icon"><Setting /></el-icon>审计日志
              </el-dropdown-item>
              <el-dropdown-item v-if="isAdmin" @click="router.push('/admin')">
                <el-icon class="ks-user-menu-icon"><Setting /></el-icon>管理后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <span v-if="loggingOut" class="ks-logout-loading">
                  <span class="ks-spinner"></span>
                  正在退出…
                </span>
                <span v-else>退出登录</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 移动端导航抽屉 -->
    <el-drawer v-model="mobileNavOpen" direction="ltr" size="280px" class="ks-mobile-nav" append-to-body>
      <template #header>
        <div class="mobile-nav-head">
          <span class="ks-logo-badge">知</span>
          <span class="ks-logo-name">知寻 KnowSeek</span>
        </div>
      </template>
      <div class="mobile-nav-list">
        <div
          v-for="item in mobileNavItems"
          :key="item.path"
          class="mobile-nav-item"
          :class="{ active: route.path === item.path }"
          @click="goMobileNav(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </div>
      </div>
      <template #footer>
        <div class="mobile-nav-user">
          <span class="ks-avatar">{{ avatarChar }}</span>
          <div class="mobile-nav-user-info">
            <div class="mobile-nav-user-name">{{ userName }}</div>
            <div class="mobile-nav-user-mail">{{ userStore.userInfo?.email }}</div>
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- 通知中心抽屉（分类 / 分页 / 已读 / SSE 实时） -->
    <el-drawer v-model="noticeDrawer" title="通知中心" size="440px" class="ks-notice-drawer" append-to-body>
      <div class="notice-drawer-body">
        <div class="notice-category-bar">
          <button
            class="notice-cat"
            :class="{ active: noticeCategory === '' }"
            type="button"
            @click="switchNoticeCategory('')"
          >
            全部
            <span v-if="noticeUnread > 0" class="notice-cat-badge">{{ noticeUnread }}</span>
          </button>
          <button
            class="notice-cat"
            :class="{ active: noticeCategory === 'team' }"
            type="button"
            @click="switchNoticeCategory('team')"
          >
            团队动态
            <span v-if="noticeCategoryUnread.team > 0" class="notice-cat-badge">{{ noticeCategoryUnread.team }}</span>
          </button>
          <button
            class="notice-cat"
            :class="{ active: noticeCategory === 'approval' }"
            type="button"
            @click="switchNoticeCategory('approval')"
          >
            审批消息
            <span v-if="noticeCategoryUnread.approval > 0" class="notice-cat-badge">{{ noticeCategoryUnread.approval }}</span>
          </button>
          <button
            class="notice-cat"
            :class="{ active: noticeCategory === 'system' }"
            type="button"
            @click="switchNoticeCategory('system')"
          >
            系统消息
            <span v-if="noticeCategoryUnread.system > 0" class="notice-cat-badge">{{ noticeCategoryUnread.system }}</span>
          </button>
        </div>

        <div v-loading="noticeLoading" class="notice-list-wrap">
          <div v-if="notices.length" class="notice-list">
            <div
              v-for="item in notices"
              :key="item.id"
              class="notice-item"
              :class="{ unread: !item.read }"
              @click="handleMarkRead(item)"
            >
              <div class="notice-head">
                <span class="notice-dot" :class="{ unread: !item.read }"></span>
                <el-tag size="small" effect="light" :type="noticeCategoryTag(item.category).type">
                  {{ noticeCategoryTag(item.category).label }}
                </el-tag>
                <span class="notice-title">{{ item.title }}</span>
              </div>
              <div class="notice-content">{{ item.content }}</div>
              <div class="notice-meta">
                <span>{{ item.create_time }}</span>
                <span v-if="!item.read" class="notice-read-hint">
                  <el-icon><Check /></el-icon> 点击标记已读
                </span>
              </div>
            </div>
          </div>
          <el-empty v-else-if="!noticeLoading" :description="noticeCategory ? '该分类暂无通知' : '暂无通知'" :image-size="80" />
        </div>
      </div>
      <template #footer>
        <div class="notice-footer">
          <span class="notice-footer-tip">未读 {{ noticeUnread }} 条</span>
          <el-pagination
            v-if="noticeTotal > noticePageSize"
            small
            layout="prev, pager, next"
            :total="noticeTotal"
            :page-size="noticePageSize"
            :current-page="noticePage"
            background
            @current-change="handleNoticePageChange"
          />
          <el-button size="small" type="primary" plain :icon="Check" @click="markAllRead">全部标为已读</el-button>
        </div>
      </template>
    </el-drawer>

    <main class="app-content" :class="{ 'ks-dynamic-bg': showDynamicBg }">
      <template v-if="showDynamicBg">
        <span class="ks-particle p1"></span>
        <span class="ks-particle p2"></span>
        <span class="ks-particle p3"></span>
        <span class="ks-particle p4"></span>
        <span class="ks-particle p5"></span>
        <span class="ks-particle p6"></span>
      </template>
      <router-view v-slot="{ Component }">
        <transition name="ks-route" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-content {
  flex: 1;
}

.el-dropdown-link {
  color: #f8fafc;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.ks-user-info {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 5px 14px 5px 6px;
  border-radius: 999px;
  color: #f8fafc;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  transition: all 0.25s ease;
  user-select: none;
}

.ks-user-info:hover {
  background: rgba(255, 255, 255, 0.13);
  border-color: rgba(147, 197, 253, 0.4);
  box-shadow: 0 4px 16px rgba(2, 8, 23, 0.26);
}

/* 顶栏消息铃铛 */
.ks-bell {
  position: relative;
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #dbeafe;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  cursor: pointer;
  transition: all 0.25s ease;
  margin-right: 8px;
}

.ks-bell:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(147, 197, 253, 0.5);
  box-shadow: 0 4px 16px rgba(2, 8, 23, 0.26);
}

.ks-bell-icon {
  font-size: 18px;
}

.ks-bell-badge {
  position: absolute;
  top: -4px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ef4444, #f97316);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.5);
  border: 2px solid rgba(15, 23, 42, 0.9);
}

/* 通知抽屉 */
.notice-drawer-body {
  min-height: 240px;
}

/* 分类页签 */
.notice-category-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.notice-cat {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
}

.notice-cat:hover {
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.notice-cat.active {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #93c5fd;
  color: #1d4ed8;
}

.notice-cat-badge {
  min-width: 17px;
  height: 17px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 17px;
  text-align: center;
}

.notice-list-wrap {
  min-height: 120px;
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notice-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.notice-item:hover {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
}

.notice-item.unread {
  background: linear-gradient(180deg, #eff6ff, #f8fbff);
  border-color: #bfdbfe;
}

.notice-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notice-dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: transparent;
}

.notice-dot.unread {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}

.notice-title {
  flex: 1;
  font-size: 14px;
  font-weight: 700;
  color: var(--ks-text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notice-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ks-text-body);
  margin-top: 6px;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notice-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

.notice-read-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ks-primary);
  margin-top: 8px;
}

.notice-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 2px;
}

.notice-footer-tip {
  font-size: 13px;
  color: #64748b;
}

.ks-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.4);
}

.ks-user-name {
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
  line-height: 1;
}

.ks-user-dept {
  font-size: 11px;
  line-height: 1;
  color: #bfdbfe;
  background: rgba(37, 99, 235, 0.28);
  border: 1px solid rgba(147, 197, 253, 0.3);
  border-radius: 999px;
  padding: 3px 9px;
  font-weight: 500;
  white-space: nowrap;
}

.ks-user-arrow {
  font-size: 12px;
  color: rgba(203, 213, 225, 0.9);
  transition: transform 0.2s ease;
}

.ks-user-info:hover .ks-user-arrow {
  transform: translateY(1px);
}

.ks-user-mail {
  color: #64748b;
}

/* 路由切换过渡：纯淡入淡出（不位移、不缩放、不模糊），
   消除页面切换时的跳动/颠簸感，兼顾登录页与主内容区 */
.ks-route-enter-active {
  transition: opacity 0.22s ease;
}

.ks-route-leave-active {
  transition: opacity 0.1s ease;
}

.ks-route-enter-from,
.ks-route-leave-to {
  opacity: 0;
}

.ks-route-enter-to,
.ks-route-leave-from {
  opacity: 1;
}

/* 退出登录加载态 */
.ks-logout-loading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ks-spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(147, 197, 253, 0.32);
  border-top-color: #fff;
  animation: ks-spin 0.7s linear infinite;
}

@keyframes ks-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 用户下拉菜单图标 */
.ks-user-menu-icon {
  margin-right: 8px;
  font-size: 15px;
  vertical-align: -2px;
}

/* 移动端导航按钮（默认隐藏，窄屏显示） */
.ks-nav-toggle {
  display: none;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #dbeafe;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  cursor: pointer;
  transition: all 0.25s ease;
  margin-right: 8px;
  font-size: 18px;
}

.ks-nav-toggle:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(147, 197, 253, 0.5);
}

/* 移动端导航抽屉 */
.mobile-nav-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mobile-nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mobile-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-title);
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.mobile-nav-item .el-icon {
  font-size: 17px;
  color: #64748b;
}

.mobile-nav-item:hover {
  background: #f1f5f9;
}

.mobile-nav-item.active {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  color: #1d4ed8;
}

.mobile-nav-item.active .el-icon {
  color: #2563eb;
}

.mobile-nav-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-top: 1px solid #eef2f7;
}

.mobile-nav-user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mobile-nav-user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-title);
}

.mobile-nav-user-mail {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 窄屏折叠逻辑已统一移至 theme.css 全局断点（避免 scoped 被全局样式覆盖） */
@media (max-width: 768px) {
  .ks-user-dept {
    display: none;
  }
  .ks-user-name {
    display: none;
  }
  .ks-bell {
    width: 36px;
    height: 36px;
    margin-right: 4px;
  }
  .ks-nav-toggle {
    width: 36px;
    height: 36px;
    margin-right: 4px;
  }
  .ks-user-info {
    padding: 4px 10px 4px 4px;
    gap: 6px;
  }
}

/* ---------- 退出登录过渡动效 ---------- */
.logout-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: linear-gradient(150deg, #060d1f 0%, #0b1730 45%, #10254d 80%, #1e3a8a 130%);
  overflow: hidden;
}

.logout-halo {
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.38), transparent 68%);
  filter: blur(70px);
  animation: logout-halo-pulse 0.9s ease-in-out infinite;
  pointer-events: none;
}

.logout-badge {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 24px;
  background: var(--ks-primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 18px 48px rgba(37, 99, 235, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  animation: logout-badge-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.logout-name {
  position: relative;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #f8fafc;
  animation: ks-fade-in 0.4s ease 0.1s both;
}

.logout-name em {
  font-style: normal;
  background: linear-gradient(90deg, #93c5fd, #a5b4fc);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.logout-spinner {
  position: relative;
  width: 46px;
  height: 46px;
  margin-top: 8px;
  animation: ks-fade-in 0.4s ease 0.2s both;
}

.logout-spinner i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3px solid rgba(148, 163, 184, 0.25);
  border-top-color: #93c5fd;
  border-right-color: #60a5fa;
  animation: logout-spin 0.75s linear infinite;
}

.logout-tip {
  position: relative;
  font-size: 12px;
  letter-spacing: 2px;
  color: #93c5fd;
  animation: ks-fade-in 0.4s ease 0.3s both;
}

.ks-logout-enter-active {
  transition: opacity 0.35s ease;
}

.ks-logout-enter-from {
  opacity: 0;
}

.ks-logout-leave-active {
  transition: opacity 0.3s ease;
}

.ks-logout-leave-to {
  opacity: 0;
}

@keyframes logout-badge-in {
  from { opacity: 0; transform: translateY(16px) scale(0.88) rotate(-8deg); }
  to { opacity: 1; transform: translateY(0) scale(1) rotate(0deg); }
}

@keyframes logout-halo-pulse {
  0%, 100% { opacity: 0.55; transform: scale(0.95); }
  50% { opacity: 1; transform: scale(1.05); }
}

@keyframes logout-spin {
  to { transform: rotate(360deg); }
}
</style>
