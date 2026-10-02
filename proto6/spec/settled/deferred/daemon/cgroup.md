# daemon cgroup：框、上限與啟動自檢

← [舊 daemon 目錄（暫緩區）](README.md)｜[整理區](../../README.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊 daemon 的 cgroup 部件；cgroup 之後另做成模組。〔2026-10-01 第十二批〕**部分已被 [B-644](../../daemon/cgroup.md) 取代**：收屍／cgroup 模組照這裡「子樹根用自己所在的 cgroup、根下開 `daemon` 子層、`cgroup.kill` 清框、sha256 前 16 hex 命名、寫上限」的做法，但框改成以 daemon 的一項為單位（`i-<h>`），沒委派好就回 1、不退回。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## B-605：依賴與啟動自檢

> **部分取代、其餘暫緩**（2026-10-01 第十二批）：子樹從哪來（首推做法 1）、根只當分支、命名、上限、跑完清框的部分已被 [B-644](../../daemon/cgroup.md) 取代；啟動自檢的 `cgroup=on/off`、委派偵測、退回 runner、`cgroup_root`、`--create-cgroup`、node 框、交框、逃生口、中途失效暫緩。條號保留、不重用。

〔使用者方向 2026-09-30 晚〕node 框、上限、有框時的清框與 cgroup 子樹鎖都屬可掛的 cgroup 部件；helper 的 cgroup 動作也歸本部件。共通最低需求仍屬核心。

〔建議預設，未拍板〕`enable_cgroup:false` 時不偵測、不建框、不取 cgroup 子樹鎖，也不依 `cgroup_root_last` 清舊框；即使機器可用 cgroup 也走現成 `cgroup=off` 路線：`node.show.cgroup:null`、`cgroup_limits` 與帶 `frame` 的 `spawn_as` 回 `unsupported`，runner 照常開格及收尾。`cgroup_root`、`create_cgroup`（含旗標）仍做既有格式／必填相依驗證，但不執行 cgroup 動作。`spawn_as` 若同時被 helper 動作開關關掉，先照 B-609 回 `not_available`；上述帶 `frame` 回 `unsupported` 指 helper 動作仍開著的情形。以下「有就用」皆以本部件開著為前提。

依據：[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

**tick 核心不需要 cgroup；daemon 有 cgroup 就用、沒有就退回 runner 那一套**（B-601、B-604）。cgroup 給 daemon／helper（node 框與資源上限）與普通程式 `aos-cg`（每項一框，[B-634](../cg.md)）用。

- 撤掉的：第十四、十五批「沒 cgroup v2 就拒絕啟動」；第十九批的「沒 cgroup 走備援、降到備援級」「完整路／備援路」與啟動時印 `standard: cgroup=…`。
- 初版不使用 systemd 當執行期依賴；systemd 只當取得委派子樹、開機自動啟動的方式（下面與 [service 範例](service.md)）。

依據：第十九批（推翻第十四、十五批）；第二十批追答 8；納入 cgroup 與 git 的疑點裁定。

### 啟動自檢

daemon 共通的最低需求與不查 git 見 [B-605 的共通自檢](runtime.md#啟動自檢b-605-的共通部分)。

- **偵測 cgroup**：照下面「什麼算有 cgroup」。stdout 印一行 `cgroup=on` 或 `cgroup=off`，只報 daemon 自己的；`off` 時 stderr 另印一次警告，不寫事項、不問 y／n。〔建議預設〕
- **沒有 cgroup 時**：B-609 的 `cgroup_limits` 回 `unsupported`，`node.show` 的 `cgroup` 為 null，B-611 只取 `state_dir` 那把鎖，程序照 B-601 由 runner 管。

### 什麼算有 cgroup

三個條件都成立才用：Linux ≥ 5.14（`cgroup.kill` 從這版起有）、`/sys/fs/cgroup` 是純 cgroup v2、拿得到**委派給自己**的子樹。

**委派給自己怎麼認**〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-6〕：

| 情形 | 算不算 |
|---|---|
| 設定明寫 `cgroup_root`，或開了 `create_cgroup` | 算：部署者說了就是要（準備不好就報錯退出，下面） |
| 省略時，systemd 說 daemon 所在的單位有 `Delegate=yes` | 算。用 `systemctl [--user] show -p Delegate <單位>` 問，單位名取 `/proc/self/cgroup` 最後一段 |
| 省略時，問不到 systemd，或單位沒有 `Delegate=yes` | 不算，`cgroup=off` |
| cgroup v1、混合模式（v2 掛在 `/sys/fs/cgroup/unified`） | 自動偵測一律不算。混合模式可以明寫 `cgroup_root` 指進去，但 controller 多半在 v1 那邊，上限會回 `unsupported`，只剩收尾與看空不空能用 |
| 自動偵測時，子樹根的祖先已被別的 daemon 鎖住（巢狀 daemon，B-611） | 不算，`cgroup=off` 照跑；它仍被外層的框和上限包住（疑-11） |

- **只看擁有者不夠**（本機實測，WSL、systemd 255）：沒加 `Delegate=yes` 的 `systemd-run --user --scope`，`cgroup.procs` 一樣歸自己；兩種 scope 都沒有 `user.delegate` xattr。只看擁有者，會把沒委派的 scope 當成可以寫，違反 systemd「一個框只有一個寫入者」的約定。
- **明寫卻準備不好**（疑-9）：明寫了 `cgroup_root` 或開了 `create_cgroup`，子樹卻準備不好、搬不動程序，報錯退出（125），不默默改成沒有 cgroup：明寫就是要，默默不用會少了上限。

### 子樹從哪來（首推不用 sudo）

**用 cgroup 時一定要有一棵已經準備好的 cgroup v2 子樹**〔使用者方向 2026-09-29 晚，第十五批；第十九批改成「沒有就照沒有 cgroup 做」〕。依序推薦：

| # | 做法 | 用不用 sudo | 說明 |
|---|---|---|---|
| 1 | `systemd-run --user --scope -p Delegate=yes aos daemon --config ~/.config/aos/daemon.json` | 不用（首推） | 省略 `cgroup_root`，就用這個 scope 當子樹。實測這台 WSL 拿得到 `cpu memory pids` |
| 2 | 使用者層 service：固定單位名、`Delegate=yes`，對該帳號 `loginctl enable-linger` | 不用 | 開機自動啟動用這個；框路徑固定，重啟時 systemd 也會先殺舊程序（[service 範例](service.md)） |
| 3 | 系統層 service：root 開、`Delegate=yes` | 要 | 有 helper（[service 範例](service.md)） |
| 4 | 沒有 systemd：root 事先 mkdir 並 chown 下面的委派檔，或 sudo 開加 `--create-cgroup` | 要 | 明寫 `cgroup_root` |
| 5 | 都沒有 | — | `cgroup=off`，照 B-601 跑 |

檢查步驟〔建議預設〕：

1. `stat -fc %T /sys/fs/cgroup` 印 `cgroup2fs`：是 cgroup v2。
2. `uname -r` 至少 5.14。
3. `systemctl --user is-system-running` 有回應：有使用者層的 systemd。
4. 在委派 scope 裡看拿到的子樹：`systemd-run --user --scope -p Delegate=yes sh -c 'p=$(sed -n "s/^0:://p" /proc/self/cgroup); cat /sys/fs/cgroup$p/cgroup.controllers'`，至少有 `memory pids`。沒有 `cpu` 時 CPU 上限回 `unsupported`，其餘照用（要 `cpu` 得讓使用者層的 systemd 委派它，屬部署設定）。

**限制要知道**：

- **不用 sudo 就只能單帳號**：沒有 root helper，就不能把框交給別的帳號，也不能以別的帳號開程序。多帳號部署一定要 sudo（3 或 4）。
- **WSL 的三個坑**（本機實測）：
  - wsl.exe 開的 shell 在 root 擁有的 `/init.scope` 裡，直接跑 daemon 只會是 `cgroup=off`。要先在 `/etc/wsl.conf` 的 `[boot]` 設 `systemd=true`，再用 1 或 2。
  - `systemd-run --user --scope` 每次開出的 scope 名字都不一樣（`run-r<隨機>.scope`），daemon 重啟後要靠 `state.json` 記的上次子樹根去清舊框（B-603）。
  - 框的檔案歸自己，不代表 systemd 真的委派了（上面「只看擁有者不夠」）。
  - 另外：VM 閒置被關時所有東西一起死，照 B-603 的「整機重開」處理。
- **硬上限由部署者在更外層設**〔第十八批〕：頂層 kernel 的額度檔只是分配政策，不承諾頂層真的被卡住；整棵子樹要有總上限，由部署者事先設在子樹根或更上一層。

**子樹的通用規則**〔第十五～十七批〕：

- **在哪**：設定的 `cgroup_root`（[P-101](../protocol/daemon/startup-and-ipc.md)）；省略時就用 daemon 自己目前所在的 cgroup。
- **根只當分支**：daemon（或其他程序）就在子樹根那層時，daemon 啟動先開 `daemon` 子層、把那層程序全搬進去（cgroup v2 規定已有子層又要開 controller 的那層不能放程序）。搬不動或一直有新程序進來：明寫 `cgroup_root` 就報錯退出，省略時當成沒有 cgroup。
- **準備好**＝子樹存在；它的資料夾和根上的委派檔（`cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`）交給了 daemon 跑的帳號。不用 sudo 開時，daemon 自己也要已經在子樹裡，因為 cgroup v2 搬程序要對共同上層有寫權。
- **sudo 開時**：daemon 在降權前（還是 root 時）把子樹資料夾及其委派檔交給降權後的帳號、自己搬進子樹下的葉框；跨子樹邊界搬程序要 root，所以只在降權前做。
- **`--create-cgroup`**（設定 `create_cgroup: true`，預設關）：子樹不在時由 daemon 自己建在 `cgroup_root`（開了就必須寫，否則用法錯 2）；sudo 開時在降權前建。建不了就報錯退出；子樹已經在就直接用。在有 systemd 的機器上這樣做會違反「一個框只有一個寫入者」，通常能用但不保證，aos 不擋。

### 框的樹、命名與交框

```
<子樹根>/daemon                daemon 與 helper
<子樹根>/n-<h>                 頂層 node（分支；上限寫這層）
          ├─ tick              這格的 runner、tick 與沒包 aos-cg 的任務
          ├─ task-<seq>-<pid>  aos-cg 開的每項一框（B-634）
          ├─ mount-<h>         本 node 掛的掛載行程（B-613）
          ├─ n-<h'>            子 node，同樣結構
          └─ （其他名字）      node 自己開的子框：逃生口
```

- **命名**〔第十六批〕：node id 是任意長的絕對路徑，不能直接當 cgroup 名。`<h>` 是 node_id 的 UTF-8 bytes 做 sha256 取前 16 個小寫 hex；碰撞機率可忽略，首版不另做偵測。node 框放在**有效上層** node 的框下（頂層放子樹根下），所以覆蓋上層時框也跟著放（B-606）。
- **保留名**：`daemon`、`tick`、`task-*`、`n-*`、`mount-*`；node 自己開子框不能用這些名字。
- **誰建、誰交**〔納入 cgroup 與 git 疑-10〕：daemon 在 node 第一次開格前自己建 `n-<h>` 與 `tick`（不寫上限）。`aos-cg` 要以 node 的帳號在 `n-<h>` 下開框、搬自己，所以 daemon 把 `n-<h>` 資料夾及其 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 交給 node 的執行帳號（inst 的 `user`）；上限檔仍歸 daemon，node 改不了。帳號不是 daemon 自己時經 helper 做（B-609 的 helper 內部動作）。開格前發現擁有者跟目前的 `user` 不同（inst 換了帳號），就重交一次。不開放給 `node.provision`。
- **連帶**：交框之後，node 帳號能對自己框裡別的帳號的程序（`aos-as` 開、放進本 node 框的）寫 `cgroup.kill`；這是預期行為。它也能關掉自己 `cgroup.subtree_control` 的 controller，等於撤掉自己子 node 的上限；這在它的權限內，祖先對整棵分支的上限照樣有效（B-609）。
- **資源上限設在 node 那層**〔使用者方向 2026-09-29 晚〕：寫在 `n-<h>` 分支一次，之後每格沿用，隨時可改（B-609）。

### 逃生口：node 自開的子框，不管

〔使用者方向 2026-09-30，第十八批 Q19；納入 cgroup 與 git 疑-7「准」〕node 可以在自己的 `n-<h>` 下另開子框（名字避開保留名），把程序搬進去、刻意留常駐程序。**這不在 aos 的管轄範圍內，aos 不管**，跟「通道是唯一逃生口」（[T-07](../../terms.md)）不算衝突。

- 格後收尾只看 `tick` 與 `task-*`，不碰這些子框（B-601）。
- daemon 重啟（B-603）與解除登記（B-606）時殺不殺，照設定 `kill_escape_cgroups`：預設 false，不殺、框留著；設成 true 就一併收尾（[P-101](../protocol/daemon/startup-and-ipc.md)）。
- 逃生口的程序仍在 node 框裡，照樣受 node 的資源上限管。框裡還有逃生口時 `n-<h>` 刪不掉：解除登記照樣完成、框留著並寫該 node 的事項，等之後空了由 B-603 的空框清理刪。
- 沒有 cgroup 時沒有框，也就沒有這種逃生口；runner 清不到的常駐程序（例如經外部服務開的）本來就不歸 daemon 管（B-601）。
- 要 daemon 追得到、`node.kill` 砍得掉的常駐程序，用通道 `node.mount` 掛（B-613）。

### 中途失效：只影響那個 node

〔建議預設〕daemon 啟動時 `cgroup=on`，之後某個 node 建框或交框失敗（上層關了 controller、權限被改、`cgroup.max.descendants` 滿了）：那個 node 照沒有 cgroup 的做法跑（B-601），寫一件該 node 的事項；別的 node 照常。不整個 daemon 降級，也不停那個 node。之後建得起來就改回用框。

quota 與初版共通界線見 [B-605 的共通自檢](runtime.md#啟動自檢b-605-的共通部分)。

**驗收：**Python 低於 3.9 時啟動報錯退出。Linux 低於 5.14、沒有純 cgroup v2、WSL 在 `/init.scope` 直接跑、或用沒加 `Delegate=yes` 的 scope 開時，daemon 照常啟動、印 `cgroup=off`、照常開格，stdout 沒有 `standard:` 行；照首推用 `systemd-run --user --scope -p Delegate=yes` 開、不寫 `cgroup_root` 時印 `cgroup=on`；省略 `cgroup_root`、或有寫但該層有程序時，原層只剩子層、沒有程序；明寫 `cgroup_root` 卻沒準備好、也沒開 `--create-cgroup` 時報錯退出（125），不自己建；開了 `--create-cgroup` 卻沒寫 `cgroup_root` 時用法錯（2），建不了時報錯退出；某個 node 建框失敗時只有它照沒有 cgroup 跑、有一件事項；node 自己開的子框裡的程序，格後與重啟時都不被收（`kill_escape_cgroups` 省略時）；偵測得到 quota 但設定強制關時不使用。

## 核心條文的 cgroup 部分

> **暫緩**（2026-10-01）：跟著 B-605 與各條一起暫緩；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

以下各段沿用來源條號，不另編號；核心的 runner、登記、收尾及掛行程仍見各條正本。

### 格後清框（B-601）

有 cgroup 時 [B-601 的 runner 做法](runtime.md)**照舊**，另外加一層框（框的樹見 B-605）：

| 步驟 | 做法 |
|---|---|
| 開格 | runner 開在那個 node 的 `n-<h>/tick` 框裡（掛載行程在 `mount-<h>`，B-605），用 `CLONE_INTO_CGROUP` 或 exec 前寫 `cgroup.procs`（[B-601 開格第 1 步](runtime.md#開格runner-與回報)） |
| 格後收尾 | runner 回報、被回收之後，daemon 對 `tick` 框與本格的 `task-*` 框寫 `cgroup.kill`，看 `cgroup.events` 的 populated 變 0，再 rmdir `task-*`（框已交給別的帳號時經 helper 刪）。不另外對程序群組送 SIGKILL |
| 範圍 | 只收 `tick` 與 `task-*`；子 node 的 `n-*`、本 node 掛的 `mount-*`、node 自己開的其他子框（逃生口，B-605）都不碰 |
| 等不到歸零 | 例如 D 狀態程序：算後代清不空，照 B-607 停格 |

- 框兜得住 runner 清不到的：跳出程序群組又自設 subreaper 的、換成別的帳號的（經 `aos-as` 開、放進本 node 框的）。經外部服務開的仍在框外，不歸 aos 管。
- 包了 `aos-cg` 的項，自己在 `task-*` 框裡當場收（[B-634](../cg.md)）；daemon 的格後收尾只是兜底。
- 某個 node 建不了框時，那個 node 照沒有 cgroup 的做法跑（B-605「中途失效」）。

### 重啟清框（B-603）

**有 cgroup 時**〔使用者方向 2026-09-29 晚；納入 cgroup 與 git 疑-8〕：daemon 開的每一格（含孫程序）都在該 node 的框裡，daemon 當掉時框還在。

1. **找舊框**：`state.json` 記著上次用的子樹根（`cgroup_root_last`，[P-116](../protocol/daemon/shutdown.md)）。這次的子樹根不同（例如首推的 `systemd-run --user --scope` 每次開出的 scope 名字都不一樣）、而舊根還在時，先對舊根取 B-611 的鎖；取不到表示另一個 daemon 在用，不碰。
2. **清**：開任何新格之前，對新舊子樹裡每個仍有程序的受管框走一次 B-604 的收尾（寬限沿用 `shutdown_grace_ms`），確認全空才往下。受管框是 `tick`、`task-*`、`mount-*` 與子 node 的 `n-*`；node 自己開的其他子框是逃生口，照 `kill_escape_cgroups` 決定殺不殺（B-605）。
3. 舊 scope 清空後沒有程序，systemd 會自己回收。

### 重建後刪空框（B-603）

- **空框清理**（有 cgroup 時；〔使用者方向 2026-09-30，第十八批〕）：重啟清空後，沒有登記對應的 `mount-*` 框直接刪（掛載行程不會接回）；沒有登記對應的 `n-*` 框先留著，等逐層重建完、仍沒人登記才由下往上刪，免得先刪掉稍後又要重建的框（重建會讓上限要重寫、用量歸零）。〔建議預設〕「重建完」＝所有已登記、沒暫停的 node 自這次啟動以來都至少跑完一格。框裡還有逃生口的程序就不刪。框已交給別的帳號時由 helper 刪（B-609）。

### 資源上限（B-609）

沿用 [B-609 通則與授權](helper-actions.md#通則)。

| 動作 | 做什麼 | 要 helper |
|---|---|---|
| `cgroup_limits` | 寫 `n-<h>` 的 CPU、記憶體、程序數上限，作用於整個分支含後代；只寫這些 controller，不設就不新增該項限制。沒有 cgroup（或這個 node 退回沒有框）回 `unsupported` | 不要 |

〔使用者方向 2026-09-30，第十八批；拿掉「整棵子樹全空才改」〕

- **隨時改**：`cgroup_limits` 調高、調低都隨時寫，不關閘門、不等全空；同一框的寫入依序做。已是相同值就核對後成功，不重寫。改限制值不算中途換資源範圍（[B-302](../../../base/identity-resources.md)）。
- **調低超過現用量**：由 Linux 自己處理（例如記憶體回收或 OOM、新 fork 失敗），aos 不擋；要記一筆的是下指令的 kernel，記在它自己的資源狀態檔（[S-203](../../../scheduling/admission.md)）。
- **controller 往下開**：要在子 node 上寫上限，上一層的 `cgroup.subtree_control` 要開 `+cpu +memory +pids`；daemon 建框時就開。某個 controller 不在（例如使用者層 systemd 沒委派 `cpu`），那一項回 `unsupported`，其餘照用。
- 上層 node 帳號關掉自己框的 controller，等於撤了自己子 node 的上限；這在它的權限內，不是逃脫，祖先對整棵分支的上限照樣有效（B-605）。

### spawn_as 的框（B-609）

- **帶 `frame`**（有 cgroup 時）：`aos-as` 在 `aos-cg` 開的 `task-<seq>-<pid>` 框裡時（寫成 `aos-cg -- aos-as <帳號> -- 原指令`，[B-634](../cg.md)），請求帶 `frame`＝那個框。helper 核對它是本 node `n-<h>` 的直接子框、存在且沒有程序，把 runner 放進去再 exec。框仍歸 node 的帳號，`aos-cg` 照 B-634 等它清空、必要時 `cgroup.kill`。
- 沒帶 `frame`、daemon 有 cgroup 時，runner 放進本 node 的 `tick` 框，格後收尾一起收（B-601）。
- 沒有 cgroup 時帶了 `frame` 回 `unsupported`。

> **已知問題，未定**〔astra 報告設計 1，2026-10-01 記錄，不改設計，等這條回來時再定〕：照現在寫法，`aos-cg` 先把監督程式自己搬進任務框，再要求殺空、等待、刪框；自己還在框裡，收尾會連自己一起殺掉、做不完。推薦寫法 `aos-cg -- aos-as …` 也讓框裡已經有人（`aos-cg` 自己），上面 helper 卻要求框「沒有程序」，正常用法也過不了。astra 建議：監督程式留在框外，只讓子程序進框；helper 改成核對框的歸屬與允許的現有程序，不要求全空。`aos-cg` 那一側見 [B-634](../cg.md)。

### 建框、交框與刪框（B-609）

- **有 cgroup 時**：daemon 在交給它的子樹內自己建框、寫限制、讀實際值，不經 systemd。框要交給別的帳號、或上層框已交給別的帳號時，建框、交框、刪框才經 helper。helper 另有兩個只給 daemon 用、不開放給 `node.provision` 的內部動作（[P-108](../protocol/daemon/provision-and-runner.md)）：
  - **建框並交框**：在可信上層框下建本 node 的 `n-<h>` 與 `tick`，交給這個 node 目前的執行帳號（B-605）；路徑由登記推導，不收呼叫者給的 cgroup 路徑。
  - **刪殘留框**：只刪子樹內、名字是 `n-*`／`mount-*`／`task-*`、已經沒有程序也沒有子框的框（B-603、B-606）。

### 掛載行程的框（B-613）

有 cgroup 時它的框放在掛它的 node 框下，名字 `mount-<h>`，本身就是葉框（B-605）。那個 node 的格後收尾不碰它；砍掉或結束時由收尾清空、刪框（B-604、B-603）。

### cgroup 子樹鎖（B-611）

- **有 cgroup 時另取一把**：以解析後的真實路徑，對實際使用的 cgroup 子樹根（含省略 `cgroup_root` 時自己所在那層）取排他鎖。明寫 `cgroup_root` 時取不到就拒絕啟動（125）；自動偵測時取不到（巢狀 daemon：祖先被外層 daemon 鎖住），就當成沒有 cgroup，`cgroup=off` 照跑（B-605；納入 cgroup 與 git 疑-11）。沒有 cgroup 時只取 `state_dir` 那把。

cgroup 子樹那把同樣直接對目錄取（cgroup 目錄裡不能另建一般檔；實測開目錄後 flock 可行，第二個 fd 會被擋），祖先往上試鎖到 cgroup 掛載點、子孫往下掃一遍。用首推做法開的兩個 daemon 各在自己的 scope，彼此是兄弟、不重疊，只有 `state_dir` 那把會擋。

### 收尾最後清框（B-604）

[B-604 的 runner 收尾](lifecycle.md#收尾)第 6 步，**有 cgroup 時**：對範圍內仍有程序的框寫 `cgroup.kill`，以 `cgroup.events` 的 populated 確認全空。

依據：第十八批；納入 cgroup 與 git 改寫計畫（`cgroup.kill` 兜底）；[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)（拆成部件）。

**驗收（開關／多實例）：**〔建議預設，未拍板〕部件關掉但機器有 cgroup 時，印 `cgroup=off`、不碰新舊框、只取核心鎖；`node.show.cgroup` 為 null，runner 的格後收尾仍成立。

搬來各段的原依據與驗收沿用 [B-601](runtime.md)、[B-603、B-604、B-611](lifecycle.md)、[B-609](helper-actions.md)、[B-613](channel.md)；只有本條開關段新增未拍板行為。
