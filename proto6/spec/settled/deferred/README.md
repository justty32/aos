# 暫緩區：之後再加的規定

← [整理區](../README.md)｜[慣例](../conventions.md)｜[通用 tick](../tick.md)｜[daemon](../daemon/README.md)

## 這是什麼

**這裡放「已經想好、但現在先不做」的規定。** 2026-10-01 使用者把 Python POC 定成「默認一切正常、先不考慮邊緣狀況」，又把 daemon 砍成只定期叫 `aos-exec` 的最核心版本。原本寫好的完整互斥、上下層判定、任務帳號檢查、落盤保證，以及整套舊 daemon（登記、runner、收尾、通道、熱重載、helper、cgroup、訊息）都還沒要做，但也不刪，就搬到這裡。

- **條號保留、不重用。** 以後加回來時沿用原號；新規定另開新號。
- **每條標題正下方有一行狀態**，三種之一：
  - **暫緩**：之後可能照原文（或改寫後）加回來。
  - **已被 X 取代**：同一件事新設計已經換了做法，原文只留作紀錄，不會照原樣回來。
  - **部分已被取代、其餘暫緩**：兩種混在一條裡，狀態行寫明哪部分被誰取代。
- **原文照 2026-09-30 的樣子留著。** 裡面的結束碼（75、2、整格回 1）、`node` 用語（tick 層現在叫工作資料夾〔使用者 2026-10-01〕；講上下層的「上層 node／下層 node」照留）、「本篇是正本」之類的話都是舊設計當時的寫法；加回來時要照 [C-08](../conventions.md) 重定碼、照 [C-09](../conventions.md) 換狀態資料夾名。
- **部分暫緩的條**：原條還在正式篇，暫緩的那段在這裡用「暫緩：B-xxx …」當標題。

## 檔案

| 檔 | 內容 |
|---|---|
| [tick.md](tick.md) | B-628 上下層判定（整條）；B-602、B-620、B-624、B-625、B-633 的暫緩部分；篇末「已撤回／被取代」 |
| [protocol/tick.md](protocol/tick.md) | tick 協議先不做的條：P-207 `aos-config-add` 的格式；P-206 的 `aos-publish` 那列 |
| [terms.md](terms.md) | T-09 收尾、排空停機、熱重載、逃生口（舊 daemon 用語） |
| [helper.md](helper.md) | B-303 可選 root helper 與 `aos-as` |
| [daemon/](daemon/README.md) | 舊 daemon 設計各條（B-504、B-601、B-603～615）與 systemd 範例 |
| [protocol/daemon/](protocol/daemon/README.md) | 舊 daemon 協議 P-101～119（P-100 除外，改寫後留在正式篇） |

## 總表

日期都是 2026-10-01。

### tick 與名詞

| 條號 | 標題 | 狀態 | 原因 | 在哪 |
|---|---|---|---|---|
| B-628 | 上下層判定：預設看資料夾包含、可登記覆蓋 | 暫緩 | 使用者：「也不需要判斷上下層」；之後由 node 模組照資料夾包含關係算 | [tick.md](tick.md) |
| B-602（部分） | 完整互斥的其餘細節 | 暫緩 | 最簡鎖已做（拿不到回 0、鎖 fd 不傳給任務）；鎖 fd 交給任務核對、後代握鎖擋下一格、回 75 先不做 | [tick.md](tick.md) |
| B-620（部分） | 任務的帳號（125） | 暫緩 | 使用者：「帳號不對，也不管」；核心不看 `user` | [tick.md](tick.md) |
| B-633（部分） | 落盤、寫不進與讀不懂 | 暫緩 | 使用者：默認紀錄是好的、`--firstdo-fsync` 先不做 | [tick.md](tick.md) |
| B-625（部分） | 加入普通設定（`aos-config-add`） | 暫緩 | 使用者 2026-10-01 第四批裁定搬暫緩區：09-29 規劃、從沒寫過程式；改 `config/` 就自己改。當機恢復、重要設定手改、恢復前驗證仍在 [tick/recovery.md](../tick/recovery.md) | [tick.md](tick.md) |
| P-207 | 加入普通設定（`aos-config-add` 的 argv 與結束碼） | 暫緩 | 同 B-625（部分） | [protocol/tick.md](protocol/tick.md) |
| B-624（部分） | 發布摘要（`aos-publish`） | 暫緩 | 使用者 2026-10-01 第五批：「aos-publish我覺得要改名，我預期它的作用，就是把這一格的一些狀況總結成json檔案寫好」，討論後「那看來aos-summarize其實是暫時不需要了，拿掉。」之後若要，方向是「把這一格的狀況總結成 JSON」，名字不用 publish（會跟傳訊混）。`aos-mq post` 仍在 [tick/mq.md](../tick/mq.md) | [tick.md](tick.md) |
| P-206（部分） | `aos-publish` 那列 | 暫緩 | 同 B-624（部分） | [protocol/tick.md](protocol/tick.md) |
| P-212 | `aos-as`：切換帳號 | 暫緩 | 使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」現行切帳號只在 daemon 設定檔做（帳號模組） | [protocol/tick.md](protocol/tick.md) |
| T-09 | 收尾、排空停機、熱重載、逃生口 | 暫緩 | 全是舊 daemon 用語，最核心 daemon 第一版不做 | [terms.md](terms.md) |

撤回、不會回來的 tick 舊做法（沒有 `.aos/` 時交給 aos-exec 的退路、inst.json 路徑正規化、`--node` 旗標、讀表驗四件事與表壞回 2、`methods` 欄、整格回 1／2／75 的碼表、`AOS_NODE_DIR`、`AOS_TICK_RECORD`、`aos-tick` 目標給檔就拿它當任務表，以及 2026-10-01 撤回的 inst 頂層與任務表的 `user`、inst「先決定身分，切完才解析」整節）列在 [tick.md 篇末](tick.md#已撤回被取代)。

### daemon 與 helper

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| B-601 | 記憶體登記與按需執行 | 部分取代、其餘暫緩 | 照週期開跑改由 [B-640](../daemon/core.md) 叫 `aos-exec`；核心沒有 id；登記、IPC 授權、helper、runner 與收屍暫緩 | [daemon/runtime.md](daemon/runtime.md) |
| B-504 | 通知只是提示 | 暫緩 | 收件與急件叫醒屬之後的訊息模組；現在只照週期（B-640）或 `wake`（B-641）跑 | [daemon/runtime.md](daemon/runtime.md) |
| B-603 | 重啟先清空，再讓樹長回來 | 部分取代、其餘暫緩 | 「存檔與讀回」「pause 批次存檔」的暫停部分已被 [B-643](../daemon/state.md) 取代（記住狀態模組：暫停與已停每次變動當場寫、重開讀回）；重啟清空、登記讀回、未處理 wake、`clean_shutdown`、批次存檔、逐層重建暫緩 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-604 | 收尾、停機、停用與退役 | 暫緩 | 第一版不做；停機改成 B-640 的「Ctrl-C 直接退出、回 0」 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-611 | 一棵資源樹只准一個 daemon | 暫緩 | 第一版不做 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-606 | 登記、解除、換父與身分額度 | 暫緩 | daemon 不認得 node；清單改成設定檔 `insts`，核心沒有 id | [daemon/registration.md](daemon/registration.md) |
| B-607 | 叫醒、暫停、故障停格與格次序號 | 部分取代、其餘暫緩 | 定期、叫醒、暫停、恢復已被 B-640、[B-641](../daemon/control.md) 取代，查詢改成 `status`；故障停格（看擋板檔）與格次序號等之後的 node 模組 | [daemon/registration.md](daemon/registration.md) |
| B-610 | 掛載行程的診斷 | 暫緩 | 第一版不做 | [daemon/channel.md](daemon/channel.md) |
| B-612 | tick–daemon 通道 | 暫緩 | 第一版不做；控制模組的 socket 不是這條通道，沒有 `AOS_TICK_TOKEN` | [daemon/channel.md](daemon/channel.md) |
| B-613 | 掛行程與砍掉 | 暫緩 | 第一版不做 | [daemon/channel.md](daemon/channel.md) |
| B-615 | 部件形式與開關 | 已被 B-640 取代 | 改成設定檔頂層 `modules`：一個模組一個鍵、有寫就開；五個 `enable_*` 開關不做 | [daemon/components.md](daemon/components.md) |
| B-608 | 熱重載 | 部分取代、其餘暫緩 | SIGHUP 重讀已被 [B-642](../daemon/reload.md) 取代（重讀設定模組：加減項、改週期免重開，`cwd`／`modules` 改了印警告要重開，設定壞了舊的照跑）；roots、身分、helper、daemon 事項、排空中不重載等暫緩 | [daemon/reload.md](daemon/reload.md) |
| B-609 | 佈建固定動作與 helper 動作 | 部分取代、其餘暫緩 | `spawn_as`（以指定帳號開程序）已被 [B-646](../daemon/account.md) 帳號模組的 root 端取代；佈建動作、交框、交鎖、runner 暫緩 | [daemon/helper-actions.md](daemon/helper-actions.md) |
| B-605 | cgroup：依賴與啟動自檢（含各條的 cgroup 部分） | 部分取代、其餘暫緩 | 「子樹根用 daemon 自己所在的 cgroup、根下開 `daemon` 子框、跑完 `cgroup.kill` 清框、寫上限」已被 [B-644](../daemon/cgroup.md) 取代（收屍／cgroup 模組：框改成一項一個 `i-<h>`、上限寫在那一項的 `cgroup` 鍵、沒委派好的 cgroup 就回 1 不退回）；node 框與交框、`cgroup_root`／`--create-cgroup`、`cgroup=on/off`、委派偵測、逃生口、子樹鎖、`cgroup_root_last`、helper 的框動作暫緩 | [daemon/cgroup.md](daemon/cgroup.md)、[daemon/runtime.md](daemon/runtime.md) |
| B-614 | 暫存訊息與急件 | 部分取代、其餘暫緩 | 「daemon 暫存訊息、急件叫醒收件方」已被 [B-645](../daemon/mq.md) 取代（訊息模組：收件人改成 daemon 的一項、信放記憶體、另開 socket 不走控制 socket）；node 收件人、寫權授權、通道憑證、急件越過上層節流暫緩 | [daemon/messaging.md](daemon/messaging.md) |
| B-303 | 可選 root helper 與解析分界（含 `aos-as`） | 部分取代、其餘暫緩 | 「sudo 開時另開 root 端、主程式永久降權」已被 [B-646](../daemon/account.md) 帳號模組取代（root 端只剩開程序、單位是 daemon 的一項、名單寫在 daemon 設定檔）；`aos-as`、身分額度、通道暫緩 | [helper.md](helper.md) |
| （附錄） | systemd service 範例 | 暫緩 | 寫的是舊設定與舊停機流程 | [daemon/service.md](daemon/service.md) |

### daemon 協議

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| P-101 | 啟動、設定與 socket | 已被 P-120、P-121 取代 | 新設定檔見 [P-120](../protocol/daemon/core.md)、控制 socket 見 [P-121](../protocol/daemon/control.md)；舊 `daemon-config` schema 與 `config.*` 範例留作紀錄 | [protocol/daemon/startup-and-ipc.md](protocol/daemon/startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | 部分取代、其餘暫緩 | sudo 開、另開 root 端、主程式降權、root 端讀到 EOF 就退出已被 [P-126](../protocol/daemon/account.md) 取代；其餘暫緩 | 同上 |
| P-103 | IPC 封包與授權 | 部分取代、其餘暫緩 | 控制用的改成 P-121（一行 JSON、不驗身分）；舊封包、傳 fd、按帳號授權暫緩 | 同上 |
| P-104 | 註冊 | 暫緩 | daemon 不認得 node | [protocol/daemon/registration.md](protocol/daemon/registration.md) |
| P-105 | 解除、叫醒、暫停、恢復與清除掛載診斷 | 部分取代、其餘暫緩 | 叫醒、暫停、恢復已被 P-121 取代；解除、清除診斷暫緩 | 同上 |
| P-106 | 查登記與最近一格 | 部分取代、其餘暫緩 | 查一項改成 P-121 的 `status`；`node.show`、`last_tick`、`node.ls` 暫緩 | 同上 |
| P-115 | 啟動 ID 與按需重建 | 暫緩 | 第一版不做 | 同上 |
| P-107～P-111 | 佈建、私有通道、runner、125、錯誤 | P-107、P-108 部分取代、其餘暫緩 | `spawn_as` 的請求與 daemon–root 端的私有通道已被 [P-126](../protocol/daemon/account.md) 取代（一條 `SOCK_SEQPACKET` socketpair）；佈建動作、runner、125、錯誤碼暫緩 | [protocol/daemon/provision-and-runner.md](protocol/daemon/provision-and-runner.md) |
| P-112 | schema 與最小範例 | 暫緩 | 七份舊 schema 與範例照留作紀錄 | 同上 |
| P-113 | 待決與跨篇 | 暫緩 | 跟整套舊協議一起暫緩 | [protocol/daemon/README.md](protocol/daemon/README.md) |
| P-114 | 停機：訊號與設定 | 暫緩 | 第一版不做；停機見 P-120 | [protocol/daemon/shutdown.md](protocol/daemon/shutdown.md) |
| P-116 | state.json 格式 | 部分取代、其餘暫緩 | 現行狀態檔是 [P-123](../protocol/daemon/state.md)（只記暫停、已停；`modules.state` 用 `$ref` 指檔）；舊 `state.json` 的登記、wake、`clean_shutdown`、`cgroup_root_last` 暫緩 | 同上 |
| P-117 | 通道變數與憑證 | 部分取代、其餘暫緩 | `AOS_DAEMON_SOCKET` 這個名字沿用到 P-121（意思改成控制 socket），另加 `AOS_DAEMON_INST`；現行控制模組連得上就能用、不使用憑證；舊通道憑證 `AOS_TICK_TOKEN` 跟著通道暫緩，未來另定〔astra 報告必修 7〕；其餘暫緩 | [protocol/daemon/channel.md](protocol/daemon/channel.md) |
| P-118、P-119 | 掛行程與砍掉；送訊息、取訊息 | P-119 部分取代、其餘暫緩 | 送訊息、取訊息的現行格式是 [P-125](../protocol/daemon/mq.md)（`send`／`take`、一行 JSON）；P-119 的 `node.send`／`node.take`、通道錯誤碼與 P-118 第一版不做 | 同上 |

### 區外暫緩的段落

整理區以外也有跟著暫緩的段落，就地標了「暫緩」，沒有搬家：[驗收入口 V-03](../../conformance.md) 裡跟上表各條有關的場景；`aos-config-add`（B-625 部分、P-207）的 [H-004 第 16 列](../../cli/commands.md)、[A-102](../../agent/configuration.md) 的鎖與提交流程、[C-07](../../contracts.md) 裡「同 `aos-config-add`」一句（2026-10-01 第四批）；發摘要 `aos-publish`（B-624 部分、P-206 那列）的 [P-307](../../protocol/messages.md) 發布檔與讀法、[kernel P-803、P-813](../../protocol/kernel-tasks.md)與 [agent P-703](../../protocol/agent-tasks.md)講「提交後發布 `published.json`」的句子、[驗收入口](../../conformance.md)的相關場景（2026-10-01 第五批）。原本也在這裡的 [inst](../../base/inst.md)「先決定身分，切完才解析」與頂層整份指示詞裡講 `user` 的部分，2026-10-01 隨 inst 頂層 `user` 撤回、直接刪掉（不搬暫緩，見 [tick.md 篇末](tick.md#已撤回被取代)）。

### 已知的設計問題（記錄，這輪不改）

- 〔astra 報告設計 1〕`aos-cg` 照舊 daemon 的規定收尾會連自己一起殺掉：監督程式先把自己搬進任務框，再要求殺空、等待、刪框；另外 [B-303](helper.md) 推薦的 `aos-cg -- aos-as …` 已讓框內有人，[B-609](daemon/helper-actions.md) 卻要求空框。astra 建議監督程式留框外、只讓子程序進框，helper 核對框的歸屬與允許的現有程序。daemon 那側本來就暫緩，等 cgroup 加回來時一起定（[B-605](daemon/cgroup.md)、[B-634](../tick/cg.md)）。
