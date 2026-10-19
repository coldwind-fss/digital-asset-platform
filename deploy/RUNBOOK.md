# V3 运行与恢复

当前对外只有一个完整产品：HTTPS 8093 → 独立 API 和 worker。沿用原已填充虚构数据的 demo 实例/数据库/文件卷/密钥标识，APP_READ_ONLY=false；这些内部标识不表示功能裁减版。8094旧链接仅重定向到8093。原main库和配置保留为历史，不再运行其API/worker，不删除数据。服务器root只用于安装，现行服务以dap-demo运行。

## 发布

1. 本地按锁文件安装、构建和契约/DTO检查；验证覆盖本次变化后执行 `python scripts/build-release.py --release-id VERSION`。本次前端使用公开VITE_SAMPLE_USERNAME/PASSWORD和可选VITE_SAMPLE_REVIEWER_USERNAME/PASSWORD预填普通登录框；不要把真实owner口令放进VITE变量。构建内带release.json逐文件SHA256，归档有独立SHA256。
2. 上传并校验 tar.gz；解包到 `/opt/digital-asset-platform/releases/VERSION`，核对 release.json 所有文件，不向 current 覆盖解压。版本含未提交源码时明确记录，不能冒充 Git tag。
3. Python 3.11—3.13 + uv。以锁文件在 `/opt/digital-asset-platform/venv` 安装后端，`uv sync --locked --no-dev --no-editable`；前端直接用构建产物，不在服务器临时装另一个版本。
4. 初次安装显式运行 provision-server.py，只创建缺少且没有冲突的 main/demo/rehearsal 目标，不清空旧库。已有目标不得重新生成主密钥。配置位于 `/etc/digital-asset-platform/INSTANCE/`；app.json 为 root:对应服务组 0640，migration.json 为 root 0600，均不进代码包。
5. 用 run_configured.py 的 migration 模式显式迁移。API/worker 从不迁移，不接收迁移连接。迁移前停写、备份并核实实例；不能无条件 downgrade。
6. 用 runtime 模式执行 release_preflight.py --check-database。安装实例化 systemd 单元，分别配置主机、端口、TLS证书与 Nginx 模板；先 nginx -t 再 reload，只修改本项目配置。
7. 指定虚构数据实例APP_READ_ONLY=false后，显式运行 `seed-experience.py --enable-full-product`，只定向升级原示例账号/说明并补复核账号和虚构凭据，不重置业务表。公开demo / Demo-Product-2026!与reviewer / Review-Product-2026!均为已有admin角色；独立复核、凭据显式授权/近期认证、版本/审计仍生效。示例密码有意公开，不用于真实业务。旧只读初始化分支仅兼容历史部署。

## 操作

`systemctl status digital-asset-platform-api@demo digital-asset-platform-jobs@demo`

`journalctl -u digital-asset-platform-api@demo -u digital-asset-platform-jobs@demo --since today`

配置更新后重启对应服务。检查 /api/v1/health/live（进程）与 /ready（DB/实例/schema）；连接页另检查 worker 心跳和积压，ready 不代表供应商或 worker 成功。失败同步保留上次成功值。API监听127.0.0.1，数据库不开放公网。

## 备份与恢复

升级、备份、恢复前先停对应 API/worker，防止数据库和文件卷取自不同时刻。使用 backup-instance.py 建 custom DB + private-files.zip +逐文件哈希/实例/head清单；主密钥/旧读钥及私有配置单独存放受控目录，不进入公开构建。每日本机备份只是单机故障恢复点，不防整机丢失；异机/云存储费用及目标需另行指定。

当前实例手动备份：`/opt/digital-asset-platform/venv/bin/python /opt/digital-asset-platform/current/deploy/backup-instance.py --instance demo --quiesce`。原demo备份timer可同时正确暂停/恢复现行API和worker；不要按名字误恢复到历史main库。原库/实例/角色标记继续精确核对。

恢复到独立 recovery 库验证，先核对名字、角色、实例和空目标，恢复 DB/文件并用对应原版本主密钥验证秘密；缺钥/错钥不可用。生产恢复会改变业务状态，必须先停服务并保留当前状态；不要把源码回退当作数据库回退。

代码兼容当前schema时可把 current 切回已验证前版再重启；不兼容时用匹配的DB/文件/密钥整套恢复。保留旧版本、配置和备份，确认前不删除。具体演练和线上地址见项目第四/第五阶段记录。

## 证书与公开访问

域名暂缓时可使用受信 IP 证书。IP证书短期有效，必须自动续期并在成功后 nginx -t / reload，监控续期失败及剩余有效期。证书私钥由 root 保管，不放应用目录或下载接口。现有其他站点/证书保持原配置。

用户业务接受与工程验证、线上发布分别记录；没有外网有限冒烟及真实证书校验不能标记上线完成。
