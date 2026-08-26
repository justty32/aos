# 名詞表：喚醒、進度與短路
← [名詞表：回合、執行與喚醒](README.md)｜[BACKGROUND](../../BACKGROUND.md)｜[workshop](../../README.md)｜[待答問題](../../OPEN-QUESTIONS.md)

一回合被什麼觸發、進度書籤記在哪，以及批次裡哪幾筆不該跑。

### tick（定期心跳／wake）

**白話**：外面每隔一段時間敲一下門，讓專案檢查有沒有今天到期、現在該做的事。
**嚴格**：一次性的 periodic dispatcher invocation，依序呼叫各定期 workflow，由各 workflow 判斷 due state 並執行；它不是一個常駐 scheduler 本體。
**在 aos 裡具體是什麼**：文件工作流已存在，入口是 `wf/workflows/tick.md` 與 `/wf-tick`；`aos wf` runtime 內建 wake 目前不存在。
**為什麼會冒出這個詞**：[workflows 場](../../records/workflows-on-aos.md) 想知道定時嗚醒是普遍需求還是這個 repo 的特例，因為它會決定是否值得長出 scheduler state。

### cursor（已處理位置／輪轉位置）

**白話**：一個書籤，記得上次做到哪裡或下次輪到誰，避免每次從頭來或總是先吃同一份。
**嚴格**：耐久 progress/scheduling pointer，可指向最後已 commit 的 event、下一個 ready job 或 round-robin 位置；必須在對應 Deliver/commit 成功後才前進。
**在 aos 裡具體是什麼**：目前沒有通用 cursor 格式；workflows task、agent history、有限資源公平排程都曾提出各自的 `cursor.json`。
**為什麼會冒出這個詞**：[核心行程場](../../records/core-process-and-subprocess.md) 的 `dofuncs`、[agent loop 場](../../records/agent-loop-architecture.md) 的 history commit 與[workflows 場](../../records/workflows-on-aos.md) 的 tick 都需要避免「先記已做、其實沒投遞成功」。

### 短路（short-circuit）與 `"needs"`

**白話**：一串接力，第一棒摔倒了，剩下的人照樣把空手交下去，最後還宣布「這場跑完了」。短路就是「前面那棒沒拿到棒子，我就不跑」。
**嚴格**：批次內前一筆非零結束時跳過後續筆數的語意。aos 目前**沒有**這個語意，且這是規格明訂的行為（非零子行程狀態、訊號終止、逾時都算「一次已完成的執行」，不中止後續記錄，回合仍回 0）。`"needs": "<exit 檔路徑>"` 是提案中的 instruction 欄位：該 exit 檔不存在或不是 0，這一筆就跳過。
**在 aos 裡具體是什麼**：**提案，目前不存在**；`core/inst/docs/format.md` 的欄位表沒有它。真要加，`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉已列出要動的檔。下一輪會先用世界內的一支 `bin/gate` 在不改 C++ 的前提下模擬，再決定要不要進格式。
**為什麼會冒出這個詞**：[agent loop 黑客松第 1 輪](../../../hackathon/records/agent-loop.md) 有人把模型那一站換成必定失敗的程式，七站裡五站在失敗之後照跑，transcript 被一則空的模型回合汙染，而 `aos exec` 仍回 0。評委判定這**不是實作與規格對不上**，是功能請求，但也說這是本輪他最想看到被做出來的東西。
