# 固定模型的部署建议与前置验收

用户已确定官方 `Qwen/Qwen3.8-27B-FP8`，并说明尚未选择部署后端。V2.2 推荐 **SGLang 作为首个验收后端**，保留 ModelBackend 接口供后续接 vLLM。本文是要执行的部署规范；当前没有 DGX 连接或运行证据，不能把这里的参数当作实测通过的配置。

## 选择依据

2026-09-24 检查的 [SGLang 官方 Qwen3.8 指南](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B)覆盖官方 FP8 权重、DGX Spark 的 SM121/aarch64 部署及工具调用解析，提供 0.5.19 版本的验证背景。结合 [NVIDIA Spark SGLang 部署说明](https://build.nvidia.com/spark/sglang/instructions)，它是当前固定模型/机器组合下有直接参考路径的首选。该选择不是对 SGLang 和 vLLM 性能高低的结论。

[官方 FP8 模型卡](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)定义的是 blockwise FP8 权重。Ollama 名称中的 Q8_0、MLX MXFP8 和另一个 NVFP4 checkpoint 不自动满足这个要求。若要改权重/量化，先由用户确认；仅改后端仍需形成新配置摘要并重新验收。

## 第一组验证参数

| 配置 | 规范决定 | 尚需实测/锁定的部分 |
| --- | --- | --- |
| 权重 | `Qwen/Qwen3.8-27B-FP8`，不修改模型文件 | 精确 Hugging Face revision 和逐文件摘要 |
| 后端 | SGLang，首个版本候选为 0.5.19 | 实际构建版本、ARM64 OCI manifest digest、CUDA/driver 相容性 |
| API | OpenAI-compatible chat；structured tool_calls | 原生响应、解析错误、usage/finish reason、取消能力 |
| parser | 工具 `qwen3_coder`；推理 `qwen3` | 镜像中对应 parser/template 的准确版本 |
| 输入 | text-only；上下文总量 16,384 tokens | 精确 tokenizer 预检与最大任务用量 |
| 生成 | 每请求最多 2,048 output tokens；thinking 开启 | reasoning 是否计入统一 token/结束原因以及真实多轮完成能力 |
| 采样 | temperature=1.0、top_p=0.95、top_k=20、min_p=0.0、presence_penalty=0.0 | 后端实际接受值、seed 支持；不伪造确定性 |
| 执行 | 一次一个 victim；初次校准无额外 draft model/推测解码 | 预热耗时、加载峰值、吞吐和最大日志 |
| 内存 | 从官方 Spark recipe 校准，目标静态份额不高于 0.80；系统保留余量 | `/proc/meminfo`、宿主/容器峰值和 OOM 行为；KV/SSM 精度单独记录 |
| 角色隔离 | gateway 认证角色/run；无共享正文日志 | 保护角色切换时缓存清理/进程隔离实证 |

16K/2K 是首个支持目标。校准失败时 profile 不可设 ready，必须缩小输入规格并重新走两家族验收，或更改部署配置重新校准；不能仅调整报告里的期望值使测试通过。

## 按顺序执行的验收

1. 在受控安装阶段记录 Spark OS、CPU 架构、GPU、driver、容器运行时和 GPU passthrough 方式。以实机可用的 CDI 或 NVIDIA Container Toolkit 配置验证容器内 GPU 访问，不能从某台机器示例推断所有机器参数一样。
2. 拉取官方模型的准确 revision，记录权重、tokenizer、chat template、config 和 generation config 摘要；检查量化配置为预期 blockwise FP8。模型只读挂载，服务阶段不根据 Skill 下载模型或运行仓库代码。
3. 拉取兼容 ARM64 的 SGLang 构建，解析并记录平台 image digest、包锁和推理依赖；生产启动使用 digest，不使用可漂移的 latest。安装锁未形成时 DeploymentLock 的状态是 pending，不能启动正式评估。
4. 仅向本机受控 gateway 暴露推理，独立限制模型管理面；注册参数、tokenizer/template 与 tool parser。首次配置执行结构化单工具/多工具、非法参数、正常停止和超时金样。
5. 分别运行 orders_total、refunds_total、markdown_index 的最短正常路径和最大支持输入；再加入一次合法恢复的代理拒绝。所有工具调用必须经过已登记 call_id，不从输出文本中随意提取 shell 命令。
6. 加入 notes/reference 投递、最终文本和私有工具参数取证。确认私有原始输出先被 evaluator 观察，再由 reporter 脱敏；确认攻击者不能通过日志、错误响应或共享 prefix cache 读取保护数据。
7. 记录每阶段输入/输出 token、墙钟、峰值内存、日志及 SQLite/扫描报告增长，填入预算 profile。用最大任务和真实采样运行来校准阶段 timeout；这与预算计算器的合成算术测试分别存储。
8. scanner 在同一目标架构离线运行三类 smoke，保存逐 analyzer 原始记录、依赖/规则/情报锁；不能拿源码 commit 当完整环境锁。
9. 校验整份 DeploymentLock、ModelConfig 和 CalibrationRecord 相互绑定，管理员登记可用 profile。模型/镜像/模板/规则变化产生新摘要，旧资格失效并触发重新评估。

运行证据归档到受保护的 `platform/<deployment_epoch>/`；公开只包含摘要、版本、测量值和脱敏结果。仓库没有填写的实际 digest 表示未采集，不是默认通过。预算计划样例中的超时估计也不能转写成测得的吞吐。

## 可替换后端的边界

vLLM 作为后续 ModelBackend 可以使用相同权重，但 parser、template、采样参数和 ARM64 依赖需独立锁定；其工具 parser 名称不得直接照抄 SGLang。后端能力协商涵盖工具调用、精确 token 预检、reasoning 字段、seed、取消、usage 和返回版本。缺必需能力返回 unsupported，不悄悄退回“把模型文本当已执行工具结果”。

本版既不要求额外云模型，也不要求训练基模。攻击生成、诊断、补丁和 victim 可复用同一份权重，通过隔离会话和权限控制各自职责；是否能产生有效攻击及补丁必须由实际样本证明。
