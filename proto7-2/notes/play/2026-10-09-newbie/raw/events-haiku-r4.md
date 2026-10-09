## 試用者
Claude Haiku（新手）
## 分鐘
0.3
## 有沒有跑成功
成功：obs 那段看到 `{"ok": true, "seq": 1, ...}` 與 `1 hello n1 {"msg": "hi"}`；must 那段看到重送回 `dup true`（seq 仍為 1）、`{"acked_upto": 1}`，資料夾裡有 must/obs 兩本帳檔。
## 對外指令數
2：`aos7-events pub`、`aos7-events read`（`--ack` 是 read 的選項，不算獨立指令）
## 新概念數
9：events 夾、seq、next_cursor（或 cursor）、obs、must、ack、event_id、dup（重送結果）、node（路徑裡上一層資料夾名，會自動帶）
## 卡點
1. `read ... --ack 1`：名字叫 read，卻是「確認、不讀」，與直覺衝突，約 1 分鐘。
2. `aos7-events --help`（不帶子命令）：印出取樣器選項（--src、--rounds、--out），只想寫一筆的新手不知道要不要跑，約 2 分鐘。
3. `n1` 目錄名：要到 `pub --help` 才知道是從上一層自動取名，README 雖寫「不用管」仍想弄懂，約 1 分鐘。
4. `next_cursor` 與 `seq` 的關係：初看需停一下，約 30 秒。
5. 沒讀 ADVANCED.md（不是 README，不在允許範圍），daemon 部分沒試。
## 五條分數（0–10，10 最好）
- 容易上手：8 兩段整段貼上直接成功，README 給了預期輸出。
- 容易理解：7 五個詞與出現順序清楚，但 `read --ack` 命名與裸 `--help` 的取樣器說明會讓人停一下。
- 複雜的藏起來：8 daemon、取樣器、state 檔、退出碼都移到 ADVANCED 或 help，第一次跑不會被迫看到。
- 外層簡單但全面：7 pub/read 涵蓋寫、讀、重送、ack；但裸命令的取樣器入口讓外層不夠乾淨。
- 要背的少：7 對外只有兩個，但概念約 9 個。
- 平均：7.4
## ELI5
這是一本只會往後記的帳本，你可以把一句話寫進去，它會給那句話一個號碼。想要一定有人處理的事，就寫進另一本「必須處理」的帳，處理完要打個勾（ack）。同一件事重複寫，它只會記一次。用 `pub` 寫，用 `read` 看。
## ELI5 之後還複雜嗎
是，ack 放在 read 底下，而且不帶子命令的 `--help` 會跑出另一套取樣器說明。
