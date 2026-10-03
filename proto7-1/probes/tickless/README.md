# 探針 tickless：一百個閒著的 node，有信才開回合

← [probes](../README.md)｜出處：[Linux 報告 §10.3](../../notes/research/2026-10-03-linux-kernel-borrow.md)（NO_HZ，D-16）

**是什麼**：100 條時間線，interval 都是 1 秒。約 15 秒，會用到幾個核，不打 LLM。

- `n/000`～`n/094` 是收信的 agent。每個 tock 處理 inbox，再寫 `idle.json`＝`{"idle_safe": inbox 空了沒, "round"}`，宣告「沒信時跳過回合也沒關係」。
- `n/095`～`n/099` 是每 3 回合做事的 cron，`idle_safe` 永遠是 false。
- kernel `k` 掛 `.aosd` 與 100 個 node，每 20 ms 看一圈：
  - 沒停、`idle.json` 是這回合寫的、`idle_safe`、inbox 空 → pause。
  - 停著而且 inbox 有信 → `resume rounds 1`：跑一回合讓 agent 收信，daemon 跑完自己停回去。

分三段，各 3 秒、各隨機丟 15 封信：

| 段 | kernel 做什麼 |
|---|---|
| A 照回合 | 不動 |
| B tickless | resume |
| C tickless | resume 之後緊接一個 `wake` |

## 結果（5 個 check 全綠，連跑 3 次）

| | A 照回合 | B 只 resume | C resume＋wake |
|---|---|---|---|
| 每秒回合（100 條合計） | 100 | 10 | 10 |
| 每秒 tick＋tock 程序 | 200 | 20 | 20 |
| daemon＋它等的 tick／tock 程序 CPU（秒／秒） | 4.1～4.4 | 0.5 | 0.5 |
| daemon 本身 CPU（秒／秒） | 0.2 | 0.12 | 0.12～0.14 |
| 信延遲 ms 中位／最大 | 480～620／930～1000 | 70～90／430～790 | 70／90～100 |
| 信延遲（回合） | 1 | 1 | 1 |

- **省下約 90% 的 tick／tock 程序與 CPU**。剩下的是 5 條 cron（每秒 10 個程序），加上每封信一次 resume（一個 tick、一個 tock）。kernel 只花了 95 個 pause，停好 95 條不到 0.1 秒。kernel 自己輪詢每秒約 0.02 CPU 秒。
- **cron 沒被停**，照樣有回合。信全部都處理了，沒有睡死的 node。
- **只 resume 會慢**：resume 不打斷「等上一回合 interval 滿」的睡眠。node 剛被 pause 不到 1 秒就來信的話，resume 後要等上一回合的 interval 跑滿才開回合，B 最慢 790 ms。C 在 resume 之後補一個 `wake`，最慢 100 ms。
- **全停時 daemon 本身仍約 0.1 CPU 秒／秒**：主迴圈照樣每 20 ms 一圈，每圈寫一份含 101 個 node 的 status.json。
- **kernel 是常駐的輪詢者**：信到了沒，沒有任何事件告訴它，只能每 20 ms 掃 100 個 inbox 加上 status.json。它自己那條線的回合沒有用處，它本身就是一個「回合外」的 watcher。

## 逼出的 daemon／tick 需求

- **N-83（對應 D-16，可以）事件式喚醒**。現在做得到 tickless，但要一個常駐 kernel 自己輪詢 inbox，還要靠跟 agent 自己約的 `idle.json`。daemon 不知道：
  - 哪條線可以跳過回合；
  - 該看哪個資料夾；
  - pause 是因為「沒事」還是「被罰」。

  最小的補法是 timeline.json 可宣告 `wake_on: ["inbox"]` 加 `idle_safe` 的來源檔，daemon 在 paused 時看那些資料夾，有變化就跑一回合；status 記 `wake_reason`。不做也行，現有基底已經省下 90%。
- **N-84（可以，小）resume 要一起打斷 interval 的等待**。`resume` 後 node 還在 `sleep_until(上一回合 tick＋interval)`，要另外補一個 `wake`。這個慢法在 B 量得到（最慢 790 ms 對 100 ms）。補法二選一：
  - daemon 收到 resume 時順便設 `kick`；
  - spec 與卡寫明「resume 後想馬上開回合要再 wake」。
