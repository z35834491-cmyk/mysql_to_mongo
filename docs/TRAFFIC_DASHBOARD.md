# Traffic Dashboard 配置与运维手册

本文说明 **Shark Platform · Traffic Dashboard**（原 Dashboard 已替换为流量大盘）所需的后端、Nginx 日志、GeoIP、Prometheus Blackbox 与前端依赖配置。

---

## 1. 功能概览

- 从 **Nginx access 日志**（尾部读取、可配置字节数）解析请求，聚合 QPS、延迟分位、状态码、Top 路径/IP。
- 可选 **MaxMind GeoIP2**（`geoip2` Python 库 + `.mmdb`）解析 `remote_addr` → 国家/省份，驱动地图与排行。
- 通过 **Prometheus HTTP API** 查询 **Blackbox Exporter**（如 `probe_success`、`probe_duration_seconds`）展示可用性。
- **Jaeger**：第二 Tab 为占位 + 模拟 Trace 列表；后续对接 Jaeger Query API 即可替换。
- 前端：**Vue 3 + ECharts 6 + echarts-gl**（3D 地球）、世界地图 JSON 自 jsDelivr 加载（需浏览器出网或使用自建 CDN）。

---

## 2. 部署必做步骤

### 2.1 数据库迁移

```bash
cd /path/to/mysql_to_mongo
pip install -r requirements.txt   # 含 geoip2
python manage.py migrate traffic
```

### 2.2 前端依赖（echarts-gl 与 echarts 6 需放宽 peer）

```bash
cd frontend
npm install
# 若未安装 echarts-gl：
npm install echarts-gl@2.0.9 --save --legacy-peer-deps
npm run build
```

### 2.3 Django `INSTALLED_APPS`

已加入 `traffic`；URL 已挂载：`/api/traffic/*`。

---

## 3. 环境变量（推荐生产使用）

| 变量 | 说明 |
|------|------|
| `TRAFFIC_NGINX_ACCESS_LOG` | Nginx access 日志**绝对路径**。未在后台配置路径时作为默认值。 |
| `TRAFFIC_GEOIP_DB` | GeoLite2-City.mmdb 或 GeoIP2-City.mmdb **绝对路径**。与后台「GeoIP mmdb」二选一，后台优先。 |

示例（Docker / systemd）：

```bash
export TRAFFIC_NGINX_ACCESS_LOG=/var/log/nginx/access.json.log
export TRAFFIC_GEOIP_DB=/usr/share/GeoIP/GeoLite2-City.mmdb
```

---

## 4. 后台配置（三种方式任选/组合）

### 4.1 Django Admin

1. 进入 `/admin/`，打开 **Traffic Dashboard Config**（单例）。
2. 填写：
   - **Access log path**：与 `TRAFFIC_NGINX_ACCESS_LOG` 相同含义。
   - **Log format**：`json`（推荐）或 `combined`。
   - **Max tail bytes**：每次 API 请求从文件**末尾**读取的最大字节数（默认 5MB）。
   - **GeoIP db path**：MaxMind 城市库路径。
   - **Use inspection prometheus**：勾选后 Blackbox 查询使用 **系统巡检**里的 Prometheus URL。
   - **Prometheus url override**：仅用于 Blackbox，非空时覆盖巡检地址。
   - **Blackbox promql**：瞬时向量查询，默认空则使用 `probe_success`。

### 4.2 页面内「设置」按钮

登录后打开 **Traffic Dashboard** → 右上角齿轮 → 与 Admin 相同的字段，调用 `GET/POST /api/traffic/config`（需登录会话）。

### 4.3 仅环境变量

不配置 DB 路径时，至少设置 `TRAFFIC_NGINX_ACCESS_LOG`；GeoIP 可只设 `TRAFFIC_GEOIP_DB`。

---

## 5. Nginx 日志格式（强烈推荐 JSON）

在 `http` 或 `server` 中定义：

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

说明：

- **`request_time`**：Nginx 秒数（浮点），后端会转为毫秒参与 P50/P95/P99。
- **`msec` / `time_local` / `@timestamp`**：任一可用于时间轴；优先 `msec` 或数字 `time`。
- **真实客户端 IP**：若经 CDN/反代，请使用 `$http_x_forwarded_for` 或 realip 模块，保证 JSON 里 `remote_addr` 为客户端 IP（或增加 `real_ip_header` 后仍用 `$remote_addr`）。

**combined 模式**：后端使用简化正则解析，**无 `request_time` 时延迟为 0**，仅建议过渡使用。

---

## 6. Prometheus Blackbox Exporter

1. 在 Prometheus 中抓取 Blackbox 指标（`probe_success`、`probe_duration_seconds` 等）。
2. 在 **系统巡检**（Inspection）配置中填写 **Prometheus URL**（例如 `http://prometheus:9090`），并勾选 Traffic 配置中的 **使用巡检 Prometheus**。
3. 若 Blackbox 使用非默认标签，可在 Traffic 配置中设置 **Blackbox promql**，例如：

   ```promql
   probe_success{job="blackbox"}
   ```

4. 可用性 KPI：对当前查询结果中 `probe_success==1` 的比例；无目标时前端显示 `—`。

---

## 7. GeoIP2（MaxMind）

1. 注册 MaxMind 账号，下载 **GeoLite2-City**（或付费 GeoIP2-City）`.mmdb`。
2. 将文件放到服务器固定路径，在 Admin / 环境变量 / 页面设置中指向该路径。
3. 安装 Python 包（已在 `requirements.txt`）：

   ```bash
   pip install geoip2==4.8.0
   ```

未配置 mmdb 时：国家显示为 `Unknown`（`??`），仍可用内置大致经纬度画气泡；内网 IP 归为 `LAN`。

---

## 8. REST API 一览（均需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/traffic/overview?range=24h` | KPI + spark 序列 + Blackbox 摘要 |
| GET | `/api/traffic/timeseries?range=24h` | QPS、请求量、延迟、状态码堆叠 |
| GET | `/api/traffic/geo?range=24h&granularity=country` | 国家聚合；`granularity=province&country=CN` 中国省份 |
| GET | `/api/traffic/top?range=24h&type=paths&limit=10` | `paths` / `slow` / `status` / `ip` |
| GET | `/api/traffic/blackbox` | 仅 Blackbox 探测列表 |
| GET | `/api/traffic/jaeger/traces` | **模拟数据**，后续替换 |
| GET/POST | `/api/traffic/config` | 读/写 TrafficDashboardConfig |

`range` 取值：`1h` | `6h` | `24h` | `7d` | `30d`。

---

## 9. 权限与菜单

- 路由仍为 `/dashboard`，权限仍为 **`view_dashboard`**。
- 侧栏名称：**Traffic Dashboard**，图标 **DataLine**。

---

## 10. 性能与限制（当前实现）

- 每次请求**重新读取日志尾部**，适合单机中小流量；超高 QPS 建议后续接入 Vector/ClickHouse 等，由 API 读库而非直读文件。
- 世界地图依赖外网 CDN；内网环境请将 `world.json` 放到可访问的静态地址并改前端 `fetch` URL（见 `frontend/src/views/Dashboard/Index.vue` 中 `cdn.jsdelivr.net`）。
- 3D 地球贴图来自 `echarts.apache.org`；离线可换本地 URL。

---

## 11. 故障排查

| 现象 | 处理 |
|------|------|
| 顶部黄条提示未配置日志 | 设置 `TRAFFIC_NGINX_ACCESS_LOG` 或在 UI/Admin 填写路径；确保 Django 进程用户有读权限。 |
| 图表全空 | 确认日志时间字段在选定 `range` 内；调大 **max_tail_bytes**；检查系统时区与日志时间。 |
| Geo 全为 Unknown | 检查 mmdb 路径、`pip install geoip2`、IP 是否为公网。 |
| Blackbox 无数据 | 检查 Prometheus URL、网络连通、`probe_success` 是否有数据；自定义 **Blackbox promql**。 |
| 3D 地球不显示 | 浏览器控制台是否加载 `echarts-gl`；贴图 URL 是否被防火墙拦截。 |

---

## 12. 后续扩展（Jaeger）

- 实现 Jaeger Query HTTP 客户端后，新增视图函数替换 `traffic_jaeger_traces_mock`，保持响应字段：`trace_id`、`root_service`、`span_count`、`duration_ms`、`started_at`、`status`。
- 服务拓扑 Tab 左侧替换为依赖图组件数据源即可。
