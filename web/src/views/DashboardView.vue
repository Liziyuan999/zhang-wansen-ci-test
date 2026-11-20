<script setup lang="ts">
/**
 * 数据看板：企业价值指标 + 近 7 日趋势（轻量 SVG 图表，无重依赖）
 */
import { ref, computed, onMounted } from 'vue'
import {
  getDashboardSummary,
  getKnowledgeHot,
  getDeptActivity,
  getRetrievalHeatmap,
  getLlmUsage,
  type DashboardSummary,
  type KnowledgeHotItem,
  type DeptActivityItem,
  type RetrievalHeatItem,
  type LlmUsageTrend,
} from '@/api/dashboard'
import { Document, Search, ChatDotRound, Promotion, OfficeBuilding, User, TrendCharts, Histogram, Calendar, Cpu } from '@element-plus/icons-vue'

const loading = ref(false)
const summary = ref<DashboardSummary | null>(null)

async function load() {
  loading.value = true
  try {
    summary.value = await getDashboardSummary()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  loadExtra()
})

// ===== 逐行注释：看板指标卡与图表数据派生 =====
// 1. metrics：六张企业价值指标卡（知识文档/检索次数/对话轮次/Agent 任务/组织用户/团队空间），
//    数据来自后端 /api/dashboard/summary，纯 computed 派生、无副作用；
// 2. docStatus/agentStates/agentTypes：文档处理状态、Agent 状态、任务类型三个分布
//    （百分比条形图数据），过滤零值并归一化避免除零；
// 3. peakPoint/polyPoints/areaPoints：轻量 SVG 图表坐标计算（680x220 画布，34 边距），
//    手写折线/面积/峰值点，不引入 echarts 等重依赖；
// 4. trendLines：近 7 日 文档/检索/对话/Agent 四线趋势，直接消费 summary.trend_7d 平行数组。
const metrics = computed(() => {
  const s = summary.value
  return [
    { key: 'document', label: '知识文档', value: s?.document.total ?? 0, sub: s ? `今日 +${s.document.today} · 本周 +${s.document.this_week}` : '', icon: Document, tone: 'blue' },
    { key: 'retrieval', label: '检索次数', value: s?.retrieval.count ?? 0, sub: s ? `成功率 ${(s.retrieval.success_rate * 100).toFixed(1)}%` : '', icon: Search, tone: 'emerald' },
    { key: 'conversation', label: '对话轮次', value: s?.conversation.count ?? 0, sub: s ? `累计消息 ${s.conversation.messages} 条` : '', icon: ChatDotRound, tone: 'amber' },
    { key: 'agent', label: 'Agent 任务', value: s?.agent.total ?? 0, sub: s ? `完成 ${s.agent.finished} · 执行中 ${s.agent.running}` : '', icon: Promotion, tone: 'violet' },
    { key: 'users', label: '组织用户', value: s?.organization.users ?? 0, sub: s ? `${s.organization.departments} 个部门` : '', icon: User, tone: 'cyan' },
    { key: 'teams', label: '团队空间', value: s?.organization.teams ?? 0, sub: '企业级知识协作', icon: OfficeBuilding, tone: 'indigo' },
  ]
})

/** 文档处理状态分布（企业质检视角） */
const docStatus = computed(() => {
  const d = summary.value?.document
  if (!d) return []
  const total = Math.max(d.ready + d.processing + d.pending + d.failed, 1)
  return [
    { key: 'ready', label: '已就绪', value: d.ready, color: '#10b981' },
    { key: 'processing', label: '处理中', value: d.processing, color: '#06b6d4' },
    { key: 'pending', label: '待处理', value: d.pending, color: '#f59e0b' },
    { key: 'failed', label: '失败', value: d.failed, color: '#ef4444' },
  ]
    .filter((i) => i.value > 0)
    .map((i) => ({ ...i, pct: Math.round((i.value / total) * 100) }))
})

/** Agent 任务状态分布 */
const agentStates = computed(() => {
  const a = summary.value?.agent
  if (!a) return []
  const total = Math.max(a.done + a.running + a.failed, 1)
  return [
    { key: 'done', label: '已完成', value: a.done, color: '#10b981' },
    { key: 'running', label: '执行中', value: a.running, color: '#2563eb' },
    { key: 'failed', label: '失败', value: a.failed, color: '#ef4444' },
  ].map((i) => ({ ...i, pct: Math.round((i.value / total) * 100) }))
})

/** Agent 任务类型分布 */
const agentTypes = computed(() => {
  const list = summary.value?.agent.by_type ?? []
  const max = Math.max(...list.map((i) => i.value), 1)
  return list
    .map((i) => ({ ...i, pct: Math.round((i.value / max) * 100) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6)
})

/** 单线峰值点（用于趋势图最高日标注） */
function peakPoint(data: number[]) {
  const W = 680
  const H = 220
  const PAD = 34
  const max = Math.max(...data, 1)
  const n = data.length
  let bi = 0
  data.forEach((v, i) => {
    if (v > data[bi]) bi = i
  })
  const x = n <= 1 ? PAD : PAD + (bi * (W - PAD * 2)) / (n - 1)
  const y = H - PAD - (data[bi] / max) * (H - PAD * 2)
  return { x, y, value: data[bi], i: bi }
}

/** SVG 折线图：datalines = [{ name, color, data }] */
function polyPoints(values: number[]) {
  const W = 680
  const H = 220
  const PAD = 34
  const max = Math.max(...values, 1)
  const n = values.length
  return values
    .map((v, i) => {
      const x = n <= 1 ? PAD : PAD + (i * (W - PAD * 2)) / (n - 1)
      const y = H - PAD - (v / max) * (H - PAD * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

function areaPoints(values: number[]) {
  const W = 680
  const H = 220
  const PAD = 34
  const max = Math.max(...values, 1)
  const n = values.length
  const line = values
    .map((v, i) => {
      const x = n <= 1 ? PAD : PAD + (i * (W - PAD * 2)) / (n - 1)
      const y = H - PAD - (v / max) * (H - PAD * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return `M ${PAD},${H - PAD} L ${line} L ${W - PAD},${H - PAD} Z`
}

const trendLines = computed(() => {
  const s = summary.value
  if (!s) return []
  return [
    { name: '文档', color: '#2563eb', data: s.trend_7d.documents },
    { name: '检索', color: '#10b981', data: s.trend_7d.retrievals },
    { name: '对话', color: '#f59e0b', data: s.trend_7d.conversations },
    { name: 'Agent', color: '#8b5cf6', data: s.trend_7d.agents },
  ]
})

const trendDates = computed(() => summary.value?.trend_7d.dates ?? [])

/** 趋势图 X 坐标（SVG 680x220 布局） */
function chartX(i: number, n: number) {
  const W = 680
  const PAD = 34
  return n <= 1 ? PAD : PAD + (i * (W - PAD * 2)) / (n - 1)
}

/** 趋势图 Y 坐标（SVG 680x220 布局） */
function chartY(v: number, data: number[]) {
  const H = 220
  const PAD = 34
  const max = Math.max(...data, 1)
  return H - PAD - (v / max) * (H - PAD * 2)
}

/** 首条主线（文档）峰值标注点 */
const peak = computed(() => {
  const data = trendLines.value[0]?.data ?? []
  if (!data.length) return { x: 0, y: 0, value: 0, i: 0 }
  const pt = peakPoint(data)
  return { x: pt.x, y: pt.y, value: pt.value, i: pt.i }
})

/* ============ 智能看板升级（功能四） ============ */
const extraLoading = ref(false)
const hotList = ref<KnowledgeHotItem[]>([])
const deptList = ref<DeptActivityItem[]>([])
const heatList = ref<RetrievalHeatItem[]>([])
const heatMax = ref(1)
const llmTrend = ref<LlmUsageTrend[]>([])
const llmSummary = ref<DashboardLlmSummary | null>(null)

interface DashboardLlmSummary {
  total_calls: number
  success_rate: number
  avg_latency_ms: number
  by_model: Array<{ model_name: string; calls: number; success_rate: number; avg_latency_ms: number }>
}

async function loadExtra() {
  extraLoading.value = true
  try {
    const [hot, dept, heat, llm] = await Promise.all([
      getKnowledgeHot(),
      getDeptActivity(),
      getRetrievalHeatmap(),
      getLlmUsage(),
    ])
    hotList.value = hot.list ?? []
    deptList.value = dept.list ?? []
    heatList.value = heat.list ?? []
    heatMax.value = heat.max || 1
    llmTrend.value = llm.trend ?? []
    llmSummary.value = llm.summary as DashboardLlmSummary
  } catch {
    // 拦截器已提示
  } finally {
    extraLoading.value = false
  }
}

/** 部门活跃度：最大总量用于柱宽归一 */
const deptMax = computed(() => Math.max(...deptList.value.map((d) => d.total), 1))

/** 热力图：生成近 14 日日期序列 */
const heatByDate = computed(() => new Map(heatList.value.map((h) => [h.date, h.count])))
const heatDates = computed(() => {
  const arr: Array<{ date: string; day: string }> = []
  const now = new Date()
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(now.getDate() - i)
    arr.push({
      date: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
      day: `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`,
    })
  }
  return arr
})
function heatCount(date: string) {
  return heatByDate.value.get(date) || 0
}
function heatLevel(count: number) {
  if (count <= 0) return 0
  const ratio = count / heatMax.value
  if (ratio >= 0.75) return 4
  if (ratio >= 0.5) return 3
  if (ratio >= 0.25) return 2
  return 1
}
const heatTotal = computed(() => heatList.value.reduce((a, h) => a + h.count, 0))

/** AI 用量：趋势序列与折线 */
const llmDates = computed(() => llmTrend.value.map((t) => t.date.slice(5)))
function llmSeries(key: 'calls' | 'success_rate' | 'avg_latency_ms') {
  return llmTrend.value.map((t) => t[key] ?? 0)
}
function llmPoly(values: number[]) {
  const W = 680
  const H = 200
  const PAD = 34
  const max = Math.max(...values, 1)
  const n = values.length
  return values
    .map((v, i) => {
      const x = n <= 1 ? PAD : PAD + (i * (W - PAD * 2)) / (n - 1)
      const y = H - PAD - (v / max) * (H - PAD * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}
const llmSummaryLine = computed(() => {
  if (!llmSummary.value) return ''
  const s = llmSummary.value
  return `累计 ${s.total_calls} 次 · 成功率 ${(s.success_rate * 100).toFixed(0)}% · 均耗 ${Math.round(s.avg_latency_ms)}ms`
})
</script>

<template>
  <div class="ks-page dashboard-page">
    <div class="ks-page-title">
      <h2>数据看板</h2>
      <p class="ks-muted">企业知识中枢核心指标一览 · 数据实时聚合自本地知识库</p>
    </div>

    <div v-loading="loading" class="dashboard-body">
      <!-- 今日概览条 -->
      <div v-if="summary" class="overview-strip">
        <div class="overview-item">
          <b>{{ summary.document.today }}</b><span>今日新增文档</span>
        </div>
        <div class="overview-item">
          <b>{{ summary.document.this_week }}</b><span>本周新增文档</span>
        </div>
        <div class="overview-item">
          <b>{{ (summary.retrieval.success_rate * 100).toFixed(0) }}%</b><span>检索成功率</span>
        </div>
        <div class="overview-item">
          <b>{{ summary.agent.running }}</b><span>执行中 Agent</span>
        </div>
        <div class="overview-item">
          <b>{{ summary.conversation.messages }}</b><span>累计消息</span>
        </div>
      </div>

      <!-- 指标卡 -->
      <div class="metric-grid">
        <div v-for="m in metrics" :key="m.key" class="ks-card metric-card" :class="`tone-${m.tone}`">
          <div class="metric-icon"><el-icon><component :is="m.icon" /></el-icon></div>
          <div class="metric-info">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value">{{ m.value }}</div>
            <div class="metric-sub">{{ m.sub }}</div>
          </div>
        </div>
      </div>

      <!-- 企业洞察：文档处理状态 / Agent 任务状态与类型 -->
      <div v-if="summary" class="insights-grid">
        <div class="ks-card insight-card">
          <div class="insight-head">
            <h3>文档处理状态</h3>
            <span class="insight-total">共 {{ summary.document.total }} 份</span>
          </div>
          <div v-if="docStatus.length" class="dist-list">
            <div v-for="i in docStatus" :key="i.key" class="dist-item">
              <div class="dist-meta">
                <span class="dist-label"><i class="dist-dot" :style="{ background: i.color }"></i>{{ i.label }}</span>
                <span class="dist-num">{{ i.value }} <em>{{ i.pct }}%</em></span>
              </div>
              <div class="dist-bar"><i class="dist-bar-fill" :style="{ width: i.pct + '%', background: i.color }"></i></div>
            </div>
          </div>
          <div v-else class="ks-empty">暂无文档</div>
        </div>

        <div class="insight-col">
          <div class="ks-card insight-card">
            <div class="insight-head">
              <h3>Agent 任务状态</h3>
              <span class="insight-total">共 {{ summary.agent.total }} 个</span>
            </div>
            <div class="state-pies">
              <div v-for="i in agentStates" :key="i.key" class="state-pie">
                <div
                  class="pie-ring"
                  :style="{
                    background: `conic-gradient(${i.color} ${i.pct * 3.6}deg, rgba(100,116,139,0.12) 0deg)`,
                  }"
                >
                  <div class="pie-inner"><b>{{ i.value }}</b></div>
                </div>
                <span class="pie-label"><i class="dist-dot" :style="{ background: i.color }"></i>{{ i.label }} {{ i.pct }}%</span>
              </div>
            </div>
          </div>
          <div class="ks-card insight-card">
            <div class="insight-head">
              <h3>Agent 任务类型</h3>
              <span class="insight-total">TOP {{ Math.min(agentTypes.length, 6) }}</span>
            </div>
            <div v-if="agentTypes.length" class="dist-list compact">
              <div v-for="i in agentTypes" :key="i.name" class="dist-item">
                <div class="dist-meta">
                  <span class="dist-label">{{ i.name }}</span>
                  <span class="dist-num">{{ i.value }}</span>
                </div>
                <div class="dist-bar"><i class="dist-bar-fill grad" :style="{ width: i.pct + '%' }"></i></div>
              </div>
            </div>
            <div v-else class="ks-empty">暂无任务</div>
          </div>
        </div>
      </div>

      <!-- 近 7 日趋势 -->
      <div class="ks-card trend-card">
        <div class="trend-head">
          <h3>近 7 日使用趋势</h3>
          <div class="trend-legend">
            <span v-for="l in trendLines" :key="l.name" class="legend-item">
              <i class="legend-dot" :style="{ background: l.color }"></i>{{ l.name }}
            </span>
          </div>
        </div>
        <div class="trend-chart">
          <svg viewBox="0 0 680 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="近 7 日趋势折线图">
            <line v-for="i in [0, 1, 2, 3]" :key="i" x1="34" :y1="34 + (i * (220 - 68)) / 3" x2="646" :y2="34 + (i * (220 - 68)) / 3" class="grid-line" />
            <text x="28" y="39" class="axis-label" text-anchor="end">100%</text>
            <text x="28" y="115" class="axis-label" text-anchor="end">50%</text>
            <text x="28" y="190" class="axis-label" text-anchor="end">0</text>
            <path v-for="l in trendLines" :key="l.name + '-area'" :d="areaPoints(l.data)" :fill="l.color" fill-opacity="0.08" />
            <polyline v-for="l in trendLines" :key="l.name" :points="polyPoints(l.data)" fill="none" :stroke="l.color" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
            <g v-for="l in trendLines" :key="l.name + '-dots'">
              <circle v-for="(v, i) in l.data" :key="i" :cx="chartX(i, l.data.length)" :cy="chartY(v, l.data)" r="3" :fill="l.color" stroke="#fff" stroke-width="1.2" class="data-dot" />
            </g>
            <g v-if="peak.value > 0">
              <line :x1="peak.x" :x2="peak.x" y1="34" :y2="peak.y" class="peak-line" />
              <circle :cx="peak.x" :cy="peak.y" r="5.5" fill="#fff" :stroke="trendLines[0].color" stroke-width="2.5" class="peak-dot" />
              <text :x="peak.x" :y="peak.y - 10" class="peak-label" text-anchor="middle">峰值 {{ peak.value }}</text>
            </g>
            <text v-for="(d, i) in trendDates" :key="d" :x="chartX(i, trendDates.length)" y="212" class="axis-label" text-anchor="middle">{{ d }}</text>
          </svg>
        </div>
      </div>

      <!-- 知识热度榜 & 部门活跃度（功能四） -->
      <div v-if="summary" v-loading="extraLoading" class="upgrade-grid">
        <div class="ks-card insight-card">
          <div class="insight-head">
            <h3><el-icon class="insight-icon"><TrendCharts /></el-icon>知识热度榜</h3>
            <span class="insight-total">TOP {{ hotList.length }}</span>
          </div>
          <div v-if="hotList.length" class="hot-list">
            <div v-for="(h, i) in hotList" :key="h.doc_id" class="hot-item">
              <span class="hot-rank" :class="`rank-${Math.min(i + 1, 3)}`">{{ i + 1 }}</span>
              <div class="hot-main">
                <div class="hot-name" :title="h.doc_name">{{ h.doc_name }}</div>
                <div class="hot-meta">浏览 {{ h.view_count }} · 检索命中 {{ h.retrieve_count }}</div>
                <div class="hot-bar">
                  <i class="hot-bar-fill" :style="{ width: Math.min((h.heat_score / (hotList[0]?.heat_score || 1)) * 100, 100) + '%' }"></i>
                </div>
              </div>
              <span class="hot-score">{{ h.heat_score }}</span>
            </div>
          </div>
          <div v-else class="ks-empty">暂无热度数据，浏览或检索文档后生成</div>
        </div>

        <div class="ks-card insight-card">
          <div class="insight-head">
            <h3><el-icon class="insight-icon"><Histogram /></el-icon>部门活跃度</h3>
            <span class="insight-total">近 7 日</span>
          </div>
          <div v-if="deptList.length" class="dept-list">
            <div v-for="d in deptList" :key="d.dept_id" class="dept-item">
              <div class="dept-meta">
                <span class="dept-name">{{ d.dept_name }}</span>
                <span class="dept-num">{{ d.total }}</span>
              </div>
              <div class="dept-bar-track">
                <div class="dept-bar" :style="{ width: (d.total / deptMax) * 100 + '%' }"></div>
              </div>
              <div class="dept-sub">文档 {{ d.documents }} · 对话 {{ d.conversations }} · 检索 {{ d.retrievals }}</div>
            </div>
          </div>
          <div v-else class="ks-empty">暂无活跃数据</div>
        </div>
      </div>

      <!-- 检索热力图（功能四） -->
      <div v-if="summary" v-loading="extraLoading" class="ks-card insight-card heatmap-card">
        <div class="insight-head">
          <h3><el-icon class="insight-icon"><Calendar /></el-icon>检索热力图</h3>
          <span class="insight-total">近 14 日检索量 · 累计 {{ heatTotal }} 次</span>
        </div>
        <div class="heat-grid">
          <div v-for="h in heatDates" :key="h.date" class="heat-col">
            <div class="heat-cell" :class="`lv-${heatLevel(heatCount(h.date))}`" :title="`${h.date} · ${heatCount(h.date)} 次检索`"></div>
            <span class="heat-day">{{ h.day }}</span>
          </div>
        </div>
        <div class="heat-legend">
          <span>低</span>
          <i class="heat-cell lv-0"></i>
          <i class="heat-cell lv-1"></i>
          <i class="heat-cell lv-2"></i>
          <i class="heat-cell lv-3"></i>
          <i class="heat-cell lv-4"></i>
          <span>高</span>
        </div>
      </div>

      <!-- AI 用量报表（功能四） -->
      <div v-if="summary" v-loading="extraLoading" class="ks-card insight-card llm-card">
        <div class="insight-head">
          <h3><el-icon class="insight-icon"><Cpu /></el-icon>AI 用量报表</h3>
          <span class="insight-total">{{ llmSummaryLine || '近 7 日' }}</span>
        </div>
        <div v-if="llmTrend.length" class="llm-body">
          <div class="llm-chart">
            <svg viewBox="0 0 680 200" preserveAspectRatio="xMidYMid meet" role="img" aria-label="AI 调用趋势折线图">
              <line v-for="i in [0, 1, 2, 3]" :key="i" x1="34" :y1="30 + i * 40" x2="646" :y2="30 + i * 40" class="grid-line" />
              <polyline :points="llmPoly(llmSeries('calls'))" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
              <polyline :points="llmPoly(llmSeries('success_rate'))" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="5 3" />
              <polyline :points="llmPoly(llmSeries('avg_latency_ms'))" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="2 4" />
              <text v-for="(d, i) in llmDates" :key="d" :x="chartX(i, llmDates.length)" y="196" class="axis-label" text-anchor="middle">{{ d }}</text>
            </svg>
            <div class="llm-legend">
              <span><i class="legend-dot" style="background:#2563eb"></i>调用次数</span>
              <span><i class="legend-dot" style="background:#10b981"></i>成功率(%)</span>
              <span><i class="legend-dot" style="background:#f59e0b"></i>平均耗时(ms)</span>
            </div>
          </div>
          <div v-if="llmSummary?.by_model?.length" class="llm-models">
            <div v-for="m in llmSummary.by_model" :key="m.model_name" class="model-row">
              <span class="model-name">{{ m.model_name }}</span>
              <span class="model-calls">{{ m.calls }} 次</span>
              <span class="model-rate">成功率 {{ (m.success_rate * 100).toFixed(0) }}%</span>
              <span class="model-lat">{{ Math.round(m.avg_latency_ms) }}ms</span>
            </div>
          </div>
        </div>
        <div v-else class="ks-empty">暂无 LLM 调用记录</div>
      </div>

      <div v-if="!summary" class="ks-empty">暂无统计数据</div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.metric-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
  position: relative;
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--tone);
  opacity: 0.9;
}
.metric-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--ks-shadow-lg);
  border-color: color-mix(in srgb, var(--tone) 35%, transparent);
}
.metric-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  background: linear-gradient(135deg, var(--tone), color-mix(in srgb, var(--tone) 52%, #0f172a));
  box-shadow: 0 6px 14px -4px var(--tone);
}
.tone-blue { --tone: #2563eb; }
.tone-emerald { --tone: #10b981; }
.tone-amber { --tone: #f59e0b; }
.tone-violet { --tone: #8b5cf6; }
.tone-cyan { --tone: #06b6d4; }
.tone-indigo { --tone: #6366f1; }
.metric-label {
  font-size: 13px;
  color: var(--ks-text-secondary, #64748b);
}
.metric-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  margin: 2px 0;
  color: var(--ks-text-primary, #0f172a);
}
.metric-sub {
  font-size: 12px;
  color: var(--ks-text-tertiary, #94a3b8);
}
.overview-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 18px;
  border-radius: var(--ks-card-radius-lg, 18px);
  background:
    radial-gradient(720px 200px at 90% -40px, rgba(139, 92, 246, 0.14), transparent 60%),
    linear-gradient(135deg, #0b1730 0%, #12295c 55%, #1e3a8a 100%);
  border: 1px solid rgba(147, 197, 253, 0.22);
  box-shadow: 0 12px 30px -14px rgba(30, 58, 138, 0.5);
  color: #f8fafc;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-right: 18px;
  border-right: 1px solid rgba(255, 255, 255, 0.14);
  min-width: 92px;
}
.overview-item:last-child {
  border-right: none;
}
.overview-item b {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  background: linear-gradient(120deg, #93c5fd, #c4b5fd);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.overview-item span {
  font-size: 12px;
  color: rgba(203, 213, 225, 0.92);
}
.trend-card {
  margin-top: 16px;
  padding: 18px 20px;
}
.trend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.trend-head h3 {
  margin: 0;
  font-size: 16px;
  color: var(--ks-text-primary, #0f172a);
}
.trend-legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--ks-text-secondary, #64748b);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.trend-chart {
  width: 100%;
  padding-top: 6px;
}
.trend-chart svg {
  width: 100%;
  height: auto;
  max-height: 260px;
}
.grid-line {
  stroke: rgba(100, 116, 139, 0.14);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}
.axis-base {
  stroke: rgba(100, 116, 139, 0.2);
  stroke-width: 1;
}
.axis-label {
  font-size: 11px;
  fill: var(--ks-text-tertiary, #94a3b8);
}
/* 趋势图增强：数据点 / 峰值标注 */
.data-dot {
  transition: r 0.15s ease;
}
.peak-line {
  stroke: rgba(37, 99, 235, 0.28);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.peak-dot {
  filter: drop-shadow(0 1px 3px rgba(15, 23, 42, 0.18));
}
.peak-label {
  font-size: 11px;
  font-weight: 600;
  fill: var(--ks-text-primary, #0f172a);
}

/* ============ insights 双栏（企业洞察） ============ */
.insights-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}
.insight-card {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.6), #fff);
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.insight-card:hover {
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
.insight-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.insight-head h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-primary, #0f172a);
}
.insight-sub {
  font-size: 12px;
  color: var(--ks-text-tertiary, #94a3b8);
  margin-bottom: 12px;
}
.insight-total {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--ks-text-primary, #0f172a);
  letter-spacing: -0.5px;
}
.insight-total small {
  font-size: 13px;
  font-weight: 500;
  color: var(--ks-text-tertiary, #94a3b8);
  margin-left: 4px;
}
/* 类型分布 */
.dist-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 6px;
}
.dist-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dist-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dist-meta {
  min-width: 96px;
  font-size: 12px;
  color: var(--ks-text-secondary, #64748b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dist-bar {
  flex: 1;
  height: 8px;
  background: rgba(100, 116, 139, 0.12);
  border-radius: 999px;
  overflow: hidden;
}
.dist-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
}
.dist-num {
  min-width: 44px;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  color: var(--ks-text-primary, #0f172a);
}
/* 分布环 */
.state-pies {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 12px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.state-pie {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.pie-ring {
  position: relative;
  width: 92px;
  height: 92px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: conic-gradient(var(--ks-ring-color, #2563eb) calc(var(--ks-ring-pct, 0) * 1%), rgba(100, 116, 139, 0.12) 0);
}
.pie-ring::before {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  background: #fff;
}
.pie-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.15;
}
.pie-inner strong {
  font-size: 17px;
  font-weight: 700;
  color: var(--ks-text-primary, #0f172a);
}
.pie-inner span {
  font-size: 11px;
  color: var(--ks-text-tertiary, #94a3b8);
}
.pie-label {
  font-size: 12px;
  color: var(--ks-text-secondary, #64748b);
}
.insight-note {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(100, 116, 139, 0.18);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ks-text-tertiary, #94a3b8);
}
.insight-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dist-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
}
.dist-label .dist-dot {
  display: inline-block;
  vertical-align: middle;
}
.dist-bar-fill.grad {
  background: linear-gradient(90deg, #2563eb, #8b5cf6);
}
.dist-list.compact .dist-item {
  gap: 6px;
}
@media (max-width: 900px) {
  .insights-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 560px) {
  .dashboard-page {
    padding: 14px;
  }
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  .metric-card {
    padding: 12px;
    gap: 10px;
    flex-direction: column;
  }
  .metric-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
  .metric-value {
    font-size: 22px;
  }
  .trend-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
@media (max-width: 375px) {
  .metric-grid {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .metric-card {
    padding: 10px;
  }
  .trend-card {
    padding: 12px;
  }
  .trend-chart svg {
    max-height: 180px;
  }
}

/* ============ 智能看板升级（功能四） ============ */
.insight-icon {
  vertical-align: -2px;
  margin-right: 4px;
  color: var(--ks-primary);
}

.upgrade-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

/* 知识热度榜 */
.hot-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.85), rgba(248, 251, 255, 0.6));
  border: 1px solid rgba(99, 102, 241, 0.1);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hot-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08);
}

.hot-rank {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--ks-text-body);
  background: rgba(100, 116, 139, 0.1);
}

.hot-rank.rank-1 {
  color: #fff;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  box-shadow: 0 4px 10px -2px rgba(245, 158, 11, 0.45);
}

.hot-rank.rank-2 {
  color: #fff;
  background: linear-gradient(135deg, #94a3b8, #64748b);
}

.hot-rank.rank-3 {
  color: #fff;
  background: linear-gradient(135deg, #d97706, #92400e);
}

.hot-main {
  flex: 1;
  min-width: 0;
}

.hot-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hot-meta {
  font-size: 11px;
  color: var(--ks-text-muted);
  margin-top: 2px;
}

.hot-bar {
  height: 4px;
  border-radius: 3px;
  background: rgba(37, 99, 235, 0.08);
  margin-top: 5px;
  overflow: hidden;
}

.hot-bar-fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #2563eb, #8b5cf6);
  transition: width 0.6s ease;
}

.hot-score {
  font-size: 14px;
  font-weight: 700;
  color: var(--ks-primary);
  flex-shrink: 0;
}

/* 部门活跃度 */
.dept-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dept-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.dept-name {
  font-weight: 600;
  color: var(--ks-text-title);
}

.dept-num {
  font-weight: 700;
  color: var(--ks-primary);
}

.dept-bar-track {
  height: 8px;
  border-radius: 6px;
  background: rgba(37, 99, 235, 0.08);
  overflow: hidden;
  margin-top: 4px;
}

.dept-bar {
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #2563eb, #10b981);
  transition: width 0.6s ease;
}

.dept-sub {
  font-size: 11px;
  color: var(--ks-text-muted);
  margin-top: 3px;
}

/* 检索热力图 */
.heatmap-card {
  margin-top: 16px;
}

.heat-grid {
  display: grid;
  grid-template-columns: repeat(14, 1fr);
  gap: 6px;
  align-items: end;
  padding: 6px 0 2px;
}

.heat-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.heat-cell {
  display: inline-block;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
}

.heat-cell.lv-0 {
  background: rgba(100, 116, 139, 0.12);
}

.heat-cell.lv-1 {
  background: rgba(37, 99, 235, 0.25);
}

.heat-cell.lv-2 {
  background: rgba(37, 99, 235, 0.5);
}

.heat-cell.lv-3 {
  background: rgba(37, 99, 235, 0.72);
}

.heat-cell.lv-4 {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 4px 12px -2px rgba(37, 99, 235, 0.45);
}

.heat-day {
  font-size: 10px;
  color: var(--ks-text-muted);
  white-space: nowrap;
}

.heat-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 11px;
  color: var(--ks-text-muted);
}

.heat-legend .heat-cell {
  width: 16px;
  aspect-ratio: auto;
  height: 16px;
}

/* AI 用量报表 */
.llm-card {
  margin-top: 16px;
}

.llm-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.llm-chart {
  width: 100%;
}

.llm-chart svg {
  width: 100%;
  height: auto;
  max-height: 220px;
}

.llm-legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--ks-text-body);
  margin-top: 6px;
}

.llm-legend .legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 5px;
}

.llm-models {
  border-top: 1px dashed rgba(99, 102, 241, 0.16);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.05);
}

.model-name {
  font-weight: 600;
  color: var(--ks-text-title);
  flex: 1;
}

.model-calls,
.model-rate,
.model-lat {
  color: var(--ks-text-body);
  white-space: nowrap;
}

.model-lat {
  color: var(--ks-primary);
  font-weight: 600;
}

@media (max-width: 768px) {
  .upgrade-grid {
    grid-template-columns: 1fr;
  }

  .heat-grid {
    gap: 3px;
  }

  .heat-day {
    font-size: 9px;
  }
}
</style>
