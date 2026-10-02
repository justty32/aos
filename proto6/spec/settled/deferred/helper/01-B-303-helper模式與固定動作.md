← [可選 root helper 與 aos-as](../helper.md)（分檔 1/2）｜[下一份](02-B-303-aos-as.md)

## B-303：可選 root helper 與解析分界〔使用者方向 2026-09-29〕

> **暫緩**（2026-10-01）：root helper 與 `aos-as`；最核心 daemon 第一版不做（使用者 2026-10-01），helper 之後另做成模組。條號保留、不重用。〔2026-10-01 第十三批〕**部分已被 [B-646](../../daemon/account.md) 取代**：帳號模組照這裡「sudo 開時另開 root 端、主程式永久降權、root 端用指定帳號開程序」的骨架，但 root 端只剩「開程序」一個動作，單位是 daemon 的一項（不是 `aos-as`、不經通道與身分額度），帳號名單寫在 daemon 設定檔。其餘暫緩。

**helper 是 daemon 的一部分**，切成小程序是為了安全，緊急時可以 kill。不需要 UID 隔離的部署可以不裝。

- 主 daemon 不是 root。目標就是通用 user 時，由 daemon 自己開；需要其他身分才交給 helper。
- 任務要換帳號，入口是普通程式 `aos-as`（下面），由它請 helper 開。
- 任務表裡的系統級任務也不是 root；要 root 的固定步驟留在 helper。

### 一支指令，看啟動方式決定模式

| 怎麼開 daemon | 模式 |
|---|---|
| 不用 sudo | 沒 helper：整樹用通用 user，要求其他身分一律拒絕 |
| 用 sudo（root） | 有 helper：daemon 在接 IPC、讀任何 node 之前先 fork 出 helper，主程式隨即永久降權（清掉 root 身分、群組、capabilities 與特權 fd）；stdout 印 `helper_pid=...`，並存兩份 PID 提示檔（[B-603](../daemon/lifecycle.md)） |

- **helper 不能比 daemon 活得久**：daemon 死掉時 helper 必須跟著結束（例如 `PR_SET_PDEATHSIG`，並以跟 daemon 之間的管道斷線為準），不留沒人管的 root 程序。
- **通用 user 不能是 root**：用 sudo 開時，取叫 sudo 的原帳號（`SUDO_UID`）；直接用 root 開或由服務啟動時，設定檔必須明寫一個非 root 帳號，否則拒絕啟動。
- **kill helper＝切斷新的特權操作**：已開的 tick 照跑到結束；之後需要其他身分的 tick 一律不跑，並寫待處理事項。helper 不自動重啟，要恢復得重開 daemon。已做的 chown 不回滾。
- systemd 沙盒防護初版不用，見 [B-605](../daemon/cgroup.md)。

〔建議預設，未拍板〕`enable_helper_actions:false` 只關對外動作，不改本條 helper 的啟動模式及核心開格／收尾；cgroup 動作另依 cgroup 部件。界線見 [B-609](../daemon/helper-actions.md)、[B-615](../daemon/components.md)。

### helper 只做固定的事

- helper 只查可信註冊、切目標帳號、exec 固定 [runner](../terms.md#t-09收尾排空停機熱重載逃生口)（有 cgroup 時另外把它放進該放的框，並替 daemon 建框、交框、刪殘留框），外加固定清單上的佈建動作（清單、參數與各動作做什麼以 [B-609](../daemon/helper-actions.md) 為正本）。每次只做清單上的一件，不接任意程式當 root 跑。
- 牽涉 helper 的設定（其他帳號的額度、佈建權）改了，要重開 daemon（[B-608](../daemon/reload.md)）。
- 先授權、切身分，之後才解析與開檔；順序以 [inst](../../../base/inst.md) 為正本。失敗不能借高權限補救。
- helper 的請求綁定 daemon 已授權的註冊項與本次目標 UID，不能拿呼叫者自填的 UID 或路徑當授權。
- 切換帳號前，清掉繼承的憑證、沒核准的 fd 與多餘特權。以指定帳號開程序時，`aos-as` 交來的鎖 fd、回報 pipe 與 stdio 是核准的 fd（[B-609](../daemon/helper-actions.md)）。不把 LLM key 傳給 runner。
- 管理 socket 只有一個明示例外：daemon 開 tick 時，以環境變數給通道的 socket 位置與本格憑證（[B-612](../daemon/channel.md)），通道上以憑證認 tick。人手與 CLI 的管理操作仍只看 socket 對面的帳號。
- runner 的環境按目標帳號及部署建立，inst 的 envs 再照它的規則疊加；不另禁止工具用一般權限改設定。
