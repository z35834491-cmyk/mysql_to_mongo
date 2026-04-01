# Traffic 分钟聚合：Redis 缓冲 → PG + ClickHouse 长期存储

## 数据流

1. **ingest** 写原始行到 Redis List（不变）。  
2. **`TRAFFIC_ROLLUP_ENABLED=1`** 时，同一批在 **Redis** 里累计分钟桶（`traffic/services/rollup_buffer.py`）。  
3. **`python manage.py traffic_rollup_flush`**（建议每分钟）：把已闭合分钟刷入 **Postgres** `TrafficMinuteRollup`，并在配置了 `CLICKHOUSE_*` 时 **同步写入 ClickHouse**。  
4. **大盘自定义时间范围**：合并查询 **Postgres + ClickHouse**（同分钟以 ClickHouse 为准），长时间数据以 CH 为主。

## 1. 创建 ClickHouse 账号 Secret

```bash
kubectl -n middleware-system create secret generic clickhouse-traffic-auth \
  --from-literal=password="$(openssl rand -base64 24)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

记下密码（或从 Secret 取回）备用。

## 2. 部署 ClickHouse

```bash
kubectl apply -f infra/kubernetes/middleware-system/clickhouse-traffic.yaml
kubectl -n middleware-system rollout status deploy/clickhouse-traffic --timeout=300s
```

## 3. 初始化库表（Job，执行一次）

```bash
kubectl apply -f infra/kubernetes/middleware-system/clickhouse-traffic-init-job.yaml
kubectl -n middleware-system wait --for=condition=complete job/clickhouse-traffic-init --timeout=300s
kubectl -n middleware-system logs job/clickhouse-traffic-init
```

## 4. 修改 Shark（shark-platform）环境变量

**方式 A（推荐）：`kubectl set env`**

```bash
NS=middleware-system
DEPLOY=shark-platform   # 按实际 Deployment 名改

kubectl -n "$NS" set env deployment/"$DEPLOY" \
  CLICKHOUSE_HOST=clickhouse."$NS".svc.cluster.local \
  CLICKHOUSE_PORT=8123 \
  CLICKHOUSE_USER=shark \
  CLICKHOUSE_DATABASE=traffic \
  CLICKHOUSE_ROLLUP_TABLE=traffic_minute_rollup

kubectl -n "$NS" patch deployment "$DEPLOY" --type=json -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/env/-","value":{
    "name":"CLICKHOUSE_PASSWORD",
    "valueFrom":{"secretKeyRef":{"name":"clickhouse-traffic-auth","key":"password"}}
  }}
]'
```

若 `env` 里已有 `CLICKHOUSE_PASSWORD`，请用 `kubectl edit deployment` 改为 `valueFrom`，避免重复 key。

**方式 B：合并 YAML**

将 `shark-platform-clickhouse-env.yaml` 中的 `env` 条目并入现有 `shark-platform` 容器（与 `TRAFFIC_REDIS_URL` 等并列），再 `kubectl apply -f your-full-deployment.yaml`。

**滚动重启**

```bash
kubectl -n middleware-system rollout restart deployment/shark-platform
kubectl -n middleware-system rollout status deployment/shark-platform --timeout=300s
```

## 5. 依赖

- 镜像需已安装 `clickhouse-connect`（本仓库 `requirements.txt` 已列）。  
- 仍需 **`TRAFFIC_ROLLUP_ENABLED=1`** 与定时 **`traffic_rollup_flush`**（见 Traffic 文档 / Cron）。

## 6. 连接串对照

| 环境变量 | 示例值 |
|----------|--------|
| `CLICKHOUSE_HOST` | `clickhouse.middleware-system.svc.cluster.local` |
| `CLICKHOUSE_PORT` | `8123` |
| `CLICKHOUSE_USER` | `shark` |
| `CLICKHOUSE_PASSWORD` | Secret `clickhouse-traffic-auth` / `password` |
| `CLICKHOUSE_DATABASE` | `traffic` |
| `CLICKHOUSE_ROLLUP_TABLE` | `traffic_minute_rollup` |

## 7. 卸载（慎用）

```bash
kubectl -n middleware-system delete job clickhouse-traffic-init --ignore-not-found
kubectl -n middleware-system delete configmap clickhouse-traffic-ddl --ignore-not-found
kubectl -n middleware-system delete deployment clickhouse-traffic --ignore-not-found
kubectl -n middleware-system delete svc clickhouse --ignore-not-found
kubectl -n middleware-system delete pvc clickhouse-traffic-data --ignore-not-found
```

PVC 删除会丢数据；Secret 可按需保留。
