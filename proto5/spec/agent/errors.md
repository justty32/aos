← [agent](README.md)｜[spec 總導航](../README.md)

# 5. 錯誤代號

讀驗：`NotAnAgent`（沒有 `info.json` 或 `_type` 不對）、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、
`MetainfoInvalid`／`UnsupportedVersion`、`FieldTypeMismatch`、`StateInvalid`、`LlmInvalid`；
內容：`MessageInvalid`、`ToolInvalid`；指示詞的代號照 [directives.md §6](../directives/errors.md)。
收回時記憶長度或尾巴跟當批對不上＝`HistoryChanged`（aos-agent.md §7；它不偵測前綴被等長改寫）。
