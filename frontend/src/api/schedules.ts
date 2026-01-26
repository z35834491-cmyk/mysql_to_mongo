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
