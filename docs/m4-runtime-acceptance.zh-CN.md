# M4 真实模型 Runtime 验收（2026-09-25）

**结论：M4 完成门槛通过，可以进入 M5。** 固定 Qwen/Qwen3.8-27B-FP8 与 SGLang 0.5.19 在分配 DGX 上运行；三份 Skill 的正常任务经生产形态的 AgentAdapter、Proxy socket 和真实 SQLite 完成发布。一次额外测试先收到真实 Proxy `denied`，模型随后修正调用并完成发布。所有原始上下文、模型响应和 trace 保留在 DGX 的 `~/skillloop/platform/m4/`，仓库仅保存脱敏计数与摘要。

## 接线与边界

`skillloop/runtime/` 实现薄 AgentAdapter、loopback Model Gateway、固定 tokenizer 预检、整批工具调用登记和私有内容寻址 trace。模型响应的原生 `tool_call_id` 只作关联；Runtime 按 deployment epoch、run/fence、response ID、batch index 和规范化参数生成内部 call ID，经 `ingress.sock` 向 Proxy 导入 ToolCall，随后以 `register_call_batch` 原子预留额度，再逐个执行。Runtime 类不打开 SQLite；Proxy 仍为唯一写入者。`SO_PEERCRED` 限制 ingress/tool socket 给 Runtime UID。固定 harness 的任务批准与初始资源由受信任测试入口设置，尚未是面向 GitHub 用户的部署控制面。

Gateway 使用固定只读模型目录、离线环境变量及本机回环 SGLang 服务。tokenizer 通过模型容器内相同 tokenizer/template 对每轮消息和工具定义计数；SGLang 0.5.19 的该固定模板在前两份 profile 的 12 个模型轮次中比直接 template 计数恒多 66 tokens，因此 Gateway 固定加入 66，并逐次要求返回的 `usage.prompt_tokens` 与预检精确相等。更新后的 `markdown_index` 和拒绝恢复测试共 13 轮全部为零差值；后端/模板行为变化时返回 `tokenizer_mismatch`，不继续宣称完整运行。最终文本另经固定 tokenizer 计数。每轮预留 2,048 输出 tokens，并检查 16,384 上下文、模型返回用量和 180 秒 run 截止。

私有 trace 每项包含 response ID、原生/内部 call ID、batch index、参数摘要、Proxy 决定和完整结果；请求上下文以内容寻址文件保存。Runtime 对 trace 与上下文合计 4 MiB 显式限额，不静默截断。最终文本、终止原因、用量和私有 `EvidenceIndex`/`RunObservation` 一并保存。正常停下却未发布时记 `agent_stopped` 业务失败；provider timeout 记 `infra_timeout` 与不完整，均有独立机制测试。

## DGX 验收

DGX 上 `scripts/dgx_m4_gate.py` 重新计算四条成功链的 trace 与事件摘要、上下文身份、工具登记对应关系、token/轮次/调用上限、准确发布和独立失败尝试，输出 `M4_REAL_RUNTIME_PASS`。脱敏 `~/skillloop/platform/m4/gate.json` 的 SHA-256 为 `feb56f8eb918a0e39798c7d430880c664cb464ed070d7112d809ef8c47b0010e`。最大单请求 prompt 3,592 tokens，最大 completion 324 tokens；这些只是本阶段短正常链的观测值，不能替代 M6 的攻击负载与预算校准。

| 执行 | 模型轮次 / 已登记工具 | 发布及取证 |
| --- | --- | --- |
| `orders_total` 正常 | 6 / 7 | 实际发布字节与 M2 oracle 一致；trace 17,399 B |
| `refunds_total` 正常 | 6 / 7 | 实际发布字节一致；trace 17,912 B |
| `markdown_index` 正常重试 | 6 / 6 | 实际发布字节一致；trace 16,657 B；最终文本 82 tokens |
| `orders_total` 拒绝恢复 | 7 / 8 | 未授权 read 被 Proxy 拒绝一次，随后读取正确资源并发布；trace 20,285 B |

`markdown_index` 的第一次尝试在 prepare 之后发生 provider timeout，未发布，`EvidenceIndex.complete=false`；它保留在独立目录，第二次成功没有覆盖第一次的不完整事实。四条成功链均满足 ≤16 轮、≤12 工具调用、每轮 prompt+2,048≤16,384、证据总量≤4 MiB。超时路径、正常停止缺产物和 trace 达限还分别由本地 Runtime 机制测试覆盖。DGX 的 Linux Runtime/Proxy 机制测试 6 项通过。

隔离正反例保留于 `~/skillloop/platform/m4/isolation/isolation.json`，SHA-256 `d96afbe34f09b8a5d598dfd1ba66411743dc49f9a332b297ec75568ea207142e`：Runtime UID 能到工具 socket；generator UID 和 Runtime 到控制 socket 被拒；模型容器仅挂载只读权重、仅发布 loopback 端口，并以离线变量加载。本地 104 项规范测试与 42 项实现测试通过（其中 3 项 Linux 专属测试在 macOS 跳过）；DGX 合并运行 M3/M4 的 23 项 Linux 机制测试通过。模型容器在验收后仍运行且 `OOMKilled=false`。DGX 此时 `docker stats` 容器内存显示 5.973 GiB/119.6 GiB；统一内存平台上这不是模型总内存峰值，峰值仍参考 M1 采样和 M6 校准。M7 的私有保护会话仍需使用独立服务生命周期复测缓存和日志隔离。

## 接续条件

M5 开始固定基础套件、SkillSpector 全覆盖归约、攻击/正常对照、finding 处置和可信判定。M4 通过不把 [待校准 ModelConfig](m1-model-config.pending.json) 或 DeploymentLock 改为 `ready=true`；M6 仍需用正式计划和最大攻击负载校准接单预算。
