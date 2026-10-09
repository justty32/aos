# prompt 包（把檔案拼成給 AI 的對話）

你寫一張清單 `prompt.json`，說「這次要給 AI 看哪些檔」；`aos7-prompt render` 照清單現讀現拼，產出一份請求檔，交給 llmcall 送出。太長的檔會自動收起來（只留編號和開頭 200 字），省 token；要看原文用 `aos7-prompt expand`。

← [proto7-2](../../README.md)｜下游：[llmcall](../llmcall/README.md)｜進階（更多讀法、門檻、回條欄位、退出碼、契約卡）→ [ADVANCED.md](ADVANCED.md)

## 要學的只有三個概念

| 概念 | 白話 |
|---|---|
| node | 給一個 AI 用的資料夾（下面的 `$D`）。清單裡、命令列上的相對路徑都從它算起。 |
| `prompt.json` | 清單：一串訊息，每則寫 `role`（`system`／`user`／`assistant`）和 `content`（一段字，或多段的陣列）。 |
| 讀檔 | `content` 裡寫 `{"$opt": "file", "$val": "docs/weekly.md"}`＝「拼的時候把這個檔讀進來」。 |

「收起來（`ref://`）」不是新東西要學：它自動發生，要原文就跑 `expand`。

## 第一次跑（約 1 分鐘）

在 repo 根目錄照抄三行：

```sh
D=$(mktemp -d) && cp -r proto7-2/packs/prompt/examples/node/. "$D"
python3 proto7-2/packs/prompt/bin/aos7-prompt render "$D" "$D/prompts/first.json" --out "$D/req.json"
python3 proto7-2/packs/prompt/bin/aos7-prompt expand "$D" "$D/req.json"
```

做了什麼：第 1 行把範例資料夾複製到暫存目錄 `$D`。範例清單 `first.json` 要 AI 摘要一份約 7800 字的週報 `docs/weekly.md`。

**你應該看到**：

- 第 2 行印一行回條，只要看兩件事：`"outcome": "rendered"`＝成功；`"tokens_est": 106` 對 `"tokens_est_full": 2606`＝送給 AI 的量（token，AI 算長度的單位，約 3 個字一個）從 2606 降到 106——週報被收起來，省了九成多。其他欄位不用管。
- 打開 `$D/req.json`：週報那段變成 `ref://<一長串編號> 已折疊 7785 字，預覽：` 加開頭 200 字。原文存在 `$D/refs/`。
- 第 3 行把收起來的段換回原文，印出完整的請求（很長，捲一下就看到週報全文）。最外層的 `litellm`／`model` 是送 AI 用的信封格式，交給 llmcall 處理，你不用懂；要換模型就在清單頂層加 `"model": "名字"`。

（短檔不會收：一段超過 6000 字才收。所以清單裡都是短檔時，兩個數字會差不多，這是正常的。）

`refs/` 可以整夾刪：只影響舊請求的展開，下次 render 會重新寫。

## 自己寫第一份清單

照 `examples/node/prompts/first.json` 改檔名就好。檔名從 node 算起：例如在 `$D` 放 `你的檔.md`，清單存成 `$D/prompts/mine.json`，就跑 `render "$D" "$D/prompts/mine.json"`（不給 `--out` 就把請求直接印在螢幕）。

```json
{
 "messages": [
  {"role": "system", "content": "你是幫忙讀文件的助理，回答要短。"},
  {"role": "user", "content": ["請摘要這份檔：", {"$opt": "file", "$val": "你的檔.md"}]}
 ]
}
```

寫錯或檔讀不到時，最後一行以 `aos7-prompt: ` 開頭，白話說哪裡錯、怎麼改；不會拼出半份，`--out` 的檔不動。全部選項：`aos7-prompt render --help`。

## 想做更多

需要時看 [ADVANCED.md](ADVANCED.md)：只讀最後幾行、讀最新幾封信、接別份清單、填空、改收起來的門檻、回條每個欄位、退出碼、契約卡、測試。
