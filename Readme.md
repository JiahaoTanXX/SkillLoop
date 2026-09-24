# SkillLoop

面向 Agent Skill 的通用安全 CI：静态发现、自动攻击取证、受限修补与持续回归。

- 当前规范：[PRD V2.2](SkillLoop-PRD-v2.2.zh-CN.md)，开头是单人逐步开发指南。
- 实施文档：[系统设计](docs/system-design-v2.2.zh-CN.md)与[分阶段 Milestones](docs/milestones-v2.2.zh-CN.md)。
- 开发位置与环境：[本地 + DGX 开发方案](docs/development-environment-v2.2.zh-CN.md)。
- 当前实施与重跑命令：[M0/M2 实施记录](docs/implementation-status-m0-m2.zh-CN.md)。
- DGX 接入与模型锁：[M1 平台记录](docs/dgx-m1-access-report.zh-CN.md)。
- 扫描器 ARM64 镜像：[固定构建输入与 smoke](deploy/scanner/README.md)。
- 首版验收：表格报告与 Markdown 索引两个家族；订单、退款、文档三份被测 Skill。
- 接口、样例与检查：[V2.2 规范附件](specs/v2.2/README.md)。
- 固定模型及推荐后端：[Qwen3.8-27B-FP8 与 SGLang 部署验收](specs/v2.2/deployment.zh-CN.md)。
- 本轮审查：[R01–R42](reviews/v2.1-2026-09-23/REVIEW.zh-CN.md)。
- 历史快照：[V2.1](SkillLoop-PRD-v2.1.zh-CN.md)、[V2.0](SkillLoop-PRD-v2.0.zh-CN.md)。

当前已有 API 4 严格线格式、两个家族三个 profile 的离线构建器及参考 oracle 交叉检查；DGX 上的固定 Qwen 模型已完成三 profile 正常与边界输入的 mock 工具调用，扫描器 ARM64 镜像已完成离线 smoke。真实 Agent、权威 Proxy、完整离线扫描情报、隔离部署、GitHub 服务和模型攻防效果仍按验收矩阵确认。

## 仓库导航

| 路径 | 内容 | 当前状态 |
| --- | --- | --- |
| `SkillLoop-PRD-v2.2.zh-CN.md` | 产品与语义规范 | 当前版本 |
| `specs/v2.2/` | API 4 schema、家族 fixture、运行与部署规范 | 参考规范，生产验收待完成 |
| `scripts/`、`tests/spec_v22/` | 规范参考函数与反例检查 | 可执行的规范检查 |
| `skillloop/`、`tests/implementation/` | 首批生产代码与独立实现测试 | M0 线格式、M2 离线业务合同 |
| `docs/` | 系统设计、milestones、开发环境 | 实施计划 |
| `reviews/` | 历史审查与复现材料 | 追溯资料 |

原始运行证据、模型缓存、密钥和本地数据不提交到此仓库；公开报告只保存脱敏结果与不透明证据引用。后续生产代码按系统设计逐阶段加入。
