# selfmod：任務改自己 node 的任務表與時間線

**是什麼**：node `s` 上的 keep 任務 `agent.py`（假 agent，照 `s/orders/*.json` 做事）在執行中改 `s/.aos/` 裡的東西：tasks.json（加任務、改 argv、改 from_round、寫壞 JSON、寫一半、壞型別、沒 name 的 keep）、timeline.json（改 interval、寫成字串）、round.json（撥鐘）、別的任務的 exit.json（假結束）。另外有：`quitter.py`（keep，把自己從 tasks.json 拿掉再 kill 自己）、`bouncer.py`（只 kill 自己，對照組）、`sleepy.py`（keep，記錄自己的 argv 版本）、`racer.py`（在 node `r` 兩個同時讀改寫 tasks.json 各 100 次，有／沒有 flock）。起 daemon 時開 `AOS7_AUDIT`。

**想讓基礎設施露出**：任務表誰能改、改了何時生效、寫壞時 tick 怎麼辦、寫入衝突、哪些 `.aos/` 檔該擋沒擋。

**結果**（三次都綠，約 10 秒）：

| 量 | 數字 |
|---|---|
| quitter：拿掉自己再 kill | 只起過 1 次（code -15） |
| bouncer：只 kill 自己 | 被起回來（D-3） |
| 改 sleepy 的 argv 後 | 跑著的不變；restart 起的是**舊版 v1**，kill 後 keep 起的才是 v2 |
| 偽造 sleepy 的 exit.json | tock 記成結束（code 0），keep 再起一個，舊程序還活著（兩份同時跑） |
| round.json 改成 1000 | 下一回合 1001 |
| 加 each 任務 | 下一個 tick 就起（延遲約 10 ms） |
| from_round 改到 +6 | 中間回合不起，到了又起 |
| tasks.json 寫一半停 400 ms | 4 個 tick 全沒起 pulse，rc 0，沒有任何紀錄 |
| from_round 寫成字串 | tick rc 1、整回合什麼都不起；只有 status 的 last_error |
| 沒寫 name 的 keep | 5 回合後 6 個活實例（每回合起一個） |
| 兩任務各讀改寫 100 次 | 不加鎖剩 100 項；自己約定 flock 200 項 |
| 改慢成 1500 ms | 下一回合生效 |
| 1500 ms 回合中改快成 50 ms | 約 1.3 秒後才 tick（等舊 interval 跑完） |
| interval_ms 寫成 "fast" | 時間線 thread 死掉（log `error`、phase stopped），改回也不復活；拿掉 timeline.json 再寫回才活 |

**發現**：

- 「只碰自己 node」把整個 `.aos/` 算自己的：round.json、別人的 exit.json、timeline.json 都能改，寫入紀錄全記 ok。
- 壞 JSON 默默當空表，壞型別讓整個 tick 例外：兩種壞法處理不一致，也都沒寫進 rounds.jsonl。
- tasks.json 沒有鎖或版本號；restart 照 birth.json 的舊定義起，沒有「照新定義重起」。
- interval 每回合開頭才讀；timeline.json 的值沒驗證，型別錯就弄死時間線。
