## 試用者
Claude Haiku（新手）
## 分鐘
0.1
## 有沒有跑成功
成功，`pub` 寫入後 `read --text` 印出 `1 hello n1 {"msg": "hi"}` 與 `# next_cursor 2`；must 通道的重送回 `dup true`、`read --channel must --ack 1` 回 `{"acked_upto": 1}`，兩本帳各一筆，與 README 描述一致。
## 對外指令數
2：`aos7-events pub`、`aos7-events read`（`--ack` 是 read 的選項，不另算）。
## 新概念數
8：events 夾、seq、obs、must、ack、event_id、cursor（next_cursor）、node。
## 卡點
1. [`ls $E` 的輸出] 看到 `state.json`、`state.json.lock` 不知道是什麼、能不能刪；「別刪鎖檔」在進階區，約 1 分鐘猜。
2. [一覽表「C 工具」、「A keep 任務」] 術語沒解釋，第一次跑用不到，不到 1 分鐘跳過。
## 五條分數（0–10，10 最好）
- 容易上手：8 第一次跑的指令貼上就成功，不需改任何東西。
- 容易理解：6 五個詞有說明，但 obs／must、cursor 與 ack 的關係要讀兩次；「C 工具」等術語沒解釋。
- 複雜的藏起來：7 daemon、契約卡、長跑都標成進階或選讀，但之後的術語（keep 任務、取樣器）仍露出。
- 外層簡單但全面：7 `--help` 完整且有例子，README 列出退出碼與檔案規則。
- 要背的少：8 對外只有 pub、read，常用選項不多；要記退出碼與 ack 語意。
- 平均：7.2
## ELI5
events 就像一本記帳本，每寫一筆就給它一個編號。你用 pub 把一件事寫進去，用 read 把它念出來。要是某件事一定要有人處理完，就寫進 must 本子，處理完要 ack 確認，沒確認的會一直留著。同一件事寫兩次也不會多一筆，因為用同一個 event_id。
## ELI5 之後還複雜嗎
是，obs 與 must 兩本、ack、event_id 要分清楚，daemon 自動記錄需要另外理解 node 與 keep 任務。
