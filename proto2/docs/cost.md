# cost 工具包

每叫一次工具，就記一筆帳。

帳放在 `<home>/ledger/`。一天一個 `.jsonl`。`summary.json` 是全部日期的累加。

## 工具

### `cost_summary`

按工具名看呼叫次數、平均時間、平均回傳字數、平均 prompt token 和總價錢。

可給 `day`，格式是 `YYYY-MM-DD`。不給就是今天。

覺得變慢、變貴，或有人問「哪個工具最貴」時用。

### `cost_recent`

看最近幾筆原始帳。

可給 `n`。預設 10，最多 50。

剛才某一步特別慢時用。

## 設定

在 `tools.json` 開包：

```json
{"packs": ["cost"], "tools": []}
```

單價放 LLM 資料夾的 `engines.json`。單位是每一百萬 token 幾美元：

```json
{"name": "paid", "price": {"input": 0.14, "output": 0.28, "reasoning": 0.28, "cached": 0.014}}
```

整台沒有 `price`，價錢就留 `null`，不猜。

## 怎麼記

工具跑完先寫時間、step、工具名、參數字數、參數記號、回傳字數、毫秒、成功與錯誤種類。

參數記號是短雜湊。不保存參數原文。

下一輪 LLM 回來後，再補 token、價錢和 `round_steps`。同一輪有多個工具，就照回傳字數分攤。

回傳很長的工具通常最貴。內容會留在記憶裡，後面每輪都會重送。

## 坑

主線 LLM 回來時沒有專用的工具包掛勾。cost 會在下一個 act、reply 或 idle 補帳。

因此 `round_steps` 是靠相鄰格推算，不是直接在 wait 那格量到。

帳本沒有鎖。資料很多時，每次補帳都重算 `summary.json`，之後會慢。
