# M0/M2 实施记录（2026-09-24）

本记录对应仓库当前提交。执行前用 `git rev-parse HEAD` 记录确切实现 SHA；PRD、API 4 schema、fixture 和验收矩阵均从同一提交读取。依赖版本固定于 `specs/v2.2/requirements-verify.txt`，Python 要求 3.12。

## 可重跑检查

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r specs/v2.2/requirements-verify.txt
.venv/bin/python scripts/verify_implementation_m0_m2.py
```

2026-09-24 本地执行结果：参考规范 104 项、实现测试 19 项均通过；R01–R42 均有参考测试 ID、命令和预定证据路径。`specs/v2.2/verification-report.json` 仅是参考规范结果，不是 Runtime 验收。

DGX 上使用 Python 3.12.3 和相同固定依赖复跑提交 `1f8b2a670835524ecac58b2e03f8d64b0751e0c4`，得到 104 + 19 项通过。该提交归档的本地和 DGX SHA-256 均为 `17f4a28f06566ee09311287094953178111124557c0e4d7671bcfbee1750638e`。两端 `unicodedata.unidata_version` 均为 15.0.0；后续变更该版本需重新验证 Markdown/CSV 的 Unicode 语义和金样。

## 已实施

| 范围 | 实施入口 | 已验证内容 |
| --- | --- | --- |
| M0 API 4 线格式 | `skillloop/protocol.py` | 44 类 record 的 schema 与摘要、10 个 JCS 金样、重复 key/BOM/非有限数/超安全整数/错 major/额外字段拒绝；Gate 优先级的纯函数反例 |
| M0 需求映射 | `specs/v2.2/operations/acceptance.json`、`scripts/verify_implementation_m0_m2.py` | R01–R42 映射完整，生产运行证据仍按各 milestone 保留 pending |
| M2 家族注册 | `skillloop/families/registry.py` | 三 profile 的注册字节摘要、固定操作身份与 profile 绑定的构建参数 schema；数据型 capability handshake 含 API major、源码/规范摘要和角色声明 |
| M2 构建与校验 | `skillloop/families/builders.py`、`skillloop/families/oracle.py` | 同一表格算法加载订单/退款映射；独立 Markdown 算法；六份固定金样、构造式私有输入、手算边界和故意损坏输出被独立参考 oracle 发现 |
| M2 fixture/Skill | `skillloop/families/fixtures.py` | 输入、期望输出和三份 Skill 包按 manifest 的字节数/摘要核对，固定 frontmatter 拒绝错身份；确定性开发 fixture factory 生成新业务输入和独立参考答案 |

## 尚未由这份记录证明

M0 的 `digest` 只证明内容身份；生产者认证和权威存储解析需 M3。M2 的 handshake 只是数据声明，M3 才认证发送方；开发 fixture factory 不充当 M7 的私有题库服务。M2 的 oracle 是与构建器分离的参考实现适配器，受信任服务进程、资源隔离与真正的 `read → build → validate → publish` 事务需 M3/M4。Linux、模型、扫描器与 GitHub 的 R01–R42 生产验收均不能由这里的单元测试改成通过。M1 平台测量另行记录。
