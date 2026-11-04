## 試用者
Claude Haiku（新手）
## 分鐘
0.3
## 有沒有跑成功
成功：`pub` 回 `{"ok": true, "seq": 1, ...}`，`read --text` 印出 `1 hello n1 {"msg": "hi"}` 與 `# next_cursor 2`；must 同 event_id 重送回 `dup true`（仍是 seq 1），`read --ack 1` 回 `{"acked_upto": 1}`。
## 對外指令數
2：`aos7-events pub`、`aos7-events read`（用到 `--text`、`--channel must`、`--ack`）
## 新概念數
8：events 夾、seq、obs、must、ack、event_id、游標（cursor／next_cursor）、退出碼（0／2／3／4）
## 卡點
1. `E=$(mktemp -d)/n1/events` 與「在 repo 根貼上」：沒說哪個目錄是 repo 根；`n1` 直到看見輸出才確定是自動帶入，約 1 分鐘。
2. `# next_cursor 2`：不確定與 `--cursor` 的關係，當作可忽略，約 1 分鐘。
3. ack 的語意分散在概念段與工具段，第一次讀沒完全理解與 `--channel must` 的搭配，約 2 分鐘；實跑直接成功。
4. obs／must 寫成「一個概念：哪一本帳」，括號敘述要重看兩次，約 1 分鐘。
## 五條分數（0–10，10 最好）
- 容易上手：8 照第一次跑的指令複製就成功，不必裝 daemon。
- 容易理解：6 五個詞有用，但 obs／must、游標、退出碼要跨段才拼得起來。
- 複雜的藏起來：6 daemon、封存段、契約卡收在後面，但「工具」「檔案與檔數」等段對新手是噪音。
- 外層簡單但全面：7 第一次跑後能順著看到 must、ack、重送。
- 要背的少：6 約 8 個概念加 4 個退出碼。
- 平均：6.7
## ELI5
events 就是一本帳本，你可以往裡面寫一筆事件，編上號碼。有兩種本子：一般的（舊的會被丟掉），和一定要有人說「我處理完了」的（沒說就一直留著）。要寫用 `pub`，要讀用 `read`，寫兩次同一件事不會多一筆。
## ELI5 之後還複雜嗎
是，ack、游標和退出碼要分開理解，第一次跑之後還有一長串進階規則。
