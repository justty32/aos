← [入口](../2026-10-28-agent-round.md)｜涵蓋：2. round：一輪本身、3. 掛勾（hook）、4. 單位介面｜上一份 [01-白話版](01-白話版.md)｜下一份 [03-4-單位介面](03-4-單位介面.md)

## 2. round：一輪本身

> **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round](../2026-10-30-aos-round/07-決定.md#決定10-30)）：順序搬到 `lib/agent/round/fsm-*.json`、現在在哪看 fsm 的 `state.txt`、`--step` 與 `hook/pause` 退場、trace 看 fsm 的行。

- **粒度看 `_entry`**（agent-ops 決定 12、13）：格只有一套。`_entry` 寫 aos-loop、每次只做下一格（照下面「從哪接著做」判）＝一格一格跑；寫 round＝一次跑完一輪。round 是**語法糖**：等於 aos-loop 加上「這一輪結束就停」的條件，留在零件庫 `lib/agent/round/`、不升成 aos 指令。§ 1 的 `loop.json` 是「loop 反覆叫 round」那種寫法，只是其中一種設定。
- **叫法**：`aos-exec round <agent 資料夾>`；loop 每次叫一次，或外面直接叫一次（§ 6 外部接口）。結束碼照 P-19：`0`＝這輪好了（或中途 yield，狀態在 stack，下次接著）、`10`＝沒題目、其他＝失敗停下等人（P-20）。
- **從哪接著做**（不另設狀態檔，看 `cur/` 跟 `history.jsonl` 最後一則就夠，agent-dan 的 brain 現在就是這樣判）：`cur/` 與 `new/` 都空 → 10；`cur/` 空 → `queue claim`；最後一則是 user／tool → 問腦；最後一則是 assistant 且有 `tool_calls` → `act`；最後一則是 assistant 沒 `tool_calls` → `queue finish`。
- **順序**（每一步都是 `aos-exec <格> <agent 資料夾> [子命令]`，stdin／stdout／結束碼是介面）：

```
round:
  hook/pre_round
  queue claim                          沒題 → 退 10
  loop:
    hook/pre_think                     compact 掛這裡
    tools  = aos-tools --file <agent>/tools.json ls --json
    system = <agent>/system.txt
    msg    = endpoint/<目前的>  stdin={"messages": system+history read, "tools": tools}
      失敗 → hook/on_error  stdin=那一行錯 → stdout stop／retry／switch；沒掛＝stop → 退那個碼
    hook/post_think   stdin=msg → stdout 非空就取代 msg
    history append    stdin=msg
    queue emit        stdin=msg
    沒 tool_calls → queue finish stdin=msg.content → hook/post_round → 退 0
    act               stdin=msg → stdout 一行一則 tool 訊息（act 內部跑 pre_tool／post_tool、插話檢查）
    history append    每一則
    hook/pause        退 10 → 退 0（yield）；0 或沒掛 → 繼續
```

- **每叫一格在 `$AOS_STACK/trace.jsonl` 追加一行** `{"started_at", "unit", "code", "elapsed_ms"}`（跟 fsm 的 trace 同形、多 `unit` 少 `state`；P-38 看樹就看這份）。
- **格失敗（非 0）＝round 失敗**，round 以那個碼退、stderr 不轉述（P-21 誰的錯誰講；格自己已經寫了一行）；只有 endpoint 的失敗先問 `hook/on_error`。
- **逾時**：整輪的 `timeout_ms` 寫在 `loop.json` 的單子（P-22、P-36 打整棵子樹）；endpoint 自己那次的逾時寫在 endpoint 格的 `.env`（`TIMEOUT_MS`），由 endpoint 自己守。
- **插話**：round 不管；由 act 在兩個工具之間問 `queue peek` 與 `hook/on_interrupt`（見 § 5）。
- 用 round 時一個行程跑完一輪；要一次一格，`_entry` 改用 aos-loop（決定 12，取代原本「掛 `hook/pause` 永遠退 10」的代定；`pause` 仍可用來在一輪中途 yield）。N-53／C-25 見文末第 3 條。

## 3. 掛勾（hook）

> **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round](../2026-10-30-aos-round/07-決定.md#決定10-30)）：順序搬到 `lib/agent/round/fsm-*.json`、現在在哪看 fsm 的 `state.txt`、`--step` 與 `hook/pause` 退場、trace 看 fsm 的行。

| 點 | 何時 | stdin | stdout／結束碼 | 沒掛時 |
|---|---|---|---|---|
| `pre_round` | 認領前 | 空 | 0 繼續；非 0＝round 失敗 | 什麼都不做 |
| `pre_think` | 每次問腦前 | 空 | 同上 | 同上 |
| `post_think` | 腦回來、接進 history 前 | 那一則 assistant（一行 JSON） | stdout 非空＝取代那一則；0 繼續 | 原樣 |
| `pre_tool` | 每個工具叫之前（act 內） | 那個 `tool_call` 物件（一行 JSON） | 0 跑；**10＝不跑**，stdout 當那次的 tool 訊息 content（例「policy 不准」）；其他＝act 失敗 | 跑 |
| `post_tool` | 每個工具回來、接進 history 前（act 內） | 那一則 tool 訊息 | stdout 非空＝取代（例截長）；0 繼續 | 原樣 |
| `post_round` | 答案寫進 `out/` 之後 | 最後那一則 assistant | 0；非 0＝round 失敗（答案已寫） | 什麼都不做 |
| `on_error` | endpoint 退非 0 | endpoint 的 stderr 那一行 | stdout 一個字：`stop`／`retry`／`switch`；非 0 或別的字＝stop | stop（P-20） |
| `on_interrupt` | act 兩個工具之間，`queue peek` 說 `new/` 有東西 | `new/` 的題名清單（一行一題） | stdout `interrupt`／`wait`；非 0＝wait | wait（hub-kernel 決定 13：各 agent 自己設） |
| `pause` | 每批工具接進 history 之後 | 空 | **10＝yield**（round 退 0、狀態在 stack）；0 繼續 | 不 yield |

- **名字**：`pre_`／`post_`＋動作（git hook 的老慣例：pre-commit／post-commit；C-54 命名方法查過 Unix 老慣例就用），決定型的叫 `on_`＋事件，`pause` 是動作。都是小寫底線（C-54）。
- **同一點只能掛一個**：`hook/<點>/` 就是那一個 aos 函數；要掛好幾個，那個函數自己依序叫（C-41「元素要不要先算由 entry 決定」、C-70 aos 不管巢狀）。不另定順序規則。
- **掛勾看到的東西**：第一個參數是 agent 資料夾、`$AOS_STACK` 是 agent 的 stack（共用），要看 history、current、endpoint.txt 都在那裡；要叫別的格就 `aos-exec <agent>/<格> <agent>`。
- **結束碼 10 的意思統一**：「正常、但這一步不做／到此為止」（P-19 的 10＝正常停）——`pre_tool` 的 10＝不跑這個工具、`pause` 的 10＝這輪到此 yield。

## 4. 單位介面

每個單位：`aos-exec <格> <agent 資料夾> <子命令> [args]`，stdin／stdout 是資料、stderr 一行 `名: 代號 原因`、錯退 1（N-43）。
