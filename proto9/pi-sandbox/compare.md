同一支 `probe.sh` 放進三種沙箱跑的對照：aos-pi、Anthropic 的 sandbox-runtime（srt）、OpenAI Codex 的 `codex sandbox`，三邊都設成「只有工作夾可寫、沒有網路」，每一項附實際錯誤訊息（11-27 家機 6.18 實跑）。

# 三種沙箱對照（aos-pi／srt／Codex）

← [pi-sandbox](README.md)

怎麼重跑：`python3 proto9/pi-sandbox/compare.py --out <檔>`（約 2 秒；srt 要先照下面裝好；不叫模型、不開網路）。下面的表就是那支印的，沒手改。

## 三邊的設定（盡量「跟 aos-pi 同樣意思」）

| | 版本 | 設定 | 怎麼起 |
|---|---|---|---|
| aos-pi | 本夾 | `aos_pi.py` 的 `pi_sky()` 標準佈局（README「天空每一筆」）；`net none`；一隻 llm kernel（`--fake`） | `compare.py` 用 `aos_pi.Sandbox` 起 daemon 與 kernel，probe 跟 pi 同一片天空、另綁 `/opt/probe` |
| srt | `@anthropic-ai/sandbox-runtime` 0.0.83（`npm install` 進 `~/.aos/scratch/proto9-impl-1127/srt/`，不在 repo） | `{"network": {"allowedDomains": [], "deniedDomains": []}, "filesystem": {"denyRead": [], "allowWrite": ["<工作夾>"], "denyWrite": []}}` | `srt --settings <檔> bash probe.sh`，cwd＝工作夾 |
| Codex | `codex-cli 0.172.0`（`/usr/bin/codex`，沒登入、不叫模型） | 自己定一個權限設定：`-c 'permissions.aospi={filesystem={":root"="read", ":workspace_roots"="write"}, network={enabled=false}}' -P aospi` | `codex sandbox -C <工作夾> <上面> -- bash probe.sh` |

設定時查到的：

- **srt**：預設整台主機都讀得到（`denyRead` 空就是全開），寫入只開 `allowWrite`；工作夾底下的 `.git/hooks`、`.git/config` 自己就擋（它叫 mandatory deny）。Linux 上 **unix socket 只能全擋或全開**（`allowUnixSockets` 只在 macOS 有用，`allowAllUnixSockets` 是全開），所以「只准一個 socket」做不到，表上 `llm_sock_models` 是擋住。沒網路時它還是設了 `HTTP_PROXY`，curl 拿到的是它代理回的 403。
- **Codex**：`codex sandbox` 一定要給 `-P`（權限設定名）。內建的 `:workspace` 會把 `/tmp` 也開成可寫，舊的 `sandbox_workspace_write.exclude_slash_tmp` 這類 `-c` 對 `-P :workspace` 沒作用（實測 `/tmp` 照樣寫得進去），所以改用自己定的 `aospi`：根唯讀、工作根可寫、不給網路；工作根底下的 `.git` 它自己就蓋成唯讀。Codex 的設定有 `network.unix_sockets`（准某幾個 socket 路徑）這一格，我沒驗（試它要開網路那種模式，這次沒跑），所以表上 `llm_sock_models` 是擋住。
- 三邊的 probe 拿到的外面路徑一樣（`~/.ssh`、repo 的 `AGENTS.md`、`~/.pi/agent/auth.json`、一個外面的夾、外面的 unix socket／abstract socket／vsock／SysV 共享記憶體／POSIX 佇列、外面一個行程的 PID）。aos-pi 多了 `/.aos`、`/llm` 兩個唯讀的地方要試；srt、Codex 那兩格是「-」（沒那個地方）。

## 怎麼讀這張表

- `want`：照「沙箱裡的程式不該做到」該是 `blocked`；`write_work`、`llm_sock_models` 兩格是該通的（工作夾可寫、准的那個 socket 連得上）。
- `blocked`／`open`／`n/a`／`-`（沒跑這項）；跟 `want` 不一樣的標 **(!)**。
- 每格底下是 probe 實際拿到的訊息（截到 90 字、家目錄寫成 `~`）。只印檔案大小、行數，不印內容。

幾格要多講一句：

- **讀工作夾外的檔**：srt、Codex 照它們的設計「整台主機唯讀看得到」，所以 `~/.ssh`、repo、pi 的 `auth.json` 都讀得到（標 (!)，是設計不同，不是設錯）；要擋得一條條寫 `denyRead`。aos-pi 的天空沒放那些路徑，是「沒有這個檔」。
- **`net_vsock`**：第一次跑時 aos-pi 這格是通的。`net none` 只管 IP 網路，vsock 不分 network namespace，所以沙箱裡連得到外面在 vsock（本機 cid 1）上聽的程式。srt、Codex 都用 seccomp 擋 `socket(AF_VSOCK)`。aos-daemon 的內建擋單補了這一條（【擬】，見 [vs-codex-srt](../cpp/aos-daemon/vs-codex-srt.md)），下面的表是補了之後重跑的。
- **`ipc_sysv_shm`、`ipc_posix_mq`**：srt 通，因為它沒開 IPC namespace；Codex 擋住，因為它開了 `--unshare-ipc`。aos-pi 第一次跑時也通；aos-daemon 改成每隻 proc 自己一份 IPC namespace 之後擋住，下面的表是改了之後重跑的。
- **`unshare_userns`**：aos-pi、Codex 都能在裡面再開一層 user namespace（aos-daemon README 寫明內建擋單「不擋開 namespace 與 mount」）；srt 擋。開了也只是在自己的天空裡再分一層，碰不到外面；記成 info。
- **`proc1_root`、`proc1_environ`**：Codex 那格的 (!) 不是洞：它有自己的 PID namespace，裡面的 1 號是沙箱自己的行程。aos-pi 不給 `/proc`，這幾項是「-」，改由 `proc_absent` 那格記。
- **`net_ssh`**：Codex 那格的錯誤是 ssh 自己嫌設定檔的擁有者（沙箱裡帳號對不上），沒走到網路；網路本身由其他幾格證明是斷的。

## 表

| check | want | aos-pi | srt | Codex |
|---|---|---|---|---|
| `write_work` | open | open | open | open |
| `write_root` | blocked | blocked<br>`sh: line 1: /probe-6: Read-only file system` | blocked<br>`sh: line 1: /probe-2: Read-only file system` | blocked<br>`sh: line 1: /probe-2: Read-only file system` |
| `write_ro:/` | blocked | blocked<br>`sh: line 1: //probe-6: Read-only file system` | blocked<br>`sh: line 1: //probe-2: Read-only file system` | blocked<br>`sh: line 1: //probe-2: Read-only file system` |
| `write_ro:/.aos` | blocked | blocked<br>`sh: line 1: /.aos/probe-6: Read-only file system` | - | - |
| `write_ro:/llm` | blocked | blocked<br>`sh: line 1: /llm/probe-6: Read-only file system` | - | - |
| `write_ro:/usr` | blocked | blocked<br>`sh: line 1: /usr/probe-6: Read-only file system` | blocked<br>`sh: line 1: /usr/probe-2: Read-only file system` | blocked<br>`sh: line 1: /usr/probe-2: Read-only file system` |
| `write_ro:/etc` | blocked | blocked<br>`sh: line 1: /etc/probe-6: Read-only file system` | blocked<br>`sh: line 1: /etc/probe-2: Read-only file system` | blocked<br>`sh: line 1: /etc/probe-2: Read-only file system` |
| `write_ro:~` | blocked | blocked<br>`sh: line 1: ~/probe-6: No such file or directory` | blocked<br>`sh: line 1: ~/probe-2: Read-only file system` | blocked<br>`sh: line 1: ~/probe-2: Read-only file system` |
| `write_outside` | blocked | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/outside-aos-pi/probe-6` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/outside-srt/probe-2: R` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/outside-codex/probe-2:` |
| `git_hooks_write` | blocked | blocked<br>`sh: line 1: /home/pi/work/.git/hooks/pre-commit: Read-only file system` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/.git/hooks/pr` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/.git/hooks/` |
| `git_hooks_new` | blocked | blocked<br>`sh: line 1: /home/pi/work/.git/hooks/probe-6: Read-only file system` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/.git/hooks/pr` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/.git/hooks/` |
| `git_config_write` | blocked | blocked<br>`sh: line 1: /home/pi/work/.git/config: Read-only file system` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/.git/config: ` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/.git/config` |
| `hardlink_out` | blocked | blocked<br>`ln: failed to create hard link '/home/pi/work/probe-6.hl' => '/etc/passwd': Invalid cross-` | blocked<br>`ln: failed to create hard link '~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/wo` | blocked<br>`ln: failed to create hard link '~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/wo` |
| `mknod_dev` | blocked | blocked<br>`mknod: /home/pi/work/probe-6.null: Operation not permitted` | blocked<br>`mknod: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/probe-2.null: Oper` | blocked<br>`mknod: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/probe-2.null: Op` |
| `setuid_gain` | blocked | blocked<br>`setuid copy of id ran as uid 0, the caller is 0` | blocked<br>`setuid copy of id ran as uid 1000, the caller is 1000` | blocked<br>`setuid copy of id ran as uid 1000, the caller is 1000` |
| `symlink_file_write` | blocked | blocked<br>`sh: line 1: /home/pi/work/probe-6.l1: No such file or directory` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/probe-2.l1: R` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/probe-2.l1:` |
| `symlink_dir_write` | blocked | blocked<br>`sh: line 1: /home/pi/work/probe-6.l2/probe-6.esc2: No such file or directory` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-srt/probe-2.l2/pr` | blocked<br>`sh: line 1: ~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/work-codex/probe-2.l2/` |
| `symlink_rename_out` | blocked | blocked<br>`mv: cannot move '/home/pi/work/probe-6.mv' to '/home/pi/work/probe-6.l2/probe-6.mv': No su` | blocked<br>`mv: inter-device move failed: '~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/wor` | blocked<br>`mv: inter-device move failed: '~/.aos/scratch/proto9-impl-1127/pi/compare/run-8ttj3m2u/wor` |
| `read:~/.ssh` | blocked | blocked<br>`sh: line 1: ~/.ssh: No such file or directory` | open **(!)**<br>`4` | open **(!)**<br>`4` |
| `read:~/repo/aos/AGENTS.md` | blocked | blocked<br>`sh: line 1: ~/repo/aos/AGENTS.md: No such file or directory` | open **(!)**<br>`13289` | open **(!)**<br>`13289` |
| `read:~/.pi/agent/auth.json` | blocked | blocked<br>`sh: line 1: ~/.pi/agent/auth.json: No such file or directory` | open **(!)**<br>`2437` | open **(!)**<br>`2437` |
| `read_etc_shadow` | blocked | blocked<br>`sh: line 1: /etc/shadow: No such file or directory` | blocked<br>`sh: line 1: /etc/shadow: Permission denied` | blocked<br>`sh: line 1: /etc/shadow: Permission denied` |
| `symlink_read` | blocked | blocked<br>`ls: cannot access '/home/pi/work/probe-6.l3/': No such file or directory 0` | open **(!)**<br>`4` | open **(!)**<br>`4` |
| `proc_absent` | blocked | blocked<br>`no /proc in this sandbox` | - | - |
| `net_dns` | blocked | blocked | blocked | blocked |
| `net_https` | blocked | blocked<br>`curl: (6) Could not resolve host: example.com` | blocked<br>`curl: (22) The requested URL returned error: 403` | blocked<br>`curl: (6) Could not resolve host: example.com` |
| `net_ip` | blocked | blocked<br>`curl: (7) Failed to connect to 1.1.1.1:80 after 0 ms: Could not connect to server` | blocked<br>`curl: (22) The requested URL returned error: 403` | blocked<br>`curl: (7) Failed to connect to 1.1.1.1:80 after 0 ms: Could not connect to server` |
| `net_dev_tcp` | blocked | blocked<br>`bash: connect: Network is unreachable bash: line 1: /dev/tcp/1.1.1.1/80: Network is unreac` | blocked<br>`bash: connect: Network is unreachable bash: line 1: /dev/tcp/1.1.1.1/80: Network is unreac` | blocked<br>`bash: socket: Operation not permitted bash: line 1: /dev/tcp/1.1.1.1/80: Operation not per` |
| `net_ping` | blocked | blocked<br>`ping: prctl: Operation not permitted` | blocked<br>`ping: socktype: SOCK_RAW ping: socket: Operation not permitted ping: => missing cap_net_ra` | blocked<br>`ping: socktype: SOCK_DGRAM ping: socket: Operation not permitted` |
| `net_ssh` | blocked | blocked<br>`Pseudo-terminal will not be allocated because stdin is not a terminal.` | blocked<br>`Pseudo-terminal will not be allocated because stdin is not a terminal.` | blocked<br>`Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` |
| `net_vsock` | blocked | blocked<br>`socket(AF_VSOCK): [Errno 1] Operation not permitted` | blocked<br>`socket(AF_VSOCK): [Errno 1] Operation not permitted` | blocked<br>`socket(AF_VSOCK): [Errno 1] Operation not permitted` |
| `llm_host_loopback` | blocked | blocked<br>`curl: (7) Failed to connect to 127.0.0.1:4000 after 0 ms: Could not connect to server` | blocked<br>`curl: (7) Failed to connect to 127.0.0.1:4000 after 0 ms: Could not connect to server` | blocked<br>`curl: (7) Failed to connect to 127.0.0.1:4000 after 0 ms: Could not connect to server` |
| `llm_anthropic_api` | blocked | blocked<br>`curl: (6) Could not resolve host: api.anthropic.com` | blocked<br>`curl: (22) The requested URL returned error: 403` | blocked<br>`curl: (6) Could not resolve host: api.anthropic.com` |
| `llm_sock_models` | open | open<br>`{"object": "list", "data": [{"id": "fake-model", "object": "model", "owned_by": "llm-kerne` | blocked **(!)**<br>`curl: (7) Failed to connect to llm:80 over unix://~/.aos/scratch/proto9-impl-1127/pi/compa` | blocked **(!)**<br>`curl: (7) Failed to connect to llm:80 over unix://~/.aos/scratch/proto9-impl-1127/pi/compa` |
| `llm_sock_bad_model` | blocked | blocked<br>`curl: (22) The requested URL returned error: 403` | blocked<br>`curl: (7) Failed to connect to llm:80 over unix://~/.aos/scratch/proto9-impl-1127/pi/compa` | blocked<br>`curl: (7) Failed to connect to llm:80 over unix://~/.aos/scratch/proto9-impl-1127/pi/compa` |
| `unix_sock_outside` | blocked | blocked<br>`[Errno 2] No such file or directory` | blocked<br>`[Errno 1] Operation not permitted` | blocked<br>`[Errno 1] Operation not permitted` |
| `unix_abstract_outside` | blocked | blocked<br>`[Errno 111] Connection refused` | blocked<br>`[Errno 1] Operation not permitted` | blocked<br>`[Errno 1] Operation not permitted` |
| `ipc_sysv_shm` | blocked | blocked<br>`shmat(98351): EINVAL (Invalid argument)` | open **(!)**<br>`attached the outside segment 98351` | blocked<br>`shmat(98351): EINVAL (Invalid argument)` |
| `ipc_posix_mq` | blocked | blocked<br>`mq_open(/aos-pi-accept-1563602): ENOENT (No such file or directory)` | open **(!)**<br>`opened the outside queue /aos-pi-accept-1563602` | blocked<br>`mq_open(/aos-pi-accept-1563602): ENOENT (No such file or directory)` |
| `kill_host_pid` | blocked | blocked<br>`/opt/probe/probe.sh: line 29: kill: (1563602) - No such process` | blocked<br>`~/repo/aos/proto9/pi-sandbox/probe.sh: line 29: kill: (1563602) - No such process` | blocked<br>`~/repo/aos/proto9/pi-sandbox/probe.sh: line 29: kill: (1563602) - No such process` |
| `ptrace_pid1` | blocked | blocked<br>`ptrace(ATTACH, 1): EPERM (Operation not permitted)` | blocked<br>`ptrace(ATTACH, 1): EPERM (Operation not permitted)` | blocked<br>`ptrace(ATTACH, 1): EPERM (Operation not permitted)` |
| `ptrace_other` | blocked | blocked<br>`ptrace(ATTACH, 5): EPERM (Operation not permitted)` | blocked<br>`ptrace(ATTACH, 1563607): ESRCH (No such process)` | blocked<br>`ptrace(ATTACH, 1563607): EPERM (Operation not permitted)` |
| `process_vm_writev_pid1` | blocked | blocked<br>`process_vm_writev(1): EPERM (Operation not permitted)` | blocked<br>`process_vm_writev(1): EPERM (Operation not permitted)` | blocked<br>`process_vm_writev(1): EPERM (Operation not permitted)` |
| `io_uring_setup` | blocked | blocked<br>`io_uring_setup: EPERM (Operation not permitted)` | blocked<br>`io_uring_setup: EPERM (Operation not permitted)` | blocked<br>`io_uring_setup: EPERM (Operation not permitted)` |
| `tiocsti` | blocked | blocked<br>`no terminal: /dev/tty: [Errno 2] No such file or directory: '/dev/tty'` | blocked<br>`no terminal: /dev/tty: [Errno 6] No such device or address: '/dev/tty'` | blocked<br>`no terminal: /dev/tty: [Errno 6] No such device or address: '/dev/tty'` |
| `no_new_privs_off` | blocked | blocked<br>`no_new_privs is 1` | blocked<br>`no_new_privs is 1` | blocked<br>`no_new_privs is 1` |
| `caps_effective` | blocked | blocked<br>`effective 0x0 permitted 0x0` | blocked<br>`effective 0x0 permitted 0x0` | blocked<br>`effective 0x0 permitted 0x0` |
| `unshare_userns` | blocked | open **(!)**<br>`unshare(CLONE_NEWUSER) worked (a nested user namespace)` | blocked<br>`unshare(CLONE_NEWUSER): EPERM (Operation not permitted)` | open **(!)**<br>`unshare(CLONE_NEWUSER) worked (a nested user namespace)` |
| `mount_tmpfs` | blocked | blocked<br>`mount tmpfs: EPERM (Operation not permitted)` | blocked<br>`mount tmpfs: EPERM (Operation not permitted)` | blocked<br>`mount tmpfs: EPERM (Operation not permitted)` |
| `umount_root` | blocked | blocked<br>`umount2(/): EPERM (Operation not permitted)` | blocked<br>`umount2(/): EPERM (Operation not permitted)` | blocked<br>`umount2(/): EPERM (Operation not permitted)` |
| `proc1_root` | blocked | - | blocked<br>`ls: cannot access '/proc/1/root/': Permission denied 0` | open **(!)**<br>`24` |
| `proc1_environ` | blocked | - | blocked<br>`bash: line 1: /proc/1/environ: Permission denied 0` | open **(!)**<br>`146` |
| `proc_net_tcp` | blocked | - | blocked | blocked |
| `proc1_mem_write` | blocked | - | blocked<br>`[Errno 13] Permission denied: '/proc/1/mem'` | blocked<br>`[Errno 13] Permission denied: '/proc/1/mem'` |
