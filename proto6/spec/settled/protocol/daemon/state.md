# daemon 協議：記住狀態模組

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-643](../../daemon/state.md)｜[慣例](../../conventions.md)

本篇只有 P-123，只寫格式。什麼時候寫、怎麼讀回，以 [B-643](../../daemon/state.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十一批：daemon 模組」](../../../../notes/verdicts/11-tick-as-unit/13-1001-第十十一批.md#2026-10-01-第十一批daemon-模組)、[plan m3m 模組三](../../../../plan/m3m-daemon-modules.md#模組三記住狀態modulesstate)；現行程式 [記住狀態](../../../../src/py/README.md#重讀設定與記住狀態m3m)（有出入以程式為準）。

## P-123．記住狀態：設定與狀態檔〔使用者 2026-10-01 第十一批；格式照現行程式〕

### 設定（原始檔）

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡，**原始檔**必須這樣寫：

```json
{"modules": {"state": {"$ref": "aos-state.json"}}}
```

- `modules.state` 的原始值必須是**只有 `$ref` 一個鍵**的物件，值是非空字串、**不帶 `#` 位置**（也不准 `$at`）；它指的檔就是狀態檔。
- 相對檔名以設定檔所在資料夾為準（跟其他 `$ref` 一樣，[P-120](core.md)）。
- `modules` 本身也要直接寫在設定檔裡（不能整個 `modules` 是 `$ref` 引進來、裡面才有 `state`）。
- 不合上面規定：設定錯，stderr 一行 `aos-daemon: config: modules.state 要直接寫成 {"$ref": "<狀態檔>"}（不帶 # 位置）`、回 1。
- **狀態檔不在**：當成 `{"insts": {}}`，不算 `$ref` 讀不到。狀態檔在但不是 JSON：照一般 `$ref` 的錯（`ReferenceJsonInvalid`）、回 1（默認一切正常，不另外處理）。

### 展開後（＝狀態檔的內容）

展開後 `modules.state` 就是狀態檔的內容，[schema](../../../protocol/schemas/daemon-module-state.schema.json) 描述的也是這個樣子：

```json
{"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}
```

| 欄位 | 型別 | 意思 |
|---|---|---|
| `insts` | 物件，必填 | 鍵＝inst 字面值（跟設定檔 `insts` 的鍵逐字比對）；**只列不正常的項** |
| `insts.<inst>.paused` | `true`，可省 | 暫停中（[B-641](../../daemon/control.md)） |
| `insts.<inst>.stopped` | `true`，可省 | 被 `stop_on_nonzero` 停掉（[B-640](../../daemon/core.md)） |

- daemon 寫的檔：每項只寫是 true 的那幾個，不寫 `false`；兩個都不是 true 的項不列。一行 JSON 加換行，非 ASCII 照原樣。
- 讀的時候只看值是 `true` 的；不認得的欄位忽略（持久檔，[C-07](../../../contracts.md)），下一次寫檔時就不見了。
- 寫檔：同資料夾的暫檔 `.<檔名>.tmp` 寫完再改名蓋過去。

範例：[兩項](../../../protocol/examples/daemon/module-state.two.valid.json)、[空的](../../../protocol/examples/daemon/module-state.empty.valid.json)；反例：[寫了 `false`](../../../protocol/examples/daemon/module-state.false.invalid.json)、[缺 `insts`](../../../protocol/examples/daemon/module-state.no-insts.invalid.json)。設定檔掛 `reload` 與 `state`（展開後）：[core-config 範例](../../../protocol/examples/daemon/core-config.modules.valid.json)。

### stdout

開起來恢復時，在任何 `exit=` 行之前印跟平常同樣的行（[P-120](core.md)、[P-121](control.md)）：`inst=<inst 字面值> paused`、`inst=<inst 字面值> stopped`（兩個都有就先 paused 再 stopped）。

### 結束碼

不變（[P-120](core.md)）；`modules.state` 寫錯是設定錯、回 1。

依據：使用者 2026-10-01 第十一批（S1～S3 照建議；設定改成 `{"$ref": …}`）。
