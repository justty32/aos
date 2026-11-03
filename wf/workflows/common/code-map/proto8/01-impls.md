← [入口](../proto8.md)｜涵蓋：`proto8/impls/` 共通建置、`inst`、`aos-util`、`aos-directive`、`aos-schema`、`aos-exec`｜下一份：[01-impls-2](01-impls-2.md)

各專案的行為細節以 [impls/README](../../../../../proto8/impls/README.md) 與各專案 README 為準；這裡只說哪個檔負責什麼。路徑相對於該段標題的資料夾。

## `impls/`（共通）

| 檔 | 負責什麼 |
|---|---|
| `cmake/settings.cmake` | 全家 C++ 專案共用的 CMake 設定（只有 `set()`），各 `CMakeLists.txt` 在 `project()` 前 include |
| `*/CMakeLists.txt`、`*/vcpkg.json` | 各專案的建置：靜態庫＋`-static-pie` 執行檔；相依（nlohmann-json 等）走 vcpkg |
| `*/.gitignore` | 擋各專案的 `bin/`、`lib/`、`build/` |
| `inst/.vscode/settings.json` | inst 的編輯器設定 |

## `impls/inst/`（C 函式庫 libaos：起一個子程式、等它、收結果）

| 檔 | 負責什麼 |
|---|---|
| `include/aos.h` | 公開介面：`aos_inst_exec`，或兩步 `aos_inst_start` → `aos_inst_wait` |
| `src/inst_exec.c` | 四個公開函數：檢查參數、開串流、起、等、填結果 |
| `src/inst_proc.c` | fork＋exec（失敗 errno 經 CLOEXEC pipe 傳回）、pidfd、逾時 SIGTERM 再 SIGKILL、單調時鐘 |
| `src/inst_stream.c` | 三個串流的開檔、fd 搬到 3 以上 |
| `src/inst_internal.h` | 內部標頭 |
| `tests/test_lib.c`、`tests/test_ffi.py` | C 單元測試、經 FFI 的測試 |

## `impls/aos-util/`（全家共用的函式庫）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/cli.hpp`、`src/cli.cpp` | 命令列 `parse_cli`（旗標在位置參數前、`--x V`／`--x=V`、`--` 結束、開關表 `switches`）、`load_cfg`（`檔` 或 `檔#/指標`） |
| `include/aos/flags.hpp`、`src/flags.cpp` | 較早一代的旗標規則（旗標名＝設定 JSON 的 key） |
| `include/aos/error.hpp` | 共用錯誤型別 `aos::Error` 與多支工具都會吐的錯誤代號 `aos::code` |
| `include/aos/io.hpp`、`src/io.cpp` | 三扇門：stdin 讀 JSON（串流）、stdout 印一行 JSON、stderr 印一行錯誤 |
| `include/aos/files.hpp`、`src/files.cpp` | 路徑、讀檔、原子寫入（暫存檔再改名） |
| `include/aos/proc.hpp`、`src/proc.cpp` | 子程序（起、看、整群送訊號、收屍）、`/proc`、memfd、`utc_now_ms`／`utc_now_ns`、獨一無二的名字 `unique_id`、身分 `identity`（`AOS_WS` ＞ `AOS_STACK` ＞ `AOS_CF` ＞ cwd） |
| `include/aos/signals.hpp`、`src/signals.cpp` | 擋 SIGINT／SIGTERM／SIGHUP、經 signalfd 讓呼叫者每次去看 |
| `include/aos/text.hpp`、`src/text.cpp` | UTF-8 檢查、照 Python `str.isspace` 去頭尾空白 |
| `tests/test_lib.cpp`、`tests/test_cli.py`、`tests/util_cli.cpp` | 單元測試；`util_cli.cpp` 是測三扇門用的小程式 |

## `impls/aos-directive/`（指示詞 `$ref`／`$env` 的函式庫）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/directive.hpp` | 公開介面：解 JSON 裡帶 `$ref`／`$env` 的物件 |
| `src/resolve.cpp` | 走訪；`$path` 字串拼接；`resolve_shallow`（只換這一格，回各 key 的起點 `dir_of`） |
| `src/ref.cpp` | `$ref`：取檔與指標、繞圈、陣列多份合併（`merge`） |
| `src/env.cpp` | `$env`：換成環境變數的值 |
| `src/internal.hpp` | 內部標頭 |
| `src/main.cpp` | 命令列 `aos-directive < 設定.json`（不算對外提供） |
| `tests/test_cli.py` | 命令列黑箱 |

## `impls/aos-schema/`（用 JSON Schema draft-07 驗 JSON）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/schema.hpp` | 公開介面：驗一份 JSON，回「哪裡不對」清單 |
| `src/validate.cpp` | 唯一碰驗證器（pboettch）的檔；先用 meta-schema 驗 schema 本身 |
| `src/load_file.cpp` | 讀 schema 檔（`SchemaMissing`／`SchemaBad`） |
| `src/main.cpp` | 命令列 `aos-schema SCHEMA檔 < doc.json`，印 `{"valid", "problems"}` |
| `examples/inst.schema.json` | inst 單子的 schema 範例 |
| `tests/test_lib.cpp`、`tests/test_cli.py`、`tests/data/*` | 單元、命令列黑箱與測試資料 |

## `impls/aos-exec/`（在工作區執行一個資料夾程式）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/exec.hpp` | 公開 API：`run_cli`、`run_inst`、`argv0`、`Result`、代號 |
| `src/main.cpp` | 命令列：把參數交給 `run_cli` |
| `src/cli/cli.cpp`、`src/cli/cli.hpp` | `run_cli`：解旗標（`--ws`、`--stack`、`--dotenv-override`）→ 一跳跳走 → `launch` |
| `src/find/find.cpp`、`src/find/find.hpp` | `hop`：定工作區 → 找入口 → 建 stack → `enter`（cd、讀 `.env`、旗標蓋回）→ 照 `$AOS_ENTRY` 挑入口、設 `AOS_CF`／`AOS_CD`／`AOS_CO` |
| `src/find/classify.cpp` | 判種類（資料夾、JSON 物件、單子、轉向）、轉向繞圈 |
| `src/env/env.cpp`、`src/env/env.hpp` | `check_ws`、`setup_stack`、`set_env`（只展開 `${名字}`、錯不印值）、JSON `.env` key |
| `src/env/dotenv.cpp` | `.env` 檔的 dotenv 基礎子集（引號、註解、`export`） |
| `src/launch/launch.cpp`、`src/launch/launch.hpp` | 執行可執行檔／argv 陣列；inst 單子交給 `run_inst` |
| `src/inst/run.cpp`、`src/inst/inst.hpp` | `run_inst`：解指示詞 → 驗欄位 → 轉成 libaos 單子 → 跑 |
| `src/inst/fields.cpp` | 單子的 10 個 key 與型別檢查 |
| `src/inst/lib_input.cpp` | Inst → libaos 的 `aos_inst_input_t`（絕對路徑、完整環境） |
| `src/inst/signals.cpp` | 跑單子期間轉訊號給子程式整群，逾 grace_ms 再 SIGKILL |
| `src/common/common.hpp` | 內部共用標頭 |
| `tests/test_cli.py` | 命令列黑箱 |
