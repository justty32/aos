## 試用者
gpt-6-luna（新手）
## 分鐘
0.3
## 有沒有跑成功
成功，`ls` 顯示 routine `hello` 的 code 0，但紀錄有 6 行，與 README 範例的 5 行不同。
## 對外指令數
5：`aos7-ctl daemon register`、`aos7-routines add`、`aos7-daemon`、`aos7-routines ls`、`aos7-ctl daemon stop`
## 新概念數
5：routine（定期做）、schedule（指定時間做一次）、node、inst、tick（定時喚醒任務的引擎）
## 卡點
無
## 五條分數（0–10，10 最好）
- 容易上手：8 README 有完整可複製的第一次跑流程。
- 容易理解：7 用例簡短，但 tick、tock 等詞沒有在第一次跑裡解釋。
- 複雜的藏起來：8 只要 add 和 ls 就能安排並查看工作。
- 外層簡單但全面：8 範例包含建立 node、啟動、檢查和停止。
- 要背的少：7 第一次跑需記住五種不同指令。
- 平均：7.6
## ELI5
它像一張提醒小紙條，告訴小幫手什麼時候要做事。用 add 寫下要做的事，定時叫醒的小幫手會照著做。用 ls 可以看看還有什麼工作。
## ELI5 之後還複雜嗎
是，因為實際設定還要知道 node、inst 和 tick 等名詞。
