# M1 离线扫描器候选与验收状态（2026-09-25）

状态：本记录保留 2026-09-25 验收前的本地候选证据；后续 DGX 实测与 M1 平台结论见 [正式阶段验收](m1-platform-acceptance.zh-CN.md)。

## 固定输入

| 输入 | 来源与固定摘要 |
| --- | --- |
| SkillSpector | v2.11.2，源码提交 `dabf4759a189be0f0428a2f7a472b3d5bdad1fe6`；依赖及规则锁见 [DGX 记录](dgx-m1-access-report.zh-CN.md) |
| OSV-Scanner | 官方 v2.6.0 Linux ARM64 发布二进制；SHA-256 `2c71403eb443d05891c4f268c3ad771cf4f16e5443463fd7851ef8f454d3c7e4` |
| PyPI 情报 | 官方 `PyPI/all.zip`，2026-09-24 快照；34,650,593 字节，SHA-256 `db970c784398bcf053473c9f9a3323f8d5d72b8c9fc0ed2960a26ccc074fcf25` |
| npm 情报 | 官方 `npm/all.zip`，2026-09-24 快照；216,612,852 字节，SHA-256 `7cd52c5e0836e11f2afebc068ba10575c62d8effe7982382b5b39032c91c0cd8` |

来源：[OSV 官方数据集](https://google.github.io/osv.dev/data/)与 [OSV-Scanner v2.6.0 发布页](https://github.com/google/osv-scanner/releases/tag/v2.6.0)。锁文件为 [`offline-osv-lock.json`](../deploy/scanner/offline-osv-lock.json)；两份情报包合计约 240 MiB，不纳入 Git 仓库。ZIP 中包含 withdrawn 记录；版本匹配与撤回处理交由 OSV-Scanner 完成，未自行用静态列表代替情报库。

## 适配与本地验证

[`offline_osv.py`](../deploy/scanner/offline_osv.py)在扫描前核对引擎与两份情报包的字节数和 SHA-256，然后把 SkillSpector SC4 查询转向官方 OSV-Scanner 的 `scan source --offline`。生成的依赖清单和扫描结果在临时目录内；只接受固定版本的 PyPI/npm 坐标。无法解释的坐标、超时、引擎错误、结果缺项和输出超限均进入 SkillSpector 的 limitation/inspection ledger，不能默认为 complete。

在本地 macOS 用同版官方 ARM64 二进制和同一份情报包验证：

| 输入 | 结果 |
| --- | --- |
| `requests==2.19.0` | 10 个 OSV 告警、无 limitation |
| `lodash@4.17.20` | 5 个 OSV 告警、无 limitation |
| 构造的不存在 PyPI 包固定版本 | 0 告警、无 limitation |
| `requests` 未固定版本 | `opaque_content` limitation |
| 无情报库 | 查询失败并记录 `analyzer_runtime_error`；启动预检失败 |
| 带 `requests==2.19.0` 的 `orders-total` Skill | SkillSpector JSON 报告 1 个 HIGH SC4，整体 `complete`，供应链 analyzer `completed` |
| 同一 Skill、模拟缺库并跳过预检来检查降级传递 | JSON 报告整体 `partial`，供应链 analyzer `degraded`，ledger 包含 `analyzer_runtime_error`；此模拟只用于验证报告语义，正式入口不会跳过预检 |

本地验证产物位于临时目录 `/private/tmp/skillloop-osv/`，没有提交模型权重、访问凭证或情报大文件。[构建说明](../deploy/scanner/README.md)列出了 DGX 只读挂载及断网运行方式。

## 待完成的 M1 门槛

1. 分配的 DGX SSH 映射端点在 2026-09-25 重试时 TCP 可连，但 SSH 握手前超时，无法传输快照或运行 ARM64 容器。需节点或 SSH 映射恢复。
2. 在 DGX 上核对传输摘要，构建 `Dockerfile.offline`，于 `--network none`、只读根/输入/情报挂载下复跑普通、可疑、依赖漏洞和缺情报四类 smoke，保存逐 analyzer 状态及原始报告摘要。
3. 导出并重新加载 OCI 归档，记录可分发身份；复核模型与扫描器的独立服务生命周期和角色隔离，再形成真实的 M1 校准及 DeploymentLock。正式生产 Runtime 的预算与证据链仍由 M3/M4/M6 验证。

在以上门槛完成前，M1 维持未通过，ModelConfig 和 DeploymentLock 不得登记为 `ready=true`。
