# 设计评审稿：citations 中文 tokenizer（剩余大项①，编号 I6）

状态：**已批准并实施**（2026-08-29）。

拍板结论：① 接受红线4 解读——tokenizer 属输入处理层，并行中文路径实施，
rules.py 原函数零改动；② 默认值保持关，真机 A/B 结论留档后再议翻转。

## 现状与问题

`app/citations/rules.py` 的词法引擎为英文冻结语料设计：ASCII tokenizer
（仅识别 `[A-Za-z0-9_]+` 类 token）+ 英文否定词表（without/no/not 等）。
中文 claim/quote 进入时几乎提取不到有效 token，导致：

- 支持性判定系统性失败（真机 T1 类问题中中文 claim 被误裁剪，EXECUTION_LOG
  有 'without' 触发误杀的实证）；
- `ENABLE_CITATION_VALIDATION` 只能维持默认关，引用校验能力整体空转。

## 提议方案：并行中文路径，不动既有规则

1. **不动 `rules.py` 现有函数与其判定逻辑**——支持/冲突/覆盖的规则语义
   原样保留（红线4 字面满足）。
2. 新增 `chinese.py`（或 rules 内独立分支）：
   - tokenizer：`[a-zA-Z0-9_]+`（英文词）+ `[\u4e00-\u9fff]`（中文字级，
     与 qdrant_local._lexical_terms 同构，保持项目内一致性）；
   - 中文否定词表：不/未/无/没有/并非/禁止/不得/严禁 及其位置逻辑
     （否定词出现在 claim 与 quote 的同一事实段→冲突判定）；
   - 数字与单位对齐：中文数字、百分比、金额（万/亿）规范化后参与支持判定。
3. **flag 隔离**：新路径由 `CITATIONS_CHINESE_TOKENIZER` 独立开关控制，
   默认关；与 `ENABLE_CITATION_VALIDATION` 串联生效（两者都开才走中文路径）。
4. **验收门**（发布门模式，沿用 shopkeeper 双 CTE 惯例）：
   - 敌意套件先行：中文 claim/quote 的支持、冲突、部分支持、数字不匹配、
     否定冲突各若干例（RED 先写）；
   - 真机 A/B：同一批 T1 类中文回合，开/关对比误杀率与漏杀率；
   - A/B 通过后由用户拍板是否翻转默认值。

## 需要拍板的点

1. **红线4 解读**：tokenizer 属"输入处理层"而非"规则语义"——新增并行
   中文路径、原函数零改动，是否接受这一解读？若认为 tokenizer 本身属于
   规则语义的一部分，则本项需要原仓库红线持有者裁决，不在本工作区实施。
2. 验收通过后默认值是否翻转（建议：先保持默认关，观察一轮真机再翻）。

## 实施与真机 A/B 结论（2026-08-29）

- 实现：app/citations/chinese.py（英文词+中文单字/bigram tokenizer、中文否定
  词表、数字锚点、r1/r2/r6 语义镜像，阈值复用 SOURCE_POLICY）；runtime_adapter
  双 flag 串联（ENABLE_CITATION_VALIDATION ∧ CITATIONS_CHINESE_TOKENIZER）。
- 敌意套件 11 例（精确包含/部分重叠/数字不符/否定冲突/否定在 claim/纯中文
  低重叠/英文兼容/空声明）全绿；路由测试验证 flag 关=英文基线行为、开=中文路径。
- 真机 A/B（T1 数据包，双 flag 开）：Q1 三个 claims 零误杀；Q2 一次裁剪为
  推断性陈述（"带出门"场景证据未覆盖），行为符合设计。
- 已知观察项：真机一次 drop_reason 展示异常（截为首字符 "…: t"），本地同代码
  不可复现；已加 drop 诊断日志（DEBUG），下次真机复跑定位。

## 规模与风险

- 规模：大（1-2 天：敌意套件半天 + 实现半天 + 真机 A/B 半天）。
- 风险：中文否定/同义改写的边界 case 多，首轮误杀率未必达标——
  因此验收门设在真机 A/B，不达标则保持关闭不损害现状。
