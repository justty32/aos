mailbox 命名調查：名字帶 mailbox 的東西如果是有序的，要不要改叫 queue（L 隊，opus 隊長＋codex 隊員）；四題 11-06 已裁、照裁定做完（見「使用者裁定」）。
← [2026-11-06](../README.md)｜[thinking](../../../README.md)

## 使用者原文（11-06）

> 再派一個隊伍，去調查一下，關於現在的_mailbox命名，如果那個mailbox是有序的話，是否應該都改名為_queue？

## 使用者裁定（11-06，選項框）

1. 命名規則草稿：「寫進 C-54 (Recommended)」→ 已寫成 [C-54 R14](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法/03-R14.md)。
2. `queue.json` 算不算一詞兩義：「不算、檔頭寫明 (Recommended)」→ llm kernel 的 `queue.hpp` 註解與 docs/01 各加一句「排法＝優先序」；判官的還沒實作，在 [os-impl 05](../os-impl/05-寄信者自設逾時.md) 窗那列加註「實作時寫明先來先掛」。
3. 板子比喻「信箱＝mailbox FIFO」：「加註 (Recommended)」→ [名詞表板子比喻](../../../../docs/CONCEPTS/附錄1-續-板子比喻.md)加 11-06 註，原句全留。
4. 兩個 kernel 的收件箱名字不一：「現在統一 requests/」（沒選推薦）→ llm kernel 的 `$AOS_STACK/mailbox/` 改名 `$AOS_STACK/requests/`、`ask` 的回信信箱跟著是 `requests/reply/`；錯誤代號 `MailboxMissing`、`MailboxBad` 與 aos-sandbox 的 `--mailbox` 旗標照 R14 第 1 點是機制名、不改；N-16、N-42、N-63、P-23 加註，舊名對照加一列；舊名不認、不寫遷移。實作結果見 [05](05-requests改名結果.md)。

## 一句話結論

**不用改：名字帶 mailbox 的箱子沒有一個是有序的；唯一當 queue 用的信箱（agent 的 `$AOS_STACK/queue/`）本來就叫 queue。** 「有序」在程式裡是一封信的屬性（寄的人帶 `--ordered`），不是箱子的屬性；11-04 起每個箱都同時收有序、無序的信。全 repo 只有寄進 agent `queue/` 的程式會帶 `--ordered`；daemon 的 `procs_ctl_mailbox` 寄件人不帶序號，llm kernel 的 `mailbox/` 照優先序挑信，回信箱是很多人挑著收——都是收件箱，不是 queue。要動的只有幾處用語（知識庫把 queue 叫 inbox、「有順序的信箱」說法），約 1 h；另有一條命名規則草稿等使用者看。

## 分檔目錄

| 分檔 | 內容 |
|---|---|
| [01-盤點](01-盤點.md) | 盤點說明與統計；資料在 [01-盤點.csv](01-盤點.csv)（228 列）、[01-成本.csv](01-成本.csv)（31 列） |
| [02-有序是什麼](02-有序是什麼.md) | 「有序」實際保證了什麼（FIFO＋兩級優先，不是優先序、不擋多讀者），各箱實際怎麼用 |
| [03-建議表](03-建議表.md) | 判準、現名 → 推薦 → 理由（17 列）、影響範圍與工時 |
| [04-規則草稿](04-規則草稿.md) | 什麼時候叫 mailbox、什麼時候叫 queue（11-06 已寫進 C-54 R14）＋跟 N-14、N-16、N-66、C-54 對不對得上 |
| [05-requests改名結果](05-requests改名結果.md) | 裁定 4 的實作：改了哪些、哪些照 R14 不改、驗收 |

## 方向題（推薦放第一）

1. **命名規則草稿要不要寫進條文？**（[04](04-規則草稿.md)）
   - **寫進 C-54 命名方法當 R14，原句照草稿，交條文日一起做 (Recommended)**：以後新開的箱照「四條都成立才叫 queue」取名，不用再查一次；約 0.5 h。
   - 只留在 thinking：省事，但下次有人開新箱還會再問一次。
2. **`queue.json`（llm kernel 的優先序排隊帳、判官未實作的先來先掛窗）用 queue 這個字，算不算跟「queue＝嚴格 FIFO 的箱」一詞兩義（C-54 R4）？**
   - **不算：它不是箱，記的是「誰在排」；檔頭一句寫明排法即可，名字不改 (Recommended)**：priority queue 本來就是常用說法；判官那份是 os-impl 05 已裁的名字。
   - 算：改成 `waiting.json` 之類；llm kernel 程式 4 檔、文件 4 檔，約 0.5 h，另要翻 os-impl 05 的名字。
3. **名詞表板子比喻「信箱＝mailbox FIFO」跟程式對不上，要不要加註？**
   - **加註、原句全留：只有當 queue 用的信箱是 FIFO；一般信箱是收件箱（名字≈時間序、整批拿），llm kernel 照優先序 (Recommended)**：免得之後有人照比喻把 daemon 的 ctl 信箱當 FIFO 用。
   - 不動：當比喻的天然差異。
4. **兩個 kernel 的收件箱名字不一（llm kernel `mailbox/`、判官 `requests/`），要不要統一？**（跟 queue 無關，盤點時看到的）
   - **先不動，等 aos-serve 通用收信執行器（大重構後、P6 後）時一起看 (Recommended)**：兩邊找箱的方式也不同（`AOS_LLM_KERNEL`＝stack 再接 `mailbox/`；`AOS_KERNEL` 直接指 `requests/`），單改名字不夠。
   - 現在統一成 `requests/`：llm kernel 程式 14 檔、文件 18 檔、知識庫 3 檔、試驗場重刷，約 2 h。

## 跟既有裁定的衝突

推薦做法沒有衝突。若硬把 mailbox 改成 queue，會撞到：使用者 11-03 定的 `procs_ctl_mailbox`（C-54 R7 例、命名.md）、11-02「要」統一的 `mailbox_warning`、N-16 10-30「『信箱』這個詞留給 agent 之間的請求投遞」、C-54 R4 一詞一義（queue 會同時指 FIFO 與非 FIFO 的箱）。

## 附記

- 任務背景寫「llm kernel 的 `requests/`」：程式裡 llm kernel 的收件箱是 `$AOS_STACK/mailbox/`，`requests/` 是判官的收件箱；llm kernel 另有每封信資料夾裡的 `request.json`（問腦 proc 的 stdin）。
- 讀碼順手看到的邊緣（判官轉寄有序信換號後回信對不上舊名等）記在 [01 末段](01-盤點.md)，跟命名無關。
