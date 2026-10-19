# 本地开发与运行

[返回首页](../../README.md) · [服务器运行手册](../../deploy/RUNBOOK.md)

## 前置环境

- Git、Python 3.12、uv、Node.js 24（含 npm）。
- 已启动的 PostgreSQL 16+，以及能在该本地实例创建数据库和角色的管理员账号。
- 本文从新克隆目录开始，命令适用于普通终端；Windows 可使用 PowerShell。服务器部署另按运行手册操作。

```sh
git clone https://github.com/coldwind-fss/digital-asset-platform.git
cd digital-asset-platform
```

## 1. 准备隔离环境和数据库

```sh
cd backend
uv sync --locked --extra dev --python 3.12
uv run python scripts/prepare_workspace.py --admin-user postgres --port 5432
```

将管理员名与端口改为自己的本地实例。管理员认证使用 PostgreSQL/libpq 的正常配置，例如本机 pgpass 或临时 `PGPASSWORD` 环境变量；不要把密码写进源码。准备脚本只处理固定名称的本地开发、测试、恢复数据库，检查已有目标，不清空已有数据。

生成的 `.local/workspace/environment.json` 包含随机数据库口令、加密主密钥和初始化令牌，已被 Git 忽略。迁移使用独立角色，API/worker 只接收运行连接。

```sh
uv run python scripts/workspace_command.py dev python -m alembic upgrade head
```

## 2. 启动 API

在 `backend/` 中：

```sh
uv run python scripts/workspace_command.py dev python -m uvicorn app.main:app --host 127.0.0.1 --port 8305
```

健康检查：[http://127.0.0.1:8305/api/v1/health/live](http://127.0.0.1:8305/api/v1/health/live)。它返回 JSON；应用页面在下一步的前端端口。

## 3. 启动前端

新终端进入 `frontend/`，复制 `.env.example` 为 `.env.local`（PowerShell 使用 `Copy-Item .env.example .env.local`，其他终端可使用 `cp`）。默认代理目标为 `http://127.0.0.1:8305`。

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

打开 **[http://127.0.0.1:5175/](http://127.0.0.1:5175/)**。

首次空库通过界面的初始化流程创建自己的管理员账号。初始化令牌为私有配置 `shared.AUTH_BOOTSTRAP_TOKEN`，在本地编辑器中读取即可。不要将令牌或整个配置贴到 issue 中。

本地新库为空，在线公开示例账号不会自动生成。可使用登记界面创建虚构数据；公开部署的示例数据工具见 `deploy/seed-experience.py`，按其说明显式使用，不要对真实数据环境随意运行。

## 4. 启动后台任务

另一终端进入 `backend/`：

```sh
uv run python scripts/workspace_command.py dev python -m app.worker
```

它负责平台采集等异步任务。未配置真实平台连接时，不会自动产生真实平台余额。验收任务功能时需要 worker。

Windows 安装依赖和完成迁移后，也可从根目录使用 `scripts/start-workspace.ps1 -Target dev -WithWorker`，通过 `scripts/stop-workspace.ps1 -Target dev` 停止这组本地服务。

## 5. 验证

从 `backend/` 执行：

```sh
uv run python scripts/workspace_command.py test python -m alembic upgrade head
uv run python scripts/workspace_command.py test python -m pytest
uv run openapi-spec-validator openapi/v1.openapi.json
uv run python scripts/check_import_boundaries.py
```

测试会清理专用测试数据库的业务表；不要将测试连接改成开发库或实际业务库。不要同时对同一测试库运行多套集成测试。

从 `frontend/` 执行：

```sh
npm run api:contract:check
npm run api:types:check
npm run build
```

## 部署到服务器

先完成本地验证和前端构建，再从根目录执行：

```sh
python scripts/build-release.py --release-id YOUR_UNIQUE_RELEASE_ID
```

输出位于 `.local/releases/`，含版本清单、逐文件哈希和归档校验值。按 [运行手册](../../deploy/RUNBOOK.md) 准备私有配置、显式迁移、Nginx、systemd、HTTPS 及恢复验证；服务器不使用本机开发配置。运行手册保留当前示例服务器的实例名称，部署到自己的服务器时应显式选择目标。

常见问题：端口被占用时先检查现有进程；数据库未迁移时 ready 不通过；更换数据库时检查名称/实例/角色；加密数据恢复需要原主密钥及对应旧读钥。
