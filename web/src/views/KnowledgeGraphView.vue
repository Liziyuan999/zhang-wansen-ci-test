<script setup lang="ts">
/**
 * 知识图谱页（GraphRAG）
 * - 轻量 SVG 自绘力导向图谱，无第三方重依赖
 * - 支持按文档过滤、关键词搜索、节点点击查看实体详情
 * - 统计卡片 / 空状态引导抽取 / 深色企业风适配
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Connection, Document, ArrowDown, Close, DataAnalysis } from '@element-plus/icons-vue'
import { getKgGraph, getKgStats, searchKgEntities, extractDocumentKg } from '@/api/kg'
import { listDocuments } from '@/api/document'
import type { KgGraphData, KgGraphNode, KgGraphLink, KgStats, KgEntity, DocListItem } from '@/types'

/* ---------------- 状态 ---------------- */
const loading = ref(false)
const graph = ref<KgGraphData>({ nodes: [], links: [] })
const stats = ref<KgStats>({ entity_count: 0, relation_count: 0, doc_count: 0, type_distribution: [] })
const docOptions = ref<DocListItem[]>([])
const selectedDocId = ref<number | null>(null)
const keyword = ref('')
const searchKeyword = ref('')
const searchResults = ref<KgEntity[]>([])
const searchLoading = ref(false)
const extracting = ref(false)
const extractingDocId = ref<number | null>(null)
const selectedNode = ref<KgGraphNode | null>(null)
const selectedLinks = ref<KgGraphLink[]>([])

/* ---------------- 布局 ---------------- */
const svgWrap = ref<HTMLElement | null>(null)
const viewW = ref(1000)
const viewH = ref(620)
let resizeObs: ResizeObserver | null = null

/* 节点类型 → 颜色 */
const typeColorMap: Record<string, string> = {
  person: '#3b82f6',
  org: '#8b5cf6',
  product: '#10b981',
  tech: '#f59e0b',
  place: '#06b6d4',
  event: '#ef4444',
  concept: '#a855f7',
  other: '#64748b',
}

function nodeColor(type: string): string {
  const t = (type || '').toLowerCase()
  return typeColorMap[t] || typeColorMap.other
}

/* ---------------- 力导向布局（轻量迭代） ---------------- */
interface Pos {
  x: number
  y: number
}
const nodePos = ref<Record<string, Pos>>({})

// ===== 逐行注释：知识图谱力导向布局（轻量自研，无第三方图库依赖）=====
// 1. 初始位置：按节点数做环形均匀分布（半径取画布短边的 0.36），保证起点不重叠；
// 2. 力模型：斥力（repulsion，节点间越近推力越大）+ 弹簧力（edges 拉近，度数高的
//    节点弹力更强会自然聚簇）+ 向心力（整体收敛到画布中心，度数越高的节点越靠中心）；
// 3. 迭代 140 轮逼近稳定布局，每轮先算合力再更新坐标，复杂度 O(n²+E)，适合百级节点；
// 4. 布局结果写入 nodePos，SVG 模板按 pos 渲染圆/标签与连线。
function computeLayout(nodes: KgGraphNode[], links: KgGraphLink[], width: number, height: number) {
  const n = nodes.length
  if (!n) {
    nodePos.value = {}
    return
  }
  const pos: Record<string, Pos> = {}
  const cx = width / 2
  const cy = height / 2
  // 初始环形分布
  nodes.forEach((nd, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    const radius = Math.min(width, height) * 0.36
    pos[String(nd.id)] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }
  })
  const idSet = new Map<number, KgGraphNode>()
  nodes.forEach((nd) => idSet.set(nd.id, nd))
  const linkSet = new Map<string, number>()
  links.forEach((lk) => {
    const key = [lk.source, lk.target].sort((a, b) => a - b).join('_')
    linkSet.set(key, (linkSet.get(key) || 0) + 1)
  })
  const degreeMap = new Map<number, number>()
  nodes.forEach((nd) => degreeMap.set(nd.id, nd.degree || 0))

  // 迭代力导向：斥力 + 弹簧 + 向心
  const repulsion = 2200
  const springK = 0.04
  const centerForce = 0.012
  for (let iter = 0; iter < 140; iter++) {
    const forces: Record<string, { fx: number; fy: number }> = {}
    nodes.forEach((nd) => {
      forces[String(nd.id)] = { fx: 0, fy: 0 }
    })
    // 两两斥力
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = pos[String(nodes[i].id)]
        const b = pos[String(nodes[j].id)]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.sqrt(dx * dx + dy * dy) || 1
        const minDist = 70
        if (dist < minDist) {
          const push = (minDist - dist) * 0.18
          dx /= dist
          dy /= dist
          forces[String(nodes[i].id)].fx += dx * push
          forces[String(nodes[i].id)].fy += dy * push
          forces[String(nodes[j].id)].fx -= dx * push
          forces[String(nodes[j].id)].fy -= dy * push
        } else {
          const f = repulsion / (dist * dist)
          dx /= dist
          dy /= dist
          forces[String(nodes[i].id)].fx += dx * f
          forces[String(nodes[i].id)].fy += dy * f
          forces[String(nodes[j].id)].fx -= dx * f
          forces[String(nodes[j].id)].fy -= dy * f
        }
      }
    }
    // 边弹簧力（度数高的节点弹力更强，形成簇）
    links.forEach((lk) => {
      const a = pos[String(lk.source)]
      const b = pos[String(lk.target)]
      if (!a || !b) return
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const ideal = 130
      const f = (dist - ideal) * springK
      const ux = dx / dist
      const uy = dy / dist
      forces[String(lk.source)].fx += ux * f
      forces[String(lk.source)].fy += uy * f
      forces[String(lk.target)].fx -= ux * f
      forces[String(lk.target)].fy -= uy * f
    })
    // 向心力
    nodes.forEach((nd) => {
      const p = pos[String(nd.id)]
      const dx = cx - p.x
      const dy = cy - p.y
      const f = centerForce * (1 + (degreeMap.get(nd.id) || 0) * 0.02)
      forces[String(nd.id)].fx += dx * f
      forces[String(nd.id)].fy += dy * f
    })
    // 更新位置
    nodes.forEach((nd) => {
      const p = pos[String(nd.id)]
      const f = forces[String(nd.id)]
      p.x += Math.max(-8, Math.min(8, f.fx))
      p.y += Math.max(-8, Math.min(8, f.fy))
    })
  }
  // 边界裁剪
  nodes.forEach((nd) => {
    const p = pos[String(nd.id)]
    p.x = Math.max(46, Math.min(width - 46, p.x))
    p.y = Math.max(30, Math.min(height - 30, p.y))
  })
  nodePos.value = pos
}

/* ---------------- 数据加载 ---------------- */
async function loadStats() {
  try {
    const data = await getKgStats()
    stats.value = data || { entity_count: 0, relation_count: 0, doc_count: 0, type_distribution: [] }
  } catch {
    // 拦截器已提示
  }
}

async function loadGraph() {
  loading.value = true
  try {
    const params: { doc_id?: number; keyword?: string; limit?: number } = {}
    if (selectedDocId.value) params.doc_id = selectedDocId.value
    if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
    params.limit = 120
    const data = await getKgGraph(params)
    graph.value = data || { nodes: [], links: [] }
    selectedNode.value = null
    selectedLinks.value = []
    await nextTick()
    computeLayout(graph.value.nodes, graph.value.links, viewW.value, viewH.value)
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadDocs() {
  try {
    const data = await listDocuments({ page: 1, page_size: 200 })
    docOptions.value = data?.items ?? []
  } catch {
    // 拦截器已提示
  }
}

async function refreshAll() {
  await Promise.all([loadStats(), loadGraph()])
}

function handleDocChange() {
  refreshAll()
}

async function handleSearch() {
  searchLoading.value = true
  try {
    if (searchKeyword.value.trim()) {
      const res = await searchKgEntities(searchKeyword.value.trim(), 20)
      searchResults.value = res || []
    } else {
      searchResults.value = []
    }
  } catch {
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

function applyEntityToGraph(e: KgEntity) {
  // 跳转到该实体：先按关键词过滤图谱
  searchKeyword.value = e.name
  selectedDocId.value = e.doc_id ?? null
  refreshAll()
}

async function handleExtract(docId: number | null) {
  if (!docId) {
    ElMessage.warning('请先在左侧选择文档')
    return
  }
  extracting.value = true
  extractingDocId.value = docId
  try {
    const res = await extractDocumentKg(docId)
    ElMessage.success(
      `抽取完成：实体 ${res.entity_count} 个，关系 ${res.relation_count} 条` +
        (res.status === 'failed' && res.error ? `（${res.error}）` : '')
    )
    await refreshAll()
  } catch (e: unknown) {
    ElMessage.error((e as { message?: string })?.message || '抽取失败')
  } finally {
    extracting.value = false
    extractingDocId.value = null
  }
}

function selectNode(nd: KgGraphNode) {
  selectedNode.value = nd
  selectedLinks.value = graph.value.links.filter(
    (lk) => lk.source === nd.id || lk.target === nd.id
  )
}

/* 视口自适应 */
function measure() {
  if (!svgWrap.value) return
  const rect = svgWrap.value.getBoundingClientRect()
  if (rect.width > 10) {
    viewW.value = Math.max(760, rect.width)
    viewH.value = Math.max(520, Math.min(720, rect.height || 620))
  }
}

function onResize() {
  measure()
  computeLayout(graph.value.nodes, graph.value.links, viewW.value, viewH.value)
}

const route = useRoute()

onMounted(() => {
  const qDoc = Number(route.query.doc_id)
  if (qDoc > 0) selectedDocId.value = qDoc
  const qKw = String(route.query.keyword || '').trim()
  if (qKw) {
    searchKeyword.value = qKw
    void handleSearch()
  }
  measure()
  loadDocs()
  refreshAll()
  if (typeof ResizeObserver !== 'undefined' && svgWrap.value) {
    resizeObs = new ResizeObserver(onResize)
    resizeObs.observe(svgWrap.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObs) resizeObs.disconnect()
})

watch(searchKeyword, (val) => {
  if (!val.trim()) {
    searchResults.value = []
    refreshAll()
  }
})

/* 辅助计算 */
const statCards = computed(() => [
  { label: '实体总数', value: stats.value.entity_count, icon: Connection, color: '#3b82f6' },
  { label: '关系总数', value: stats.value.relation_count, icon: ArrowDown, color: '#8b5cf6' },
  { label: '已抽取文档', value: stats.value.doc_count, icon: Document, color: '#10b981' },
  { label: '实体类型', value: stats.value.type_distribution.length, icon: DataAnalysis, color: '#f59e0b' },
])

const typeDist = computed(() => stats.value.type_distribution.slice(0, 8))

const docNameById = (id: number | null | undefined) => {
  if (!id) return '—'
  const found = docOptions.value.find((d) => d.id === id)
  return found ? found.doc_name : `文档 #${id}`
}
</script>

<template>
  <div class="kg-page">
    <!-- 顶部标题 -->
    <div class="kg-header">
      <div class="kg-title-row">
        <div class="kg-title-icon"><el-icon :size="20"><Connection /></el-icon></div>
        <div>
          <h2 class="kg-title">知识图谱 <em>GraphRAG</em></h2>
          <p class="kg-sub">实体与关系自动抽取，构建企业级语义网络</p>
        </div>
      </div>
      <el-button :icon="Refresh" @click="refreshAll">刷新</el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="kg-stats">
      <div v-for="c in statCards" :key="c.label" class="kg-stat-card">
        <div class="kg-stat-icon" :style="{ background: c.color + '1a', color: c.color }">
          <el-icon :size="18"><component :is="c.icon" /></el-icon>
        </div>
        <div class="kg-stat-info">
          <div class="kg-stat-value">{{ c.value }}</div>
          <div class="kg-stat-label">{{ c.label }}</div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="kg-toolbar">
      <div class="kg-tool-left">
        <el-select
          v-model="selectedDocId"
          placeholder="全部文档"
          clearable
          filterable
          style="width: 220px"
          @change="handleDocChange"
        >
          <el-option
            v-for="d in docOptions"
            :key="d.id"
            :label="d.doc_name"
            :value="d.id"
          />
        </el-select>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索实体，如：绩效考核、AI 助手"
          clearable
          style="width: 260px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      </div>
      <div class="kg-tool-right">
        <el-button
          type="warning"
          plain
          :loading="extracting"
          @click="handleExtract(selectedDocId)"
        >
          {{ extracting ? `抽取中…` : '抽取所选文档图谱' }}
        </el-button>
      </div>
    </div>

    <!-- 搜索建议列表 -->
    <div v-if="searchResults.length" class="kg-search-hits">
      <span class="kg-search-hits-title">实体命中：</span>
      <button
        v-for="e in searchResults"
        :key="e.id"
        class="kg-hit"
        @click="applyEntityToGraph(e)"
      >
        <span class="kg-hit-name">{{ e.name }}</span>
        <span class="kg-hit-meta">{{ e.type }} · 关系 {{ e.relation_count ?? 0 }}</span>
      </button>
    </div>

    <!-- 图谱主体 -->
    <div class="kg-body">
      <div ref="svgWrap" v-loading="loading" class="kg-canvas">
        <div v-if="!graph.nodes.length && !loading" class="kg-empty">
          <el-icon :size="52" color="#94a3b8"><Connection /></el-icon>
          <h3>图谱还是空的</h3>
          <p>在上方选择文档后点击「抽取所选文档图谱」，系统将自动抽取实体与关系。</p>
          <el-button type="primary" :loading="extracting" @click="handleExtract(selectedDocId)">
            立即抽取{{ selectedDocId ? '当前文档' : '（请先选择文档）' }}
          </el-button>
        </div>
        <template v-else-if="graph.nodes.length">
          <svg
            :width="viewW"
            :height="viewH"
            class="kg-svg"
            :viewBox="`0 0 ${viewW} ${viewH}`"
          >
            <defs>
              <marker id="kg-arrow" viewBox="0 0 10 10" refX="16" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
              </marker>
            </defs>
            <!-- 连线 -->
            <g v-for="(lk, idx) in graph.links" :key="`l${idx}`">
              <line
                :x1="nodePos[String(lk.source)]?.x ?? 0"
                :y1="nodePos[String(lk.source)]?.y ?? 0"
                :x2="nodePos[String(lk.target)]?.x ?? 0"
                :y2="nodePos[String(lk.target)]?.y ?? 0"
                class="kg-edge"
                :class="{ 'kg-edge-active': selectedNode && (lk.source === selectedNode.id || lk.target === selectedNode.id) }"
                marker-end="url(#kg-arrow)"
              />
            </g>
            <!-- 节点 -->
            <g
              v-for="nd in graph.nodes"
              :key="nd.id"
              class="kg-node"
              :class="{ 'kg-node-active': selectedNode?.id === nd.id }"
              @click="selectNode(nd)"
            >
              <circle
                :cx="nodePos[String(nd.id)]?.x ?? 0"
                :cy="nodePos[String(nd.id)]?.y ?? 0"
                :r="Math.min(34, 12 + (nd.degree || 0) * 3)"
                :fill="nodeColor(nd.type)"
                fill-opacity="0.16"
                :stroke="nodeColor(nd.type)"
                stroke-width="1.6"
              />
              <circle
                :cx="nodePos[String(nd.id)]?.x ?? 0"
                :cy="nodePos[String(nd.id)]?.y ?? 0"
                :r="3"
                :fill="nodeColor(nd.type)"
              />
              <text
                :x="nodePos[String(nd.id)]?.x ?? 0"
                :y="(nodePos[String(nd.id)]?.y ?? 0) + 42"
                class="kg-node-text"
                text-anchor="middle"
              >
                {{ nd.name.length > 10 ? nd.name.slice(0, 9) + '…' : nd.name }}
              </text>
            </g>
          </svg>
          <div class="kg-canvas-tip">点击节点查看实体详情 · 共 {{ graph.nodes.length }} 个实体 / {{ graph.links.length }} 条关系</div>
        </template>
      </div>

      <!-- 实体详情面板 -->
      <transition name="kg-slide">
        <div v-if="selectedNode" class="kg-detail">
          <div class="kg-detail-head">
            <span class="kg-detail-type" :style="{ background: nodeColor(selectedNode.type) + '1f', color: nodeColor(selectedNode.type) }">
              {{ selectedNode.type }}
            </span>
            <button class="kg-detail-close" type="button" @click="selectedNode = null">
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <h3 class="kg-detail-name">{{ selectedNode.name }}</h3>
          <div class="kg-detail-meta">
            <span>度数 <b>{{ selectedNode.degree }}</b></span>
            <span>来源 <b>{{ docNameById(selectedNode.doc_id) }}</b></span>
          </div>
          <p class="kg-detail-desc">{{ selectedNode.description || '暂无描述' }}</p>
          <div v-if="selectedLinks.length" class="kg-detail-links">
            <div class="kg-detail-links-title">关联关系（{{ selectedLinks.length }}）</div>
            <div v-for="(lk, i) in selectedLinks" :key="i" class="kg-detail-link">
              <span class="kg-detail-link-type">{{ lk.relation_type }}</span>
              <span class="kg-detail-link-names">
                <template v-if="lk.source === selectedNode.id">
                  {{ graph.nodes.find((n) => n.id === lk.target)?.name || '?' }}
                </template>
                <template v-else>
                  {{ graph.nodes.find((n) => n.id === lk.source)?.name || '?' }}
                </template>
              </span>
            </div>
          </div>
          <el-empty v-else description="暂无关联关系" :image-size="60" />
        </div>
      </transition>
    </div>

    <!-- 类型分布 -->
    <div v-if="typeDist.length" class="kg-types">
      <div class="kg-types-title">实体类型分布</div>
      <div class="kg-types-bar">
        <div
          v-for="t in typeDist"
          :key="t.type"
          class="kg-types-seg"
          :style="{ width: (t.count / Math.max(stats.entity_count, 1)) * 100 + '%', background: nodeColor(t.type) }"
          :title="`${t.type}: ${t.count}`"
        ></div>
      </div>
      <div class="kg-types-legend">
        <span v-for="t in typeDist" :key="t.type" class="kg-types-item">
          <i :style="{ background: nodeColor(t.type) }"></i>{{ t.type }} {{ t.count }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kg-page {
  max-width: 1240px;
  margin: 0 auto;
  padding: 24px 20px 40px;
}

/* 头部 */
.kg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  flex-wrap: wrap;
  gap: 10px;
}

.kg-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kg-title-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: var(--ks-primary-gradient);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--ks-shadow-primary);
}

.kg-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--ks-text-title);
  margin: 0;
  line-height: 1.3;
}

.kg-title em {
  font-style: normal;
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-primary);
  background: var(--ks-primary-soft);
  padding: 2px 8px;
  border-radius: 999px;
  margin-left: 6px;
  vertical-align: middle;
}

.kg-sub {
  font-size: 13px;
  color: var(--ks-text-secondary);
  margin: 2px 0 0;
}

/* 统计卡片 */
.kg-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.kg-stat-card {
  background: var(--ks-card-bg);
  border: 1px solid var(--ks-card-border);
  border-radius: var(--ks-card-radius);
  box-shadow: var(--ks-shadow-sm);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.kg-stat-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kg-stat-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--ks-text-title);
  line-height: 1.1;
}

.kg-stat-label {
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-top: 2px;
}

/* 工具栏 */
.kg-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  background: var(--ks-card-bg);
  border: 1px solid var(--ks-card-border);
  border-radius: var(--ks-card-radius);
  box-shadow: var(--ks-shadow-sm);
  padding: 12px 14px;
}

.kg-tool-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.kg-tool-right {
  display: flex;
  align-items: center;
}

/* 搜索命中 */
.kg-search-hits {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
  background: var(--ks-primary-soft);
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 12px;
  padding: 10px 12px;
}

.kg-search-hits-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ks-primary-active);
}

.kg-hit {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(37, 99, 235, 0.2);
  background: #fff;
  border-radius: 999px;
  padding: 5px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
}

.kg-hit:hover {
  background: var(--ks-primary);
  color: #fff;
  border-color: var(--ks-primary);
}

.kg-hit-name {
  font-weight: 700;
}

.kg-hit-meta {
  font-size: 12px;
  opacity: 0.75;
}

/* 图谱主体 */
.kg-body {
  display: flex;
  gap: 14px;
  position: relative;
}

.kg-canvas {
  flex: 1;
  min-height: 560px;
  background: var(--ks-card-bg);
  border: 1px solid var(--ks-card-border);
  border-radius: var(--ks-card-radius-lg);
  box-shadow: var(--ks-shadow-md);
  position: relative;
  overflow: hidden;
}

.kg-svg {
  display: block;
  background:
    radial-gradient(circle at 30% 25%, rgba(37, 99, 235, 0.05), transparent 45%),
    radial-gradient(circle at 75% 70%, rgba(139, 92, 246, 0.05), transparent 45%),
    linear-gradient(180deg, #fbfdff, #f4f8ff);
}

.kg-edge {
  stroke: #94a3b8;
  stroke-width: 1.4;
  stroke-opacity: 0.55;
  transition: stroke 0.2s ease, stroke-width 0.2s ease;
}

.kg-edge-active {
  stroke: var(--ks-primary);
  stroke-width: 2.2;
  stroke-opacity: 0.9;
}

.kg-node {
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.kg-node text {
  fill: var(--ks-text-body);
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.kg-node-active circle:first-child {
  stroke-width: 3;
  filter: drop-shadow(0 2px 8px rgba(37, 99, 235, 0.35));
}

.kg-canvas-tip {
  position: absolute;
  left: 14px;
  bottom: 12px;
  font-size: 12px;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 999px;
  padding: 4px 12px;
  border: 1px solid var(--ks-card-border);
  pointer-events: none;
}

.kg-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  padding: 20px;
}

.kg-empty h3 {
  margin: 0;
  font-size: 18px;
  color: var(--ks-text-title);
}

.kg-empty p {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--ks-text-secondary);
  max-width: 420px;
}

/* 详情面板 */
.kg-detail {
  width: 300px;
  flex-shrink: 0;
  background: var(--ks-card-bg);
  border: 1px solid var(--ks-card-border);
  border-radius: var(--ks-card-radius-lg);
  box-shadow: var(--ks-shadow-lg);
  padding: 16px;
  max-height: 560px;
  overflow-y: auto;
}

.kg-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kg-detail-type {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 3px 10px;
}

.kg-detail-close {
  border: none;
  background: #f1f5f9;
  color: #64748b;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.kg-detail-close:hover {
  background: var(--ks-danger-bg);
  color: var(--ks-danger);
}

.kg-detail-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--ks-text-title);
  margin: 10px 0 6px;
  word-break: break-all;
}

.kg-detail-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--ks-text-secondary);
  margin-bottom: 10px;
}

.kg-detail-meta b {
  color: var(--ks-text-body);
}

.kg-detail-desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--ks-text-body);
  background: var(--ks-page-bg);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 0 0 12px;
  word-break: break-word;
}

.kg-detail-links-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--ks-text-secondary);
  margin-bottom: 8px;
}

.kg-detail-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed #e2e8f0;
  font-size: 13px;
}

.kg-detail-link:last-child {
  border-bottom: none;
}

.kg-detail-link-type {
  font-size: 11px;
  font-weight: 700;
  color: var(--ks-primary-active);
  background: var(--ks-primary-soft);
  border-radius: 6px;
  padding: 2px 7px;
  flex-shrink: 0;
}

.kg-detail-link-names {
  color: var(--ks-text-body);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 类型分布 */
.kg-types {
  margin-top: 14px;
  background: var(--ks-card-bg);
  border: 1px solid var(--ks-card-border);
  border-radius: var(--ks-card-radius);
  box-shadow: var(--ks-shadow-sm);
  padding: 14px 16px;
}

.kg-types-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ks-text-title);
  margin-bottom: 10px;
}

.kg-types-bar {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: #eef2f7;
  margin-bottom: 10px;
}

.kg-types-seg {
  height: 100%;
  transition: width 0.5s ease;
}

.kg-types-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.kg-types-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.kg-types-item i {
  width: 9px;
  height: 9px;
  border-radius: 3px;
  display: inline-block;
}

/* 动画 */
.kg-slide-enter-active,
.kg-slide-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.kg-slide-enter-from,
.kg-slide-leave-to {
  opacity: 0;
  transform: translateX(16px);
}

/* 移动端适配 */
@media (max-width: 900px) {
  .kg-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  .kg-body {
    flex-direction: column;
  }
  .kg-detail {
    width: 100%;
    max-height: none;
  }
}

@media (max-width: 560px) {
  .kg-page {
    padding: 16px 12px 28px;
  }
  .kg-tool-left,
  .kg-tool-right {
    width: 100%;
  }
  .kg-tool-left .el-select,
  .kg-tool-left .el-input {
    width: 100% !important;
  }
  .kg-canvas {
    min-height: 420px;
  }
}
</style>
