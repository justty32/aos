# rollback — 確認定義未被使用後換回最新前版，消耗該份歷史。

← [lib](../../README.md)｜換上工具 [promote](../promote/README.md)

stdin 收 `{"defs":"/abs/defs","target":"d"}`，成功 stdout 收 `{"target":"d","restored":"2026-11-07T10-41-00.000Z"}`。旗標與 JSON 同源，`--help` 可查。

與 promote 共用 `../promote/swap.py`：相同路徑限制、相同 `daemons` 參數與 `$AOS_DAEMON` 預設、同樣只透過 `aos-daemon-ctl ls --json` 查非 `stopped` 的 proc；正被使用即 `DefBusy`，檔案不動。

從 `<defs>/.prev/<target>/` 取符合 `YYYY-MM-DDTHH-MM-SS.sssZ` 格式、名稱最新的一份目錄，其他子目錄保留。現版先移到 `.prev/.tmp-<時間>/`，前版 rename 回目標後刪現版暫存；若搬前版失敗，先把現版搬回。成功後已用的時間目錄消失；`<target>` 歷史目錄空了就刪，較舊歷史保留。清理失敗回 `SwapFailed`，必要時在錯誤中指出保留的暫存。

沒有歷史回 `PrevMissing`；正式定義不在回 `DefMissing`。其他錯誤代號為 `ArgumentsBad`、`PathBad`、`DefBusy`、`DaemonFailed`、`SwapFailed`，格式與退出碼照 promote。此工具不把被退回的現版另存成新的歷史。

若時間格式目錄底下又有時間格式目錄，無法區分「時間型子定義的歷史」與「含時間型子目錄的前版」，會在搬移前回 `SwapFailed`、不動檔。這個命名空間需要圖紙另定辨識方式；目前不猜是哪一版。
