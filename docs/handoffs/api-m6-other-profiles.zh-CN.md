# M6 API 并行接续：退款、Markdown

最新用户范围：当前主对话只负责订单 M7；分别创建退款与 Markdown 的 M6 接续任务，供另一窗口接管。用户要求不要再查询 API 的使用额度上限或账户余额。此前给出10元总费用预算；不要擅自把共享预算变成每 profile 各10元，实际请求费用/预留账本必须保留。最终成本范围由主任务协调，任务创建不应被账户余额查询阻塞。

## 每次进入先读

- `docs/m6-repair-progress.zh-CN.md`、`milestones/M6/progress.json`
- 各自私有进程、日志、manifest、plan、spending、原始证据
- `milestones/M7/api-readiness.json`、`milestones/M7/api-parallel-admission.json`

## 接入

DGX SSH 已授权；优先复用 ControlPath `/private/tmp/skillloop-demo-ssh-20260929`，host `61.172.235.130`，port `6019`，user `asus_gx10`。不要打印或复制凭证进入提示、仓库或普通日志。ControlMaster过期时向主任务报告需要重连，不反复撞认证。

API base_url `https://maas.qianwenaiapi.com/compatible-mode/v1`，model `qwen3.8-flash`，每个请求 enable_thinking=false。凭证已在 DGX `/home/asus_gx10/skillloop/api-private/qwen.key`，权限600；配置在同目录config.json，原始探针响应/calibration证据也在该私有目录。模型列表认证成功；普通与流式探针各1次，原始usage均为prompt30/completion1，但未返回原始reasoning_tokens字段。不要把缺失记为0，不要为获得字段启用thinking。raw_response、攻击、秘密与trace只能留在DGX私有目录。

价格由用户给出：输入0.8元/M tokens，输出2.7元/M tokens。已有两次接入探针的保守费用预留共0.026336元。API transport单独快照在DGX `api-private/transport-v1`；本地较新源码在 skillloop/runtime/qwen_api.py 和 skillloop/protection/api_budget.py。已有准入报告因完整矩阵费用、原始reasoning证据和真实业务校准未通过而rejected，不能宣称矩阵已启动。

## 历史与范围

退款旧DGX活动m6-n11r：父回归PID822568为SIGSTOP；submitted34结果（33必需+1协议重试）、candidate11结果（10正式封存，1条timing未完成），operator618290正在等它。不要恢复或删除该旧活动；新API配置必须单独版本化/记录，禁止并入旧配置分数。Markdown旧m6-n11m活动未创建；旧m6-b08只是历史。

参考矩阵：退款11案例×3重复×submitted/candidate=66开发必需运行，保护容量另24；Markdown8×3×2=48开发必需运行，保护容量另24。新扫描/发现若新增必需项，保留所有历史及失败，不能压缩分母。每profile的128次/8小时硬上限不提高，现有时钟不重置。冻结、真实模型结果、budget、parent Gate和最终review必须完整核验。

当前模型服务不运行；封存的M7容器skillloop-m7-orders已退出，生命周期进程停止。勿自行恢复旧退款调度或编辑repo-m6-v11快照。

## 开发协调

共享本地仓库含大量未提交的既有M6工作，禁止commit/push/PR。各自只编辑自己profile的操作脚本、handoff和进度文件，先做独立目录/source snapshot，避免修改共享运行中的快照。全局M6 progress/docs由主任务协调更新。M6之外的订单M7、Demo/M8–M9属于主任务，不在这些新任务内启动。

持续推进实现、业务校准和真实实验；Gate未满足时保留阻断事实及原始证据，不用机制测试或原模型结果冒充新API的完整验收。
