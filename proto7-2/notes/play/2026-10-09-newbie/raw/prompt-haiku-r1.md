## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，第 2 行回條看到 `"outcome": "rendered"`、`tokens_est` 106 對 `tokens_est_full` 2606，第 3 行 expand 印出週報全文；另外照「自己寫第一份清單」寫的 `mine.json` 也 render 成功（outcome rendered）。
## 對外指令數
2：`aos7-prompt render`、`aos7-prompt expand`
## 新概念數
6：node（AI 的資料夾）、prompt.json 清單（messages／role／content）、讀檔指令 `$opt`＋`$val`、收起來（`ref://` 編號）、tokens_est（token 估值）、expand（換回原文）
## 卡點
1. 第一次跑第 2 行的回條：`tokens_est` 是什麼單位、為什麼比 `tokens_est_full` 小，第一次跑的段落沒講，我是看到「收起來」才猜出來，花約 1 分鐘。
2. 第 3 行 expand 的輸出最外層是 `{"litellm": {"model": "chatgpt-gpt-6-sol-high", ...}}`：README 沒說 litellm 是什麼、model 從哪來，我看不懂，花約 1 分鐘，沒有影響後續（不會卡住）。
3. 自己寫清單時，README 只說「照 first.json 改檔名」，沒說讀檔路徑是從 node 算起（要到「三個概念」表才看到），我把 `mine.json` 放在 `$D/prompts/`、讀的檔放在 `$D` 根目錄，才第一次就過，花約 1 分鐘。
4. 「維護者」一節的「不碰 llmcall／budget」、以及連結到的 spec.md、wfnode、llmcall 我依規則都沒讀，對「budget」一詞完全不懂，但不影響第一次跑。
## 五條分數（0–10，10 最好）
- 容易上手：8 三行照抄就跑出README 說的結果，沒有需要猜的地方。
- 容易理解：6 三個概念表有幫助，但 tokens_est、litellm 包裝、`$opt`／`$val` 的意思在第一次跑都沒講清楚。
- 複雜的藏起來：7 收起來是自動發生的，進階指令（tail、latest、append、$ref、$fmt、$env）都收在「進階」之後，第一次不用看。
- 外層簡單但全面：7 render／expand 兩個指令就能完成主流程，進階讀法與退出碼也都有，但全面性要靠讀進階才看得到。
- 要背的少：8 只要記兩個指令和一個清單 JSON 形狀。
- 平均：7.2
## ELI5
這個東西像一張購物清單：你寫下要給 AI 看哪些檔，它就幫你把這些檔照順序拼成一份給 AI 的請求。太長的檔會自動摺起來，只留開頭幾百字，省錢用。想看原文時就用 expand 把摺起來的部分打開。用的時候只要寫一張清單、執行 render，再視需要執行 expand 就好。
## ELI5 之後還複雜嗎
否，核心只有「寫清單、拼、需要時展開」三件事，其他讀檔指令要用到再查進階即可。
