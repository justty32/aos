# proto4-1 — kernel 直接執行 `.aos/inst`（Python）

← [proto4](../proto4/README.md)（Janet：kernel 在進程內 eval inst；那條「資料夾模擬 lisp」的線留在那裡）

2026-09-08 開的。**參考 proto2、吸取教訓**，用 Python 快速做一版：每次 tick 一個資料夾＝cd 進去、執行 `./.aos/inst`。怎麼執行看那個資料夾的 `.aos/config.json`。這是 C++ 版 daemon／kernel 之前的行為原型。

## 檔案

- `aos_kernel.py`：`Kernel`（register／unregister／pause／resume／ls／step／run／stop）與 `exec_inst(dir, tick)`。命令列：`python3 aos_kernel.py DIR... [--steps N] [--interval SEC]`，DIR 寫法 `[名字=]資料夾[:間隔]`。
- `aos_daemon.py`：常駐進程裡一個 kernel，請求是 JSON 檔。`start|run|stop|ls`、`register DIR [NAME] [INTERVAL]`、`unregister|pause|resume NAME`、`req '{...}'`；home 走 `--home` 或 `AOS_DAEMON_DIR`。
- `test/`：`python3 -m unittest discover -s test`（21 條；daemon 測試真的開進程，家在 /tmp、跑完自己收）。`test/fx/` 是測試用資料夾。

## 執行 inst 的規則

有執行位、而且開頭是 `#!` 或 ELF → 直接執行 `./.aos/inst <tick> [args…]`；否則退回 `/bin/sh ./.aos/inst <tick> [args…]`（跟 shell 遇到 ENOEXEC 一樣，所以「一段 shell 文字沒 chmod」也能跑）。工作目錄＝那個資料夾。環境一律繼承，另給 `AOS_TICK`、`AOS_DIR`（絕對路徑）。

`.aos/config.json` 可以沒有、可以是 `{}`。**沒設的就默默吞掉**：

| 欄位 | 意思 | 沒設時 |
|---|---|---|
| `version` | 格式版本 | 1；不認識的版本＝錯誤、不跑 |
| `args` | 接在 tick 後面的參數 | `[]` |
| `env` | 額外環境變數 | 只有繼承的＋`AOS_*` |
| `stdin` | `"null"`／`"inherit"`／相對路徑 | `/dev/null` |
| `stdout` | `"null"`／`"inherit"`／相對路徑（append） | `/dev/null` |
| `stderr` | 同上，多一個 `"stdout"`＝併進 stdout | `/dev/null` |
| `exit` | `{"ok":[0], "pause":[], "unregister":[]}`：退出碼的意思；不在 ok 裡＝錯誤；pause／unregister 是 inst 叫 kernel 把自己暫停／註銷 | **任何退出碼都不算錯**，只記 code |
| `user` | 用誰跑；跟現在不同就走 `runuser`（要 root） | 不換 |
| `interval` | 資料夾自己宣告幾格跑一次 | 1；register 有給的優先 |
| `timeout` | 秒，超過就砍、算錯誤 | 不限 |

算錯誤（記在 proc 的 `error`、stderr 印一行、別人照跑）的只有：inst 不在、config 壞／版本不認識、跑不起來（含 runuser 失敗）、timeout、config 有設 `exit` 而退出碼不在 ok 裡。

## daemon 的家

`kernel.pid`、`state.json`（每格寫一次，`ls` 讀它，daemon 沒跑也讀得到）、`procs.json`（登記表，每格落一次，重開接回來）、`kernel.log`、`requests/`（請求檔 `<毫秒>-<pid>-<流水>.json`，處理完搬到 `requests/done/` 同名，多 `ok`／`result`）。

請求：`{"op":"register","dir":…,"name":…,"interval":…}`、`{"op":"unregister"|"pause"|"resume","name":…}`、`{"op":"ls"}`、`{"op":"steps"}`、`{"op":"stop"}`、`{"op":"set-interval","sec":N}`。

## 從 proto2 吸取的教訓（哪些做了）

- 一個進程一個 kernel，不再一個世界一個 `aos-loop`；暫停是 kernel 的旗子，不是 SIGSTOP。
- `start` 等到 pid 活著、第一格跑完才回「起來了」（proto2 教訓 26：要有就緒語意）。
- 登記表持久化在 `procs.json`，`stop` 不掉登記、重開接回來（教訓 28）；daemon 沒跑時丟的請求先放著，下次 start 撿走。
- inst 卡住有 `timeout`（教訓 06「tick 內卡住」）。
- 每個資料夾的輸出照自己的 config 走，不再混在一份 clock log（教訓 33）。
- SIGTERM 跑完這格乾淨收工、自己刪 pid 檔；`stop` 先請它自己收，不理才 TERM、再不理才 KILL；殭屍不算活著。
- 請求與狀態全是 JSON（不沿用 proto4 的 Janet 表達式）。

## 沒做／沒驗

`user` 只驗了「非 root 時走 runuser 會失敗、記錯誤不炸」的路徑（其實沒寫測試，沒有 root 可試）；關終端機的 SIGHUP 沒實測（`start_new_session=True` 理論上擋得住）；多個客戶端同時丟請求沒測。

```sh
cd proto4-1
python3 -m unittest discover -s test
export AOS_DAEMON_DIR=~/.aosd
python3 aos_daemon.py start --interval 1
python3 aos_daemon.py register test/fx/counter cnt
python3 aos_daemon.py ls
python3 aos_daemon.py pause cnt
python3 aos_daemon.py stop
```
