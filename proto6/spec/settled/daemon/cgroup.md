# daemon cgroup：框、上限與啟動自檢

← [daemon 目錄](README.md)｜[整理區](../README.md)

## B-605：依賴與啟動自檢

**tick 核心不需要 cgroup；daemon 有 cgroup 就用、沒有就退回 runner 那一套**（B-601、B-604）。cgroup 給 daemon／helper（node 框與資源上限）與普通程式 `aos-cg`（每項一框，[B-634](../tick.md)）用。

- 撤掉的：第十四、十五批「沒 cgroup v2 就拒絕啟動」；第十九批的「沒 cgroup 走備援、降到備援級」「完整路／備援路」與啟動時印 `standard: cgroup=…`。
- 初版不使用 systemd 當執行期依賴；systemd 只當取得委派子樹、開機自動啟動的方式（下面與文末附錄）。

依據：第十九批（推翻第十四、十五批）；第二十批追答 8；納入 cgroup 與 git 的疑點裁定。

### 啟動自檢

- **daemon 自己的最低需求**：Python 3.9；不合就報錯退出（125）。
- **不查 git**：git 只有任務表上的 `aos-git` 會用（[B-630](../tick.md)），daemon 不查。
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
| 2 | 使用者層 service：固定單位名、`Delegate=yes`，對該帳號 `loginctl enable-linger` | 不用 | 開機自動啟動用這個；框路徑固定，重啟時 systemd 也會先殺舊程序（文末附錄） |
| 3 | 系統層 service：root 開、`Delegate=yes` | 要 | 有 helper（文末附錄） |
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

〔使用者方向 2026-09-30，第十八批 Q19；納入 cgroup 與 git 疑-7「准」〕node 可以在自己的 `n-<h>` 下另開子框（名字避開保留名），把程序搬進去、刻意留常駐程序。**這不在 aos 的管轄範圍內，aos 不管**，跟「通道是唯一逃生口」（[T-07](../terms.md)）不算衝突。

- 格後收尾只看 `tick` 與 `task-*`，不碰這些子框（B-601）。
- daemon 重啟（B-603）與解除登記（B-606）時殺不殺，照設定 `kill_escape_cgroups`：預設 false，不殺、框留著；設成 true 就一併收尾（[P-101](../protocol/daemon/startup-and-ipc.md)）。
- 逃生口的程序仍在 node 框裡，照樣受 node 的資源上限管。框裡還有逃生口時 `n-<h>` 刪不掉：解除登記照樣完成、框留著並寫該 node 的事項，等之後空了由 B-603 的空框清理刪。
- 沒有 cgroup 時沒有框，也就沒有這種逃生口；runner 清不到的常駐程序（例如經外部服務開的）本來就不歸 daemon 管（B-601）。
- 要 daemon 追得到、`node.kill` 砍得掉的常駐程序，用通道 `node.mount` 掛（B-613）。

### 中途失效：只影響那個 node

〔建議預設〕daemon 啟動時 `cgroup=on`，之後某個 node 建框或交框失敗（上層關了 controller、權限被改、`cgroup.max.descendants` 滿了）：那個 node 照沒有 cgroup 的做法跑（B-601），寫一件該 node 的事項；別的 node 照常。不整個 daemon 降級，也不停那個 node。之後建得起來就改回用框。

### 有就用的其他功能

- project quota 等功能在啟動時自動偵測，設定檔可強制關（P-101 的 `disable`，可熱重載，B-608）。
- 沒有 quota 時，磁碟用量由磁碟資源任務定期量（[B-304](../../base/identity-resources.md)、[S-203](../../scheduling/admission.md)）。
- 檔案系統不限定：node 放在不支援某些功能的地方，那些功能就不支援；不列白名單或拒絕清單。

依據：使用者方向 2026-09-29 晚。

### 初版不做

systemd 的沙盒防護（`CapabilityBoundingSet` 等）以後再考慮；helper 掛 tmpfs 拿掉；原本打算交給 systemd 的開程序、定時叫醒等做法，初版全由 daemon 自己做（使用者方向 2026-09-29 晚）。

**驗收：**Python 低於 3.9 時啟動報錯退出。Linux 低於 5.14、沒有純 cgroup v2、WSL 在 `/init.scope` 直接跑、或用沒加 `Delegate=yes` 的 scope 開時，daemon 照常啟動、印 `cgroup=off`、照常開格，stdout 沒有 `standard:` 行；照首推用 `systemd-run --user --scope -p Delegate=yes` 開、不寫 `cgroup_root` 時印 `cgroup=on`；省略 `cgroup_root`、或有寫但該層有程序時，原層只剩子層、沒有程序；明寫 `cgroup_root` 卻沒準備好、也沒開 `--create-cgroup` 時報錯退出（125），不自己建；開了 `--create-cgroup` 卻沒寫 `cgroup_root` 時用法錯（2），建不了時報錯退出；某個 node 建框失敗時只有它照沒有 cgroup 跑、有一件事項；node 自己開的子框裡的程序，格後與重啟時都不被收（`kill_escape_cgroups` 省略時）；偵測得到 quota 但設定強制關時不使用。

