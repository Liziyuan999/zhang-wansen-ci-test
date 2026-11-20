<script setup lang="ts">
/**
 * Agent 任务页：任务创建 / 检索片段预览 / 人工确认流程
 */
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, View, Check, Close, Timer, Document, Tickets, EditPen, ArrowDown, Share, Connection } from '@element-plus/icons-vue'
import { createAgentTask, confirmAgentTask, listAgentTasks } from '@/api/agent'
import { getLlmStatus, type LlmStatus } from '@/api/chat'
import { listDocuments } from '@/api/document'
import WorkflowCanvasBuilder from '@/components/WorkflowCanvasBuilder.vue'
import type { AgentTaskResp, DocListItem } from '@/types'

/* ---------------- 列表 ---------------- */
const tasks = ref<AgentTaskResp[]>([])
const loading = ref(false)
let timer: number | null = null

const statusMeta: Record<string, { label: string; type: string }> = {
  retrieving: { label: '检索中', type: 'primary' },
  waiting_confirm: { label: '待人工确认', type: 'warning' },
  finished: { label: '已完成', type: 'primary' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

const taskTypeMeta: Record<string, string> = {
  weekly_report: '周报生成',
  doc_compare: '文档对比',
  write_plan: '方案撰写',
}

function taskTypeIcon(task: AgentTaskResp) {
  if (task.task_type === 'doc_compare') return Tickets
  if (task.task_type === 'write_plan') return EditPen
  return Document
}

function displayType(task: AgentTaskResp): string {
  return task.task_type ? taskTypeMeta[task.task_type] || task.task_type : 'Agent 任务'
}

function displayTime(task: AgentTaskResp): string {
  return task.create_time || '-'
}

/** 关联文档名称（多选 id -> 名称） */
function docNameOf(task: AgentTaskResp): string {
  const ids = task.selected_doc_ids || []
  if (!ids.length) return '未选择文档'
  const names = docOptions.value
    .filter((d) => ids.includes(d.id))
    .map((d) => d.doc_name)
  return names.length ? names.join('、') : `文档 ${ids.join('、')}`
}

/** 补充参数摘要（params JSON -> 文本） */
function paramSummary(task: AgentTaskResp): string {
  const p = task.params
  if (!p || !Object.keys(p).length) return ''
  return Object.entries(p)
    .map(([k, v]) => `${k}：${Array.isArray(v) ? v.join('、') : v}`)
    .join('；')
}

/** 人工确认状态（详情弹窗直观展示） */
function confirmStatus(task: AgentTaskResp) {
  if (!task.need_confirm) return { label: '无需确认', type: 'info' as const }
  switch (task.status) {
    case 'waiting_confirm':
      return { label: '待人工确认', type: 'warning' as const }
    case 'finished':
      return { label: '已确认执行', type: 'success' as const }
    case 'cancelled':
      return { label: '已取消', type: 'info' as const }
    case 'failed':
      return { label: '失败', type: 'danger' as const }
    default:
      return { label: task.status, type: 'info' as const }
  }
}

// ===== 逐行注释：Agent 任务列表加载与轮询 =====
// 1. loadTasks：调用后端 /api/agent/tasks 拉取当前用户全部任务（周报/文档对比/方案撰写）；
// 2. 状态机：retrieving(检索中) → waiting_confirm(待人工确认) → finished/failed/cancelled，
//    前端据此渲染标签；need_confirm 任务必须先经用户确认才会真正调用 LLM 生成（安全机制）；
// 3. startPolling：每 5 秒轮询一次，让"检索中/待确认"任务自动刷新到最新状态；
// 4. docNameOf/paramSummary：把任务关联文档 id 与补充参数 JSON 还原成可读文本供界面展示。
async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await listAgentTasks()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  timer = window.setInterval(() => {
    loadTasks()
  }, 5000)
}

function stopPolling() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

/* ---------------- 新建任务 ---------------- */
const createVisible = ref(false)
const creating = ref(false)
const docOptions = ref<DocListItem[]>([])
const createForm = reactive({
  task_type: 'weekly_report' as 'weekly_report' | 'doc_compare' | 'write_plan',
  doc_ids: [] as number[],
  param_text: '',
  graph_engine: 'classic' as 'classic' | 'langgraph' | 'canvas',
})
/** 工作流编排画布：打开画布弹窗 / 待提交的画布 JSON / 画布来源任务类型 */
const canvasVisible = ref(false)
const pendingCanvasJson = ref('')
const pendingCanvasTaskType = ref('weekly_report' as 'weekly_report' | 'doc_compare' | 'write_plan')

function openCanvas() {
  canvasVisible.value = true
}

function handleCanvasCreate(payload: { canvasJson: string; taskType: string }) {
  pendingCanvasJson.value = payload.canvasJson
  pendingCanvasTaskType.value = payload.taskType as 'weekly_report' | 'doc_compare' | 'write_plan'
  canvasVisible.value = false
  openCreate()
}
/** 模型供应商列表与选中项（null=使用默认） */
const llmStatus = ref<LlmStatus | null>(null)
const selectedProviderId = ref<number | null>(null)

async function loadProviders() {
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
}
/* 新建任务联网检索开关：默认开启，检索阶段融合实时网络结果 */
const createWebSearch = ref(true)

const taskTypeOptions = [
  { value: 'weekly_report', label: '周报生成', desc: '基于选定文档自动生成部门周报', icon: Document },
  { value: 'doc_compare', label: '文档对比', desc: '对选定文档进行内容对比分析', icon: Tickets },
  { value: 'write_plan', label: '方案撰写', desc: '基于选定文档撰写工作方案', icon: EditPen },
]

async function loadDocOptions() {
  try {
    const res = await listDocuments({ page: 1, page_size: 100 })
    docOptions.value = res.items.filter((d) => d.status === 'success')
  } catch {
    // 忽略
  }
}

function openCreate() {
  createForm.task_type = pendingCanvasJson.value ? pendingCanvasTaskType.value : 'weekly_report'
  createForm.doc_ids = []
  createForm.param_text = ''
  createForm.graph_engine = pendingCanvasJson.value ? 'canvas' : 'classic'
  createWebSearch.value = true
  selectedProviderId.value = null
  createVisible.value = true
}

/** 是否为 LangGraph 工作流任务（params.graph_engine === 'langgraph'） */
function isLangGraph(task: AgentTaskResp): boolean {
  return (task.params && task.params.graph_engine === 'langgraph') || !!task.workflow_trace?.length
}

async function submitCreate() {
  if (!createForm.doc_ids.length) {
    ElMessage.warning('请至少选择一份文档')
    return
  }
  if (createForm.graph_engine === 'canvas' && !pendingCanvasJson.value) {
    ElMessage.warning('画布编排模式需要先在工作流编排画布中生成节点')
    return
  }
  creating.value = true
  try {
    const params: Record<string, unknown> = {
      web_search: createWebSearch.value,
      graph_engine: createForm.graph_engine,
    }
    if (createForm.param_text.trim()) {
      params.extra = createForm.param_text.trim()
    }
    const task = await createAgentTask({
      task_type: createForm.task_type,
      doc_ids: createForm.doc_ids,
      params,
      model_provider_id: selectedProviderId.value,
      canvas_json: createForm.graph_engine === 'canvas' ? pendingCanvasJson.value : null,
    })
    createVisible.value = false
    pendingCanvasJson.value = ''
    ElMessage.success('任务已创建，检索完成后需要人工确认')
    await loadTasks()
  } catch {
    // 拦截器已提示
  } finally {
    creating.value = false
  }
}

/* ---------------- 人工确认 ---------------- */
async function handleConfirm(task: AgentTaskResp, confirm: boolean) {
  try {
    const updated = await confirmAgentTask(task.task_id, confirm)
    ElMessage.success(confirm ? '已确认，任务继续执行' : '已取消该任务')
    // 更新本地列表中的该任务
    const idx = tasks.value.findIndex((t) => t.task_id === task.task_id)
    if (idx >= 0) tasks.value[idx] = updated
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 详情 ---------------- */
const detailVisible = ref(false)
const detailTask = ref<AgentTaskResp | null>(null)
/** 检索片段默认展开，可点击标题折叠 */
const detailChunkExpanded = ref(true)

function openDetail(task: AgentTaskResp) {
  detailTask.value = task
  detailVisible.value = true
}

function statusTag(task: AgentTaskResp) {
  const meta = statusMeta[task.status] || { label: task.status, type: 'info' }
  return (meta.type as 'success' | 'warning' | 'primary' | 'danger' | 'info')
}

function statusLabel(task: AgentTaskResp) {
  return (statusMeta[task.status] || { label: task.status }).label
}

/* ---------------- 工作流可视化 ---------------- */
type FlowStatus = 'ok' | 'running' | 'pending' | 'error'

interface FlowNodeItem {
  key: string
  name: string
  brief: string
  status: FlowStatus
  summary?: string
  cost_ms?: number
}

const FLOW_DEFAULT_NAMES: Record<string, string> = {
  plan: '任务规划',
  retrieve: '知识检索',
  generate: '内容生成',
  reflect: '质量反思',
  refine: '精修定稿',
}

/** 根据任务状态与已有轨迹推导可视化节点状态（finished=全部完成；waiting_confirm=等待人工确认；进行中=当前节点 running；失败/取消=异常终止） */
function flowNodes(task: AgentTaskResp): FlowNodeItem[] {
  const trace = task.workflow_trace || []
  const hasTrace = trace.length > 0
  const st = task.status
  const nodes: FlowNodeItem[] = []

  if (!hasTrace) {
    // 经典模式：无 workflow_trace 的旧任务，根据任务状态/参数生成更丰富兜底节点信息
    const params = (task.params && typeof task.params === 'object' ? task.params : {}) as Record<string, unknown>
    const typeName = task.task_type || '通用任务'
    const docCount = Array.isArray(params.doc_ids) ? params.doc_ids.length : 0
    const extra = typeof params.extra === 'string' && params.extra.trim() ? params.extra.trim() : ''
    const briefInput = `任务类型：${typeName}${docCount ? `，关联文档 ${docCount} 份` : ''}`
    const briefRetrieve = `RAG 检索${params.web_search ? ' + 联网搜索' : ''}${extra ? `；补充说明：${extra.slice(0, 40)}` : ''}`
    const generic: FlowNodeItem[] = [
      { key: 'input', name: '任务输入', brief: briefInput, status: 'pending' },
      { key: 'retrieve', name: '知识检索', brief: briefRetrieve, status: 'pending' },
      { key: 'generate', name: '内容生成', brief: st === 'failed' ? 'LLM 生成失败，任务终止' : st === 'cancelled' ? '任务已取消，未生成结果' : 'LLM 生成结果', status: 'pending' },
      { key: 'done', name: '完成', brief: st === 'finished' ? '任务交付完成' : st === 'waiting_confirm' ? '等待人工确认后继续执行' : '任务交付', status: 'pending' },
    ]
    let done = st === 'finished' ? 4 : st === 'waiting_confirm' ? 2 : st === 'retrieving' || st === 'processing' || st === 'pending' ? 1 : 2
    if (st === 'failed' || st === 'cancelled') done = 1
    generic.forEach((n, i) => {
      if (i < done) n.status = 'ok'
      else if (i === done) n.status = st === 'failed' || st === 'cancelled' ? 'error' : 'running'
      else n.status = 'pending'
    })
    if (st === 'waiting_confirm') {
      generic.forEach((n, i) => {
        if (i === done) n.status = 'pending'
      })
    }
    return generic
  }

  const traceMap: Record<string, FlowNodeItem> = {}
  trace.forEach((t) => {
    traceMap[t.node] = {
      key: t.node,
      name: t.name || FLOW_DEFAULT_NAMES[t.node] || t.node,
      brief: t.summary || '',
      status: 'ok',
      summary: t.summary,
      cost_ms: t.cost_ms,
    }
  })
  const keys = ['plan', 'retrieve', 'generate', 'reflect', 'refine']
  keys.forEach((k) => {
    const t = traceMap[k]
    nodes.push(
      t || {
        key: k,
        name: FLOW_DEFAULT_NAMES[k] || k,
        brief: '',
        status: 'pending',
      },
    )
  })
  const executed = trace.length
  const waiting = st === 'waiting_confirm'
  nodes.forEach((n, i) => {
    if (i < executed) n.status = 'ok'
    else if (i === executed) n.status = waiting ? 'pending' : st === 'failed' || st === 'cancelled' ? 'error' : 'running'
    else n.status = 'pending'
  })
  if (st === 'finished') nodes.forEach((n) => (n.status = 'ok'))
  return nodes
}

function flowStatusLabel(s: FlowStatus): string {
  return { ok: '已完成', running: '执行中', pending: '待执行', error: '失败' }[s] || s
}

function flowStatusTag(s: FlowStatus): 'success' | 'primary' | 'info' | 'danger' {
  return ({ ok: 'success', running: 'primary', pending: 'info', error: 'danger' } as Record<FlowStatus, 'success' | 'primary' | 'info' | 'danger'>)[s]
}

const detailFlowActive = ref<string>('')
const detailFlowNode = computed(() => {
  if (!detailTask.value || !detailFlowActive.value) return null
  return flowNodes(detailTask.value).find((n) => n.key === detailFlowActive.value) || null
})
function selectFlowNode(key: string) {
  detailFlowActive.value = detailFlowActive.value === key ? '' : key
}
/** 列表卡片结果摘要 */
function resultPreview(task: AgentTaskResp): string {
  const r = task.task_result || ''
  return r.length > 90 ? `${r.slice(0, 90)}…` : r
}

function renderResult(result: string | null | undefined) {
  if (!result) return '暂无结果'
  // task_result 可能是文本或 JSON 字符串
  try {
    const parsed = JSON.parse(result)
    if (typeof parsed === 'object' && parsed !== null) {
      return JSON.stringify(parsed, null, 2)
    }
    return result
  } catch {
    return result
  }
}

/** 任务结果占位文案：按任务状态给出柔和提示，避免空白区域 */
function resultPlaceholder(task: AgentTaskResp): string {
  if (task.task_result) return renderResult(task.task_result)
  if (task.status === 'waiting_confirm') return '暂无生成结果：任务待人工确认'
  if (task.status === 'retrieving' || task.status === 'processing' || task.status === 'pending') {
    return '暂无生成结果：任务处理中'
  }
  if (task.status === 'failed') {
    return task.error_msg ? `任务执行失败：${task.error_msg}` : '任务执行失败，暂无生成结果'
  }
  if (task.status === 'cancelled') return '任务已取消，暂无生成结果'
  return '暂无生成结果'
}

onMounted(() => {
  loadTasks()
  loadDocOptions()
  loadProviders()
  startPolling()
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="ks-page">
    <div class="page-header">
      <h2 class="ks-page-title">Agent 任务</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadTasks">刷新</el-button>
        <el-button :icon="Connection" @click="openCanvas">工作流编排</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建任务</el-button>
      </div>
    </div>

    <div class="auto-refresh-tip">列表每 5 秒自动刷新，检索完成的任务将进入「人工确认」环节。</div>

    <div v-loading="loading">
      <div v-if="tasks.length" class="task-grid">
        <div v-for="task in tasks" :key="task.task_id" class="task-card">
          <div class="task-head">
            <span class="task-name">
              <el-icon class="task-type-icon"><component :is="taskTypeIcon(task)" /></el-icon>
              {{ displayType(task) }}
            </span>
            <el-tag :type="statusTag(task)" size="small" effect="light">{{ statusLabel(task) }}</el-tag>
            <el-tag v-if="isLangGraph(task)" size="small" effect="plain" class="engine-tag">LangGraph</el-tag>
          </div>

          <div class="task-meta">
            <span>任务号：{{ task.task_id }}</span>
            <span>创建：{{ displayTime(task) }}</span>
            <span v-if="task.finish_time">完成：{{ task.finish_time }}</span>
          </div>

          <div class="task-chunks">
            <span class="ks-muted">检索片段：{{ task.retrieval_chunks?.length || 0 }} 条</span>
            <span class="ks-muted">关联文档：{{ task.selected_doc_ids?.length || 0 }} 份</span>
          </div>

          <div class="task-flow-mini" :title="`工作流进度：${flowNodes(task).filter((n) => n.status === 'ok').length}/${flowNodes(task).length} 节点完成`">
            <template v-for="(n, i) in flowNodes(task)" :key="n.key">
              <span class="mini-dot" :class="'mini-' + n.status" :title="`${n.name}：${flowStatusLabel(n.status)}`"></span>
              <span v-if="i < flowNodes(task).length - 1" class="mini-line"></span>
            </template>
            <span class="mini-label">{{ flowNodes(task).filter((n) => n.status === 'ok').length }}/{{ flowNodes(task).length }} 节点完成</span>
          </div>

          <div v-if="task.status === 'waiting_confirm'" class="task-confirm">
            <span class="confirm-hint">需要人工确认后继续执行</span>
            <div class="confirm-actions">
              <el-button size="small" type="success" :icon="Check" @click="handleConfirm(task, true)">确认执行</el-button>
              <el-button size="small" type="danger" :icon="Close" @click="handleConfirm(task, false)">取消任务</el-button>
            </div>
          </div>

          <div v-if="task.task_result" class="task-result-preview">{{ resultPreview(task) }}</div>

          <div class="task-actions">
            <el-button size="small" text type="primary" :icon="View" @click="openDetail(task)">查看详情</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else-if="!loading" description="暂无任务，点击右上角新建" />
    </div>

    <!-- 新建任务弹窗 -->
    <el-dialog v-model="createVisible" append-to-body width="660px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">新建 Agent 任务</div>
          <div class="dialog-head-sub">选择任务类型并关联知识库文档，系统将自动检索、生成并等待人工确认</div>
        </div>
      </template>

      <el-form label-position="top" class="create-form">
        <div class="form-section-title">任务类型</div>
        <div class="task-type-grid">
          <div
            v-for="t in taskTypeOptions"
            :key="t.value"
            class="task-type-card"
            :class="{ active: createForm.task_type === t.value }"
            @click="createForm.task_type = t.value as 'weekly_report' | 'doc_compare' | 'write_plan'"
          >
            <div class="tt-head">
              <span class="tt-icon" :class="'tt-icon-' + t.value">
                <el-icon><component :is="t.icon" /></el-icon>
              </span>
              <span class="tt-name">{{ t.label }}</span>
            </div>
            <div class="tt-desc">{{ t.desc }}</div>
          </div>
        </div>

        <div class="form-section-title">关联文档（多选）</div>
        <el-select
          v-model="createForm.doc_ids"
          multiple
          filterable
          collapse-tags
          placeholder="选择已解析成功的文档"
          class="doc-select"
        >
          <el-option
            v-for="d in docOptions"
            :key="d.id"
            :label="`${d.doc_name} (v${d.version_no})`"
            :value="d.id"
          />
        </el-select>

        <div class="form-section-title">补充参数（可选）</div>
        <el-input
          v-model="createForm.param_text"
          type="textarea"
          :rows="2"
          placeholder="如：周报周期、对比关注点、方案要求等"
        />

        <div class="form-section-title">生成模型（可选，不选择使用默认）</div>
        <el-select
          v-model="selectedProviderId"
          placeholder="默认模型"
          clearable
          class="doc-select"
        >
          <el-option
            v-for="p in llmStatus?.providers || []"
            :key="p.id"
            :label="`${p.name} · ${p.model}`"
            :value="p.id"
          />
        </el-select>

        <div class="form-section-title">编排引擎</div>
        <div class="engine-option">
          <el-radio-group v-model="createForm.graph_engine" class="engine-radio-group">
            <el-radio value="classic">经典模式</el-radio>
            <el-radio value="langgraph">LangGraph 工作流</el-radio>
            <el-radio value="canvas">画布编排</el-radio>
          </el-radio-group>
          <span class="engine-hint" v-if="createForm.graph_engine === 'canvas'">
            将按「工作流编排」画布中保存的节点与连线顺序执行，trace 逐节点回显
          </span>
          <span class="engine-hint" v-else>
            LangGraph 工作流将以「规划 → 检索 → 生成 → 反思 → 精修」的多节点流程编排，并在详情中展示节点轨迹
          </span>
        </div>

        <div v-if="createForm.graph_engine === 'canvas'" class="canvas-pending-tip">
          <el-icon><Connection /></el-icon>
          <span>已关联画布编排（{{ pendingCanvasJson ? '节点数据就绪，可在画布中继续调整' : '尚未生成画布，请先打开「工作流编排」' }}）。提交后任务按画布执行。</span>
        </div>

        <div class="form-section-title">检索方式</div>
        <div class="web-search-option">
          <el-switch
            v-model="createWebSearch"
            active-text="联网检索"
            inactive-text="仅本地知识库"
            inline-prompt
          />
          <span class="web-search-hint">开启后检索阶段同步融合实时网络结果，提升时效性</span>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建任务</el-button>
      </template>
    </el-dialog>

    <!-- 工作流编排画布弹窗 -->
    <el-dialog
      v-model="canvasVisible"
      append-to-body
      width="92%"
      class="canvas-dialog"
      :show-close="false"
    >
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">工作流编排画布</div>
          <div class="dialog-head-sub">拖拽编排 Agent 工作流：添加节点 → 拖线连接 → 双击编辑参数 → 保存模板或直接创建任务</div>
        </div>
      </template>
      <WorkflowCanvasBuilder
        v-if="canvasVisible"
        @create="handleCanvasCreate"
        @close="canvasVisible = false"
      />
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" append-to-body :title="detailTask ? `${displayType(detailTask)} #${detailTask.task_id}` : ''" width="680px" class="task-detail-dialog">
      <template v-if="detailTask">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="任务号">{{ detailTask.task_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag(detailTask)" size="small" class="status-tag">{{ statusLabel(detailTask) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ displayTime(detailTask) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detailTask.finish_time || '-' }}</el-descriptions-item>
          <el-descriptions-item label="人工确认">
            <el-tag :type="confirmStatus(detailTask).type" size="small">{{ confirmStatus(detailTask).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="`关联文档（${detailTask.selected_doc_ids?.length || 0}）`">
            {{ docNameOf(detailTask) }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="paramSummary(detailTask)" class="detail-block">
          <div class="detail-title">补充参数</div>
          <div class="param-box">{{ paramSummary(detailTask) }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-title">
            <el-icon><Share /></el-icon> 工作流可视化
            <el-tag v-if="isLangGraph(detailTask)" size="small" effect="plain" class="engine-tag">LangGraph</el-tag>
            <el-tag v-else size="small" effect="plain" class="engine-tag">经典流程</el-tag>
            <span class="flow-legend"><i class="legend-dot ok"></i>完成 <i class="legend-dot running"></i>执行中 <i class="legend-dot pending"></i>待执行 <i class="legend-dot error"></i>失败</span>
          </div>
          <div class="flow-canvas">
            <template v-for="(node, ni) in flowNodes(detailTask)" :key="node.key">
              <div
                class="flow-node"
                :class="['flow-' + node.status, { active: detailFlowActive === node.key }]"
                @click="selectFlowNode(node.key)"
              >
                <div class="flow-node-icon">
                  <el-icon v-if="node.status === 'ok'"><Check /></el-icon>
                  <el-icon v-else-if="node.status === 'error'"><Close /></el-icon>
                  <el-icon v-else><Timer /></el-icon>
                </div>
                <div class="flow-node-name">{{ node.name }}</div>
                <div v-if="node.cost_ms !== undefined" class="flow-node-cost">{{ node.cost_ms }}ms</div>
                <div class="flow-node-status">{{ flowStatusLabel(node.status) }}</div>
              </div>
              <div
                v-if="ni < flowNodes(detailTask).length - 1"
                class="flow-link"
                :class="{ done: flowNodes(detailTask)[ni + 1].status === 'ok' }"
              >
                <span class="flow-link-line"></span>
                <span class="flow-link-arrow"></span>
              </div>
            </template>
          </div>
          <div v-if="detailFlowNode" class="flow-detail-panel">
            <div class="flow-detail-head">
              <span class="flow-detail-name">{{ detailFlowNode.name }}</span>
              <el-tag size="small" :type="flowStatusTag(detailFlowNode.status)" class="status-tag">{{ flowStatusLabel(detailFlowNode.status) }}</el-tag>
              <span v-if="detailFlowNode.cost_ms !== undefined" class="flow-detail-cost">耗时 {{ detailFlowNode.cost_ms }}ms</span>
            </div>
            <div class="flow-detail-summary">{{ detailFlowNode.summary || detailFlowNode.brief || '（无摘要）' }}</div>
          </div>
        </div>

        <div v-if="detailTask.error_msg" class="detail-block">
          <div class="detail-title error-title">
            <el-icon><Close /></el-icon> 错误信息
          </div>
          <div class="error-box">{{ detailTask.error_msg }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-title chunk-toggle" @click="detailChunkExpanded = !detailChunkExpanded">
            <el-icon><Timer /></el-icon> 检索片段（{{ detailTask.retrieval_chunks?.length || 0 }}）
            <el-icon class="chunk-arrow" :class="{ rotated: !detailChunkExpanded }"><ArrowDown /></el-icon>
          </div>
          <div v-show="detailChunkExpanded" class="chunk-body">
            <div v-if="detailTask.retrieval_chunks?.length" class="chunk-list">
              <div v-for="(chunk, i) in detailTask.retrieval_chunks" :key="chunk.chunk_id" class="chunk-item">
                <div class="chunk-head">
                  <span class="chunk-no">{{ i + 1 }}</span>
                  <span class="chunk-meta">文档 #{{ chunk.doc_id }}</span>
                  <span v-if="chunk.page_no" class="chunk-meta">第 {{ chunk.page_no }} 页</span>
                  <span v-if="chunk.sheet_name" class="chunk-meta">{{ chunk.sheet_name }}</span>
                  <span v-if="chunk.score !== undefined" class="chunk-meta">相关度 {{ chunk.score.toFixed(3) }}</span>
                </div>
                <div class="chunk-text">{{ chunk.text || '(无内容)' }}</div>
              </div>
            </div>
            <el-empty v-else description="暂无检索片段" :image-size="60" />
          </div>
        </div>

        <div v-if="detailTask.web_sources?.length" class="detail-block">
          <div class="detail-title">
            <el-icon><Tickets /></el-icon> 网络来源（{{ detailTask.web_sources.length }}）
          </div>
          <div class="web-source-list">
            <div v-for="(src, si) in detailTask.web_sources" :key="si" class="web-source-item">
              <a class="web-source-link" :href="src.url" target="_blank" rel="noopener noreferrer">{{ src.title }}</a>
              <div v-if="src.snippet" class="web-source-snippet">{{ src.snippet }}</div>
            </div>
          </div>
        </div>

        <div v-if="detailTask.workflow_trace?.length" class="detail-block">
          <div class="detail-title">
            <el-icon><Share /></el-icon> 工作流轨迹（LangGraph，{{ detailTask.workflow_trace.length }} 节点）
          </div>
          <div class="wf-trace">
            <div v-for="(step, si) in detailTask.workflow_trace" :key="si" class="wf-step">
              <div class="wf-step-main">
                <span class="wf-step-no">{{ si + 1 }}</span>
                <span class="wf-step-name">{{ step.name }}</span>
                <span class="wf-step-status">{{ step.status }}</span>
                <span v-if="step.cost_ms" class="wf-step-cost">{{ step.cost_ms }}ms</span>
              </div>
              <div v-if="step.summary" class="wf-step-summary">{{ step.summary }}</div>
            </div>
          </div>
        </div>

        <div class="detail-block">
          <div class="detail-title">任务结果</div>
          <template v-if="detailTask.task_result">
            <pre class="result-box">{{ renderResult(detailTask.task_result) }}</pre>
          </template>
          <div v-else class="result-placeholder">
            <el-icon><Document /></el-icon>
            <span>{{ resultPlaceholder(detailTask) }}</span>
          </div>
        </div>

        <div v-if="detailTask.status === 'waiting_confirm'" class="detail-confirm">
          <el-button type="success" :icon="Check" @click="handleConfirm(detailTask, true)">确认执行</el-button>
          <el-button type="danger" :icon="Close" @click="handleConfirm(detailTask, false)">取消任务</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.auto-refresh-tip {
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-bottom: 16px;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.task-card {
  position: relative;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.8));
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-radius: var(--ks-card-radius);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.8);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow 0.28s cubic-bezier(0.22, 1, 0.36, 1), transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.28s ease;
  animation: ks-fade-in 0.35s ease both;
}

.task-card:hover {
  transform: translateY(-5px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow:
    0 18px 40px rgba(15, 23, 42, 0.1),
    0 8px 22px rgba(37, 99, 235, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.96);
}

.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.2px;
  line-height: 1.35;
  color: var(--ks-text-title);
}

.task-type-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  color: var(--ks-primary);
  font-size: 15px;
  flex-shrink: 0;
  transition: transform 0.28s ease, color 0.28s ease, box-shadow 0.28s ease, background 0.28s ease;
}

.task-card:hover .task-type-icon {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  transform: rotate(-8deg) scale(1.1);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
}

.task-meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  line-height: 1.6;
  color: #5b6b84;
}

.task-chunks {
  font-size: 13px;
}

.task-confirm {
  background: var(--ks-warning-bg);
  border: 1px solid #fde68a;
  border-radius: 10px;
  padding: 10px 12px;
}

.confirm-hint {
  font-size: 13px;
  color: #b45309;
  display: block;
  margin-bottom: 8px;
}

.confirm-actions {
  display: flex;
  gap: 8px;
}

.task-actions {
  border-top: 1px solid #f1f5f9;
  padding-top: 8px;
}

/* 状态标签：语义颜色加深、文字与背景对比度达标、胶囊造型 */
:deep(.status-tag) {
  border-radius: 999px;
  padding: 0 10px;
  height: 22px;
  line-height: 20px;
  font-weight: 600;
  letter-spacing: 0.3px;
  border: 1px solid transparent;
}

:deep(.status-tag.el-tag--primary) {
  color: #1d4ed8;
  background: #dbeafe;
  border-color: #bfdbfe;
}

:deep(.status-tag.el-tag--warning) {
  color: #b45309;
  background: #fef3c7;
  border-color: #fde68a;
}

:deep(.status-tag.el-tag--success) {
  color: #047857;
  background: #d1fae5;
  border-color: #a7f3d0;
}

:deep(.status-tag.el-tag--danger) {
  color: #b91c1c;
  background: #fee2e2;
  border-color: #fecaca;
}

:deep(.status-tag.el-tag--info) {
  color: #475569;
  background: #e2e8f0;
  border-color: #cbd5e1;
}

/* ---------------- 新建任务弹窗 ---------------- */
.dialog-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-head-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--ks-text-title);
}

.dialog-head-sub {
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-title);
  margin: 14px 0 8px;
}

.form-section-title:first-child {
  margin-top: 0;
}

.task-type-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.task-type-card {
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  padding: 14px 14px 12px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.task-type-card:hover {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.1);
  transform: translateY(-3px);
}

.task-type-card.active {
  border-color: var(--ks-primary);
  background: linear-gradient(180deg, #f5f9ff 0%, #ffffff 100%);
  box-shadow: 0 0 0 1px var(--ks-primary), 0 8px 22px rgba(37, 99, 235, 0.2);
}

.tt-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tt-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  transition: color 0.25s ease, background 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
}

.task-type-card:hover .tt-icon {
  transform: translateY(-2px);
}

.task-type-card.active .tt-icon {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  border-color: transparent;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35);
}

.tt-icon-weekly_report {
  background: linear-gradient(135deg, #fef3c7, #ffedd5);
  color: #d97706;
  border-color: rgba(245, 158, 11, 0.25);
}

.tt-icon-doc_compare {
  background: linear-gradient(135deg, #d1fae5, #ccfbf1);
  color: #059669;
  border-color: rgba(16, 185, 129, 0.25);
}

.tt-icon-write_plan {
  background: linear-gradient(135deg, #e0e7ff, #ede9fe);
  color: #6366f1;
  border-color: rgba(99, 102, 241, 0.25);
}

.task-type-card.active .tt-icon-weekly_report {
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 6px 16px rgba(245, 158, 11, 0.35);
}

.task-type-card.active .tt-icon-doc_compare {
  background: linear-gradient(135deg, #10b981, #0d9488);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.35);
}

.task-type-card.active .tt-icon-write_plan {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
}

.tt-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-title);
  line-height: 1.4;
}

.tt-desc {
  font-size: 12px;
  color: #5b6b84;
  line-height: 1.55;
  min-height: 18px;
}

.doc-select {
  width: 100%;
}

.doc-select-hint {
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-top: 6px;
}

/* 新建弹窗内下拉弹层：避免被弹窗裁剪，并限制最大高度可滚动 */
.create-form :deep(.el-select__popper) {
  z-index: 3100 !important;
}

:deep(.ks-agent-select-popper) {
  max-height: 300px;
}

:deep(.ks-agent-select-popper .el-select-dropdown__list) {
  max-height: 280px;
  overflow-y: auto;
}

.param-box {
  padding: 10px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ks-text-body);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 新建弹窗联网检索开关 */
.engine-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: linear-gradient(180deg, #f5f9ff, #f8fafc);
  border: 1px solid #e2e8f0;
}

.engine-radio-group {
  flex-shrink: 0;
}

.engine-hint {
  font-size: 12px;
  color: var(--ks-text-secondary);
  line-height: 1.6;
}

.engine-tag {
  flex-shrink: 0;
  font-size: 11px;
  letter-spacing: 0.3px;
}

/* 工作流可视化（展示型流程图） */
.flow-legend {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 6px;
}

.legend-dot.ok { background: #10b981; }
.legend-dot.running { background: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18); }
.legend-dot.pending { background: #cbd5e1; }
.legend-dot.error { background: #ef4444; }

.flow-canvas {
  display: flex;
  align-items: stretch;
  gap: 6px;
  flex-wrap: wrap;
  padding: 14px 8px 6px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fbff, #f6f8fc);
}

.flow-node {
  flex: 0 0 auto;
  min-width: 88px;
  max-width: 132px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.flow-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}

.flow-node.active {
  border-color: rgba(37, 99, 235, 0.55);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.flow-node-icon {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
  background: #cbd5e1;
}

.flow-node-name {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  text-align: center;
  line-height: 1.3;
}

.flow-node-cost {
  font-size: 10px;
  color: #94a3b8;
}

.flow-node-status {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 999px;
  font-weight: 600;
  color: #64748b;
  background: #f1f5f9;
}

/* 节点状态配色 */
.flow-node.flow-ok .flow-node-icon { background: linear-gradient(135deg, #10b981, #059669); }
.flow-node.flow-ok .flow-node-status { color: #047857; background: rgba(16, 185, 129, 0.14); }
.flow-node.flow-running .flow-node-icon { background: linear-gradient(135deg, #3b82f6, #2563eb); animation: flow-pulse 1.6s ease-in-out infinite; }
.flow-node.flow-running .flow-node-status { color: #1d4ed8; background: rgba(59, 130, 246, 0.14); }
.flow-node.flow-error .flow-node-icon { background: linear-gradient(135deg, #ef4444, #dc2626); }
.flow-node.flow-error .flow-node-status { color: #b91c1c; background: rgba(239, 68, 68, 0.14); }

@keyframes flow-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.35); }
  50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.08); }
}

/* 节点连线 */
.flow-link {
  flex: 1 1 18px;
  min-width: 18px;
  display: flex;
  align-items: center;
  position: relative;
  padding-bottom: 18px;
}

.flow-link-line {
  flex: 1;
  height: 2px;
  background: #dbe4f0;
  border-radius: 2px;
}

.flow-link.done .flow-link-line {
  background: linear-gradient(90deg, #10b981, #34d399);
}

.flow-link-arrow {
  position: absolute;
  right: -2px;
  top: calc(50% - 10px);
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 6px solid #cbd5e1;
}

.flow-link.done .flow-link-arrow {
  border-left-color: #34d399;
}

/* 选中节点摘要面板 */
.flow-detail-panel {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.18);
  background: linear-gradient(180deg, #f0f6ff, #f8fafc);
}

.flow-detail-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.flow-detail-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.flow-detail-cost {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.flow-detail-summary {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
  word-break: break-word;
}

/* 列表卡片迷你工作流 */
.task-flow-mini {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.03);
  border: 1px dashed rgba(37, 99, 235, 0.16);
}

.mini-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.mini-dot.mini-ok { background: #10b981; }
.mini-dot.mini-running { background: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }
.mini-dot.mini-pending { background: #cbd5e1; }
.mini-dot.mini-error { background: #ef4444; }

.mini-line {
  flex: 1;
  min-width: 6px;
  height: 2px;
  background: #dbe4f0;
  border-radius: 2px;
}

.mini-label {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8;
  font-weight: 500;
  white-space: nowrap;
}

/* 列表卡片结果摘要 */
.task-result-preview {
  font-size: 12px;
  color: #5b6b84;
  line-height: 1.55;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.05);
  border-left: 3px solid rgba(37, 99, 235, 0.35);
  word-break: break-word;
}

/* 工作流轨迹时间线 */
.wf-trace {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
}

.wf-step {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f8fafc;
}

.wf-step-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.wf-step-no {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  color: #fff;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.wf-step-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.wf-step-status {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-weight: 600;
}

.wf-step-cost {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.wf-step-summary {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #5b6b84;
  word-break: break-word;
}

/* 新建弹窗联网检索开关 */
.web-search-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: linear-gradient(180deg, #f5f9ff, #f8fafc);
  border: 1px solid #e2e8f0;
}

.web-search-hint {
  font-size: 12px;
  color: var(--ks-text-secondary);
  line-height: 1.6;
}

/* 详情弹窗网络来源 */
.web-source-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.web-source-item {
  padding: 8px 12px;
  border-left: 3px solid rgba(37, 99, 235, 0.35);
  border-radius: 0 8px 8px 0;
  background: rgba(37, 99, 235, 0.05);
}

.web-source-link {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
  text-decoration: none;
  word-break: break-all;
}

.web-source-link:hover {
  color: #2563eb;
  text-decoration: underline;
}

.web-source-snippet {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #5b6b84;
  word-break: break-word;
}

/* 详情弹窗键值对齐：label 固定列宽右对齐、muted 色，值主文本色加粗 */
:deep(.task-detail-dialog .el-descriptions__label) {
  display: inline-block;
  width: 124px;
  min-width: 124px;
  text-align: right;
  color: #64748b;
  font-weight: 500;
  background: #f8fafc;
  padding: 10px 12px;
}

:deep(.task-detail-dialog .el-descriptions__content) {
  color: #1e293b;
  font-weight: 500;
  font-size: 13px;
  line-height: 1.6;
  padding: 10px 12px;
}

:deep(.task-detail-dialog .el-descriptions__cell) {
  border-color: #e2e8f0;
}

/* 空态占位统一柔和样式（检索片段为空等场景） */
:deep(.task-detail-dialog .el-empty__image svg) {
  opacity: 0.55;
}

:deep(.task-detail-dialog .el-empty__description) {
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.6;
}

.detail-block {
  margin-top: 18px;
}

.detail-title {
  position: relative;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.1px;
  color: var(--ks-text-title);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 7px;
}

.detail-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #3b82f6, #6366f1);
}

.error-title {
  color: #dc2626;
}

.error-title::before {
  background: linear-gradient(180deg, #ef4444, #f97316);
}

.error-box {
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.22);
  color: #dc2626;
  font-size: 13px;
  line-height: 1.7;
  word-break: break-all;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.chunk-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f8fafc;
}

.chunk-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.chunk-no {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--ks-primary);
  color: #fff;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.chunk-meta {
  font-size: 12px;
  color: #5b6b84;
}

.chunk-text {
  position: relative;
  font-size: 14px;
  line-height: 1.75;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  cursor: pointer;
  border-radius: 6px;
  padding: 3px 4px;
  transition: background 0.2s ease;
}

.chunk-text:hover {
  background: rgba(37, 99, 235, 0.05);
}

/* 正文超过 3 行默认省略，点击展开全文 */
.chunk-text-collapsed {
  max-height: 73.5px; /* 14px * 1.75 * 3 */
  overflow: hidden;
}

.chunk-text-collapsed::after {
  content: '展开全文';
  position: absolute;
  right: 8px;
  bottom: 3px;
  font-size: 11px;
  font-weight: 600;
  color: #2563eb;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0), #f8fafc 62%);
  padding: 20px 0 0 14px;
  pointer-events: none;
}

.result-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.8;
  letter-spacing: 0.01em;
  color: #334155;
  max-height: 380px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  margin: 0;
}

/* 任务结果占位：柔和提示，避免空白区域 */
.result-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 12px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(241, 245, 249, 0.6));
  border: 1px dashed #cbd5e1;
  color: #8ba0b8;
  font-size: 13px;
  line-height: 1.6;
  text-align: center;
  word-break: break-all;
}

.result-placeholder .el-icon {
  font-size: 17px;
  color: #94a3b8;
  flex-shrink: 0;
}

/* 检索片段折叠交互（默认展开） */
.chunk-toggle {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s ease;
}

.chunk-toggle:hover {
  color: var(--ks-primary);
}

.chunk-arrow {
  margin-left: auto;
  font-size: 14px;
  color: var(--ks-text-secondary);
  transition: transform 0.25s ease, color 0.25s ease;
}

.chunk-toggle:hover .chunk-arrow {
  color: var(--ks-primary);
}

.chunk-arrow.rotated {
  transform: rotate(-90deg);
}

.detail-confirm {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
/* ---------------- 移动端适配 ---------------- */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .header-actions {
    flex-wrap: wrap;
    width: 100%;
  }

  .header-actions .el-button {
    flex: 1;
    margin-left: 0;
  }

  .task-grid {
    grid-template-columns: 1fr !important;
  }
}
.canvas-pending-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 2px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--ks-primary-soft, rgba(37, 99, 235, 0.08));
  color: var(--ks-text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.5;
}
.canvas-pending-tip .el-icon { color: var(--ks-primary, #2563eb); flex-shrink: 0; }
.canvas-dialog { max-width: 1320px; }
@media (max-width: 760px) {
  .canvas-dialog { width: 98%; }
}
</style>
