# fleet：一個 daemon 管 150 條時間線

一個 daemon 管 150 個 node（`g0/n000`…，分在 10 個資料夾下），一半是 keep 任務（`sleep 60`），一半是 each 任務（`true`），interval 100～500 ms。量 5 秒，再 pause 一條、最後 stop --kill。

想讓基礎設施露出的事：規模變大時，哪一段先撐不住（每回合起的 Python 程序、每圈全掃、thread、記憶體）。

跑：`python3 proto7-1/probes/fleet/probe.py`（`FLEET_N`、`FLEET_WINDOW` 可調）。約 20 秒，會吃掉十幾核。

## 結果（16 核機器，3 次）

| 量 | 數字 |
|---|---|
| 第一次掃描起完 150 條迴圈 | 11.6～12.3 秒；這段時間 status.json 沒寫、控制檔（含 stop）沒人處理 |
| tick＋tock 程序 | 每秒 ~544 個，每個 ~22 ms CPU，合計 ~12 核 |
| 回合實際間隔 / interval | 中位 1.8 倍、p90 ~4 倍、最大 ~5.5 倍；回合只跑到該有的 ~45% |
| daemon 主迴圈一圈（設計是 ~20 ms） | 中位 ~115 ms、最大 ~220 ms |
| daemon 本身 | 0.43 核、151 thread、32 MB |
| aos7-run 包裝程序 | 每個 14 MB；75 個 keep 任務 ≈ 1 GB（任務本身是 `sleep`） |
| status.json | ~15 KB（每圈整個重寫） |
| scan_nodes／live_tasks 全掃（任務資料夾 ~2400 個，在探針裡單獨量） | ~2 ms／~20 ms（機器忙時量到過 194 ms） |
| pause：寫控制檔→處理完／→status 顯示 | 50～150 ms／410～560 ms |
| stop --kill（~78 個活任務） | 1.2 秒收完，kill 75 筆、0 失敗 |

## 發現

- 最先撐不住的是**每回合兩個 Python 程序**（tick、tock）：一核大約只撐得住每秒 22 個回合。150 條 × 平均 ~4 回合／秒就把 16 核機器吃滿，daemon 主迴圈、時間線 thread 跟著排不到 CPU。
- 第一次掃描在主迴圈裡一條一條起 thread，機器一忙每起一條要等上百 ms；全部起完前主迴圈一直卡在 `scan()`，status 與控制檔都停擺。
- 每個任務外面套一個 aos7-run Python 包裝（14 MB），keep 任務多時記憶體都花在這裡。
- status.json 每圈對每個 node 做 live_tasks（讀 pid.json、看 /proc），任務資料夾只增不減（P-12），這項只會越來越慢。
- stop --kill 很快，沒有留下任務。
