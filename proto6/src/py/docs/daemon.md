# proto6/src/py — aos-daemon

← [proto6/src/py README](../README.md)｜上一份：[hooks 與 tasks-blocked](hooks.md)｜下一份：[控制模組與 aos-ctl](ctl.md)

## aos-daemon（第三段最核心 daemon）

照 [plan 第三段 m3](../../../plan/m3-daemon-core.md) 寫的，新寫。就是「一個叫 `aos-exec` 的 cron」：讀設定檔裡的 inst 清單，每項照自己的週期叫一次同一個 `bin/` 裡的 `aos-exec <inst 字面值>`，等它結束、stdout 印一行。沒有 socket、登記、收屍；daemon 不認得 node（node 就是一份 `argv` 寫 `aos-tick` 的 inst）。核心也沒有「id」這個概念（使用者 2026-10-01）：一項就是它的 `inst` 字面值，印出來也是 `inst=…`。

```sh
proto6/src/py/bin/aos-daemon --config daemon.json     # Ctrl-C／SIGTERM 直接退出、回 0，不殺正在跑的子程序
```

設定檔：

```json
{
  "cwd": "/home/u/nodes",
  "interval_ms": 60000,
  "stop_on_nonzero": false,
  "exec_out_path": "<inst>/out.log",
  "exec_err_path": "<inst>/err.log",
  "insts": {
    "a": {},
    "jobs/report.json": {"interval_ms": 5000, "stop_on_nonzero": true}
  }
}
```

| 鍵 | 意思 |
|---|---|
| `insts` | 物件（使用者 2026-10-01 改；陣列寫法撤掉、不相容）。**鍵＝inst 字面值**，**原樣**當 aos-exec 的參數（資料夾或檔都行），印出來也照字面；**值＝該項設定**（`interval_ms`、`stop_on_nonzero` 蓋過頂層；`{}`＝全用頂層預設）。第幾項照鍵的順序（JSON 讀入保序）從 0 數；同一個鍵寫兩次時 JSON 讀入只留後面那個 |
| `cwd`（頂層） | 起點：aos-exec 子程序的工作目錄、相對路徑的基準。沒寫＝daemon 啟動時的工作目錄；相對的也以它為準 |
| `interval_ms` | 上一次結束後隔多久再叫（剛開時每項先立刻跑一次）。頂層是預設、每項可蓋過；兩邊都沒有＝設定錯、回 1 |
| `stop_on_nonzero` | 碼不是 0 時這一項就不再叫、多印一行 `stopped`。頂層是預設、每項可蓋過；都沒有＝`false`。所有項都停了 daemon 照樣開著 |
| `exec_out_path`（頂層） | aos-exec 的 stdout 接到哪個檔（接在檔尾、父資料夾不在就建）。相對以起點為準；`<inst>` 換成 inst 字面值，inst 是檔時換成它字面上的 dirname（空的用 `.`）。~~沒寫＝daemon 自己的 stdout~~ 沒寫＝丟掉（`/dev/null`，使用者 2026-10-01）；寫 `/dev/stdout` 接回 daemon 的 stdout |
| `exec_err_path`（頂層） | aos-exec 的 stderr 接到哪個檔，規則同 `exec_out_path`。~~沒寫＝daemon 自己的 stderr~~ 沒寫＝丟掉（`/dev/null`，使用者 2026-10-01）；寫 `/dev/stderr` 接回 daemon 的 stderr |
| `modules`（頂層） | 可選，要是物件（不是＝設定錯、回 1）。一個模組一個鍵；目前只有 `control`（[控制模組](ctl.md#控制模組與-aos-ctlm3n)，有寫就開），其他鍵照收、不看 |

**整份設定檔先經 aos 指示詞展開再讀**（使用者 2026-10-01；跟 inst 同一套 `lib/aos_directives.py`，`$ref`／`$fmt`／`$env`）。順序與兩種起點：

1. **先展開**：整份從根一路走進物件與陣列，每一格解到底。`$ref` 的相對檔名**一律以設定檔所在的資料夾**為準（`os.path.abspath`，不解符號連結；被引進來的檔裡再 `$ref` 也照這個資料夾，中心路徑不換）。`$opt` 物件原樣留著、不走進去（核心沒有吃選項的位置，留給模組）。引到自己的祖先＝`ReferenceCycle`。
2. **展開完才讀鍵**：頂層 `cwd`（可以是 `$ref` 引進來的值）照上表的規則算起點——**相對的 `cwd` 以 daemon 啟動時的工作目錄為準，不是設定檔的資料夾**；`inst` 值、`exec_out_path`、`exec_err_path` 再以起點為準。

所以同一份設定檔裡，`$ref` 的檔名跟 `inst`／`cwd` 的值起點不同：前者看設定檔放哪，後者看 daemon 從哪開（或 `cwd`）。例：設定檔在 `conf/daemon.json`、daemon 從 `/w` 開：

```json
{"interval_ms": {"$ref": "defaults.json#/interval_ms"}, "insts": {"$ref": "list.json"}}
```

讀的是 `conf/defaults.json`、`conf/list.json`；`list.json` 裡寫 `{"x.json": {}}` 跑的是 `/w/x.json`。指示詞錯（讀不到、循環、位置找不到…）stderr 一行 `aos-daemon: config: <代號>: …`、回 1。

stdout 每次一行（時間是印出那刻的本地時間，ISO 8601 帶時區）：

```text
2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812
2026-10-01T15:04:05+08:00 inst=jobs/report.json exit=3 ms=23
2026-10-01T15:04:05+08:00 inst=jobs/report.json stopped
```

aos-exec 的 stdout、stderr（使用者 2026-10-01：兩條都由頂層鍵決定、沒寫就丟到 `/dev/null`，不再接到 daemon 自己的 stdout／stderr；沒寫的那條直接開成 `DEVNULL`、不經 pipe）：有寫路徑的那條每次收齊（`communicate()`，讀到 pipe 底）再一次寫出，有內容才寫，前面一律加一行標頭（時間、`stdout`／`stderr`、第幾項＝`insts` 鍵的順序從 0 起、inst 字面值；寫到 `<inst>` 個別檔也加，使用者 2026-10-01 同意）；同一次兩條都有就先 stdout 段再 stderr 段，跟 daemon 自己那一行共用一把鎖，多項同時結束也不交錯：

```text
== 2026-10-01T15:04:05+08:00 stdout index=1 inst=jobs/report.json ==
done 3 rows
== 2026-10-01T15:04:05+08:00 stderr index=1 inst=jobs/report.json ==
boom
```

inst 裡任務自己的 stdout／stderr 照 inst 規則（預設 `/dev/null`，寫 `{"$opt": "inherit"}` 才會跟著 aos-exec 進來）。被訊號殺的碼印成 `128+N`。結束碼：用法錯（沒給 `--config`、多給參數）、設定錯、設定檔讀不到、指示詞錯都 1；SIGINT／SIGTERM 0。daemon 退出後還在跑的 aos-exec 再寫有設路徑的那條（pipe）會吃 SIGPIPE，照默認一切正常不處理（使用者 2026-10-01 同意）；沒設的那條是 `/dev/null`，不會。

| 函式（`lib/aos_daemon.py`，名字都從這裡 re-export） | 實作在 | plan 步驟 |
|---|---|---|
| `main()`、`_Parser` | `aos_daemon.py` | 1 讀設定檔（先展開指示詞） |
| `read_config()`、`expand()`、`load_config()`、`err_path_for()`（與 `Item`、`Setup`、`load_full()`） | `aos_daemon_config.py` | 1 讀設定檔（先展開指示詞） |
| `run_once()` | `aos_daemon_run.py` | 2 叫一次、印一行 |
| `write_outputs()`、`_block()`、`say()`、`now()`（與 `drain()`、`clock()`） | `aos_daemon_output.py` | 2 叫一次、印一行 |
| `loop()` | `aos_daemon_run.py` | 3 週期、4 非 0 停不停 |
| `_quit()` | `aos_daemon.py` | 5 Ctrl-C 與 SIGTERM |

`aos_daemon.py` 超過 300 行後照職責拆成母模組＋四個子模組（不改行為）：母模組留執行期的共用狀態（`_items`、`_items_lock`、`_cg`、`_acct`、`_state`、socket 路徑、鎖檔 fd）與 `main()`；`aos_daemon_config`（設定檔、`Item`、`Setup`）、`aos_daemon_output`（stdout 一行、收與寫 aos-exec 輸出）、`aos_daemon_run`（每一項的迴圈、`state_changed()`、`give_env()`）、`aos_daemon_kill`（kill／restart 送訊號，第十九批）。`main()` 會換掉的 `_cg`／`_acct`／`_state` 留在母模組，子模組呼叫時才去 `aos_daemon` 讀，所以 `aos_daemon_reload` 等讀的 `aos_daemon._cg` 照舊有效。

測試 `tests/test_daemon_config.py`（步驟 1、2）、`test_daemon_run.py`（步驟 3～6）（原 `test_daemon.py`，共用 `_daemon_util.py`）：`Step1Config`～`Step6Tick`，一個類別一步（步驟 1 另有 `Step1Directives`：指示詞與 `modules`），兩檔合計約 6 秒。
