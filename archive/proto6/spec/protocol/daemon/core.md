# daemon 協議：aos-daemon 設定檔與輸出

← [daemon 協議](README.md)｜行為：[B-640](../../daemon/core.md)｜[慣例](../../conventions.md)

## P-120：aos-daemon 的 argv、設定檔、輸出與結束碼

```sh
aos-daemon --config <設定檔>     # 前景、不讀 stdin；-h／--help 印用法回 0
```

詳見 `aos-daemon --help` 或 `proto6/src/py/lib/aos_daemon*.py`。daemon 自己不讀 `AOS_*`（設定檔的 `$env` 例外）；它開的 `aos-exec` 繼承環境，另依掛的模組加變數（[P-121](control.md)、[P-125](mq.md)）。

### 設定檔

整份先經指示詞展開（`$ref`、`$fmt`、`$env`；`$ref` 相對檔名以設定檔所在資料夾為準），下面是**展開後**的樣子。schema：`proto6/spec/protocol/schemas/daemon-core-config.schema.json`。頂層 `cwd` 只是 `aos-exec` 子程序的工作目錄與相對路徑起點，daemon 不 chdir（對照 [C-11](../../conventions.md)）。

```json
{
  "cwd": "/home/u/nodes",
  "interval_ms": 60000,
  "stop_on_nonzero": false,
  "exec_out_path": "<inst>/out.log",
  "exec_err_path": "<inst>/err.log",
  "modules": {"control": {"socket": "./aos.sock"}},
  "insts": {
    "a": {},
    "jobs/report.json": {"interval_ms": 5000, "stop_on_nonzero": true}
  }
}
```

| 頂層欄位 | 型別 | 意思 |
|---|---|---|
| `insts` | 物件，必填 | 鍵＝inst 字面值（原樣交給 `aos-exec`）；值＝該項設定，`{}`＝全用預設。第幾項照鍵順序從 0 數 |
| `cwd` | 字串 | 起點；省＝daemon 啟動時的工作目錄 |
| `interval_ms` | 非負整數毫秒 | 各項預設週期；某項與頂層都沒有＝設定錯 |
| `stop_on_nonzero` | 布林 | 各項預設，省＝false |
| `exec_out_path`／`exec_err_path` | 字串 | `aos-exec` 的 stdout／stderr 接到的檔（接檔尾、父資料夾不在就建；`<inst>` 換成該項位置）；省＝丟掉；`/dev/stdout`、`/dev/stderr` 接回 daemon 自己的 |
| `exec_output_max_bytes` | 非負整數 | 每次每條串流最多留的 bytes，超過丟最早的；省＝1048576；只有頂層有效 |
| `lock_path` | 非空字串 | 鎖檔，相對以設定檔所在資料夾為準；省＝設定檔路徑加 `.lock` |
| `modules` | 物件 | 一個模組一個鍵，有寫就開：`control`（[P-121](control.md)）、`reload`（`{}`，[P-122](reload.md)）、`state`（原始必須是 `{"$ref":"<狀態檔>"}`，[P-123](state.md)）、`cgroup`（`{}`，[P-124](cgroup.md)）、`mq`（`{"<門名>":<路徑>,…}`，[P-125](mq.md)）、`account`（[P-126](account.md)）；其他鍵照收 |

| `insts.<inst>` 欄位 | 型別 | 意思 |
|---|---|---|
| `interval_ms`、`stop_on_nonzero` | 同上 | 蓋過頂層 |
| `cgroup` | 物件 | 該項的 cgroup 上限（[P-124](cgroup.md)） |
| `account` | 物件 | `{"user":"<帳號>"}`（[P-126](account.md)） |
| `mq` | 字串陣列 | 訂哪幾扇門，門名須在 `modules.mq`（[P-125](mq.md)） |

不認得的欄位一律忽略；其他型別錯不另外檢查，出事時自然丟錯回 1。範例在 `proto6/spec/protocol/examples/daemon/core-config.*.json`（`.valid`／`.invalid` 為驗證結果）。

### stdout

每行開頭是本地時間（ISO 8601、到秒、帶時區），空一格接內容。

| 什麼時候 | 內容 |
|---|---|
| 一次 `aos-exec` 結束 | `inst=<inst> exit=<碼> ms=<毫秒>`（被訊號 N 殺＝128+N） |
| 因 `stop_on_nonzero` 停掉 | `inst=<inst> stopped`（在該次 `exit` 行之後） |
| 暫停／恢復 | `inst=<inst> paused`／`resumed`（[P-121](control.md)） |
| 重讀設定 | 見 [P-122](reload.md) |
| 開起來恢復狀態 | `inst=<inst> paused`／`stopped`（[P-123](state.md)） |
| 開框／清殘留 | `inst=<inst> cgroup=i-<h>`／`reaped`（[P-124](cgroup.md)） |

```text
2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812
2026-10-01T15:04:05+08:00 inst=jobs/report.json exit=3 ms=23
2026-10-01T15:04:05+08:00 inst=jobs/report.json stopped
```

`aos-exec` 的輸出照 `exec_out_path`／`exec_err_path` 寫，有內容才寫，前面一行標頭（第幾項從 0 數；有丟 bytes 時尾端加 `dropped=<bytes>`）：

```text
== 2026-10-01T15:04:05+08:00 stdout index=1 inst=jobs/report.json ==
done 3 rows
== 2026-10-01T15:04:05+08:00 stderr index=1 inst=jobs/report.json ==
boom
```

### daemon 自己的 stderr 與結束碼

設定錯時印一行、回 1，不開始跑：

| 情況 | 那一行 |
|---|---|
| 設定檔讀不到、不是 JSON、指示詞錯 | `aos-daemon: config: <代號>: <說明>`（代號如 `ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferenceCycle`、`EnvironmentVariableMissing`） |
| 缺 `interval_ms`、`modules` 型別錯、`modules.state` 不是 `$ref`、`exec_output_max_bytes`／`lock_path`／`kill_grace_ms` 型別錯、訊息門或某項 `mq` 寫錯 | `aos-daemon: config: <說明>` |
| 鎖檔被別的 daemon 握著 | `aos-daemon: lock: another aos-daemon holds <鎖檔絕對路徑>` |

| 結束碼 | 什麼時候 |
|---|---|
| 0 | SIGINT／SIGTERM 正常停機；`--help` |
| 1 | 用法錯、設定錯、鎖檔被握、模組前提不符（cgroup 沒委派好、帳號模組沒用 root 開／設定錯／root 端不見），其他沒接住的錯（Python traceback） |
