# rename：node 搬家改名（S-14、P-15）

node `a` 有 keep 任務 `sitter.py`（掛 `b/inbox` 為 `mnt/b_in`），node `b` 有 keep 任務 `peer.py`（掛 `a/inbox` 為 `mnt/a_in`），interval 100 ms。

1. 回合中途 `mv a a2`（同一層改名）；2. `mv a2 deep/x/a3`（深兩層）；3. 對搬過的 sitter 下 kill；4. restart peer。

sitter 同時用 `$AOS7_TASK`（絕對）與「相對 cwd 的 `.aos/tasks/<tid>/`」等 tock，比較兩條路。

跑：`python3 proto7-1/probes/rename/probe.py`（約 1.5 秒）。

## 結果

- daemon 50 ms 內記 `node- a`、`node+ a2`；round.json 跟著搬，回合接著數（第 5 回合起）。
- **搬家那回合不見了**：只有 keep 任務時一回合＝tick 緊接 tock，mv 常落在 tick／tock 程序執行中，它們照舊路徑寫完，把 `a/.aos/round.json`、`a/.aos/rounds.jsonl` 建回來（鬼資料夾，沒有 timeline.json 所以不算 node）；新位置的 rounds.jsonl 缺第 4 回合（3 次都是）。
- 搬過的 sitter：程序還活著，pid.json 跟著搬 → a2 認得它是活任務，keep 沒起第二份；kill 也收得到。
- 但 `AOS7_NODE`／`AOS7_TASK` 還是舊路徑：照環境變數等 tock 的任務（`aos7_fs.wait_tock` 也是）**從此收不到 tock**；用相對 cwd 的路徑照常收到（cwd 跟著資料夾走）。寫 `$AOS7_NODE/…` 會失敗，鬼資料夾出現後又「成功」寫進鬼資料夾。
- 掛載是相對符號連結：同一層改名，sitter 的 `mnt/b_in` 還通；搬到深兩層就斷。b 掛 `a/inbox` 的連結一改名就斷（ENOENT）。
- kill 搬過的 sitter：aos7-run 把真的 `exit.json`（code -15）寫回**舊路徑**（又建一次鬼資料夾）；新位置的 tock 看不到，記成 `lost`。keep 再起的新 sitter 環境正確、掛載正常。
- **restart peer**：照舊宣告重掛 `a/inbox`，tick 把不存在的目標建成資料夾（M-2），信寄「成功」但進了沒人看的鬼資料夾 `a/inbox`，寄件方看不出錯。

> **基礎設施修補之後（10-03）**：aos7-run 改成經任務資料夾的 fd 寫 exit.json，kill 搬過的任務時結束碼寫到新位置、舊路徑不再被建回來（探針的第 3 步已改成檢查這件事）。其他發現照舊，見 [infra-needs.md](../../notes/infra-needs.md)。
