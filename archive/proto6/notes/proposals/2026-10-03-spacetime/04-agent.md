# 04 agent：依託 tick-tock 換狀態的任務

← [入口](README.md)｜使用者筆記：[aos 的分層](../../2026-10-03-aos-layering.md)

## 一、它是什麼

- 〔使用者〕「有 LLM 呼叫、工具使用的，就算 agent」（筆記第 51 行）。
- 〔使用者〕核心是 idle、think、act 三態的狀態機；做法是提供一個任務，依託 tick-tock 換狀態；其他先不管（第 74～75 行）。
- 〔使用者〕主體＝node＝一條時間線服務的資料夾（第 52～54 行）；id＝相對空間根的路徑（第 56 行）。
- 〔推論〕agent 是看任務性質認定的角色，不是程式、不是資料夾類型。同一個 node 的表上也有排程任務，它就同時是 kernel（[03](03-kernel.md)）。
- 〔推論〕這個 node 不是 09-29 封存的登記樹（[T-02](../../../spec/terms.md) 第 39 行），只是「一條時間線＝一個資料夾＝一個主體」。
- 〔推論〕身分就是 `team/agents/amy` 這種路徑。10-02「絕對路徑＋Linux 帳號」（[03](../2026-10-02-agent/03-agent長相.md) 第 10、29 行）被取代。
- 〔推論〕不做：不排別人、不管資源、不自己開背景程序（任務都由 tick 啟動，第 41 行）。
- 〔推論〕被管的方式：kernel 在 tick-tock 時刻 kill／restart 它的任務（第 67 行）；要讓整個 amy 停或續，用 daemon ctl 停止／繼續她的時間線（第 69 行）。所以「睡」可以是 idle，也可以是時間線被停止。

## 二、一個任務怎麼依託 tick-tock 換狀態

〔推論〕兩種讀法，都合第 74～75 行。不問使用者，屬技術選型。

| | 甲：跨回合常駐 | 乙：每回合啟動一次 |
|---|---|---|
| 怎麼跑 | tick 啟動一次；任務收到 tock 時換狀態（第 42 行：任務可跨回合、tock 只通知） | 每回合 tick 啟動；讀狀態檔、走一步、寫回、結束 |
| 狀態在哪 | 記憶體；每次換狀態落檔，才能被 restart 接回 | 只在檔裡 |
| 長 LLM 呼叫 | think 自然跨回合 | think 那一步本身跨回合，就變回甲 |
| kill／restart 落點 | 任務中途 | 多半在回合邊界 |

- 〔推論〕兩種都需要「狀態落成檔」。差別只在記憶體裡有沒有一份。
- 〔推論〕10-02 的「一格一步」（[README](../2026-10-02-agent/README.md) 第 9 行）就是乙；它的五項任務表（03 第 45～58 行）可當乙的長相。
- 〔推論〕T-06「一輪 agent＝一次計算」（[terms](../../../spec/terms.md) 第 40 行）兩種都算。

```text
team/agents/amy/
  .aos/tasks.json          tick 啟動什麼
  .aos/tick/current/       回合紀錄（record.json）
  state/agent.json         目前在 idle／think／act 哪一態、第幾回合換的
  state/ 其他              記憶、對話（細節先不管）
```

## 三、跟現況的差距

- 現行沒有 agent：proto6 `lib/` 只有 `aos_exec.py` 第 22 行註解提到；proto5 `lib/aos_agent*.py` 沒搬。
- 今天 `aos-tick` 等每項跑完（`aos_tick_run.py` 第 86 行）、整格握鎖（`aos_tick.py` 第 134～141 行）。甲做不到，要等 [02](02-tick與回合.md) 的 tick 改。乙今天能跑，但長 LLM 呼叫會卡住整格。
- tick 不給逾時（`aos_tick_run.py` 第 15 行），LLM 任務得自備。
- 10-02 的「睡＝paused、醒＝grant 到私門」（README 第 9 行）改為：睡＝idle 或時間線被 ctl 停止；醒＝ctl 繼續。門與信屬訊息交流，留後。

## 四、邊緣（正常流程會發生）

- 甲：amy 的 tick 每回合還會啟動東西，同 node 新舊任務並存（[05](05-交叉例子.md)）。怎麼避開屬技術選型。
- kill 落在 think 中：那次 LLM 呼叫白做；restart 後從狀態檔接回。
- 乙：tock 時多半沒任務在跑，tock 照寫，沒人收。
- 工具是 LLM 任務的子程序時，核心不清後代（[B-602](../../../spec/tick.md) 第 15 行）。
- 〔使用者〕重疊只管最基本的（第 55 行）。〔推論〕kernel 的 node 包住 amy 是正常；kernel 讀寫 amy 的檔沒有鎖保護（鎖只護 tick，`aos_tick.py` 第 191 行）。

## 五、LLM 可讀檢視

〔使用者〕操作和協議盡量用 JSON 或文字，讓 LLM 讀得懂、好用（第 7～9 行）。

| 項目 | 今天是什麼 | 符不符合 | 〔建議〕怎麼改 |
|---|---|---|---|
| agent 狀態 | 沒有 | — | node 下一個 JSON 檔 |
| 任務表 | `tasks.json` | 符合 | — |
| 回合資訊 | `record.json`，`$ref` 拆檔（`aos_tick_record.py` 第 6～8 行） | 符合 | agent 看回合就讀它 |
| 出生資料（誰啟動、第幾回合、屬哪個 node） | 環境變數 `AOS_TICK_CWD`、`AOS_TASK_ID`（`aos_tick_run.py` 第 6～7 行、[C-10](../../../spec/conventions.md) 第 43 行起） | 不符：LLM 看不到 env | 任務資料夾裡一個 JSON |
| tock 通知 | 沒有 | — | node 下的 JSON（怎麼送留後） |
| kill／restart | SIGTERM 再 SIGKILL（`aos_daemon_kill.py` 第 49 行） | 不符：訊號不是文字 | 控制檔寫一行文字或一行 JSON（plan9 [03](../2026-10-02-plan9/03-daemon變成檔案伺服器.md) 第 49～59 行） |
| 時間線停止／繼續 | socket 一行 JSON（`aos_daemon_ctl.py` 第 4 行；[第二十五批](../../verdicts/11-tick-as-unit/26-1002-第二十五批.md)） | 半：是 JSON 但不是檔 | 同上；狀態讀一行 key=value（plan9 03 第 66 行）或 JSON |
| 結束碼 | 只記非 0（[B-633](../../../spec/tick.md) 第 31 行） | 半：只有數字 | 任務自寫結果 JSON |
| 鎖 | `tick.lock` 空檔 flock（`aos_tick.py` 第 197 行） | 不符：讀不出誰持有 | 技術選型 |
| LLM 呼叫 | 10-02 `request.json`／`response.json`（03 第 53 行） | 符合 | — |

不定欄位。

## 六、已由筆記定下

- agent＝有 LLM 呼叫、工具使用的任務（第 51 行）。
- 核心＝idle／think／act 狀態機，一個任務依託 tick-tock 換狀態（第 74～75 行）。
- 身分＝相對空間根的資料夾路徑（第 56 行）。
- 任務可跨回合，tock 只通知（第 42 行）。
- kernel 在 tick-tock 時 kill／restart 任務，用 ctl 停止／繼續時間線（第 67、69 行）。
- 重疊只管最基本的（第 55 行）。

## 七、技術問題（使用者說心裡有答案，不問）

- 甲還是乙、狀態檔放哪。
- 同 node 新舊任務並存怎麼避開。
- 回合節奏、時間線之間怎麼對照、起始回合的 tock 算不算。
- 失敗與結束碼怎麼被看見。
- 一 agent 一帳號與否。

方向題由 [README](README.md) 統一收，本檔不另問。

## 八、留給之後

- kill／restart 細節：kernel 停掉 think 中的任務。
- 訊息交流：tock 怎麼通知任務；agent 之間的門與信。
- 權限：帳號、誰能寫 amy 的控制檔。
- agent 細節：記憶、工具、prompt（第 75 行「先不管」）。
