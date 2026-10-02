← [暫緩區：之後再加的規定](../README.md)（分檔 2/3）｜所在段落：總表｜[上一份](01-總表-tick與名詞.md)｜[下一份](03-總表-daemon協議與其他.md)

### daemon 與 helper

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| B-601 | 記憶體登記與按需執行 | 部分取代、其餘暫緩 | 照週期開跑改由 [B-640](../../daemon/core.md) 叫 `aos-exec`；核心沒有 id；登記、IPC 授權、helper、runner 與收屍暫緩 | [daemon/runtime.md](../daemon/runtime.md) |
| B-504 | 通知只是提示 | 暫緩 | 收件與急件叫醒屬之後的訊息模組；現在只照週期（B-640）或 `wake`（B-641）跑 | [daemon/runtime.md](../daemon/runtime.md) |
| B-603 | 重啟先清空，再讓樹長回來 | 部分取代、其餘暫緩 | 「存檔與讀回」「pause 批次存檔」的暫停部分已被 [B-643](../../daemon/state.md) 取代（記住狀態模組：暫停與已停每次變動當場寫、重開讀回）；重啟清空、登記讀回、未處理 wake、`clean_shutdown`、批次存檔、逐層重建暫緩 | [daemon/lifecycle.md](../daemon/lifecycle.md) |
| B-604 | 收尾、停機、停用與退役 | 暫緩 | 第一版不做；停機改成 B-640 的「Ctrl-C 直接退出、回 0」 | [daemon/lifecycle.md](../daemon/lifecycle.md) |
| B-611 | 一棵資源樹只准一個 daemon | 暫緩 | 第一版不做 | [daemon/lifecycle.md](../daemon/lifecycle.md) |
| B-606 | 登記、解除、換父與身分額度 | 暫緩 | daemon 不認得 node；清單改成設定檔 `insts`，核心沒有 id | [daemon/registration.md](../daemon/registration.md) |
| B-607 | 叫醒、暫停、故障停格與格次序號 | 部分取代、其餘暫緩 | 定期、叫醒、暫停、恢復已被 B-640、[B-641](../../daemon/control.md) 取代，查詢改成 `status`；故障停格（看擋板檔）與格次序號等之後的 node 模組 | [daemon/registration.md](../daemon/registration.md) |
| B-610 | 掛載行程的診斷 | 暫緩 | 第一版不做 | [daemon/channel.md](../daemon/channel.md) |
| B-612 | tick–daemon 通道 | 暫緩 | 第一版不做；控制模組的 socket 不是這條通道，沒有 `AOS_TICK_TOKEN` | [daemon/channel.md](../daemon/channel.md) |
| B-613 | 掛行程與砍掉 | 暫緩 | 第一版不做 | [daemon/channel.md](../daemon/channel.md) |
| B-615 | 部件形式與開關 | 已被 B-640 取代 | 改成設定檔頂層 `modules`：一個模組一個鍵、有寫就開；五個 `enable_*` 開關不做 | [daemon/components.md](../daemon/components.md) |
| B-608 | 熱重載 | 部分取代、其餘暫緩 | SIGHUP 重讀已被 [B-642](../../daemon/reload.md) 取代（重讀設定模組：加減項、改週期免重開，`cwd`／`modules` 改了印警告要重開，設定壞了舊的照跑）；roots、身分、helper、daemon 事項、排空中不重載等暫緩 | [daemon/reload.md](../daemon/reload.md) |
| B-609 | 佈建固定動作與 helper 動作 | 部分取代、其餘暫緩 | `spawn_as`（以指定帳號開程序）已被 [B-646](../../daemon/account.md) 帳號模組的 root 端取代；佈建動作、交框、交鎖、runner 暫緩 | [daemon/helper-actions.md](../daemon/helper-actions.md) |
| B-605 | cgroup：依賴與啟動自檢（含各條的 cgroup 部分） | 部分取代、其餘暫緩 | 「子樹根用 daemon 自己所在的 cgroup、根下開 `daemon` 子框、跑完 `cgroup.kill` 清框、寫上限」已被 [B-644](../../daemon/cgroup.md) 取代（收屍／cgroup 模組：框改成一項一個 `i-<h>`、上限寫在那一項的 `cgroup` 鍵、沒委派好的 cgroup 就回 1 不退回）；node 框與交框、`cgroup_root`／`--create-cgroup`、`cgroup=on/off`、委派偵測、逃生口、子樹鎖、`cgroup_root_last`、helper 的框動作暫緩 | [daemon/cgroup.md](../daemon/cgroup.md)、[daemon/runtime.md](../daemon/runtime.md) |
| B-614 | 暫存訊息與急件 | 部分取代、其餘暫緩 | 「daemon 暫存訊息、急件叫醒收件方」已被 [B-645](../../daemon/mq.md) 取代（訊息模組：收件人改成 daemon 的一項、信放記憶體、另開 socket 不走控制 socket）；node 收件人、寫權授權、通道憑證、急件越過上層節流暫緩 | [daemon/messaging.md](../daemon/messaging.md) |
| B-303 | 可選 root helper 與解析分界（含 `aos-as`） | 部分取代、其餘暫緩 | 「sudo 開時另開 root 端、主程式永久降權」已被 [B-646](../../daemon/account.md) 帳號模組取代（root 端只剩開程序、單位是 daemon 的一項、名單寫在 daemon 設定檔）；`aos-as`、身分額度、通道暫緩 | [helper.md](../helper.md) |
| （附錄） | systemd service 範例 | 暫緩 | 寫的是舊設定與舊停機流程 | [daemon/service.md](../daemon/service.md) |
