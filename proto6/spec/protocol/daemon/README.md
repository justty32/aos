# daemon 協議

← [共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

本篇原是單檔 `protocol/daemon.md`，2026-09-29 依主題拆成本資料夾；條號不變。這是 daemon 協議唯一的條號表。各條所在檔案：

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

本篇只定 daemon 的設定欄位、IPC method 的 params／result、tick–daemon 通道的變數與 method（〔使用者方向 2026-09-30，第十九批〕P-117～119）、helper 私有通道、runner 回報與錯誤碼；行為一律以 [daemon 正本](../../daemon.md)（B-601～614）為正本，這裡寫到行為時只留一句加條號（[P-001](../README.md)）。JSON 與錯誤通則見 [共用約定](../README.md)。〔使用者方向 2026-09-30，第十八批〕

## P-113．待決與跨篇

見 [README P-008](../README.md#p-008)。
