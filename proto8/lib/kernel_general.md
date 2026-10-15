# 通用 kernel（身體 `aos_kernel_general.py`＋判官 `aos_kernel_judge.py`、規則判官 `aos_kernel_judge_rules.py`）

← [proto8/lib](README.md)｜規範：[N-42](../NORMS/09-kernel.md)（第二種：通用管理，判斷交給 agent）｜概念：[C-47](../CONCEPTS/04-kernel.md)｜規劃與決定：[thinking 10-15 通用 kernel](../thinking/2026-10-15-general-kernel.md)｜第一種：[kernel_llm.md](kernel_llm.md)｜demo：[demo/kernels/general](../demo/kernels/general/run.py)（`python3 proto8/demo/run.py kernels/general`）

> **基礎實作（N-18 最簡單的）、還不是規範。** 動工時自己定的點列在 [thinking 通用 kernel「動工自定點」](../thinking/2026-10-15-general-kernel.md#動工自定點)。

**閘門不改**：`aos_gate.py` 的 `mailbox` 指到這支的信箱就行；信（＝那張 inst 本身＋`priority`／`reply`／`sent`）與回信（N-30 結果）的形狀同第一種，讀信、認領、跑一封、回信共用 `aos_mailbox.py`。差別只在「誰先跑」由**判官**決定——判官是一張 inst（N-12）：stdin＝kernel 的 state 窗的子集（`queue`、`running`、`slots`、`budget`），stdout 最後一份＝決定。10-15 深夜 KISS 批次 1（[KISS 彙整](../thinking/2026-10-15-kiss/README.md) 1.8、1.9）純刪：便宜的直接跑、只有一封直接跑、判官的 `defer`、判官逾時預設 30 秒、`log`、`slots` 純值糖、kernel 替判官清環境變數都沒了。

```
呼叫者 ──▶ aos_gate.py ──信──▶ 信箱 new/ ──▶ aos_kernel_general.py（一拍＝一段忙碌期）──state 窗──▶ 判官 inst ──決定──┐
       ◀── stdout／碼 ◀──── reply/<名> ◀──── 一封一條執行緒、各自一支子程式（格在它結束時放）◀─────────────┘
```

## 設定

```
python3 aos_kernel_general.py [--key 值 ...] [KERNEL.json | -]
```

| key | 意思 |
|---|---|
| `mailbox` | 信箱資料夾（必填，同閘門的 `mailbox`） |
| `state` | state 窗（必填，N-19），欄位見下 |
| `slots` | 每種資源幾格：`{"llm": 1, "cpu": 2, "human": 1}`（只收物件；沒寫＝`{}`，來一封就 `ResourceUnknown`） |
| `judge` | 判官：TARGET 或一張 inst（沒寫＝一律用規則）；逾時寫在判官 inst 自己的 `timeout_ms`，沒寫＝不限 |
| `budget`、`aging_ticks`、`near_ms` | 同第一種；`budget` 只管 `llm` 的信 |
| `poll_ms` | 一拍之內多久看一次信箱與跑完的信（50） |

**資源**＝信的 `_metainfo.resource`（信就是 target 那張 inst，它寫的 `_metainfo` 原樣在最上層）：沒寫、或 `slots` 沒有這種＝回 `ResourceUnknown`（會經閘門排隊的 inst 就是要佔格的，沒寫是作者漏寫）。`human`＝人的注意力（C-28、C-29）：那支 inst 等人回信落檔，格就一直佔著，回信到或它的 `timeout_ms` 到才放。

## state 窗（判官的 stdin＝它的子集）

沿用 loop 骨架的名字（`state`、`pid`、`runs`、`last_error`、`last_warning`、`beat`；`last_warning`＝這拍最後一件回信寫不進去 `ReplyFailed`，不寫 stderr），加 kernel 自己的 key。每次要決定前寫一份、拍完寫一份；判官拿到的是剛寫的那份**只留 `queue`、`running`、`slots`、`budget`**（同一份物件的子集，不是新格式；`aos_kernel_judge.JUDGE_KEYS`）。10-15 起規則判官、agent 判官都這樣——整份給小模型太大、太慢（[實跑](../thinking/2026-10-15-judge-live.md)）。

```jsonc
{"state": "running", "pid": 123, "runs": 7, "last_error": null, "last_warning": null, "beat": 1792...,   // runs＝第幾拍
 "queue":   {"<信名>": {"priority": {...}, "_metainfo": {...}, "waited_runs": 2, "waited_ms": 830}},
 "running": {"<信名>": {"resource": "human", "since": 1792...}},
 "slots":   {"llm": {"total": 1, "used": 1}, "cpu": {"total": 2, "used": 0}},
 "budget":  {"limit": null, "used": 0, "day": "2026-10-15"},
 "served": 12, "seen": {"<信名>": 5}, "judge_error": null, "judge_asked": [...]}
```

不給信的 stdin 內容；要讓判官知道是什麼活，作者在 `_metainfo.summary` 寫一句。

## 判官的 stdout

```json
{"run": ["<信名>"], "reject": [{"id": "<信名>", "error": {"code": "CostTooHigh", "msg": "太貴"}}]}
```

- 沒點名的＝「不是我挑的」，**不是**「一定要等」（使用者 10-15 定：跑、不跑、沒說三種話；原本多一個 `defer` key 說同一件事，10-15 深夜 KISS 批次 1 拿掉）。不認得的 id 丟掉；`run` 超過該資源空格的照順序截掉。級數不能改。
- **補位**：套完判官的決定後，某種資源還有空格，就從**剩下的信**（沒被 `reject`、沒被判官點到起跑的）照第一種的規則（`order`：deadline 插隊＋級數＋aging＋先來後到，每種資源各自）補滿；只在判官答對時補（判官錯整個本來就走規則）。判官控制自己 `run` 的順序與 `reject`，補位只補空格。判官全沒點名也不會卡住。
- `reject`＝回信 `{"error": {code, msg}}`，呼叫端的閘門 stderr 一份 N-29、退出 1。
- **判官錯只有一條路**：判官這拍沒給合法答案（結束碼非 0、逾時、起不來、形狀不對、同一個 id 出現兩次）＝這拍改用第一種的確定規則（`aos_kernel_llm.order`：deadline 插隊＋級數＋aging＋先來後到，每種資源各自補滿），`judge_error` 記原因（答對一次清回 null）。kernel **不數連錯、不停問、不等人歸零**：下次局面變了照樣問；判官要「連錯幾次就改口或停住」是判官格自己的事（C-53 只處理自己的錯，同 N-38 的精神；10-15 使用者「都同意。」，[盤點第 3 條](../thinking/2026-10-15-principles.md)；原本有 `max_fails`、`judge_fails`）。
- **判官自己的腦別指回這個信箱**：會卡死（卡死就卡死，使用者定；kernel 跑判官跟跑任何 inst 一樣，一個 key 都不碰，C-52——原本替判官清 `AOS_KERNEL` 的那段拿掉）。

## 一拍

1. `cur/` 還有信＝上一拍被收掉（kernel 重起）→ 回 `KernelRestarted`、不重跑（N-20）。
2. 反覆：收跑完的（回信、放格）→ 讀 `new/`（過期 `DeadlineMissed`、資源沒寫或不認得 `ResourceUnknown`、`llm` 額度見底 `BudgetExhausted`）→ **局面變了才決定**（排隊的名單、在跑的名單、空格數跟上次一樣＝不問，沿用；**排隊的信沒有任何一種資源有空格＝這拍什麼也起不了，也不問**，格一放才問；有信有空格就問判官，只有一封也問——判官要能 reject 它）→ 照決定認領（new/→cur/）、起跑。
3. 沒有在跑的、這輪也沒起新的＝這拍結束。所以一拍可能很長（例：等人回信），期間新來的信照樣被收、被排。

stdout 一份 `{runs, served, dropped, waiting, budget, judge: {asked, fallback, skipped}}`（順序看呼叫端回來的先後；沒有 log 檔）；設定不對＝stderr 錯誤、退出 1。

## agent 判官（換一行 TARGET）

`demo/kernels/general/judges/agent.json`＝`aos-demo kernels/general/judges/agent/ask_judge.py [定義資料夾]`：開一個暫存 frame（`frame.json` 指回定義資料夾，沒給＝`judges/agent/`；要換腦就另開一個資料夾放 `brain.json`＋`frame.json` 指回 `judges/agent/`、把它當引數給，10-15 使用者「都按照推薦」）、`args.json`＝`{"question": 判官的 stdin（state 窗子集）}`），在裡面跑 `aos loop judges/agent/loop.json`（agent 當函數，[frame.md](frame.md)），讀 `ret.json`，把 reply 原樣印出來（不是 JSON＝kernel 退回規則，同一條路）；ret.json 是錯、沒有＝stderr 一份 `JudgeFailed`、退出 1（只這一個代號）。`judges/agent/system.md` 開頭 `/no_think`（不靠模型思考，見 [agent_lib.md](agent_lib.md#邊緣狀況使用者-10-15-定)）、說只回那三種話，腦預設 LM Studio（`judges/agent/brain.json`）。kernel 設定的 `judge` 從 `judges/rules.json` 換成它就好；demo 預設不跑它。

## 測試

`tests/test_kernel_general.py`（20 個）：判官的答案照辦、stdin＝state 窗子集（只有四個 key）、沒點名＝空格補位、判官點一封＋規則補另一格、reject 不補位、超格截掉、資源沒寫＝`ResourceUnknown`、不認得的資源、reject 到呼叫端是 N-29、判官錯五種都退回規則、連錯照樣每次問（kernel 不數）、局面沒變（有空格）不問、格全滿來新信不問＋格放了才問、0 格從不問、一封也問判官（能 reject）、human 格回信／逾時就放、重起回 `KernelRestarted`、設定錯、真的 daemon＋loop 端到端收工後沒漏行程。
