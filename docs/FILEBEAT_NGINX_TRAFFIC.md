# Nginx + Filebeat 实时日志接入 Shark Traffic（操作手册）

本文说明：在 Nginx 侧产出 **一行一条 JSON** 的 access 日志，用 **Filebeat** 采集并**近实时**送到 Shark 的 `POST /api/traffic/ingest`（写入 Redis 缓冲，供 Traffic Dashboard 使用）。

> **与平台关系**：仅需在 Nginx/Filebeat（及可选 Logstash）所在环境操作；**不必在 Shark 界面里做任何「发布」动作**。Shark 侧预先配好环境变量与 Traffic 设置即可。

---

## 1. Shark 侧前置条件（必须）

| 项 | 说明 |
|----|------|
| `TRAFFIC_REDIS_URL` | Shark 可连的 Redis，ingest 会把**原始日志行** `RPUSH` 到指定 list |
| `TRAFFIC_INGEST_TOKEN` | 随机强密钥；ingest 仅校验 `Authorization: Bearer <token>` |
| Traffic 设置 | **采集模式** 选 **远程推送 → Redis**（`access_log_mode=redis`），并配置 `redis_log_key` 或多数据源 `log_sources[].redis_key` |
| 可选 `?source=` | 与后台 `log_sources` 里某条 **id** 一致，例如 `?source=api-gateway` |
| `TRAFFIC_ROLLUP_ENABLED=1` | 若需分钟聚合表，ingest 进程与 Web 建议都开启，并定时 `traffic_rollup_flush` |

ingest 接口路径（相对站点根）：**`/api/traffic/ingest`**（完整示例：`https://<shark-host>/api/traffic/ingest`）。

单次请求体行数上限见环境变量 **`TRAFFIC_INGEST_MAX_BODY_LINES`**（默认约 2 万行）；高 QPS 时请控制 Filebeat/Logstash 的 `bulk_max_size` 与 `worker` 数，避免单包过大或触发 Nginx `client_max_body_size`。

---

## 2. Nginx：JSON access 日志（与平台解析一致）

在 `http` 或 `server` 中定义 **一行一条合法 JSON**（字段名与 `docs/TRAFFIC_DASHBOARD.md` §5 一致；**务必包含 `msec`**，避免仅 `time_local` 在非英文 `LC_TIME` 下解析失败）：

```nginx
log_format access_json escape=json
  '{'
    '"time_local":"$time_local",'
    '"msec":"$msec",'
    '"remote_addr":"$remote_addr",'
    '"request_uri":"$request_uri",'
    '"status":$status,'
    '"request_time":"$request_time",'
    '"http_user_agent":"$http_user_agent"'
  '}';

access_log /var/log/nginx/access.json.log access_json;
```

经 CDN/反代时，请按实际方案把 **真实客户端 IP** 写入 JSON（例如 realip 后仍用 `$remote_addr`，或增加 `x_forwarded_for` 等字段并在边缘规范为单 IP）。

重载 Nginx：

```bash
sudo nginx -t && sudo systemctl reload nginx
```

确认文件可读（Filebeat 运行用户需有读权限）：

```bash
sudo ls -l /var/log/nginx/access.json.log
```

---

## 3. 为何 Filebeat 往往不能「直连」Shark ingest

Shark ingest 要求请求体为：

- **`Content-Type: text/plain`**：正文为 **多行文本**，**每一行 = 一条完整的 Nginx JSON 日志原文**；或  
- **`Content-Type: application/json`**：`{"lines": ["行1", "行2", ...]}`，数组元素同样是**原始字符串**。

而 Filebeat 默认输出到 Elasticsearch/Logstash/Kafka 等时，事件是 **带 `@timestamp`、`host`、`agent` 等外壳的 JSON**，**不是**「一行一条 access JSON」。若把该整段 JSON 推进 Shark，**解析会失败**。

因此推荐两种落地方式：

- **方案 A（推荐）**：Filebeat → **轻量 Logstash** → HTTP POST Shark（正文只拼 `message` 行）。  
- **方案 B**：不用 Filebeat，同机使用仓库脚本 **`scripts/traffic_ingest_push_incremental.sh`**（bash + curl，逻辑与 ingest 一致）。可与运维约定「只选一种」，避免同一文件双路重复推送。

下面给出 **方案 A** 的完整配置示例。

---

## 4. 方案 A：Filebeat + Logstash → Shark HTTP

### 4.1 Filebeat（8.x）

目标：**不要把每行 JSON 拆成多字段**，保留整行在 `message` 里，交给 Logstash 原样 POST。

`/etc/filebeat/filebeat.yml` 示例：

```yaml
filebeat.inputs:
  - type: filestream
    id: nginx-access-shark
    enabled: true
    paths:
      - /var/log/nginx/access.json.log
    # 不要用 ndjson 解析器把字段摊平；整行作为 message 推送
    prospector.scanner.exclude_files: [".gz$"]

processors:
  - add_host_metadata: ~

output.logstash:
  hosts: ["127.0.0.1:5044"]
```

启动并设为开机自启：

```bash
sudo filebeat test config -c /etc/filebeat/filebeat.yml
sudo systemctl enable --now filebeat
sudo journalctl -u filebeat -f
```

### 4.2 Logstash：Beats 入、HTTP 出

`/etc/logstash/conf.d/shark-traffic-ingest.conf` 示例（请替换 URL、Token、可选 `source`）。

Shark 接受 **`text/plain`** 且 **body 中每一行是一条完整 Nginx JSON**。Filebeat 经 Beats 协议传来的原始行在字段 **`message`** 里，因此 Logstash 侧对每个事件 **POST 一行** 即可（实现简单；极高 QPS 时请求数多，可再考虑聚批，见 4.3）。

```ruby
input {
  beats {
    port => 5044
  }
}

filter {
  if ![message] or [message] =~ /^\s*$/ {
    drop { }
  }
}

output {
  http {
    url => "https://YOUR-SHARK-HOST/api/traffic/ingest?source=YOUR_SOURCE_ID"
    http_method => "post"
    format => "message"
    message => "%{message}"
    headers => {
      "Authorization" => "Bearer YOUR_TRAFFIC_INGEST_TOKEN"
      "Content-Type" => "text/plain; charset=utf-8"
    }
  }
}
```

> **插件**：使用 Logstash 自带的 **`http` output**（[官方文档](https://www.elastic.co/guide/en/logstash/current/plugins-outputs-http.html)）。若你发行版中插件名或 `format` 选项不同，以当前版本文档为准；核心原则是 **HTTP 正文 = 原始日志行（含换行则只应一行一条 access JSON）**。

### 4.3 批处理（可选，降低 HTTP 次数）

单条 POST 在 **QPS 很高** 时会对 Shark 与网络产生压力。可选做法：

1. **不经过 Filebeat**：同机使用 **`scripts/traffic_ingest_push_incremental.sh`**，按固定字节/行数切批 POST（与现有 ingest 完全对齐）。  
2. **在 Logstash 中聚批**：使用 **`aggregate` filter**、`ruby` filter 或自定义插件，将窗口内多条 `message` 合并为 JSON **`{"lines":["...","..."]}`** 再 `Content-Type: application/json` POST；实现与 Logstash 版本相关，此处不展开，可由中间件同事按环境编写。  
3. **换用 Vector / Fluent Bit**：配置将多行事件编码为 Shark 接受的 JSON `lines` 数组（若你采用此路线，可单独维护一份配置，本手册以 Filebeat 为主）。

验证 Shark 是否收到：

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "https://YOUR-SHARK-HOST/api/traffic/ingest" \
  -H "Authorization: Bearer YOUR_TRAFFIC_INGEST_TOKEN" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-binary $'{"msec":"1730000000.000","remote_addr":"127.0.0.1","request_uri":"/","status":200,"request_time":"0.001"}\n'
```

应返回 **200** 且 JSON 含 `"accepted": 1`。若 **403** 检查 Token；**503** 检查 Shark 的 `TRAFFIC_REDIS_URL` / `TRAFFIC_INGEST_TOKEN` 是否已设置。

---

## 5. 方案 B：不用 Filebeat — `traffic_ingest_push_incremental.sh`

仓库内脚本从 **同一 JSON 日志文件** 增量读取并 POST 到 ingest，适合「不想维护 Logstash」的场景：

- 环境变量：`SHARK_BASE` 或 `TRAFFIC_INGEST_URL`、`TRAFFIC_INGEST_TOKEN`、`NGINX_ACCESS_JSON_LOG` 等。  
- 详见脚本头部注释：`scripts/traffic_ingest_push_incremental.sh`。

可用 **systemd timer** 或 **cron** 每 10～30 秒执行一次；与 Filebeat **不要对同一文件双写 Shark**，择一即可。

---

## 6. 防火墙与 TLS

- Nginx/Filebeat/Logstash 所在网络需能访问 **Shark Ingress/LB 的 HTTPS**。  
- 生产务必 **TLS**；Token 仅放在 Filebeat/Logstash 配置或 Secret 中，**勿提交 Git**。  
- 若 Shark 前还有 Nginx，注意 **`client_max_body_size`** 大于单批 POST 体积。

---

## 7. 验收

1. 压几条请求，确认 `/var/log/nginx/access.json.log` 持续增长。  
2. 看 Filebeat/Logstash 日志无报错。  
3. Shark：`curl` 抽检 ingest 返回 `accepted` > 0。  
4. Traffic Dashboard：Redis 模式下数秒内应能看到曲线（分钟聚合需 flush 任务）。

---

## 8. 常见问题

| 现象 | 可能原因 |
|------|----------|
| ingest 403 | `Authorization` 头不是 `Bearer <TRAFFIC_INGEST_TOKEN>` 或 Token 不一致 |
| ingest 503 | Shark 未配置 `TRAFFIC_REDIS_URL` 或未设 `TRAFFIC_INGEST_TOKEN` |
| 图表时间全挤在「现在」 | JSON 缺少可解析时间字段，务必带 **`msec`** 或 ISO8601 |
| 有数据但 Geo 全 Unknown | Shark 未挂载 MaxMind `.mmdb` 或 IP 非公网 |
| Filebeat 直连 ingest 失败 | Filebeat 默认事件格式与 Shark 要求的「行原文」不一致，请走 **Logstash** 或 **ingest 脚本** |

更通用的 Traffic 说明见：**[TRAFFIC_DASHBOARD.md](./TRAFFIC_DASHBOARD.md)**。
