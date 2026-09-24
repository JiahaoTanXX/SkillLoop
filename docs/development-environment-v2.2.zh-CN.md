# SkillLoop V2.2 开发位置与环境方案

状态：已选实施方案，待验证 DGX 实机信息。依据 [系统设计](system-design-v2.2.zh-CN.md)、[Milestones](milestones-v2.2.zh-CN.md)、[部署验收规范](../specs/v2.2/deployment.zh-CN.md)。本文件定义在哪里开发、怎样同步以及何时可以进入下一阶段；不把尚未连接的远程节点视为已配置完成。

## 结论：本地开发，DGX 验证和运行

| 工作 | 主要位置 | 理由与出门条件 |
| --- | --- | --- |
| PRD、API 4 类型、JCS/摘要、纯状态机、计划/预算、Gate、报告、CLI | 本地工作站 | 迭代快，可用固定 fixture 测合同；合并前再在 DGX 的 Linux/aarch64 跑同一提交 |
| 表格与 Markdown 家族 parser、构建器、独立 oracle、金样 | 本地工作站 | 大部分是纯业务逻辑；跨架构金样必须相同 |
| SQLite 真实并发/崩溃、AF_UNIX + `SO_PEERCRED`、OCI 角色隔离 | DGX | 这些依赖目标 Linux 内核、文件系统和容器配置；本地模拟结果不能作为正式验收 |
| 官方 FP8 模型、SGLang、SkillSpector ARM64 离线扫描、token/内存/时延校准 | DGX | 依赖 GPU、aarch64、驱动和实际部署镜像；在 DGX 锁定 digest 后才标记 ready |
| 三 profile 端到端 campaign、私有题库、撤销/恢复、GitHub Checks | DGX 上的受控服务与专用测试仓库 | 必须在最终安全边界和真实运行环境取证；GitHub 负责源代码和检查状态 |

这里的“本地”指日常编辑和纯函数测试；DGX 是生产验收的唯一目标机器。不要把两份不同步的源目录靠手工拷贝维持一致。以 Git commit SHA 为共享身份：本地提交并推送，DGX 拉取或检出同一 SHA，记录其配置/镜像/模型摘要，然后执行。开发期可用独立测试分支；正式报告绑定准确 commit，不用浮动 `main` 代替。

## 固定环境选择

| 层 | 方案 |
| --- | --- |
| 代码版本 | GitHub `JiahaoTanXX/SkillLoop` 为源代码中心；每个 milestone 的实现与验收都绑定 commit SHA |
| Python | 本地与 DGX 都先使用 Python 3.12 独立 `.venv`；在依赖锁中记录精确版本。当前仓库的 V2.2 参考检查依赖见 `specs/v2.2/requirements-verify.txt` |
| DGX 系统 | Linux/aarch64；先确认实际 OS、驱动、Docker/NVIDIA Container Toolkit、磁盘和远程访问，再填 DeploymentLock |
| 模型 | 官方 `Qwen/Qwen3.8-27B-FP8`，首选 SGLang；0.5.19、16K/2K、并发 1 是 PRD 的首轮候选配置，实测后锁定权重 revision、tokenizer/template、镜像 manifest digest 和采样参数 |
| 数据库 | 单机 SQLite WAL + FULL；Proxy 独占权威文件，模型调用不占写事务 |
| 进程通信 | Linux `AF_UNIX/SOCK_SEQPACKET` + `SO_PEERCRED`；按注册角色分 socket/UID，模型只有推理接口 |
| 容器 | 低权 worker 使用只读根、无外网、无提权和固定资源限额；模型服务单独使用 GPU profile |
| 访问 | SSH 登录 DGX，通过 SSH tunnel 访问仅绑定受控接口的调试端点；不把模型管理口、Proxy socket、SQLite 或私有题库开放到公网 |
| 证据 | 原始 trace、保护题库和敏感输入保存在 DGX 受控目录及备份中；GitHub 只放脱敏报告、摘要和可公开的规范 fixture |

官方资料可作为硬件与模型安装的起点：[DGX Spark 系统与远程访问](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)、[GPU 容器运行时](https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html)、[SGLang on DGX Spark](https://build.nvidia.com/spark/sglang/instructions)、[Qwen 官方 FP8 模型](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)。这些安装示例会更新，实际部署必须锁定版本与摘要；不能直接把示例中的 `latest` 用作正式证明。NVIDIA 文档说明 DGX Spark 可通过 SSH 远程访问，并提供 GPU 容器运行路径；具体机器的可用性仍需实测。

## 一次开发循环

1. 在本地按一个 milestone 建工作分支，修改代码、规范和有意义的合同测试；运行本地快速测试。
2. 提交并推送。DGX 在独立工作目录检出该精确 SHA；部署脚本记录 Python/依赖、容器、模型、扫描器和配置摘要。
3. 在 DGX 跑该 milestone 的 Linux/模型/事务/端到端门槛；原始证据写入受控目录，脱敏结论与索引回填到验收记录。
4. 失败时在本地修复并形成新 commit，DGX 重新检出、重跑。不得把旧 SHA 的绿色结果挪给新 SHA。
5. 通过后合并。后续模型/镜像/模板/规则变化产生新配置身份与重评，不沿用旧证明。

M0、M2 的纯合同实现现在就能开始；M1 的模型与扫描器 spike 可在获得 DGX SSH 权限后并行进行。M3 可以先写纯事务逻辑，但真 SQLite/UDS 验收必须在 DGX；M4 起的真实 Agent 路径依赖 M1、M3 完成。首版不需要把日常编辑器全部迁到 DGX，也不应把 Mac 上的模拟隔离结果当作 Linux 安全验收。

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

再使用已批准的 GPU 容器方式检查 `nvidia-smi` 能否在容器内运行，确定 Docker 权限、磁盘预留、模型缓存路径与 SSH tunnel。不要把 token、私钥或完整环境变量写入日志。此时还不启动正式评估，也不填写未取得的镜像/model digest。DGX 节点地址、登录身份和权限未提供前，这份清单只能作为待执行操作。

## 开发开始条件

架构和 milestones 足以启动 M0 的实现；DGX 不在线时也能做本地纯合同工作。M1 完成前不能承诺固定模型在目标机器上可用；M3/M4 的真实权限和 Agent 路径通过前不能宣称系统可运行；M7/M8 的保护与 CI 通过前不能发布正式安全绿色检查。具体实施以每个 milestone 的出门条件逐级推进。
