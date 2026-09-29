# SkillLoop 三 Skill 状态首页与订单 Web Demo

## 访问

公网登录：<http://61.172.235.130:8019/login>。

节点监听 `0.0.0.0:8888`，公网转发为 `61.172.235.130:8019`。
独立 Demo 访问口令保存在 DGX `~/skillloop/demo-private/web-password`，权限 600；与 SSH 密码分开。

## 三 Skill 首页

登录后进入 `/`，可切换订单、退款和 Markdown。首页每五秒读取 DGX 私有目录中各任务发布的脱敏状态；观测超过五分钟标为“较早”。订单展示封存的 M6 活动与最近网页 Demo。退款/Markdown 展示当前任务状态及单独标注的历史攻击记录；当前正式 API 矩阵未准入时显示 0，不将校准或旧活动记作新矩阵。

## 展示步骤

1. 登录后从首页进入「订单工作台」。示例 Skill 有意信任订单备注；用户可上传 UTF-8 Markdown 文件（最多 8 KiB）或直接编辑。文件先在浏览器预览，不会自动发送或运行。
2. 点击「运行全流程」。依次执行 Demo 规则扫描、真实 API 攻击、模型修补、候选回归、本地判定。
3. 查看原 Skill 与候选的必需/实际/完整/不完整分母、安全违规及业务失败。
4. 查看修补字节数、候选摘要、请求/token 用量和费用；导出脱敏 JSON。
5. 点击「历史证据报告」展示此前冻结订单的真实 M6 统计、配对限制与内容身份。

任意非订单 Skill 尚未接入对应工具与可信业务判定规则。首页会展示退款与 Markdown 的进度，但不会把固定订单环境的结果冒充其攻击测试。

新活动只使用受控订单读取和发布工具，不运行上传的代码。只允许一个活动工作，重复请求去重；进程中断后保留不完整记录，不自动重跑。每个活动最多 25 次模型请求、900 秒、20 个持久活动；HTTP 接口不能执行命令或读取任意文件。

## 验证结果

M8 本地 CI/CD：v3 的 21 项测试全部通过；独立重建触发、配置变更、旧任务隔离、续期与持久结果，见 `milestones/M8/acceptance-review-v3.json`。

M9 订单 Demo 范围：服务器 HTTP 登录/API 检查、浏览器登录/启动/自动更新/导出通过；真实活动在 DGX 依据原始响应、实际上下文、发布记录和共享费用账本独立复核，见 `milestones/M9/acceptance-review.json`。每个活动独立统计，不拼接攻击分数。

目前两份已独立复核的最终版本活动各运行 3 次原 Skill、3 次候选，13 次真实 API 请求，均未确认攻击成功。因此没有证明修补阻断攻击的价值。

## 范围限制

这是订单 Demo 全流程验收。M7 暂缓，正式三次重复和私有保护尚未完成，候选正式资格为 inconclusive。API 原始 reasoning 字段缺失，不能把已知计数 0 当作完整 reasoning 用量为零。规则扫描不是正式模型 ScannerReport。M6/M7 原始活动、时钟、冻结候选及运行快照均未修改。

攻击载荷、模型请求/响应及原始工具 trace 只在 DGX 私有活动目录。网页不公开这些材料，不显示 API Key；公开统计不是生产资格或三 profile 全局验收。

## 运维

DGX 当前源码快照 `~/skillloop/demo-web-v3`；后台会话 `skillloop-web-demo`。
日志 `~/skillloop/demo-private/web-server-v3.log`；任务库 `~/skillloop/demo-private/jobs.sqlite`。
使用现有私有 API 配置和共享 `api-private/calibration-v1/cost.sqlite`，不查账户钱包，不复制预算账本。
更新源码需建新快照，并确认没有正在执行的活动，再切换服务。

本机静态预览：

```bash
python demo/server.py --port 8765
```

真实工作台只在 DGX 启用。本机预览不执行模型实验。

重跑本地 CI 测试并生成新的不可覆盖收据：

```bash
python scripts/local_orders_ci.py --output milestones/M8/new-local-ci-receipt.json
python scripts/local_orders_ci.py --review milestones/M8/new-local-ci-receipt.json --output milestones/M8/new-local-ci-review.json
```

## 2026-09-29 网站更新

新独立快照 `demo-web-hub-v5` 已部署到相同公网地址。29 项实现测试通过；公网登录页返回 200，未登录状态 API 返回 401。部署后的 v5 独立 CI 收据因自动审批连接中断未生成，见 `milestones/M9/hub-delivery-v5.json`。源代码通过 SSH/SCP 归档传至 DGX，与 GitHub 无关；没有 commit、push 或 PR。
