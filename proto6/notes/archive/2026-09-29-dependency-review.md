> 封存 2026-09-29：拍板題已由裁定第十四批回答。由 [縮短版](../2026-09-29-dependency-review.md) 取代（決定＋現況＋比較）。

# 依賴盤點：如果依賴就停在這裡，是好是壞

← [筆記索引](../README.md)｜[規格入口](../../spec/README.md)｜[WSL 查證](../2026-09-29-wsl-machine-check.md)｜[systemd-run 延遲實測](../probes/systemd-run-latency.md)

2026-09-29。使用者的偏好是「外部依賴越少越好、留下的越穩越好」。本篇把 proto6 spec 目前實際用到的東西逐項列出來，看停在這裡好不好。只看、不改 spec。

標記：〔查證〕＝本機（Manjaro，kernel 6.18、systemd 261、git 2.55、Python 3.14）不用 sudo 實際跑過，或抄自 [WSL 查證](../2026-09-29-wsl-machine-check.md)；〔推論〕＝一般知識，沒在這兩台實測。本機查證原始輸出沒進 repo。

## 一、先講結論

- **大體是好的。** 必要的東西幾乎都是 Linux 本身（帳號、檔案權限、cgroup v2、Unix socket）加上 git 和 Python，沒有資料庫、沒有常駐的第三方服務。LiteLLM、SQLite 都已經拿掉。
- **但「標配」不等於「開箱可用」。** 真正會讓人卡住的不是裝不裝得到，而是要**另外設定**：systemd 使用者層的 cgroup 委派、WSL 要開 systemd、project quota 要專用磁碟、多帳號之間的群組／ACL、每個帳號的 git 設定。
- **有幾個依賴 spec 沒寫、卻一定會用到**：第三方 `jsonschema`（還連帶一個用 Rust 編的套件）、「不覆蓋」的 rename、git 的 `safe.directory` 與作者設定、HTTPS 要的憑證包。這些要補進清單。
- **可以再砍**：磁碟 quota、tmpfs 掛載、ACL、執行期的第三方 jsonschema。砍掉的代價都不大。

## 二、依賴清單（核對後）

「必要」＝少了整套不能跑；「實質必要」＝spec 寫成可選，但別的條文沒它做不到；「可選」＝不用就少一個功能。

### 2.1 Linux kernel 功能

分三小塊：身分、權限與磁碟；程序與資源；檔案與時間。

#### 身分、權限與磁碟

| 項目 | 拿來做什麼 | 必要？ | 穩定度與坑 | 退路 |
|---|---|---|---|---|
| 帳號／UID、setresuid、setgroups、initgroups | 一 node 一帳號；helper 切身分；補充群組照系統設定（[inst](../../spec/base/inst.md)） | 無 helper 模式只用一個帳號；隔離時必要 | 幾十年沒變。坑：帳號查詢走 NSS，接 LDAP／sssd 的機器查詢可能慢或斷線〔推論〕 | 不要隔離就全樹一個帳號 |
| 檔案權限、chown | 各 node 資料夾歸自己帳號；投件目錄開寫權 | 必要 | 極穩。坑：WSL 的 `/mnt/c` 沒有 metadata，全部 777、UID 1000〔查證〕 | node 樹不能放 `/mnt/c` |
| 共享群組、setgid 目錄 | 投件者能寫別人的 `requests/`（[P-208](../../spec/settled/protocol/node.md)） | 多帳號時必要 | 極穩 | — |
| POSIX ACL | spec 寫「共享群組**或** ACL」，給部署者選 | 可選（初步清單列成必要，其實不是） | ext4／xfs／btrfs／tmpfs 預設都支援；本機 `setfacl` 實測可用〔查證〕。WSL `/mnt/c` 不支援〔推論〕 | 只用群組 |
| 磁碟 project quota | 磁碟 module 的「計量歸屬」，只記帳不設上限（[P-107](../../spec/settled/protocol/daemon/provision-and-runner.md)） | 可選 | **最麻煩的一項**：ext4 要 `project` feature＋`prjquota` 掛載，根分割區開不了；兩台機器根目錄都是 `noquota`；WSL 要另做 loop 映像〔查證〕。擁有者可以用 `chattr -p` 自己改 project ID 逃掉記帳（notes-review 已提） | 改成掃目錄算用量（見第四節） |
| mount（tmpfs） | helper 在授權空目錄掛 tmpfs | 可選 | 要 root。WSL 的 `/tmp` 本來就不是 tmpfs〔查證〕 | 拿掉，暫存就在磁碟 |

#### 程序與資源

| 項目 | 拿來做什麼 | 必要？ | 穩定度與坑 | 退路 |
|---|---|---|---|---|
| cgroup v2 | 資源框、限制、量用量、OOM 證據、**殺乾淨整個程序樹** | **實質必要**：資源 module 可選，但 [B-202](../../spec/base/execution.md)「後代要能驗證全空」與 [B-603](../../spec/settled/daemon.md) 重啟全殺，沒有 cgroup 做不到可靠版本 | 主流發行版 2021 年後預設純 v2（Fedora 31+、Ubuntu 21.10+、Debian 11+、RHEL 9+）〔推論〕。本機與 WSL 都是純 v2〔查證〕；**RHEL 8、Ubuntu 20.04 這類舊系統預設 v1／混用，整套不能跑**〔推論〕 | 見第三節第一名 |
| cgroup.kill、pids.events、memory.events | 一次殺光、判斷 OOM／fork 失敗 | 實質必要 | `cgroup.kill` 要 kernel 5.14〔推論〕，本機有〔查證〕。WSL 發現父層 `pids.events` 不準，要看子層〔查證〕 | 舊 kernel 改成反覆讀 `cgroup.procs` 逐個殺 |
| Unix socket＋SO_PEERCRED | daemon IPC 認人 | 必要 | 極穩。坑：socket 路徑上限約 107 bytes | — |
| socketpair SEQPACKET＋SCM_RIGHTS | daemon 與 helper 私有通道、傳 fd（[P-108](../../spec/settled/protocol/daemon/provision-and-runner.md)）；初步清單沒列 | helper 模式必要 | 極穩 | — |
| memfd＋封印（seal） | helper 收到的「密封 inst 快照 fd」；初步清單沒列 | helper 模式必要 | kernel 3.17 起就有〔推論〕 | 改成唯讀暫存檔，但要多防替換 |
| prctl `PR_SET_PDEATHSIG` | daemon 死了 helper 跟著死；初步清單沒列 | helper 模式必要 | 極穩，但 Python 標準庫沒有，要走 ctypes 叫 glibc〔推論〕 | 靠管道斷線偵測（spec 已要求兩者並用） |
| signal、pidfd | TERM→2 秒→KILL；安全地指到某個程序 | 必要／pidfd 是「例如」 | pidfd_open 要 kernel 5.3〔推論〕；Python 3.9 起有 `os.pidfd_open`，本機有〔查證〕 | pidfd 可省，靠 cgroup 殺 |
| boot_id、`/proc/<pid>/stat` starttime | 跨重啟認程序、發現重開機 | 必要 | 穩。坑：WSL 只終止 distro 時 boot_id 變不變，還沒查〔查證：WSL 筆記列為未查〕；`/proc` 掛 `hidepid` 時看不到別人的程序〔推論〕 | — |

#### 檔案與時間

| 項目 | 拿來做什麼 | 必要？ | 穩定度與坑 | 退路 |
|---|---|---|---|---|
| flock | 每個 node 一把 tick 鎖（[P-203](../../spec/settled/protocol/node.md)） | 必要 | 本機檔案系統上極穩。NFS、9p、drvfs 上語意不可靠〔推論〕 | node 樹只放本機檔案系統 |
| rename＋fsync（含目錄） | 完整發布收件 | 必要 | 極穩。**坑：spec 要「不覆蓋已有檔」，普通 rename 會覆蓋**，見第四節 | 用 link 或 renameat2 |
| inotify | 只當門鈴，可遺失 | 可選 | 穩。坑：每帳號 watch 上限（本機 524288、instance 1024〔查證〕，舊 kernel 預設 8192〔推論〕）；`/mnt/c` 沒有〔查證〕 | 不用，靠 IPC 叫醒＋定期補查 |
| network namespace | 只當網路用量的量測範圍 | 可選 | 首版不限速 | 不裝網路 module |
| monotonic 時鐘 | 逾時 | 必要 | WSL 上比牆鐘慢約 4%、睡醒牆鐘大跳〔查證〕 | spec 已改用序號排先後 |
| Landlock、seccomp | **spec 沒用**；只在 notes 當候選外牆 | 不算依賴 | WSL 只有 Landlock ABI 3〔查證〕 | — |

### 2.2 系統程式

| 項目 | 拿來做什麼 | 必要？ | 穩定度與坑 | 退路 |
|---|---|---|---|---|
| systemd（使用者層） | 無 helper 時提供「委派給我的 cgroup 子樹」（[P-107](../../spec/settled/protocol/daemon/provision-and-runner.md)）；方向上還要管定時、開程序 | 實質必要 | systemd 本身極穩。**坑都在設定**：要 `user@` 有 `Delegate`（本機預設 cpu／memory／pids，沒有 io〔查證〕）；使用者沒登入時要 linger 才有 user manager（本機已開〔查證〕）；`systemd-run --user` 要走使用者 D-Bus 與 `XDG_RUNTIME_DIR`〔推論〕；WSL 從 `wsl.exe` 進來的 shell 在 `/init.scope`，不在委派樹裡〔查證〕 | helper 模式改用系統層 systemd；沒 systemd 見第三節 |
| systemd（系統層） | 開機拉起 daemon；可選 `CapabilityBoundingSet`、`SystemCallFilter`；方向上的 `systemd-run --uid` | helper 模式實質必要 | 同上。WSL 要在 wsl.conf 開 `systemd=true`（公司機已開，255 版）〔查證〕 | 手動 sudo 前景開 |
| sudo | 「用 sudo 開＝有 helper」，並用 `SUDO_UID` 找原帳號 | 可選（不隔離就不用） | 極穩。坑：doas 不設 `SUDO_UID`〔推論〕；本機有 `run0`〔查證〕，它設不設 `SUDO_UID` 未查 | spec 已允許在設定檔明寫通用帳號 |
| git | node 狀態、group 提交與還原、同一 commit 讀摘要 | 必要 | 核心指令十幾年沒變。坑見第四節（作者設定、safe.directory、hooks、殘留 index.lock） | 無，這是狀態模型本身 |
| useradd／groupadd | helper 的 `account_create` | helper 模式必要 | 極穩（shadow-utils）。坑：帳號「不建 home」會連帶影響 git 設定 | 部署者手動先建帳號 |
| setfacl | 選 ACL 路線才要；Python 標準庫沒有 ACL 介面 | 可選 | `acl` 套件幾乎都有，本機有〔查證〕 | 只用群組 |
| setquota／xfs_quota | quota 路線才要 | 可選 | 本機只有 `xfs_quota`、沒有 `setquota`；WSL 兩個都沒裝〔查證〕 | 掃目錄 |

### 2.3 語言環境與函式庫

| 項目 | 拿來做什麼 | 必要？ | 穩定度與坑 | 退路 |
|---|---|---|---|---|
| Python 3 | [CLI 走查](../../spec/cli.md)前置寫明「Python 3」；proto5 全用標準庫＋sqlite3，proto6 已不用 SQLite | 必要（spec 沒寫死語言，但走查與範例都是 Python） | 3.x 小版本每年一版、舊版五年停支援。坑：每開一次程序約 5.6 ms〔查證：延遲實測〕，冷 node 多時控制層 CPU 會上來（notes-review 量到閒置約 4%） | 熱路徑（tick、runner）以後可換編譯語言 |
| Python 標準庫 json、socket、fcntl、subprocess、urllib、ssl | JSON、IPC、鎖、開程序、HTTP | 必要 | 極穩 | — |
| 第三方 `jsonschema` | spec 的正反例驗證（[validate.py](../../spec/protocol/examples/messages/validate.py)）；**執行期**也要驗工具參數（[agent 工具](../../spec/agent/tools.md)「參數不合 schema 不派工」） | 規格測試必要；執行期是暗中依賴 | 它再拉 `attrs`、`referencing`、`jsonschema-specifications`、`rpds-py`（Rust 編的）〔查證：pip show〕。validate.py 用的 `RefResolver` 已被標為將移除〔查證：DeprecationWarning〕 | 執行期自寫小型子集驗證器 |
| OpenSSL＋CA 憑證包＋DNS | HTTPS 打 LLM | 用 LLM 就必要 | 系統標配。坑：精簡容器常缺憑證包〔推論〕 | 本機 HTTP endpoint 不需要 |
| glibc | ctypes 叫 prctl／renameat2 等 | 暗中必要 | 本機 2.44〔查證〕。musl（Alpine）行為略有差〔推論〕 | 不支援 musl |

## 三、整體評價

### 3.1 標配 vs 要另外設定

| 幾乎每台現代 Linux 都有、不用動 | 有東西，但要另外設定才能用 |
|---|---|
| 帳號、權限、群組、Unix socket、signal、flock、rename、fsync、inotify、monotonic | systemd 使用者層委派＋linger（無 helper 模式的資源框靠它） |
| cgroup v2（2021 年後的發行版） | WSL：wsl.conf 開 systemd、關 interop、收緊 automount；daemon 要用 systemd unit 開 |
| systemd、git、Python 3、sudo、useradd、setfacl | project quota：要專用分割區或 loop 映像，還要裝工具 |
| OpenSSL 與憑證包 | 多帳號交接：每個投件目錄的群組或 ACL、setgid |
| | 每個 node 帳號的 git 作者設定與 `safe.directory` |
| | 第三方 `jsonschema`（要 pip 或套件管理器另裝） |

好在哪：左欄是「幾十年沒變的 Linux 基本功」，和使用者的偏好完全一致；沒有資料庫、沒有常駐第三方服務，LLM 也不綁 LiteLLM。
壞在哪：右欄每一項都要人動手，而且**設錯時多半不會立刻壞**，是在某次重開、某個新帳號、某台新機器上才出事。

### 3.2 最脆弱的前三名

1. **systemd 使用者層的 cgroup 委派這條鏈。** 「殺乾淨整個程序樹」「重啟先全殺」都靠它，但它要 user manager 在跑（linger）、要委派對的 controller、daemon 要真的被開在委派樹裡（WSL 從 `wsl.exe` 開就不在）、`systemd-run --user` 還要 D-Bus。任一環沒接上，daemon 就只能管自己開的直接子程序。
   - 退路：①有 helper 時改用系統層 systemd 或 helper 自己建 cgroup；②沒 systemd 的機器，由 root 一次性把某個 cgroup 子目錄 chown 給 daemon 帳號（委派本來就是 kernel 功能，systemd 只是代辦）；③最後手段是「子程序收養者（subreaper）＋讀 `/proc`」，但 daemon 一重開就追不到，保證明顯變弱，要老實標出來。
   - 無論哪條，啟動時都要自檢「我在不在可寫的 cgroup 子樹裡」，做不到就照 [B-302](../../spec/base/identity-resources.md) 明確報錯。
2. **磁碟 project quota。** 要特定檔案系統、特定掛載選項、另裝工具、根分割區通常開不了、WSL 要做映像，而且擁有者自己就能逃掉記帳。它換來的只是「記帳」，不是上限。
   - 退路：磁碟 module 改成定期掃 node 資料夾算大小；spec 本來就說只記帳，語意不變。
3. **多帳號之間的檔案交接。** 群組／ACL、setgid、git 的 `safe.directory`、無 home 帳號的 git 作者設定，四件事要一起對，錯一件就是「權限被拒」或「git 拒絕讀別人的 repo」。WSL 的 `/mnt/c` 則是整個權限模型失效。
   - 退路：首版只用群組＋setgid（不用 ACL）；aos 呼叫 git 時一律用命令列帶齊設定（見第四節），不靠各帳號的 `~/.gitconfig`；node 樹啟動自檢檔案系統類型。

次一名是第三方 `jsonschema`：它不在系統裡、會跟著 pip 版本變、還帶一個編譯套件。

### 3.3 可以再砍的依賴

| 砍掉什麼 | 改用什麼 | 代價 |
|---|---|---|
| project quota＋`setquota`／`xfs_quota`＋專用磁碟＋helper 的 `quota` 動作 | 磁碟 module 定期走訪 node 資料夾算大小（像 `du`） | 大樹走一次要時間與 I/O；數字有延遲；硬連結可能重算。但 quota 本來也只記帳，承諾不變 |
| helper 的 `mount`（tmpfs） | 不掛，暫存就在磁碟；要的話在 helper 模式用 systemd 的 `PrivateTmp` 類設定 | 暫存吃磁碟不吃記憶體；WSL 本來就這樣 |
| ACL（和 `setfacl`） | 只用共享群組＋setgid 目錄 | 群組變多（每個收件區一個）；改群組要 helper；新群組下一格才生效 |
| 執行期的第三方 `jsonschema` | 自寫只支援常用關鍵字的驗證器；spec 已寫「不支援的規則要拒絕」，本來就允許子集 | 要寫、要測；少數複雜工具 schema 會被拒。規格正反例仍可用 jsonschema 跑，那只是開發工具 |
| `systemd-run`（每次開程序都經過 systemd） | systemd 只負責「開機拉起 daemon＋委派一棵 cgroup 子樹」，daemon 自己在子樹裡建框、寫限制——**P-107 的無 helper 模式本來就這樣寫** | 跟「站在 systemd 上、不重造輪子」的方向有張力；要自己寫殺樹與寫限制（量不大）。好處是執行期不用 D-Bus、每次省 5～25 ms〔查證：延遲實測〕 |
| inotify | IPC 叫醒＋kernel 定期補查 | 外部直接丟檔時反應變慢；spec 已把它定為可遺失的門鈴 |
| 「sudo」這個名字 | 寫成「用 root 開（sudo、run0 或系統服務）」，原帳號從 `SUDO_UID` 或設定檔來 | 幾乎沒有；只是改字 |

砍不掉的：git（它就是狀態模型）、cgroup v2（殺乾淨靠它）、帳號與權限、Unix socket、Python（除非換語言）。

## 四、看起來沒列、其實暗中依賴

| 暗中依賴 | 從哪冒出來 | 坑 |
|---|---|---|
| 「不覆蓋」的發布 | [P-003](../../spec/protocol/README.md)「rename 不覆蓋已有檔」 | 普通 rename 會蓋掉。要用 hard link（proto5 就這樣做）或 `renameat2(RENAME_NOREPLACE)`；Python 標準庫沒有 renameat2〔查證：`os.renameat2` 不存在〕，只能 ctypes；兩者都要檔案系統支援 |
| 本機 POSIX 檔案系統 | flock、rename、inotify、UID、ACL 全部假設 | node 樹放 NFS、9p、`/mnt/c` 會一起出問題；spec 只說 Windows 掛載「不在保護承諾內」，沒說**不准放** |
| 最低 kernel 版本 | pidfd 5.3、CLONE_INTO_CGROUP 5.7、cgroup.kill 5.14〔推論〕 | 實際下限約 5.14。RHEL 9、Ubuntu 22.04 以上、WSL 6.6 都過〔WSL 查證，其餘推論〕 |
| 最低 Python 版本 | `pidfd_open`、`send_fds` 要 3.9〔推論〕 | spec 只寫「Python 3」 |
| git 作者設定 | [P-205](../../spec/settled/protocol/node.md)「作者用 repo 設定」；CLI 走查要求「git 作者已設」 | helper 建的帳號「不建 home」，就沒有 `~/.gitconfig`，第一次 commit 就失敗。要在 repo 內設，或用環境變數帶 |
| git `safe.directory` | kernel 要「固定同一 commit 讀」成員的 repo | git 2.35.2 起，讀別的帳號擁有的 repo 會被拒（「dubious ownership」）〔推論〕。要替讀者帳號設例外 |
| git hooks 與系統設定 | P-205「不執行 git hooks」 | `--no-verify` 擋不住所有 hook，要改 `core.hooksPath`；`/etc/gitconfig` 也能偷塞設定，可用 `GIT_CONFIG_NOSYSTEM=1` 關掉〔推論〕 |
| 殘留的 `index.lock` | 當機時 git 正在寫 | 下一格 commit 直接失敗；恢復流程要能安全清掉 |
| D-Bus 與 `XDG_RUNTIME_DIR` | 方向上的 `systemd-run --user` | 用 cron、ssh 無登入環境開 daemon 時常缺〔推論〕 |
| swap | memory 限制 | 沒設 `memory.swap.max=0`，超量會被擠進 swap 而不是被殺〔查證：WSL〕 |
| HTTPS 憑證包 | LLM 呼叫 | 見 2.3 |

## 五、需要使用者拍板的問題

> 已裁定，見 [verdicts 第十四批](../verdicts/05-dependencies.md#第十四批依賴同日晚已落進-spec)。

只列問題和建議，決定權在使用者。

1. **磁碟記帳要不要砍掉 quota，改成定期掃資料夾？** 建議：砍。quota 是本清單最難設定、最容易逃掉的一項，而它只換到記帳。
2. **systemd 的「最低必要範圍」劃在哪？** 選項：甲、只要求「開機拉起 daemon＋委派一棵 cgroup 子樹」，`systemd-run` 當可選實作；乙、每次開程序都走 `systemd-run`。建議：甲當必要底線、乙當實作選擇，這樣執行期不綁 D-Bus。（「daemon 站在 systemd 上」是使用者的方向，這題只問底線畫多低。）
3. **沒有 systemd 的 Linux（Alpine、多數容器、沒開 systemd 的 WSL）支不支援？** 建議：首版不支援，啟動時自檢並清楚報錯；留「root 手動委派 cgroup」當文件上的退路。
4. **多帳號交接首版只准群組，還是也寫 ACL？** 建議：只寫群組＋setgid，ACL 留給部署者自選、spec 不承諾。
5. **執行期驗工具參數：用第三方 jsonschema，還是自寫子集？** 建議：自寫子集；jsonschema 只留在規格測試。
6. **要不要把最低版本寫進 spec 並做啟動自檢？**（kernel ≥ 5.14、Python ≥ 3.9、git ≥ 2.35、cgroup 純 v2、systemd 能委派 cpu／memory／pids） 建議：要。systemd 的確切下限還沒查，先寫「能委派這三個 controller」。
7. **helper 的 `mount`（tmpfs）動作要不要留？** 建議：首版拿掉。
8. **node 樹放哪種檔案系統要不要明文限制？** 建議：明文只支援本機 ext4／xfs／btrfs（tmpfs 可測試用），拒絕 `/mnt/c`、NFS、9p，啟動時檢查。
9. **「用 sudo 開」要不要改寫成「用 root 開」？** 建議：改，並查 `run0` 是否設 `SUDO_UID`；沒設就走設定檔明寫通用帳號那條路。
