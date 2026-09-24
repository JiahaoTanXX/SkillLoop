# V2.2 规范附件 · API 4

[PRD V2.2](../../SkillLoop-PRD-v2.2.zh-CN.md)与此目录按同一 Git commit 分发。V2.1 的对象和检查保留作历史，不能混用 API 3 和 API 4 的结果。

## 从哪里开始

1. 读 PRD 最前面的单人开发步骤，以及 [user-decisions.json](user-decisions.json) 中已确认的范围。
2. 读 [protocol.schema.json](protocol.schema.json) 和[核心参考说明](core/README.zh-CN.md)，理解输入、事实、结果、Gate 与证明的边界。
3. 读 [两个任务家族](families/README.zh-CN.md)，查看实际 Skill、固定开发用例、人工期望输出和不支持的语法。
4. 读 [运行规范](operations/operations.zh-CN.md)，理解私有题库、撤销、调用、预算、CI 和恢复。
5. 按 [部署验收](deployment.zh-CN.md)在 Spark 上锁定 SGLang、官方 FP8 模型和离线扫描环境。
6. 用 [逐项修订状态](review-resolution.json) 和 [需求验收索引](operations/acceptance.json)核对每个问题的决定、规范、反例和实际运行证据。

## 执行本地规范检查

在独立虚拟环境安装 [requirements-verify.txt](requirements-verify.txt)，然后从仓库根目录运行：

```sh
python -m pip install -r specs/v2.2/requirements-verify.txt
python scripts/verify_specs_v22.py
```

该入口验证结构、事实归约/门禁、权威索引、有限权限、业务金样、操作状态/预算、review 对应关系及文件一致性，生成 [verification-report.json](verification-report.json)。它使用合成参考事实，不启动生产 Agent，不连接 GPU、GitHub 或外部接收端，也不证明实际 OS/数据库隔离。

[probe-migration.json](probe-migration.json) 将原审查 P01–P15 分别对应到 API 4 的语义反例，避免只拒绝旧版字段而没有修正同类逻辑。报告保留实际测试 ID 与输入文件 SHA-256；文件修改后必须重新运行，不能沿用旧报告。

## 规范层级和证据

- JSON Schema 校验类型与字段；跨字段规则、引用真实性和数据库权限必须另外验证。
- 核心 reference 函数给出可执行的状态/判定语义，生产实现必须通过同样合同测试，不能只接受模型自报结果。
- `families/` 的开发 payload 和样例秘密都是公开合成测试数据，绝不作为实际私有 holdout。保护集由已批准规则在运行时新建，原文不进入仓库。
- `operations/` 的预算与竞争模型用例验证规则计算；真正的 SQLite 并发、断电/崩溃、Linux UDS/OCI、模型和扫描器测试仍需目标环境执行。
- 每条 review 的四个状态分开记录。当前未取得实际平台证据的字段必须保留 `pending`，不会因 Markdown 或 schema 通过而自动关闭。
- 机器检查只保证报告中列出的断言；自然语言语义、真实运行和未覆盖输入不在此检查的穷尽保证内。

规范变更要同时更新文档、结构、参考函数、正反例及版本。核心字段/权限/判分语义的破坏性变更升 API major；家族注册表内的新 profile 必须经过能力协商并产生新 registry/config 摘要。所有当前证明都绑定精确配置，不能把扩展能力悄悄加到旧 pass 里。
