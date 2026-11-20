<script setup lang="ts">
/**
 * 对话页：SSE 流式 + 溯源引用 + 反馈 + 重置上下文
 * 说明：
 *  - 后端 ask 接口为 SSE（citations/delta/done/error）
 *  - 重置上下文调用后端 reset-context 端点，历史消息同步清空
 *  - 参考文档多选：文档名带入提问 + doc_ids 传给后端做精确限定 RAG 检索
 */
// ===== 逐行注释：对话页核心逻辑（script setup） =====
// 1. 会话管理：loadConvs 拉取会话列表，newConversation 新建空会话，
//    switchConversation 切换会话并拉取历史消息（getConversationDetail）。
// 2. 发消息（sendMessage）：校验输入 -> 乐观追加用户消息 -> 调 askSSE 流式接收 ->
//    打字机逐字渲染（displayText/pendingText 字段，nextTick 配合滚动到底）。
// 3. SSE 回调分发：onCitation 更新引用列表（含关联图谱实体 collectKgEntities）、
//    onWebSources 展示联网来源、onDelta 追加增量、onDone 落定 conv_id/msg_id、
//    onFallback 提示模型供应商自动回退、onError 终止流式状态。
// 4. 溯源与反馈：citations 可打开 CitationsDialog 查看引用原文片段；
//    sendFeedback 提交 good/bad 反馈；resetConversationContext 重置上下文后清空本地消息。
// 5. 模型选择：getLlmStatus 拉取已启用供应商列表，切换时把 providerId 传入 askSSE。
// 6. 移动端适配：< 768px 时隐藏会话列表/引用面板，聊天主区全屏展示。
// ===== 逐行注释：localMsg 辅助字段 =====
// - streaming：该条消息正在流式生成（显示停止/加载态）。
// - displayText / pendingText：打字机动画专用——displayText 为已渲染部分，
//   pendingText 为待渲染缓存，定时器逐字搬运，避免高频 delta 直接改 DOM 造成卡顿。
// ===== 逐行注释：collectKgEntities =====
// 1. 遍历当前消息全部引用的 related_entities（图谱实体）。
// 2. 用 Set 按实体 id 去重（同一实体可出现在多个引用片段中）。
// 3. 最多取 8 个，渲染为"关联实体"标签，点击 goKgEntity 跳图谱页按关键词聚焦。
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Promotion, CopyDocument, RefreshRight, Document, ChatDotRound, Link, CircleCheckFilled, Warning, Connection } from '@element-plus/icons-vue'
import {
  createConversation,
  listConversations,
  getConversationDetail,
  deleteConversation,
} from '@/api/conversation'
import { askSSE, sendFeedback, resetConversationContext, getLlmStatus, type LlmStatus } from '@/api/chat'
import { listDocuments } from '@/api/document'
import CitationsDialog from '@/components/CitationsDialog.vue'
import type { Citation, ConvItem, DocListItem, WebSource, KgEntity } from '@/types'

const router = useRouter()

/** 从引文中聚合关联知识图谱实体（去重，最多 8 个） */
function collectKgEntities(msg: LocalMsg): KgEntity[] {
  const seen = new Set<number>()
  const out: KgEntity[] = []
  for (const c of msg.citations || []) {
    for (const e of c.related_entities || []) {
      if (!seen.has(e.id)) {
        seen.add(e.id)
        out.push(e)
      }
    }
  }
  return out.slice(0, 8)
}

/** 跳转知识图谱页并按实体关键词聚焦 */
function goKgEntity(name: string) {
  router.push({ path: '/knowledge-graph', query: { keyword: name } })
}

interface LocalMsg {
  id?: number
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  webSources?: WebSource[]
  streaming?: boolean
  feedback?: 'good' | 'bad'
  /* 打字机渲染辅助字段（仅用于逐字加载展示，不参与业务逻辑） */
  displayText?: string
  pendingText?: string
}

/* ---------------- 会话列表 ---------------- */
const convs = ref<ConvItem[]>([])
const currentConvId = ref<number | null>(null)
const currentTitle = ref('新对话')
const loadingConvs = ref(false)

async function loadConvs() {
  loadingConvs.value = true
  try {
    convs.value = await listConversations()
  } catch {
    // 拦截器已提示
  } finally {
    loadingConvs.value = false
  }
}

async function newConversation() {
  try {
    const conv = await createConversation()
    currentConvId.value = conv.id
    currentTitle.value = conv.title
    messages.value = []
    await loadConvs()
  } catch {
    // 拦截器已提示
  }
}

async function openConversation(convId: number) {
  if (convId === currentConvId.value) return
  stopStreaming()
  try {
    const detail = await getConversationDetail(convId)
    currentConvId.value = convId
    currentTitle.value = detail.conv.title
    messages.value = (detail.messages || []).map((m) => ({
      id: m.id,
      role: m.role === 'user' ? ('user' as const) : ('assistant' as const),
      content: m.content,
    }))
    resetApplied.value = false
    scrollToBottom()
  } catch {
    // 拦截器已提示
  }
}

async function removeConversation(convId: number) {
  try {
    await ElMessageBox.confirm('确定删除该会话吗？', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteConversation(convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
      currentTitle.value = '新对话'
      messages.value = []
    }
    await loadConvs()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 消息与对话 ---------------- */
const messages = ref<LocalMsg[]>([])
const inputText = ref('')
const sending = ref(false)
const abortController = ref<AbortController | null>(null)
const resetApplied = ref(false)
/* 慢响应提示：首 token 等待过久 / 模型回退时展示，首个 delta 到达后自动隐藏 */
const streamHint = ref('')
const msgListRef = ref<HTMLElement>()
/* 联网检索开关：默认关，开启后对话融合实时网络搜索结果 */
const webSearch = ref(false)

/* 参考文档多选 */
const docOptions = ref<DocListItem[]>([])
const selectedDocs = ref<number[]>([])

async function loadDocOptions() {
  try {
    const res = await listDocuments({ page: 1, page_size: 100 })
    docOptions.value = res.items.filter((d) => d.status === 'success')
  } catch {
    // 忽略
  }
}

function stopStreaming() {
  abortController.value?.abort()
  abortController.value = null
}

function scrollToBottom() {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTop = msgListRef.value.scrollHeight
    }
  })
}

/* ---------------- 打字机逐字渲染 ---------------- */
const TYPE_INTERVAL_MS = 50
const TYPE_STEP_MIN = 1
const TYPE_STEP_MAX = 1
let typeTimer: number | null = null

// ===== 逐行注释：打字机逐字渲染（ensureTypeTimer / flushPending） =====
// 1. 全局唯一定时器：每 50ms 扫描所有 streaming 消息，把 pendingText 前 1 个字符
//    搬运到 displayText（逐步展示，模拟打字效果），搬运后自动滚动到底部。
// 2. 步长策略：TYPE_STEP_MIN/MAX 均为 1（逐字），若后续想加速打字机，调大上限即可，
//    上限被 pending 长度钳制，不会越界。
// 3. 定时器生命周期：ensureTypeTimer 保证只存在一个实例（防多消息并发重复开 timer）；
//    所有消息都不再 streaming 时 stopTypeTimer 自动清理，避免后台空转。
// 4. flushPending：流结束/中断时把剩余缓冲一次性冲入 displayText，保证收尾文本完整
//    （用户点击停止后不会出现"答案突然断在半截"的观感）。
function ensureTypeTimer() {
  if (typeTimer !== null) return
  typeTimer = window.setInterval(() => {
    let stepped = false
    for (const m of messages.value) {
      if (!m.streaming || !m.pendingText) continue
      const pending = m.pendingText
      const step = Math.min(
        TYPE_STEP_MIN + Math.floor(Math.random() * (TYPE_STEP_MAX - TYPE_STEP_MIN + 1)),
        pending.length,
      )
      m.displayText = (m.displayText || '') + pending.slice(0, step)
      m.pendingText = pending.slice(step)
      stepped = true
    }
    if (stepped) scrollToBottom()
    if (!messages.value.some((m) => m.streaming)) stopTypeTimer()
  }, TYPE_INTERVAL_MS)
}

function stopTypeTimer() {
  if (typeTimer !== null) {
    window.clearInterval(typeTimer)
    typeTimer = null
  }
}

/** 流结束/中断时，将剩余缓冲一次性冲入渲染文本，快速收尾 */
function flushPending(msg: LocalMsg) {
  if (msg.pendingText) {
    msg.displayText = (msg.displayText || '') + msg.pendingText
    msg.pendingText = ''
  }
}

async function ensureConversation(): Promise<number> {
  if (currentConvId.value) return currentConvId.value
  const conv = await createConversation()
  currentConvId.value = conv.id
  currentTitle.value = conv.title
  return conv.id
}

// ===== 逐行注释：发消息主流程（handleSend） =====
// 1. 输入校验：空文本或正在发送中直接返回（防连点重复提交）。
// 2. 参考文档增强：若选中了参考文档，将文档名列表（含版本号）拼入问题开头
//    "[参考资料：...]\n"，同时 doc_ids 传给 askSSE 做精确限定 RAG 检索——双通道确保命中。
// 3. 乐观 UI：清空输入框、置 sending=true、创建 AbortController（供"停止生成"按钮中断流）。
// 4. ensureConversation：无会话时先建会话（后端返回 conv.id），保证历史消息可持久化归档。
// 5. 消息入列：先 push 用户消息，再 push 一条 streaming=true 的空 assistant 消息（占位渲染）。
// 6. askSSE 回调：slowTimeoutMs=8000（千问等模型首 token 慢，8s 无增量提示"模型响应中"）、
//    onSlowTip 写 streamHint、onFallback 提示模型已自动回退、onCitation/onWebSources 更新
//    引用与联网来源、onDelta 写入 pendingText（打字机定时器逐字搬运到 displayText）、
//    onDone 落定 conv_id/msg_id 并结束流式态。
// 7. 收尾：无论成功/失败都 sending=false、flushPending 冲掉残留缓冲、停止打字机与慢响应定时器。
async function handleSend() {
  const question = inputText.value.trim()
  if (!question || sending.value) return

  // 若选择了参考文档：文档名作为上下文提示带入提问，同时将 doc_ids 传给后端做精确限定检索
  let finalQuestion = question
  if (selectedDocs.value.length) {
    const names = docOptions.value
      .filter((d) => selectedDocs.value.includes(d.id))
      .map((d) => `${d.doc_name}(v${d.version_no})`)
    finalQuestion = `[参考资料：${names.join('、')}]\n${question}`
  }

  inputText.value = ''
  sending.value = true
  abortController.value = new AbortController()

  try {
    const convId = await ensureConversation()
    messages.value.push({ role: 'user', content: question })
    const aiMsg: LocalMsg = { role: 'assistant', content: '', streaming: true }
    messages.value.push(aiMsg)
    scrollToBottom()

    await askSSE(convId, finalQuestion, {
      signal: abortController.value.signal,
      /* 千问等模型首 token 较慢：8s 无增量即提示“模型响应中”，避免误以为卡死（保留停止按钮） */
      slowTimeoutMs: 8000,
      onSlowTip: (message) => {
        streamHint.value = message
        scrollToBottom()
      },
      onFallback: (message) => {
        streamHint.value = '（模型调用失败，已自动切换可用模型）'
        ElMessage.warning(message)
      },
      onCitation: (citations) => {
        aiMsg.citations = citations
        scrollToBottom()
      },
      onWebSources: (sources) => {
        aiMsg.webSources = sources
        scrollToBottom()
      },
      onDelta: (text) => {
        streamHint.value = ''
        aiMsg.content += text
        aiMsg.pendingText = (aiMsg.pendingText || '') + text
        ensureTypeTimer()
        scrollToBottom()
      },
      onDone: (payload) => {
        streamHint.value = ''
        flushPending(aiMsg)
        aiMsg.streaming = false
        aiMsg.id = payload.msg_id
        if (payload.conv_id && payload.conv_id !== currentConvId.value) {
          currentConvId.value = payload.conv_id
        }
        loadConvs()
        scrollToBottom()
      },
      onError: (message) => {
        streamHint.value = ''
        flushPending(aiMsg)
        aiMsg.streaming = false
        if (!aiMsg.content) {
          aiMsg.content = `（生成失败：${message}）`
          if (!aiMsg.displayText) aiMsg.displayText = aiMsg.content
        }
        ElMessage.error(message)
      },
    }, webSearch.value, selectedProviderId.value, selectedDocs.value)
  } catch (err) {
    const aiMsg = messages.value[messages.value.length - 1]
    if (aiMsg && aiMsg.streaming) {
      flushPending(aiMsg)
      aiMsg.streaming = false
      if (!aiMsg.content) {
        aiMsg.content = '（发送失败，请重试）'
        if (!aiMsg.displayText) aiMsg.displayText = aiMsg.content
      }
    }
    ElMessage.error((err as Error).message || '发送失败')
  } finally {
    sending.value = false
    abortController.value = null
  }
}

function handleStop() {
  stopStreaming()
  const aiMsg = messages.value[messages.value.length - 1]
  if (aiMsg?.streaming) {
    flushPending(aiMsg)
    aiMsg.streaming = false
  }
  sending.value = false
}

async function handleResetContext() {
  if (currentConvId.value) {
    try {
      await resetConversationContext(currentConvId.value)
      messages.value = []
      ElMessage.success('上下文已重置，后续提问不再依赖本次会话历史')
    } catch {
      // 接口失败时仍保留本地清空
      messages.value = []
      resetApplied.value = true
    }
  } else {
    resetApplied.value = true
    messages.value = []
    selectedDocs.value = []
    ElMessage.success('已重置上下文，后续提问不再依赖本次会话历史')
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/* ---------------- 消息操作 ---------------- */
async function copyMessage(msg: LocalMsg) {
  try {
    await navigator.clipboard.writeText(msg.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const feedbackVisible = ref(false)
const feedbackTarget = ref<LocalMsg | null>(null)
const feedbackContent = ref('')
const feedbackScore = ref<'good' | 'bad'>('good')

function openFeedback(msg: LocalMsg, score: 'good' | 'bad') {
  feedbackTarget.value = msg
  feedbackScore.value = score
  feedbackContent.value = ''
  feedbackVisible.value = true
}

async function submitFeedback() {
  if (!feedbackTarget.value?.id) {
    ElMessage.warning('该消息暂不可反馈')
    return
  }
  try {
    await sendFeedback({
      msg_id: feedbackTarget.value.id,
      score: feedbackScore.value,
      content: feedbackContent.value.trim() || undefined,
    })
    feedbackTarget.value.feedback = feedbackScore.value
    feedbackVisible.value = false
    ElMessage.success('感谢您的反馈')
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 模型状态 ---------------- */
const llmStatus = ref<LlmStatus | null>(null)
/** 用户选择的模型供应商（null 表示使用默认） */
const selectedProviderId = ref<number | null>(null)

/** 当前生效模型的展示文案（跟随下拉选择实时更新） */
const currentProviderLabel = computed(() => {
  const p = llmStatus.value?.providers?.find((p) => p.id === selectedProviderId.value)
  return p ? `${p.name} · ${p.model}` : (llmStatus.value?.model || '未选择')
})

async function loadLlmStatus() {
  try {
    llmStatus.value = await getLlmStatus()
    // 默认绑定默认供应商，保证下拉框展示与实际调用模型一致，避免"切换无变化"的误判
    const providers = llmStatus.value?.providers || []
    const def = providers.find((p) => p.is_default) || providers[0]
    if (def && selectedProviderId.value === null) {
      selectedProviderId.value = def.id
    }
  } catch {
    llmStatus.value = null
  }
}

/* ---------------- 引用链接渲染 ---------------- */
/** 富文本渲染：将回答中的 [n]（本地引用）与 [Wn]（网络来源）渲染为高亮可点击锚点，其余内容安全转义 */
function renderRich(text: string): string {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  return escaped
    .replace(/\[W(\d+)\]/g, '<span class="cite-ref cite-ref-web" data-type="web" data-idx="$1">[W$1]</span>')
    .replace(/\[(\d+)\]/g, '<span class="cite-ref cite-ref-local" data-type="local" data-idx="$1">[$1]</span>')
}

function onCiteRefClick(e: MouseEvent, msg: LocalMsg) {
  const el = (e.target as HTMLElement).closest('.cite-ref') as HTMLElement | null
  if (!el) return
  e.preventDefault()
  e.stopPropagation()
  const type = el.dataset.type
  const idx = Number(el.dataset.idx || 0)
  if (type === 'web') {
    const src = msg.webSources?.[idx - 1]
    if (src?.url) {
      window.open(src.url, '_blank', 'noopener,noreferrer')
      return
    }
    ElMessage.info('该网络来源不可用')
    return
  }
  // 本地引用：展示溯源引用弹窗
  if (msg.citations?.length) {
    activeCitations.value = msg.citations
    citationsVisible.value = true
    return
  }
  ElMessage.info('该消息无溯源引用')
}

/* ---------------- 溯源引用 ---------------- */
const citationsVisible = ref(false)
const activeCitations = ref<Citation[]>([])

function openCitations(msg: LocalMsg) {
  if (!msg.citations?.length) {
    ElMessage.info('该消息无溯源引用')
    return
  }
  activeCitations.value = msg.citations
  citationsVisible.value = true
}

/* ---------------- 生命周期 ---------------- */
onMounted(() => {
  loadConvs()
  loadDocOptions()
  loadLlmStatus()
})

watch(
  () => messages.value.length,
  () => scrollToBottom(),
)

onBeforeUnmount(() => {
  stopTypeTimer()
})
</script>

<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <aside class="chat-sidebar">
      <el-button type="primary" :icon="Plus" class="new-conv-btn" @click="newConversation">新建对话</el-button>

      <div v-loading="loadingConvs" class="conv-list">
        <div
          v-for="conv in convs"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentConvId }"
          @click="openConversation(conv.id)"
        >
          <el-icon class="conv-icon"><ChatDotRound /></el-icon>
          <span class="conv-title">{{ conv.title }}</span>
          <el-icon class="conv-del" @click.stop="removeConversation(conv.id)"><Delete /></el-icon>
        </div>
        <div v-if="!convs.length && !loadingConvs" class="ks-empty">暂无历史会话</div>
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <section class="chat-main">
      <div class="chat-header">
        <div class="chat-title">
          <el-icon style="margin-right: 6px"><Document /></el-icon>
          {{ currentTitle }}
          <el-tag
            v-if="llmStatus"
            size="small"
            :type="llmStatus.configured ? 'success' : 'warning'"
            class="llm-status-tag"
          >
            {{ llmStatus.configured ? `当前模型 · ${currentProviderLabel}` : '模型未接入 · 本地降级回答' }}
          </el-tag>
          <el-select
            v-if="llmStatus?.providers?.length"
            v-model="selectedProviderId"
            size="small"
            class="model-select"
            placeholder="选择模型"
            :title="`切换对话模型（当前：${currentProviderLabel}）`"
          >
            <el-option
              v-for="p in llmStatus.providers"
              :key="p.id"
              :label="`${p.name} · ${p.model}`"
              :value="p.id"
            />
          </el-select>
        </div>
        <div class="chat-header-actions">
          <el-tooltip content="重置上下文：后续提问不再携带本次会话历史">
            <el-button size="small" :icon="RefreshRight" @click="handleResetContext">
              {{ resetApplied ? '已重置上下文' : '重置上下文' }}
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <!-- 消息区 -->
      <div ref="msgListRef" class="msg-list">
        <div v-if="!messages.length" class="chat-welcome">
          <div class="welcome-flow" aria-hidden="true">
            <i class="wf wf-1"></i>
            <i class="wf wf-2"></i>
            <i class="wf wf-3"></i>
          </div>
          <span class="w-particle wp-1"></span>
          <span class="w-particle wp-2"></span>
          <span class="w-particle wp-3"></span>
          <div class="welcome-orb">
            <div class="welcome-badge">知</div>
            <span class="orb-ring orb-ring-1"></span>
            <span class="orb-ring orb-ring-2"></span>
          </div>
          <div class="welcome-title">您好，我是知寻KnowSeek助手</div>
          <div class="welcome-desc">基于企业知识库为您提供精准问答，每条回答均可溯源引用。</div>
          <div class="welcome-hint">
            <span class="hint-chip">上传文档沉淀知识</span>
            <span class="hint-arrow">→</span>
            <span class="hint-chip">提问</span>
            <span class="hint-arrow">→</span>
            <span class="hint-chip">溯源引用</span>
            <span class="hint-arrow">→</span>
            <span class="hint-chip">反馈优化</span>
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="msg-row"
          :class="msg.role === 'user' ? 'msg-user' : 'msg-ai'"
        >
          <div class="msg-bubble">
            <div class="msg-content">
              <span class="answer-text" v-html="renderRich(msg.displayText ?? msg.content)" @click="onCiteRefClick($event, msg)"></span>
              <span v-if="msg.streaming" class="type-cursor">▍</span>
            </div>

            <div v-if="msg.role === 'assistant' && !msg.streaming && msg.citations?.length" class="local-sources">
              <div class="local-sources-title">
                <el-icon><Document /></el-icon>
                <span>本地引用（{{ msg.citations.length }}）</span>
              </div>
              <div v-for="(c, ci) in msg.citations" :key="ci" class="local-source-item">
                <span class="local-source-doc">{{ c.doc_name }}</span>
                <span v-if="c.page_no" class="local-source-page">第 {{ c.page_no }} 页</span>
                <span v-if="c.sheet_name" class="local-source-page">工作表：{{ c.sheet_name }}</span>
              </div>
            </div>

            <div v-if="msg.role === 'assistant' && !msg.streaming && collectKgEntities(msg).length" class="local-entities">
              <div class="local-entities-title">
                <el-icon><Connection /></el-icon>
                <span>关联知识图谱（{{ collectKgEntities(msg).length }}）</span>
              </div>
              <div class="local-entities-tags">
                <el-tag
                  v-for="e in collectKgEntities(msg)"
                  :key="e.id"
                  size="small"
                  class="kg-entity-tag"
                  effect="plain"
                  @click="goKgEntity(e.name)"
                >
                  {{ e.name }}
                </el-tag>
              </div>
            </div>

            <div v-if="msg.role === 'assistant' && !msg.streaming && msg.webSources?.length" class="web-sources">
              <div class="web-sources-title">
                <el-icon><Link /></el-icon>
                <span>网络来源（{{ msg.webSources.length }}）</span>
              </div>
              <div v-for="(src, si) in msg.webSources" :key="si" class="web-source-item">
                <a class="web-source-title" :href="src.url" target="_blank" rel="noopener noreferrer">{{ src.title }}</a>
                <div v-if="src.snippet" class="web-source-snippet">{{ src.snippet }}</div>
              </div>
            </div>

            <div v-if="msg.role === 'assistant' && !msg.streaming && msg.content" class="msg-tools">
              <el-tooltip content="复制回答" placement="top" :show-after="200">
                <el-button class="msg-tool-btn" size="small" circle text :icon="CopyDocument" @click="copyMessage(msg)" />
              </el-tooltip>
              <el-tooltip content="溯源引用" placement="top" :show-after="200">
                <el-button class="msg-tool-btn" size="small" circle text @click="openCitations(msg)">
                  <el-icon><Link /></el-icon>
                  <span class="cite-count">{{ msg.citations?.length || 0 }}</span>
                </el-button>
              </el-tooltip>
              <el-tooltip content="有帮助" placement="top" :show-after="200">
                <el-button
                  class="msg-tool-btn"
                  size="small"
                  circle
                  text
                  :type="msg.feedback === 'good' ? 'success' : ''"
                  @click="msg.feedback === 'good' ? undefined : openFeedback(msg, 'good')"
                >
                  <el-icon><CircleCheckFilled /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="需改进" placement="top" :show-after="200">
                <el-button
                  class="msg-tool-btn"
                  size="small"
                  circle
                  text
                  :type="msg.feedback === 'bad' ? 'danger' : ''"
                  @click="msg.feedback === 'bad' ? undefined : openFeedback(msg, 'bad')"
                >
                  <el-icon><Warning /></el-icon>
                </el-button>
              </el-tooltip>
            </div>

            <div v-if="msg.streaming" class="streaming-tip">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span> 生成中…
              <span v-if="streamHint" class="streaming-hint">{{ streamHint }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input-area">
        <div class="input-toolbar">
          <span class="ks-muted">参考文档（多选，将作为上下文提示）：</span>
          <el-select
            v-model="selectedDocs"
            multiple
            collapse-tags
            clearable
            placeholder="选择参考文档"
            style="width: 320px"
            size="small"
          >
            <el-option
              v-for="d in docOptions"
              :key="d.id"
              :label="`${d.doc_name} (v${d.version_no})`"
              :value="d.id"
            />
          </el-select>
          <el-switch
            v-model="webSearch"
            class="web-search-switch"
            active-text="联网检索"
            inactive-text="联网检索"
            inline-prompt
          />
          <span v-if="resetApplied" class="reset-badge">上下文已重置</span>
        </div>

        <div class="input-box">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="输入您的问题，Enter 发送，Shift+Enter 换行"
            @keydown="handleKeydown"
          />
          <div class="input-actions">
            <el-button v-if="sending" text @click="handleStop">停止生成</el-button>
            <el-button type="primary" :icon="Promotion" :loading="sending" @click="handleSend">发送</el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- 溯源引用弹窗 -->
    <CitationsDialog v-model="citationsVisible" :citations="activeCitations" />

    <!-- 反馈弹窗 -->
    <el-dialog v-model="feedbackVisible" append-to-body :title="feedbackScore === 'good' ? '反馈：有帮助' : '反馈：需改进'" width="460px">
      <el-input v-model="feedbackContent" type="textarea" :rows="4" placeholder="请补充您的意见（可选）" />
      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" @click="submitFeedback">提交反馈</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.chat-layout {
  height: calc(100vh - 56px);
  display: flex;
  max-width: 1440px;
  margin: 0 auto;
}

.chat-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: rgba(11, 23, 48, 0.55);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-right: 1px solid rgba(148, 163, 184, 0.16);
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.new-conv-btn {
  width: 100%;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  color: rgba(226, 232, 240, 0.88);
  font-size: 13px;
  transition: background 0.18s ease, box-shadow 0.18s ease;
  border: 1px solid transparent;
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 10px rgba(2, 8, 23, 0.2);
}

.conv-item.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.3), rgba(37, 99, 235, 0.14));
  border-color: rgba(96, 165, 250, 0.4);
  color: #dbeafe;
  font-weight: 600;
  box-shadow: inset 3px 0 0 #3b82f6;
}

.conv-icon {
  flex-shrink: 0;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-del {
  flex-shrink: 0;
  opacity: 0;
  color: var(--ks-danger);
}

.conv-item:hover .conv-del {
  opacity: 1;
}

.conv-list .ks-empty {
  padding: 20px 0;
  color: rgba(203, 213, 225, 0.7);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: transparent;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.llm-status-tag {
  flex-shrink: 0;
}

/* 模型选择下拉：明确的下拉框外观，避免被误认为按钮 */
.model-select {
  width: 230px;
  flex-shrink: 0;
}

.model-select .el-select__wrapper {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(37, 99, 235, 0.25);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
  padding: 2px 8px;
  min-height: 26px;
  cursor: pointer;
}

.model-select .el-select__wrapper.is-focused {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.model-select .el-select__selected-item,
.model-select .el-select__placeholder {
  font-size: 12px;
  font-weight: 500;
}

.model-select .el-select__caret {
  color: var(--ks-text-secondary);
}

.msg-list {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  scrollbar-gutter: stable;
  overscroll-behavior: contain;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 消息区滚动条：始终可见，保证长内容可完整阅读 */
.msg-list::-webkit-scrollbar {
  width: 10px;
}

.msg-list::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #b6c4e8, #93a9d8);
  border-radius: 5px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.msg-list::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #93a9d8, #7b92c4);
  background-clip: padding-box;
}

.msg-list::-webkit-scrollbar-track {
  background: transparent;
}

.msg-list {
  scrollbar-width: thin;
  scrollbar-color: #93a9d8 transparent;
}

.chat-welcome {
  position: relative;
  margin: 80px auto 0;
  text-align: center;
}

.welcome-flow {
  position: absolute;
  inset: -60px -120px;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.wf {
  position: absolute;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  filter: blur(64px);
  opacity: 0.5;
  animation: wf-drift 11s ease-in-out infinite;
}

.wf-1 { left: 8%; top: 0; background: radial-gradient(circle, rgba(37, 99, 235, 0.42), transparent 70%); }
.wf-2 { right: 2%; top: 34%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(139, 92, 246, 0.34), transparent 70%); animation-delay: -4s; }
.wf-3 { left: 32%; bottom: -30px; width: 260px; height: 260px; background: radial-gradient(circle, rgba(14, 165, 233, 0.32), transparent 70%); animation-delay: -7s; }

@keyframes wf-drift {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(34px, -26px, 0) scale(1.16); }
}

.w-particle {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(147, 197, 253, 0.95), rgba(147, 197, 253, 0));
  filter: blur(1px);
  z-index: 0;
  pointer-events: none;
  animation: wp-float 7s ease-in-out infinite;
}

.wp-1 { width: 7px; height: 7px; left: 26%; top: 14%; }
.wp-2 { width: 9px; height: 9px; left: 63%; top: 8%; animation-delay: -2.4s; }
.wp-3 { width: 6px; height: 6px; left: 47%; top: 42%; animation-delay: -4.8s; }

@keyframes wp-float {
  0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.25; }
  50% { transform: translate3d(20px, -46px, 0); opacity: 0.95; }
}

.chat-welcome > :not(.welcome-flow):not(.w-particle) {
  position: relative;
  z-index: 1;
}

.welcome-badge {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #1e40af);
  color: #fff;
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  position: relative;
  animation: ks-logo-glow 3s ease-in-out infinite;
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 8px;
}

.welcome-desc {
  font-size: 14px;
  color: rgba(203, 213, 225, 0.85);
  margin-bottom: 16px;
}

.welcome-hint {
  font-size: 12px;
  color: rgba(148, 163, 184, 0.9);
}

.msg-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 10px;
  max-width: 82%;
  animation: msg-enter 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes msg-enter {
  from { opacity: 0; transform: translateY(16px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.msg-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6 0%, #1e40af 60%, #0f172a 170%);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.28);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.msg-bubble {
  position: relative;
  border-radius: 16px;
  padding: 12px 16px;
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.msg-content {
  position: relative;
  z-index: 1;
  white-space: pre-wrap;
}

.msg-user .msg-bubble {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 68%, #4338ca 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  border: 1px solid rgba(37, 99, 235, 0.28);
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.msg-ai .msg-bubble {
  position: relative;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92) 0%, rgba(243, 248, 255, 0.78) 100%);
  backdrop-filter: blur(16px) saturate(140%);
  -webkit-backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-bottom-left-radius: 4px;
  box-shadow:
    0 8px 30px rgba(15, 23, 42, 0.08),
    0 0 22px rgba(37, 99, 235, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  color: var(--ks-text-title);
  font-size: 15px;
  line-height: 1.75;
  font-weight: 450;
  transition: box-shadow 0.3s ease, border-color 0.3s ease, transform 0.3s ease;
}

.msg-ai .msg-bubble:hover {
  transform: translateY(-2px);
  box-shadow:
    0 14px 38px rgba(15, 23, 42, 0.1),
    0 0 30px rgba(37, 99, 235, 0.14),
    inset 0 1px 0 rgba(255, 255, 255, 0.95);
  border-color: rgba(37, 99, 235, 0.2);
}

.streaming-tip {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.streaming-hint {
  margin-left: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

/* 打字机光标 */
.type-cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--ks-primary);
  font-weight: 700;
  animation: ks-cursor-blink 0.9s steps(2, start) infinite;
}

@keyframes ks-cursor-blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ks-primary);
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.65);
  animation: blink 1.2s infinite;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.2;
  }
  40% {
    opacity: 1;
  }
}

.msg-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgba(37, 99, 235, 0.1);
}

/* 网络来源区块：与引用区块风格协调 */
.local-sources {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgba(37, 99, 235, 0.1);
}

.local-sources-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-primary);
  margin-bottom: 8px;
}

.local-source-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
  padding: 6px 10px;
  border-left: 3px solid rgba(139, 92, 246, 0.4);
  border-radius: 0 8px 8px 0;
  background: rgba(139, 92, 246, 0.05);
  font-size: 13px;
}

.local-source-item:last-child {
  margin-bottom: 0;
}

.local-source-doc {
  font-weight: 600;
  color: #4c1d95;
  word-break: break-all;
}

.local-source-page {
  font-size: 12px;
  color: rgba(71, 85, 105, 0.85);
  background: rgba(139, 92, 246, 0.08);
  border-radius: 4px;
  padding: 1px 6px;
}

/* 回答内引用锚点 */
.cite-ref {
  display: inline-block;
  margin: 0 1px;
  padding: 0 3px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.cite-ref-local {
  color: #1d4ed8;
  background: rgba(37, 99, 235, 0.12);
  border: 1px solid rgba(37, 99, 235, 0.35);
}

.cite-ref-web {
  color: #0e7490;
  background: rgba(14, 165, 233, 0.12);
  border: 1px solid rgba(14, 165, 233, 0.35);
}

.cite-ref:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.24);
}

.web-sources {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgba(37, 99, 235, 0.1);
}

.local-entities {
  margin-top: 8px;
  padding: 8px 10px;
  border-top: 1px dashed rgba(139, 92, 246, 0.2);
}

.local-entities-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #8b5cf6;
  margin-bottom: 6px;
}

.local-entities-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kg-entity-tag {
  cursor: pointer;
  border-color: rgba(139, 92, 246, 0.35);
  color: #a78bfa;
  background: rgba(139, 92, 246, 0.08);
}

.kg-entity-tag:hover {
  color: #c4b5fd;
  border-color: #8b5cf6;
  background: rgba(139, 92, 246, 0.18);
}

.web-sources-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-primary);
  margin-bottom: 8px;
}

.web-source-item {
  margin-bottom: 8px;
  padding: 8px 10px;
  border-left: 3px solid rgba(37, 99, 235, 0.35);
  border-radius: 0 8px 8px 0;
  background: rgba(37, 99, 235, 0.05);
}

.web-source-item:last-child {
  margin-bottom: 0;
}

.web-source-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
  text-decoration: none;
  word-break: break-all;
}

.web-source-title:hover {
  color: #2563eb;
  text-decoration: underline;
}

.web-source-snippet {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(71, 85, 105, 0.85);
  word-break: break-word;
}

.web-search-switch {
  margin-left: 4px;
}

.web-search-switch .el-switch__label {
  font-size: 12px;
  color: rgba(203, 213, 225, 0.8);
}

.msg-tools .msg-tool-btn.el-button {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: rgba(203, 213, 225, 0.82);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.msg-tools .msg-tool-btn.el-button:hover {
  color: #fff;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.5), rgba(99, 102, 241, 0.44));
  border-color: rgba(147, 197, 253, 0.34);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.26);
  transform: translateY(-2px);
}

.msg-tools .msg-tool-btn.el-button:active {
  transform: translateY(0);
}

.msg-tools .msg-tool-btn.el-button.is-success {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.4);
  background: rgba(52, 211, 153, 0.14);
}

.msg-tools .msg-tool-btn.el-button.is-danger {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.14);
}

.msg-tools .cite-count {
  font-size: 11px;
  margin-left: 1px;
}

.chat-input-area {
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  padding: 12px 20px 16px;
  background: rgba(11, 23, 48, 0.55);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
}

.input-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.input-toolbar .ks-muted {
  font-size: 12px;
  color: rgba(203, 213, 225, 0.8);
}

.reset-badge {
  font-size: 12px;
  color: var(--ks-success);
  background: #ecfdf5;
  border-radius: 4px;
  padding: 2px 8px;
}

.input-box {
  position: relative;
  border-radius: 12px;
  border: 1px solid var(--el-border-color);
  background: #fff;
  box-shadow: var(--ks-shadow-sm);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.input-box:focus-within {
  border-color: var(--ks-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16), 0 0 24px rgba(37, 99, 235, 0.16), var(--ks-shadow-md);
}

.input-box .el-textarea__inner {
  border: none;
  box-shadow: none;
  padding: 10px 14px;
  background: transparent;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
  padding: 0 10px 10px;
}
/* ---------------- 移动端适配 ---------------- */
@media (max-width: 900px) {
  .chat-layout {
    flex-direction: column;
  }

  /* 会话列表折叠为顶部横条，移动端仍可切换会话 */
  .chat-sidebar {
    width: 100% !important;
    max-height: 220px;
    overflow-y: auto;
    border-right: none !important;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    padding: 10px !important;
    flex-direction: row;
  }

  .chat-sidebar .new-conv-btn {
    flex-shrink: 0;
  }

  .conv-list {
    display: flex;
    flex-direction: row;
    gap: 8px;
    overflow-x: auto;
  }

  .conv-item {
    flex-shrink: 0;
    max-width: 180px;
  }

  .chat-main {
    flex: 1;
  }
}

@media (max-width: 768px) {
  .chat-header {
    flex-wrap: wrap;
    gap: 8px;
  }

  .chat-title {
    min-width: 0;
  }

  .msg-tools {
    flex-wrap: wrap;
  }

  .input-toolbar {
    flex-wrap: wrap;
  }

  .input-box textarea {
    font-size: 15px;
  }
}
</style>
