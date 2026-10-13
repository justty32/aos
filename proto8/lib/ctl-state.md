# ctl 與 state 的慣例

← [proto8/lib](README.md)｜上一份：[daemon](daemon.md)

NORMS N-11 的骨架是「設定檔讀一次 → ctl 蓋過 → state 回報」；下面是 lib 照著做的慣例，不是規範。實作（ctl.json、state.json 的讀寫）在 `aos_ctl_state.py`，loop、daemon 共用。

| 層 | 設定檔 | ctl | state |
|---|---|---|---|
| inst | inst.json | 沒有（跑一次，沒東西可改；要停用訊號） | **就是 exit 檔**：一個數（十進位＋換行），不是 json、不另開 state.json |
| loop | loop.json | ctl.json | state.json |
| daemon | daemon.json | ctl.json | state.json |

key 分四組，每組落在哪幾個檔是固定的：

| 組 | key | 設定檔 | ctl | state |
|---|---|---|---|---|
| 節奏 | `times`、`interval_ms`、`interval_mode` | 初始值 | 期望值（可蓋） | 生效中的值 |
| 旗子 | `paused`、`stop` | — | `{val, now}` | 併進 `state` 那格 |
| 位置／身體／收尾 | `ctl`、`ctl_poll_ms`、`state`、`inst`、`grace_ms`、`error_wait_ms`、`control_dir`、`load`、`save`、`work_dir` | 有 | 不能蓋 | 不回報 |
| 回報 | 見下面 state 骨架 | — | — | 有 |

**ctl.json**（loop、daemon 同一份）：`paused`、`stop`、`times`、`interval_ms`、`interval_mode`，規矩照 N-06～N-08。

**state.json 共同骨架**（loop、daemon 都有）：

```jsonc
{
  "id": "/abs/x.json",         // 設定檔的 realpath
  "state": "running",          // 七個狀態值之一，見下表
  "pid": 12345,                // 自己的 pid
  "runs": 2,                   // 身體跑了幾次（loop：inst；daemon：掃幾圈）
  "times": 5, "interval_ms": 1000, "interval_mode": "after",   // 節奏組＝生效中的值
  "ctl_mtime": 1760280000.123, // 上次套用的 ctl.json 的 mtime；沒有＝null
  "last_error": null           // 最後一次自己出錯的那行；沒有＝null
}
```

各層擴充：loop 加 `skipped`（fixed 跳拍數）、`last_code`（exit 檔最後一行）；daemon 加 `skipped`、`loops`（表上幾個，只寫個數；要細節用控制指令查）。

**狀態值**：一套七個（`aos_loop.STATES`），意思固定，各層用得到哪幾個不限。

| 值 | 意思 | 誰會寫 |
|---|---|---|
| `starting` | 行程起了、第一份 state 還沒寫出來 | daemon 替底下的 loop 答 |
| `waiting` | 等下一次（間隔中） | loop、daemon |
| `running` | 身體正在跑 | loop（daemon 掃一下就完，看不到） |
| `paused` | 期望 paused、身體沒在跑 | loop、daemon |
| `done` | 次數跑完（runs ≥ times），最後一份 | loop（daemon 次數到＝收工，寫 stopped） |
| `stopping` | 讀到 stop 或收到訊號，收尾中 | loop、daemon |
| `stopped` | 結束，最後一份 | loop、daemon；daemon 看到底下 loop 行程沒了也這樣答 |
