import request from '../utils/request'

export interface Schedule {
  id: number
  staff_name: string
  shift_date: string
  shift_type: string
  extra_info: Record<string, any>
  created_at: string
  updated_at: string
}

export function getSchedules() {
  return request.get<Schedule[]>('/schedules/')
}
