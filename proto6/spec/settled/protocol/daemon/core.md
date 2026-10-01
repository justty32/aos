# daemon 協議：aos-daemon 的 argv、設定檔與輸出

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-640](../../daemon/core.md)｜[慣例](../../conventions.md)

本篇只有 P-120，只寫格式。daemon 做什麼（週期、起點、停不停、停機）以 [B-640](../../daemon/core.md) 為正本。

依據：[第二十批篇末「2026-10-01：最核心 daemon」](../../../../notes/verdicts/11-tick-as-unit.md#2026-10-01最核心-daemon待統一更新-spec)、[plan m3](../../../../plan/m3-daemon-core.md)；現行程式 [aos-daemon](../../../../src/py/README.md#aos-daemon第三段最核心-daemon)（有出入以程式為準）。

## P-120．aos-daemon 的 argv、設定檔、輸出與結束碼〔使用者方向 2026-10-01；欄位名照現行程式〕

### argv

```sh
aos-daemon --config <設定檔>
```

- `--config` 必填，只收一個設定檔。前景執行，不讀 stdin。
- 多給參數、沒給 `--config` 算用法錯。`-h`／`--help` 印用法、回 0。
- daemon 叫的是跟自己放在同一個 `bin/` 裡的 `aos-exec`，不照 `PATH` 找。
- daemon 自己不讀 `AOS_*` 環境變數（設定檔裡寫 `$env` 指示詞時例外，那是展開時讀的）。它開的 `aos-exec` 繼承 daemon 的環境；掛了控制模組時另加兩個變數（[P-121](control.md)）。

### 設定檔

JSON 檔。**整份先經 aos 指示詞展開**（`$ref`、`$fmt`、`$env`，跟 inst 同一套；`$ref` 的相對檔名以設定檔所在資料夾為準），展開完才照下表讀。所以原始檔裡任何位置都可以是指示詞；下表與 [schema](../../../protocol/schemas/daemon-core-config.schema.json) 描述的是**展開後**的樣子。兩種起點的差別見 [B-640](../../daemon/core.md)。

〔使用者 2026-10-01〕跟 tasks.json 頂層預設的對照（對照表正本見 [C-11](../../conventions.md)）：頂層 `cwd` **不改 daemon 自己的工作目錄**（daemon 不 chdir，只把它當 `aos-exec` 子程序的工作目錄）；相對路徑（`cwd`、inst 字面值、`exec_out_path`、`exec_err_path`、`socket`）以 daemon 啟動時的工作目錄（或 `cwd`）為起點；指示詞是**整份先展開**，不像 tasks.json 只展開到 `tasks` 那層。

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

**頂層**

| 欄位 | 型別 | 意思 |
|---|---|---|
| `insts` | 物件，必填 | 鍵＝inst 字面值（原樣交給 `aos-exec`）；值＝這一項的設定物件（下表），`{}`＝全用頂層預設。第幾項照鍵的順序從 0 數 |
| `cwd` | 字串，可省 | 起點，只用作 `aos-exec` 子程序的工作目錄與相對路徑的起點，不改 daemon 自己的工作目錄。省略＝daemon 啟動時的工作目錄；相對的也以那裡為準 |
| `interval_ms` | 非負整數毫秒，可省 | 各項的預設週期 |
| `stop_on_nonzero` | 布林，可省 | 各項的預設；省略＝false |
| `exec_out_path` | 字串，可省 | `aos-exec` 的 stdout 接到哪個檔（接在檔尾、父資料夾不在就建）。相對以起點為準；`<inst>` 這幾個字換成這一項的位置（規則見 [B-640](../../daemon/core.md)「輸出」）。省略＝丟掉（`/dev/null`）；寫 `/dev/stdout` 接回 daemon 自己的 stdout |
| `exec_err_path` | 字串，可省 | `aos-exec` 的 stderr 接到哪個檔，規則同 `exec_out_path`。省略＝丟掉（`/dev/null`）；寫 `/dev/stderr` 接回 daemon 自己的 stderr |
| `modules` | 物件，可省 | 一個模組一個鍵，有寫就開。目前認 `control`（`{"socket": <路徑>}`，見 [P-121](control.md)）、`reload`（`{}`，見 [P-122](reload.md)）、`state`（原始檔必須是 `{"$ref": "<狀態檔>"}`，展開後是狀態檔內容，見 [P-123](state.md)）；其他鍵照收、不看 |

**`insts` 每一項的值**

| 欄位 | 型別 | 意思 |
|---|---|---|
| `interval_ms` | 非負整數毫秒，可省 | 蓋過頂層 |
| `stop_on_nonzero` | 布林，可省 | 蓋過頂層 |

- 不認得的欄位（頂層、每一項、`modules` 裡）一律忽略（持久檔，[C-07](../../../contracts.md)）。daemon 不另外印出不認得的欄位。
- **某一項自己沒寫、頂層也沒寫 `interval_ms`＝設定錯**。〔astra 報告設計 3〕schema 用條件規則表達（頂層沒有 `interval_ms` 時，`insts` 每一項都必填），直接拿 schema 驗的工具也擋得到；程式自己的檢查照留（錯誤訊息見下面「daemon 自己的 stderr」）。
- 其他型別錯（例如 `insts` 不是物件、某一項的值不是物件、`control` 缺 `socket`）照「POC 默認一切正常」不另外檢查，出事時程式自然丟錯、回 1。
- 舊設計的設定檔（`version`、`socket_path`、`roots`……，`daemon-config.schema.json`）屬[暫緩區 P-101](../../deferred/protocol/daemon/startup-and-ipc.md)，跟這份不相容。

範例：[最小](../../../protocol/examples/daemon/core-config.minimal.valid.json)、[每項蓋過頂層、掛控制模組、帶不認得的模組鍵](../../../protocol/examples/daemon/core-config.full.valid.json)；反例：[`insts` 寫成陣列（舊寫法）](../../../protocol/examples/daemon/core-config.insts-array.invalid.json)、[頂層與那一項都沒有 `interval_ms`](../../../protocol/examples/daemon/core-config.no-interval.invalid.json)、[只有一項且是 `{}`、頂層沒有 `interval_ms`](../../../protocol/examples/daemon/core-config.inst-no-interval.invalid.json)〔astra 報告設計 3〕、[`control` 缺 `socket`](../../../protocol/examples/daemon/core-config.control-no-socket.invalid.json)。〔2026-10-01 第十一批〕掛 `reload` 與 `state`（展開後）：[範例](../../../protocol/examples/daemon/core-config.modules.valid.json)；反例 [`state` 不是狀態檔內容（例如寫成 `path`）](../../../protocol/examples/daemon/core-config.state-not-expanded.invalid.json)。

### stdout

每行開頭是印出那一刻的**本地時間**，ISO 8601、到秒、帶時區（例如 `2026-10-01T15:04:05+08:00`），空一格接內容：

| 什麼時候 | 內容 |
|---|---|
| 一次 `aos-exec` 結束 | `inst=<inst 字面值> exit=<碼> ms=<毫秒>`；被訊號 N 殺掉時 `<碼>` 是 128+N |
| 這一項因 `stop_on_nonzero` 停掉 | `inst=<inst 字面值> stopped`：在該次 `exit` 行之後另印一行，中間可能穿插其他項的行〔astra 報告必修 8〕 |
| 控制模組收到 `pause`／`resume` | `inst=<inst 字面值> paused`、`inst=<inst 字面值> resumed`（[P-121](control.md)） |
| 重讀設定（SIGHUP） | `reload: need restart: cwd`／`modules`、`inst=<inst 字面值> removed`／`added`、`reloaded`（[P-122](reload.md)） |
| 記住狀態：開起來恢復 | `inst=<inst 字面值> paused`、`inst=<inst 字面值> stopped`，在任何 `exit=` 行之前（[P-123](state.md)） |

```text
2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812
2026-10-01T15:04:05+08:00 inst=jobs/report.json exit=3 ms=23
2026-10-01T15:04:05+08:00 inst=jobs/report.json stopped
```

`aos-exec` 自己的 stdout 不在這裡；它照 `exec_out_path` 寫（下一節），沒寫就丟掉。

### aos-exec 的 stdout 與 stderr

〔使用者方向 2026-10-01〕各自寫到 `exec_out_path`、`exec_err_path` 指的檔；沒寫就丟掉。每次收齊、有內容才寫，前面一行標頭，時間後面寫 `stdout` 或 `stderr`，第幾項從 0 數；內容最後沒有換行就補一個：

```text
== 2026-10-01T15:04:05+08:00 stdout index=1 inst=jobs/report.json ==
done 3 rows
== 2026-10-01T15:04:05+08:00 stderr index=1 inst=jobs/report.json ==
boom
```

同一次兩條都有內容時，先寫 stdout 那段再寫 stderr 那段，中間不夾別項的輸出。寫到一般檔或 `/dev/stdout`、`/dev/stderr`，格式都一樣。

### daemon 自己的 stderr

設定錯時印一行、回 1，daemon 不開始跑：

| 情況 | 那一行 |
|---|---|
| 設定檔讀不到、不是 JSON、指示詞錯 | `aos-daemon: config: <代號>: <說明>`；代號照指示詞的錯誤代號，例如 `ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferenceCycle`、`ReferencePointerInvalid`、`EnvironmentVariableMissing` |
| 某一項與頂層都沒有 `interval_ms`；`modules` 不是物件；`modules.state` 不是 `$ref`（[P-123](state.md)） | `aos-daemon: config: <說明>`（沒有代號） |
| 用法錯 | argparse 的用法說明加一行 `aos-daemon: error: <說明>` |

其他沒接住的錯照 Python 預設印 traceback。

### 結束碼

照 [C-08](../../conventions.md)：

| 碼 | 什麼時候 |
|---|---|
| 0 | 收到 SIGINT／SIGTERM 退出（正常停機）；`-h`／`--help` |
| 1 | 用法錯、設定錯、設定檔讀不到、指示詞錯、其他沒接住的錯 |

daemon 正常運作時不會自己結束（所有項都停了也照樣開著），所以 0 只會來自訊號。

依據：使用者方向 2026-10-01（設定檔追加裁定、m3 待問裁定、m3 實作後追加裁定、`insts` 改成物件、`exec_out_path` 與輸出預設丟掉）；結束碼慣例改版。
