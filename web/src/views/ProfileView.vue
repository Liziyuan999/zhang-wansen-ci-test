<script setup lang="ts">
/**
 * 个人中心：资料展示与编辑（昵称/部门）、账号安全（修改密码）
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Lock, OfficeBuilding, Calendar, Clock, Refresh, DataAnalysis, Document, InfoFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getProfile, updateProfile, listDepartments, changePassword } from '@/api/user'
import type { DeptInfo, UserProfile } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const isAdmin = computed(() => userStore.isAdmin)

const profile = ref<UserProfile | null>(null)
const loading = ref(false)
const saving = ref(false)

const depts = ref<DeptInfo[]>([])
const deptLoading = ref(false)

const avatarChar = computed(() => (profile.value?.username || '知').charAt(0).toUpperCase())
const roleLabel = computed(() => {
  const r = profile.value?.role
  if (r === 'admin') return { label: '管理员', type: 'warning' as const }
  if (r === 'staff') return { label: '员工', type: 'primary' as const }
  return { label: r || '-', type: 'info' as const }
})
const statusLabel = computed(() => {
  const s = profile.value?.status
  if (s === 'active') return { label: '正常', type: 'success' as const }
  if (s === 'disabled') return { label: '已禁用', type: 'danger' as const }
  return { label: s || '-', type: 'info' as const }
})

/* ---------------- 资料编辑 ---------------- */
const profileForm = reactive({ username: '', dept_id: null as number | null })

async function loadProfile() {
  loading.value = true
  try {
    profile.value = await getProfile()
    profileForm.username = profile.value.username
    profileForm.dept_id = profile.value.dept_id
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadDepts() {
  deptLoading.value = true
  try {
    depts.value = await listDepartments()
  } catch {
    // 拦截器已提示
  } finally {
    deptLoading.value = false
  }
}

async function handleSaveProfile() {
  const name = profileForm.username.trim()
  if (!name) {
    ElMessage.warning('昵称不能为空')
    return
  }
  const payload: { username?: string; dept_id?: number } = {}
  if (name !== profile.value?.username) payload.username = name
  if (profileForm.dept_id !== profile.value?.dept_id) payload.dept_id = profileForm.dept_id ?? undefined
  if (!Object.keys(payload).length) {
    ElMessage.info('没有需要修改的内容')
    return
  }
  saving.value = true
  try {
    const updated = await updateProfile(payload)
    profile.value = updated
    profileForm.username = updated.username
    profileForm.dept_id = updated.dept_id
    // 同步顶栏展示信息
    if (userStore.userInfo) {
      userStore.setUserInfo({
        ...userStore.userInfo,
        username: updated.username,
        dept_id: updated.dept_id,
        dept_name: updated.dept_name,
      })
    }
    ElMessage.success('资料已更新')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

/* ---------------- 修改密码 ---------------- */
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const pwdSaving = ref(false)
/** 是否已设置密码（老用户仅验证码登录时为 false，需先设置） */
const hasPassword = computed(() => !!profile.value?.has_password)

async function handleChangePassword() {
  if (hasPassword.value) {
    if (!pwdForm.old_password || !pwdForm.new_password) {
      ElMessage.warning('请填写原密码与新密码')
      return
    }
  } else {
    if (!pwdForm.new_password) {
      ElMessage.warning('请设置新密码')
      return
    }
  }
  if (pwdForm.new_password.length < 6) {
    ElMessage.warning('新密码长度至少 6 位')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  try {
    await ElMessageBox.confirm(
      hasPassword.value
        ? '确定修改密码吗？修改后下次登录将使用新密码。'
        : '确定设置登录密码吗？设置后可使用邮箱 + 密码直接登录。',
      hasPassword.value ? '修改密码' : '设置密码',
      {
        confirmButtonText: hasPassword.value ? '确认修改' : '确认设置',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  pwdSaving.value = true
  try {
    await changePassword(
      hasPassword.value
        ? { old_password: pwdForm.old_password, new_password: pwdForm.new_password }
        : { new_password: pwdForm.new_password },
    )
    ElMessage.success(hasPassword.value ? '密码修改成功' : '密码设置成功，现在可以使用邮箱 + 密码登录了')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    // 刷新密码状态：设置后 has_password 变为 true
    profile.value = { ...(profile.value as UserProfile), has_password: true }
  } catch {
    // 拦截器已提示
  } finally {
    pwdSaving.value = false
  }
}

onMounted(() => {
  loadProfile()
  loadDepts()
})
</script>

<template>
  <div class="ks-page profile-page">
    <div class="page-header">
      <h2 class="ks-page-title">个人中心</h2>
      <el-button :icon="Refresh" @click="loadProfile">刷新</el-button>
    </div>

    <div v-loading="loading" class="profile-grid">
      <!-- 左侧：身份卡 -->
      <div class="profile-side">
        <div class="profile-card">
          <div class="avatar-badge">{{ avatarChar }}</div>
          <div class="profile-name">{{ profile?.username || '-' }}</div>
          <div class="profile-mail">{{ profile?.email || '-' }}</div>
          <div class="profile-tags">
            <el-tag size="small" :type="roleLabel.type" effect="light">{{ roleLabel.label }}</el-tag>
            <el-tag size="small" :type="statusLabel.type" effect="light">{{ statusLabel.label }}</el-tag>
            <el-tag v-if="profile?.dept_name" size="small" type="info" effect="plain">{{ profile.dept_name }}</el-tag>
          </div>
          <div class="profile-stats">
            <div class="stat-item">
              <el-icon><Calendar /></el-icon>
              <div class="stat-body">
                <span class="stat-label">注册时间</span>
                <span class="stat-value">{{ profile?.create_time ? profile.create_time.slice(0, 16).replace('T', ' ') : '-' }}</span>
              </div>
            </div>
            <div class="stat-item">
              <el-icon><Clock /></el-icon>
              <div class="stat-body">
                <span class="stat-label">最近登录</span>
                <span class="stat-value">{{ profile?.last_login_time ? profile.last_login_time.slice(0, 16).replace('T', ' ') : '-' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：快捷工具 + 资料编辑 + 账号安全 -->
      <div class="profile-main">
        <div class="profile-card tool-card">
          <div class="section-title">
            <el-icon><OfficeBuilding /></el-icon>
            快捷工具
            <span class="section-sub">企业运营效率工具</span>
          </div>
          <div class="tool-grid">
            <div class="tool-item" @click="router.push('/dashboard')">
              <div class="tool-icon"><el-icon><DataAnalysis /></el-icon></div>
              <div class="tool-info">
                <b>数据看板</b>
                <span>企业核心指标与近 7 日趋势</span>
              </div>
            </div>
            <div class="tool-item" @click="router.push('/report/weekly')">
              <div class="tool-icon"><el-icon><Document /></el-icon></div>
              <div class="tool-info">
                <b>AI 周报</b>
                <span>LangGraph 智能生成企业周报</span>
              </div>
            </div>
            <div v-if="isAdmin" class="tool-item" @click="router.push('/audit-logs')">
              <div class="tool-icon"><el-icon><Lock /></el-icon></div>
              <div class="tool-info">
                <b>审计日志</b>
                <span>全站操作留痕查询（管理员）</span>
              </div>
            </div>
          </div>
        </div>

        <div class="profile-card section-card">
          <div class="section-title">
            <el-icon><User /></el-icon>
            个人资料
            <span class="section-sub">邮箱为登录账号，不可修改</span>
          </div>
          <el-form label-position="top" class="profile-form">
            <div class="form-row">
              <el-form-item label="昵称">
                <el-input v-model="profileForm.username" placeholder="请输入昵称" maxlength="32" />
              </el-form-item>
              <el-form-item label="部门">
                <el-select
                  v-model="profileForm.dept_id"
                  placeholder="选择部门"
                  :loading="deptLoading"
                  class="dept-select"
                >
                  <el-option v-for="d in depts" :key="d.id" :label="d.dept_name" :value="d.id" />
                </el-select>
              </el-form-item>
            </div>
            <el-form-item label="邮箱">
              <el-input :model-value="profile?.email || ''" disabled />
            </el-form-item>
            <div class="form-actions">
              <el-button type="primary" :loading="saving" :icon="Refresh" @click="handleSaveProfile">保存资料</el-button>
            </div>
          </el-form>
        </div>

        <div class="profile-card section-card">
          <div class="section-title">
            <el-icon><Lock /></el-icon>
            账号安全
            <span class="section-sub">
              {{ hasPassword ? '定期修改密码，保障账号安全' : '您尚未设置密码，设置后可使用邮箱 + 密码登录' }}
            </span>
          </div>
          <!-- 无密码老用户：首次设置引导 -->
          <div v-if="!hasPassword" class="pwd-first-set">
            <el-icon><InfoFilled /></el-icon>
            <span>当前账号暂未设置密码，仅支持验证码登录。请设置一个登录密码，之后即可使用邮箱 + 密码直接登录。</span>
          </div>
          <el-form label-position="top" class="profile-form">
            <div class="form-row">
              <el-form-item v-if="hasPassword" label="原密码">
                <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" autocomplete="current-password" />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 6 位" autocomplete="new-password" />
              </el-form-item>
            </div>
            <el-form-item label="确认新密码">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" autocomplete="new-password" />
            </el-form-item>
            <div class="form-actions">
              <el-button type="warning" :loading="pwdSaving" :icon="Lock" @click="handleChangePassword">
                {{ hasPassword ? '修改密码' : '设置密码' }}
              </el-button>
            </div>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.tool-card {
  margin-bottom: 16px;
}
.tool-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 6px;
}
.tool-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(100, 116, 139, 0.16);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}
.tool-item:hover {
  border-color: var(--ks-primary, #2563eb);
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.1);
  transform: translateY(-1px);
}
.tool-icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--ks-primary, #2563eb);
  background: color-mix(in srgb, var(--ks-primary, #2563eb) 12%, transparent);
}
.tool-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.tool-info b {
  font-size: 14px;
  color: var(--ks-text-primary, #0f172a);
}
.tool-info span {
  font-size: 12px;
  color: var(--ks-text-secondary, #64748b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 768px) {
  .tool-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 375px) {
  .tool-card {
    padding: 12px;
  }
}

.profile-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

.profile-side {
  position: sticky;
  top: 20px;
}

.profile-card {
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.8));
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-radius: var(--ks-card-radius);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.8);
  padding: 24px;
  animation: ks-fade-in 0.35s ease both;
}

.profile-side .profile-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
}

.avatar-badge {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 36px;
  font-weight: 700;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.4);
  margin-bottom: 10px;
}

.profile-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--ks-text-title);
}

.profile-mail {
  font-size: 13px;
  color: #64748b;
  word-break: break-all;
}

.profile-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin: 8px 0 4px;
}

.profile-stats {
  width: 100%;
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
}

.stat-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: #64748b;
}

.stat-item .el-icon {
  margin-top: 2px;
  font-size: 16px;
  flex-shrink: 0;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-value {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
  word-break: break-all;
}

.section-card {
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.1px;
  color: var(--ks-text-title);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.section-title .el-icon {
  color: var(--ks-primary);
  font-size: 17px;
}

.section-sub {
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  color: var(--ks-text-secondary);
}

/* 无密码老用户：首次设置引导条 */
.pwd-first-set {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.28);
  color: #b45309;
  font-size: 13px;
  line-height: 1.6;
}

.pwd-first-set .el-icon {
  margin-top: 2px;
  flex-shrink: 0;
}

.profile-form {
  max-width: 560px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.dept-select {
  width: 100%;
}

.form-actions {
  margin-top: 4px;
}

/* 响应式：窄屏单列布局 */
@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
  .profile-side {
    position: static;
  }
  .form-row {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .section-sub {
    display: none;
  }
  .profile-card {
    padding: 18px;
  }
}
</style>
