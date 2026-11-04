## 試用者
gpt-6-luna（新手）
## 分鐘
0.5
## 有沒有跑成功
成功，fake 回條 answered 並扣 623 tokens；LiteLLM 真傳輸回 `OK。`、usage 1650 tokens，兩者都結算成功。
## 對外指令數
6：`aos7-budget ledger`、`aos7-budget init`、`aos7-llmcall call`、`aos7-budget status`、`aos7-llmcall status`、`bash .../examples/litellm/run.sh`。
## 新概念數
10：node、grant、ledger（帳任務）、reserve（預留）、call ID、gateway、raw 回覆、receipt（回條）、usage/token 計量、soft 預算（超出只記錄）。
## 卡點
無。README 提到 spec，但跑範例不需要讀；依規則未開啟 spec。
## 五條分數（0–10，10 最好）
- 容易上手：9 fake 一段可直接複製，真傳輸也只要一行指令。
- 容易理解：7 成功結果清楚，但 grant、帳任務、結算等名詞要先消化。
- 複雜的藏起來：9 背景帳任務與真傳輸細節由範例腳本處理。
- 外層簡單但全面：8 一次拿到原文、usage、結算與 status 證據。
- 要背的少：7 要記住 call、status 和 budget 的 init／ledger 等子指令。
- 平均：8.0
## ELI5
這個工具幫你把問題送給一個會回答的模型。你先放一張「可以花多少」的小紙條，再把問題送出去。工具會把答案和用了多少字記下來。最後你可以再問它這次有沒有完成。
## ELI5 之後還複雜嗎
是，因為實際使用還要理解預留額度、呼叫識別碼與結算回條。
