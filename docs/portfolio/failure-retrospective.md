# Failure Retrospective

Phase 4.5 的最终验收不是一次顺利的 happy-path run。下面的问题都来自实际实现或验收
过程，并分别形成了聚焦回归。历史顺序和限制以
[finalization evidence](../verification/phase-4-5-finalization-evidence.md) 为准。

## Leak Matcher False Positive

**Failure:** 第一次授权 real smoke 已完成任务并生成合法产物，但泄漏扫描把普通单词中的
`task-`、`mask-` 子串误判为 API token。

**Cause:** matcher 使用了过宽的 token prefix 规则，没有区分完整凭据形态和普通文本。

**Correction:** 先直接逐字节比对已配置 secret，确认产物没有泄漏；随后增加失败回归，
收紧 matcher，仅识别真实 token 形态。

**Lesson:** 安全检查既要 fail closed，也要有精确语义。误报会掩盖真正风险，并使通过的
业务路径无法被可信验收。

## MySQL Connector Segmentation Fault

**Failure:** 第二次 real smoke 在 macOS ARM64 的
`mysql.connector.connection_cext._open_connection` 中发生 Python segmentation fault。

**Cause:** Connector/Python C extension 在该本地环境不稳定；异常无法由常规 Python
错误处理可靠捕获。

**Correction:** adapter 强制 `use_pure=True`，保留只读 SQL、连接配置和 locator 契约；
聚焦 MySQL suite 通过后再运行完整授权 smoke。

**Lesson:** 外部 adapter 的实现选择属于可靠性边界。只测试返回值不足以发现 native
extension 带来的进程级失败。

## Uploaded Source Opened The Frontend Origin

**Failure:** 浏览器验收发现 `Open uploaded source` 使用相对 URL，在 Vite 开发环境中
解析到 `5173`，重新打开前端，而不是请求 API 文件路由。

**Cause:** backend 返回的 thread-scoped path 是正确的，但 React 组件没有将它与
`apiBaseUrl` 组合。

**Correction:** 先写组件回归复现错误 href，再将已验证相对 path 解析到 API origin。
复测确认下载事件命中 `/api/threads/<thread>/uploads/<name>`，内容与上传 fixture 一致。

**Lesson:** 安全路径合同和浏览器 URL 解析是两个责任边界，必须在真实部署拓扑下共同
验证。

## Wrong-Thread Fixture Reduced Source Coverage

**Failure:** 第一次确定性四来源比较只得到三个来源。

**Cause:** 上传 fixture 的 thread ID 与运行请求不一致，collector 按设计拒绝 foreign
thread locator。

**Correction:** 丢弃该探索结果，使用与请求一致的 fixture 重新运行；两次 canonical
JSON 和 artifact tuple 完全一致。

**Lesson:** 安全拒绝可能表现为“少一条数据”，演示 fixture 也必须遵守生产 thread
identity 契约，不能为了凑齐来源绕过隔离。

## Formal Knowledge Corpus Remained Absent

**Observation:** Qdrant Local + FastEmbed adapter smoke 通过，但配置的正式 index 不存在，
也没有建设语料、ingestion/chunking pipeline 或 retrieval-quality dataset。

**Decision:** Showcase 对 knowledge 采用局部降级，继续交付其他来源并显示 limitation；
作品集只声明 adapter、fingerprint 和 citation chain 已验证。

**Lesson:** “基础设施可运行”和“数据质量已证明”是不同命题。没有正式语料和评测时，
准确率必须保持 unmeasured。

## Resulting Engineering Principles

- 每个失败必须落到最近责任边界的回归，而不是只增加 E2E 重试；
- 安全拒绝和来源不可用必须成为用户可见的 limitation；
- native adapter、浏览器 origin 和 thread identity 都属于产品闭环的一部分；
- 验收记录失败、修复和未测范围，不把最终绿灯改写成“一开始就正确”。
