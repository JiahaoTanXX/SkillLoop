# V2.1 规范附件（wire API 3）

与根目录 `SkillLoop-PRD-v2.1.zh-CN.md` 按同一个 Git commit 分发；评审或实现时获取整个目录，不能只复制 Markdown 后把缺失相对附件当作已审查。

- `protocol.schema.json`：所有可信模块交接的结构规范；根 oneOf 根据 kind 判别，严格拒绝额外属性。
- `gate-spec.json`：M1 的最低用例矩阵与硬规则配置，规范参考判定在校验脚本中。
- `policy-mechanism.json`：不可被候选修改的全局工具上限、每实例发布上限和事务前置机制。
- `scanner-profile.json`：固定上游 commit 与必要 analyzer 清单；ready 状态不冒充 DGX 安装验收。
- `runtime-profile.template.json`：预算参数和 calibration_ready=false；实际运行前必须填写实测校准并形成新 profile digest。
- `examples/valid-records.json`：各实体、六工具请求/成功返回、四种 CI 状态的完整结构样例，均为合成规范数据。
- 四份独立报告示例：[pass](examples/ci-result.pass.json)、[fail且候选pass](examples/ci-result.fail.json)、[needs_contract](examples/ci-result.needs_contract.json)、[inconclusive](examples/ci-result.inconclusive.json)。每份仍须通过跨字段校验，不能凭自报verdict放行。
- `examples/invalid-records.json`：跨字段反例；错误分为 schema 和 semantic 层，不能仅用 JSON 可解析判通过。
- `examples/gate-cases.json`：Gate 正反例，提交/候选各自输入。
- `golden/orders/`：独立业务输入与规范期望输出；invalid-inputs.json 是 validator 机制负例，不是 Agent 正常用例。
- `review-resolution.json`：V01–V36 的规范位置、反例与后续运行验收；设计修正不等于运行验收完成。
- `verification-report.json`：本次规范校验结果，不是项目安全效果报告。

验证命令（临时或项目独立虚拟环境）：

```sh
python -m pip install -r specs/v2.1/requirements-verify.txt
python scripts/verify_specs_v21.py
```

校验器用 Draft 2020-12 JSON Schema 和 RFC8785，校验对象结构、跨字段不变量、四状态/Gate 反例、策略集合反例、业务金样、review 编号及文档链接。它不是生产运行器，不会证明 OS 隔离、SQLite 崩溃原子性或模型攻防效果；这些必须用 PRD 验收矩阵在实际实现上执行。

## 不由 JSON Schema 单独保证的语义

1. Candidate/Policy/Contract/请求/证明的摘要按 PRD 指定投影计算；存在可信引用与批准有效性由控制面查询。
2. SourceSnapshot/CIResult：git_commit 必须真实 SHA、immutable；local_observed 必须 SHA=null、unverified，不能动态通过。
3. ToolCall：资源 ID 的语法正确不等于被授权；Tool Proxy 核对注册表、socket 身份、run/fence。write 字节限额以UTF-8字节而非JSON Schema字符数判定。
4. GateInput：cases 的 subject 必须等于被裁决 subject，case token 不重复，baseline 单列；不可信的错绑输入在 ingestion 层拒绝，不参与判定。确定的制品篡改由可信证据写 definite_failures。
5. GateResult/CIResult：verdict 必须等于可信 Gate 函数输出；schema 只能检查形状，不能让提交者自报 pass。candidate 非空字段成对出现，内部 subject 一致；M1 promoted 仅指 submitted 自身已通过并完成本地 CAS，不表示候选替原提交晋级。
6. policy 为有效 allow 元组集合，禁止 deny/OR，重复分支拒绝；校验摘要后才能比较子集。
7. RunResult 的有效实际违规不能被不完整的其他字段抹掉；同run多目标不增加独立样本。预期机制拒绝另记，不用 RunResult 冒充正常业务成功。

## 版本与兼容性

文档版本2.1、wire api_major=3。新增核心必填字段、身份/权限/判分含义变化提升wire major；不能靠同一schema版本给不同模块不同解释。未来显示字段应通过经版本批准的可选display_metadata容器引入；本版未开放该容器，因此同样拒绝未知属性。所有对象采用明确的必填+可空规则，nullable不表示字段可缺失。
