# M1 DGX Spark 平台验收（2026-09-25）

**阶段结论：M1 平台可行性门槛通过，可以进入 M3。生产部署状态仍为 `ready=false`。** 此结论按 [Milestone 定义](milestones-v2.2.zh-CN.md)只覆盖模型、离线 scanner 和初步角色生命周期；M3 的真实 Proxy/SQLite、M4 的生产 Runtime 和 M6 的正式预算校准还未完成。原始模型日志、扫描报告、OCI 归档保留在分配节点的 `~/skillloop/platform/`，公开仓库只存摘要和脱敏结论。

最终 DGX 验收脚本对模型探针成功条件、原始文件摘要、三份 scanner 报告的覆盖与 finding、缺情报失败、角色分离和 OCI 归档摘要逐项断言通过。脱敏关口记录 `m1-gate.json` 的 SHA-256 为 `a4644a592276eeeaf7793a4b6bc8a2fa28ea79b68eae488834330882e8637517`。

## 模型侧复核

固定 `Qwen/Qwen3.8-27B-FP8` 官方 revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`，81/81 模型文件摘要通过；SGLang 0.5.19 ARM64 镜像 digest `sha256:4cba07b0c68725991890c64843403396effb7faa39ac47261166b2299095c513`。原始 [M1 记录](dgx-m1-access-report.zh-CN.md)证明单工具、多工具、解析错误、客户端超时、三 profile 短路径和最大输入、一次模拟工具拒绝恢复、token/时延/内存及日志测量。2026-09-25 重新核对七份关键原始文件 SHA-256，与原记录全部一致。16K 上下文、2K 输出、并发 1 仅为 M1 实测候选上限；正式接单额度还要在 M4/M6 校准。

## 离线扫描侧验收

固定输入在 [scanner 锁](m1-scanner-lock.json)与 [离线情报锁](../deploy/scanner/offline-osv-lock.json)。官方 OSV PyPI/npm 快照和 OSV-Scanner Linux ARM64 二进制由本地传至分配 DGX，接收端逐文件核对字节数与 SHA-256，三项均与锁一致。SkillSpector 固定源码、62 项 hash-pinned 依赖、YARA 规则和轮子摘要仍与 [原打包记录](../deploy/scanner/README.md)一致。容器使用 `--network none`、只读根/Skill/情报挂载、非 root 用户、`--cap-drop ALL` 和独立 tmpfs。

| DGX smoke | 报告 SHA-256 | 结果与逐 analyzer 覆盖 |
| --- | --- | --- |
| 原版 `orders-total/SKILL.md` 单文件 | `d30537d96040b833a7ab1977d2ca9e5386e63d28abf70842eafb62d6bcf2f69d` | 0 finding，`complete`；19 completed、5 not applicable、3 disabled |
| 明确的可疑指令文本 | `6453e0a2519013c5f94c7075554749bfed6534b67a61f5ace2a71a3d5bbe48be` | P1 与 YR4 两个 HIGH finding，`complete`；19/4/4 |
| `requests==2.19.0` 依赖 | `e2827113fdbe45d6fead87dd0829c8f30a241d807a7aaf5785bbe78a267800f3` | SC4 一个 HIGH finding，`complete`，供应链 analyzer `completed`；19/4/4 |
| 移除离线情报挂载 | 失败日志 `d89bcc2aefb15e4f0d5003e163280182861936fb58f573f4367fc241bc7bc63c` | 启动预检退出 78，无正式扫描报告；禁止把缺情报标成 complete |

`disabled` 是本次明确使用 `--no-llm` 关闭的语义 analyzer，不等于已覆盖；M5 的正式 scanner 覆盖归约必须继续保留该状态。完整目录扫描还出现一个 AS3 MEDIUM finding（报告 `aca377f88935995a1eb1f364f1ac0671a27b92e5e24f21cfb872ee311ea038c6`），与单文件正常 smoke 的扫描范围不同，保留到 M5 核实和处置。

## 可分发身份与角色隔离

DGX 上构建的离线 scanner 为 linux/arm64，OCI manifest `sha256:165f1d7ae6e878970136b78bda4fb9b7cc5a52d305734f7d3b6318d6434ffe9c`。Buildx 导出的 OCI archive SHA-256 为 `88af38d185603b3dd2c54e4a4c9ce54fef4ce3dd381bca5e31796f824bb54d0b`；`docker load` 接受该归档，按 manifest digest 在断网容器中返回 SkillSpector v2.11.2。Docker 本地 tagged manifest list digest `sha256:aabb494f62b8c3e554b10eb447c85a81de1b1806c37d70e6b596d1a57eca19b3`，部署锁使用可分发的 OCI manifest digest。

角色策略固定为**独立服务容器生命周期**。在同一固定 SGLang 镜像上，开发容器写入合成缓存标记后销毁；保护容器以独立 tmpfs/缓存路径启动，确认标记不存在，且两角色之间没有遗留测试容器。初步证据 SHA-256 `d319c28d52bea1f6774ada31bbe22500e5fe8323a7269d381cc758bdb55fd2d1`。该检查验证容器和临时缓存边界，尚未验证实际模型服务处理保护内容后的日志/内部缓存；M4/M7 要用生产 Runtime 再做正反例，不能把本次检查延伸为生产隔离结论。

## 锁与下一阶段

[ModelConfig](m1-model-config.pending.json)、[CalibrationReport](m1-calibration.pending.json)和 [DeploymentLock](m1-deployment-lock.pending.json)均按 API 4 schema 与 JCS digest 校验，保持 `ready=false`。CalibrationReport 的 `probe_records` 为空，表示没有把 M1 mock harness 的初步测量冒充为生产预算；M1 原始测量的真实摘要见上述原记录。进入 M3 后，先以固定脚本在真实 SQLite + AF_UNIX Proxy 上完成事务门槛；通过后才进入 M4。
