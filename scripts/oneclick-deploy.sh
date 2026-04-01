#!/usr/bin/env bash
#
# Shark Platform — 交互式一键部署（Docker Compose）
# 用法（在仓库根目录）:
#   ./scripts/oneclick-deploy.sh
#
# 非交互:
#   ./scripts/oneclick-deploy.sh --yes
#   ./scripts/oneclick-deploy.sh --yes --sync
#   ./scripts/oneclick-deploy.sh --yes --sync --traffic
#   # 仅 --traffic 且无 --sync 时需 Redis 地址:
#   ONCLICK_TRAFFIC_REDIS_URL='redis://:pass@host:6379/0' ./scripts/oneclick-deploy.sh --yes --traffic
#
# 环境变量（非交互可选）:
#   ONCLICK_DJANGO_SECRET_KEY  ONCLICK_ALLOWED_HOSTS  ONCLICK_CSRF_TRUSTED_ORIGINS
#   ONCLICK_PUBLIC_URL         ONCLICK_TRAFFIC_REDIS_URL  ONCLICK_TRAFFIC_ROLLUP=1
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE_FILE="$ROOT/infra/docker/docker-compose.yml"
COMPOSE_SYNC_DEP="$ROOT/infra/docker/docker-compose.sync-depends.yml"
ENV_DEPLOY="$ROOT/infra/docker/.env.deploy"
SERVICE_NAME="syncer_app"

YES=0
SYNC=0
TRAFFIC_FLAG=0

for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    --sync) SYNC=1 ;;
    --traffic) TRAFFIC_FLAG=1 ;;
    -h|--help)
      cat <<'USAGE'
Shark Platform 一键部署（Docker Compose）

  ./scripts/oneclick-deploy.sh              交互向导
  ./scripts/oneclick-deploy.sh --yes        非交互：仅应用 + 随机密钥
  ./scripts/oneclick-deploy.sh --yes --sync 非交互：含 MySQL/Mongo/Redis/RabbitMQ
  ./scripts/oneclick-deploy.sh --yes --sync --traffic
                                            同上 + 栈内 Redis 供 Traffic ingest

无 --sync 但使用 --traffic 时需设置 ONCLICK_TRAFFIC_REDIS_URL。
USAGE
      exit 0
      ;;
    *)
      echo "未知参数: $arg（使用 --help）" >&2
      exit 1
      ;;
  esac
done

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  BOLD="$(tput bold)" DIM="$(tput dim)" GREEN="$(tput setaf 2)" YELLOW="$(tput setaf 3)"
  CYAN="$(tput setaf 6)" RESET="$(tput sgr0)"
else
  BOLD="" DIM="" GREEN="" YELLOW="" CYAN="" RESET=""
fi

say() { printf '%b\n' "$*"; }
step() { say "${CYAN}${BOLD}>>>${RESET} $*"; }
warn() { say "${YELLOW}!!${RESET} $*" >&2; }
ok() { say "${GREEN}✓${RESET} $*"; }
die() { say "${YELLOW}错误:${RESET} $*" >&2; exit 1; }

prompt() {
  local def="$1" msg="$2" line
  if (( YES )); then
    echo "$def"
    return
  fi
  read -r -p "${msg} [${def}]: " line || true
  if [[ -z "${line// }" ]]; then
    echo "$def"
  else
    echo "$line"
  fi
}

prompt_yn() {
  local def="$1" msg="$2" c
  if (( YES )); then
    [[ "$def" == [yY]* ]] && return 0 || return 1
  fi
  while true; do
    read -r -p "${msg} (y/n) [${def}]: " c || true
    c="${c:-$def}"
    case "$c" in
      [yY]|[yY][eE][sS]) return 0 ;;
      [nN]|[nN][oO]) return 1 ;;
      *) say "请输入 y 或 n" ;;
    esac
  done
}

strip_newlines() { tr -d '\r\n' | head -c 8192; }

check_docker() {
  command -v docker >/dev/null 2>&1 || die "未找到 docker。"
  docker info >/dev/null 2>&1 || die "Docker 未运行或无权限。"
  docker compose version >/dev/null 2>&1 || die "需要 Docker Compose V2（docker compose）。"
}

write_env_deploy() {
  local secret="$1" hosts="$2" csrf="$3" pub="$4" redis_url="$5" ingest_token="$6" rollup="$7"
  umask 077
  mkdir -p "$(dirname "$ENV_DEPLOY")"
  : >"$ENV_DEPLOY"
  {
    echo "# 由 scripts/oneclick-deploy.sh 生成 — 勿提交 Git"
    echo "DJANGO_SECRET_KEY=${secret}"
    echo "ALLOWED_HOSTS=${hosts}"
    echo "CSRF_TRUSTED_ORIGINS=${csrf}"
    echo "PUBLIC_URL=${pub}"
    echo "PYTHONUNBUFFERED=1"
    [[ -n "$redis_url" ]] && echo "TRAFFIC_REDIS_URL=${redis_url}"
    [[ -n "$ingest_token" ]] && echo "TRAFFIC_INGEST_TOKEN=${ingest_token}"
    [[ "$rollup" == "1" ]] && echo "TRAFFIC_ROLLUP_ENABLED=1"
  } >>"$ENV_DEPLOY"
  ok "已写入 ${ENV_DEPLOY}"
}

clear 2>/dev/null || true
say ""
say "${BOLD}Shark Platform — 一键部署${RESET}"
say "${DIM}${ROOT}${RESET}"
say ""

check_docker
ok "Docker / Compose 可用"
[[ -f "$COMPOSE_FILE" ]] || die "缺少 ${COMPOSE_FILE}"

# ---------- 配置变量 ----------
SECRET=""
HOSTS=""
CSRF=""
PUB=""
REDIS_URL=""
INGEST_TOKEN=""
ROLLUP=0

if (( YES )); then
  SECRET="${ONCLICK_DJANGO_SECRET_KEY:-$(openssl rand -base64 48 | tr -d '\n')}"
  HOSTS="${ONCLICK_ALLOWED_HOSTS:-*}"
  CSRF="${ONCLICK_CSRF_TRUSTED_ORIGINS:-http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5173,http://localhost:5173}"
  PUB="${ONCLICK_PUBLIC_URL:-http://localhost:8000}"

  if (( TRAFFIC_FLAG )); then
    if (( SYNC )); then
      REDIS_URL="redis://:root@redis:6379/2"
      INGEST_TOKEN="$(openssl rand -hex 32 | tr -d '\n')"
    else
      REDIS_URL="${ONCLICK_TRAFFIC_REDIS_URL:-}"
      [[ -n "$REDIS_URL" ]] || die "非交互下使用 --traffic 且无 --sync 时，请设置环境变量 ONCLICK_TRAFFIC_REDIS_URL"
      INGEST_TOKEN="$(openssl rand -hex 32 | tr -d '\n')"
    fi
    [[ "${ONCLICK_TRAFFIC_ROLLUP:-}" == "1" ]] && ROLLUP=1
  fi
else
  say "${BOLD}按提示输入；直接回车使用默认值。${RESET}"
  say ""

  step "编排规模"
  say "  ${DIM}[1]${RESET} 仅 Shark + SQLite（默认）"
  say "  ${DIM}[2]${RESET} 完整栈：MySQL、Mongo 副本集、Redis、RabbitMQ"
  if prompt_yn "n" "是否启用完整依赖栈？"; then
    SYNC=1
  fi

  step "Django 安全与访问"
  DEF_SEC="$(openssl rand -base64 48 | tr -d '\n')"
  SECRET="$(prompt "$DEF_SEC" "DJANGO_SECRET_KEY")"
  SECRET="$(echo "$SECRET" | strip_newlines)"
  [[ -n "$SECRET" ]] || SECRET="$DEF_SEC"

  HOSTS="$(prompt "*" "ALLOWED_HOSTS（逗号分隔）")"
  HOSTS="$(echo "$HOSTS" | strip_newlines)"

  DEF_CSRF="http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5173,http://localhost:5173"
  CSRF="$(prompt "$DEF_CSRF" "CSRF_TRUSTED_ORIGINS")"
  CSRF="$(echo "$CSRF" | strip_newlines)"

  PUB="$(prompt "http://localhost:8000" "PUBLIC_URL")"
  PUB="$(echo "$PUB" | strip_newlines)"

  step "Traffic Dashboard（ingest → Redis，可选）"
  if (( SYNC )); then
    if prompt_yn "n" "是否启用 Traffic（使用 Compose 内 Redis，密码 root）？"; then
      TRAFFIC_FLAG=1
      REDIS_URL="redis://:root@redis:6379/2"
      INGEST_TOKEN="$(openssl rand -hex 32 | tr -d '\n')"
      say "${DIM}TRAFFIC_INGEST_TOKEN=${INGEST_TOKEN}${RESET}"
      if prompt_yn "n" "是否设置 TRAFFIC_ROLLUP_ENABLED=1（需定时 traffic_rollup_flush）？"; then
        ROLLUP=1
      fi
    fi
  else
    if prompt_yn "n" "是否启用 Traffic（需自行填写可达的 Redis URL）？"; then
      TRAFFIC_FLAG=1
      RU="$(prompt "" "TRAFFIC_REDIS_URL（例 redis://:pass@host:6379/0）")"
      RU="$(echo "$RU" | strip_newlines)"
      [[ -n "$RU" ]] || die "未填写 TRAFFIC_REDIS_URL"
      REDIS_URL="$RU"
      INGEST_TOKEN="$(openssl rand -hex 32 | tr -d '\n')"
      say "${DIM}TRAFFIC_INGEST_TOKEN=${INGEST_TOKEN}${RESET}"
      if prompt_yn "n" "是否设置 TRAFFIC_ROLLUP_ENABLED=1？"; then
        ROLLUP=1
      fi
    fi
  fi

  step "确认启动"
  say "  完整依赖栈: $([[ $SYNC -eq 1 ]] && echo 是 || echo 否)"
  say "  Traffic: $([[ -n "$REDIS_URL" ]] && echo 是 || echo 否)"
  prompt_yn "y" "确认写入配置并启动容器？" || die "已取消"
fi

write_env_deploy "$SECRET" "$HOSTS" "$CSRF" "$PUB" "$REDIS_URL" "$INGEST_TOKEN" "$ROLLUP"

mkdir -p "$ROOT/state" "$ROOT/logs"

step "构建并启动"
CMD=(docker compose -f "$COMPOSE_FILE")
if (( SYNC )); then
  CMD+=(--profile sync -f "$COMPOSE_SYNC_DEP")
  warn "首次拉取镜像可能较慢；Mongo 副本集初始化约 1～2 分钟。"
fi
CMD+=(up -d --build)

say "${DIM}${CMD[*]}${RESET}"
"${CMD[@]}"

step "等待就绪: GET /api/system/health（最多约 120s）"
ok_hit=0
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8000/api/system/health" >/dev/null 2>&1; then
    ok_hit=1
    break
  fi
  sleep 2
done

say ""
say "${BOLD}──────── 结果 ────────${RESET}"
if (( ok_hit )); then
  ok "Web: http://localhost:8000（若 PUBLIC_URL 不同请以实际为准）"
  say "  管理员: ${BOLD}admin${RESET} / ${BOLD}admin${RESET} — 请登录后立即改密。"
  if [[ -n "$INGEST_TOKEN" ]]; then
    say "  Traffic: POST .../api/traffic/ingest  Header: Authorization: Bearer ${INGEST_TOKEN}"
  fi
  say "  环境文件: ${ENV_DEPLOY}（勿提交）"
  say "  文档: docs/deployment/README.md"
else
  warn "健康检查未通过，查看日志:"
  say "  docker compose -f infra/docker/docker-compose.yml logs -f $SERVICE_NAME"
  exit 1
fi
say "${BOLD}──────────────────────${RESET}"
say ""
