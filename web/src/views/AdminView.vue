<script setup lang="ts">
/**
 * 管理后台：部门 / 用户 / 文档总览 / 对话总览 / 反馈记录 / 操作日志 / LLM 记录 / 系统配置
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Setting, Document, ChatDotRound, User, OfficeBuilding, Key } from '@element-plus/icons-vue'
import {
  listUsers,
  updateUser,
  listAdminDepartments,
  createAdminDepartment,
  updateAdminDepartment,
  deleteAdminDepartment,
  listOperationLogs,
  listLlmLogs,
  listSysConfigs,
  updateSysConfig,
  listAdminDocuments,
  listAdminConversations,
  listAdminFeedback,
  handleFeedback,
  listModelProviders,
  createModelProvider,
  updateModelProvider,
  deleteModelProvider,
  setDefaultModelProvider,
  roleOverview,
} from '@/api/admin'
import type {
  AdminPermPoint,
  AdminRoleItem,
} from '@/api/admin'
import type {
  AdminConversation,
  AdminDept,
  AdminDoc,
  AdminFeedback,
  AdminUser,
  LlmLogItem,
  ModelProviderItem,
  OperationLogItem,
  SysConfigItem,
} from '@/types'

type MenuKey = 'dept' | 'user' | 'role' | 'doc' | 'conv' | 'feedback' | 'log' | 'llm' | 'provider' | 'config'
const activeMenu = ref<MenuKey>('dept')

const menus: Array<{ key: MenuKey; label: string; icon: unknown }> = [
  { key: 'dept', label: '部门管理', icon: OfficeBuilding },
  { key: 'user', label: '用户管理', icon: User },
  { key: 'role', label: '角色权限', icon: Key },
  { key: 'doc', label: '文档总览', icon: Document },
  { key: 'conv', label: '对话总览', icon: ChatDotRound },
  { key: 'feedback', label: '反馈记录', icon: Setting },
  { key: 'log', label: '操作日志', icon: Setting },
  { key: 'llm', label: 'LLM 记录', icon: Setting },
  { key: 'provider', label: '模型供应商', icon: Setting },
  { key: 'config', label: '系统配置', icon: Setting },
]

/* ---------------- 部门管理 ---------------- */
const depts = ref<AdminDept[]>([])
const deptLoading = ref(false)
const deptDialogVisible = ref(false)
const deptDialogMode = ref<'create' | 'edit'>('create')
const deptEditing = ref<AdminDept | null>(null)
const deptForm = reactive({
  dept_name: '',
  parent_id: undefined as number | undefined,
  leader_id: undefined as number | undefined,
  description: '',
  sort_order: 0,
})
const savingDept = ref(false)
// 负责人候选（管理员/员工均可任职，取前 100 用户）
const deptLeaderOptions = ref<AdminUser[]>([])

async function loadDepts() {
  deptLoading.value = true
  try {
    depts.value = await listAdminDepartments()
  } catch {
    // 拦截器已提示
  } finally {
    deptLoading.value = false
  }
}

async function loadDeptLeaders() {
  try {
    const res = await listUsers({ page: 1, page_size: 100 })
    deptLeaderOptions.value = res.items
  } catch {
    // 拦截器已提示
  }
}

/** 生成树形选择数据（编辑时排除自身及后代，避免环） */
function buildDeptTreeOptions(nodes: AdminDept[], excludeId?: number | null): AdminDept[] {
  const filtered: AdminDept[] = []
  for (const n of nodes) {
    if (n.id === excludeId) continue
    filtered.push({ ...n, children: n.children ? buildDeptTreeOptions(n.children, excludeId) : [] })
  }
  return filtered
}

const deptTreeOptions = computed(() => buildDeptTreeOptions(depts.value, deptDialogMode.value === 'edit' ? deptEditing.value?.id : null))

/** 根据 parent_id 反查上级部门名称（支持多级树） */
function parentDeptName(parentId: number | null | undefined): string {
  if (parentId == null) return '-'
  const find = (nodes: AdminDept[]): string | null => {
    for (const n of nodes) {
      if (n.id === parentId) return n.dept_name
      if (n.children?.length) {
        const hit = find(n.children)
        if (hit) return hit
      }
    }
    return null
  }
  return find(depts.value) ?? '-'
}

function openCreateDept(parent?: AdminDept) {
  deptDialogMode.value = 'create'
  deptEditing.value = null
  deptForm.dept_name = ''
  deptForm.parent_id = parent?.id
  deptForm.leader_id = undefined
  deptForm.description = ''
  deptForm.sort_order = 0
  deptDialogVisible.value = true
}

function openEditDept(dept: AdminDept) {
  deptDialogMode.value = 'edit'
  deptEditing.value = dept
  deptForm.dept_name = dept.dept_name
  deptForm.parent_id = dept.parent_id ?? undefined
  deptForm.leader_id = dept.leader_id ?? undefined
  deptForm.description = dept.description ?? ''
  deptForm.sort_order = dept.sort_order ?? 0
  deptDialogVisible.value = true
}

async function submitDept() {
  const name = deptForm.dept_name.trim()
  if (!name) {
    ElMessage.warning('请输入部门名称')
    return
  }
  savingDept.value = true
  try {
    if (deptDialogMode.value === 'create') {
      await createAdminDepartment({
        dept_name: name,
        parent_id: deptForm.parent_id ?? null,
        leader_id: deptForm.leader_id ?? null,
        description: deptForm.description.trim() || undefined,
        sort_order: deptForm.sort_order || 0,
      })
      ElMessage.success('部门已创建')
    } else if (deptEditing.value) {
      await updateAdminDepartment(deptEditing.value.id, {
        dept_name: name,
        parent_id: deptForm.parent_id ?? null,
        leader_id: deptForm.leader_id ?? null,
        description: deptForm.description.trim() || null,
        sort_order: deptForm.sort_order || 0,
      })
      ElMessage.success('部门已更新')
    }
    deptDialogVisible.value = false
    await loadDepts()
  } catch {
    // 拦截器已提示
  } finally {
    savingDept.value = false
  }
}

async function removeDept(dept: AdminDept) {
  try {
    await ElMessageBox.confirm(
      `确定删除部门「${dept.dept_name}」吗？有下级部门或仍有成员时无法删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteAdminDepartment(dept.id)
    ElMessage.success('部门已删除')
    await loadDepts()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 用户管理 ---------------- */
const users = ref<AdminUser[]>([])
const userTotal = ref(0)
const userPage = ref(1)
const userPageSize = ref(10)
const userLoading = ref(false)
const userKeyword = ref('')
const editUserVisible = ref(false)
const editTarget = ref<AdminUser | null>(null)
const editForm = reactive({ username: '', role: 'staff', status: 'active', dept_id: undefined as number | undefined })
const savingUser = ref(false)

async function loadUsers() {
  userLoading.value = true
  try {
    const res = await listUsers({
      page: userPage.value,
      page_size: userPageSize.value,
      keyword: userKeyword.value || undefined,
    })
    users.value = res.items
    userTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    userLoading.value = false
  }
}

function searchUsers() {
  userPage.value = 1
  loadUsers()
}

function openEditUser(user: AdminUser) {
  editTarget.value = user
  editForm.username = user.username
  editForm.role = user.role
  editForm.status = user.status
  editForm.dept_id = user.dept_id
  editUserVisible.value = true
}

async function submitEditUser() {
  if (!editTarget.value) return
  savingUser.value = true
  try {
    await updateUser(editTarget.value.id, {
      username: editForm.username,
      role: editForm.role,
      status: editForm.status,
      dept_id: editForm.dept_id,
    })
    ElMessage.success('用户已更新')
    editUserVisible.value = false
    await loadUsers()
  } catch {
    // 拦截器已提示
  } finally {
    savingUser.value = false
  }
}

/* ---------------- 文档总览 ---------------- */
const docs = ref<AdminDoc[]>([])
const docTotal = ref(0)
const docPage = ref(1)
const docPageSize = ref(10)
const docLoading = ref(false)
const docKeyword = ref('')
const docType = ref('')
const docStatus = ref('')

async function loadDocs() {
  docLoading.value = true
  try {
    const res = await listAdminDocuments({
      keyword: docKeyword.value || undefined,
      file_type: docType.value || undefined,
      status: docStatus.value || undefined,
      page: docPage.value,
      page_size: docPageSize.value,
    })
    docs.value = res.items
    docTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    docLoading.value = false
  }
}

/* ---------------- 对话总览 ---------------- */
const convs = ref<AdminConversation[]>([])
const convTotal = ref(0)
const convPage = ref(1)
const convPageSize = ref(10)
const convLoading = ref(false)
const convKeyword = ref('')

async function loadConvs() {
  convLoading.value = true
  try {
    const res = await listAdminConversations({
      keyword: convKeyword.value || undefined,
      page: convPage.value,
      page_size: convPageSize.value,
    })
    convs.value = res.items
    convTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    convLoading.value = false
  }
}

/* ---------------- 反馈记录 ---------------- */
const feedbacks = ref<AdminFeedback[]>([])
const feedbackTotal = ref(0)
const feedbackPage = ref(1)
const feedbackPageSize = ref(10)
const feedbackLoading = ref(false)
const feedbackStatus = ref('')

async function loadFeedbacks() {
  feedbackLoading.value = true
  try {
    const res = await listAdminFeedback({
      status: feedbackStatus.value || undefined,
      page: feedbackPage.value,
      page_size: feedbackPageSize.value,
    })
    feedbacks.value = res.items
    feedbackTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    feedbackLoading.value = false
  }
}

async function markFeedbackHandled(row: AdminFeedback) {
  try {
    await handleFeedback(row.id)
    ElMessage.success('反馈已标记处理')
    await loadFeedbacks()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 操作日志 ---------------- */
const logs = ref<OperationLogItem[]>([])
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(10)
const logLoading = ref(false)
const logAction = ref('')

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await listOperationLogs({ page: logPage.value, page_size: logPageSize.value, action: logAction.value || undefined })
    logs.value = res.items
    logTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    logLoading.value = false
  }
}

/* ---------------- LLM 记录 ---------------- */
const llmLogs = ref<LlmLogItem[]>([])
const llmTotal = ref(0)
const llmPage = ref(1)
const llmPageSize = ref(10)
const llmLoading = ref(false)

async function loadLlmLogs() {
  llmLoading.value = true
  try {
    const res = await listLlmLogs({ page: llmPage.value, page_size: llmPageSize.value })
    llmLogs.value = res.items
    llmTotal.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    llmLoading.value = false
  }
}

/* ---------------- 模型供应商 ---------------- */
const providers = ref<ModelProviderItem[]>([])
const providerLoading = ref(false)
const providerDialogVisible = ref(false)
const providerEditingId = ref<number | null>(null)
const providerForm = reactive({
  name: '',
  base_url: '',
  model: '',
  api_key: '',
  is_default: false,
  enabled: true,
})
const savingProvider = ref(false)

async function loadProviders() {
  providerLoading.value = true
  try {
    providers.value = await listModelProviders()
  } catch {
    // 拦截器已提示
  } finally {
    providerLoading.value = false
  }
}

function openCreateProvider() {
  providerEditingId.value = null
  providerForm.name = ''
  providerForm.base_url = ''
  providerForm.model = ''
  providerForm.api_key = ''
  providerForm.is_default = false
  providerForm.enabled = true
  providerDialogVisible.value = true
}

function openEditProvider(row: ModelProviderItem) {
  providerEditingId.value = row.id
  providerForm.name = row.name
  providerForm.base_url = row.base_url
  providerForm.model = row.model
  providerForm.api_key = ''
  providerForm.is_default = row.is_default
  providerForm.enabled = row.enabled
  providerDialogVisible.value = true
}

async function submitProvider() {
  if (!providerForm.name.trim() || !providerForm.base_url.trim() || !providerForm.model.trim()) {
    ElMessage.warning('请填写供应商名称、Base URL 与模型名称')
    return
  }
  savingProvider.value = true
  try {
    if (providerEditingId.value) {
      await updateModelProvider(providerEditingId.value, {
        name: providerForm.name,
        base_url: providerForm.base_url,
        model: providerForm.model,
        api_key: providerForm.api_key || undefined,
        is_default: providerForm.is_default,
        enabled: providerForm.enabled,
      })
      ElMessage.success('供应商已更新')
    } else {
      await createModelProvider({
        name: providerForm.name,
        base_url: providerForm.base_url,
        model: providerForm.model,
        api_key: providerForm.api_key,
        is_default: providerForm.is_default,
        enabled: providerForm.enabled,
      })
      ElMessage.success('供应商已创建')
    }
    providerDialogVisible.value = false
    await loadProviders()
  } catch {
    // 拦截器已提示
  } finally {
    savingProvider.value = false
  }
}

async function removeProvider(row: ModelProviderItem) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${row.name}」吗？删除后该供应商不可用。`, '删除模型供应商', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteModelProvider(row.id)
    ElMessage.success('供应商已删除')
    await loadProviders()
  } catch {
    // 拦截器已提示
  }
}

async function setDefaultProvider(row: ModelProviderItem) {
  try {
    await setDefaultModelProvider(row.id)
    ElMessage.success(`已将「${row.name}」设为默认供应商`)
    await loadProviders()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 系统配置 ---------------- */
const configs = ref<SysConfigItem[]>([])
const configLoading = ref(false)
const configEditVisible = ref(false)
const configCreateMode = ref(false)
const editConfigKey = ref('')
const editConfigValue = ref('')
const editConfigDesc = ref('')
const savingConfig = ref(false)

async function loadConfigs() {
  configLoading.value = true
  try {
    configs.value = await listSysConfigs()
  } catch {
    // 拦截器已提示
  } finally {
    configLoading.value = false
  }
}

function openEditConfig(item: SysConfigItem) {
  configCreateMode.value = false
  editConfigKey.value = item.config_key
  editConfigValue.value = item.config_value
  editConfigDesc.value = item.description || ''
  configEditVisible.value = true
}

/** 新增配置项：配置表初始仅内置少量键，需支持业务侧自定义键值 */
function openCreateConfig() {
  configCreateMode.value = true
  editConfigKey.value = ''
  editConfigValue.value = ''
  editConfigDesc.value = ''
  configEditVisible.value = true
}

async function submitConfig() {
  const key = (editConfigKey.value || '').trim()
  if (!key) {
    ElMessage.warning('请填写配置键')
    return
  }
  savingConfig.value = true
  try {
    await updateSysConfig(key, editConfigValue.value, editConfigDesc.value || undefined)
    ElMessage.success(configCreateMode.value ? '配置已新增' : '配置已更新')
    configEditVisible.value = false
    await loadConfigs()
  } catch {
    // 拦截器已提示
  } finally {
    savingConfig.value = false
  }
}

/* ---------------- 角色权限 ---------------- */
const roleItems = ref<AdminRoleItem[]>([])
const roleCatalog = ref<AdminPermPoint[]>([])
const roleLoading = ref(false)
const roleKeyword = ref('')
const roleOnlyCustom = ref(false)
const roleStats = ref({ team_total: 0, custom_total: 0, perm_total: 0 })

async function loadRoles() {
  roleLoading.value = true
  try {
    const res = await roleOverview({ keyword: roleKeyword.value, only_custom: roleOnlyCustom.value })
    roleItems.value = res.items || []
    roleCatalog.value = res.catalog || []
    roleStats.value = {
      team_total: res.team_total || 0,
      custom_total: res.custom_total || 0,
      perm_total: res.perm_total || 0,
    }
  } catch {
    // 拦截器已提示
  } finally {
    roleLoading.value = false
  }
}

function permName(key: string) {
  const hit = roleCatalog.value.find((p) => p.key === key)
  return hit ? hit.name : key
}

/* ---------------- 页签切换 ---------------- */
function switchMenu(key: MenuKey) {
  activeMenu.value = key
  if (key === 'dept') loadDepts()
  else if (key === 'user') loadUsers()
  else if (key === 'role') loadRoles()
  else if (key === 'doc') loadDocs()
  else if (key === 'conv') loadConvs()
  else if (key === 'feedback') loadFeedbacks()
  else if (key === 'log') loadLogs()
  else if (key === 'llm') loadLlmLogs()
  else if (key === 'provider') loadProviders()
  else if (key === 'config') loadConfigs()
}

function fmtTime(t?: string | null) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

onMounted(() => {
  loadDepts()
  loadDeptLeaders()
})
</script>

<template>
  <div class="ks-admin-layout">
    <aside class="ks-admin-sidebar">
      <el-menu :default-active="activeMenu" @select="switchMenu">
        <el-menu-item v-for="m in menus" :key="m.key" :index="m.key">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.label }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="ks-admin-main">
      <!-- 部门管理 -->
      <section v-if="activeMenu === 'dept'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">部门管理</h2>
          <div class="admin-tools">
            <el-button type="primary" :icon="Plus" @click="openCreateDept()">新增顶级部门</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="deptLoading">
          <el-table
            :data="depts"
            stripe
            row-key="id"
            :tree-props="{ children: 'children' }"
            default-expand-all
          >
            <el-table-column prop="dept_name" label="部门名称" min-width="180" />
            <el-table-column label="上级部门" min-width="140">
              <template #default="{ row }">{{ parentDeptName(row.parent_id) }}</template>
            </el-table-column>
            <el-table-column label="负责人" min-width="120">
              <template #default="{ row }">
                <span v-if="row.leader_name">{{ row.leader_name }}</span>
                <span v-else class="ks-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="成员数" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.member_count > 0 ? 'primary' : 'info'" effect="plain">
                  {{ row.member_count }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="排序" width="80" prop="sort_order" />
            <el-table-column label="创建时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" text :icon="Plus" @click="openCreateDept(row)">子部门</el-button>
                <el-button size="small" text type="primary" @click="openEditDept(row)">编辑</el-button>
                <el-button size="small" text type="danger" @click="removeDept(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!depts.length && !deptLoading" description="暂无部门" />
        </div>
      </section>

      <!-- 用户管理 -->
      <section v-if="activeMenu === 'user'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">用户管理</h2>
          <div class="admin-tools">
            <el-input
              v-model="userKeyword"
              placeholder="搜索用户名 / 邮箱"
              clearable
              style="width: 240px"
              :prefix-icon="Search"
              @keyup.enter="searchUsers"
            />
            <el-button type="primary" @click="searchUsers">搜索</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="userLoading">
          <el-table :data="users" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column prop="email" label="邮箱" min-width="180" />
            <el-table-column label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                  {{ row.role === 'admin' ? '管理员' : '员工' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '正常' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dept_name" label="部门" min-width="120" />
            <el-table-column label="最近登录" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.last_login_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="openEditUser(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="userTotal > userPageSize"
            layout="total, prev, pager, next"
            :total="userTotal"
            :page-size="userPageSize"
            :current-page="userPage"
            @current-change="(p: number) => { userPage = p; loadUsers() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- 文档总览 -->
      <section v-if="activeMenu === 'doc'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">文档总览</h2>
          <div class="admin-tools">
            <el-input
              v-model="docKeyword"
              placeholder="搜索文档名称"
              clearable
              style="width: 220px"
              :prefix-icon="Search"
              @keyup.enter="docPage = 1; loadDocs()"
            />
            <el-select v-model="docType" placeholder="文件类型" clearable style="width: 120px" @change="docPage = 1; loadDocs()">
              <el-option label="PDF" value="pdf" />
              <el-option label="Word" value="docx" />
              <el-option label="Excel" value="xlsx" />
              <el-option label="PPT" value="pptx" />
              <el-option label="TXT" value="txt" />
              <el-option label="Markdown" value="md" />
            </el-select>
            <el-select v-model="docStatus" placeholder="解析状态" clearable style="width: 130px" @change="docPage = 1; loadDocs()">
              <el-option label="排队中" value="pending" />
              <el-option label="解析中" value="processing" />
              <el-option label="已解析" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-button type="primary" @click="docPage = 1; loadDocs()">搜索</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="docLoading">
          <el-table :data="docs" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="doc_name" label="文档名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="file_type" label="类型" width="80" />
            <el-table-column prop="version_no" label="版本" width="70">
              <template #default="{ row }">v{{ row.version_no }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="uploader" label="上传者" width="100" />
            <el-table-column prop="dept_name" label="部门" width="110" />
            <el-table-column label="更新时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.update_time) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="docTotal > docPageSize"
            layout="total, prev, pager, next"
            :total="docTotal"
            :page-size="docPageSize"
            :current-page="docPage"
            @current-change="(p: number) => { docPage = p; loadDocs() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- 对话总览 -->
      <section v-if="activeMenu === 'conv'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">对话总览</h2>
          <div class="admin-tools">
            <el-input
              v-model="convKeyword"
              placeholder="搜索会话标题"
              clearable
              style="width: 240px"
              :prefix-icon="Search"
              @keyup.enter="convPage = 1; loadConvs()"
            />
            <el-button type="primary" @click="convPage = 1; loadConvs()">搜索</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="convLoading">
          <el-table :data="convs" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="title" label="会话标题" min-width="240" show-overflow-tooltip />
            <el-table-column prop="username" label="用户" width="120" />
            <el-table-column prop="msg_count" label="消息数" width="90" />
            <el-table-column label="上下文" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_context_reset ? 'warning' : 'success'" size="small">
                  {{ row.is_context_reset ? '已重置' : '正常' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.update_time) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="convTotal > convPageSize"
            layout="total, prev, pager, next"
            :total="convTotal"
            :page-size="convPageSize"
            :current-page="convPage"
            @current-change="(p: number) => { convPage = p; loadConvs() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- 反馈记录 -->
      <section v-if="activeMenu === 'feedback'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">反馈记录</h2>
          <div class="admin-tools">
            <el-select v-model="feedbackStatus" placeholder="处理状态" clearable style="width: 130px" @change="feedbackPage = 1; loadFeedbacks()">
              <el-option label="待处理" value="pending" />
              <el-option label="已处理" value="handled" />
            </el-select>
            <el-button type="primary" @click="feedbackPage = 1; loadFeedbacks()">查询</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="feedbackLoading">
          <el-table :data="feedbacks" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户" width="110" />
            <el-table-column label="评价" width="80">
              <template #default="{ row }">
                <el-tag :type="row.score === 'good' ? 'success' : 'danger'" size="small">
                  {{ row.score === 'good' ? '满意' : '不满意' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="反馈内容" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.content || row.msg_preview || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'handled' ? 'info' : 'warning'" size="small">
                  {{ row.status === 'handled' ? '已处理' : '待处理' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status !== 'handled'"
                  size="small"
                  text
                  type="primary"
                  @click="markFeedbackHandled(row)"
                >标记处理</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="feedbackTotal > feedbackPageSize"
            layout="total, prev, pager, next"
            :total="feedbackTotal"
            :page-size="feedbackPageSize"
            :current-page="feedbackPage"
            @current-change="(p: number) => { feedbackPage = p; loadFeedbacks() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- 操作日志 -->
      <section v-if="activeMenu === 'log'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">操作日志</h2>
          <div class="admin-tools">
            <el-input v-model="logAction" placeholder="按操作类型筛选" clearable style="width: 200px" @keyup.enter="logPage = 1; loadLogs()" />
            <el-button type="primary" @click="logPage = 1; loadLogs()">查询</el-button>
          </div>
        </div>
        <div class="ks-card" v-loading="logLoading">
          <el-table :data="logs" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="username" label="用户" width="110" />
            <el-table-column prop="action" label="操作" width="140" />
            <el-table-column prop="module" label="模块" width="110" />
            <el-table-column prop="path" label="路径" min-width="200" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
            <el-table-column label="时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="logTotal > logPageSize"
            layout="total, prev, pager, next"
            :total="logTotal"
            :page-size="logPageSize"
            :current-page="logPage"
            @current-change="(p: number) => { logPage = p; loadLogs() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- LLM 记录 -->
      <section v-if="activeMenu === 'llm'">
        <h2 class="ks-page-title">LLM 调用记录</h2>
        <div class="ks-card" v-loading="llmLoading">
          <el-table :data="llmLogs" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="user_id" label="用户ID" width="80" />
            <el-table-column prop="scenario" label="场景" width="130" />
            <el-table-column prop="model_name" label="模型" min-width="140" />
            <el-table-column prop="prompt_tokens" label="输入Token" width="100" />
            <el-table-column prop="completion_tokens" label="输出Token" width="100" />
            <el-table-column prop="total_tokens" label="总Token" width="90" />
            <el-table-column prop="latency_ms" label="耗时(ms)" width="100" />
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_success ? 'success' : 'danger'" size="small">{{ row.is_success ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="150">
              <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="llmTotal > llmPageSize"
            layout="total, prev, pager, next"
            :total="llmTotal"
            :page-size="llmPageSize"
            :current-page="llmPage"
            @current-change="(p: number) => { llmPage = p; loadLlmLogs() }"
            style="margin-top: 14px; justify-content: flex-end"
          />
        </div>
      </section>

      <!-- 模型供应商 -->
      <section v-if="activeMenu === 'provider'">
        <div class="admin-head">
          <h2 class="ks-page-title" style="margin-bottom: 0">模型供应商</h2>
          <el-button type="primary" :icon="Plus" @click="openCreateProvider">新增供应商</el-button>
        </div>
        <div class="ks-card" v-loading="providerLoading">
          <el-table :data="providers" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" min-width="130" />
            <el-table-column prop="base_url" label="Base URL" min-width="240" show-overflow-tooltip />
            <el-table-column prop="model" label="模型" min-width="130" />
            <el-table-column label="API Key" min-width="150">
              <template #default="{ row }">
                <span v-if="row.api_key_configured" class="api-key-mask">{{ row.api_key_masked }}</span>
                <el-tag v-else size="small" type="info">未配置</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="默认" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_default ? 'success' : 'info'" size="small">{{ row.is_default ? '默认' : '—' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="190" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="openEditProvider(row)">编辑</el-button>
                <el-button size="small" text type="primary" :disabled="row.is_default" @click="setDefaultProvider(row)">设为默认</el-button>
                <el-button size="small" text type="danger" @click="removeProvider(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!providers.length && !providerLoading" description="暂无模型供应商" />
          <div class="provider-tip">提示：新增供应商后需配置 API Key 方可使用；编辑时 API Key 留空表示不修改。默认供应商在调用失败时自动兜底。</div>
        </div>
      </section>

      <!-- 角色权限 -->
      <section v-if="activeMenu === 'role'">
        <div class="section-head">
          <h2 class="ks-page-title">角色权限</h2>
          <div class="role-toolbar">
            <el-input
              v-model="roleKeyword"
              size="small"
              placeholder="按团队名称筛选"
              clearable
              style="width: 180px"
              @keyup.enter="loadRoles"
              @clear="loadRoles"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-checkbox v-model="roleOnlyCustom" size="small" @change="loadRoles">仅看自定义角色</el-checkbox>
            <el-button size="small" type="primary" @click="loadRoles">刷新</el-button>
          </div>
        </div>
        <div class="role-stats">
          <div class="role-stat"><span class="role-stat-num">{{ roleStats.team_total }}</span><span class="role-stat-label">团队数</span></div>
          <div class="role-stat"><span class="role-stat-num">{{ roleStats.custom_total }}</span><span class="role-stat-label">自定义角色</span></div>
          <div class="role-stat"><span class="role-stat-num">{{ roleStats.perm_total }}</span><span class="role-stat-label">权限点</span></div>
          <div class="role-stat"><span class="role-stat-num">{{ roleItems.length }}</span><span class="role-stat-label">角色条目</span></div>
        </div>
        <div class="ks-card" v-loading="roleLoading">
          <el-table :data="roleItems" stripe>
            <el-table-column prop="team_name" label="所属团队" min-width="160" show-overflow-tooltip />
            <el-table-column prop="role_name" label="角色名称" min-width="140" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.built_in ? 'info' : 'success'" size="small" effect="light">
                  {{ row.built_in ? '内置' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="member_count" label="成员数" width="90" align="center" />
            <el-table-column prop="perm_count" label="权限数" width="90" align="center" />
            <el-table-column label="权限点" min-width="320">
              <template #default="{ row }">
                <el-tag
                  v-for="p in row.perms"
                  :key="p"
                  size="small"
                  effect="plain"
                  class="perm-tag"
                >{{ permName(p) }}</el-tag>
                <span v-if="!row.perms.length" class="perm-none">未分配权限点</span>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="说明" min-width="180" show-overflow-tooltip />
          </el-table>
          <el-empty
            v-if="!roleItems.length && !roleLoading"
            description="暂无角色数据。团队创建后系统自动生成内置角色；如需自定义角色，请前往「团队详情 → 角色权限」页签新增。"
          />
          <div class="provider-tip">
            说明：本页为全平台角色权限只读总览，内置三档角色权限固定；自定义角色的新增与权限矩阵调整请在「团队详情 → 角色权限」页签由团队所有者或拥有「角色管理」权限的成员操作，变更会写入审计日志。
          </div>
        </div>
      </section>
      <!-- 系统配置 -->
      <section v-if="activeMenu === 'config'">
        <div class="section-head">
          <h2 class="ks-page-title">系统配置</h2>
          <el-button type="primary" size="small" @click="openCreateConfig">新增配置</el-button>
        </div>
        <div class="ks-card" v-loading="configLoading">
          <el-table :data="configs" stripe>
            <el-table-column prop="config_key" label="配置键" min-width="180" />
            <el-table-column prop="config_value" label="配置值" min-width="200" />
            <el-table-column prop="description" label="说明" min-width="220" />
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="openEditConfig(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!configs.length && !configLoading" description="暂无配置，可点击右上角「新增配置」创建" />
        </div>
      </section>
    </main>

    <!-- 新增/编辑部门弹窗 -->
    <el-dialog
      v-model="deptDialogVisible"
      append-to-body
      :title="deptDialogMode === 'create' ? '新增部门' : '编辑部门'"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item label="部门名称" required>
          <el-input v-model="deptForm.dept_name" placeholder="请输入部门名称" maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="deptForm.parent_id"
            :data="deptTreeOptions"
            :props="{ label: 'dept_name', children: 'children' }"
            node-key="id"
            clearable
            check-strictly
            placeholder="不选则为顶级部门"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="deptForm.leader_id" clearable filterable placeholder="请选择负责人" style="width: 100%">
            <el-option
              v-for="u in deptLeaderOptions"
              :key="u.id"
              :label="`${u.username}${u.email ? '（' + u.email + '）' : ''}`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="deptForm.description" type="textarea" :rows="2" maxlength="255" show-word-limit placeholder="部门职责说明（可选）" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="deptForm.sort_order" :min="0" :max="9999" style="width: 160px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDept" @click="submitDept">{{ deptDialogMode === 'create' ? '创建' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户弹窗 -->
    <el-dialog v-model="editUserVisible" append-to-body :title="`编辑用户：${editTarget?.username}`" width="480px">
      <el-form label-position="top" v-if="editTarget">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="editForm.role">
            <el-radio value="staff">员工</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="editForm.status">
            <el-radio value="active">正常</el-radio>
            <el-radio value="disabled">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="editForm.dept_id"
            :data="depts"
            :props="{ label: 'dept_name', children: 'children' }"
            node-key="id"
            check-strictly
            clearable
            placeholder="选择部门"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editUserVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="submitEditUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑配置弹窗 -->
    <el-dialog
      v-model="configEditVisible"
      append-to-body
      :title="configCreateMode ? '新增配置项' : `编辑配置：${editConfigKey}`"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item label="配置键" required>
          <el-input
            v-model="editConfigKey"
            :disabled="!configCreateMode"
            placeholder="小写英文 + 下划线，如 demo_active"
          />
        </el-form-item>
        <el-form-item label="配置值" required>
          <el-input v-model="editConfigValue" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="editConfigDesc" placeholder="配置项用途说明（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingConfig" @click="submitConfig">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑供应商弹窗 -->
    <el-dialog v-model="providerDialogVisible" append-to-body :title="providerEditingId ? '编辑模型供应商' : '新增模型供应商'" width="560px">
      <el-form label-position="top">
        <el-form-item label="供应商名称">
          <el-input v-model="providerForm.name" placeholder="如：千问Qwen / DeepSeek" />
        </el-form-item>
        <el-form-item label="Base URL（OpenAI 兼容）">
          <el-input v-model="providerForm.base_url" placeholder="如：https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="providerForm.model" placeholder="如：qwen-plus / deepseek-chat" />
        </el-form-item>
        <el-form-item :label="providerEditingId ? 'API Key（留空则不修改）' : 'API Key'">
          <el-input v-model="providerForm.api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="providerForm.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="providerForm.is_default" active-text="默认供应商" inactive-text="非默认" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingProvider" @click="submitProvider">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  animation: ks-page-enter 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.admin-tools {
  display: flex;
  gap: 8px;
}

/* 分区标题行：标题与右侧操作按钮同排，避免只有空态没有操作入口 */
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.section-head .ks-page-title {
  margin-bottom: 0;
}

.ks-card {
  overflow-x: auto;
}

.api-key-mask {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: var(--ks-text-secondary);
  background: rgba(100, 116, 139, 0.08);
  border-radius: 4px;
  padding: 1px 8px;
}

.provider-tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ks-text-secondary);
  line-height: 1.6;
}

/* 角色权限页签 */
.role-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.role-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0;
}

.role-stat {
  background: #fff;
  border: 1px solid var(--ks-border-color, #e5e7eb);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.role-stat-num {
  font-size: 20px;
  font-weight: 600;
  color: var(--ks-text-primary, #1f2937);
}

.role-stat-label {
  font-size: 12px;
  color: var(--ks-text-secondary);
}

.perm-tag {
  margin: 0 6px 6px 0;
}

.perm-none {
  font-size: 12px;
  color: var(--ks-text-secondary);
}

@media (max-width: 900px) {
  .role-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
