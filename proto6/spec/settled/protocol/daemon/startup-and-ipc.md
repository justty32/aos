# daemon 協議：啟動、設定與 IPC

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../base/identity-resources.md)、[inst](../../../base/inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

## P-101．啟動、設定與 socket〔建議預設，未拍板〕

### 指令與輸入輸出

完整 argv：`aos daemon --config /absolute/daemon.json [--create-cgroup] [--firstdo-fsync]`。前景執行，stdin 不讀。兩個旗標都只在啟動時讀，改了要重開（[B-608](../../daemon/reload.md)）。

- `--create-cgroup` 等於設定的 `create_cgroup: true`，兩處任一開著就算開（[B-605](../../daemon/cgroup.md)）。
- `--firstdo-fsync`〔使用者方向 2026-09-30，修正輪暫定的裁定；使用者原話 `aos-daemon --firstdo-fsync`〕：開了就在它開的每一格環境放 `AOS_TICK_FIRSTDO_FSYNC=1`，讓那一格開格時 fsync（[B-633](../../tick.md)、[B-601](../../daemon/runtime.md)）。

| 介面 | 內容 |
|---|---|
| stdout | 啟動時印 `helper_pid=<PID>`（沒 helper 印 `none`）；node 問題的警告；熱重載每次一行 `reload applied=<欄位,…> restart_required=<欄位,…>`（沒有就留空）；設定有不認得的欄位時一行 `config_unknown_fields=<欄位,…>`（[C-07](../../../contracts.md)）；啟動時一行 `cgroup=on` 或 `cgroup=off`（`off` 時 stderr 另印一次警告），不印 git 的偵測行（[B-605](../../daemon/cgroup.md)） |
| stderr | 只印 daemon 自身原因造成的錯誤 |
| 讀 | 設定檔；登記 inst 的原始 bytes（讀不到怎麼辦見 [B-601](../../daemon/runtime.md)） |
| 寫 | socket；`state_dir` 下的恢復檔與鎖；node 的 `.aos/attention/`；P-110 的掛載行程未啟動旁檔 |
| 環境 | 不作授權。daemon 只替它開的程序放兩個通道變數（[P-117](channel.md)），帶了 `--firstdo-fsync` 時另放 `AOS_TICK_FIRSTDO_FSYNC=1`；自己不讀 `AOS_*` |
| 訊號 | SIGINT／SIGTERM 停機（P-114、[B-604](../../daemon/lifecycle.md)）；SIGHUP 熱重載（[B-608](../../daemon/reload.md)）；其他訊號由父程序看 wait 狀態 |

依據：第十八批（熱重載輸出行、SIGHUP）；第十九批（通道變數）；第二十批（撤第十九批的 `standard: cgroup=full|fallback` 偵測行）；納入 cgroup 與 git 改寫計畫（`cgroup=on|off`）。

### 結束碼

| 碼 | 意思 |
|---|---|
| `0` | 正常停機 |
| `2` | 用法或設定錯，還沒開始做事。開了 `create_cgroup`（設定或 `--create-cgroup` 任一處）卻缺 `cgroup_root` 也算這種（第十七批） |
| `125` | daemon 自己失敗：最低需求不合（缺 cgroup 不算，第十九批）、取不到排他鎖、初始化、清空或運行中失敗；明寫的 `cgroup_root`（或開了 `create_cgroup`）卻準備不好、或取不到它的 cgroup 子樹鎖（[B-605](../../daemon/cgroup.md)、[B-611](../../daemon/lifecycle.md)）；stderr 說明 |

啟動自檢見 [B-605](../../daemon/cgroup.md)，排他鎖見 [B-611](../../daemon/lifecycle.md)。

### 設定檔欄位

[設定 schema](../../../protocol/schemas/daemon-config.schema.json)：持久檔，不認得的欄位忽略（[C-07](../../../contracts.md)）。哪些欄位能熱重載、哪些要重開，見 [B-608](../../daemon/reload.md) 的表。

哪些計時用毫秒、哪些用格數，見 [daemon 篇「時間」](../../daemon/README.md)（astra 審整理區裁定裁-2）。

| 欄位 | 意思 |
|---|---|
| `version` | 必填，1 |
| `common_user` | 可省；非空帳號名稱或非負 UID。預設見 P-102 |
| `socket_path` | 必填；正規化絕對檔案路徑，例如 `/run/user/1000/aos/daemon.sock`，多 UID 部署可用 `/run/aos/daemon.sock` |
| `state_dir` | 必填；daemon 可寫的絕對目錄，存 `state.json`、自身 `attention/` 與 PID 提示檔 |
| `pause_save_interval_ms` | 可省，正整數，預設 1000；pause 批次存檔間隔（[B-603](../../daemon/lifecycle.md)） |
| `shutdown_grace_ms` | 可省，非負毫秒，預設 2000；收尾時第一次 SIGTERM 到第二次 SIGTERM（runner 清空）的寬限；有 cgroup 時之後再 `cgroup.kill` 兜底（[B-604](../../daemon/lifecycle.md)） |
| `stop_mode`〔第十八批〕 | 可省，`"immediate"`（預設）或 `"drain"`；SIGINT／SIGTERM 走哪種停機（B-604） |
| `drain_timeout_ms`〔第十八批〕 | 可省，正整數毫秒，預設 600000；排空停機最多等多久。跟 `shutdown_grace_ms` 是兩個值 |
| `kill_escape_cgroups`〔第十八批 Q19；納入 cgroup 與 git 疑-7〕 | 可省，布林，預設 false；true＝daemon 重啟與解除登記時，連 node 自開的子框（逃生口）一起收尾（[B-605](../../daemon/cgroup.md)）。沒有 cgroup 時沒作用 |
| `mount_diag_max`〔第十八批；第十九批改名，原 `once_diag_max`〕 | 可省，非負整數，預設 1024；掛載行程的診斷最多留幾筆，0＝不留（[B-610](../../daemon/channel.md)） |
| `mount_diag_ttl_ticks`〔第十八批；第十九批改名；astra 審整理區裁-2 改成格數，取代 `mount_diag_ttl_ms`〕 | 可省，正整數，預設 1000；掛載行程的診斷結束後，掛它的上層再開幾格就淘汰（[B-610](../../daemon/channel.md)）。舊設定寫的 `mount_diag_ttl_ms` 照 [C-07](../../../contracts.md) 忽略 |
| `cgroup_root` | 可省；已準備好（或要 daemon 自己建）的 cgroup v2 子樹絕對路徑。明寫了卻準備不好就回 125。省略就自動偵測：daemon 所在的單位經 systemd 確認 `Delegate=yes` 才用它，否則照沒有 cgroup 做。「準備好」、偵測與子層搬移見 [B-605](../../daemon/cgroup.md) |
| `create_cgroup` | 可省，布林，預設 false；true＝子樹不在時 daemon 自己建（同 `--create-cgroup`），此時 `cgroup_root` 必填（B-605） |
| `disable` | 可省，不重複字串陣列，目前只認 `quota`；強制關掉啟動時偵測到的可選功能（B-605） |
| `roots` | 必填，頂層登記陣列；每項見下面「頂層項」，`node_id` 不可重複 |

範例：[最小設定](../../../protocol/examples/daemon/config.minimal.valid.json)、[開了 create_cgroup 的設定](../../../protocol/examples/daemon/config.create-cgroup.valid.json)、[使用者委派（省略 cgroup_root）](../../../protocol/examples/daemon/config.user-delegate.valid.json)、[反例：開了卻沒寫 cgroup_root](../../../protocol/examples/daemon/config.create-cgroup-no-root.invalid.json)、[反例：版本 2](../../../protocol/examples/daemon/config.version.invalid.json)、〔第十八批〕[前綴與範圍額度、排空與新欄位，另帶一個不認得的欄位仍收](../../../protocol/examples/daemon/config.grant-prefix.valid.json)、[反例：範圍涵蓋系統帳號](../../../protocol/examples/daemon/config.grant-range-system.invalid.json)、[反例：空前綴](../../../protocol/examples/daemon/config.grant-prefix-empty.invalid.json)。

### 部件與核心開關欄位

〔建議預設，未拍板〕下列都是設定檔頂層的可省布林值，省略為 true；型別錯回 2。行為與重開規則以 [B-615](../../daemon/components.md) 為正本。

| 欄位 | 對應行為 |
|---|---|
| `enable_messaging` | [B-614 訊息部件](../../daemon/messaging.md) |
| `enable_cgroup` | [B-605 cgroup 部件](../../daemon/cgroup.md) |
| `enable_reload` | [B-608 熱重載](../../daemon/reload.md) |
| `enable_drain` | [B-604 排空停機](../../daemon/lifecycle.md) |
| `enable_helper_actions` | [B-609 helper 動作](../../daemon/helper-actions.md) |

依據：[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)（同程式、設定檔開關）；欄位細節未拍板。本輪只改 Markdown；現有設定 schema 與範例尚未加入這五鍵的型別定義，不能拿它們通過當成已驗過新開關。

### 頂層項

| 欄位 | 意思 |
|---|---|
| `node_id` | 必填 |
| `identity_grant` | 必填，身分額度（下面） |
| `interval_ms` | 可省，正整數；一格的標準長度，外部規定、保留毫秒（[B-607](../../daemon/registration.md)） |
| `provision` | 可省，佈建權（下面） |

頂層項沒有 `parent_id`：上層固定 null（[B-606](../../daemon/registration.md)）。inst 怎麼找、base 在哪，照 [inst](../../../base/inst.md)；找不到時回什麼見 [B-606](../../daemon/registration.md)。

### 身分額度 `identity_grant`

非空、不重複的陣列，每項是下列之一。意思、排除規則與包含判定見 [B-606](../../daemon/registration.md)。

| 形狀 | 例 |
|---|---|
| 帳號名稱字串（非空、不是 `root`） | `"aos-alice"` |
| UID 整數（不是 0） | `1001` |
| 〔第十八批〕前綴 `{"prefix":<非空字串>}` | `{"prefix":"aos-"}` |
| 〔第十八批〕範圍 `{"uid_min":N,"uid_max":M}`，N ≥ 1000，N ≤ M | `{"uid_min":20000,"uid_max":29999}` |

`uid_min ≤ uid_max` schema 表達不了，由程式核對。

### 佈建權 `provision`

可省，省略＝沒有佈建權。形狀 `{"actions":[…],"paths":[…],"groups":[…]}`：

| 欄位 | 意思 |
|---|---|
| `actions` | 必填、不重複；只認 [P-107](provision-and-runner.md) 表上除了 `spawn_as` 以外的九種動作（`spawn_as` 看身分額度，不進這裡） |
| `paths` | 必填、不重複；可佈建的絕對目錄範圍，空陣列＝不授任何路徑。`cgroup_root` 不算一般可寫路徑授權 |
| `groups`〔第十八批〕 | 可省；可建立、可加成員、可 chgrp 的群組，每項是確切名稱字串或 `{"prefix":…}`；省略＝不授群組 |

子登記的佈建權只能是父的子集（B-606）。

### socket

- 權限預設：父目錄 0750、socket 0660，群組由部署配置（首版不用 ACL）。
- 每個 `socket_path` 對應一把同目錄的 `daemon.lock` 獨占鎖。
- socket 的準備、殘留 socket 的清理、`state_dir` 的排他鎖（有 cgroup 時另加 cgroup 子樹那把）見 [B-611](../../daemon/lifecycle.md)。
- 可連 socket 不等於通過授權（[B-601](../../daemon/runtime.md)）。

## P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕

啟動模式、`SUDO_UID`、永久降權、kill helper 不重拉、daemon 死了 helper 跟著退出，全部照 [B-303](../../helper.md)。

**PID 提示檔**（什麼時候寫、刪，舊檔怎麼看，見 [B-603](../../daemon/lifecycle.md)）：

| 檔 | 內容 |
|---|---|
| `state_dir/helper.pid` | 一行 PID；沒 helper 寫 `none` |
| `state_dir/daemon.pid` | 一行 PID |

helper PID 另照 P-101 印在 stdout。helper 的設定副本、父死監看與失聯見 [B-601](../../daemon/runtime.md)；熱重載的界線見 [B-608](../../daemon/reload.md)。

## P-103．IPC 封包與授權〔建議預設，未拍板〕

### 封包

- Unix stream；UTF-8 JSON，每行一筆、LF 結尾；含 LF 最多 262144 bytes。
- 不用 batch，也不用 notification。
- 請求與回應沿 [common](../../../protocol/schemas/common.schema.json) 的 `RpcRequest`／`RpcResponse`；`params` 必填 object。
- 每條連線逐筆處理，回應沿用請求 ID。
- **附 fd**：只有 `node.provision` 的 `spawn_as` 在請求那一行附 SCM_RIGHTS fd（[P-107](provision-and-runner.md)，第十九批）；其他請求附了 fd，就關掉 fd 並回 `invalid_params`。

### 誰可呼叫

每個 method 誰可呼叫、帶憑證時怎麼讀、授權順序與斷線後不准盲重送，以 [B-601](../../daemon/runtime.md)「IPC 授權與身分額度」為正本（astra 審整理區必-8 從本條搬上）。
