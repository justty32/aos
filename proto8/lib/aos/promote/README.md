# promote — 確認定義未被使用後換上副本，保留可退回的前版。

← [lib](../../README.md)｜退回工具 [rollback](../rollback/README.md)

stdin 收 `{"defs":"/abs/defs","target":"d","from":"/abs/candidates"}`；成功 stdout 收 `{"target":"d","promoted_at":"2026-11-07T10:41:00.000Z","prev":"/abs/defs/.prev/d/2026-11-07T10-41-00.000Z"}`。旗標與 JSON 同源，`--help` 可查。

先透過 PATH 上的 `aos-daemon-ctl --daemon D ls --json` 查各 daemon；任何非 `stopped` 的 proc，其 `def` 的 realpath 等於目標或在目標底下，都回 `DefBusy`，不動檔。`daemons` 未給時用 `$AOS_DAEMON`，環境也未設就不查；可給多個 daemon 或空陣列。

舊定義由 `os.rename` 移到 `<defs>/.prev/<target>/<時間>/`；新版先複製到 `<defs>/.prev/.tmp-<時間>/`，再 rename 到目標。中途出錯會搬回舊定義並清理暫存；若恢復本身也失敗，錯誤行會指出保留前版的位置。內部檔案的 symbolic link 原樣複製。

`target` 不收絕對路徑、空段、`.` 開頭的段、越出定義根的 symbolic link 或以 symbolic link 作為目標本身。`defs`、`from` 必須絕對；正式與候選定義都必須已是資料夾。時間精確到 UTC 毫秒，目錄名把 `:` 換 `-`；同毫秒已有歷史時往後取下一毫秒。

錯誤代號：`ArgumentsBad`、`PathBad`、`DefMissing`、`DefBusy`、`DaemonFailed`、`SwapFailed`。錯誤透過 `tool_io` 同時印 stderr 與 stdout，退 1；daemon 自己的 stderr 透出，失敗最後一行接到 `DaemonFailed` 原因。不同檔案系統、同時換同一份定義、換版期間新 proc 啟動、被強制中斷的復原不另處理。
