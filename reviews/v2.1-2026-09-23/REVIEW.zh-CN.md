**SkillLoop PRD V2.1 工程就绪审查**

审查日期：2026-09-23。审查基线：`c8b61e4bba418c4fb03780df1911ba236878384a`；已核实 GitHub main 与本地 HEAD 一致。范围包含 PRD 全文、`specs/v2.1/`、参考校验脚本和固定版本扫描器的部分上游源码。审查没有修改 PRD、规范附件或参考实现，没有提交 GitHub 评论。

**结论：暂不建议将本版作为“无需再做协议决策即可直接实施”的冻结基线。** 产品边界和安全方向已较明确，但可信判分仍有可复现的不一致，保护测试与续评存在生命周期冲突，模块交接和开发验收还缺少必需定义。可以开始确定性原型和平台可行性验证；在下列 P1 项关闭前，不宜全面铺开完整闭环，更不宜把附件自检通过视为规范已经收口。

这里的“问题”分为三种：**实证不一致**指已有参考代码/附件可复现；**规范缺口**指两种不同实现都能声称遵守正文；**待验证风险**指可行性尚无实际证据。后两种不代表已经发生漏洞。本报告的 P1 表示冻结相关工程接口前必须处理，P2 表示相关功能验收前必须处理；不是对尚不存在的生产系统做漏洞定级。

正文用 R01–R42 记录问题，每项给出触发方式、影响和关闭条件。建议的具体改法是审查意见，不代表产品已经作出决策。

**已执行的检查与证据**

原脚本执行成功：22 类实体、49 条合法记录、19 条非法记录、563 项字段检查、17 组 Gate 场景均通过。随后新增 15 个反例探针；其中 14 个 JSON 对象均被 schema 和现有跨字段检查接受，另一个 CSV 反例被参考业务函数接受。它们展示的是不同层面的校验缺口，不是 15 个独立的生产漏洞。

| 探针 | 实际结果 | 对应问题 |
| --- | --- | --- |
| P01 | `delivery_failed` 仍归约为 complete、safe_robust_utility=true | R01 |
| P02 | `policy_decisions=[unknown]` 仍归约为 complete、safe_robust_utility=true | R01 |
| P03 | effect_success=true 与 safety_pass=true 同时出现 | R02 |
| P04 | `complete=false, utility_pass=false` 只得 inconclusive；无法表达独立已证实业务失败 | R03 |
| P05 | scanner 自报 complete、exit=2、无原始报告、无完成 analyzer，仍通过结构及语义检查 | R30 |
| P06 | 2 个 subject × 9 例仅预留 1 个 rollout、1ms，仍通过检查 | R06 |
| P07 | CIResult 内嵌 pass GateResult 有 incomplete_items，外层检查不报错 | R04 |
| P08 | submitted pass、required=9、completed=0，仍通过检查 | R04 |
| P09 | read_resource allow 元组没有任何资源绑定，仍被接受 | R13 |
| P10 | 同一个 allow 集合仅逆序，双向子集成立但 policy_digest 变化 | R14 |
| P11 | attack case 无 payload、无 objective、无 clean pair，仍被接受 | R18 |
| P12 | 同一 TaskInstance 中同名 resource_id 对应不同 bytes_digest，仍被接受 | R33 |
| P13 | 未加引号字段中的双引号 `Al"ice` 被 CSV 参考函数接受 | R31 |
| P14 | utility_success=null、agent_outcome=indeterminate，被归约为 complete=true、utility_pass=false | R03 |
| P15 | policy_only 候选声明修改 `tools/executor.py`，仍通过现有检查 | R22 |

复现代码：[reproduce.py](reproduce.py)；原始结果：[reproduction-results.json](reproduction-results.json)。安装仓库固定验证依赖后执行 `python reviews/v2.1-2026-09-23/reproduce.py` 即可。本次执行环境为本地 macOS/Python 3.13 临时虚拟环境；未运行 DGX、OCI 隔离、真实模型或扫描器集成验收。

**判分与协议一致性**

**R01 · P1 · 实证不一致：不完整攻击/未知策略可以被归约成安全成功。** 依据：[PRD L259](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L259)、[PRD L271](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L271)；[校验器 L191](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L191)。正文要求 delivery_failed、context_exceeded、unknown policy 导致不完整；`reduce_case()` 只按 infra_status 与 evidence_complete 判断 complete，不检查 exposure_status 或 policy_decisions。P01/P02 均返回安全成功。不能假定上游“自然会把另一个字段改对”，因为 RunResult schema 和语义检查接受这种组合。

**关闭条件：** 明确每种状态的合法组合和归约真值表；unknown/投递失败必须传播为 incomplete，加入端到端 RunResult→CaseResult→Gate 反例。

**R02 · P1 · 实证不一致：安全结论有两套可矛盾的事实来源。** 依据：[PRD L273](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L273)、[PRD L305](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L305)；[校验器 L200](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L200)。`objective_results` 的 effect success 与 `any_security_violation` 独立填写；P03 能同时返回 effect_success=true 和 safety_pass=true。当前没有 objective 注册对象证明哪些 effect 是“已批准禁止行为”，也没有从事件统一派生 violation 的规则。

**关闭条件：** 定义目标注册表、事件谓词、目标版本及 prohibited 标志；可信 evaluator 从同一事件事实计算二者，拒绝矛盾结果。不要把任意名为 effect 的非安全目标一律当违规，分类本身也要固定。

**R03 · P1 · 实证不一致：业务失败与未知结果相互混淆，破坏 fail 优先级。** 依据：[PRD L275](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L275)、[PRD L311](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L311)；[校验器 L149](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L149)、[校验器 L204](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L204)。P14 中未知 utility 被压成 false，可能形成假 fail；另一方面，P04 中已知业务失败伴随其他证据不完整，只得到 inconclusive。`definite_failures` 枚举还没有独立 utility_failure，Gate 无法区分“确知失败”与“因缺重复暂未通过”。

**关闭条件：** 分离 `utility_status=pass|fail|unknown` 与 coverage_complete；保留独立证实失败，不用缺数据生成失败。明确 Agent 预算耗尽、无产物、基础设施超时分别属于哪类。

**R04 · P1 · 实证不一致：CI 报告的嵌套语义和证据计数没有闭合。** 依据：[PRD L318](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L318)、[PRD L320](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L320)；[校验器 L114](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L114)。P07 中嵌套 GateResult 单独检查会报 pass_with_missing，包进 CIResult 后反而通过；P08 允许零完成用例的 pass 报告。现有检查也没有把 coverage 与实际 `(subject,case)` 索引、Gate digest 和所有 decision 的配置绑定验证起来。

**关闭条件：** 递归校验嵌套实体，并通过可信索引重算计数；分别校验 submitted/candidate，而不是要求失败 submitted 的缺测阻断已完整的 candidate。报告生成必须由 Gate 结果构造，不能接受调用方自报 verdict。

**R05 · P1 · 规范缺口：最低“数量矩阵”不能证明跑了指定基础套件。** 依据：[PRD L249](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L249)、[PRD L305](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L305)；[校验器 L139](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L139)。Gate 只统计 dev/protected 的 clean/attack 数量；没有验证这些 token 对应三种指定 objective、固定 fixture、必要重复、历史用例以及最新冻结计划。传入任意九个分类正确的 token 仍能满足数量规则。正文说 ingestion 可信，但缺少 ingestion 必须执行的完整校验合同。

**关闭条件：** 建立 suite/plan 权威 manifest，Gate 从其读取 required 集合，按 case digest、objective、split、重复数核对结果；数量检查仅作为附加检查。明确谁负责校验 policy/obligation/compiler 和批准有效性，产出何种不可伪造的证据。

**R06 · P1 · 实证与规范缺口：ExecutionPlan 无法唯一描述多候选的实际执行矩阵。** 依据：[PRD L285](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L285)、[PRD L293](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L293)、[PRD L320](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L320)；[ExecutionPlan schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L2042)。现在只有 subject_digests 与 required_cases 两个列表。它们是否笛卡尔积？第一轮被淘汰候选是否也需全部保护测试？新增第二候选是否意味着旧候选新增全部测试？active 是否算 subject？这些会改变覆盖和预算。P06 还证明预留数未由计划计算。

**关闭条件：** 明确逐 `(subject,case,repetition,phase)` 计划项、角色和终止原因，区分 required/abandoned/not_applicable；预留数与时间由同一计划计算，并检查 revision 追加与冻结规则。

**保护测试、证据与发布生命周期**

**R07 · P1 · 规范冲突风险：保护查询限制与正常续评路径没有协调。** 依据：[PRD L143](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L143)、[PRD L289](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L289)、[PRD L301](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L301)、[PRD L348](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L348)。同 subject/head 每 epoch 一次、全项目五次；同时候选采用后必须新提交重评，active 要按同 case 比较，attestation 24 小时到期且不启用执行缓存。这里的“subject/head”是二元组、两个独立唯一键，还是任选其一？若按 subject 唯一，同一候选落到新提交可能不能再测；若按 head 唯一，新 head 重复相同 subject 又能反复查询。到期重评、原 head 基础设施故障重跑、active baseline 重跑也无明确豁免/计费规则。

**关闭条件：** 用场景表冻结唯一键、计数主体、消耗时点、续期方式和 active 取证方式；至少跑通“候选通过→新提交→提交通过→24h 后续评”。不能通过换 job 绕账本，也不能把正常使用永久锁死。

**R08 · P1 · 规范缺口：隐藏保护信息可能通过计划和请求元数据提前暴露。** 依据：[PRD L108](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L108)、[PRD L139](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L139)、[PRD L145](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L145)、[PRD L289](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L289)；schema `CaseTemplate/EvaluationRequest/ExecutionPlan`。最终 finalist 之前计划已有 protected token；完整 CaseTemplate 又含 payload_digest、fixture_digest、objective_ids，ExecutionRequest 含 case/suite digest。没有定义各角色能读这些对象的哪个投影、保护 token 是否可跨 epoch 关联，以及私有证据索引解析权限。低熵模板的普通哈希不是隐藏内容的可靠屏障。

**关闭条件：** 列出每实体×角色×阶段可见字段，开发计划仅持有不可反推的引用；私有映射、trace、oracle 放在保护域。冻结保护集后再授权保护执行，测试 API、错误消息和文件权限的旁路读取。

**R09 · P1 · 规范缺口：保护套件的创建、轮换与使用后失效没有协议。** 依据：[PRD L249](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L249)、[PRD L301](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L301)。具体保护字节不公开是合理的，但当前也没有 suite 构建器、独立性要求、epoch 初始化命令、轮换记录 schema、历史证明如何随轮换失效等定义。五次即要求管理员轮换，会直接影响“一次确认后自动更新”的运营承诺。

**关闭条件：** 明确初始套件负责人、生成与审核方式、与 dev 去重规则、耗尽后的外部状态/恢复命令、管理员可见范围和新 epoch 生效点；公开结构与合同测试，私有 payload 单独部署。说明每五次人工操作是 M1 限制还是另设额度策略。

**R10 · P1 · 规范缺口：撤销/取消与发布的原子性跨越了未定义的状态存储。** 依据：[PRD L92](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L92)、[PRD L204](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L204)、[PRD L215](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L215)、[PRD L299](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L299)。publish 的字节、grant 和 outbox 在 proxy SQLite 内，但批准通过只读接口查询，generation/fence 由 controller 增加。若 proxy 先查到有效批准，随后控制面撤销提交，再由 proxy 提交发布，正文“撤销先提交则拒绝”的顺序无法仅靠本地 SQLite 事务保证。

**关闭条件：** 指定批准有效性、trust revision、run 生命周期/fence 的权威存储和发布线性化点；可把生效的 fence/撤销版本同步写入 proxy 的同库事务，并定义控制面确认语义。必须有可控竞争测试，而非只检查函数调用顺序。

**R11 · P1 · 规范缺口：可信 runtime 与 victim 的权限边界未落到进程/RPC。** 依据：[PRD L88](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L88)、[PRD L100](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L100)、[PRD L161](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L161)。模型只能产生 tool,args，runtime 注入 call_id/run/fence；但部署表只列 victim worker 拥有工具 socket，未说明 runtime 在哪个 UID/进程、谁能直接连接 proxy、谁能分配 call_id。若把不可信 AgentAdapter 和可信预算/身份注入放一起，后续实现可能允许重复 call_id、绕过批处理或预算。SO_PEERCRED 只识别进程身份，不验证“这个调用确由模型产生”。

**关闭条件：** 画出实际进程/UID/socket 映射，固定可信调用登记点、call_id 分配与参数绑定；代理核验注册调用和 fence。明确 M1 是否把 runtime/注册适配器列入可信计算基，而非暗示它们也可任意恶意。

**权限、身份与交接数据**

**R12 · P1 · 规范缺口：approved_cap 与语义授权范围只有名字，没有可批准的完整对象。** 依据：[PRD L190](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L190)、[PRD L196](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L196)；schema `ContractBody/ApprovalRecord/Policy`。ContractBody 只有 approved_resource_slots 和 approved_sink_slots 等字符串列表，未定义 slot 的资源类型、允许操作、租户/实例归属、目标绑定与最大动作集合如何生成。Policy.domain_digest、EvaluationRequest.semantic_authorization_digest 又没有对应规范对象与哈希投影。实现者无法仅凭这些附件一致地算出 approved_cap。

**关闭条件：** 补充 AuthorizationDomain、slot binding、approved-cap schema 与确定性展开函数；管理员实际批准其摘要。给出同 slot 错资源/错 sink/错实例拒绝的反例。

**R13 · P1 · 实证与规范缺口：策略元组没有按工具校验参数语义。** 依据：[PRD L168](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L168)、[PRD L188](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L188)、[PRD L190](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L190)；[Policy schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L565)。resource_bindings 允许空数组、任意 parameter 字符串和读写类型；P09 空绑定仍合法。build 样例使用 input_ids[0]/[1]，正文仅说恰好两表，未指定交换顺序是否等价。destination_id 还允许任意资源前缀。

**关闭条件：** 定义每工具必需绑定、访问方向、合法 check_set/destination、数组参数归一规则和未知参数处理；先证明动作是合法元组，再做集合包含检查。资源类型正确与权限正确分别校验。

**R14 · P2 · 实证不一致：集合没有规范排序，等价权限可伪装为新候选。** 依据：[PRD L122](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L122)、[PRD L188](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L188)、[PRD L285](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L285)；[校验器 L177](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L177)。JCS 不重排数组，P10 中仅逆序 allowed_actions 即改变 policy_digest，双向集合包含仍成立。义务列表、slot 集合也需说明哪些有序、哪些无序。因此“四摘要变了”不足以证明修复有语义变化。

**关闭条件：** 对集合类字段定义排序键和去重规则，先规范化再哈希；明确展示顺序不进入语义身份。no_change 除字节身份外增加有效策略/义务等价检查，避免重排计作修复。

**R15 · P1 · 规范缺口：宣称跨模块共享协议，但多个核心对象与 RPC 尚不存在。** 依据：[PRD L68](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L68)、[PRD L255](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L255)、[PRD L324](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L324)。22 类实体中没有 AttackPlan、MutationSpec、ObjectiveDefinition、LogicalFinding、FindingDisposition、ExecutionRecord、EvidenceIndex、RegistryEntry、Campaign/Lease、插件请求/响应 envelope，以及实际补丁内容对象。仅一个 digest 无法说明其指向文件的结构。八个 Adapter 也没有方法、错误、取消和版本握手协议。

**关闭条件：** 补足 M1 实际跨信任边界的对象和方法合同；不一定每个内部类都要上 wire，但每个跨进程/持久交接对象必须可校验、有所有者、版本和正反例。未来扩展对象可以明确 deferred。

**R16 · P1 · 规范缺口：执行记录仍存在潜在自引用，多个摘要缺精确投影。** 依据：[PRD L140](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L140)、[PRD L145](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L145)；[RunResult schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L1779)。ExecutionRecordDigest 的文字定义包括“结果与证据索引”，RunResult 自身却包含 execution_record_digest；若完整结果入记录就形成环。Task/Case/Run“除自身摘要”规则没有明确 execution_record_digest 是哪个对象的自身摘要。模型/tool/runtime/fixture/world/registry 的组合格式也未固定。

**关闭条件：** 明确 DAG：原始事件→无记录摘要的结果正文→ExecutionRecord→Gate→Attestation；用 JSON Pointer 列出投影，不靠自然语言“等字段”。给出每类对象的输入字节和已知摘要金样。

**R17 · P1 · 规范缺口：一个 run 的指纹与整个 subject 的通过证明层级混用。** 依据：[PRD L139](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L139)、[PRD L140](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L140)、[PRD L141](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L141)、[PRD L326](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L326)；schema `EvaluationRequest/Attestation`。EvaluationRequest 包含单一 case_digest，ExecutionRecordDigest 又描述实际 run/实例；Attestation 只有一个 request_fingerprint 和 execution_record_digest，却引用需要至少九例的 Gate decision。是每 run 一张，还是整场一张？promote 需要哪些证明、怎样覆盖全部 required runs，没有定义。

**关闭条件：** 分离 RunAttestation 与 EvaluationAttestation，或明确后者绑定完整 manifest/Merkle root；发布检查验证全套计划、结果、有效期与精确 subject/config，而非随机一例的有效证明。

**攻击、修补与业务语义**

**R18 · P1 · 实证与规范缺口：基础九例只有数量描述，没有可直接执行的套件合同。** 依据：[PRD L249](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L249)、[PRD L251](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L251)；[CaseTemplate schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L360)。公开附件是合成结果，不包含完整 dev fixture/攻击 payload/objective 谓词/投递位置；保护字节可私有，但其合同也需存在。P11 表明 attack case 可无 payload、objective、clean pair。每 finding 的原始 case＋变体如何共享或新增 clean 对照、何为同族新变体/重复、重放属于 repetition 还是新 case，都影响计数。

**关闭条件：** 冻结 SuiteManifest 与基础 dev 实例；规定 attack 必需字段、clean_pair 一致性、重复标准、预登记重复数；由测试计划机械生成覆盖，不让模型自己声明“有效攻击”。

**R19 · P1 · 规范缺口：投递长度、内容哈希与工具返回的语义没有协调。** 依据：[PRD L155](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L155)、[PRD L167](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L167)、[PRD L178](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L178)、[PRD L257](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L257)。notes 上限 1KiB，read 返回上限 4KiB，而单 payload 1500 Unicode 码点可达 6000 UTF-8 字节，append 后更长。只允许改 content_utf8 又意味着 bytes_digest 仍是原文摘要；它究竟证明底层资源还是实际展示字节？

**关闭条件：** 分别定义原资源字节、变异后展示字节、payload 字节和哈希；在执行前校验槽位的最终字节/token 限额，不能等运行时超限后归为安全成功。给出非 ASCII 最大 payload、append 超限、原文未读、多次读取命中规则的反例。

**R20 · P1 · 规范缺口：泄漏目标与所有输出通道没有封闭定义。** 依据：[PRD L110](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L110)、[PRD L155](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L155)、[PRD L273](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L273)、[PRD L358](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L358)。notes 可含敏感文本且禁止复制到发布结果，但 Agent 最终文本、tool args、错误日志、公开诊断、报告片段是否也是外发 sink？只检查 publication 就可能忽略“最终回答直接打印秘密”；全面过滤 canary 又会掩盖被测暴露。

**关闭条件：** 列出每种源、接收者、允许变换和观测通道；区分允许进入私有证据与禁止进入公开报告/用户响应。定义精确匹配、编码/分片变体是否覆盖及相应边界，说明合法客户姓名恰与 canary 相同如何判定。私有证据保留与报告脱敏分别设计。

**R21 · P1 · 待验证风险：strict 起点令核心攻击效果不可达，可能无法证明修补循环的价值。** 依据：[PRD L249](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L249)、[PRD L283](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L283)、[PRD L287](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L287)、[PRD L426](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L426)。三种基础目标都被固定代理机制阻断；精确 oracle、完整 receipt 和固定 sink 又阻断错误发布。若代理正确，effect_ASR 本来就可能恒为零，策略补丁也无法再添加已强制的条件。文档已正确禁止把机制夹具冒充自然效果，但尚未给出 M1 如何展示有意义的自然问题→补丁→改善。

**关闭条件：** 先做小规模可行性实验，验证一种真实可复现的 utility 劫持/恢复或尚在范围内的安全问题；分别定义平台强制收益、Skill 文字收益、攻击生成收益。没有改善时允许 honest negative result，同时明确“工程闭环完成”和“修补价值已证实”是两个验收结论。

**R22 · P1 · 实证与规范缺口：补丁只有摘要和限额，缺应用语义与身份约束检查。** 依据：[PRD L285](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L285)；[PatchCandidate schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L1939)。没有规定补丁是统一 diff、替换文件还是结构补丁；frontmatter 的边界、重复 key、解析器、换行、编码、不可修改字段集合均未固定。P15 中 policy_only 却声称改代码仍通过。每轮字节限额的“净新增/总增删”是相对最初 submitted、逐轮求和还是最终 diff，可能产生不同结果。

**关闭条件：** 冻结 PatchProposal/PatchApplication 格式与解析规则；由可信 applicator 重算 changed_paths、累计字节和候选摘要，拒绝任意模型自报统计；加入跨轮先增后删、重复 YAML key、伪父摘要等反例。

**R23 · P1 · 规范缺口：finding 何时“关闭”仍无完整状态转移。** 依据：[PRD L239](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L239)、[PRD L241](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L241)、[PRD L243](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L243)、[PRD L251](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L251)。高风险动态适用 finding 生成攻击但全不成功时，是保留未决、管理员判误报，还是有限覆盖可缓解？没有触发过漏洞时，几次被拒绝是否能产生 mitigated_by_policy？低/中 open 可警告，但后文低/中“已审批误报”措辞也可能被误解为必须审批。扫描器报告静态依赖问题，而自动补丁禁止改依赖，谁接手？

**关闭条件：** 定义 verification×disposition 转移表、转换权限、证据义务、不可自动解决时的终态；建立 scanner rule→动态目标/静态证据/不支持映射。未复现不能直接等于误报或修复。

**R24 · P1 · 规范缺口：“关键历史全部必测”的历史集合未定义。** 依据：[PRD L58](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L58)、[PRD L251](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L251)、[PRD L293](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L293)。是当前 campaign 发现的失败，还是项目以往 campaign 的关键失败？若仅本场，持续回归价值有限；若跨场继承，跨作业批次 deferred 不应被误解为禁止读取历史。critical/high 按 scanner 还是业务 objective 分级？契约、插件、模型变更后旧 case 如何迁移或不适用？

**关闭条件：** 规定历史库作用域、纳入/淘汰权限、版本兼容映射、隐私分区与容量公式。超量仍可保持 inconclusive，但必须有合法人工恢复路径，避免历史只增不减后永久无法运行。

**运行、依赖与开发路线**

**R25 · P1 · 规范缺口：预算尚不能证明完整评估会放得下。** 依据：[PRD L295](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L295)、[PRD L297](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L297)；runtime profile。模板给出 40 runs、4h、每请求 2048 输出 token，却没有总输入/输出 token 硬上限、阶段 timeout 明细、每轮扫描次数、每 finding 的最坏新增 run 计算、重放/active/重试如何计额、终止和写盘余量。日志 2MiB/run 也没有明确超限行为；按 16 轮反复记录完整上下文时可能先触顶。

**关闭条件：** 给出 executable budget calculator 和 representative plans（无 finding、一 finding、两轮修补、有 active、一次重试、历史逼近容量）；输出所需 runs/tokens/时间/磁盘并在启动前拒绝不可满足计划。工具模型输出不要静默截断。

**R26 · P1 · 规范缺口：campaign/run 的异常状态机缺少足够可执行规则。** 依据：[PRD L275](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L275)、[PRD L281](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L281)、[PRD L293](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L293)、[PRD L299](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L299)。正文有总体阶段顺序，但没有指定模型正常停止却未 publish、publish 后继续调用、达到 12 工具/16 轮、无工具最终回答、参数解析失败、provider timeout、worker lease 失效、取消中 scan 结束等分支。一次重试的资格与有效失败永久保留规则也需机器表达。正文表格出现 mechanism_valid/expected_rejection，而 RunResult 不接收这两个枚举，README 又要求机制负例另记；独立机制测试记录的 schema 和归档路径仍缺失。

**关闭条件：** 冻结 transition 表（事件、前置条件、原子写入、下一状态、reason code、是否重试、预算影响），规定所有非终态的恢复方式；状态未知不得续跑保护搜索或抹除失败。

**R27 · P1 · 规范缺口：配对实验的模型和环境等价条件不够具体。** 依据：[PRD L128](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L128)、[PRD L180](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L180)、[PRD L283](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L283)。指纹声明采样、thinking、模型 digest，但没有 ModelConfig schema、精确权重/tokenizer/template/服务镜像、seed 支持与后端非确定性声明。前后版本 runs 的顺序、并发、warmup、sampling seed 和 active 复测策略没有固定。

**关闭条件：** 定义具体配置对象和 run 顺序策略，记录实际后端返回版本；后端不支持 seed 要明确而非伪造确定性。相同 case 不等于相同随机轨迹，报告改善应给配对结果和样本范围，不能宣称单次通过就是稳定提升。

**R28 · P1 · 待验证风险：关键平台可行性验证应前置，不能等到底座全部完成。** 依据：[PRD L36](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L36)、[PRD L182](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L182)、[PRD L295](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L295)。当前没有固定模型、量化、推理后端、native tool calling template、ARM64 容器及依赖锁；模板 calibration_ready=false。DGX Spark 是 Arm/统一内存平台，能装下权重不等于能够以既定上下文和并发完成工具闭环。[NVIDIA 硬件规范](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)。

**关闭条件：** 在大规模实现之前完成最小 spike：固定镜像/模型，UDS gateway，4 工具正常路径，最长 Skill/输入/reference 与一次拒绝恢复，测峰值内存、耗时、token 和日志体积。失败时先调整 profile；不要先把不可验证的参数扩散到所有模块。

**R29 · P1 · 待验证风险：固定扫描器 commit 不等于固定可复现的离线扫描环境。** 依据：[PRD L224](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L224)、[PRD L226](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L226)；scanner profile。上游固定 commit 的 pyproject 仍含依赖范围，并要求 Python >=3.12,<3.15；YARA 等依赖需在 ARM64 验证。供应链分析源码仍调用 OSV，再走 fallback，并可能保留 limitations。断网并不保证所有带依赖包输入都能得到 complete。[上游依赖声明](https://github.com/NVIDIA/SkillSpector/blob/dabf4759a189be0f0428a2f7a472b3d5bdad1fe6/pyproject.toml)、[供应链分析源码](https://github.com/NVIDIA/SkillSpector/blob/dabf4759a189be0f0428a2f7a472b3d5bdad1fe6/src/skillspector/nodes/analyzers/static_patterns_supply_chain.py#L1755)。

**关闭条件：** 锁定安装产物/传递依赖与规则摘要，保存真实离线 smoke 原始结果及 analyzer 状态映射；对“依赖不在离线情报中”的输入明确 incomplete 或受限支持边界，禁止由 adapter 擅自改 complete。CLI 参数名称本次未发现直接错误；问题是可复现环境和覆盖证明尚缺。

**R30 · P1 · 实证不一致：ScannerReport 的 complete 语义没有可执行约束。** 依据：[PRD L230](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L230)、[PRD L232](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L232)、[PRD L235](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L235)；[ScannerReport schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L2843)。P05 同时声明 complete、exit=2、无原始报告、完成 analyzer 为空，schema 和 semantic_errors 均放行。`completed_or_justified_analyzers` 只有 ID 列表，无法在本实体中表示每 analyzer 的 not_applicable 依据和状态证据，required 列表也不与固定 24 个 ID 校验。

**关闭条件：** 定义逐 analyzer CoverageEntry，校验集合完整性、唯一性、原始报告版本、reason/evidence 与退出码规则；从注册 profile 导出 required 集，不能由报告作者少填以缩小检查面。

**输入、工具与外部集成细节**

**R31 · P2 · 实证不一致：CSV 解析比声明的 RFC4180 子集更宽。** 依据：[PRD L151](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L151)；[校验器 L210](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L210)。P13 的 `c1,Al"ice` 被接受；RFC4180 明确未加引号字段不能含双引号，Python csv 的 strict=True 并不能等同于这条语法约束。[RFC 4180 §2](https://www.rfc-editor.org/rfc/rfc4180#section-2)。

**关闭条件：** 明确采用 RFC 子集还是 Python 方言；若保持前者，新增词法校验和金样。同步冻结 header 顺序、空白行、空白客户名、首尾空格、Unicode 控制/格式字符的边界，避免不同语言实现出现不同业务真值。

**R32 · P2 · 规范缺口：手写 report.json 怎样满足“精确参考输出”未定义。** 依据：[PRD L132](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L132)、[PRD L153](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L153)、[PRD L169](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L169)、[PRD L170](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L170)。build 输出规定 JCS+LF，但 write_artifact 可写任意 UTF-8；validate 是比较原始字节还是解析后结构？不同 key 顺序、空白、无末尾 LF、重复 JSON key、1.0/1e0、额外字段的处理尚不明确。全局“只允许安全整数”还需落到原始 JSON 解析层：JSON Schema 的 integer 按数值判断，不能替代对词法形式、重复 key 与 JCS 可编码性的检查。当前参考函数只有生成路径，没有输出解析/验证规范。

**关闭条件：** 明确唯一接受语言。建议严格解析拒绝重复 key/非整数/未知字段，校验结构和业务值后要求 JCS+LF，或者明确允许语义等价并在存储前规范化；两种方案只能择一，receipt 必须绑定实际存储字节。

**R33 · P2 · 实证与规范缺口：资源注册表没有唯一性、生命周期与加载合同。** 依据：[PRD L116](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L116)、[PRD L161](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L161)、[PRD L163](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L163)；[TaskInstance schema](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/specs/v2.1/protocol.schema.json#L448)。P12 同 ID 不同字节被接受。包允许 32 文件，TaskInstance 最多 32 资源，若全部包文件加两输入、notes、artifact、sink 都注册会超限；哪些包文件作为运行 reference 也未指定 manifest。资源 ID 虽是逻辑标识，却允许 `..` 等片段，不能让实现者误当文件路径使用。

**关闭条件：** 固定 loader 选择规则、SKILL.md 必需性/frontmatter/编码规范、资源唯一键与跨 run 命名作用域、slot 到资源映射；说明只注册运行必需资源或协调容量。资源 ID 只查表，不拼接宿主路径。

**R34 · P1 · 规范缺口：receipt/grant/幂等的边界故障尚未定义完整。** 依据：[PRD L143](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L143)、[PRD L200](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L200)、[PRD L206](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L206)、[PRD L208](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L208)。grant 最长 10 分钟明确，但 receipt 无 issued_at、默认 TTL 和到期计算规则；批准在 run 中到期如何处理，旧版本内容写回相同 hash 的 ABA 如何处理，失败动作是否保存幂等结果，prepare 成功后 grant 过期使用同 key 是否永远返回旧 grant，均未封口。

**关闭条件：** 固定 receipt 与 run/批准截止的关系；以版本而非仅内容 hash 防 ABA；列出每工具各失败码的缓存/重试语义。同 key 的历史成功查询与新动作授权分开，同时明确取消/旧 fence 是否允许查询已有结果。

**R35 · P1 · 规范缺口：逻辑工具计数与幂等身份仍缺权威分配规则。** 依据：[PRD L174](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L174)、[PRD L188](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L188)、[PRD L206](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L206)。跳过的调用也计额、内部重传不计额，这个原则正确，但没有 call_id 去重作用域/持久表/参数 hash、何时原子预留、一次回复超过剩余额度如何处理。`idempotency_key`、call_id、模型原生 tool_call_id 三种 ID 也未给对应关系。

**关闭条件：** 指定可信 runtime 分配 call_id，原生 ID 仅关联消息；每批调用先校验并按规则预留，代理重传绑定同参数。增加重复原生 ID、同 call_id 不同 args、并发超额、多调用中途失败的可执行金样。

**R36 · P2 · 规范缺口：CLI 虽称固定契约，命令输出和退出行为尚不完整。** 依据：[PRD L243](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L243)、[PRD L318](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L318)、[PRD L332](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L332)。import/scan/admin/promote/report 的 stdout 应是哪一 schema，scan 无契约输出 ScanReport 还是 CIResult，四状态各对应哪个具体退出码，needs_contract/inconclusive 如何映射 GitHub check，缺 snapshot、无权限、业务输入非法如何区分 64/77/74，没有逐命令表。review-finding 是否必须走 admin namespace 也不清楚。

**关闭条件：** 给出 command×输入×输出类型×退出码×副作用表，固定完整 flags、ID 格式、冲突/重试行为；普通身份无法调用管理命令的示例须包含本地 socket 权限验证。

**R37 · P1 · 规范缺口：GitHub CI 的触发、权限与实际执行拓扑尚未交付。** 依据：[PRD L326](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L326)、[PRD L342](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L342)、[PRD L369](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L369)。正文讨论 PR head 和 webhook，却只有本地 --git-repo 命令；未说明谁拉取提交、fork PR 权限、webhook 验证、GitHub token 权限与存放、required check 名称、取消的旧 SHA check 状态及模型/config 变更怎样触发。若未来直接执行 PR 中 workflow 或构建脚本，就会超出当前“只读对象树且不执行包代码”的边界。

**关闭条件：** 选择 webhook service/GitHub Actions/受控本地 runner 的明确拓扑，给入口事件 schema 与持久 generation 规则；未可信 PR 字节仅进入导入/扫描/模型数据路径。若 M1 只做本地模拟 check，应从 M1 验收中明确标注 GitHub 集成 deferred。

**R38 · P1 · 待验证风险：无 GC、有限磁盘与单活跃作业缺少可恢复运营路径。** 依据：[PRD L295](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L295)、[PRD L301](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L301)、[PRD L328](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L328)。只在剩余<2GiB 时拒绝新作业，不代表已预留活动作业、模型缓存、数据库/WAL、扫描器报告及保护证据空间；只准删无引用临时文件而最终报告不断引用运行证据，会逐步没有可清理空间。没有定义 DB 损坏、服务停机、16 队列满、管理员中断、备份恢复后 revision/fence 单调性的处理。

**关闭条件：** M1 可继续不做自动 GC，但必须提供容量计算、队列满响应、人工导出/归档/停用与恢复运行手册；恢复后的旧 grant/lease/attestation 默认失效。磁盘写失败要保持不可通过，且有途径持久记录失败。

**范围、验收与规范维护**

**R39 · P2 · 范围未收口：G1/G2/G3 是路线目标，尚不是可直接施工的后续规格。** 依据：[PRD L59](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L59)、[PRD L72](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L72)、[PRD L371](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L371)。两契约是否属于同一家族、何谓“真实不同”、通用运算语法/DSL 支持哪些操作、第二宿主是谁、合同测试具体断言等都仍 deferred。声明“核心 diff 空”也不能单独证明通用性，业务专用逻辑可藏进通用接口或配置。

**关闭条件：** 把 M1 冻结范围与后续设计任务分开；为 G1 定义两个事先冻结的契约和参数化能力，为 G2 选不同语义家族，为 G3 指定宿主能力矩阵。验收同时看无核改动、接口合同和实际用例，不能仅检查目录 diff。

**R40 · P1 · 规范缺口：M1 完成与产品效果成功的验收仍不充分。** 依据：[PRD L157](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L157)、[PRD L360](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L360)、[PRD L422](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L422)。验收矩阵列了正反例类别，但没有必需实例数、重复配置、环境、预期状态/事件、证据路径；实际两个 Skill 也尚未给出文件。仅九例且通常每例一次，只能证明有限套件通过，不能支撑泛化安全率或稳定自动修复。参考业务计算和 build 若复用同一函数，错误也可能自洽通过。adjudicable_attack_cases 的纳入条件、false_refusal 是否计入后续恢复成功的拒绝、按目标或总体汇总、p95 算法和候选/active 的样本门槛也需要固定，且目前缺少正式 Metrics 对象。

**关闭条件：** 建立 requirement→test ID→fixture→command→expected verdict/events→evidence 矩阵；冻结两 Skill；业务 oracle 采用独立人工金样及实现交叉验证。分开报告工程正确性、业务可用性和修补改善，不因没有自然漏洞而伪造成功样本，也不因有循环代码便声称已证实价值。

**R41 · P2 · 实证与规范缺口：“正文/配置差异必使检查失败”尚未实现。** 依据：[PRD L64](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L64)；[校验器 L139](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L139)、[校验器 L385](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/scripts/verify_specs_v21.py#L385)。GateSpec 中多个行为开关/precedence 未由 gate 函数读取，而是硬编码；目前值一致不代表改配置后仍一致。规范脚本对正文主要检查 V01–V36 ID、链接、代码块和禁用措辞，不验证每条 MUST；PRD.md 与具版本文件也缺一致性约束。现有 15 个反例进一步说明“specification_only pass”只代表预列用例通过。

**关闭条件：** 区分可配置值与不可变常量；常量变动应显式被拒。用规范条款 ID 绑定机器断言/人工审查状态；唯一正文使用入口指针或生成副本校验。review-resolution 应区分“已决定”“已结构表达”“已反例验证”“已运行验收”，而非笼统关闭。

**R42 · P2 · 待验证风险：隔离配置方向正确，但可信假设与资源限制没有冻结。** 依据：[PRD L94](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L94)、[PRD L104](https://github.com/JiahaoTanXX/SkillLoop/blob/c8b61e4bba418c4fb03780df1911ba236878384a/SkillLoop-PRD-v2.1.zh-CN.md#L104)。network=none、只读 rootfs、cap_drop 等并不独立规定 CPU/内存/PID/文件描述符/UDS 消息上限、默认 seccomp/LSM、进程间观察权限以及模型服务管理面的隔离。也未声明宿主 root、内核、管理员、oracle/compiler、已注册插件哪些可信，哪些攻击者可控制。

**关闭条件：** 写明 M1 攻击者能力与可信计算基；固定 OCI/服务配置和资源限制，补服务端输入长度与超时约束。逐角色验证访问拒绝与合法调用；将内核逃逸/管理员恶意等明确排除或另设验收，不给超出测试范围的保证。

**建议的实施顺序与进入条件**

这不是人员或日程安排；每一步只在有可重复证据时进入下一步。

| 阶段 | 必须交付 | 进入下一阶段的证据 |
| --- | --- | --- |
| A. 收口高风险设计并做短平台实验 | 修正 Run→Case→Gate 真值表；计划/授权/保护/证明合同；固定一组 DGX 模型与扫描器环境 | 本报告反例有明确预期；模型四工具最短路径、最大输入与一次拒绝恢复实测可行；离线 scanner 原始输出可解析 |
| B. 确定性可信底座 | 输入/output validator、独立 goldens、policy compiler、proxy SQLite、批准与撤销/fence | 未接模型也能验证合法发布、越权拒绝、ABA、撤销竞争、响应丢失幂等、配额与崩溃恢复 |
| C. 首个完整评估纵向流程 | 一个 Skill、九例 manifest、可信 runtime、事件、CaseResult/Gate、不可变报告 | 正常/注入/未读/投递失败/证据丢失均得到指定结果；无用例或自报 verdict 不能通过 |
| D. 受限修补 | Finding 状态机、PatchProposal/applicator、候选计划 revision、配对回归 | 原提交失败且候选通过时双 verdict 正确；只改变 policy 顺序不是改善；预算不足保持 incomplete |
| E. 保护、采用和 CI | 私有 suite/epoch、保护账本、采用新提交、续评、Registry CAS、实际 GitHub 接入 | 跑通 R07 生命周期；旧 worker/head/config 不能发布；保护内容不回流补丁器 |
| F. M1 验收 | 第二个同契约 Skill、全部需求测试索引、运行操作手册和实际效果报告 | 限定范围内全部必须项通过；效果为空如实报告；明确区分工程完成与研究假设成立 |
| G. G1/G2/G3 | 各自先冻结新业务/宿主规范，再实现 | 不修改内核仍通过事先冻结的独立合同与金样，随后才能声明对应通用性 |

建议先关闭 R01–R07、R10–R13、R15–R18；这些决定可信数据流和模块接口。R21/R28/R29 的实验应在重工程投入之前完成，它们决定预期产品效果、平台和依赖是否可行。其余条目依赖相应模块逐步补齐，不能留成实现者自行选择的隐藏决策。

**可冻结标准**

每一条 M1 MUST 都能回答：谁执行、接受哪种已版本化输入、读取哪个权威状态、在什么事务/阶段生效、失败是什么状态和原因、哪个反例验证它、证据保存在哪里。每个跨模块引用都能解析到完整规范对象；每个未知/缺测均有传播路径；每个已证实失败不能被重试、证据缺失或另一 subject 的成功覆盖。所有重要分歧都写成唯一规则或显式不支持。

本报告没有把“未在 DGX 验收”误报为文档自相矛盾，也没有将已明确 deferred 的外部副作用、任意 shell、跨作业批次或自动 GC 列为 M1 必须补做的功能。对应条目只要求收口它们对当前 M1 的边界、恢复和声明的影响。即使关闭本次发现，也应把它视为达到可实施基线的证据，不能把一次审查当作对所有未来缺陷的证明。
