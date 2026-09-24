# V2.2 运行、隔离与持续 CI 规范

本附件是待实现系统的规范。`spec_v22_operations.py` 只运行状态、预算与事务顺序的参考模型；真实 SQLite 并发、进程隔离、模型、扫描器和 GitHub 验收均仍为 `pending`。API 4 核心对象以根目录协议为准，本目录专有对象使用 [operations.schema.json](operations.schema.json)。固定配置、状态转换和验收分别见本目录 JSON。

`operations.schema.json` 固定本版配置文件的结构和常量，不能拿它验证任意新部署记录。实际控制消息及管理命令输出使用 [control.schema.json](control.schema.json)，方法与返回实体类型见 [control-methods.json](control-methods.json)；核心编排 RPC 使用核心 schema，二者不是同名的两套任意参数入口。跨类型摘要只能在对应身份有权访问的存储中解析，再检查完整被引用对象；摘要本身不证明来源。

## 1. 一次批准后的持续运行（R07–R09）

管理员首次批准 AuthorizationDomain、任务契约、插件/模型配置和 SuiteFactoryProfile。批准默认持续有效至撤销或语义配置改变；可选人工设定的截止时间必须明确展示。控制器只能在仍有效批准下续租短期执行权限，不能延长已经到期的管理员批准。EvaluationAttestation 有效 24 小时，服务自动在需要使用过期证明时新建续评 campaign；不把历史 pass 改成 fail。

每 campaign 仅评估一个 Skill/profile。去重键为项目、源提交、配置摘要、触发 generation；重复事件返回原 campaign。新提交采用候选、到期续评和配置变更产生新 generation/campaign。候选默认输出补丁 artifact；只有预配置发布器才可创建修复 PR，不自动合并。候选通过不能把原提交的 check 变绿。

finalist 和开发计划冻结后，可信私有 Factory 创建一个新 epoch。它使用已批准模板/变异范围、私有随机种子、独立业务 oracle，检查 schema、真值、注入有效性、目标覆盖和与开发集重复，再提交不可变私有 manifest。生成失败为 `inconclusive/protected_suite_unavailable`，不能用公开测试补齐。私有种子不进入开发日志；公开只提供随机 opaque ref，不公开低熵 payload 的普通 hash。

同 campaign 的 submitted、finalist 和仍合格 active 使用相同保护样例各重复三次；淘汰候选不参加保护。若 submitted 与 finalist 是同 subject，复用同一计划身份，不重复计数。首个 payload 释放前原子登记保护 session；执行键为 `(deployment_epoch,campaign_id,epoch_id,subject_digest,case_ref,repetition_index)`。保护反馈之后不再换候选。明确未投递可按原计划恢复，已投递结果仅可读取，投递状态未知则不完整。新提交和证明续评使用新 epoch，不存在每五次必须人工换题的门槛；配额用于资源接纳。自动轮换不声称无限独立或已证明抵抗长期自适应攻击。

## 2. 真实权限边界和同库撤销（R10–R11、R34–R35）

proxy 独占 SQLite，权威保存有效批准及 trust revision、run 状态/fence、调用登记、工具额度、产物 BLOB/版本、receipt/grant、幂等结果、接收事件和 outbox。控制服务可以保存请求与投影，但必须等 proxy 事务提交后才确认“撤销已生效”。发布事务校验同库状态；撤销先提交拒绝发布，发布先提交保留事实。控制通知丢失按 operation_id 查询，不推断事务是否发生。

可信 runtime/已注册 AgentAdapter 属于可信计算基。模型只产生 tool,args；runtime 分配内部 call_id，持久绑定规范参数摘要、run/fence、response ID 和批次位置。模型原生 tool_call_id 只作关联。每个批次先原子检查额度并预留全部调用；超过剩余额度则整批不执行，记录预算耗尽。批内失败后的调用标 skipped，仍计已预留额度。内部同 call_id 同参数传输重试不增加额度，同 ID 异参拒绝。逻辑新调用即使查询已有幂等结果也消耗一次工具预算。

正式工具 socket 只挂载给可信 runtime，模型进程、scanner、generator、patcher 无此 socket。所有服务以独立 UID、SO_PEERCRED 和注册 run/fence 验证；角色字符串、路径名、manifest 自报身份不能授权。[rpc.json](rpc.json) 固定 RPC 与 UID/方法映射。关键适配器需预先审核注册，不能将任意插件视为不可信却赋予 runtime 权限。

单次控制 RPC 最多等待 10 秒。模型推理、导出和其他长操作先返回 `accepted + OperationTicket`，调用方按该 ticket 查询 `get_operation`；只有 completed 才能取得正式结果引用。ticket 绑定原角色、run 和截止，调用方不能读其他角色操作，重传同 operation_id 不重建作业。取消须先停止新动作，迟到结果隔离；10 秒是控制消息期限，不是把 180 秒模型运行上限偷偷改短。

receipt 的 `issued_at` 必填，TTL 300 秒；expires_at=min(issued_at+300s,run_deadline,effective_approval_lease_expiry)。grant TTL 600 秒，但实际截止还不得晚于 receipt、run 和有效批准租约。时间统一 UTC；超时使用 monotonic。产物版本始终单调递增；写回相同字节仍是新版本，旧 receipt 失效，防止 ABA。批准/租约到期后拒绝新动作，历史已提交事实不消失。

同 key prepare 重传返回原 grant，即使已过期也不续期；模型需新 key 和有效 receipt 重新申请。工具入口先验证当前调用身份/fence，随后同 run/tool/key 查询相同参数历史结果；旧 fence 不允许借重试查询，controller 通过独立只读恢复接口查历史。确定性处理失败缓存该调用结果；明确事务未开始的忙/传输失败可同 call_id 重传；结果未知先查询权威库，禁止盲重发。每 TaskInstance 最多一次新 publication，换 grant/key 不重置；查询既有结果不产生新副作用。

## 3. 生命周期、finding 和历史（R23–R26）

[lifecycle.json](lifecycle.json) 是转换表，每项指定事件、来源状态、下一状态、原子记录、重试资格和预算影响。模型正常停止、无工具最终回复或逻辑预算耗尽且缺必需产物，记已证实 utility fail；provider 超时、lease 丢失、模型/事件 trace 缺失记 unknown/incomplete；二者并存时确定失败仍保留。一次成功 publish 结束业务动作，但 runtime 必须采集本次终止输出并交 final-output oracle 检查合成秘密；不能以“工具已成功”跳过输出通道取证。

每开发计划项最多一次基础设施重试，每 campaign 总共最多两次；仅限明确无有效结果且无未知副作用。保护重试进一步要求可证明 payload 尚未投递。重试是新 run，旧记录不可覆盖；已确认违规/业务失败不能重试成通过。取消后晚到 scanner/模型输出隔离归档，不再修改正式计划、结果或发布资格。机制测试独立 MechanismTestResult，不混用 Agent RunResult 枚举。

finding 分离 verification 与 disposition。`not_reproduced` 不是误报/修复。动态 confirmed 的修复要求原攻击、变体和正常回归；只有完整确定性策略覆盖证明才能记预防性 mitigated，未复现不能增加真实漏洞修复数。高/关键/未知未决阻断；低/中静态 open 可 warning。依赖风险超出可修补范围转 manual_action_required。管理员可依据证据确认有限期误报，不能覆盖实际禁止 effect。规则与动态目标/静态检查/unsupported 的映射由批准注册表维护，未知规则保守未决。

关键历史是项目跨 campaign 的已证实失败，按 family/contract/objective/oracle 版本分区；“单 campaign Gate”不禁止读取历史。旧案例经兼容映射继续必测，未知兼容性阻断；模型变化不自动使历史失效。移除只允许管理员依据等价合并、明确不适用或项目停用批准，保存理由与证据；预算不足不能删难例。超容量可提高批准预算、迁移/归档确已不适用历史，否则诚实不完整；本版不伪称无界历史可在有限预算中完成。

## 4. 可执行计划与资源预算（R25、R27–R29）

一份 profile 基础 5 dev + 4 protected case，每 case 三次；每完整 subject 为 27 runs。计划是显式 `(subject,case,repetition,phase)` 项，不做 subject×全部案例的隐式笛卡尔积。淘汰候选没有保护必测项；后发现案例不追溯给已淘汰候选，但纳入 submitted/finalist/active 的最终必测矩阵。新增计划只能追加带理由 revision，不能删已经失败的证据。

[budget-plans.json](budget-plans.json) 给出无 finding、一 finding、两轮修补、active、一重试、历史临界和超额等代表矩阵。每项由展开后的运行条目计算 runs、tokens、超时和磁盘；额外扫描、辅助生成/诊断/修补、warmup、数据库/WAL 和终止落盘均预留。128 victim attempts、8 小时是接纳上限，不是测得吞吐；正式运行必须同时满足真实校准 profile。不可满足的计划启动前拒绝，新增 finding 不够预算则不完整；不能抽掉必要测试。模型输出或 trace 超限明确中止，不静默截断。

当前指定模型 Qwen/Qwen3.8-27B-FP8，首选 SGLang 0.5.19/CUDA 13/ARM64，native tool parser qwen3_coder、reasoning parser qwen3，thinking 开启；上下文 16,384（含预留输出 2,048），并发 1，不加 draft 模型。实际权重/tokenizer/template/镜像摘要和源 FP8 校准尚未取得；不能用 q8_0 或 MLX mxfp8 替换。KV cache 精度独立记录，不由源权重 FP8 推定。角色切换先清除共享状态/缓存或重启隔离实例；没有可证明隔离则保护不可启动。

实际 ModelConfig 记录精确采样、seed 支持/返回版本和后端非确定性。配对运行按案例与重复序号交替 subject 顺序，固定在计划中；warmup 独立计费，不纳入成功率。首次平台 spike 必须在重工程之前验证四工具正常路径、最长输入/Skill/reference、拒绝恢复及日志，记录内存/token/耗时。扫描器需锁定 ARM64 安装镜像、Python/传递依赖、YARA、规则和离线情报摘要；真实离线正常/可疑/缺情报三类 smoke 保存 stdout/stderr/raw JSON。无这些证据保持 readiness pending。

## 5. 可见性、CI 与操作命令（R08、R36–R38）

[visibility.json](visibility.json) 固定实体投影，隐藏结果索引不是可下载 URL。日志错误不能包含隐藏内容。公开开发材料、私有保护材料和控制面凭据使用不同目录/UID/socket；开发角色没有解析 protected opaque ref 的 API。

[cli.json](cli.json) 固定各命令参数、stdout 类型、退出码和副作用。stdout 为一份严格 JSON，诊断走 stderr；相同 operation_id/参数返回同对象，异参 conflict。scan 可无契约并返回 ScannerReport；只有 evaluate 产生 CIResult。评测四状态为 0/1/3/4；语法或无效引用 64，无权限 77，I/O 74，暂时拥塞 75。review-finding 只能在 admin namespace。

`evaluate --repair-rounds=0|1|2` 冻结本场允许轮数；默认 2。`harden --campaign --parent-subject` 只在未 freeze 的开发阶段提交一轮提案/应用，返回 `HardenResult`，复用本场剩余预算，不创建第二次保护查询。两个命令的 verdict 退出码一致，harden 的 pass 仅说明本轮开发结果，不能用它直接晋级或发布 GitHub 绿色检查。正式通过必须由完整 evaluate 的 CIResult 给出。

真实 GitHub 集成采用受控服务轮询 GitHub API，固定批准的 GitHub App 安装、仓库和配置；不依赖公开 webhook。只读 PR/fork 精确 head Git 对象，不执行 PR workflow、hook、包脚本或构建脚本。App 默认 contents:read、pull_requests:read、checks:write；可选开 PR 发布器独立增加权限。Checks 名称 `SkillLoop / security`，绑定可信 App ID 和精确 head SHA。pass→success；fail→failure；needs_contract→action_required；inconclusive→failure，不能用 neutral/skipped 误放行 required check。旧 generation cancelled，任何新 head/config 都要新检查。续评、force-push、重放事件和乱序结果均经持久 generation 控制。本地 Registry CAS 不声称与 GitHub 跨系统原子。

人工运维提供 inspect、export、archive、restore。接单预留活动作业、扫描器、数据库/WAL 与紧急记录空间；队列最多16，满返回 busy 不丢事件。归档先撤销依赖其在线证据的资格，验证导出摘要再删除本地非活动记录；不是自动 GC。DB 损坏停止新动作；恢复备份必须建立新 deployment_epoch，旧 grant/lease/attestation 全失效。完全磁盘硬故障可能无法写失败记录，此时非零进程退出和外部心跳告警为最后证据，不承诺凭空落盘。

## 6. 验收和可信限制（R40、R42）

[acceptance.json](acceptance.json) 将 review/需求映射到输入、命令、期望事件、环境和证据路径。reference_assertion 仅说明纯函数/结构反例通过；Linux 隔离、SQLite 竞争/崩溃、真实模型和 GitHub 均为 runtime_pending。不得将参考事务顺序模型报告成真实数据库测试。

宿主 root、内核、管理员及批准的 compiler/oracle/runtime 属于可信基；内核逃逸、恶意管理员和任意恶意插件不在本版保证范围。[runtime-profile.json](runtime-profile.json) 固定 worker 的 CPU/内存/PID/fd/tmpfs/UDS 限额和网络/提权限制。Linux 目标环境必须分别测合法调用和跨角色访问拒绝；服务端检查消息长度与截止时间，不能只依赖容器配置。

工程验收、跨家族业务可用和修补效果分开。三份 Skill 各自 campaign 跑完固定三次重复，不能以 27 次有限样本声称普遍安全率。实际效果零则如实记录；自然漏洞、utility 劫持恢复、final-answer/mock-channel 泄漏和平台机制收益分别列举。
