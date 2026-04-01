#!/usr/bin/env bash
# Shark Platform：本地一键构建并启动 Docker Compose
# 用法（在仓库根目录）:
#   ./scripts/deploy-local.sh
#   ./scripts/deploy-local.sh --sync    # 同时启动 MySQL / Mongo RS / Redis / RabbitMQ，并等待依赖后启动应用
#   ./scripts/deploy-local.sh --migrate # 对已运行的 syncer_app 执行 migrate（不重建）
#   ./scripts/deploy-local.sh --help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_BASE=(docker compose -f infra/docker/docker-compose.yml)
SERVICE_NAME="syncer_app"
SYNC=0
MIGRATE_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --sync) SYNC=1 ;;
    --migrate) MIGRATE_ONLY=1 ;;
    -h|--help)
      cat <<'USAGE'
用法（在仓库根目录）:
  ./scripts/deploy-local.sh              仅应用 + SQLite，构建并启动 Compose
  ./scripts/deploy-local.sh --sync       同时 MySQL / Mongo RS / Redis / RabbitMQ，并等待依赖
  ./scripts/deploy-local.sh --migrate    对已运行的 syncer_app 执行 migrate
  ./scripts/deploy-local.sh --help       显示本说明
USAGE
      exit 0
      ;;
    *)
      echo "未知参数: $arg（使用 --help）" >&2
      exit 1
      ;;
  esac
done

if (( MIGRATE_ONLY )); then
  echo ">>> migrate ($SERVICE_NAME)"
  "${COMPOSE_BASE[@]}" exec -T "$SERVICE_NAME" python3 manage.py migrate
  echo ">>> 完成"
  exit 0
fi

CMD=("${COMPOSE_BASE[@]}")
if (( SYNC )); then
  CMD+=(--profile sync -f infra/docker/docker-compose.sync-depends.yml)
  echo ">>> 启动模式: 含 sync profile（MySQL / Mongo / Redis / RabbitMQ + 依赖顺序）"
else
  echo ">>> 启动模式: 仅应用（SQLite state）"
fi

CMD+=(up -d --build)

echo ">>> ${CMD[*]}"
"${CMD[@]}"

echo ""
echo ">>> 等待健康检查（最多 90s）..."
ok=0
for i in $(seq 1 45); do
  if curl -sf "http://127.0.0.1:8000/api/system/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if (( ok )); then
  echo ">>> 就绪: http://localhost:8000 （默认 admin / admin，请尽快修改密码）"
else
  echo ">>> 未在 90s 内探测到 /api/system/health，请检查: docker compose -f infra/docker/docker-compose.yml logs -f $SERVICE_NAME" >&2
  exit 1
fi
