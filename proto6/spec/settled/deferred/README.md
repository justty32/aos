# 暫緩區：之後再加的規定

← [整理區](../README.md)｜[慣例](../conventions.md)｜[通用 tick](../tick.md)｜[daemon](../daemon/README.md)

## 這是什麼

**這裡放「已經想好、但現在先不做」的規定。** 2026-10-01 使用者把 Python POC 定成「默認一切正常、先不考慮邊緣狀況」，又把 daemon 砍成只定期叫 `aos-exec` 的最核心版本。原本寫好的完整互斥、上下層判定、任務帳號檢查、落盤保證，以及整套舊 daemon（登記、runner、收尾、通道、熱重載、helper、cgroup、訊息）都還沒要做，但也不刪，就搬到這裡。

- **條號保留、不重用。** 以後加回來時沿用原號；新規定另開新號。
- **每條標題正下方有一行狀態**，三種之一：
  - **暫緩**：之後可能照原文（或改寫後）加回來。
  - **已被 X 取代**：同一件事新設計已經換了做法，原文只留作紀錄，不會照原樣回來。
  - **部分已被取代、其餘暫緩**：兩種混在一條裡，狀態行寫明哪部分被誰取代。
- **原文照 2026-09-30 的樣子留著。** 裡面的結束碼（75、2、整格回 1）、`node` 用語、「本篇是正本」之類的話都是舊設計當時的寫法；加回來時要照 [C-08](../conventions.md) 重定碼、照 [C-09](../conventions.md) 換狀態資料夾名。
- **部分暫緩的條**：原條還在正式篇，暫緩的那段在這裡用「暫緩：B-xxx …」當標題。

## 檔案

| 檔 | 內容 |
|---|---|
| [tick.md](tick.md) | B-628 上下層判定（整條）；B-602、B-620、B-633 的暫緩部分；篇末「已撤回／被取代」 |
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
| T-09 | 收尾、排空停機、熱重載、逃生口 | 暫緩 | 全是舊 daemon 用語，最核心 daemon 第一版不做 | [terms.md](terms.md) |

撤回、不會回來的 tick 舊做法（沒有 `.aos/` 時交給 aos-exec 的退路、inst.json 路徑正規化、`--node` 旗標、讀表驗四件事與表壞回 2、`methods` 欄、整格回 1／2／75 的碼表、`AOS_NODE_DIR`、`AOS_TICK_RECORD`）列在 [tick.md 篇末](tick.md#已撤回被取代)。

### daemon 與 helper

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| B-601 | 記憶體登記與按需執行 | 部分取代、其餘暫緩 | 照週期開跑改由 [B-640](../daemon/core.md) 叫 `aos-exec`；核心沒有 id；登記、IPC 授權、helper、runner 與收屍暫緩 | [daemon/runtime.md](daemon/runtime.md) |
| B-504 | 通知只是提示 | 暫緩 | 收件與急件叫醒屬之後的訊息模組；現在只照週期（B-640）或 `wake`（B-641）跑 | [daemon/runtime.md](daemon/runtime.md) |
| B-603 | 重啟先清空，再讓樹長回來 | 暫緩 | 第一版不做；daemon 重開什麼都不帶，暫停只在記憶體 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-604 | 收尾、停機、停用與退役 | 暫緩 | 第一版不做；停機改成 B-640 的「Ctrl-C 直接退出、回 0」 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-611 | 一棵資源樹只准一個 daemon | 暫緩 | 第一版不做 | [daemon/lifecycle.md](daemon/lifecycle.md) |
| B-606 | 登記、解除、換父與身分額度 | 暫緩 | daemon 不認得 node；清單改成設定檔 `insts`，核心沒有 id | [daemon/registration.md](daemon/registration.md) |
| B-607 | 叫醒、暫停、故障停格與格次序號 | 部分取代、其餘暫緩 | 定期、叫醒、暫停、恢復已被 B-640、[B-641](../daemon/control.md) 取代，查詢改成 `status`；故障停格（看擋板檔）與格次序號等之後的 node 模組 | [daemon/registration.md](daemon/registration.md) |
| B-610 | 掛載行程的診斷 | 暫緩 | 第一版不做 | [daemon/channel.md](daemon/channel.md) |
| B-612 | tick–daemon 通道 | 暫緩 | 第一版不做；控制模組的 socket 不是這條通道，沒有 `AOS_TICK_TOKEN` | [daemon/channel.md](daemon/channel.md) |
| B-613 | 掛行程與砍掉 | 暫緩 | 第一版不做 | [daemon/channel.md](daemon/channel.md) |
| B-615 | 部件形式與開關 | 已被 B-640 取代 | 改成設定檔頂層 `modules`：一個模組一個鍵、有寫就開；五個 `enable_*` 開關不做 | [daemon/components.md](daemon/components.md) |
| B-608 | 熱重載 | 暫緩 | 第一版不做；改設定就重開 daemon | [daemon/reload.md](daemon/reload.md) |
| B-609 | 佈建固定動作與 helper 動作 | 暫緩 | 第一版不做；helper 之後另成模組 | [daemon/helper-actions.md](daemon/helper-actions.md) |
| B-605 | cgroup：依賴與啟動自檢（含各條的 cgroup 部分） | 暫緩 | 第一版不做；cgroup 之後另成模組 | [daemon/cgroup.md](daemon/cgroup.md)、[daemon/runtime.md](daemon/runtime.md) |
| B-614 | 暫存訊息與急件 | 暫緩 | 訊息之後另成模組（`aos-mq`），不走控制 socket | [daemon/messaging.md](daemon/messaging.md) |
| B-303 | 可選 root helper 與解析分界（含 `aos-as`） | 暫緩 | 第一版不做；helper 之後另成模組 | [helper.md](helper.md) |
| （附錄） | systemd service 範例 | 暫緩 | 寫的是舊設定與舊停機流程 | [daemon/service.md](daemon/service.md) |

### daemon 協議

| 條號 | 標題 | 狀態 | 原因（或被誰取代） | 在哪 |
|---|---|---|---|---|
| P-101 | 啟動、設定與 socket | 已被 P-120、P-121 取代 | 新設定檔見 [P-120](../protocol/daemon/core.md)、控制 socket 見 [P-121](../protocol/daemon/control.md)；舊 `daemon-config` schema 與 `config.*` 範例留作紀錄 | [protocol/daemon/startup-and-ipc.md](protocol/daemon/startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | 暫緩 | 第一版不做 | 同上 |
| P-103 | IPC 封包與授權 | 部分取代、其餘暫緩 | 控制用的改成 P-121（一行 JSON、不驗身分）；舊封包、傳 fd、按帳號授權暫緩 | 同上 |
| P-104 | 註冊 | 暫緩 | daemon 不認得 node | [protocol/daemon/registration.md](protocol/daemon/registration.md) |
| P-105 | 解除、叫醒、暫停、恢復與清除掛載診斷 | 部分取代、其餘暫緩 | 叫醒、暫停、恢復已被 P-121 取代；解除、清除診斷暫緩 | 同上 |
| P-106 | 查登記與最近一格 | 部分取代、其餘暫緩 | 查一項改成 P-121 的 `status`；`node.show`、`last_tick`、`node.ls` 暫緩 | 同上 |
| P-115 | 啟動 ID 與按需重建 | 暫緩 | 第一版不做 | 同上 |
| P-107～P-111 | 佈建、私有通道、runner、125、錯誤 | 暫緩 | 第一版不做 | [protocol/daemon/provision-and-runner.md](protocol/daemon/provision-and-runner.md) |
| P-112 | schema 與最小範例 | 暫緩 | 七份舊 schema 與範例照留作紀錄 | 同上 |
| P-113 | 待決與跨篇 | 暫緩 | 跟整套舊協議一起暫緩 | [protocol/daemon/README.md](protocol/daemon/README.md) |
| P-114 | 停機：訊號與設定 | 暫緩 | 第一版不做；停機見 P-120 | [protocol/daemon/shutdown.md](protocol/daemon/shutdown.md) |
| P-116 | state.json 格式 | 暫緩 | daemon 不存狀態 | 同上 |
| P-117 | 通道變數與憑證 | 部分取代、其餘暫緩 | `AOS_DAEMON_SOCKET` 這個名字沿用到 P-121（意思改成控制 socket），另加 `AOS_DAEMON_INST`；憑證 `AOS_TICK_TOKEN` 被「連得上就能用」取代；其餘暫緩 | [protocol/daemon/channel.md](protocol/daemon/channel.md) |
| P-118、P-119 | 掛行程與砍掉；送訊息、取訊息 | 暫緩 | 第一版不做 | 同上 |

### 區外暫緩的段落

整理區以外也有跟著暫緩的段落，就地標了「暫緩」，沒有搬家：[inst](../../base/inst.md)「先決定身分，切完才解析」與頂層整份指示詞裡講 `user` 的部分；[驗收入口 V-03](../../conformance.md) 裡跟上表各條有關的場景。
