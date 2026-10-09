# 新手試用：compact（記憶整理）

← [總表](README.md)｜受測：`proto7-2/modules/compact/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/compact-haiku.md](raw/compact-haiku.md)、[raw/compact-luna.md](raw/compact-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 6 | ≤10 | 是 |
| 對外指令 | 3（now／forget／watch） | ≤3 | 是 |
| 新概念（兩位取多） | 5 | ≤5 | 是 |
| 分數（兩位取差） | 6.6 | ≥7 | 否 |
| **總判** | **不過**（分數） | | |

跑通情況：兩位都跑通：220 則→21 則，原文進 archive。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 8 | 9 |
| 容易理解 | 6 | 9 |
| 複雜的藏起來 | 6 | 8 |
| 外層簡單但全面 | 7 | 8 |
| 要背的少 | 6 | 9 |
| 平均 | 6.6 | 8.6 |

## 卡點（新手視角，依嚴重度）

1. README 開頭沒先說 node 是什麼（Haiku）
2. dry-run 說原因是「大小超過 16384」，正式 `now --force` 的 JSON 卻寫 trigger: force，兩者不一致，不確定正式跑是靠什麼觸發（Haiku）

## ELI5

這是幫電腦整理舊筆記的小工具。筆記太多時，它先把舊原文收進備份，再換成一則短摘要，最近的和沒做完的都留著。先 `now --dry-run` 看計畫，確定後 `now --force` 真的整理。

## ELI5 之後還複雜嗎

第一次跑不複雜；但同一份 README 很快帶出 llmcall、budget、真 AI、pending、退出碼 0–3、bigram 相似度（Haiku 判是、luna 也說後段多）。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 說明 dry-run 的觸發原因和 `--force` 實跑的 trigger 欄位為什麼不同（或第一次跑不用 --force 也能示範）
- [ ] README 開頭一句說 node 是什麼
- [ ] 「第二次跑（llmcall）」「第三次跑（真 AI）」與 stage 相似度、退出碼表移到「進階」標題下，第一次讀的人能明確知道可以停在哪
