<script setup lang="ts">
/**
 * 拖拽式工作流画布编排器
 * - 从左侧面板点击/拖拽添加节点（input/plan/retrieve/generate/reflect/refine/output）
 * - 节点在画布内拖拽移动；从节点右侧端口拖出连线到目标节点创建依赖
 * - 双击节点编辑参数；点击连线选中后按 Delete 或工具栏删除
 * - 保存/更新模板（后端 /api/agent/templates）；加载已有模板回填画布
 * - 「用画布创建任务」将 canvas_json 交给父组件发起任务
 */
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete, Download, FolderOpened, Brush, CaretRight, Close, Rank } from '@element-plus/icons-vue'
import { listAgentTemplates, createAgentTemplate, updateAgentTemplate } from '@/api/agent'
import { getLlmStatus, type LlmStatus } from '@/api/chat'
import type { CanvasNode, CanvasEdge, AgentTemplateItem } from '@/types'

const emit = defineEmits<{
  (e: 'create', payload: { canvasJson: string; taskType: string }): void
  (e: 'close'): void
}>()

/* ---------------- 节点类型元数据 ---------------- */
interface NodeTypeMeta {
  type: CanvasNode['type']
  name: string
  color: string
  desc: string
  defaultConfig: Record<string, unknown>
}

const NODE_TYPES: NodeTypeMeta[] = [
  { type: 'input', name: '任务输入', color: '#64748b', desc: '任务目标与补充说明', defaultConfig: { prompt: '' } },
  { type: 'plan', name: '任务规划', color: '#2563eb', desc: 'LLM 生成执行计划', defaultConfig: { prompt: '' } },
  { type: 'retrieve', name: '知识检索', color: '#10b981', desc: '向量检索知识片段', defaultConfig: { query: '', top_k: 8 } },
  { type: 'generate', name: '内容生成', color: '#f59e0b', desc: 'LLM 基于上下文生成', defaultConfig: { prompt: '', temperature: 0.7, max_tokens: 2000, model_provider_id: null } },
  { type: 'reflect', name: '质量反思', color: '#8b5cf6', desc: 'LLM 评审与改进建议', defaultConfig: { prompt: '' } },
  { type: 'refine', name: '精修定稿', color: '#ec4899', desc: 'LLM 修订最终版本', defaultConfig: { prompt: '' } },
  { type: 'output', name: '结果输出', color: '#0d9488', desc: '汇总输出最终结果', defaultConfig: {} },
]

const NODE_META: Record<string, NodeTypeMeta> = Object.fromEntries(NODE_TYPES.map((t) => [t.type, t]))

const taskTypeOptions = [
  { value: 'weekly_report', label: '周报生成' },
  { value: 'doc_compare', label: '文档对比' },
  { value: 'write_plan', label: '方案撰写' },
]

/* ---------------- 画布状态 ---------------- */
const nodes = ref<CanvasNode[]>([])
const edges = ref<CanvasEdge[]>([])
const selectedNodeId = ref<string>('')
const selectedEdgeId = ref<string>('')
const templateName = ref('')
const taskType = ref('weekly_report')
const editingTemplateId = ref<number | null>(null)
const dirty = ref(false)

const templates = ref<AgentTemplateItem[]>([])
const llmStatus = ref<LlmStatus | null>(null)
const loadingTemplates = ref(false)
const saving = ref(false)

/* 画布尺寸与交互 */
const canvasEl = ref<HTMLElement | null>(null)
const canvasW = ref(960)
const canvasH = ref(520)
const NODE_W = 150
const NODE_H = 58

/* 拖拽节点 */
const dragState = ref<{ nodeId: string; offsetX: number; offsetY: number } | null>(null)

/* 拖线状态 */
const linkState = reactive<{
  active: boolean
  sourceNodeId: string
  fromX: number
  fromY: number
  toX: number
  toY: number
}>({ active: false, sourceNodeId: '', fromX: 0, fromY: 0, toX: 0, toY: 0 })

/* 节点参数编辑 */
const editVisible = ref(false)
const editingNode = ref<CanvasNode | null>(null)
const editForm = reactive<Record<string, unknown>>({})

let uid = 0
function genId(prefix: string): string {
  uid += 1
  return `${prefix}_${Date.now().toString(36)}_${uid}`
}

function ensureNode(node: CanvasNode) {
  return {
    ...node,
    config: { ...NODE_META[node.type]?.defaultConfig, ...(node.config || {}) },
  }
}

function ensureDefaults() {
  nodes.value = nodes.value.map(ensureNode)
}

/* ---------------- 节点添加 ---------------- */
function addNode(type: CanvasNode['type'], x?: number, y?: number) {
  const meta = NODE_META[type]
  const id = genId('n')
  const node: CanvasNode = {
    id,
    type,
    name: meta?.name || type,
    x: x ?? Math.min(40 + Math.random() * (canvasW.value - NODE_W - 80), canvasW.value - NODE_W - 40),
    y: y ?? Math.min(40 + Math.random() * (canvasH.value - NODE_H - 80), canvasH.value - NODE_H - 40),
    config: { ...(meta?.defaultConfig || {}) },
  }
  nodes.value.push(node)
  selectedNodeId.value = id
  dirty.value = true
}

/* HTML5 拖拽添加：从面板拖入画布 */
function onPanelDragStart(e: DragEvent, type: CanvasNode['type']) {
  e.dataTransfer?.setData('text/plain', type)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}
function onCanvasDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}
function onCanvasDrop(e: DragEvent) {
  e.preventDefault()
  const type = e.dataTransfer?.getData('text/plain') as CanvasNode['type']
  if (!type || !NODE_META[type]) return
  const rect = canvasEl.value?.getBoundingClientRect()
  if (!rect) return
  const x = e.clientX - rect.left - NODE_W / 2
  const y = e.clientY - rect.top - NODE_H / 2
  addNode(type, Math.max(8, x), Math.max(8, y))
}

/* ---------------- 节点拖拽移动 ---------------- */
function onNodeMouseDown(e: MouseEvent, node: CanvasNode) {
  if ((e.target as HTMLElement).closest('.port')) return
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  selectedNodeId.value = node.id
  selectedEdgeId.value = ''
  dragState.value = { nodeId: node.id, offsetX: e.clientX - node.x, offsetY: e.clientY - node.y }
}

function onGlobalMouseMove(e: MouseEvent) {
  const ds = dragState.value
  if (ds?.nodeId) {
    const n = nodes.value.find((nd) => nd.id === ds.nodeId)
    if (n) {
      n.x = Math.max(0, Math.min(e.clientX - ds.offsetX, canvasW.value - NODE_W))
      n.y = Math.max(0, Math.min(e.clientY - ds.offsetY, canvasH.value - NODE_H))
      dirty.value = true
    }
    return
  }
  if (linkState.active) {
    linkState.toX = e.clientX
    linkState.toY = e.clientY
  }
}

function onGlobalMouseUp(e: MouseEvent) {
  if (dragState.value?.nodeId) {
    dragState.value = null
    return
  }
  if (linkState.active) {
    finishLink(e.clientX, e.clientY)
  }
}

/* ---------------- 端口连线 ---------------- */
function nodeCenter(node: CanvasNode): { x: number; y: number } {
  return { x: node.x + NODE_W / 2, y: node.y + NODE_H / 2 }
}

function onPortMouseDown(e: MouseEvent, node: CanvasNode) {
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  const center = nodeCenter(node)
  linkState.active = true
  linkState.sourceNodeId = node.id
  linkState.fromX = center.x + NODE_W / 2
  linkState.fromY = center.y
  linkState.toX = center.x + NODE_W / 2
  linkState.toY = center.y
}

function hitTestNode(px: number, py: number): CanvasNode | null {
  const rect = canvasEl.value?.getBoundingClientRect()
  if (!rect) return null
  const cx = px - rect.left
  const cy = py - rect.top
  for (const n of nodes.value) {
    if (cx >= n.x && cx <= n.x + NODE_W && cy >= n.y && cy <= n.y + NODE_H) return n
  }
  return null
}

function finishLink(mx: number, my: number) {
  const target = hitTestNode(mx, my)
  linkState.active = false
  if (!target) return
  if (target.id === linkState.sourceNodeId) {
    ElMessage.warning('不能连接节点自身')
    return
  }
  if (edges.value.some((ed) => ed.source === linkState.sourceNodeId && ed.target === target.id)) {
    ElMessage.warning('该连线已存在')
    return
  }
  const id = genId('e')
  edges.value.push({ id, source: linkState.sourceNodeId, target: target.id })
  dirty.value = true
  ElMessage.success('连线已创建')
}

/* ---------------- 连线路径 ---------------- */
function edgePath(edge: CanvasEdge): string {
  const s = nodes.value.find((n) => n.id === edge.source)
  const t = nodes.value.find((n) => n.id === edge.target)
  if (!s || !t) return ''
  const sx = s.x + NODE_W
  const sy = s.y + NODE_H / 2
  const tx = t.x
  const ty = t.y + NODE_H / 2
  const dx = Math.max(40, Math.abs(tx - sx) / 2)
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`
}

function tempPath(): string {
  if (!linkState.active) return ''
  const sx = linkState.fromX
  const sy = linkState.fromY
  const rect = canvasEl.value?.getBoundingClientRect()
  if (!rect) return ''
  const tx = linkState.toX - rect.left
  const ty = linkState.toY - rect.top
  const dx = Math.max(40, Math.abs(tx - sx) / 2)
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`
}

function selectEdge(edgeId: string) {
  selectedEdgeId.value = edgeId
  selectedNodeId.value = ''
}

function deleteSelected() {
  if (selectedEdgeId.value) {
    edges.value = edges.value.filter((ed) => ed.id !== selectedEdgeId.value)
    selectedEdgeId.value = ''
    dirty.value = true
    return true
  }
  if (selectedNodeId.value) {
    const nid = selectedNodeId.value
    nodes.value = nodes.value.filter((n) => n.id !== nid)
    edges.value = edges.value.filter((ed) => ed.source !== nid && ed.target !== nid)
    selectedNodeId.value = ''
    dirty.value = true
    return true
  }
  return false
}

/* ---------------- 节点参数编辑 ---------------- */
function openEdit(node: CanvasNode) {
  editingNode.value = node
  Object.keys(editForm).forEach((k) => delete editForm[k])
  Object.entries(node.config || {}).forEach(([k, v]) => {
    editForm[k] = v as never
  })
  editVisible.value = true
}

function saveEdit() {
  if (!editingNode.value) return
  editingNode.value.config = { ...editForm }
  editVisible.value = false
  dirty.value = true
  ElMessage.success('节点参数已更新')
}

function editFieldLabel(key: string): string {
  const labels: Record<string, string> = {
    prompt: '节点指令',
    query: '检索问题（留空则用上游摘要）',
    top_k: '检索数量',
    temperature: '温度（0-2）',
    max_tokens: '最大输出长度',
    model_provider_id: '生成模型',
  }
  return labels[key] || key
}

function isGenerateNode(node: CanvasNode): boolean {
  return node.type === 'generate'
}

/* ---------------- 模板 ---------------- */
async function loadTemplates() {
  loadingTemplates.value = true
  try {
    templates.value = await listAgentTemplates()
  } catch {
    templates.value = []
  } finally {
    loadingTemplates.value = false
  }
}

function applyTemplate(tpl: AgentTemplateItem) {
  if (!tpl.canvas_json) {
    ElMessage.warning('该模板没有画布数据')
    return
  }
  try {
    const parsed = JSON.parse(tpl.canvas_json)
    nodes.value = (parsed.nodes || []).map(ensureNode)
    edges.value = parsed.edges || []
    templateName.value = tpl.template_name
    taskType.value = tpl.task_type || 'weekly_report'
    editingTemplateId.value = tpl.id
    dirty.value = false
    selectedNodeId.value = ''
    selectedEdgeId.value = ''
    ElMessage.success(`已加载模板「${tpl.template_name}」`)
  } catch (err) {
    ElMessage.error(`模板画布解析失败：${String(err)}`)
  }
}

async function saveTemplate() {
  if (!nodes.value.length) {
    ElMessage.warning('画布为空，请先添加节点')
    return
  }
  if (!templateName.value.trim()) {
    ElMessage.warning('请填写模板名称')
    return
  }
  const payload = {
    template_name: templateName.value.trim(),
    task_type: taskType.value,
    canvas_json: JSON.stringify({ nodes: nodes.value, edges: edges.value }),
  }
  saving.value = true
  try {
    if (editingTemplateId.value) {
      await updateAgentTemplate(editingTemplateId.value, payload)
      ElMessage.success('模板已更新')
    } else {
      const created = await createAgentTemplate(payload)
      editingTemplateId.value = created.id
      ElMessage.success('模板已保存')
    }
    dirty.value = false
    await loadTemplates()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function clearCanvas() {
  if (nodes.value.length && !window.confirm('确定清空当前画布吗？')) return
  nodes.value = []
  edges.value = []
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  editingTemplateId.value = null
  dirty.value = false
}

function createTaskFromCanvas() {
  if (!nodes.value.length) {
    ElMessage.warning('画布为空，请先添加节点')
    return
  }
  const canvasJson = JSON.stringify({ nodes: nodes.value, edges: edges.value })
  emit('create', { canvasJson, taskType: taskType.value })
}

function presetTemplate(name: string, type: CanvasNode['type'], layout: [number, number][]) {
  nodes.value = layout.map(([x, y], i) => ({
    id: genId('n'),
    type: i === 0 ? 'input' : i === layout.length - 1 ? 'output' : type,
    name: NODE_META[type].name,
    x,
    y,
    config: { ...NODE_META[type].defaultConfig },
  }))
  edges.value = nodes.value.slice(1).map((n, i) => ({
    id: genId('e'),
    source: nodes.value[i].id,
    target: n.id,
  }))
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  editingTemplateId.value = null
  templateName.value = name
  dirty.value = true
}

function loadPreset() {
  presetTemplate('通用检索生成流', 'retrieve', [
    [20, 20],
    [210, 20],
    [400, 20],
    [590, 20],
  ])
}

function loadPresetPlan() {
  const types: CanvasNode['type'][] = ['input', 'plan', 'retrieve', 'generate', 'reflect', 'refine', 'output']
  const xs = [20, 210, 400, 590, 780, 970, 1160]
  const ys = [40, 40, 40, 40, 40, 40, 40]
  nodes.value = types.map((t, i) => ({
    id: genId('n'),
    type: t,
    name: NODE_META[t].name,
    x: xs[i],
    y: ys[i],
    config: { ...NODE_META[t].defaultConfig },
  }))
  edges.value = nodes.value.slice(1).map((n, i) => ({
    id: genId('e'),
    source: nodes.value[i].id,
    target: n.id,
  }))
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  editingTemplateId.value = null
  templateName.value = '规划-检索-生成-反思-精修流'
  dirty.value = true
}

/* ---------------- 画布尺寸自适应 ---------------- */
function measureCanvas() {
  const el = canvasEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  if (rect.width > 60) canvasW.value = Math.max(720, Math.floor(rect.width - 8))
  canvasH.value = Math.max(440, Math.floor(Math.min(rect.height || 520, window.innerHeight - 320)))
}

const statusCount = computed(() => {
  const types = nodes.value.map((n) => n.type)
  return {
    total: nodes.value.length,
    edges: edges.value.length,
    plan: types.filter((t) => ['plan', 'retrieve', 'generate', 'reflect', 'refine'].includes(t)).length,
  }
})

function nodeColor(type: CanvasNode['type']): string {
  return NODE_META[type]?.color || '#64748b'
}

/* 键盘删除选中元素 */
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    if (selectedNodeId.value || selectedEdgeId.value) deleteSelected()
  }
}

onMounted(async () => {
  window.addEventListener('mousemove', onGlobalMouseMove)
  window.addEventListener('mouseup', onGlobalMouseUp)
  window.addEventListener('keydown', onKeyDown)
  measureCanvas()
  loadTemplates()
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
  loadPreset()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onGlobalMouseMove)
  window.removeEventListener('mouseup', onGlobalMouseUp)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div class="wcb-root">
    <!-- 顶栏 -->
    <div class="wcb-header">
      <div class="wcb-header-left">
        <span class="wcb-title"><el-icon><Rank /></el-icon> 工作流编排画布</span>
        <span class="wcb-sub">拖拽节点 → 连线 → 编辑参数 → 保存模板 / 创建任务</span>
      </div>
      <div class="wcb-header-right">
        <el-button size="small" :icon="Brush" @click="loadPreset">预设：检索生成流</el-button>
        <el-button size="small" @click="loadPresetPlan">预设：完整五阶段</el-button>
        <el-button size="small" :icon="Delete" :disabled="!selectedNodeId && !selectedEdgeId" @click="deleteSelected">删除选中</el-button>
        <el-button size="small" @click="clearCanvas">清空</el-button>
        <el-button size="small" type="primary" :icon="Download" :loading="saving" @click="saveTemplate">
          {{ editingTemplateId ? '更新模板' : '保存模板' }}
        </el-button>
      </div>
    </div>

    <div class="wcb-main">
      <!-- 左侧：节点面板 -->
      <div class="wcb-panel">
        <div class="wcb-panel-title">节点库 <span class="wcb-panel-hint">（拖入画布或点击添加）</span></div>
        <div
          v-for="t in NODE_TYPES"
          :key="t.type"
          class="wcb-palette-item"
          draggable="true"
          :style="{ '--node-color': t.color }"
          @dragstart="onPanelDragStart($event, t.type)"
          @click="addNode(t.type)"
        >
          <span class="palette-dot" :style="{ background: t.color }"></span>
          <div class="palette-info">
            <div class="palette-name">{{ t.name }}</div>
            <div class="palette-desc">{{ t.desc }}</div>
          </div>
          <el-icon class="palette-add"><Plus /></el-icon>
        </div>

        <div class="wcb-panel-title wcb-tpl-title">模板</div>
        <el-select
          v-model="editingTemplateId"
          size="small"
          placeholder="加载已有模板"
          clearable
          class="wcb-tpl-select"
          @change="(v: number | null) => { const t = templates.find((x) => x.id === v); if (t) applyTemplate(t) }"
        >
          <el-option
            v-for="t in templates"
            :key="t.id"
            :label="t.template_name"
            :value="t.id"
          >
            <span>{{ t.template_name }}</span>
            <span class="tpl-type">{{ taskTypeOptions.find((o) => o.value === t.task_type)?.label || t.task_type }}</span>
          </el-option>
        </el-select>
        <div class="wcb-tpl-meta">
          <el-input v-model="templateName" size="small" placeholder="模板名称" class="wcb-tpl-name" />
          <el-select v-model="taskType" size="small" class="wcb-tpl-type">
            <el-option v-for="o in taskTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
      </div>

      <!-- 中间：画布 -->
      <div class="wcb-canvas-wrap" ref="canvasEl" @dragover="onCanvasDragOver" @drop="onCanvasDrop">
        <svg class="wcb-svg" :width="canvasW" :height="canvasH">
          <defs>
            <marker id="wcb-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#64748b" />
            </marker>
          </defs>
          <path
            v-for="edge in edges"
            :key="edge.id"
            :d="edgePath(edge)"
            fill="none"
            stroke="#94a3b8"
            :stroke-width="selectedEdgeId === edge.id ? 3 : 2"
            :stroke-dasharray="selectedEdgeId === edge.id ? 'none' : '6 3'"
            marker-end="url(#wcb-arrow)"
            class="wcb-edge"
            @click.stop="selectEdge(edge.id)"
          />
          <path
            v-if="linkState.active"
            :d="tempPath()"
            fill="none"
            stroke="#2563eb"
            stroke-width="2"
            stroke-dasharray="6 4"
            class="wcb-temp-edge"
          />
        </svg>

        <div
          v-for="node in nodes"
          :key="node.id"
          class="wcb-node"
          :class="{ selected: selectedNodeId === node.id }"
          :style="{ left: node.x + 'px', top: node.y + 'px', width: NODE_W + 'px', height: NODE_H + 'px', '--node-color': nodeColor(node.type) }"
          @mousedown="onNodeMouseDown($event, node)"
          @dblclick="openEdit(node)"
        >
          <div class="wcb-node-colorbar"></div>
          <div class="wcb-node-body">
            <span class="wcb-node-icon" :style="{ background: nodeColor(node.type) }">{{ node.name.slice(0, 1) }}</span>
            <div class="wcb-node-info">
              <div class="wcb-node-name">{{ node.name }}</div>
              <div class="wcb-node-type">{{ node.type }}</div>
            </div>
          </div>
          <span
            class="port"
            :title="`从 ${node.name} 拖出连线`"
            :style="{ left: NODE_W - 5 + 'px', top: NODE_H / 2 - 5 + 'px' }"
            @mousedown.stop="onPortMouseDown($event, node)"
          ></span>
        </div>

        <div class="wcb-canvas-tip" v-if="!nodes.length">
          <el-icon><Plus /></el-icon> 从左侧拖入节点，或用预设快速开始
        </div>
      </div>
    </div>

    <!-- 底部操作条 -->
    <div class="wcb-footer">
      <div class="wcb-stats">
        <span>节点 {{ statusCount.total }}</span>
        <span>连线 {{ statusCount.edges }}</span>
        <span>编排节点 {{ statusCount.plan }}</span>
        <span v-if="dirty" class="wcb-dirty">未保存变更</span>
      </div>
      <div class="wcb-footer-actions">
        <el-button size="small" :icon="Close" @click="emit('close')">关闭</el-button>
        <el-button size="small" type="primary" :icon="CaretRight" @click="createTaskFromCanvas">用画布创建任务</el-button>
      </div>
    </div>

    <!-- 节点参数编辑 -->
    <el-dialog v-model="editVisible" append-to-body :title="editingNode ? `编辑节点：${editingNode.name}` : ''" width="460px" class="ks-dialog">
      <el-form label-position="top" v-if="editingNode">
        <template v-for="(v, k) in editingNode.config" :key="k">
          <el-form-item :label="editFieldLabel(k)">
            <el-input
              v-if="k === 'prompt' || k === 'query'"
              v-model="editForm[k] as string"
              type="textarea"
              :rows="k === 'prompt' ? 3 : 2"
            />
            <el-input-number
              v-else-if="k === 'top_k' || k === 'max_tokens'"
              v-model="editForm[k] as number"
              :min="k === 'top_k' ? 1 : 200"
              :max="k === 'top_k' ? 50 : 8000"
            />
            <el-slider
              v-else-if="k === 'temperature'"
              v-model="editForm[k] as number"
              :min="0"
              :max="2"
              :step="0.1"
              show-input
            />
            <el-select
              v-else-if="k === 'model_provider_id'"
              v-model="editForm[k] as number | null"
              clearable
              placeholder="默认模型"
            >
              <el-option v-for="p in llmStatus?.providers || []" :key="p.id" :label="`${p.name} · ${p.model}`" :value="p.id" />
            </el-select>
            <el-input v-else v-model="editForm[k] as string" />
          </el-form-item>
        </template>
        <div v-if="!Object.keys(editingNode.config || {}).length" class="wcb-no-param">该节点无需参数配置</div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存参数</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.wcb-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 520px;
  background: var(--ks-card-bg, #fff);
  border: 1px solid var(--ks-card-border, rgba(15, 23, 42, 0.06));
  border-radius: var(--ks-card-radius-lg, 18px);
  box-shadow: var(--ks-shadow-lg, 0 12px 32px rgba(15, 23, 42, 0.1));
  overflow: hidden;
}

.wcb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(120deg, rgba(6, 13, 31, 0.92), rgba(11, 23, 48, 0.9));
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}
.wcb-header-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wcb-title { display: inline-flex; align-items: center; gap: 6px; color: #f8fafc; font-weight: 600; font-size: 15px; }
.wcb-sub { color: #93c5fd; font-size: 12px; }
.wcb-header-right { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

.wcb-main {
  display: flex;
  flex: 1;
  min-height: 0;
}
.wcb-panel {
  width: 216px;
  flex-shrink: 0;
  padding: 10px;
  border-right: 1px solid var(--ks-card-border, rgba(15, 23, 42, 0.06));
  background: var(--ks-page-bg, #eef2f8);
  overflow-y: auto;
}
.wcb-panel-title { font-size: 12px; font-weight: 600; color: var(--ks-text-secondary, #64748b); margin: 6px 0 8px; }
.wcb-panel-hint { font-weight: 400; font-size: 11px; }
.wcb-palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  margin-bottom: 6px;
  border: 1px solid var(--ks-card-border, rgba(15, 23, 42, 0.06));
  border-radius: 10px;
  background: var(--ks-card-bg, #fff);
  cursor: grab;
  transition: all 0.15s;
}
.wcb-palette-item:hover { border-color: var(--node-color); box-shadow: var(--ks-shadow-sm, none); transform: translateY(-1px); }
.palette-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.palette-info { flex: 1; min-width: 0; }
.palette-name { font-size: 13px; font-weight: 600; color: var(--ks-text-title, #0b1526); }
.palette-desc { font-size: 11px; color: var(--ks-text-secondary, #64748b); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.palette-add { color: var(--ks-text-secondary, #64748b); }
.wcb-tpl-title { margin-top: 12px; }
.wcb-tpl-select { width: 100%; margin-bottom: 8px; }
.tpl-type { float: right; color: #94a3b8; font-size: 12px; }
.wcb-tpl-meta { display: flex; gap: 6px; }
.wcb-tpl-name { flex: 1; }
.wcb-tpl-type { width: 110px; }

.wcb-canvas-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: auto;
  background: #f8fafc;
  background-image: radial-gradient(circle, rgba(15, 23, 42, 0.08) 1px, transparent 1px);
  background-size: 22px 22px;
}
.wcb-svg { position: absolute; left: 0; top: 0; pointer-events: none; }
.wcb-edge { pointer-events: stroke; cursor: pointer; }
.wcb-temp-edge { pointer-events: none; }

.wcb-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 2px solid var(--node-color);
  border-radius: 12px;
  box-shadow: var(--ks-shadow-md, 0 4px 12px rgba(15, 23, 42, 0.08));
  cursor: grab;
  user-select: none;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.wcb-node:hover { box-shadow: var(--ks-shadow-primary, 0 6px 20px rgba(37, 99, 235, 0.22)); }
.wcb-node.selected { box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25), var(--ks-shadow-md, none); }
.wcb-node-colorbar { height: 5px; background: var(--node-color); border-radius: 8px 8px 0 0; }
.wcb-node-body { display: flex; align-items: center; gap: 8px; padding: 8px 10px; flex: 1; }
.wcb-node-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.wcb-node-info { min-width: 0; }
.wcb-node-name { font-size: 13px; font-weight: 600; color: #0b1526; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wcb-node-type { font-size: 11px; color: #64748b; }
.port {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.25);
  cursor: crosshair;
  z-index: 5;
}
.port:hover { transform: scale(1.25); background: #3b82f6; }

.wcb-canvas-tip {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 14px;
  pointer-events: none;
}

.wcb-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--ks-card-border, rgba(15, 23, 42, 0.06));
  background: var(--ks-page-bg, #eef2f8);
}
.wcb-stats { display: flex; gap: 14px; font-size: 12px; color: var(--ks-text-secondary, #64748b); }
.wcb-dirty { color: var(--ks-warning, #f59e0b); font-weight: 600; }
.wcb-footer-actions { display: flex; gap: 8px; }
.wcb-no-param { color: #94a3b8; font-size: 13px; padding: 8px 0; }

@media (max-width: 760px) {
  .wcb-main { flex-direction: column; }
  .wcb-panel { width: auto; max-height: 180px; border-right: none; border-bottom: 1px solid var(--ks-card-border, rgba(15, 23, 42, 0.06)); }
  .wcb-canvas-wrap { min-height: 420px; }
}
</style>
