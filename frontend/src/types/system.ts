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
  score: number
  summary: string
  ai_analysis?: string
  metrics_summary?: any[]
  health_summary?: { score: number; level?: string; reasons?: string[] }
  fleet_summary?: {
    server_count: number
    avg_cpu_pct?: number
    avg_mem_pct?: number
    avg_disk_pct?: number
    top_cpu?: any[]
    top_mem?: any[]
    top_disk?: any[]
  }
  alerts_summary?: {
    firing_total: number
    critical_total: number
    warning_total: number
    top_alerts?: { name: string; count: number }[]
  }
  servers?: any[]
  trend_7d?: { date: string; score?: number; firing?: number; critical?: number; avg_cpu?: number; avg_mem?: number; avg_disk?: number }[]
  forecast_7_15_30?: any
}
