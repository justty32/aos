# agent 優先級與共用 cpu（提案）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)

2026-09-24。**只是提案**：沒改程式、沒改規範、沒跑 daemon／kernel。事實照 proto5 規範與 `lib/` 程式查的；「照規範應該可以」的都沒真跑。

使用者原話（摘）：agent 越來越多時，(1) 想讓某個 agent 的 llm／tool 都最優先——可能要動 kernel、在 json 加欄位，也可能交給 llm cpu 排；
(2) 想讓一些 agent 共用 cpu——應該不用動 kernel 和 daemon，把某個 agent 的 tool 弄成 aos-exec 之類的就好。

| 檔 | 內容 |
|---|---|
| [priority.md](priority.md) | 題 1：現在怎麼派工、say 到模型回來的路徑圖與插點、四種放法比較、「把 amy 設成最優先」的操作 |
| [shared-cpu.md](shared-cpu.md) | 題 2：現在哪些已經共用、使用者猜想對不對、兩個 agent 共用一支工具一顆 cpu 的例子、上千個時卡在哪 |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra（gpt-6-astra）唯讀審查的任務書與報告 |

## 題 1：優先級

**現況**：kernel 派工**沒有優先權**：同一池、時間到了的工作照 queue 順序拿。工作的隊伍只有一條，在 kernel 帳本（`queue`）；cpu 自己沒有工作的隊伍（kernel 一次只給一顆 cpu 一件）。
llm cpu 是同步等模型的，一顆一次只問一件。一個 agent 的三種工作（自己的每一格、問模型、跑工具）都經過這條隊，而**工具預設跟所有 agent 的 tick 搶 default 池**。

**選項**（細節與表格在 [priority.md §2](priority.md)）：

| | 改什麼 | 餓死 | 一句 |
|---|---|---|---|
| (a) kernel 看 `priority` | kernel＋agent 程式數十行（粗估）、規範 8 檔 | **一個 VIP 就可能餓死別人**，要另加 aging 或保留名額 | 最通用、最貴 |
| (b') 交給模型伺服器 | 不改（`llm.params` 併進 HTTP body） | 看伺服器 | 原本的「交給 llm cpu 排」在現行協定下不成立：cpu 看不到 kernel 還沒給它的工作，沒得排 |
| (c) 高優先 agent 專屬池 | 不改程式，只改 K 與 amy 的 info | 別人不會被 amy 餓死；amy 自己的工作之間仍排隊 | 閒著時那幾顆浪費 |
| (d) cpu 可服務多池（有先後） | 只動 kernel（驗證、派工、check、ls；粗估） | 一般池留著自己的 cpu 就不會 | (c) 的不浪費版；借出去時 amy 要等那件做完，沒有統一上限 |

**建議**：先用 **(c)**，零改動就能讓 amy 的 tick、問模型、工具三樣都**不跟別的 agent 搶**（tick 與工具最好也分開池，不然 amy 的長工具會擋她自己的 tick）；在意閒置浪費時再做 **(d)**；(a) 等真的要分很多級再說。
不管哪個，**模型伺服器是最後一道隊伍**，aos 這層優先不代表伺服器先回（伺服器支援的話疊 (b')）。

**最小版**：教程 05 加一節「讓某個 agent 最優先」（(c) 的四步）；修 check 的小洞：現在只查名字叫 `llm` 的池、各池模型代號合成一張表，
改成按池保留、agent 照自己的 `llm.pool` 查（`aos_kernel_check.py`＋kernel cli-ops.md、aos-agent cli-check.md 各一句）。

## 題 2：共用 cpu

**現況**：**已經全部共用**。agent 沒有自己的 cpu、也沒有常駐行程；`start` 就是進現有的池。所有 agent 的 tick 輪流在 default 池跑、
問模型排同一條 llm 隊、工具跟 tick 一起擠 default 池。「一個 agent 一份」的只有帳本一筆行程紀錄和家裡的 tick 鎖。

**使用者猜想**：「不用動 kernel、daemon」**對**；但工具**本來就是** aos-exec 跑的（每個 tool call 是一份 posix inst，kernel 派給 exec cpu）。
`kind=aos` 不是一種工具，是「aos-exec 自己失敗、程式沒跑」的回音分類。

**真正做不到的**：讓**某一支工具**固定走某個池（例如一張 GPU 讓好幾個 agent 排隊用）。現在池只能設在 agent 一級（`tool_pool`），一設就是那個 agent 的全部工具。
「一個只有一顆 cpu 的池」本身就是一把排隊的鎖，缺的只是工具那一級的開關。

**建議與最小版**：工具檔加一欄 `_pool`（跟 `_timeout_ms` 一樣，底線開頭、模型看不到）：寫了就走那池、沒寫照舊。
規範改 agent info.md §3.3、aos-agent send.md §5.2；程式改 `aos_agent_home.py`（驗）、`aos_agent_batch.py`（選池一行）、`aos_kernel_check.py`（agent 檢查查池在不在），粗估十幾行＋測試。kernel 派工、daemon 不動。

**上千個時**卡的不是共用本身，是「閒著的 agent 也一直被派一格看一眼」「每顆 cpu 一支常駐 Python、閒著也每 20 ms 掃資料夾」「大家都讀寫同一份大帳本」——後兩個對到 proto5-2 README 要拍的第 3、1、2 題；第一個是新題（[shared-cpu.md §4](shared-cpu.md)）。

## astra 審查

必修 10 條、建議 6 條，**全部改進提案**（[review-astra.md](review-astra.md)）。改最多的：(c) 只保證「不跟別人搶」、不保證 amy 自己不排隊（tick 與工具分池）；
(a) 一個 VIP 就能餓死別人（tick `interval_ms=0` 閒著也每格重新入選）；(d) 借出去沒有等待上限；路徑圖少了一格 agent tick；
`interval_ms` 調成 200 通常沒用、只有 0 有用；共用工具例子加 `_pool` 後要把 `tool_pool` 改回來；規模表的速率、帳本讀寫、輪詢三處改正。

## 要使用者拍的

**題 1**
1. 「最優先」要做到哪一層？只要 aos 這層不排隊，還是連模型伺服器那層都要先回？——**預設：先 aos 這層**；伺服器那層看你用的端點支不支援。
2. 先用 (c) 專屬池（零改動、閒置時浪費）可以嗎？——**預設：可以**，嫌浪費再做 (d)。
3. 將來要不要「很多級」優先（(a)，要處理餓死）？——**預設：先不要**。

**題 2**
1. 「共用 cpu」你指的是哪個：(iv) 幾個 agent 專用一組 cpu，還是 (v) 某一支工具讓好幾個 agent 排隊共用？——**預設：(v)**。
2. 工具檔加 `_pool` 可以嗎？——**預設：可以**，就這一欄、其他不動。
3. 閒著的 agent 也每秒被叫醒一次，要不要列進 proto5-2 的規模題？——**預設：列進去，這版不做**。
