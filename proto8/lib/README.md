# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

三支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`；相對路徑一律從呼叫者的 cwd 算。TARGET 都可以接 `檔#/位置`（見[指示詞](directives.md)）。inst 照 NORMS N-12 重做（10-14）：命令列走 `aos_cli`——`[--key 值 ...] [TARGET | -] [-- argv...]`，`-`＝設定從 stdin 來，純量 key 有同名旗標；stdout／stderr 吐 JSON 串流。loop、daemon 還沒重做，命令列仍只收一個 TARGET。

## 細節（各一份）

| 檔 | 內容 |
|---|---|
| （`aos_cli.py` 檔頭） | 命令列與三扇門：TARGET／`-`／旗標／`--` 合成設定、JSON 串流讀寫（N-12 程式範本） |
| [directives.md](directives.md) | 指示詞 lib（`$ref`、`$env`、`resolve()`）與命令列 TARGET 的 `檔#/位置`（`split_target`、`target_id`、`locate`） |
| [inst.md](inst.md) | inst：TARGET、key、`run()`、exit 檔、訊號、API |
| [loop.md](loop.md) | loop：loop.json、每一次怎麼跑、ctl.json、state.json、退出碼、給 daemon 共用的 |
| [daemon.md](daemon.md) | daemon：daemon.json、自己的 state／ctl、表、控制資料夾與指令、save／load、收工 |
| [ctl-state.md](ctl-state.md) | ctl 與 state 的慣例：各層的設定檔／ctl／state、key 四組、state 骨架、七個狀態值 |

## 程式

| 檔 | 是什麼 |
|---|---|
| `aos_directives.py` | 指示詞 lib；命令列 TARGET 的 `檔#/位置`（三支程式共用） |
| `aos_cli.py` | 命令列與 stdio（`config()`、`parse_argv()`、`load_target()`、`read_stream()`、`emit()`／`error()`／`warn()`、`CliError`）；inst、loop 共用，N-12 的程式範本 |
| `aos_inst.py` | inst：設定從 TARGET／stdin／旗標來、解好、挑認得的 key、跑一次、stdout 吐一份結果（命令列＋`run()`） |
| `aos_loop.py` | loop：包一個 inst，跑幾次、隔多久、讀 ctl.json（命令列＋`run()`＋`load_config()`）；re-export 下面兩檔的名字 |
| `aos_ctl_state.py` | ctl.json（`parse_ctl`、`want`、`CtlFile`）、state.json（`STATES`、`state_doc`、`read_state`、`StateFile`）、`write_json`；loop、daemon 共用 |
| `aos_proc.py` | 子程序的行程群組：等結束、整群送訊號、收屍（`kill`、`reap`）；loop、daemon 共用 |
| `aos_daemon.py` | daemon：命令列＋`run()`、daemon.json、主迴圈；re-export 下面兩檔的名字 |
| `aos_daemon_table.py` | daemon 的表：`Table`（一條指令一個方法、save／load、收工）、`DaemonError` |
| `aos_daemon_folder.py` | daemon 的指令（`handle()`、save／load 檔）與控制資料夾（掃、回覆 `.done`） |
| `tests/` | unittest，見[下面](#測試tests) |

相依只往下：`aos_directives` ← `aos_cli` ← `aos_inst` ← `aos_ctl_state`／`aos_proc` ← `aos_loop` ← `aos_daemon_table` ← `aos_daemon_folder` ← `aos_daemon`。

## ctl 與 state 的慣例

搬到 [ctl-state.md](ctl-state.md)（NORMS N-11 的骨架「設定檔讀一次 → ctl 蓋過 → state 回報」，lib 照著做的慣例）。

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，53 個、約 12 秒。按受測的程式分五個檔（`test_cli.py`、`test_directives.py`、`test_inst.py`、`test_loop.py`、`test_daemon.py`），共用的暫存資料夾基底 `Tmp` 與路徑在 `helpers.py`；loop 與 daemon 都起真的行程、走檔案；每個測試用 mktemp 的暫存資料夾，跑完刪掉。改 lib 就跑一次，新行為補一個測試。

## 行程與執行緒的規矩

inst、loop、daemon 都是單執行緒（loop 多一條轉 stderr 的小執行緒），子程式一律用 `subprocess.Popen` 起，不用 `os.fork()`、不用 `preexec_fn`；cwd、環境變數經 `Popen(cwd=, env=)` 只給子程式，不 `chdir`、不改 `os.environ`。誰起子程序誰負責收：loop 把 aos_inst 起在新 session、daemon 把 loop 起在新 session，收的時候整群送訊號、收屍前整群補 SIGKILL（群組號碼不會先被拿走）。
