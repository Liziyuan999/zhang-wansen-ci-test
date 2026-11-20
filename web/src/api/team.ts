/**
 * 组织中心接口：创建 / 我的团队 / 详情 / 编辑 / 邀请 / 接受 / 撤销 / 移除 / 移交
 */
import { request } from './request'
import { getAccessToken } from '@/utils/auth-token'
import type {
  TeamItem,
  TeamDetail,
  TeamInvitation,
  InviteInfo,
  TeamLog,
  SharedDoc,
  DownloadApproval,
  TeamExitApproval,
  MyApprovals,
  PendingCount,
  AttendanceToday,
  AttendanceGeo,
  AttendanceSummary,
  MyAttendance,
  AttendanceFixApproval,
  FixApprovalList,
  PermPoint,
  TeamRole,
} from '@/types'

/** 创建团队（创建者自动成为 owner） */
export function createTeam(payload: { name: string; description?: string }) {
  return request<TeamItem>({
    url: '/team/create',
    method: 'post',
    data: { name: payload.name, description: payload.description || '' },
  })
}

/** 我的团队列表（含成员数、我的角色） */
export function listMyTeams() {
  return request<TeamItem[]>({
    url: '/team/my',
    method: 'get',
  })
}

/** 团队详情（成员 + 邀请记录） */
export function getTeam(teamId: number) {
  return request<TeamDetail>({
    url: `/team/${teamId}`,
    method: 'get',
  })
}

/** 编辑团队名称/描述（owner/admin） */
export function updateTeam(teamId: number, payload: { name: string; description?: string }) {
  return request<TeamItem>({
    url: `/team/${teamId}`,
    method: 'put',
    data: { name: payload.name, description: payload.description || '' },
  })
}

/** 邀请成员（QQ 邮箱，发送邀请邮件） */
export function inviteMember(teamId: number, qqEmail: string) {
  return request<TeamInvitation>({
    url: `/team/${teamId}/invite`,
    method: 'post',
    data: { qq_email: qqEmail },
  })
}

/** 邀请信息查询（接受页展示，无需登录） */
export function getInviteInfo(token: string) {
  return request<InviteInfo>({
    url: '/team/invite/info',
    method: 'get',
    params: { token },
  })
}

/** 接受邀请（当前登录用户邮箱须与邀请邮箱一致） */
export function acceptInvite(token: string) {
  return request<{ team_id: number; team_name: string }>({
    url: `/team/invite/${token}/accept`,
    method: 'post',
  })
}

/** 撤销邀请（仅 pending 可撤销） */
export function revokeInvite(invitationId: number) {
  return request<null>({
    url: `/team/invite/${invitationId}/revoke`,
    method: 'post',
  })
}

/** 移除成员（owner 不可被移除；owner 移除任意、admin 仅移除 member） */
export function removeMember(teamId: number, userId: number) {
  return request<null>({
    url: `/team/${teamId}/member/${userId}`,
    method: 'delete',
  })
}

/** 移交团队所有权 */
export function transferOwner(teamId: number, targetUserId: number) {
  return request<null>({
    url: `/team/${teamId}/transfer`,
    method: 'post',
    data: { target_user_id: targetUserId },
  })
}

/** 调整成员角色（owner 可调 member/admin/owner/自定义角色；admin 仅可调 member；owner 角色不可被修改） */
export function setMemberRole(teamId: number, userId: number, role: 'owner' | 'admin' | 'member' | string) {
  return request<null>({
    url: `/team/${teamId}/member/${userId}/role`,
    method: 'put',
    data: { role },
  })
}

/* ---------------- 自定义角色管理 ---------------- */
export function listRoles(teamId: number) {
  return request<{ catalog: PermPoint[]; roles: TeamRole[] }>({
    url: `/team/${teamId}/roles`,
    method: 'get',
  })
}

export function createRole(teamId: number, payload: { role_name: string; perms: string[]; remark?: string }) {
  return request<TeamRole>({
    url: `/team/${teamId}/roles`,
    method: 'post',
    data: payload,
  })
}

export function updateRole(teamId: number, roleId: number, payload: { role_name?: string; perms?: string[]; remark?: string }) {
  return request<TeamRole>({
    url: `/team/${teamId}/roles/${roleId}`,
    method: 'put',
    data: payload,
  })
}

export function deleteRole(teamId: number, roleId: number) {
  return request<{ role_id: number; downgraded: number }>({
    url: `/team/${teamId}/roles/${roleId}`,
    method: 'delete',
  })
}

/** 通过邀请链接/token 加入团队（校验 token 有效、未过期、邮箱匹配） */
export function joinTeam(payload: { token: string }) {
  return request<TeamItem>({
    url: '/team/join',
    method: 'post',
    data: { token: payload.token },
  })
}

/** 成员退出团队（owner 需先移交或解散） */
export function leaveTeam(teamId: number) {
  return request<null>({
    url: `/team/${teamId}/leave`,
    method: 'post',
  })
}

/** 解散团队（仅 owner，会清除成员/邀请/通知/日志） */
export function dissolveTeam(teamId: number) {
  return request<null>({
    url: `/team/${teamId}`,
    method: 'delete',
  })
}

/** 团队动态/操作日志（仅团队成员） */
export function getTeamLogs(teamId: number) {
  return request<TeamLog[]>({
    url: `/team/${teamId}/logs`,
    method: 'get',
  })
}

/* ================= 团队共享知识库 ================= */

/** 共享知识库列表：团队所有者的文档对全体成员可见可查阅 */
export function listSharedDocs(teamId: number) {
  return request<{ total: number; items: SharedDoc[] }>({
    url: `/team/${teamId}/shared-docs`,
    method: 'get',
  })
}

/** 共享文档详情（不暴露物理路径） */
export function getSharedDoc(teamId: number, docId: number) {
  return request<SharedDoc>({
    url: `/team/${teamId}/shared-docs/${docId}`,
    method: 'get',
  })
}

/** 成员申请下载共享文档；owner/admin 直接放行（返回 status=direct） */
export function requestDownload(teamId: number, docId: number, reason = '') {
  return request<{ status: 'pending' | 'direct'; approval_id: number | null }>({
    url: `/team/${teamId}/shared-docs/${docId}/download-request`,
    method: 'post',
    params: { reason },
  })
}

/** 下载共享文档（带鉴权；成员需审批通过后凭 approval_id 下载） */
export async function downloadSharedDoc(teamId: number, docId: number, approvalId?: number) {
  // 修复 P1-2 同类问题：原实现读 'access_token'，实际键为 'knowseek_access_token'，
  // 导致 Authorization 头为空、下载恒 401。统一走 getAccessToken()。
  const token = getAccessToken()
  const url = `/api/team/${teamId}/shared-docs/${docId}/download${approvalId ? `?approval_id=${approvalId}` : ''}`
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!resp.ok) {
    let msg = `下载失败（HTTP ${resp.status}）`
    try {
      const j = await resp.json()
      msg = j?.message || msg
    } catch {
      // 保持默认提示
    }
    throw new Error(msg)
  }
  const blob = await resp.blob()
  const disposition = resp.headers.get('content-disposition') || ''
  const nameMatch = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i)
  const fallbackName = `shared_doc_${docId}.${nameMatch ? '' : 'file'}`
  const filename = nameMatch ? decodeURIComponent(nameMatch[1].replace(/^"|"$/g, '')) : fallbackName
  const urlObj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = urlObj
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(urlObj)
}

/* ================= 下载审批 ================= */

/** 下载审批列表（仅 owner/admin，可按状态筛选 + 分页） */
export function listDownloadApprovals(
  teamId: number,
  params: { status?: string; page?: number; page_size?: number } = {},
) {
  return request<{ total: number; items: DownloadApproval[] }>({
    url: `/team/${teamId}/approvals/downloads`,
    method: 'get',
    params: {
      status: params.status || '',
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
}

/** 审批通过下载申请 */
export function approveDownload(teamId: number, approvalId: number) {
  return request<DownloadApproval>({
    url: `/team/${teamId}/approvals/downloads/${approvalId}/approve`,
    method: 'post',
  })
}

/** 拒绝下载申请 */
export function rejectDownload(teamId: number, approvalId: number, rejectReason = '') {
  return request<DownloadApproval>({
    url: `/team/${teamId}/approvals/downloads/${approvalId}/reject`,
    method: 'post',
    params: { reject_reason: rejectReason },
  })
}

/* ================= 退出团队审批 ================= */

/** 成员提交退出团队申请（owner 不可退出） */
export function requestExit(teamId: number, reason = '') {
  return request<TeamExitApproval>({
    url: `/team/${teamId}/approvals/exits`,
    method: 'post',
    params: { reason },
  })
}

/** 退出审批列表（仅 owner/admin） */
export function listExitApprovals(
  teamId: number,
  params: { status?: string; page?: number; page_size?: number } = {},
) {
  return request<{ total: number; items: TeamExitApproval[] }>({
    url: `/team/${teamId}/approvals/exits`,
    method: 'get',
    params: {
      status: params.status || '',
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
}

/** 审批通过退出申请（自动移除成员） */
export function approveExit(teamId: number, approvalId: number) {
  return request<TeamExitApproval>({
    url: `/team/${teamId}/approvals/exits/${approvalId}/approve`,
    method: 'post',
  })
}

/** 拒绝退出申请 */
export function rejectExit(teamId: number, approvalId: number, rejectReason = '') {
  return request<TeamExitApproval>({
    url: `/team/${teamId}/approvals/exits/${approvalId}/reject`,
    method: 'post',
    params: { reject_reason: rejectReason },
  })
}

/* ================= 我的申请 / 待审批计数 ================= */

/** 我的申请记录：下载申请 + 退出申请 */
export function myApprovals(teamId: number) {
  return request<MyApprovals>({
    url: `/team/${teamId}/approvals/my`,
    method: 'get',
  })
}

/** 待审批计数（owner/admin 视角；成员返回自己的待审批申请数） */
export function pendingApprovalCount(teamId: number) {
  return request<PendingCount>({
    url: `/team/${teamId}/approvals/pending-count`,
    method: 'get',
  })
}

/* ================= 企业打卡（四段班次 + 工作区域） ================= */

/** 班次打卡：am_in / am_out / pm_in / pm_out（服务端校验班次时段与工作区域） */
export function clock(teamId: number, slot: 'am_in' | 'am_out' | 'pm_in' | 'pm_out', lat: number, lng: number) {
  return request<{ date: string; slot: string; time: string; distance_m: number }>({
    url: `/team/${teamId}/attendance/clock`,
    method: 'post',
    params: { slot, lat, lng },
  })
}

/** 查看团队工作区域配置 */
export function attendanceGeo(teamId: number) {
  return request<AttendanceGeo>({
    url: `/team/${teamId}/attendance/geo`,
    method: 'get',
  })
}

/** 配置团队工作区域（仅 owner/admin） */
export function updateAttendanceGeo(
  teamId: number,
  data: { lat: number; lng: number; radius_m: number; enabled: boolean },
) {
  return request<AttendanceGeo>({
    url: `/team/${teamId}/attendance/geo`,
    method: 'put',
    params: data,
  })
}

/** 近 N 天团队出勤汇总 */
export function attendanceSummary(teamId: number, days = 7) {
  return request<AttendanceSummary>({
    url: `/team/${teamId}/attendance/summary`,
    method: 'get',
    params: { days },
  })
}

/** 今日打卡状态 + 团队打卡统计 */
export function attendanceToday(teamId: number) {
  return request<AttendanceToday>({
    url: `/team/${teamId}/attendance/today`,
    method: 'get',
  })
}

/** 我的打卡记录（按日期倒序） */
export function myAttendance(teamId: number, limit = 30) {
  return request<MyAttendance>({
    url: `/team/${teamId}/attendance/my`,
    method: 'get',
    params: { limit },
  })
}

/* ================= 考勤补卡申请（复用审批中心） ================= */

/** 提交补卡申请 */
export function requestFix(teamId: number, data: { date: string; slot: string; reason?: string }) {
  return request<AttendanceFixApproval>({
    url: `/team/${teamId}/attendance/fix/request`,
    method: 'post',
    params: { date: data.date, slot: data.slot, reason: data.reason || '' },
  })
}

/** 补卡申请列表（管理员看全部；成员仅看自己） */
export function listFixes(teamId: number, status = '') {
  return request<FixApprovalList>({
    url: `/team/${teamId}/attendance/fix/list`,
    method: 'get',
    params: { status },
  })
}

/** 审批通过补卡申请（修正打卡记录） */
export function approveFix(teamId: number, fixId: number) {
  return request<AttendanceFixApproval>({
    url: `/team/${teamId}/attendance/fix/${fixId}/approve`,
    method: 'post',
  })
}

/** 驳回补卡申请 */
export function rejectFix(teamId: number, fixId: number, rejectReason = '') {
  return request<AttendanceFixApproval>({
    url: `/team/${teamId}/attendance/fix/${fixId}/reject`,
    method: 'post',
    params: { reject_reason: rejectReason },
  })
}
