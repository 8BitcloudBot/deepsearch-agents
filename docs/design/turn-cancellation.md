# 设计评审稿：回合取消机制（H 轮暂缓大项②，编号 I5）

状态：**已批准实施**（用户 2026-08-29 对 9 项剩余问题全部做修复规划并准备修复；
本项为唯一交互形态新增，评审稿随实施提交，如对交互有异议可回退前端部分）。

## 现状

跑飞的回合只能等超时（真机实测最长 289s），用户无主动中断手段。

## 方案

1. **API**：`DELETE /api/conversations/{cid}/turns/{tid}`（204）：
   - turn 不存在/非本人 → 404；
   - 已终态 → 409；
   - running：取消其执行任务（`asyncio.Task.cancel()`）；服务重启后无任务
     的僵尸 running 回合直接标记失败（与 G4 回收呼应）。
2. **事件**：新增 WS 事件类型 `turn.cancelled`（合同新增类型，旧客户端按
   未知类型忽略——parseConversationEvent 只校验 type 为字符串，兼容 ✓）。
3. **执行侧**：`_execute_once` 捕获 `asyncio.CancelledError`（BaseException
   子类，现有 `except Exception` 不会误吞）→ `fail_turn("本轮研究已取消。")`
   → emit `turn.cancelled` → 正常返回（任务体面退出）。
4. **任务映射**：`app.state.turn_tasks` 从 set 升级为
   `dict[(cid, tid), Task]`，done callback 清理；删除端点按键定位。
5. **前端**：stage 线旁显示"停止"按钮（仅执行中可见），点击调用 DELETE；
   `turn.cancelled` 事件按失败类文案处理并清 stage。

## 红线核对

- store 语义零变更：取消收敛为 failed 是 running 的合法终态转移（红线2 ✓）；
- WS 合同只新增事件类型与 data 字段（红线5 ✓）；错误文案固定不泄漏（红线3 ✓）；
- citations 不触碰（红线4 ✓）。

## 敌意用例（RED-first）

- 执行中回合 DELETE → status=failed、result.error="本轮研究已取消。"、
  WS 收到 turn.cancelled；
- 取消已终态回合 → 409；取消不存在回合 → 404；
- 排队中的回合（同会话串行锁等待）被取消 → 不再执行、状态 failed。
