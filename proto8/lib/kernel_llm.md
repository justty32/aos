# LLM kernel（閘門 `aos_gate.py`＋身體 `aos_kernel_llm.py`）

← [proto8/lib](README.md)｜規範：[N-42](../NORMS/09-kernel.md)（第一種：管 LLM 呼叫）｜概念：[C-47](../CONCEPTS/04-kernel.md)｜決定：[thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)、[LLM kernel 優先級](../thinking/2026-10-15-llm-kernel.md)｜demo：[demo/kernels/llm](../demo/kernels/llm/run.py)（`python3 proto8/demo/run.py kernels/llm`）

> **基礎實作（N-18 最簡單的）、還不是規範。** 動工時自己定的點列在 [thinking LLM kernel「動工自定點」](../thinking/2026-10-15-llm-kernel.md#動工自定點)。

兩支：**閘門**包住要排隊的 inst（例：腦），**kernel** 是 daemon 底下一個 loop 每拍跑一次的身體。中間是一個信箱資料夾（N-16 Maildir）。信箱的共用部分（讀信、認領、跑一封、回信）在 `aos_mailbox.py`，兩種 kernel 都用。10-15 深夜 KISS 批次 1（[KISS 彙整](../thinking/2026-10-15-kiss/README.md) 1.8、1.9）純刪：閘門的 `wait_ms`／`poll_ms`／`QueueTimeout`、環境變數 `AOS_KERNEL`／`AOS_PRIORITY`、kernel 的 `log`、三個空錯誤類別都沒了。

```
呼叫者 ──N-12──▶ aos_gate.py ──信──▶ 信箱 tmp/→new/ ──▶ aos_kernel_llm.py（每拍：挑一封、new/→cur/、aos_inst 真跑）
        ◀─stdout／碼──        ◀──────── reply/<名> ◀─────────────── 回信
```

## 閘門 `aos_gate.py`

```
python3 aos_gate.py [--target T] [--mailbox DIR] [--priority P] [GATE.json]     # stdin＝原樣轉給真正的 inst
```

```jsonc
// gate.json（相對路徑從呼叫者的 cwd 算）
{"target": "brain.json",              // 真正要跑的 inst：TARGET（可接 #/位置）或內嵌一張 inst（必填）
 "mailbox": "/run/aos/llm-mb",        // 信箱資料夾（必填；閘門不認環境變數。demo 省字寫 {"$env": "AOS_KERNEL"}，只是指示詞的便利）
 "priority": "low"}                   // 選填：純量＝{"val": 值}；物件 {"val", "deadline", …} 照帶、不驗；沒寫＝不填
```

- **換腦一行**：agent 定義資料夾的 `brain.json` 換成一張跑閘門的 inst（例 `demo/kernels/llm/boss/brain.json`：`aos gate <閘門設定>`），其他不動；只換某次呼叫＝在那次的 frame 放這份 `brain.json`。demo 第 3 段只有 boss 的腦經閘門，clerk 用自己定義的腦（demo 不示範上層伸手進下層的 frame）。
- **信**（`new/<奈秒時間>.<pid>.json`，名字字典序＝先來後到）＝**target 那張 inst 本身**（inst 族，C-48）：key 攤在最上層（`argv`、`cwd`（轉絕對）、`timeout_ms`、`_metainfo`…；`id`＝target 的 id），加私有 key `priority`、`reply`（回信的絕對路徑 `reply/<名>.json`）、`sent`（epoch 秒）；`stdin`＝旁檔 `reply/<名>.stdin`（呼叫者 stdin 的內容）。kernel 只要把 `stdout`／`stderr` 填成旁檔 `reply/<名>.stdout`／`.stderr`，就能直接 `aos_inst.run(信)`（不認得的 key 一律忽略）。
- **回信**＝aos_inst 的結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`），或 N-29 形狀 `{"error": {"code", "msg"}}`。閘門讀回信、讀 stdout／stderr 旁檔原樣吐出，回信與旁檔一起刪掉。
- **呼叫端看到的＝直接叫 target**：stdout、stderr 原樣、退出碼＝target 的碼（測試逐字比過）。**閘門是透明的**：這時 stderr 與碼都是 target 的，不是閘門自己的；target 守 N-43（正常退 0、不寫 stderr）閘門就守。閘門只在自己出錯（下一條）時才說自己的話（10-15 使用者「都按照推薦。」，[盤點 S3](../thinking/2026-10-15-principles.md)）。
- 錯（stderr 一份 N-29、退出 1）：kernel 回的 `DeadlineMissed`／`BudgetExhausted`／`KernelRestarted`、設定不對（含沒寫 `mailbox`）、`Usage`（不收 `-`：stdin 是請求本身）。kernel 那邊 target 起不來（例 `CommandNotFound`）也是 1。排隊等多久只有一把尺＝包閘門那張 inst 的 `timeout_ms`（逾時 aos_inst 送 SIGTERM、閘門撤信）。
- SIGTERM／SIGINT／SIGHUP：信還在 new/ 就撤掉（連 stdin 旁檔）、stderr 一份 `Signaled`（帶訊號號碼）、退出 1（原 128＋N）；已被拿走的讓它跑完，回信與旁檔沒人收（留在 reply/）。
- target 在 kernel 的環境跑（環境變數＝kernel 的＋target 的 `envs`，不是呼叫者的）；stdin／stdout／stderr 被閘門蓋掉（同 fsm 的格）。

## kernel `aos_kernel_llm.py`

```
python3 aos_kernel_llm.py [--key 值 ...] [KERNEL.json | -]
```

| key | 意思 |
|---|---|
| `mailbox` | 信箱資料夾（必填） |
| `state` | state 窗（必填，N-19）：loop 骨架的名字 `{state: "waiting", pid, runs, last_error, last_warning, beat}`（`last_warning`＝這拍最後一件回信寫不進去 `ReplyFailed`；不寫 stderr），加 `seen`（每封信第一次看到的 runs）、`budget: {limit, used, day}`、`served` |
| `slots` | 一拍最多跑幾封（1）；>1＝同一拍幾封一起跑，等最慢的跑完這拍才結束 |
| `budget` | 一天的 token 額度（null＝不限）；用量＝target stdout（旁檔）最後一份的 `usage.total_tokens`，沒有＝0；換日歸零。兩顆真腦都在 assistant 訊息頂層帶 `usage`（[agent.md](agent.md)），包閘門就計得到 |
| `aging_ticks` | 每等幾拍升一級（10） |
| `near_ms` | deadline 剩不到這麼久＝插隊（30000） |

**一拍**（跑一次＝一拍；被 aos-loop 拍，loop 掛在 aos-daemon 底下）：

1. `cur/` 裡還有信＝上一拍跑到一半被收掉 → 回 `KernelRestarted`、刪信，不重跑（N-20）。
2. 讀 `new/`：deadline 已過＝回 `DeadlineMissed` 丟掉；額度見底＝每封回 `BudgetExhausted`（不排隊、不等額度回來）。
3. 排序：**deadline 快到**（剩不到 `near_ms`）的插隊、越近越前 → **有效級數**高的先（`low`／`normal`／`high`＝-1／0／1，數字取正負號，不認得＝0；有效＝級數＋等了幾拍 // `aging_ticks`）→ deadline 近的先 → `_metainfo.cost` 小的先（沒寫＝0）→ 先來後到。
4. 認領前 `slots` 封（new/→cur/，被撤走的跳過），信本身就是 inst：填 stdout／stderr 旁檔、`aos_inst.run()` 跑、回信＝結果（N-30）、刪信。

stdout 一份 `{runs, served, dropped, waiting, budget}`（`served` 的順序＝服務順序；沒有 log 檔，順序從呼叫端回來的先後看）；設定不對＝stderr 錯誤、退出 1（`state` 沒寫＝`WindowMissing`）。

## 慣例：只包葉子

kernel 一格一次一封。**只包腦（或單一貴工具）**：boss 的腦回完才去叫 clerk，clerk 的腦再排隊，一格就夠（demo 第 3 段）。要是包了「會再叫別人的工具」（例：整個 agent 當工具的那張 inst），它佔著格等裡面的腦，裡面的腦排不到＝卡死；使用者 10-15 定「卡死就卡死」，不做機制，靠這條慣例。

## 測試

`tests/test_gate.py`（17 個）：信＝target 那張 inst（key 攤平＋priority／reply／sent、stdin 旁檔）、回信＝N-30 結果、旁檔收乾淨、級數順序、deadline 插隊與同級 deadline、過期 `DeadlineMissed`、aging、`_metainfo.cost`、`BudgetExhausted`（含換日歸零）、cur/ 殘信 `KernelRestarted`、slots、`--priority` 旗標與沒 `mailbox`＝錯、SIGTERM 撤信、呼叫端看到的跟直接叫逐字一樣、錯碼、kernel 命令列（state 窗用 loop 骨架名字）、真腦（假伺服器回 usage）經閘門＋think：額度照加、history 沒有 usage。
