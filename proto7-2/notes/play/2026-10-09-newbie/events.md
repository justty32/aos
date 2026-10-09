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

狀態：回改隊已改（分支 `loop9/events`），重試三輪，見下。

- [x] 第一次跑的 `<proto7-2>` 佔位換成腳本自動帶（`P=$PWD/proto7-2`、`E=$(mktemp -d)/n1/events`）；第一次跑整個不用 daemon
- [x] log.on 第一次跑不需要了；移到「讓 daemon 自動記（選讀）」並加一句白話
- [x] obs／must 一句話講清，放在第一次跑之前（五詞表），`pub --help` 也有
- [x] 新手詞表壓到 5（events 夾、seq、obs／must、ack、event_id）

## 重試

改法（介面只加不改，函式不動）：`pub` 的 `--event-id` 可省（自動產生，印在結果）、events 夾還沒建 state 時 `--node` 可省（取夾的上一層資料夾名，跟 compact 的 `node.name` 慣例一致）；`aos7-events`／`pub`／`read` 的 `--help` 加白話與例子；README 第一次跑改成「寫一筆、讀出來」＋「must 寫、重送、讀、ack」兩段，不用 daemon。

| 輪 | 改了什麼 | Haiku | luna | 分鐘 | 指令 | 概念（取多） | 過 |
|---|---|---|---|---|---|---|---|
| 1 | 免 daemon 第一次跑、CLI 預設、`--help`、五詞表 | 6.6（概念 7） | 8.4（概念 5） | 0.2 | 2 | 7 | 否（分數） |
| 2 | 第一次跑拆兩段、五詞照出現順序、輸出逐行白話；astra 審兩條（自動 id 在 unknown 也印、明給壞 `source.node` 不被預設蓋過） | 7.2（概念 8） | 8.8（概念 5） | 0.2 | 2 | 8 | 分數過、概念 Haiku 不過 |
| 3 | 輸出註解拿掉 node、說 state 檔別動 | 6.7（概念 8） | 8.6（概念 5） | 0.3 | 2 | 8 | 否（分數、概念） |

原始回報：raw/events-{haiku,luna}-r{1,2,3}.md。第 3 輪 Haiku 嫌「obs／must（一個概念：哪一本帳）」的括號難讀，已改回第 2 輪寫法（未再測）。

**總判：三輪用完，按「取較差」未過（最後一輪 Haiku 6.7、概念 8）。** 分鐘、指令已過；luna 三輪都 ≥8.4、概念 5。Haiku 的分數在 6.6～7.2 之間浮動，概念多數的是 README 已併入五詞的細分（obs、must 分開算，next_cursor、node、退出碼另算）；剩下的扣分點是第一次跑以後的進階段（工具、檔案與檔數、契約卡）讓頁面顯長。下一步若要再壓：把進階段搬到另一頁（README 只留五詞＋第一次跑＋一句連結），這要動契約卡的放置慣例，交頂層定。

全套測試（rebase main 後）：823 項 OK。
