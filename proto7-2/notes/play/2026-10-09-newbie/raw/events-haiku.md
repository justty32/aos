## 試用者
Claude Haiku（新手）
## 分鐘
0.6
## 有沒有跑成功
成功，照「第一次跑」一節做完：`events/` 出現 `obs.active.jsonl`、`state.json`、`state.json.lock`；`read` 讀到 round.observed 與 daemon 事件；`pub` 首次回 `seq 1, dup false`，重送回 `seq 1, dup true`；`read --channel must` 讀到 demo.hello；`--ack 1` 回 `{"acked_upto": 1}`；停 daemon 後多出 `must.active.jsonl`，共四檔。背景 daemon 已用 `aos7-ctl daemon <root> stop --kill` 關掉，確認我起的那個已不在。
## 對外指令數
5：`aos7-ctl daemon`（register／stop）、`aos7-ctl add`、`aos7-daemon`、`aos7-events read`、`aos7-events pub`
## 新概念數
10：node（每個 node 一個 events/）、daemon 根（`.aosd`）、keep 任務與 tasks.json、tick／tock 回合、obs 與 must 兩通道、event_id 與 dup 重送、seq 與游標（cursor／next_cursor）、ack（消費確認，與「保存確認」不同）、固定檔數的 active 與封存段（keep 4）、gap（缺號）
## 卡點
1. 第一次跑 `aos7-ctl add` 那行：JSON 裡的 `<proto7-2>` 要自己換成絕對路徑（README 只說「JSON 也換」，我一開始漏看）。約 1 分鐘，靠上下文補上。
2. `touch $R/.aosd/log.on` 的 `log.on`：README 只寫「要收 daemon 流水帳才放」，我不知道它是什麼開關、為什麼是檔案，只能照做，不敢省略。未花時間。
3. `aos7-daemon $R &` 與 `sleep 3`：README 沒說 daemon 會佔住終端，我照字面用背景執行，沒問題。未花時間。
4. 「must」與「obs」的差別：工具段寫「pub 預設 obs」，但「要 ack」「滿了拒收（退出碼 3）」要到契約卡才看到。我只能照指令打，無法判斷何時該用 `--must`。約 3 分鐘，僅靠 README 內文推斷。
5. 環境注意（非 README 問題）：執行 `pgrep` 時看到另一個 worktree（aos-wt/NP）的 aos7-daemon 在跑，不是我的，我沒有碰它。
6. 自己的失誤（非 README 問題）：我在 zsh 裡寫 `echo ===` 分隔符，zsh 報 `== not found`，要重跑一次 pub 段。約 1 分鐘。
## 五條分數（0–10，10 最好）
- 容易上手：6 照第一次跑一節可以直接跑通，成功結果也對得上；但需自己換 placeholder、不懂的旗標（log.on）只能照抄。
- 容易理解：4 指令做了什麼看得出來，但 obs／must、ack、gap、固定檔數的含義要靠契約卡才懂，第一次讀不會形成概念。
- 複雜的藏起來：5 工具表與契約卡分層是好的；但第一次跑就要碰 daemon、node、tasks.json、timeline.json，前置概念沒被藏起來。
- 外層簡單但全面：6 對外就 pub／read 兩個子命令，外層確實簡單；代價是要先懂 aos7-ctl／aos7-daemon 才能讓它動。
- 要背的少：5 對外約 5 條指令，但要記的概念約 10 個，背負主要在概念而非指令。
- 平均：5.2
## ELI5
有一台電腦裡住著一個會定時看狀況的機器人，它會把發生的事寫進一本固定厚度的小本子（events 資料夾），舊頁會被撕掉。你想記一件事，就用 pub 寫一筆，想翻來看就用 read，看完要蓋章確認就用 ack。事情重寫一次不會變成兩筆，所以重送是安全的。
## ELI5 之後還複雜嗎
是，要先知道機器人（daemon）、房間（node）、任務表（tasks.json）怎麼起來，而且 must 與 obs 何時用、ack 代表什麼，還得回頭讀契約卡。
