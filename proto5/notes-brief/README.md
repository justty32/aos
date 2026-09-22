這裡是 notes/ 的精簡版，每份不超過 5000 字；要細節看完整版

| 檔名連結 | 這份是什麼 | 對應完整版 |
|---|---|---|
| [2026-09-22-act-report-astra.md](2026-09-22-act-report-astra.md) | 調查歷代工具在哪裡執行、等候時是否占用 cpu，以及模型收到真結果或收據的差別。比較五種方案，保留崩潰、副作用、排程重疊風險與原報告的 12 題選擇。 | [完整版](../notes/2026-09-22-act-report-astra.md) |
| [2026-09-22-act-summary.md](2026-09-22-act-summary.md) | Claude 把工具方案收斂成短工具同步、慢工具交 tool cpu，結果仍接成 tool 訊息的建議。列出共用工作協議、waits、串行與未知結果處理的 6 題待拍板。 | [完整版](../notes/2026-09-22-act-summary.md) |
| [2026-09-22-agent-task.md](2026-09-22-agent-task.md) | 記錄 aos-agent 實作任務：先檢查 waits，再走 idle、think、act 一格。保留新增入口、產出檔、讀驗、寫檔順序、自癒、測試與實跑要求。 | [完整版](../notes/2026-09-22-agent-task.md) |
| [2026-09-22-daemon-kernel-report-astra.md](2026-09-22-daemon-kernel-report-astra.md) | 調查 aos-run、daemon、kernel 如何啟動、交件、換行程與處理退出碼。整理控制檔協議、文件與程式落差，以及 proto5 移植時不能直接照搬的限制。 | [完整版](../notes/2026-09-22-daemon-kernel-report-astra.md) |
| [2026-09-22-daemon-kernel-spec-task.md](2026-09-22-daemon-kernel-spec-task.md) | 交代如何把 proto4-3 真實行為整理成可供審閱的 proto5 規範草稿。保留格式與程式分檔、產出範圍、待定標記、禁區和回報規則。 | [完整版](../notes/2026-09-22-daemon-kernel-spec-task.md) |
| [2026-09-22-daemon-kernel-summary.md](2026-09-22-daemon-kernel-summary.md) | Claude 建議保留 daemon 與 kernel 分工，列出規範分檔與應修正的舊版問題。集中 6 題決策，包括 module、第一版命令、避免重疊執行、終止子程式與錯誤代號。 | [完整版](../notes/2026-09-22-daemon-kernel-summary.md) |
| [2026-09-22-llm-cpu-plan-task.md](2026-09-22-llm-cpu-plan-task.md) | 交代 llm cpu 的預先規劃任務，只寫規劃筆記，交使用者審閱後才決定規範。要求說清楚舊版交件流程、新版檔案協議，以及 think 如何送出、等待、收回與自癒。 | [完整版](../notes/2026-09-22-llm-cpu-plan-task.md) |
| [2026-09-22-llm-cpu-report-astra.md](2026-09-22-llm-cpu-report-astra.md) | 調查 proto4 的同步 LLM、排隊與 worker、kernel module，以及 agent 等待結果的完整流程。保留檔案與結果格式、容量及逾時邊界、取消與崩潰窗口、重要文件落差。 | [完整版](../notes/2026-09-22-llm-cpu-report-astra.md) |
| [2026-09-22-llm-cpu-summary.md](2026-09-22-llm-cpu-summary.md) | Claude 提議 llm cpu 每次同步做一件工作，以請求檔交件、結果檔回覆、waits 等待。列出 engine、結果位置、交件方式、容量、同步切換與送收辨識的 6 題決策。 | [完整版](../notes/2026-09-22-llm-cpu-summary.md) |
| [2026-09-22-timeout-report-astra.md](2026-09-22-timeout-report-astra.md) | 調查各代有哪些時間限制，區分工作逾時、等待、連敗與整格卡死。保留責任分層、建議預算、終止與恢復風險，以及原報告全部 11 題待拍板。 | [完整版](../notes/2026-09-22-timeout-report-astra.md) |
| [2026-09-22-timeout-summary.md](2026-09-22-timeout-summary.md) | Claude 建議先加工具限時與引擎連敗暫停，整格硬上限留給外層執行者。用 5 題選擇確認預算位置、預設秒數、恢復方式，以及 waits 這輪要不要期限。 | [完整版](../notes/2026-09-22-timeout-summary.md) |

## 今天要使用者拍板的題目總表

> **實作之後的對照**：proto5.1 照這 23 題的建議做完三段（daemon＋kernel＋agent＋llm cpu＋tool cpu 一條龍跑通），逐題結論在 [proto5.1/notes/findings-brief.md](../../proto5.1/notes/findings-brief.md) 第 3 節——15 題可行照建議、6 題要修、2 題（llm cpu 1、6）還是要你決定。

以下共 23 題，題號保留各份 summary 的原編號，前綴用來區分來源。建議是原文 Claude 的建議，尚未拍板；完整選項與理由請看同列連到的精簡版。astra 原報告與 summary 的方案若不同，各篇保留自己的說法，本表只彙整四份 summary。

| 題號 | 一句話 | 建議 |
|---|---|---|
| [act 1](2026-09-22-act-summary.md) | 慢工具完成前，模型等真結果還是先收據？ | A：以等待真結果為主；收據制留給明確標成 async 的長工作。 |
| [act 2](2026-09-22-act-summary.md) | 工具預設同步，還是一律交 tool cpu？ | A：預設同步；工具標 `_run: "cpu"` 才交出去。 |
| [act 3](2026-09-22-act-summary.md) | tool cpu 與 llm cpu 是否共用協議？ | A：共用請求／結果／waits 外框，各用自己的 payload。 |
| [act 4](2026-09-22-act-summary.md) | aos-agent 可否自己新增 waits？ | A：可以，供送 LLM／工具工作及連敗暫停使用。 |
| [act 5](2026-09-22-act-summary.md) | 同一則 assistant 的多個 call 串行還是並行？ | A：先串行，保留副作用順序。 |
| [act 6](2026-09-22-act-summary.md) | 工具結果不明時是否自動重試？ | A：回「結果不明」tool 訊息，不自動重試，避免重複副作用。 |
| [daemon／kernel 1](2026-09-22-daemon-kernel-summary.md) | module 機制要不要留？ | A：不留；llm cpu／tool cpu 都用普通行程。 |
| [daemon／kernel 2](2026-09-22-daemon-kernel-summary.md) | pause／resume／restart 要不要進第一版？ | A：先不做；agent 暫停用 waits，重啟用 rm＋add。 |
| [daemon／kernel 3](2026-09-22-daemon-kernel-summary.md) | daemon 與 kernel 要不要合併？ | A：維持兩支、各自的家，分開管理 Linux 進程與排程。 |
| [daemon／kernel 4](2026-09-22-daemon-kernel-summary.md) | 如何防止同一行程重疊執行？ | A：kernel 換人前看 daemon 的 running，還在跑就不換。 |
| [daemon／kernel 5](2026-09-22-daemon-kernel-summary.md) | 如何連同正在執行的子程式一起終止？ | A：aos-run 第一次收到 TERM 就轉送給子程式 group。 |
| [daemon／kernel 6](2026-09-22-daemon-kernel-summary.md) | 三支程式要不要具名錯誤代號？ | A：要；stderr 統一 `aos-xxx: <代號>: <白話>`。 |
| [llm cpu 1](2026-09-22-llm-cpu-summary.md) | 請求檔帶完整 engine，還是只帶 endpoint 名字？ | A：帶已解好的完整 engine；其中 api_key 會落地，是否接受由使用者決定。 |
| [llm cpu 2](2026-09-22-llm-cpu-summary.md) | 結果寫回 agent，還是留在 cpu 家？ | A：寫到請求指定的 agent 絕對路徑，方便 input／waits 使用。 |
| [llm cpu 3](2026-09-22-llm-cpu-summary.md) | agent 直接寫請求，還是透過 kernel syscall？ | A：直接寫進 cpu 的 requests/。 |
| [llm cpu 4](2026-09-22-llm-cpu-summary.md) | cpu 一次同步問一件，還是派背景 worker？ | A：一次同步問一件；容量由同時開幾顆 cpu 決定。 |
| [llm cpu 5](2026-09-22-llm-cpu-summary.md) | 如何切換同步問與交給 cpu？ | A：engine.cpu 有寫就交出去，沒寫仍同步，方便測試與小 agent。 |
| [llm cpu 6](2026-09-22-llm-cpu-summary.md) | 送出與收回如何區分？ | A：看 ask-result.json 在不在，不另加 state.ask 欄位。 |
| [逾時 1](2026-09-22-timeout-summary.md) | 工具預算放在哪一層？ | A：工具元素旁的 _timeout_ms；保留 _meta 為純 inst。 |
| [逾時 2](2026-09-22-timeout-summary.md) | 工具預設可以跑幾秒？ | A：60 秒，可依工具覆寫。 |
| [逾時 3](2026-09-22-timeout-summary.md) | 引擎連敗幾次停、如何恢復？ | A：連敗 3 次加入 continue.json 等待、errors 歸零；人 touch 才恢復，不以新 input 解鎖。 |
| [逾時 4](2026-09-22-timeout-summary.md) | 整格硬上限由誰負責？ | A：外面的 run／kernel；等 kernel 落地，這輪先不做。 |
| [逾時 5](2026-09-22-timeout-summary.md) | waits 這輪要不要加 until？ | A：先不加，人工 pause 可以一直等。 |
