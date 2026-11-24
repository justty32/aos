← [回入口 01-保證佈局入口.md](../01-保證佈局入口.md)｜段落：三、入口、loop、fsm｜上一份：[01-一-aos-保證的與二-佈局](01-一-aos-保證的與二-佈局.md)｜下一份：—

## 三、入口、loop、fsm

- **P-05** 標準範本 [templates/agents/agent-fsm](../../../templates/README.md#agent-fsm) 的入口 `_entry`（預設 `$AOS_ENTRY`，[ideas § 13](../../../thinking/2026-10/19/ideas/README.md)）是沒 `+x` 的 JSON 單子：`{"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}`——`aos-exec` 這個資料夾＝把這隻掛上 daemon，掛好就回來。身體的入口是 `body.json`＝`["aos-loop", "loop.json"]`，由 `interfaces.json` 的 `entry` 指，掛上去之後 daemon 跑的是它（設定檔是 aos-loop 唯一的位置參數，N-11）。JSON 入口（單子、argv 陣列、`js[$AOS_ENTRY]`，C-73）由 aos-exec 讀、**不寫 shebang、不設 `+x`**（寫法見 P-40）。（使用者 11-05「aos-agent add。當然，你也可以把_entry寫成aos agent add，這樣我們也可以aos-exec了。」，[portable-flow](../../../thinking/2026-11/05/portable-flow/README.md) 題 4；入口照範本寫＝使用者 11-13「cv-P05:A」，[convention-vs-agent-fsm](../../../thinking/2026-11/13/convention-vs-agent-fsm.md)；C-73、P-27）
  - **也可以這樣寫：入口是可執行檔**，不經 daemon、直接跑 loop——`_entry` 設 `+x`、帶 shebang（`#!/bin/sh`），下一行 `exec aos-loop loop.json`；或讓 loop.json 帶 `_entry`、入口寫 `exec aos-exec loop.json`。這種入口照樣寫 shebang，不靠 aos-exec 與單子對沒 `#!` 的檔（Linux 本身跑不起來）改用 `/bin/sh` 跑的退路（N-59 第 5 件）；用 `exec` 少一層行程、訊號直達 loop（本稿定）。（§ 4 原話「#usr/bin/sh aos-loop loop.json」；退路：§ 22 使用者「乙」）
- **P-06** `loop.json` 的欄位：aos-loop 認的 key 照 [cpp/aos-loop](../../../cpp/aos-loop/README.md) 共九個（待裁網頁 條文-3 選 A）：
  - `exec`＝每次跑誰（三種寫法見下）；`max`＝最多幾次（沒寫＝不限）。
  - `interval_ms`＝上一次結束到下一次開始至少隔幾毫秒（沒寫＝0，N-32）。
  - `ctl`、`state`、`state_flux`＝三個窗的檔名，在 `$AOS_STACK` 底下；沒寫＝`ctl.json`／`state.json`／`state_flux.json`、寫 `null`＝不開（使用者 11-04 題 5「留 key、沒寫時預設就是這兩個名」，[four-elements 06](../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)；三個窗見 [aos-loop docs/02](../../../cpp/aos-loop/docs/02-窗.md)）。
  - `on_start`、`on_stop`＝loop 起來、要退時各跑一次，寫法同 `exec`；`on_timeout_ms`＝這兩格的期限（非負整數，0＝不限，沒寫＝5000）。細節見 [aos-loop docs/01](../../../cpp/aos-loop/docs/01-用法.md)。
  （補齊到八個＝使用者 11-13「cv-P06:A」，[convention-vs-agent-fsm](../../../thinking/2026-11/13/convention-vs-agent-fsm.md)；第九個 `on_timeout_ms` 照程式補，待裁網頁 條文-3 選 A。）其他 key 如 `body`、`_entry`、`description` loop 不看，是給 aos-exec 用的（[ideas 10-22 § 5](../../../thinking/2026-10/22/ideas/03-5-loop.md#5-loop10-22)）。`exec` 三種寫法：
  - 字串＝aos-exec 的目標（子資料夾、檔、`檔#/指標`；每次 `aos-exec -- <exec>`）。相對路徑照 cwd 算、loop 不轉（慣例下 cwd＝loop.json 所在的資料夾）。
  - 陣列 `[目標, 參數...]`（每次 `aos-exec -- 目標 參數...`）。
  - 單子物件：loop／fsm／daemon 在自己行程內用 aos-exec 跑單子的同一套跑；跑的期間 `AOS_CF`／`AOS_CD`／`AOS_CO` 怎麼設、單子壞怎麼退，照 N-36。（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../../thinking/2026-10/24/exec-relative/01-使用者原文.md#10-24-exec-直接放單子)）

  loop.json 帶 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`（放在大 JSON 裡就寫 `{"$env": "AOS_CF", "$path": "#/<位置>"}`，N-45）時，`aos-exec loop.json` 就能把 loop 跑起來（沒 `argv` 的物件當資料夾，N-61；使用者 10-21 下午「你說的這兩個可以刪的，確實跟我想的一樣，都可以做。」，[ideas 10-21 § 8](../../../thinking/2026-10/21/ideas/05-7-審後的五個細縫與修正.md#8-aos-loop10-21-下午)）。loop 每次起一個 `exec`，看它的結束碼決定下一步（P-19）。（§ 1；拍板點 1；欄位名為原型自訂，daemon／窗的條文也用這兩個名字，[ideas § 22](../../../thinking/2026-10/19/ideas/README.md)、N-28；`exec` 這個名字：使用者「exec，loop／daemon 的 run 也一起改 exec」，[thinking](../../../thinking/2026-10/23/naming.md)）

  例：單子放在同一份 loop.json 的 `body`、寫 `"exec": "loop.json#/body"`（aos-exec 從 loop.json 的資料夾跑它），就是普通的字串目標。大 JSON 的位置例如 `#/loops/a`（`loops` 只是指標的例子；daemon 的名單叫 `procs`，[thinking 11-03 procs](../../../thinking/2026-11/03/procs/README.md)）。

- **P-07** fsm 一次只跑一格：讀 `$AOS_STACK/stage.txt`（沒有＝`start`；檔名：使用者 11-04 題 10「fsm改名，嘗試用同義詞」，[four-elements 07](../../../thinking/2026-11/04/four-elements/07-實作步驟.md) 步 3；fsm.json 的 `start`／`states` 不改），跑那格；格的碼被 `next` 接住（0 或表上明寫的碼）就寫下一個狀態、退 0；沒接住的非 0 不換狀態、以原碼退（新舊打架，11-17「新的覆蓋舊的」：P-19 較晚）。字串 `next` 只接 0；物件 `next` 接表上的碼與 `"*"`，查法照 N-36。每次之間狀態都落在 stack，人看得到。**標準＝`aos-fsm fsm.json`**（[cpp/aos-fsm](../../../cpp/aos-fsm/README.md)；§ 10；設定檔是唯一的位置參數）：表長 `{"start","states":{名:{"exec","next"}}}`（使用者：「fsm.json，現在是用val，幫我改成exec」，[thinking](../../../thinking/2026-10/23/naming.md)）。`exec` 跟 P-06 同三種（字串的相對 cwd＝agent 資料夾；單子物件時 `AOS_CO`＝`/states/<名>/exec`）。fsm.json 可帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`，`aos-exec fsm.json` 就是一次（F6）；不寫 trace（使用者 11-03「整個拿掉」，[thinking 11-03 trace](../../../thinking/2026-11/03/trace.md)，N-39）。shell 版 fsm（自己讀 `stage.txt`、`case` 換狀態，見第八節範例「全 shell」）是對照寫法，`stage.txt` 同一個檔、同一格式，兩種可互換。（C-62、N-53 agent 是被外面 loop 一次一次驅動的狀態機；N-36 一次一格、表一定明寫）

  例：單子放同一格的 `body`、寫 `"exec": "fsm.json#/states/<名>/body"`，就是普通的字串目標。範本 `templates/agents/agent-fsm/fsm.json` 的 wait 退 11 接到 think、退 10 接回 wait，其他三格退 10 接到 idle，都是被 `next` 接住、fsm 退 0。

- **P-08～P-10** 接在 [01-P-08～P-10](02-三-入口-loop-fsm/01-P-08～P-10.md)。
