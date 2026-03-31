# 基础设施与本地编排

与 Django 应用 **`deploy/`**（批量部署引擎）区分：本目录仅放 **Docker Compose** 与 **Kubernetes 示例清单**。

| 路径 | 说明 |
|------|------|
| [docker/docker-compose.yml](./docker/docker-compose.yml) | 本地全栈。在**仓库根目录**执行：`docker compose -f infra/docker/docker-compose.yml up -d --build` |
| [docker/mysql/](./docker/mysql/) | MySQL `my.cnf` 与可选 `init/` SQL |
| [kubernetes/](./kubernetes/) | 示例 Deployment / Service / ConfigMap+Secret / PVC |

根目录 [Dockerfile](../Dockerfile)、[entrypoint.sh](../entrypoint.sh)、[nginx.conf](../nginx.conf) 为镜像与进程入口。

详细生产步骤见 [docs/K8S_RBAC_GUIDE.md](../docs/K8S_RBAC_GUIDE.md)。

**探针**：`GET /api/system/health`（无鉴权）。
