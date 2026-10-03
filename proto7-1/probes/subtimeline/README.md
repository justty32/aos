# subtimeline：任務在執行中生出／收掉子時間線

**是什麼**：node `p` 上的 keep 任務 `maker.py`（假 agent，照 `p/orders/*.json` 做事）在執行中建新 node（寫 `.aos/tasks.json`＋`.aos/timeline.json`）：建在自己 node 底下（`p/sub/*`）、經過掛載建在外面（`q/c`）、不經掛載直接建（`z/d`）。子時間線上跑 `true`（each）與 `sleeper.py`（keep，每 50 ms 寫 `work/hb.txt`）。再試各種收法：rm -rf（上面有活任務）、先 pause 再刪、只刪 timeline.json、同名重建；最後由探針對 5 ms 的時間線連刪 8 次看會不會被建回來（P-15）。起 daemon 時開 `AOS7_AUDIT` 看寫入紀錄。

**想讓基礎設施露出**：node 出生／消失的協議、活任務變孤兒、tock 建回資料夾、建一半的競態、父 node 對巢狀子 node 的「只碰自己 node」（M-5）。

**結果**（三次都綠，約 8～15 秒）：

| 量 | 數字 |
|---|---|
| 寫好 timeline.json → daemon `node+` | 1～2 ms（不用 rescan ctl） |
| → 第一個 tick 結束 | 17～152 ms |
| 先寫 timeline.json、隔 400 ms 才寫 tasks.json | 空回合 1～8 個 |
| 寫入紀錄 ok:false：先 tasks 後 timeline／反過來 | 0／4 筆 |
| 父 rm -rf 沒掛載的巢狀子 node | ok 17 筆、ok:false 3 筆 |
| rm -rf 後子上的 sleeper | 還活著（孤兒），資料夾被它建回 `work/` |
| 孤兒結束時 aos7-run | 把 `.aos/tasks/<tid>/exit.json` 建回已刪的 node |
| 同名重建 | 回合從 1 重數（刪前是 6～17） |
| pause 後刪、同名重建 | paused.json 還留著，新 node 一出生就停著 |
| 只刪 timeline.json 再寫回 | 回合接著數，原 sleeper 接著收 tock |
| 5 ms 時間線 rm -rf 8 次 | 6～8 次被建回 `.aos/round.json`、`.aos/rounds.jsonl` |

**發現**：

- node 出生沒有「準備好了」的訊號：timeline.json 一出現就開回合。只能約定先寫 tasks.json、最後寫 timeline.json。
- 寫入紀錄判不判違規看寫的順序：timeline.json 寫下去之前，子資料夾算父自己的 node，之後才算「巢狀別人的 node」。改子 node 的一個檔算違規，整個 rm -rf 掉卻大半算 ok。
- 父要管自己 node 裡的子時間線，得先加掛自己 node 裡的路徑（等一個 tick）。直接寫只被記違規，照樣生效。
- rm -rf 有活任務的 node：daemon 只記 `node-`，活任務沒人收，status 也不列；daemon stop --kill 也收不到它。
- 刪掉的 node 會被建回成空殼：活任務的 makedirs、aos7-run 寫 exit.json、還沒發現 gone 的 tock（`gone` 要等下一圈掃描，最多 20 ms）都會建。
- pause 綁 node id、node 消失不清，同名重建就繼承 pause；status 有 `paused: true`，log 沒說原因。
- 同名重用回合從 1 重數，daemon 沒記 node 的歷史，log 裡分不出前後兩段。

> **使用者 10-03 Q4 選 (a) 之後（探針已改成驗新行為）**：rm -rf 子 node、或只刪 timeline.json，daemon 都會 kill 上面的活任務（log `node-gone-kill`），不留孤兒；被刪的資料夾不再被 tick／tock／aos7-run 建回來。只刪 timeline.json 不再是「暫停但保留任務」：寫回後 keep 重起、回合接著數。想暫停用 pause。
