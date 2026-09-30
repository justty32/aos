# 可選 root helper 與 aos-as

← [整理區](README.md)｜[daemon](daemon.md)｜[通用 tick](tick.md)｜其餘身分規則：[身分與資源](../base/identity-resources.md)

本篇只有 B-303，從[身分與資源](../base/identity-resources.md)搬來，條號不變。身分額度的歸屬（B-301）、部署（B-302）與磁碟（B-304）仍在原篇。

## B-303：可選 root helper 與解析分界〔使用者方向 2026-09-29〕

**helper 是 daemon 的一部分**，切成小程序是為了安全，緊急時可以 kill。不需要 UID 隔離的部署可以不裝。

- 主 daemon 不是 root。目標就是通用 user 時，由 daemon 自己開；需要其他身分才交給 helper。
- 任務要換帳號，入口是普通程式 `aos-as`（下面），由它請 helper 開。
- 任務表裡的系統級任務也不是 root；要 root 的固定步驟留在 helper。

### 一支指令，看啟動方式決定模式

| 怎麼開 daemon | 模式 |
|---|---|
| 不用 sudo | 沒 helper：整樹用通用 user，要求其他身分一律拒絕 |
| 用 sudo（root） | 有 helper：daemon 在接 IPC、讀任何 node 之前先 fork 出 helper，主程式隨即永久降權（清掉 root 身分、群組、capabilities 與特權 fd）；stdout 印 `helper_pid=...`，並存兩份 PID 提示檔（[B-603](daemon.md)） |

- **helper 不能比 daemon 活得久**：daemon 死掉時 helper 必須跟著結束（例如 `PR_SET_PDEATHSIG`，並以跟 daemon 之間的管道斷線為準），不留沒人管的 root 程序。
- **通用 user 不能是 root**：用 sudo 開時，取叫 sudo 的原帳號（`SUDO_UID`）；直接用 root 開或由服務啟動時，設定檔必須明寫一個非 root 帳號，否則拒絕啟動。
- **kill helper＝切斷新的特權操作**：已開的 tick 照跑到結束；之後需要其他身分的 tick 一律不跑，並寫待處理事項。helper 不自動重啟，要恢復得重開 daemon。已做的 chown 不回滾。
- systemd 沙盒防護初版不用，見 [B-605](daemon.md)。

### helper 只做固定的事

- helper 只查可信註冊、切目標帳號、exec 固定 [runner](terms.md#t-09收尾排空停機熱重載逃生口)（有 cgroup 時另外把它放進該放的框，並替 daemon 建框、交框、刪殘留框），外加固定清單上的佈建動作（清單、參數與各動作做什麼以 [B-609](daemon.md) 為正本）。每次只做清單上的一件，不接任意程式當 root 跑。
- 牽涉 helper 的設定（其他帳號的額度、佈建權）改了，要重開 daemon（[B-608](daemon.md)）。
- 先授權、切身分，之後才解析與開檔；順序以 [inst](../base/inst.md) 為正本。失敗不能借高權限補救。
- helper 的請求綁定 daemon 已授權的註冊項與本次目標 UID，不能拿呼叫者自填的 UID 或路徑當授權。
- 切換帳號前，清掉繼承的憑證、沒核准的 fd 與多餘特權。以指定帳號開程序時，`aos-as` 交來的鎖 fd、回報 pipe 與 stdio 是核准的 fd（[B-609](daemon.md)）。不把 LLM key 傳給 runner。
- 管理 socket 只有一個明示例外：daemon 開 tick 時，以環境變數給通道的 socket 位置與本格憑證（[B-612](daemon.md)），通道上以憑證認 tick。人手與 CLI 的管理操作仍只看 socket 對面的帳號。
- runner 的環境按目標帳號及部署建立，inst 的 envs 再照它的規則疊加；不另禁止工具用一般權限改設定。

### `aos-as`：切換帳號的包裝

核心不切帳號。任務要用別的帳號跑，就在 argv 寫 `aos-as <帳號> -- 原指令`（argv、檔名與結束碼見 [P-212](protocol/node.md)）。它是普通程式，不是系統級任務。

〔建議預設，未拍板〕步驟：

1. 把原指令寫成一份 inst，放到 ignored 的 `.aos/jobs/as-<seq>-<pid>.json`：
   - `argv`、目前 cwd；
   - 環境：用 `envs` 的 `clear` 寫下目前的環境，但**拿掉 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`**〔暫定，astra 審整理區必-2〕。憑證只放記憶體、不寫檔（[B-612](daemon.md)）；fd 經 helper 傳過去號碼可能變。這三個由 runner 最後補上正確的值（[B-609](daemon.md)）；
   - stdin／stdout／stderr 寫成繼承，因為 runner 已拿交來的三個 fd 當自己的 stdio。
2. 帶本格憑證經通道送 `node.provision` 的 `spawn_as`（[B-609](daemon.md)；參數與限制不變：誰能叫、帳號要在身分額度內、放在哪）。同一包交出繼承到的鎖 fd（`AOS_TICK_LOCK_FD`）、一條回報 pipe 的寫端，另交自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走。自己在 `aos-cg` 的 `task-*` 框裡時（`aos-cg -- aos-as …`），一併帶那個框當 `frame`（[B-634](tick.md)、[B-609](daemon.md)）。
3. 讀 pipe 到 EOF，拿到 runner 的回報（[P-110](protocol/daemon/provision-and-runner.md)），照它結束：正常結束回同一碼，被訊號結束就用同一個訊號結束自己；刪掉那份 inst。runner 先清空它名下的程序才寫回報（B-601），所以 `aos-as` 結束時原指令與它的後代都已結束。

- **鎖**：別的帳號的程序繼承同一份鎖 fd，照 [B-602](tick.md) 核對得到。
- **有 git 時**：別的帳號的程序寫進 aos 範圍的檔，要讓 tick 帳號讀得到（例如用 [B-609](daemon.md) 的共享群組），否則 `aos-git` 讀不到、當故障（[B-630](tick.md)）。`aos-as` 等到 pipe EOF 才結束，所以它結束前核心不會開下一項。
- **被取消**：呼叫方對 `aos-as` 送 SIGTERM／SIGINT，它就結束（不刪那份 inst，留給清理）；runner 發現回報 pipe 斷了就清空原指令、結束。中間可能有一小段跟下一項重疊，見 [B-609](daemon.md)「呼叫方不在了」〔暫定〕。
- **不行時**：沒有通道變數（不是 daemon 開的格），或 daemon 回 `helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`，都回 125、不寫 `exit`，stderr 印代碼。回應成功但 pipe 沒回報就關了，也回 125（`result_unknown`），呼叫它的一方不能重跑。不另設替代路。
- **daemon 那側**：`spawn_as` 由「帶本格憑證的程序」呼叫，實際上就是 `aos-as`；tick 自己不呼叫。

依據：astra 審整理區必-2、設-3（環境不寫憑證、呼叫方不在了）；納入 cgroup 與 git 改寫計畫（`frame`、跨帳號寫進 aos 範圍的檔要讓 tick 帳號讀得到）；使用者方向 2026-09-29（helper、啟動模式、kill helper）；2026-09-29 晚（systemd 沙盒）；第十八批（佈建動作以 B-609 為正本）；第十九批第 9 條（通道例外）、疑點裁定 10（核准的 fd）；第二十批追答 8、疑點裁定 6（`aos-as`）。

**驗收：**授權及切身分後開檔見 [V-03](../conformance.md)；另測切帳號失敗回 125、無 `exit`，kill helper 後不得偷改用通用 user。任務帶跟 tick 不同的 `user` 時那一項回 125；包了 `aos-as` 而且有 helper、有通道時以指定帳號跑，任務內用 `AOS_TICK_LOCK_FD` 核對得到獨占鎖、輸出照任務表寫的走；直接跑的格裡 `aos-as` 回 125（`no_channel`）。
