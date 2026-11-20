<script setup lang="ts">
/**
 * AI 周报：选周期 → LLM 生成 → 预览 / 复制 / 导出
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, CopyDocument, Download, Document as DocIcon } from '@element-plus/icons-vue'
import { getReportTemplate, generateWeeklyReport, type ReportTemplate, type WeeklyReport } from '@/api/report'
import { getLlmStatus, type LlmStatus } from '@/api/chat'

const loading = ref(false)
const template = ref<ReportTemplate | null>(null)
const report = ref<WeeklyReport | null>(null)

const form = reactive({
  period: 'week',
  customRange: [] as string[],
  focus: '',
})

/** 模型供应商选择（null=使用默认） */
const llmStatus = ref<LlmStatus | null>(null)
const selectedProviderId = ref<number | null>(null)

async function loadProviders() {
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
}

const periodLabel = computed(() => {
  const p = form.period
  if (p === 'week') return '本周'
  if (p === 'last_week') return '上周'
  if (p === '7d') return '近 7 天'
  if (p === 'custom') return '自定义周期'
  return p
})

async function loadTemplate() {
  try {
    template.value = await getReportTemplate()
  } catch {
    // 拦截器已提示
  }
}

async function generate() {
  if (form.period === 'custom' && (!form.customRange || form.customRange.length !== 2)) {
    ElMessage.warning('请选择自定义周期的开始与结束日期')
    return
  }
  loading.value = true
  report.value = null
  try {
    report.value = await generateWeeklyReport({
      period: form.period,
      start_date: form.period === 'custom' ? form.customRange[0] : undefined,
      end_date: form.period === 'custom' ? form.customRange[1] : undefined,
      focus: form.focus.trim() || undefined,
      model_provider_id: selectedProviderId.value,
    })
    ElMessage.success('周报已生成')
  } catch {
    // 拦截器已提示（超时请稍后重试）
  } finally {
    loading.value = false
  }
}

async function copyReport() {
  if (!report.value) return
  try {
    await navigator.clipboard.writeText(report.value.markdown)
    ElMessage.success('已复制 Markdown 周报')
  } catch {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

function exportReport(type: 'md' | 'html') {
  if (!report.value) return
  const content = type === 'md' ? report.value.markdown : report.value.html
  const blob = new Blob([content], { type: type === 'md' ? 'text/markdown;charset=utf-8' : 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const label = `知寻周报_${report.value.period_label.replace(/\s+/g, '_')}`
  a.href = url
  a.download = `${label}.${type === 'md' ? 'md' : 'html'}`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => { loadTemplate(); loadProviders() })
</script>

<template>
  <div class="ks-page report-page">
    <div class="ks-page-title">
      <h2>AI 周报生成</h2>
      <p class="ks-muted">基于 LangChain/LangGraph 聚合知识库 · 对话 · Agent · 组织数据，一键生成企业周报草稿</p>
    </div>

    <div class="report-layout">
      <!-- 配置区 -->
      <div class="ks-card report-config">
        <h3>1. 选择统计周期</h3>
        <div class="period-group">
          <el-radio-group v-model="form.period">
            <el-radio-button value="week">本周</el-radio-button>
            <el-radio-button value="last_week">上周</el-radio-button>
            <el-radio-button value="7d">近 7 天</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
          <el-date-picker
            v-if="form.period === 'custom'"
            v-model="form.customRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="custom-range"
          />
        </div>

        <h3>2. 生成模型（可选，不选择使用默认）</h3>
        <el-select
          v-model="selectedProviderId"
          placeholder="默认模型"
          clearable
          class="custom-range"
        >
          <el-option
            v-for="p in llmStatus?.providers || []"
            :key="p.id"
            :label="`${p.name} · ${p.model}`"
            :value="p.id"
          />
        </el-select>

        <h3>3. 补充关注点（可选）</h3>
        <el-input
          v-model="form.focus"
          type="textarea"
          :rows="3"
          maxlength="300"
          show-word-limit
          placeholder="例如：重点总结本周知识库使用情况、Agent 任务完成度、需关注的风险点"
        />

        <el-button
          type="primary"
          size="large"
          :icon="MagicStick"
          :loading="loading"
          class="generate-btn"
          @click="generate"
        >
          {{ loading ? '正在生成…' : `生成${periodLabel}周报` }}
        </el-button>

        <div class="report-tpl">
          <div class="tpl-title"><el-icon><DocIcon /></el-icon> 预置模板骨架</div>
          <div v-if="template" class="tpl-sections">
            <div v-for="s in template.sections" :key="s.title" class="tpl-item">
              <b>{{ s.title }}</b>
              <span>{{ s.desc }}</span>
            </div>
          </div>
          <div v-else class="ks-muted">模板加载中…</div>
        </div>
      </div>

      <!-- 预览区 -->
      <div class="ks-card report-preview">
        <div class="preview-head">
          <h3>周报预览</h3>
          <div v-if="report" class="preview-actions">
            <el-button :icon="CopyDocument" size="small" @click="copyReport">复制 Markdown</el-button>
            <el-button :icon="Download" size="small" @click="exportReport('md')">导出 .md</el-button>
            <el-button :icon="Download" size="small" @click="exportReport('html')">导出 .html</el-button>
          </div>
        </div>
        <div v-loading="loading" class="preview-body">
          <template v-if="report">
            <div class="report-meta">
              <span>统计周期：{{ report.period_label }}</span>
              <span>生成方式：{{ report.source === 'llm' ? '大模型智能生成' : '模板骨架（LLM 不可用降级）' }}</span>
              <span>生成时间：{{ report.generated_at }}</span>
            </div>
            <div class="report-html" v-html="report.html"></div>
            <details class="md-source">
              <summary>查看 Markdown 源码</summary>
              <pre>{{ report.markdown }}</pre>
            </details>
          </template>
          <div v-else-if="!loading" class="ks-empty">选择周期后点击生成，周报草稿将在此预览</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}
.report-layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  align-items: start;
}
.report-config,
.report-preview {
  padding: 18px 20px;
}
.report-config h3,
.report-preview h3 {
  margin: 0 0 10px;
  font-size: 15px;
  color: var(--ks-text-primary, #0f172a);
}
.report-config h3:not(:first-child) {
  margin-top: 18px;
}
.period-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}
.custom-range {
  width: 100%;
}
.generate-btn {
  width: 100%;
  margin-top: 18px;
}
.report-tpl {
  margin-top: 18px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(100, 116, 139, 0.06);
}
.tpl-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
}
.tpl-sections {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tpl-item {
  display: flex;
  flex-direction: column;
  font-size: 12px;
}
.tpl-item b {
  color: var(--ks-primary, #2563eb);
}
.tpl-item span {
  color: var(--ks-text-secondary, #64748b);
}
.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.preview-body {
  min-height: 320px;
  border-radius: 10px;
  border: 1px solid rgba(100, 116, 139, 0.15);
  padding: 16px;
}
.report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--ks-text-secondary, #64748b);
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(100, 116, 139, 0.2);
  margin-bottom: 12px;
}
.report-html {
  font-size: 14px;
  line-height: 1.75;
  color: var(--ks-text-primary, #0f172a);
}
.report-html :deep(h1) {
  font-size: 20px;
  margin: 4px 0 12px;
}
.report-html :deep(h2) {
  font-size: 16px;
  margin: 14px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(100, 116, 139, 0.15);
}
.report-html :deep(h3) {
  font-size: 14px;
  margin: 10px 0 6px;
}
.report-html :deep(ul) {
  padding-left: 20px;
  margin: 6px 0;
}
.report-html :deep(table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
  margin: 8px 0;
}
.report-html :deep(th),
.report-html :deep(td) {
  border: 1px solid rgba(100, 116, 139, 0.25);
  padding: 6px 8px;
}
.report-html :deep(blockquote) {
  border-left: 3px solid var(--ks-primary, #2563eb);
  padding: 4px 12px;
  margin: 8px 0;
  color: var(--ks-text-secondary, #64748b);
  background: rgba(37, 99, 235, 0.05);
}
.md-source summary {
  cursor: pointer;
  font-size: 13px;
  color: var(--ks-text-secondary, #64748b);
  margin-top: 14px;
}
.md-source pre {
  max-height: 320px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.05);
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
@media (max-width: 960px) {
  .report-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 768px) {
  .report-page {
    padding: 14px;
  }
  .report-config,
  .report-preview {
    padding: 14px;
  }
  .preview-actions {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
  }
}
@media (max-width: 375px) {
  .period-group :deep(.el-radio-button__inner) {
    padding: 8px 12px;
    font-size: 12px;
  }
  .report-html {
    font-size: 13px;
  }
}
</style>
