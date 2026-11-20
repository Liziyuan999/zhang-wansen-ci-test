<script setup lang="ts">
/**
 * 审计日志：管理视角，登录/检索/Agent/组织/文档/系统管理操作留痕查询
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { listAuditModules, listAuditLogs, type AuditLogItem, type AuditModuleOption } from '@/api/audit'

const loading = ref(false)
const items = ref<AuditLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const modules = ref<AuditModuleOption[]>([])
const filters = reactive({
  module: '',
  action: '',
  operator: '',
  dateRange: [] as string[],
  status: '',
})

const moduleOptions = computed(() => modules.value.map((m) => ({ label: m.module_label, value: m.module })))
const actionOptions = computed(() => {
  const m = modules.value.find((x) => x.module === filters.module)
  return m ? m.actions.map((a) => ({ label: a, value: a })) : []
})

async function loadModules() {
  try {
    modules.value = await listAuditModules()
  } catch {
    // 拦截器已提示
  }
}

async function load() {
  loading.value = true
  try {
    const res = await listAuditLogs({
      page: page.value,
      page_size: pageSize.value,
      module: filters.module || undefined,
      action: filters.action || undefined,
      operator: filters.operator.trim() || undefined,
      start: filters.dateRange?.[0] || undefined,
      end: filters.dateRange?.[1] || undefined,
      status: filters.status || undefined,
    })
    items.value = res.items
    total.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.module = ''
  filters.action = ''
  filters.operator = ''
  filters.dateRange = []
  filters.status = ''
  page.value = 1
  load()
}

function statusType(s: string) {
  if (s === 'success') return 'success'
  if (s === 'failure') return 'danger'
  return 'warning'
}

const detailVisible = ref(false)
const detailTarget = ref<AuditLogItem | null>(null)
function showDetail(item: AuditLogItem) {
  detailTarget.value = item
  detailVisible.value = true
}

function fmtTime(t: string) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '-'
}

onMounted(() => {
  loadModules()
  load()
})
</script>

<template>
  <div class="ks-page audit-page">
    <div class="ks-page-title">
      <h2>审计日志</h2>
      <p class="ks-muted">登录 · 检索 · Agent · 组织 · 文档 · 系统管理操作全留痕，支持组合筛选与分页</p>
    </div>

    <!-- 筛选区 -->
    <div class="ks-card audit-filters">
      <div class="filter-row">
        <el-select v-model="filters.module" placeholder="操作类型" clearable class="filter-item" @change="filters.action = ''">
          <el-option v-for="o in moduleOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.action" placeholder="具体操作" clearable class="filter-item">
          <el-option v-for="o in actionOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="filters.operator" placeholder="操作人" clearable class="filter-item" @keyup.enter="search" />
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          class="filter-item filter-date"
        />
        <el-select v-model="filters.status" placeholder="状态" clearable class="filter-item">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failure" />
          <el-option label="其他" value="other" />
        </el-select>
        <div class="filter-actions">
          <el-button type="primary" :icon="Search" @click="search">查询</el-button>
          <el-button :icon="Refresh" @click="reset">重置</el-button>
        </div>
      </div>
    </div>

    <!-- 日志表格 -->
    <div class="ks-card audit-table-card">
      <el-table v-loading="loading" :data="items" class="ks-table audit-table" table-layout="fixed">
        <el-table-column label="时间" width="168">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作人" width="120">
          <template #default="{ row }">
            <span class="op-user">{{ row.username || '匿名' }}</span>
            <span v-if="row.email" class="op-mail">{{ row.email }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="module_label" label="类型" width="110" />
        <el-table-column prop="action_label" label="操作" width="110" />
        <el-table-column label="详情" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.detail || row.action_label }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="View" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="page = 1; load()"
        />
      </div>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="审计详情" width="520px" class="audit-dialog">
      <div v-if="detailTarget" class="audit-detail">
        <div class="detail-row"><span>记录 ID</span><b>{{ detailTarget.id }}</b></div>
        <div class="detail-row"><span>时间</span><b>{{ fmtTime(detailTarget.create_time) }}</b></div>
        <div class="detail-row"><span>操作人</span><b>{{ detailTarget.username || '匿名' }}（{{ detailTarget.email || '-' }}）</b></div>
        <div class="detail-row"><span>类型 / 操作</span><b>{{ detailTarget.module_label }} / {{ detailTarget.action_label }}</b></div>
        <div class="detail-row"><span>状态</span><b>{{ detailTarget.status }}</b></div>
        <div class="detail-row"><span>IP 地址</span><b>{{ detailTarget.ip || '-' }}</b></div>
        <div class="detail-row"><span>请求方法</span><b>{{ detailTarget.method || '-' }}</b></div>
        <div class="detail-row"><span>请求路径</span><b>{{ detailTarget.path || '-' }}</b></div>
        <div class="detail-row"><span>耗时</span><b>{{ detailTarget.duration_ms != null ? detailTarget.duration_ms + ' ms' : '-' }}</b></div>
        <div class="detail-row detail-desc"><span>详情</span><p>{{ detailTarget.detail || '无' }}</p></div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}
.audit-filters {
  padding: 14px 16px;
  margin-bottom: 14px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.filter-item {
  width: 150px;
}
.filter-date {
  width: 250px;
}
.filter-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.audit-table-card {
  padding: 6px 16px 14px;
}
.audit-table {
  width: 100%;
}
.op-user {
  font-weight: 600;
  color: var(--ks-text-primary, #0f172a);
}
.op-mail {
  display: block;
  font-size: 11px;
  color: var(--ks-text-tertiary, #94a3b8);
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.audit-detail .detail-row {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed rgba(100, 116, 139, 0.15);
  font-size: 13px;
}
.audit-detail .detail-row span {
  width: 90px;
  flex-shrink: 0;
  color: var(--ks-text-secondary, #64748b);
}
.audit-detail .detail-row b {
  font-weight: 500;
  color: var(--ks-text-primary, #0f172a);
  word-break: break-all;
}
.audit-detail .detail-desc {
  flex-direction: column;
}
.audit-detail .detail-desc p {
  margin: 4px 0 0;
  white-space: pre-wrap;
  word-break: break-all;
}
@media (max-width: 768px) {
  .audit-page {
    padding: 14px;
  }
  .filter-item,
  .filter-date {
    width: 100%;
  }
  .filter-actions {
    margin-left: 0;
    width: 100%;
  }
  .pager {
    justify-content: center;
    overflow-x: auto;
  }
}
@media (max-width: 375px) {
  .audit-filters {
    padding: 10px;
  }
  .audit-table-card {
    padding: 6px 8px 12px;
  }
  .audit-dialog {
    width: 92% !important;
  }
}
</style>
