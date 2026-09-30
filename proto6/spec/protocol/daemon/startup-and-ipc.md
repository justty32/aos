# daemon 協議：啟動、設定與 IPC

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-101．啟動、設定與 socket〔建議預設，未拍板〕

完整 argv：`aos daemon --config /absolute/daemon.json [--create-cgroup]`；`--create-cgroup` 等於設定的 `create_cgroup: true`，兩處任一開著就算開〔第二十批進行順序：本輪只驗形狀、不生效，下一步納入 cgroup，[B-605](../../daemon.md)〕。前景執行；stdin 不讀。

- stdout：啟動時印 `helper_pid=<PID>`（無 helper 為 `none`）；〔使用者方向 2026-09-30，第二十批〕第十九批的啟動偵測行 `standard: cgroup=full|fallback` 撤，本輪不印 cgroup 或 git 的偵測行（[B-605](../../daemon.md)）；node 問題的警告；〔第十八批〕熱重載每次一行 `reload applied=<欄位,…> restart_required=<欄位,…>`（沒有就留空），設定有不認得的欄位時一行 `config_unknown_fields=<欄位,…>`（[C-07](../../contracts.md)）。
- stderr：只印 daemon 自身原因造成的錯誤。
- 讀：設定檔、登記 inst 的原始 bytes（部署須授通用 user 必要讀取及目錄穿越權；讀不到就拒絕，不交 root 代讀）。寫：socket、`state_dir` 下的恢復檔與鎖、node 的 `.aos/attention/`、P-110 的掛載行程未啟動旁檔。環境不作授權；〔使用者方向 2026-09-30，第十九批〕daemon 只替它開的程序放兩個通道變數（[P-117](channel.md)），自己不讀 `AOS_*`。
- 結束碼：正常停機 0；用法／設定在開始做事前就錯回 2（〔第十七批〕開了 create_cgroup——設定或 `--create-cgroup` 任一處——卻缺 `cgroup_root` 一律算這種，本輪照樣驗）；自己的最低需求不合（〔第十九批〕缺 cgroup 不算）、取不到排他鎖、初始化、清空或運行中 daemon 自己失敗回 125，stderr 說明；〔下一步納入 cgroup〕明寫的 `cgroup_root` 準備不好也回 125。啟動自檢見 [B-605](../../daemon.md)，排他鎖見 [B-611](../../daemon.md)。
- 訊號：SIGINT／SIGTERM 停機（P-114、[B-604](../../daemon.md)）；〔第十八批〕SIGHUP 熱重載（[B-608](../../daemon.md)）；其他訊號由父程序看 wait 狀態。

[設定 schema](../schemas/daemon-config.schema.json)（持久檔，不認得的欄位忽略，[C-07](../../contracts.md)）。哪些欄位能熱重載、哪些要重開，見 [B-608](../../daemon.md) 的表。

| 欄位 | 意思 |
|---|---|
| `version` | 必填，1 |
| `common_user` | 可省，非空帳號名稱或非負 UID；預設見 P-102 |
| `socket_path` | 必填，正規化絕對檔案路徑，例如 `/run/user/1000/aos/daemon.sock`；多 UID 部署可用 `/run/aos/daemon.sock` |
| `state_dir` | 必填，daemon 可寫的絕對目錄；存 `state.json`、自身 `attention/` 及 PID 提示檔 |
| `pause_save_interval_ms` | 可省，正整數，預設 1000；pause 批次存檔間隔（[B-603](../../daemon.md)）。〔第二十批〕以下各 `_ms` 都是 daemon 本身的計時，保留毫秒（[C-01](../../contracts.md)） |
| `shutdown_grace_ms` | 可省，非負毫秒，預設 2000；收尾時 SIGTERM 到 SIGKILL（下一步納入 cgroup 後是 `cgroup.kill`）的寬限（[B-604](../../daemon.md)） |
| `stop_mode`〔第十八批〕 | 可省，`"immediate"`（預設）或 `"drain"`；SIGINT／SIGTERM 走哪種停機（B-604） |
| `drain_timeout_ms`〔第十八批〕 | 可省，正整數毫秒，預設 600000；排空停機最多等多久，跟 `shutdown_grace_ms` 是兩個值 |
| `kill_escape_cgroups`〔第十八批；〔暫定，第二十批疑-13〕撤〕 | 逃生口不再提供（[B-605](../../daemon.md)），這欄撤出 schema；舊設定寫了照 [C-07](../../contracts.md) 忽略 |
| `mount_diag_max`〔第十八批；第十九批改名，原 `once_diag_max`〕 | 可省，非負整數，預設 1024；掛載行程的診斷最多留幾筆，0＝不留（[B-610](../../daemon.md)） |
| `mount_diag_ttl_ms`〔第十八批；第十九批改名，原 `once_diag_ttl_ms`〕 | 可省，正整數毫秒，預設 86400000；掛載行程的診斷結束後留多久 |
| `cgroup_root`〔下一步納入 cgroup；本輪只驗形狀、不生效〕 | 可省；已準備好（或要 daemon 自己建）的 cgroup v2 子樹絕對路徑；省略就用 daemon 自己目前所在的 cgroup，用不了就照沒有 cgroup 做。「準備好」與子層搬移見 [daemon 篇末](../../daemon.md) |
| `create_cgroup`〔下一步納入 cgroup；本輪只驗形狀、不生效〕 | 可省，布林，預設 false；true＝子樹不在時 daemon 自己建（同 `--create-cgroup`），此時 `cgroup_root` 必填（B-605） |
| `disable` | 可省，不重複字串陣列，目前只認 `quota`；強制關掉啟動時偵測到的可選功能（B-605） |
| `roots` | 必填，頂層登記陣列；每項如下，`node_id` 不可重複 |

範例：[最小設定](../examples/daemon/config.minimal.valid.json)、[開了 create_cgroup 的設定](../examples/daemon/config.create-cgroup.valid.json)、[反例：開了卻沒寫 cgroup_root](../examples/daemon/config.create-cgroup-no-root.invalid.json)、[反例：版本 2](../examples/daemon/config.version.invalid.json)、〔第十八批〕[前綴與範圍額度、排空與新欄位，另帶一個不認得的欄位仍收](../examples/daemon/config.grant-prefix.valid.json)、[反例：範圍涵蓋系統帳號](../examples/daemon/config.grant-range-system.invalid.json)、[反例：空前綴](../examples/daemon/config.grant-prefix-empty.invalid.json)。

頂層項必填 `node_id`、`identity_grant`，可帶正整數 `interval_ms`（一格的標準長度，外部規定、保留毫秒，[B-607](../../daemon.md)）與 `provision`；無 `parent_id`（上層固定 null，[B-606](../../daemon.md)）。inst 尋找及 base 依 [inst](../../base/inst.md)。找不到 inst 是用法錯 2；IPC 註冊回 -32602／invalid_params，不使 daemon 退出。

**身分額度**（`identity_grant`）是非空、不重複的陣列，每項是下列之一；意思、排除規則與包含判定見 [B-606](../../daemon.md)：

| 形狀 | 例 |
|---|---|
| 帳號名稱字串（非空、不是 `root`） | `"aos-alice"` |
| UID 整數（不是 0） | `1001` |
| 〔第十八批〕前綴 `{"prefix":<非空字串>}` | `{"prefix":"aos-"}` |
| 〔第十八批〕範圍 `{"uid_min":N,"uid_max":M}`，N ≥ 1000，N ≤ M | `{"uid_min":20000,"uid_max":29999}` |

`uid_min ≤ uid_max` 由程式核對，schema 表達不了。

**佈建權**（`provision`）可省，省略等於無佈建權：`{"actions":[…],"paths":[…],"groups":[…]}`。`actions`、`paths` 必填，各自不得重複；`actions` 只認 [P-107](provision-and-runner.md) 的九種；`paths` 是可佈建的絕對目錄範圍，空陣列不授任何路徑；〔第十八批〕`groups` 可省，是可建立、可加成員、可 chgrp 的群組，每項是確切名稱字串或 `{"prefix":…}`，省略＝不授群組。`cgroup_root` 不是一般可寫路徑授權。子登記的佈建權只能是父的子集（B-606）。

socket 權限預設：父目錄 0750、socket 0660，群組由部署配置（首版不用 ACL）。每個 socket_path 對應一把同目錄的 `daemon.lock` 獨占鎖。socket 的準備、殘留 socket 的清理與 `state_dir`（下一步納入 cgroup 後另加 cgroup 子樹）的排他鎖見 [B-611](../../daemon.md)；可連 socket 不等於通過授權（[B-601](../../daemon.md)）。

## P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕

啟動模式、SUDO_UID、永久降權、kill helper 不重拉及 daemon 死亡連帶退出，完全依 [B-303](../../base/identity-resources.md)。啟動同時寫 `state_dir/helper.pid`（一行 PID，無 helper 寫 `none`）及 `state_dir/daemon.pid`（一行 PID）。正常退出刪兩檔；啟動見舊檔只當提示，不拿來殺程序。helper PID 也依 P-101 輸出；非 root 啟動只准通用 user，改設定不能冒充切 UID。

helper 的設定副本、父死監看與失聯時怎麼辦見 [B-601](../../daemon.md)，熱重載的界線見 [B-608](../../daemon.md)。

## P-103．IPC 封包與授權〔建議預設，未拍板〕

Unix stream，UTF-8 JSON 每行加 LF，含 LF 最多 262144 bytes；〔第十九批〕只有 `node.provision` 的 `spawn_as` 在請求那一行附 SCM_RIGHTS fd（[P-107](provision-and-runner.md)），其他請求附了 fd 就關掉並回 `invalid_params`；不用 batch／notification。請求與回應沿 [common](../schemas/common.schema.json) 的 `RpcRequest`／`RpcResponse`；`params` 必填 object。每條連線逐筆處理，回應沿用請求 ID。授權的順序與呼叫者怎麼認見 [B-601](../../daemon.md)：不帶憑證看 `SO_PEERCRED.uid`，〔使用者方向 2026-09-30，第十九批〕帶憑證時表中「X 的 owner 或祖先 owner」讀成「憑證所屬的 tick 就是 X 或在 X 的有效上層鏈上」（[B-612](../../daemon.md)）。

表中的 owner 是登記保存的 `owner_uid`，何時更新見 [B-606](../../daemon.md)；上層指有效上層鏈（預設看資料夾包含，登記可覆蓋，B-606）。

| method | 誰可呼叫 |
|---|---|
| `node.register` | 新成員：有效上層的 owner 或祖先 owner；首次必須有上層同意，不能自行接到別人的鏈。既有項：原 owner 或祖先 owner，不能搶別隊。〔第十九批〕覆蓋上層與換父：同時是新舊兩個上層的 owner 或祖先 owner；舊上層沒在這個 daemon 登記時只看新上層（[B-606](../../daemon.md)） |
| `node.unregister` | 目標 owner 或祖先 owner；效果包含目標已登記子樹 |
| `node.wake` | 目標 owner 或祖先 owner |
| `node.mount`〔第十九批〕 | 掛載的上層（`parent_id`，帶憑證時省略＝憑證所屬的 tick）的 owner 或祖先 owner（[B-613](../../daemon.md)） |
| `node.kill`〔第十九批〕 | 掛它的那個上層的 owner 或祖先 owner；看路徑，不看當時的憑證 |
| `node.send`〔第十九批〕 | 必帶憑證；寄件 tick 的執行帳號對收件 tick 的 `requests/` 有寫權（[B-614](../../daemon.md)） |
| `node.take`〔第十九批〕 | 必帶憑證；只取憑證所屬 tick 自己的 |
| `node.pause`、`node.resume` | 目標 owner 或祖先 owner |
| `daemon.info` | 有 socket 連接權；只回本次啟動 ID，不暴露登記 |
| `node.ls` | 有 socket 連接權；逐筆只列 peer 是 owner／祖先 owner 的登記及保留的掛載行程結果，無可見項回空陣列 |
| `node.show` | 目標 owner 或祖先 owner；含 P-106 保留的掛載行程結果 |
| `mount.clear`〔第十八批；第十九批改名，原 `once.clear`〕 | 有 socket 連接權；只清 peer 是 owner／祖先 owner 的已結束掛載行程紀錄（[B-610](../../daemon.md)） |
| `node.provision` | 目標 owner 或祖先 owner，且目標登記有相符的 `provision` 授權；需 helper 的動作再由 helper 核對。〔第十九批〕`spawn_as` 例外：必帶憑證、憑證所屬的 tick 就是目標，帳號看身分額度，不看 `provision` 授權（[B-609](../../daemon.md)） |
| `daemon.attention.ls`、`daemon.attention.show` | 只回 peer 是來源 owner／祖先 owner 的事項，見 P-601 |
| `daemon.attention.done` | 來源 owner 或祖先 owner；只把 daemon 自身事項標成完成，見 P-601 |

既有成員可重登自己，但不能擴大目前額度或佈建權；擴大與下授的規則見 [B-606](../../daemon.md)。root／通用 user 沒有全樹特權、RPC ID 不是執行收據、斷線後不准盲重送，見 [B-601](../../daemon.md)。
