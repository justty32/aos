# llm kernel 的排序搬上共用骨架（線 aos-kllm-round-1120）：骨架 round.py 多一步「誰先」（ordered：驗不過的排最前、其餘交包的 rank），llm kernel 拿掉自己的 order、改給 row／rank；行為不變

← 設計：[aos-kres-1120/07-排程介面](aos-kres-1120/07-排程介面.md)｜使用者已答：[aos-kres-1120/08](aos-kres-1120/08-使用者已答.md) 第 9 題

依據：使用者在資源基底第 9 題（「排程：骨架補上「先後」之後，llm kernel 現在那套排序（級數、aging 等）要不要搬上去？」）選「現在一起搬」。頂層派、線隊長交。

## 做了什麼

開工時的事實（跟任務書的說法對不上一處）：llm kernel **本來就跑骨架的一輪**（`kernel_llm/_entry` 叫 `round.run(llm_rules, …)`），沒有自己一份一輪流程。它自己的只有「誰先」那一口：`llm_rules.order` 一手包了「驗不過的排最前」與「級數、期限、黏著、速度、等多久、先寄」。所以「搬上骨架」做的是設計稿 07 第二節說的那件：骨架補上「先後」這一步，llm kernel 的排序改成掛在這一步上。

- `kernel/round.py` 多一個 `ordered(pack, ctx, incoming)`，一輪裡原本叫 `pack.order` 的地方改叫它：
  - 包有 `order`：整個交給它（掛 proc 那一包照舊用，滿格留隊的信照上一輪隊序在前）。
  - 否則骨架排：每封叫包的 `row(ctx, name, letter)` 拿一列；回 `None`＝驗不過，排最前（照信名），輪到時由包的 `admit` 回錯（設計稿 07 卡點 3「驗不過的信排最前，搬走時要有人接」＝骨架接）。其餘的列照信名先後交給包的 `rank(ctx, rows)` 排；`ctx` 同一份，規則讀得到 kernel 自己的狀態（卡點 1：黏著讀上一輪 `backends`）。
  - 沒有 `row`：每列 `{"id": 信名, "letter": 信}`；沒有 `rank`：照信名（`letters.letter_key`，有序信先）。
- `kernel_llm/llm_rules.py`：拿掉 `order`，換成 `row`（＝`examined`，驗不過回 None）與 `rank`（＝`order.sort(rows, aging_cycles, 上一輪 backends)`）。額度、能力包、帳本、問模型都沒動，留在這包。卡點 2（保留格也讀級數）：級數照舊由 `examine` 算一次、`row` 與 `admit` 讀同一份，沒有兩處對不齊的問題。
- 新測試 `kernel/tests/test_kernel_rank.py`（4 支）：`order` 整個接手、都沒有時照信名、驗不過的最前＋`rank` 拿到照信名的好列與同一個 ctx、只有 `rank` 時列裡有信。
- 文件：`kernel/README.md`（口的清單拿掉必給的 `order`，加「誰先」一段、零件表 round.py 一格）、`kernel_llm/README.md`（零件表 llm_rules.py 一格）、`kernel_llm/docs/03-元素等.md`（流程圖與口的清單）。

## 證據

### 全套測試逐夾比

兩份乾淨複本（`base`＝`git archive f522b5570`；`m2`＝同一份疊本線三個程式／測試檔），各自 install，清掉 `AOS_*` 後逐夾跑 unittest，共 79 夾（`~/.aos/scratch/aos-kllm-round-1120/suite-base.txt`、`suite-m2.txt`，比對 `cmp.sh`）：

- 78 夾的支數與結果逐夾相同。
- `py/tools/aos/kernel/tests`：base 122 支 OK，m2 126 支 OK（多出的 4 支是新加的 `test_kernel_rank.py`）。
- `py/tools/aos/kernel_llm/tests` 兩邊都是 80 支 OK。
- 兩邊都退 5 的 `templates/kernel/tests`、`templates/tests/image-move-check` 是 0 支（不是 unittest，前幾條線也一樣）。
- 第一筆 commit `f7b0e3d05` 交出時這一段還是空的，第二筆補上。

### 假腦＋真 daemon 實跑

腳本 `~/.aos/scratch/aos-kllm-round-1120/live.sh COPY TREE`：從複本的 `templates/start-api/llm` 抄出定義夾、`slots 1`、不留 high 格、三支只記事件的 hook（`before_verdict`、`after_verdict`、`before_reply` 純通知），只起 llm daemon。兩份複本：`base`＝`git archive f522b5570`、`m2`＝同一份疊本線三個檔；各自 install。

| 項目 | base（改前） | m2（改後） |
|---|---|---|
| 1. 一般請求（`fake`） | rc 0，`FAKE ANSWER to: hello` | 同 |
| 2. 被額度擋（`capped`，`budget.max_calls 1`） | 第一封 rc 0；第二封 rc 1，`BudgetMissing`、`endpoint capped: max_calls 1 reached in this window (day)` | 同 |
| 3. 同一輪多封的排序（A 先佔唯一一格；B～G 先寄進旁邊的假信箱，再一個 `mv` 同一輪搬進來） | `A C E B G F D` | `A C E B G F D` |
| 4. 三個 hook 點各發 | bv 10、av 16、br 9；事件名 before_verdict／after_verdict／before_reply | 同（次數也同） |
| 5. 一輪的時間（daemon log 的 `elapsed_ms`，全程含 hook 行程） | 43 輪，中位數 323 ms、p90 671 ms | 51 輪，中位數 147 ms、p90 359 ms |

排序那組的信：B normal、C high、D low、E normal＋期限、F normal 但包 `speed: slow`、G normal 最後寄；都用 2 秒的 `fake_slow`。兩邊都是 high → 有期限 → 快包先寄 → 快包後寄 → 慢包 → low。

一輪的時間：兩份實跑時兩套全套測試都在背景跑，機器很忙，數字只說明「沒有變慢的跡象」，差距是雜訊不是改善。改動在一輪裡只多一層函式呼叫（`ordered` 叫 `row`、`rank`，跟原本 `order` 裡做的一樣多）。

## 沒做的

- **「等了多久」骨架不記**：設計稿 07 說骨架要多給規則「等了多久」。今天只有 llm kernel 用它，記在它自己的 `queue.json`、放在 `row` 回的列裡；搬進骨架要骨架多一份狀態檔、掛 proc 那一包也要改，超出最小做法。列在 kernel README 的「誰先」那段。
- **「自己有哪些規則」的宣告**（第 8 題「另外一個json吧」）：檔名、放哪他沒說，沒做。
- **schema 誰定、亂報、怎麼問到**：使用者答先不定，照任務書不做。
- **掛 proc 那一包**沒改成 `row`／`rank`，照舊給 `order`（它要照上一輪隊序，`rank` 拿不到上一輪的隊序以外的東西也能做，但任務只搬 llm kernel）。
- 不能用 `aos-llm send` 寄一封 priority 壞掉的信（它在寄件端就驗了），所以「驗不過的排最前」實跑沒測到；單元測試 `test_bad_rows_first_then_rank` 測了骨架那段，llm kernel 的 PriorityBad 回信原本的測試照過。

## 跟設計對不上處

- 任務書說「llm kernel 的一輪流程還有自己一份」：實際沒有，llm kernel 本來就叫 `round.run`；自己一份的只有排序那一口。
- 設計稿 07 說骨架要給「等了多久」：沒給（見上）。

## 替使用者做的選擇

1. 「先後」給規則的形式（設計稿 07 說「是實作的事」）：選 Python 包的兩個口 `row`、`rank`，不做資料檔或外部程式。最小，llm kernel 直接用得上。
2. 保留包自己整個排的 `order` 口，不強迫所有包走 `row`／`rank`（掛 proc 那一包不在任務範圍）。兩種寫法並存：有 `order` 就不叫 `row`／`rank`。
3. 驗不過的信排在最前、照信名，跟原本 llm kernel 的做法一樣，並做成骨架的預設（任何給 `row` 的包都一樣）。
4. 沒有 `rank` 時的預設順序用 `letters.letter_key`（有序信先，再照名字），跟掛 proc 那一包沒開留隊時一樣。

## 教學與條文

照任務書不動。`docs/tutorial/` 與 CONCEPTS／NORMS／CONVENTION 裡有沒有寫到「包要給 `order`」沒逐處查完；知識庫 `knowledge/aos` 沒有寫到 `order` 口或 `round.py`（grep 過），沒改。
