# daemon 重讀設定模組

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜格式：[P-122](../protocol/daemon/reload.md)

程式：`lib/aos_daemon_reload.py`；測試：`tests/test_daemon_reload.py`。

## B-642：重讀設定模組

做什麼：設定檔寫了 `modules.reload`，送 SIGHUP 就重讀同一份設定檔、照新清單跑，不用重開。觸發只有 SIGHUP，不自己偵測、控制 socket 不收 reload。沒掛時 SIGHUP 照 Python 預設殺掉 daemon。

原則：

- 新鍵立刻跑；不見的鍵不再排、但正在跑的那次不殺；還在的鍵原地換新設定、暫停與已停照留。
- 頂層 `cwd`、`modules`、`exec_out_path`、`exec_err_path`、`lock_path` 改了**不套用**，stdout 印警告要重開。
- **設定壞了整份不套用、舊的照跑、daemon 不退出**：這是「默認一切正常」唯一的例外，因為不能為了一次手滑打掉跑得好好的 daemon。
- 重讀以記憶體為準，不拿狀態檔覆蓋；拿掉的項連信箱一起丟，框等最後一次清完才刪。
