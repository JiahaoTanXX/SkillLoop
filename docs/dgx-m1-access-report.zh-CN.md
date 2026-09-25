# DGX 接入与 M1 平台记录（2026-09-24）

此文件只记录脱敏、可复核的结果。登录信息、SSH 端点、口令、原始日志和模型权重不进入 Git 仓库。原始运行文件留在 DGX 用户目录的 `~/skillloop/platform/`，后续正式证据服务在 M3/M4 建立。

## 接入检查

| 检查 | 结果 |
| --- | --- |
| 用户分配节点 SSH 登录 | 通过 |
| 系统/Python | Linux aarch64，Python 3.12.3 |
| GPU | NVIDIA GB10；驱动 580.142 |
| GPU 容器透传 | `docker run --rm --gpus all public.ecr.aws/docker/library/ubuntu:24.04 nvidia-smi -L` 成功 |
| 磁盘 | 916 GiB 根分区，检查时剩余超过 700 GiB；满足手册要求的 20% 空闲保留 |
| M0/M2 同版复跑 | GitHub 提交 `a2f3c0119c4a832818887c5a32f07fc35e1bfb75` 的归档 SHA-256 为 `2891dee3e775c12ce6fde887d44834fd50542c362ce4157f3ed769acef1c6161`，本地与 DGX 接收端一致；DGX 上参考检查 104 项、实现检查 17 项通过 |

DGX 到 GitHub 的 HTTPS 拉取曾发生 TLS 中断和连接失败。此次用小于 1 MB 的上述精确提交归档传输并核对摘要后复跑；推送至 GitHub 的同一提交已在本地确认成功。后续部署仍以 Git 提交 SHA 为代码身份。

手册建议模型等大文件从节点内的 ModelScope 等可达国内来源下载，并说明 `/home/xsuper/models/` 只在存在时可只读复用。本次分配节点没有该共享目录；当前用户的既有 `~/models/` 里是 Nemotron checkpoint，未发现可核验的 Qwen3.8-27B-FP8。因此使用 ModelScope 的 Qwen 同名模型镜像在节点内下载，不从本地上传大模型，也不依赖 DGX 直连 Hugging Face。登录信息表没有另列模型路径。

## 固定模型与镜像

模型为 `Qwen/Qwen3.8-27B-FP8`。官方 Hugging Face revision 固定为 `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`。从 ModelScope 的 Qwen 同名镜像下载权重后，使用该官方 revision 的 tree 文件元数据逐文件检查：67 个 LFS 文件按 SHA-256、14 个普通 Git 文件按 blob SHA-1，最终 **81/81 文件大小和摘要匹配**。镜像中最初有三份说明/许可证文件与官方 revision 不同，已替换为分别单独校验通过的官方文件，再重新完成 81 项全量核对。模型 `config.json` 的架构为 `Qwen3_5ForConditionalGeneration`，`tokenizer_config.json` 含 chat template；两文件均在上述摘要核对范围内。

候选 SGLang 镜像为 `lmsysorg/sglang:v0.5.19-cu130` 的 linux/arm64 manifest `sha256:4cba07b0c68725991890c64843403396effb7faa39ac47261166b2299095c513`，已核对它与官方标签的 ARM64 manifest 一致。通过国内可达镜像代理拉取成功；容器内 `sglang.__version__` 返回 `0.5.19`。仅把端口映射到节点的 `127.0.0.1:30000`，模型目录只读挂载，并设置离线加载。下文记录了实际启动和工具调用结果。

SkillSpector 固定源提交 `dabf4759a189be0f0428a2f7a472b3d5bdad1fe6`，源版本 2.11.2；`uv.lock` SHA-256 为 `5de3b0c121a34472026462c9fad368019accbe094ba4693198364c105e5ea93c`，源码内四个 YARA 规则文件的排序摘要清单 SHA-256 为 `f1137fe1cc4b140d6b13abac94c215dd92c1b41ab62dfef102ab62fbdd699699`。锁文件导出的依赖清单通过逐 wheel hash 校验，从镜像安装 62 个依赖，并安装该固定源码提交；CLI 返回 `SkillSpector v2.11.2`。可重算的导出依赖清单 SHA-256 为 `1786cdbe3b2a9bd5de91e5493c5cb17278e14de9b5373cff8b57fdebac0432f0`。

已按 [ARM64 扫描器镜像构建记录](../deploy/scanner/README.md)把同一固定源码打成 `skillspector-2.11.2-py3-none-any.whl`（SHA-256 `4e046af9b21218c650f463d22896e4b5cc3326178a3b13fbc3cb8c4031bac70a`），以 `public.ecr.aws/docker/library/python@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9` 为 ARM64 基础镜像，在 DGX 构建的本地镜像 ID 为 `sha256:905f66cb3253c884385232984a5535367b896fd5192abe0ee10239ec5fa2c093`，大小约 115 MB。镜像内 `skillspector --version` 返回 v2.11.2。镜像 ID 是本地实测的内容身份，正式 DeploymentLock 仍需固定可分发 OCI 身份。

| `--no-llm` smoke | 实际结果 | 逐 analyzer 覆盖 |
| --- | --- | --- |
| 原版 `orders-total` Skill | 退出 0，0 finding，静态扫描标记 complete | 19 completed，5 not_applicable，3 disabled（语义 LLM） |
| 附加项目测试用泄漏诱导文本 | 退出 0，0 finding | 与原版相同；此文本未被静态规则识别，作为检测缺口保留 |
| 附加明确的忽略指令/泄密外发文本 | 退出 0，2 finding（P1、YR4） | 与原版相同；用于确认静态规则可命中明显模式 |
| 带测试依赖、OSV 访问故障 | 退出 0，报告为 **partial**，1 个 SC4 finding | 18 completed，4 not_applicable，4 disabled，1 degraded（`static_patterns_supply_chain`）；不能把 SC4 fallback 当成完整离线情报 |

使用该镜像在 `--network none`、只读根、非 root、`--cap-drop ALL` 和只读 Skill 挂载下重新运行三类 smoke：普通 `orders-total/SKILL.md` 为 0 finding、`complete`，19 completed / 5 not_applicable / 3 disabled；可疑文本为 2 个 HIGH finding、`complete`，19 / 4 / 4；带测试依赖且无 OSV 网络为 1 个 finding、`partial`，18 completed / 4 not_applicable / 4 disabled / 1 degraded。三份容器报告 SHA-256 依次为 `b431f60fad78f806aea2be8b719fda4932f3e377e76bd88aebaa602a0f6384ea`、`a7bbf228b5835376fe0878c8a98cd657d9b2b1891dc2e982b27c05dff050ac45`、`018b1d92b5fa6086c2d3d66d5f80de38eabd88d0e8140ab9e5ba8275d2eca6e6`。原始报告只保留在 DGX。

这些 smoke 只证明固定版本扫描器在该节点能运行，且报告中的 analyzer 降级可被读出。`--no-llm` 显式关闭三个语义分析器；尚无已批准的完整离线漏洞情报快照，因此未宣称全量 scanner coverage。
当前随源码提供的有限 OSV fallback 位于 `osv_client.py`，其 SHA-256 为 `d6c40aa8b9a6c779f55d3022ba1de883482f0b0bd6c12a0d18c62b387a686d84`；供应链静态分析器源码 SHA-256 为 `4e333f86b01a4dc8081adafd1ea6e611d56f74cb8c903c6bbc5341d769c2b5c6`。这两个锁只保证可重现该 fallback，不能替代完整离线情报库。
所固定版本的扫描器说明明确：SC4 的完整查询依赖 `api.osv.dev`，断网时只退回有限静态列表，进程内缓存也不是可移植的离线情报快照。要在本节点获得完整离线覆盖，需要另建受批准、可固定摘要的情报源或给扫描器增加离线查询后端，并重新实测；不能把现有 fallback 记为完整扫描通过。

## SGLang 协议与业务可行性实测

实际使用上述 digest 的容器启动 FP8 模型；`/v1/models` 返回 `Qwen/Qwen3.8-27B-FP8`。只读模型目录、禁用服务期远程模型下载、`--context-length 16384`、`--mem-fraction-static 0.80`、`--max-running-requests 1`、`--chunked-prefill-size 2048`、`--attention-backend flashinfer`、`--reasoning-parser qwen3`、`--tool-call-parser qwen3_coder`、`--disable-radix-cache`。权重 66/66 分片加载，启动期图捕获 42/42 完成；服务已 ready。主机可用内存在启动前约 115 GiB、图捕获时约 12 GiB、ready 后约 16 GiB，仍需以完整业务负载测峰值和 OOM 风险。

| 探针 | 实际结果 |
| --- | --- |
| 单工具 | HTTP 200，1 个结构化 `echo` 调用，参数匹配；73 completion tokens，其中 46 reasoning tokens；9.17 秒 |
| 同轮多工具 | HTTP 200，2 个结构化 `echo` 调用，参数匹配；333 completion tokens，其中 280 reasoning tokens；41.5 秒 |
| 错误 JSON 请求 | HTTP 400，结构化错误响应 |

基础协议探针证明后端的工具调用和错误请求处理。业务可行性使用 [独立 M1 mock 工具探针](../scripts/dgx_m1_probe.py)，它按 PRD §7.1 的 `build_artifact` 语义在构建时写入产物，再完成校验、准备和发布；`write_artifact` 只作为可选的版本 CAS 入口。此探针不代替 M3 的真实 SQLite/Proxy 事务。

| 三 profile 最大输入 | 业务结果 | 累计请求用量 | 总耗时 |
| --- | --- | --- | --- |
| `orders_total` | 7 次工具调用，发布且产物字节正确，0 次拒绝 | prompt 18,185；completion 421；reasoning 97 tokens | 62.51 秒 |
| `refunds_total` | 7 次工具调用，发布且产物字节正确，0 次拒绝 | prompt 18,246；completion 569；reasoning 228 tokens | 81.67 秒 |
| `markdown_index` | 6 次工具调用，发布且产物字节正确，0 次拒绝 | prompt 10,677；completion 526；reasoning 239 tokens | 71.74 秒 |

表中的 token 是多轮请求累计量，不是单次上下文长度。三个最大输入使用 profile 的 20 行表格/记录、100 行文档及 1 KiB notes 边界，且输出经独立业务校验。为补足单次测量，再次运行三种最大输入且三次均发布正确：最高单请求 prompt tokens 分别为 4,414、4,420、2,538；最高单请求 completion tokens 分别为 157、195、168；总耗时分别为 70.80、86.71、61.15 秒。它们低于当前 16K/2K 配置，但这七组业务输入不能覆盖后续所有攻击负载，正式接单预算仍要在 M4/M6 校准。

| 短路径/故障探针 | 实际结果 |
| --- | --- |
| `orders_total` clean A | 发布且字节正确；0 拒绝；73.77 秒 |
| `refunds_total` clean A | 发布且字节正确；0 拒绝；62.52 秒 |
| `markdown_index` clean A | 发布且字节正确；0 拒绝；64.11 秒 |
| `orders_total` clean B，第一次 `build_artifact` 模拟拒绝 | 记录 1 次拒绝后重新构建、发布且字节正确；89.08 秒 |
| 1 ms 客户端请求超时 | 捕获 `TimeoutError`，17.4 ms 内返回超时记录；这是客户端超时路径，不证明服务端即时取消计算 |

短路径探针逐次保存 token 使用和 finish reason。前三份 clean A 的单请求最高 prompt tokens 分别为 1,583、1,572、1,505；单请求最高 completion tokens 分别为 236、164、149。拒绝恢复的单请求峰值是 prompt 1,734、completion 156 tokens。超时探针和 mock 工具链仅用于 M1 可行性，M4 仍须验证生产 Runtime 的证据登记与取消/unknown 语义。

采样参数探针用 `temperature=1`、`top_p=0.95`、`top_k=20`、`min_p=0`、`presence_penalty=0` 和固定 seed 发起两次请求，均返回 HTTP 200 和独立 reasoning 字段；两次完整输出不一致，因此 seed 可用性不能写成确定性保证，`seed_support` 仍保留 `unverified`。

资源探针在业务测试期间每 10 秒记录主机可用内存、容器内存、GPU 利用率和服务日志大小，共 65 个样本；最低 `MemAvailable` 为 17.51 GiB，服务日志在采样窗口增长 45,107 字节。测试结束前容器状态为 running、`OOMKilled=false`，根分区仍剩余 693 GiB 以上，符合手册的 20% 空闲要求。GB10 统一内存下 `nvidia-smi` 的显存已用/总量为 N/A，不能由容器内存统计推断独立显存峰值。测试完成后已停止模型容器并释放资源。

当前未证明同一服务生命周期内切换开发/保护角色时正文、日志和缓存均隔离；因此后续 M4/M7 的保护运行采用**独立容器生命周期**，并对启动、清理及角色绑定做实测，不能把本次 `--disable-radix-cache` 单独当成完整隔离证明。

DGX 私有原始记录保留在 `~/skillloop/platform/`，未提交模型权重、原始日志或登录信息。可复核的文件 SHA-256：`m1-protocol.json` 为 `e182e9887c72862e6c3d7795c682ba88d5336fc5dc2c5524d5881c2a5926e0fd`；`m1-max.json` 为 `4338fff5e8b9a1d57ddec095ce9321c030a658f6abb257891333c46e5c727edb`；`m1-short.json` 为 `e64a2a275d4b41b560230312edc335ef9279571c9bcc5951bf90a94fa636d1bf`；`m1-max-calibration.json` 为 `3b6518df0fb693642f8a6d44526bd5963d97c1a432ca5f729a06974aebe56f72`；`m1-sampling.json` 为 `98d2ea40c730c9b41e889f47809be182656719d6d2df59f4728c1774e585e096`；`m1-timeout.json` 为 `64322aebaa09bccf175cbb7f230120fdfaf1ffa097e6e44ad6477c4494c022ba`；`m1-telemetry.jsonl` 为 `bf3dcdfc505c3c15d28efa6446f798f7fb80a18e90884538715cfaf229af83fd`。

官方 revision 的 66 个权重文件按文件名、字节数和 SHA-256 组成 JCS manifest，其摘要为 `sha256:ccd51f0f8d3e8f34ea33d55020547a7a6d10fa5dc472ed5d09a540483ffce1f5`；四个 tokenizer 文件同样构成 JCS manifest，摘要为 `sha256:a2b7687cb6c2baa433e9057dbc6bf0e7bd37e21752d33d8fc6be0104f212e3b1`。模板 UTF-8 字节 SHA-256 为 `sha256:c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`。manifest 摘要的定义是对有序文件元数据作 RFC 8785 JCS 后再 SHA-256，不是把权重文件串接后的摘要。

[待校准 ModelConfig](m1-model-config.pending.json)是通过 API 4 schema 校验的真实模型身份记录，`ready=false`、`calibration_digest=null`。其中 `top_k=20` 已在两次采样请求中被后端接受，但固定 seed 的完整输出不同；不能把这份 pending 配置登记为可评估部署。完整 DeploymentLock 还缺正式扫描器镜像/情报锁和生产预算校准记录，因此暂不生成虚构的 ready lock。

## M1 结论与剩余门槛

2026-09-25 已完成官方 PyPI/npm 离线情报与 OSV-Scanner 的本地候选适配；固定输入、测试结果及 DGX 待验收项见 [M1 离线扫描器候选记录](m1-offline-scanner-candidate.zh-CN.md)。该候选尚未在 DGX ARM64 容器验收，不能改变下文的非 ready 结论。

同日随后通过登录表中的公网 SSH 映射恢复连接，并完成 [M1 平台验收](m1-platform-acceptance.zh-CN.md)：离线 scanner 的 ARM64 断网 smokes、OCI 导出重载和独立角色生命周期初步检查通过。本文以下段落保留 2026-09-24 当时的待办状态；以新验收文件为当前阶段结论。生产 `ready=false` 不变。

固定模型、SGLang ARM64 镜像和三 profile 的 mock 工具可行性已在 DGX Spark 实测；原生单/多工具、解析拒绝、客户端超时、三份短路径与最大输入、一次模拟工具拒绝恢复均有结果。当前机器可承载并发 1 的这批测试；16K 上下文与 2K 输出保留为待扩大样本校准的初值。

M1 的**模型可行性和 ARM64 扫描器打包可行性已确认，完整部署 readiness 仍未通过**：SkillSpector 尚缺经批准的完整离线 OSV 情报锁及可分发的正式 OCI 身份；同进程角色隔离尚无证明，后续选择独立容器生命周期并验证；生产 Runtime/Proxy 的调用预算、tokenizer 预检、取消、凭证和证据链要在 M3/M4 实测。扫描器的 `partial` 不得变成 complete，ModelConfig 与 DeploymentLock 均保持非 ready。M3 的本地事务实现可按依赖关系开始，但不能据此启动正式评估。
