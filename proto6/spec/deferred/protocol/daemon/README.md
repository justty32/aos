# 暫緩區：舊 daemon 協議

← [暫緩區](../../README.md)｜[舊 daemon 行為](../../daemon/README.md)｜[現行 daemon 協議](../../../protocol/daemon/README.md)｜[共用約定](../../../protocol/README.md)

> **這個資料夾整個在暫緩區**（2026-10-01）。這裡是 2026-10-01 之前設計的完整 daemon 協議：舊設定檔、IPC 封包與 method、runner、helper 私有通道、停機與 `state.json`、tick–daemon 通道。daemon 改成只叫 `aos-exec`、不認得 node，最核心 daemon 第一版不做這些（使用者 2026-10-01）。現行的格式見 [P-120](../../../protocol/daemon/core.md)（`aos-daemon`）與 [P-121](../../../protocol/daemon/control.md)（控制模組）。條號保留、不重用；每條標題下有一行狀態。

舊協議只定格式：設定欄位、IPC method 的 params／result、通道、helper 私有通道、runner 回報與錯誤碼。行為寫在[舊 daemon 正本](../../daemon/README.md)。

| 檔案 | 放什麼 |
|---|---|
| [startup-and-ipc.md](startup-and-ipc.md) | 啟動 argv、設定檔欄位、socket、helper 生死、IPC 封包與誰可呼叫 |
| [registration.md](registration.md) | 註冊、解除、叫醒、暫停、查登記、啟動 ID |
| [provision-and-runner.md](provision-and-runner.md) | 佈建動作、helper 私有通道、runner、錯誤碼、schema |
| [shutdown.md](shutdown.md) | 停機訊號、`state.json` 格式 |
| [channel.md](channel.md) | tick–daemon 通道：變數、憑證、掛行程、送取訊息 |

各條所在檔案與狀態：

| 條號 | 標題 | 檔案 | 狀態 |
|---|---|---|---|
| P-101 | 啟動、設定與 socket | [startup-and-ipc.md](startup-and-ipc.md) | 已被 P-120、P-121 取代 |
| P-102 | sudo 與 helper 生死 | [startup-and-ipc.md](startup-and-ipc.md) | 暫緩 |
| P-103 | IPC 封包與授權 | [startup-and-ipc.md](startup-and-ipc.md) | 部分被 P-121 取代、其餘暫緩 |
| P-104 | 註冊 | [registration.md](registration.md) | 暫緩 |
| P-105 | 解除、叫醒、暫停、恢復與清除掛載診斷 | [registration.md](registration.md) | 部分被 P-121 取代、其餘暫緩 |
| P-106 | 查登記與最近一格 | [registration.md](registration.md) | 部分被 P-121 取代、其餘暫緩 |
| P-107 | 佈建固定動作 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-108 | daemon 與 helper 的私有通道 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-109 | runner argv 與解析 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-110 | runner 結束與 125 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-111 | 錯誤 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-112 | schema 與最小範例 | [provision-and-runner.md](provision-and-runner.md) | 暫緩 |
| P-113 | 待決與跨篇 | [README.md](README.md) | 暫緩 |
| P-114 | 停機：訊號與設定 | [shutdown.md](shutdown.md) | 暫緩 |
| P-115 | 啟動 ID 與按需重建 | [registration.md](registration.md) | 暫緩 |
| P-116 | state.json 格式 | [shutdown.md](shutdown.md) | 部分已被 [P-123](../../../protocol/daemon/state.md) 取代，其餘暫緩 |
| P-117 | 通道變數與憑證 | [channel.md](channel.md) | 部分被 P-121 取代、其餘暫緩 |
| P-118 | 掛行程與砍掉 | [channel.md](channel.md) | 暫緩 |
| P-119 | 送訊息、取訊息與通道錯誤碼 | [channel.md](channel.md) | 暫緩 |

舊協議的 schema 與範例留在原處、不刪不改：`daemon-config`、`daemon-rpc`、`daemon-registration`、`daemon-state`、`daemon-runner-report`、`daemon-provision`、`daemon-helper`、`daemon-launch-error`（[schemas](../../../../notes/archive/spec-2026-10-02/protocol/schemas/)），範例在 [examples/daemon](../../../protocol/examples/daemon/) 裡 `core-config.*`、`ctl_*` 以外的檔。

## P-113．待決與跨篇

> **暫緩**（2026-10-01）：隨整份舊協議暫緩；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。原本在 `protocol/daemon/README.md`，2026-10-01 搬來。

見 [README P-008](../../../../notes/archive/spec-2026-10-02/protocol/readme/03-P-007-P-008-schema與待決.md#p-008)。
