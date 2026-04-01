# Docker Compose 本地编排

在仓库根目录执行 `docker compose`，**`-f` 指向本仓库清单**（勿与 Django 应用内 `deploy/` 批量部署引擎混淆）。

## 文件

| 路径 | 说明 |
|------|------|
| `infra/docker/docker-compose.yml` | 主文件：默认仅 **Shark + SQLite**；`--profile sync` 再起 MySQL / Mongo 副本集 / Redis / RabbitMQ |
| `infra/docker/docker-compose.sync-depends.yml` | 可选：应用 **depends_on** MySQL 健康与 Mongo 初始化完成后再启动（与 `sync` profile 同用） |
| `infra/docker/.env.example` | `COMPOSE_PROFILES=sync` 等示例 |
| `infra/docker/mysql/` | MySQL `my.cnf` 与可选 `init/` SQL |

## 常用命令

```bash
# 仅 Shark（推荐日常开发，省资源）
docker compose -f infra/docker/docker-compose.yml up -d --build

# 联调 MySQL → Mongo 同步
docker compose -f infra/docker/docker-compose.yml --profile sync up -d --build

# 应用等待依赖就绪后再起
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.sync-depends.yml \
  --profile sync up -d --build
```

也可在仓库根目录 `.env` 中设置 `COMPOSE_PROFILES=sync`，省略每次 `--profile sync`。

## 访问与账号

- 默认 Web：**http://localhost:8000**
- 首次启动由 `entrypoint.sh` 创建超级用户（默认 **`admin` / `admin`**），**上线务必修改密码**。

## 与「一键脚本」关系

`./scripts/deploy-local.sh` 封装上述 `docker compose` 调用，可选 `--sync`、`--migrate`。
