# 部署与运维文档（索引）

Shark Platform 的**环境搭建、编排与生产上线**说明集中在本目录；功能使用手册仍在 `docs/` 根下。

| 文档 | 说明 |
|------|------|
| [docker-compose.md](./docker-compose.md) | 本地 Docker Compose：默认仅应用、可选 `sync` profile（MySQL/Mongo/Redis 等） |
| [kubernetes.md](./kubernetes.md) | 生产 Kubernetes：RBAC、Secret、PVC、Ingress、初始化与维护 |
| [traffic-middleware.md](./traffic-middleware.md) | Traffic 相关中间件：GeoIP PVC、Redis、ingest、ClickHouse（YAML 在 `infra/kubernetes/middleware-system/`） |

**一键本地起服务**（构建镜像并启动 Compose）：

```bash
./scripts/deploy-local.sh
./scripts/deploy-local.sh --sync      # 附带 MySQL / Mongo RS / Redis / RabbitMQ
./scripts/deploy-local.sh --migrate   # 仅对已运行的容器执行 migrate
```

**清单路径**

| 用途 | 路径 |
|------|------|
| Compose 主文件 | `infra/docker/docker-compose.yml` |
| 依赖顺序覆盖 | `infra/docker/docker-compose.sync-depends.yml` |
| Compose 环境示例 | `infra/docker/.env.example` |
| K8s 应用示例 | `infra/kubernetes/shark-platform.yaml` 等 |
| Traffic 中间件 YAML | `infra/kubernetes/middleware-system/*.yaml` |
| ClickHouse DDL | `infra/clickhouse/traffic_minute_rollup.sql` |

根目录 [Dockerfile](../../Dockerfile)、[entrypoint.sh](../../entrypoint.sh)、[nginx.conf](../../nginx.conf) 为镜像与进程入口。健康检查：`GET /api/system/health`（无鉴权）。
