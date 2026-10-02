← [可選 root helper 與 aos-as](../helper.md)（分檔 2/2）｜所在段落：B-303：可選 root helper 與解析分界〔使用者方向 2026-09-29〕｜[上一份](01-B-303-helper模式與固定動作.md)

### `aos-as`：切換帳號的包裝

核心不切帳號。任務要用別的帳號跑，就在 argv 寫 `aos-as <帳號> -- 原指令`（argv、檔名與結束碼見 [P-212](../../protocol/tick.md)）。它是普通程式，不是系統級任務。

〔建議預設，未拍板〕步驟：

1. 把原指令寫成一份 inst，放到 ignored 的 `.aos/jobs/as-<seq>-<pid>.json`：
   - `argv`、目前 cwd；
   - 環境：用 `envs` 的 `clear` 寫下目前的環境，但**拿掉 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`**〔暫定，astra 審整理區必-2〕。憑證只放記憶體、不寫檔（[B-612](../daemon/channel.md)）；fd 經 helper 傳過去號碼可能變。這三個由 runner 最後補上正確的值（[B-609](../daemon/helper-actions.md)）；
   - stdin／stdout／stderr 寫成繼承，因為 runner 已拿交來的三個 fd 當自己的 stdio。
2. 帶本格憑證經通道送 `node.provision` 的 `spawn_as`（[B-609](../daemon/helper-actions.md)；參數與限制不變：誰能叫、帳號要在身分額度內、放在哪）。同一包交出繼承到的鎖 fd（`AOS_TICK_LOCK_FD`）、一條回報 pipe 的寫端，另交自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走。自己在 `aos-cg` 的 `task-*` 框裡時（`aos-cg -- aos-as …`），一併帶那個框當 `frame`（[B-634](../cg.md)、[B-609](../daemon/helper-actions.md)）。〔astra 報告設計 1〕這時框裡已有 `aos-cg` 自己與 `aos-as`，跟 helper 要求空框衝突，記在[暫緩區已知問題](../readme/03-總表-daemon協議與其他.md#已知的設計問題記錄這輪不改)，這輪不改。
3. 讀 pipe 到 EOF，拿到 runner 的回報（[P-110](../protocol/daemon/provision-and-runner.md)），照它結束：正常結束回同一碼，被訊號結束就用同一個訊號結束自己；刪掉那份 inst。runner 先清空它名下的程序才寫回報（B-601），所以 `aos-as` 結束時原指令與它的後代都已結束。

- **鎖**：別的帳號的程序繼承同一份鎖 fd，照 [B-602](../../tick.md) 核對得到。
- **有 git 時**：別的帳號的程序寫進 aos 範圍的檔，要讓 tick 帳號讀得到（例如用 [B-609](../daemon/helper-actions.md) 的共享群組），否則 `aos-git` 讀不到、當故障（[B-630](../git.md)）。`aos-as` 等到 pipe EOF 才結束，所以它結束前核心不會開下一項。
- **被取消**：呼叫方對 `aos-as` 送 SIGTERM／SIGINT，它就結束（不刪那份 inst，留給清理）；runner 發現回報 pipe 斷了就清空原指令、結束。中間可能有一小段跟下一項重疊，見 [B-609](../daemon/helper-actions.md)「呼叫方不在了」〔暫定〕。
- 〔建議預設，未拍板〕helper 動作被開關關掉時，`spawn_as` 回 `not_available`，`aos-as` 回 125、stderr 印代碼、不開原指令。
- **不行時**：沒有通道變數（不是 daemon 開的格），或 daemon 回 `helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`，都回 125、不寫 `exit`，stderr 印代碼。回應成功但 pipe 沒回報就關了，也回 125（`result_unknown`），呼叫它的一方不能重跑。不另設替代路。
- **daemon 那側**：`spawn_as` 由「帶本格憑證的程序」呼叫，實際上就是 `aos-as`；tick 自己不呼叫。

依據：astra 審整理區必-2、設-3（環境不寫憑證、呼叫方不在了）；納入 cgroup 與 git 改寫計畫（`frame`、跨帳號寫進 aos 範圍的檔要讓 tick 帳號讀得到）；使用者方向 2026-09-29（helper、啟動模式、kill helper）；2026-09-29 晚（systemd 沙盒）；第十八批（佈建動作以 B-609 為正本）；第十九批第 9 條（通道例外）、疑點裁定 10（核准的 fd）；第二十批追答 8、疑點裁定 6（`aos-as`）。

**驗收：**授權及切身分後開檔見 [V-03](../../../notes/archive/spec-2026-10-02/conformance.md)；另測切帳號失敗回 125、無 `exit`，kill helper 後不得偷改用通用 user。任務帶跟 tick 不同的 `user` 時那一項回 125；包了 `aos-as` 而且有 helper、有通道時以指定帳號跑，任務內用 `AOS_TICK_LOCK_FD` 核對得到獨占鎖、輸出照任務表寫的走；直接跑的格裡 `aos-as` 回 125（`no_channel`）。
