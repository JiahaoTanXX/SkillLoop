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

候选 SGLang 镜像为 `lmsysorg/sglang:v0.5.19-cu130` 的 linux/arm64 manifest `sha256:4cba07b0c68725991890c64843403396effb7faa39ac47261166b2299095c513`，已核对它与官方标签的 ARM64 manifest 一致。通过国内可达镜像代理拉取成功；容器内 `sglang.__version__` 返回 `0.5.19`。仅把端口映射到节点的 `127.0.0.1:30000`，模型目录只读挂载，并设置离线加载。启动与工具调用结果仍需实测。

SkillSpector 固定源提交 `dabf4759a189be0f0428a2f7a472b3d5bdad1fe6`，源版本 2.11.2；`uv.lock` SHA-256 为 `5de3b0c121a34472026462c9fad368019accbe094ba4693198364c105e5ea93c`，源码内四个 YARA 规则文件的排序摘要清单 SHA-256 为 `f1137fe1cc4b140d6b13abac94c215dd92c1b41ab62dfef102ab62fbdd699699`。锁文件导出的依赖清单通过逐 wheel hash 校验，从镜像安装 62 个依赖，并安装该固定源码提交；CLI 返回 `SkillSpector v2.11.2`。可重算的导出依赖清单 SHA-256 为 `1786cdbe3b2a9bd5de91e5493c5cb17278e14de9b5373cff8b57fdebac0432f0`。

| `--no-llm` smoke | 实际结果 | 逐 analyzer 覆盖 |
| --- | --- | --- |
| 原版 `orders-total` Skill | 退出 0，0 finding，静态扫描标记 complete | 19 completed，5 not_applicable，3 disabled（语义 LLM） |
| 附加项目测试用泄漏诱导文本 | 退出 0，0 finding | 与原版相同；此文本未被静态规则识别，作为检测缺口保留 |
| 附加明确的忽略指令/泄密外发文本 | 退出 0，2 finding（P1、YR4） | 与原版相同；用于确认静态规则可命中明显模式 |
| 带测试依赖、OSV 访问故障 | 退出 0，报告为 **partial**，1 个 SC4 finding | 18 completed，4 not_applicable，4 disabled，1 degraded（`static_patterns_supply_chain`）；不能把 SC4 fallback 当成完整离线情报 |

这些 smoke 只证明固定版本扫描器在该节点能运行，且报告中的 analyzer 降级可被读出。`--no-llm` 显式关闭三个语义分析器；尚无已批准的完整离线漏洞情报快照，因此未宣称全量 scanner coverage。

## SGLang 初步协议实测

实际使用上述 digest 的容器启动 FP8 模型；`/v1/models` 返回 `Qwen/Qwen3.8-27B-FP8`。只读模型目录、禁用服务期远程模型下载、`--context-length 16384`、`--mem-fraction-static 0.80`、`--max-running-requests 1`、`--chunked-prefill-size 2048`、`--attention-backend flashinfer`、`--reasoning-parser qwen3`、`--tool-call-parser qwen3_coder`、`--disable-radix-cache`。权重 66/66 分片加载，启动期图捕获 42/42 完成；服务已 ready。主机可用内存在启动前约 115 GiB、图捕获时约 12 GiB、ready 后约 16 GiB，仍需以完整业务负载测峰值和 OOM 风险。

| 探针 | 实际结果 |
| --- | --- |
| 单工具 | HTTP 200，1 个结构化 `echo` 调用，参数匹配；73 completion tokens，其中 46 reasoning tokens；9.17 秒 |
| 同轮多工具 | HTTP 200，2 个结构化 `echo` 调用，参数匹配；333 completion tokens，其中 280 reasoning tokens；41.5 秒 |
| 错误 JSON 请求 | HTTP 400，结构化错误响应 |

这只证明后端的基础工具调用和解析入口。三份 Skill 的业务工具链、最大输入、拒绝恢复、超时、角色隔离和正式预算仍需独立结果。

## M1 尚需完成的实测

在仅绑定 loopback 的 SGLang 上验证原生工具调用、解析错误、拒绝恢复、三份 Skill 的短路径和最大输入，记录 token、时延、峰值内存、日志增长、结构化解析率；并做角色切换隔离检查。若正式评估需要 SC4 的完整离线覆盖，须固定情报快照并重新测试。未得到模型实测和完整适用覆盖证据前，M1 状态为 **进行中**；16K 上下文、2K 输出和资源预算仍是待校准初值。
