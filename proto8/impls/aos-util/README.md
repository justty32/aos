# aos-util

**一句話：aos 這一家命令列工具共用的小函式庫——錯誤型別與全家的錯誤代號、三扇門（stdin／stdout／stderr）、旗標（兩套：10-21 起的命令列、
10-16～17 那代）、設定檔、路徑與原子寫入、子程序、訊號。** 沒有執行檔，只出 `lib/libaos-util.a`。全家慣例見 [impls/README.md](../README.md)。

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
| `aos/error.hpp` | `aos::Error{code, msg}`；**全家共用的錯誤代號** `aos::code::*`（Usage、FlagUnknown、JsonSyntax、InputExtra、FieldType、Conflict、ReadFailed、WriteFailed、MkdirFailed、LaunchFailed、Internal）。只有一支工具會吐的代號放那支自己的 `code` |
| `aos/io.hpp`（`src/io.cpp`） | 三扇門：`read_stream`（JSON 串流 → 一個個值，壞尾丟掉）、`read_stdin`（一份：空＝`{}`、多份＝InputExtra、解不出來＝JsonSyntax）、`dumps`（排版同 Python `json.dumps`，key 照原順序）、`emit`、`emit_error`；JSON 小工具 `is_count`（非負整數）。`Json`＝`nlohmann::ordered_json` |
| `aos/cli.hpp`（`src/cli.cpp`） | **10-21 起的命令列**（aos-exec、aos-loop、aos-fsm、aos-daemon 共用；對應 bin 的 `aos_flags.parse`／`load_cfg`）：`parse_cli(argv, 旗標表)`——旗標寫在位置參數前面，第一個不是旗標的參數（不以 `-` 開頭，或就是 `-`）起全部原樣放進 `rest`；`--` 結束旗標；旗標都帶一個值（`--x V` 或 `--x=V`，`--x=` 是空字串），重複給最後一個算；不認得的旗標、缺值＝`Usage`（`rest` 夠不夠由呼叫者判斷）。`load_cfg(spec)`——設定檔 `檔` 或 `檔#/指標`，回那個位置的值（不驗是不是物件）：讀不到 ReadFailed、不是 JSON JsonSyntax、`#` 後不是 `/` 或指不到 FieldType、第一行 `#!` 跳過 |
| `aos/flags.hpp`（`src/flags.cpp`） | **10-16～17 那代**（跟 `aos/cli.hpp` 是兩套；目前全家沒有程式叫它，aos-schema、aos-directive 的 bin 也沒用）：命令列旗標 `parse_flags(argc, argv, keys, prog)`：`--key 值`（名字＝JSON key 原名）、值先當 JSON 解、`--` 後面整段放 `rest`、位置參數＝Usage、不認得＝FlagUnknown |
| `aos/files.hpp`（`src/files.cpp`） | 路徑 `abspath`／`dirname`／`join`（照 Python `os.path`）、`read_file`、`read_json`、**原子寫入** `write_json`（寫 `.名字.tmp` 再 rename；所在資料夾沒有就建）；**入口尋址** `split_hash`（`檔#/指標` 第一個 `#` 就切，`#` 後不是 `/`＝FieldType）、`read_json_at`（讀檔、第一行 `#!` 跳過、照 JSON pointer 取值；讀不到 ReadFailed、不是 JSON JsonSyntax、指不到 FieldType） |
| `aos/proc.hpp`（`src/proc.cpp`） | 子程序：`spawn`（posix_spawn，可自成 session）、`has_exited`／`wait_exited`（不收屍）、`signal_group`、`reap`（整群補 SIGKILL 再收屍）、`stop`、`wait_plain`；`proc_started`、`boot_id`（/proc）；`sibling_tool`（找兄弟執行檔）；`memfd_with`／`memfd_empty`／`read_all` |
| `aos/signals.hpp`（`src/signals.cpp`） | `SignalCatcher`：擋住 INT／TERM／HUP、用 signalfd 讀；`start`／`sleep(ms)`（有訊號馬上醒）／`first()`／`stop` |

標頭開頭都有白話說明（含「為什麼原子寫入」「為什麼不用訊號處理函數」「行程群組、收屍、memfd 是什麼」），從那裡讀。

## 對應 Python

`proto8/lib/aos_cli.py` 的 `CliError`、`read_stream`、`_load_stdin`、`emit`、`error`、`parse_argv`、`_value`、`is_int`；
`aos_ctl_state.py` 的 `write_json`、`proc_started`；`aos_proc.py` 的 `_exited`、`_killpg`、`reap`、`stop`；
`aos_loop.py` 的 `Loop.run` 裡 `signal.signal(...)` 那段。
`aos/cli.hpp` 對應的是 `proto8/bin/aos_flags.py` 的 `parse`、`load_cfg`（10-21 ideas § 3、10-21 傍晚 § 9）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `ctest` 跑 `test_cli`（`tests/test_cli.py`）：用測試小程式 `tests/util_cli.cpp`（讀一份、原樣印）測 emit 排版、讀 stdin 空／多份／壞掉。
  另跑 `test_lib_*`（`tests/test_lib.cpp`，一條一個 ctest）：入口尋址 `split_hash`／`read_json_at`（切 `#`、`#` 後沒 `/`、shebang 跳過、`~0`／`~1` 跳脫、指不到）。
  其餘 files／proc／signals 由 aos-loop、aos-daemon 的 compare 測試覆蓋；`parse_cli`／`load_cfg` 沒有自己的測試，由 aos-exec、aos-loop、aos-fsm、aos-daemon 的 `test_cli`（旗標、`檔#/指標`）覆蓋。
- 別的專案怎麼連、vcpkg、產物：見 [impls/README.md「建置」](../README.md#建置)。

## 已知限制

- 只支援 Linux（`posix_spawn` 的 `SETSID`、`memfd_create`、`signalfd`、`/proc`）。
