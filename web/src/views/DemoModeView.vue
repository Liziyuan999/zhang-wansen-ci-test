<script setup lang="ts">
/**
 * 演示模式（功能五）
 * 引导流程：欢迎页 → 一键灌入演示数据 → 引导参观亮点页 → 一键清除恢复
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, DataAnalysis, Connection, Promotion, Document, ChatDotRound, Delete, Check, Loading, OfficeBuilding, TrendCharts } from '@element-plus/icons-vue'
import { getDemoStatus, seedDemo, clearDemo, type DemoStatus } from '@/api/demo'

const router = useRouter()

const status = ref<DemoStatus | null>(null)
const loading = ref(false)
const seeding = ref(false)
const clearing = ref(false)

const steps = [
  { key: 'intro', title: '产品能力概览', desc: '先认识知寻 KnowSeek 的六大差异化能力' },
  { key: 'seed', title: '一键灌入演示数据', desc: '生成演示部门、成员、文档与知识关系，不触碰真实数据' },
  { key: 'tour', title: '参观亮点功能', desc: '前往知识图谱 / Agent 工作流 / 数据看板查看演示效果' },
  { key: 'clear', title: '一键清除恢复', desc: '演示结束后清除全部演示数据，恢复干净环境' },
]

const highlights = [
  { icon: Connection, title: '知识图谱 GraphRAG', desc: '文档实体自动抽取与关系网络，跨文档智能联想', path: '/knowledge-graph' },
  { icon: Promotion, title: 'Agent 拖拽工作流', desc: '可视化编排多步骤 AI 任务，一键运行实时跟踪', path: '/agent-task' },
  { icon: TrendCharts, title: '智能数据看板', desc: '知识热度、部门活跃、检索热力图与 AI 用量报表', path: '/dashboard' },
  { icon: Document, title: 'AI 文档 Copilot', desc: '选中文档正文即问即答，一键摘要 / 翻译 / 要点', path: '/document' },
  { icon: ChatDotRound, title: '企业级 AI 对话', desc: '多模型接入、引用溯源、团队共享问答', path: '/chat' },
  { icon: OfficeBuilding, title: '组织与共享', desc: '部门空间、成员协作、权限审批一体化管理', path: '/team' },
]

async function loadStatus() {
  try {
    status.value = await getDemoStatus()
  } catch {
    // 拦截器已提示
  }
}

// ===== 逐行注释：一键灌入演示数据 =====
// 1. ElMessageBox.confirm 二次确认：向用户明示"真实数据会被保留、演示数据带独立标记"；
// 2. seedDemo(true)：调用后端 /api/demo/seed，keep_original=true 表示不清空真实数据，
//    后端 demo_service.seed_demo 生成演示部门/成员/文档/知识图谱/对话/活跃日志；
// 3. 成功后按返回统计（文档数/成员数/实体数）提示，并刷新状态条；
// 4. handleClear 对称地调用 clearDemo 一键清除演示标记数据，恢复干净环境。
async function handleSeed() {
  try {
    await ElMessageBox.confirm('将灌入演示部门、成员、文档、知识关系与对话数据。真实数据会被保留，演示数据带独立标记，之后可一键清除。', '进入演示模式', {
      confirmButtonText: '灌入演示数据',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
  seeding.value = true
  try {
    const res = await seedDemo(true)
    ElMessage.success(`演示数据已灌入：${res.documents} 份文档、${res.users} 位成员、${res.entities} 个实体`)
    await loadStatus()
  } catch {
    // 拦截器已提示
  } finally {
    seeding.value = false
  }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('将清除所有演示数据（仅演示标记数据，不影响真实数据）。确定继续吗？', '退出演示模式', {
      confirmButtonText: '清除演示数据',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  clearing.value = true
  try {
    const res = await clearDemo()
    ElMessage.success(`已清除演示数据：移除 ${res.removed_documents} 份文档、${res.removed_users} 位成员`)
    await loadStatus()
  } catch {
    // 拦截器已提示
  } finally {
    clearing.value = false
  }
}

function goTour(path: string) {
  router.push(path)
}

onMounted(() => {
  loadStatus()
})
</script>

<template>
  <div class="ks-page demo-page">
    <div class="ks-page-title">
      <h2><el-icon class="demo-title-icon"><MagicStick /></el-icon>演示模式</h2>
      <p class="ks-muted">一键灌入演示数据，30 秒体验知寻 KnowSeek 全部亮点能力 · 随时一键清除恢复</p>
    </div>

    <!-- 状态条 -->
    <div class="demo-status-bar" :class="status?.active ? 'active' : ''">
      <el-icon class="ds-icon">
        <Loading v-if="loading" class="is-loading" />
        <Check v-else-if="status?.active" />
        <MagicStick v-else />
      </el-icon>
      <div class="ds-main">
        <b>{{ status?.active ? '演示模式运行中' : '演示模式未开启' }}</b>
        <span v-if="status?.active && status.seeded_at">灌入时间 {{ (status.seeded_at || '').replace('T', ' ').slice(0, 19) }} · 演示部门 {{ status.counts.departments }} · 成员 {{ status.counts.users }} · 文档 {{ status.counts.documents }}</span>
        <span v-else>点击下方按钮一键灌入演示数据，快速了解产品能力</span>
      </div>
      <template v-if="status?.active">
        <el-button type="danger" plain :icon="Delete" :loading="clearing" @click="handleClear">一键清除恢复</el-button>
      </template>
      <template v-else>
        <el-button type="primary" :icon="MagicStick" :loading="seeding" @click="handleSeed">一键灌入演示数据</el-button>
      </template>
    </div>

    <!-- 流程步骤 -->
    <div class="demo-steps">
      <div v-for="(s, i) in steps" :key="s.key" class="demo-step">
        <div class="demo-step-no">{{ i + 1 }}</div>
        <div class="demo-step-main">
          <b>{{ s.title }}</b>
          <span>{{ s.desc }}</span>
        </div>
      </div>
    </div>

    <!-- 亮点功能导览 -->
    <div class="ks-card demo-highlights">
      <div class="insight-head">
        <h3>六大差异化亮点</h3>
        <span class="insight-total">点击卡片直接前往体验</span>
      </div>
      <div class="highlight-grid">
        <div v-for="h in highlights" :key="h.path" class="highlight-card" @click="goTour(h.path)">
          <div class="highlight-icon"><el-icon><component :is="h.icon" /></el-icon></div>
          <div class="highlight-main">
            <b>{{ h.title }}</b>
            <span>{{ h.desc }}</span>
          </div>
          <span class="highlight-go">前往 →</span>
        </div>
      </div>
    </div>

    <!-- 数据说明 -->
    <div class="demo-note">
      <el-icon><DataAnalysis /></el-icon>
      <div>
        <b>数据隔离说明</b>
        <p>演示数据带有独立标记，清除操作仅删除演示标记的数据，绝不会触碰或影响你的真实文档、对话与用户数据。灌入前可选择保留原数据，亦可随时清除恢复原状。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.demo-page {
  max-width: 1180px;
}

.demo-title-icon {
  vertical-align: -3px;
  color: var(--ks-primary);
}

.demo-status-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 14px;
  background: linear-gradient(140deg, rgba(37, 99, 235, 0.08), rgba(124, 58, 237, 0.05));
  border: 1px solid rgba(37, 99, 235, 0.16);
}

.demo-status-bar.active {
  background:
    radial-gradient(420px 120px at 92% -20px, rgba(16, 185, 129, 0.22), transparent 60%),
    linear-gradient(140deg, rgba(16, 185, 129, 0.08), rgba(37, 99, 235, 0.05));
  border-color: rgba(16, 185, 129, 0.28);
}

.ds-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 12px;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ks-primary);
  background: rgba(37, 99, 235, 0.1);
}

.demo-status-bar.active .ds-icon {
  color: #10b981;
  background: rgba(16, 185, 129, 0.12);
}

.ds-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ds-main b {
  font-size: 15px;
  color: var(--ks-text-title);
}

.ds-main span {
  font-size: 12px;
  color: var(--ks-text-muted);
}

.demo-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 16px;
}

.demo-step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.9), rgba(248, 251, 255, 0.7));
  border: 1px solid rgba(99, 102, 241, 0.12);
}

.demo-step-no {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
}

.demo-step-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.demo-step-main b {
  font-size: 13px;
  color: var(--ks-text-title);
}

.demo-step-main span {
  font-size: 11px;
  line-height: 1.5;
  color: var(--ks-text-muted);
}

.demo-highlights {
  margin-top: 16px;
}

.insight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.insight-head h3 {
  font-size: 15px;
  color: var(--ks-text-title);
  margin: 0;
}

.insight-total {
  font-size: 12px;
  color: var(--ks-text-muted);
}

.highlight-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.highlight-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  cursor: pointer;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.9), rgba(248, 251, 255, 0.65));
  border: 1px solid rgba(99, 102, 241, 0.14);
  transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.24s ease, border-color 0.24s ease;
}

.highlight-card:hover {
  transform: translateY(-4px);
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow: 0 14px 30px -10px rgba(37, 99, 235, 0.22);
}

.highlight-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 6px 14px -4px rgba(37, 99, 235, 0.5);
}

.highlight-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.highlight-main b {
  font-size: 13px;
  color: var(--ks-text-title);
}

.highlight-main span {
  font-size: 11px;
  line-height: 1.5;
  color: var(--ks-text-muted);
}

.highlight-go {
  font-size: 12px;
  color: var(--ks-primary);
  flex-shrink: 0;
  font-weight: 600;
}

.demo-note {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.18);
  color: var(--ks-text-body);
  font-size: 12px;
}

.demo-note .el-icon {
  font-size: 22px;
  color: #10b981;
  flex-shrink: 0;
  margin-top: 2px;
}

.demo-note b {
  color: var(--ks-text-title);
}

.demo-note p {
  margin: 3px 0 0;
  line-height: 1.6;
  color: var(--ks-text-muted);
}

@media (max-width: 768px) {
  .demo-steps {
    grid-template-columns: 1fr 1fr;
  }

  .highlight-grid {
    grid-template-columns: 1fr;
  }

  .demo-status-bar {
    flex-wrap: wrap;
  }

  .demo-status-bar .el-button {
    width: 100%;
  }
}
</style>
