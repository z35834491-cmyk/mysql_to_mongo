import type { DBInstancePayload } from '@/api/db_manager_pro'

export type DbTypeKey = DBInstancePayload['db_type']

export type PitrField =
  | { key: string; label: string; kind: 'text'; placeholder?: string }
  | { key: string; label: string; kind: 'number'; min?: number; max?: number }
  | { key: string; label: string; kind: 'switch' }

export type EditorSnippet = { label: string; insertText: string; detail?: string }

export interface DbTypePreset {
  defaultPort: number
  defaultDatabasePlaceholder: string
  monacoLanguage: string
  defaultSql: string
  sqlCompletion: Array<{ label: string; detail?: string }>
  editorSnippets: EditorSnippet[]
  pitrFields: PitrField[]
}

export const DB_TYPE_PRESETS: Record<DbTypeKey, DbTypePreset> = {
  mysql: {
    defaultPort: 3306,
    defaultDatabasePlaceholder: '如 information_schema 或业务库名',
    monacoLanguage: 'mysql',
    defaultSql: 'SELECT 1;\n',
    sqlCompletion: [
      { label: 'SELECT', detail: 'MySQL 查询' },
      { label: 'SHOW DATABASES', detail: '列出库' },
      { label: 'SHOW TABLES', detail: '列出表' },
      { label: 'EXPLAIN', detail: '执行计划' },
      { label: 'LIMIT', detail: '限制行数' }
    ],
    editorSnippets: [
      { label: 'SELECT 模板', insertText: 'SELECT ${1:*}\nFROM ${2:table_name}\nWHERE ${3:condition};', detail: 'MySQL 查询模板' },
      { label: 'INSERT 模板', insertText: 'INSERT INTO ${1:table_name} (${2:cols})\nVALUES (${3:values});', detail: '插入' },
      { label: 'UPDATE 模板', insertText: 'UPDATE ${1:table_name}\nSET ${2:column} = ${3:value}\nWHERE ${4:id} = ${5:1};', detail: '更新' }
    ],
    pitrFields: [
      { key: 'mysql_binlog_dir', label: 'MySQL Binlog 目录', kind: 'text', placeholder: '/data/mysql/binlog' }
    ]
  },
  postgresql: {
    defaultPort: 5432,
    defaultDatabasePlaceholder: '如 postgres 或业务库名',
    monacoLanguage: 'pgsql',
    defaultSql: 'SELECT 1;\n',
    sqlCompletion: [
      { label: 'SELECT', detail: 'PostgreSQL 查询' },
      { label: '\\dt', detail: 'psql: 列出表（文档提示）' },
      { label: 'EXPLAIN ANALYZE', detail: '分析执行' },
      { label: 'LIMIT', detail: '限制行数' },
      { label: 'RETURNING', detail: 'DML 返回子句' }
    ],
    editorSnippets: [
      { label: 'SELECT 模板', insertText: 'SELECT ${1:*}\nFROM ${2:table_name}\nWHERE ${3:condition};', detail: 'PostgreSQL 查询' },
      { label: 'INSERT RETURNING', insertText: 'INSERT INTO ${1:table} (${2:cols})\nVALUES (${3:vals})\nRETURNING ${4:*};', detail: '插入并返回' }
    ],
    pitrFields: [
      { key: 'pg_wal_archive_dir', label: 'PostgreSQL WAL 目录', kind: 'text', placeholder: '/data/postgres/wal_archive' },
      { key: 'pg_restore_data_dir', label: 'PostgreSQL 恢复目录', kind: 'text', placeholder: '/data/postgres/pitr_restore' },
      { key: 'pg_ctl_path', label: 'pg_ctl 路径', kind: 'text', placeholder: '/usr/local/bin/pg_ctl' },
      { key: 'pg_pitr_port', label: 'PITR 恢复端口', kind: 'number', min: 1024, max: 65535 },
      { key: 'pg_auto_start_recovery', label: '自动启动恢复', kind: 'switch' }
    ]
  },
  redis: {
    defaultPort: 6379,
    defaultDatabasePlaceholder: 'Redis 逻辑库号（如 0）',
    monacoLanguage: 'redis',
    defaultSql: 'PING\n',
    sqlCompletion: [
      { label: 'GET', detail: '读取键' },
      { label: 'SET', detail: '设置键' },
      { label: 'HGET', detail: '哈希读' },
      { label: 'HSET', detail: '哈希写' },
      { label: 'DEL', detail: '删除键' }
    ],
    editorSnippets: [
      { label: 'GET/SET', insertText: 'GET ${1:key}\nSET ${1:key} ${2:value}', detail: '读写示例' }
    ],
    pitrFields: []
  },
  mongo: {
    defaultPort: 27017,
    defaultDatabasePlaceholder: '如 admin 或业务库名',
    monacoLanguage: 'javascript',
    defaultSql: 'db.collection.find({})\n',
    sqlCompletion: [
      { label: 'find', detail: '查询文档' },
      { label: 'aggregate', detail: '聚合管道' },
      { label: 'insertOne', detail: '插入单条' },
      { label: 'updateOne', detail: '更新单条' },
      { label: 'deleteOne', detail: '删除单条' }
    ],
    editorSnippets: [
      { label: 'find 模板', insertText: 'db.getCollection("${1:coll}").find({ ${2:filter} })', detail: '查询' },
      { label: 'aggregate 模板', insertText: 'db.getCollection("${1:coll}").aggregate([\n  { $match: { ${2:field}: ${3:value} } }\n])', detail: '聚合' }
    ],
    pitrFields: []
  },
  rabbitmq: {
    defaultPort: 5672,
    defaultDatabasePlaceholder: 'vhost（如 /）',
    monacoLanguage: 'plaintext',
    defaultSql: '# RabbitMQ 管理端常用：队列/交换机请在控制台或 API 中配置\n',
    sqlCompletion: [
      { label: 'queue', detail: '队列相关（文档提示）' },
      { label: 'exchange', detail: '交换机（文档提示）' },
      { label: 'vhost', detail: '虚拟主机' }
    ],
    editorSnippets: [],
    pitrFields: []
  }
}

export function getDbTypePreset(dbType: string | undefined): DbTypePreset {
  const key = (dbType || 'mysql') as DbTypeKey
  return DB_TYPE_PRESETS[key] ?? DB_TYPE_PRESETS.mysql
}
