# code map — core/inst/ CLI 層

← [core/inst 分冊入口](../inst.md)｜[本資料夾導覽](README.md)｜[code map 總圖](../../code-map.md)

`core/inst/src/` 裡 CLI 層（`aos init`／`aos exec`／`aos deliver` 的世界／回合層）的逐檔職責。
**新增／刪除 `core/inst/src/run*.cpp`／`run*.hpp`，就在這一份加／減那一列。**

---

## core/inst/src/ — CLI 層

| 檔案 | 負責 |
|------|------|
| `run.hpp`／`run.cpp` | CLI 對內介面、init／exec argv 解析、folder 預設 `.`、將 `--loop 0` 警告並下限化為 1 ms、配置失敗例外邊界，以及 exec／init 兩個 C 入口（deliver 的解析與 C 入口自帶於 `run_deliver.cpp`，只在 `run.hpp` 掛一行宣告） |
| `run_internal.hpp` | CLI 各實作檔之間的內部宣告：單回合、loop、init world、deliver world |
| `run_init.cpp` | 建立 `.aos/`、版本 1、`inst.tempd/` inbox 與回合計數器 `turn`（初值 `0`，§B-3），失敗時回滾剛建立的狀態 |
| `run_deliver.cpp` | `aos deliver [folder] [-f FILE|-]`：argv 解析（folder 預設 `.`、輸入預設 stdin、`-` 與 `-f -` 都是 stdin、認不得的選項回 2）、把輸入整份讀進記憶體（`-f` 的路徑相對**呼叫者的** cwd，所以讀在 chdir 之前），再進世界驗 `.aos` 與版面版本、呼叫庫層 `deliver_instructions`、把 `{"delivery","count","target"}` 印成單行 JSON（§D-3）。退出碼 0／1／2；`aos_deliver_cli_main` 是它的 C 入口 |
| `run_exec.cpp` | 單回合：進入 world、驗版本、aggregate → claim → execute batch → release，release 成功後遞增 `.aos/turn`（讀不到視為 `0`，裁-5／§B-3；temp→fsync→rename→fsync 目錄），並把結果映成診斷與 0／1／3 |
| `run_loop.cpp` | `--loop` 的空回合輪詢、0／1／3 政策，以及兩段式 SIGINT／SIGTERM 收尾 |
| `run_batch.hpp`／`run_batch.cpp` | CLI 內部批次迴圈：整批解析後以父行程環境 resolve 全部記錄，再同步執行一般記錄、複製 `parallel` 記錄進 thread，最後全數 join；resolve 錯誤會印出記錄、位置與變數 |
