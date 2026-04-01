# middleware-system：GeoLite2-City（PVC）+ Traffic Redis + Shark 配置步骤

**安全提示**：若改用 **MaxMind 官方直链** 下载，**License Key 不得写入 Git**。

**命名空间**：`middleware-system`  
**Shark Deployment**：`shark-platform`  
**Redis Deployment**：`traffic-redis`  

当前仓库中的 **Job / CronJob** 使用 **jsDelivr npm 镜像**拉取 `GeoLite2-City.mmdb.gz`，**不需要** `maxmind-credentials` Secret。第三方镜像的版本与授权请自行评估（见 §13）。

---

## 1. 命名空间

```bash
kubectl create namespace middleware-system
```

---

## 2.（可选）MaxMind 官方凭据 Secret

仅当你把 Job 改回 **download.maxmind.com + Basic 认证** 时才需要：

```bash
kubectl -n middleware-system create secret generic maxmind-credentials \
  --from-literal=account_id='你的AccountID' \
  --from-literal=license_key='你的LicenseKey' \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 3. Traffic ingest 密钥 Secret

```bash
export TRAFFIC_INGEST_TOKEN="$(openssl rand -hex 32)"
echo "请保存 Nginx 推送用的 TOKEN: $TRAFFIC_INGEST_TOKEN"

kubectl -n middleware-system create secret generic traffic-ingest \
  --from-literal=token="$TRAFFIC_INGEST_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 4. GeoIP PVC

```bash
kubectl apply -f geoip-maxmind-pvc.yaml
```

（若集群要求 StorageClass，编辑 YAML 中 `storageClassName` 后重试。）

---

## 5. Redis（若尚未创建）

```bash
kubectl apply -f traffic-redis.yaml
kubectl -n middleware-system rollout status deploy/traffic-redis --timeout=120s
```

---

## 6. 首次下载 GeoLite2-City 到 PVC

来源：`https://cdn.jsdelivr.net/npm/geolite2-city/GeoLite2-City.mmdb.gz`（无需 MaxMind Secret）。

```bash
kubectl apply -f maxmind-geolite2-download-job.yaml
kubectl -n middleware-system wait --for=condition=complete job/maxmind-geolite2-city-initial --timeout=300s
kubectl -n middleware-system logs job/maxmind-geolite2-city-initial
```

重跑前需删旧 Job：`kubectl -n middleware-system delete job maxmind-geolite2-city-initial --ignore-not-found`

失败时：`kubectl -n middleware-system describe job maxmind-geolite2-city-initial`（出口需能访问 `cdn.jsdelivr.net`）

---

## 7. 定期更新（CronJob，每周日 04:00 UTC）

```bash
kubectl apply -f maxmind-geolite2-cronjob.yaml
```

手动触发一次（与 CronJob 同模板）：

```bash
kubectl -n middleware-system create job --from=cronjob/maxmind-geolite2-city-download maxmind-geolite2-manual-$(date +%s)
kubectl -n middleware-system wait --for=condition=complete job/maxmind-geolite2-manual-* --timeout=300s
```

（将 `job/...` 换成实际 Job 名。）

---

## 8. Shark：挂载 PVC + 环境变量

将 `shark-platform-geoip-traffic-patch.yaml` 中的 `volumes` / `volumeMounts` / `env` **合并**进你现有的 `shark-platform` Deployment（容器名若不是 `shark-platform` 请改名）。

若使用 **kubectl patch**（示例，需按实际容器名调整）：

```bash
# 请先备份当前 Deployment YAML
kubectl -n middleware-system get deploy shark-platform -o yaml > shark-platform.bak.yaml
```

推荐用 **Kustomize strategic merge** 或手工编辑 `kubectl edit deploy shark-platform -n middleware-system`，确保包含：

- `volumeMounts`: `name: geoip-maxmind`, `mountPath: /data/geoip`, `readOnly: true`
- `volumes`: `persistentVolumeClaim.claimName: geoip-maxmind-pvc`
- `env`:
  - `TRAFFIC_REDIS_URL=redis://traffic-redis.middleware-system.svc.cluster.local:6379/2`
  - `TRAFFIC_GEOIP_DB=/data/geoip/GeoLite2-City.mmdb`
  - `TRAFFIC_INGEST_TOKEN` 来自 `secretKeyRef: traffic-ingest / key: token`

滚动：

```bash
kubectl -n middleware-system rollout status deploy/shark-platform --timeout=300s
```

验证 mmdb：

```bash
POD=$(kubectl -n middleware-system get pods -l app=shark-platform -o jsonpath='{.items[0].metadata.name}')
kubectl -n middleware-system exec -it "$POD" -- ls -la /data/geoip/GeoLite2-City.mmdb
```

---

## 9. Shark 应用迁移（如需要）

```bash
kubectl -n middleware-system exec deploy/shark-platform -- python manage.py migrate traffic
```

---

## 10. Web 配置 Traffic Dashboard

登录 → Traffic Dashboard → 设置：

- **采集模式**：远程推送 → Redis  
- **Redis List Key**：`traffic:access:lines`（默认）  
- **Redis 最大行数**：如 `200000`  
- **MaxMind mmdb**：`/data/geoip/GeoLite2-City.mmdb`  
- **日志格式**：JSON 行  

保存后应显示 Redis URL 已配置。

---

## 11. 独立 Nginx 服务器推送日志

```bash
# 在 Nginx 机上
export SHARK_BASE="https://你的Shark入口域名"
export TOKEN='与上面 traffic-ingest Secret 中 token 一致'

sudo tail -n 2000 /var/log/nginx/access.json.log | curl -sS -X POST "${SHARK_BASE}/api/traffic/ingest" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-binary @-
```

成功示例：`{"accepted":2000,"truncated":false}`

### 11.1 推送出现 HTTP 413（Payload Too Large）

入口 **Nginx / Ingress** 默认 `client_max_body_size` 常为 **1m**，大批量 JSON 行易触发 413。处理方式任选：

- **推送端**：使用仓库脚本 `scripts/traffic_ingest_push_incremental.sh`（已按约 **512KiB / 400 行** 切包）；仍 413 时可 `export BATCH_MAX_BYTES=262144`、`BATCH_MAX_LINES=200`。
- **Shark 前向代理**：本仓库 `nginx.conf` 已对 `server` 设置 `client_max_body_size 32m;`，部署镜像后生效。**Kubernetes Ingress** 需加注解，例如 Nginx Ingress：`nginx.ingress.kubernetes.io/proxy-body-size: "32m"`。

---

## 12. 文件清单

| 文件 | 说明 |
|------|------|
| `geoip-maxmind-pvc.yaml` | PVC |
| `maxmind-credentials-secret.example.yaml` | 占位示例，勿填真密钥 |
| `maxmind-geolite2-download-job.yaml` | 首次 Job |
| `maxmind-geolite2-cronjob.yaml` | 周更 CronJob |
| `traffic-redis.yaml` | Redis + Service |
| `shark-platform-geoip-traffic-patch.yaml` | Shark 片段参考 |

---

## 13. GeoLite2 下载说明

### 13.0 当前默认（仓库内 Job / CronJob）

从 **jsDelivr** 拉取 npm 包 `geolite2-city` 中的压缩库：

`https://cdn.jsdelivr.net/npm/geolite2-city/GeoLite2-City.mmdb.gz`

- **优点**：无需 Account / License Key；适合内网集群仅放行 jsDelivr 的场景。  
- **注意**：版本取决于 npm 包维护者更新节奏；**MaxMind 服务条款**对再分发有要求，是否允许使用该镜像请由法务/合规自行判断。

### 13.0.1 MaxMind 官方直链（需改回 YAML 时使用）

`https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz`，Basic 认证：**Account ID** + **License Key**。

脚本中 **`curl -L` 必填**：会先 **302 到 Cloudflare R2**。集群需放行 `*.r2.cloudflarestorage.com`。

### 13.1 `curl: (22) ... 451` 排查（主要针对 **官方** 下载）

使用 **jsDelivr** 时一般不会返回 MaxMind 的 **451**；若失败多为 **404 / 超时 / 出口拦截**，请检查 Job 日志与 `cdn.jsdelivr.net` 连通性。

1. **先在本机验证**（确认账号与 Key 正确、能走完整重定向）：

   ```bash
   curl -sSL -I -L -u 'ACCOUNT_ID:LICENSE_KEY' \
     'https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz'
   ```

   期望最终为 **200** 且 `Content-Type` 与文件相关；若仍为 **451**，见下条。

2. **451 Unavailable For Legal Reasons**  
   MaxMind 对 **部分国家/地区** 不再提供 **GeoLite2 City** 自动下载（合规限制）。若你处于受限区域，即使用 `-L` 也会 **451**。处理方式任选其一：
   - 在**允许下载的环境**（如海外构建机、合规出口）下载 `GeoLite2-City.tar.gz`，再 `kubectl cp` 到临时 Pod 写入 PVC，或放入对象存储后 initContainer 拉取；
   - 使用 MaxMind 允许的 **付费 GeoIP2** 产品（按合同与账户权限）；
   - 使用其他兼容 **`.mmdb`** 的地理库（需自行评估授权与精度），配置仍指向 `TRAFFIC_GEOIP_DB` 路径即可。

3. **集群出口防火墙**  
   放行对 `download.maxmind.com` 及对跳转目标 **R2** 域名的 **HTTPS**（见 [MaxMind 说明：presigned URLs / redirect](https://dev.maxmind.com/geoip/release-notes/2024)）。

4. **账户侧**  
   在 MaxMind 后台确认已创建 **License Key**，且已勾选/同意 **GeoLite2** 相关许可；Key 与 **Account ID**（数字）不要弄反（Basic 认证：用户名 = Account ID）。

### 13.2 官方 geoipupdate（可选）

也可在镜像内使用 MaxMind 的 [geoipupdate](https://github.com/maxmind/geoipupdate) 按 `GeoIP.conf` 更新，同样需网络可达上述域名。

若 MaxMind 变更 URL，以 [MaxMind 文档](https://dev.maxmind.com/geoip/updating-databases) 为准。

### 14. Traffic 分钟聚合长期存储（ClickHouse，可选）

分钟桶在 **Redis** 缓冲、`traffic_rollup_flush` 写入 **Postgres** 并镜像 **ClickHouse** 时，见同目录 **[README-CLICKHOUSE-TRAFFIC.md](./README-CLICKHOUSE-TRAFFIC.md)**（部署 YAML、`shark-platform` 环境变量与 `kubectl` 命令）。
