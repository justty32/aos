aos-daemon 的鎖跟 Codex 的 Linux 沙箱、Anthropic sandbox-runtime（srt）逐條對照：seccomp 擋單、namespace、其他鎖三張表，加進擋單的、給使用者挑的、從他們的測試改寫過來的測項（11-27）。

# aos-daemon 對照 Codex、srt（11-27）

← [aos-daemon README](README.md)｜起因：使用者 11-27 定「照 A」（aos-daemon 照最小方案自己做、零件挑輪子），找輪子報告建議「擋單和測項跟 Codex、srt 逐條對照」

## 對照的是哪一版

| | 版本 | 讀了哪些檔 |
|---|---|---|
| **Codex** | `openai/codex` commit `fe6dca34229d9db8f5be09f7dc4b99c2de9ee44e`（2026-11-27） | `codex-rs/linux-sandbox/` 的 `src/seccomp.rs`、`src/bwrap.rs`、`src/linux_run_main.rs`、`src/launcher.rs`、`README.md`，測試 `src/seccomp_tests.rs`、`src/bwrap_tests.rs`、`src/linux_run_main_tests.rs`、`tests/suite/*.rs`；`.git` 等名字定在 `codex-rs/protocol/src/permissions.rs` |
| **srt** | `anthropic-experimental/sandbox-runtime` commit `0bbebed0aa9a8e628dc4df8bc30293550a1988eb`（2026-11-12），`package.json` 0.0.83 | `src/` 的 Linux 部分（`linux-sandbox-utils.ts`、`sandbox-utils.ts`、`generate-seccomp-filter.ts`）、`vendor/seccomp-src/seccomp-unix-block.c`、`vendor/seccomp-src/apply-seccomp.c`，測試 `test/sandbox/` |

- 用 `gh api` 讀原始碼，沒有 clone、沒有執行他們的任何東西。兩邊都是 Apache-2.0；**本 repo 沒有逐字抄他們的程式碼**，測試是照意思自己寫的，旁邊註明 `idea from …`。
- 我們這邊照 11-27 這輪改完的 aos-daemon（內建擋單 44 個＋`personality` 看參數＋`AF_VSOCK`）。

**做法上最大的不同**（先講，下面的表才看得懂）：Codex 與 srt 都是「包一條指令」的工具，底下用 bwrap，**從整台主機唯讀看得到（`--ro-bind / /`）開始，再把不准的地方遮掉**；網路走它們自己的代理。aos-daemon 是**天空從零組**（沒放的就不存在）、一直開著的 daemon、每隻 proc 一個 Landlock domain。所以他們有很多「遮哪些路徑」的規則（`.git`、`.bashrc`、憑證檔），我們這邊對應的是「天空表裡放不放、放唯讀還是可寫」，由起 proc 的人（以後的 `aos-pi`）決定。

## 表一：seccomp

三邊都是「預設放、列的擋」，擋的回 `EPERM`（srt 的 `clone3` 回 `ENOSYS`）。Codex 依網路設定有四種模式，表裡寫最常見的 Restricted（沒網路、沒代理），別的模式不同時另外寫。

| 系統呼叫 | aos-daemon | Codex | srt |
|---|---|---|---|
| `init_module`、`finit_module`、`delete_module`、`create_module`、`get_kernel_syms`、`query_module` | 擋 | 不擋 | 不擋 |
| `kexec_load`、`kexec_file_load`、`reboot` | 擋 | 不擋 | 不擋 |
| `swapon`、`swapoff` | 擋 | 不擋 | 不擋 |
| `settimeofday`、`clock_settime`、`clock_adjtime`、`adjtimex` | 擋 | 不擋 | 不擋 |
| `acct`、`quotactl`、`quotactl_fd` | 擋 | 不擋 | 不擋 |
| `bpf`、`perf_event_open`、`userfaultfd` | 擋 | 不擋 | 不擋 |
| `keyctl`、`add_key` | 擋 | 不擋 | 不擋 |
| `request_key` | 擋 | **擋**（理由：主機上的幫手程式會替它連網；只有 VmSocketRestricted 模式不擋） | 不擋 |
| `ptrace`、`process_vm_readv`、`process_vm_writev` | 擋 | **擋**（VmSocketRestricted 模式除外） | 不擋（命令跑在自己的 PID namespace 當 2 號、外層幫手設 dumpable 0，看不到也碰不到） |
| `kcmp`、`pidfd_getfd` | 擋 | 不擋 | 不擋 |
| `open_by_handle_at`、`name_to_handle_at`、`lookup_dcookie` | 擋 | 不擋 | 不擋 |
| `iopl`、`ioperm`、`syslog` | 擋 | 不擋 | 不擋 |
| `uselib`、`vhangup`、`nfsservctl`、`_sysctl` | 擋 | 不擋 | 不擋 |
| `move_pages`、`migrate_pages` | 擋 | 不擋 | 不擋 |
| `io_uring_setup`、`io_uring_enter`、`io_uring_register` | 擋 | **擋**（每種模式；理由：io_uring 不經 `socket()` 也開得出 `AF_VSOCK`） | **擋** |
| `personality` | 只放 Docker 那五個值 | 不管 | 不管 |
| `socket`／`socketpair` 的 `AF_VSOCK` | **擋（11-27 新加）** | **擋**（每種模式） | `socket` 擋；`socketpair` 不管（核心本來就不支援） |
| `socket` 的 `AF_UNIX` | 放 | Restricted 放；代理模式擋（設定可開） | **擋**（`allowAllUnixSockets` 才放；`socketpair` 不管） |
| `socket` 的其他 family | 放（`net none` 時新的 network namespace 只有 lo） | Restricted：`AF_UNIX` 以外都擋；代理模式只放 `AF_INET`／`AF_INET6`（透明 TCP 再放 `AF_NETLINK` 的 `NETLINK_ROUTE`） | 放 |
| `connect`、`accept`、`accept4`、`bind`、`listen`、`getpeername`、`getsockname`、`shutdown`、`sendto`、`sendmmsg`、`recvmmsg`、`getsockopt`、`setsockopt` | 放 | Restricted **擋**（`recvfrom` 刻意不擋）；代理模式放 | 放 |
| `unshare`／`clone` 帶 `CLONE_NEWUSER`、`CLONE_NEWNS` | **放**（使用者 11-26 定：要能疊 daemon） | 放 | **擋**（`SRT_ALLOW_NESTED_USERNS=1` 才放；`unshare` 另擋 `UNSHARE_EMPTY_MNTNS`） |
| `clone3` | 放 | 放 | **`ENOSYS`**（讓 libc 退回 `clone`，好讓上一條擋得到） |
| `setns`、`mount`、`umount2`、`pivot_root`、`open_tree`、`move_mount`、`fsopen`、`fsconfig`、`fsmount`、`fspick`、`mount_setattr`、`open_tree_attr` | **放**（同上，疊 daemon） | 放 | **擋**（同上） |
| `ioctl` 的 `TIOCSTI` | 不擋（每隻 `setsid`、stdin 是 `/dev/null`、天空沒有終端機；家機 6.18 的 `dev.tty.legacy_tiocsti` 是 0，核心本來就只准有 `CAP_SYS_ADMIN` 的） | 不擋（bwrap `--new-session`） | 不擋（`--new-session`） |
| 別的架構（i386 的 `int 0x80`） | **整個行程殺掉** | 沒寫（交給 seccompiler 的預設） | 不在 ia32 上跑（`socketcall()` 會繞過） |
| x32 的號碼 | **整個行程殺掉** | 擋單裡每個號碼加上 x32 的位元也擋，x32 自己號碼的那幾個也列 | 沒寫 |
| 過濾器誰身上 | 每隻 proc 與 init，exec 前最後一步 | 命令與它的收屍 1 號 | 命令（2 號）；外層那支只上「namespace」那份 |

## 表二：namespace

| | aos-daemon | Codex | srt |
|---|---|---|---|
| user | daemon 開一份，底下的 proc 都在這一份裡（可選 subuid 的帳號） | 每次 `--unshare-user` | 每次 `--unshare-user`；`apply-seccomp` 被拒時再開一層 |
| pid | daemon 開一份，**proc 之間互相看得到**（daemon職責第 46 條：先不做每隻一份） | `--unshare-pid`＋`--as-pid-1`（預設；可設定繼承） | `--unshare-pid`，裡面再開一層，命令是 2 號 |
| mount | 每隻一份，根從一塊空的 tmpfs 組起 | bwrap 一定開；從整台唯讀開始再遮 | 同 Codex |
| net | 每隻一份（預設 `none`，只有 lo）；`net host` 可選 | 限網時 `--unshare-net`；有代理時裡面放一個 TCP↔unix socket 的橋 | 有任何網路設定就 `--unshare-net`；裡面用 socat 接到外面的代理 |
| **ipc** | **每隻一份（11-27 新加）** | **`--unshare-ipc`，一律** | 不開 |
| uts | 不開 | 不開 | 不開 |
| cgroup | 不開 | 不開 | 不開 |

## 表三：其他的鎖

| | aos-daemon | Codex | srt |
|---|---|---|---|
| no_new_privs | 每隻 | 有上 seccomp 時（幾乎都有） | 有 |
| capabilities | caps 0、bounding set 清空、securebits 全鎖 | `--cap-drop ALL`；裡面那一步發現還有 caps 就不跑 | `--cap-drop ALL`（uid 0 且要上 seccomp 時多留 `CAP_SETFCAP`） |
| 看得到哪些檔 | **從零組**：天空表沒放的不存在 | 整台唯讀，再遮掉不准讀的 | 整台唯讀（或整台可寫），再遮掉 |
| `/proc` | 選配；掛的是 daemon 那一層 PID namespace 的，看得到兄弟 | 新的一份（掛不了時退回外面的） | 新的一份（weaker 模式綁外面的），裡面再掛一份 |
| `/dev` | 自己的小 tmpfs：null、zero、full、random、urandom 加 fd 連結，唯讀；沒有 tty、pts | bwrap `--dev`（多一個 tty） | bwrap `--dev` |
| `/dev/shm` | 沒有（要就自己放 tmpfs） | 根可寫時才給 | 沒處理 |
| `.git` 等「改了會在外面被執行」的檔 | daemon 不自動做；天空表多一筆唯讀 bind 蓋在可寫的夾上就是（`escape` 組驗了：寫、換名、刪、經 symlink 寫、卸掉、重掛可寫都不行）；`.git` 本身是指到外面的 symlink 時**起不來**（fail closed） | 可寫的夾裡 `.git`、`.agents`、`.codex`、`.aws` 自動唯讀；不在的也蓋一個空的唯讀夾、不讓建；經可寫 symlink 的直接起不來 | `.git/hooks` 一律擋、`.git/config` 預設擋（`.git` 本身可寫）；`.gitconfig`、`.gitmodules`、`.bashrc`、`.bash_profile`、`.zshrc`、`.zprofile`、`.profile`、`.ripgreprc`、`.mcp.json` 與 `.vscode`、`.idea`、`.claude/commands`、`.claude/agents` 擋寫，往下找三層 |
| io_uring | 擋 | 擋 | 擋 |
| ptrace、讀寫別人的記憶體 | seccomp 擋；Landlock 的 domain 也看不到 domain 外的行程（`/proc/<PID>/mem` 開不了） | seccomp 擋；user namespace | 自己的 PID namespace＋dumpable 0 |
| unix socket | 不擋；連得到的只有天空裡有的 socket 檔；abstract socket：`net none` 的 network namespace 隔開，Landlock ABI 6 以上再擋 | Restricted 放；代理模式擋 | 全擋或全放 |
| SysV IPC、POSIX mqueue | 自己的 IPC namespace（11-27） | 自己的 IPC namespace | **共用外面的** |
| TIOCSTI | `setsid`、stdin `/dev/null` | `--new-session` | `--new-session` |
| 再開 user namespace | 放（疊 daemon） | 放 | 擋（seccomp＋`user.max_user_namespaces=0`，或 bwrap `--disable-userns`） |
| Landlock | 每隻自己一個 domain（只為了 ptrace 與 ABI 6 的訊號、abstract socket 範圍） | 只剩「舊模式」 | 沒有 |
| 起的人死了 | `on_parent_death`；proc 跟著 daemon 走 | `--die-with-parent` | `--die-with-parent` |
| 環境變數 | 只給設定寫的（加 `AOS_NAME`） | 大致照傳 | 照傳，憑證類的 `--unsetenv` |
| 記憶體、行程數、`/tmp` 大小 | cgroup 上限、tmpfs `size` | 沒有 | 沒有 |
| hostname | 外面的（沒開 UTS） | 同 | 同 |

## 加進擋單的（【擬】）

- **`socket`、`socketpair` 的 `AF_VSOCK` 回 `EPERM`**。兩邊都擋。vsock 是虛擬機與主機之間的 socket，不分 network namespace：`net none` 的 proc 照樣連得到這台機器的 hypervisor 上聽 vsock 的服務（WSL2 的 Windows 那一邊、VM 外面的主機）。家機實測 `off` 時 proc 開得出 `AF_VSOCK` 的 socket（vsock 模組在），加了之後五種開法都 `EPERM`。pi 會用的 node、bash、python3、git、curl 在預設的鎖下照跑過一次（node 的 unix socket、python3、`git status`／`log`／`diff`、`curl file://` 都行），不用 vsock。
- 其他「他們擋、我們沒擋」的，看下一節：都牽涉到使用者已經定過的事或 pi 要用的東西，沒有自己加。
- 「我們擋、他們沒擋」的很多（模組、kexec、時鐘、bpf、keyring、`kcmp` 等，44 個裡兩邊都沒擋的有 37 個）：他們靠「沒有 caps」與 user namespace 擋住大部分，我們照 systemd、Docker 的清單多擋一層；沒拿掉任何一個。

## 給使用者挑（有疑慮，沒加）

1. **擋「再開 user／mount namespace」與 mount 那一族**（srt 預設擋）。pi 在裡面會怎樣：擋了，pi 的 shell 就不能自己再開一層沙箱（`unshare`、`bwrap`、裝在裡面的 docker 類工具都失敗），我們的 Landlock 底下本來也 `mount` 不了；不擋就是現在這樣。衝突：使用者 11-26 定「不擋，要能疊 daemon」。選項：
   - 甲（現在）：不擋。
   - 乙：加一個設定（例 `"locks": {"nest": false}`），預設擋、要疊 daemon 的那隻才放。代價：多一個開關、預設變了。
   - 丙：照 srt 整組擋、`clone3` 回 `ENOSYS`，疊 daemon 等以後再說。
2. **擋 `AF_UNIX` socket**（srt 預設全擋、Codex 代理模式擋）。不能照做：pi 腦的路是 `/llm/sock`（unix socket）。我們擋的方式是「天空裡沒有的 socket 檔就連不到」；要再細，找輪子報告寫 Landlock 要到 ABI 9 才限得了 unix socket，兩台的核心都還不到，等以後。
3. **擋連網那一組系統呼叫**（Codex Restricted 擋 `connect`、`bind` 等 13 個）。我們的 `net none` 已經只剩 lo，再擋會連 unix socket 的 `connect` 一起擋掉（pi 連 `/llm/sock` 要用）。建議不做。
4. **每隻自己一個 PID namespace**（兩邊都開）。現在 proc 看得到兄弟的 PID 與命令列（channels-1127 實測）。daemon職責第 46 條先不做；要做是另一題（還要一支收屍的 1 號）。
5. **`.git` 以外的點檔自動唯讀**（Codex：`.git`、`.agents`、`.codex`、`.aws`；srt：`.git/hooks`、`.git/config`、`.bashrc`、`.gitconfig`、`.vscode`、`.idea`、`.claude/commands` 等）。這是佈局的事，歸起 pi 的那一方（最小方案第 5 節第 2 條只講 `.git`），daemon 只要支援「唯讀 bind 蓋在可寫的夾上」（已經支援，`escape` 組驗了）。要不要在 `aos-pi` 的預設佈局多蓋幾個（例 `AGENTS.md`、`.claude/`、`Makefile` 這類你在外面會執行或餵給別的 agent 的），是使用者的事。
6. **`/dev/tty`**（bwrap `--dev` 有）、**遮 `/proc` 的危險處**：沒做，pi 目前不需要。
7. **x32 的作法**：我們整個殺掉、Codex 是照擋單擋（x32 程式還能跑）。我們這樣比較嚴，維持。

## 從他們的測試改寫過來的

照意思自己寫，測試旁註明 `idea from …`（只取意思，沒有逐字抄）。

| 他們的測項 | 我們的測試（組） |
|---|---|
| srt `seccomp-vsock-block.test.ts`（每種 type 都 EPERM、domain 暫存器上半有東西也擋、別的 family 不受影響、網路不限時也擋）；Codex `seccomp_tests.rs::x32_preserves_allowed_calls_and_socket_conditions` | `seccomp`：`AF_VSOCK` 五種開法（`net none`、`net host` 各一次）、`AF_UNIX`／`AF_INET`／`AF_INET6`／`AF_NETLINK` 照開、`off` 時不擋 |
| srt `pid-namespace-isolation.test.ts`（擋 `io_uring_setup`／`io_uring_enter`、對 1 號 `ptrace(PTRACE_ATTACH)`、`process_vm_writev`） | `seccomp`：擋單多試 `io_uring_enter`、`io_uring_register`、對 PID 1 的 `process_vm_writev`、`ptrace_attach` |
| srt 同檔「denies opening /proc/1/mem for write」「denies umount(/proc)」 | `escape`：開 daemon 與 init 的 `/proc/<PID>/mem` 寫是 `EACCES`；`umount /proc` 是 `EPERM` |
| srt `docker-weak-sandbox.test.ts`「no way to unmount a deny」 | `escape`：卸掉 `.git` 的唯讀層、把它重掛成可寫、在 `/tmp` 上掛 tmpfs 都 `EPERM` |
| Codex `suite/sandbox.rs::sandbox_blocks_metadata_writes_inside_writable_root`；srt `mandatory-deny-paths.test.ts`（`.git/config`、`.git/hooks/pre-commit`） | `escape`：可寫的 `/work` 照寫，`.git/config`、新的 hook、`.git` 裡新檔都 `EROFS`，外面的檔沒變 |
| Codex `sandbox_keeps_parent_repo_discovery_while_blocking_child_metadata` | `escape`：`.git` 換名、刪掉都 `EBUSY` |
| Codex `sandbox_blocks_codex_symlink_replacement_attack`、`sandbox_reports_codex_symlink_build_failure_without_panicking` | `escape`：`.git` 是指到外面的 symlink 時，唯讀那層蓋不上去，`start` 是 `EIO`（fail closed），decoy 沒被動 |
| srt `write-through-links.test.ts`、`symlink-write-path.test.ts`、`integration.test.ts`「prevents symlink-based write escape」 | `escape`：在 `/work` 自己做 symlink 指到 `.git/hooks`、`/etc`、外面真的路徑，經它寫：`EROFS`、`EROFS`、`ENOENT`，外面沒多檔 |
| srt `integration.test.ts`「special files: mkfifo allowed, hard link to /etc/passwd fails」 | `escape`：`/tmp` 裡 `mkfifo` 可以；`/work` 硬連結到 `/etc/passwd` 是 `EXDEV` |
| srt `integration.test.ts`「prevents privilege escalation（setuid、sudo）」 | `escape`：uid 1 的 proc 跑 `/usr/bin/sudo -n id -u` 失敗（no_new_privs、nosuid） |
| Codex `bwrap_populates_minimal_dev_nodes`、`test_dev_null_write` | `escape`：`/dev` 五個是字元裝置、`/dev/null` 寫得進、`/dev/zero` 讀到 0、`/dev/full` 寫是 `ENOSPC` |
| Codex `test_root_write`、`test_writable_root` | `escape`：`/usr` 寫是 `EROFS`、`/work` 照寫 |
| Codex `sandbox_blocks_curl`／`nc`／`dev_tcp_redirection` | `escape`：`net none` 連 `1.1.1.1:80` 是 `ENETUNREACH`、自己的 `::1` 是 `ECONNREFUSED` |
| Codex `proc_mount_denial_preserves_…`（user、ipc、net namespace 跟外面不同） | `ipc`：六隻（含外面）的 `ns/ipc` 都不同，加上 SysV／mqueue 三個方向都看不到 |

我們原本就有、不用搬的：no_new_privs、caps 全 0（`landlock`、`access`）、唯讀的地方寫不進去（`ns`）、x32 與 i386（`seccomp`，我們是殺掉）、網路（`net`）、起的人死了跟著走與沒有孤兒（`teardown`、`killgrp`）。

**沒搬的**（我們不這樣做，或跟 daemon 無關）：擋 `AF_UNIX`、擋再開 namespace 與 mount（見「給使用者挑」第 1、2 條）；每隻自己的 PID namespace、`/proc` 只看得到自己（第 4 條）；代理、網域名單、TLS、憑證遮蔽（我們走 `/llm`）；glob 的讀取遮蔽、整台唯讀時的遮法（我們從零組，沒有要遮的）；bwrap 的版本、路徑、argv 組法這類單元測試；WSL 的 interop（Codex `wsl_interop_cannot_run_windows_program_*`：Codex 遮 `/run/WSL`；我們的天空預設沒有 `/run`、`/mnt/c`，**公司 WSL 上沒驗過**，建議在那台補一條「proc 跑不了 Windows 的 `.exe`」）。
