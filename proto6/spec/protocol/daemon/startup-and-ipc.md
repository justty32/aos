# daemon 協議：啟動、設定與 IPC

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-101．啟動、設定與 socket〔建議預設，未拍板〕

完整 argv：`aos daemon --config /absolute/daemon.json`。前景執行；stdin 不讀，stdout 啟動時印 `helper_pid=<PID>`（無 helper 為 `none`）及 node 問題的警告；stderr 只印 daemon 自身原因造成的錯誤。讀設定、登記 inst 的原始 bytes（部署須授通用 user 必要讀取及目錄穿越權；讀不到就拒絕，不交 root 代讀），寫 socket、state_dir 恢復檔、node 的 `.aos/attention/` 及 P-110 的 once 失敗旁檔。環境不作授權，不定義 `AOS_*` 變數。正常停機回 0；用法／設定尚未開始做事前失敗回 2；初始化、清空或運行中的 daemon 自己失敗回 125。啟動先照 [B-605](../../daemon.md) 自檢：版本低於下限、沒有 cgroup v2、拿不到交給 daemon 的 cgroup 子樹，都回 125 並在 stderr 說明。SIGINT／SIGTERM 走 P-114 的正常停機；其他訊號由父程序看 wait 狀態。

[設定 schema](../schemas/daemon-config.schema.json)：

| 欄位 | 意思 |
|---|---|
| `version` | 必填，1 |
| `common_user` | 可省，非空帳號名稱或非負 UID；預設見 P-102 |
| `socket_path` | 必填，正規化絕對檔案路徑，例如 `/run/user/1000/aos/daemon.sock`；多 UID 部署可用 `/run/aos/daemon.sock` |
| `state_dir` | 必填，daemon 可寫的絕對目錄；存 `state.json`、自身 `attention/` 及 PID 提示檔 |
| `pause_save_interval_ms` | 可省，正整數，預設 1000；pause 有變動時批次存檔間隔 |
| `shutdown_grace_ms` | 可省，預設 2000，非負毫秒；到期後依執行器收尾 |
| `cgroup_root` | 可省；不用 sudo 開時，使用者事先建好並交給 daemon 帳號的 cgroup v2 子樹絕對路徑。省略時用 systemd `Delegate=yes` 劃給 daemon 的子樹；各種啟動方式的子樹來源依 [B-605](../../daemon.md)，拿不到就不啟動 |
| `disable` | 可省，不重複字串陣列，目前只認 `quota`；強制關掉啟動時偵測到的可選功能（B-605） |
| `roots` | 必填，頂層登記陣列；每項如下，`node_id` 不可重複 |

頂層項必填 `node_id`、`identity_grant`，可帶正整數 `interval_ms` 與 `provision`；無 parent_id／once。身分額度是非空、不重複的帳號／UID 陣列。inst 尋找及 base 只依 [P-010](../README.md)；頂層與普通 node 必須是資料夾，once 可為單檔。找不到 inst 是用法錯 2；IPC 註冊回 -32602／invalid_params，不使 daemon 退出。

`provision` 是可省的固定動作授權：`{"actions":[…],"paths":[…]}`，兩欄必填、各自不得重複；省略等於無佈建權。`actions` 只認 P-107 五種；`paths` 是可佈建的絕對目錄範圍，空陣列不授任何路徑。`cgroup_root` 不是一般可寫路徑授權。

設定於啟動讀定，修改後重開 daemon。部署者先配置 socket 父目錄的穿越權及 socket 的連接權；預設父目錄 0750、socket 0660，群組由部署配置（首版不用 ACL），不在封包給任意人改。無法 bind、位置過長或權限不足就明確失敗。每個 socket_path 對應一把同目錄的 `daemon.lock` 獨占鎖；持鎖後才能清理屬於這個實例的殘留 socket，不能刪活著的 socket。可連 socket 不等於通過 method 授權。

## P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕

啟動模式、SUDO_UID、永久降權、kill helper 不重拉及 daemon 死亡連帶退出，完全依 [B-303](../../base/identity-resources.md)。啟動同時寫 `state_dir/helper.pid`（一行 PID，無 helper 寫 `none`）及 `state_dir/daemon.pid`（一行 PID）。正常退出刪兩檔；啟動見舊檔只當提示，不拿來殺程序。helper PID 也依 P-101 輸出；非 root 啟動只准通用 user，改設定不能冒充切 UID。

〔建議預設，未拍板〕root 設定及父目錄不得由不受信任 node 改寫；fork 前固定設定副本，處理設定父死訊號的競態，父死訊號與私有通道斷線共同監看。額度不准 UID 0 或 root 別名。舊程序依 [B-603](../../daemon.md) 清空；helper 消失而不能收尾時保留占用、阻止新格，不宣稱清空。

## P-103．IPC 封包與授權〔建議預設，未拍板〕

Unix stream，UTF-8 JSON 每行加 LF，含 LF 最多 262144 bytes；不用 batch／notification。請求與回應沿 [common](../schemas/common.schema.json) 的 `RpcRequest`／`RpcResponse`；`params` 必填 object。每條連線逐筆處理，回應沿用請求 ID。先驗 JSON／method／參數，再以 `SO_PEERCRED.uid` 和可信註冊鏈授權；不能用 PID、路徑前綴、封包的 `user` 當呼叫者。

登記保存授權時解析出的 `owner_uid`；改 inst 不立即改掉 IPC owner。有效的下一格身分採用或經原 owner／父層授權的重新登記，才更新它。上層指可信註冊鏈的祖先，不是 OS 父目錄；同 UID 共用同一 OS 權限，不能辨別是哪個 node 或工具在呼叫。

| method | 誰可呼叫 |
|---|---|
| `node.register` | 新成員：已登記父 node 的 owner，或該父的祖先 owner；首次必須有父層同意，不能自行接到別人的鏈。既有項：原 owner 或祖先 owner；不能換父或搶別隊 |
| `node.unregister` | 目標 owner 或祖先 owner；效果包含目標已登記子樹 |
| `node.wake` | 目標 owner 或祖先 owner |
| `node.pause`、`node.resume` | 目標 owner 或祖先 owner |
| `daemon.info` | 有 socket 連接權；只回本次啟動 ID，不暴露登記 |
| `node.ls` | 有 socket 連接權；逐筆只列 peer 是 owner／祖先 owner 的登記及保留的 once 結果，無可見項回空陣列 |
| `node.show` | 目標 owner 或祖先 owner；含 P-106 保留的 once 結果，不開 tick |
| `node.provision` | 目標 owner 或祖先 owner，且目標登記有相符的 `provision` 授權；需 helper 的動作再由 helper 核對 |
| `daemon.attention.ls`、`daemon.attention.show` | 只回 peer 是來源 owner／祖先 owner 的事項，見 P-601 |
| `daemon.attention.done` | 來源 owner 或祖先 owner；只把 daemon 自身事項標成完成，見 P-601 |

root／通用 user 不因名稱自帶全樹 RPC 特權；它若是 owner／祖先才符合表格。既有成員可重登自己，但不能擴大目前額度或佈建權；新授額度及佈建權限只能由父層 owner／祖先 owner 在自身授權內下授。首次由父層登記，本版不提供首次自登記。

RPC ID 只配對回應，不是永久執行收據。斷線不代表沒做；登記／pause／resume 可核對目前值，wake 可合併但不是永久去重，once 與特權動作不准因沒回應就盲重送。daemon 不加持久重播帳本。
