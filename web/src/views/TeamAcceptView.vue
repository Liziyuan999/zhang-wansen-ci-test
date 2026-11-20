<script setup lang="ts">
/**
 * 接受团队邀请页：展示邀请信息，邮箱匹配后确认加入
 * 未登录时由路由守卫跳转登录页（带 redirect 回跳）
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Message, WarningFilled, Check, Promotion } from '@element-plus/icons-vue'
import { getInviteInfo, acceptInvite } from '@/api/team'
import { useUserStore } from '@/stores/user'
import type { InviteInfo } from '@/types'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const token = computed(() => (route.query.token as string) || '')
const targetEmail = computed(() => (route.query.email as string) || '')

const loading = ref(true)
const failed = ref(false)
const errorText = ref('')
const invite = ref<InviteInfo | null>(null)
const accepting = ref(false)

/** 当前登录用户邮箱是否与邀请邮箱一致 */
const emailMatched = computed(() => {
  if (!invite.value) return false
  const cur = userStore.userInfo?.email || ''
  return cur.toLowerCase() === invite.value.email.toLowerCase()
})

/** 邀请是否仍处于待接受状态 */
const pending = computed(() => invite.value?.status === 'pending')

async function load() {
  if (!token.value) {
    failed.value = true
    errorText.value = '邀请链接缺少必要参数，请检查邮件中的完整链接'
    loading.value = false
    return
  }
  try {
    invite.value = await getInviteInfo(token.value)
  } catch (e) {
    failed.value = true
    errorText.value = (e as Error)?.message || '邀请链接无效或已过期'
  } finally {
    loading.value = false
  }
}

async function handleAccept() {
  if (!invite.value) return
  accepting.value = true
  try {
    const res = await acceptInvite(token.value)
    ElMessage.success(`已加入团队「${res.team_name}」`)
    router.push('/team')
  } catch {
    // 拦截器已提示；保持页面，可刷新重试
    await load()
  } finally {
    accepting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="accept-page">
    <div v-loading="loading" class="accept-wrap">
      <!-- 加载中 -->
      <div v-if="loading" class="accept-card loading-card">
        <span class="loading-icon"></span>
        <div class="loading-text">正在加载邀请信息…</div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="failed" class="accept-card error-card">
        <span class="status-icon danger"><el-icon><WarningFilled /></el-icon></span>
        <div class="card-title">邀请链接无效</div>
        <div class="card-desc">{{ errorText }}</div>
        <div class="card-foot">
          <el-button @click="router.push('/team')">前往组织中心</el-button>
        </div>
      </div>

      <!-- 邀请信息 -->
      <div v-else-if="invite" class="accept-card">
        <span class="status-icon" :class="{ danger: !pending, primary: pending }">
          <el-icon><Promotion /></el-icon>
        </span>
        <div class="card-title">团队邀请</div>

        <div class="info-box">
          <div class="info-row">
            <span class="info-label">团队</span>
            <span class="info-value team-name-text">{{ invite.team_name }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">邀请人</span>
            <span class="info-value">{{ invite.inviter_name }}（{{ invite.inviter_email }}）</span>
          </div>
          <div class="info-row">
            <span class="info-label">邀请邮箱</span>
            <span class="info-value">{{ invite.email }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">状态</span>
            <span class="info-value">
              <el-tag :type="pending ? 'warning' : 'info'" size="small" effect="light" class="status-tag">
                {{ pending ? '待接受' : '已处理' }}
              </el-tag>
            </span>
          </div>
        </div>

        <!-- 邮箱匹配 & 待接受 → 确认加入 -->
        <template v-if="pending">
          <div v-if="emailMatched" class="accept-zone">
            <div class="accept-tip">当前账号 <b>{{ userStore.userInfo?.email }}</b> 与邀请邮箱一致，确认后将加入该团队。</div>
            <el-button type="primary" size="large" :icon="Check" :loading="accepting" @click="handleAccept">
              确认加入
            </el-button>
          </div>
          <div v-else class="error-zone">
            <el-icon class="error-icon"><WarningFilled /></el-icon>
            <div>
              <div class="error-title">邮箱不匹配</div>
              <div class="error-desc">该邀请仅限 <b>{{ invite.email }}</b> 接受。当前登录账号为
                <b>{{ userStore.userInfo?.email || '未登录' }}</b>，请使用被邀请的邮箱账号登录后再接受。</div>
            </div>
          </div>
        </template>

        <!-- 已处理 -->
        <div v-else class="error-zone">
          <el-icon class="error-icon"><WarningFilled /></el-icon>
          <div>
            <div class="error-title">邀请已处理</div>
            <div class="error-desc">该邀请已被接受、拒绝或已过期，无法再次加入。</div>
          </div>
        </div>

        <div class="card-foot">
          <el-button text @click="router.push('/team')">前往组织中心</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.accept-page {
  min-height: calc(100vh - 60px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.accept-wrap {
  width: 460px;
  max-width: 100%;
}

.accept-card {
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.95), rgba(248, 251, 255, 0.86));
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  border-radius: var(--ks-card-radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.14), 0 8px 24px rgba(37, 99, 235, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.95);
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  animation: ks-fade-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.status-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  margin-bottom: 16px;
}

.status-icon.primary {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
}

.status-icon.danger {
  color: #dc2626;
  background: #fee2e2;
  box-shadow: 0 10px 24px rgba(239, 68, 68, 0.2);
}

.card-title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--ks-text-title);
  margin-bottom: 6px;
}

.card-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
  margin: 12px 0 4px;
}

.info-box {
  width: 100%;
  margin: 20px 0 4px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.info-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  gap: 14px;
}

.info-row + .info-row {
  border-top: 1px solid #eef2f7;
}

.info-label {
  width: 72px;
  text-align: left;
  font-size: 13px;
  color: #64748b;
  flex-shrink: 0;
}

.info-value {
  flex: 1;
  text-align: left;
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  word-break: break-all;
}

.team-name-text {
  font-weight: 700;
  color: var(--ks-text-title);
}

.accept-zone {
  width: 100%;
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.accept-tip {
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}

.accept-tip b {
  color: var(--ks-primary);
}

.error-zone {
  width: 100%;
  margin-top: 20px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  text-align: left;
}

.error-icon {
  font-size: 18px;
  color: #dc2626;
  flex-shrink: 0;
  margin-top: 2px;
}

.error-title {
  font-size: 14px;
  font-weight: 700;
  color: #b91c1c;
}

.error-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #7f1d1d;
  margin-top: 4px;
}

.error-desc b {
  color: #b91c1c;
}

.card-foot {
  margin-top: 20px;
  width: 100%;
  display: flex;
  justify-content: center;
}

.loading-card {
  padding: 48px 32px;
  gap: 14px;
}

.loading-icon {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid rgba(147, 197, 253, 0.3);
  border-top-color: var(--ks-primary);
  animation: ks-spin 0.7s linear infinite;
}

.loading-text {
  font-size: 13px;
  color: var(--ks-text-secondary);
}

/* 状态标签胶囊（与全局体系一致） */
:deep(.status-tag) {
  border-radius: 999px;
  padding: 0 10px;
  height: 22px;
  line-height: 20px;
  font-weight: 600;
  letter-spacing: 0.3px;
  border: 1px solid transparent;
}

:deep(.status-tag.el-tag--warning) {
  color: #b45309;
  background: #fef3c7;
  border-color: #fde68a;
}

:deep(.status-tag.el-tag--info) {
  color: #475569;
  background: #e2e8f0;
  border-color: #cbd5e1;
}

@keyframes ks-spin {
  to {
    transform: rotate(360deg);
  }
}
/* ---------------- 移动端适配 ---------------- */
@media (max-width: 768px) {
  .accept-zone,
  .error-zone,
  .accept-card {
    width: calc(100vw - 28px) !important;
    padding: 20px 16px !important;
  }

  .info-row {
    flex-direction: column;
    gap: 4px;
  }

  .card-foot {
    flex-wrap: wrap;
  }

  .card-foot .el-button {
    flex: 1;
    margin-left: 0 !important;
  }
}
</style>
