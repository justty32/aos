# branch 工具包

一句話：把同一題分成兩、三個不同方向同時想，再收回主線比較。

## 工具

- `fork(directions, budget?)`：開兩到三條。`directions` 每條只寫一個角度，不要重疊。回 `branch_id`。
- `join(branch_id)`：被喚醒後一次收回全部方向、總結、用量與花費。
- `adopt(branch_id, n)`：把第 `n` 條的整段記憶變成主線。`n` 從 1 開始。

## 什麼時候用

同一題真的有不同走法，先分開想會更清楚時才用。
方向可用「做法」「最可能失敗的地方」「完全不同的假設」切開。
一輪就能想完的小題不要用。

## 設定

在 `tools.json` 的 `packs` 加上 `"branch"`。

`budget` 有三個可選值：

- `per_branch_tokens`：每條的輸出上限。預設 1500，不能更高。
- `total_tokens`：全部分支的輸出上限。預設 4500，不能更高。
- `max_cost_usd`：預估花費上限。引擎沒寫 `price` 時無法估錢，會回 `null`。

例子：

```json
{"directions":["找最省力的做法","找最可能失敗的地方","從反過來的假設想"],"budget":{"per_branch_tokens":1000,"total_tokens":3000}}
```

## 檔案放哪

`<home>/branches/<id>/base.json` 是分岔當下的主線快照。
每條有自己的 `prompts.json` 和 `summary.md`。
`meta.json` 記方向、請求檔名、預算、用量和花費。
送出後 agent 會睡。共用層收齊才喚醒一次；`state.json` 不重複存分支進度。

## 坑

第一版只能直接問 LLM。不會生小孩，分支也不能叫工具。
最多三條。每條最多帶回 800 字。
沒有自動評審、投票、重試或清理舊分支。
`adopt` 沒有復原鈕。接手後第一版不允許再 `fork`。
沒有單價時，花費只能顯示 `null`。
