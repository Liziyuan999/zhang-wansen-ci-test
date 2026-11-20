/**
 * 知寻 KnowSeek 前端类型定义
 * 与后端 Pydantic schema 严格对齐（见 server/app/schemas）
 */

/** 后端统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页结果（后端返回 total + items，未回传 page/size） */
export interface PageResult<T> {
  total: number
  items: T[]
}

/** 部门 */
export interface DeptInfo {
  id: number
  dept_name: string
}

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  email: string
  role: 'staff' | 'admin' | string
  status: string
  dept_id: number
  dept_name?: string | null
  avatar?: string | null
  totp_enabled?: boolean
  has_password?: boolean
  last_login_time?: string | null
}

/** 个人中心完整资料 */
export interface UserProfile {
  id: number
  username: string
  email: string
  role: 'staff' | 'admin' | string
  status: string
  dept_id: number
  dept_name?: string | null
  avatar?: string | null
  totp_enabled?: boolean
  has_password?: boolean
  last_login_time?: string | null
  create_time?: string | null
  update_time?: string | null
}

/** 认证令牌与用户信息 */
export interface TokenData {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
}

/** 文档列表项 */
export interface DocListItem {
  id: number
  doc_name: string
  origin_file_name: string
  file_type: string
  file_size: number
  version_no: number
  status: 'pending' | 'processing' | 'success' | 'failed' | string
  progress: number
  summary?: string | null
  create_time: string
  update_time: string
  tags: string[]
  versions: number[]
}

/** 文档详情（含解析产物） */
export interface DocDetail extends DocListItem {
  file_path?: string | null
  fail_msg?: string | null
  ocr_content?: string | null
  extract_result?: Record<string, unknown> | null
  content_preview?: string | null
  content_pages?: number | null
}

/** 会话（对话列表项） */
export interface ConvItem {
  id: number
  title: string
  create_time: string
  update_time: string
}

/** 会话消息 */
export interface MsgItem {
  id: number
  role: 'user' | 'assistant' | string
  content: string
  ref_chunk_ids?: number[] | null
  create_time: string
}

/** 会话详情 */
export interface ConvDetail {
  conv: ConvItem
  messages: MsgItem[]
}

/** 溯源引用 */
export interface Citation {
  chunk_id: string
  doc_id: number
  doc_name: string
  content: string
  page_no?: number | null
  sheet_name?: string | null
  score?: number
  /** 命中文档的关联知识图谱实体（GraphRAG 联动） */
  related_entities?: KgEntity[]
}

/** 联网检索来源 */
export interface WebSource {
  title: string
  url: string
  snippet: string
}

/** SSE 事件类型 */
export type SSEEventType = 'citations' | 'web_sources' | 'delta' | 'done' | 'error' | 'fallback'

export interface SSEEvent<T = unknown> {
  type: SSEEventType
  data?: T
  content?: string
  conv_id?: number
  msg_id?: number
  message?: string
}

/** 知识图谱：实体（后端 /api/kg/search 返回结构） */
export interface KgEntity {
  id: number
  name: string
  type: string
  description?: string | null
  doc_id?: number | null
  relation_count?: number
  source?: string
}

/** 知识图谱：图谱节点 */
export interface KgGraphNode {
  id: number
  name: string
  type: string
  degree: number
  doc_id?: number | null
  description?: string | null
  source?: string
}

/** 知识图谱：图谱连线 */
export interface KgGraphLink {
  source: number
  target: number
  relation_type: string
  doc_id?: number | null
}

/** 知识图谱：图谱数据 */
export interface KgGraphData {
  nodes: KgGraphNode[]
  links: KgGraphLink[]
}

/** 知识图谱：统计 */
export interface KgStats {
  entity_count: number
  relation_count: number
  doc_count: number
  type_distribution: Array<{ type: string; count: number }>
}

/** 知识图谱：抽取结果 */
export interface KgExtractResult {
  doc_id: number
  status: string
  entity_count: number
  relation_count: number
  cost_ms?: number
  error?: string | null
}

/** Agent 模板 */
export interface AgentTemplateItem {
  id: number
  template_name: string
  task_type: string
  selected_doc_ids?: number[] | null
  params?: Record<string, unknown> | null
  canvas_json?: string | null
  schedule_type?: string
  schedule_cron?: string | null
  notify_on_finish?: boolean
  create_time?: string
  update_time?: string
}

/** Agent 画布节点 */
export interface CanvasNode {
  id: string
  type: 'input' | 'plan' | 'retrieve' | 'generate' | 'reflect' | 'refine' | 'output'
  name: string
  x: number
  y: number
  config: Record<string, unknown>
}

/** Agent 画布连线 */
export interface CanvasEdge {
  id: string
  source: string
  target: string
  label?: string
}

/** Agent 画布 JSON */
export interface CanvasJson {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
}

/** Agent 任务 */
export interface AgentTaskResp {
  task_id: number
  task_type?: string
  status: 'retrieving' | 'waiting_confirm' | 'finished' | 'failed' | 'cancelled' | string
  need_confirm: boolean
  selected_doc_ids?: number[] | null
  params?: Record<string, unknown> | null
  create_time?: string | null
  finish_time?: string | null
  error_msg?: string | null
  retrieval_chunks: Array<{
    chunk_id: string
    doc_id: number
    text?: string
    page_no?: number | null
    sheet_name?: string | null
    score?: number
  }>
  web_sources?: WebSource[] | null
  workflow_trace?: Array<{ node: string; name: string; status: string; summary: string; cost_ms?: number }> | null
  task_result?: string | null
}

/** 管理后台：用户 */
export interface AdminUser {
  id: number
  username: string
  email: string
  role: string
  status: string
  dept_id: number
  dept_name?: string | null
  last_login_time?: string | null
  create_time: string
}

/** 管理后台：部门（树形） */
export interface AdminDept {
  id: number
  dept_name: string
  parent_id: number | null
  leader_id: number | null
  leader_name?: string | null
  description?: string | null
  sort_order: number
  member_count: number
  create_time: string
  children?: AdminDept[]
}

/** 管理后台：文档总览 */
export interface AdminDoc {
  id: number
  doc_name: string
  origin_file_name: string
  file_type: string
  file_size: number
  version_no: number
  status: string
  progress: number
  dept_id?: number | null
  dept_name?: string | null
  uploader?: string | null
  create_time: string
  update_time: string
}

/** 管理后台：会话总览 */
export interface AdminConversation {
  id: number
  title: string
  user_id: number
  username?: string | null
  msg_count: number
  is_context_reset: boolean
  create_time: string
  update_time: string
}

/** 管理后台：用户反馈 */
export interface AdminFeedback {
  id: number
  msg_id: number
  user_id: number
  username?: string | null
  score: string
  content?: string | null
  status: string
  create_time: string
  msg_conv_id?: number | null
  msg_preview?: string | null
}

/** 管理后台：操作日志 */
export interface OperationLogItem {
  id: number
  user_id?: number | null
  username?: string | null
  dept_id?: number | null
  action: string
  module: string
  method?: string | null
  path?: string | null
  detail?: string | null
  ip?: string | null
  status: string
  duration_ms: number
  create_time: string
}

/** 管理后台：LLM 调用记录 */
export interface LlmLogItem {
  id: number
  user_id?: number | null
  scenario: string
  model_name: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  latency_ms: number
  is_success: boolean
  error_msg?: string | null
  create_time: string
}

/** 管理后台：系统配置 */
export interface SysConfigItem {
  config_key: string
  config_value: string
  description?: string | null
}

/** 反馈记录（管理后台展示；后端暂未提供管理接口，字段按 Feedback 模型对齐） */
export interface FeedbackRecord {
  id: number
  msg_id: number
  user_id: number
  score: 'good' | 'bad' | string
  content?: string | null
  status: 'pending' | 'handled' | string
  create_time: string
}

/* ================= 组织中心 ================= */

/** 团队成员 */
export interface TeamMember {
  user_id: number
  username: string
  email: string
  role: 'owner' | 'admin' | 'member' | string
  joined_at?: string | null
}

/** 权限点（权限矩阵勾选项） */
export interface PermPoint {
  key: string
  label: string
}

/** 角色（内置三档 + 自定义角色） */
export interface TeamRole {
  id: number | null
  team_id: number
  role_key: string
  role_name: string
  perms: string[]
  built_in: boolean
  remark?: string | null
  member_count: number
  create_time?: string | null
}

/** 团队邀请记录 */
export interface TeamInvitation {
  id: number
  email: string
  status: 'pending' | 'accepted' | 'declined' | 'expired' | string
  /** 邀请 token（可复制链接的关键凭据） */
  token: string
  /** 完整可复制邀请链接 */
  accept_url: string
  inviter_name?: string | null
  expires_at?: string | null
  create_time?: string | null
}

/** 我的团队列表项 */
export interface TeamItem {
  id: number
  name: string
  description?: string | null
  owner_id: number
  owner_name?: string | null
  member_count: number
  my_role: 'owner' | 'admin' | 'member' | string
  create_time?: string | null
}

/** 团队详情（成员 + 邀请记录） */
export interface TeamDetail extends TeamItem {
  members: TeamMember[]
  invitations: TeamInvitation[]
}

/** 团队操作日志（动态留痕） */
export interface TeamLog {
  id: number
  user_id: number
  username: string
  action: string
  message: string
  create_time?: string | null
}

/** 团队通知（通知中心） */
export interface NoticeItem {
  id: number
  team_id: number
  team_name: string
  sender_id: number
  sender_name: string
  title: string
  content: string
  create_time: string
  /** sent=我发送的 / received=我接收的 */
  direction: 'sent' | 'received' | string
  /** 接收者：是否已读；发送者：null */
  read: boolean | null
}

/** 邀请信息（接受页展示） */
export interface InviteInfo {
  team_id: number
  team_name: string
  inviter_id: number
  inviter_name: string
  inviter_email: string
  email: string
  status: string
  expires_at?: string | null
}

/* ================= 模型供应商 ================= */

/** 模型供应商（管理后台） */
export interface ModelProviderItem {
  id: number
  name: string
  base_url: string
  model: string
  api_key_masked: string
  api_key_configured: boolean
  is_default: boolean
  enabled: boolean
  create_time?: string | null
  update_time?: string | null
}

/** 模型供应商（可选列表项，对话/Agent/周报下拉） */
export interface ModelProviderOption {
  id: number
  name: string
  base_url: string
  model: string
  /** 是否为默认供应商（llm-status 返回） */
  is_default?: boolean
}

/* ================= 个人通知中心（分类/分页/实时） ================= */

/** 个人通知项（UserNotification） */
export interface UserNotificationItem {
  id: number
  title: string
  content: string
  ntype: string
  /** team=团队动态 / approval=审批消息 / system=系统消息 */
  category: 'team' | 'approval' | 'system' | string
  related_id?: number | null
  read: boolean
  create_time: string
}

/** 通知列表结果（含分类计数） */
export interface NoticeListResult {
  total: number
  items: UserNotificationItem[]
  category_counts: Record<string, number>
}

/** 未读数（总数 + 分类） */
export interface UnreadCount {
  count: number
  team: number
  approval: number
  system: number
}

/** 通知实时推送事件（SSE /api/notice/events） */
export interface NoticeSSEEvent {
  type: 'notice'
  unread: number
  latest_id: number | null
  latest_title: string | null
  latest_category: string | null
  ts: number
}

/* ================= 团队共享知识库 / 审批 / 打卡 ================= */

/** 共享文档（团队所有者的文档系列） */
export interface SharedDoc {
  id: number
  doc_name: string
  origin_file_name: string
  file_type: string
  file_size: number
  version_no: number
  status: string
  summary?: string | null
  update_time?: string | null
  owner_name?: string | null
  ocr_content?: string
  content_preview?: string
  content_pages?: number
}

/** 下载审批记录 */
export interface DownloadApproval {
  id: number
  team_id: number
  doc_id: number
  doc_name: string
  origin_file_name: string
  file_type: string
  applicant_id: number
  applicant_name: string
  approver_name?: string | null
  reason: string
  /** pending=待审批 / approved=已通过 / rejected=已拒绝 */
  status: 'pending' | 'approved' | 'rejected' | string
  reject_reason?: string | null
  apply_time?: string | null
  handle_time?: string | null
}

/** 退出团队审批记录 */
export interface TeamExitApproval {
  id: number
  team_id: number
  applicant_id: number
  applicant_name: string
  applicant_email: string
  approver_name?: string | null
  reason: string
  status: 'pending' | 'approved' | 'rejected' | string
  reject_reason?: string | null
  apply_time?: string | null
  handle_time?: string | null
}

/** 考勤补卡申请记录 */
export interface AttendanceFixApproval {
  id: number
  team_id: number
  user_id: number
  applicant_name: string
  applicant_email: string
  approver_name?: string | null
  date: string
  slot: string
  slot_label: string
  reason: string
  status: 'pending' | 'approved' | 'rejected' | string
  reject_reason?: string | null
  apply_time?: string | null
  handle_time?: string | null
}

/** 补卡申请列表 */
export interface FixApprovalList {
  items: AttendanceFixApproval[]
}

/** 我的申请记录（下载 + 退出 + 补卡） */
export interface MyApprovals {
  downloads: DownloadApproval[]
  exits: TeamExitApproval[]
  fixes: AttendanceFixApproval[]
}

/** 待审批计数 */
export interface PendingCount {
  downloads: number
  exits: number
  fixes: number
  total: number
}

/** 打卡记录（我的打卡记录项，四段班次） */
export interface AttendanceRecord {
  id: number
  date: string
  clock_in_time?: string | null
  clock_out_time?: string | null
  am_in_time?: string | null
  am_out_time?: string | null
  pm_in_time?: string | null
  pm_out_time?: string | null
  /** 缺卡班次列表，如 ['am_in', 'pm_out'] */
  missing_slots?: string[]
}

/** 单段班次状态 */
export interface AttendanceSlotStatus {
  done: boolean
  time: string | null
  /** 是否已判定缺卡（未打卡且已过该班次打卡窗口） */
  missing?: boolean
}

/** 今日打卡状态 */
export interface AttendanceToday {
  date: string
  my: {
    am_in_time?: string | null
    am_out_time?: string | null
    pm_in_time?: string | null
    pm_out_time?: string | null
    clock_in_time?: string | null
    clock_out_time?: string | null
    slots: Record<'am_in' | 'am_out' | 'pm_in' | 'pm_out', AttendanceSlotStatus>
    /** none=未打卡 / am_in..pm_out=最新完成的班次 */
    status: 'none' | 'am_in' | 'am_out' | 'pm_in' | 'pm_out'
  }
  stats: {
    member_count: number
    am_in_count: number
    am_out_count: number
    pm_in_count: number
    pm_out_count: number
    checked_in: number
    checked_out: number
    attendance_rate: number
    latest_clock?: string | null
  }
}

/** 团队工作区域配置 */
export interface AttendanceGeo {
  configured: boolean
  lat?: number
  lng?: number
  radius_m?: number
  enabled?: boolean
  update_time?: string | null
}

/** 近 N 天出勤汇总 */
export interface AttendanceSummary {
  member_count: number
  days: {
    date: string
    am_in: number
    am_out: number
    pm_in: number
    pm_out: number
    attendance_rate: number
  }[]
}

/** 我的打卡记录列表 */
export interface MyAttendance {
  items: AttendanceRecord[]
}
