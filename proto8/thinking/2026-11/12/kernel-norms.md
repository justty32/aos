# kernel 條文改寫（11-12）：照 11-11 kernel 討論的結論改 C-47、N-42、N-63 等與文件、內容檔補 kernel 一頁

← [2026-11-12](README.md)｜依據：[11-11 kernel](../11/kernel/README.md)（原話 [01](../11/kernel/01-原話與經過.md)、清單 [03](../11/kernel/03-過時清單與日後清單.md)，03 的表每列已標結果）｜條文：[C-47](../../../docs/CONCEPTS/04-kernel.md)、[N-42](../../../docs/NORMS/09-kernel.md)

## 使用者原話

- 11-12，頂層說「kernel 的條文這次不改寫，等框架設計一起」，使用者答：「條文改寫也可以做。然後通用kernel可以開始出圖紙。」
- 11-12 稍早：「kernel那邊，小而獨立的可以做，只是猜.stack感覺可以留著?。」

## 改了什麼（照 03 的表）

- **C-47**：定義改成「資源管理＋排程」、從寄件人看（請求寄到哪，那裡對寄件人就是 kernel；收件 proc 不必自覺；啥都不管也是一種管理）。分成幾段：一律寄 `AOS_KERNEL`、多種 syscall（問腦走 `AOS_LLM_KERNEL`）、轉交也算與鏈（共通的只有 aos-post 信封、`reply_to` 二選一）、擺法只是範例（繼承式、0 號 proc 式）、安全的保底是 Linux 本身（人也改用 kernel；aos-daemon-ctl＝指名 daemon 的工具）、已裁定未實作（狀態位址用問的、通用框架）。11-05「判完自己 fork 去跑的不算 kernel」整句刪掉；11-06 註改成一句。
- **N-42**：開頭「兩支不併成一支」原句不改，加 11-11 註（見下「要你裁的」1）；(2) 改成「現況（判官、兩個範例擺法）＋方向（框架、判官收進框架，未實作）」，選項框裁的下一站、數量另指、hook 三時機寫成框架要有的能力；no-pid「stop、rm、sleep 也要過判官」改成「要不要判是收件 proc 自己的事」。
- **N-63 01** 實例 `AOS_KERNEL`：值＝一般 proc 送 syscall 請求的地方（仍指到信箱）；沒設退回 `AOS_DAEMON` 保留；aos-daemon-ctl 定位改「指名 daemon 的工具」。**N-63 02** 第 9 行與 **NORMS 08 ④**：加「`AOS_DAEMON` 照傳，約定一般 proc 不用」。
- **附錄1**：daemon、kernel 兩列與 3g.6 那列對齊新定義；順帶板子比喻 aos-daemon-ctl 那行（03 沒列、同一個裁定）。
- **文件**：`kernel/README` 標題、`kernel/docs/02`（一句話定義、三個範例擺法、`AOS_KERNEL` 一節、三級改成「誰能繞過 kernel：靠 Linux 權限」）、`cmd/docs/03`、`cmd/aos-daemon-ctl/README`、`cmd/aos-agent/README` 與 `docs/01`（後兩處 03 沒列，同一個定位）。
- **出廠內容檔**（`proto8/knowledge/aos/`，普通 json）：`world.json`、`_description.json`、`_index.json`（world 那格）、`cli/daemon.json` 的 kernel／aos-daemon-ctl 說法跟上；新增 `kernel.json`（what、where_to_send、templates、write_your_own），`_index.json` 加一項，`knowledge/README` 的 aos 列加一句。

## 照現行寫、沒照 03 改的

- **「兩個變數都沒設＝報錯、不再猜 `./.stack`」**：N-63 02、C-47、kernel/docs/02、cmd/docs/03、aos-agent README 與 docs/02、內容檔 `kernel.json` 都照現行（`AOS_KERNEL` 沒設走 `AOS_DAEMON`，再沒有才找 cwd 的 `./.stack`）寫，加註「11-11 曾議改成報錯；11-12 使用者『只是猜.stack感覺可以留著?』，未定案」。
- **`aos-agent ctl who` 先問 kernel 要狀態位址再讀**：沒實作，N-63 02 與 aos-agent README 維持「只查 `AOS_DAEMON` 那台的表」，加註已裁未實作。
- **N-42 (1) 分檔**（LLM kernel 自成一支）：併進框架時再改，何時併沒定。

## 標成未實作的

- 通用 kernel 框架（收信、規則＋hook 三時機、下一站、數量另指、回信二選一、排隊）與判官收進框架：N-42 (2)「方向（11-11 定，未實作）」、C-47「已裁定、未實作」②、kernel/docs/02。
- 狀態位址用問的（「狀態在哪」查詢信、不用 symlink、記不記工具自己決定）：C-47「已裁定、未實作」①、N-63 02、aos-agent README。
- 問腦總機併進框架：N-42 開頭的 11-11 註（何時併沒定）。

## 刪掉的舊原文（被 11-11 推翻）

C-47 的 11-05 原話「kernel的定義是管理某proc是否可以執行」「他的proc是掛在linux底下，而非daemon底下。不太...好」，以及同段後半「除此之外，假如他判斷要跑這個請求後，所做的動作是直接執行linux原生proc，或是一些函數，那他算kernel嗎？我覺得是不算的...」（還有效的「轉交也算」那半句照留）；選項文字「加嚴」「Linux 權限＋約定」；kernel/docs/02 的 11-05 原話後半「而kernel按照定義，他是管理proc是否要執行的傢伙」（前半照留）。

## 要你裁的

1. **N-42「兩支不併成一支」（10-16）要不要翻掉**：11-11 頂層的理解是「框架一份、問腦＝框架＋問腦專屬那包」，你沒明確確認、後續發言方向一致。條文原句沒改、加了註。確認就把原句改成「一份通用框架，問腦是框架加專屬那包（何時併未定）」。
2. **兩個都沒設時要不要報錯**：你 11-12 說「只是猜.stack感覺可以留著?」帶問號。現在條文照現行（猜 `./.stack`）寫。確定留就把各處的「未定案」註拿掉；改報錯就照 03 日後清單第 4 項改程式。

## 順帶看到的（不是衝突、只記）

- 「`AOS_DAEMON` 照傳、約定一般 proc 不用」跟現在的工具有落差：`subagent`、`fork`、`self_tools`、`agents_ctl` 與 hook 的 clock 解析仍直接用 `AOS_DAEMON`（[11-11 現況查核](../11/kernel/02-現況查核.md)）；fork／subagent 認 `AOS_KERNEL` 另一條線在改，其餘等狀態位址做好。
- N-42 開頭「都基於 daemon」照 10-15 原樣留：講的是先做哪兩種，不是 kernel 的定義。
