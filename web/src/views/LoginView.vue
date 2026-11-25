<script setup lang="ts">
/** 登录/注册页：QQ 邮箱验证码 + 密码双模式
 *  - 登录：验证码（邮箱+验证码）或 密码（邮箱+密码）（POST /api/auth/login，mode=code|password）
 *  - 注册：QQ 邮箱 + 验证码 + 用户名 + 密码 + 部门（POST /api/auth/register，注册即登录）
 */
import { reactive, ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Message, Document, ChatDotRound, CollectionTag } from '@element-plus/icons-vue'
import { sendCode, registerApi, loginApi, forgotPassword, resetPassword, getSsoConfig, listDepartments, lockStatus, unlockApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import type { DeptInfo } from '@/types'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

const activeTab = ref<'login' | 'register'>('login')
/** 登录方式：验证码登录 / 密码登录 */
const loginMode = ref<'code' | 'password'>('code')
const loading = ref(false)
const departments = ref<DeptInfo[]>([])
const countdown = ref(0)
const sending = ref(false)

const loginFormRef = ref<FormInstance>()
const loginPwdFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({ email: '', code: '', remember: true })
/** 密码登录表单 */
const loginPwdForm = reactive({ email: '', password: '', remember: true })
const registerForm = reactive({
  email: '',
  code: '',
  username: '',
  password: '',
  confirm: '',
  dept_name: '',
})

/** 找回密码弹窗（M1） */
const forgotVisible = ref(false)
const forgotSubmitting = ref(false)
const forgotResetting = ref(false)
const forgotCountdown = ref(0)
let forgotTimer: number | null = null
const forgotForm = reactive({ email: '', code: '', new_password: '', confirm: '' })

// 账号锁定：登录失败触发锁定后，可通过邮箱验证码自助解锁
const lockVisible = ref(false)
const lockEmail = ref('')
const lockCode = ref('')
const lockSending = ref(false)
const lockCountdown = ref(0)
const lockSubmitting = ref(false)
let lockTimer: ReturnType<typeof setInterval> | null = null

function openLockDialog(email: string) {
  lockEmail.value = email
  lockCode.value = ''
  lockVisible.value = true
}

async function handleSendUnlockCode() {
  if (!lockEmail.value || !emailPattern.test(lockEmail.value)) {
    ElMessage.warning('请先填写正确的邮箱')
    return
  }
  lockSending.value = true
  try {
    await sendCode(lockEmail.value, 'unlock')
    ElMessage.success('解锁验证码已发送，请查收邮箱')
    lockCountdown.value = 60
    if (lockTimer) clearInterval(lockTimer)
    lockTimer = setInterval(() => {
      lockCountdown.value -= 1
      if (lockCountdown.value <= 0 && lockTimer) {
        clearInterval(lockTimer)
        lockTimer = null
      }
    }, 1000)
  } catch {
    // 拦截器已提示
  } finally {
    lockSending.value = false
  }
}

async function handleUnlock() {
  if (!lockEmail.value || !lockCode.value) {
    ElMessage.warning('请填写邮箱与验证码')
    return
  }
  lockSubmitting.value = true
  try {
    await unlockApi(lockEmail.value, lockCode.value)
    ElMessage.success('账号已解锁，请重新登录')
    lockVisible.value = false
    if (loginMode.value === 'code') loginForm.email = lockEmail.value
    else loginPwdForm.email = lockEmail.value
    loginForm.code = ''
    loginPwdForm.password = ''
  } catch {
    // 拦截器已提示
  } finally {
    lockSubmitting.value = false
  }
}

const forgotRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6-64 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== forgotForm.new_password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function handleForgotSend() {
  if (!forgotForm.email || !emailPattern.test(forgotForm.email)) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }
  forgotSubmitting.value = true
  try {
    await forgotPassword(forgotForm.email)
    ElMessage.success('重置验证码已发送，请查收邮箱（未配置 SMTP 时请查看后端控制台）')
    forgotCountdown.value = 60
    if (forgotTimer) window.clearInterval(forgotTimer)
    forgotTimer = window.setInterval(() => {
      forgotCountdown.value -= 1
      if (forgotCountdown.value <= 0 && forgotTimer !== null) {
        window.clearInterval(forgotTimer)
        forgotTimer = null
      }
    }, 1000)
  } catch {
    // 拦截器已提示
  } finally {
    forgotSubmitting.value = false
  }
}

async function handleResetPassword() {
  if (!forgotForm.email || !emailPattern.test(forgotForm.email)) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }
  if (!forgotForm.code || forgotForm.new_password.length < 6) {
    ElMessage.warning('请完整填写验证码与新密码')
    return
  }
  if (forgotForm.new_password !== forgotForm.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  forgotResetting.value = true
  try {
    await resetPassword({
      email: forgotForm.email,
      code: forgotForm.code,
      new_password: forgotForm.new_password,
    })
    ElMessage.success('密码已重置，请使用新密码重新登录')
    forgotVisible.value = false
    Object.assign(forgotForm, { email: '', code: '', new_password: '', confirm: '' })
  } catch (e) {
    const err = e as Error & { code?: number }
    if (err?.code === 10006) forgotForm.code = ''
  } finally {
    forgotResetting.value = false
  }
}

const qqHint = computed(() => (loginForm.email.includes('@qq.com') ? '' : '建议使用 QQ 邮箱'))

/** 企业 SSO 入口预留（M2） */
const ssoProviders = ref<Array<{ provider: string; name: string; enabled: boolean; configured: boolean; hint: string }>>([])
onMounted(async () => {
  // 记住邮箱：退出登录后自动回填（登出仅清 token，不清邮箱）
  const savedEmail = localStorage.getItem('ks_remember_email')
  if (savedEmail) {
    loginForm.email = savedEmail
    loginPwdForm.email = savedEmail
  }
  try {
    ssoProviders.value = await getSsoConfig()
  } catch {
    ssoProviders.value = []
  }
})

/** 验证码倒计时进度（0-1，用于圆环动画） */
const codeProgress = computed(() => (countdown.value > 0 ? countdown.value / 60 : 0))

const loginRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 8, message: '验证码长度不正确', trigger: 'blur' },
  ],
}

const loginPwdRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6-64 位', trigger: 'blur' },
  ],
}

const registerRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 8, message: '验证码长度不正确', trigger: 'blur' },
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 30, message: '用户名长度 2-30 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度 6-32 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, cb) => {
        if (value !== registerForm.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
  dept_name: [{ required: true, message: '请选择部门', trigger: 'change' }],
}

let timer: number | null = null

/* ---------------- 进场加载动效（品牌启动画面 -> 内容入场） ---------------- */
const bootShow = ref(true)
const pageIn = ref(false)
let bootTimer: number | null = null

function playIntro() {
  bootShow.value = true
  pageIn.value = false
  if (bootTimer !== null) window.clearTimeout(bootTimer)
  bootTimer = window.setTimeout(() => {
    bootShow.value = false
    pageIn.value = true
  }, 1000)
}

onMounted(async () => {
  playIntro()
  try {
    departments.value = await listDepartments()
  } catch {
    // 部门接口异常时注册表单部门可选填（后端允许空字符串时自动建部门）
  }
  // 清除浏览器自动填充到注册表单的历史账号密码
  const clearAutoFill = () => {
    Object.assign(registerForm, { email: '', code: '', username: '', password: '', confirm: '', dept_name: '' })
  }
  clearAutoFill()
  window.setTimeout(clearAutoFill, 100)
})

async function handleSendCode(purpose: 'login' | 'register') {
  const email = purpose === 'login' ? loginForm.email : registerForm.email
  if (!email || !emailPattern.test(email)) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }
  sending.value = true
  try {
    await sendCode(email, purpose)
    ElMessage.success('验证码已发送，请查收邮箱（未配置 SMTP 时请查看后端控制台）')
    countdown.value = 60
    timer = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0 && timer !== null) {
        window.clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch {
    // 错误提示已由拦截器统一弹出
  } finally {
    sending.value = false
  }
}

async function handleLogin() {
  if (loginMode.value === 'code') {
    if (!loginFormRef.value) return
    const valid = await loginFormRef.value.validate().catch(() => false)
    if (!valid) return
  } else {
    if (!loginPwdFormRef.value) return
    const valid = await loginPwdFormRef.value.validate().catch(() => false)
    if (!valid) return
  }
  loading.value = true
  try {
    const tokens =
      loginMode.value === 'code'
        ? await loginApi({ email: loginForm.email, code: loginForm.code, remember: loginForm.remember })
        : await loginApi({
            email: loginPwdForm.email,
            mode: 'password',
            password: loginPwdForm.password,
            remember: loginPwdForm.remember,
          })
    userStore.setTokens(tokens)
    // 记住邮箱：勾选"记住我"时持久化邮箱，退出登录后回填；未勾选则清除
    const usedEmail = loginMode.value === 'code' ? loginForm.email : loginPwdForm.email
    const usedRemember = loginMode.value === 'code' ? loginForm.remember : loginPwdForm.remember
    if (usedRemember) {
      localStorage.setItem('ks_remember_email', usedEmail)
    } else {
      localStorage.removeItem('ks_remember_email')
    }
    ElMessage.success(`欢迎回来，${tokens.user.username}`)
    const redirect = (route.query.redirect as string) || '/document'
    router.push(redirect)
  } catch (e) {
    // D1/D2/D5：登录失败明确提示（拦截器已弹 message），并按失败类型引导
    const err = e as Error & { code?: number; data?: { retry_after_seconds?: number; locked?: boolean } | null }
    if (err?.data?.locked) {
      const usedEmail = loginMode.value === 'code' ? loginForm.email : loginPwdForm.email
      ElMessage.warning('账号已锁定，请通过邮箱验证码解锁后重试')
      openLockDialog(usedEmail)
    } else if (err?.code === 10006) {
      loginForm.code = ''
      ElMessage.warning('验证码已失效或错误，请重新获取验证码后再试')
    } else if (err?.code === 10010) {
      // 老用户尚未设置密码：引导切换验证码登录
      loginMode.value = 'code'
      loginForm.email = loginPwdForm.email
      ElMessage.warning('该账号尚未设置密码，已为你切换到验证码登录，登录后可在个人中心设置密码')
    } else if (err?.code === 10007) {
      const sec = err.data?.retry_after_seconds ?? 60
      ElMessage.warning(`尝试过于频繁，请 ${Math.ceil(sec / 60)} 分钟后重试`)
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerFormRef.value) return
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const tokens = await registerApi({
      email: registerForm.email,
      code: registerForm.code,
      username: registerForm.username,
      password: registerForm.password,
      dept_name: registerForm.dept_name,
    })
    userStore.setTokens(tokens)
    ElMessage.success('注册成功，已自动登录')
    router.push('/document')
  } catch (e) {
    // 拦截器已弹出错误提示；验证码失效（10006）时清空输入框引导重新获取
    const err = e as Error & { code?: number }
    if (err?.code === 10006) {
      registerForm.code = ''
    }
  } finally {
    loading.value = false
  }
}

function switchTab(tab: string) {
  activeTab.value = tab as 'login' | 'register'
}
</script>

<template>
  <div class="login-page" :class="{ 'page-in': pageIn }">
    <!-- 品牌启动加载画面 -->
    <transition name="ks-boot">
      <div v-if="bootShow" class="boot-screen">
        <div class="boot-halo"></div>
        <div class="boot-badge">知</div>
        <div class="boot-name">知寻 <em>KnowSeek</em></div>
        <div class="boot-slogan">让企业知识触手可及</div>
        <div class="boot-progress"><i></i></div>
      </div>
    </transition>

    <!-- 全局流动光晕层 -->
    <div class="ambient-glow ambient-1"></div>
    <div class="ambient-glow ambient-2"></div>
    <div class="flow-lines" aria-hidden="true">
      <i></i>
      <i></i>
      <i></i>
    </div>

    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-glow glow-1"></div>
      <div class="brand-glow glow-2"></div>
      <div class="brand-grid"></div>
      <div class="brand-particle p1"></div>
      <div class="brand-particle p2"></div>
      <div class="brand-particle p3"></div>
      <div class="brand-particle p4"></div>
      <div class="brand-particle p5"></div>
      <div class="brand-particle p6"></div>

      <div class="brand-content">
        <div class="brand-badge">知</div>
        <div class="brand-name">知寻 KnowSeek</div>
        <div class="brand-slogan">让企业知识触手可及</div>
        <div class="brand-desc">
          企业级智能知识中枢 —— 文档沉淀 · 智能问答 · 溯源引用 · Agent 任务
        </div>

        <ul class="brand-features">
          <li class="feature-item">
            <span class="feature-icon"><el-icon><Message /></el-icon></span>
            <span>QQ 邮箱验证码 / 密码 双模式登录</span>
          </li>
          <li class="feature-item">
            <span class="feature-icon"><el-icon><Document /></el-icon></span>
            <span>文档四阶段自动解析入库</span>
          </li>
          <li class="feature-item">
            <span class="feature-icon"><el-icon><ChatDotRound /></el-icon></span>
            <span>SSE 流式对话与溯源引用</span>
          </li>
          <li class="feature-item">
            <span class="feature-icon"><el-icon><CollectionTag /></el-icon></span>
            <span>多版本管理与标签体系</span>
          </li>
        </ul>

        <div class="brand-foot">© 2026 KnowSeek · 企业级智能知识中枢</div>
      </div>
    </div>

    <!-- 右侧登录面板 -->
    <div class="login-panel">
      <div class="panel-glow"></div>
      <div class="panel-inner">
        <div class="panel-head">
          <div class="panel-title">【第一幕】欢迎回来</div>
          <div class="panel-sub">登录或注册以继续使用 KnowSeek</div>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs" @tab-change="switchTab">
          <el-tab-pane label="登录" name="login">
            <!-- 双模式切换：验证码登录 / 密码登录 -->
            <div class="login-mode-switch">
              <button
                type="button"
                class="mode-btn"
                :class="{ active: loginMode === 'code' }"
                @click="loginMode = 'code'"
              >
                <el-icon><ChatDotRound /></el-icon>
                <span>验证码登录</span>
              </button>
              <button
                type="button"
                class="mode-btn"
                :class="{ active: loginMode === 'password' }"
                @click="loginMode = 'password'"
              >
                <el-icon><Lock /></el-icon>
                <span>密码登录</span>
              </button>
            </div>

            <!-- 验证码登录表单 -->
            <el-form
              v-if="loginMode === 'code'"
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              label-position="top"
            >
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="loginForm.email" placeholder="name@qq.com" size="large" clearable />
                <div v-if="qqHint" class="form-hint">{{ qqHint }}</div>
              </el-form-item>
              <el-form-item label="验证码" prop="code">
                <div class="code-row">
                  <el-input v-model="loginForm.code" placeholder="邮箱收到的验证码" size="large" clearable />
                  <el-button
                    class="code-btn"
                    size="large"
                    :disabled="countdown > 0"
                    :loading="sending"
                    @click="handleSendCode('login')"
                  >
                    <template v-if="countdown > 0">
                      <svg class="code-ring" viewBox="0 0 28 28" width="18" height="18">
                        <circle cx="14" cy="14" r="11" fill="none" stroke="#dbeafe" stroke-width="3" />
                        <circle
                          cx="14"
                          cy="14"
                          r="11"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="3"
                          :stroke-dasharray="2 * Math.PI * 11"
                          :stroke-dashoffset="2 * Math.PI * 11 * (1 - codeProgress)"
                          stroke-linecap="round"
                          transform="rotate(-90 14 14)"
                        />
                      </svg>
                      <span>{{ countdown }}s 后重发</span>
                    </template>
                    <template v-else>
                      <span class="code-btn-lg">发送验证码</span><span class="code-btn-sm">获取码</span>
                    </template>
                  </el-button>
                </div>
              </el-form-item>
              <div class="login-opt-row">
                <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
                <a class="forgot-link" @click.prevent="forgotVisible = true">忘记密码？</a>
              </div>
              <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="handleLogin">
                登 录
              </el-button>
              <div class="sso-row" v-if="ssoProviders.length">
                <span class="sso-divider">企业账号登录</span>
                <div class="sso-btns">
                  <el-button
                    v-for="p in ssoProviders"
                    :key="p.provider"
                    class="sso-btn"
                    :disabled="!p.enabled || !p.configured"
                    size="large"
                  >
                    <span class="sso-name">{{ p.name }}</span><template v-if="!p.configured"><span class="sso-tag">（待配置）</span></template>
                  </el-button>
                </div>
              </div>
            </el-form>

            <!-- 密码登录表单 -->
            <el-form
              v-else
              ref="loginPwdFormRef"
              :model="loginPwdForm"
              :rules="loginPwdRules"
              label-position="top"
            >
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="loginPwdForm.email" placeholder="name@qq.com" size="large" clearable autocomplete="username" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="loginPwdForm.password"
                  type="password"
                  show-password
                  placeholder="请输入登录密码"
                  size="large"
                  clearable
                  autocomplete="current-password"
                  @keyup.enter="handleLogin"
                />
              </el-form-item>
              <div class="login-opt-row">
                <el-checkbox v-model="loginPwdForm.remember">记住我</el-checkbox>
                <a class="forgot-link" @click.prevent="loginMode = 'code'">忘记密码？</a>
                <a class="forgot-link" @click.prevent="openLockDialog(loginPwdForm.email || loginForm.email)">账号锁定？</a>
              </div>
              <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="handleLogin">
                登 录
              </el-button>
              <div class="mode-hint">
                尚未设置密码？<a class="forgot-link" @click.prevent="loginMode = 'code'">切换验证码登录</a>，登录后可在个人中心设置
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top">
              <el-form-item label="QQ 邮箱" prop="email">
                <el-input v-model="registerForm.email" placeholder="name@qq.com" size="large" clearable autocomplete="off" />
              </el-form-item>
              <el-form-item label="验证码" prop="code">
                <div class="code-row">
                  <el-input v-model="registerForm.code" placeholder="邮箱收到的验证码" size="large" clearable autocomplete="off" />
                  <el-button
                    class="code-btn"
                    size="large"
                    :disabled="countdown > 0"
                    :loading="sending"
                    @click="handleSendCode('register')"
                  >
                    <template v-if="countdown > 0">
                      <svg class="code-ring" viewBox="0 0 28 28" width="18" height="18">
                        <circle cx="14" cy="14" r="11" fill="none" stroke="#dbeafe" stroke-width="3" />
                        <circle
                          cx="14"
                          cy="14"
                          r="11"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="3"
                          :stroke-dasharray="2 * Math.PI * 11"
                          :stroke-dashoffset="2 * Math.PI * 11 * (1 - codeProgress)"
                          stroke-linecap="round"
                          transform="rotate(-90 14 14)"
                        />
                      </svg>
                      <span>{{ countdown }}s 后重发</span>
                    </template>
                    <template v-else>
                      <span class="code-btn-lg">发送验证码</span><span class="code-btn-sm">获取码</span>
                    </template>
                  </el-button>
                </div>
              </el-form-item>
              <el-form-item label="用户名" prop="username">
                <el-input v-model="registerForm.username" placeholder="2-30 位" size="large" clearable autocomplete="off" />
              </el-form-item>
              <el-form-item label="部门" prop="dept_name">
                <el-select v-model="registerForm.dept_name" placeholder="选择所属部门" size="large" style="width: 100%">
                  <el-option v-for="d in departments" :key="d.id" :label="d.dept_name" :value="d.dept_name" />
                </el-select>
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  show-password
                  placeholder="6-32 位"
                  size="large"
                  autocomplete="new-password"
                />
              </el-form-item>
              <el-form-item label="确认密码" prop="confirm">
                <el-input
                  v-model="registerForm.confirm"
                  type="password"
                  show-password
                  placeholder="再次输入密码"
                  size="large"
                  autocomplete="new-password"
                />
              </el-form-item>
              <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="handleRegister">
                注册并登录
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
    <!-- 账号锁定解锁弹窗：连续登录失败锁定后，邮箱验证码自助解锁 -->
    <el-dialog v-model="lockVisible" title="账号已锁定，验证邮箱解锁" width="420px" :close-on-click-modal="false">
    <div class="lock-dialog-body">
      <p class="lock-tip">连续登录失败达到次数后账号会被临时锁定，锁定期间无法登录。验证邮箱后即可解锁。</p>
      <el-form label-position="top">
        <el-form-item label="邮箱">
          <el-input v-model="lockEmail" placeholder="name@qq.com" size="large" clearable />
        </el-form-item>
        <el-form-item label="解锁验证码">
          <div class="code-row">
            <el-input v-model="lockCode" placeholder="邮箱收到的验证码" size="large" clearable />
            <el-button
              class="code-btn"
              size="large"
              :disabled="lockCountdown > 0"
              :loading="lockSending"
              @click="handleSendUnlockCode"
            >
              <span v-if="lockCountdown > 0">{{ lockCountdown }}s 后重发</span>
              <span v-else>发送解锁码</span>
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="lockVisible = false">取消</el-button>
      <el-button type="primary" :loading="lockSubmitting" @click="handleUnlock">解锁并返回登录</el-button>
    </template>
  </el-dialog>
  </div>
</template>

<style scoped>
/* 全页统一盒模型，避免内容溢出 */
.login-page,
.login-page *,
.login-page *::before,
.login-page *::after {
  box-sizing: border-box;
}

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: stretch;
  position: relative;
  overflow: hidden;
  background: linear-gradient(150deg, #060d1f 0%, #0b1730 40%, #10254d 78%, #1e3a8a 130%);
}

/* 全局流动光晕 */
.ambient-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
  animation: ambient-drift 14s ease-in-out infinite, ambient-hue 18s ease-in-out infinite;
}

.ambient-1 {
  width: 620px;
  height: 620px;
  left: -180px;
  top: -160px;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.5), transparent 68%);
}

.ambient-2 {
  width: 560px;
  height: 560px;
  right: -140px;
  bottom: -200px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.38), transparent 68%);
  animation-delay: -6s;
}

/* 流动光线 */
.flow-lines {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.flow-lines i {
  position: absolute;
  top: -10%;
  bottom: -10%;
  width: 240px;
  background: linear-gradient(180deg, transparent, rgba(96, 165, 250, 0.16), transparent);
  filter: blur(6px);
  animation: flow-move 9s linear infinite;
}

.flow-lines i:nth-child(1) { left: 12%; animation-duration: 11s; animation-delay: 0s; }
.flow-lines i:nth-child(2) { left: 48%; width: 160px; animation-duration: 13s; animation-delay: -4s; }
.flow-lines i:nth-child(3) { left: 78%; animation-duration: 9.5s; animation-delay: -7s; }

/* ---------- 左侧品牌区 ---------- */
.login-brand {
  flex: 1.2;
  position: relative;
  z-index: 1;
  overflow: hidden;
  color: #f8fafc;
  background: linear-gradient(150deg, #0b1526 0%, #0f1f3d 45%, #172a56 75%, #1e3a8a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(148, 163, 184, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.07) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 90% 70% at 50% 45%, #000 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse 90% 70% at 50% 45%, #000 30%, transparent 75%);
  pointer-events: none;
}

.brand-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.55;
  pointer-events: none;
}

.brand-particle {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(147, 197, 253, 0.9), rgba(147, 197, 253, 0));
  filter: blur(1px);
  pointer-events: none;
  animation: particle-float 8s ease-in-out infinite;
}

.brand-particle.p1 { width: 6px; height: 6px; left: 18%; top: 22%; animation-duration: 7s; animation-delay: 0s; }
.brand-particle.p2 { width: 10px; height: 10px; left: 68%; top: 18%; animation-duration: 9s; animation-delay: -2s; }
.brand-particle.p3 { width: 5px; height: 5px; left: 34%; top: 58%; animation-duration: 8s; animation-delay: -4s; }
.brand-particle.p4 { width: 8px; height: 8px; left: 78%; top: 62%; animation-duration: 10s; animation-delay: -5s; }
.brand-particle.p5 { width: 5px; height: 5px; left: 12%; top: 74%; animation-duration: 7.5s; animation-delay: -1s; }
.brand-particle.p6 { width: 7px; height: 7px; left: 56%; top: 84%; animation-duration: 9.5s; animation-delay: -6s; }

.glow-1 {
  width: 480px;
  height: 480px;
  left: -140px;
  top: -120px;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.55), transparent 70%);
}

.glow-2 {
  width: 420px;
  height: 420px;
  right: -120px;
  bottom: -160px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.35), transparent 70%);
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 520px;
  padding: 48px 40px;
}

.brand-badge {
  width: 76px;
  height: 76px;
  border-radius: 22px;
  background: var(--ks-primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
  font-weight: 700;
  margin-bottom: 28px;
  position: relative;
  opacity: 0;
}

.brand-badge::after {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 26px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.5), transparent 70%);
  filter: blur(10px);
  z-index: -1;
  animation: badge-halo 3.2s ease-in-out infinite;
}

.brand-name {
  font-size: 38px;
  font-weight: 700;
  letter-spacing: 1px;
  margin-bottom: 12px;
  opacity: 0;
}

.brand-slogan {
  font-size: 19px;
  color: #93c5fd;
  margin-bottom: 26px;
  opacity: 0;
}

.brand-desc {
  font-size: 14px;
  color: #cbd5e1;
  max-width: 460px;
  line-height: 1.9;
  margin-bottom: 34px;
  opacity: 0;
}

.brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  opacity: 0;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px 16px;
  backdrop-filter: blur(8px);
  transition: background 0.2s, transform 0.2s;
}

.feature-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(4px);
}

.feature-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.35);
  color: #93c5fd;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}

.brand-foot {
  margin-top: 40px;
  font-size: 12px;
  color: #64748b;
  opacity: 0;
}

/* ---------- 右侧登录面板 ---------- */
.login-panel {
  width: 540px;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 56px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  box-sizing: border-box;
}

.panel-glow {
  position: absolute;
  inset: 8% 12%;
  background: radial-gradient(ellipse at 50% 0%, rgba(96, 165, 250, 0.28), transparent 65%);
  filter: blur(30px);
  pointer-events: none;
}

.panel-inner {
  width: 100%;
  max-width: 400px;
  position: relative;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.84) 0%, rgba(243, 248, 255, 0.74) 100%);
  backdrop-filter: blur(26px) saturate(150%);
  -webkit-backdrop-filter: blur(26px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 26px;
  box-shadow:
    0 24px 64px rgba(2, 8, 23, 0.45),
    0 4px 16px rgba(2, 8, 23, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  padding: 40px 44px 36px;
  opacity: 0;
  transition: box-shadow 0.35s ease, border-color 0.35s ease;
}

.panel-inner:hover {
  border-color: rgba(147, 197, 253, 0.7);
  box-shadow:
    0 32px 84px rgba(2, 8, 23, 0.52),
    0 8px 24px rgba(37, 99, 235, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.panel-head {
  margin-bottom: 24px;
}

.panel-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--ks-text-title);
  margin-bottom: 8px;
}

.panel-sub {
  font-size: 14px;
  color: var(--ks-text-secondary);
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.login-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--el-border-color);
}

.login-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 600;
  color: var(--ks-text-secondary);
  padding: 0 28px;
  height: 42px;
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--ks-primary);
}

.login-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  border-radius: 3px;
  background: var(--ks-primary-gradient);
}

.login-tabs :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-body);
  padding-bottom: 4px;
}

.login-tabs :deep(.el-input__wrapper) {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.28) inset;
  transition: box-shadow 0.25s ease, background 0.25s ease, transform 0.25s ease;
}

.login-tabs :deep(.el-input__wrapper.is-focus) {
  background: #fff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16), 0 0 0 1px var(--el-color-primary) inset, 0 6px 18px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}

.login-tabs :deep(.el-input__inner) {
  height: 42px;
  line-height: 42px;
}

.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.code-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}

.code-btn {
  flex: 0 0 auto;
  min-width: 0;
  height: 42px;
  padding: 0 16px;
  border-radius: 10px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
}

.code-btn:not(.is-disabled) {
  background: var(--ks-primary-light);
  border-color: transparent;
  color: var(--ks-primary);
}

.code-btn:not(.is-disabled):hover {
  background: #dbeafe;
  color: var(--ks-primary-active);
}

.code-btn.is-disabled {
  background: #f8fafc;
  border-color: var(--el-border-color);
  color: var(--ks-text-secondary);
}

.code-ring {
  color: var(--ks-primary);
  flex-shrink: 0;
}

.form-hint {
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-top: 6px;
  line-height: 1.2;
}

/* 双模式登录切换（验证码 / 密码） */
.login-mode-switch {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin: 4px 0 18px;
  min-width: 0;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
}

.mode-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  padding: 0 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ks-text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.28s ease;
}

.mode-btn .el-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.mode-btn:hover {
  background: rgba(37, 99, 235, 0.08);
  color: var(--ks-primary);
}

.mode-btn.active {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  color: #fff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.32);
}

.mode-btn.active .el-icon {
  color: rgba(255, 255, 255, 0.9);
}

/* 记住我 / 忘记密码 行 */
.login-opt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 2px 0 16px;
  min-width: 0;
}

.login-opt-row :deep(.el-checkbox) {
  margin-right: 0;
}

.login-opt-row :deep(.el-checkbox__label) {
  font-size: 13px;
  color: var(--ks-text-body);
}

.forgot-link {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--ks-primary);
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s ease;
}

.forgot-link:hover {
  color: var(--ks-primary-active);
}

/* 底部企业登录区 */
.sso-row {
  margin-top: 24px;
  min-width: 0;
}

.sso-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-bottom: 12px;
}

.sso-divider::before,
.sso-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--el-border-color-lighter);
}

.sso-btns {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.sso-btn {
  flex: 1 1 auto;
  min-width: max-content;
  height: auto;
  min-height: 42px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
  line-height: 1.2;
}

.sso-name,
.sso-tag {
  flex: 0 0 auto;
  white-space: nowrap;
}

.sso-tag {
  opacity: 0.85;
}

.mode-hint {
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--ks-text-secondary);
  line-height: 1.6;
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
  height: 46px;
  border-radius: 12px;
  letter-spacing: 1px;
  font-weight: 600;
  font-size: 15px;
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  border: none;
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.submit-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 30%, rgba(255, 255, 255, 0.45) 50%, transparent 70%);
  transform: translateX(-120%);
  animation: btn-shine 3.6s ease-in-out infinite;
  pointer-events: none;
}

.submit-btn:hover {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  transform: translateY(-2px);
  box-shadow: 0 12px 30px rgba(37, 99, 235, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

@media (max-width: 1000px) {
  .login-brand {
    display: flex;
    flex: none;
    width: 100%;
    min-height: 300px;
    height: 40vh;
    align-items: center;
    justify-content: center;
  }
  .login-panel {
    width: 100%;
    padding: 8px 20px 32px;
  }
  .panel-inner {
    padding: 28px 24px;
  }
}

/* 矮屏适配：压缩间距保证注册表单完整可见，不依赖滚动 */
@media (max-height: 800px) {
  .login-panel {
    padding: 16px 56px;
  }
  .panel-inner {
    padding: 20px 32px 18px;
  }
  .panel-head {
    margin-bottom: 12px;
  }
  .panel-title {
    font-size: 24px;
  }
  .panel-sub {
    font-size: 13px;
  }
  .login-tabs :deep(.el-tabs__header) {
    margin-bottom: 12px;
  }
  .login-tabs :deep(.el-tabs__item) {
    height: 36px;
  }
  .login-tabs :deep(.el-form-item) {
    margin-bottom: 14px;
  }
  .login-tabs :deep(.el-input__inner) {
    height: 38px;
    line-height: 38px;
  }
  .code-btn {
    height: 38px;
  }
  .submit-btn {
    height: 40px;
    margin-top: 0;
  }
}

@media (max-width: 1000px) and (max-height: 800px) {
  .login-panel {
    padding: 12px 20px;
  }
  .panel-inner {
    padding: 18px 22px 16px;
  }
}

@keyframes ambient-drift {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(52px, -36px, 0) scale(1.16); }
}

@keyframes ambient-hue {
  0%, 100% { filter: blur(90px) hue-rotate(0deg) saturate(1.1); }
  50% { filter: blur(104px) hue-rotate(18deg) saturate(1.35); }
}

@keyframes flow-move {
  0% { transform: translateX(-40%) skewX(-14deg); opacity: 0; }
  25% { opacity: 0.9; }
  75% { opacity: 0.9; }
  100% { transform: translateX(140%) skewX(-14deg); opacity: 0; }
}

@keyframes particle-float {
  0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.25; }
  50% { transform: translate3d(20px, -56px, 0); opacity: 0.9; }
}

@keyframes badge-pulse {
  0%, 100% { box-shadow: 0 12px 32px rgba(37, 99, 235, 0.45), 0 0 0 0 rgba(59, 130, 246, 0.4), inset 0 0 0 1px rgba(255, 255, 255, 0.18); }
  50% { box-shadow: 0 14px 44px rgba(37, 99, 235, 0.65), 0 0 0 16px rgba(59, 130, 246, 0), inset 0 0 0 1px rgba(255, 255, 255, 0.28); }
}

@keyframes badge-halo {
  0%, 100% { opacity: 0.5; transform: scale(0.95); }
  50% { opacity: 0.95; transform: scale(1.08); }
}

@keyframes panel-rise {
  from { opacity: 0; transform: translateY(22px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes btn-shine {
  0% { transform: translateX(-120%); }
  55% { transform: translateX(120%); }
  100% { transform: translateX(120%); }
}

/* ---------- 进场加载动效：pageIn 触发品牌区/面板入场 ---------- */
.login-page.page-in .brand-badge {
  animation: badge-pulse 3.2s ease-in-out infinite, ks-fade-in 0.5s ease both;
}
.login-page.page-in .brand-name {
  animation: ks-fade-in 0.5s ease 0.08s both;
}
.login-page.page-in .brand-slogan {
  animation: ks-fade-in 0.5s ease 0.16s both;
}
.login-page.page-in .brand-desc {
  animation: ks-fade-in 0.5s ease 0.24s both;
}
.login-page.page-in .brand-features {
  animation: ks-fade-in 0.5s ease 0.32s both;
}
.login-page.page-in .brand-foot {
  animation: ks-fade-in 0.5s ease 0.4s both;
}
.login-page.page-in .panel-inner {
  animation: panel-rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* 窄屏按钮文案默认隐藏（480px 以下切短文案） */
.code-btn-sm {
  display: none;
}

/* ---------- 品牌启动加载画面 ---------- */
.boot-screen {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: linear-gradient(150deg, #060d1f 0%, #0b1730 45%, #10254d 80%, #1e3a8a 130%);
  overflow: hidden;
}

.boot-halo {
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.4), transparent 68%);
  filter: blur(70px);
  animation: boot-halo-pulse 1.6s ease-in-out infinite;
  pointer-events: none;
}

.boot-badge {
  position: relative;
  z-index: 1;
  width: 88px;
  height: 88px;
  border-radius: 26px;
  background: var(--ks-primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 18px 48px rgba(37, 99, 235, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  animation: boot-badge-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.boot-badge::after {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 32px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.45), transparent 70%);
  filter: blur(12px);
  z-index: -1;
  animation: badge-halo 1.6s ease-in-out infinite;
}

.boot-name {
  position: relative;
  z-index: 1;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #f8fafc;
  animation: ks-fade-in 0.5s ease 0.15s both;
}

.boot-name em {
  font-style: normal;
  background: linear-gradient(90deg, #93c5fd, #a5b4fc);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.boot-slogan {
  position: relative;
  z-index: 1;
  font-size: 14px;
  letter-spacing: 3px;
  color: #93c5fd;
  animation: ks-fade-in 0.5s ease 0.25s both;
}

.boot-progress {
  position: relative;
  z-index: 1;
  width: 168px;
  height: 3px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.22);
  overflow: hidden;
  margin-top: 10px;
  animation: ks-fade-in 0.4s ease 0.35s both;
}

.boot-progress i {
  display: block;
  width: 46%;
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #3b82f6, #818cf8);
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.8);
  animation: boot-load 0.9s cubic-bezier(0.45, 0, 0.2, 1) both;
}

/* 启动画面退场 */
.ks-boot-leave-active {
  transition: opacity 0.45s ease, transform 0.45s ease;
}
.ks-boot-leave-to {
  opacity: 0;
  transform: scale(1.04);
}

@keyframes boot-badge-in {
  from { opacity: 0; transform: translateY(18px) scale(0.86) rotate(-8deg); }
  to { opacity: 1; transform: translateY(0) scale(1) rotate(0deg); }
}

@keyframes boot-load {
  0% { transform: translateX(-130%); }
  100% { transform: translateX(240%); }
}

@keyframes boot-halo-pulse {
  0%, 100% { opacity: 0.55; transform: scale(0.94); }
  50% { opacity: 1; transform: scale(1.06); }
}

/* ---------- 移动端登录页：背景补齐 + 登录框置下 + 品牌区置上 ---------- */
@media (max-width: 1000px) {
  .login-page {
    flex-direction: column;
    align-items: stretch;
  }
  .brand-content {
    max-width: 460px;
    width: 100%;
    padding: 24px;
  }
  .brand-badge {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    font-size: 28px;
    margin-bottom: 18px;
  }
  .brand-name {
    font-size: 30px;
    margin-bottom: 8px;
  }
  .brand-slogan {
    font-size: 16px;
    margin-bottom: 14px;
  }
  .brand-desc {
    font-size: 13px;
    margin-bottom: 0;
  }
  .brand-features,
  .brand-foot {
    display: none;
  }
  .login-panel {
    align-items: flex-start;
  }
  .panel-inner {
    max-width: 100%;
  }
}

/* 矮屏压缩品牌区高度，保证登录表单完整可见 */
@media (max-width: 1000px) and (max-height: 760px) {
  .login-brand {
    min-height: 0;
    height: 24vh;
  }
  .brand-content {
    padding: 14px 20px;
  }
  .brand-badge {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    font-size: 22px;
    margin-bottom: 10px;
  }
  .brand-name {
    font-size: 23px;
    margin-bottom: 4px;
  }
  .brand-slogan {
    font-size: 14px;
    margin-bottom: 6px;
  }
  .brand-desc {
    display: none;
  }
}

@media (max-width: 480px) {
  .code-row {
    gap: 8px;
  }
  .code-btn {
    height: 40px;
    padding: 0 12px;
  }
  .code-btn-lg {
    display: none;
  }
  .code-btn-sm {
    display: inline;
  }
  .login-panel {
    padding: 6px 14px 24px;
  }
  .panel-inner {
    padding: 24px 18px 20px;
  }
  .panel-title {
    font-size: 24px;
  }
  .login-mode-switch {
    margin: 2px 0 14px;
  }
  .mode-btn {
    gap: 4px;
    padding: 0 8px;
    height: 36px;
    font-size: 13px;
  }
  .login-tabs :deep(.el-tabs__item) {
    padding: 0 18px;
    font-size: 15px;
  }
  .sso-btn {
    font-size: 12px;
  }
}
.lock-dialog-body .lock-tip {
  margin: 0 0 12px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #b45309;
  background: #fef3c7;
  border-radius: 8px;
}
</style>
