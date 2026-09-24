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

## 固定模型与镜像

模型为 `Qwen/Qwen3.8-27B-FP8`。官方 Hugging Face revision 固定为 `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`。从 ModelScope 的 Qwen 同名镜像下载权重后，使用该官方 revision 的 tree 文件元数据逐文件检查：67 个 LFS 文件按 SHA-256、14 个普通 Git 文件按 blob SHA-1，最终 **81/81 文件大小和摘要匹配**。镜像中最初有三份说明/许可证文件与官方 revision 不同，已替换为分别单独校验通过的官方文件，再重新完成 81 项全量核对。模型 `config.json` 的架构为 `Qwen3_5ForConditionalGeneration`，`tokenizer_config.json` 含 chat template；两文件均在上述摘要核对范围内。

候选 SGLang 镜像为 `lmsysorg/sglang:v0.5.19-cu130` 的 linux/arm64 manifest `sha256:4cba07b0c68725991890c64843403396effb7faa39ac47261166b2299095c513`，已核对它与官方标签的 ARM64 manifest 一致。通过镜像代理拉取该 digest 的操作仍在进行；成功启动、实际 SGLang 版本和工具调用尚需实测，不能据 manifest 就宣称 M1 完成。

SkillSpector 固定源提交 `dabf4759a189be0f0428a2f7a472b3d5bdad1fe6`，源版本 2.11.2；`uv.lock` SHA-256 为 `5de3b0c121a34472026462c9fad368019accbe094ba4693198364c105e5ea93c`，源码内四个 YARA 规则文件的排序摘要清单 SHA-256 为 `f1137fe1cc4b140d6b13abac94c215dd92c1b41ab62dfef102ab62fbdd699699`。正在按锁安装 ARM64 Python 依赖；普通、可疑、缺离线情报三种扫描及逐 analyzer 覆盖仍待执行。

## M1 尚需完成的实测

在仅绑定 loopback 的 SGLang 上验证原生工具调用、解析错误、拒绝恢复、三份 Skill 的短路径和最大输入，记录 token、时延、峰值内存、日志增长、结构化解析率；并做角色切换隔离检查。扫描器安装后做三类离线 smoke 和 analyzer 覆盖。未得到这些证据前，M1 状态为 **进行中**；16K 上下文、2K 输出和资源预算仍是待校准初值。
