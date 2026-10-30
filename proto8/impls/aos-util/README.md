# aos-util

`libaos-util - aos 這一家命令列工具共用的小函式庫`（NAME，C-54 R1）

**一句話：aos 這一家命令列工具共用的小函式庫——錯誤型別與全家的錯誤代號、三扇門（stdin／stdout／stderr）、旗標（兩套：全家用的 `aos/cli.hpp`、
沒人叫的 `aos/flags.hpp`）、設定檔、路徑與原子寫入、子程序、訊號。** 沒有執行檔，只出 `lib/libaos-util.a`。全家慣例見 [impls/README.md](../README.md)。

像一家店的共用倉庫：每支工具自己只放自己獨有的東西，「好幾支都要」的一律放這裡，一份就好。

## 用法

```cpp
int main() {
    try {
        aos::Json in = aos::read_stdin();      // stdin 一份 JSON
        return aos::emit(做事(in));             // stdout 一行、退 0
    } catch (const aos::Error& e) {
        return aos::emit_error(e);              // stderr 一行 {"error": {"code", "msg"}}、退 1
    }
}
```

## 元素（一個標頭一個元素）

| 標頭 | 放什麼 |
|---|---|
| `aos/error.hpp` | `aos::Error{code, msg}`；**全家共用的錯誤代號** `aos::code::*`（ArgumentsBad、FlagUnknown、InputBad、InputExtra、CfgMissing、CfgBad、WriteFailed、MkdirFailed、LaunchFailed、Internal；10-30 加投遞的 CommandUnknown、MailboxMissing、LetterMissing、LetterBad；照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)）。只有一支工具會吐的代號放那支自己的 `code` |
| `aos/io.hpp`（`src/io.cpp`） | 三扇門：`read_stream`（JSON 串流 → 一個個值，壞尾丟掉）、`read_stdin`（一份：空＝`{}`、多份＝InputExtra、解不出來＝InputBad）、`dumps`（排版同 Python `json.dumps`，key 照原順序）、`emit`、`emit_error`；JSON 小工具 `is_count`（非負整數）。`Json`＝`nlohmann::ordered_json` |
| `aos/cli.hpp`（`src/cli.cpp`） | **命令列**（aos-exec、aos-loop、aos-fsm、aos-daemon 共用；對應 `proto8/bin/aos_flags.py` 的 `parse`）：`parse_cli(argv, 旗標表)`——旗標寫在位置參數前面，第一個不是旗標的參數（不以 `-` 開頭，或就是 `-`）起全部原樣放進 `rest`；`--` 結束旗標；旗標都帶一個值（`--x V` 或 `--x=V`，`--x=` 是空字串），重複給最後一個算；可另給一張不帶值的旗標表 `switches`（給了＝`opts[名]` 是 `"1"`、重複給一樣、寫 `--x=V`＝`ArgumentsBad`；aos-exec 的 `--dotenv-override`）；不認得的旗標＝`FlagUnknown`、缺值＝`ArgumentsBad`（`rest` 夠不夠由呼叫者判斷）。`load_cfg(spec)`——設定檔 `檔` 或 `檔#/指標`，回那個位置的值（不驗是不是物件）：檔不在 CfgMissing、其他讀不了或不是 JSON CfgBad、`#` 後不是 `/` CfgBad、`#/` 指不到 CfgMissing、第一行 `#!` 跳過 |
| `aos/flags.hpp`（`src/flags.cpp`） | **另一套旗標**（跟 `aos/cli.hpp` 是兩套；全家沒有程式叫它，aos-schema、aos-directive 的 bin 也沒用）：命令列旗標 `parse_flags(argc, argv, keys, prog)`：`--key 值`（名字＝JSON key 原名）、值先當 JSON 解、`--` 後面整段放 `rest`、位置參數＝ArgumentsBad、不認得＝FlagUnknown |
| `aos/files.hpp`（`src/files.cpp`） | 路徑 `abspath`／`dirname`／`join`（照 Python `os.path`）、`read_file`、`read_json`、**原子寫入** `write_json`（寫 `.名字.tmp` 再 rename；所在資料夾沒有就建）；**入口尋址** `split_hash`（`檔#/指標` 第一個 `#` 就切，`#` 後不是 `/`＝CfgBad）、`read_json_at`（讀檔、第一行 `#!` 跳過、照 JSON pointer 取值；檔不在 CfgMissing、其他讀不到或不是 JSON CfgBad、指不到 CfgMissing） |
| `aos/proc.hpp`（`src/proc.cpp`） | 子程序：`spawn`（posix_spawn，可自成 session）、`has_exited`／`wait_exited`（不收屍）、`signal_group`、`reap`（整群補 SIGKILL 再收屍）、`stop`、`wait_plain`；`proc_started_at_ticks`、`boot_id`（/proc）、`utc_now_ms`（ISO 8601 UTC 到毫秒，state 的 `recorded_at`、trace 的 `started_at`）、`utc_now_ns`、`utc_ms_at`；**信號** `unique_id`（`<UTC 奈秒 20 位>.<pid>.<started_at_ticks>`，N-16 的信號與 aos-lock 放鎖的改名；10-30 從 aos-llm-kernel、aos-post、aos-lock 三份收來）；`sibling_tool`（找兄弟執行檔）；`memfd_with`／`memfd_empty`／`read_all` |
| `aos/text.hpp`（`src/text.cpp`） | `is_utf8`（嚴格，同 Python 的 utf-8 解碼）、`space_at`、`lstrip`／`rstrip`／`strip`（照 Python `str.isspace`／`str.strip()` 認 Unicode 空白，含全形空白）。aos-exec 的 `.env` 值、aos-fsm 的 state 檔與 `next` 檢查用 |
| `aos/signals.hpp`（`src/signals.cpp`） | `SignalCatcher`：擋住 INT／TERM／HUP、用 signalfd 讀；`start`／`sleep(ms)`（有訊號馬上醒）／`first()`／`stop` |

標頭開頭都有白話說明（含「為什麼原子寫入」「為什麼不用訊號處理函數」「行程群組、收屍、memfd 是什麼」），從那裡讀。

## 對應 Python

`aos/cli.hpp` 的 `parse_cli` 對應 `proto8/bin/aos_flags.py` 的 `parse`（10-21 ideas § 3、10-21 傍晚 § 9）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `ctest` 跑 `test_cli`（`tests/test_cli.py`）：用測試小程式 `tests/util_cli.cpp`（讀一份、原樣印）測 emit 排版、讀 stdin 空／多份／壞掉。
  另跑 `test_lib_*`（`tests/test_lib.cpp`，一條一個 ctest）：入口尋址 `split_hash`／`read_json_at`（切 `#`、`#` 後沒 `/`、shebang 跳過、`~0`／`~1` 跳脫、指不到）、`cli`（`parse_cli`／`load_cfg` 的代號——FlagUnknown、ArgumentsBad、CfgMissing、CfgBad）。
  其餘 files／proc／signals 由 aos-loop、aos-daemon 的 compare 測試覆蓋；`parse_cli`／`load_cfg` 沒有自己的測試，由 aos-exec、aos-loop、aos-fsm、aos-daemon 的 `test_cli`（旗標、`檔#/指標`）覆蓋。
- 別的專案怎麼連、vcpkg、產物：見 [impls/README.md「建置」](../README.md#建置)。

## 已知限制

- 只支援 Linux（`posix_spawn` 的 `SETSID`、`memfd_create`、`signalfd`、`/proc`）。
