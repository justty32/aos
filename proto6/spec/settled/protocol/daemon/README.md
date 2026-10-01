# daemon 協議

← [整理區](../../README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)｜[慣例](../../conventions.md)｜[暫緩區的舊協議](../../deferred/protocol/daemon/README.md)

daemon 協議只定格式：`aos-daemon` 的 argv、設定檔欄位、輸出與結束碼，控制模組的 socket 訊息、環境變數與 `aos-ctl`。行為寫在 [daemon 正本](../../daemon/README.md)。

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-100 | 範圍 | [README.md](README.md) |
| P-120 | aos-daemon 的 argv、設定檔、輸出與結束碼 | [core.md](core.md) |
| P-121 | 控制 socket、環境變數與 aos-ctl | [control.md](control.md) |

2026-10-01 之前的舊協議（P-101～119：舊設定檔、IPC 封包、登記與查詢 method、runner、helper 私有通道、停機與 `state.json`、tick–daemon 通道）第一版都不做，在[暫緩區](../../deferred/protocol/daemon/README.md)，條號保留、不重用。

## P-100．範圍〔使用者方向 2026-10-01〕

本篇只定格式：

- 核心 `aos-daemon`：argv、設定檔欄位（指示詞展開後的樣子）、stdout／stderr 的行格式、結束碼（P-120）；
- 控制模組：socket 上一行 JSON 的請求與回應、錯誤代碼、往下傳的環境變數、`aos-ctl` 的 argv、輸出與結束碼（P-121）。

行為一律以 [daemon 正本](../../daemon/README.md)（[B-640](../../daemon/core.md)、[B-641](../../daemon/control.md)）為準；這裡寫到行為時只留一句加條號（[P-001](../../../protocol/README.md)）。結束碼照 [C-08](../../conventions.md)，環境變數總表見 [C-10](../../conventions.md)。

依據：使用者方向 2026-10-01（最核心 daemon、控制模組）；原本的範圍（設定、IPC method、通道、helper 私有通道、runner）定於使用者方向 2026-09-29、第十八批、第十九批，隨舊協議搬到暫緩區。
