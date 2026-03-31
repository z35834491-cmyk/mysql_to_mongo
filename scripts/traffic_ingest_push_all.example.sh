#!/usr/bin/env bash
# 示例：同一台 Nginx 上把四个 access json 日志分别推到 Shark（多日志源）。
# 复制为 traffic_ingest_push_all.sh，改 TOKEN / SHARK_BASE / 路径后 chmod +x 使用。
#
# Shark 后台「多站点 / 域名」里四个 id 需与此处 TRAFFIC_INGEST_SOURCE 一致，
# Redis 模式填对应 redis_key；并配置四个独立 STATE_FILE，避免游标串台。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH="${SCRIPT_DIR}/traffic_ingest_push_incremental.sh"

export TRAFFIC_INGEST_TOKEN="${TRAFFIC_INGEST_TOKEN:?请 export TRAFFIC_INGEST_TOKEN}"
export SHARK_BASE="${SHARK_BASE:?请 export SHARK_BASE，如 https://ops.example.com}"

# 可选：首次部署跳过历史
# export INGEST_SKIP_BACKLOG=1
# 日志行很长或仍 413 时调小单包（默认脚本已约 512KiB/400 行）
# export BATCH_MAX_BYTES=262144
# export BATCH_MAX_LINES=200

# 日志目录（按你机器实际路径改）
LOG_DIR="${LOG_DIR:-/var/log/nginx}"

run_one() {
  local id="$1"
  local file="$2"
  export NGINX_ACCESS_JSON_LOG="$file"
  export TRAFFIC_INGEST_SOURCE="$id"
  export STATE_FILE="${STATE_ROOT:-/var/lib/traffic-ingest-push}/state_${id}"
  echo "=== $id → $file ==="
  "$PUSH"
}

run_one api          "${LOG_DIR}/access_api.json.log"
run_one bot          "${LOG_DIR}/access_bot.json.log"
run_one erp          "${LOG_DIR}/access_erp.json.log"
run_one web_admin    "${LOG_DIR}/access_web_admin.json.log"
