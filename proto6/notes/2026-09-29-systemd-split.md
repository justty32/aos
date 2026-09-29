# daemon 與 root helper：哪些交給 systemd

← [筆記索引](README.md)｜方向來源：[裁定紀錄「下班前的方向」第一條](2026-09-29-verdicts.md#下班前的方向同日尚未落進-spec)｜延遲實測：[systemd-run 延遲](probes/systemd-run-latency.md)

2026-09-29 晚。使用者定了方向：daemon 站在 systemd 上面，能交給 systemd 的就交，不重造輪子，安全要小心。本篇把 spec 裡 daemon 和 root helper **現在負責的每一件事**逐條列出，標「交給 systemd／自己留著／不確定」。**這輪只列清單，沒改 spec**；每條最後一欄是 spec 條號，之後改 spec 時照著找。

## 先講結論

- 能交出去的大多是「開程序、切帳號、資源框、殺乾淨、逾時、OOM」這些 OS 層的事，systemd 做得比我們自己寫的好，也不會拿重用的 PID 殺錯人。
- 留下來的是 aos 自己的規矩：誰能登記誰、身分額度、叫醒要合併、pause 閘門、存檔與重建、待辦。systemd 沒有這些概念。
- 最大的安全問題：**能叫 system 層 systemd 開程序的人，等於有 root**。所以「誰去叫 systemd」決定了整套的權限大小。建議見第三節。

## 這輪做的小實驗（只用 user 層，沒用 sudo）

暫存在 scratchpad，做完已停掉所有測試 unit、清掉 `set-property` 留下的設定檔。

| 試了什麼 | 結果 |
|---|---|
| `systemd-run --user --uid=65534`、`-p User=nobody` | 都失敗，退出 216：user 層確實不能切帳號 |
| 程式 `setsid sleep &` 後自己退出 | 主程式一結束，systemd 把另開 session 的孫子也殺掉（預設 `KillMode=control-group`） |
| 加 `ExitType=cgroup` | 等整個框空了才算結束；配 `RuntimeMaxSec=2` 到時回 `Result=timeout` |
| `MemoryMax=20M` 吃 200 MB | `Result=oom-kill`，直接分得出是 OOM，不必從 SIGKILL 猜 |
| 巢狀 slice＋`systemctl set-property --runtime` 改上限 | 可以，實際寫進 cgroup 的 `memory.max`；停掉 slice 會連裡面的程序一起停 |
| `set-property --runtime` 之後停掉 slice | 設定檔留在 `/run/user/1000/systemd/user.control/`，下次同名 slice 出現會**套回舊上限**，要 `systemctl revert` 才清得掉 |
| `TimeoutStopSec=2` 停一個不理 TERM 的程式 | 約 2.1 秒後 KILL，`Result=timeout` |
| 把 node 路徑轉成 unit 名（12 層、378 字元） | 失敗：unit 名最多 255 字元 |
| 框內程式跑 `systemctl --user set-property 自己的 slice MemoryMax=900M` | **成功**，還能 `systemd-run --user` 在框外開新程序 |
| 框內程式直接寫上層 slice 的 `memory.max` | **成功**（整棵 user 樹的 cgroup 檔都歸同一個帳號） |
| 加 `InaccessiblePaths=/run/user/1000/bus` 與 `…/systemd` | 框內連不上 user systemd，開不出框外程序 |
| 加 `ProtectControlGroups=yes` | 框內 cgroup 變唯讀，改不了上限，但還讀得到 `cgroup.procs` |
| 不用 sudo 叫 system 層 `systemd-run` | 被 polkit 拒絕（沒開互動認證） |

## 一、daemon 現在做的事

| # | 事情 | 歸類 | 怎麼做／為什麼 | 條號 |
|---|---|---|---|---|
| D1 | 記憶體登記表、父子鏈、身分額度核對 | 自己留著 | systemd 不懂「誰是誰的上層、准用哪些帳號」。unit 只是執行容器 | B-601、B-301、P-104 |
| D2 | 本機 socket、看對面帳號（SO_PEERCRED）決定能不能操作 | 自己留著 | 授權規則是 aos 的。socket 本身可選擇讓 systemd 先開好（socket activation），不影響授權 | B-601、P-101、P-103 |
| D3 | 按 `interval_ms` 定期叫醒 | 不確定 | timer 的 `OnUnitInactiveSec=` 正好是「收尾後重新計時、不補跑」。卡在：wake 要合併成一個 pending、pause 要擋、daemon 不在時 timer 照樣觸發會繞過 daemon、一萬個 node 就是一萬個 timer unit | B-601、P-104 |
| D4 | 叫醒合併：執行中再叫只留一個 pending | 自己留著 | 對一個正在跑的 unit 再 `start` 什麼都不做，systemd 沒有「跑完再來一次」 | B-504、P-105 |
| D5 | pause／resume 閘門、退出 3／125 自動停格 | 自己留著 | pause 只擋新格、不動正在跑的。systemd 的 freeze 是把正在跑的程序凍住，意思不同（實測凍住後連 stop 都要先解凍） | P-105 |
| D6 | 同一 node 不同時跑兩格 | 交給 systemd | 每個 node 一個固定 unit 名，同名 unit 還在時 systemd 拒絕再開，天然互斥。`aos-tick` 自己的 node 鎖照留（直接呼叫也要守） | B-602 |
| D7 | 開 tick／once 程序 | 交給 systemd | transient service（`systemd-run` 或 D-Bus `StartTransientUnit`），`ExecStart` 固定是 `aos-runner` | B-201、P-108 |
| D8 | 開格前讀 inst 的 `user` 做授權 | 自己留著 | 授權先於開程序，是 aos 的規則；systemd 只負責照給定的 `User=` 跑 | B-601、B-303 |
| D9 | 把 inst 快照 fd 與回報 pipe 交給 runner | 不確定 | systemd 只收 stdin／stdout／stderr 三個 fd，不能另塞 `--inst-fd`、`--status-fd`。`OpenFile=` 是由 systemd 身分開檔，system 層就是 root 代讀，違反「讀不到就拒絕」 | P-108、P-109、P-110 |
| D10 | 建 node 資源框（node 分支＋執行 leaf） | 交給 systemd | 每個 node 一個 slice（減號分層就是巢狀），tick unit 就是 leaf。名稱要另想，見拍板題 3 | P-107、P-503 |
| D11 | 寫 CPU／記憶體／pids 上限 | 交給 systemd | `systemctl set-property --runtime`：`MemoryMax=`、`TasksMax=`、`CPUQuota=`＋`CPUQuotaPeriodSec=`。注意實測的「舊設定會套回來」 | P-107、P-503、P-504 |
| D12 | `node.show` 回實際 cgroup 值 | 交給 systemd | 從 unit 的 `ControlGroup` 拿路徑，再讀 kernel 檔；不用 systemd 記的期望值冒充實際值 | P-106 |
| D13 | 殺乾淨後代：TERM→2 秒→KILL | 交給 systemd | `KillMode=control-group`（預設）＋`TimeoutStopSec=2`，按框殺、不看 PID，另開 session 也跑不掉（實測） | B-202、B-203 |
| D14 | 確認框真的空了；有後代被強制清時記失敗 | 自己留著 | systemd 靜靜把剩下的殺掉，不告訴你「有人殘留」；KILL 後仍殺不掉時 unit 變 failed，框卻可能不空。做法：runner 收尾前看自己框的 `cgroup.procs`，daemon 看 `cgroup.events` 的 populated | B-202 |
| D15 | 逾時 | 交給 systemd | `RuntimeMaxSec=`（monotonic）。差別：從 unit 起算，含 runner 前置那幾毫秒，spec 是從放行起算 | B-203、P-109 |
| D16 | 取消 | 交給 systemd | `systemctl stop`。「每個 attempt 只發布一次結果」的判定照留在執行器 | B-203 |
| D17 | OOM 證據 | 交給 systemd | `Result=oom-kill`＋框的 `memory.events`；WSL 要加 `MemorySwapMax=0` | B-204 |
| D18 | 收尾程序不被成員上限困住 | 交給 systemd | 收尾是 systemd 本身在做，本來就在成員框外 | B-204 |
| D19 | 重啟先把舊程序全殺 | 交給 systemd | 全部 aos unit 放在一個 `aos.slice` 底下，啟動時 `stop aos.slice`；systemd 按框記，不會殺錯重用 PID | B-603、P-116 |
| D20 | `state.json`、boot id、pause 批次存檔 | 自己留著 | aos 自己的狀態；transient unit 重開機就消失，不能拿來存 | B-603、P-115、P-116 |
| D21 | daemon 自己開機自啟、崩潰重啟 | 交給 systemd | 把 daemon 寫成 service unit（`Restart=on-failure`）。WSL 本來就只能這樣起 | B-603、[WSL 查證](2026-09-29-wsl-machine-check.md) |
| D22 | Ctrl-C 停機：停新格、等寬限、清空 | 交給 systemd | 清空用 `stop aos.slice`；「先停新格、清完才存檔回 0」的順序照留 | B-604、P-114 |
| D23 | unregister：排空目標與子樹 | 交給 systemd | 停掉該 node 的 slice 就連子樹一起停（實測） | B-604、P-105 |
| D24 | 新檔通知就叫醒 | 不確定 | `.path` unit 能盯資料夾，但觸發後直接開 unit 會繞過 pending／pause；要嘛讓它只去叫 `aos node wake`，要嘛 daemon 自己用 inotify | B-504 |
| D25 | `node.show`／`node.ls` 最近一格 | 自己留著 | 格式與判定是 aos 的；原始材料（退出碼、Result、時間）可以從 unit 取 | P-106 |
| D26 | node 待辦、once 的 `.err` 旁檔、stdout 警告 | 自己留著 | 純 aos 的事 | B-601、P-110、P-601 |
| D27 | `helper.pid`、`daemon.pid` 提示檔 | 自己留著 | 小事；daemon 跑成 unit 時 `MainPID` 也查得到 | P-102 |
| D28 | 不把管理 socket、LLM key 帶給 runner | 交給 systemd | unit 由 systemd 從乾淨狀態開，不繼承呼叫者的 fd 和環境變數 | B-303、P-109 |
| D29 | 收集 runner 的 stderr | 交給 systemd | `StandardError=file:` 或交一個 fd；跟 D9 一起定 | P-109 |

## 二、root helper 現在做的事

| # | 事情 | 歸類 | 怎麼做／為什麼 | 條號 |
|---|---|---|---|---|
| H1 | sudo 開時 fork 出 helper、主程式永久降權 | 不確定 | 取決於第三節選哪種部署；選 D 就照留 | B-303、P-102 |
| H2 | daemon 死 helper 跟著死；kill helper 不重拉 | 自己留著 | 只要還有 helper 就要。父死訊號＋通道斷線照舊 | B-303、P-102 |
| H3 | bind／unbind：重驗登記鏈、身分、inst 來源 | 自己留著 | 這就是安全邊界，systemd 不懂 aos 的授權 | P-108 |
| H4 | start：切帳號、放進資源框、exec 固定 runner | 交給 systemd | helper 只組一個固定形狀的 transient unit：`User=`＝目標、`Slice=`＝由登記推導、`ExecStart=`＝固定 runner。fork、setgroups、寫 cgroup 都不用自己寫 | P-108、B-303 |
| H5 | 切換前清憑證、fd、多餘特權 | 交給 systemd | 從 PID 1 開本來就乾淨；再加 `NoNewPrivileges=yes`、`CapabilityBoundingSet=`（空） | B-303 |
| H6 | stop：跨帳號收尾 | 交給 systemd | `systemctl stop` 該 unit；別的帳號的 unit 要 root 才能停，所以還是經 helper 叫 | P-108 |
| H7 | 建帳號 | 自己留著 | 還是 `useradd`。systemd 的 `DynamicUser=` 會回收重用 UID，違反「UID 不自動回收」 | P-107、B-604 |
| H8 | chown | 自己留著 | systemd 只替自己管的幾個目錄改擁有者，管不到任意 node 資料夾 | P-107 |
| H9 | project quota 記帳歸屬 | 自己留著 | systemd 沒有這功能 | P-107、B-304 |
| H10 | 在授權空目錄掛 tmpfs | 不確定 | `systemd-mount` 做得到但一樣要 root，重開機就沒；`TemporaryFileSystem=` 只有該程序看得到，別的 node 看不到，意思不同。交出去好處不大 | P-107 |
| H11 | `CapabilityBoundingSet`、`SystemCallFilter` 額外防護 | 交給 systemd | 寫在 helper／daemon 自己的 unit 裡。但要知道：這些**管不住它去叫 PID 1 開一個 root 的 unit**，見下節 | B-303 |

**統計**：交給 systemd 20 條（daemon 16、helper 4）；自己留著 15 條（daemon 10、helper 5）；不確定 5 條（D3、D9、D24、H1、H10）。

## 三、安全性

### 兩層 systemd 差在哪

- **system 層**（PID 1）：能用 `User=` 切成任何帳號、能開 root 程序、能停任何人的 unit。一般帳號去叫會被 polkit 擋（實測）；root 叫則什麼都准。
- **user 層**（`systemd-run --user`，每個帳號自己一個）：不能切帳號（實測 216）。整棵 user 樹的 cgroup 檔都歸該帳號，所以**同帳號的任何程式都能改自己的上限、在框外開程序**（實測）。

一條要記住的規則：**誰能叫 system 層開 unit，誰就等於 root**。`CapabilityBoundingSet`、`NoNewPrivileges` 只限制程序自己，限制不了它請 PID 1 代辦（舊調查〈[宿主 root 第二道牆](investigations/proto5-host-root-second-wall.md)〉也講過「不得留下請牆外服務代辦的通道」）。

### 幾種部署形態

| 形態 | 誰叫 systemd | 權限大小 | 主要風險 | 跟現有裁定的關係 |
|---|---|---|---|---|
| A 全在 user 層 | daemon（通用 user）叫 `--user` | 只有通用 user 自己的 | 工具與 daemon 同帳號：能改上限、框外開程序、殺 daemon、讀 state。前兩項可用下面的「共同防護」擋住，後兩項擋不住 | 就是現在的「不用 sudo＝沒 helper 模式」。符合 B-301「沒 helper 不承諾成員隔離」。沒人登入也要跑得起來，需要管理者一次性 `loginctl enable-linger` |
| B daemon 在 system 層跑成 root | daemon 自己叫 PID 1 | root 全部 | daemon 要讀 IPC、讀大量 node 的 inst，被騙一次就是 root。bounding set 攔不住它叫 PID 1 | **抵觸裁定 5**「主 daemon 非 root」。也沒有「kill helper 收回特權」這個緊急開關 |
| C daemon 非 root，靠 polkit 或窄 sudo 叫 `systemd-run` | daemon（通用 user） | 實際等於 root | polkit 規則看得到 unit 名與動作，看不到 `User=`、`ExecStart=`，准了就等於准它用任何身分跑任何程式。sudoers 的參數萬用字元擋不住多塞 `--uid=0`；要擋就得寫一支 root 小程式驗參數——那就是 D | 名義上「daemon 非 root」，實質違反裁定 5 的用意。kill 不掉一個獨立的特權程序，只能改規則檔收回 |
| D 保留 root helper，只替 daemon 叫 systemd | helper（root）叫 PID 1 | helper 是 root，但只收 daemon 的固定幾種請求 | helper 的驗證程式碼就是安全邊界，跟現在一樣；好處是 helper 變小：不再自己 fork、切帳號、寫 cgroup、殺程序樹 | 符合裁定 5 與 B-303。見下方三點 |
| E（附帶）daemon 帶 `CAP_SETUID` 自己切 | 不經 systemd 切帳號 | 近乎 root（`CAP_SETUID` 能切成 UID 0） | 同 B | 只是列出來，不建議 |

形態 D 跟三條既有裁定的關係：

- **「root helper 本質是 daemon 的一部分、切出來為了能 kill」**：照舊。helper 還是 daemon 用 sudo 啟動時 fork 出來的那支，只是做的事變少。
- **「通用 user 不能預設 root」**：不變。helper 組 unit 時 `User=` 只能是額度內、非 0 的帳號。
- **「kill helper 只切斷新的特權操作」**：反而更自然。tick 的 unit 歸 systemd 管、不是 helper 的孩子，kill helper 後已開的照跑到完。代價：要停別帳號的 unit 也得靠 helper，helper 死了 daemon 就停不掉它們——P-102 已寫「保留占用、阻止新格、不宣稱清空」，不衝突。

形態 D 帶出的一個新狀況：tick unit 不再是 daemon 程序的孩子，**daemon 突然死掉時它們不會跟著死**。B-603 本來就「下次啟動先清空再開」，所以正確性沒問題；若要 daemon 一死就清，得讓 daemon 自己也是 unit、tick unit 設 `BindsTo=`（見拍板題 5）。

### 不管哪種形態都該加的共同防護（加在每個 tick unit 上）

- `NoNewPrivileges=yes`、`CapabilityBoundingSet=`（空）：程式拿不到新特權。
- `InaccessiblePaths=/run/user/<UID>/bus /run/user/<UID>/systemd`：連不上 user systemd，不能自己改上限、不能在框外開程序（實測有效）。
- `ProtectControlGroups=yes`：cgroup 檔唯讀，不能直接改上限；仍讀得到自己的 `cgroup.procs`，runner 做 D14 的檢查不受影響（實測）。
- `KillMode=control-group`、`TimeoutStopSec=2`，WSL 另加 `MemorySwapMax=0`。
- 多帳號部署（D）：成員帳號不開 linger，就沒有自己的 user systemd；system 層的 polkit 預設也不准沒登入的帳號開 unit。這兩點**這輪沒法不用 sudo 驗證**，要列進部署檢查。

### 建議

**兩段：沒 helper 時用 A＋共同防護；要多帳號時用 D。不用 B、C、E。** 理由：

1. A 就是現在的沒 helper 模式，只把「自己開程序、自己殺樹」換成 systemd，權限一點沒多。加上兩條封鎖後，資源上限從「工具想逃就逃」變成「真的有效」。
2. 需要切帳號就一定有一個能叫 PID 1 的特權點。D 讓這個點維持「一支很小、能 kill 的 root 程序、只收固定請求」，符合裁定 5 與 sudo 模式的全部細節；C 看起來沒 root，實際把 root 交給了整支 daemon。
3. D 的 helper 比現在的 helper 小：切帳號、放框、殺樹、逾時、OOM 都交 systemd，helper 剩「重驗授權＋組固定 unit＋建帳號／chown／quota／tmpfs」。

## 四、需要使用者拍板的問題

| # | 問題 | 建議 |
|---|---|---|
| 1 | 部署形態選哪個？ | A（沒 helper）＋D（多帳號）兩段；B、C、E 不用。理由見上節 |
| 2 | 定期叫醒要不要真的用 systemd timer？ | 首版不用：daemon 自己一個計時表，timer 只拿來開機自啟 daemon。pending 合併、pause、daemon 不在時照觸發、萬級 unit，四件事都要 daemon 補，省不到東西 |
| 3 | unit／slice 名稱怎麼對 node 路徑？路徑轉成 unit 名會超過 255 字元（實測），slice 用減號分層，名字每層變長 | 用路徑算短雜湊當名字（例如每層 8 個十六進位字），對照只存在 daemon 記憶體；slice 仍照登記樹巢狀，約可撐 20 多層。路徑本身仍是 node id，只有 unit 名換成短名 |
| 4 | inst 快照與回報 pipe 怎麼交給 runner？systemd 只給三個標準 fd | stdin＝inst 快照（memfd）、stdout＝回報 pipe、stderr＝診斷收集；runner 讀完後把 stdin／stdout 換成 `/dev/null` 再開子程式。要改 P-109 的 argv（拿掉兩個 fd 參數） |
| 5 | daemon 突然死掉時，在途 tick 要不要立刻跟著死？ | 用 systemd 管 daemon 時設 `BindsTo=`，一死就清；前景手開時不綁，靠下次啟動 `stop aos.slice`（B-603 本來就這樣）。兩種都合「全殺」裁定 |
| 6 | 資源上限加在哪一層？每格都帶三個限制要多約 20 毫秒 | 上限只設在 node 的 slice（登記或改配額時設一次），每格的 unit 不帶限制，開格只多約 5 毫秒。這個「放在 slice 就便宜」是推測，實作前要量 |
| 7 | 沒 helper 模式要不要預設封鎖 user systemd 與 cgroup（共同防護的兩條）？封了之後工具就不能用 `systemctl --user` | 預設封，node 設定可明寫關掉；關掉時文件寫清楚「這個 node 的上限不算數」。跟「工具就是工具、風險自負」不衝突：只是讓預設下資源 module 說的話算數 |
| 8 | `set-property --runtime` 的舊上限會在同名 slice 再出現時套回來（實測） | daemon 啟動清空時一併 `systemctl revert` aos 的 slice，再由 kernel 照已提交配額重設（P-504 本來就說重啟後由 kernel 重新佈建） |
