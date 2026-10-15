# LLM kernel（閘門 `aos_gate.py`＋身體 `aos_gate_kernel.py`）

← [proto8/lib](README.md)｜規範：[N-42](../NORMS/09-kernel.md)（第一種：管 LLM 呼叫）｜概念：[C-47](../CONCEPTS/04-kernel.md)｜決定：[thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)、[LLM kernel 優先級](../thinking/2026-10-15-llm-kernel.md)｜demo：[demo/kernel](../demo/kernel/run.py)（`python3 proto8/demo/run.py kernel`）

> **基礎實作（N-18 最簡單的）、還不是規範。** 動工時自己定的點列在 [thinking LLM kernel「動工自定點」](../thinking/2026-10-15-llm-kernel.md#動工自定點)。

兩支：**閘門**包住要排隊的 inst（例：腦），**kernel** 是 daemon 底下一個 loop 每拍跑一次的身體。中間是一個信箱資料夾（N-16 Maildir）。

```
呼叫者 ──N-12──▶ aos_gate.py ──信──▶ 信箱 tmp/→new/ ──▶ aos_gate_kernel.py（每拍：挑一封、new/→cur/、aos_inst 真跑）
        ◀─stdout／碼──        ◀──────── reply/<名> ◀─────────────── 回信
```

## 閘門 `aos_gate.py`

```
python3 aos_gate.py [--target T] [--kernel DIR] [--wait-ms N] [GATE.json]     # stdin＝原樣轉給真正的 inst
```

```jsonc
// gate.json（相對路徑從呼叫者的 cwd 算）
{"target": "brain.json",              // 真正要跑的 inst：TARGET（可接 #/位置）或內嵌一張 inst（必填）
 "kernel": {"$env": "AOS_KERNEL"},    // 信箱資料夾；沒寫＝環境變數 AOS_KERNEL
 "priority": "low",                   // 選填：純量＝{"level": 值}；物件 {"level", "deadline", …} 照帶；沒寫＝環境變數 AOS_PRIORITY
 "wait_ms": 60000}                    // 選填：排隊（信還在 new/）最多等多久；沒寫＝不限
```

- **換腦一行**：agent.json 的 `brain` 指到一張跑閘門的 inst（`{"argv": ["python3", ".../aos_gate.py", "gate.json"]}`），其他不動。
- **信**（`new/<奈秒時間>.<pid>.json`，名字字典序＝先來後到）：`{kind, inst（解好、路徑絕對）, stdin（文字）, priority, _metainfo（target 的，照抄）, reply, sent}`。
- **呼叫端看到的＝直接叫 target**：stdout、stderr 原樣、退出碼＝target 的碼（測試逐字比過）。
- 錯（stderr 一份 N-29、退出 125）：`QueueTimeout`（排隊超過 `wait_ms`，信撤回）、kernel 回的 `DeadlineMissed`／`BudgetExhausted`／`KernelRestarted`、設定不對、`Usage`（不收 `-`：stdin 是請求本身）。kernel 那邊 target 起不來＝照 aos_inst 的碼（例 127 `CommandNotFound`）。
- SIGTERM／SIGINT／SIGHUP：信還在 new/ 就撤掉、退出 128＋N；已被拿走的讓它跑完，回信沒人收（留在 reply/）。
- target 在 kernel 的環境跑（環境變數＝kernel 的＋target 的 `envs`，不是呼叫者的）；stdin／stdout／stderr 被閘門蓋掉（同 fsm 的格）。

## kernel `aos_gate_kernel.py`

```
python3 aos_gate_kernel.py [--key 值 ...] [KERNEL.json | -]
```

| key | 意思 |
|---|---|
| `mailbox` | 信箱資料夾（必填） |
| `state` | state 窗（必填，N-19）：`{tick, seen（每封信第一次看到的拍）, budget: {limit, used, day}, served, updated}` |
| `slots` | 一拍最多跑幾封（1）；>1＝同一拍幾封一起跑，等最慢的跑完這拍才結束 |
| `budget` | 一天的 token 額度（null＝不限）；用量＝回信 stdout 最後一份的 `usage.total_tokens`，沒有＝0；換日歸零 |
| `aging_ticks` | 每等幾拍升一級（10） |
| `near_ms` | deadline 剩不到這麼久＝插隊（30000） |
| `log` | 選填：每處理一封追加一行 JSON（demo 拿來看順序） |

**一拍**（跑一次＝一拍；被 aos-loop 拍，loop 掛在 aos-daemon 底下）：

1. `cur/` 裡還有信＝上一拍跑到一半被收掉 → 回 `KernelRestarted`、刪信，不重跑（N-20）。
2. 讀 `new/`：deadline 已過＝回 `DeadlineMissed` 丟掉；額度見底＝每封回 `BudgetExhausted`（不排隊、不等額度回來）。
3. 排序：**deadline 快到**（剩不到 `near_ms`）的插隊、越近越前 → **有效級數**高的先（`low`／`normal`／`high`＝-1／0／1，數字取正負號，不認得＝0；有效＝級數＋等了幾拍 // `aging_ticks`）→ deadline 近的先 → `_metainfo.cost` 小的先（沒寫＝0）→ 先來後到。
4. 認領前 `slots` 封（new/→cur/，被撤走的跳過），蓋 stdin／stdout／stderr、`aos_inst.run()` 跑、寫回信 `{result, stdout, stderr}`、刪信。

stdout 一份 `{tick, served, dropped, waiting, budget}`；設定不對＝stderr 錯誤、退出 125（`state` 沒寫＝`WindowMissing`）。

## 慣例：只包葉子

kernel 一格一次一封。**只包腦（或單一貴工具）**：boss 的腦回完才去叫 clerk，clerk 的腦再排隊，一格就夠（demo 第 3 段）。要是包了「會再叫別人的工具」（例：整個 `ask`），它佔著格等裡面的腦，裡面的腦排不到＝卡死；使用者 10-15 定「卡死就卡死」，不做機制，靠這條慣例。

## 測試

`tests/test_gate.py`（15 個）：級數順序、deadline 插隊與同級 deadline、過期 `DeadlineMissed`、aging、`_metainfo.cost`、`BudgetExhausted`（含換日歸零）、cur/ 殘信 `KernelRestarted`、slots、`QueueTimeout` 撤信、SIGTERM 撤信、呼叫端看到的跟直接叫逐字一樣、錯碼、kernel 命令列。
