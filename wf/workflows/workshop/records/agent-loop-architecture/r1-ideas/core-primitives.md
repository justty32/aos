# 本場任務與 `aos core` 該收掉的原語

> 本場的開題、T5 的做法與投遞缺口，加上〈成形的方向〉底下的兩節：`aos core` 該收掉什麼，
> 以及逼出 effect／`unknown` 的那道斷點續跑硬邊界。

本場與[前一場](../../four-open-choices-tradeoffs.md)是同一批參與者；前一場四題未拍板，agent loop 的
形狀要能容納那些選擇繼續懸著。

使用者開題的原話是：

> **討論關於 agent loop 在我們做實現的話，大概架構會長怎麼樣，
> 會需要啥樣的基礎 aos core 功能。**

roadmap T5 的做法：先不加新的 C++，只用 `.aos/inst.json` 與幾支腳本跑出完整 loop，觀察腳本重複踩到
哪一條協定：

> **這一階段的產出不是程式，是規格：腳本裡哪些地方重複、哪些地方難寫，
> 就是 `aos agent` 該收掉的東西。**

開場前就存在的缺口：三步交接協定已有彙整／取件／釋放，**只有投遞仍是口頭約定，沒有函式。**

## 成形的方向

### `aos core` 該收掉什麼

候選原語是四類：原子投遞（deliver）、外部效果（effect，先落 request／key 再執行、原子提交 stdout、
stderr、exit 與狀態）、狀態發布（publish，不讓 cursor／事件逐檔露出半套）、`unknown` 的人工恢復
（retry／放棄／匯入或採納既有結果）。R2 收成 Publish／Deliver／Effect（含 resolve）三項，候選簽名與
「腳本自己做不好什麼」見 [三個功能家族](../r2-three-primitives/three-primitives.md)。

`deliver` 的邊界：CLI 與 lib 共用同一份實作；輸入無效時**直接拒絕，不要發布**；只有繞過 API、直接
塞進信箱的壞檔，才由既有彙整者隔離成 `.bad`。大小上限與 `--durable` 要明講，不能由每支 agent 腳本
自行猜測。同 key 同內容回 Already、異內容回 Conflict 是候選語意。

「投遞沒有實作」是最小、最獨立的缺口：它不是 agent 專用功能，任何外部處理器要安全地把 instruction
放進三步協定都需要它。effect 做成通用外呼，不做成 `llm` 子命令，因為同一個 crash 空窗也會出現在有
副作用的工具。

## 斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once

無法消除的空窗：provider 已收到請求，本機還沒把 response 發布就 crash，重開後只看本機無法判斷要不要
再呼叫。這個狀態叫 `unknown`。

可安全自動恢復只有兩種：provider 接受同一 idempotency key，重送不會再付一次；或 provider 能按
request ID 查回原結果。兩者都沒有時停住，讓人選 retry、abandon／lost，或 import／adopt 一份外部
找回的結果。**不得把 unknown 當作「沒跑過」自動重叫。**

**rename 保發布，不保任意 LLM CLI 恰好付費一次。**`.runi` 負責本地批次，commit／receipt／effect
record 負責跨外呼的恢復，兩者解不同層次。優雅 Ctrl-C 可以讓 wrapper 主動寫出 unknown；hard kill
能否也自動留下可辨識狀態，仍是問題。
