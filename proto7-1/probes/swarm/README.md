# swarm：一回合幾十個短命任務（map／reduce）

跑：`python3 proto7-1/probes/run_all.py swarm`（約 10 秒）。

## 是什麼

同一個 daemon 上分幾段，一段一個 node：

- **A `each50`**（interval 300 ms）：tasks.json 寫 50 個同名 `map`（each）＋同回合 `reduce same`＋下回合 `reduce next`，跑 14 回合。map 算一塊寫 `out/r<回合>/<i>.json`，`(回合+i)%23==0` 的故意 exit 3。
- **B `disp`**（150 ms）：一個常駐調度任務每收到 tock、確認上一批都結束，就寫 40 個 `spawn/*.json`，跑 5 批。**B2 `disp2`**：同樣，但每寫一個 spawn 停 3 ms。
- **N `names`**：tid 撞名（同名多份、名字裡帶 `-r1`、`a/b` 對 `a_b`）。
- **C `bloat`／`clean`**（100 ms）：bloat 先塞 4000 個已結束的任務資料夾，跟乾淨的 node 比。

## 想讓基礎設施露出什麼

tick 起很多任務要多久、提前 tock 什麼時候到、reduce 怎麼知道 map 全完了、map 失敗怎麼被看到、任務資料夾累積的代價。

## 結果（一次典型的數字）

- **tick 起 52 個任務**：tick 工作 p50 133 ms（不含 tick 自己 Python 啟動），40 個約 80 ms。tock 只要 8 ms。
- **提前 tock**：A（interval 300）14/14 回合提前，tick→tock p50 200 ms。B（interval 150）tick 就吃掉大半個 interval，只有 1～3/5 提前。interval 從 tick 開始前算，tick 本身越慢，越沒機會提前。
- **「這批都結束了」沒有訊號**：同回合 reduce 要等 `round.json` 的 `started` 出現自己（＝清單完整），再一個一個輪詢 50 個 `exit.json`。下回合 reduce 讀 `rounds.jsonl` 上一回合那行就夠（50/50 都在 `ended`），但前提是那回合是提前 tock。tock.json 不說這次是提前還是到時，`early` 只在 daemon 的 `log.jsonl`。
- **map 失敗**看得到：`exit.json` 的 code＝3，`rounds.jsonl` 的 `ended` 也有（28 筆，兩邊對得上）。
- **一批 spawn 不是原子的**：B2 每批寫 40 個檔約 120 ms，3 批全被下個 tick 拆成兩回合起（`[[1,[2,3]],[3,[4,5]],[5,[6,7]]]`）。調度的 keep 任務只能自己數「這批起了幾個」。
- **調度不能是 tasks.json 的 keep**：做完自己結束，下個 tick 又被起回來從第 1 批再派（D-3）。改用一次性 spawn 起。
- **tid**：同名 50 份是 `map-r1`、`map-r1-2`…`map-r1-50`，不撞。`a/b` 和 `a_b` 變成 `a_b-r1`、`a_b-r1-2`，看起來像同一個任務的兩份，要讀 birth.json 才分得出。
- **只增不減**：14 回合就有 728 個資料夾、3640 檔、11.8 MB（一個短命任務約 16 KB 磁碟）。rounds.jsonl 每回合 2.5 KB。
- **掃描變慢（C，4000 個資料夾）**：tick 4→56 ms、tock 3→46 ms，interval 100 的回合週期變成 150 ms；daemon 自己 CPU 從 ~10% 變 ~52%（每 20 ms 寫 status.json 都全掃 `live_tasks`，4000 個一次 12 ms）。照 A 的速度（52 個／300 ms）約 25 秒就到 4000 個。

> **使用者 10-03 Q3 選 (a) 之後**（tock 把結束超過 `keep_ended_rounds` 回合的任務資料夾搬到 `.aos/tasks-old/`；探針加了 D 段 `arch`，跟 C 段 `bloat` 一樣塞 4000 個已結束的資料夾，但 `keep_ended_rounds: 0`）。同一次跑、兩次的範圍：
>
> | | tick 工作 ms p50 | tock 工作 ms p50 | 回合週期 ms p50（interval 100） |
> |---|---|---|---|
> | 沒有舊資料夾（clean） | 4～7 | 3～4 | 100～101 |
> | 4000 個留在 tasks/（bloat，搬之前的行為） | 53～70 | 63～86 | 164～206 |
> | 4000 個搬到 tasks-old/ 之後（arch） | 4～5 | 3 | 100 |
>
> 搬的那一次 tock 要 85～110 ms（只發生一次）。daemon 自己的 CPU：修補前塞 4000 個時是 52%。status 的 live 改成每 0.25 秒重算之後，同一情境降到 12～13%，D 段量到 15～17%。D 段時整個 daemon 上還有其他段留下的 node 在跑，所以這個數不能拿來跟 C 段直接比。
