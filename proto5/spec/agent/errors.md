← [agent](README.md)｜[spec 總導航](../README.md)

# 5. 錯誤代號

讀驗：`NotAnAgent`（沒有 `info.json` 或 `_type` 不對）、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、
`MetainfoInvalid`／`UnsupportedVersion`、`FieldTypeMismatch`、`StateInvalid`、`LlmInvalid`；
內容：`MessageInvalid`、`ToolInvalid`；指示詞的代號照 [directives.md §6](../directives/errors.md)。
收回時記憶長度或尾巴跟當批對不上＝`HistoryChanged`（aos-agent.md §7；它不偵測前綴被等長改寫）。
（09-24 access-impl）`tools` 元素的 `$opt` 形狀錯＝`FieldTypeMismatch`／`UnknownOption`／`OptionConflict`，寫了不存在的原名或改名後撞名＝`ToolInvalid`（[§3.4](tools-opt.md)）。
（09-24 access-impl）權限牆（[§3.5](access.md)）：`access.json` 格式錯、路徑不在、指示詞解不過＝`AccessInvalid`（本身不是 JSON＝`JsonSyntax`，帶行列）；可寫 mount 碰到信任資料＝`AccessUnsafe`；要關牢卻找不到 bwrap＝`NoBwrap`；關牢的工具 `_meta` 用 `$env` 讀了敏感名字＝`EnvUnsafe`。這四個只讓當批的工具不執行（給模型的訊息只講被擋、請它轉告使用者跑 `aos-agent check`），不擋 tick。
