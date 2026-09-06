# self 工具包

看 agent 自己現在怎麼樣。

| 工具 | 做什麼 |
|---|---|
| `self_status()` | 看格數、開機時間、記憶大小、資料夾大小與 LLM 用量。 |

`step` 是被推了幾格。`busy` 是其中真的有做事的格數。

`last_usage` 是上一個主線 LLM 回覆的用量。`today_usage_all` 是整個 LLM 世界今天的總數，`by_engine` 保留各引擎拆帳。

資料夾很大時，計算 `folder_bytes` 會慢。現在先照實走完整棵目錄。
