← [inst-posix](README.md)｜[spec 總導航](../README.md)

# 5. 錯誤代號（讀／驗階段）

驗不過就是一個 `InstError`，`str(e)` 是「代號: 白話」。執行者原樣印一行到自己的 stderr，
退出碼 125（執行者自己失敗，那次**根本沒跑**，不寫 `exit` 檔）。

| 代號 | 什麼時候 |
|---|---|
| `ReadFailed` | inst.json 讀不到（指名的 `.json` 不存在也算） |
| `JsonSyntax` | 不是合法 JSON |
| `NotAnObject` | 頂層解完不是物件 |
| `MetainfoInvalid` | `_metainfo` 不是物件，或缺 `_type`／`_version`（裡面其他 key 忽略，不算多餘） |
| `UnsupportedInstType` | `_metainfo` 的 `_type` 不是字串 `"posix"` |
| `UnsupportedInstVersion` | `_metainfo`（posix）的 `_version` 不是整數 `1`（`true`／`false` 也不算） |
| `EmptyArgv` | 沒有 `argv`、解出來是空陣列、或 `argv[0]` 是空字串 |
| `FieldTypeMismatch` | 某個位置解完型別不對（頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs` 要物件） |
| `EnvKeyInvalid` | `envs` 的 key 空、或含 `=`（`$` 開頭不會走到這裡，實際代號是 `UnknownDirective`，見 4.1） |

指示詞機制的代號（`UnknownDirective`、`DirectiveValueTypeMismatch`、`FormatVariableInvalid`、
`UnknownOption`、`OptionConflict`、`EnvironmentVariableMissing`、`UnknownFormatVariable`、
`ReferenceReadFailed`／`ReferenceJsonInvalid`／`ReferencePointerInvalid`／`ReferenceCycle`）見
[directives.md](../directives/README.md) 第 6 節，本文不重複定義；本文只在 3.3／第 4 節訂了「這個位置
認不認得這個選項」之類的宿主規則，實際判定與報錯代號是機制層的事。
