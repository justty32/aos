# daemon 協議

← [共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

本篇原是單檔 `protocol/daemon.md`，2026-09-29 依主題拆成本資料夾；條號不變。各條所在檔案：

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-100 | 範圍 | [README.md](README.md) |
| P-101 | 啟動、設定與 socket | [startup-and-ipc.md](startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | [startup-and-ipc.md](startup-and-ipc.md) |
| P-103 | IPC 封包與授權 | [startup-and-ipc.md](startup-and-ipc.md) |
| P-104 | 註冊 | [registration.md](registration.md) |
| P-105 | 解除、叫醒、暫停與恢復 | [registration.md](registration.md) |
| P-106 | 查登記與最近一格 | [registration.md](registration.md) |
| P-107 | 佈建固定動作 | [provision-and-runner.md](provision-and-runner.md) |
| P-108 | daemon 與 helper 的私有通道 | [provision-and-runner.md](provision-and-runner.md) |
| P-109 | runner argv 與解析 | [provision-and-runner.md](provision-and-runner.md) |
| P-110 | runner 結束與 125 | [provision-and-runner.md](provision-and-runner.md) |
| P-111 | 錯誤 | [provision-and-runner.md](provision-and-runner.md) |
| P-112 | schema 與最小範例 | [provision-and-runner.md](provision-and-runner.md) |
| P-113 | 待決與跨篇 | [README.md](README.md) |
| P-114 | 前景 Ctrl-C 停機 | [shutdown.md](shutdown.md) |
| P-115 | 啟動 ID 與按需重建 | [registration.md](registration.md) |
| P-116 | 存檔與重開 | [shutdown.md](shutdown.md) |

## P-100．範圍〔使用者方向 2026-09-29〕

本篇定 daemon 的設定、IPC、helper 與 runner；責任與重啟行為見 [daemon 正本](../../daemon.md)，JSON 與錯誤見 [共用約定](../README.md)。

## P-113．待決與跨篇

見 [README P-008](../README.md#p-008)。
