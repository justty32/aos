# 探針 sched：排程型 kernel

自己寫的 kernel（`kernel.py`，keep 任務，node `k`，回合 100 ms）用 daemon ctl 的 pause／resume 管 6 條成員時間線。成員每回合起一個 `member.py`（each），做一點事、記一行到 `<成員>/work.jsonl`。kernel 經過掛載點讀寫：`aosd → .aosd`（寫 ctl、讀 status.json、看 ctl-done）、`m_<成員> → <成員>/.aos`（讀 round.json）。kernel 每件事記在 `$AOS7_TASK/sched.jsonl`。

四段，各開一個空間（約 10 秒）：

| 段 | 做法 |
|---|---|
| a1 round-robin | 6 條同時只跑 N=2，每 3 個 kernel 回合輪替；換人時 pause 與 resume 一起寫 |
| a2 round-robin（安全） | 先 pause 出去的，輪詢 status.json 看到 `phase: paused` 才 resume 進來的 |
| b 優先序 | h1、h2 的 `queue/` 有工作就只讓它們跑，lows（任務 160 ms，比回合長）全 pause |
| c 類 cron | 每 K 個 kernel 回合讓成員只跑一回合：fast（resume 後輪詢 round.json，一前進就 pause）／naive（下個 kernel tock 才 pause）／batch（resume、pause 一起寫）；另有兩條不受管的背景成員（70、130 ms） |

## 想讓基礎設施露出什麼

pause／resume 從寫 ctl 到生效多久、「只跑一回合」做不做得到、pause 時回合中途的任務怎樣、同時在跑的條數會不會超過 N、kernel 怎麼知道 ctl 被執行了、各時間線回合不同步的影響。

## 結果（4 次都綠，數字取第 4 次；機器忙時延遲會翻倍）

- **ctl→ctl-done 回條**：5～21 ms（daemon 主迴圈 20 ms）。
- **pause→真停**（status 的 `phase` 變 `paused`）：中位 18～49 ms，最多 ~130 ms（要等成員本回合 tock 完、interval 滿）。pause 寫下後成員又開了 1 回合的：每段 1～2 次／17～30 次（寫 ctl 與 daemon 讀到之間剛好碰到回合邊界）。
- **resume→成員回合前進**：16～51 ms（20 ms 輪詢＋tick 程序時間）。
- **同時在跑超過 N**：a1（一起寫）4 次裡 3 次出現同時 4 條在跑（status 樣本 3～29% 超過 2、log 的回合區間最多 4 條重疊）；a2（安全）0 次，代價是換人時有 5～77 ms 沒人跑（status 樣本裡 0 條在跑的佔 13%）。
- **ctl-done 回條不代表生效**：回條只表示「改了 paused 清單」。status 樣本常看到 `paused: true` 但 `phase` 還在跑（a2 36 次）。kernel 要知道「真的停了」只能自己輪詢 status.json 的 phase。
- **開頭**：沒有辦法宣告「node 一出生就停著」。a 段沒預先停，沒輪到的 4 條在 kernel 停住它們之前各跑了 2 回合（~200 ms）。c 段的做法是在 daemon 起來前預寫 daemon 自己的 `.aosd/paused.json`。
- **只跑一回合**：fast 20/20 精準；naive（等 kernel 下個 tock 才 pause）5～7/8，其餘多跑 1 回合；batch（resume、pause 同一批）0 回合，兩個互相抵掉。fast 會準，是因為成員一回合至少是 tick＋tock 兩個 Python 程序的時間（~60 ms），比 kernel 偵測（5 ms）加 daemon 輪詢（20 ms）長。這靠時序剛好，沒有保證；kernel 若只在自己的 tock 動作，就是 naive 的結果。
- **pause 不搶佔**：低優先 pause 生效時，12 次裡有 12 個任務還在跑，54 個低優先任務裡有 14 個的執行區間跟高優先的工作重疊。停著時結束的任務，要等 resume 後的 tock 才記進 rounds.jsonl 的 `ended`（延遲中位 65 ms，最多 ~300 ms；停得越久越晚）。
- **優先序反應**：工作放進 queue 到高優先開始做，要 1.2～3.3 個 kernel 回合（124～326 ms）。kernel 只在自己的 tock 看 queue。
- **回合不同步**：「每 K 個 kernel 回合」換算到成員身上不是固定回合數。70 ms 的 b1 在一個 kernel 回合裡跑 0／1／2 回合（1／14／10 次），130 ms 的 b2 跑 0／1（6／19 次）。kernel 決定 step 到成員任務真的開始要 36～63 ms，所以 step 落在成員自己時間軸上的哪裡是隨機的。
- **雜項**：pause 一個不存在的 node（`ghost/nope`）回條 `ok: true`。`.aosd/ctl-done/` 只增不減（2.6 秒累積 64 檔）。同一批 ctl 依檔名排序執行，kernel 的檔名要補零（`k-00012-…`），不然 10 會排在 9 前面。
