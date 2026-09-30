# daemon 協議

← [整理區](../../README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../base/identity-resources.md)、[inst](../../../base/inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

daemon 協議只定格式：設定欄位、IPC method 的 params／result、通道、helper 私有通道、runner 回報與錯誤碼。行為寫在 [daemon 正本](../../daemon/README.md)。

這是 daemon 協議**唯一的條號表**。本篇原是單檔 `protocol/daemon.md`，2026-09-29 依主題拆成本資料夾，條號不變。

| 檔案 | 放什麼 |
|---|---|
| [startup-and-ipc.md](startup-and-ipc.md) | 啟動 argv、設定檔欄位、socket、helper 生死、IPC 封包與誰可呼叫 |
| [registration.md](registration.md) | 註冊、解除、叫醒、暫停、查登記、啟動 ID |
| [provision-and-runner.md](provision-and-runner.md) | 佈建動作、helper 私有通道、runner、錯誤碼、schema |
| [shutdown.md](shutdown.md) | 停機訊號、`state.json` 格式 |
| [channel.md](channel.md) | tick–daemon 通道：變數、憑證、掛行程、送取訊息 |

各條所在檔案：

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-100 | 範圍 | [README.md](README.md) |
| P-101 | 啟動、設定與 socket | [startup-and-ipc.md](startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | [startup-and-ipc.md](startup-and-ipc.md) |
| P-103 | IPC 封包與授權 | [startup-and-ipc.md](startup-and-ipc.md) |
| P-104 | 註冊 | [registration.md](registration.md) |
| P-105 | 解除、叫醒、暫停、恢復與清除掛載診斷 | [registration.md](registration.md) |
| P-106 | 查登記與最近一格 | [registration.md](registration.md) |
| P-107 | 佈建固定動作 | [provision-and-runner.md](provision-and-runner.md) |
| P-108 | daemon 與 helper 的私有通道 | [provision-and-runner.md](provision-and-runner.md) |
| P-109 | runner argv 與解析 | [provision-and-runner.md](provision-and-runner.md) |
| P-110 | runner 結束與 125 | [provision-and-runner.md](provision-and-runner.md) |
| P-111 | 錯誤 | [provision-and-runner.md](provision-and-runner.md) |
| P-112 | schema 與最小範例 | [provision-and-runner.md](provision-and-runner.md) |
| P-113 | 待決與跨篇 | [README.md](README.md) |
| P-114 | 停機：訊號與設定 | [shutdown.md](shutdown.md) |
| P-115 | 啟動 ID 與按需重建 | [registration.md](registration.md) |
| P-116 | state.json 格式 | [shutdown.md](shutdown.md) |
| P-117 | 通道變數與憑證 | [channel.md](channel.md) |
| P-118 | 掛行程與砍掉 | [channel.md](channel.md) |
| P-119 | 送訊息、取訊息與通道錯誤碼 | [channel.md](channel.md) |

## P-100．範圍〔使用者方向 2026-09-29〕

本篇只定格式：

- daemon 的設定欄位；
- IPC method 的 params／result；
- tick–daemon 通道的變數與 method（P-117～119）；
- helper 私有通道、runner 回報與錯誤碼。

行為一律以 [daemon 正本](../../daemon/README.md)（B-601～614）為準；這裡寫到行為時只留一句加條號（[P-001](../../../protocol/README.md)）。JSON 與錯誤通則見 [共用約定](../../../protocol/README.md)。

依據：使用者方向 2026-09-29；第十八批（協議篇只留格式）；第十九批（通道 P-117～119）。

## P-113．待決與跨篇

見 [README P-008](../../../protocol/README.md#p-008)。
