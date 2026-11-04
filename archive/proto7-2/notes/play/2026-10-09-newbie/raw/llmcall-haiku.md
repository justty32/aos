## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，fake 暖身看到 answered、used 623、billing final；真傳輸 `run.sh` 看到 LiteLLM 真模型回 `text: "OK"`、usage total_tokens 1649、退出碼 0。
## 對外指令數
7：`aos7-llmcall call`、`status`、`adopt`、`aos7-budget ledger`、`init`、`status`、`examples/litellm/run.sh`
## 新概念數
15：call_id、holder、logical、budget、grant、gateway（llm.fake／llm.litellm）、reserve、settle、meter、receipt、round／tock、patience、intent 與 raw、adopt、soft bound 與 overrun
## 卡點
1. [`run.sh ./evidence`] 寫相對路徑又要求從 repo 根執行，輸出會落進 repo；改傳絕對路徑。約 1 分鐘。
2. [`examples/litellm/`] 只給目錄連結，沒 README；不知道 req 用哪個 model、run.sh 做了什麼、evidence 每個檔是什麼，只能靠文字猜成功長什麼樣。約 2 分鐘。
3. [多處「見 spec」] llm.litellm 的 HTTP 對應、bound: soft、overrun、intent 無回覆就 unknown、adopt 只收同 C 同雜湊——只寫在 spec／藍圖，完全不懂。約 2 分鐘。
4. [`status`] 輸出一大段巢狀 JSON，找不到「成功」在哪一行，要對照 README 的 answered、used、billing final。約 1 分鐘。
5. [退出碼 0～4] 失敗時無法光靠 README 判斷 3（未完整交付）和 4（已交付但帳未清）各該怎麼辦。
## 五條分數（0–10，10 最好）
- 容易上手：6 照抄整段即可跑通，但要先懂要開 budget ledger。
- 容易理解：4 術語多（reserve、settle、receipt、intent、adopt、round），細節常指向 spec。
- 複雜的藏起來：5 `call` 一個指令藏起預留、送出、存檔、結算，但 `status` 把內部狀態全攤開。
- 外層簡單但全面：6 `call` 涵蓋預留、冪等重送、結算、回條，遲到有 `adopt`。
- 要背的少：5 日常 call／status，但還要記 budget 三條與退出碼 0～4。
- 平均：5.2
## ELI5
這是幫你問大模型一句話、同時幫你記帳的小工具。先開一本「預算帳」寫上最多能用多少 token。用 call 送出問題，它先預留額度、把回答存成檔、照實際用量扣帳，最後給你一張收據。同一個編號再問一次不會重送，只把之前的收據給你。
## ELI5 之後還複雜嗎
是，要懂預留、結算、遲到回覆和退出碼 0～4 才知道失敗時怎麼辦；照抄只處理得了成功。
