# code map — core/inst/ 函式庫本體

← [core/inst 分冊入口](../inst.md)｜[本資料夾導覽](README.md)｜[code map 總圖](../../code-map.md)

`core/inst/` 函式庫本體的逐檔職責：對外公開標頭，以及 inst／format／resolve／handoff／exec 五個核心分層。
**新增／刪除 `core/inst/include/aos/` 的標頭，或 `core/inst/src/` 底下屬於這五層的原始碼檔（`inst.cpp`／`format*.cpp`／`.hpp`／`resolve.cpp`／`handoff*.cpp`／`.hpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`），就在這一份加／減那一列。**
C ABI 包裝層見 [capi.md](capi.md)、CLI 層見 [cli.md](cli.md)；跨層的「新增一個 instruction 欄位」維護鏈在 [分冊入口](../inst.md)。

---

## core/inst/include/aos/ — 對外公開標頭

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `inst.hpp` | C++ API。五個分層的宣告都在這（見上面「單向相依是鐵律」）：inst／format／resolve／handoff／exec | `inst_t`、待解析指示詞位置、`InstState`、`read_*`／`write_*`／`validate`、`ResolveContext`／`ResolveResult`／`resolve`、handoff API、`ExecState`／`ExecResult`／`execute()` 與各 `to_string` |
| `inst.h` | C ABI（給非 C++ 呼叫者用），是 `inst.hpp` 的鏡像，型別靠 `static_assert` 對齊（見 `src/capi.cpp`） | `aos_instruction`（opaque）、`aos_exec_result`、`aos_inst_state`／`aos_inst_field`／`aos_exec_state`、`aos_instruction_new/free/clear`、`aos_instruction_argc/arg/push_arg`、`aos_instruction_field/set_field`、`aos_instruction_stderr_merge/set_stderr_merge`、`aos_instruction_env_count/env_key/env_value/set_env`、`aos_instruction_timeout_ms/set_timeout_ms`、`aos_instruction_parallel/set_parallel`、`aos_instruction_read_buffer/read_fd/read_file`、`aos_instruction_write_buffer/write_fd/write_file`、`aos_instruction_execute`、`aos_*_state_string`、`aos_version_string` |

## core/inst/src/ — 五個核心分層

| 檔案 | 負責 |
|------|------|
| `inst.cpp` | **inst 層**：`inst_t::clear()`、`to_string(InstState)`。不碰位元組／JSON，也不碰行程 |
| `format.cpp` | **format 層的公開進入點**：`validate`（對仍是指示詞的位置延後值檢查）、`read_one`／`read_all`／`write_one`／`write_all`（保持整批原子性），以及 `pending_directives` 的查找 `find_directive` |
| `format_internal.hpp` | **內部標頭**（不對外）：format 層三個檔之間的宣告——`find_directive`／`encode`／`decode`。format 層是唯一懂 instruction JSON schema 的層，這個標頭不可以被 handoff／resolve／exec 引用 |
| `format_decode.cpp` | **format 層**：instruction JSON → `inst_t`。認得的 key（`known_key`）、字串位置的 `$env`／`$ref` 指示詞辨認並記進 `pending_directives`、`stderr` 專屬的 `{"$opt":"merge"}` 都在這裡 |
| `format_encode.cpp` | **format 層**：`inst_t` → instruction JSON。未解析的指示詞照原樣寫回，所以能無損 round trip |
| `resolve.cpp` | **resolve 層**：以明示的環境與 `base_path` 交易式解析 `$env`／`$ref`；讀取被引用 JSON、套用 RFC 6901 pointer，以正規化路徑＋pointer 追蹤無限深引用鏈及循環。錯誤帶回 instruction 位置、檔案、pointer、鏈與 errno；完成後重新呼叫 format 驗證。不依賴 handoff 或 exec |
| `handoff.cpp` | **handoff 層的三個公開動作**：投遞聚合（含空投遞消化與原子發佈）、取件、釋放，以及兩個 `to_string`；只依賴 inst＋format，不印訊息、不執行 instruction |
| `handoff_fs.hpp`／`.cpp` | **內部標頭**（不對外）。handoff 層的路徑推導與低階檔案存取：從 base path 推出 `.temp`／`.runi`／`.tempd`（`HandoffPaths`）、EINTR-safe 的整檔讀寫、投遞檔名判定與 path join。不碰 `HandoffResult`、不做交接決策 |
| `exec.cpp` | **exec 層**：唯一碰 `fork`／`execve`／`waitpid` 的檔。`execute()`：組 `argv`＋`envp`（透過 `spawn_prep`）→ `fork` → 子行程 `setpgid`＋重導向（stderr merge 時在 stdout 設好後 `dup2(1, 2)`）＋`chdir`＋`execve`（`run_child`，全程 async-signal-safe）→ 父行程視 `timeout_ms` 決定直接 `wait_retry` 或 `wait_until` 輪詢；逾時先對整個行程群組送 `SIGTERM`、給 `kTimeoutGraceMs`（2000ms）緩衝，仍不收就 `SIGKILL` 整個群組——打群組是因為忽略 `SIGTERM` 的孫行程才殺得掉。結束後若 `exit_path` 非空就把 exit code 寫進那個檔 |
| `spawn_prep.hpp`／`.cpp` | **內部標頭**（不對外）。`prepare_spawn()`：在 `fork` 之前把所有會配置記憶體的準備工作做完——合併繼承的環境變數與 `inst.env`（後者覆蓋前者）、組 `envp`、若 `argv[0]` 沒有 `/` 就沿 `PATH`（或 `confstr(_CS_PATH)` 的預設值）逐段找可執行檔。子行程只拿到已經算好的穩定指標 |
| `wait.hpp`／`.cpp` | **內部標頭**。`wait_retry()`：EINTR-safe 的 `waitpid` 包裝。`wait_until()`：用 `CLOCK_MONOTONIC` 算經過時間，指數退避（上限 `kMaxPollMs`＝50ms）輪詢 `waitpid(WNOHANG)` 直到逾時 |

**改 exec 的行為要小心兩件事**：① `fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的操作（細節與理由見 `core/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」）；② 逾時後的 `SIGKILL` 一定要打整個行程群組（`-pid`），不是單一 `pid`。

**這一層有幾處刻意的設計，不要「修」**：PATH 撞到同名目錄時回 exit 126 而不是 127；三處 `kill(-pid, ...)` 的回傳值刻意忽略；`wait_until()` 出錯時直接 return、不 kill 不 reap。外部審查工具會反覆把它們當成 bug 提出來。
