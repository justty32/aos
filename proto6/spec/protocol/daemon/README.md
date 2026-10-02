# daemon 協議

← [規格](../../../README.md)｜[共用約定](../../README.md)｜行為：[daemon](../../daemon/README.md)｜[慣例](../../conventions.md)｜[暫緩區的舊協議](../../deferred/protocol/daemon/README.md)

只定格式：設定檔欄位、socket 上的 JSON、環境變數、輸出行。行為看 [daemon 篇](../../daemon/README.md)與程式（`proto6/src/py/lib/aos_daemon*.py`、`aos_ctl.py`、`aos_mq.py`）；argv 與結束碼看各程式的 `--help` 或原始碼，本區只列簡表。schema 與範例是格式正本：`proto6/spec/protocol/schemas/`、`proto6/spec/protocol/examples/daemon/`。

| 條號 | 內容 | 檔 |
|---|---|---|
| P-100 | 範圍（本檔） | README.md |
| P-120 | aos-daemon 設定檔、輸出、結束碼 | [core.md](core.md) |
| P-121 | 控制 socket 與 aos-ctl | [control.md](control.md) |
| P-122 | 重讀設定 | [reload.md](reload.md) |
| P-123 | 記住狀態 | [state.md](state.md) |
| P-124 | 收屍／cgroup | [cgroup.md](cgroup.md) |
| P-125 | 訊息門與 aos-mq | [mq.md](mq.md) |
| P-126 | 帳號模組 | [account.md](account.md) |

舊協議（P-101～119）第一版不做，在[暫緩區](../../deferred/protocol/daemon/README.md)。

## P-100：範圍

- 結束碼照 [C-08](../../conventions.md)（只有 0 與 1，用法錯也是 1），環境變數總表 [C-10](../../conventions.md)。
- 各 socket 一律一條連線一問一答、一行 JSON（UTF-8、LF）、1 秒內送完、不驗身分；請求陌生欄位照收不理；回應 `{"ok":true,…}` 或 `{"ok":false,"error":"<代碼>","detail":"<字串>"}`。
- socket 檔開好後一律 chmod 666；誰能連由所在資料夾的擁有者／群組／權限決定（管理者先建好，daemon 不建、不改）。
- 請求與回應分開驗 schema。
