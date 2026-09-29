# 依賴盤點：決定、現況與還用得到的比較

← [筆記索引](README.md)｜裁定：[第十四批](verdicts/05-dependencies.md#第十四批依賴同日晚已落進-spec)｜[規格入口](../spec/README.md)｜[WSL 查證](2026-09-29-wsl-machine-check.md)｜[systemd-run 延遲實測](probes/systemd-run-latency.md)

2026-09-29。使用者的偏好是「外部依賴越少越好、留下的越穩越好」。原本的盤點（逐項依賴表、最脆弱前三名、拍板題）已封存，見 archive/2026-09-29-dependency-review.md（已封存檔 2026-09-29-dependency-review.md，索引見 [archive/README.md](archive/README.md)）。本頁只留決定、現況與以後還用得到的比較。

標記：〔查證〕＝本機（Manjaro，kernel 6.18）或公司 WSL 實際跑過；〔推論〕＝一般知識，沒實測。

## 決定（第十四批與追加，已落進 spec）

- **Python 盡量只用標準庫**；唯一例外是執行期驗工具參數用第三方 `jsonschema`（不自寫子集）。
- **cgroup v2 是必要依賴。** 殺乾淨整個程序樹、重啟先全殺都靠它。
- **quota、systemd 都是可選**：有就用，沒有就用 aos 自帶的土方法（磁碟用量定期掃資料夾；程序由 daemon 自己管）。**初版不用 systemd**；以前「交給 systemd」的做法都改讀成「有 systemd 時的做法」。
- **沒有 systemd 的 Linux 也要能跑**，降級執行，不在啟動時拒絕。
- **多帳號交接首版只用群組＋setgid**，不用 ACL；**tmpfs 首版拿掉**。
- **檔案系統不設白名單**：放在不支援某些功能的地方，那些功能就不支援。
- **「用 sudo 開」不改名。**
- 遠期方向（只記錄）：aos 基底之後希望改用 C++11 乃至 C99，agent 這塊才引入 Python。

細節與追加題（最低版本自檢、cgroup 子樹來源、daemon 當掉後清程序）見 [裁定第十四批](verdicts/05-dependencies.md)。

## 現況：必要的依賴

| 類別 | 項目 |
|---|---|
| Linux kernel | 帳號／UID、檔案權限、共享群組與 setgid、cgroup v2（含 `cgroup.kill`）、Unix socket＋SO_PEERCRED、flock、rename＋fsync、boot_id 與 `/proc` starttime |
| helper 模式另需 | socketpair＋SCM_RIGHTS、memfd 封印、`PR_SET_PDEATHSIG`（Python 要走 ctypes）、useradd／groupadd |
| 程式 | git（狀態模型本身，砍不掉）、Python 3 標準庫、sudo（只在隔離時） |
| 用 LLM 時 | OpenSSL、CA 憑證包、DNS |

可選：project quota、inotify（只當門鈴）、network namespace、systemd。

## 還用得到的比較

### 暗中依賴（spec 沒明列、實作時一定會撞到）

- **「不覆蓋」的發布**：普通 rename 會蓋掉已有檔；要用 hard link（proto5 做法）或 `renameat2(RENAME_NOREPLACE)`（Python 標準庫沒有，只能 ctypes）〔查證〕。
- **最低 kernel 約 5.14**（pidfd 5.3、CLONE_INTO_CGROUP 5.7、cgroup.kill 5.14）〔推論〕；RHEL 8、Ubuntu 20.04 這類預設 v1／混用的舊系統整套不能跑。Python 要 3.9 以上（`pidfd_open`、`send_fds`）。

git 相關：

- **git 作者設定**：helper 建的帳號不建 home 就沒有 `~/.gitconfig`，第一次 commit 就失敗；要在 repo 內設或用環境變數帶。
- **git `safe.directory`**：2.35.2 起讀別帳號擁有的 repo 會被拒〔推論〕；kernel 讀成員 repo 要設例外。
- **git hooks 與系統設定**：擋 hook 要改 `core.hooksPath`；`GIT_CONFIG_NOSYSTEM=1` 關掉 `/etc/gitconfig`〔推論〕。
- **殘留 `index.lock`**：當機時留下會讓下一格 commit 失敗，恢復流程要能安全清掉。

其他：

- **swap**：沒設 `memory.swap.max=0`，超量會被擠進 swap 而不是被殺〔查證：WSL〕。
- **本機 POSIX 檔案系統**：flock、rename、inotify、UID 都假設它；NFS、9p、`/mnt/c` 會一起出問題（`/mnt/c` 全部 777、UID 1000〔查證〕）。

### 砍掉某些依賴的代價

| 砍掉 | 改用 | 代價 |
|---|---|---|
| project quota | 定期走訪 node 資料夾算大小 | 大樹走一次要時間與 I/O、數字有延遲、硬連結可能重算；但 quota 本來也只記帳 |
| ACL | 共享群組＋setgid | 群組變多；改群組要 helper、下一格才生效 |
| tmpfs 掛載 | 暫存直接放磁碟 | 暫存吃磁碟不吃記憶體；WSL 的 `/tmp` 本來就不是 tmpfs |
| `systemd-run` | daemon 自己在 cgroup 子樹裡建框、寫限制 | 要自己寫殺樹與寫限制（量不大）；好處是不用 D-Bus、每次省 5～25 ms〔查證〕 |
| inotify | IPC 叫醒＋定期補查 | 外部直接丟檔時反應變慢 |

### 最容易設錯的地方

設錯時多半不會立刻壞，是在某次重開、某個新帳號、某台新機器上才出事：

1. **cgroup 子樹從哪來**：有 systemd 時要 linger、委派對的 controller、daemon 要真開在委派樹裡（WSL 從 `wsl.exe` 進來的 shell 在 `/init.scope`，不在委派樹裡〔查證〕）；沒有 systemd 時要 root 一次性把某個 cgroup 子目錄交給 daemon 帳號。啟動時都要自檢。
2. **多帳號交接**：群組、setgid、`safe.directory`、無 home 帳號的 git 作者設定，四件要一起對。
3. **第三方 `jsonschema`**：不在系統裡、會跟 pip 版本變，還連帶一個 Rust 編的套件（`rpds-py`）〔查證〕。
