# self 工具包

讓 agent 看自己現在是誰、跑多久、記憶多長、花多少錢。

## 工具

| 工具 | 什麼時候用 |
|---|---|
| `self_status()` | 看格數、記憶、資料夾大小與 LLM 用量。 |
| `self_cost(day?)` | 問今天或某天花了多少錢。日期寫 `YYYY-MM-DD`。 |
| `self_who()` | 問自己、父、小孩、時鐘與 LLM 在哪。 |
| `self_time()` | 只想知道本地時間或開機多久。這支不掃資料夾。 |

`self_status` 的 `history_tokens` 是字數除以 3。

`history_pct` 是記憶字數占 80000 字硬上限的百分比。

`self_cost` 讀 LLM 資料夾的 `engines.json`。
每台可放：

```json
"price": {"input": 0.14, "output": 0.28, "reasoning": 0.28, "cached": 0.014}
```

單位是每一百萬 token 幾美元。沒有 `price` 時，`cost_usd` 是 `null`，不猜。

## 坑

`folder_bytes` 會走完整個世界。資料夾大時會慢。

父子檔目前沒有直接寫 clock。`self_who` 會看父世界的 `.aos/inst` 判斷 shared 或 own。
