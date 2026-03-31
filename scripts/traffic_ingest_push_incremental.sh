#!/usr/bin/env bash
# 增量推送 Nginx JSON access 日志到 Shark POST /api/traffic/ingest（仅需 bash + curl + awk + dd/tail）
#
# 环境变量（与旧版 Python 脚本对齐）:
#   TRAFFIC_INGEST_URL / SHARK_BASE + /api/traffic/ingest
#   TRAFFIC_INGEST_TOKEN 或 TOKEN
#   NGINX_ACCESS_JSON_LOG   默认 /var/log/nginx/access.json.log
#   STATE_FILE              状态前缀，默认 /var/lib/traffic-ingest-push/state
#                             实际文件: ${STATE_FILE}.meta / .partial / .lock
#   BATCH_MAX_LINES         默认 400（与 BATCH_MAX_BYTES 同时生效，先到先切）
#   BATCH_MAX_BYTES         默认 524288（512KiB），避免 Nginx 默认 client_max_body_size 1m 导致 413
#   CONNECT_TIMEOUT         curl --connect-timeout（秒）默认 30
#   MAX_TIME                curl --max-time（秒）默认 120
#   DRY_RUN=1               只打印，不写状态、不 POST
#   INGEST_SKIP_BACKLOG=1   若尚无 .meta，则只记录到 EOF，不推历史
#   TRAFFIC_INGEST_SOURCE   可选，追加 ?source= 与后台 log_sources 的 id 对应
#
# crontab 示例:
#   * * * * * TRAFFIC_INGEST_TOKEN=xxx SHARK_BASE=https://ops.example.com \
#     /path/to/traffic_ingest_push_incremental.sh >>/var/log/traffic-ingest.log 2>&1

set -euo pipefail

: "${NGINX_ACCESS_JSON_LOG:=/var/log/nginx/access.json.log}"
: "${STATE_FILE:=/var/lib/traffic-ingest-push/state}"
: "${BATCH_MAX_LINES:=400}"
: "${BATCH_MAX_BYTES:=524288}"
: "${CONNECT_TIMEOUT:=30}"
: "${MAX_TIME:=120}"
: "${DRY_RUN:=0}"
: "${INGEST_SKIP_BACKLOG:=0}"

[[ "$BATCH_MAX_LINES" =~ ^[0-9]+$ ]] || BATCH_MAX_LINES=400
(( BATCH_MAX_LINES < 1 )) && BATCH_MAX_LINES=1
(( BATCH_MAX_LINES > 100000 )) && BATCH_MAX_LINES=100000

[[ "$BATCH_MAX_BYTES" =~ ^[0-9]+$ ]] || BATCH_MAX_BYTES=524288
(( BATCH_MAX_BYTES < 4096 )) && BATCH_MAX_BYTES=4096
(( BATCH_MAX_BYTES > 52428800 )) && BATCH_MAX_BYTES=52428800

TOKEN="${TRAFFIC_INGEST_TOKEN:-${TOKEN:-}}"

die() { echo "$*" >&2; exit 1; }

file_inode() {
  if stat -c '%i' "$1" 2>/dev/null; then return; fi
  stat -f '%i' "$1"
}

file_size() {
  if stat -c '%s' "$1" 2>/dev/null; then return; fi
  stat -f '%z' "$1"
}

# 去掉旧版 .json 后缀，统一用 ${STATE_FILE}.meta
STATE_BASE="${STATE_FILE%.json}"
META="${STATE_BASE}.meta"
PARTIAL="${STATE_BASE}.partial"
LOCKF="${STATE_BASE}.lock"

if [[ -z "$TOKEN" ]]; then
  die "请设置 TRAFFIC_INGEST_TOKEN 或 TOKEN"
fi

if [[ -n "${TRAFFIC_INGEST_URL:-}" ]]; then
  BASE_URL="${TRAFFIC_INGEST_URL%/}"
elif [[ -n "${SHARK_BASE:-}" ]]; then
  BASE_URL="${SHARK_BASE%/}/api/traffic/ingest"
else
  die "请设置 TRAFFIC_INGEST_URL 或 SHARK_BASE"
fi

INGEST_URL="$BASE_URL"
if [[ -n "${TRAFFIC_INGEST_SOURCE:-}" ]]; then
  if [[ "$INGEST_URL" == *\?* ]]; then
    INGEST_URL="${INGEST_URL}&source=${TRAFFIC_INGEST_SOURCE}"
  else
    INGEST_URL="${INGEST_URL}?source=${TRAFFIC_INGEST_SOURCE}"
  fi
fi

TMPDIR=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

read_meta() {
  saved_inode=""
  saved_offset=0
  [[ -f "$META" ]] || return 0
  # shellcheck disable=SC1090
  while IFS= read -r line; do
    case "$line" in
      inode=*) saved_inode="${line#inode=}" ;;
      offset=*) saved_offset="${line#offset=}" ;;
    esac
  done < "$META"
  [[ "$saved_offset" =~ ^[0-9]+$ ]] || saved_offset=0
}

write_meta() {
  local i="$1" o="$2"
  mkdir -p "$(dirname "$META")"
  local t
  t=$(mktemp)
  printf 'inode=%s\noffset=%s\n' "$i" "$o" > "$t"
  mv -f "$t" "$META"
}

chunk_ends_with_newline() {
  local f="$1"
  [[ -s "$f" ]] || return 1
  [[ "$(tail -c1 "$f" | od -An -t x1 2>/dev/null | tr -d ' \n')" = "0a" ]]
}

post_file() {
  local body="$1"
  local code out
  out=$(mktemp)
  code=$(
    curl -sS -o "$out" -w '%{http_code}' -X POST "$INGEST_URL" \
      --connect-timeout "$CONNECT_TIMEOUT" \
      --max-time "$MAX_TIME" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: text/plain; charset=utf-8" \
      --data-binary "@${body}"
  ) || true
  if [[ "$code" == "200" ]]; then
    cat "$out"
    rm -f "$out"
    return 0
  fi
  local err
  err=$(head -c 400 "$out" 2>/dev/null || true)
  rm -f "$out"
  if [[ "$code" == "413" ]]; then
    die "HTTP 413 请求体过大。可：① 降低 BATCH_MAX_BYTES（当前 ${BATCH_MAX_BYTES}）或 BATCH_MAX_LINES（当前 ${BATCH_MAX_LINES}）；② 在 Nginx/Ingress 增大 client_max_body_size / proxy-body-size；③ 提高 cron 频率减小单次积压。"
  fi
  die "POST 失败 HTTP ${code} ${err}"
}

# 当前行写入 body 后的字节数（UTF-8 安全）
line_payload_bytes() {
  LC_ALL=C printf '%s\n' "$1" | wc -c | tr -d ' '
}

flush_batch() {
  local cur_batch="$1"
  local cnt="$2"
  local resp
  [[ -s "$cur_batch" ]] || return 0
  resp=$(post_file "$cur_batch")
  echo "$resp"
  total=$((total + cnt))
  batches=$((batches + 1))
  : > "$cur_batch"
}

run_locked() {
  read_meta

  [[ -f "$NGINX_ACCESS_JSON_LOG" ]] || die "日志不存在: $NGINX_ACCESS_JSON_LOG"

  local cur_ino cur_size
  cur_ino=$(file_inode "$NGINX_ACCESS_JSON_LOG")
  cur_size=$(file_size "$NGINX_ACCESS_JSON_LOG")

  if [[ ! -f "$META" && "$INGEST_SKIP_BACKLOG" == "1" ]]; then
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "{\"note\":\"dry_run skip_backlog\",\"offset\":${cur_size}}"
    else
      write_meta "$cur_ino" "$cur_size"
      : > "$PARTIAL"
      echo "{\"note\":\"initialized at EOF (INGEST_SKIP_BACKLOG=1)\",\"offset\":${cur_size}}"
    fi
    return 0
  fi

  local offset="$saved_offset"
  if [[ -n "$saved_inode" && "$saved_inode" != "$cur_ino" ]]; then
    offset=0
    : > "$PARTIAL"
  fi
  if (( offset > cur_size )); then
    offset=0
    : > "$PARTIAL"
  fi

  local chunk_size=$((cur_size - offset))
  local CHUNK="$TMPDIR/chunk"
  local MERGED="$TMPDIR/merged"
  local LINES="$TMPDIR/lines.txt"

  if (( chunk_size > 0 )); then
    dd if="$NGINX_ACCESS_JSON_LOG" of="$CHUNK" bs=1 skip="$offset" count="$chunk_size" 2>/dev/null
  else
    : > "$CHUNK"
  fi

  local new_off=$((offset + chunk_size))

  if [[ ! -s "$CHUNK" && ! -s "$PARTIAL" ]]; then
    write_meta "$cur_ino" "$new_off"
    echo '{"accepted":0,"note":"no new data"}'
    return 0
  fi

  if [[ ! -s "$CHUNK" ]]; then
    echo '{"accepted":0,"note":"only partial line buffered"}'
    return 0
  fi

  if [[ -s "$PARTIAL" ]]; then
    cat "$PARTIAL" "$CHUNK" > "$MERGED"
  else
    cp "$CHUNK" "$MERGED"
  fi

  local ends_nl=0
  chunk_ends_with_newline "$CHUNK" && ends_nl=1

  : > "$LINES"
  if [[ "$ends_nl" -eq 1 ]]; then
    awk 'NR>1{print prev} {prev=$0} END{print prev}' "$MERGED" > "$LINES"
    : > "$PARTIAL"
  else
    awk -v pfile="$PARTIAL" '
      NR>1 { print prev }
      { prev=$0 }
      END { printf "%s", prev > pfile; close(pfile) }
    ' "$MERGED" > "$LINES"
  fi

  grep -v '^$' "$LINES" > "$TMPDIR/lines_nonempty" || true
  mv -f "$TMPDIR/lines_nonempty" "$LINES"

  if [[ ! -s "$LINES" ]]; then
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "{\"accepted\":0,\"note\":\"only partial\",\"dry_run\":true,\"would_offset\":${new_off}}"
    else
      write_meta "$cur_ino" "$new_off"
      echo '{"accepted":0,"note":"only partial line buffered"}'
    fi
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    local n
    n=$(wc -l < "$LINES" | tr -d ' ')
    echo "{\"dry_run\":true,\"lines\":${n},\"would_offset\":${new_off}}"
    return 0
  fi

  local total=0 batches=0
  local cur_batch="$TMPDIR/cur_batch"
  : > "$cur_batch"
  local cnt=0
  local bbytes=0
  local inc
  while IFS= read -r line || [[ -n "${line:-}" ]]; do
    [[ -z "$line" ]] && continue
    inc=$(line_payload_bytes "$line")
    if (( inc > BATCH_MAX_BYTES )); then
      echo "traffic_ingest: 警告 单行字节数 ${inc} > BATCH_MAX_BYTES=${BATCH_MAX_BYTES}，请调大 BATCH_MAX_BYTES 或入口 Nginx client_max_body_size" >&2
    fi
    if (( cnt > 0 && ( cnt >= BATCH_MAX_LINES || bbytes + inc > BATCH_MAX_BYTES ) )); then
      flush_batch "$cur_batch" "$cnt" || die "POST 失败"
      cnt=0
      bbytes=0
    fi
    printf '%s\n' "$line" >> "$cur_batch"
    cnt=$((cnt + 1))
    bbytes=$((bbytes + inc))
  done < "$LINES"
  flush_batch "$cur_batch" "$cnt" || die "POST 失败"

  write_meta "$cur_ino" "$new_off"
  echo "{\"posted_lines\":${total},\"batches\":${batches}}"
}

if command -v flock >/dev/null 2>&1; then
  mkdir -p "$(dirname "$LOCKF")"
  exec 200>"$LOCKF"
  flock 200
  run_locked
else
  echo "warning: 无 flock，并发 cron 可能竞态" >&2
  run_locked
fi
