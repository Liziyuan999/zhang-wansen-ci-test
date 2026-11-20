<script setup lang="ts">
/**
 * 文档库页：上传（四阶段进度轮询）/ 多版本 / 标签 / 筛选 / 删除 / 下载 / 导出
 */
// ===== 逐行注释：文档库页核心逻辑（script setup） =====
// 1. 列表与筛选：loadList 组装 keyword/file_type/status/tag 筛选参数请求分页列表；
//    filters 为响应式筛选条件，tag 以逗号拼接传给后端（后端按标签交集过滤）。
// 2. 上传流程（handleUpload 等）：上传后返回 doc_id，随即启动四阶段进度轮询
//    （pending/processing/success/failed），配合 UploadProgress 组件展示解析进度，
//    完成后自动刷新列表并支持继续追加标签。
// 3. 版本管理：选中文档后 getDocumentDetail 加载详情，uploadVersion 上传新版本
//    （后端对同一 origin_file_name 自动 version_no+1），历史版本列表可回看。
// 4. Copilot 联动：鼠标划选正文片段 captureSelection 捕获选区文本，
//    copilotSelected 传给 CopilotPanel 组件做选中片段问答/改写。
// 5. 其他操作：assignTags 打标签、updateDocMeta 改名、deleteDocument 删除（软删除）、
//    reprocessDocument 失败重试重新解析、downloadDocument 下载（Blob 触发浏览器保存）、
//    exportDocuments 导出清单 xlsx（后端生成文件后前端再下载）。
// ===== 逐行注释：筛选状态与选项 =====
// - fileTypeOptions：前端展示允许上传的扩展名集合（与后端 ALLOWED_FILE_TYPES 对齐）。
// - statusOptions：解析状态筛选项（processing 解析中 / success 成功 / failed 失败 / pending 待处理）。
// - tagOptions：部门内全部标签，下拉多选后自动触发 loadList 刷新。
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { Search, Refresh, Upload, Download, Delete, FolderOpened, Connection } from '@element-plus/icons-vue'
import {
  listDocuments,
  uploadDocument,
  uploadVersion,
  getDocumentDetail,
  downloadDocument,
  deleteDocument,
  reprocessDocument,
  exportDocuments,
  assignTags,
  updateDocMeta,
} from '@/api/document'
import { collectTags } from '@/api/tag'
import UploadProgress from '@/components/UploadProgress.vue'
import CopilotPanel from '@/components/CopilotPanel.vue'
import type { DocDetail, DocListItem } from '@/types'

/* ---------------- AI Copilot 选中片段（功能三） ---------------- */
const copilotSelected = ref('')

function captureSelection() {
  const sel = window.getSelection()
  const text = sel?.toString().trim() || ''
  if (text) {
    copilotSelected.value = text.slice(0, 2000)
  }
}

function clearCopilotSelection() {
  copilotSelected.value = ''
  window.getSelection()?.removeAllRanges()
}

/* ---------------- 列表与筛选 ---------------- */
const loading = ref(false)
const list = ref<DocListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)

const filters = reactive({
  keyword: '',
  file_type: '',
  status: '',
  tags: [] as string[],
})

const fileTypeOptions = ['pdf', 'docx', 'pptx', 'xlsx', 'txt', 'md', 'csv', 'png', 'jpg', 'jpeg']
const statusOptions = [
  { label: '解析中', value: 'processing' },
  { label: '解析成功', value: 'success' },
  { label: '解析失败', value: 'failed' },
  { label: '待处理', value: 'pending' },
]

const tagOptions = ref<string[]>([])

async function loadList() {
  loading.value = true
  try {
    const params = {
      keyword: filters.keyword || undefined,
      file_type: filters.file_type || undefined,
      status: filters.status || undefined,
      tag: filters.tags.length ? filters.tags.join(',') : undefined,
      page: page.value,
      page_size: pageSize.value,
    }
    const res = await listDocuments(params)
    list.value = res.items
    total.value = res.total
    const tags = collectTags(res.items)
    if (tags.length) tagOptions.value = Array.from(new Set([...tagOptions.value, ...tags]))
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadList()
}

function handleReset() {
  filters.keyword = ''
  filters.file_type = ''
  filters.status = ''
  filters.tags = []
  page.value = 1
  loadList()
}

function handlePageChange(p: number) {
  page.value = p
  loadList()
}

/* ---------------- 上传与进度 ---------------- */
const progressDialog = ref(false)
const progressDocId = ref(0)
const progressDocName = ref('')

const uploadRef = ref()
// ===== 逐行注释：上传与解析进度（customUpload / UploadProgress 联动） =====
// 1. customUpload：Element Plus 上传组件的自定义上传函数——不走组件内置请求，
//    改为调用 uploadDocument（FormData multipart）以便统一注入鉴权头与错误拦截。
// 2. 上传成功：记录 doc_id / doc_name，打开进度弹窗（progressDialog）由 UploadProgress
//    组件按四阶段轮询后端进度（pending -> processing(progress 百分比) -> success/failed）。
// 3. clearFiles：无论成败都清空上传组件缓存文件，避免重复选择同一文件不触发 change。
// 4. onUploadFinished：进度完成后关闭弹窗、刷新列表；若正在查看的详情恰是刚上传的文档，
//    同步 loadDetail 刷新详情内容（解析出的正文/标签/图谱状态）。
// 5. retryParse / manualReparse：失败重试——调 reprocessDocument 触发后端清空旧切片重新解析，
//    然后重开进度弹窗继续轮询；manualReparse 为详情页内的"人工解析"兜底按钮。
// 6. handleDetailDownload：Blob 下载——后端返回二进制流，前端创建 ObjectURL 触发浏览器保存，
//    文件名回退 origin_file_name，最后 revokeObjectURL 释放内存。
function customUpload(options: UploadRequestOptions) {
  const file = options.file as File
  uploadDocument(file)
    .then((doc) => {
      progressDocId.value = doc.id
      progressDocName.value = doc.doc_name || file.name
      progressDialog.value = true
    })
    .catch(() => {
      // 拦截器已提示
    })
    .finally(() => {
      uploadRef.value?.clearFiles()
    })
}

function onUploadFinished(doc: DocDetail) {
  progressDialog.value = false
  loadList()
  if (doc.id === detail.value?.id) loadDetail()
}

/** 失败重试：触发重新解析，并重新打开进度弹窗轮询 */
async function retryParse(docId: number, docName: string) {
  try {
    await reprocessDocument(docId)
    ElMessage.success('已触发重新解析，正在后台处理')
    progressDocId.value = docId
    progressDocName.value = docName
    progressDialog.value = false
    // 待弹窗完全关闭后重新打开，触发 open() 重置状态并重新轮询
    setTimeout(() => {
      progressDialog.value = true
    }, 100)
  } catch {
    // 拦截器已提示
  }
}

function retryDetail() {
  if (!detail.value) return
  detailVisible.value = false
  retryParse(detail.value.id, detail.value.doc_name)
}

/** 跳转知识图谱页并聚焦当前文档 */
const router = useRouter()
function goKnowledgeGraph() {
  if (!detail.value) return
  router.push({ path: '/knowledge-graph', query: { doc_id: detail.value.id } })
}

/** 人工解析：文档自动解析失败 / 内容不出现时，手动触发解析兜底 */
const reprocessing = ref(false)
async function manualReparse() {
  if (!detail.value || reprocessing.value) return
  reprocessing.value = true
  try {
    await reprocessDocument(detail.value.id)
    ElMessage.success('已提交人工解析，完成后将自动刷新')
    await loadDetail()
  } catch {
    // 拦截器已提示
  } finally {
    reprocessing.value = false
  }
}

/** 详情页内下载 */
async function handleDetailDownload() {
  if (!detail.value) return
  try {
    const blob = await downloadDocument(detail.value.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = detail.value.origin_file_name || `${detail.value.doc_name}.${detail.value.file_type}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch {
    ElMessage.error('下载失败，请检查后端文件是否仍存在')
  }
}

/** 详情页内删除 */
async function handleDetailDelete() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(`确定删除文档「${detail.value.doc_name}」及其全部版本吗？`, '删除文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteDocument(detail.value.id)
    ElMessage.success('已删除')
    detailVisible.value = false
    loadList()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 详情 ---------------- */
const detailVisible = ref(false)
const detail = ref<DocDetail | null>(null)
const detailLoading = ref(false)
const ocrExpanded = ref(false)
const extractExpanded = ref(false)
const previewExpanded = ref(true)

// ===== 逐行注释：文档详情抽屉（openDetail / loadDetail） =====
// 1. openDetail：打开抽屉并重置展开态——先置 detail=null + 三个折叠区全收起
//    （预览展开、OCR 折叠、图谱抽取折叠），再请求详情避免旧数据闪现。
// 2. 详情返回 DocDetail：含正文预览 preview、OCR 文本 ocr_text、抽取实体/关系
//    extract_entities/extract_relations、切片列表 chunks、版本历史 versions 等。
// 3. loadDetail：详情已在展示时静默刷新（如人工解析完成后重拉状态），不重置折叠态。
// 4. formatSize：字节数人性化格式化（B/KB/MB 三级），用于列表与详情的大小展示。
async function openDetail(docId: number) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  ocrExpanded.value = false
  extractExpanded.value = false
  previewExpanded.value = true
  try {
    detail.value = await getDocumentDetail(docId)
  } catch {
    // 拦截器已提示
  } finally {
    detailLoading.value = false
  }
}

async function loadDetail() {
  if (!detail.value) return
  try {
    detail.value = await getDocumentDetail(detail.value.id)
  } catch {
    // 忽略
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function formatTime(t?: string | null) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

/* ---------------- 下载 / 导出 ---------------- */
async function handleDownload(doc: DocListItem) {
  try {
    const blob = await downloadDocument(doc.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.origin_file_name || `${doc.doc_name}.${doc.file_type}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch {
    ElMessage.error('下载失败，请检查后端文件是否仍存在')
  }
}

async function handleExport() {
  try {
    // 后端 download=true 回传 xlsx 二进制，前端按 Blob 落地保存（原实现只提示服务器路径，用户无法取得文件）
    const blob = await exportDocuments({
      keyword: filters.keyword || undefined,
      file_type: filters.file_type || undefined,
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `文档清单_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功，文件已保存到本地下载目录')
  } catch {
    ElMessage.error('导出失败，请稍后重试')
  }
}

/* ---------------- 删除 ---------------- */
async function handleDelete(doc: DocListItem) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${doc.doc_name}」及其全部版本吗？`, '删除文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteDocument(doc.id)
    ElMessage.success('已删除')
    if (list.value.length === 1 && page.value > 1) page.value -= 1
    loadList()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 标签编辑 ---------------- */
const tagDialogVisible = ref(false)
const tagTarget = ref<DocListItem | null>(null)
const tagInput = ref<string[]>([])

function openTagDialog(doc: DocListItem) {
  tagTarget.value = doc
  tagInput.value = [...(doc.tags || [])]
  tagDialogVisible.value = true
}

async function saveTags() {
  if (!tagTarget.value) return
  try {
    await assignTags(tagTarget.value.id, tagInput.value)
    ElMessage.success('标签已更新')
    tagDialogVisible.value = false
    loadList()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 版本上传 ---------------- */
const versionDialogVisible = ref(false)
const versionTarget = ref<DocListItem | null>(null)
const versionUploadRef = ref()

function openVersionDialog(doc: DocListItem) {
  versionTarget.value = doc
  versionDialogVisible.value = true
}

function customVersionUpload(options: UploadRequestOptions) {
  if (!versionTarget.value) return
  const file = options.file as File
  uploadVersion(versionTarget.value.id, file)
    .then((res) => {
      ElMessage.success(`新版本 v${res.version_no} 上传成功，后台解析中`)
      versionDialogVisible.value = false
      loadList()
    })
    .catch(() => {
      // 拦截器已提示
    })
    .finally(() => {
      versionUploadRef.value?.clearFiles()
    })
}

function statusTag(status: string) {
  const map: Record<string, string> = {
    success: 'success',
    processing: 'primary',
    pending: 'info',
    failed: 'danger',
  }
  return (map[status] || 'info') as 'success' | 'primary' | 'info' | 'danger'
}

onMounted(loadList)
onBeforeUnmount(() => {
  // 页面卸载清理
})
</script>

<template>
  <div class="ks-page">
    <div class="page-header">
      <h2 class="ks-page-title">文档库</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadList">刷新</el-button>
        <el-button :icon="Download" @click="handleExport">导出清单</el-button>
        <el-button type="primary" :icon="Upload" @click="uploadRef?.$el?.querySelector('input')?.click()">
          上传文档
        </el-button>
        <el-upload
          ref="uploadRef"
          :show-file-list="false"
          :http-request="customUpload"
          accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.png,.jpg,.jpeg"
          style="display: none"
        />
      </div>
    </div>

    <div class="ks-card filter-bar">
      <el-input
        v-model="filters.keyword"
        placeholder="按文件名 / 内容关键词搜索"
        clearable
        style="width: 260px"
        :prefix-icon="Search"
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filters.file_type" placeholder="文件类型" clearable style="width: 140px">
        <el-option v-for="t in fileTypeOptions" :key="t" :label="t.toUpperCase()" :value="t" />
      </el-select>
      <el-select v-model="filters.status" placeholder="解析状态" clearable style="width: 140px">
        <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select
        v-model="filters.tags"
        placeholder="标签（多选）"
        multiple
        clearable
        collapse-tags
        style="width: 220px"
      >
        <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
      </el-select>
      <el-button class="search-btn" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <div v-loading="loading">
      <div v-if="list.length" class="doc-grid">
        <div v-for="(doc, idx) in list" :key="doc.id" class="doc-card" :style="{ '--idx': idx }">
          <div class="doc-card-head">
            <span class="doc-type">{{ doc.file_type.toUpperCase() }}</span>
            <el-tag :type="statusTag(doc.status)" size="small" effect="light" class="doc-status">{{ doc.status }}</el-tag>
          </div>

          <div class="doc-card-title" :title="doc.doc_name" @click="openDetail(doc.id)">
            <el-icon class="doc-icon"><FolderOpened /></el-icon>
            <span>{{ doc.doc_name }}</span>
          </div>

          <div v-if="doc.status === 'processing'" class="doc-progress">
            <el-progress :percentage="doc.progress" :stroke-width="6" :show-text="false" />
            <span class="ks-muted">{{ doc.progress }}% · 解析中</span>
          </div>
          <div v-else-if="doc.status === 'failed'" class="doc-fail">
            <span class="fail-text">解析失败</span>
            <el-button size="small" type="danger" text @click.stop="retryParse(doc.id, doc.doc_name)">
              人工解析
            </el-button>
          </div>

          <div class="doc-meta">
            <span>v{{ doc.version_no }}</span>
            <span>{{ formatSize(doc.file_size) }}</span>
            <span>{{ formatTime(doc.update_time) }}</span>
          </div>

          <div v-if="doc.tags.length" class="doc-tags">
            <el-tag v-for="t in doc.tags" :key="t" size="small" type="primary" effect="plain">{{ t }}</el-tag>
          </div>
          <div v-else class="ks-muted">暂无标签</div>

          <div class="doc-card-actions">
            <el-button size="small" class="act-btn act-primary" text @click="openDetail(doc.id)">详情</el-button>
            <el-button size="small" class="act-btn" text @click="openTagDialog(doc)">标签</el-button>
            <el-button size="small" class="act-btn" text @click="openVersionDialog(doc)">新版本</el-button>
            <el-button size="small" class="act-btn" text @click="handleDownload(doc)">下载</el-button>
            <span class="act-divider"></span>
            <el-button size="small" class="act-btn act-danger" text @click="handleDelete(doc)">删除</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else-if="!loading" description="暂无文档，点击右上角上传" />

      <div v-if="total > pageSize" class="pager">
        <el-pagination
          layout="total, prev, pager, next, jumper"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          background
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 上传解析进度 -->
    <UploadProgress
      v-model="progressDialog"
      :doc-id="progressDocId"
      :doc-name="progressDocName"
      @finished="onUploadFinished"
    />

    <!-- 详情弹窗（企业化） -->
    <el-dialog v-model="detailVisible" append-to-body width="1180px" class="detail-dialog">
      <div v-loading="detailLoading" class="detail-body detail-body-copilot">
        <div class="detail-main">
        <template v-if="detail">
          <div class="doc-detail-hero" :class="detail.status">
            <div class="ddh-icon"><el-icon><FolderOpened /></el-icon></div>
            <div class="ddh-main">
              <div class="ddh-title">{{ detail.doc_name }}</div>
              <div class="ddh-sub">
                <el-tag :type="statusTag(detail.status)" size="small" effect="light">
                  {{ detail.status === 'success' ? '解析成功' : detail.status === 'failed' ? '解析失败' : detail.status === 'processing' ? '解析中' : '待处理' }}
                </el-tag>
                <span class="ddh-badge">{{ detail.file_type.toUpperCase() }}</span>
                <span class="ddh-meta">v{{ detail.version_no }} · {{ formatSize(detail.file_size) }}</span>
              </div>
              <div v-if="detail.status === 'processing'" class="ddh-progress">
                <el-progress :percentage="detail.progress" :stroke-width="6" style="width: 200px" />
              </div>
            </div>
            <div class="ddh-actions">
              <el-button size="small" :icon="Refresh" @click="loadDetail">刷新</el-button>
              <el-button size="small" :icon="Connection" @click="goKnowledgeGraph">知识图谱</el-button>
              <el-button
                size="small"
                type="primary"
                :icon="Refresh"
                :loading="reprocessing"
                :disabled="detail.status === 'processing' || detail.status === 'pending'"
                @click="manualReparse"
              >
                人工解析
              </el-button>
            </div>
          </div>

          <el-descriptions :column="2" border class="ddh-desc">
            <el-descriptions-item label="文档名称">{{ detail.doc_name }}</el-descriptions-item>
            <el-descriptions-item label="原始文件">{{ detail.origin_file_name }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ detail.file_type.toUpperCase() }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatSize(detail.file_size) }}</el-descriptions-item>
            <el-descriptions-item label="当前版本">v{{ detail.version_no }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(detail.status)" size="small">{{ detail.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatTime(detail.create_time) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(detail.update_time) }}</el-descriptions-item>
            <el-descriptions-item label="版本历史">
              <span v-for="v in detail.versions" :key="v" class="version-badge">v{{ v }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="标签">
              <el-tag v-for="t in detail.tags" :key="t" size="small" type="primary" effect="plain" class="dt-tag">
                {{ t }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <div class="detail-section">
            <div class="section-title">内容摘要</div>
            <div class="section-body">{{ detail.summary || '暂无摘要（解析完成后生成）' }}</div>
          </div>

          <!-- 正文预览：点击文档打开即可查看内部详细内容 -->
          <div class="detail-section" :class="{ 'preview-empty': !detail.content_preview }">
            <div class="section-title clickable" @click="previewExpanded = !previewExpanded">
              正文预览<span v-if="detail.content_pages" class="preview-pages">共 {{ detail.content_pages }} 段</span>（{{ previewExpanded ? '收起' : '展开' }}）
            </div>
            <div v-if="previewExpanded" class="preview-body">
              <pre v-if="detail.content_preview" class="preview-body-pre" @mouseup="captureSelection">{{ detail.content_preview }}</pre>
              <div v-else class="preview-placeholder">暂无正文内容（文档尚未解析或无可读文本）</div>
            </div>
          </div>

          <div v-if="detail.fail_msg" class="detail-section fail-box">
            <div class="section-title">失败原因</div>
            <div class="section-body">{{ detail.fail_msg }}</div>
            <div class="fail-retry-row">
              <el-button
                size="small"
                type="danger"
                plain
                :icon="Refresh"
                :loading="reprocessing"
                @click="manualReparse"
              >
                点击人工解析
              </el-button>
            </div>
          </div>

          <div v-if="detail.ocr_content" class="detail-section">
            <div class="section-title clickable" @click="ocrExpanded = !ocrExpanded">
              OCR 识别内容（{{ ocrExpanded ? '收起' : '展开' }}）
            </div>
            <div v-if="ocrExpanded" class="section-body mono">{{ detail.ocr_content }}</div>
          </div>

          <div v-if="detail.extract_result" class="detail-section">
            <div class="section-title clickable" @click="extractExpanded = !extractExpanded">
              结构化抽取结果（{{ extractExpanded ? '收起' : '展开' }}）
            </div>
            <div v-if="extractExpanded" class="section-body mono">
              {{ JSON.stringify(detail.extract_result, null, 2) }}
            </div>
          </div>
        </template>
        </div>
        <div v-if="detail" class="detail-copilot">
          <CopilotPanel
            :doc-id="detail.id"
            :doc-name="detail.doc_name"
            :selected-text="copilotSelected"
            @clear-selected="clearCopilotSelection"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button :icon="Download" @click="handleDetailDownload">下载</el-button>
        <el-button type="danger" plain @click="handleDetailDelete">删除</el-button>
      </template>
    </el-dialog>

    <!-- 标签编辑弹窗 -->
    <el-dialog v-model="tagDialogVisible" append-to-body title="编辑标签" width="460px">
      <el-select
        v-model="tagInput"
        multiple
        filterable
        allow-create
        default-first-option
        placeholder="输入或选择标签，回车创建"
        style="width: 100%"
      >
        <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
      </el-select>
      <template #footer>
        <el-button @click="tagDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTags">保存</el-button>
      </template>
    </el-dialog>

    <!-- 版本上传弹窗 -->
    <el-dialog v-model="versionDialogVisible" append-to-body title="上传新版本" width="460px">
      <p class="version-tip">
        为文档「{{ versionTarget?.doc_name }}」上传新版本，上传后将在后台重新解析。
      </p>
      <el-upload
        ref="versionUploadRef"
        drag
        :show-file-list="true"
        :http-request="customVersionUpload"
        accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.png,.jpg,.jpeg"
        style="width: 100%"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击选择文件</em></div>
      </el-upload>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 18px;
  border-radius: var(--ks-card-radius);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.8), rgba(248, 251, 255, 0.62));
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  padding: 12px 14px;
}

/* 搜索按钮：去亮色，统一为浅色描边风格 */
.filter-bar .search-btn.el-button {
  color: var(--ks-text-body);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(245, 249, 255, 0.78));
  border: 1px solid var(--el-border-color);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  transition: color 0.22s ease, border-color 0.22s ease, background 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
}

.filter-bar .search-btn.el-button:hover {
  color: var(--ks-primary);
  border-color: rgba(37, 99, 235, 0.32);
  background: var(--ks-primary-light);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.14);
  transform: translateY(-1px);
}

.filter-bar .search-btn.el-button:active {
  transform: translateY(0);
}

.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.doc-card {
  position: relative;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.8));
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-radius: var(--ks-card-radius);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid rgba(255, 255, 255, 0.8);
  transition: box-shadow 0.28s cubic-bezier(0.22, 1, 0.36, 1), transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.28s ease;
  animation: ks-card-enter 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: calc(var(--idx, 0) * 55ms);
  will-change: transform, opacity;
}

.doc-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: radial-gradient(420px 140px at 16% -8%, rgba(37, 99, 235, 0.14), transparent 72%),
    radial-gradient(300px 120px at 92% 108%, rgba(124, 58, 237, 0.1), transparent 70%);
  opacity: 0;
  transition: opacity 0.4s ease;
}

.doc-card:hover {
  transform: translateY(-6px);
  border-color: rgba(99, 102, 241, 0.35);
  box-shadow:
    0 20px 44px rgba(15, 23, 42, 0.1),
    0 8px 22px rgba(37, 99, 235, 0.12),
    0 0 0 1px rgba(99, 102, 241, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.96);
}

.doc-card:hover::before {
  opacity: 1;
}

.doc-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.doc-type {
  font-size: 12px;
  font-weight: 700;
  color: #1d4ed8;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-radius: 6px;
  padding: 3px 10px;
  letter-spacing: 0.4px;
}

.doc-status.el-tag {
  font-weight: 600;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.doc-status.el-tag--success {
  animation: ks-status-success 2.6s ease-in-out infinite;
}

.doc-status.el-tag--primary {
  animation: ks-tag-pulse 2.2s ease-in-out infinite;
}

.doc-status.el-tag--danger {
  color: #dc2626;
  border-color: rgba(239, 68, 68, 0.28);
  background: #fef2f2;
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.06);
}

.doc-card:hover .doc-status {
  transform: translateY(-1px);
}

.doc-card-title {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ks-text-title);
  cursor: pointer;
  word-break: break-all;
  line-height: 1.4;
  min-height: 42px;
}

.doc-card-title:hover {
  color: var(--ks-primary);
}

.doc-icon {
  color: var(--ks-primary);
  margin-top: 2px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-radius: 8px;
  padding: 3px;
  width: 22px;
  height: 22px;
  transition: transform 0.28s ease, color 0.28s ease, box-shadow 0.28s ease, background 0.28s ease;
}

.doc-card:hover .doc-icon {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  transform: rotate(-8deg) scale(1.14);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
}

.doc-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-progress .el-progress {
  flex: 1;
}

.doc-fail {
  font-size: 12px;
  color: var(--ks-danger);
  background: #fef2f2;
  border-radius: 4px;
  padding: 2px 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.doc-fail .fail-text {
  line-height: 1.5;
}

.doc-meta {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.doc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 24px;
}

.doc-card-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 10px;
  margin-top: auto;
}

.doc-card-actions .act-btn.el-button {
  height: 26px;
  padding: 3px 8px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.2px;
  transition: color 0.22s ease, background-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
}

.doc-card-actions .act-btn.el-button:hover {
  transform: translateY(-1px);
}

.doc-card-actions .act-btn.el-button:active {
  transform: translateY(0);
}

.doc-card-actions .act-btn.el-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
}

.doc-card-actions .act-btn.act-primary.el-button {
  color: var(--ks-primary);
  font-weight: 600;
}

.doc-card-actions .act-btn.act-primary.el-button:hover {
  color: var(--ks-primary);
  background: var(--ks-primary-light);
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.16);
}

.doc-card-actions .act-btn.el-button:not(.act-primary):not(.act-danger) {
  color: var(--ks-text-secondary);
}

.doc-card-actions .act-btn.el-button:not(.act-primary):not(.act-danger):hover {
  color: var(--ks-text-title);
  background: rgba(15, 23, 42, 0.05);
}

.doc-card-actions .act-divider {
  width: 1px;
  height: 14px;
  background: var(--el-border-color);
  margin: 0 4px;
  flex-shrink: 0;
}

.doc-card-actions .act-btn.act-danger.el-button {
  color: rgba(239, 68, 68, 0.55);
  font-weight: 500;
}

.doc-card-actions .act-btn.act-danger.el-button:hover {
  color: var(--ks-danger);
  background: var(--ks-danger-bg, #fef2f2);
  box-shadow: 0 2px 10px rgba(239, 68, 68, 0.14);
}

.pager {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 分页控件精细化：更精致页码/总数/跳页 */
.pager .el-pagination {
  --el-pagination-button-bg-color: #fff;
  --el-pagination-hover-color: #2563eb;
  font-variant-numeric: tabular-nums;
}

.pager .el-pagination .el-pagination__total {
  color: #64748b;
  font-size: 12px;
  margin-right: 8px;
}

.pager .el-pagination .el-pager li {
  border-radius: 8px;
  font-weight: 600;
  min-width: 30px;
  height: 30px;
  line-height: 28px;
  margin: 0 2px;
  border: 1px solid transparent;
  transition: all 0.18s;
}

.pager .el-pagination .el-pager li.is-active {
  background: linear-gradient(135deg, #2563eb, #4338ca);
  border-color: transparent;
  box-shadow: 0 4px 10px -3px rgba(37, 99, 235, 0.55);
  color: #fff;
}

.pager .el-pagination .el-pager li:not(.is-active):hover {
  color: #2563eb;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.pager .el-pagination .btn-prev,
.pager .el-pagination .btn-next {
  border-radius: 8px;
  min-width: 30px;
  height: 30px;
  margin: 0 2px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: all 0.18s;
}

.pager .el-pagination .btn-prev:not(.is-disabled):hover,
.pager .el-pagination .btn-next:not(.is-disabled):hover {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #2563eb;
}

.pager .el-pagination .el-pagination__jump {
  margin-left: 10px;
  color: #64748b;
  font-size: 12px;
}

.pager .el-pagination .el-pagination__jump .el-input__inner {
  border-radius: 8px;
  border-color: #e2e8f0;
  height: 30px;
  font-weight: 600;
}

.pager .el-pagination .el-pagination__jump .el-input__inner:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.detail-progress {
  margin-left: 8px;
  display: inline-block;
}

.version-badge {
  display: inline-block;
  background: var(--ks-primary-light);
  color: var(--ks-primary);
  border-radius: 4px;
  font-size: 12px;
  padding: 2px 6px;
  margin-right: 6px;
}

.dt-tag {
  margin-right: 4px;
}

.detail-section {
  margin-top: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-title);
  margin-bottom: 8px;
}

.section-title.clickable {
  cursor: pointer;
  color: var(--ks-primary);
}

.section-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--ks-text-body);
  background: linear-gradient(160deg, #f8fbff 0%, #eef4ff 100%);
  border: 1px solid rgba(37, 99, 235, 0.08);
  border-radius: 8px;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.section-body.mono {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  max-height: 240px;
  overflow-y: auto;
}

.fail-box .section-title {
  color: var(--ks-danger);
}

.fail-retry-row {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.version-tip {
  color: var(--ks-text-body);
  font-size: 13px;
  margin-bottom: 14px;
}

@keyframes ks-card-enter {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes ks-status-success {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.3);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.06);
  }
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

  .filter-bar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .filter-bar .el-input,
  .filter-bar .el-select {
    flex: 1 1 100%;
  }

  .doc-grid {
    grid-template-columns: 1fr !important;
  }
}

/* ============ 详情弹窗企业化 ============ */
.detail-dialog .el-dialog__body {
  padding-top: 16px;
}

.doc-detail-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 14px;
  background:
    radial-gradient(520px 180px at 88% -30px, rgba(124, 58, 237, 0.4), transparent 60%),
    radial-gradient(420px 160px at 2% 115%, rgba(37, 99, 235, 0.42), transparent 55%),
    linear-gradient(135deg, #0b1730, #16306a 60%, #1e3a8a);
  border: 1px solid rgba(147, 197, 253, 0.24);
  box-shadow: 0 12px 28px -12px rgba(30, 58, 138, 0.55);
  color: #f8fafc;
}

.doc-detail-hero.failed {
  background:
    radial-gradient(520px 180px at 88% -30px, rgba(244, 63, 94, 0.32), transparent 60%),
    radial-gradient(420px 160px at 2% 115%, rgba(37, 99, 235, 0.35), transparent 55%),
    linear-gradient(135deg, #200f13, #3b1220 55%, #5b1a2e);
  border-color: rgba(251, 113, 133, 0.32);
}

.ddh-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  box-shadow: 0 8px 18px -6px rgba(0, 0, 0, 0.5);
}

.doc-detail-hero.failed .ddh-icon {
  background: linear-gradient(135deg, #fb7185, #dc2626);
}

.ddh-main {
  flex: 1;
  min-width: 0;
}

.ddh-title {
  font-size: 16px;
  font-weight: 800;
  color: #fff;
  word-break: break-all;
}

.ddh-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.ddh-badge {
  font-size: 11px;
  font-weight: 700;
  color: #dbeafe;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 6px;
  padding: 2px 8px;
  letter-spacing: 0.4px;
}

.ddh-meta {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.85);
}

.ddh-progress {
  margin-top: 8px;
}

.ddh-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

@media (max-width: 760px) {
  .ddh-actions {
    flex-wrap: wrap;
  }
}

/* 正文预览 */
.preview-pages {
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
}

.preview-body {
  max-height: 420px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px 14px;
}

.preview-body pre {
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.7;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-placeholder {
  color: #94a3b8;
  font-size: 13px;
  padding: 8px 2px;
}

.preview-empty .section-title {
  color: #94a3b8;
}

.ddh-desc {
  margin-bottom: 12px;
}

.summary-panel {
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.8));
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.summary-panel .section-title {
  color: var(--ks-primary);
  font-weight: 700;
}

.fail-retry-row {
  margin-top: 10px;
}

/* ============ AI Copilot 双栏详情（功能三） ============ */
.detail-body-copilot {
  display: flex;
  gap: 16px;
  height: 70vh;
  min-height: 0;
}

.detail-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.detail-copilot {
  width: 360px;
  flex-shrink: 0;
  min-width: 0;
  min-height: 0;
  border-left: 1px solid rgba(37, 99, 235, 0.12);
  padding-left: 14px;
  overflow: hidden;
  display: flex;
}

.preview-body-pre {
  user-select: text;
  cursor: text;
}

.preview-body-pre::selection {
  background: rgba(37, 99, 235, 0.22);
}

@media (max-width: 1024px) {
  .detail-body-copilot {
    flex-direction: column;
    height: auto;
  }

  .detail-copilot {
    width: auto;
    border-left: none;
    border-top: 1px solid rgba(37, 99, 235, 0.12);
    padding-left: 0;
    padding-top: 12px;
    overflow: visible;
    display: block;
  }

  .detail-main {
    max-height: none;
  }
}
</style>
