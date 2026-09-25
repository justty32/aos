本次以工作樹中的程式碼為準，完成唯讀調查，未修改檔案、未呼叫真模型。指定的實作與測試已逐檔閱讀；以下區分「程式實際行為」「既有測試涵蓋」及「由執行順序推導的崩潰／競態窗口」。

最核心的事實是：**proto4-7 把模型請求交給 kernel 的 `llm` module；module 排入檔案佇列，再啟動獨立 OS worker 做同步 HTTP。agent 留下結果檔路徑，日後重新被執行時查檔。kernel 收到 101 後只處理排程，不知道 agent 在等哪個檔。**

這裡稱為「LLM cpu」的 worker，**沒有登記成 `K/cpus/` 裡的一顆普通 cpu**。module 的排程函式在 kernel tick 行程內執行；模型呼叫則在它啟動的背景 worker 行程中執行。[派工實作:192](../../proto4-5/llm_cpu_tick.py)、[kernel 呼叫順序:41](../../proto4-3/aos_kernel_tick.py)

## 分檔目錄

> 2026-09-25 整理：原檔 1099 行超過 300 行門檻，按標題逐字拆進 [`2026-09-22-llm-cpu-report-astra/`](2026-09-22-llm-cpu-report-astra/01-術語與aos-llm.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 長度 |
|---|---|---|---|
| 1 | [01-術語與aos-llm.md](2026-09-22-llm-cpu-report-astra/01-術語與aos-llm.md) | 0. proto5 術語與本次讀到的現況；1. proto4-5 第一層：`aos-llm`（1.1～1.7） | 262 行 |
| 2 | [02-llm-cpu-上.md](2026-09-22-llm-cpu-report-astra/02-llm-cpu-上.md) | 2. proto4-5 第二層：llm-cpu ＞ 2.1～2.5（分工、家目錄、請求檔、回應檔、一格 tick） | 208 行 |
| 3 | [03-llm-cpu-下.md](2026-09-22-llm-cpu-report-astra/03-llm-cpu-下.md) | 2. ＞ 2.6～2.11（派工、收尾與逾時、冪等、兩種模式、`--wait` 路徑、崩潰窗口） | 166 行 |
| 4 | [04-aos-agent交出與收回.md](2026-09-22-llm-cpu-report-astra/04-aos-agent交出與收回.md) | 3. proto4-7：`aos-agent` 如何交出問題再收回（3.1～3.11） | 262 行 |
| 5 | [05-kernel-module與落差.md](2026-09-22-llm-cpu-report-astra/05-kernel-module與落差.md) | 4. proto4-3 kernel：module／syscall／101（4.1～4.5）；5. 文件與程式對不上的地方；6. 測試證據與本次驗證範圍 | 205 行 |
