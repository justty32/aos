# 2026-09-29 使用者裁定（八）：取消、每任務 cgroup 與原型缺口收尾

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第十七批。全部裁定後批優先，見[裁定索引](README.md)。以下皆為〔使用者方向 2026-09-29，第十七批〕。

## A．spec 審稿剩下的（已落進 spec）

1. **取消工作**：新增檔案請求 `work.cancel`，投到持有那件工作的 node；排隊中的直接拿掉，在跑的由 node 請 daemon 殺掉；取消請求檔的擁有 UID 要等於原請求檔的擁有 UID 或該 node 的擁有者，否則回沒權限並丟掉。改：[work P-411](../../spec/protocol/work.md)（正本）、[messages P-306](../../spec/protocol/messages.md) method 表、[execution B-203](../../spec/base/execution.md)、[kernel P-806](../../spec/protocol/kernel-tasks.md)、[protocol README](../../spec/protocol/README.md)；schema：msg-methods、新增 msg-cancel-payload、kernel-work-state 加 `submitter_uid` 與 `canceling`；範例：messages 下 work-cancel 正反例六份。
2. **每個任務一層 cgroup**：tick 在 node 框的 `tick` 葉，每個任務開與 `tick` 並列的 `task-<序號>`，結束有剩就 `cgroup.kill`、等空再 rmdir；成本每任務多約 0.1 毫秒（[實測](../probes/per-task-cgroup-cost.md)）。改：[node P-203](../../spec/settled/protocol/tick.md)、[execution B-202](../../spec/base/execution.md)、[P-107](../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)、[B-605](../../spec/settled/daemon.md) 命名。原型未改，記 G-15。
3. **agent 自己開的 once 做完，aos 不主動叫醒**，由 agent 自己看結果。改：[agent-tasks P-707](../../spec/protocol/agent-tasks.md)。
4. **給 kernel 的一般回話（agent.say）交給 kernel 現有的收件任務**：寫 history、回確認。改：[kernel P-803、P-814](../../spec/protocol/kernel-tasks.md)、[messages P-306](../../spec/protocol/messages.md)。
5. **node 接受哪些請求由任務表決定**：各任務用 `methods` 宣告，沒人宣告的由 tick 回 -32601。改：[node P-202](../../spec/settled/protocol/tick.md)、[messages P-306](../../spec/protocol/messages.md)、[kernel P-814](../../spec/protocol/kernel-tasks.md) 任務表；schema：node-tasks 加 `methods`；範例：node 兩份新正反例、kernel／agent 範本與 agent 任務表補 methods。

## B．原型缺口（spec-gaps 逐條標狀態）

- 已定：G-1（缺 cgroup_root 回 2，[P-101](../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md)、[B-605](../../spec/settled/daemon.md)）、G-8（新增 SourceChanged，[inst](../../spec/base/inst.md)、[P-110／P-111](../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)、daemon-rpc schema，原型改碼改測）、G-12（假 cgroup 只求可重現，[原型 README](../../proto/README.md)）、G-14（分頁中重開回 1，[cli/commands](../../spec/cli/commands.md) 第 7 列）、G-4 位置（`.aos/runner-stderr.log`，[P-109](../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)、[node P-200](../../spec/settled/protocol/tick.md)，輪替延後）。
- 下一輪：G-5、G-9、G-10。延後：G-6、G-7、G-13。見[規格缺口](../../proto/notes/spec-gaps.md)。

## C．第十六批發現的

1. **設定檢查跑完、寫好問題紀錄就回 0**，只有檢查自己跑不起來才非 0。改：[kernel P-805](../../spec/protocol/kernel-tasks.md)、[cli/commands](../../spec/cli/commands.md) 第 31 列。
2. **有寫 cgroup_root 但那層有程序，比照省略**：搬進 `daemon` 葉，搬不動報錯。改：[B-605](../../spec/settled/daemon.md)、[P-101](../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md)；原型一律搬並加測。
3. **daemon 範例的工作目錄示意改成 P-402 前綴格式**：`jobs/job-1`、`try-1` 改成 `<前綴>-attempt-1`。改：examples/daemon 六份。

## 落 spec 時的取名與補充

不是使用者逐字裁定，有疑問以後續裁定為準。

- work.cancel 的材料是 `{request_id}`（原請求 RPC id）；錯誤碼 `cancel_not_authorized`、`work_not_found`；「node 的擁有者」取 node 根目錄的擁有 UID。在跑的用 daemon 的 `node.unregister` 殺 once。
- 任務層名 `task-<本格第幾項>`，和 `tick` 並列（`tick` 已有程序，開 controller 後不能再有子層）。為了讓 tick 自建任務層，node 框的委派檔要交給 node 的執行帳號；上限檔仍歸 daemon。
- 「kernel 現有的收件任務」取範本裡的 schedule（它本來就收 recheck）；history 放 `state/kernel/history/<id>.json`，形狀沿 agent-history。
- 同一 method 只能由一項任務宣告；沒人宣告的由 tick 開格時回 -32601，另開一個 `aos-tick unclaimed` 提交。
- 設定檢查的 validate-only 不寫紀錄，照舊 0／2，給 resume 判斷。

## 留下一輪

- 每任務一層 cgroup 的原型實作（G-15）。
- agent 自跑 once 與 LLM 請求的取消由誰宣告 work.cancel，範本還沒指定。
