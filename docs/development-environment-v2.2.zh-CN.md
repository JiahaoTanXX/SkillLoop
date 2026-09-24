# SkillLoop V2.2 开发位置与环境方案

状态：已选实施方案，DGX Spark 接入和首轮模型实测已记录于 [M1 平台报告](dgx-m1-access-report.zh-CN.md)。依据 [系统设计](system-design-v2.2.zh-CN.md)、[Milestones](milestones-v2.2.zh-CN.md)、[部署验收规范](../specs/v2.2/deployment.zh-CN.md)。本文件定义在哪里开发、怎样同步以及何时可以进入下一阶段。

## 结论：本地开发，DGX 验证和运行

| 工作 | 主要位置 | 理由与出门条件 |
| --- | --- | --- |
| PRD、API 4 类型、JCS/摘要、纯状态机、计划/预算、Gate、报告、CLI | 本地工作站 | 迭代快，可用固定 fixture 测合同；合并前再在 DGX 的 Linux/aarch64 跑同一提交 |
| 表格与 Markdown 家族 parser、构建器、独立 oracle、金样 | 本地工作站 | 大部分是纯业务逻辑；跨架构金样必须相同 |
| SQLite 真实并发/崩溃、AF_UNIX + `SO_PEERCRED`、OCI 角色隔离 | DGX | 这些依赖目标 Linux 内核、文件系统和容器配置；本地模拟结果不能作为正式验收 |
| 官方 FP8 模型、SGLang、SkillSpector ARM64 离线扫描、token/内存/时延校准 | DGX | 依赖 GPU、aarch64、驱动和实际部署镜像；在 DGX 锁定 digest 后才标记 ready |
| 三 profile 端到端 campaign、私有题库、撤销/恢复、GitHub Checks | DGX 上的受控服务与专用测试仓库 | 必须在最终安全边界和真实运行环境取证；GitHub 负责源代码和检查状态 |

这里的“本地”指日常编辑和纯函数测试；DGX 是生产验收的唯一目标机器。以 Git commit SHA 为共享身份：本地提交并推送，DGX 拉取或接收该 SHA 的校验归档，记录其配置/镜像/模型摘要，然后执行。当前 DGX 到 GitHub 的 HTTPS 访问不稳定，M0/M2 已用小源码归档传输并在两端核对 SHA-256；这只是受限网络下的同提交交付方式，正式报告仍绑定准确 commit，不用浮动 `main` 代替。

## 固定环境选择

| 层 | 方案 |
| --- | --- |
| 代码版本 | GitHub `JiahaoTanXX/SkillLoop` 为源代码中心；每个 milestone 的实现与验收都绑定 commit SHA |
| Python | 本地与 DGX 都先使用 Python 3.12 独立 `.venv`；在依赖锁中记录精确版本。当前仓库的 V2.2 参考检查依赖见 `specs/v2.2/requirements-verify.txt` |
| DGX 系统 | PRD 目标为 DGX Spark 的 Linux/aarch64；先确认远程节点的确切型号、OS、架构、驱动、Docker/NVIDIA Container Toolkit、磁盘和远程访问，再填 DeploymentLock |
| 模型 | 官方 `Qwen/Qwen3.8-27B-FP8`，SGLang 0.5.19；DGX 上已锁定权重 revision、tokenizer/template 和 ARM64 镜像 digest，16K/2K、并发 1 与采样值仍按 M1 结果校准；当前 ModelConfig 保持 `ready=false` |
| 数据库 | 单机 SQLite WAL + FULL；Proxy 独占权威文件，模型调用不占写事务 |
| 进程通信 | Linux `AF_UNIX/SOCK_SEQPACKET` + `SO_PEERCRED`；按注册角色分 socket/UID，模型只有推理接口 |
| 容器 | 低权 worker 使用只读根、无外网、无提权和固定资源限额；模型服务单独使用 GPU profile |
| 访问 | SSH 登录 DGX，通过 SSH tunnel 访问仅绑定受控接口的调试端点；不把模型管理口、Proxy socket、SQLite 或私有题库开放到公网 |
| 证据 | 原始 trace、保护题库和敏感输入保存在 DGX 受控目录及备份中；GitHub 只放脱敏报告、摘要和可公开的规范 fixture |

当前节点不依赖直连 Hugging Face 下载模型：权重从节点可达的 ModelScope 同名镜像获取，再逐文件对官方固定 revision 的大小与摘要核验。SGLang ARM64 镜像通过可达的国内镜像代理按 digest 拉取，Python 依赖从国内镜像下载并校验锁定 wheel hash。镜像源只负责传输，身份以最终摘要、版本和实测结果确定；不可把镜像站同名文件直接当成官方固定版本。

官方资料可作为硬件与模型安装的起点：[DGX Spark 系统与远程访问](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)、[GPU 容器运行时](https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html)、[SGLang on DGX Spark](https://build.nvidia.com/spark/sglang/instructions)、[Qwen 官方 FP8 模型](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)。这些安装示例会更新，实际部署必须锁定版本与摘要；不能直接把示例中的 `latest` 用作正式证明。NVIDIA 文档说明 DGX Spark 可通过 SSH 远程访问，并提供 GPU 容器运行路径；具体机器的可用性仍需实测。

## 一次开发循环

1. 在本地按一个 milestone 建工作分支，修改代码、规范和有意义的合同测试；运行本地快速测试。
2. 提交并推送。DGX 能连 GitHub 时检出精确 SHA；网络中断时在本地生成 `git archive`，校验两端 SHA-256 后送到独立工作目录。部署脚本记录 Python/依赖、容器、模型、扫描器和配置摘要。
3. 在 DGX 跑该 milestone 的 Linux/模型/事务/端到端门槛；原始证据写入受控目录，脱敏结论与索引回填到验收记录。
4. 失败时在本地修复并形成新 commit，DGX 重新检出、重跑。不得把旧 SHA 的绿色结果挪给新 SHA。
5. 通过后合并。后续模型/镜像/模板/规则变化产生新配置身份与重评，不沿用旧证明。

M0、M2 的纯合同实现已完成首轮本地/DGX 复跑；M1 模型与扫描器 spike 在 DGX 进行中。M3 可以接着在本地写事务逻辑，但真实 SQLite/UDS 验收必须在 DGX；M4 起的真实 Agent 路径依赖 M1、M3 完成。日常编辑器保持在本地，Mac 上的模拟隔离结果不充当 Linux 安全验收。

## 代码如何到 DGX

GitHub 仓库是代码传递通道；模型权重、密钥、原始证据和 SQLite 数据库留在 DGX 的独立目录。首次在 DGX 建立代码副本，以下命令只检出源码和运行当前的规范检查，不代表生产服务已存在：

```sh
mkdir -p "$HOME/skillloop"
git clone https://github.com/JiahaoTanXX/SkillLoop.git "$HOME/skillloop/source"
cd "$HOME/skillloop/source"
git fetch origin main
SKILLLOOP_COMMIT="PASTE_FULL_COMMIT_SHA_FROM_LOCAL"
git checkout --detach "$SKILLLOOP_COMMIT"
git rev-parse HEAD
python3.12 -m venv .venv
.venv/bin/python -m pip install -r specs/v2.2/requirements-verify.txt
.venv/bin/python scripts/verify_specs_v22.py
```

`SKILLLOOP_COMMIT` 的值由本地 `git rev-parse HEAD` 得到。私有仓库需要给 DGX 配置只读 deploy key 或其他受控 Git 凭据，不把个人 token 写进脚本。第一次 clone 后，每次本地改动执行 `git commit`、`git push`；DGX 网络可达时在干净代码目录检出新的 `SKILLLOOP_COMMIT`。若 HTTPS 仍中断，则在本地对该提交运行 `git archive --format=tar "$SKILLLOOP_COMMIT"`，计算 SHA-256，以小文件传输到 DGX，接收端重新核对摘要并解包到新目录。记录归档摘要与原提交 SHA；不能把工作树的未提交文件混入归档。DGX 不直接编辑主源码；热修先提交回 GitHub，再部署新的 SHA。

建议把目录分开：`~/skillloop/source` 仅存 Git 代码；`~/skillloop/model-cache` 存只读模型文件；`~/skillloop/data` 存 Proxy 数据库；`~/skillloop/evidence` 存原始取证；`~/skillloop/private` 存保护题库。后四者不在 Git 工作树内，按服务角色限制读写并单独备份。远程服务启动后，调试访问通过 SSH tunnel；不要为方便本地调用而把模型管理口或数据库直接暴露到公网。

生产容器部署要等 M3/M4 实现服务入口、Dockerfile、依赖锁和迁移脚本后进行：DGX 检出准确 SHA，在 DGX 的 ARM64 环境构建镜像并锁定 digest，运行迁移与集成测试，通过后用该 digest 启动/切换受控服务。Mac 上的构建产物不能直接充当 DGX 的生产镜像。每次切换前记录旧版本与回滚点；包含模型、scanner、权限或 Gate 语义变化时重新评估，不能只重启进程沿用绿色结果。

## DGX 接入检查清单

先只做只读探测并记录到 `platform/<deployment_epoch>/` 的私有目录：

```sh
uname -a
uname -m
python3 --version
docker --version
nvidia-smi
df -h
git --version
```

上述接入检查和 GPU 容器 smoke 已通过；实际摘要与剩余限制见 M1 平台报告。不要把 token、私钥或完整环境变量写入日志。当前只是平台可行性测试，尚未启动正式评估。

## 开发开始条件

M0/M2 已有离线实现，固定模型在目标节点已能完成三 profile 的最大输入与短路径 mock 工具调用；完整 M1 readiness 仍取决于预算校准、扫描覆盖和角色隔离证据。可以开始不依赖 M1 的 M3 实现；M3/M4 的真实权限和 Agent 路径通过前不能宣称系统可运行，M7/M8 的保护与 CI 通过前不能发布正式安全绿色检查。具体实施以每个 milestone 的出门条件逐级推进。
