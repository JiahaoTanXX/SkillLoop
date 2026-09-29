# SkillLoop 展示站与待测 Skill 提交页

- 公网首页：<http://61.172.235.130:8019/>。三个 Skill 的历史证据和当前状态分开展示，五秒读取脱敏状态，较早观测标注时间。
- 订单历史报告：`/orders`；订单网页 Demo 记录：`/workbench`、`/showcase`。
- 自带 Skill 提交：`/custom`。用户可上传或编辑 ≤8 KiB UTF-8 Markdown，填写纯文本任务、期望精确答案和合成禁止标记。文件先在浏览器预览，点击保存后进入 DGX 私有待测目录，不自动运行。
- 用户已暂停所有后台实验。服务端对新订单和自带 Skill 模型运行均返回 423；只有保存草稿可用。退款和 Markdown 当前正式 API 矩阵仍未验收，历史攻击活动另列。
- 公网端口 `61.172.235.130:8019` 映射 DGX `0.0.0.0:8888`。独立 Demo 口令存于 DGX `~/skillloop/demo-private/web-password`，权限 600。
- 原始 Skill 提交、攻击载荷、秘密、模型响应和 trace 只留 DGX 私有目录；公开接口只提供脱敏统计。

展示版源码归档、停止记录、测试与 HTTP 检查见 `milestones/M9/presentation-delivery-v6b.json`。33 项机制测试通过；本次交付未启动模型。正式 M7/M9 验收及生产资格均未通过；GitHub 未 commit、push 或创建 PR。
