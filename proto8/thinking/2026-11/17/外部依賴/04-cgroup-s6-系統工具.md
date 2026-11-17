# 04 cgroup、s6 與其他系統工具

← [入口](../外部依賴.md)｜上一份 [03-cmake-或-makefile](03-cmake-或-makefile.md)｜下一份 [05-python-模組](05-python-模組.md)

**結論**：cgroup 只有 `aos-daemon` 用、只認 cgroup v2、預設關；開了但環境不行時 `auto` 會警告後照常跑、`on` 會拒絕啟動。**s6 核心不用**：daemon 的軟上限與換身分是自己用系統呼叫做的；會叫 s6 的只有選配指令 `aos-sandbox`。安裝腳本對這些只要「查一遍、印一張表」，少了不擋安裝。（本檔只讀程式，**cgroup 與 s6 都沒實跑**。）

## cgroup：誰用、怎麼用

| 項目 | 實況（出處都在 `impls/aos-daemon/src/`） |
|---|---|
| 版本 | **只認 v2**：讀 `/proc/self/cgroup` 的 `0::` 行，根＝`/sys/fs/cgroup<路徑>`；沒有 `0::` 行就是「no cgroup v2 entry」（`child/cgroup.cpp`） |
| 要哪些控制器 | 根的 `cgroup.controllers` 要有 `memory`、`pids` |
| 會寫哪些地方 | 在自己的 cgroup 底下建 `daemon/`（把自己搬進去）與 `procs/<名>/`（每個 proc 一格），開 `+memory +pids`；失敗只收回自己建的 |
| 拿來做什麼 | ① `mem_total_mb` → `memory.max`（有 `memory.swap.max` 就寫 0）② `procs_total` → `pids.max` ③ 收 proc 時 `cgroup.kill` 一次收掉整群 ④ 從 `memory.events`、`pids.events` 判斷是不是撞上限 ⑤ 重接舊 proc 時看 `cgroup.procs` |
| 要什麼權限 | daemon 自己的 cgroup 子樹要可寫＝**要委派**。repo 裡沒有自動包裝（`launch.json#/wrap` 沒實作）；文件教使用者自己包：`systemd-run --user --scope --collect -p Delegate=yes -- aos-daemon daemon.json`（`docs/09-份額.md`）；沒有 systemd 使用者管理員的環境要自己想辦法 |
| 開關 | `daemon.json` 頂層 `"cgroup"`：`"off"`（預設，不碰）／`"auto"`（試，不行就警告 `cgroup: none (<原因>)` 當 off）／`"on"`（不行就 `CfgBad`、退 1） |
| 沒有時其他鍵怎樣 | 寫了 `mem_total_mb`／`procs_total` 但 cgroup 沒開：proc 照起，只記 `limits_ignored`，警告一次 `… need cgroup (cgroup is off|none), ignored`；**不會退回 rlimit**。rlimit 系列的鍵跟 cgroup 無關，一律在子行程用 `setrlimit` 做 |
| 核心版本 | `cgroup.kill` 要 Linux 5.14+（公司 WSL 6.6；**沒實跑**） |
| 測試 | `test_cgroup.py`：`systemctl --user show-environment` 失敗就整組跳過；每例用 `systemd-run --user --scope -p Delegate=yes` 包 daemon |
| 安全備註 | proc 跟 daemon 同一個 uid，proc 自己也能改 cgroupfs；要擋得換子 uid（文件已寫） |

## s6：到底有沒有被用到

| 位置 | 用法 | 算不算依賴 |
|---|---|---|
| `impls/aos-daemon/src/child/limits.cpp` | 註解寫「照 s6-softlimit／s6-setuidgid 的做法」，**自己用系統呼叫做，不 exec s6** | 不算 |
| `cmd/aos-sandbox/bin/aos-sandbox` | 設了上限才在前面加 `s6-softlimit`；root 帶 `user` 加 `s6-setuidgid`；非 root 帶 `user` 走 `sudo -n -k /usr/local/bin/s6-setuidgid 帳號`；找不到就 `CommandMissing`、退 1（`--dry-run` 不擋） | **選配**（只有這支指令的這兩個功能） |
| `cmd/aos-sandbox/root/setup.sh` | root 手動跑：把 4 支 s6 工具抄進 `/usr/local/bin`、建 `aos-run` 帳號、`/srv/aos-run`、寫 sudoers 規則；s6 來源預設指向一份 **11-15 已刪的自編版** | 選配；預設來源已失效（邊緣狀況） |
| `impls/aos-daemon/examples/root/s6/run` | 給 s6-supervise 用的範例腳本，repo 裡沒人跑它 | 不算 |
| 測試 | `test_sandbox.py` 沒有 `/usr/local/bin/s6-setuidgid` 就跳過；`test_acceptance.py` 把一個已刪的路徑加進 PATH | 只影響測試 |
| 其他 | `docs/notes`、`docs/NORMS`、`CONCEPTS`、`knowledge/aos/cli/sandbox.json`、大量 `thinking/` 筆記 | 只在文件 |

s6-rc、execline、s6-svscan 在程式裡都沒被叫過。

## 安裝腳本怎麼檢查、怎麼講

推薦：**查、印表、不擋**（必需的缺了才退 1）。草稿輸出（程式輸出一律英文）：

```
required:
  ok   g++ 13.3 (C++20)        ok   make 4.3        ok   python3 3.12
optional (missing only disables the listed feature):
  ok      bwrap        aos-sandbox
  MISSING s6-softlimit aos-sandbox limits      -> install package "s6"
  MISSING s6-setuidgid aos-sandbox "user"      -> install package "s6", then cmd/aos-sandbox/root/setup.sh
  MISSING setfacl      aos-share               -> install package "acl"
  ok      tmux         agent screens (screen/ask/linger)
  ?       cgroup v2    aos-daemon "cgroup": "auto"/"on"  -> run under systemd-run --user -p Delegate=yes
  MISSING jsonschema   aos-comm check uses the builtin validator instead
```

| 檢查項 | 怎麼查（不用 root、不改系統） |
|---|---|
| 指令類（bwrap、s6-*、setfacl、tmux、newuidmap、git、claude、codex、node） | `shutil.which` |
| cgroup v2 | `/sys/fs/cgroup/cgroup.controllers` 存在＝有 v2；**不試寫**（要委派的話寫入結果跟安裝時的 shell 有關，查了也不準），只印「需要委派」的提示 |
| sudo 規則 | 不查（`sudo -n -l` 會留 log，也可能要密碼），只在 `aos-sandbox` 那列提示 setup.sh |
| jsonschema | `importlib.util.find_spec("jsonschema")` |

同一份檢查最好也能單獨跑（例 `install.py --check`），讓使用者裝完系統套件後重查，不用重編。
