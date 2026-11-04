# think 工具包

think 把難題交給較會想的模型。
它不會卡住 agent 的時鐘。
結果放在 `<home>/thoughts/`。

## 什麼時候用

符合下面一項才用：

1. 要同時權衡三件以上的事。
2. 做錯很難回頭。
3. 一般方法試了兩次，還是卡住。

能查、能算、能做一次小實驗的事，先直接做。
同一題開始後不要再送一次。

## 工具

### `think`

參數只有 `question`，另有可選的 `budget`。
當格回 `開始想了 id=...`。
送出後 agent 會睡；完成時結果會直接接回對話。

### `think_steps`

參數與 `think` 一樣。
最多走三步。
下一步只收到原問題和上一步短結論。
更早的步驟不會重送。

### `critique`

參數是 `draft`，另有可選的 `budget`。
它最多找三個重要漏洞。
每條有原因和最小修法。

### `thoughts_list`

不用參數。
列最近 20 份思考的編號、題目短句、狀態、步數、用量和完成時間。

### `thought_read`

參數是 `id`。
重讀原問題、各步短結論、最後結論和用量。
只在真的要查理由時用。

## 設定

在 agent 的 `tools.json` 開這包：

```json
{"packs": ["think"], "tools": []}
```

建議在 LLM 資料夾的 `engines.json` 指定一台：

```json
{"name": "local-thinker", "role": "thinker"}
```

有 `role: "thinker"` 時，固定用清單中的第一台。
沒有時，沿用 agent 原本的 engine。
兩種情況都會在請求的 `params.max_tokens` 寫預算。
深思請求的 priority 比 agent 原本低一級。

`budget` 可放四個值：

- `max_tokens`：預設與上限都是 6000。
- `max_steps`：`think_steps` 預設與上限都是 3。其他工具固定 1。
- `wait_s`：預設與上限都是 600 秒。
- `max_usd`：預設與上限都是 0.10 美元。

只能往下調。
引擎有 `price` 才估錢。
單價鍵是 `input`、`output`、`reasoning`、`cached`，單位是每百萬 token 幾美元。
沒單價就把金額留成 `null`，不猜。

## 檔案

每份思考在 `<home>/thoughts/<id>/`：

- `meta.json`：題目、狀態、預算、引擎、用量。
- `01.json` 到 `03.json`：每步短結論、完整結果和用量。
- `conclusion.md`：目前最好的最後結論。

pack 會把 `thoughts/` 加進 `<home>/.gitignore`。

## 坑

- 旁線結果由共用層收進 `<home>/side/think/`；包不碰 LLM 的 `results/`。
- 逾時、失敗、取消與缺鐘都直接回一則聊天錯誤。
- 模型可能把 token 全用在隱藏 reasoning，正文卻是空的。這時會標 `budget_exceeded`。多步思考會保留上一個可用結論。
- 不做重試、換引擎、清舊資料和同時多份思考。
