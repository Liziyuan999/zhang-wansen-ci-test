<script setup lang="ts">
/**
 * AI 文档 Copilot 侧栏（功能三）
 * 支持：一键摘要 / 中英互译 / 文档要点提炼 / 基于选中片段提问
 */
import { ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, DocumentCopy, RefreshRight, ChatLineRound, Delete, Position } from '@element-plus/icons-vue'
import { runCopilot, type CopilotCitation, type CopilotResult } from '@/api/copilot'

const props = defineProps<{
  docId: number
  docName: string
  selectedText: string
}>()

const emit = defineEmits<{ (e: 'clear-selected'): void }>()

const busy = ref(false)
const lastAction = ref('')
const answer = ref('')
const displayAnswer = ref('')
const citations = ref<CopilotCitation[]>([])
const questionInput = ref('')

/* ---------------- 打字机流式展示 ---------------- */
let typeTimer: ReturnType<typeof setInterval> | null = null

function stopTyping() {
  if (typeTimer) {
    clearInterval(typeTimer)
    typeTimer = null
  }
}

function typewrite(full: string) {
  stopTyping()
  displayAnswer.value = ''
  const step = Math.max(2, Math.ceil(full.length / 180))
  let idx = 0
  typeTimer = setInterval(() => {
    idx = Math.min(full.length, idx + step)
    displayAnswer.value = full.slice(0, idx)
    if (idx >= full.length && typeTimer) {
      clearInterval(typeTimer)
      typeTimer = null
    }
  }, 28)
}

/* ---------------- 动作执行 ---------------- */
// ===== 逐行注释：Copilot 动作执行（四动作统一入口）=====
// 1. execute(action, question)：按动作类型分发到后端 /api/documents/{docId}/copilot：
//    summary=一键摘要 / translate=中英互译 / outline=要点提炼 / ask=基于选中片段提问；
// 2. 请求携带 doc_id、action、source_text（当前选中文本）与 question（提问内容），
//    后端在 copilot_service.run_copilot 中按动作构造提示词并调用 LLM；
// 3. 返回后写入 answer 与 citations（引用来源列表），再用 typewrite 打字机效果流式展示；
// 4. 忙时防重入（busy 开关），切换文档自动清空状态，卸载前停止打字机定时器。
async function execute(action: string, question = '') {
  if (busy.value) return
  busy.value = true
  stopTyping()
  answer.value = ''
  displayAnswer.value = ''
  citations.value = []
  lastAction.value = action
  try {
    const res = await runCopilot({
      doc_id: props.docId,
      action,
      source_text: props.selectedText || undefined,
      question: question || undefined,
    })
    answer.value = res.answer || '（未返回内容）'
    citations.value = res.citations || []
    typewrite(answer.value)
  } catch {
    // 拦截器已提示
  } finally {
    busy.value = false
  }
}

function doSummary() {
  execute('summary')
}
function doTranslate() {
  execute('translate')
}
function doOutline() {
  execute('outline')
}
function doAsk() {
  const q = questionInput.value.trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  execute('ask', q)
}

function clearSelection() {
  emit('clear-selected')
}

/* 切换文档时清空状态 */
watch(
  () => props.docId,
  () => {
    stopTyping()
    answer.value = ''
    displayAnswer.value = ''
    citations.value = []
    lastAction.value = ''
    questionInput.value = ''
  },
)

onBeforeUnmount(() => stopTyping())

const actionHint = {
  ask: '基于选中片段或文档上下文作答，并附带引用定位',
  summary: '生成结论先行的结构化摘要（约 400 字）',
  translate: '按文档语言自动中英互译，保留专业书面语气',
  outline: '提炼结构化要点大纲，一/（一）/1. 层级呈现',
} as Record<string, string>
</script>

<template>
  <div class="copilot-panel">
    <div class="cp-head">
      <div class="cp-title">
        <el-icon class="cp-title-icon"><MagicStick /></el-icon>
        <span>AI 文档 Copilot</span>
      </div>
      <div class="cp-sub">智能理解 · 精准定位 · 即问即答</div>
    </div>

    <!-- 选中片段 -->
    <div v-if="props.selectedText" class="cp-selection">
      <div class="cp-selection-head">
        <el-icon><DocumentCopy /></el-icon>
        <span>已选中片段</span>
        <el-button link size="small" :icon="Delete" class="cp-clear" @click="clearSelection">清除</el-button>
      </div>
      <div class="cp-selection-text">{{ props.selectedText.slice(0, 140) }}{{ props.selectedText.length > 140 ? '…' : '' }}</div>
      <div class="cp-selection-tip">可基于该片段提问，也可忽略片段使用全文档</div>
    </div>

    <!-- 操作区 -->
    <div class="cp-actions">
      <el-button class="cp-action-btn" :loading="busy && lastAction === 'summary'" @click="doSummary">
        <el-icon><DocumentCopy /></el-icon>一键摘要
      </el-button>
      <el-button class="cp-action-btn" :loading="busy && lastAction === 'translate'" @click="doTranslate">
        <el-icon><Position /></el-icon>中英互译
      </el-button>
      <el-button class="cp-action-btn" :loading="busy && lastAction === 'outline'" @click="doOutline">
        <el-icon><RefreshRight /></el-icon>文档要点
      </el-button>
    </div>

    <!-- 选中提问 -->
    <div class="cp-ask">
      <el-input
        v-model="questionInput"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入问题，基于文档内容精准回答…"
        @keydown.enter.prevent="doAsk"
      />
      <el-button
        type="primary"
        class="cp-ask-btn"
        :icon="ChatLineRound"
        :loading="busy && lastAction === 'ask'"
        :disabled="!questionInput.trim()"
        @click="doAsk"
      >
        选中文档提问
      </el-button>
    </div>

    <!-- 回答区 -->
    <div v-if="displayAnswer || busy" class="cp-result">
      <div class="cp-result-head">
        <span>{{ busy ? '思考中…' : '回答' }}</span>
        <span v-if="lastAction" class="cp-action-tag">{{ lastAction }}</span>
      </div>
      <div class="cp-result-body">
        <div class="cp-answer">{{ displayAnswer }}<span v-if="busy" class="cp-cursor">▍</span></div>
        <div v-if="!busy && answer && displayAnswer.length < answer.length" class="cp-typing-tip">生成中…</div>
      </div>
    </div>

    <!-- 引用定位 -->
    <div v-if="citations.length" class="cp-citations">
      <div class="cp-citations-title">引用定位（{{ citations.length }}）</div>
      <div class="cp-citation-item" v-for="(c, i) in citations" :key="c.chunk_id || i">
        <span class="cp-cite-idx">[{{ i + 1 }}]</span>
        <span class="cp-cite-loc">
          {{ c.doc_name || props.docName }}{{ c.page_no ? ` · 第${c.page_no}页` : '' }}{{ c.sheet_name ? ` · ${c.sheet_name}` : '' }}
        </span>
        <span class="cp-cite-snippet">{{ c.snippet }}</span>
      </div>
    </div>

    <div v-if="!displayAnswer && !busy" class="cp-empty">
      <el-icon><MagicStick /></el-icon>
      <p>点击上方能力卡片，或选中正文片段后输入问题</p>
      <p class="cp-empty-hint">回答将流式呈现，并附引用定位便于核对</p>
    </div>
  </div>
</template>

<style scoped>
.copilot-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 2px;
}

.cp-head {
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(140deg, rgba(37, 99, 235, 0.1), rgba(124, 58, 237, 0.06));
  border: 1px solid rgba(37, 99, 235, 0.16);
}

.cp-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ks-text-title);
}

.cp-title-icon {
  color: var(--ks-primary);
  font-size: 18px;
}

.cp-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ks-text-muted);
}

.cp-selection {
  border: 1px dashed rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.05);
  border-radius: 10px;
  padding: 10px 12px;
}

.cp-selection-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-primary);
}

.cp-clear {
  margin-left: auto;
  color: var(--ks-text-muted);
}

.cp-selection-text {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ks-text-body);
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  padding: 6px 8px;
  max-height: 96px;
  overflow-y: auto;
  word-break: break-word;
}

.cp-selection-tip {
  margin-top: 6px;
  font-size: 11px;
  color: var(--ks-text-muted);
}

.cp-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.cp-action-btn {
  flex-direction: column;
  gap: 4px;
  height: auto;
  padding: 10px 4px;
  font-size: 12px;
  border-radius: 10px;
  color: var(--ks-text-body);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(245, 249, 255, 0.8));
  border: 1px solid rgba(37, 99, 235, 0.14);
  transition: all 0.22s ease;
}

.cp-action-btn:hover {
  color: var(--ks-primary);
  border-color: rgba(37, 99, 235, 0.4);
  background: var(--ks-primary-light);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.12);
}

.cp-action-btn .el-icon {
  font-size: 16px;
}

.cp-ask {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.cp-ask-btn {
  height: 44px;
  flex-shrink: 0;
}

.cp-result {
  border-radius: 12px;
  background: linear-gradient(160deg, #f8fbff, #eef4ff);
  border: 1px solid rgba(37, 99, 235, 0.12);
  overflow: hidden;
}

.cp-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-primary);
  border-bottom: 1px solid rgba(37, 99, 235, 0.1);
}

.cp-action-tag {
  font-size: 11px;
  font-weight: 400;
  color: var(--ks-text-muted);
}

.cp-result-body {
  padding: 12px;
  min-height: 60px;
}

.cp-answer {
  font-size: 13px;
  line-height: 1.75;
  color: var(--ks-text-body);
  white-space: pre-wrap;
  word-break: break-word;
}

.cp-cursor {
  color: var(--ks-primary);
  animation: cp-blink 0.9s steps(2) infinite;
}

@keyframes cp-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.cp-citations {
  border-radius: 12px;
  border: 1px solid rgba(124, 58, 237, 0.16);
  background: rgba(124, 58, 237, 0.04);
  padding: 10px 12px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.cp-citations-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-text-title);
  margin-bottom: 8px;
}

.cp-citation-item {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  font-size: 12px;
  padding: 4px 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

.cp-cite-idx {
  color: var(--ks-primary);
  font-weight: 700;
  flex-shrink: 0;
}

.cp-cite-loc {
  color: var(--ks-text-body);
  font-weight: 500;
  min-width: 0;
  flex-shrink: 1;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.cp-cite-snippet {
  color: var(--ks-text-muted);
  line-height: 1.5;
  min-width: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.cp-empty {
  text-align: center;
  color: var(--ks-text-muted);
  font-size: 12px;
  padding: 28px 12px;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  background: rgba(248, 251, 255, 0.5);
}

.cp-empty .el-icon {
  font-size: 28px;
  color: var(--ks-primary);
  opacity: 0.6;
}

.cp-empty-hint {
  font-size: 11px;
  color: var(--ks-text-muted);
  margin-top: 4px;
}
</style>
