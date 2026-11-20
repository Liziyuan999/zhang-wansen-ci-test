<script setup lang="ts">
/**
 * 组织中心页：我的团队列表 / 创建 / 编辑 / 详情（成员管理 + 邀请成员 + 邀请记录）
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, EditPen, View, User, Message, Promotion, Link, Bell, SwitchButton, Delete, Clock, Search, OfficeBuilding, Key, Timer, Management, Setting, Warning, CircleCheck, Files, Download, Checked, CircleClose, Calendar, DataAnalysis, Document, ArrowRight, Location, Histogram } from '@element-plus/icons-vue'
import {
  createTeam,
  listMyTeams,
  getTeam,
  updateTeam,
  inviteMember,
  revokeInvite,
  removeMember,
  transferOwner,
  setMemberRole,
  joinTeam,
  dissolveTeam,
  getTeamLogs,
  listSharedDocs,
  getSharedDoc,
  requestDownload,
  downloadSharedDoc,
  listDownloadApprovals,
  approveDownload,
  rejectDownload,
  requestExit,
  listExitApprovals,
  approveExit,
  rejectExit,
  myApprovals,
  pendingApprovalCount,
  clock,
  attendanceGeo,
  updateAttendanceGeo,
  attendanceSummary,
  attendanceToday,
  myAttendance,
  requestFix,
  listFixes,
  approveFix,
  rejectFix,
  listRoles,
  createRole,
  updateRole,
  deleteRole,
} from '@/api/team'
import { sendNotice } from '@/api/notice'
import type { TeamItem, TeamDetail, TeamMember, TeamLog, SharedDoc, DownloadApproval, TeamExitApproval, MyApprovals, PendingCount, AttendanceToday, AttendanceGeo, AttendanceSummary, MyAttendance, AttendanceRecord, AttendanceFixApproval, TeamRole, PermPoint } from '@/types'

/* ---------------- 我的团队列表 ---------------- */
const teams = ref<TeamItem[]>([])
const loading = ref(false)

/** 组织中心总览统计 */
const overviewStats = computed(() => {
  const owned = teams.value.filter((t) => t.my_role === 'owner').length
  const admin = teams.value.filter((t) => t.my_role === 'admin').length
  const totalMembers = teams.value.reduce((s, t) => s + (t.member_count || 0), 0)
  return { total: teams.value.length, owned, admin, totalMembers }
})

function fmtDate(v?: string | null): string {
  if (!v) return '-'
  const s = String(v).replace('T', ' ')
  return s.length > 16 ? s.slice(0, 16) : s
}

/** 时间截取（"YYYY-MM-DD HH:MM:SS" -> "HH:MM"） */
function fmtClock(v?: string | null): string {
  if (!v) return '-'
  const s = String(v)
  const t = s.includes(' ') ? s.split(' ')[1] : s
  return t.length >= 5 ? t.slice(0, 5) : t
}

/** 角色权限说明矩阵 */
const roleMatrix = [
  { role: '所有者', desc: '团队最高权限：解散团队、移交所有权、任命管理员', className: 'rk-owner' },
  { role: '管理员', desc: '编辑团队信息、邀请成员、调整成员角色、发送团队通知', className: 'rk-admin' },
  { role: '成员', desc: '参与团队协作，查看成员、资料与团队动态', className: 'rk-member' },
]

function rolePerms(role: string): string[] {
  if (role === '所有者') return ['解散团队', '移交所有权', '任命管理员', '编辑团队信息', '邀请成员', '发送通知']
  if (role === '管理员') return ['编辑团队信息', '邀请成员', '调整成员角色', '发送通知', '移除成员']
  return ['查看成员', '查看团队资料', '查看团队动态']
}

const roleMeta: Record<string, { label: string; type: 'success' | 'warning' | 'primary' | 'danger' | 'info' }> = {
  owner: { label: '所有者', type: 'success' },
  admin: { label: '管理员', type: 'warning' },
  member: { label: '成员', type: 'info' },
}

const invStatusMeta: Record<string, { label: string; type: 'success' | 'warning' | 'primary' | 'danger' | 'info' }> = {
  pending: { label: '待接受', type: 'warning' },
  accepted: { label: '已加入', type: 'success' },
  declined: { label: '已拒绝', type: 'info' },
  expired: { label: '已过期', type: 'info' },
}

function roleTag(role: string) {
  const meta = roleMeta[role]
  if (meta) return meta.type
  const custom = roleList.value.find((r) => r.role_key === role)
  return custom ? 'primary' : 'info'
}
function roleLabel(role: string) {
  const meta = roleMeta[role]
  if (meta) return meta.label
  const custom = roleList.value.find((r) => r.role_key === role)
  return custom ? custom.role_name : role
}
function invTag(status: string) {
  return (invStatusMeta[status] || { label: status, type: 'info' as const }).type
}
function invLabel(status: string) {
  return (invStatusMeta[status] || { label: status }).label
}

async function loadTeams() {
  loading.value = true
  try {
    teams.value = await listMyTeams()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

/** 顶部刷新按钮：真实重拉团队列表并同步当前详情 */
async function handleRefresh() {
  loading.value = true
  try {
    teams.value = await listMyTeams()
    if (detailTeam.value) {
      const fresh = teams.value.find((t) => t.id === detailTeam.value!.id)
      detailTeam.value = fresh ? { ...detailTeam.value, ...fresh } : null
    }
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

/* ---------------- 加入团队（邀请链接 / token） ---------------- */
const joinVisible = ref(false)
const joining = ref(false)
const joinForm = reactive({ input: '' })

/** 从完整邀请链接中提取 token（支持纯 token 输入） */
function extractToken(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  try {
    const url = new URL(trimmed)
    const t = url.searchParams.get('token')
    if (t) return t
  } catch {
    // 非 URL，视为纯 token
  }
  return trimmed
}

function openJoin() {
  joinForm.input = ''
  joinVisible.value = true
}

async function submitJoin() {
  const token = extractToken(joinForm.input)
  if (!token) {
    ElMessage.warning('请输入邀请链接或邀请 token')
    return
  }
  joining.value = true
  try {
    const team = await joinTeam({ token })
    joinVisible.value = false
    ElMessage.success(`已加入团队「${team.name}」`)
    await loadTeams()
    // 加入成功后自动进入该团队详情
    const fresh = teams.value.find((t) => t.id === team.id)
    if (fresh) openDetail(fresh)
  } catch {
    // 拦截器已提示（含邮箱不匹配、token 失效等）
  } finally {
    joining.value = false
  }
}

/* ---------------- 退出团队（申请制：成员提交申请，所有者/管理员审批后移除） ---------------- */
const exitVisible = ref(false)
const exitSubmitting = ref(false)
const exitTeam = ref<TeamItem | TeamDetail | null>(null)
const exitForm = reactive({ reason: '' })

/** 团队卡片「退出」入口：非 owner 成员走退出申请制 */
function handleLeave(team: TeamItem) {
  openExitApply(team)
}

function openExitApply(team: TeamItem | TeamDetail | null) {
  if (!team) return
  exitTeam.value = team
  exitForm.reason = ''
  exitVisible.value = true
}

async function submitExitApply() {
  const team = exitTeam.value
  if (!team || exitSubmitting.value) return
  exitSubmitting.value = true
  try {
    await requestExit(team.id, exitForm.reason.trim())
    exitVisible.value = false
    ElMessage.success('退出申请已提交，等待团队所有者/管理员审批')
  } catch {
    // 拦截器已提示（owner 需先移交或解散、重复申请等）
  } finally {
    exitSubmitting.value = false
  }
}

/* ---------------- 解散团队（二次确认 + 输入团队名锁定） ---------------- */
const dissolveVisible = ref(false)
const dissolveName = ref('')
const dissolving = ref(false)
const dissolveTarget = ref<TeamItem | TeamDetail | null>(null)

function openDissolve(team: TeamItem | TeamDetail | null) {
  if (!team) return
  dissolveTarget.value = team
  dissolveName.value = ''
  dissolveVisible.value = true
}

const dissolveInputMatched = computed(() => {
  const target = dissolveTarget.value
  return !!target && dissolveName.value.trim() === target.name
})

async function confirmDissolve() {
  const team = dissolveTarget.value
  if (!team || !dissolveInputMatched.value || dissolving.value) return
  dissolving.value = true
  try {
    await dissolveTeam(team.id)
    ElMessage.success('团队已解散')
    dissolveVisible.value = false
    detailVisible.value = false
    await loadTeams()
  } catch {
    // 拦截器已提示
  } finally {
    dissolving.value = false
  }
}

/* ---------------- 创建团队 ---------------- */
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({ name: '', description: '' })

function openCreate() {
  createForm.name = ''
  createForm.description = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入团队名称')
    return
  }
  creating.value = true
  try {
    await createTeam({ name: createForm.name.trim(), description: createForm.description.trim() })
    createVisible.value = false
    ElMessage.success('团队创建成功')
    await loadTeams()
  } catch {
    // 拦截器已提示
  } finally {
    creating.value = false
  }
}

/* ---------------- 编辑团队 ---------------- */
const editVisible = ref(false)
const editing = ref(false)
const editTeam = ref<TeamItem | null>(null)
const editForm = reactive({ name: '', description: '' })

function openEdit(team: TeamItem) {
  editTeam.value = team
  editForm.name = team.name
  editForm.description = team.description || ''
  editVisible.value = true
}

async function submitEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('请输入团队名称')
    return
  }
  editing.value = true
  try {
    await updateTeam(editTeam.value!.id, { name: editForm.name.trim(), description: editForm.description.trim() })
    editVisible.value = false
    ElMessage.success('团队信息已更新')
    await loadTeams()
  } catch {
    // 拦截器已提示
  } finally {
    editing.value = false
  }
}

/* ---------------- 详情弹窗 ---------------- */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailTeam = ref<TeamDetail | null>(null)

function canManage(team: TeamItem | TeamDetail | null): boolean {
  return !!team && (team.my_role === 'owner' || team.my_role === 'admin')
}

function canRemove(team: TeamDetail, member: TeamMember): boolean {
  if (member.role === 'owner') return false
  if (team.my_role === 'owner') return true
  if (team.my_role === 'admin' && member.role === 'member') return true
  return false
}

function avatarChar(name: string): string {
  return (name || '知').charAt(0).toUpperCase()
}

async function openDetail(team: TeamItem) {
  detailVisible.value = true
  detailLoading.value = true
  detailTeam.value = null
  teamLogs.value = []
  inviteEmail.value = ''
  memberKeyword.value = ''
  detailTab.value = 'members'
  pendingCount.value = null
  sharedDocs.value = []
  attendance.value = null
  myAttendanceRecords.value = []
  myApprovalRecords.value = null
  downloadApprovals.value = []
  exitApprovals.value = []
  try {
    detailTeam.value = await getTeam(team.id)
    await loadLogs(team.id)
    openSettingsForm()
    await loadTeamExtras(team.id)
    await loadRoles(team.id)
  } catch {
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

/** 详情弹窗内刷新（邀请/撤销/移除后保持最新） */
async function refreshDetail() {
  if (!detailTeam.value) return
  try {
    detailTeam.value = await getTeam(detailTeam.value.id)
    await loadLogs(detailTeam.value.id)
    openSettingsForm()
    await loadTeamExtras(detailTeam.value.id)
    await loadRoles(detailTeam.value.id)
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 详情页签 / 成员搜索 / 统计 ---------------- */
const detailTab = ref<'members' | 'invites' | 'logs' | 'settings' | 'shared' | 'attendance' | 'approvals' | 'roles'>('members')
const memberKeyword = ref('')

const filteredMembers = computed(() => {
  const kw = memberKeyword.value.trim().toLowerCase()
  if (!detailTeam.value) return []
  if (!kw) return detailTeam.value.members
  return detailTeam.value.members.filter(
    (m) => m.username.toLowerCase().includes(kw) || m.email.toLowerCase().includes(kw),
  )
})

const detailStats = computed(() => {
  const t = detailTeam.value
  if (!t) return []
  const admins = t.members.filter((m) => m.role === 'owner' || m.role === 'admin').length
  const pending = t.invitations.filter((i) => i.status === 'pending').length
  const pendingApprovals = pendingCount.value ? pendingCount.value.total : 0
  return [
    { label: '团队成员', value: t.members.length, icon: User, tone: 'blue' },
    { label: '管理员', value: admins, icon: Management, tone: 'purple' },
    { label: '待审批', value: pendingApprovals, icon: DataAnalysis, tone: 'amber' },
    { label: '团队动态', value: teamLogs.value.length, icon: Timer, tone: 'green' },
  ]
})

/* ---------------- 团队设置（详情内基本信息编辑） ---------------- */
const settingsForm = reactive({ name: '', description: '' })
const settingsSaving = ref(false)

function openSettingsForm() {
  if (!detailTeam.value) return
  settingsForm.name = detailTeam.value.name
  settingsForm.description = detailTeam.value.description || ''
}

async function submitSettings() {
  if (!detailTeam.value) return
  if (!settingsForm.name.trim()) {
    ElMessage.warning('请输入团队名称')
    return
  }
  settingsSaving.value = true
  try {
    await updateTeam(detailTeam.value.id, {
      name: settingsForm.name.trim(),
      description: settingsForm.description.trim(),
    })
    detailTeam.value.name = settingsForm.name.trim()
    detailTeam.value.description = settingsForm.description.trim()
    ElMessage.success('团队设置已保存')
    await loadTeams()
  } catch {
    // 拦截器已提示
  } finally {
    settingsSaving.value = false
  }
}

/* ---------------- 团队动态 / 操作日志 ---------------- */
const teamLogs = ref<TeamLog[]>([])

async function loadLogs(teamId: number) {
  try {
    teamLogs.value = await getTeamLogs(teamId)
  } catch {
    teamLogs.value = []
  }
}

/* ---------------- 发团队通知（owner/admin） ---------------- */
const noticeVisible = ref(false)
const noticeSending = ref(false)
const noticeForm = reactive({ title: '', content: '' })

function openSendNotice() {
  noticeForm.title = ''
  noticeForm.content = ''
  noticeVisible.value = true
}

async function submitNotice() {
  if (!detailTeam.value) return
  if (!noticeForm.title.trim()) {
    ElMessage.warning('请输入通知标题')
    return
  }
  if (!noticeForm.content.trim()) {
    ElMessage.warning('请输入通知内容')
    return
  }
  noticeSending.value = true
  try {
    await sendNotice({
      team_id: detailTeam.value.id,
      title: noticeForm.title.trim(),
      content: noticeForm.content.trim(),
    })
    noticeVisible.value = false
    ElMessage.success('通知已发送，团队全体成员可见')
    await loadLogs(detailTeam.value.id)
  } catch {
    // 拦截器已提示
  } finally {
    noticeSending.value = false
  }
}

/* ---------------- 邀请成员 ---------------- */
const inviteEmail = ref('')
const inviting = ref(false)
/** 最近一次生成的邀请链接（提交成功后展示，供复制） */
const lastInviteLink = ref('')

async function copyLink(url: string) {
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('邀请链接已复制')
  } catch {
    // 剪贴板权限受限时降级为临时 textarea
    try {
      const ta = document.createElement('textarea')
      ta.value = url
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      ElMessage.success('邀请链接已复制')
    } catch {
      ElMessage.error('复制失败，请手动选中复制')
    }
  }
}

async function submitInvite() {
  const email = inviteEmail.value.trim()
  if (!email) {
    ElMessage.warning('请输入要邀请的 QQ 邮箱')
    return
  }
  if (!/^[\w.+-]+@[\w-]+(\.[\w-]+)+$/.test(email)) {
    ElMessage.warning('邮箱格式不正确')
    return
  }
  if (!detailTeam.value) return
  inviting.value = true
  try {
    const inv = await inviteMember(detailTeam.value.id, email)
    inviteEmail.value = ''
    lastInviteLink.value = inv.accept_url || ''
    ElMessage.success('邀请成功，可复制链接发送给对方')
    await refreshDetail()
  } catch {
    // 拦截器已提示
  } finally {
    inviting.value = false
  }
}

/* ---------------- 撤销邀请 ---------------- */
async function handleRevoke(invitationId: number) {
  try {
    await ElMessageBox.confirm('确定撤销该邀请吗？被邀请人将无法再通过此链接加入。', '撤销邀请', {
      confirmButtonText: '撤销',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await revokeInvite(invitationId)
    ElMessage.success('邀请已撤销')
    await refreshDetail()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 移除成员 ---------------- */
async function handleRemove(member: TeamMember) {
  if (!detailTeam.value) return
  try {
    await ElMessageBox.confirm(`确定将成员 ${member.username}（${member.email}）移出团队吗？`, '移除成员', {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await removeMember(detailTeam.value.id, member.user_id)
    ElMessage.success(`成员 ${member.username} 已移除`)
    await refreshDetail()
    await loadTeams()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 移交所有权（仅 owner） ---------------- */
async function handleTransfer(member: TeamMember) {
  if (!detailTeam.value) return
  try {
    await ElMessageBox.confirm(
      `确定将团队所有权移交给 ${member.username}（${member.email}）吗？移交后您将变为普通成员。`,
      '移交所有权',
      { confirmButtonText: '确认移交', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await transferOwner(detailTeam.value.id, member.user_id)
    ElMessage.success('团队所有权已移交')
    await refreshDetail()
    await loadTeams()
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 角色权限调整（owner 可调 member/admin/owner，admin 仅调 member） ---------------- */
const roleChanging = ref(false)
function canChangeRole(team: TeamDetail, member: TeamMember): boolean {
  if (member.role === 'owner') return false
  if (member.user_id === team.owner_id) return false
  if (team.my_role === 'owner') return true
  if (team.my_role === 'admin' && member.role === 'member') return true
  return false
}

function roleChangeOptions(team: TeamDetail): Array<{ label: string; value: string }> {
  const opts = [
    { label: '成员', value: 'member' },
    { label: '管理员', value: 'admin' },
  ]
  if (team.my_role === 'owner') opts.push({ label: '所有者', value: 'owner' })
  // 动态追加自定义角色（仅 owner/admin 可分配自定义角色给普通成员）
  if (team.my_role === 'owner' || team.my_role === 'admin') {
    for (const r of roleList.value) {
      if (!r.built_in) opts.push({ label: r.role_name, value: r.role_key })
    }
  }
  return opts
}

/* ---------------- 自定义角色管理（角色管理 tab） ---------------- */
const roleList = ref<TeamRole[]>([])
const permCatalog = ref<PermPoint[]>([])
const roleTabLoading = ref(false)
const roleDlgVisible = ref(false)
const roleDlgEditing = ref<TeamRole | null>(null)
const roleForm = reactive({ role_name: '', remark: '', perms: [] as string[] })
const roleDeleting = ref(false)

async function loadRoles(teamId: number) {
  try {
    const data = await listRoles(teamId)
    roleList.value = data.roles
    permCatalog.value = data.catalog
  } catch {
    // 拦截器已提示
  }
}

function openRoleCreate() {
  roleDlgEditing.value = null
  roleForm.role_name = ''
  roleForm.remark = ''
  roleForm.perms = []
  roleDlgVisible.value = true
}

function openRoleEdit(role: TeamRole) {
  roleDlgEditing.value = role
  roleForm.role_name = role.role_name
  roleForm.remark = role.remark || ''
  roleForm.perms = [...(role.perms || [])]
  roleDlgVisible.value = true
}

async function saveRole() {
  if (!detailTeam.value) return
  const name = roleForm.role_name.trim()
  if (!name) {
    ElMessage.warning('请填写角色名称')
    return
  }
  try {
    if (roleDlgEditing.value && roleDlgEditing.value.id != null) {
      await updateRole(detailTeam.value.id, roleDlgEditing.value.id, {
        role_name: name,
        perms: roleForm.perms,
        remark: roleForm.remark.trim(),
      })
      ElMessage.success('角色已更新')
    } else {
      await createRole(detailTeam.value.id, {
        role_name: name,
        perms: roleForm.perms,
        remark: roleForm.remark.trim(),
      })
      ElMessage.success('角色已创建')
    }
    roleDlgVisible.value = false
    await loadRoles(detailTeam.value.id)
    await refreshDetail()
  } catch {
    // 拦截器已提示
  }
}

async function removeRole(role: TeamRole) {
  if (!detailTeam.value) return
  try {
    await ElMessageBox.confirm(
      `删除自定义角色「${role.role_name}」后，${role.member_count} 名已分配该角色的成员将自动降级为普通成员，是否继续？`,
      '删除角色',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  roleDeleting.value = true
  try {
    if (role.id == null) return
    await deleteRole(detailTeam.value.id, role.id)
    ElMessage.success('角色已删除')
    await loadRoles(detailTeam.value.id)
    await refreshDetail()
  } catch {
    // 拦截器已提示
  } finally {
    roleDeleting.value = false
  }
}

function rolePermLabel(role: TeamRole): string {
  const map = new Map(permCatalog.value.map((p) => [p.key, p.label]))
  const names = (role.perms || []).map((k) => map.get(k) || k)
  return names.length ? names.join('、') : '无权限'
}

function permLabel(key: string): string {
  const found = permCatalog.value.find((p) => p.key === key)
  return found ? found.label : key
}

async function handleRoleChange(member: TeamMember, role: string) {
  if (!detailTeam.value) return
  const current = detailTeam.value
  if (role === 'owner') {
    // 设为所有者触发移交语义，二次确认
    try {
      await ElMessageBox.confirm(
        `确定将 ${member.username}（${member.email}）设为团队所有者吗？您将自动降为普通成员。`,
        '设为所有者',
        { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  } else if (role === member.role) {
    return
  }
  try {
    roleChanging.value = true
    await setMemberRole(current.id, member.user_id, role as 'owner' | 'admin' | 'member')
    ElMessage.success(`已更新 ${member.username} 的角色`)
    await refreshDetail()
    await loadTeams()
  } catch {
    // 拦截器已提示；刷新以回滚下拉显示
    await refreshDetail()
  } finally {
    roleChanging.value = false
  }
}

/* ================= 团队扩展：共享知识库 / 审批中心 / 企业打卡 ================= */

/** 待审批计数 */
const pendingCount = ref<PendingCount | null>(null)

/** 当前团队是否可管理（owner/admin） */
const canManageTeam = computed(
  () => !!detailTeam.value && (detailTeam.value.my_role === 'owner' || detailTeam.value.my_role === 'admin'),
)

async function refreshPendingCount(teamId: number) {
  try {
    pendingCount.value = await pendingApprovalCount(teamId)
  } catch {
    pendingCount.value = null
  }
}

/** 打开详情后加载全部扩展数据 */
async function loadTeamExtras(teamId: number) {
  await Promise.all([
    refreshPendingCount(teamId),
    loadSharedDocs(teamId),
    loadAttendance(teamId),
    loadApprovals(teamId),
  ])
}

/* ---------------- 共享知识库 ---------------- */
const sharedDocs = ref<SharedDoc[]>([])
const sharedLoading = ref(false)
const sharedTotal = ref(0)

async function loadSharedDocs(teamId: number) {
  sharedLoading.value = true
  try {
    const res = await listSharedDocs(teamId)
    sharedDocs.value = res.items
    sharedTotal.value = res.total
  } catch {
    sharedDocs.value = []
    sharedTotal.value = 0
  } finally {
    sharedLoading.value = false
  }
}

/** 下载申请弹窗 */
const downloadVisible = ref(false)
const downloadSubmitting = ref(false)
const downloadTarget = ref<SharedDoc | null>(null)
const downloadForm = reactive({ reason: '' })

function openDownloadApply(doc: SharedDoc) {
  if (!detailTeam.value) return
  downloadTarget.value = doc
  downloadForm.reason = ''
  downloadVisible.value = true
}

async function submitDownloadApply() {
  const team = detailTeam.value
  const doc = downloadTarget.value
  if (!team || !doc || downloadSubmitting.value) return
  downloadSubmitting.value = true
  try {
    const res = await requestDownload(team.id, doc.id, downloadForm.reason.trim())
    downloadVisible.value = false
    if (res.status === 'direct') {
      await doDownload(team.id, doc.id)
      ElMessage.success('您拥有直接下载权限，已开始下载')
    } else {
      ElMessage.success('下载申请已提交，等待团队所有者/管理员审批')
    }
  } catch {
    // 拦截器已提示
  } finally {
    downloadSubmitting.value = false
  }
}

/** 实际下载 */
async function doDownload(teamId: number, docId: number, approvalId?: number) {
  try {
    await downloadSharedDoc(teamId, docId, approvalId)
  } catch (e) {
    ElMessage.error((e as Error)?.message || '下载失败')
  }
}

/** 查看共享文档摘要 */
const sharedSummaryVisible = ref(false)
const sharedSummary = ref<SharedDoc | null>(null)
const sharedSummaryPreviewExpanded = ref(true)

async function openSharedSummary(doc: SharedDoc) {
  if (!detailTeam.value) return
  try {
    sharedSummary.value = await getSharedDoc(detailTeam.value.id, doc.id)
    sharedSummaryPreviewExpanded.value = true
    sharedSummaryVisible.value = true
  } catch {
    // 拦截器已提示
  }
}

/* ---------------- 企业打卡（四段班次 + 工作区域） ---------------- */
const attendance = ref<AttendanceToday | null>(null)
const attendanceLoading = ref(false)
const myAttendanceRecords = ref<AttendanceRecord[]>([])
const clocking = ref(false)
const clockingSlot = ref('')

type SlotKey = 'am_in' | 'am_out' | 'pm_in' | 'pm_out'
interface SlotDef { key: SlotKey; label: string; time: string; start: number; end: number }
/** 四段班次：start/end 为可打卡时间窗（分钟制，与后端 SHIFT_SLOTS 保持一致） */
const SLOT_DEFS: SlotDef[] = [
  { key: 'am_in', label: '上午上班', time: '08:30', start: 0, end: 720 },
  { key: 'am_out', label: '上午下班', time: '12:00', start: 510, end: 810 },
  { key: 'pm_in', label: '下午上班', time: '13:30', start: 720, end: 1020 },
  { key: 'pm_out', label: '下午下班', time: '17:00', start: 810, end: 1439 },
]

/** 当前是否处于该班次可打卡窗口（用于禁用打卡按钮） */
function slotClockable(def: SlotDef): boolean {
  const d = new Date()
  const cur = d.getHours() * 60 + d.getMinutes()
  return cur >= def.start && cur <= def.end
}

/** 当前是否未到该班次打卡时间（用于按钮文案提示） */
function slotNotYet(def: SlotDef): boolean {
  const d = new Date()
  return d.getHours() * 60 + d.getMinutes() < def.start
}

async function loadAttendance(teamId: number) {
  attendanceLoading.value = true
  try {
    const [todayRes, myRes] = await Promise.all([attendanceToday(teamId), myAttendance(teamId, 15)])
    attendance.value = todayRes
    myAttendanceRecords.value = myRes.items
  } catch {
    attendance.value = null
    myAttendanceRecords.value = []
  } finally {
    attendanceLoading.value = false
  }
  loadGeo(teamId)
  loadSummary(teamId)
}

/** 获取当前定位（Promise 包装，失败返回 null）。
 * 定位增强：权限拒绝 / 不可用 / 超时分别给出引导文案；
 * 高精度超时或位置暂不可用时自动降级为非高精度重试一次；
 * 硬超时兜底：部分浏览器/系统下 timeout 参数不生效导致回调永不触发，此处保证任何情况都会返回结果。 */
function getCurrentPosition(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      ElMessage.warning('当前浏览器不支持定位，请使用支持定位的浏览器（HTTPS 环境）打卡')
      resolve(null)
      return
    }
    let attempts = 0
    const MAX_ATTEMPTS = 2
    let hardTimer: ReturnType<typeof setTimeout> | null = null
    const finish = (v: { lat: number; lng: number } | null, msg?: string) => {
      if (hardTimer) {
        clearTimeout(hardTimer)
        hardTimer = null
      }
      if (msg) {
        ElMessage.warning({ message: msg, duration: 0, showClose: true })
      }
      resolve(v)
    }
    const tryLocate = () => {
      attempts += 1
      const t = attempts === 1 ? 8000 : 6000
      // 硬超时：即使浏览器忽略 timeout 参数，也能在 1.5s 宽限后结束等待
      hardTimer = setTimeout(() => {
        finish(null, attempts >= MAX_ATTEMPTS ? '定位超时：请移动到信号良好位置（靠近窗户或室外）后重试，或检查系统定位开关；也可在工作区域弹窗中手动输入经纬度' : undefined)
      }, t + 1500)
      navigator.geolocation.getCurrentPosition(
        (pos) => finish({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        (err) => {
          const code = err.code
          // 超时 / 位置暂不可用：降级为非高精度重试一次（部分环境高精度模式会一直等待超时）
          if (attempts < MAX_ATTEMPTS && (code === 2 || code === 3)) {
            if (hardTimer) {
              clearTimeout(hardTimer)
              hardTimer = null
            }
            setTimeout(tryLocate, 300)
            return
          }
          finish(null, positionErrorMessage(err))
        },
        // 第一次高精度（timeout 8s），重试时关闭高精度并缩短超时
        { enableHighAccuracy: attempts === 1, timeout: t, maximumAge: 30000 },
      )
    }
    tryLocate()
  })
}

function positionErrorMessage(err: GeolocationPositionError): string {
  switch (err.code) {
    case 1:
      return '定位权限被拒绝：请在浏览器地址栏/设置中允许本站访问位置信息，刷新页面后重试'
    case 2:
      return '无法获取定位：位置信息不可用，请检查系统定位服务是否开启（Windows 设置 > 隐私 > 位置）'
    case 3:
      return '定位超时：请移动到信号良好位置（靠近窗户或室外）后重试，或检查系统定位开关'
    default:
      return '获取定位失败：' + (err.message || '请检查定位权限')
  }
}

async function handleClock(slot: 'am_in' | 'am_out' | 'pm_in' | 'pm_out') {
  const team = detailTeam.value
  if (!team || clocking.value) return
  const pos = await getCurrentPosition()
  if (!pos) return
  clocking.value = true
  clockingSlot.value = slot
  try {
    await clock(team.id, slot, pos.lat, pos.lng)
    ElMessage.success('打卡成功')
    await loadAttendance(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    clocking.value = false
    clockingSlot.value = ''
  }
}

/* 工作区域配置（owner/admin） */
const geoVisible = ref(false)
const geoLoading = ref(false)
const geo = ref<AttendanceGeo>({ configured: false })
const geoForm = reactive({ lat: 0, lng: 0, radius_m: 500, enabled: true })
const locating = ref(false)

async function loadGeo(teamId: number) {
  geoLoading.value = true
  try {
    geo.value = await attendanceGeo(teamId)
    if (geo.value.configured) {
      geoForm.lat = geo.value.lat || 0
      geoForm.lng = geo.value.lng || 0
      geoForm.radius_m = geo.value.radius_m || 500
      geoForm.enabled = geo.value.enabled !== false
    }
  } catch {
    geo.value = { configured: false }
  } finally {
    geoLoading.value = false
  }
}

function openGeoDialog() {
  geoVisible.value = true
  if (detailTeam.value) loadGeo(detailTeam.value.id)
}

function useMyLocationForGeo() {
  locating.value = true
  getCurrentPosition().then((pos) => {
    locating.value = false
    if (pos) {
      geoForm.lat = Number(pos.lat.toFixed(6))
      geoForm.lng = Number(pos.lng.toFixed(6))
    } else {
      // 定位失败：引导手动输入兜底（快速定位不可用时的替代方案）
      ElMessage.warning('获取当前位置失败，请在下方手动输入公司办公地址的经纬度（可在高德/百度地图拾取坐标）')
    }
  })
}

async function saveGeo() {
  const team = detailTeam.value
  if (!team) return
  if (geoForm.lat === 0 && geoForm.lng === 0) {
    ElMessage.warning('请先点击"使用我的当前位置"，或手动输入有效的中心经纬度后再保存')
    return
  }
  try {
    await updateAttendanceGeo(team.id, {
      lat: geoForm.lat,
      lng: geoForm.lng,
      radius_m: geoForm.radius_m,
      enabled: geoForm.enabled,
    })
    ElMessage.success('工作区域已保存')
    geoVisible.value = false
    await loadGeo(team.id)
  } catch {
    // 拦截器已提示
  }
}

/** 打卡出勤汇总（近 7 天） */
const attendanceSummaryData = ref<AttendanceSummary | null>(null)
const summaryLoading = ref(false)
async function loadSummary(teamId: number) {
  summaryLoading.value = true
  try {
    attendanceSummaryData.value = await attendanceSummary(teamId, 7)
  } catch {
    attendanceSummaryData.value = null
  } finally {
    summaryLoading.value = false
  }
}

/* ---------------- 审批中心 ---------------- */
const approvalsLoading = ref(false)

/** 下载审批（owner/admin） */
const downloadApprovals = ref<DownloadApproval[]>([])
const downloadApprovalTotal = ref(0)
const downloadApprovalPage = ref(1)
const downloadApprovalStatus = ref('pending')
const APPROVAL_STATUS_OPTIONS = [
  { label: '待审批', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
  { label: '全部', value: '' },
]

async function loadDownloadApprovals(teamId: number) {
  approvalsLoading.value = true
  try {
    const res = await listDownloadApprovals(teamId, {
      status: downloadApprovalStatus.value,
      page: downloadApprovalPage.value,
      page_size: 20,
    })
    downloadApprovals.value = res.items
    downloadApprovalTotal.value = res.total
  } catch {
    downloadApprovals.value = []
    downloadApprovalTotal.value = 0
  } finally {
    approvalsLoading.value = false
  }
}

/** 退出审批（owner/admin） */
const exitApprovals = ref<TeamExitApproval[]>([])
const exitApprovalTotal = ref(0)
const exitApprovalPage = ref(1)
const exitApprovalStatus = ref('pending')

async function loadExitApprovals(teamId: number) {
  approvalsLoading.value = true
  try {
    const res = await listExitApprovals(teamId, {
      status: exitApprovalStatus.value,
      page: exitApprovalPage.value,
      page_size: 20,
    })
    exitApprovals.value = res.items
    exitApprovalTotal.value = res.total
  } catch {
    exitApprovals.value = []
    exitApprovalTotal.value = 0
  } finally {
    approvalsLoading.value = false
  }
}

/** 我的申请（成员视角） */
const myApprovalRecords = ref<MyApprovals | null>(null)

async function loadMyApprovals(teamId: number) {
  try {
    myApprovalRecords.value = await myApprovals(teamId)
  } catch {
    myApprovalRecords.value = null
  }
}

async function loadApprovals(teamId: number) {
  if (canManageTeam.value) {
    await Promise.all([loadDownloadApprovals(teamId), loadExitApprovals(teamId), loadFixApprovals(teamId)])
  } else {
    await loadMyApprovals(teamId)
  }
}

/** 考勤补卡审批（owner/admin） */
const fixApprovals = ref<AttendanceFixApproval[]>([])
const fixApprovalStatus = ref('pending')
const FIX_SLOT_OPTIONS = [
  { label: '上午上班', value: 'am_in' },
  { label: '上午下班', value: 'am_out' },
  { label: '下午上班', value: 'pm_in' },
  { label: '下午下班', value: 'pm_out' },
]

async function loadFixApprovals(teamId: number) {
  approvalsLoading.value = true
  try {
    const res = await listFixes(teamId, fixApprovalStatus.value)
    fixApprovals.value = res.items
  } catch {
    fixApprovals.value = []
  } finally {
    approvalsLoading.value = false
  }
}

/** 补卡申请弹窗 */
const fixVisible = ref(false)
const fixSubmitting = ref(false)
const fixForm = reactive({ date: '', slot: 'am_in', reason: '' })

function openFixDialog(slot: string = 'am_in', date?: string) {
  if (date) {
    fixForm.date = date
  } else {
    const today = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    fixForm.date = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
  }
  fixForm.slot = slot
  fixForm.reason = ''
  fixVisible.value = true
}

async function submitFix() {
  const team = detailTeam.value
  if (!team || fixSubmitting.value) return
  if (!fixForm.date) {
    ElMessage.warning('请选择补卡日期')
    return
  }
  fixSubmitting.value = true
  try {
    await requestFix(team.id, { date: fixForm.date, slot: fixForm.slot, reason: fixForm.reason })
    ElMessage.success('补卡申请已提交，等待管理员审批')
    fixVisible.value = false
    await loadMyApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    fixSubmitting.value = false
  }
}

async function handleApproveFix(ap: AttendanceFixApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  try {
    await ElMessageBox.confirm(
      `确定通过 ${ap.applicant_name} 的补卡申请吗？（${ap.date} ${ap.slot_label}）通过后将自动修正该日打卡记录。`,
      '通过补卡申请',
      { confirmButtonText: '通过并修正', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  approving.value = true
  try {
    await approveFix(team.id, ap.id)
    ElMessage.success('已通过补卡申请，打卡记录已修正')
    await loadFixApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

async function handleRejectFix(ap: AttendanceFixApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入拒绝原因（将通知申请人）', '拒绝补卡申请', {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (v: string) => (v && v.trim() ? true : '拒绝原因不能为空'),
    })
    reason = value?.trim() || ''
  } catch {
    return
  }
  approving.value = true
  try {
    await rejectFix(team.id, ap.id, reason)
    ElMessage.success('已拒绝补卡申请')
    await loadFixApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

/** 审批处理（通过 / 拒绝） */
const approving = ref(false)

async function handleApproveDownload(ap: DownloadApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  try {
    await ElMessageBox.confirm(
      `确定通过 ${ap.applicant_name} 对《${ap.doc_name}》的下载申请吗？通过后该成员即可下载此文档。`,
      '通过下载申请',
      { confirmButtonText: '通过', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  approving.value = true
  try {
    await approveDownload(team.id, ap.id)
    ElMessage.success('已通过下载申请')
    await loadDownloadApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

async function handleRejectDownload(ap: DownloadApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入拒绝原因（将通知申请人）', '拒绝下载申请', {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (v: string) => (v && v.trim() ? true : '拒绝原因不能为空'),
    })
    reason = value?.trim() || ''
  } catch {
    return
  }
  approving.value = true
  try {
    await rejectDownload(team.id, ap.id, reason)
    ElMessage.success('已拒绝下载申请')
    await loadDownloadApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

async function handleApproveExit(ap: TeamExitApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  try {
    await ElMessageBox.confirm(
      `确定通过 ${ap.applicant_name} 的退出团队申请吗？通过后将自动移除该成员。`,
      '通过退出申请',
      { confirmButtonText: '通过并移除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  approving.value = true
  try {
    await approveExit(team.id, ap.id)
    ElMessage.success('已通过退出申请，成员已移除')
    await loadExitApprovals(team.id)
    await refreshPendingCount(team.id)
    await refreshDetail()
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

async function handleRejectExit(ap: TeamExitApproval) {
  const team = detailTeam.value
  if (!team || approving.value) return
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入拒绝原因（将通知申请人）', '拒绝退出申请', {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (v: string) => (v && v.trim() ? true : '拒绝原因不能为空'),
    })
    reason = value?.trim() || ''
  } catch {
    return
  }
  approving.value = true
  try {
    await rejectExit(team.id, ap.id, reason)
    ElMessage.success('已拒绝退出申请')
    await loadExitApprovals(team.id)
    await refreshPendingCount(team.id)
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

/** 已通过的下载申请 → 直接下载 */
async function downloadByApproval(ap: DownloadApproval) {
  const team = detailTeam.value
  if (!team) return
  await doDownload(team.id, ap.doc_id, ap.id)
}

/** 审批状态标签 */
const approvalStatusMeta: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'info' }> = {
  pending: { label: '待审批', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
}

function approvalTag(status: string) {
  return (approvalStatusMeta[status] || { label: status, type: 'info' as const }).type
}
function approvalLabel(status: string) {
  return (approvalStatusMeta[status] || { label: status }).label
}

/** 打卡状态标签 */
const attendanceStatusMeta: Record<string, { label: string; type: 'success' | 'warning' | 'info' | 'primary' }> = {
  none: { label: '未打卡', type: 'info' },
  am_in: { label: '上午上班', type: 'warning' },
  am_out: { label: '上午下班', type: 'success' },
  pm_in: { label: '下午上班', type: 'warning' },
  pm_out: { label: '已下班', type: 'success' },
}

function attendanceTag(status: string) {
  return (attendanceStatusMeta[status] || { label: status, type: 'info' as const }).type
}
function attendanceLabel(status: string) {
  return (attendanceStatusMeta[status] || { label: status }).label
}

onMounted(loadTeams)
</script>

<template>
  <div class="ks-page">
    <!-- 组织中心头部：品牌横幅 + 数据总览 -->
    <div class="org-hero">
      <div class="org-hero-deco"></div>
      <div class="org-hero-main">
        <div>
          <h2 class="ks-page-title team-title">组织中心</h2>
          <div class="page-sub">创建团队、邀请成员、管理权限与协作动态，一站式管理企业组织。</div>
        </div>
        <div class="header-actions">
          <el-button class="org-hero-btn" :icon="Refresh" :loading="loading" @click="handleRefresh">刷新</el-button>
          <el-button class="org-hero-btn" :icon="Link" @click="openJoin">加入团队</el-button>
          <el-button class="org-hero-btn" type="primary" :icon="Plus" @click="openCreate">创建团队</el-button>
        </div>
      </div>
      <div v-if="teams.length" class="org-stats">
        <div class="org-stat">
          <div class="org-stat-icon blue"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="org-stat-meta"><b>{{ overviewStats.total }}</b><span>我的团队</span></div>
        </div>
        <div class="org-stat">
          <div class="org-stat-icon amber"><el-icon><User /></el-icon></div>
          <div class="org-stat-meta"><b>{{ overviewStats.totalMembers }}</b><span>团队成员</span></div>
        </div>
        <div class="org-stat">
          <div class="org-stat-icon purple"><el-icon><Management /></el-icon></div>
          <div class="org-stat-meta"><b>{{ overviewStats.owned }}</b><span>我拥有</span></div>
        </div>
        <div class="org-stat">
          <div class="org-stat-icon green"><el-icon><Warning /></el-icon></div>
          <div class="org-stat-meta"><b>{{ overviewStats.admin }}</b><span>我管理</span></div>
        </div>
      </div>
    </div>

    <div v-loading="loading">
      <div v-if="teams.length" class="team-grid">
        <div v-for="team in teams" :key="team.id" class="team-card">
          <div class="team-head">
            <span class="team-name">
              <span class="team-icon"><el-icon><OfficeBuilding /></el-icon></span>
              <span class="team-name-text">{{ team.name }}</span>
            </span>
            <el-tag :type="roleTag(team.my_role)" size="small" effect="light" class="status-tag">
              {{ roleLabel(team.my_role) }}
            </el-tag>
          </div>

          <div class="team-desc" :class="{ empty: !team.description }">
            {{ team.description || '暂无团队描述' }}
          </div>

          <div class="team-meta">
            <span class="meta-chip"><el-icon><User /></el-icon>{{ team.member_count }} 人</span>
            <span class="meta-chip"><el-icon><OfficeBuilding /></el-icon>所有者 {{ team.owner_name || `#${team.owner_id}` }}</span>
            <span v-if="team.create_time" class="meta-chip"><el-icon><Clock /></el-icon>{{ fmtDate(team.create_time) }}</span>
          </div>

          <div class="team-actions">
            <el-button size="small" type="primary" :icon="View" @click="openDetail(team)">进入团队</el-button>
            <el-button v-if="canManage(team)" size="small" text :icon="EditPen" @click="openEdit(team)">编辑</el-button>
            <el-button
              v-if="team.my_role !== 'owner'"
              size="small"
              text
              type="danger"
              class="team-leave-btn"
              @click="handleLeave(team)"
            >
              退出
            </el-button>
            <el-button
              v-if="team.my_role === 'owner'"
              size="small"
              text
              type="danger"
              class="team-leave-btn"
              @click="openDissolve(team)"
            >
              解散
            </el-button>
          </div>
        </div>
      </div>

      <div v-if="teams.length" class="capability-wrap">
        <div class="capability-title">
          <div class="capability-title-main">
            <span class="capability-badge"><el-icon><Key /></el-icon></span>
            <div>
              <h3>团队角色与权限</h3>
              <p>了解不同角色的权限边界，保障团队数据安全与协作秩序。</p>
            </div>
          </div>
          <div class="capability-tip">当前您可创建、加入并管理多个团队</div>
        </div>
        <div class="capability-grid">
          <div v-for="r in roleMatrix" :key="r.role" class="capability-card" :class="r.className">
            <div class="cap-card-head">
              <span class="cap-role-icon"><el-icon><CircleCheck /></el-icon></span>
              <b>{{ r.role }}</b>
            </div>
            <p class="cap-card-desc">{{ r.desc }}</p>
            <div class="cap-perms">
              <span v-for="(p, i) in rolePerms(r.role)" :key="i" class="cap-perm"><el-icon><CircleCheck /></el-icon>{{ p }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!loading" class="team-empty-wrap">
        <el-empty description="还没有加入任何团队" :image-size="120" />
        <div class="team-empty-tips">
          <div class="tips-title">如何加入团队？</div>
          <ol class="tips-list">
            <li>点击右上角「<b>加入团队</b>」，输入团队所有者或管理员发给您的<em>邀请链接</em>（或邀请 token）；</li>
            <li>邀请链接通常长这样：<code>http://localhost:5173/team/accept?token=xxxx</code>；</li>
            <li>加入成功后，团队将出现在下方列表，点击「<b>进入团队</b>」即可开始协作。</li>
          </ol>
          <div class="tips-alt">还没有团队？点击「<b>创建团队</b>」成为所有者，再邀请成员加入。</div>
        </div>
      </div>
    </div>

    <!-- 创建团队弹窗 -->
    <el-dialog v-model="createVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">创建团队</div>
          <div class="dialog-head-sub">创建者将自动成为团队所有者，并可邀请成员加入</div>
        </div>
      </template>

      <el-form label-position="top" class="team-form">
        <el-form-item label="团队名称" required>
          <el-input v-model="createForm.name" maxlength="64" show-word-limit placeholder="如：产品中心、研发一部" />
        </el-form-item>
        <el-form-item label="团队描述（可选）">
          <el-input v-model="createForm.description" type="textarea" :rows="3" maxlength="255" show-word-limit placeholder="介绍团队的定位与用途" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建团队</el-button>
      </template>
    </el-dialog>

    <!-- 编辑团队弹窗 -->
    <el-dialog v-model="editVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">编辑团队</div>
          <div class="dialog-head-sub">仅团队所有者或管理员可修改团队信息</div>
        </div>
      </template>

      <el-form label-position="top" class="team-form">
        <el-form-item label="团队名称" required>
          <el-input v-model="editForm.name" maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="团队描述（可选）">
          <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="submitEdit">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- 团队详情抽屉：概览 / 成员 / 邀请 / 动态 / 设置 -->
    <el-drawer v-model="detailVisible" append-to-body size="780px" direction="rtl" class="team-detail-drawer">
      <template #header>
        <div class="detail-hero">
          <div class="detail-hero-deco"></div>
          <div class="detail-hero-icon"><el-icon><OfficeBuilding /></el-icon></div>
          <div class="detail-hero-main">
            <div class="detail-hero-name">{{ detailTeam?.name || '团队详情' }}</div>
            <div class="detail-hero-sub">{{ detailTeam?.description || '暂无团队描述' }}</div>
            <div class="detail-hero-meta">
              <span><el-icon><User /></el-icon>{{ detailTeam ? detailTeam.members.length : 0 }} 名成员</span>
              <span><el-icon><OfficeBuilding /></el-icon>所有者 {{ detailTeam?.owner_name || `#${detailTeam?.owner_id}` }}</span>
              <span v-if="detailTeam?.create_time"><el-icon><Clock /></el-icon>创建于 {{ fmtDate(detailTeam?.create_time) }}</span>
            </div>
          </div>
          <div class="detail-hero-actions">
            <el-button v-if="canManage(detailTeam)" type="primary" plain :icon="Bell" @click="openSendNotice">发通知</el-button>
            <el-button v-if="detailTeam && detailTeam.my_role === 'owner'" type="danger" plain :icon="Delete" @click="openDissolve(detailTeam)">解散</el-button>
            <el-button v-else-if="detailTeam" type="danger" plain :icon="SwitchButton" @click="openExitApply(detailTeam)">退出</el-button>
          </div>
        </div>
      </template>

      <div v-loading="detailLoading">
        <template v-if="detailTeam">
          <!-- 概览统计条 -->
          <div class="detail-stats">
            <div v-for="s in detailStats" :key="s.label" class="detail-stat" :class="s.tone">
              <el-icon><component :is="s.icon" /></el-icon>
              <div class="detail-stat-meta"><b>{{ s.value }}</b><span>{{ s.label }}</span></div>
            </div>
          </div>

          <!-- 功能模块入口卡 -->
          <div class="detail-modules">
            <div class="module-card" @click="detailTab = 'shared'">
              <div class="module-icon module-icon-blue"><el-icon><Files /></el-icon></div>
              <div class="module-meta">
                <b>共享知识库</b>
                <span>{{ sharedTotal }} 篇共享文档</span>
              </div>
              <el-icon class="module-arrow"><ArrowRight /></el-icon>
            </div>
            <div class="module-card" @click="detailTab = 'attendance'">
              <div class="module-icon module-icon-green"><el-icon><Calendar /></el-icon></div>
              <div class="module-meta">
                <b>企业打卡</b>
                <span>{{ attendance ? attendanceLabel(attendance.my.status) : '加载中' }}</span>
              </div>
              <el-icon class="module-arrow"><ArrowRight /></el-icon>
            </div>
            <div class="module-card" @click="detailTab = 'approvals'">
              <div class="module-icon module-icon-amber"><el-icon><DataAnalysis /></el-icon></div>
              <div class="module-meta">
                <b>审批中心</b>
                <span>{{ canManageTeam ? (pendingCount ? `待审批 ${pendingCount.total}` : '无待办') : (pendingCount ? `我的待审批 ${pendingCount.total}` : '加载中') }}</span>
              </div>
              <el-icon class="module-arrow"><ArrowRight /></el-icon>
            </div>
          </div>

          <el-tabs v-model="detailTab" class="detail-tabs">
            <!-- 成员 -->
            <el-tab-pane label="成员" name="members">
              <div v-if="canManage(detailTeam)" class="invite-panel">
                <div class="detail-title">
                  <el-icon><Promotion /></el-icon> 邀请新成员
                </div>
                <div class="invite-row">
                  <el-input
                    v-model="inviteEmail"
                    placeholder="输入成员 QQ 邮箱，如 123456@qq.com"
                    class="invite-input"
                    clearable
                    @keyup.enter="submitInvite"
                  />
                  <el-button type="primary" :icon="Message" :loading="inviting" @click="submitInvite">发送邀请</el-button>
                </div>
                <div class="invite-hint">邀请链接将通过邮件发送至对方邮箱，有效期 48 小时。</div>
              </div>

              <div class="tab-toolbar">
                <div class="detail-title">
                  <el-icon><User /></el-icon> 成员列表（{{ filteredMembers.length }} / {{ detailTeam.members.length }}）
                </div>
                <el-input
                  v-model="memberKeyword"
                  placeholder="搜索姓名或邮箱"
                  size="small"
                  clearable
                  class="member-search"
                  :prefix-icon="Search"
                />
              </div>
              <div v-if="filteredMembers.length" class="member-list">
                <div v-for="m in filteredMembers" :key="m.user_id" class="member-item">
                  <span class="member-avatar">{{ avatarChar(m.username) }}</span>
                  <div class="member-main">
                    <div class="member-name">
                      {{ m.username }}
                      <el-tag :type="roleTag(m.role)" size="small" effect="light" class="status-tag">{{ roleLabel(m.role) }}</el-tag>
                    </div>
                    <div class="member-mail">{{ m.email }}</div>
                  </div>
                  <div class="member-time">{{ fmtDate(m.joined_at) }}</div>
                  <div class="member-ops">
                    <el-select
                      v-if="canChangeRole(detailTeam, m)"
                      :model-value="m.role"
                      size="small"
                      class="role-select"
                      :disabled="roleChanging"
                      @change="(val: string) => handleRoleChange(m, val)"
                    >
                      <el-option
                        v-for="opt in roleChangeOptions(detailTeam)"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      />
                    </el-select>
                    <el-button
                      v-if="detailTeam.my_role === 'owner' && m.role !== 'owner'"
                      size="small"
                      text
                      type="warning"
                      @click="handleTransfer(m)"
                    >
                      移交
                    </el-button>
                    <el-button
                      v-if="canRemove(detailTeam, m)"
                      size="small"
                      text
                      type="danger"
                      @click="handleRemove(m)"
                    >
                      移除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-else class="member-empty">暂无成员</div>
            </el-tab-pane>

            <!-- 邀请记录 -->
            <el-tab-pane :label="`邀请记录${detailTeam.invitations.filter((i) => i.status === 'pending').length ? '·' + detailTeam.invitations.filter((i) => i.status === 'pending').length : ''}`" name="invites">
              <div class="detail-title">
                <el-icon><Message /></el-icon> 邀请记录（{{ detailTeam.invitations.length }}）
              </div>
              <div v-if="detailTeam.invitations.length" class="invite-list">
                <div v-for="inv in detailTeam.invitations" :key="inv.id" class="invite-item">
                  <div class="invite-main">
                    <div class="invite-mail">{{ inv.email }}</div>
                    <div class="invite-sub">
                      <span v-if="inv.inviter_name">邀请人：{{ inv.inviter_name }}</span>
                      <span v-if="inv.create_time">发起：{{ fmtDate(inv.create_time) }}</span>
                      <span v-if="inv.expires_at">过期：{{ fmtDate(inv.expires_at) }}</span>
                    </div>
                  </div>
                  <el-tag :type="invTag(inv.status)" size="small" effect="light" class="status-tag">{{ invLabel(inv.status) }}</el-tag>
                  <el-button
                    v-if="inv.status === 'pending' && inv.accept_url"
                    size="small"
                    text
                    type="primary"
                    @click="copyLink(inv.accept_url)"
                  >
                    复制链接
                  </el-button>
                  <el-button
                    v-if="canManage(detailTeam) && inv.status === 'pending'"
                    size="small"
                    text
                    type="danger"
                    @click="handleRevoke(inv.id)"
                  >
                    撤销
                  </el-button>
                </div>
              </div>
              <div v-else class="member-empty">暂无邀请记录</div>
            </el-tab-pane>

            <!-- 团队动态 -->
            <el-tab-pane :label="`团队动态${teamLogs.length ? '·' + teamLogs.length : ''}`" name="logs">
              <div class="detail-title">
                <el-icon><Clock /></el-icon> 团队动态（{{ teamLogs.length }}）
              </div>
              <div v-if="teamLogs.length" class="log-list">
                <div v-for="log in teamLogs" :key="log.id" class="log-item">
                  <span class="log-dot"></span>
                  <div class="log-main">
                    <div class="log-message">{{ log.message }}</div>
                    <div class="log-sub">{{ fmtDate(log.create_time) }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="member-empty">暂无团队动态</div>
            </el-tab-pane>

            <!-- 团队设置 -->
            <el-tab-pane v-if="canManage(detailTeam)" label="团队设置" name="settings">
              <div class="settings-panel">
                <div class="detail-title">
                  <el-icon><Setting /></el-icon> 基本信息
                </div>
                <el-form label-position="top" class="team-form">
                  <el-form-item label="团队名称" required>
                    <el-input v-model="settingsForm.name" maxlength="64" show-word-limit />
                  </el-form-item>
                  <el-form-item label="团队描述（可选）">
                    <el-input v-model="settingsForm.description" type="textarea" :rows="3" maxlength="255" show-word-limit placeholder="介绍团队的定位与用途" />
                  </el-form-item>
                </el-form>
                <el-button type="primary" :loading="settingsSaving" @click="submitSettings">保存设置</el-button>

                <el-divider />

                <div class="detail-title danger-title">
                  <el-icon><Warning /></el-icon> 危险操作
                </div>
                <div class="danger-row">
                  <div class="danger-row-main">
                    <b>{{ detailTeam.my_role === 'owner' ? '解散团队' : '退出团队' }}</b>
                    <span>{{ detailTeam.my_role === 'owner' ? '解散后所有成员关系、邀请与动态将被清除，操作不可恢复。' : '退出后将无法查看该团队资料，需重新接受邀请才能加入。' }}</span>
                  </div>
                  <el-button v-if="detailTeam.my_role === 'owner'" type="danger" plain :icon="Delete" @click="openDissolve(detailTeam)">解散团队</el-button>
                  <el-button v-else type="danger" plain :icon="SwitchButton" @click="openExitApply(detailTeam)">退出团队</el-button>
                </div>
              </div>
            </el-tab-pane>

            <!-- 共享知识库 -->
            <el-tab-pane label="共享知识库" name="shared">
              <div class="tab-toolbar">
                <div class="detail-title">
                  <el-icon><Files /></el-icon> 共享知识库（{{ sharedTotal }}）
                </div>
                <div class="shared-hint">团队所有者上传的文档对全体成员可见，下载需向所有者/管理员申请审批。</div>
              </div>
              <div v-loading="sharedLoading">
                <div v-if="sharedDocs.length" class="shared-list">
                  <div v-for="doc in sharedDocs" :key="doc.id" class="shared-item">
                    <div class="shared-main">
                      <div class="shared-name">{{ doc.doc_name }}</div>
                      <div class="shared-sub">
                        <span>{{ doc.origin_file_name }}</span>
                        <span>{{ (doc.file_type || '').toUpperCase() }}</span>
                        <span v-if="doc.file_size">{{ (doc.file_size / 1024).toFixed(0) }} KB</span>
                        <span>v{{ doc.version_no }}</span>
                        <span v-if="doc.owner_name">所有者 {{ doc.owner_name }}</span>
                      </div>
                    </div>
                    <div class="shared-ops">
                      <el-button size="small" text type="primary" @click="openSharedSummary(doc)">详情</el-button>
                      <el-button size="small" type="primary" plain @click="openDownloadApply(doc)">申请下载</el-button>
                    </div>
                  </div>
                </div>
                <div v-else-if="!sharedLoading" class="member-empty">暂无共享文档</div>
              </div>
            </el-tab-pane>

            <!-- 企业打卡 -->
            <el-tab-pane label="企业打卡" name="attendance">
              <div v-loading="attendanceLoading" class="attend-wrap">
                <div v-if="attendance" class="attend-today">
                  <div class="attend-today-card">
                    <div class="attend-head">
                      <div class="attend-date">{{ attendance.date }}</div>
                      <div class="attend-head-right">
                        <el-tag :type="attendanceTag(attendance.my.status)" size="small" effect="light" class="status-tag">
                          {{ attendanceLabel(attendance.my.status) }}
                        </el-tag>
                        <el-button size="small" text class="geo-link" :icon="Location" @click="openGeoDialog">
                          工作区域
                          <el-tag v-if="geo.configured" size="small" :type="geo.enabled === false ? 'danger' : 'success'" effect="plain" class="geo-state">
                            {{ geo.enabled === false ? '已停用' : '已配置' }}
                          </el-tag>
                          <el-tag v-else size="small" type="warning" effect="plain" class="geo-state">未配置</el-tag>
                        </el-button>
                      </div>
                    </div>
                    <div class="attend-shift-grid">
                      <div v-for="def in SLOT_DEFS" :key="def.key" class="attend-shift-item"
                           :class="{ done: attendance.my.slots[def.key].done, missing: attendance.my.slots[def.key].missing }">
                        <div class="shift-label">
                          <span class="shift-dot"></span>{{ def.label }}
                        </div>
                        <div class="shift-time">{{ def.time }}</div>
                        <div class="shift-status">
                          <template v-if="attendance.my.slots[def.key].done">
                            <el-icon class="shift-check"><CircleCheck /></el-icon>
                            {{ fmtClock(attendance.my.slots[def.key].time) }}
                          </template>
                          <template v-else-if="attendance.my.slots[def.key].missing">
                            <el-tag type="danger" size="small" effect="plain" class="shift-missing">已缺卡</el-tag>
                            <el-button
                              size="small"
                              type="primary"
                              plain
                              class="shift-btn"
                              @click="openFixDialog(def.key)"
                            >申请补卡</el-button>
                          </template>
                          <template v-else>
                            <el-button
                              size="small"
                              class="shift-btn"
                              :disabled="!slotClockable(def)"
                              :loading="clocking && clockingSlot === def.key"
                              @click="handleClock(def.key)"
                            >{{ slotNotYet(def) ? '未到时间' : '打卡' }}</el-button>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="attend-stats">
                    <div class="attend-stat">
                      <b>{{ attendance.stats.am_in_count }}</b>
                      <span>上午上班 / {{ attendance.stats.member_count }} 人</span>
                    </div>
                    <div class="attend-stat">
                      <b>{{ attendance.stats.am_out_count }}</b>
                      <span>上午下班</span>
                    </div>
                    <div class="attend-stat">
                      <b>{{ attendance.stats.pm_in_count }}</b>
                      <span>下午上班</span>
                    </div>
                    <div class="attend-stat">
                      <b>{{ attendance.stats.pm_out_count }}</b>
                      <span>下午下班</span>
                    </div>
                    <div class="attend-stat">
                      <b>{{ attendance.stats.attendance_rate }}%</b>
                      <span>今日出勤率</span>
                    </div>
                    <div class="attend-stat">
                      <b>{{ attendance.stats.latest_clock ? fmtClock(attendance.stats.latest_clock) : '-' }}</b>
                      <span>最近打卡</span>
                    </div>
                  </div>

                  <!-- 近 7 天团队出勤汇总 -->
                  <div class="attend-summary">
                    <div class="detail-title">
                      <el-icon><Histogram /></el-icon> 近 7 天团队出勤
                      <el-button size="small" text :icon="Refresh" :loading="summaryLoading" @click="loadSummary(detailTeam!.id)">刷新</el-button>
                    </div>
                    <div v-if="attendanceSummaryData" class="summary-table">
                      <div class="summary-row summary-head">
                        <span>日期</span><span>上午上班</span><span>上午下班</span><span>下午上班</span><span>下午下班</span><span>出勤率</span>
                      </div>
                      <div v-for="d in attendanceSummaryData.days" :key="d.date" class="summary-row">
                        <span>{{ d.date }}</span><span>{{ d.am_in }}</span><span>{{ d.am_out }}</span><span>{{ d.pm_in }}</span><span>{{ d.pm_out }}</span><span>{{ d.attendance_rate }}%</span>
                      </div>
                    </div>
                    <div v-else class="member-empty">暂无出勤数据</div>
                  </div>
                </div>
                <div class="attend-records">
                  <div class="detail-title"><el-icon><Calendar /></el-icon> 我的打卡记录</div>
                  <div v-if="myAttendanceRecords.length" class="attend-list">
                    <div v-for="r in myAttendanceRecords" :key="r.id" class="attend-record-item">
                      <span class="attend-record-date">{{ r.date }}</span>
                      <span class="attend-record-time">上午上班 {{ r.am_in_time ? fmtClock(r.am_in_time) : '-' }}<el-tag v-if="(r.missing_slots || []).includes('am_in')" type="danger" size="small" effect="plain" class="record-missing">缺卡</el-tag></span>
                      <span class="attend-record-time">上午下班 {{ r.am_out_time ? fmtClock(r.am_out_time) : '-' }}<el-tag v-if="(r.missing_slots || []).includes('am_out')" type="danger" size="small" effect="plain" class="record-missing">缺卡</el-tag></span>
                      <span class="attend-record-time">下午上班 {{ r.pm_in_time ? fmtClock(r.pm_in_time) : '-' }}<el-tag v-if="(r.missing_slots || []).includes('pm_in')" type="danger" size="small" effect="plain" class="record-missing">缺卡</el-tag></span>
                      <span class="attend-record-time">下午下班 {{ r.pm_out_time ? fmtClock(r.pm_out_time) : '-' }}<el-tag v-if="(r.missing_slots || []).includes('pm_out')" type="danger" size="small" effect="plain" class="record-missing">缺卡</el-tag></span>
                      <el-button
                        v-if="(r.missing_slots || []).length"
                        size="small"
                        type="primary"
                        plain
                        class="record-fix-btn"
                        @click="openFixDialog((r.missing_slots || [])[0], r.date)"
                      >申请补卡</el-button>
                    </div>
                  </div>
                  <div v-else class="member-empty">暂无打卡记录</div>
                </div>
              </div>

              <!-- 工作区域（地理围栏）配置弹窗 -->
              <el-dialog v-model="geoVisible" title="工作区域（地理围栏）配置" width="520px" append-to-body>
                <div v-loading="geoLoading">
                  <el-alert v-if="!geo.configured" type="warning" :closable="false" show-icon
                    title="团队尚未配置工作区域，成员将无法打卡" class="geo-tip" />
                  <el-form label-width="90px">
                    <el-form-item label="中心纬度">
                      <el-input-number v-model="geoForm.lat" :precision="6" :step="0.0001" :controls="false" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="中心经度">
                      <el-input-number v-model="geoForm.lng" :precision="6" :step="0.0001" :controls="false" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="围栏半径(米)">
                      <el-input-number v-model="geoForm.radius_m" :min="50" :max="200000" :step="50" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="启用围栏">
                      <el-switch v-model="geoForm.enabled" />
                    </el-form-item>
                    <el-form-item label="快速定位">
                      <el-button :loading="locating" :icon="Location" @click="useMyLocationForGeo">使用我的当前位置</el-button>
                      <span class="geo-hint">打卡将校验成员是否位于此围栏内，请以企业办公地址为中心配置</span>
                    </el-form-item>
                  </el-form>
                </div>
                <template #footer>
                  <el-button @click="geoVisible = false">取消</el-button>
                  <el-button type="primary" @click="saveGeo">保存</el-button>
                </template>
              </el-dialog>
            </el-tab-pane>

            <!-- 审批中心 -->
            <el-tab-pane label="审批中心" name="approvals">
              <div v-if="canManageTeam" class="approval-panel">
                <div class="approval-block">
                  <div class="tab-toolbar">
                    <div class="detail-title"><el-icon><Files /></el-icon> 下载审批（{{ downloadApprovalTotal }}）</div>
                    <div class="approval-filters">
                      <el-select v-model="downloadApprovalStatus" size="small" style="width: 110px" @change="loadDownloadApprovals(detailTeam!.id)">
                        <el-option v-for="o in APPROVAL_STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                      </el-select>
                      <el-button size="small" text :icon="Refresh" @click="loadDownloadApprovals(detailTeam!.id)">刷新</el-button>
                    </div>
                  </div>
                  <div v-if="downloadApprovals.length" class="approval-list">
                    <div v-for="ap in downloadApprovals" :key="ap.id" class="approval-item">
                      <div class="approval-main">
                        <div class="approval-name">
                          {{ ap.doc_name }}
                          <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                        </div>
                        <div class="approval-sub">
                          <span>申请人 {{ ap.applicant_name }}</span>
                          <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                          <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                        </div>
                      </div>
                      <div class="approval-ops">
                        <el-button v-if="ap.status === 'pending'" size="small" type="success" plain @click="handleApproveDownload(ap)">通过</el-button>
                        <el-button v-if="ap.status === 'pending'" size="small" type="danger" plain @click="handleRejectDownload(ap)">拒绝</el-button>
                        <el-button v-if="ap.status === 'approved'" size="small" type="primary" plain @click="downloadByApproval(ap)">下载</el-button>
                      </div>
                    </div>
                  </div>
                  <div v-else class="approval-empty">
                    <div class="approval-empty-title">暂无下载审批记录</div>
                    <div class="approval-empty-hint">
                      成员在「共享知识库」页签发起文档下载申请后，待办会出现在这里。若成员尚未上传共享文档，可先到「共享知识库」页签完成上传，再请成员发起一次下载申请进行验证。
                    </div>
                  </div>
                </div>

                <el-divider />

                <div class="approval-block">
                  <div class="tab-toolbar">
                    <div class="detail-title"><el-icon><SwitchButton /></el-icon> 退出审批（{{ exitApprovalTotal }}）</div>
                    <div class="approval-filters">
                      <el-select v-model="exitApprovalStatus" size="small" style="width: 110px" @change="loadExitApprovals(detailTeam!.id)">
                        <el-option v-for="o in APPROVAL_STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                      </el-select>
                      <el-button size="small" text :icon="Refresh" @click="loadExitApprovals(detailTeam!.id)">刷新</el-button>
                    </div>
                  </div>
                  <div v-if="exitApprovals.length" class="approval-list">
                    <div v-for="ap in exitApprovals" :key="ap.id" class="approval-item">
                      <div class="approval-main">
                        <div class="approval-name">
                          {{ ap.applicant_name }}
                          <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                        </div>
                        <div class="approval-sub">
                          <span>{{ ap.applicant_email }}</span>
                          <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                          <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                        </div>
                      </div>
                      <div class="approval-ops">
                        <el-button v-if="ap.status === 'pending'" size="small" type="success" plain @click="handleApproveExit(ap)">通过并移除</el-button>
                        <el-button v-if="ap.status === 'pending'" size="small" type="danger" plain @click="handleRejectExit(ap)">拒绝</el-button>
                      </div>
                    </div>
                  </div>
                  <div v-else class="approval-empty">
                    <div class="approval-empty-title">暂无退出审批记录</div>
                    <div class="approval-empty-hint">
                      成员在团队详情中提交退出申请后，审批待办会出现在这里。退出申请仅对非团队创建人可见，创建人退出需先完成团队移交。
                    </div>
                  </div>
                </div>

                <el-divider />

                <div class="approval-block">
                  <div class="tab-toolbar">
                    <div class="detail-title"><el-icon><Calendar /></el-icon> 考勤补卡审批（{{ fixApprovals.length }}）</div>
                    <div class="approval-filters">
                      <el-select v-model="fixApprovalStatus" size="small" style="width: 110px" @change="loadFixApprovals(detailTeam!.id)">
                        <el-option v-for="o in APPROVAL_STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                      </el-select>
                      <el-button size="small" text :icon="Refresh" @click="loadFixApprovals(detailTeam!.id)">刷新</el-button>
                    </div>
                  </div>
                  <div v-if="fixApprovals.length" class="approval-list">
                    <div v-for="ap in fixApprovals" :key="ap.id" class="approval-item">
                      <div class="approval-main">
                        <div class="approval-name">
                          {{ ap.applicant_name }} · {{ ap.date }} {{ ap.slot_label }}
                          <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                        </div>
                        <div class="approval-sub">
                          <span v-if="ap.applicant_email">{{ ap.applicant_email }}</span>
                          <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                          <span v-if="ap.reject_reason">拒绝原因：{{ ap.reject_reason }}</span>
                          <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                        </div>
                      </div>
                      <div class="approval-ops">
                        <el-button v-if="ap.status === 'pending'" size="small" type="success" plain @click="handleApproveFix(ap)">通过并修正</el-button>
                        <el-button v-if="ap.status === 'pending'" size="small" type="danger" plain @click="handleRejectFix(ap)">拒绝</el-button>
                      </div>
                    </div>
                  </div>
                  <div v-else class="approval-empty">
                    <div class="approval-empty-title">暂无补卡审批记录</div>
                    <div class="approval-empty-hint">
                      成员在「考勤打卡」中提交补卡申请后，审批待办会出现在这里。审批通过后系统自动补写该日打卡记录，同一日期重复申请会被拒绝。
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="approval-panel">
                <div class="tab-toolbar">
                  <div class="detail-title"><el-icon><DataAnalysis /></el-icon> 我的申请</div>
                  <el-button size="small" type="primary" plain :icon="Calendar" @click="openFixDialog">补卡申请</el-button>
                </div>
                <div v-if="myApprovalRecords">
                  <div class="approval-block">
                    <div class="approval-sub-title">下载申请</div>
                    <div v-if="myApprovalRecords.downloads.length" class="approval-list">
                      <div v-for="ap in myApprovalRecords.downloads" :key="ap.id" class="approval-item">
                        <div class="approval-main">
                          <div class="approval-name">
                            {{ ap.doc_name }}
                            <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                          </div>
                          <div class="approval-sub">
                            <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                            <span v-if="ap.reject_reason">拒绝原因：{{ ap.reject_reason }}</span>
                            <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                          </div>
                        </div>
                        <div class="approval-ops">
                          <el-button v-if="ap.status === 'approved'" size="small" type="primary" plain @click="downloadByApproval(ap)">下载</el-button>
                        </div>
                      </div>
                    </div>
                    <div v-else class="approval-empty">
                      <div class="approval-empty-title">暂无下载申请</div>
                      <div class="approval-empty-hint">到「共享知识库」页签选择文档点击下载，需要审批的申请会先出现在这里，审批通过后即可直接下载。</div>
                    </div>
                  </div>
                  <div class="approval-block">
                    <div class="approval-sub-title">退出申请</div>
                    <div v-if="myApprovalRecords.exits.length" class="approval-list">
                      <div v-for="ap in myApprovalRecords.exits" :key="ap.id" class="approval-item">
                        <div class="approval-main">
                          <div class="approval-name">
                            退出团队申请
                            <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                          </div>
                          <div class="approval-sub">
                            <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                            <span v-if="ap.reject_reason">拒绝原因：{{ ap.reject_reason }}</span>
                            <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else class="approval-empty">
                      <div class="approval-empty-title">暂无退出申请</div>
                      <div class="approval-empty-hint">如需退出团队，在团队详情底部提交退出申请，由团队所有者/管理员审批后生效；创建人需先完成团队移交。</div>
                    </div>
                  </div>
                  <div class="approval-block">
                    <div class="approval-sub-title">补卡申请</div>
                    <div v-if="myApprovalRecords.fixes.length" class="approval-list">
                      <div v-for="ap in myApprovalRecords.fixes" :key="ap.id" class="approval-item">
                        <div class="approval-main">
                          <div class="approval-name">
                            {{ ap.date }} {{ ap.slot_label }}
                            <el-tag :type="approvalTag(ap.status)" size="small" effect="light" class="status-tag">{{ approvalLabel(ap.status) }}</el-tag>
                          </div>
                          <div class="approval-sub">
                            <span v-if="ap.reason">理由：{{ ap.reason }}</span>
                            <span v-if="ap.reject_reason">拒绝原因：{{ ap.reject_reason }}</span>
                            <span v-if="ap.apply_time">申请于 {{ fmtDate(ap.apply_time) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else class="approval-empty">
                      <div class="approval-empty-title">暂无补卡申请</div>
                      <div class="approval-empty-hint">点击右上角「补卡申请」，选择需要补卡的日期与时段后提交，审批进度会显示在这里；审批通过后系统自动补写当日打卡记录。</div>
                    </div>
                  </div>
                </div>
                <div v-else class="approval-empty">
                  <div class="approval-empty-title">暂无申请记录</div>
                  <div class="approval-empty-hint">你还没有发起过下载、退出或补卡申请。到「共享知识库」页签下载文档，或点击右上角「补卡申请」提交一条即可看到审批进度。</div>
                </div>
              </div>
            </el-tab-pane>
            <!-- 自定义角色管理（仅所有者可见） -->
            <el-tab-pane v-if="detailTeam && detailTeam.my_role === 'owner'" label="角色管理" name="roles">
              <div class="roles-head">
                <div class="roles-head-info">
                  <div class="roles-head-title">角色与权限矩阵</div>
                  <div class="roles-head-sub">自建角色并勾选权限点，将角色分配给成员后即可生效</div>
                </div>
                <el-button type="primary" plain size="small" :icon="Plus" @click="openRoleCreate">+ 新建角色</el-button>
              </div>
              <div class="roles-list" v-loading="roleTabLoading">
                <div v-for="r in roleList" :key="r.role_key" class="role-row">
                  <div class="role-row-main">
                    <div class="role-row-name">
                      <span class="role-name-text">{{ r.role_name }}</span>
                      <el-tag v-if="r.built_in" size="small" effect="plain" type="info">内置</el-tag>
                      <el-tag v-else size="small" effect="light" type="success">自定义</el-tag>
                      <span class="role-count">成员 {{ r.member_count }}</span>
                    </div>
                    <div class="role-row-perms" :title="rolePermLabel(r)">
                      <template v-if="r.perms.length">
                        <el-tag v-for="p in r.perms" :key="p" size="small" effect="plain" class="perm-tag">{{ permLabel(p) }}</el-tag>
                      </template>
                      <span v-else class="perm-empty">无权限</span>
                    </div>
                    <div class="role-row-remark">{{ r.remark || (r.built_in ? '系统内置角色，权限固定' : '') }}</div>
                  </div>
                  <div class="role-row-actions">
                    <el-button v-if="!r.built_in" size="small" text type="primary" :icon="EditPen" @click="openRoleEdit(r)">编辑</el-button>
                    <el-button v-if="!r.built_in" size="small" text type="danger" :icon="Delete" :loading="roleDeleting" @click="removeRole(r)">删除</el-button>
                  </div>
                </div>
                <div v-if="!roleList.length" class="member-empty">暂无角色数据</div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </el-drawer>

    <!-- 共享文档摘要弹窗 -->
    <el-dialog v-model="sharedSummaryVisible" append-to-body width="560px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">共享文档详情</div>
          <div class="dialog-head-sub">{{ sharedSummary?.doc_name || '' }}</div>
        </div>
      </template>
      <div v-if="sharedSummary" class="summary-body">
        <div class="summary-meta">
          <span>类型 {{ (sharedSummary.file_type || '').toUpperCase() }}</span>
          <span v-if="sharedSummary.file_size">大小 {{ (sharedSummary.file_size / 1024).toFixed(0) }} KB</span>
          <span>版本 v{{ sharedSummary.version_no }}</span>
          <span v-if="sharedSummary.owner_name">所有者 {{ sharedSummary.owner_name }}</span>
          <span v-if="sharedSummary.update_time">更新 {{ fmtDate(sharedSummary.update_time) }}</span>
        </div>
        <div v-if="sharedSummary.summary" class="summary-content">{{ sharedSummary.summary }}</div>
  <div v-if="sharedSummary.content_preview" class="detail-section" :class="{ 'preview-empty': !sharedSummary.content_preview }">
    <div class="section-title clickable" @click="sharedSummaryPreviewExpanded = !sharedSummaryPreviewExpanded">
      正文预览<span v-if="sharedSummary.content_pages" class="preview-pages">共 {{ sharedSummary.content_pages }} 段</span>（{{ sharedSummaryPreviewExpanded ? '收起' : '展开' }}）
    </div>
    <div v-if="sharedSummaryPreviewExpanded" class="preview-body">
      <pre>{{ sharedSummary.content_preview }}</pre>
    </div>
  </div>
  <div v-else-if="sharedSummary && !sharedSummary.summary" class="summary-content preview-empty">该文档暂无正文内容（可能仍在解析中或格式暂不支持预览）</div>
        <div v-else class="summary-content empty">暂无摘要</div>
      </div>
      <template #footer>
        <el-button @click="sharedSummaryVisible = false">关闭</el-button>
        <el-button v-if="sharedSummary && detailTeam" type="primary" @click="openDownloadApply(sharedSummary); sharedSummaryVisible = false">申请下载</el-button>
      </template>
    </el-dialog>

    <!-- 自定义角色编辑弹窗（权限矩阵） -->
    <el-dialog v-model="roleDlgVisible" append-to-body width="600px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">{{ roleDlgEditing ? '编辑角色' : '新建自定义角色' }}</div>
          <div class="dialog-head-sub">配置权限矩阵，保存后可在成员管理中分配该角色</div>
        </div>
      </template>
      <div class="role-form">
        <div class="role-form-row">
          <span class="role-form-label">角色名称</span>
          <el-input v-model="roleForm.role_name" maxlength="64" placeholder="如：财务审核员、外协专员" class="role-form-input" />
        </div>
        <div class="role-form-row">
          <span class="role-form-label">备注说明</span>
          <el-input v-model="roleForm.remark" maxlength="255" placeholder="选填，说明该角色的职责范围" class="role-form-input" />
        </div>
        <div class="role-form-row role-form-perm-row">
          <span class="role-form-label">权限矩阵</span>
          <div class="perm-matrix">
            <label v-for="p in permCatalog" :key="p.key" class="perm-item">
              <el-checkbox v-model="roleForm.perms" :value="p.key">{{ p.label }}</el-checkbox>
            </label>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="roleDlgVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleTabLoading" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- 下载申请弹窗 -->
    <el-dialog v-model="downloadVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">申请下载</div>
          <div class="dialog-head-sub">《{{ downloadTarget?.doc_name || '' }}》需经团队所有者/管理员审批</div>
        </div>
      </template>
      <el-form label-position="top" class="team-form">
        <el-form-item label="申请理由（可填）">
          <el-input v-model="downloadForm.reason" type="textarea" :rows="3" maxlength="255" show-word-limit placeholder="说明下载用途，便于审批人快速通过" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="downloadVisible = false">取消</el-button>
        <el-button type="primary" :loading="downloadSubmitting" @click="submitDownloadApply">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 补卡申请弹窗 -->
    <el-dialog v-model="fixVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">考勤补卡申请</div>
          <div class="dialog-head-sub">迟到 / 漏卡时段可提交申请，经团队管理员审批后自动修正打卡记录</div>
        </div>
      </template>
      <el-form label-position="top" class="team-form">
        <el-form-item label="补卡日期" required>
          <el-date-picker v-model="fixForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled-date="(d: Date) => d.getTime() > Date.now()" placeholder="选择漏卡日期" />
        </el-form-item>
        <el-form-item label="补卡时段" required>
          <el-radio-group v-model="fixForm.slot">
            <el-radio-button v-for="o in FIX_SLOT_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="申请理由">
          <el-input v-model="fixForm.reason" type="textarea" :rows="3" maxlength="200" show-word-limit placeholder="说明迟到/漏卡原因，便于管理员快速审批" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fixVisible = false">取消</el-button>
        <el-button type="primary" :loading="fixSubmitting" @click="submitFix">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 解散团队二次确认弹窗（需输入团队名，确认按钮锁定直到输入一致） -->
    <el-dialog v-model="dissolveVisible" append-to-body width="460px" class="ks-dialog" :close-on-click-modal="false" @closed="dissolveName = ''">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title danger-title">解散团队</div>
          <div class="dialog-head-sub">此操作不可恢复，请谨慎操作</div>
        </div>
      </template>
      <div class="dissolve-confirm">
        <div class="dissolve-warn">
          <span class="dissolve-warn-icon"><el-icon><Warning /></el-icon></span>
          <div>
            即将解散团队 <b>「{{ dissolveTarget?.name }}」</b>，解散后将移除全部成员、清空邀请与动态记录，<b class="danger-text">且无法恢复</b>。
          </div>
        </div>
        <div class="dissolve-input-label">请输入团队名称以确认：</div>
        <el-input
          v-model="dissolveName"
          size="large"
          :placeholder="`输入「${dissolveTarget?.name || ''}」以解锁确认按钮`"
          clearable
          @keyup.enter="confirmDissolve()"
        />
        <div v-if="dissolveName && !dissolveInputMatched" class="dissolve-mismatch">
          团队名称不一致，无法解散
        </div>
      </div>
      <template #footer>
        <el-button @click="dissolveVisible = false">取消</el-button>
        <el-button
          type="danger"
          :disabled="!dissolveInputMatched"
          :loading="dissolving"
          @click="confirmDissolve"
        >
          确认解散
        </el-button>
      </template>
    </el-dialog>

    <!-- 加入团队弹窗 -->
    <el-dialog v-model="joinVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">加入团队</div>
          <div class="dialog-head-sub">输入团队所有者或管理员发送的邀请链接 / token 即可加入</div>
        </div>
      </template>

      <el-form label-position="top" class="team-form" @submit.prevent="submitJoin">
        <el-form-item label="邀请链接或 Token" required>
          <el-input
            v-model="joinForm.input"
            type="textarea"
            :rows="2"
            placeholder="粘贴完整邀请链接，或仅输入邀请 token，例如：http://localhost:5173/team/accept?token=xxxx"
            clearable
          />
        </el-form-item>
        <div class="join-tip">
          校验规则：邀请 token 须有效、未过期；当前登录邮箱须与邀请邮箱一致，否则将提示失败。
        </div>
      </el-form>

      <template #footer>
        <el-button @click="joinVisible = false">取消</el-button>
        <el-button type="primary" :loading="joining" @click="submitJoin">加入团队</el-button>
      </template>
    </el-dialog>

    <!-- 发团队通知弹窗 -->
    <el-dialog v-model="noticeVisible" append-to-body width="520px" class="ks-dialog">
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">发团队通知</div>
          <div class="dialog-head-sub">通知将发送给团队全体成员（您自己不计未读），成员可在顶栏铃铛中查看</div>
        </div>
      </template>

      <el-form label-position="top" class="team-form">
        <el-form-item label="通知标题" required>
          <el-input v-model="noticeForm.title" maxlength="64" show-word-limit placeholder="如：本周团队例会通知" />
        </el-form-item>
        <el-form-item label="通知内容" required>
          <el-input v-model="noticeForm.content" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="请输入通知正文" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="noticeVisible = false">取消</el-button>
        <el-button type="primary" :loading="noticeSending" @click="submitNotice">发送通知</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}

.team-title {
  margin-bottom: 4px;
}

.page-sub {
  font-size: 13px;
  color: var(--ks-text-secondary);
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.team-card {
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

.team-card:hover {
  transform: translateY(-5px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow:
    0 18px 40px rgba(15, 23, 42, 0.1),
    0 8px 22px rgba(37, 99, 235, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.96);
}

.team-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.team-name {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.team-name-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.2px;
  line-height: 1.35;
  color: var(--ks-text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  color: var(--ks-primary);
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.28s ease, color 0.28s ease, background 0.28s ease, box-shadow 0.28s ease;
}

.team-card:hover .team-icon {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #4338ca);
  transform: rotate(-8deg) scale(1.08);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
}

.team-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ks-text-body);
  min-height: 20px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.team-desc.empty {
  color: #94a3b8;
}

.team-meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  line-height: 1.6;
  color: #5b6b84;
}

.team-actions {
  border-top: 1px solid #f1f5f9;
  padding-top: 10px;
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 状态标签：胶囊造型（与 AgentTaskView 体系一致） */
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

/* ---------------- 弹窗 ---------------- */
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

.team-form {
  padding-top: 4px;
}

/* ---------------- 详情 ---------------- */
.invite-panel {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.7), rgba(248, 251, 255, 0.5));
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 4px;
}

.invite-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.invite-input {
  flex: 1;
}

.invite-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 8px;
}

.invite-link-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.invite-link-input {
  flex: 1;
}

.role-select {
  width: 96px;
  margin-right: 4px;
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

.member-list,
.invite-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.member-item:hover {
  border-color: rgba(37, 99, 235, 0.3);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.07);
}

.member-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
}

.member-main {
  flex: 1;
  min-width: 0;
}

.member-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-title);
}

.member-mail {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.member-time {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}

.member-ops {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.invite-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
}

.invite-main {
  flex: 1;
  min-width: 0;
}

.invite-mail {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-title);
  word-break: break-all;
}

.invite-sub {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.member-empty {
  padding: 18px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.6);
}

.approval-empty {
  padding: 22px 18px;
  text-align: center;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.6);
}

.approval-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
}

.approval-empty-hint {
  margin-top: 8px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #94a3b8;
  max-width: 560px;
  margin-left: auto;
  margin-right: auto;
}

/* ---------------- 空态引导 ---------------- */
.team-empty-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 0 8px;
}

.team-empty-tips {
  max-width: 560px;
  width: 100%;
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.85), rgba(255, 255, 255, 0.9));
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

.tips-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ks-text-title);
  margin-bottom: 10px;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ks-text-body);
}

.tips-list code {
  background: #eef2ff;
  color: #4338ca;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 12px;
  word-break: break-all;
}

.tips-alt {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e2e8f0;
  font-size: 13px;
  color: #64748b;
}

/* ---------------- 团队操作行 ---------------- */
.team-opts-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

/* ---------------- 加入团队 ---------------- */
.join-tip {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 8px 12px;
}

/* ---------------- 团队动态 ---------------- */
.log-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 300px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid #f1f5f9;
}

.log-item:last-child {
  border-bottom: none;
}

.log-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.log-main {
  flex: 1;
  min-width: 0;
}

.log-message {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ks-text-body);
  word-break: break-word;
}

.log-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.team-leave-btn {
  margin-left: auto;
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

  .team-grid {
    grid-template-columns: 1fr;
  }

  /* 详情弹窗内成员/邀请行窄屏布局 */
  .member-item {
    flex-wrap: wrap;
    gap: 8px;
  }

  .member-time {
    display: none;
  }

  .member-ops {
    width: 100%;
    justify-content: flex-end;
  }

  .invite-row {
    flex-direction: column;
    align-items: stretch;
  }

  .invite-row .el-button {
    width: 100%;
    margin-left: 0;
  }

  .team-empty-tips {
    padding: 14px 16px;
  }

  /* 组织中心窄屏：横幅/统计/权限区单列 */
  .org-hero-main {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .org-stats {
    grid-template-columns: repeat(2, 1fr);
    margin-top: 12px;
  }

  .capability-grid {
    grid-template-columns: 1fr;
  }

  .detail-hero {
    align-items: flex-start;
  }

  .detail-hero-actions {
    display: none;
  }

  .detail-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .tab-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}

/* ---------------- 组织中心：品牌横幅 + 数据总览 ---------------- */
.org-hero {
  position: relative;
  border-radius: 18px;
  padding: 22px 24px 18px;
  margin-bottom: 20px;
  background:
    radial-gradient(1200px 500px at 12% -20%, rgba(56, 189, 248, 0.22), transparent 60%),
    radial-gradient(900px 420px at 108% 0%, rgba(129, 140, 248, 0.30), transparent 55%),
    radial-gradient(700px 380px at 50% 130%, rgba(16, 185, 129, 0.10), transparent 60%),
    linear-gradient(140deg, #050b1c 0%, #0a1838 38%, #102a5e 72%, #16357f 100%);
  border: 1px solid rgba(147, 197, 253, 0.22);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.10),
    inset 0 0 0 1px rgba(255, 255, 255, 0.02),
    0 18px 40px -18px rgba(2, 8, 26, 0.85);
  overflow: hidden;
}

/* 背景网格纹理（高端质感） */
.org-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(147, 197, 253, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(147, 197, 253, 0.05) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(ellipse 90% 80% at 30% 20%, #000 40%, transparent 100%);
  pointer-events: none;
}

.org-hero-deco {
  position: absolute;
  top: -120px;
  right: -80px;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.40), rgba(99, 102, 241, 0.18) 45%, transparent 70%);
  filter: blur(46px);
  pointer-events: none;
}

.org-hero-deco::after {
  content: '';
  position: absolute;
  left: -140px;
  bottom: -180px;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.20), transparent 70%);
  filter: blur(40px);
}

.org-hero-main {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.org-hero .team-title {
  color: #f8fafc;
  margin-bottom: 6px;
}

.org-hero .page-sub {
  color: rgba(191, 219, 254, 0.85);
}

.org-hero-btn {
  border-color: rgba(147, 197, 253, 0.35);
  color: #dbeafe;
  background: rgba(255, 255, 255, 0.06);
}

.org-hero-btn:hover {
  color: #fff;
  border-color: rgba(147, 197, 253, 0.6);
  background: rgba(255, 255, 255, 0.12);
}

.org-hero-btn.el-button--primary {
  border-color: transparent;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
}

.org-stats {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 18px;
}

.org-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.09);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.org-stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #fff;
  flex-shrink: 0;
}

.org-stat-icon.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.org-stat-icon.amber { background: linear-gradient(135deg, #f59e0b, #d97706); }
.org-stat-icon.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.org-stat-icon.green { background: linear-gradient(135deg, #10b981, #059669); }

.org-stat-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.org-stat-meta b {
  font-size: 20px;
  font-weight: 800;
  color: #f8fafc;
  line-height: 1.1;
}

.org-stat-meta span {
  font-size: 12px;
  color: rgba(191, 219, 254, 0.85);
  margin-top: 2px;
  white-space: nowrap;
}

/* 团队卡片元信息 chip */
.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 999px;
  padding: 2px 9px;
}

.meta-chip .el-icon {
  font-size: 12px;
  color: #94a3b8;
}

/* ---------------- 角色权限能力区 ---------------- */
.capability-wrap {
  margin-top: 24px;
}

.capability-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.capability-title-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.capability-badge {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  box-shadow: 0 8px 20px rgba(139, 92, 246, 0.28);
}

.capability-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--ks-text-title);
}

.capability-title p {
  margin: 2px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.capability-tip {
  font-size: 12px;
  color: #64748b;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  padding: 5px 12px;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.capability-card {
  border-radius: 14px;
  padding: 16px 16px 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.capability-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.1);
}

.capability-card.rk-owner { border-top: 3px solid #f59e0b; }
.capability-card.rk-admin { border-top: 3px solid #3b82f6; }
.capability-card.rk-member { border-top: 3px solid #10b981; }

.cap-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cap-role-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
  flex-shrink: 0;
}

.rk-owner .cap-role-icon { background: linear-gradient(135deg, #f59e0b, #d97706); }
.rk-admin .cap-role-icon { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.rk-member .cap-role-icon { background: linear-gradient(135deg, #10b981, #059669); }

.cap-card-head b {
  font-size: 15px;
  font-weight: 700;
  color: var(--ks-text-title);
}

.cap-card-desc {
  margin: 10px 0 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.cap-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cap-perm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 999px;
  padding: 3px 9px;
}

.cap-perm .el-icon {
  font-size: 12px;
  color: #10b981;
}

/* ---------------- 团队详情抽屉 ---------------- */
.detail-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 4px 2px;
  position: relative;
  overflow: hidden;
}

.detail-hero-deco {
  position: absolute;
  right: -40px;
  top: -80px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.28), transparent 70%);
  filter: blur(30px);
  pointer-events: none;
}

.detail-hero-icon {
  position: relative;
  width: 54px;
  height: 54px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
  flex-shrink: 0;
}

.detail-hero-main {
  position: relative;
  min-width: 0;
  flex: 1;
}

.detail-hero-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--ks-text-title);
  line-height: 1.3;
}

.detail-hero-sub {
  font-size: 12px;
  color: #64748b;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 380px;
}

.detail-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.detail-hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.detail-hero-actions {
  position: relative;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 概览统计条 */
.detail-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 4px;
}

.detail-stat {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.detail-stat .el-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
  flex-shrink: 0;
}

.detail-stat.blue .el-icon { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.detail-stat.purple .el-icon { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.detail-stat.amber .el-icon { background: linear-gradient(135deg, #f59e0b, #d97706); }
.detail-stat.green .el-icon { background: linear-gradient(135deg, #10b981, #059669); }

.detail-stat-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.detail-stat-meta b {
  font-size: 16px;
  font-weight: 800;
  color: var(--ks-text-title);
  line-height: 1.1;
}

.detail-stat-meta span {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  white-space: nowrap;
}

/* 详情页签 */
.detail-tabs {
  margin-top: 12px;
}

.detail-tabs :deep(.el-tabs__item) {
  font-weight: 600;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 2px 0 10px;
  flex-wrap: wrap;
}

.member-search {
  width: 240px;
}

/* 团队设置 */
.settings-panel {
  max-width: 520px;
}

.danger-title .el-icon {
  color: #ef4444;
}

.danger-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  flex-wrap: wrap;
}

.danger-row-main {
  min-width: 0;
  flex: 1;
}

.danger-row-main b {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #b91c1c;
}

.danger-row-main span {
  display: block;
  font-size: 12px;
  color: #991b1b;
  margin-top: 2px;
}

/* ---------------- 解散团队二次确认弹窗 ---------------- */
.dissolve-confirm {
  padding: 4px 2px 8px;
}

.dissolve-warn {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.7;
  color: #7f1d1d;
  margin-bottom: 18px;
}

.dissolve-warn b {
  color: #b91c1c;
}

.dissolve-warn-icon {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: rgba(220, 38, 38, 0.12);
  color: #dc2626;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.dissolve-input-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ks-text-body);
  margin-bottom: 8px;
}

.dissolve-mismatch {
  margin-top: 8px;
  font-size: 12px;
  color: #dc2626;
}

.danger-text {
  color: #b91c1c;
}

.danger-title {
  color: #b91c1c;
}

/* ---------------- 团队扩展：共享知识库 / 打卡 / 审批 ---------------- */
.shared-list,
.approval-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
}

.shared-item,
.approval-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.shared-item:hover,
.approval-item:hover {
  border-color: rgba(37, 99, 235, 0.3);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.07);
}

.shared-main,
.approval-main {
  flex: 1;
  min-width: 0;
}

.shared-name,
.approval-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ks-text-title);
  word-break: break-word;
}

.shared-sub,
.approval-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.shared-ops,
.approval-ops {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.shared-hint {
  font-size: 12px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 6px 10px;
}

.approval-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.approval-block {
  margin-bottom: 4px;
}

.approval-sub-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ks-text-title);
  margin: 10px 0 8px;
}

.attend-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.attend-today {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 12px;
}

.attend-today-card {
  background: linear-gradient(135deg, #0b1730, #1e3a8a);
  border-radius: 14px;
  padding: 16px;
  color: #f8fafc;
}

.attend-date {
  font-size: 14px;
  font-weight: 700;
}

.attend-my-status {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0 14px;
  font-size: 12px;
  color: rgba(191, 219, 254, 0.9);
}

.attend-time {
  color: #dbeafe;
}

.attend-actions {
  display: flex;
  gap: 8px;
}

.attend-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.attend-stat {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
}

.attend-stat b {
  font-size: 18px;
  font-weight: 800;
  color: var(--ks-text-title);
}

.attend-stat span {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.attend-list {
  display: flex;
  flex-direction: column;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.attend-record-item {
  display: flex;
  gap: 16px;
  padding: 9px 14px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  color: var(--ks-text-body);
}

.attend-record-item:last-child {
  border-bottom: none;
}

.attend-record-date {
  font-weight: 600;
  color: var(--ks-text-title);
  width: 100px;
  flex-shrink: 0;
}

.attend-record-time {
  color: #64748b;
}

.summary-body {
  padding: 2px;
}

.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #64748b;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
}

.summary-content {
  font-size: 13px;
  line-height: 1.8;
  color: var(--ks-text-body);
  white-space: pre-wrap;
  word-break: break-word;
}

.summary-content.empty {
  color: #94a3b8;
}
.detail-section {
  margin-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
  padding-top: 12px;
}
.detail-section .section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary, #303133);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
.detail-section .preview-pages {
  font-weight: 400;
  color: var(--el-text-color-secondary, #909399);
  font-size: 12px;
}
.detail-section .preview-body {
  margin-top: 8px;
  max-height: 420px;
  overflow-y: auto;
  background: #f7f8fa;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 6px;
  padding: 10px 12px;
}
.detail-section .preview-body pre {
  margin: 0;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}
.detail-section.preview-empty .preview-body {
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
}


/* ============ 企业级组织中心配色升级 ============ */
.org-hero {
  position: relative;
  border-radius: 18px;
  padding: 24px 26px 20px;
  margin-bottom: 20px;
  background:
    radial-gradient(1100px 320px at 85% -40px, rgba(124, 58, 237, 0.42), transparent 60%),
    radial-gradient(900px 300px at -5% 0%, rgba(37, 99, 235, 0.45), transparent 55%),
    linear-gradient(135deg, #0b1730 0%, #12295c 48%, #1e3a8a 100%);
  border: 1px solid rgba(147, 197, 253, 0.22);
  box-shadow: 0 14px 34px -14px rgba(30, 58, 138, 0.55);
  overflow: hidden;
}

.org-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 26px 26px;
  mask-image: radial-gradient(ellipse at 50% 20%, #000 20%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 20%, #000 20%, transparent 75%);
  pointer-events: none;
}

.org-hero-deco {
  position: absolute;
  top: -120px;
  right: -80px;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.5), transparent 70%);
  filter: blur(42px);
  pointer-events: none;
}

.org-hero-deco::before {
  content: '';
  position: absolute;
  bottom: -200px;
  left: -120px;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.32), transparent 70%);
  filter: blur(38px);
}

.team-title {
  position: relative;
  z-index: 1;
}

.org-stat {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.org-stat::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, #60a5fa, #3b82f6);
}

.org-stat:nth-child(2)::before {
  background: linear-gradient(180deg, #fbbf24, #f59e0b);
}

.org-stat:nth-child(3)::before {
  background: linear-gradient(180deg, #c084fc, #8b5cf6);
}

.org-stat:nth-child(4)::before {
  background: linear-gradient(180deg, #34d399, #10b981);
}

.org-stat:hover {
  transform: translateY(-2px);
  border-color: rgba(147, 197, 253, 0.4);
  box-shadow: 0 10px 22px -10px rgba(30, 58, 138, 0.55);
}

.org-stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 14px -6px rgba(0, 0, 0, 0.4);
}

.org-stat-icon.blue { background: linear-gradient(135deg, #60a5fa, #2563eb); }
.org-stat-icon.amber { background: linear-gradient(135deg, #fbbf24, #d97706); }
.org-stat-icon.purple { background: linear-gradient(135deg, #a78bfa, #7c3aed); }
.org-stat-icon.green { background: linear-gradient(135deg, #34d399, #059669); }

.org-stat-meta b {
  font-size: 22px;
  font-weight: 800;
  color: #f8fafc;
  line-height: 1.1;
}

/* ============ 打卡：四段班次 + 工作区域 ============ */
.attend-today {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.attend-today-card {
  position: relative;
  background:
    radial-gradient(500px 180px at 90% -20px, rgba(139, 92, 246, 0.35), transparent 60%),
    radial-gradient(400px 160px at 0% 110%, rgba(59, 130, 246, 0.4), transparent 55%),
    linear-gradient(135deg, #0b1730, #16306a 60%, #1e3a8a);
  border-radius: 16px;
  padding: 16px 18px;
  color: #f8fafc;
  border: 1px solid rgba(147, 197, 253, 0.22);
  box-shadow: 0 12px 28px -12px rgba(30, 58, 138, 0.6);
}

.attend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.attend-date {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.3px;
}

.attend-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.geo-link {
  color: rgba(191, 219, 254, 0.92) !important;
}

.geo-link:hover {
  color: #fff !important;
}

.geo-state {
  margin-left: 2px;
}

.geo-tip {
  margin-bottom: 12px;
}

.geo-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.attend-shift-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 14px;
}

/* 中等宽度收为两列：四列并排时卡片内容（时段 + 补卡按钮）会被挤压重叠 */
@media (max-width: 1200px) {
  .attend-shift-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .attend-shift-grid {
    grid-template-columns: 1fr;
  }
}

.attend-shift-item {
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  padding: 12px 10px;
  text-align: center;
  transition: all 0.18s ease;
}

.attend-shift-item.done {
  background: linear-gradient(160deg, rgba(16, 185, 129, 0.18), rgba(16, 185, 129, 0.06));
  border-color: rgba(52, 211, 153, 0.5);
}

.shift-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #dbeafe;
}

.shift-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.22);
}

.attend-shift-item.done .shift-dot {
  background: #34d399;
  box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.24);
}

.shift-time {
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  margin: 6px 0 8px;
  letter-spacing: 0.5px;
}

.shift-status {
  min-height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #a7f3d0;
}

.shift-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}

.shift-missed-tip {
  font-size: 11px;
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.32);
  border-radius: 999px;
  padding: 1px 8px;
}

.shift-fix-btn {
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.45);
  color: #fcd34d;
  height: 24px;
  padding: 0 10px;
  font-size: 12px;
}

.shift-fix-btn:hover {
  background: rgba(245, 158, 11, 0.24);
  border-color: #f59e0b;
  color: #fef3c7;
}

.shift-check {
  font-size: 15px;
  color: #34d399;
  margin-right: 4px;
}

.shift-btn {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.3);
  color: #f8fafc;
}

.shift-btn:hover {
  background: rgba(255, 255, 255, 0.22);
  border-color: #60a5fa;
  color: #fff;
}

.attend-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.attend-stat {
  position: relative;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

.attend-stat:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px -10px rgba(15, 23, 42, 0.25);
}

.attend-stat::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
}

.attend-stat:nth-child(2)::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.attend-stat:nth-child(3)::before { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.attend-stat:nth-child(4)::before { background: linear-gradient(90deg, #10b981, #34d399); }
.attend-stat:nth-child(5)::before { background: linear-gradient(90deg, #0ea5e9, #38bdf8); }
.attend-stat:nth-child(6)::before { background: linear-gradient(90deg, #f43f5e, #fb7185); }

.attend-stat b {
  font-size: 19px;
  font-weight: 800;
  color: var(--ks-text-title);
}

.attend-stat span {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.attend-summary {
  grid-column: 1 / -1;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
}

.summary-table {
  margin-top: 8px;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  overflow: hidden;
  font-size: 12px;
}

.summary-row {
  display: grid;
  grid-template-columns: 1.4fr repeat(5, 1fr);
  padding: 7px 12px;
  color: #475569;
}

.summary-row > span {
  text-align: center;
}

.summary-row > span:first-child {
  text-align: left;
}

.summary-head {
  background: linear-gradient(135deg, #0b1730, #1e3a8a);
  color: #e0e7ff;
  font-weight: 700;
}

.summary-row:not(.summary-head):nth-child(even) {
  background: #f8fafc;
}

/* ---------------- 自定义角色管理 ---------------- */
.roles-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.roles-head-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.roles-head-sub {
  margin-top: 3px;
  font-size: 12px;
  color: #64748b;
}

.roles-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.role-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.role-row:hover {
  border-color: #93c5fd;
  box-shadow: 0 6px 18px -10px rgba(37, 99, 235, 0.25);
}

.role-row-main {
  min-width: 0;
  flex: 1;
}

.role-row-name {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.role-name-text {
  font-weight: 700;
  color: #0f172a;
}

.role-count {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}

.role-row-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.perm-tag {
  border-radius: 999px;
}

.perm-empty {
  font-size: 12px;
  color: #94a3b8;
}

.role-row-remark {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.role-row-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.role-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.role-form-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.role-form-label {
  width: 68px;
  flex-shrink: 0;
  padding-top: 8px;
  font-size: 13px;
  color: #334155;
}

.role-form-input {
  flex: 1;
}

.role-form-perm-row {
  align-items: flex-start;
}

.perm-matrix {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px;
}

.perm-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.perm-item:hover {
  border-color: #93c5fd;
  box-shadow: 0 4px 12px -8px rgba(37, 99, 235, 0.3);
}
/* ============ 组织中心：统计卡 / 团队卡 / 角色区统一企业风增强 ============ */
.org-stat {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.org-stat:hover {
  transform: translateY(-3px);
  border-color: rgba(147, 197, 253, 0.38);
  box-shadow: 0 12px 28px -12px rgba(30, 58, 138, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.org-stat-icon {
  box-shadow: 0 6px 14px -4px rgba(30, 58, 138, 0.45);
}

.team-card {
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 255, 0.96)),
    #fff;
  border: 1px solid rgba(30, 58, 138, 0.12);
  box-shadow: var(--ks-shadow-md);
}

.team-card:hover {
  transform: translateY(-3px);
  border-color: rgba(37, 99, 235, 0.3);
  box-shadow: 0 16px 34px -16px rgba(30, 58, 138, 0.35), var(--ks-shadow-md);
}

.team-head .team-icon {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  box-shadow: 0 4px 10px -2px rgba(37, 99, 235, 0.4);
}

.capability-card {
  box-shadow: var(--ks-shadow-sm);
  border: 1px solid var(--ks-card-border);
}

.capability-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--ks-shadow-lg);
}

</style>
