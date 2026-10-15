# ctl 與 state 的慣例

← [proto8/lib](README.md)｜上一份：[daemon](daemon.md)

NORMS N-11 的骨架是「設定檔讀一次 → ctl 蓋過 → state 回報」；下面是 lib 照著做的慣例，不是規範。實作（ctl 窗、state 窗的讀寫）在 `aos_ctl_state.py`，loop、daemon 共用。

| 層 | 設定 | ctl | state |
|---|---|---|---|
| inst | inst.json／stdin／旗標 | 沒有（跑一次，沒東西可改；要停用訊號） | 沒有（不開窗；exit 檔只是與舊時代的橋樑，暫定 e） |
| loop | loop.json／stdin／旗標 | ctl 窗（必填，N-19） | state 窗（必填，N-19） |
| daemon | daemon.json（loop.json 的超集）／stdin／旗標 | ctl 窗（必填） | state 窗（必填）；子項另有 table 窗 |
| fsm | fsm.json／stdin／旗標 | 沒有（不開 ctl：暫停、停止交給拍它的 loop，N-39） | state 窗（必填，N-19）；只記 `phase`，不套下面的骨架、不寫時間與 pid（N-39，見 [fsm](fsm.md)） |

key 分四組，每組落在哪幾個檔是固定的：

| 組 | key | 設定 | ctl | state |
|---|---|---|---|---|
| 節奏 | `times`、`interval_ms`、`interval_mode` | 初始值 | 期望值（可蓋） | 生效中的值 |
| 旗子 | `paused`、`stop` | — | `{val, now}` | 併進 `state` 那格 |
| 回音 | `seq` | — | 流水號（寫的人帶） | `ctl_seq`＝上次採用的那份的 seq |
| 位置／身體／收尾 | `ctl`、`ctl_poll_ms`、`state`、`inst`（loop 必填、daemon 選填：每拍的身體）、`grace_ms`、`error_wait_ms`、`id`；daemon 另有 `children`、`policies`、`ctl_dir`、`table`、`load`、`work_dir` | 有 | 不能蓋 | 不回報 |

**ctl 窗**（loop、daemon 同一份）：`paused`、`stop`、`times`、`interval_ms`、`interval_mode`、`seq`，規矩照 N-06～N-08。回音以序號為準（N-14）：daemon 寫子 loop 的 ctl 時把 seq 加一，等子 loop 的 state 回報 `ctl_seq` 趕上。

**state 窗共同骨架**（loop、daemon 都有）：

```jsonc
{
  "id": "/abs/x.json",         // 設定的 id（沒寫＝設定檔的 realpath#/位置；從 stdin 來又沒寫＝null）
  "state": "running",          // 七個狀態值之一，見下表
  "pid": 12345,                // 心跳（N-17）：自己的 pid
  "started": 1050011,          // 心跳：啟動時間（/proc/<pid>/stat 第 22 欄）；pid＋它對得上＝同一個行程
  "boot_id": "45db…",          // 心跳：開機 id
  "runs": 2,                   // 身體跑了幾次（loop：inst；daemon：拍數）
  "times": 5, "interval_ms": 1000, "interval_mode": "after",   // 節奏組＝生效中的值
  "last_error": null,          // 最後一次自己出錯的那行；沒有＝null
  "last_warning": null,        // 跑起來後預料到、不結束也不算錯的意外（「代號: 白話」）；沒有＝null
  "ctl_seq": 3,                // 上次採用的 ctl 的 seq；沒有＝null
  "beat": 1791985930.186       // 寫的那一刻（epoch 秒）；內容沒變也每秒碰一次
}
```

各層擴充：loop 加 `skipped`（fixed 跳拍數）、`last_code`（aos_inst 結果的 code）、`signal`（被哪個訊號停掉；沒有＝null，10-15 晚起退出碼不再用 128＋N 說）；daemon 加 `skipped`、`last_code`、`loops`（表上幾個；要細節用控制指令查）。daemon 回答子項的 `get`／`list` 時多一格 `phase`（子項六態）。

**`last_warning`**（10-15 使用者「都按照推薦。」，[盤點 S1](../thinking/2026-10-15-principles.md)）：以前寫 stderr 的警告改記這裡——N-43 正常退出不在 stderr 噴東西。loop：ctl 窗壞檔、不見了、讀不了（`CtlBad`／`CtlMissing`／`CtlReadFailed`，讀到好的那份就清回 null）。daemon 再加表那邊最近一件（`PolicyFailed`、`RestartFailed`、`TableWriteFailed`、收工時寫不了子項 ctl 的 `WriteFailed`；ctl 窗的優先）。寫 state 窗時，窗所在的那一層資料夾沒有就建一層（不 -p；frame 的 `loop/state.json`、`fsm/state.json` 靠這條，10-15 盤點 P3）。**state 窗自己寫不了**（`StateWriteFailed`，例：再上層也沒有）沒地方記＝窗壞了，同 N-19 窗缺：收掉身體、結束、stderr 一份錯誤、退 1。

**狀態值**：一套七個（`aos_loop.STATES`），意思固定，各層用得到哪幾個不限。daemon 子項的六態 `phase` 是另一套，在 table 窗（暫定 b：撞名不改）。

| 值 | 意思 | 誰會寫 |
|---|---|---|
| `starting` | 行程起了、第一份 state 還沒寫出來 | daemon 替底下的 loop 答 |
| `waiting` | 等下一次（間隔中） | loop、daemon |
| `running` | 身體正在跑 | loop、daemon（有 inst 時） |
| `paused` | 期望 paused、身體沒在跑 | loop、daemon |
| `done` | 次數跑完（runs ≥ times），最後一份 | loop、daemon |
| `stopping` | 讀到 stop 或收到訊號，收尾中 | loop、daemon |
| `stopped` | 結束，最後一份 | loop、daemon；daemon 看到底下 loop 行程沒了也這樣答 |
