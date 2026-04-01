# Traffic 中间件（K8s）：GeoIP · Redis · ClickHouse

统一说明 `infra/kubernetes/middleware-system/` 下与 **Traffic Dashboard** 相关的清单与操作。以下命令默认在**仓库根目录**执行，`kubectl` 指向目标集群。

**命名空间示例**：`middleware-system`  
**Shark Deployment 示例**：`shark-platform`  

---

## A. GeoLite2（PVC）+ Traffic Redis + Shark 环境

**安全提示**：若改用 **MaxMind 官方直链** 下载，**License Key 不得写入 Git**。

当前仓库内 **Job / CronJob** 可使用 **jsDelivr npm 镜像**拉取 `GeoLite2-City.mmdb.gz`，**不需要** `maxmind-credentials` Secret。第三方镜像的版本与授权请自行评估（见本文 **A.13**）。

### A.1 命名空间

```bash
kubectl create namespace middleware-system
```

### A.2（可选）MaxMind 官方凭据 Secret

仅当你把 Job 改回 **download.maxmind.com + Basic 认证** 时才需要：

```bash
kubectl -n middleware-system create secret generic maxmind-credentials \
  --from-literal=account_id='你的AccountID' \
  --from-literal=license_key='你的LicenseKey' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### A.3 Traffic ingest 密钥 Secret

```bash
export TRAFFIC_INGEST_TOKEN="$(openssl rand -hex 32)"
echo "请保存 Nginx 推送用的 TOKEN: $TRAFFIC_INGEST_TOKEN"

kubectl -n middleware-system create secret generic traffic-ingest \
  --from-literal=token="$TRAFFIC_INGEST_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### A.4 GeoIP PVC

```bash
kubectl apply -f infra/kubernetes/middleware-system/geoip-maxmind-pvc.yaml
```

（若集群要求 StorageClass，编辑 YAML 中 `storageClassName` 后重试。）

### A.5 Redis（若尚未创建）

```bash
kubectl apply -f infra/kubernetes/middleware-system/traffic-redis.yaml
kubectl -n middleware-system rollout status deploy/traffic-redis --timeout=120s
```

### A.6 首次下载 GeoLite2-City 到 PVC

来源示例：`https://cdn.jsdelivr.net/npm/geolite2-city/GeoLite2-City.mmdb.gz`（无需 MaxMind Secret）。

```bash
kubectl apply -f infra/kubernetes/middleware-system/maxmind-geolite2-download-job.yaml
kubectl -n middleware-system wait --for=condition=complete job/maxmind-geolite2-city-initial --timeout=300s
kubectl -n middleware-system logs job/maxmind-geolite2-city-initial
```

重跑前需删旧 Job：`kubectl -n middleware-system delete job maxmind-geolite2-city-initial --ignore-not-found`

### A.7 定期更新（CronJob）

```bash
kubectl apply -f infra/kubernetes/middleware-system/maxmind-geolite2-cronjob.yaml
```

### A.8 Shark：挂载 PVC + 环境变量

将 `infra/kubernetes/middleware-system/shark-platform-geoip-traffic-patch.yaml` 中的 `volumes` / `volumeMounts` / `env` **合并**进现有 `shark-platform` Deployment。

需包含：

- `volumeMounts`: `name: geoip-maxmind`, `mountPath: /data/geoip`, `readOnly: true`
- `volumes`: `persistentVolumeClaim.claimName: geoip-maxmind-pvc`
- `env`:
  - `TRAFFIC_REDIS_URL=redis://traffic-redis.middleware-system.svc.cluster.local:6379/2`
  - `TRAFFIC_GEOIP_DB=/data/geoip/GeoLite2-City.mmdb`
  - `TRAFFIC_INGEST_TOKEN` 来自 `secretKeyRef: traffic-ingest / key: token`

```bash
kubectl -n middleware-system rollout status deploy/shark-platform --timeout=300s
```

### A.9 迁移（如需要）

```bash
kubectl -n middleware-system exec deploy/shark-platform -- python manage.py migrate traffic
```

### A.10 Web 配置 Traffic Dashboard

登录 → Traffic Dashboard → 设置：**远程推送 → Redis**、Redis Key、`MaxMind mmdb` 路径、`JSON` 日志格式等。详见 [TRAFFIC_DASHBOARD.md](../TRAFFIC_DASHBOARD.md)。

### A.11 独立 Nginx 推送日志

```bash
export SHARK_BASE="https://你的Shark入口域名"
export TOKEN='与 traffic-ingest Secret 中 token 一致'

sudo tail -n 2000 /var/log/nginx/access.json.log | curl -sS -X POST "${SHARK_BASE}/api/traffic/ingest" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-binary @-
```

**HTTP 413**：见 [FILEBEAT_NGINX_TRAFFIC.md](../FILEBEAT_NGINX_TRAFFIC.md) 与 `scripts/traffic_ingest_push_incremental.sh`；Ingress 需放大 `client_max_body_size` / `proxy-body-size`。

### A.12 文件清单（YAML）

| 文件 | 说明 |
|------|------|
| `geoip-maxmind-pvc.yaml` | PVC |
| `maxmind-credentials-secret.example.yaml` | 占位示例 |
| `maxmind-geolite2-download-job.yaml` | 首次 Job |
| `maxmind-geolite2-cronjob.yaml` | 周更 CronJob |
| `traffic-redis.yaml` | Redis + Service |
| `shark-platform-geoip-traffic-patch.yaml` | Shark 片段参考 |

### A.13 GeoLite2 下载与合规说明

- **jsDelivr**：`https://cdn.jsdelivr.net/npm/geolite2-city/GeoLite2-City.mmdb.gz` — 无需 Key；注意条款与版本滞后。
- **MaxMind 官方**：`download.maxmind.com` + Basic（Account ID + License Key），需 `curl -L` 跟随重定向；**451** 多为地区限制或账户未开通 GeoLite2。
- 亦可使用 [geoipupdate](https://github.com/maxmind/geoipupdate) 或合规渠道将 `.mmdb` 放入 PVC。

---

## B. ClickHouse（Traffic 分钟聚合长期存储，可选）

### B.1 数据流

1. **ingest** 写原始行到 Redis List。  
2. **`TRAFFIC_ROLLUP_ENABLED=1`** 时在 Redis 累计分钟桶。  
3. **`python manage.py traffic_rollup_flush`**：写入 Postgres `TrafficMinuteRollup`，并可选写入 ClickHouse。  
4. 大盘长区间：合并 **Postgres + ClickHouse**（同分钟以 CH 为准）。

### B.2 创建 ClickHouse 账号 Secret

```bash
kubectl -n middleware-system create secret generic clickhouse-traffic-auth \
  --from-literal=password="$(openssl rand -base64 24)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### B.3 部署与初始化

```bash
kubectl apply -f infra/kubernetes/middleware-system/clickhouse-traffic.yaml
kubectl -n middleware-system rollout status deploy/clickhouse-traffic --timeout=300s

kubectl apply -f infra/kubernetes/middleware-system/clickhouse-traffic-init-job.yaml
kubectl -n middleware-system wait --for=condition=complete job/clickhouse-traffic-init --timeout=300s
kubectl -n middleware-system logs job/clickhouse-traffic-init
```

### B.4 Shark 环境变量

```bash
NS=middleware-system
DEPLOY=shark-platform

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

镜像需含 `clickhouse-connect`（见根目录 `requirements.txt`）。合并片段可参考 `shark-platform-clickhouse-env.yaml`。

### B.5 卸载（慎用）

```bash
kubectl -n middleware-system delete job clickhouse-traffic-init --ignore-not-found
kubectl -n middleware-system delete deployment clickhouse-traffic --ignore-not-found
kubectl -n middleware-system delete svc clickhouse --ignore-not-found
kubectl -n middleware-system delete pvc clickhouse-traffic-data --ignore-not-found
```

DDL ConfigMap 等按集群实际资源名清理。

---

## 相关文档

- [TRAFFIC_DASHBOARD.md](../TRAFFIC_DASHBOARD.md) — 大盘与 ingest API  
- [FILEBEAT_NGINX_TRAFFIC.md](../FILEBEAT_NGINX_TRAFFIC.md) — Filebeat / Logstash 推送  
- SQL 参考：`infra/clickhouse/traffic_minute_rollup.sql`
