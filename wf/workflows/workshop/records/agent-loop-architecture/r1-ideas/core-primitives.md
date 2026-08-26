# 本場任務與 `aos core` 該收掉的原語

> 本場的開題、T5 的做法與投遞缺口，加上〈成形的方向〉底下的兩節：`aos core` 該收掉什麼，
> 以及逼出 effect／`unknown` 的那道斷點續跑硬邊界。

本場接續[前一場](../../four-open-choices-tradeoffs.md)的同一批四位參與者；他們帶著 World、kernel、
子行程拓樸與身分仍未拍板的完整脈絡。任務書明講：**不要假裝前四題已定案**，agent loop 的
形狀必須能容納那些選擇繼續懸著。

使用者開題的原話是：

> **討論關於 agent loop 在我們做實現的話，大概架構會長怎麼樣，
> 會需要啥樣的基礎 aos core 功能。**

roadmap T5 給的做法是先不加新的 C++，只用 `.aos/inst.json` 與幾支腳本跑出完整 loop；這一輪
因此不是先設計 `aos agent`，而是觀察腳本重複踩到哪一條協定：

> **這一階段的產出不是程式，是規格：腳本裡哪些地方重複、哪些地方難寫，
> 就是 `aos agent` 該收掉的東西。**

任務書另點名一個 agent loop 開始前就存在的缺口：三步交接協定已有彙整／取件／釋放，
**只有投遞仍是口頭約定，沒有函式。**

## 成形的方向

### `aos core` 該收掉什麼

這一塊是本輪最集中的產出。**四位獨立地都先提出投遞，再提出一個可記錄 `unknown` 的外部效果

| 子命令／函式（候選形狀，未拍板） | 簽名 | 誰提的 | 為什麼腳本自己做不好 |
|---|---|---|---|
| **原子投遞 `deliver`** | CLI：`aos core deliver --to BASE [--key K] [--durable] -`；lib：`deliver_instruction(rootfd, base, bytes, opts) -> receipt` | **四位獨立地都提了**；工程師／架構師／開發者放在 `aos core`，研究人員寫成 `aos deliver` | 腳本很容易短寫、撞名、只寫半份或重送；共用原語可統一 schema／大小檢查、同目錄唯一 temp、write-all、可選 fsync 與 rename。架構師另要求同 key 同內容回 Already、異內容回 Conflict |
| **外部效果 `effect run`／`invoke`／`capture`** | CLI：`aos core effect run --dir CALL --key K -- CMD...`；概念上的 lib：先落 request／key，再執行，最後原子提交 stdout、stderr、exit 與狀態 | **四位獨立地都提了**；命名分別是 capture、invoke、effect run、effect | LLM 或工具可能已被遠端接受、甚至已付費，本機卻在結果落盤前 crash；普通 shell redirection 看不出「沒執行」與「執行了但沒記下」的差別，也無法安全決定是否重跑 |
| **狀態發布 `publish`** | 工程師：`publish(rootfd, path, bytes, opts)`；架構師：`aos core publish EVENT.d TEMPD`，以一次 rename 發布整組檔案 | 工程師、架構師兩位明確要求公開；研究人員與開發者把同一動作包在 effect 完成裡 | cursor、事件與 commit 若逐檔可見，讀者可能看見一半狀態；腳本必須反覆重寫 temp／rename／同步順序。尚未決定它應是公開原語，還是 `deliver`／`effect` 的內部零件 |
| **人工恢復 `effect recover`** | 架構師候選：`recover N --retry|--lost|--import FILE`；研究人員另用 `adopt`，工程師用 retry／abandon，開發者用 reconcile | 架構師明確給 CLI；其餘三位獨立地都要求同一組人工決策，但未都主張由 core 提供命令 | `unknown` 沒有普遍正確的自動答案；把 retry、放棄、匯入／採納既有結果做成明示動作，才不會由腳本偷偷重複付費或重做副作用 |

`deliver` 的細節，四位給出的邊界也一致：CLI 與 lib 必須共用同一份實作；輸入無效時**直接拒絕，
不要發布**；只有繞過 API、直接塞進信箱的壞檔，才由既有彙整者隔離成 `.bad`。大小上限與
`--durable` 要明講，不能由每支 agent 腳本自行猜測。

這使「投遞沒有實作」成為最小、最獨立的缺口：它不是 agent 專用功能，任何外部處理器要安全地
把 instruction 放進三步協定，都需要它。四位也都把 effect 做成通用外呼，而不是 `llm` 子命令，
因為同一個 crash 空窗也會出現在有副作用的工具。

## 斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once

**四位獨立地都指出同一個無法消除的空窗**：provider 已收到請求，但本機還沒把 response
發布，這時 crash，重開後無法只看本機判斷要不要再呼叫。工程師叫它「attempt 有、response 無」，
其餘三位都叫 `unknown`／ambiguous。

可安全自動恢復的情況只有兩種：provider 接受同一 idempotency key，重送不會再付一次；或
provider 能按 request ID 查回原結果。兩者都沒有時，四位都要求停住，讓人選 retry、abandon／
lost，或 import／adopt 一份外部找回的結果。**不得把 unknown 當作「沒跑過」自動重叫。**

資深工程師的一句話最直接：

> **rename 保發布，不保任意 LLM CLI 恰好付費一次。**

`.runi` 仍負責本地批次，commit／receipt／effect record 負責跨外呼的恢復；它們解的是不同層次。
優雅 Ctrl-C 可以讓 wrapper 主動寫出 unknown，但 hard kill 能否也自動留下可辨識狀態，仍是問題。

