# 2026-10-14 aos-fsm：agent 變成一張方法表（傍晚）

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[05-aos-llm-agent題](05-aos-llm-agent題.md)｜下一份：[07-fsm樹與一拍](07-fsm樹與一拍.md)

## 10. 使用者原話

> aos-agent 他就是一個單次執行程式，被 aos loop 叫起來，每次叫起來就是換狀態。然後，你知道 golang 有那個所謂的 interface，或是 C 語言的函數指標，或是 C++ 的 class 的繼承，然後 class 函數可以被覆蓋。我會覺得，aos-agent 他被叫起來之後，看看狀態，如果是 idle，就去跑 inst-idle.json，如果是 thinking 那就是 inst-think.json, …。inst-idle.json 中，可以就是去看看有沒有 in/

> 這套概念應該可以延伸更多，inst/loop/daemon…

> fsm 這個想法太棒了

> （第 7 題「非同步」的意思）inst-think.json 他可以是跑起來就一直等，等到 llm endpoint 回東西，它處理好後再結束，也可以是把請求丟到某個資料夾，想著有人會處理

> 就是說 aos fsm 他可以是嵌套的。inst-think.json 內部也可以是 aos fsm，也就是 ask, wait, …

> 然後 aos fsm 他所要呼叫的 inst.json，也不一定要指定 .json 單檔案，也可以指定資料夾，那就是走 aos inst 那套

## 11. 架構（含 [08](08-fsm拍板與改寫.md) 十題、[12](12-七題回覆.md) 第 5 題）

- **aos-fsm**（`aos_fsm.py`）是通用程式：讀一份 JSON（`start`＋`states` 表＋窗），每拍查表、呼叫一格、換狀態。**aos_agent.py 不存在**；agent＝aos-fsm＋一個預設表資料夾（範本：幾張 inst、幾支方法程式）。10-15 的 `aos_agent_lib.py` 是現成格的庫、不是 agent 本體（[10-15 §6](../2026-10-15-topics/02-agent工具與試146.md#6-agent-格庫改名設定走-stdin)）。
- 表＝vtable：`states` 一定明寫在 agent.json。**每格的值＝一個 aos-inst TARGET**：`.json` 檔、資料夾（先找 `<資料夾>/.aos/inst.json`、再 `<資料夾>/inst.json`）、可接 `#/位置`；fsm 不另訂找法，直接用 aos-inst 的 `find()`／`load()`。也收一張內嵌 inst 單子（含 `$ref` 解出來的）。不靠慣例檔名、不做繼承（沒有 extends、沒有搜尋路徑）；想沿用範本就一格一格寫範本的路徑或 `$ref`。預設表資料夾只是可被引用的範本，不是父類。
- **一格可以是一個資料夾＝一個子物件**（使用者定）：`"thinking": "think/"`，think/ 裡有自己的 inst.json；若是巢狀 fsm，think/ 裡就是子 fsm 的設定、子表、子 state 窗。
- **aos-fsm 可以巢狀**（使用者定，像階層式狀態機）：某格的 inst 本身是另一個 aos-fsm，例：外層 `thinking` → think/inst.json 的 argv 是 `aos_fsm.py`，內層表 `ask → waiting → …`。接法見 [07 §12.3](07-fsm樹與一拍.md)（三題已定，見 §12.4）。
- 呼叫一格＝工具呼叫同一機制：fsm 寫 `work/N-args.json`（`{"state","step","prev","cfg"}`，cfg＝agent.json 合成後整份，[10-15 §6](../2026-10-15-topics/02-agent工具與試146.md#6-agent-格庫改名設定走-stdin)），把那張 inst 蓋上 stdin／stdout／stderr／exit（D-4 `run(dict)`），跑完取 stdout 最後一份（N-12）。
- 下一狀態：inst 回傳與結束碼概念上都正當；aos-fsm 採 stdout 最後一份的 `next`，沒吐＝看表上靜態 next，表也沒有才留原狀態（[10](10-lisp組合子.md)）。`data` 由 fsm 存進 state 窗、下一拍當 `prev` 給下一格。
- 出錯：方法 exit≠0、或查不到那格＝錯：表有 `error` 格就跳去（args 帶原狀態與錯），沒有就留原狀態＋`last_error`；上一拍沒留 ret（被殺一半）＝重進同狀態、`prev.interrupted: true`，由方法自己決定。
- 現在狀態記在 state 窗（`phase`＋`data`），fsm 開頭讀回。**state 窗必填**（使用者定，N-19 含 fsm）：缺 key 或 `null` 報錯不執行；巢狀內層也要有自己的 state 窗。ctl 窗選填（內層不另開）。
- 窗：state／ctl（只認 paused／stop、帶 seq）／lock 都是 fsm 的；心跳可選（設定 key）。鎖同時擋「表裡指回自己資料夾」的遞迴。
- 方法間資料：大的放檔（history.json 只有方法寫）、小的走 `data`；state 窗只有 fsm 寫（N-09）。
- **think 兩種實作同等地位、換一格即可**（使用者定）：(甲) 同步——inst 起來就叫 aos-llm、等回覆、處理完才結束；(乙) 非同步——inst 把請求寫成檔丟進某個請求資料夾（N-16 Maildir／JSONL 皆可）就結束、回 `{"next":"waiting"}`，「想著有人會處理」：處理者不綁定（worker loop、常駐服務、daemon 底下的東西、甚至人）；`waiting` 格下一拍去看回覆有沒有到。**規範中立，兩種都合規；基礎實作先做 (甲) 阻塞版**（第 7 題，[12](12-七題回覆.md)），(乙) 留在預設表資料夾裡當可換的一格。兩者都不自己 setsid／fork 背景行程。
- 共同核心＝方法表 lib `aos_methods.py`：載表、呼叫一格、取 stdout 最後一份；不含繼承。相依 `aos_directives ← aos_inst ← aos_methods ← aos_fsm`。
- 不套的：inst（它就是函數指標，不加 pre／post／on_timeout）、loop（不加鉤子，要鉤子就讓 loop 拍一個 fsm）、aos-llm 與工具（葉子）。daemon 的策略格（`child_exit`）重做 daemon 時再接，預設維持現行為。
