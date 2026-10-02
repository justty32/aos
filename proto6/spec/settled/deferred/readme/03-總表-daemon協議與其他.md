← [暫緩區：之後再加的規定](../README.md)（分檔 3/3）｜所在段落：總表｜[上一份](02-總表-daemon與helper.md)

### daemon 協議

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| P-101 | 啟動、設定與 socket | 已被 P-120、P-121 取代 | 新設定檔見 [P-120](../../protocol/daemon/core.md)、控制 socket 見 [P-121](../../protocol/daemon/control.md)；舊 `daemon-config` schema 與 `config.*` 範例留作紀錄 | [protocol/daemon/startup-and-ipc.md](../protocol/daemon/startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | 部分取代、其餘暫緩 | sudo 開、另開 root 端、主程式降權、root 端讀到 EOF 就退出已被 [P-126](../../protocol/daemon/account.md) 取代；其餘暫緩 | 同上 |
| P-103 | IPC 封包與授權 | 部分取代、其餘暫緩 | 控制用的改成 P-121（一行 JSON、不驗身分）；舊封包、傳 fd、按帳號授權暫緩 | 同上 |
| P-104 | 註冊 | 暫緩 | daemon 不認得 node | [protocol/daemon/registration.md](../protocol/daemon/registration.md) |
| P-105 | 解除、叫醒、暫停、恢復與清除掛載診斷 | 部分取代、其餘暫緩 | 叫醒、暫停、恢復已被 P-121 取代；解除、清除診斷暫緩 | 同上 |
| P-106 | 查登記與最近一格 | 部分取代、其餘暫緩 | 查一項改成 P-121 的 `status`；`node.show`、`last_tick`、`node.ls` 暫緩 | 同上 |
| P-115 | 啟動 ID 與按需重建 | 暫緩 | 第一版不做 | 同上 |
| P-107～P-111 | 佈建、私有通道、runner、125、錯誤 | P-107、P-108 部分取代、其餘暫緩 | `spawn_as` 的請求與 daemon–root 端的私有通道已被 [P-126](../../protocol/daemon/account.md) 取代（一條 `SOCK_SEQPACKET` socketpair）；佈建動作、runner、125、錯誤碼暫緩 | [protocol/daemon/provision-and-runner.md](../protocol/daemon/provision-and-runner.md) |
| P-112 | schema 與最小範例 | 暫緩 | 七份舊 schema 與範例照留作紀錄 | 同上 |
| P-113 | 待決與跨篇 | 暫緩 | 跟整套舊協議一起暫緩 | [protocol/daemon/README.md](../protocol/daemon/README.md) |
| P-114 | 停機：訊號與設定 | 暫緩 | 第一版不做；停機見 P-120 | [protocol/daemon/shutdown.md](../protocol/daemon/shutdown.md) |
| P-116 | state.json 格式 | 部分取代、其餘暫緩 | 現行狀態檔是 [P-123](../../protocol/daemon/state.md)（只記暫停、已停；`modules.state` 用 `$ref` 指檔）；舊 `state.json` 的登記、wake、`clean_shutdown`、`cgroup_root_last` 暫緩 | 同上 |
| P-117 | 通道變數與憑證 | 部分取代、其餘暫緩 | `AOS_DAEMON_SOCKET` 這個名字沿用到 P-121（意思改成控制 socket），另加 `AOS_DAEMON_INST`；現行控制模組連得上就能用、不使用憑證；舊通道憑證 `AOS_TICK_TOKEN` 跟著通道暫緩，未來另定〔astra 報告必修 7〕；其餘暫緩 | [protocol/daemon/channel.md](../protocol/daemon/channel.md) |
| P-118、P-119 | 掛行程與砍掉；送訊息、取訊息 | P-119 部分取代、其餘暫緩 | 送訊息、取訊息的現行格式是 [P-125](../../protocol/daemon/mq.md)（`send`／`take`、一行 JSON）；P-119 的 `node.send`／`node.take`、通道錯誤碼與 P-118 第一版不做 | 同上 |

### 區外暫緩的段落

整理區以外也有跟著暫緩的段落，就地標了「暫緩」，沒有搬家：[驗收入口 V-03](../../../conformance.md) 裡跟上表各條有關的場景；`aos-config-add`（B-625 部分、P-207）的 [H-004 第 16 列](../../../cli/commands.md)、[A-102](../../../agent/configuration.md) 的鎖與提交流程、[C-07](../../../contracts.md) 裡「同 `aos-config-add`」一句（2026-10-01 第四批）；發摘要 `aos-publish`（B-624 部分、P-206 那列）的 [P-307](../../../protocol/messages.md) 發布檔與讀法、[kernel P-803、P-813](../../../protocol/kernel-tasks.md)與 [agent P-703](../../../protocol/agent-tasks.md)講「提交後發布 `published.json`」的句子、[驗收入口](../../../conformance.md)的相關場景（2026-10-01 第五批）。原本也在這裡的 [inst](../../../base/inst.md)「先決定身分，切完才解析」與頂層整份指示詞裡講 `user` 的部分，2026-10-01 隨 inst 頂層 `user` 撤回、直接刪掉（不搬暫緩，見 [tick.md 篇末](../tick/04-已撤回與被取代.md#已撤回被取代)）。

### 已知的設計問題（記錄，這輪不改）

- 〔astra 報告設計 1〕`aos-cg` 照舊 daemon 的規定收尾會連自己一起殺掉：監督程式先把自己搬進任務框，再要求殺空、等待、刪框；另外 [B-303](../helper.md) 推薦的 `aos-cg -- aos-as …` 已讓框內有人，[B-609](../daemon/helper-actions.md) 卻要求空框。astra 建議監督程式留框外、只讓子程序進框，helper 核對框的歸屬與允許的現有程序。daemon 那側本來就暫緩，等 cgroup 加回來時一起定（[B-605](../daemon/cgroup.md)、[B-634](../cg.md)）。
