← [daemon 維運：佈建與 helper 動作](../helper-actions.md)（分檔 2/2）｜所在段落：B-609：佈建固定動作與 helper 動作｜[上一份](01-B-609-通則與動作.md)

### 以指定帳號開程序（`spawn_as`）

tick 核心不呼叫它；呼叫者是**帶本格憑證的程序**，實際上就是任務 argv 裡包的 `aos-as`（[B-303](../../helper.md)、[P-212](../../../protocol/tick.md)）。參數見 [P-107](../../protocol/daemon/provision-and-runner.md)。daemon 這一側的規則（誰能叫、帳號限制、開什麼、回傳）不因呼叫者換人而變。以下做法為〔建議預設〕。

- **誰能叫**：只收通道上帶憑證的請求，`node_id` 必須就是憑證所屬、登記中的 node。掛載行程叫回 `kind_mismatch`，不帶憑證回 `forbidden`。不看登記的 `provision` 授權，看的是身分額度。
- **帳號的限制**：`user` 必須落在這個 node 的身分額度內（B-606 的規則，排除 UID 0 與 root 別名），不合回 `user_not_granted`，不存在回 `user_invalid`；不能用它建帳號。沒有 helper 回 `helper_unavailable`；排空或停機中回 `stopping`。
- **開什麼**：`path` 必須是這個 node 資料夾裡 `.aos/jobs/` 下的一般檔（`aos-as` 寫好的那份 inst，檔名由它定，見 [P-212](../../../protocol/tick.md)），逐段核對、不跟隨 symlink。daemon 取它的不可變快照，連同這個已核准的路徑交給 helper（`daemon.helper.spawn` 的 `path`，[P-108](../../protocol/daemon/provision-and-runner.md)）。helper fork、降成該帳號、exec 固定 aos-runner，以這個路徑當 `--target`；runner 照 B-601 核對原來源的 bytes 跟快照相同（不同回 `source_changed`），再照 [inst](../../../../base/inst.md) 跑。不收 argv、env 或輸出路徑。〔暫定〕這份暫存 inst 要讓目標帳號讀得到（例如用 B-609 的群組動作），讀不到就是前置失敗。
- **鎖與 fd**：請求同包交來 5 個 fd：鎖 fd、回報 pipe 的寫端，以及 `aos-as` 自己的 stdin、stdout、stderr。
  - helper 以 fstat 核對鎖 fd 就是這個 node 的 `.aos/tick.lock`，不符回 `invalid_params`。
  - runner 與它開的程序繼承這份鎖 fd（同一個 open file description），照 [B-602](../../../tick.md) 核對。
  - 〔第二十批，建議預設〕runner 以交來的三個 stdio fd 當自己的 stdin／stdout／stderr（不收集成 `.aos/runner-stderr.log`），原指令照那份 inst 寫的 stdio 走，所以輸出照任務表寫的去處。
  - **環境最後才補**〔暫定，astra 審整理區必-2〕：runner 照 inst 的 `envs` 建好子程式環境之後，最後才放進 `AOS_TICK_LOCK_FD`（runner 收到的鎖 fd 的新號碼；fd 經 SCM_RIGHTS 傳過來號碼可能變了）與這一格的兩個通道變數（B-612）；這三個不受 `clear` 影響，inst 裡寫了同名的也被蓋掉。所以 `aos-as` 寫的 inst 裡不放它們（[B-303](../../helper.md)），憑證不會落到磁碟上。
- **放在哪**：runner 是 helper 的子程序，不掛回 tick；它名下的程序照 B-601 由它自己清空：原指令結束後先清空、再寫回報。清不到的還握著鎖 fd 時，下一格回 75（[B-602](../../../tick.md)）。
  - cgroup 的 `frame` 與放框規則見 [B-609 的 cgroup 部分](../cgroup/04-資源上限與收尾清框.md#spawn_as-的框b-609)。

- **回傳**：runner 開起來就回 `{node_id}`，不等它結束；前置失敗回錯、不開程序。結束碼不經回應：runner 把 [P-110](../../protocol/daemon/provision-and-runner.md) 的那一行回報寫進 `aos-as` 交來的 pipe，`aos-as` 讀到 EOF 為止、照它結束。回應說成功、pipe 卻沒有回報就關了，這一項算失敗、結果不明，不重跑。
- **daemon 不記這個程序**：不進登記表、不留 B-610 的診斷、不發新憑證，也不能對它送 `node.kill`。helper 記下這個 runner 屬於哪個 node；daemon 收尾那個 node 時，helper 對它做 B-604 的收尾。
- **呼叫方不在了**〔暫定，astra 審整理區設-3〕：取消或逾時由呼叫的一方對 `aos-as` 做（它收到 SIGTERM／SIGINT 就結束）。`aos-as` 一結束，回報 pipe 的讀端就關了；runner 發現讀端關了（對寫端 poll 看到錯誤），照 B-601 立刻清空名下的程序、結束，不再寫回報。
  - **這一項什麼時候算結束**：對核心來說是 `aos-as` 結束的時候，所以下一項可能在 runner 清空之前就開了；這段時間裡原指令還握著鎖 fd，同資料夾的下一格拿不到鎖（回 75），但本格的下一項可能跟它短暫重疊。要避免，呼叫方應等 `aos-as` 自己結束，不要中途殺它。

依據：第十九批疑點裁定 10（握著鎖的一方經 helper 以別的帳號開、那個程序只需知道開它的那一格仍握著鎖）；第二十批追答 8、疑點裁定 6（呼叫者從 tick 改成普通程式 `aos-as`）；納入 cgroup 與 git 改寫計畫（`frame`）。

### daemon 自己做的與 helper 做的

- daemon 自己做得到的就自己做，不經 systemd；無 helper 時用通用 user 做，授權和上層限制照舊。
- 凡是要動到不屬於 daemon 帳號的檔或程序（其他帳號、群組、quota、以別的帳號開程序與收尾），才經 helper；無 helper 回 `helper_unavailable`。
- daemon 與 helper 自己留在成員限額之外。
- cgroup 的 helper 內部動作見 [B-609 的 cgroup 部分](../cgroup/04-資源上限與收尾清框.md#建框交框與刪框b-609)。

**驗收：**每個動作超出授權路徑、群組或額度都被拒；`aos-as` 開的原指令印出的環境裡 `AOS_TICK_LOCK_FD` 是它實際拿到的 fd 號碼、有本格憑證，而 `.aos/jobs/` 那份 inst 裡沒有憑證；暫存 inst 在授權後被改掉時回 `source_changed`；`aos-as` 被 SIGTERM 後，原指令也很快被清掉，下一格拿得到鎖，OS 現況不符回 `conflict`；多帳號部署下能靠這些動作讓兩個 node 帳號經共享群組交接檔案；沒 helper 時要 helper 的動作回 `helper_unavailable`；沒有 cgroup 時 `cgroup_limits` 回 `unsupported`，有 cgroup 時有程序在跑也能調低記憶體上限並立即生效；`spawn_as` 帶 `frame` 時開起來的程序在那個 `task-*` 框裡；`spawn_as` 帶額度外的帳號被拒；`aos-as` 帶本格憑證呼叫時，額度內的帳號開起來的程序以 `AOS_TICK_LOCK_FD` 核對得到獨占鎖，輸出走 `aos-as` 交來的 stdio，結束碼經回報 pipe 回到 `aos-as`；不帶憑證、由掛載行程叫、沒有 cgroup 卻帶 `frame`、附的 fd 不是 5 個都被拒。

**驗收（開關／多實例）：**〔建議預設，未拍板〕關 helper 動作後，`spawn_as` 與帳號／群組佈建回 `not_available`，沒有副作用；已授權的核心開格／收尾照常，cgroup 開關不受它牽動。
