# 验证与交付范围

[返回首页](../../README.md) · [实施与评审](REVIEW.md)

## 当前检查点

日期：2026-10-19。线上成品基于 `dap-v3-20261019-rc7`，迁移头 `0017_notification_preferences`。本次 GitHub 发布整理代码、文档、截图和 CI，不改变线上业务 API、模块、数据模型或视觉方案。

| 检查 | 结果与范围 |
| --- | --- |
| 本地完整后端测试 | **103 passed, 2 warnings，228.20 秒**；真实 PostgreSQL，独立测试库 |
| 契约 | OpenAPI 校验、语义检查、生成 DTO 漂移检查通过 |
| 模块边界 | 导入依赖检查通过 |
| 前端 | TypeScript 检查及生产构建通过 |
| 线上 HTTPS | 证书、前端、API、数据库和实例检查通过 |
| 线上业务 | 实际登记/编辑/重新登录后持久化、版本冲突、凭据受控查看、独立复核、CSV 导入、附件下载哈希及人工费用验证 |
| 实际视口 | 桌面与 390×844 窄屏检查；窄屏无横向文档溢出，无浏览器控制台错误 |
| 恢复 | 独立数据库与私有附件恢复、加密数据与密钥配套验证 |
| GitHub CI | 每次业务代码 push / PR 运行；最新状态以 Actions 为准 |

两条本地警告来自 Starlette 测试客户端依赖的弃用提示，不影响本次测试结果；依赖升级时需重新检查兼容性。

## 如何核对

完整测试在 [backend/tests](../../backend/tests)，CI 定义在 [工作流](../../.github/workflows/digital-asset-platform-contract.yml)。CI 使用一次性 PostgreSQL 16，分别创建运行/迁移角色，执行错误目标拒绝、迁移、重复迁移、契约、边界、完整测试及前端构建。

| 重点 | 建议阅读 |
| --- | --- |
| 数据库隔离、迁移与契约 | `test_database_target.py`、`test_schema_contract.py`、`test_openapi_contract.py` |
| 本地身份和会话 | `test_local_identity.py` |
| 资源、目录和范围 | `test_resources.py`、`test_spec04_boundaries.py`、`test_postgres_integration.py` |
| 凭据、费用、同步、治理 | `test_credentials.py`、`test_stage2_security.py`、`test_stage2_flows.py`、`test_stage2_finance_revision.py` |
| 导入、恢复与完整产品部署 | `test_stage3.py`、`test_stage4.py` |

契约声明 127 个操作，实际注册 119 个，8 个历史规划项不计为实现，运行时契约外操作为 0。契约和测试保留差异约束，避免将规划误写为完成功能。

## 发布与运行

公开地址：[https://114.55.146.5:8093/](https://114.55.146.5:8093/)。旧 8094 链接重定向到同一完整应用。普通登录、写入、凭据权限及独立确认规则均有效。线上数据虚构，真实个人平台 Key 未放入该实例。

发布包包括文件清单和 SHA256；API、worker、Nginx 分别运行，数据库仅内部访问。已启用本机备份与 IP 证书续期。[操作与恢复步骤](../../deploy/RUNBOOK.md)

## 如实说明的边界

- 自动测试通过、工程发布和产品负责人业务接受是不同状态；本页记录工程证据，不代签用户验收。
- 公开数据共享并实际持久化；不同访问者的更改可能相互可见，没有每人独立沙箱。
- DeepSeek 真实余额采集曾使用本机私有配置验证；源码及线上示例没有真实 Key。它不支持按 Key 的历史 Token 统计。
- 附件限制不等于恶意软件扫描；单机备份不等于异地灾备，异机备份目标尚未指定。
- 尚未承诺高并发容量、高可用集群或任意规模图谱。地图有 100 节点 / 200 边的查询上限。
- 新开发库的安装步骤由隔离脚本和 CI 支撑；部署到另一台服务器仍需按该服务器权限、网络、证书及备份目标配置。
