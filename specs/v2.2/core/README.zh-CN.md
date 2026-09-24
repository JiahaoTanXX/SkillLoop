# 核心协议与参考判定

本目录是 API 4 的合成规范样例，不是生产系统日志。所有来源认证、角色权限、数据库完整性和真实模型验收必须由部署系统证明；仅重新计算摘要不能把攻击者对象变成可信对象。

## 从哪里读

- [协议 schema](../protocol.schema.json)：44 种核心 envelope 的严格字段；源码 [build_schema.py](build_schema.py) 显式生成它，普通校验不会重新生成期望值。
- [参考函数](../../../scripts/spec_v22_core.py)：事件归约、计划、Gate/CI、权限展开、实际字节补丁、扫描覆盖及执行证明。
- [gate-world.json](gate-world.json)：一个已认证事件→结果→单例归约的最小合成世界，重复数 1 只用于单元反例，不替代首版每例 3 次。
- [gate-authority.json](gate-authority.json) 与 [suite-templates.json](suite-templates.json)：九个权威案例、每例三次、显式计划和合成 CaseResult。
- [required-run-chain.json](required-run-chain.json)：27 条独立合成执行的请求、绑定、证据、结果、ExecutionRecord、完整清单和最终证明；不得向真实 CI 提交为验收证据。
- [execution-chain.json](execution-chain.json)：一个执行链的最小例子。
- [hash-goldens.json](hash-goldens.json)：10 份固定投影及其 JCS 摘要。
- [valid-records.json](valid-records.json)：覆盖全部核心类型的结构正例；不意味着彼此都是同场执行、每个引用都可用于正式晋级。

## 身份与引用规则

每种 envelope 的摘要为 `sha256(JCS({api_major,kind,body}))`，不含顶层 digest 自身。原文件摘要计算实际字节；Policy 的 allowed_actions/bindings 先排序、重复拒绝。CandidateBundle 的 skill_digest 是按路径排序的 `{path,bytes_digest}` 清单摘要，再与 policy/obligation/compiler 摘要一起进入 CandidateBundle envelope。变化传播遵循 PRD §6 的有向无环依赖。

RunResultBody 不持有自身 ExecutionRecord 摘要。`reduce_case` 首先产生 `result_body_digests`；`attach_execution_records` 解析对应执行对象后填入另一个字段 `run_record_digests`。二者不能混用。最终晋级必须解析完整 RequiredRunManifest，保留权威账本中所有实际执行过的重试；`validate_attestation` 从这些结果重新归约案例和 Gate，比较原证明，不能仅验证签名、计数或一个成功 run。

参考函数接收的 `records`、`result_index`、注册表与 GateContext 必须来自可信服务完整索引。caller 不可先筛掉失败再传入；生产索引、来源权限、执行请求和原始证据的交叉认证属于实际验收。`runtime_verified=true` 等合成 fixture 字段仅模拟前置条件成立，不代表本项目已通过平台实验。

## 受限补丁与包边界

只接受精确父 subject 上的 UTF-8 字节区间编辑。允许 SKILL.md 的 frontmatter 之后和已存在 references/*.md；不增加可执行文件。固定 frontmatter 恰五键：name、description、api_major、family_id、profile_id。包最多 32 文件、单文件 4 KiB、总 128 KiB；实际上下文还有独立 token 上限。

每轮重放历史 proposal 验证 before/after 链，按删除字节加新增字节重新计费，同长度替换也消耗额度。两轮累计最多三条路径、8 KiB 修改、相对原提交净增长 4 KiB。policy_only 不得带文本编辑；权限集合重排不是修复；产物 subject 始终采用同一 CandidateBundle 投影。

## 扫描和运行边界

[scanner-profile.json](scanner-profile.json) 冻结 24 项参考覆盖清单。`fixture_only=true` 表明它用于测试：正式扫描器安装必须锁定实际依赖、规则、ARM64 镜像和离线情报，并证明这些 analyzer 的实际完成或注册的不适用依据。`scanner-example.json` 的合成 complete 不能充当离线 smoke。

[单元反例](../../../tests/spec_v22/test_core.py)验证未知投递/策略/效果传播、失败优先、逐 subject 覆盖、权限集合、实际补丁和摘要链。[跨模块检查](../../../tests/spec_v22/test_integration.py)将公开三份 profile 的 15 个实际开发案例转换为核心结构。详细覆盖以统一 verification-report.json 中列出的测试 ID 为准。
