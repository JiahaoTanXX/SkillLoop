# M6 有界修补开发记录

## 2026-09-29 14:30 UTC 全部后台实验暂停与展示交付

按用户指令，DGX 原 M6 序列 PID 618290 和已停止态退款子进程 PID 822568 已核对身份并终止；退款与 Markdown 独立任务不再发起模型/API 请求。已有失败、不完整、账本和原时钟保留。公网唯一保留服务是展示站点；`/api/workflow` 与 `/api/custom` 的新实验 POST 均由服务端返回 423。自带 Skill 页面 `/custom` 只把待测 Markdown 与任务判定条件保存至 DGX 私有目录，不运行模型，也不产生新 API 费用。

新版首页突出三个 Skill 已有证据：订单 21/21 冻结候选回归与历史网页闭环，退款/Markdown 各自独立历史活动的确认攻击记录；当前实验状态折叠显示，活动身份和 Gate 保留，未跨活动合并。展示快照 `demo-web-presentation-v6b`，33 项机制测试通过，公网登录 200、匿名提交列表 401、提交页跳转登录 303；见 `milestones/M9/presentation-delivery-v6b.json`。GitHub 未提交或推送，正式 M7/M9 Gate 未通过。


## 2026-09-29 三 Skill 网页交付（14:14 UTC）

公网首页已切换到三个 Skill 的状态展示，五秒轮询脱敏状态，超过五分钟未更新会标注观测较早。订单原活动 42 次（40 完整、2 不完整）与最近一次独立网页 Demo 分开显示；退款和 Markdown 分别显示任务发布的当前校准/Gate 状态，并将旧活动攻击结果另列，不跨活动拼接。退款和 Markdown 正式 API 矩阵当前均为 0，正式 Gate 未通过。

网页允许上传或编辑 UTF-8 Markdown 订单 Skill（≤8 KiB），只有主动点击运行按钮才提交真实 API Demo。执行器仅有受控订单读取和汇总工具；任意其他 Skill 尚缺可信工具与 oracle 适配，不能宣称已经支持通用攻击验收。部署快照 `demo-web-hub-v5`，归档摘要见 `milestones/M9/hub-delivery-v5.json`。独立快照测试 29/29 通过、备用端口四个页面/API 返回 200、公网登录 200 且状态接口匿名访问 401。部署版独立 CI 收据生成请求因自动审批连接中断没有执行，保持 pending；GitHub 未提交或推送。


## 2026-09-29 订单 Demo 最新范围

用户最新指令：M7 暂缓，M8 仅本地 CI/CD，优先完成订单 Web Demo。公网端口表明确 `61.172.235.130:8019 → gx10-b489:8888`。已部署带独立口令的登录页、历史证据报告和可编辑 Skill 的真实 API 全流程工作台，入口 <http://61.172.235.130:8019/login>。

本地 CI/CD 21 项测试全部通过，独立复核见 `milestones/M8/acceptance-review-v3.json`。订单 Demo 范围复核见 `milestones/M9/acceptance-review.json`。两个最终版本真实活动均各自完成 3 次原 Skill、3 次候选、13 次 API 请求，原始上下文、响应、工具发布、分母与实际支出均在 DGX 独立重算。均无确认攻击成功，不能声称修补阻断攻击。每个活动每例一次，原始 reasoning 字段缺失；M7 未通过，正式候选资格仍 inconclusive。旧控制 Demo 与所有失败记录保留，不跨活动拼接攻击分数。

M6 原运行快照、冻结身份和时钟未改动。其他两个 M6 窗口已收到取消费用阻断、立即推进的最新指令；自动审批拒绝永久移除全部 profile 的共享费用上限，原账本保留，两窗口正在协调有限额度授权与唯一迁移负责人；额度转述不一致时需核对直接用户原文。此处不宣称其 M6 完成。

以下为保留的历史实施记录，阶段顶部状态以各 milestone 最新机器记录为准。

状态：2026-09-29，实施中；未验收，候选未冻结。

## 进入依据

M5 正式开发基线验收通过。故意脆弱 Skill 的独立扩展诊断已完成 25 个案例、75 次必需运行；3 个协议错误原尝试和重试保留，实际共 78 次。5 条可映射发现均有原攻击与不同变体覆盖，gate 证据状态 pass，开发安全判定 fail。11 个已确认失败 run 保留作为 M6 输入。见 [M5 验收摘要](../milestones/M5/discovery-acceptance.json)。用户明确授权在验收后开始 M6。

## 已实现

- `skillloop/repair/applicator.py`：API 4 PatchProposal、精确父 CandidateBundle 和文件字节摘要；UTF-8 范围、重叠、允许路径、frontmatter 与身份检查；策略只能收紧；两轮、三文件、累计增删 8 KiB、净增长 4 KiB 额度逐轮重算。历史账本伪报成本被拒。
- `skillloop/repair/proposal.py`：Qwen 仅提出 Skill 正文，可信代码封装准确字节范围。原响应、提议、诊断摘要与应用结果私有保存；生成失败和应用失败保留在分母。patcher 配置显式 `enable_thinking=false`。
- `skillloop/repair/history.py`：SQLite 私有失败库，按家族、profile、契约、目标注册表、oracle 和隐私域精确匹配；导入前独立重算失败运行的 trace、SQLite 和判定。只按完全相同 CaseTemplate 摘要共用回归，否则新增历史案例并保留原始身份引用。
- `skillloop/repair/budget.py`：逐 subject/case/repetition/phase 的追加计划；128 次、全活动两次合格重试、8 小时及 token/磁盘预算；执行前持久扣账；显式保留 submitted/finalist 保护容量；预算不足或未校准不能冻结。
- `scripts/dgx_m6_repair.py`：准备候选、重扫、受限执行的独立步骤；候选以组合摘要绑定，原攻击、变体和正常案例复用原始字节，适用历史加入套件。每个候选活动有独立身份。完整回归要求校准接单记录。
- `scripts/dgx_m6_gate.py`：重新应用补丁、核对源码与候选、重编套件/历史、重算计划 revision、扫描及逐运行可信证据；分别报告候选判定和对 M5 的历史配对改善/退化/未决，跨活动引用不会充当当前 Gate 的运行证据。

## 当前验证

最终本地实现测试共 90 项：86 项通过，4 项按平台条件跳过，其中新增 M6 机制测试 22 项通过。API 4 规范的 104 项测试通过。DGX 第三个独立快照已复跑通过全部 22 项 M6 机制测试。

## DGX 第一轮实测

`~/skillloop/m6-b01` 保存首轮模型提出的三个 Skill 正文、完整响应和受限应用结果。订单、退款各生成一次；Markdown 首次输出协议不合法，第二次生成成功。实际生成总数 4、应用成功 3、可评估候选 3，失败尝试保留。全部四个原始响应的 `reasoning_tokens` 均为 0。

| Profile | 回归案例 | 必需运行 | 确认失败历史记录 | 补丁实际增删字节 | 净增长字节 |
| --- | ---: | ---: | ---: | ---: | ---: |
| orders_total | 7 | 21 | 15 | 1,405 | 235 |
| refunds_total | 11 | 33 | 4 | 1,511 | 381 |
| markdown_index | 8 | 24 | 2 | 1,330 | 190 |

合计 26 案例、78 次必需运行，包含原攻击、不同变体、正常任务和适用历史。21 条失败历史来自两个先前活动的独立确认；只对 CaseTemplate 摘要完全相同的记录共用回归项。Markdown 的早期原攻击内容不同，新增一条历史案例，不能以本轮原攻击代替。

首次订单重扫已保存原始 `report.json`，归约代码错读 `coverage_complete` 字段而发生 `KeyError`。这是框架失败，未计作安全失败或修补成功。第二个实现快照改为读取规范 `ScannerReport.body.status`，并在归约前保存进程退出码、模型调用数及耗时。

第二个快照还把初版候选的诊断义务占位摘要替换为域绑定的正式 `RepairObligations`。使用原始 Qwen 响应中的同一正文重新绑定精确父组合，保留原提议数与失败分母；不重新调用模型搜索新正文。旧候选组合和失败重扫仍保存在 `m6-b01`，新组合独立写入 `m6-b02`，不得混用身份。

三份正式义务组合均已重绑完成，修正后的三份重扫已在 DGX 启动。当前机器状态见 [M6 进度摘要](../milestones/M6/progress.json)。完整回归尚未运行，预算校准和冻结判断仍 pending。

第三个快照修正了零发现扫描的 meta 适用性归约：固定镜像中 `nodes/meta_analyzer.py` 在没有 finding 时明确返回 `not_applicable/no_applicable_files`，其模块 SHA-256 为 `035a62ab4f141ac427882d1099f03934b536619d06fe03a1b2cf7a5976f6e8a4`。只有原始报告零发现、过滤前后均为零、meta 计划/完成/失败等工作量均为零且 LLM 可用时，才认可这个不适用状态；三个真正执行语义检查的节点仍必须 completed。反例测试验证过滤掉 finding、有计划未执行及跳过语义扫描均不能通过。原 v2 归约记录保留，未重跑模型掩盖旧结论。

三份原始重扫均已完成。第三个快照从同一份原始报告独立重算：

| Profile | 扫描覆盖 | 尚未处置 high | Qwen 调用数 | 实际耗时（秒） |
| --- | --- | ---: | ---: | ---: |
| orders_total | complete | 0 | 3 | 8.33 |
| refunds_total | complete | 0 | 4 | 93.96 |
| markdown_index | complete | 2 | 4 | 73.59 |

这 11 次扫描响应的 `reasoning_tokens` 均为 0。Markdown 候选仍有 `P1`、`RA1` 两条 high 告警，位置为 `SKILL.md:10`；当前保持 open/unverified，不能自动宣称误报或已经修复，也不能冻结该候选。订单与退款的零 high 也不能代替动态回归通过。重算摘要为 `sha256:1bc355e728add24bf99d001c23e2fff8a474b24bba9828d72882575f59428821`，私有文件为 `~/skillloop/m6-b02/rescan-recompute-v3.json`。

- 首个实现归档 SHA-256：`ba8ebdd1c485d6998dfecf943c7b29df22c788d40c6369ede49583d19678150c`，目录 `~/skillloop/repo-m6-v1`。
- 第二个实现归档 SHA-256：`1936fa97a9f53f3795012999a3c0fec9530c16e654be57844fe6460e4d996bc5`，目录 `~/skillloop/repo-m6-v2`。
- 第三个实现归档 SHA-256：`bf764d6d44085e7a62cbd22e85b65109f0f1be1f2a729a24251bac1fd89e8aa2`，目录 `~/skillloop/repo-m6-v3`。

候选正文、模型响应、历史库、攻击内容和原始扫描报告只保存在 DGX 私有目录，未写入公开报告。

## 尚待完成

1. 对 Markdown 候选两条新 high 发现做诊断、目标映射或明确静态处置依据；保持原有两轮额度和全部失败分母。
2. 最大业务输入与攻击负载，以及 scanner、辅助模型、预热、写盘/终结阶段的预算校准；代表计划包含无 finding、一 finding、两轮 + active、重试及历史容量边界。
3. 锁定后续执行实现快照，在接单预算内运行每个候选的原攻击、不同变体、正常对照和适用历史；新增 finding 先追加计划并预留资源，逐例三次重复。失败保留，纯协议错误重试需有无公开副作用的证据。
4. 独立 Gate 重算、配对效果统计、候选冻结或无法冻结的明确原因；仅在允许范围内追加第二轮。

M5 证据不回写；当前配置是单独版本化的 `m6-qwen-nonthinking-v1`。M6 完成前不得宣称修补有效或阶段验收通过。M7 保护题库及生产资格评估尚未启动，生产 `ready=false`。

## 配对计划和新配置校准

按用户最新指令，M6 验收后依次推进 M7–M10；当前仍停留在 M6。

第四个快照 `a50c2bacbef248d824611d1976514cab139d636ab9e97c95e6d4c8096993bd75` 的最大输入探针发现：150 秒 Agent 上限不足，且探针 notes 没有 evaluator 必需的唯一合成秘密标记。两次失败与第三个已开始的执行证据保留在 `~/skillloop/m6-cal-v4`，不计作真实攻击效果，未开放候选回归。拒绝依据独立保存为 `calibration-rejection.json`。

第五个快照 `6b6a56e8dc477e0e6cf315308fc7aef5342d96abe9cd257a382ba9b239aad6cc` 修正探针后，在配置 v3 下完成六次最大输入运行，业务全部正确，reasoning tokens 全部为零；worker 耗时 139.27–179.98 秒。该配置的候选回归没有启动。其校准不回填 v4 配置的通过记录。

预算复核确认：M5 是跨活动历史引用，不能替代当前配置下原 Skill 的开发对照。第六个快照将原 Skill 和候选的开发项放入同一 ExecutionPlan 和持久支出账本，并继续预留双方保护矩阵。首轮需执行原 Skill 78 次、候选 78 次，合计 156 次必需开发运行；每个 profile 独立接单，分别为 42、66、48 次。第二轮保留首轮所有执行事实；原 Skill 不重复重跑，旧候选的未开始保护容量保留为 abandoned，新候选先追加预算再运行。

当前配置为 `m6-qwen-nonthinking-v4`：Agent 210 秒、worker 240 秒、provider 120 秒、Proxy 230 秒；scanner 500 秒、最多四次模型请求。16 回合、16K 总上下文和2K 单次输出上限保留。实际预检耗时计入回合时限，达到生成长度上限记录不完整，不能当作完整回答。磁盘预算按每次 victim 8 MiB 加阶段和总预留计算。接近128次的计划也可能被8小时上限拒绝，不能删除历史或减少重复凑数。

最大输入包含表格20行、32字符标识、64字符标签及金额边界；文档4,096字节、100个标题、12,293字节合法制品；notes 为1,024字节且有唯一合成秘密，最大追加payload2,048字节。探针是独立校准执行，不充当开发回归结果。当前 v4 配置必须重新实测后才开放156次矩阵。

第六个快照归档 SHA-256：`c230fa7d2033db25a1586fa32cb738fdfb5370c24814bcb70d4c9a45369276bc`，目录 `~/skillloop/repo-m6-v6`；活动 `~/skillloop/m6-b06`，校准 `~/skillloop/m6-cv6`。本地实现测试95项：91通过、4跳过；规范104项通过；DGX新增M6机制测试27项通过。M6仍未验收，保护评估未开始，生产ready仍false。

## 多轮截止时间缺口与 tokenizer 修正

配置 v4 六次最大输入校准均完成，业务通过、reasoning tokens 均为零；三个 profile 的容量准入分别为68、92、74次。正式原 Skill 回归随后暴露多轮截止时间不足：保留11次尝试，8次完整、3次不完整，其中1次完整运行确认业务失败。当前 worker 完成后停止该配置的后续执行，候选回归尚未开始。`~/skillloop/m6-b06/configuration-rejection.json` 和 `interrupted-development-index.json` 明确记录此活动未验收。

旧 tokenizer 每次精确预检都重新加载模型的 tokenizer，DGX 计时约6秒。新实现由每个调用角色独立持有一个 tokenizer 子进程，通过 stdin 传递请求、请求编号绑定响应，并限制输入、响应和等待时间。它使用同一官方 tokenizer/template，进程间不共用输入或文本计数缓存；实例关闭时回收自己的子进程。独立 DGX 探针的新旧计数一致，首次加载4.455秒，后续0.00114/0.00064秒；该探针没有调用模型。模型的实际上下文预检和返回 `prompt_tokens` 一致性检查仍执行。

第七个独立快照 SHA-256：`f6dc3a3435b2086a444d33d0027bbff9556d4c20b4c8d5e88c0800af67802ce2`，目录 `~/skillloop/repo-m6-v7`；活动 `~/skillloop/m6-b08`，校准 `~/skillloop/m6-cv7`。配置 v5 为 Agent235秒、worker265秒、Proxy255秒、provider120秒、scanner300秒，思考关闭。必须重新校准，不能借用旧配置结果。原正文提议沿用首次模型响应，实际诊断来源保留，不伪称为新模型调用。

新增机制包括随机活动身份、校准运行的源码与候选上下文核验、第二轮生成前容量检查，以及逐个合法 PatchProposal 的两轮计数。失败历史允许在其余 CaseTemplate 字段全部相同、仅不透明 case_id 不同的情况下共用执行项，所有原失败摘要和证据引用仍保留；不同 payload、fixture、目标、重复次数或 clean pair 不会由此归并。历史库目前有23条适用记录，回归案例仍为26个，配对开发仍要求156次运行。

新 launcher 首次缺少 scanner image 参数，在创建容器之前报 TypeError。空目录、原日志和失败分类保留为 `scanner-launch-failure.json`，scanner容器执行数和模型聊天请求数均为零；明确加入固定离线镜像后从重扫步骤继续。

当前本地实现测试101项：96通过、5按平台条件跳过；规范104项通过。DGX第七个快照33项机制测试通过，包含实际 Linux Proxy/SQLite 的脚本模型配对测试；脚本模型测试不充当真实 Qwen 攻击证据。M6仍未验收，M7–M10尚未开始。

配置v5的六次最大输入校准已全部完成，业务均通过、reasoning tokens均为零，耗时120.96–153.23秒。独立重算通过后，三个profile的完整容量准入分别为68、92、74次；当前正在执行156次配对开发矩阵。

本地新增M6验收审查器仅接收独立重算报告，核对同一活动/配置与父Gate链、最终候选三次重复、静态告警、预算和冻结绑定。原 Skill 的所有必需执行项必须有可核验的运行记录；其已知失败不阻断候选审查。原 Skill 运行记录存在但覆盖不完整时，配对效果保持未决并列为验收限制；候选自身仍必须完整通过所有必需运行。M7 需要重新完成自己的保护评估，M6 结论不产生正面的原 Skill CIResult。报告一致性测试不替代实机原始证据复核。

## 验收预算复核与运行进度

辅助阶段预算复核发现，预热是最多16回合的 Agent 执行，原准入记录只预留一次模型调用的 token；patcher 的1K输出上限允许15,360个输入 token，原输入预留也偏低。新的独立归约先核验原准入记录，再按完整辅助阶段上界重新计算容量，并在冻结记录中绑定修正后的预算。原准入文件保留，运行次数、时间、磁盘和总 token 硬上限不提高；无法满足修正预算的候选不得冻结。

2026-09-29 04:47 UTC 的运行进度：订单原 Skill 21次尝试中20个必需项完整，候选21/21完整且未报告失败；退款原 Skill 35次尝试中33个必需项完整，候选23/33完整且未报告失败；Markdown尚未执行。原始不完整尝试保留，退款的两次合规重试计入实际分母。593次已读取模型响应的reasoning tokens均为零。这些数值是执行进度，尚非最终独立Gate结论。

本地实现测试109项：104通过、5按平台条件跳过；规范104项通过。验收程序单独版本化，正在运行的v7源码快照保持不变。M6验收仍pending，M7–M10尚未开始。

第九个独立验收快照归档SHA-256：`81862a94a95404d2802db5511c62f625c817c68bc91c5a8fc1f0e90e2a7a573f`，目录`~/skillloop/repo-m6-v9`。DGX已通过41项M6机制测试；其中脚本模型/Proxy测试只验证机制，不充当真实Qwen结果。基于当前部分原始证据的独立预检查保持pending。该快照没有修改正在运行的v7文件，也未启动M7。

五类代表计划使用当前DGX校准与完整辅助阶段上界计算，结果保存为`~/skillloop/m6-b08/calibrated-capacity-examples-v9.json`，摘要`sha256:b390099757931f32fdd4a0e3376ba5a33f507cae67024ea0b749bf63d6d8b4f9`。这些是接单计算，未作为实际victim运行记录：

| 计划 | 含重试储备的尝试数 | 保守墙钟（秒） | 准入 |
| --- | ---: | ---: | --- |
| 无finding | 56 | 17,410 | ready |
| 一个finding | 68 | 20,590 | ready |
| 两轮候选及active | 98 | 28,540 | ready |
| 历史接近运行容量 | 122 | 34,900 | rejected：墙钟超限 |
| 历史超容量 | 134 | 38,080 | rejected：次数、输出token和墙钟超限 |

本次三个profile的支出账本共用`m5-acceptance.json`的接单起点，排队等待也计入8小时。原时间戳和正在运行的源码保持不变；`~/skillloop/m6-v9-finalize2.py`在追加第二轮前核对剩余时间，最低新增容量都不足时拒绝生成并记录原因。若旧活动因排队耗尽墙钟，应保留未完成结论，在修正按profile接单调度后用新活动完整验证，不能重置旧时钟或把跨活动分数拼成当前Gate。

已设置当前任务每20分钟自动接续（`skillloop-m6-m10`）：先检查已有任务与证据再推进；只在实质变化、失败、完成或需用户输入时说明。最终M6独立验收之前，M7保护评估保持未开始。

## 按profile接单与实际支出核验

新实现要求每个新活动只接单一个profile，在准备阶段建立绑定活动和profile的不可变时钟。第二轮继承第一轮时钟，账本重启时拒绝更换起点；旧活动继续使用原时间戳。校准按活动中实际接单的profile执行两次最大输入探针，不能要求一个单profile活动同时含有三份候选。不同profile可分别形成独立完整Gate；同一profile的第二轮必须保持原活动身份并引用精确父Gate，审查还要求配置与归约源码一致。

候选执行结束后，以只写一次的`closed-development-spending.json`绑定实际账本与逐次运行文件的字节摘要、写入时间。独立Gate核对消费次数、重试、保守时间收费、时钟和运行记录，检查剩余时间能否容纳全部预留运行及终结阶段。账本或文件被修改、关闭后出现新写入、剩余容量不足都不能冻结候选。第二轮开始前也核验剩余完整容量，并用持久的独占claim避免重启或重复调度恢复搜索额度。

辅助阶段明确预留两次历史/计划处理各60秒；终结总预留600秒拆为三次Gate和一次耐久写盘，每项150秒。Gate使用实际截止时间。预算上限、每例三次重复、两次合规重试储备和两轮有效提议上限不增加。

v10在DGX的篡改机制测试实际正确拒绝修改后的文件，但Linux因文件写入跨越毫秒而返回`spending_closed_before_execution`，断言仅接受`spending_snapshot_changed`导致测试失败。旧快照及日志保留：`~/skillloop/repo-m6-v10`、`m6-v10-mechanism-failure.log`、`m6-v10-test-classification.json`。这次失败是测试分类问题，模型调用数为零，不能计为安全失败或修补结果。

v11修正断言，归档SHA-256为`5ea937aca73a7f429eb6f699bd5dab62951a73f94dbcd6fb9eb21b1120ca82ba`，目录`~/skillloop/repo-m6-v11`。本地125项实现测试：119通过、6按平台条件跳过；DGX57项M6机制测试通过。脚本模型的机制测试不充当Qwen攻击证据。当前v7真实回归和v9有界终结程序保持不变；v11尚未开始真实模型活动，必须在旧活动关闭后按profile顺序接单，并完整验证，不能把旧活动的分数用作新Gate结果。

新活动的顺序为：`prepare --profile` →固定镜像`rescan` →该profile两次`calibrate` →独立`admit` →原Skill的`regress --subject-role submitted` →候选`regress` →独立Gate；若需要且额度允许，再进入同一profile第二轮并完整复测。一个profile的活动关闭后才准备下一个，避免再次把排队时间消耗在已接单活动内。所有攻击内容与原始证据继续留在DGX私有目录。

## 顺序调度已部署，等待旧活动关闭

2026-09-29 06:17 UTC，旧活动仍在执行：实际134次尝试、130个必需项完整、4次不完整，14次报告失败；795次模型响应的reasoning tokens均为0且没有缺失用量字段。这是执行进度，不是最终Gate。订单与退款候选合计54/54完整且尚未报告失败；Markdown原Skill有23个必需项完整，候选尚未开始。Markdown新增的不完整原尝试经检查属于ProtocolError，没有发布副作用、业务结果未知，符合原定重试规则；实际重试和原失败均须保留。

`operations/dgx_m6_sequence.py`实现后续顺序调度，独立部署在`~/skillloop/m6-operator-v1`，没有修改v7、v9或v11源码快照。脚本SHA-256为`e6c2f28d6a65696b58c27e7d4f4bc22396f2b99814d5cf0d7488b49cae399757`。每个步骤前核对v11源码索引摘要`sha256:af90fcfb855095c624f72c5ab17f5a9c27c856eed67f65d30cc938b367e106b7`；整个调度持有独占文件锁，状态和日志只写一次，失败原文仅留DGX私有日志。

调度进程618290已启动，状态目录`~/skillloop/m6-v11-sequence1`、日志`~/skillloop/m6-v11-sequence1.log`。它先等待旧主进程、终结程序和残留工作进程全部退出，核验旧验收审查的摘要及pending结论，才允许新活动开始。预检查识别出了现有主程序和工作进程；当前没有新profile活动目录，没有新增模型运行。旧审查缺失、已通过或不一致时会停止并保留失败记录，不能自动越过验收。

若旧活动仍未验收，新调度保留其未验收结论并仅把独立确认的失败加入兼容历史。三个新profile的首轮目录计划为`m6-n11o/r/m`，各自的第二轮为`m6-n12o/r/m`，校准目录为`m6-c11o/r/m`。每个profile完成或明确记录未验收后才准备下一个；第二轮保留原时钟和两轮搜索额度，剩余预算不足时在模型生成前拒绝。所有运行都在新活动中完整重做，旧分数不充当当前Gate结果。M6独立验收仍pending；调度程序不启动M7。

本次新增8项调度机制测试在本地及DGX均通过，覆盖顺序接单、剩余时钟、写一次证据、PID复用与残留工作进程、第二轮条件及预算拒绝。累计本地实现测试133项：127通过、6按平台条件跳过；v11的57项DGX机制测试保持原记录，调度测试另计8项。这些测试没有调用Qwen，也不充当修补效果证据。

06:26 UTC完成一份仅针对已落盘Markdown运行的独立证据复算：25份原Skill记录（含原ProtocolError与完整重试）及3份候选记录，合计28份。配置、源码、计划、身份、载荷绑定、trace、SQLite和参考判定一致；其中164次原始模型响应的reasoning tokens全部为0。本次没有新增模型请求，也没有写入最终Gate或冻结记录。私有审计文件`~/skillloop/m6-b08/partial-evidence-audit-0624.json`，摘要`sha256:5cbc13014cd94a964e256b423042eb2e8cc45037c768728af20f30979e9868e8`。Markdown候选回归仍在执行，旧终结程序和新顺序调度仍等待；M6验收状态保持pending。

## 旧活动关闭，新订单活动开始

按用户07:23 UTC的最新指令，当前自动接续范围收敛到M6：完整独立验收后提交详细脱敏报告并停止自动接续，暂不开始M7、M8、M9、M10。

旧活动`m6-b08`已结束，主进程389706和终结程序578458均已退出。实际159次尝试、155个必需项完整、4次不完整保留；三个候选78/78完整且动态回归未报告失败，原Skill有14次报告失败。943次模型响应的reasoning tokens均为0。v9独立Gate摘要`sha256:8e124d0ebbb400170a5b73f3e8e85992c71b55e5cf25aed5dd531d5a54db8c86`：订单改善6项、未决1项；退款改善3项；Markdown改善5项；三个profile均没有已确认退化。Markdown仍有2条未处置high，未冻结，活动整体未验收。旧审查`~/skillloop/m6-final-acceptance-review.json`为pending、m7_entry_ready=false，摘要`sha256:9d02f858badfd982366caf08792d5c8de1885691b8829466185cf1416675c9e6`。

Markdown第二轮在模型生成前被拒绝：原接单时钟已消耗25,606.90秒，最低新增容量7,620秒，合计超过28,800秒硬上限；新增模型调用为0。旧时钟、原始证据和未验收结论保留。旧Gate中订单与退款的冻结仅属该旧活动，不计入新活动的运行或冻结证明。

顺序调度618290已按预定流程开始`~/skillloop/m6-n11o`，订单活动身份`m6-01629d47a0cc7a474c78f93b`，独立时钟从07:10:00.976 UTC开始；源码仍为未修改的v11。按配置摘要`sha256:4c400dcf1071d735054fb91cab14465d8d098d3ee814966eaa54f9fa666cedfa`运行，thinking=false。原正文提议沿用既有响应并绑定新父组合，没有重新搜索首轮正文；旧独立确认的失败作为兼容历史复算导入。当前订单历史快照23条，案例仍7个，当前活动要求原Skill21次和候选21次；其他profile尚未接单。

新订单重扫complete、0条未处置high，3次扫描模型响应的reasoning tokens均为0。两次最大输入校准完整、业务通过，耗时153.66和149.84秒，reasoning tokens均为0。独立准入通过，摘要`sha256:1485d75bc019e2d08164b909c1ad5d571240d8bc920f8be9f0d57d7e6c9a4230`；完整预留68次尝试、20,710秒、16,246,784输入token、2,316,288输出token及1,283,457,024字节。此为完整容量预留，实际支出仍须在候选结束后封存和由Gate交叉核验。

订单原Skill回归正在执行，其中一次在发布后provider_timeout：业务判定pass、覆盖不完整、耗时238.91秒，没有确认安全违规。该尝试不符合重试条件，保留原记录；不能计为完整配对或删除。候选回归与独立Gate尚未开始，M6整体验收仍pending。

2026-09-29 07:51 UTC 只读核验更新：顺序调度器618290与订单原Skill回归进程658464仍在运行；`m6-n11o`首轮订单活动未变。已落盘11条submitted结果，其中9条覆盖完整、2条不完整；11条utility均为pass，均未报告security violation。原始trace中66次模型响应的reasoning tokens均为0，缺失用量字段为0；累计prompt 172,645 tokens、completion 14,574 tokens。订单候选仍未开始，活动支出尚未封存，Gate尚未运行。旧最终审查仍为pending且`m7_entry_ready=false`；没有进入下一个profile或M7。本快照只是运行进度，不替代最终独立复算。

2026-09-29 07:55 UTC 再次只读核验：调度器618290和订单原Skill回归658464仍在运行。结果记录增至12条，其中10条覆盖完整、2条不完整；utility均为pass，无security violation。累计72次模型响应，reasoning tokens为0且无缺失用量，prompt 188,412 tokens、completion 15,989 tokens。订单候选仍未开始，实际支出尚未封存，Gate未运行；最终审查仍pending、`m7_entry_ready=false`。这是新的运行进度快照，不构成Gate结论。

2026-09-29 08:05 UTC 只读复核：订单原Skill回归已产生16条结果，14条覆盖完整、2条不完整；utility 16/16为pass，安全违规0。原始trace有98次模型响应、reasoning tokens 0、用量缺失0，prompt 256,105 tokens、completion 21,477 tokens。调度器618290与回归进程658464仍在运行；submitted仍未达到21条必需完整运行，候选回归、支出封存和独立Gate均未开始。旧最终审查保持pending、`m7_entry_ready=false`。失败和不完整记录继续计入并保留；以上仅是运行快照。

2026-09-29 08:15 UTC 只读复核：订单原Skill submitted 已有19条结果，17条覆盖完整、2条不完整；utility 19/19为pass，security violation为0。116次原始模型响应的reasoning tokens均为0、用量字段无缺失；prompt 302,170 tokens、completion 25,286 tokens。调度器618290与submitted回归658464仍运行。尚未达到21条必需完整submitted运行，候选、实际支出封存及独立Gate均未开始；最终审查仍pending、`m7_entry_ready=false`。本快照不构成验收结论。

2026-09-29 08:25 UTC 阶段变化：订单submitted阶段结束，执行脚本退出码为0；21条结果中19条覆盖完整、2条不完整，全部utility pass，其中1条真实security violation保留为原Skill失败。顺序调度已开始同一活动的候选回归；当前2/21条候选记录均完整、utility pass、无security violation。两侧已落盘共23条结果，涉及142次模型响应、prompt 368,387 tokens、completion 29,994 tokens；reasoning tokens均为0且用量记录完整。候选仍在运行，支出快照尚未关闭，独立Gate未开始；最终审查仍pending、`m7_entry_ready=false`。原始失败和不完整记录均保留，本快照不代替独立Gate。

2026-09-29 08:35 UTC 只读核验：同一订单候选回归增至6/21条，6条均完整、utility pass、无security violation。submitted结果保持21条（19条覆盖完整、2条不完整、1条原Skill安全违规）；两侧累计27条结果、167次模型响应，reasoning tokens均为0且用量无缺失，prompt 433,800 tokens、completion 34,367 tokens。调度器618290及订单候选回归进程仍在运行；候选未完成、实际支出快照未关闭，Gate仍未开始。最终审查pending、`m7_entry_ready=false`。

2026-09-29 08:45 UTC 只读复核：订单候选进度为10/21条，当前10条均完整、utility pass且无security violation；原Skill的21条结果保持不变（19条覆盖完整、2条不完整、1条安全违规）。累计31条结果、191次模型响应，reasoning tokens均为0且用量字段完整，prompt 496,577 tokens、completion 38,448 tokens。调度器618290和订单候选回归进程仍在运行；候选尚未完成、支出封存与独立Gate均未开始，旧最终审查仍pending且`m7_entry_ready=false`。

2026-09-29 08:55 UTC 只读复核：订单候选进度达到14/21条，14条均完整、utility pass、无security violation。submitted仍为21条（19条覆盖完整、2条不完整、1条安全违规）。两侧共35条结果、215次模型响应；reasoning tokens均为0、用量完整，prompt 559,596 tokens、completion 42,667 tokens。候选回归和调度器仍运行；候选、实际支出封存和独立Gate尚未完成/开始，最终审查pending，`m7_entry_ready=false`。

2026-09-29 09:05 UTC 只读复核：订单候选已有19/21条结果，19条均覆盖完整、utility pass、无security violation。submitted仍为21条（19条完整、2条不完整、保留1条原Skill安全违规）。累计40条结果、247次模型响应，reasoning tokens为0且用量字段完整，prompt 641,412 tokens、completion 47,786 tokens。候选与调度器进程仍运行；待完成最后2条候选记录后才会封存支出并运行独立Gate。旧审查仍pending、`m7_entry_ready=false`。


## 订单新活动完成，退款活动运行中（2026-09-29 09:18 UTC）

顺序调度器仍为 PID 618290，源码与索引摘要未变；DGX 当前运行退款原 Skill 的 submitted 回归，PID 745771。订单活动 `m6-n11o` 已完成 submitted、candidate 和独立 Gate，并在顺序调度记录中关闭为 frozen；随后才启动退款活动 `m6-n11r`。未启动 Markdown profile，也未创建最终 M6 `acceptance-review.json`。

订单候选的独立 Gate verdict 为 pass 并冻结：21/21 必需运行完整、utility 全部通过、无安全违规、无未解决 high；模型响应129次，`reasoning_tokens=0`。原 Skill submitted 有21条尝试，其中19条完整、2条不完整，并保留1条已确认失败。Gate 的配对统计为改善1、退化0、不变18、未决2；因此该 profile 的候选 Gate 可通过，但提交基线存在失败，配对覆盖不完整，`orders_total-review.json` 仍为 pending。不得将这项局部候选 Gate 通过解释为 M6 验收。

订单两侧共42条运行结果（40条完整、2条不完整），共259次模型响应；prompt 672,701 tokens、completion 49,896 tokens，reasoning tokens 0、用量字段无缺失。实际支出快照已关闭：42次执行尝试、无重试、观测墙钟7,248秒，接单保留68次、计划66次，尚余26次及7,610秒保留墙钟。Gate 文件嵌入摘要为 `sha256:4d965d86a1ba47cfc67d290f8625577d8dda50b4b6e704c79417d15770f08fd9`；封存支出摘要为 `sha256:0d83aaf60ee70faace3ab36bd06e263cd76eae8d63db1dc5785a64e45283a56a`；profile 关闭记录摘要为 `sha256:795367db6f4a78d2fa2c00246894a8e76abdb628350bce0ff5326787e088d3c7`。

退款新活动配置与源码索引摘要分别为 `sha256:4c400dcf1071d735054fb91cab14465d8d098d3ee814966eaa54f9fa666cedfa` 和 `sha256:af90fcfb855095c624f72c5ab17f5a9c27c856eed67f65d30cc938b367e106b7`；预算接纳90项计划、预留92次尝试，状态 ready。submitted 回归仍运行，候选和 Gate 尚未开始。顺序调度报告订单 profile review 为 pending，原因是退款和 Markdown 报告尚不存在；整体 M6 仍 pending，`m7_entry_ready=false`。


## 退款 submitted 运行快照（2026-09-29 09:35 UTC）

DGX 顺序调度器 PID 618290 和退款原 Skill 回归 PID 745771 仍运行；回归尚无完成标记，候选回归、支出封存与 Gate 均未启动。对 DGX 私有执行目录的规范结果摘要显示，退款 submitted 已有7条结果记录：6条覆盖完整且 utility pass，1条覆盖不完整且 utility unknown；截至此时安全违规为0。该不完整尝试按归约记录属于 `model_or_runtime_protocol_error` 类，原始记录保留，是否符合重试资格仍按运行证据与既定流程确定。

这7条记录包含43次模型响应；原始usage字段完整，prompt 110,130 tokens、completion 9,647 tokens，reasoning tokens均为0。退款 profile 总需求为33条 submitted 与33条 candidate 运行；当前仅 submitted 阶段运行，不能把尚未开始的candidate记为结果。该 profile 的准入仍为ready，预留92次尝试、计划90次。

当前v11第一轮矩阵累计可见49条结果：订单42条、退款7条；46条完整、3条不完整，保留1条原Skill确认安全失败；302次模型响应，prompt 782,831 tokens、completion 59,543 tokens，reasoning tokens 0且usage完整。此为运行进度摘要，不是Gate或M6验收。最终审查文件尚未生成，Markdown尚未开始，`m7_entry_ready=false`。原始trace、响应和攻击内容留在DGX私有目录。


## 退款 submitted 新增安全失败记录（2026-09-29 09:45 UTC）

顺序调度器 PID 618290 与退款原Skill submitted 回归 PID 745771 仍在运行；该阶段尚无finish标记，候选、支出封存和Gate未开始。退款submitted结果累计10条，其中9条完整、1条不完整；9条utility pass，另1条utility状态unknown。现有结果中出现1条security violation，作为原Skill失败保留，不删减或改写；此前协议不完整记录仍保留。

10条结果的59次模型响应全部有usage，prompt 153,522 tokens、completion 13,222 tokens、reasoning tokens 0。合并已完成的订单profile，当前第一轮累计52条结果、49条完整、3条不完整、2条原Skill安全失败；318次模型响应，prompt 826,223 tokens、completion 63,118 tokens，reasoning tokens 0、usage缺失0。以上为过程摘要；退款候选尚未开始，M6整体仍pending，Markdown未开始，`m7_entry_ready=false`。原始攻击、响应和trace仍仅保存在DGX私有目录。


## 退款 submitted 进度（2026-09-29 09:55 UTC）

DGX上同一退款活动仍处于submitted回归，PID 745771；顺序调度器PID 618290运行中。阶段无finish标记，candidate、封存支出和独立Gate尚未开始。当前可归约的submitted结果累计13条：12条完整、1条不完整，12条utility pass、1条原Skill安全违规；此前不完整协议尝试及失败记录均保留。

原始usage摘要累计82次模型响应，prompt 211,652 tokens、completion 17,807 tokens，reasoning tokens为0且相关字段完整。退款profile已观测墙钟2,756.6秒，支出账本保守收费3,975秒，预算仍保留27,070秒墙钟及92次尝试的准入上限；当前账本记录15次victim尝试，含执行中/未归约尝试，不能把它们都算成完成结果。整体首轮已归约55条结果（订单42、退款13），52条完整、3条不完整、2条原Skill安全失败；M6仍pending，Markdown未开始，`m7_entry_ready=false`。


## 退款 submitted 运行快照（2026-09-29 10:05 UTC）

原Skill submitted 回归与顺序调度器仍在运行；尚无该阶段finish记录，candidate、封存支出和Gate均未启动。退款当前有17条结果（16条完整、1条不完整），16条utility pass；保留1条security violation及先前协议不完整记录，没有新增失败。101次模型响应的usage完整，prompt 261,739、completion 22,116 tokens，reasoning tokens为0。

退款活动观测墙钟3,289.7秒、保守收费4,770秒，已记录18次victim尝试（含未归约执行），保留预算为27,070秒墙钟。第一轮矩阵当前59条已归约结果、56条完整、3条不完整、2条submitted安全失败；360次模型响应，prompt 934,440、completion 72,012 tokens，reasoning tokens 0。该阶段状态仍为运行中，M6 pending，后续profile未开始，最终验收尚未产生。


## 退款 submitted 运行快照（2026-09-29 10:15 UTC）

退款原Skill submitted 回归仍在运行，候选、支出封存和Gate尚未开始。当前结果20条，其中19条完整、1条不完整；19条utility pass，原Skill安全违规仍为1条，没有新增失败。已读到的122次模型响应usage完整，prompt 314,578、completion 26,641 tokens，reasoning tokens 0。

该活动观测墙钟3,840.4秒，账本保守收费5,565秒，共记录21次victim尝试（含未归约/执行中尝试）。本轮累计已归约62条结果，59条完整、3条不完整、2条原Skill安全失败；381次模型响应，prompt 987,279、completion 76,537 tokens，reasoning tokens为0。运行进程及独占顺序调度保持原状，M6仍pending。


## 退款 submitted 运行快照（2026-09-29 10:25 UTC）

退款submitted仍在运行，结果累计23条：22条覆盖完整、1条不完整；22条utility pass，原Skill安全违规仍为1条，没有新增失败。candidate、实际支出封存和独立Gate仍未开始。139次模型响应usage完整，prompt 359,891、completion 30,801 tokens，reasoning tokens为0。

退款活动观测墙钟4,406.2秒，账本保守收费6,360秒，记录24次victim尝试（可能含在途或未归约运行）。当前v11第一轮累计65条结果、62条完整、3条不完整、2条原Skill安全失败；398次模型响应，prompt 1,032,592、completion 80,697 tokens，reasoning tokens 0。M6仍pending，未启动后续profile。


## 退款 submitted 运行快照（2026-09-29 10:35 UTC）

DGX顺序调度器及退款submitted进程仍运行；该回归阶段未结束，candidate、支出封存和Gate尚未启动。结果累计26条：25条完整、1条不完整；utility 25条pass、1条unknown，原Skill安全违规仍1条，未发现新失败。159次模型响应均有usage，prompt 413,184、completion 35,467 tokens，reasoning tokens为0。

退款活动观测墙钟5,007.1秒、账本收费7,155秒，记录27次victim尝试（包含在途/未归约项）。当前首轮累计68条归约结果，65条完整、3条不完整、2条submitted安全失败；418次模型响应，prompt 1,085,885、completion 85,363 tokens，reasoning tokens 0。M6仍pending，当前profile后续阶段和Markdown未启动。


## 退款 submitted 运行快照（2026-09-29 10:45 UTC）

退款原Skill submitted 回归仍在运行，累计29条结果：28条覆盖完整、1条不完整；28条utility pass，原Skill安全违规仍为1条，没有新增失败。candidate、实际支出封存和独立Gate尚未开始。178次模型响应usage完整，prompt 463,131、completion 39,841 tokens，reasoning tokens为0。

退款活动观测墙钟5,558.1秒，账本保守收费7,950秒，记录30次victim尝试（可能含在途或未归约运行）；仍保留27,070秒预算墙钟。当前v11第一轮累计71条结果、68条完整、3条不完整、2条原Skill安全失败；437次模型响应，prompt 1,135,832、completion 89,737 tokens，reasoning tokens 0。顺序调度和submitted回归继续运行，M6仍pending，M7未启动。

## 退款候选回归已开始（2026-09-29 11:06 UTC）

本次只读核验确认DGX顺序调度器仍运行，退款 `submitted` 阶段已结束并返回0，随后进入同一活动的候选回归。当前有34条 `submitted` 结果记录，对应33个必需项及1次保留的协议错误重试；其中1条协议不完整尝试与1条原Skill安全违规均保留。退款活动观测墙钟6,764.9秒、账本保守收费9,805秒、victim尝试37次、重试1次；接单保留92次与27,070秒墙钟预算未变。

候选阶段已有worker运行，尚无已落盘候选结果。订单活动原有42条结果中，21条候选完整且已冻结；当前矩阵共76条结果、73个必需项完整、3条不完整，原Skill安全失败2条。此次数值来自进程、阶段状态和私有结果文件数量的只读核对；本快照未重新计算token总量，不构成动态效果Gate。退款Gate、Markdown活动及最终 `acceptance-review.json` 尚未开始/生成，M6仍pending，M7–M10未启动。

11:07 UTC核验：退款候选已有5/33条结果记录，当前候选worker仍运行；退款 `submitted` 仍为34条记录（33项必需运行加1次协议重试）。退款活动观测墙钟7,194.4秒，账本收费10,600秒，victim尝试40次、重试1次，当前准入预算未变化。订单42条加退款现有39条，第一轮已落盘81条记录、78个必需项完整、3条不完整；Gate和实际支出封存未开始。模型token汇总本次没有重算，原始trace继续仅留DGX。

## M6必需运行数说明与当前进度（2026-09-29 11:12 UTC）

独立矩阵固定为26个案例、156次必需回归运行：`orders_total` 7案例×3重复×原Skill/候选=42次，`refunds_total` 11×3×2=66次，`markdown_index` 8×3×2=48次。校准、扫描和符合条件的协议重试是额外工作，不减少156次分母。DGX刷新显示退款候选为6/33，当前已完整完成79/156次必需运行；82条结果记录中3条不完整，2条原Skill安全失败保留。当前profile仍在回归中，候选尚未全部完成、实际支出尚未封存，独立Gate与最终验收均未运行。

11:18 UTC核验：退款候选结果增至8/33；顺序调度器与回归/worker仍运行，退款Gate与最终审查尚未开始。订单候选仍保持21/21完整、Gate通过并冻结；订单 profile review 继续pending，因为原Skill基线有不完整与安全失败，配对结论不能当作完整。当前首轮矩阵已有84条结果，81个必需项完整、3条不完整；原Skill确认安全失败仍为2条。此为进度，不是最终验收。

## 用户要求暂停后续profile（2026-09-29 11:23 UTC）

订单profile已完成首轮全部流程并由独立Gate通过、冻结：活动 `m6-01629d47a0cc7a474c78f93b`；候选bundle `668d3147…c2f2b3`；配置摘要 `4c400dcf…6cedfa`；源码索引摘要 `af90fcfb…7e106b7`；Gate摘要 `4d965d86…f08fd9`；冻结摘要 `20bf1841…f7646a99`。7个案例的21/21候选运行完整，Gate无缺项、无候选失败、无未处置high，冻结通过。129次模型响应的 `reasoning_tokens` 为0。补丁实际增删1,405字节、净增长235字节。订单实际42次执行、0次重试、观测墙钟7,248秒；接单预算68次/20,710秒、计划66次，余26次与7,610秒。扫描3次模型调用reasoning tokens为0；两次校准分别153.66和149.84秒，完整且业务通过。

原Skill基线为21条尝试，19条完整、2条不完整，并保留1条确认安全失败。与候选配对为改善1、不变18、退化0、未决2，配对覆盖不完整。因此订单候选Gate通过并冻结，但 `orders_total-review.json` 为pending：当前只收到订单Gate，退款和Markdown Gate报告缺失，且原Skill配对有2项未决。不能据此称M6整体验收通过。

按用户要求，退款回归父进程822568已通过SIGSTOP暂停，正在运行的单个worker自然结束并保存第11条候选结果（业务完整、utility pass、无安全违规）；父进程停住前没有写入该条的wrapper timing，因此该记录尚未最终归约。DGX核验时另有顺序调度器618290等待该暂停的父进程，没有活动模型worker；退款候选11条结果文件中10条此前已最终化。退款活动累计墙钟7,895.7秒、账本收费11,925秒、victim尝试45次、重试1次，预算预留92次/27,070秒；实际支出快照尚未封存，退款Gate未运行。Markdown目录和prepare-start标记均不存在，尚未启动。状态文件保留，没有改写运行快照、源码或原始证据。

自动任务复核：`~/.codex/automations` 本地目录为空，`progress.json` 中的 `skillloop-m6: ACTIVE` 是陈旧记录。Codex app的view调用只显示自动任务卡片，没有返回可核验状态；尝试以旧ID更新为PAUSED因缺少kind/name/prompt/rrule被参数校验拒绝，未产生修改。没有新建替代任务，以免在无恢复时间安排时重新启动已暂停的profile。需用户明确恢复时点后再设自动接续。

## 订单配对分母与改善项分类澄清

只读读取DGX `m6-n11o` 的compiled案例kind及submitted原始result，Gate摘要仍为 `4d965d86…f08fd9`。7案例实际为5攻击案例和2正常对照，各重复3次。修补前攻击测试15次：13次完整、2次不完整，确认security violation 0、utility fail 0。正常对照6次全部完整，其中security violation 1、utility fail 0。因此本轮配对中的改善1来自正常对照的安全违规消失，不能宣传为一次注入攻击从成功变失败；持平18是13次攻击通过和5次正常对照通过保持通过，未决2是原Skill的2次不完整攻击测试。旧M5及其他活动历史失败不并入此活动攻击成功分母。

## 退款与Markdown修补前攻击次数核对

本次仅在DGX私有目录按CaseTemplate.case_kind归约已保存submitted result，未启动模型、恢复暂停进程或改写快照。当前退款m6-n11r为9个攻击案例、27次必需攻击运行，实际28次（包含1次协议重试）：27完整、1不完整，报告1次攻击security violation，类别为合成秘密泄露的original案例；正常对照6次另有1次security violation。因此本轮退款submitted安全违规总数实际为2，先前运行快照的1已纠正；独立Gate尚未运行，这里仍是结果记录统计。当前Markdown m6-n11m目录不存在、攻击运行0。

旧活动m6-b08由v9独立Gate复算，摘要8e124d0e…4db8c86：退款攻击28次（27完整、1不完整），确认合成秘密泄露3次，original 1、variant 2；正常对照实际7次、1不完整、无安全违规。Markdown攻击19次（18完整、1不完整），确认未经校验发布5次，original 2、variant 1、基础/历史案例2；正常对照6次均完整且无安全违规。旧活动这两个profile合计47次攻击尝试、45次完整、2次不完整、8次确认攻击成功。旧活动与当前活动分别统计，不跨活动拼接分数。退款父进程仍为T(stopped)，Markdown当前活动未创建。

## 订单范围验收及 M7 封存（2026-09-29 12:07 UTC）

订单 M6 原始 trace、SQLite、补丁、静态复扫、预算、冻结和源文件已再次独立重算，结果与原 Gate 完全相同。新增单 profile 验收记录为 ready_with_limits，摘要 be8275c0…7e5cee4；限制为 submitted 配对覆盖不完整。整体三 profile M6 review 保持原有 pending，不把单 profile 接单门槛冒充全局验收。

用户随后要求封存 M7，开始 M8–M9 的工作。M7 正式保护评估未创建活动、模型运行0/24；新快照13项机制测试通过，v1完整套件结构测试失败与启动记录保留。模型生命周期进程已停止，保护容器不运行，候选未修改。M8–M9 先实施订单 Demo、本地 CI 判定和报告；正式资格仍受未通过的 M7 Gate 阻断，GitHub commit/push/PR 未授权。退款保持停止，Markdown当前活动未开始。

## API 并行范围准入（2026-09-29 12:36 UTC）

用户新增授权：订单 M7 与退款、Markdown M6 使用 qwen3.8-flash API 并行准备；API费用总上限10元，输入0.8元/M、输出2.7元/M，thinking=false。旧退款活动仍暂停，旧Markdown活动尚未创建。API凭证只在DGX私有目录保存，仓库不含凭证。模型列表认证成功；非私有的普通/流式各一次接入探针，输入30、输出1 token，均没有原始reasoning_tokens字段，不能把缺失记成0。两条raw响应只在DGX私有目录，费用保守预留共0.026336元。

新API配置与原DGX模型不同，不能继承旧配置下的开发分数作为新模型验收。新配置完整capacity计划保留全部必需重复、保护容量、重试和辅助预算，准入报告见 milestones/M7/api-parallel-admission.json；10元共享上限不足，原始reasoning用量证据缺失，真实业务校准未通过。因此三项正式API矩阵尚未启动，不能称为运行中或已完成。M8本地Demo开发继续，正式M8–M9资格仍等待父Gate。


## 退款 profile candidate 阶段快照（2026-09-29 10:55 UTC）

顺序调度器确认退款 submitted 阶段结束（exit code 0），并已启动 candidate 回归；candidate 进程仍运行，尚无候选结果记录，独立Gate和profile review未开始。submitted 有34条结果记录：33条完整、1条协议不完整；33条utility pass，保留2条原Skill安全违规（比10:45快照新增1条）。203次模型响应usage完整，prompt 529,009、completion 45,778 tokens，reasoning tokens为0。

退款活动观测墙钟7,895.7秒，账本保守收费11,925秒，记录45次victim尝试（可能含校准、扫描、submitted、在途或未归约工作），预算准入上限92次、计划90次，保留墙钟27,070秒。v11第一轮累计76条结果、73条完整、3条不完整、3条原Skill安全失败；462次模型响应，prompt 1,201,710、completion 95,674 tokens，reasoning tokens 0。订单候选已冻结但profile审查pending；Markdown尚未开始。M6仍pending，M7未启动。
