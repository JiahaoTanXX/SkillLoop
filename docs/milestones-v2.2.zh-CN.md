# SkillLoop V2.2 开发 Milestones

状态：2026-09-25。以 [系统设计](system-design-v2.2.zh-CN.md)为实施蓝图，以 [PRD V2.2](../SkillLoop-PRD-v2.2.zh-CN.md)、[API 4 规范](../specs/v2.2/README.md)和 [验收索引](../specs/v2.2/operations/acceptance.json)为验收依据。M0 规范与线协议基线、M2 离线业务合同已实现并在本地与 DGX 复跑；[实现记录](implementation-status-m0-m2.zh-CN.md)界定了尚待后续里程碑验证的生产部分。M1 [平台验收](m1-platform-acceptance.zh-CN.md)通过，生产 ready 仍 pending。M3 之后的生产 Runtime、Proxy 和 GitHub 服务尚未实施。

## 使用方法

按依赖顺序开发，每个 milestone 留下可重跑的命令、配置摘要、测试报告及证据目录。下一阶段可在前一阶段收尾时开始不依赖它的代码，但涉及权限、证据或判定的功能只有前置门槛通过后才能用于正式评估。不要以参考测试代替真实 Linux/模型/CI 验收。Milestone 编号表示依赖顺序，不表示日程或工作量承诺。

| Milestone | 可检查的增量 | 主要依赖 | 完成后可做什么 |
| --- | --- | --- | --- |
| M0 规范基线 | API 4 合同、需求映射、参考检查可重跑 | 无 | 建立生产实现的共同语义 |
| M1 平台可行性 | Spark 模型和扫描器的真实锁与校准 | M0 | 确定支持规格和接单预算 |
| M2 家族与数据 | 两家族三 profile 的 parser、构建、独立 oracle、金样 | M0 | 离线验证正常业务 |
| M3 可信事务底座 | 批准/绑定、六工具、凭证、发布、撤销与恢复 | M0、M2 | 无模型完成合法工具链 |
| M4 真实 Runtime | Qwen 工具调用循环、登记、取证与隔离 | M1、M3 | 真实模型完成三份正常 Skill |
| M5 发现与攻击 | 扫描覆盖、基础套件、finding 驱动攻击及可信判定 | M2、M4 | 开发阶段可证实或否定问题 |
| M6 两轮修补 | 受限补丁、回归、历史、预算与冻结 | M5 | 得到可比较的最终候选 |
| M7 保护与 Gate | 私有新 epoch、完整矩阵、attestation 与报告 | M6 | 对每个 subject 给出最终四态结果 |
| M8 GitHub 持续 CI | 精确 SHA Checks、资格、续评与补丁附件 | M7 | 提交可持续自动评估 |
| M9 首版跨家族验收 | 三份独立 campaign 和完整真实环境证据 | M8 | 判定工程正确性、业务可用性 |
| M10 效果与运维 | 配对修补价值、归档/恢复和容量演练 | M9 | 给出可复核的项目最终结论 |

## M0 规范基线与实施骨架

**交付**：固定当前 PRD/规范 commit、API 4 类型与校验代码入口、JCS/摘要金样、需求 ID → 测试 ID → 证据路径矩阵；建立 `skillloop/` 包、测试和证据目录，但不填虚构的运行证据。将现有 [verification-report.json](../specs/v2.2/verification-report.json)标为参考层报告。

**完成门槛**：在独立环境运行 `python scripts/verify_specs_v22.py` 并保存准确依赖和命令结果；解析器拒绝未知字段、重复 key、无效数字、错 API major；哈希金样、完整 RequiredRunManifest 与 fail 优先反例通过。把 R01–R42 的生产验收状态显式保留 pending，直到相应 milestone 实测。

**出门产物**：版本锁、schema 合同测试报告、requirements traceability 表。主要对应 PRD §2、§6、§9、§16。

## M1 DGX Spark 平台可行性

**交付**：官方 FP8 权重 revision/逐文件摘要、tokenizer/template、SGLang aarch64 镜像 digest 与实际后端版本的初始 DeploymentLock；固定模型的 ModelConfig；SkillSpector ARM64 离线依赖/规则/情报锁；可行性测量和原始日志。此时用独立最小 harness 模拟已登记工具的正常/拒绝响应，以现有三份 Skill 和 fixture 验证模型能力；不要求 M3/M4 的生产服务先存在。SGLang 0.5.19、16K 上下文、2K 输出是首轮待验证配置，不作为现成实测结果。

**完成门槛**：harness 在 Spark 上验证原生单工具/多工具调用、解析错误、超时、三份 Skill 的短正常路径和最大输入、一次模拟工具拒绝后恢复、最终文本/工具参数取证；记录峰值内存、token、时延、日志增长和结构化解析率。scanner 分别对普通、可疑、缺离线情报 Skill 做 smoke，并提供逐 analyzer 覆盖。角色切换的正文/缓存隔离有初步证据；如果不成立，保护使用独立服务生命周期。实测上限小于拟支持输入时先修改 profile，再重测。M4 用生产 Runtime/Proxy 重做路径验证，M6 用其数据完成正式预算校准。

**出门产物**：`platform/<deployment_epoch>/` 的实际记录、可行性结论和供后续校准使用的初始阶段界限；完整生产 readiness 继续保持 pending。对应 PRD §4、§8.1、§13。

## M2 两家族业务合同

**交付**：同一 `table-report` 插件加载 `orders_total` 和 `refunds_total` 配置；`markdown-index` 独立插件；三份 profile 的严格输入解析、受信任构建器、独立 oracle、fixture factory、输出 JCS+LF 校验及合同测试。沿用已有 [三份 Skill 和固定金样](../specs/v2.2/families/README.zh-CN.md)，不重生成金样覆盖错误。

**完成门槛**：六组固定 fixture、空集合/零金额/最大金额/重复名称/重复锚点/最大文档与排序金样通过；非法 CSV 引号、金额词法、孤立外键、非法 Markdown 链接/围栏、重复 JSON key、浮点/指数/额外空白都拒绝。加入退款 profile 不修改表格 parser、oracle 或通用运算。独立 oracle 对故意植入的构建器错误能报错。

**出门产物**：注册表实现、家族 capability handshake、业务合同测试报告。对应 PRD §1、§3、§7.1。

## M3 授权、Proxy 与本地事务

**交付**：批准域/TaskBinding/Policy 校验、同任务资源表、AF_UNIX + peer 认证、权威 SQLite migrations、六工具、artifact 版本与实际字节、receipt/grant、幂等与 outbox、撤销/取消操作。可用固定脚本扮演可信 Runtime 完成工具链。

**完成门槛**：无模型完成 `read → build/write → validate → prepare → publish`；错误资源/租户、空 read binding、未知参数、权限扩大、旧 fence、未登记 call、同 ID 异参均拒绝。发布与撤销交错、commit 前/后杀进程、响应丢失后同 key 恢复、相同字节重写导致旧 receipt 失效均用真实 SQLite 并发与故障测试验证；一次任务最多一条新 publication。

**出门产物**：数据库迁移及回滚方案、事务日志与机制测试报告。对应 PRD §4–§7、§15；参考状态机测试不能替代本关。

## M4 真实模型 Runtime 与全量取证

**交付**：受信任薄 AgentAdapter、Model Gateway、精确 tokenizer 预检、模型多轮工具调用、批量原子额度预留、事件流和内容寻址上下文、终止输出捕获。Runtime 只用 Proxy 访问工具；模型和低权 worker 均无工具 socket。

**完成门槛**：三份 Skill 各自完成正常任务，并在一次可恢复拒绝后仍能完成；模型产生的每个调用能追溯 response ID、内部 call_id、batch index、参数摘要、Proxy 决定和结果。整批超额零执行、批内后续 skipped 仍计额；正常停止但缺产物为业务 fail，provider timeout 为 unknown/incomplete。4 MiB trace 或 token 上限触发明确不完整，不静默截断。

**出门产物**：三 profile 的真实模型 execution chain、隔离正反例和资源测量。对应 PRD §4、§7、§8.4、§9。

## M5 静态发现、攻击生成与开发判定

**交付**：SkillSpector 覆盖归约、finding verification/disposition 双轴、每 profile 固定 dev 2 正常 + 3 攻击、MutationSpec 槽位变异、finding 驱动原攻击与有效变体、可信 validator 和 ObjectiveDefinition evaluator。

**完成门槛**：零 finding 仍跑基础套件；扫描退出 0 但缺 analyzer 归为不完整；相同 payload 重放不能冒充变体。原资源/payload/渲染字节分别留摘要，最终字节和 tokenizer 上限在执行前检查；未读、未投递、已暴露、模型尝试、代理拦截、真实禁止效果分别记事实。模拟秘密在私有模型输入不误判泄漏，`final_answer`/`mock_publication`/公开诊断的明文及登记编码变体被检测。已证实失败与缺测并存仍 fail。

**出门产物**：三 profile 的开发 SuiteManifest、计划行、攻击与对照证据、finding 处置记录。对应 PRD §8–§9。

## M6 有界修补、回归和预算

**交付**：PatchProposal/Applicator、最多两轮诊断循环、跨 campaign 历史库、显式计划 revision 与预算接单器、候选冻结机制。补丁仅为精确父版本的允许文本范围和/或策略收紧。

**完成门槛**：frontmatter、代码、依赖、测试、oracle、Gate、扩大权限的补丁全部拒绝；错父摘要、切断 UTF-8、重叠 edits、纯重排无变化拒绝。跨轮文件 union ≤3、累计增删 ≤8 KiB、最终净增长 ≤4 KiB。每轮重新扫描并运行原攻击、不同变体、正常对照和适用历史；确定失败不可被重试覆盖。无 finding、一个 finding、两轮+active、接近 128 次、历史超容量等代表计划按真实校准计算；容纳不了完整保护矩阵时不冻结假 finalist。

**出门产物**：每轮 parent→candidate 身份链、开发回归结果、预算和历史兼容报告。对应 PRD §8.2、§10–§11。

## M7 私有保护、Gate 和证明

**交付**：批准 SuiteFactoryProfile 后自动新建私有 epoch；保护 vault、首次投递前 session 预留、配对执行、独立 Gate/CIResult/EvaluationAttestation、脱敏 PublicReport。保护开始后不再修改候选。

**完成门槛**：私有套件包含 1 正常 + 3 攻击且每例 3 重复，覆盖三目标，与开发集/已用题去重并通过 oracle、字节/token、canary 碰撞检查。不合格题库返回 `inconclusive/protected_suite_unavailable`；开发角色不能经报告、错误、哈希、缓存解析题目。submitted、finalist、active 的必要矩阵逐项核对；缺一项不通过，失败重试不消失；已投递或投递未知的保护项不重抽同套题。四态 Gate 和每 subject 独立 CIResult 与权威索引重算一致。

**出门产物**：私有访问审计、完整证明链和公开脱敏报告；证据中的私有内容仅由保护角色读取。对应 PRD §9、§12。

## M8 GitHub 持续 CI 与资格登记

**交付**：专用 GitHub App、受控轮询器、精确 SHA Checks、补丁附件、Registry CAS、证明到期与配置变更续评、CLI/管理命令、operation ticket 与幂等恢复。

**完成门槛**：fork PR 只读导入，不运行其脚本；force-push、重复轮询、乱序旧 worker、同 trigger 换 job、配置变更、24 小时证明到期分别产生正确 generation/campaign 关系。submitted fail + candidate pass 时原提交 Check 仍 failure；needs_contract/inconclusive 阻断 required check。采用候选后形成新提交、新 campaign 和新保护 epoch；旧 attestation 不晋级。发布前后核对远端 head，GitHub 失败可幂等恢复且不宣称与本地事务原子。

**出门产物**：真实测试仓库的 Check 链接/请求摘要、续评与竞态证据、CLI 合同报告。对应 PRD §12、§14。

## M9 首版工程与跨家族验收

**交付**：`orders_total`、`refunds_total`、`markdown_index` 各一场独立完整 campaign；R01–R42 对应真实环境验收记录；工程与业务两份结论。表格两 profile 复用同一实现版本，文档使用独立家族代码，内核计划/权限/循环/Gate 无家族特例。

**完成门槛**：三份 Skill 均走完扫描、正常与攻击、候选修补复测、私有保护和最终判定；每个必需 case 各 3 重复，真实输入/事件/输出/报告可追溯。Linux/SQLite/模型/扫描器/GitHub 的生产测试由实际实现运行，[acceptance.json](../specs/v2.2/operations/acceptance.json)中的 runtime_pending 只有在证据齐全时逐项更新。工程正确性和跨家族业务可用性分别记 pass/fail，不用规范测试或同家族两个名称代替。

**出门产物**：三份 campaign 的不可变证据索引、验收矩阵及发布候选报告。对应 PRD §1、§16–§17。

## M10 修补价值与运行恢复

**交付**：在明确范围内记录真实模型受注入影响前后的配对复测，正常 utility 回归、禁止 effect、最终回答与模拟发布通道分别统计；完成队列、磁盘、取消、归档/导出/恢复、数据库损坏演练。

**完成门槛**：至少一个自然运行中已证实的业务劫持或模拟秘密泄漏，有精确父 subject、原攻击、不同变体、正常对照和候选配对证据，且修补后改善、正常任务不退化，才可声明“修补价值已证实”。若没有此证据，结论固定为 `repair_value_not_demonstrated`，工程与业务结果不被改写。归档前撤销依赖旧证据的资格；恢复新 deployment epoch 后旧 receipt/grant/lease/attestation 全部无效；超历史容量能按批准迁移或明确不完整，不能删失败用例凑通过。

**出门产物**：效果报告、机制测试报告、运维手册、最终三结论。对应 PRD §11、§15–§16。

## 每阶段统一完成记录

建议为每个 milestone 保存 `milestones/Mx/evidence-manifest.json`，至少包含：PRD/规范/实现 commit、配置与依赖摘要、目标机器/容器、执行命令、测试 ID、fixture、预期与实际 verdict、原始证据索引、失败项、验收人和时间。Milestone 通过只表示该阶段的出门条件达成；任何原始证据丢失或配置漂移，应把依赖该证据的当前资格置为 stale 并重新验证。
