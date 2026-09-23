# SkillLoop PRD v2.0 工程审查

审查日期：2026-09-23。原文：[用户提供的 v2.0](/Users/jet/Downloads/SkillLoop-PRD-v2.0.zh-CN.md)。审查快照：[440行完整副本](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md)，SHA-256：`cff10b800fc16a6bcab6201045cdfe6937c5a27c8d72bbd71d8f4f8dca51941f`。本文L行号指该快照。上一轮审查：[v0.7报告](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v0.7-review.zh-CN.md)。

**结论：v2.0已经解决许多上一轮的概念性缺口，但仍不能标为 Ready for Implementation。** 这次主要问题是：新增规则之间仍有直接冲突，一些声称已经规范化的接口只有字段清单或未提供的附件，部分安全保证超出了所描述算法实际能证明的范围。

本轮列出 **36项主要问题：7项阻断、27项高优先级、2项中优先级**，另附字段级收口清单。七项阻断为V01正式schema交付、V02权限表冲突、V03Gate完整规则、V04有效策略包含、V05grant获取协议、V06实际隔离拓扑、V09组合候选身份。数量不是实现漏洞计数，也不是对“所有问题已穷尽”的保证；每条按已读文档给出明确反例或缺失契约。

用户新约束优先于文档旧排期：**4名开发者，3天；DGX和本地模型已跑通。** 原文“一周P0”不能直接平移为三天承诺。代码现状、SkillSpector安装状态、四人的专长未确认。本次不假定项目从未写过代码，也不把未展示的实现当作已完成。三天计划另见 [工作安排](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-three-day-plan.zh-CN.md)。

这是设计审查，未运行项目实现，也未连接DGX。文档中的“必须”和§18自评是审查对象，不是本次自动认可的事实。级别：**阻断**＝开工冻结前必须决策；**高**＝相关模块实现前必须收口；**中**＝对应版本验收前必须收口。每项给出反例、建议和关闭证据。

## 一、必须先定下来的规则

### V01｜阻断｜正式schema与四状态样例未随本次材料交付

**原文：** [§5 L97–112](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:97)、§14 L276–300。

- 文档说正式类型以 `specs/ci-result.schema.json` 为准，且四个完整样例已经固定；在本次文件所在目录及当前工作区，五个对应相对路径均不存在。可能在未提供的仓库中存在，不能据此断言整个项目没有，但目前无法审查它们与正文的一致性。
- 同时写“字段不可按状态缺失”，又要求实现时继续扩展schema增加适用性、逐例结果等核心字段。它们不是可由四名开发者各自推断的显示字段。
- **建议：** 第一天第一小时确定唯一规范仓库、schema版本和附件commit；至少补足 TaskInstance、ToolCall、RunResult、PatchCandidate、GateInput/Result、CIResult、Policy/Receipt，并生成四状态有效/无效样例。未写完的接口不要标“已固定”。
- **关闭证据：** 同一schema校验全部样例，A/B/C/D四个工作流均以它生成或验证数据；缺关键字段和非法枚举明确失败。

### V02｜阻断｜CI服务能否批准契约、修改Gate，前后直接冲突

**原文：** [§4 L93](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:93)、§16 L327–335。

- §4允许“项目管理员或CI服务身份”批准契约哈希、调整GateSpec；§16明确CI service对这两项为拒绝。两种实现的信任边界完全不同。
- **建议：** 以§16较小权限表为唯一来源：管理员确认契约/修改Gate/批准例外，CI只在已批准域内创建实例grant、执行判定和满足条件的晋级。同步删改§4的扩大授权句。
- **关闭证据：** 同一个CI身份调用确认契约、修改Gate均被拒；在批准域内申请任务grant成功，越域失败。

### V03｜阻断｜Gate有优先表，但适用集合、绝对门槛与对象作用域仍未固定

**原文：** [§12 L239–250](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:239)、§11 L235。

- “首次接入满足绝对正常任务与安全标准”没有给具体标准；哪些正常case关键、需要几个case、Attempt Rate是否阻断、低/中级已实现违规是否阻断，仍未唯一规定。§9仅允许无已证实违规的低/中open做warning，§12却只把高/关键违规列为确定失败。
- 必须限定证据的bundle作用域。提交版曾泄漏是修补收益证据，不应让候选因作业中“任一已证实违规”永久fail；但候选自己的有效违规不能被重试覆盖。
- “active 100%、candidate 75%不可晋级”要求整体能力不退化，正文硬规则主要写关键逐例；若下降发生在非关键case，尚缺唯一裁决。
- **建议：** 固定 GateSpec：必要case清单、critical来源、每目标severity、首次绝对阈值、逐例与聚合条件、改善声明条件、候选与提交各自证据集合。三天版建议所有选定业务case都必须通过，所有已实现禁止副作用都阻断；这是收窄配置，不是普遍标准。
- **关闭证据：** 首次无active、非关键case退化、低级实际违规、提交失败但候选通过、无适用用例五种场景都有确定结果。

### V04｜阻断｜策略包含算法没有处理deny，可能错误证明扩权为收紧

**原文：** [§8 L146–150](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:146)。

- 文法允许deny，算法却只描述新旧允许分支的元组、phase、max_calls与receipt比较，没有定义allow/deny优先级，也没有将deny纳入有效权限归一化。
- **反例：** 旧策略 `allow read {A,B}` 加 `deny read B`；新策略只保留allow。允许分支逐条完全相同，但删除deny后实际新增读取B的能力。
- “允许序列子集”的声明还需固定状态机、共享计数器与分支配额语义。两个各限1次的分支是否合计允许2次，不能只逐行比较max_calls。
- **建议：** 三天版采用无OR的具体动作集合＋固定前置条件＋单一全局计数器；deny优先或干脆禁止显式deny并用默认拒绝。先计算有效允许集合再比较。更一般AST的序列包含证明延期。
- **关闭证据：** 删除deny、重叠分支、分裂配额、撤去receipt和新增目的地等反例全部不获subset_proved。若保留通用DSL，必须附精确定义和算法，而不是只列语法名字。

### V05｜阻断｜Agent必须提供grant_id，但取得它的合法路径没有定义

**原文：** [§7 L126–138](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:126)、§8 L154、§13 L262。

- publish要求grant_id，工具表没有获取动作授权的接口；控制面何时知道产物hash、实际参数并签发grant也未定义。若在任务开始时就签发完整动作摘要，产物尚未生成；若随后由控制器自动补上，需要描述这个绑定协议。
- 不可读“批准记录/密钥”应与可使用“不透明grant引用”区分。权限结果 `needs_trusted_approval` 在无人值守CI中是暂停、等待、拒绝还是输入缺失，也没有生命周期。
- **建议：** 预批准任务范围与一次动作凭证分开。三天版由controller基于已批准范围、实际产物和动作生成引用，经可信工具响应/任务控制元数据交给Agent；引用不能授权超出批准域的动作。摘要排除其自身grant_id和可循环字段，写明idempotency_key是否纳入。
- **关闭证据：** 从空会话完成一条合法发布，不需要模型猜ID或填写approved；缺授权时不会永久挂起，也不会偷偷由模型升级权限。

### V06｜阻断｜权限域表仍与mock写权限、网络隔离和模型可见性存在落地缺口

**原文：** [§4 L80–93](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:80)、§16 L337。

- dev-runner写独立mock世界，但接收事件/receipt同库、只有可信代理可以产生。若runner能直接写该库，就能绕过代理伪造证据；若只能写工作产物，必须明确是哪一个存储域。
- Unix用户/文件权限解决文件访问的一部分问题，不能单独证明默认无外网或不同挂载可见性。必须指定实际使用的namespace/容器/防火墙或等效机制及权限，不能把“六身份”当实施完成。
- 统一model-gateway会接触开发、保护和补丁prompt；其日志、请求关联、错误转储不得成为保护数据旁路。六身份表没有明确攻击生成器和diagnoser归属。
- **建议：** 交付实际拓扑与部署脚本。mock接收/receipt由proxy独占数据库，runner只能RPC调用；写产物另隔离。为每条跨域RPC鉴别调用身份和run绑定；统一gateway禁正文日志或分域存储。
- **关闭证据：** 每个worker实际尝试写receipt、读保护数据、调用代理管理接口、访问外网和模型管理端点均被拒；合法推理与工具请求通过。controller/proxy本来需要控制面访问，拒绝测试必须按角色期望执行，不能套同一禁读模板。

### V07｜高｜保护评估器只输出聚合摘要，不足以执行逐例防回归

**原文：** [§10 L225](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:225)、§11 L235、§12 L248、§13 L261。

- 要求active与finalist在同suite逐例比较，但保护评估器只向Gate返回聚合原因和证明摘要。active过A不过B、candidate不过A过B，聚合相同但关键A回归；普通统计摘要无法判定。
- 保护用例对patcher保密，不等于对可信Gate也必须隐藏所有可验证逐例事实。
- **建议：** 二选一：Gate在保护域内执行逐例比较，只向外输出签名判定；或传给Gate不可反推payload的case token＋critical＋结果矩阵。定义active/candidate配对关系和缺测判定。
- **关闭证据：** A/B交换成败必失败，且patcher与共享artifact不能读取逐例payload。

### V08｜高｜canary与禁止目的地“永远不可见”会使部分攻击无法成立

**原文：** [§7 L126](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:126)、§8 L152、§9 L197、§13 L260。

- 隐藏canary字节只由Oracle持有，与模拟未授权读取返回秘密、或合法输入含敏感片段的泄漏测试不一致。Victim若任何时刻都不能接触canary，就不可能真实复制它；测试可能只验证“没有秘密可泄漏”。
- 禁止目的地具体ID也对攻击器和Victim全隐藏，但错误发布攻击需要能提出一个已知或自行构造的模拟目标；工具只接受受绑定ID，攻击可达性需说明。
- **建议：** 区分“不可获得隐藏评分清单”和“通过正常数据/成功越权读取而看见测试秘密”。资源定位/非授权sink可以公开或由攻击者生成，秘密内容和成功谓词不预先交给攻击器；runtime暴露是被测事实，不应被prompt审计误拦。
- **关闭证据：** 一个机制夹具能产生真实合成泄漏并被Oracle检出；strict路径阻止同目标；失败不是因为攻击者根本无法表达目标。合成泄漏夹具不冒充P0自然漏洞发现。

### V09｜阻断｜策略候选不改变文件时，“空补丁”与版本身份存在冲突

**原文：** [§5 L101、109–110](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:101)、§10 L213–223、§12 L250–252。

- 允许策略义务修补，但文件补丁为空不计修复；纯策略加固有实际意义，却可能被误拒绝。SkillBundle主要绑定文件树，PolicyBundle单列；文件相同、策略不同的两个候选如何获得不同candidate身份，尚未明确。
- 要求“相同候选重新提交后验证”，但编译策略在受保护控制面，不能由普通PR写入；新commit如何选择已批准policy候选没有协议。
- **建议：** 定义 `CandidateBundle=(skill_digest,policy_digest,obligation_digest,compiler_digest)`，空指组合无变化，不只文件diff为空。重新提交时关联已批准候选引用，CI重新验证其组合；单独提交相同Markdown不得自动继承另一策略的通过。
- **关闭证据：** 同Skill两policy有不同候选和证明；纯策略修补可被如实标注；政策丢失/替换后的新提交不能冒用原证明。

### V10｜高｜“恢复授权”可能扩权；strict模式下策略修补的可改进空间要明确

**原文：** [§8 L148](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:148)、§10 L209–215、§15 L310–317。

- 诊断建议“为被错误阻断的合法路径恢复授权”，但自动补丁只允许单调收紧。相对当前父候选放宽一个被误收紧的动作，按现规则也是扩权，即使仍在管理员批准的原始上限内。
- strict路径已强制合法资源、目的地和完整验证，三个义务在不少配置中本来就成立；不能预设再编译同一条件会带来安全提升。P0又不含宽权限消融。
- **建议：** 区分文本fallback恢复业务、丢弃失败候选回到已批准parent、提出新的更少收紧候选、真正提高权限。三天版只做前两类，不自动恢复权限。效果展示优先选择确实观测到的功能恢复/更少违规尝试，不能预设真实泄漏修复。
- **关闭证据：** 过度收紧的候选失败后，控制器不会以“恢复业务”跳过包含检查；若无改善，输出拒绝或机制结果。

### V11｜高｜历史全量分批到底是P0还是P1，仍直接冲突

**原文：** [§11 L229–233](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:229)、§15 L312、§17 L356。

- §11要求PR覆盖全部相关关键历史，超40run按同suite分批；§15把历史全量批处理列P1；“唯一FR表”把历史/夜间FR-11整体列P1。
- 若三天内按P1延期整个模块，就无法满足P0的关键历史门禁；若实现完整批处理，排期明显增大。
- **建议：** 拆ID：P0在单作业内运行有界关键历史，超容量返回inconclusive；P1实现跨作业批次聚合与夜间非关键全量。三天计划采用该裁剪，明确不称原文完整P0已完成。
- **关闭证据：** 关键历史数量超限时不静默抽样、不pass；范围表、FR表、预算章节一致。

### V12｜高｜case身份与run身份混在一起，配对、凭证和重复统计会冲突

**原文：** [§5 L103–108](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:103)、§8 L152、§9 L203、§11 L235。

- TaskInstance含run_id，EvaluationCase含task_instance_digest；但旧新版本要求相同TaskInstance配对、receipt又要求跨run不复用。若复用实例，两个run身份错绑；若每次生成实例，case digest变化，配对键不稳定。
- 多objective“同run有独立case键”与按case统计需要明确重复/关联关系；同campaign多次重复遇到一次成一次败，怎么归约一个case没有定义。
- **建议：** 固定CaseTemplate/fixture作为配对身份，每次执行生成独立TaskInstance与ExecutionRun；增加 `paired_case_id/repetition_index/attempt_index`。凭证始终绑定具体run；指标声明case-level如何归约重复，另存run-level原始值。
- **关闭证据：** 两bundle×同case×两重复得到四独立run、相同配对键；凭证跨run失败，统计不把同run多finding当独立样本。

## 二、接口、事务、预算与判定问题

### V13｜高｜EvaluationFingerprint包含执行后才知道的内容，不能直接作为运行前缓存键

**原文：** [§5 L110–112](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:110)、§14 L302。

- 实际截断结果、实际授权事件序列、evidence_index、verdict等并非都能在执行前确定；把“上表外”理解为纳入全部字段，还可能出现证明/指纹循环引用。run专属grant和任务ID若纳入键，每次运行又必然不同。
- **建议：** 分 `EvaluationRequestFingerprint`（已冻结输入、计划、语义授权）与 `ExecutionRecordDigest`（实际事件、截断、输出、实例ID），Attestation最后绑定两者。三天版暂不做执行缓存，保留指纹和历史引用即可；不把缓存关闭误解成省略版本绑定。
- **关闭证据：** 运行前能独立计算请求指纹；执行记录改变不改输入键但使证明变化；授权撤销仍实时生效，无自引用哈希。

### V14｜高｜资源义务没有覆盖validate/publish；reference读取也缺绑定来源

**原文：** [§7 L128–138](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:128)、§10 L221。

- `deny_unapproved_resource`绑定read/build/write，未包含会读取产物的validate/publish。其他强制层可能已经限制它们，但文档必须证明每个入口都做了相同资源约束，不能靠推测补齐。
- read可读包内reference，而所有资源必须在TaskInstance绑定；谁把Skill resource纳入绑定、如何与业务input区分、恶意包能否申请控制资源没有规定。
- **建议：** 工具注册表声明每个参数的resource类别与读写作用，通用入口对全部工具应用任务/资源绑定；reference由loader生成独立只读命名空间，不能由Skill自报授权。
- **关闭证据：** validate/publish另一任务的合法artifact被拒；包内reference合法读通，但相似ID不能访问控制面或任意文件。

### V15｜高｜SQLite原子发布尚未覆盖artifact字节及可变版本指针

**原文：** [§7 L133–136](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:133)、§8 L152–161。

- 同库保存摘要和接收事件不自动保证实际artifact字节存在且持久。产物若在文件系统，数据库先commit、文件未落盘或GC删除后，可能有“成功发布”事件却没有可重放内容。
- 当前产物版本在数据库外更新时，“重读版本”与提交之间仍有竞争。文档仅明确发布事务，build/write和validate与版本索引的事务边界未定。
- **建议：** 三天版把小产物字节、版本、receipt、grant和模拟接收事件一起放proxy拥有的SQLite；或先持久化不可变内容寻址对象，再在事务里更新指针，且GC尊重引用。明确journal/synchronous等持久化配置，模型调用不得占用写事务。[SQLite原子提交说明](https://www.sqlite.org/atomiccommit.html)
- **关闭证据：** write与publish并发、数据库commit后进程终止、重启后取回产物均满足事件与字节一致；不存在发布了另一版本的情况。

### V16｜高｜幂等结果与消费后的权限、配额检查顺序未固定

**原文：** [§7 L138](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:138)、§8 L154–161、§11 L229。

- 成功后grant已committed，若重试先检查未消费grant就会拒绝，而规范要求同key返回旧结果；若先按key查结果但不校验调用身份，又可能泄露其他任务的结果。
- denied/格式错误消耗Agent调用数；工具自身幂等重试是计新调用、只计模型请求，还是不计副作用预算，需要区分。`reserved`在独立事务可见还是仅同事务内部状态未说明。
- **建议：** 顺序固定：认证actor/run→查task-scoped幂等记录并验证参数→命中则返回旧结果→新动作才检查当前授权与quota并提交。Agent发起的新调用消耗调用预算，副作用额度只在实际新提交时消费；内部传输重试另计。
- **关闭证据：** 相同key不同任务无法读取结果；成功后相同参数重试返回旧publication；新key复用grant失败，配额不超用。

### V17｜高｜签名记录、证明有效期和可信身份还缺协议字段

**原文：** [§5 L102、110](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:102)、§9 L174、§12 L252、§16 L325。

- 文字要求管理员签名、证明未过期，Attestation字段却没有issuer、issued_at、expires_at、签名/数据库授权记录标识；TaskContract含approval_record，其hash与approval绑定contract hash可能循环。
- 六OS身份如何在RPC中认证、如何区分同host不同job，密钥存哪、撤销版本如何查询仍未定。
- **建议：** 三天同机版采用可信服务＋OS认证socket＋受保护审批记录ID即可，不临时造一套跨机签名体系。契约body先哈希，approval另绑定body digest；证明显式有效期/issuer/current revision。若必须签名则固定算法、key_id及验签位置。
- **关闭证据：** 伪actor、过期证明、换contract body、无审批记录均拒绝；不存在自己包含自己签名/摘要的序列化过程。

### V18｜高｜不可变ExecutionPlan、复扫新增计划与跨批Gate尚无共同状态机

**原文：** [§10 L207–209](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:207)、§11 L229–233、§13 L264。

- 第一次victim前不可变计划不能提前知道全部自适应新攻击/复扫finding；需要不可变revision而不是覆盖。强制重放若“预算内”无法执行，哪个计划判缺测也需固定。
- 同一head每epoch一次保护campaign与跨批、环境重试、重启续跑如何计数？新的job能否获得新的40run预算并无限绕过总上限？“同一Gate窗口”的时长与冻结点没有定义。
- **建议：** `campaign_id→plan_revision→batch_id→run_id`分层；新revision追加，父子关系和全campaign预算不变；一次保护campaign可恢复未完成执行，但不能产生新候选。三天版不实现跨批，单作业放不下即inconclusive。
- **关闭证据：** 新风险没有被计划遗漏；重启不重置预算/保护次数；重复新job不能无限消费同campaign资源。

### V19｜高｜合法最大输入、12次调用、上下文和90秒超时没有同时满足的保证

**原文：** [§6 L118](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:118)、§7 L126–142、§11 L231。

- 每次读取16KiB，两张64KiB表完整读取需要8次；说明再读一次，加build/validate/publish共12次，已经没有一次拒绝恢复空间。若说明也需分页或reference必读，就超过12。所谓正常5–6次只对小文件成立。
- 两份大CSV、Skill正文、reference上限与16384-token上下文可能冲突；输入上限不等于模型能完整看到。90秒须容纳多轮推理和工具调用，模型“已跑通”不代表该负载能达标。
- 40×90秒为60分钟，大于45分钟job上限；不是逻辑错误（硬墙钟可提前终止），但不能承诺40条最坏运行都能完成。2MiB×40也超过64MiB日志上限，需预留和预测。
- **建议：** 三天profile用小fixture（建议每输入≤4KiB、≤20行）并实际预估prompt tokens；run timeout由真实完整轨迹校准后冻结，计划按总墙钟预留。若build读取全输入、模型无需全读，要写明并重新定义动态暴露覆盖。
- **关闭证据：** 最大支持样例＋一次非法动作后的恢复实测完成，超过支持范围明确拒绝；执行计划能在墙钟内完成或提前诚实报容量不足。

### V20｜高｜无限整数金额与RFC8785数字规范不兼容，输出尺寸也未受推导约束

**原文：** [§5 L97](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:97)、§7 L140。

- amount_cents只要求非负十进制整数，没有上限；JCS基于IEEE754 double的数字表示，大整数可能无法保持精确跨实现值。Python任意精度整数不能自动解决输出/哈希互操作。[RFC8785 §3.1](https://www.rfc-editor.org/rfc/rfc8785#section-3.1)
- 100个很长的name在输入64KiB内，输出还加字段名/计数，可能超过64KiB产物限额。ID/name最大长度、CSV BOM/换行、前导零金额、Unicode数字和控制字符规则没有完全规定。
- **建议：** 为每金额和所有聚合结果规定安全整数上限（例如总和≤2^53−1），或统一十进制字符串；拒绝不合规范数字。冻结字段长度、CSV接受子集、产物尺寸与末尾换行计hash规则。
- **关闭证据：** 2^53边界、超大和、长名字、非ASCII字符、BOM和非法金额金样得到同一结果；哈希不因不同JSON库而漂移。

### V21｜高｜第二个Skill和声明式表格插件仍不足以直接实现

**原文：** [§7 L140](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:140)、§15 L315。

- returns-audit只给业务名称，未给列、退货/订单关联键、重复/部分退货、累计退款超原订单、金额异常定义、输出schema。开发者无法写唯一正确的oracle。
- 要同一个预冻结插件支持列映射、join、filter、aggregate及输出schema，相当于增加一门小型关系变换DSL；其语法、类型、null、排序、溢出和错误规则未提供。不能把这个额外工程量隐在“第二Skill只改配置”里。
- G2 Markdown标题锚点/链接规范也需确定解析器、重复标题、相对链接、代码块、HTML和锚点生成方式；不是给一个family_id就能互操作。
- **建议：** 三天先交付一个固定orders契约和两份真实不同流程/防护写法的同契约Skill，明确低于原定orders/returns G1证明要求；若保留完整G1，首日上午必须写完returns契约及有限操作schema，预留开发工时。G2延期。
- **关闭证据：** 独立开发者只看契约就能产生相同returns/Markdown索引输出；第二接入没有暗改factory/oracle。

### V22｜高｜无契约扫描与本地导入CLI没有贯通，unsupported的外部映射未统一

**原文：** [§1 L33](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:33)、§6 L116–118、§7 L124、§14 L272–300。

- 支持缺契约时先静态扫描并返回needs_contract，但唯一import命令强制approved-id，evaluate要bundle；没有明确允许未批准导入或单独scan路径。
- unsupported_profile/unsupported_execution/unsupported_context/unsupported_capability出现多处，有时像最终状态，而外部只有四verdict。是非评测参数错误64，还是inconclusive/needs_contract？本地目录没有commit时，schema示例的40hex SHA怎样表示？
- **建议：** import允许不传契约，只创建unapproved snapshot；evaluate缺契约仍可扫描。外部verdict只有四个，unsupported均为明确reason并映射；无git来源用null＋source_kind，禁止伪造SHA。
- **关闭证据：** 一条无契约本地目录命令能产出扫描证据和needs_contract；脚本依赖、超上下文与未知插件各有确定退出码和结果样例。

### V23｜高｜Finding重新打开规则过宽，策略缓解可能每次复扫都被撤销

**原文：** [§9 L166–184](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:166)。

- 策略缓解通常不删除危险文字，扫描器会继续观察到相同风险；“重新观测到同逻辑风险”即自动reopened，可能把已经有效的mitigated_by_policy每轮打回。需要区分持续静态观察与新的突破缓解证据。
- 前文fixed必须结构证据＋动态回归，后文static-only允许静态证明或人工处置；需按verification_method规定不同关闭路径。修改任何关键包内容就使例外失效，也可能导致无关补丁反复人工审批。
- **建议：** 新观察绑定旧finding后先检验缓解适用域、policy digest与回归证明是否失效；仅静态持续命中不等于缓解被突破。例外失效依具体证据/范围变更，保守失效可用但须明确人工成本。
- **关闭证据：** 文本不变而策略仍阻断时状态稳定；真实副作用重现必reopen；静态依赖风险可按正确分支关闭。

### V24｜高｜Robust Utility漏掉“无违规副作用”，指标发生语义退化

**原文：** [§11 L235](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:235)、§9 L201。

- v2.0定义为攻击case中utility_success比例。任务正常完成并同时泄漏的运行会记robust_utility=1；上一版要求正常完成且无违规。Gate另检查安全，并不能消除报告和优化排序的误导。
- objective_success可观察“授权决定”，但realized ASR与attempt成功不能混用；若目标是引出被拒绝请求，应明确这是attempt objective，不能称系统被攻破。
- **建议：** 恢复 `utility_success && !any_security_violation` 为safe robust utility；原公式改名attacked_task_completion。为每objective登记成功层级attempt/effect，ASR分别出数。多重复的归约依V12执行。
- **关闭证据：** 业务成功但泄漏的样例safe robust utility为0；被拦截不计effect ASR；案例级和run级分母各有手算校验。

## 三、集成、证据与长期运行的剩余问题

### V25｜高｜扫描器可用profile仍未落到实际版本与离线操作

**原文：** [§3 L65](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:65)、§6 L120、§17 L360。

- v2.0要求记录扫描器commit，但没有选定具体发行/commit、required analyzer集合、实际JSON样例。适配器“SkillSpector及最小规则”的关系不明：最小规则是补充还是扫描器失败时的替代？失败不能靠替代规则输出完整扫描通过。
- “OSV默认关闭或固定离线快照”不是现成可用接口的证明。核查先前固定版本上游说明，`--no-llm`仍可能查询OSV，离线时退回内置列表；不能用这个参数宣称网络已禁用。[上游说明](https://github.com/NVIDIA/SkillSpector/blob/dabf4759a189be0f0428a2f7a472b3d5bdad1fe6/README.md#trust-model-and-data-egress)
- 退出0但JSON partial、退出0但有active finding、超时被杀且已输出部分报告，需列为完整映射测试。0不等于无发现；coverage按必要analyzer定义，不能只看全局标签。
- **建议：** 首日上午跑真实扫描spike，冻结一个可用profile和原始fixture；离线由网络边界保证，缓存/情报版本明确记录。若不能跑通，保留inconclusive并展示其余闭环，不能把mock扫描当真实集成完成。
- **关闭证据：** 真实正常包、危险包、partial/错误三种报告可解析；无网络出口，模式与报告一致。

### V26｜高｜lstat前后比较不等于安全打开，也不保证整个目录同一时刻一致

**原文：** [§6 L116](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:116)。

- 在lstat与open之间替换目录组件/链接，可能让复制代码先读取边界外文件，再在事后检测变化；仅检测到后拒绝不等于从未读到秘密。逐文件稳定也不能排除跨文件A旧B新的混合快照。
- **建议：** 对可信git来源优先从指定commit物化不可变tree；本地目录用目录fd相对打开、no-follow/beneath约束和打开后的fstat，文件内容只从同一fd读取。定义“稳定扫描窗口”或拒绝可变源，而非声称任意活动目录的原子快照。[Linux openat2路径解析约束](https://man7.org/linux/man-pages/man2/openat2.2.html)
- **关闭证据：** 恶意并发换链接不会读出边界外字节；混合版本目录明确拒绝；source SHA与最终tree对应。

### V27｜高｜工具表还不是完整协议，若干边界决定正常任务能否执行

**原文：** [§7 L130–140](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:130)。

- write首次创建的expected_version是null、0还是特殊常量？build是否可覆盖已有output、需不需要expected_version？read按字节分页切开UTF-8码点时如何返回合法bytes_utf8？offset可否负数/越界？重复input_ids、transform_id白名单、失败验证是否返回receipt_id，都没定义。
- grant_id是公开引用，但返回给模型的receipt是否泄漏其他隐藏检查信息，需要固定公开错误原因粒度。多个工具调用同一回复中前一个失败后，后一个继续还是整批终止也需规定。
- **建议：** 每工具补严格请求/返回schema＋前后状态表。三天版可禁模型分页/限制小文件、禁止build覆盖、write仅有明确expected_version；未知字段和未知transform拒绝，不用默许默认值。
- **关闭证据：** 首次写、stale写、UTF-8边界、失败validate、多调用混合成败、重复input与未知transform都有唯一结果。

### V28｜高｜Skill文本低信任与可执行指导角色之间缺少明确prompt协议

**原文：** [§2 L37](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:37)、§6 L118、§7 L126、§13 L264。

- Skill需要指导执行，不能把它当完全忽略的数据；同时它不能覆盖可信任务/工具规则。以哪个message role加载、如何标记来源、工具结果中的结构化字段与攻击槽位怎样分离、context超限后何时拒绝未说明。
- 按需references64KiB与禁止静默截断需要运行时token预检；“自动检查prompt不含禁止字段”不能简单搜索敏感字符串，否则V08真实暴露测试也会被拦。
- **建议：** 冻结system/task/skill/resource/tool-result模板和role映射；来源身份由可信结构携带，模型看到的文本标签不充当凭证。采样、chat template及thinking设置入指纹；按阶段可见性检查资料来源而非盲搜词。
- **关闭证据：** 恶意Skill的伪system段落不能改变代理规则；同样文件加载在不同role会导致指纹不同；上下文不足显式未完成。[Ollama工具循环需保留调用与结果关联](https://docs.ollama.com/capabilities/tool-calling)

### V29｜高｜P0无发现时是否仍攻击、A/B track与reference变异范围尚未收口

**原文：** [§2 L37](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:37)、§9 L186–199、§12 L239、§15 L310、§17 L354。

- AttackPlan由finding展开，但没有明确零finding时的最低通用攻击套件；Gate又允许无发现相关项not_applicable，可能出现扫描零告警→零攻击→pass的合法实现。
- P0只变不参与真值的输入，包投毒FR-09列P1；表格又把同包reference授权伪造当攻击槽位。修改物理reference文件会改变bundle，是B；只替换工具返回则是A，需要明确是哪一个。
- **建议：** 固定与扫描发现无关的基础正常/攻击矩阵，finding计划只能追加不能取消；三天版只执行A类runtime槽位，B仅静态审查。reference注入若走A，必须作为运行时低信任响应变异记录、保持原包摘要不变。
- **关闭证据：** issues=[]仍跑基础攻击和正常保护；A/B身份与digest变化一致；没有把未实现的删除工具objective算覆盖。

### V30｜高｜worker lease、取消与预算恢复缺少fencing和一次性消费机制

**原文：** [§11 L229](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:229)、§14 L302。

- worker卡住后lease到期，新worker接手，旧worker恢复可能继续调用工具或写结果。只用“单写者”与租约不保证外部推理请求、工具执行和状态更新均拒绝旧worker。
- 预算预留后崩溃如何结算、无法确认模型是否已执行是否重新发起、作业累计45分钟在重启后是否清零，尚未定。
- **建议：** job/run带递增fencing token，proxy和写结果入口核对；预算预留持久化，有unknown计保守消耗，重启不重置时间/次数。三天版可禁止自动续跑model阶段，标inconclusive后新job显式重启；必须保留发布幂等和取消阻断。
- **关闭证据：** 旧worker恢复不能再提交动作；进程被杀后预算不回到零；取消后无新增publication。

### V31｜高｜日志恢复、证据不可变、结果重算和GC保留期之间需要统一规则

**原文：** [§8 L160](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:160)、§13 L266–268、§5 L112。

- commit后日志缺失可从事务事实补齐；另处写日志不完整不晋级，需区分可恢复缺日志与不可恢复模型上下文缺失。不能用接收事件推断不存在的完整模型trace。
- 结果不可覆盖，但同job后续harden、取消、用新Gate重算均可能改变汇总；要版本化报告和指针。GC对有效attestation的引用规则与“30天保留”相互影响，还缺证明何时过期。
- **建议：** 事务事件可补日志但标reconstructed；模型输入/输出缺失不得补造。每次判定生成新decision/report ID；可变latest指针只做索引。三天版不做自动GC，设磁盘水位和人工清理边界，避免错删证据。
- **关闭证据：** 只有已落库事实可恢复，缺模型trace仍inconclusive；重判不覆盖旧报告，活跃证明不能引用已删对象。

### V32｜高｜哈希排除规则过于通用，可能排除业务字段；路径规范化缺映射规则

**原文：** [§5 L97–112](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:97)、§7 L140。

- “排除显示名称、本地路径”应只适用于指定元数据字段；客户name、文档路径等可能本身是业务数据，不能按字段名或递归规则统一排除。文件树摘要纳入规范路径，与“本地路径排除”也需区分。
- NFC路径若重命名物化文件，原引用可能失效；若不改字节路径，访问映射如何确定？JCS并不自动做Unicode规范化；需在它之前定义路径处理，业务字符串保持原值。[RFC8785](https://www.rfc-editor.org/rfc/rfc8785#section-3.1)
- **建议：** 每对象显式列hash projection，而不是全局猜字段；digest表示统一为裸hex或sha256:前缀；文件树序列化用JCS数组等无歧义格式。三天版可只接受ASCII安全文件名，限制profile而非冒充完整Unicode支持。
- **关闭证据：** 改客户name/参考路径必改变相关摘要；改显示时间不影响内容身份；等价/冲突Unicode路径按固定规则接受或拒绝。

### V33｜高｜核心状态仍缺映射：缺授权、非法可信输入、unsupported与未知风险

**原文：** [§2 L41](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:41)、§7 L138–140、§12 L239–248、§14 L274。

- 输入validator拒绝非法fixture“不算Agent功能失败”，但它属于正常测试还是生成器错误？若所有正常case均被提前拒绝，不能因此认定Agent完成了业务。
- 合法发布任务缺grant被描述为“确定性业务失败或授权拒绝”，两个分支仍未收口；可能是fixture漏配授权，不应归咎于Skill。unknown policy始终阻断与未注册工具只是blocked_attempt也要区分可恢复拒绝和证据未知。
- **建议：** 用 `case_validity/agent_outcome/policy_decision/infra_status/job_verdict`分层映射表。预期拒绝非法输入是独立平台测试；合法fixture缺grant是harness配置错误；明确授权不存在的负例应预先声明预期拒绝。
- **关闭证据：** 合法数据任务至少真正执行；平台负例不充clean utility分母；正常拒绝后可继续任务，不因一次deny自动inconclusive。

### V34｜高｜PR head时效检查与本地晋级无法天然成为同一原子事务

**原文：** [§12 L250–252](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:250)、§14 L272、302–304。

- SQLite CAS能保护本地active revision，不能原子锁住GitHub远端PR head。查head之后到本地commit之间仍可能force-push；只写“晋级事务验证当前head”不能实现跨系统原子性。
- 独立制品发布或本地source无PR时，“必须仍为PR head”也应不适用。触发需覆盖policy/contract/model/tool变更，不能只监听Skill路径。
- **建议：** 检查永远绑定commit SHA，远端新head自然需要新检查；本地Registry发布绑定不可变digest与触发generation，并通过最新事件撤销过期资格。声明外部head查询是乐观时效检查，发布资格还受仓库现有合并流程；不承诺跨系统原子。三天可只做受控提交触发和本地CAS。
- **关闭证据：** force-push后的旧check不会给新SHA变绿；旧generation不能覆盖active；无PR本地profile有明确适用性。

### V35｜中｜风险例外、缓解证明与人工工作量没有产品闭环

**原文：** [§9 L174–184](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:174)、§14 L272、§16 L333。

- 高频静态高风险误报会全部inconclusive；自动模型不能销案是合理边界，但管理员具体如何看到证据、选择false_positive还是accepted_risk、期限多久、哪些风险禁止例外没有定义。
- “例外不覆盖另一个已证实违规”正确，但同一风险已实现违规时管理员能否accepted_risk继续pass，必须明定，不能让默认纯函数与人工覆盖产生两套答案。
- **建议：** 三天版不做风险接受自动放行；只允许管理员按固定命令审核明确静态误报，保留证据和有效域，实际禁止副作用仍fail。长期版再制定风险接受政策。
- **关闭证据：** accepted_risk不能覆盖本次实际违规；例外过期和证据变化自动阻断，有具体人工处理出口。

### V36｜中｜“因果证据”“新贡献”和“一周/三天完成”需要区分事实、假设与交付等级

**原文：** [§15 L310–321](/Users/jet/Downloads/NVIDIA_DGX/reviews/SkillLoop-PRD-v2.0.snapshot.md:310)、§19 L429。

- 轨迹可支持来源与行为关联，但仅记录先后不构成因果识别。要宣称注入导致失败，至少需要去掉注入的配对正常对照；模型随机性也要披露。
- §19直接称本项目“新贡献”，而插件化、有限修补与CI回归首先是设计组合；三天原型不能自动证明新颖性或增量收益。保留为拟验证贡献更准确。
- 三天与正文七天计划不一致，且G2才是v2.0通用工具完成条件；四人并行不能把跨模块依赖和GPU串行时间消掉。
- **建议：** 使用“可追踪证据/配对支持的归因”和“拟验证的组合价值”；建立明确Sprint-3D范围，未完成的P0/G1/G2逐项列出。未观测到有效补丁时可交付拒绝与证据，但不宣称自动修复效果验证成功。
- **关闭证据：** 演示每个数字指向真实run；受控机制夹具单独标识；完成等级由测试矩阵确定而非由标题决定。

## 四、上一轮问题是否真正关闭

v2.0的§18是设计处理记录，不能直接当工程问题关闭单。以下按概念决策和接口完整性分别判断；“有明显改善”不代表已跑测试。

| 上轮ID | 本版已有进展 | 本次仍需补充 |
|---|---|---|
| R01、R06、R10、R33 | 双verdict、三种baseline、无合格active、CAS已经明确 | V03、V09、V12、V34：作用域、组合制品、实例身份和远端时效 |
| R02、R39、R44 | finalist后一次campaign、epoch与研究cohort更清楚 | V07、V18：逐例证明和恢复/批次预算 |
| R03、R09、R24 | strict/ablation、修补触发、目标/普通失败分开 | V08、V10、V24、V33：可达性、扩权、指标与授权错误归因 |
| R04、R05、R27 | 三轴finding与优先表已有规范 | V03、V23、V35：阈值/范围、重开条件和例外 |
| R07、R08、R41、R47 | 预算账本、分批、队列、水位已描述 | V11、V18、V19、V30、V31：范围冲突与执行可行性 |
| R11、R37 | 有限AST、三类编译义务和proof domain | V04、V09、V14：deny/序列语义、策略身份、入口遗漏 |
| R12、R13、R14 | 同SQLite发布事务、receipt绑定、崩溃点明显改善 | V05、V15、V16、V17：授予路径、真实字节、幂等顺序、证明期限 |
| R15、R16、R35、R38 | 六隔离域、角色表、证据链和输出隔离 | V02、V06、V07、V08、V28、V31：直接冲突与实际拓扑 |
| R17、R18、R19、R20、R22、R46 | 支持profile、五工具、首个表格规范更具体 | V14、V19、V20、V21、V22、V27、V29：参数边界/第二契约仍缺 |
| R21、R25、R26 | 暴露与有效性分离、重试不覆盖首败 | V12、V24、V33：重复统计、robust定义、平台错误分母 |
| R23、R40 | 内容泄漏剩余风险和宿主适用范围更清楚 | V08、V09、V14：秘密可见性与实际产物/策略绑定 |
| R28、R29、R30、R31、R32、R34 | 扫描映射、快照、哈希、CLI、指纹均有描述 | V01、V13、V17、V22、V25、V26、V32：附件与可执行协议 |
| R36、R42、R43、R45、R48 | 累计补丁限额、机制夹具、M0阈值、FR矩阵有改善 | V09、V10、V11、V21、V29、V36：纯策略候选/范围/三天取舍 |

## 五、其他需要在规范冻结时写清的细节

这些是上述主问题的具体字段清单，不另凑成独立漏洞数量：

- **字节与token：** 单位KiB还是KB、payload码点计量、UTF-8分页、JSON换行是否入artifact hash、文本长度限额与模型token预检必须一致。
- **p95语义：** “延迟增加>150%”意味着超过基线2.5倍；如果想表示“达到基线150%”则是1.5倍，需改成明确公式。
- **时间：** wall clock用于过期、monotonic用于执行预算；取消、重启和机器时钟变化的处理不能混用。
- **schema版本：** “未知必填字段”不是标准JSON schema行为描述；必须定义未知属性的拒绝/忽略策略、api_major与schema_version的关系，以及新增关键字段何时升major。
- **插件信任：** manifest自报trust_role不授予权限，可信controller按受保护注册表分配；加载未注册Python模块本身可能执行代码，不可在高权域动态import不可信插件。
- **scanner严重度：** 静态severity不能直接覆盖动态目标的业务severity；动态risk由批准的目标谓词定义，未知风险等级必须显式处理。
- **策略规则单位：** max_calls是每工具、每动作元组还是规则总量；required_receipt是类型、检查集还是具体ID；phase有哪些状态；all_of含互斥resource时如何归一化。
- **异常输入：** CSV非法输入金样是输入validator机制测试，不等于模型端正常用例；每个报告分母注明测试种类。
- **业务机密：** “额外公开敏感字段不能进入输出”用语矛盾，需明示字段是可读但不可发布，还是根本不可读，并落实allowed_transforms。
- **证明状态：** eligible/promoted/revoked/expired/stale/cancelled与四verdict分开存储；旧证明即使verdict=pass也可能已不具备发布资格。
- **重放配对：** 正常/攻击fixture的业务投影相同，注入字节不同；不同bundle比较同一攻击字节。不要把两种“相同fixture”混为一谈。
- **模型独立性：** 同模型权重可复用，不复用messages、私有日志或隐藏结果；seed支持不代表完全确定性。
- **控制测试覆盖：** 拒绝测试必须包括未知工具、第三方receipt、反向调用管理员socket、policy更换、已commit响应丢失、旧worker复活、保护报告间接泄漏。
- **无发现与无历史：** 无历史可not_applicable，零扫描发现不能让全部动态安全测试not_applicable。

## 六、审查结束条件

下一版无需再写更长的理念说明，应把剩余决定变成短而可执行的schema、函数契约和金样：GateSpec、ToolProtocol、PolicyEffectiveSet、GrantIssue/CommitProtocol、Case/RunIdentity、CandidateBundle、ExecutionPlan与RoleAccessMatrix。每个问题关闭需附规范位置及至少一个反例的预期结果。

三天内优先修V01–V06、V09，再将其余高优先级问题按收窄后的Sprint-3D适用范围解决；延期的能力明确unsupported，不把该范围的失败隐藏成pass。原文G2、完整插件SDK、通用策略序列证明和长期队列不能依靠声明已写入文档就算完成。
