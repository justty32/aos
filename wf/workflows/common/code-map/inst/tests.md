# code map — core/inst/ 測試

← [core/inst 分冊入口](../inst.md)｜[本資料夾導覽](README.md)｜[code map 總圖](../../code-map.md)

`core/inst/tests/` 的逐檔涵蓋範圍。
**新增／刪除 `core/inst/tests/` 底下任何測試檔或測試共用標頭，就在這一份加／減那一列。**

---

## core/inst/tests/ — 測試

跑法見 [testing 工作流](../../../testing.md)。

| 檔案 | 涵蓋 |
|------|------|
| `test_format_read.cpp`／`test_format_write.cpp`／`test_format_malformed.cpp` | format 層：JSON round trip、各種壞輸入、已知/未知欄位 |
| `test_resolve_env.cpp` | resolve 層的 `$env`：所有合法位置、缺變數的回報、解析後重驗、未解析 round trip、stderr 的三種形式、非字串位置禁用指示詞、`capture_environment` |
| `test_resolve_ref.cpp` | resolve 層的 `$ref`：所有合法位置、檔案／pointer／JSON 錯誤、巢狀 env/ref、深鏈無上限、循環與路徑正規化、RFC 6901 跳脫、referenced `$opt`、未解析 round trip |
| `resolve_test_support.hpp` | resolve 層測試共用的 parse、明示 context、暫存目錄與被引用檔案寫入 |
| `test_exec_streams.cpp`／`test_exec_path.cpp`／`test_exec_status.cpp` | exec 層：重導向、PATH 解析、exit status／signal 對應 |
| `test_timeout.cpp` | exec 層：逾時、行程群組 `SIGTERM`→`SIGKILL` |
| `test_handoff.cpp` | handoff 公開 API：衍生路徑、字典序攤平、忽略狀態副檔名、壞投遞隔離、既有 base、空 inbox、claim／release，以及「發布才有 header sidecar」的過帳 |
| `test_handoff_header.cpp` | 彙整的耐久性面：header 四欄位照字面驗、批 id 的確定性、崩潰窗口重播（不得二次發布）、roll forward（崩在兩個 rename 之間）、殘缺 `.temp` 不 roll forward、header 讀不懂就照常重發。崩潰全部用「佈置崩潰後的檔案現場」重現，不殺行程、無 sleep |
| `test_handoff_regression.cpp` | **CLI 端到端**的審查回歸（M1 審查 B 隊四支攻擊腳本 `t3.sh`／`v7.sh`／`v8.sh`／`v11.sh` 改寫而成，手工佈置檔案系統狀態、不 shell out）：#1 固定檔名生產者連投三回合都要真的執行（含「header 未 swept 時殘留不重跑」的反向）、#3 收件匣裡的 FIFO 不讓一輪停擺（自帶 `alarm` 看門狗，退回阻塞就砍行程而不是掛住 CI）、#4 巢狀 `"id"` 不參與去重、#25 斷掉的 symlink `inst.json` 回 1 且投遞不遺失、#21 去重命中不執行無關殘骸（舊固定槽位與新兄弟唯一暫存兩個名字都測）、#26 header 與 sweep 同時失敗時退出碼 1；另有 §D-4「`inst.json` 已有一批就不覆蓋不合併」的確定性佈置。斷言的是退出碼、`.aos/turn`、stderr 與子行程真的留下的腳印 |
| `handoff_test_support.hpp` | handoff 測試共用的暫存世界目錄與整檔讀寫 |
| `test_run_support.hpp` | CLI 測試共用的暫存 world、檔案 I/O、cwd guard、`ScopedFd`（把 stdin／stdout／stderr 暫時換成檔案再換回來——CLI 直接寫真的 fd，而測試跟它同一個 process）與呼叫 helper |
| `test_run_init.cpp` | init、額外 argv 拒絕、`turn` 初值 `0`、`.aos/.gitignore` 內容一字不差（§E-4）與舊世界缺它不算錯，以及 init／exec 的目前目錄預設；`.aos` 是普通檔印 `Not a directory`、是目錄印 `already exists` 兩種訊息各驗一次 |
| `test_run_loop.cpp` | loop argv、連續回合、失敗節流、信號收尾、遇 3 停止與目前目錄預設 |
| `test_run_handoff.cpp` | CLI 的版本、空回合、彙整、隔離、取件、釋放與連續回合整合；`.aos/turn` 在有工作的回合遞增、空轉不動、缺檔的舊世界視為 `0`（裁-5）；`.runi` 已存在時回 3 且**完全不彙整**（投遞還在、沒有 `inst.json`／`inst-head.json`）；重導向開檔失敗會在 stderr 留一行 warning 而退出碼不變 |
| `test_run_turn.cpp` | `.aos/version` 的尾端空白容忍（`1`／`1\n`／`1\n\n`／`1 \n` 皆收，`0`／`2`／空／`abc` 皆拒）在 exec 與 deliver 兩條路徑上；`turn` 等於 `UINT64_MAX` 時拒絕遞增（ERANGE）；`turn.temp` 被目錄佔住時回 1 且不動 `turn`；`RLIMIT_FSIZE` 觸頂時（fork 出的子行程裡 `setrlimit`）不被 SIGXFSZ 砍死、走錯誤路徑並清掉 `turn.temp` |
| `test_run_deliver.cpp` | `aos deliver`：同一 process 連投 N 次得 N 份不同名、單行 JSON 三欄位照字面驗、stdin／`-`／`-f -`／`-f FILE` 四種輸入、投遞後 exec 真的執行、壞批次拒收且收件匣零殘檔、非世界與壞版面回 1、argv 錯回 2；庫層 `deliver_instructions` 的 canonical 位元組、空批次、缺收件匣、非 `.json` 路徑與驗證原因回報。stdin／stdout 用 `dup2` 換描述子在同一 process 內接管 |
| `test_run_batch.cpp` | CLI 批次失敗、路徑基準、循序、parallel、批次尾端 join，以及 `$env`／`$ref` 實際執行整合 |
| `exec_test_support.hpp` | 測試共用的小工具 |
| `test_capi.c` | C ABI 往返測試（獨立的 C 執行檔，不連 C++ 測試框架）；含 `aos_deliver_buffer`／`aos_deliver_file`：正常投遞、buffer 太小（投遞仍發生，只是報不出名字）、壞投遞拒收、來源檔案讀不到、收件匣不存在 |

C++ 測試建成一支 `aos_inst_tests`；C ABI 測試建成 `aos_inst_capi_tests`。
