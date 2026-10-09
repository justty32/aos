## 試用者
Claude Haiku（新手）
## 分鐘
0.1
## 有沒有跑成功
成功，第一次跑看到 `"outcome": "rendered"`、`"tokens_est": 106` 對 `"tokens_est_full": 2606`；`expand` 印出完整週報摘要請求；自己寫的 `mine.json` 也 render 成功（`"outcome": "rendered"`）。
## 對外指令數
2：`aos7-prompt render`、`aos7-prompt expand`
## 新概念數
4：node（給 AI 用的資料夾，相對路徑從它算）；prompt.json 清單（messages、role、content）；`{"$opt": "file", "$val": ...}` 讀檔標記；`ref://` 收起來（README 說不算新概念，但看 `expand` 與回條時需要懂）
## 卡點
1. 全程沒有明顯卡住。我把 `mktemp -d` 改成在工作目錄下建暫存資料夾，花不到 1 分鐘。
2. `aos7-prompt --help` 只列出 `render`／`expand` 兩個子指令，看不到 `--out`、`--max-chars` 等選項；README 寫「`--help` 看全部選項」，但我沒試 `render --help`，所以不確定細節在哪。花約 0 分鐘（未追查）。
3. README 說失敗時回條的 `why` 會說明錯誤，但沒有給失敗範例，我看不出 `why` 長什麼樣子。花約 0 分鐘（未追查）。
4. `expand` 的輸出很長，README 的「捲一下」在指令列上我改用 `head` 截斷看前段；這是我自己的做法，不是 README 的問題。
## 五條分數（0–10，10 最好）
- 容易上手：9 三行照抄就跑通，回條數字與 README 描述一致。
- 容易理解：7 「三個概念」表很清楚，但「node」與信封格式 `litellm`／`model` 要靠 README 說明才懂。
- 複雜的藏起來：8 收起來是自動發生的，新手只需要知道 `expand` 可以看原文。
- 外層簡單但全面：6 外層只有兩個指令，但進階的 `$fmt`、`$ref`、`$env`、`append`、退出碼等擠在一段裡，第一次看不出涵蓋範圍。
- 要背的少：9 只要記兩個指令與一種清單寫法。
- 平均：7.8
## ELI5
這個工具像一個剪貼簿。你先寫一張小清單，寫上「要給 AI 看哪幾個檔」。然後執行 render 指令，它會把那些檔照順序拼成一份給 AI 的請求。太長的檔會先收起來，只留開頭一小段，省下很多字。要看原文，就執行 expand 指令。
## ELI5 之後還複雜嗎
否，第一次用只要寫清單和跑兩個指令，進階讀法可以等需要時再看。
