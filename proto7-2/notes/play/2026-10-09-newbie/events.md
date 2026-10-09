# 新手試用：events（事件保存）

← [總表](README.md)｜受測：`proto7-2/modules/events/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/events-haiku.md](raw/events-haiku.md)、[raw/events-luna.md](raw/events-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 15 | ≤10 | 否 |
| 對外指令 | 2（pub／read（第一次跑另要 aos7-daemon、aos7-ctl register／add／stop，不計）） | ≤3 | 是 |
| 新概念（兩位取多） | 10 | ≤5 | 否 |
| 分數（兩位取差） | 5.2 | ≥7 | 否 |
| **總判** | **不過**（分鐘、概念、分數） | | |

跑通情況：兩位都跑通：pub 首次 seq 1、重送 dup true、must 讀到並 ack。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 6 | 8 |
| 容易理解 | 4 | 6 |
| 複雜的藏起來 | 5 | 7 |
| 外層簡單但全面 | 6 | 7 |
| 要背的少 | 5 | 7 |
| 平均 | 5.2 | 7.0 |

## 卡點（新手視角，依嚴重度）

1. `aos7-ctl add` 那行 JSON 裡的 `<proto7-2>` 要自己換成絕對路徑，容易漏看（Haiku）
2. `touch .aosd/log.on` 是什麼開關沒說，只能照抄（Haiku）
3. obs 和 must 差在哪、何時該 `--must`，要讀到契約卡才看到；ack（消費確認）與保存確認的差別只指向 spec（兩位都提）

## ELI5

有一個會定時看狀況的機器人，把發生的事寫進一本固定厚度的本子，舊頁會撕掉。你想記一件事就 pub，想看就 read，看完蓋章就 ack。同一件事寫兩次不會變兩筆。

## ELI5 之後還複雜嗎

是（兩位都說是）。pub／read 很簡單，但第一次跑就要先懂 daemon、node、tasks.json、timeline.json，再加 obs／must、cursor、ack、封存段，Haiku 數到 10 個詞。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 第一次跑的 `<proto7-2>` 佔位換成腳本自動帶（像 mail 的 `P=$PWD/proto7-2`）
- [ ] log.on 加一句白話，或第一次跑不需要就拿掉
- [ ] obs／must 用一句話講清「must＝一定要有人讀完 ack，滿了會拒收」，放在第一次跑之前
- [ ] 新手詞表壓到 ≤5
