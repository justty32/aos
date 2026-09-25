本報告以 **2026-09-22 調查時的工作樹**為準；調查開始時 HEAD 為 `9c45f06cd6ac4bd6c2e24f66cf724952dd2dfe92`。全程未修改檔案。已逐支閱讀指定程式與相關測試；**沒有執行會建立檔案、啟動 daemon 或 worker 的測試**。另外用記憶體中的 JSON 與 mock 讀檔核對了部分解析差異。

以下以程式碼為事實來源，測試作為既有行為的旁證。「型別」若沒有另註，是程式正常寫出的型別，**不表示讀取端有完整驗證該型別**。

| 本報告用語 | 意思 |
|---|---|
| `H` | daemon 家目錄 |
| `K` | kernel 家目錄 |
| CPU | daemon 管理的一支 `aos-run`；反覆讀取同一路徑的指令檔 |
| kernel 行程／`pid` | kernel 的邏輯行程，名稱是字串，來自 `<pid>.json` 的檔名；不是 Linux PID |
| daemon entry 的 `pid` | `aos-run` 的 Linux PID，整數 |
| 一次執行 | 一次 `aos_exec.run_target()` |
| kernel tick | 一次 `aos-kernel-tick`；與 CPU 完成一次執行不是同一件事 |
| `kind` | `child`、`aos`、`usage`，用來區分退出碼來源 |

---

## 分檔目錄

> 2026-09-25 整理：原檔 1210 行超過 300 行門檻，按標題逐字拆進 [`2026-09-22-daemon-kernel-report-astra/`](2026-09-22-daemon-kernel-report-astra/01-aos-run.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 長度 |
|---|---|---|---|
| 1 | [01-aos-run.md](2026-09-22-daemon-kernel-report-astra/01-aos-run.md) | 1. aos-run（1.1～1.5） | 137 行 |
| 2 | [02-aos-daemon.md](2026-09-22-daemon-kernel-report-astra/02-aos-daemon.md) | 2. aos-daemon／aos-daemon-ctl（2.1～2.9） | 297 行 |
| 3 | [03-aos-kernel-入口到退出碼.md](2026-09-22-daemon-kernel-report-astra/03-aos-kernel-入口到退出碼.md) | 3. aos-kernel ＞ 3.1～3.10（入口、家目錄、config、inst、state、行程狀態、init／boot／add、tick、FIFO、退出碼） | 261 行 |
| 4 | [04-aos-kernel-崩潰到llm介面.md](2026-09-22-daemon-kernel-report-astra/04-aos-kernel-崩潰到llm介面.md) | 3. aos-kernel ＞ 3.11～3.15（換檔與崩潰、syscall rm、module、ls、LLM module 介面） | 188 行 |
| 5 | [05-aos-kernel-llm檔案到測試.md](2026-09-22-daemon-kernel-report-astra/05-aos-kernel-llm檔案到測試.md) | 3. aos-kernel ＞ 3.16～3.20（`K/llm/`、LLM 排程、既有使用事實、錯誤代號、測試旁證） | 228 行 |
| 6 | [06-文件落差與proto5相容.md](2026-09-22-daemon-kernel-report-astra/06-文件落差與proto5相容.md) | 4. 文件與程式碼的落差，以及 proto5 相容性（4.1～4.5） | 94 行 |
