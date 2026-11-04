# 03 kernel：在 tick-tock 時刻管任務的排程任務

← [入口](README.md)｜使用者筆記：[aos 的分層](../../2026-10-03-aos-layering.md)

## 1 它是什麼

- 〔使用者〕kernel 跑在時空上（筆記第 18 行）。有資源管理、排程任務的就算 kernel（第 51 行）。
- 〔使用者〕管理單位是任務，時間單位是 tick-tock（第 66 行）。管任務＝在 tick-tock 時對跑著的任務 kill、restart（第 67 行）。資源與排程算法隨意（第 68 行）。
- 〔使用者〕管另一條時間線＝下 daemon ctl 讓它停止或繼續（第 69 行）。管轄範圍先不管（第 70 行）。
- 〔推論〕kernel 是角色，不是程式或資料夾類型。node 任務表有排程任務就是 kernel；同表再有 LLM 任務，也是 agent。
- 〔推論〕node＝一條時間線服務的資料夾（第 53～54 行），id＝相對空間根的路徑（第 56 行）。不是 09-29 封存的登記樹（[T-02](../../../spec/terms.md) 第 39 行）。
- 〔推論〕手上兩種對象：跑著的任務（kill／restart）、別的時間線（停止／繼續）。都在 tick-tock 時刻動。
- 〔推論〕感官只有讀檔與回合數。看不到 pid、cgroup、帳號〔使用者，經 thread-vs-process 轉述〕。量測仍是合作式（[astra-layering](../../reviews/2026-10-03-astra-layering.md) 第 199～243 行）。
- 不做：啟動任務。只有 tick 能（第 41 行）。

## 2 具體長相

```text
team/                       ← kernel 的 node（id `team`）
  .aos/tasks.json           ← 一項排程任務
  .aos/tick/current|last/   ← 自己的回合
  policy.json members.json  ← 政策；成員 node id
  state/<成員>.json         ← 讀到的成員摘要＋來源回合
  agents/amy  agents/bob    ← 成員 node（巢狀正常）
```

- 一回合：收（讀成員紀錄與摘要）→ 判（照 policy）→ 動（kill／restart 任務，或 ctl 停止／繼續時間線）。
- 〔推論〕「讓成員醒」已有答案：繼續它的時間線，或 restart 它的任務。期望檔降為一種做法：成員任務自己讀的政策資料。擋板（`aos_tick.py` 第 147、209～224 行）是 tick 自己認的另一種停法。
- 〔推論〕多層兩條路，都不需要政策樹等於資料夾樹：
  - ctl 跨時間線：同 daemon 直接下；別的 daemon 走路二寫它的控制檔（第 84 行）。
  - 路一（第 83 行）：上層 tick 生任務開子 daemon。對上層 kernel 它是普通任務，kill／restart 就管住整個子 daemon。
- 〔推論〕往下需要兩條線：kernel→任務、kernel→時間線。長相留給之後。

## 3 跟現況的差距

| [10-02 kernel 03](../2026-10-02-kernel/03-推薦方案.md) | 站不站 |
|---|---|
| 資料夾放政策、名單、成員狀態（第 9～19 行） | 站 |
| kernel 擁有 `daemon.json`（第 13、21 行） | 翻：daemon 是運行層 |
| 成員預置 paused、寄 grant 叫醒（第 36、57 行） | 改：叫醒＝ctl 繼續時間線 |
| 收判套報（第 40～66 行） | 站；套＝kill／restart／ctl |
| cgroup、帳號分資源（第 73、75 行） | 翻：拉出 daemon（轉述） |
| 多層＝daemon 跑 daemon（第 86～102 行） | 換意思回來：路一，核心不知從屬 |

- 現行程式沒有 kernel。[11-01](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md) 第 14 行「排程是掛在 tick 任務表上的程式」站。
- 零件在 daemon：`aos_daemon_ctl.py` 第 29 行有 wake／pause／resume／status／kill／restart。對象是 daemon 的一項，不是時間線，也不是 tick 啟動的單一任務。
- daemon 的 kill 整項殺，連 tick 帶任務（`aos_daemon_kill.py` 第 11～16 行）。單一任務今天沒人能殺：tick 自己 Popen 再 wait（`aos_tick_run.py` 第 75、86 行）。
- 〔推論〕一項＝一條時間線時，pause／resume 一項就近似停止／繼續時間線。

## 4 邊緣（正常流程就會發生）

- kernel 第 N 回合讀到成員第 M 回合。只能記來源回合，不是同時快照。
- 成員任務跨回合：連幾回合「還在跑」，分不出長任務與卡住。殺不殺是政策。
- 動作只在 tick-tock 時刻。任務在兩個時刻之間出事，最快下個時刻才處理。
- 停止時間線不等於 kill 它的任務。停了以後跨回合任務照跑。
- kernel 任務自己跨回合：下回合 tick 再啟動一個，新舊並存同寫 `state/`。
- 巢狀：kernel 能寫成員 `tasks.json`＝能用成員身分（[T-08](../../../spec/terms.md) 第 41 行）。別的 daemon 動同一資料夾＝外部世界（T-07 第 13 行）。
- 兩個 kernel 互停：成環不管（第 85 行）。

## 5 LLM 可讀檢視

〔使用者〕操作和協議盡量用 JSON 或文字（第 7～9 行）。

| 項目 | 今天 | 符不符合 | 〔建議〕改成 |
|---|---|---|---|
| kill／restart | SIGTERM→SIGKILL（`aos_daemon_kill.py` 第 38～57 行） | 不符：訊號沒有文字，結果也讀不到 | 一行文字或 JSON 寫進任務控制檔；結果寫 JSON |
| 停止／繼續時間線 | `aos-ctl` 連 socket 送一行 JSON（`aos_daemon_ctl.py` 第 97～104 行） | 半符：是 JSON，不是檔 | 寫進時間線控制檔；plan9 提案的一行文字（[03](../2026-10-02-plan9/03-daemon變成檔案伺服器.md) 第 47～61 行） |
| 時間線狀態 | ctl status 回 JSON（`aos_daemon_ctl.py` 第 179～183 行）；plan9 提案一行 key=value（第 63～69 行） | 符，但不是檔 | node 下 JSON 檔 |
| 回合資訊 | `record.json` | 符 | 照舊 |
| 任務出生資料 | 環境變數 `AOS_TICK_CWD`、`AOS_TASK_ID`（`aos_tick.py` 第 269～274 行）、`AOS_DAEMON_*`（`aos_daemon_run.py` 第 163～180 行） | 不符：kernel 看不到別人的環境 | 任務資料夾裡的 JSON |
| 任務在不在跑 | pid、空鎖檔（`aos_tick.py` 第 191～203 行） | 不符：讀不出誰持有 | 狀態寫 JSON |
| 任務結果 | 只記非 0 結束碼（`aos_tick.py` 第 179 行，B-633） | 半符 | 記進 JSON，含原因 |
| 政策、名單、摘要、擋板 | JSON；`tasks-blocked` 可放 `{"kinds":[…]}` | 符 | 照舊 |

欄位不定。

## 6 已定與技術問題

已由筆記定下：
- 排程單位＝任務，時間單位＝tick-tock（第 66 行）。
- 讓成員醒＝ctl 繼續時間線、restart 任務（第 67、69 行）。
- 資源與排程算法隨意（第 68 行）。
- 各時間線各自數回合（第 54 行）。
- 巢狀放行（第 55 行）；成員鍵＝node id（第 56 行）。
- 多層：ctl、路一、路二（第 69、83、84 行）；成環不管（第 85 行）。

技術問題（使用者說心裡有答案，不問）：
- kernel 怎麼看見各 node 的任務。
- 量不到真實資源。
- 任務表誰能改。
- 不同時間線的回合怎麼對照；kernel 能否調節奏。
- 失敗與結束碼怎麼被看見。
- 〔推論〕kernel 任務每回合一格或跨回合；同 node 兼 agent 時誰排前。

## 7 留給之後

- kill／restart 細節：怎麼送、等多久、restart 算不算新任務。
- kernel→任務、kernel→時間線的線怎麼長。
- 權限：誰能 ctl 誰（第 69、84 行）。
- 管轄範圍（第 70 行）。
- 成員→kernel 的提醒；tock 怎麼通知跨回合的 kernel 任務。
