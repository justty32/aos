# 02 tick 與回合：aos 的時間

← [入口](README.md)｜使用者筆記：[aos 的分層](../../2026-10-03-aos-layering.md)

## 1 是什麼

- 〔使用者〕tick 是動作、很快結束、只是起頭；tick 結束＝回合開始，tock 結束＝回合結束（筆記第 31、32、39 行）。任務一律由 tick 啟動，tick 給空間、把任務和 daemon 對接（第 41、44 行）。任務可跨回合，tock 只通知「回合結束、第幾回合」（第 42 行）。不準時無妨（第 45 行）。
- 〔使用者〕tick 是核心設施；一條 tick-tock 時間線服務一個資料夾＝一個 **node**；daemon 要支援多條時間線同時跑；node id＝相對空間根的路徑，如 `team/agents/amy`（第 50～56 行）。這不是封存的 node／kernel 登記樹（T-02）。
- 〔使用者〕基礎架構核心理論已 OK，daemon 與 tick-tock 剩技術選型、邊做邊調（第 60～61 行）。
- 〔推論〕這層只做三件事：推回合數、把任務放進 node、說出「第 N 回合結束」。不等、不殺、不看結束碼、不排程。
- 〔使用者〕tick-tock 是 kernel 對跑著的任務做 kill、restart 的時刻（第 67 行）。〔推論〕所以這層要提供時刻，不提供動作；動作是 [kernel](03-kernel.md) 的任務做的。
- 看得到：node、回合數、哪些任務還活著。看不到：pid、帳號、cgroup，停在 [daemon](01-daemon.md)。

## 2 長相

```text
tick N ┐ 回合 N ──────────┐ tock N ┐ 回合 N+1 ─ tick N+1 …
       ├ 任務 a（N 起）──結束  │        │
       └ 任務 A（N-2 起）──────┼────────┼──── 還在跑
```

- **tick**〔推論〕：認 node → 讀表 → 回合數 +1、寫「N 開始」 → 逐項啟動、不等，對接 daemon → 結束。
- **tock**〔推論〕：寫「N 結束」 → 告訴本 node 還活著的任務「N 結束」 → 結束。不收任務。
- **任務一生**：被 tick N 啟動（拿到資料夾、知道起於 N）→ 跑 → 每次 tock 收到「M 結束」→ 自己決定何時結束。
- **回合數**〔推論〕：每條時間線各數（第 54 行），接今天的 `seq`（`aos_tick_record.py` 第 101～102 行開格 +1）。今天 `ended:true` 由 tick 收尾寫（`aos_tick.py` 第 186 行、[tick.md](../../../spec/tick.md) 第 34 行），新體系歸 tock。
- **互斥**〔推論〕：「重疊只管最基本的」（第 55 行）＝同一 daemon 內一個資料夾一條時間線（B-602 那層）。今天 flock 握到整格跑完（`aos_tick.py` 第 134～141 行）；任務並存後，鎖不能握到任務結束。
- **任務表順序**：今天陣列位置＝依序跑（B-620）。〔推論〕tick 不等後只剩「依序啟動」；tasks-blocked 只擋同一次 tick 還沒啟動的項。`after_task`／`after_all` 今天在任務結束後跑（`aos_tick.py` 第 181～184 行），只能搬到 tock 或變成任務自己的事。
- **對接的線**（不定格式）：任務要能被認出屬於哪個 node、第幾回合啟動；tock 要找得到本 node 還活著的任務；daemon 要管得到它。今天 tick 只給 `AOS_TICK_CWD`、`AOS_TASK_ID`／`INDEX`（`aos_tick_run.py` 第 7 行、C-10），沒有回合數；daemon 只認得自己開的 pid（`aos_daemon_run.py` 第 37 行）。
- **怎麼給資料夾**：cwd（`aos_tick_run.py` 第 75 行）、環境變數、FUSE 路徑，可並用。「只碰 tick 給的」是約定（T-07）。

## 3 跟現況的差距

| 現況 | 新體系 |
|---|---|
| `aos-tick` 跑完所有任務才結束（`aos_tick.py` 第 161～186 行；`aos_tick_run.py` 第 75 行 Popen、第 86 行 wait） | 翻：只啟動不等 |
| `ended:true` 等 hooks 跑完才寫 | 翻：歸 tock |
| flock 握整格（B-602） | 改：不握到任務結束 |
| `seq` 開格 +1 | 留，叫回合數 |
| B-620 陣列順序＝依序跑 | 改：啟動順序 |
| daemon 週期從上次結束起算（`aos_daemon_run.py` 第 123 行；裁定 [07](../../verdicts/11-tick-as-unit/07-1001-最核心daemon.md) 第 13 行） | tick 很快結束，週期≈`interval_ms` |
| 「十個 tick≈十個 `interval_ms`」（[11-01](../../verdicts/11-tick-as-unit/01-0930-方向與追答.md) 第 12 行；[astra](../../reviews/2026-10-03-astra-layering.md) 第 110～121 行） | 「十個回合」＝十次 tock，與牆鐘無關（第 45 行），C-01 改字 |

## 4 邊緣（正常流程就會發生）

- 同 node 新舊任務並存：正常，靠「起於第幾回合」區分。
- tock 時沒任務在跑：只寫「N 結束」。
- 任務在 tock N 與 tick N+1 之間結束：不屬任何回合。
- 多條時間線各自數：kernel 的 N ≠ amy 的 N（見 [05](05-交叉例子.md)）。
- 任務比 daemon 活得久：新 daemon 找不到它，它收不到 tock；出事歸 daemon（第 36 行）。

## 5 LLM 可讀檢視

〔使用者〕操作與協議盡量用 JSON 或文字（第 7～9 行）。

| 項目 | 今天 | 符合 | 怎麼改 |
|---|---|---|---|
| 回合資訊 | `record.json`（`seq`、`ended`） | 是 | 〔建議〕node 下 JSON，tock 也寫進去 |
| 任務表 | tasks.json、inst JSON | 是 | 留 |
| 任務出生資料 | `AOS_TICK_*`／`AOS_TASK_*` 環境變數（C-10），無回合數 | 否 | 〔建議〕寫成任務資料夾裡的 JSON：誰啟動、第幾回合、屬哪個 node |
| 結束碼 | inst `exit` 文字檔；record 只記非 0（B-633） | 半 | 〔建議〕留文字檔，0 也看得到 |
| 互斥 | flock 空鎖檔（`aos_tick.py` 第 191～199 行） | 否 | 〔建議〕旁邊放 JSON 寫誰持有、哪個回合 |
| tock 通知 | 沒有 | — | 〔建議〕文字或 JSON 檔；送法留給之後 |
| kill／restart | SIGTERM／SIGKILL（`aos_daemon_kill.py` 第 49 行） | 否 | 〔建議〕一行文字或 JSON 寫進控制檔，如 plan9 提案 ctl（[03](../2026-10-02-plan9/03-daemon變成檔案伺服器.md) 第 52～58 行）、status 一行 key=value（第 66 行） |

## 6 已由筆記定下

- 回合數每條時間線各數（第 54 行）。
- 同一資料夾只管最基本的重疊（第 55 行）。
- node id＝相對空間根路徑（第 56 行）。
- tock 不收任務（第 42 行）；不準時無妨（第 45 行）。

## 7 技術問題（使用者說心裡有答案，不問）

- tock 何時進場（全結束／時間到／先到者）。〔推論〕「全結束才 tock」會讓長任務跨不了回合，跟第 42 行衝突。
- 鎖的粒度（一次 tick 動作／一整回合）。
- 誰叫 tock；週期起算。
- 結束碼誰記（tock／daemon／任務自寫 inst `exit`）。
- 時間線之間要不要對齊。
- 起始回合的 tock 算不算（例子第 43 行照字面是 tock 4、5、6）。
- tock 誰都能跑（B-627）與否；daemon 重開後回合數延不延續。

## 8 留給之後

- tock → 任務「N 結束」怎麼送：訊息交流。
- tick → daemon 對接任務：登記方式。
- kill／restart：以回合數為條件（起於 N、到 M 還活著）需要 daemon 知道啟動回合。
