# SkillLoop

**SkillLoop 是面向 AI Agent Skill 的安全评估与 CI 原型。**它围绕一份被测 Skill 和受控业务任务，组合静态检查、攻击测试、隔离执行、证据归约、有限修补与回归评估，帮助判断 Skill 是否完成业务目标、是否产生越权副作用，以及结论是否有足够证据支持。

当前规范版本为 **V2.2 / API 4**。仓库同时包含规范与可执行参考检查、Python 原型、DGX Spark 上的模型/扫描实验记录，以及一个用于演示的订单 Web 工作台。它仍在逐阶段实现和验收：**阶段验收或本地 Demo 通过不等于整个系统已达到生产就绪状态**。

## 目录

- [项目要解决什么问题](#项目要解决什么问题)
- [项目能力与边界](#项目能力与边界)
- [当前进度](#当前进度)
- [快速开始](#快速开始)
- [订单 Web Demo](#订单-web-demo)
- [主要工作流](#主要工作流)
- [仓库结构](#仓库结构)
- [开发与 DGX 验收](#开发与-dgx-验收)
- [安全使用说明](#安全使用说明)
- [文档索引](#文档索引)

## 项目要解决什么问题

Agent Skill 通常由自然语言指令、工具使用规则和业务约束组成。仅靠静态扫描或模型自评，无法证明它是否完成了任务，也无法确认它有没有泄露信息、越权读写或触发不允许的业务效果。SkillLoop 的目标是把这些问题变成一条可追溯的评估链：

1. 固定被测源码、任务契约、模型和运行配置的身份。
2. 检查 Skill 内容并生成可验证的测试目标。
3. 在受控任务和工具代理中运行正常与对抗用例。
4. 从权威事件和业务产物判断成功、失败或证据不足。
5. 在严格限制内提出补丁，并对候选版本重新运行回归。
6. 汇总脱敏结果；只有完整且满足门槛的证据才支持资格判定。

系统将**工程正确性、业务可用性和修补价值**作为不同问题评估。扫描告警、模型声称成功或一次偶然通过，都不能单独证明 Skill 安全。

## 项目能力与边界

### 已有实现

- **API 4 协议与证据身份**：严格 JSON 解析、JSON Schema 校验、JCS 规范化摘要及内容寻址身份工具。
- **受控业务家族**：`orders_total`、`refunds_total` 属于表格汇总家族；`markdown_index` 使用独立的 Markdown 索引逻辑。每个 profile 有登记配置、fixture 和业务判定参考。
- **工具代理原型**：SQLite 权威存储、任务与调用身份、限额、幂等与发布状态机；Linux 实现使用 Unix `SOCK_SEQPACKET` 和内核 peer UID 校验。
- **模型 Runtime 与发现流程**：Agent 适配器、网关、扫描结果处理、发现目标与攻击计划原型。
- **有限修补原型**：对精确候选父版本应用受限字节补丁，记录历史和预算，并提供候选回归入口。
- **本地订单 CI/CD 和 Web 工作台**：用于展示订单 profile 的受限端到端流程与脱敏报告。

### 明确不代表的能力

- 规范检查通过只说明列出的参考断言通过；它不证明 Linux 隔离、真实 GPU 模型、扫描器部署、保护评估或 GitHub 集成已经全部通过。
- 仓库中的红队 Skill 是**故意有漏洞的测试材料**，只用于隔离实验，不能作为正常 Skill 安装或运行。
- 当前 V2.2 目标是单机 Linux/aarch64/DGX Spark、固定模型配置及受控工具。它不以执行任意 Skill 代码、开放 shell、连接真实业务写入端或自动合并代码为目标。
- Demo 使用订单 profile 展示流程；它不是三个 profile 的全局验收，也不能单独证明补丁带来了安全提升。

## 当前进度

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| V2.2 / API 4 规范参考检查 | 可在本地运行 | 检查规范、样例、参考函数和文档一致性；报告明确标注未验证的运行时范围。 |
| M0–M5 | 阶段验收通过 | M5 开发矩阵在 DGX 完成 15 个案例、45 次必需运行；4 次初始不完整尝试保留并按计划补齐，实际共 49 次。 |
| M5b 发现诊断 | 阶段验收通过 | 25 个案例、75 次必需运行；11 个已确认失败的 run 保留在证据中。它是独立诊断扩展，不替代生产资格。 |
| M6 有界修补 | 实施中 | 已有精确补丁应用、失败历史、计划/预算账本及候选回归入口；候选尚未冻结。 |
| M7 保护评估 | 暂缓 / 未正式验收 | 私有保护集的正式评估及生产资格未完成。 |
| M8 本地订单 CI/CD | 订单范围验收通过 | 本地触发、去重、配置变更与收据重建有记录；不代表 GitHub 服务或模型评估已验收。 |
| M9 订单 Web Demo | Demo 范围验收通过 | 浏览器与受控活动流程已复核；最终候选活动未证明修补价值。 |
| 全局生产就绪 | **未就绪** | `production_ready` 保持 `false`；M6/M7 及完整目标环境验收仍是门槛。 |

以每个阶段的验收文档和机器可读收据为准。阶段结果绑定精确源码与配置身份，源码或部署变化后不能沿用旧证明。详情见 [M5 验收](docs/m5-development-acceptance.zh-CN.md)、[M5b 记录](docs/m5b-qwen-discovery.zh-CN.md)、[M6 进度](docs/m6-repair-progress.zh-CN.md)和 [订单 Demo 说明](demo/README.md)。

## 快速开始

以下命令均从 **`SkillLoop/` 仓库根目录**运行。规范检查使用 Python 3.12 和独立虚拟环境：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r specs/v2.2/requirements-verify.txt
python scripts/verify_specs_v22.py
```

检查脚本会运行规范参考检查和 `tests/spec_v22/` 中的单元检查，并更新 `specs/v2.2/verification-report.json`。报告中的 `runtime_security_verified`、`dgx_model_verified`、`offline_scanner_deployment_verified` 和 `github_integration_verified` 为 `false`，因为这些检查本身不执行相应的目标环境验收。

如需单独运行规范单元检查：

```bash
python -m unittest discover -s tests/spec_v22 -v
```

`tests/implementation/` 含更多原型和目标平台测试；其中有依赖 Linux socket 行为或 DGX/模型环境的项目。请先阅读对应测试、Milestone 验收说明和依赖，再选择适合当前机器的测试范围。仓库没有声明一条在任意桌面系统上都等价于完整系统验收的总测试命令。

## 订单 Web Demo

### 本机静态预览

```bash
python demo/server.py --port 8765
```

浏览器打开 `http://127.0.0.1:8765/`。不传私有 DGX 配置时，服务只绑定 loopback，用于浏览界面、profile 和公开报告；**本机预览不会运行模型实验或真实修补工作流**。按 `Ctrl+C` 停止。

### DGX 受控工作台

真实工作流依赖 DGX 上的私有 API 配置、费用账本、私有活动目录和访问口令。公网绑定时服务要求显式提供私有目录、配置、账本和权限为 `0600` 的认证文件；不可把密钥或原始运行数据放入仓库或网页。部署入口、活动限制、登录及现有限制详见 [Demo README](demo/README.md) 和 [订单 Demo 设计](docs/orders-demo-design.zh-CN.md)。

Demo 中一次订单活动会执行受限扫描、攻击、修补、候选回归和本地判定；网页展示聚合结果、预算和脱敏 JSON。活动限额、重复请求去重、未知/不完整记录和私有取证均由服务端工作流处理。当前已复核活动没有确认攻击成功，因此**不能据此声称修补有效**。

### 本地订单 CI/CD 收据

如要单独重建本地订单流程收据，请为输出文件使用一个尚不存在的新路径：

```bash
python scripts/local_orders_ci.py --output milestones/M8/my-local-ci-receipt.json
python scripts/local_orders_ci.py \
  --review milestones/M8/my-local-ci-receipt.json \
  --output milestones/M8/my-local-ci-review.json
```

脚本不会覆盖已有收据。该流程验证的是本地订单 CI/CD 逻辑，不调用 GitHub、不运行模型，也不把 M7 或生产资格标记为通过。

## 主要工作流

V2.2 目标流程由以下阶段组成：

1. **导入与批准**：固定 Git commit、Skill 字节、任务契约和运行配置；输入未获批准时不能进入正式评估。
2. **扫描与计划**：生成扫描覆盖报告、finding、攻击计划及显式运行计划。缺少 analyzer 覆盖或计划项目不能悄悄算作安全通过。
3. **开发用例执行**：在受控工具和任务绑定下运行正常与攻击用例，保存原始事件和独立业务判定。
4. **有界修补与回归**：按补丁策略和额度修改候选；保留被淘汰版本，重新执行原用例、变体与正常路径。
5. **保护评估**：冻结候选后由隔离的保护域生成并执行私有用例，避免把保护题目和答案暴露给开发角色。
6. **Gate 与报告**：按权威运行清单归约每个 subject 的结果，区分 `fail`、`needs_contract`、`inconclusive` 和 `pass`，输出脱敏报告。
7. **资格与 CI**：只有提交版本自身、当前配置和完整有效证明满足要求，才可产生对应资格或精确 commit 的检查结果。候选通过不能替原提交版本变绿。

当前仓库有多个阶段的原型和验收结果，完整生产链仍在实施。详细状态语义和组件边界见 [系统设计](docs/system-design-v2.2.zh-CN.md)与 [Milestone 计划](docs/milestones-v2.2.zh-CN.md)。

## 仓库结构

```text
SkillLoop/
├── skillloop/                 # Python 原型：协议、家族、Proxy、Runtime、发现、修补与 CI 判定
├── tests/
│   ├── spec_v22/              # V2.2 规范与参考语义检查
│   └── implementation/        # 实现、集成及平台相关测试
├── specs/
│   ├── v2.1/                  # 历史 API 3 规范，追溯用途
│   └── v2.2/                  # 当前 API 4 schema、profile、fixture 与运行规范
├── scripts/                   # 规范验证、阶段 gate、DGX 实验和本地 CI 命令
├── demo/                      # 订单 Web UI、只读报告与受控工作流
├── deploy/scanner/            # 离线扫描器镜像、桥接程序和部署说明
├── profiles/                  # profile 运行/校准辅助程序
├── operations/                # 阶段操作和实机序列入口
├── docs/                      # 系统设计、开发环境、阶段记录与交接
├── milestones/                # 机器可读进度、收据、Gate 与验收证据索引
├── reviews/                   # 历史审查和复现材料
└── SkillLoop-PRD-v2.2.zh-CN.md # 当前产品与语义规范
```

**不要混用 V2.1 与 V2.2 的结果**：V2.1 使用 API 3，是历史版本；当前规范入口是 V2.2/API 4。规范检查入口为 `scripts/verify_specs_v22.py`。

## 开发与 DGX 验收

推荐工作方式是本机编辑纯逻辑与规范，在目标 DGX Linux/aarch64 环境完成与架构、内核、GPU、模型或隔离相关的验收。每次验收都应绑定精确 Git commit、部署摘要和配置摘要；不要把某个环境的绿色结果移给另一个源码版本。

固定模型目标为官方 `Qwen/Qwen3.8-27B-FP8`，V2.2 部署候选使用 SGLang。仓库中的部署文档规定了需要锁定模型 revision、权重摘要、镜像 digest、tokenizer/template、工具解析器和运行参数；文档中的候选配置不能代替实测。当前生产 `ready` 仍为 `false`。

DGX 接入、提交传输、代码目录与证据隔离的步骤见 [开发环境方案](docs/development-environment-v2.2.zh-CN.md)；模型和扫描器验收清单见 [部署规范](specs/v2.2/deployment.zh-CN.md)及[扫描器文档](deploy/scanner/README.md)。

日常开发循环：

1. 修改实现时同步更新相关 schema、文档、正反例或验收条目。
2. 在本机运行适用的规范/单元检查，检查工作区改动和报告差异。
3. 将精确 commit 交付目标 Linux/DGX 环境；在该环境运行对应阶段验收并保留原始证据。
4. 仅将可公开的脱敏结论、摘要和证据索引写回仓库；原始 trace、模型缓存、私有题库、密钥和本地数据库留在受控目录。

## 安全使用说明

- `specs/v2.2/families/redteam/` 中的 Skill 有意包含安全问题，只应用于隔离红队测试。
- 不要把仓库中的合成 fixture、payload 或示例秘密当成私有保护集。
- 不要向公网开放模型管理端点、Proxy socket、SQLite、私有证据目录或保护题库。
- Demo 的静态预览和公开报告只提供受限展示；不要把它当作任意代码执行器或生产安全服务。
- 原始模型输入/输出、攻击载荷、工具 trace 和私有活动证据不应提交到 Git。提交前检查文件内容和 `git status`。

## 文档索引

| 文档 | 用途 |
| --- | --- |
| [当前 PRD V2.2](SkillLoop-PRD-v2.2.zh-CN.md) | 当前产品范围、术语、判定语义与需求条款 |
| [V2.2 规范入口](specs/v2.2/README.md) | API 4 schema、参考检查、fixture 与规范层级 |
| [系统设计](docs/system-design-v2.2.zh-CN.md) | 模块职责、信任边界、存储、执行链和 Gate |
| [Milestone 计划](docs/milestones-v2.2.zh-CN.md) | 分阶段实施与验收目标 |
| [开发环境方案](docs/development-environment-v2.2.zh-CN.md) | 本机与 DGX 的分工、源码交付和接入步骤 |
| [M0–M2 实施记录](docs/implementation-status-m0-m2.zh-CN.md) | 基础协议与早期阶段的实现入口和复跑方式 |
| [M1 平台报告](docs/dgx-m1-access-report.zh-CN.md) | DGX 接入和模型环境记录 |
| [M3 / M4 / M5 验收](docs/m3-proxy-acceptance.zh-CN.md) · [M4](docs/m4-runtime-acceptance.zh-CN.md) · [M5](docs/m5-development-acceptance.zh-CN.md) | Proxy、Runtime 与开发矩阵阶段证据 |
| [M5b 诊断记录](docs/m5b-qwen-discovery.zh-CN.md) | Qwen 语义发现实验、失败记录与限制 |
| [M6 修补进度](docs/m6-repair-progress.zh-CN.md) | 当前有界修补实施状态 |
| [扫描器部署说明](deploy/scanner/README.md) | 离线扫描镜像、桥接和扫描/攻击入口 |
| [订单 Demo 使用说明](demo/README.md) | Demo 访问、工作流展示、验收结果和运维范围 |
| [模型部署验收规范](specs/v2.2/deployment.zh-CN.md) | Qwen/SGLang 与 DGX 上的部署锁定和验收要求 |
| [V2.1 审查记录](reviews/v2.1-2026-09-23/REVIEW.zh-CN.md) | 历史审查及复现追踪 |
| [V2.1 / V2.0 PRD](SkillLoop-PRD-v2.1.zh-CN.md) · [V2.0](SkillLoop-PRD-v2.0.zh-CN.md) | 历史版本，不作为当前规范 |

---

生产代码和验收状态持续演进；若本页与 V2.2 schema、profile 注册表或机器可读验收记录冲突，以当前版本规范和对应阶段的精确验收证据为准。
