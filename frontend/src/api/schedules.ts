import request from '../utils/request'

export interface StaffInfo {
  id: number
  name: string
}

export interface BizShiftRespVO {
  id: number
  ruleId: number
  shiftDate: string
  startTime: string
  endTime: string
  staffIds: string
  staffList: StaffInfo[]
  createTime: string
}

export interface ScheduleResponse {
  code: number
  data: BizShiftRespVO[]
  msg: string
}

export function getSchedules() {
  return request.get<ScheduleResponse>('/schedules/')
}

export interface PhoneAlertConfig {
  public_url: string
  slack_webhook_url: string
  external_api_url: string
  external_api_username: string
  external_api_password?: string
  incoming_token: string
  auto_complete_minutes: number
  has_external_api_password?: boolean
}

export function getPhoneAlertConfig() {
  return request.get<PhoneAlertConfig>('/schedules/phone-alert/config')
}

export function savePhoneAlertConfig(config: PhoneAlertConfig) {
  return request.post<{ msg: string }>('/schedules/phone-alert/config', config)
}
