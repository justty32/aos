# aos 現況：已經碰了 Linux 的哪些「硬體面」、哪些完全沒碰、同一個帳號的影響

← [README](README.md)｜上一份：[01-對照表](01-對照表.md)｜下一份：[03-別人怎麼做](03-別人怎麼做.md)

讀程式與文件確認（repo HEAD `7b29aa17a`），沒碰活的 daemon 與 `~/aos-home`。另在家機暫存夾 `~/.aos/scratch/linux-as-hw-1118/`（`git archive` 取 HEAD、`install.py` 退 0）做了兩個不用 daemon 的小實測（E1、E2，見末節）。

## 先講結論

1. **aos 碰得比想像多，而且方向一致**：每一樣都是「借 Linux 現成的鎖」（C-64），沒有自己造鎖。排程之外已經有：份額（rlimit＋可選 cgroup）、看得見什麼（bwrap 沙箱）、換身分（daemon `user`、`aos-asuser` 的 subuid）、替共用夾開門（`aos-share` 的 ACL）、kernel 站照名字填身分與份額（`users`／`limits` 表）。
2. **但「換身分」這條電線最後一段沒接上**：kernel 站會填 `user: "sub:N"`，可是 daemon 今天還不認 `sub:N`（`LimitBad`），kernel 站 README 自己寫「daemon 認之前，`users` 不要填 `sub:N`」。daemon 認的 `user: 帳號名` 又要 daemon 是 root。所以**實際上今天每一隻 agent、每一個工具都跟使用者同一個 Linux 帳號**。
3. **aos 的「身分」是自報的**：信的 `sender` 是寄件人自己的 `$AOS_WS`（沒設再看 `$AOS_STACK`…）。E1 實測：一行 `AOS_WS=…/eca_main aos-post send` 就寄出一封 `sender` 寫著 eca_main 的信；信夾的 Linux 擁有者照實是 1000，但沒有人看這個。Linux 有一張造不了假的身分證（檔案擁有者、`SO_PEERCRED`），aos 沒用。
4. **完全沒碰的**：系統呼叫過濾（seccomp）、Landlock、網路細管（照 uid 放行、只准連某埠）、磁碟總量、設備、journald、inotify、kernel keyring、ptrace 限制、PAM。
5. **同一個帳號的影響，一句話**：aos 內部的每一道門（kernel 拒絕、沙箱、使用者專區驗證）都是「君子協定＋布景」，擋得住守規矩或被關在布景裡的 agent，擋不住拿著 shell、沒被關的 agent。沙箱檢查的 A 落差、sbx-fix 的九條、使用者專區那句「擋不住會開 shell 刻意造假的 agent」，**根是同一個**。

## 一、已經碰了的（逐項）

| 塊 | 做到哪 | 在哪 | 備註 |
|---|---|---|---|
| 行程排程 | daemon 起停睡醒、收屍、出錯留 `stopped`＋`reason`；kernel 站 `allowed`／`max_running`／`queue` 決定起不起、何時起；llm kernel 排腦的請求與額度 | [aos-daemon](../../../../cpp/aos-daemon/README.md)、[kernel 站](../../../../py/tools/aos/kernel/README.md)、知識庫 `aos/kernel.json` | 使用者原本的重心，最完整 |
| 每支行程的上限 | `limits`：`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`，daemon 在子行程裡 `setrlimit`；`limits_max` 天花板；SIGXCPU／SIGXFSZ 認出命中 | [daemon docs/09](../../../../cpp/aos-daemon/docs/09-份額.md) | `procs` 在同一個 uid 下數的是**整個帳號**的行程（X11），等於不能用 |
| 一群行程的總量 | 可選 cgroup v2：`cgroup: off｜auto｜on`（預設 off），`mem_total_mb`、`procs_total`，讀 OOM 事件、`cgroup.kill` | 同上 | 11-13 使用者裁「要可選」；要 systemd user 委派，公司 WSL 沒有 |
| 看得見什麼、網路開關 | `aos-sandbox`（bwrap）：`ro`／`rw` 白名單、`net` 布林、`env` 白名單、上限（要 s6）、`user` | [aos-sandbox](../../../../py/aos/apps/sandbox/README.md) | 範本佈局讓工作區包住整棵樹，沙箱碰得到 daemon（[sbx-fix-1118](../sbx-fix-1118.md)，修法待裁）；設定寫壞＝不關照跑（11-12「甲，出事自己負責」） |
| 換身分（要 root） | daemon `limits.user`＝帳號名，子行程 `setgroups`＋`setgid`＋`setuid`；沙箱 `user: aos-run` 走 sudoers＋s6 | daemon docs/09、沙箱「要 root 的那半」 | daemon 不是 root＝`LimitBad … switching users needs the daemon to run as root` |
| 換身分（免 root） | `aos-asuser sub:N -- 程式`：user namespace＋`newuidmap`，換成真的 subuid（家機 `sub:5`＝100004）；`--fix` 把 subuid 寫的檔改回使用者；沙箱 `user: "sub:N"` 就是前面接它 | [aos-asuser](../../../../py/aos/apps/asuser/README.md)、[教學 10](../eca-claude-小試驗教學/10-aos-asuser.md) | 家機工具齊；公司 WSL 缺 `uidmap` 套件 |
| 替共用夾開門 | `aos-share`：`team` 共寫、`read` 唯讀、`key` 金鑰、`work` 可改不可刪、`drop` 投遞箱、`stack`；`check`、`reset` | [aos-share](../../../../py/aos/apps/share/README.md)、[教學 11](../eca-claude-小試驗教學/11-aos-share.md) | 公司 WSL 缺 `acl` 套件；只有在 agent 換了 uid 之後才有意義 |
| 身分政策 | kernel 站 `users`（名字樣式→帳號或 `sub:N`）、`groups`、`limits.default／max／by_sender`；寄件人自帶的 `user` 一律丟掉（身分由 kernel 定，不由 agent 自己說） | kernel 站 README「限制與身分」 | **daemon 還不認 `sub:N` 與 `groups`**（kernel-limits-plan 段 3 C++ 沒做） |
| 一點點「看 uid」 | aos-llm 等回信前檢查「kernel 的 uid 寫不寫得進我的回信箱」；`cli_cell` 只收自己 uid 擁有的小格 | `cpp/aos-llm/src/wait/wait.cpp`、`py/aos/agentlib/cli_cell.py` | 為多 uid 預先鋪的小檢查，不是身分驗證 |
| 認行程 | `/proc` 的 pid＋開始時間＋`boot_id`；清道夫讀 `/proc/<pid>/environ` | `py/aos/sweep_proc.py` | 同 uid 才讀得到別人的 environ——換 uid 後清道夫要重想 |
| 人的身分 | 使用者專區 `~/.aos/user/`，回信用 `aos-user verify` 比對專區留底 | 知識庫 `aos/user_zone.json` | AGENTS 鐵律 2 原文：「擋得住轉述與假回信、擋不住會開 shell 的 agent 刻意連專區留底一起造假」 |

規劃面：11-13 [kernel-limits-plan](../../13/kernel-limits-plan.md) 已經把「每隻 agent 一個 subuid、一台 daemon 一個群組、共用夾用 ACL、cgroup 可選、先不用 root」整套想完並由使用者裁了（K1～K18），試驗 X1～X37 在家機做過；11-14 施工了 kernel 站、aos-share、aos-asuser、aos-sandbox 認 `sub:N` 這幾段（[kernel-limits-1114](../../14/kernel-limits-1114.md)）。**剩 daemon 那段（C++：認 `sub:N`、多群組、替 stack 設 ACL、換身分前關 fd 清環境）沒做**。

## 二、完全沒碰的

| 塊 | 白話 | 沒有它的後果（今天） |
|---|---|---|
| seccomp | 系統呼叫白名單 | 被關進沙箱的程式，仍能用所有系統呼叫（例：開 user namespace、ptrace 自己的子行程） |
| Landlock | 不用 root、程式自己綁自己 | 沒用到「agent 起來後自己宣告只碰這幾個夾」這條免 root 的路；家機核心有開（`/sys/kernel/security/lsm` 列著 `landlock`） |
| 網路細管 | 只准連 LiteLLM 那個埠、不准連外 | 只有全通或全斷；`net:true` 連宿主 127.0.0.1 全通 |
| 磁碟總量 | 一隻 agent 最多寫多少 | 寫滿磁碟只能靠人看 `du` |
| 設備 | `/dev`、群組授權 | 沒需求，沒碰 |
| journald／集中日誌 | 一本誰都改不了別人那頁的帳 | 每個 stack 自己記，agent 改得到自己的紀錄 |
| inotify | 信到就響 | 全部輪詢（N-14 說了「inotify 加速」，還沒做） |
| keyring／秘密 | 金鑰放哪最安全 | 靠環境變數白名單＋proxy 把金鑰放外面；同 uid 的行程讀得到彼此的 environ |
| ptrace 收緊、PAM、logind | — | 同 uid＝能附身彼此 |

## 三、全部 agent 跟使用者同一個 Linux 帳號，影響在哪

用 01 的大樓比喻：大家戴同一張員工證，所以物業的門禁對 aos 內部沒作用。具體是：

1. **誰都改得到誰的檔**：別隻 agent 的 stack、定義、daemon 的信箱、llm kernel 的 `kernel.json`、使用者專區的留底。規則 1「不碰別人的 stack」是約定，不是鎖。
2. **誰都殺得到誰**：同 uid 的 `kill`、`ptrace`、讀 `/proc/<pid>/environ`（環境變數裡若有金鑰就看得到）都不用權限。
3. **寄件人造得了假**（E1）：kernel 站的 `allowed`、`by_sender`、llm kernel 照寄件人算額度，都建在自報的 `sender` 上。守規矩的 agent 不會亂寫，但「刻意」或「被 prompt 注入」的 agent 一行就繞過。
4. **份額有一格是壞的**：`procs`（`RLIMIT_NPROC`）數的是整個帳號，寫小了 agent 起不來，寫大了等於沒寫。
5. **沙箱是唯一真的牆**：它靠「布景」（mount namespace）而不是「身分」，所以只要布景搭錯（工作區包住整棵樹），牆就沒了；而且只有被關進去的才有牆：範本（`templates/`）裡沒有任何一份 `sandbox.json`，沙箱設定只在 aos-sandbox 的 `examples/`，要自己抄進定義夾（教學 09 就是這樣關 eca-claude）。
6. **好處也是真的**：使用者看得到、改得到、刪得到 agent 寫的一切；git 不會抱怨「dubious ownership」（X27）；搬家時不用管檔案擁有者；公司 WSL 不用多裝套件。**換 uid 的每一個代價，都是現在免費拿到的方便**（見 [04](04-邊緣狀況.md)）。

## 四、本線的兩個小實測（家機，暫存夾，沒起 daemon）

| # | 做什麼 | 結果 | 說明 |
|---|---|---|---|
| E1 | `aos-post init box1`；`AOS_WS=/home/lorkhan/aos-home/ws/eca_main aos-post send box1`（使用者本人的 shell 寄） | 信的 `letter.json` 寫 `"sender": "/home/lorkhan/aos-home/ws/eca_main"`；信夾 `stat` 是 `owner=1000:1001` | 寄件人欄＝自報；Linux 記下的擁有者是真的、但沒人看。換了 uid 之後，「看擁有者」就是一張造不了假的寄件證（[05 丙](05-發想.md)） |
| E2 | `aos-asuser sub:5 -- <暫存夾>/bin/aos-post send <暫存夾>/exp/box1` | `CommandMissing … Permission denied`、退 127 | 家目錄是 `700`：換了身分的程式**連 aos 的執行檔都起不來**，更別說寫信箱。這就是 X2「共用夾的每一層祖先都要給別人 x」；aos 裝在家目錄底下時，第一件事就卡在這（[04 第 1 條](04-邊緣狀況.md)） |

E2 後沒有去改家目錄權限（那是使用者的系統設定），往下的「寫進信箱、投遞箱讀不讀得到」11-13 的 X23、X24、X33 已做過，這裡不重做。暫存夾留著沒刪；沒起任何常駐行程。
