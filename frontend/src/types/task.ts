export interface Task {
  task_id: string
  status: 'running' | 'stopped' | 'error' | 'created' | 'initializing'
  config?: any
  metrics?: {
    phase: string
    processed_count: number
    binlog_file?: string
    binlog_pos?: number
    last_update: number
    error?: string
    current_table?: string
    full_insert_count?: number
    inc_insert_count?: number
    update_count?: number
    delete_count?: number
  }
  type?: 'sync' | 'monitor'
}

export interface TaskLog {
  lines: string[]
  total: number
  page: number
  page_size: number
}

export interface TaskStats {
  // Define stats structure if needed
}
