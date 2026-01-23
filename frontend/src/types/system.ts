export interface MonitorConfig {
  enabled: boolean
  k8s_namespace: string
  k8s_container_name: string
  k8s_label_selector: string
  k8s_tail_lines: number
  include_keywords: string[]
  exclude_keywords: string[]
  s3_bucket: string
  s3_endpoint: string
  s3_access_key: string
  s3_secret_key: string
  s3_region: string
  s3_archive_enabled: boolean
  slack_webhook_url: string
}

export interface MonitorTask {
  task_id: string
  status: string
  metrics: any
}

export interface InspectionReport {
  report_id: string
  created_at: number
  status: string
  score: number
  summary: string
  ai_analysis?: string
  metrics?: any
}
