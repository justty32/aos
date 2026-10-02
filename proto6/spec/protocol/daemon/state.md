# daemon 協議：記住狀態模組

← [daemon 協議](README.md)｜行為：[B-643](../../daemon/state.md)｜[慣例](../../conventions.md)

## P-123：記住狀態：設定與狀態檔

schema：`proto6/spec/protocol/schemas/daemon-module-state.schema.json`；範例：`examples/daemon/module-state.*`。程式：`aos_daemon_state.py`。

**設定（原始檔）**：`modules.state` 必須是只有 `$ref` 一個鍵的物件，值是非空字串、不帶 `#`、不准 `$at`；`modules` 本身要直接寫在設定檔裡。相對檔名以設定檔所在資料夾為準。

```json
{"modules": {"state": {"$ref": "aos-state.json"}}}
```

不合＝設定錯，`aos-daemon: config: modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）`、回 1。狀態檔不在＝當 `{"insts": {}}`；在但不是 JSON＝一般 `$ref` 錯（`ReferenceJsonInvalid`）、回 1。

**狀態檔內容**（展開後 `modules.state` 就是它）：

```json
{"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `insts` | 物件，必填 | 鍵＝inst 字面值；只列不正常的項 |
| `insts.<inst>.paused` | `true`，可省 | 暫停中 |
| `insts.<inst>.stopped` | `true`，可省 | 被 `stop_on_nonzero` 停掉 |

只寫 true 的欄位、不寫 `false`；讀時只看 `true`、陌生欄位忽略（下次寫檔就不見）。寫檔：同資料夾暫檔 `.<檔名>.tmp` 寫完改名蓋過。

**stdout**：開起來恢復時，在任何 `exit=` 行之前印 `inst=<inst> paused`、`inst=<inst> stopped`（兩者都有先 paused）。結束碼不變，`modules.state` 寫錯＝設定錯回 1。
