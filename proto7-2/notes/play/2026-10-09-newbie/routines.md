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

狀態：已改（回改隊 loop9/routines），重試 1 輪過，見下「重試」。

- [x] 修 out.log 預期行數（實跑 6）或說明行數隨 sleep 時間變
- [x] 第一次跑裡 daemon 那三行（起、等、停）各加一句白話註解（為什麼背景、為什麼 sleep 3）
- [x] 一句話說「r＝回合＝daemon 每醒一次」，不用新手去讀契約卡

## 重試

### 第 1 輪（2026-10-09，回改隊）

改法：第一次跑整段改成**不開 daemon**——`add` 兩件（`--every 1m`、`--at +1s`）後 `ls --run` 立刻把到期的做掉、再列清單，第二次 `ls --run` 顯示沒有到期的；daemon、回合、`3r` 移到「讓它自己定時跑（可選）」一節並逐行註解（為什麼 `&`、`sleep 3`、interval_ms、out.log 在哪、行數看機器快慢）；契約卡與表格式收到「維護者細節」分隔線後。介面：`ls --run`（不增子指令）；輸出拿掉 tock／keep 字樣、時間到秒、重名／找不到印原因、`rm` 印 removed；`--help` 每個參數有中文說明。原始回報：[raw/routines-haiku-retry1.md](raw/routines-haiku-retry1.md)、[raw/routines-luna-retry1.md](raw/routines-luna-retry1.md)。

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 6.3（開頭＋第一次跑約 1400 字 3.5＋指令 7 行 1.75＋卡點 1） | ≤10 | 是 |
| 對外指令 | 3（add／ls〔含 --run〕／rm；第一次跑不碰 aos7-daemon／aos7-ctl） | ≤3 | 是 |
| 新概念（兩位取多） | 4（Haiku：node、routine、schedule、inst；luna：node、routine、schedule、ls --run） | ≤5 | 是 |
| 分數（兩位取差） | 7.4（Haiku 8／6／8／7／8；luna 8.8） | ≥7 | 是 |
| **總判** | **過** | | |

兩位都跑通，輸出與 README 一致。Haiku 剩下的小卡點（node 沒定義、`--every`／`--at` 寫法只靠範例、新加的 routine 為何馬上跑、`<proto7-2>` 要自己算）已在 README 第一次跑段各補一句（未再重試）。兩位仍說「ELI5 之後還複雜：要自動定時就得懂 daemon／回合」——這是可選的下一步，第一次跑已不需要。
