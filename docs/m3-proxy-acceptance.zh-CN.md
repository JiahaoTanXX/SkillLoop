# M3 可信事务底座验收（2026-09-25）

**结论：M3 完成门槛通过，可以进入 M4。** 本阶段使用固定脚本扮演受信任 Runtime；不宣称真实模型已连接 Proxy。M4 必须把模型产生的调用通过受信任 Adapter 登记并复跑三 profile 的真实执行链。

## 交付边界

`skillloop/proxy/` 实现批准域、Policy 与 TaskBinding 交集、任务内资源映射、六工具、SQLite 权威事务、artifact 字节和递增版本、receipt/grant、幂等结果、publication/outbox、撤销与取消。`AF_UNIX SOCK_SEQPACKET` 控制与工具 socket 使用 Linux `SO_PEERCRED` 核对 UID；业务身份由已登记的 run/fence/call 绑定，客户端自报角色无效。控制协议使用 API 4 schema 和 JCS digest。工具调用前必须持久登记整个模型响应批次，额度原子预留；每任务 publication 主键限制为一条。

**可信对象入口** `stage_approval`、`stage_task`、`stage_object` 在 M3 由同进程固定验收 harness 调用。M4 后，ToolCall 通过独立 `ingress.sock` 与 Runtime UID 鉴权导入；任务批准和初始资源仍由受信任 harness 设置。生产部署须只让 Proxy 所有者写数据库，分别为 controller/runtime 配置 socket UID/GID，Runtime 不得挂载数据库。M3 本身不把脚本入口当作模型路径证据；真实链见 [M4 验收](m4-runtime-acceptance.zh-CN.md)。

## 实测记录

在本地运行 `python -m unittest discover -s tests/spec_v22 -q`：104 项通过；`python -m unittest discover -s tests/implementation -q`：39 项通过，其中 3 项 Linux 专属测试在 macOS 跳过。分配 DGX 的 Linux 主机运行 `tests.implementation.test_proxy_store` 和 `tests.implementation.test_proxy_linux`：20 项全部通过。DGX 验收日志保留于 `~/skillloop/platform/m3/acceptance.log`，SHA-256 为 `fd0b76fcb58f9239ddca030fbc3da2fbbf94bc89ff4bfe9c940f26b4201230df`。DGX SQLite 3.45.1 上检查 `user_version=1`、`journal_mode=wal`、`synchronous=2`（FULL）。

| 门槛 | 机制验收 |
| --- | --- |
| 无模型合法链 | `orders_total` 的 M2 固定真实输入资源；`read → build/write → validate → prepare → publish`，发布内容摘要等于实际存储字节摘要。另两 profile 的模型链留给 M4。 |
| 授权与调用身份 | 跨任务资源/租户、无 read binding、Policy 扩权、未知参数、旧 fence、未登记调用、同内部 ID 异参拒绝；同一登记批次改 native ID 拒绝，完全重复不再扣额度。 |
| 批次与幂等 | 超额度整批零登记/零扣额；前一调用失败后续 `skipped_after_failure` 仍占已预留额度；新逻辑调用重用同 key 扣新额度而不重复效果。 |
| 凭证与发布 | 相同字节重写使版本 +1，旧 receipt 失效；第二次发布被拒绝；publication、grant 消费与 outbox 同一事务提交。 |
| 故障与竞态 | 在 build 和 publish 事务的 commit 前/后分别杀子进程；恢复分别得到 `proven_not_started`/`committed`，响应丢失后同调用重放无第二效果。独立 SQLite 连接并发竞争 publish/revoke，撤销先提交则无发布，发布先提交则保留已承诺的一条。恢复读取先获取 SQLite 写锁，避免把正在提交的事务误报为未开始。 |
| Linux RPC | 两个 socket 的 UID/方法边界、登记后的真实工具请求、拒绝响应；超大包由内核限额或服务限额拒绝。每角色最多 16 条开放连接，请求限时 10 秒。 |

## 数据库迁移与回滚

迁移脚本为 `skillloop/proxy/migrations/001_initial.sql`，仅在空库中以 `BEGIN IMMEDIATE` 一次提交 schema、`schema_migrations`、`trust_state` 和 `PRAGMA user_version=1`；打开既有库时校验版本与 deployment epoch。每连接启用外键、WAL、FULL 同步。不存在自动降级迁移。

后续版本升级前，先停止 Proxy/Controller/Runtime 并等候在途请求结束；使用 SQLite online backup API 对权威库制作带校验摘要的完整快照，另存对应代码、schema 版本与 deployment epoch。测试恢复时停止所有写入者，在新路径恢复该快照，核对 `PRAGMA integrity_check`、`user_version`、deployment epoch 与关键表计数，随后从该路径启动匹配代码。回滚正式环境时也按此顺序停服并恢复整库快照，不能只删除迁移表或复制仍有写入的 `.db` 文件；快照之后承诺的 publication/outbox 需要先按外部交付状态核对，避免重放外部副作用。M3 没有真实外部发布，`publication` 是库内 mock sink，故本阶段回滚可由整库快照完成。

## M4 接续条件

M3 的平台与事务关口已过。M4 需要将受信任 Runtime 与固定的 Qwen3.8-27B-FP8 推理服务相连，完成三 profile 真正的模型工具循环、全量取证和角色隔离复测。M1 的 CalibrationReport/DeploymentLock 仍保持 `ready=false`，不能因为 M3 通过而提前置为生产就绪。
