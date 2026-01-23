export interface Server {
  id: string
  host: string
  user: string
  port: number
  key_path?: string
  password?: string
}

export interface DeployPlan {
  plan_id: string
  name: string
  server_ids: string[]
  script_content: string
  files: {name: string, content: string}[]
  status: 'created' | 'running' | 'completed' | 'failed'
  logs?: string[]
}
