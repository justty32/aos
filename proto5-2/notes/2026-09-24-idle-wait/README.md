# 等模型的 agent 不空轉（提案，2026-09-24）

← [notes 索引](../README.md)｜[proto5-2 README](../../README.md)｜數字：[measure.md](measure.md)｜(b) 細則：[plan-b.md](plan-b.md)｜腳本：[exp/](exp/)

**只是提案，沒改程式、沒改規範。** 使用者原話：cpu 會上千、agent 上千，llm cpu 只有幾顆，大部分 agent 在等模型，cpu 處理它們像空轉；
能不能有個特殊 cpu 專門看、看到再喚醒？這應該是 kernel 的責任，或做成 lib？希望 kernel 簡單。前提：留在現有檔案／JSON 協定內。

## 1. 量到的事實

- **一格空轉的 agent tick**：起一支 Python 跑 `aos-agent tick`，讀家裡 6 個檔（含整份記憶）、stat K 兩個檔、除了鎖檔什麼都不寫、退 101。
  26 ms，其中 21 ms 是 Python 起來＋import；算上 cpu 那邊起行程、寫回音，一次約 **40 ms CPU**。
- **kernel 那邊更貴**：proto5 的 kernel 收一則回音、出一則 ack、派一件，**各把整份帳本存一次**，所以每多空轉一次＝帳本多存三次。
  帳本 1000 個 agent 約 1 MB，存一次 18.5 ms → 一次空轉在 kernel 花 **56 ms**，而 kernel 只有一條線。
- 真跑 60 秒（3 顆 llm 被掛住、300 個 agent 全在等）：cpu 給 300 顆時 kernel 一格要 **7 秒多**；給 30 顆時一格 1.6 秒，但每個 agent 16 秒才被看一次。
- 換算 1000 個 agent：**現在的瓶頸是 kernel 每格時間**（單線程整份存帳本，花的是 CPU 不是磁碟）。default cpu 開 16 顆以上，
  每個 agent 大約**一到兩分鐘**才被看一次＝模型答案回來後平均要多等半分鐘到一分鐘才有人收。cpu 顆數是第二道牆（一顆 cpu 一格只做一件）。

## 2. proto5-2 池式 tick 已經解掉多少

它讓 kernel「每格只碰有事的 cpu、每格最多存 4 次帳本」——**把上面最貴的那段拿掉了**。但**空轉本身沒解**：在等的 agent 每格仍被派一次、
仍是一件「有事」的派工與回音；cpu-notify 與巡檢只管「cpu 做完了」，管不到「agent 該不該跑」。kernel 不再是牆之後，牆換成 CPU：
proto5-2 沒實作，假設一格 1.2 秒、default 500 顆，每個 agent 2.4 秒被看一次，**空轉約 17 CPU 秒／秒**（比整台 16 執行緒還多）；cpu 少一點就換成醒得慢。

## 3. 方案比較

| | (a) 喚醒員 | (b) kernel 停車＋喚醒 | (c) agent 自己省 | (d) 回音落地丟喚醒檔 |
|---|---|---|---|---|
| 做法 | 一支常駐程式掃所有 agent 家，該醒的才替它投一格 `add --once` 的 tick；agent 不再是反覆行程 | agent 送單時帶 `wake: agent-<名>`；在等時退 **102**＝停車（下次時間推到 `park_ms` 後）；那張單的回音**放好後**，kernel 把它拉回來 | c1：`tick.interval_ms` 調大；c2：tick 開頭加「沒事就快退」的捷徑 | 誰寫回音誰 touch 一個喚醒檔，有人只看那個資料夾 |
| 誰負責 | aos-agent 這邊（lib） | kernel | agent | 寫回音的人＋看的人 |
| kernel | **不變** | **變複雜**：`add` 多一欄、回音待辦多兩欄、行程多一旗標、判定多一列、出貨多一步；估 50～80 行＋崩潰測試 | 不變 | 看放哪 |
| agent 規範 | 大改：start／stop／status／check；跨多次 tick 的 fails／bad 要自己記（池照樣用 kernel 的） | 小改：send.md、退出碼表、start 要確認 kernel 認得 102 | c1 不改；c2 小改 | 小改 |
| 1000 個在等 | 掃一輪約 19 ms，在等的不佔 cpu、不進 kernel | 在等的不佔 cpu、不進 kernel；只有保底到期的巡一次 | c1 調大 10 倍＝空轉少 10 倍，但**有事的每一步也慢 10 倍**；c2 不拖慢有事的步，但只省 agent 那 20 ms，kernel 的 56 ms 照付 | 同 (a)／(b) |
| 漏喚醒 | 掃的是現在的狀態，不漏邊；但要自己判斷「該不該醒」，跟 tick 的邏輯（門、送一半、收一半還沒結清…）**一分岔就叫不醒** | 事件是準的（它等的那張單回來了）；守住 [plan-b.md](plan-b.md) 的時序就不漏，保底只補程式錯與崩潰窗口 | 不會漏，只是慢 | 檔丟失敗、丟太早都會漏；inotify 只有 Linux，cpu-notify §5 已不選 |
| 醒得多快 | 比 (b) 多約兩格（喚醒員自己也要被派、投的單要等 kernel 收） | 最早下一次派工，池滿照排 | 最慢一個 interval | 看誰在看 |
| 跟 proto5-2 | 不打架，但多一個 kernel 外的排程者 | 不打架：停車＝進 `delayed`；喚醒＝推一筆進 `ready`，舊的那筆照舊格規則丟；已在 `ready` 的不重推 | 不打架 | cpu-notify 是 cpu→kernel，這是 kernel→agent |

**(a) 要補的**：每個 agent 同時最多一格在途的 tick，要固定、崩了能接上的單名（例如 `tick-<名>`，撞 `AlreadyExists`＝還在跑）；
那格 tick 的回音由喚醒員 ack；判斷該不該醒要跟 agent 共用同一份程式，不然就是第二份不完整的狀態機（[measure.md D](measure.md)）。
(a) 還有個變體：喚醒員**在同一支 Python 裡直接跑 tick**，連 kernel 都不經過，最省；但一個家壞了會拖到同批，池、優先權、fails／bad 全要搬出 kernel。

**(d) 其實不是獨立的一條**：回音檔 `K/responses/<單>.json` 本身就是「喚醒檔」，檔名開頭就是 agent 名（`aw-<名>-…`）。放在 kernel 裡看＝(b)；放在外面看＝(a) 的便宜掃法。

## 4. 建議

**選 (b)。** 喚醒的事件是準的，不用另寫一份「該不該醒」；agent 仍是 kernel 的反覆行程，所以 start／stop／status、池、J 隊的「專屬池」優先、fails／bad 全部照舊；延遲最短。
**老實講 kernel 會變複雜**，而且比第一版估的多：要讓「崩在任兩步之間都不漏」，喚醒得跟著回音待辦存進帳本、取消與退件也要帶、要防重複排隊（細則與逐個時序在 [plan-b.md](plan-b.md)）。
想讓 kernel 完全不動就選 (a)，代價是複雜度搬到 aos-agent，還多一個 kernel 外的排程者。

分三步：
1. **proto5 就做（要動 kernel）**：kernel 那幾件＋`park_ms` 保底；agent 送單帶 `wake`，「批在途、這格什麼都沒收到」改退 102。
   只解「等模型／等工具」這半，J 隊講的 idle 沒輸入照舊。**agent 與 kernel 要一起升級**（舊 kernel 把 102 當失敗，十次就 bad）。
   **不動 kernel 的第一步沒有好選擇**：只有 c1（每一步都變慢）、c2（只省兩成多）、或先做 (a)（之後換 (b) 會丟掉）。
2. **idle 也停車**：kernel 多一個 `wake NAME` syscall，`aos-agent say` 放好輸入後投一張；idle 沒輸入也退 102。
   say 崩在兩步之間、外人直接丟檔或 touch 門檔的，靠 `park_ms`（最慢 `park_ms` 才發現）。
3. **proto5-2 落地時**把停車／喚醒寫進 kernel-tick 第 4、8、10 步。

做完之後 1000 個 agent、3 顆 llm：在等的 agent 不花 cpu、不進 kernel；真的要跑的 tick 跟著「模型和工具每秒回來幾件」走，
加上保底（1000÷300 秒≈每秒 3 格）。proto5 的 kernel 就算一件事存六次帳本也撐得住；帳本整份存的根本問題還是要 proto5-2 解。

## 5. 要使用者拍的

1. **(b) 動 kernel 還是 (a) 不動 kernel？** 預設：**(b)**，kernel 多 50～80 行＋崩潰測試，換「喚醒準、其他都不用改」。
2. **保底 `park_ms` 多長？** 預設：**300 秒**。太短在 proto5 會把 kernel 拖回去（1000 個 agent、60 秒＝每秒 17 格×56 ms）。
3. **idle 沒輸入要不要也停車（第 2 步，多一個 `wake` syscall）？** 預設：**要，排在第 1 步之後**。
4. **退出碼用 102 可以嗎？** 預設：**可以**（0／1／2／101 已用；`start` 已經在擋 `done_exit` 跟 1、101 撞，要多擋 102）。

## astra 審查

必修 8 條、建議 6 條，**全部改進提案**（[review-astra.md](review-astra.md)）。改最多的：(b) 的喚醒要跟著回音待辦存帳本、取消與退件也要叫、`ready` 不能疊兩筆、
say 的崩潰窗口是正常情況（全寫進 [plan-b.md](plan-b.md)）；實驗 B 修了「模型逾時 125 秒會在窗口內結清」與 CPU 邊界、窗口拉到 60 秒重跑；
proto5-2 的「14 核」改成標明假設的範圍；kernel 行數從 20～30 改估 50～80；(a) 補上去重與 ack 的責任。

## 附錄

| 檔 | 內容 |
|---|---|
| [measure.md](measure.md) | 實驗 A～E 的數字與換算公式 |
| [plan-b.md](plan-b.md) | (b) 的規則、叫醒一個行程的判斷、逐個時序為什麼不漏、改多少 |
| [exp/](exp/) | `a_agent_tick.py`（一格多貴）、`count_io.py`（數檔案讀寫）、`b_e2e.py`＋`run_all.sh`（真 daemon／kernel）、`c_ledger.py`（存帳本多久）、`d_peek.py`（喚醒員掃一輪） |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra 唯讀審查的任務書與報告 |
