# 2026-09-29 使用者裁定（七）：spec 審稿修正與原型缺口

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第十六批。全部裁定後批優先，見[裁定索引](README.md)。

## 第十六批（同日晚，已落進 spec）

來源兩處：一次 spec 審稿挑出的前後不一致（1～7），以及第一段原型的[規格缺口](../../proto/notes/spec-gaps.md)（8～10）。以下皆為〔使用者方向 2026-09-29，第十六批〕。

1. **設定檢查失敗不擋收結果**：沒有任務以 `needs` 依賴 check，收已派結果的任務照跑。改：[kernel-tasks P-805、P-814](../../spec/protocol/kernel-tasks.md)（members、usage 的 needs 改「無」）、[kernel 範本範例](../../spec/protocol/examples/kernel-tasks/kernel-template.minimal.valid.json)、[cli/commands](../../spec/cli/commands.md) 第 31 列。
2. **回應沒寫入權限也報錯丟掉**：跟請求一樣照 P-206，只有暫時性失敗才留著補送。改：[messages P-303](../../spec/protocol/messages.md)。
3. **投給 LLM 池沒權限，投件時才報錯**：設定檢查不先擋。改：[agent-tasks P-701、P-712](../../spec/protocol/agent-tasks.md)、[S-301](../../spec/scheduling/llm.md)。
4. **LLM 結果回來就是投進 agent 收件夾**，照一般收件由所屬 kernel 叫醒，拿掉「回覆到了誰叫醒 aos 不管」。改：[S-301、S-305](../../spec/scheduling/llm.md)、[llm-work](../../spec/protocol/llm-work.md) 開頭。
5. **帶 `in_reply_to` 的回話只記錄**，不建待處理輸入、不觸發 LLM、不再回話，免得自己回自己無限循環。改：[agent-tasks P-705、P-708](../../spec/protocol/agent-tasks.md)、[messages P-306](../../spec/protocol/messages.md)、[agent/input](../../spec/agent/input.md)、[cli/commands](../../spec/cli/commands.md)。
6. **attempt 工作目錄名加發件者前綴**：`<前綴>-<attempt_id>`，前綴是配出 attempt_id 的 node（材料的 node_id）路徑做 sha256 取前 16 個小寫 hex；檔案內容裡的 attempt_id 不加。改：[work P-402](../../spec/protocol/work.md)（正本）、[terms T-03](../../spec/terms.md)、[kernel-tasks P-806](../../spec/protocol/kernel-tasks.md)、kernel-work-state 兩份範例的 work_dir。
7. **鬧鐘檔名分請求和回應**：`.aos/alarms/req-<id>.json`／`resp-<id>.json`。改：[node P-206](../../spec/settled/protocol/tick.md)。鬧鐘紀錄沒有 schema／範例，不用跟著改。
8. **cgroup 框的命名照原型（G-2）**：daemon 在 `<子樹>/daemon`；node 框在父框下 `n-<sha256(node_id) 前 16 hex>`，本格在其 `tick`；once 在父框下 `once-<同法>`。改：[B-605](../../spec/settled/daemon.md)、[P-107](../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)。
9. **沒寫 cgroup_root 時原層只當分支（G-3）**：daemon 啟動先在自己所在那層開 `daemon` 子層，把自己和那層其他程序都搬進去。改：[B-605](../../spec/settled/daemon.md)、[P-101](../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md)；原型補上搬其他程序並加測。
10. **登記 once 時帳號就要存在（G-11）**：不存在就拒絕、回 `user_invalid`；wake 時仍重新解析。改：[P-104](../../spec/settled/deferred/protocol/daemon/registration.md)；原型拿掉 once 的放寬，測試改成登記就被拒。

## 落 spec 時的取名與補充

以下是落 spec 隊補的細節，不是使用者逐字裁定；有疑問以使用者後續裁定為準。

- 第 6 條前綴的雜湊取法跟第 8 條 cgroup 框名同一套（sha256 前 16 hex），碰撞機率可忽略，讀目錄時仍核對裡面 request 的 node_id。
- 第 9 條搬不動（或一直有新程序進來）就報錯退出；只在省略 `cgroup_root` 時做，有寫 `cgroup_root` 的情況照舊（daemon 自己已在子樹裡）。（已被第十七批 C2 取代，見 [08](08-cancel-task-cgroup-and-gaps.md)。）
- 原型 `bin/` 三支入口先前被 repo 根目錄的 `.gitignore`（`bin/`）吃掉、沒進 git，這次一併補進並在 `proto6/proto/.gitignore` 加 `!bin/`。
