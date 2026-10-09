# 新手試用：routines（例行事／定時一次）

← [總表](README.md)｜受測：`proto7-2/modules/routines/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/routines-haiku.md](raw/routines-haiku.md)、[raw/routines-luna.md](raw/routines-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 10 | ≤10 | 是 |
| 對外指令 | 3（add／ls／rm（第一次跑另要 aos7-daemon、aos7-ctl register／stop，不計）） | ≤3 | 是 |
| 新概念（兩位取多） | 8 | ≤5 | 否 |
| 分數（兩位取差） | 6.2 | ≥7 | 否 |
| **總判** | **不過**（概念、分數） | | |

跑通情況：兩位都跑通，但 out.log 都是 6 行，README 寫 5。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 7 | 8 |
| 容易理解 | 5 | 7 |
| 複雜的藏起來 | 6 | 8 |
| 外層簡單但全面 | 6 | 8 |
| 要背的少 | 7 | 7 |
| 平均 | 6.2 | 7.6 |

## 卡點（新手視角，依嚴重度）

1. README 預期 out.log「5」行、註解說 4 次 routine＋1 次 schedule，兩位實跑都得到 6（5＋1），數字和註解對不上，不知道以哪個為準
2. 沒說 daemon 會不會佔住終端；`&`、`wait "$D"`、`sleep 3` 為什麼是 3 秒都要猜（Haiku）
3. timeline.json 的 `interval_ms: 200`、`.aos/tasks/routines/out.log` 這路徑從哪來都沒解釋（Haiku）
4. 回合／tick／tock／keep 任務第一次讀不懂，要靠契約卡拼（Haiku，luna 也說 tick／tock 沒解釋）

## ELI5

這是一個小幫手，每次「心跳」時去看一張清單。清單上兩種事：每隔幾次心跳做一次的，和到指定時間只做一次、做完就劃掉的。add 寫進清單、ls 看清單、rm 刪掉。要先把背景程式開起來心跳才會跳。

## ELI5 之後還複雜嗎

是（兩位都說是）。add／ls／rm 好懂，但「心跳＝回合」「keep 任務」「表格式」是 ELI5 外的東西，第一次跑就要碰 daemon。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 修 out.log 預期行數（實跑 6）或說明行數隨 sleep 時間變
- [ ] 第一次跑裡 daemon 那三行（起、等、停）各加一句白話註解（為什麼背景、為什麼 sleep 3）
- [ ] 一句話說「r＝回合＝daemon 每醒一次」，不用新手去讀契約卡
