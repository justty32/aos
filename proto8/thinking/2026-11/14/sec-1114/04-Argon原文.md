線安 ok-sec 的 04 Argon 原文：Gemini 4 Argon (High) 審 01、02、03 的 (A) 審查與 (B) 提案，逐字未改。

← [sec-1114 紀錄](../sec-1114.md)｜上一份 [03 計劃](03-計劃.md)｜下一份 [05 採納表](05-採納表.md)

> 指令：在 `/tmp/ok-sec-argon` 跑 `agy -p "$(cat prompt.txt)" --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`；prompt＝英文指示＋01、02、03 全文（76 KB，送出時 03 還沒寫入 E3）。11-14 12:2x 完成，一次成功、沒有 Authentication required。

---

這裡是 Argon 對 `01-備料.md`、`02-fable稿.md`、`03-計劃.md` 的共同設計與審查意見。以下分為 **(A) 具體問題審查** 與 **(B) 改進與替代提案** 兩部分。

---

## (A) 審查：02／03 的具體問題

### A1. 〔Blocking｜Linux ACL 與 `other` 位元事實錯誤／威脅模型破洞〕家目錄與 `~/aos-home` 開 `g:sub:G:--x` 後，所有 `umask 022`（755/644）檔案會經由 `other` 位元對全體 `sub:N` 敞開
- **位置**：03 §一.3、§三 D2、§四 第 1 期 `1a`、§六 Q9（推薦選項 1）；02 §四
- **問題**：
  1. Linux 核心 POSIX ACL 權限判定順序（`fs/posix_acl.c:posix_acl_permission`）為：`owner (u::)` → `named user (u:X)` → `group / named group (g:: / g:X)` → **`other (o::)`**。
  2. `sub:N`（真 uid `100000+N-1`）不是 `lorkhan`（`1000`），也不在 `lorkhan` 群組。因此對任何由 `lorkhan` 擁有、且未逐一掛上 `sub:N`／`sub:G` ACL 的檔案或資料夾，**Linux 核心看的是該檔案的 `other` 權限位**！
  3. 原先 `/home/lorkhan` 是 `0700`，靠家目錄頂層擋住裡面所有 `umask 022`（`0755`/`0644`）的檔案。一旦照 Q9-1 在 `/home/lorkhan` 與 `~/aos-home` 加上 `g:sub:G:--x`：
     - **家目錄失守**：LLM 百分之百猜得到固定點檔案路徑，所有 `0644`/`0755` 的 `~/.claude.json`、`~/.claude/`、`~/.gitconfig`、`~/.bashrc`、`~/.bash_history`、`~/.ssh/config`、`~/repo/aos` 立刻被全體 `sub:N` 透過 `other: r--` 讀光。
     - **`~/aos-home` 內部失守**：03 第 1 期 `1a` 只對 `~/aos-home`「**頂層**」做 `o-rwx`。第 2/3 期為了讓 `sub:N` 走進 `~/aos-home`，必然在 `~/aos-home` 頂層加 `g:sub:G:--x`；一加之後，`~/aos-home` 底下原本 `0755`/`0644` 的子目錄與檔案又全部經由 `other` 位對 `sub:N` 可讀。
     - **新檔持續外洩**：01 §4.3 B 指出 `dirs.cpp:17`（`0777 & ~umask`）、`files.cpp:258`（`open 0666`）、`child.cpp:107`（`0644`）皆以 `umask 022` 建檔。即便跑一次 chore，daemon 下一秒新建的 `exec.json`、`procs_state.json` 或新目錄仍是 `0644`/`0755`（`other` 可讀）。
- **修法**：
  1. **廢棄 Q9-1（絕不可在 `/home/lorkhan` 加 `g:sub:G:--x`）**。應把活樹放家目錄外（如 `/srv/aos-$USER`），或由啟動器用 mount namespace 把 `~/aos-home` bind-mount 到 `/run/user/1000/aos`（見 B2）。
  2. `daemon` 與工具在安全模式下必須將 `umask` 設為 `0077`（或將 `files.cpp`/`dirs.cpp` 改為私有模式），且對整棵 `~/aos-home` 遞迴 `chmod -R o-rwx` 並設 `d:o::---`。

---

### A2. 〔Blocking｜Linux ACL Mask 事實錯誤〕預設 ACL `d:u:lorkhan:rwx` 擋不住 `mode 0600/0700` 與 `chmod 0644/0755`——使用者會被 `ACL_MASK` 鎖在門外，且寄件人可造出「連內圈都刪不掉的毒信」
- **位置**：02 §四（「每個夾都加預設 ACL：使用者 rwx——agent 之後建的檔，使用者照樣能改能刪」）、§八；03 §二 E2、E4
- **問題**：
  1. 依 Linux 核心 `posix_acl_create_masq()`，在有 Default ACL 的目錄下呼叫 `open(..., O_CREAT, mode)` 或 `mkdir(..., mode)` 時，新檔案的 **`ACL_MASK` 會與 `mode` 的群組位元 `(mode >> 3) & 7` 做位元 AND**；事後執行 `chmod` 也會直接改寫 `ACL_MASK`。
  2. **日常工具會鎖死內圈使用者**：Python 的 `tempfile.mkstemp()`、`NamedTemporaryFile`、`mkdtemp` 以及許多原子寫檔工具一律用 `0600`／`0700` 建檔。因為 `(0600 >> 3) & 7 == 0`，建出後 `ACL_MASK` 為 `---`，使得 `u:lorkhan:rwx` 變成 `#effective:---`！同理，agent 若跑 `chmod 0755 subdir` 或 `chmod 0644 file`，`ACL_MASK` 就變成 `r-x`／`r--`。若 `sub:N` 在工作區建了 `0700`（或 `chmod 0755`）的子目錄並在裡面放檔，內圈 `lorkhan`（uid 1000）因為不是該子目錄的 owner 且有效權限無 `w`，**連 `git checkout`、`rm -rf` 該子目錄或編輯該檔都會 `Permission denied`**（E4 只測了預設 `0666`/`0777`，沒測 `0600` 與 `chmod`）。
  3. **E2 信箱可被塞入「不可刪毒信」（DoS）**：在 `aos-post` 中，一封信是一個子目錄 `tmp/<信>/letter.json`。被注入的 `sub:6`（T2）是 `tmp/<信>` 的 owner，它可以 `mkdir("tmp/<信>", 0700)`（或在 `rename` 前 `chmod 0700 tmp/<信>`），裡面塞一個檔案再 `rename` 進 `new/<信>`。因為 Linux 禁止對非空目錄做 `rmdir`，而收件人 `sub:5` 與內圈 `lorkhan` 對 `new/<信>` 的有效權限都是 `---`（無法 `unlink` 裡面的 `letter.json`），這封信會變成**連收件人與內圈 daemon／LLM kernel 都無法刪除或清理的永久毒信**。
- **修法**：
  1. 第 0 期補測 `mkstemp(0600)` 與 `chmod 0644/0700` 對 Default ACL 的影響（見 B5）。
  2. 信箱改用「單檔投遞」（見 B1），或在 `aos-post take`／daemon 遇到 `EACCES` 壞信時自動以 `aos-asuser --fix` 奪回權限後刪除。

---

### A3. 〔Blocking｜威脅模型與 Linux Inode 語意錯誤〕02 §五／Q4「信夾 Linux 擁有者＝真寄件人，偽造不了、可關上 P7 假回信的洞」在現行 E2 設定下不成立
- **位置**：02 §五、§十一 Q4；03 §四 第 4 期
- **問題**：
  1. **原地覆寫（In-place overwrite）不改變 `st_uid`**：在 03 §二 E2 中，為了讓收件人 `sub:5` 能處理信件，信箱設了 `d:u:sub:5:rwx`。當內圈 `lorkhan`（uid 1000）寄信給 `sub:5` 時，`letter.json` 的 `st_uid` 是 `1000`，但同時繼承了 `u:sub:5:rwx`（**含寫入權 `w`**）！在 Linux 中，只要 `sub:5` 用 `open("letter.json", O_WRONLY | O_TRUNC)` 原地改寫內容（不刪檔重建），**inode 的 `st_uid` 依然是 `1000`（`lorkhan`）**！`sub:5` 可以拿任何一封以前 `lorkhan` 寄給它的信原地改寫成假回信，拿去騙看 `st_uid` 的驗證器。
  2. **`sub:N` 的 userns 內看別人的 `st_uid` 會變成 `65534 (nobody)`**：Linux `stat()` 透過 `from_kuid_munged()` 將真實 uid 轉成當前 userns 的 uid。若 `aos-asuser sub:5` 的 `uid_map` 只映射了 `lorkhan` 與 `sub:5` 自己，則 `sub:6`、`sub:7` 寄來的信在 `sub:5` 裡做 `stat()`，**`st_uid` 全部都是 `65534 (overflowuid)`**，根本分不出是誰寄的。
  3. **把專區 L1 驗證搞壞**：01 §4.3 E 指出現行專區 L1 `verify` 需讀取 `~/.aos/user/done/<月>/<原信名>/reply.json` 與 `log.jsonl`。但 02 §四把 `~/.aos/user`（done、log）設為中圈「進不去」，導致掛在中圈 `fsm` 隊長（`sub:auto`，02 §十）上的 `kernel_gate` 或驗證工具直接 `EACCES` 無法執行 L1 `verify`。
  4. **轉寄鏈不保留原寄件人 `st_uid`**：依 P4，請求經中間站轉寄時是由中間站重寫信件，`st_uid` 只代表「上一站」而非原始寄件人。
- **修法**：
  1. 收件人只讀不寫信件內容（見 B1），且 **不要靠收件人自己目錄下檔案的 `st_uid` 取代專區 L2 簽章**。
  2. 對中圈 agent 而言，只要 `~/.aos/user/done` 不可寫，它本來就無法連留底一起造假；若中圈站需要驗專區回信，應直接推進 P7 規劃的 **L2 `ed25519` 簽章**（公鑰唯讀公開，任何圈都能離線驗簽，不必讀私密的 `done/`）。

---

### A4. 〔Blocking｜User Namespace 巢狀與 `/etc/passwd` 事實錯誤〕中圈 `sub:N` 內無法再跑帶 `user` 的 `aos-sandbox`，且預設號段 `1..1000` 會與系統帳號撞號
- **位置**：02 §一、§三（硬限制 2 與號段）、§七（接鏈順序）、§十；03 §二
- **問題**：
  1. **中圈套外圈 `aos-sandbox` 的衝突**：02 §七寫接鏈為 `daemon → aos-asuser sub:N → rlimit → aos-sandbox → aos-exec → agent`，02 §十也規定施工 agent 在 `sub:N` 內跑測試／外來程式時再進 `aos-sandbox`。但行程一旦在 `aos-asuser sub:N` 的 userns 內：
     - 主機的 `root`（`kuid 0`）並未映射進此 userns，因此系統上 setuid-root 的 `newuidmap`、`sudo`、或 setuid 版 `bwrap` 的 setuid 位元與 file capabilities 會被核心直接忽略（`bprm_caps_from_vfs_caps` 回傳無特權）。只要 `sandbox.json` 寫了 `user`（不論是 `sub:M` 或 `aos-run`）必定失敗。
     - 就算 `sandbox.json` 不寫 `user`，`bwrap --unshare-all` 在 `sub:N` 內建第二層 userns 時無法呼叫 `newuidmap`，核心只准映射單一 uid（`sub:N`）與單一 egid，沙箱內看所有系統檔與 `lorkhan` 檔案 owner 全變 `65534 (nobody)`。
  2. **`uid_range: [1, 1000]` 在 userns 內與 `/etc/passwd` 系統帳號撞號**：若 `aos-asuser` 將 `1..60000` 映射到 `100000..159999` 並在 ns 內 `setresuid(N)`，當 `N` 取 `1..999`（02 §三預設 `1..1000`）時，在 ns 內查 `/etc/passwd` 的 `getpwuid(getuid())` 會直接撞上系統帳號（例如 `sub:1` 變成 `daemon`、`sub:5` 變成 `games`、家目錄變成 `/usr/games`、`sub:33` 變成 `www-data`）！而當 `N > 1000`（或映射成真號 `100004`）時，`getpwuid()` 回傳 `NULL`，Python `getpass.getuser()`、`Path.home()`、`ssh` 等工具會直接拋出 `KeyError: getpwuid(): uid not found`。
- **修法**：
  1. 若 agent 定義同時有 `limits.user: "sub:N"` 與 `sandbox`，應由 `aos-sandbox` 在最外層一次完成 userns 切換與 bwrap，不要在 `aos-asuser` 裡再包一層 `aos-asuser`；agent 內部呼叫外圈 `aos-sandbox` 時禁止填 `user` 欄位。
  2. `uid_range` 避開 `1..999`（改從 `10001` 起算），或在 `aos-asuser` 中明確測試並處理 `getpwuid()` 行為（見 B2、B5）。

---

### A5. 〔Blocking｜弄壞活樹與分期順序倒置〕第 1 期 `1a` 會立刻弄壞家機現有的 B6（`aos-run`），且把「`.env` 收 600」排在第 2 期換 uid 之前、第 4 期移金鑰之後，會害第 2 期 agent 啟動即崩潰
- **位置**：02 §四、§七、§九；03 §四 第 1 期 `1a`、第 2 期、第 4 期
- **問題**：
  1. **`1a` 直接弄壞已上線的 `aos-run`（B6）**：01 §4.1 D/F 記載家機已建好 `aos-run`（uid 951），且 B6 接鏈為 `sudo -n -k s6-setuidgid aos-run bwrap ...`——注意 **`bwrap` 是在變成 `aos-run`（uid 951）之後才執行**！`aos-run` 不在 `lorkhan` 群組裡，原本全靠 `~/aos-home` 的 `other (o=rx)` 穿越並綁定工作區或信箱。第 1 期 `1a` 一旦對 `~/aos-home` 跑 `chmod o-rwx`，所有存取 `~/aos-home` 下路徑的 `aos-run` 沙箱當場 `EACCES` 壞死。
  2. **第 1 期（`.env` 600）與第 2 期（換 uid）、第 4 期（金鑰移內圈）順序倒置**：01 §4.4 E 指出定義夾的 `.env` 是由 `aos-exec`（`find.cpp:108`）讀取，而 02 §七的接鏈是**先 `aos-asuser sub:N` 換完 uid，才執行 `aos-exec`**！第 1 期 `1a` 把 `.env`、token 檔與 `exec.json` 全部改成 `0600`（只有 `lorkhan` 可讀），但「金鑰只留內圈、fsm 定義不再放 key」卻排在**第 4 期**。結果到了第 2、3 期，任何換成 `sub:N` 的 agent 在 `aos-exec` 開場讀 `.env` 或工具讀 `env_file` 時直接拿到 `Permission denied`！
- **修法**：
  1. 若機器存在 `aos-run` 帳號，對 `~/aos-home` 做 `o-rwx` 時必須同步維持 `aos-run` 所需路徑的穿越權（或只在 `/srv/aos-run` 跑）。
  2. 將「換 `sub:N` 的 agent 改走內圈 LLM kernel、不再直接讀 `.env`」提前到第 2 期與 `sub:N` 綁在一起（或改由内圈在換 uid 前讀入白名單環境變數），絕不可在 `sub:N` 仍需讀 `.env` 時就把 `.env` 鎖成 `0600`。

---

### A6. 〔Important｜Linux `/proc` 與 `sweeper` 機制錯誤〕03 的 D1／`1d`（表上記 pid＋啟動時間）只修得到 `adopt`，修不到 `sweeper`
- **位置**：03 §二 E1、§三 D1、§四 `1d`
- **問題**：
  - `adopt` 是收養 daemon 表上有登記的頂層子行程，改記 `(pid, starttime)` 可行。
  - 但 `sweeper`（`py/aos_sweep_proc.py:130`）要清的是 **agent 用 `shell` 私自 fork 出去、脫離父行程且從未登記在 daemon 表上的孤兒孫行程**！孫行程的 PID 根本不在 daemon 表上，D1 的改法對 `sweeper` 完全無效，換 uid 後 `sweeper` 依舊一隻孤兒都清不到。
- **修法**：
  - Linux 的 `/proc/<pid>/status` 權限為 `0444`（跨 uid 可讀），裡面的 `Uid:` 與 `Gid:` 記錄了核心真實 uid（`100000+N-1`）與 daemon 群組（`sub:G`）。
  - 在「一隻 agent 一個 `sub:N`」的設計下，**`/proc/<pid>/status` 的 `Uid`/`Gid` 是核心保證、連 `env -i` 或 double-fork 都逃不掉的身分標籤**（比原本可被 `env -i` 洗掉的 `/proc/<pid>/environ` 還安全）！`sweeper` 應改讀 `/proc/<pid>/status` 的 `Uid`/`Gid` 對照 `uids.json` 與 daemon `group` 來清掃。

---

### A7. 〔Important｜Linux `tmux` 架構與行程樹事實錯誤〕02 §八／E3「只有 tmux 格子裡跑的指令前面多接 `aos-asuser sub:N`」會使 cgroup、rlimit、訊號與 `cli_cell.py` 全部失效
- **位置**：01 §4.3 F；02 §七、§八；03 §二 E3、§四 第 5 期
- **問題**：
  1. 若由 daemon 的 `limits.user` 先把子行程換成 `sub:N` 再跑 `aos-exec` → `cli_cell.py`：此時 `cli_cell.py` 已經是 `sub:N`（`100004`）。除了 `cli_cell.py:27` 的 `st_uid == os.getuid()` 檢查不過之外，**`tmux` server 本身在 C 層會用 `SO_PEERCRED` 檢查連線端 uid**，uid `100004` 連 uid `1000` 的 tmux socket 會被 server 直接踢掉。
  2. 反之，若照 02 §八讓 `cli_cell.py` 留在 uid 1000，發指令叫使用者的 tmux server 在 pane 裡跑 `aos-asuser sub:N -- ...`：**在 tmux 架構中，pane 裡的行程是由 `tmux server`（uid 1000）fork 出來的子行程，根本不是 `daemon` 的子行程**！結果 `daemon` 設的 `rlimit`、B5 `cgroup`、以及 `tend.cpp` 按 pid/pgid 送的 `SIGTERM`/`SIGKILL` 全都管不到 pane 裡的 agent。
- **修法**：
  - 換 uid 的 CLI/eca agent 應由 `daemon` 在該 agent 的 cgroup／rlimit／`sub:N` 內啟動專屬的 `tmux -S <stack>/tmux.sock` server；使用者看畫面則透過 `aos-agent attach <name>`（內部自動接 `aos-asuser sub:N -- tmux -S ... attach`）。

---

### A8. 〔Important｜Git `safe.directory` 漏列施工項〕E4 測試手動加了 `--git-safe`，但 02／03 施工項漏掉在 daemon 啟動 `sub:N` 時注入該設定
- **位置**：02 §八；03 §二 E4、§四 第 2/3 期
- **問題**：
  - 03 §二 E4 寫「帶 `--git-safe` 跑 `git status` 成功」。自 Git 2.35.2（CVE-2022-24765）起，只要 `.git` 擁有者（`1000`）與當前 euid（`100004`）不同，agent 在 `shell` 工具裡跑任何 `git status`／`git diff` 都會報 `fatal: detected dubious ownership`；若 agent 照提示跑 `git config --global --add safe.directory`，又會因寫不進 `/home/lorkhan/.gitconfig` 而 `EACCES`。
  - 02 與 03 第 2、3 期的 daemon 施工項完全沒提自動注入 `--git-safe` 的環境變數（`GIT_CONFIG_COUNT` 等）。
- **修法**：daemon 啟動 `sub:N`（或 `aos-asuser` 預設）自動帶入 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=*`（見 B2）。

---

### A9. 〔Important｜多台 daemon 撞號與不可逆退回（Rollback）缺陷〕頂層預設號段重疊會造成活樹與測試樹互殺；`--fix` 退回不會清除 Default ACL 與 sticky
- **位置**：02 §三、§九；03 §二 E1、§四 第 2 期 `2d`
- **問題**：
  1. **多 daemon 撞真 uid/gid**：02 §三將頂層 daemon 預設 `uid_range` 定為 `[1, 1000]`、群組從 `60001` 起。但使用者常同時跑活樹與暫存測試樹（如 03 `2d` 在 `/tmp` 起暫存樹試跑）。兩台頂層 daemon 的一號 agent 都會拿到 `sub:1`（真號 `100000`）。如 E1 實測所證，**不同 userns 但同一個真號 `100000` 在核心裡是同一個人**，測試樹的 `sub:1` 可直接 `kill -9` 或讀寫活樹的 `sub:1`，且共用同一個 `RLIMIT_NPROC`！
  2. **第 2、3 期退回不乾淨**：
     - 02 §九寫第 2 期退回只需「把那格（`limits.user`）拿掉」。但第 2 期已把信箱 `tmp/`、`new/`、`cur/` `chown` 給 `100004` 並設了 sticky（`1730`）。若不跑 `--fix` 就拿掉 `limits.user`，agent 變回 uid `1000`，不再是 sticky 目錄 `new/` 的 owner，別人寄來的信它反而 `rename` 不進 `cur/`（`EPERM`）！
     - 第 3 期退回寫「改回 `off`，跑一次 `aos-asuser --fix`」。但 `--fix` 只改回 owner 與 `u+rw`（01 §4.1 C），**不會拔掉滿樹的 Default ACL（`d:g::---`、`d:o::---`）與信箱 sticky bit（`1730`）**，退回後新建檔案仍受殘留 Default ACL 影響。
- **修法**：
  1. 在 `~/.aos/uid_alloc.json` 集中登記各棵 daemon 樹的號段與群組號，禁止多台 daemon 撞號。
  2. 新增 `aos-share reset -R PATH`（執行 `aos-asuser --fix -R` ＋ `setfacl -b -R` ＋ 還原信箱 `1730 → 0700/0755`），列為第 2、3 期正式退回步驟。

---

### A10. 〔Important｜違反 P5 (K17)、01 §三 分工邊界與內圈 Symlink 越權洞〕
- **位置**：01 §二 P5、§三、§4.4 B；02 §四、§七、§八；03 §四 `2c`
- **問題**：
  1. **與 P5 (K17) 衝突**：K17 裁定「子 daemon 的 agent 不帶上層群組」。若子 daemon 設了自己的群組 `sub:G2`，其 agent 不帶頂層 `sub:G1`，則頂層只對 `sub:G1` 開 `knowledge/` 唯讀或路徑穿越時，子 daemon 的 agent 會全部進不去。
  2. **違反 01 §三「不改 B6 圖紙」**：01 §三明定「B6 sudo 接鏈（已派工）照它的線走，本線不改它的圖紙」，03 `2c` 卻把「sandbox 設定壞掉改拒起」塞給「ok-limits（B6 那支）」，還設條件「在 `limits.user` 有設時」（但 `sandbox.json` 若語法壞掉，`aos-sandbox` 根本讀不出裡面的 `user`，也不知道外層 daemon 有無設 `limits.user`）。
  3. **內圈跟隨中圈 Symlink 越權**：01 §4.4 B 指出 `write`/`edit` 工具會先 `realpath` 跟隨 symlink。02 §八讓中圈施工 agent 可寫 repo 子夾、再交由內圈（eca 隊長或使用者）修改與 commit。被注入的中圈 agent 只要在可寫子夾建一個指向內圈 `procs_ctl.json`、`hooks.json` 或 `~/.bashrc` 的 symlink，內圈 eca 用 `write`/`edit` 修改該檔時就會代為覆寫內圈敏感檔。
- **修法**：
  1. `knowledge/` 等共用唯讀夾在子 daemon 啟動時自動補上子 daemon 的 `sub:G2` ACL。
  2. `aos-sandbox` 設定壞掉應**無條件拒起**（符合 P6 精神），作為獨立小項交給 `aos-sandbox`，不綁 B6。
  3. `tool_io.py` 的 `write`/`edit` 解路徑後應檢查 `realpath` 是否越出工作區／子夾邊界，拒絕跨界 symlink。

---

### A11. 〔Minor｜本機 IPC 與共享鎖〕未進 bwrap 的中圈 agent 共享 `/tmp`、`127.0.0.1` 與 `flock`
- **位置**：01 §4.3 F；02 §二、§七
- **問題**：
  1. `aos-asuser` 只開 `CLONE_NEWUSER`，未開 mount／net namespace。所有未進 bwrap 的中圈 agent 與內圈共享 `127.0.0.1`（如專區 web server、本機 MCP HTTP server）與 `/tmp`。
  2. 01 §4.3 F 提到共用回信鎖 `.reply.lock`；且在 Linux 中，**只要對任何檔案有唯讀權限（`O_RDONLY`），就能呼叫 `flock(fd, LOCK_EX)` 上排他鎖**！若內圈 daemon 或工具對某個中圈可讀的檔案（如 `procs_state.json` 或 `.reply.lock`）使用 `flock`，中圈 agent 可故意長抱 `LOCK_EX` 凍死內圈。
- **修法**：內圈自用的 `flock` 鎖檔必須放在中圈不可讀的 `0700` 目錄內；回信鎖改為每收件人獨立或不用跨圈共用鎖檔。

---

## (B) 提案：更簡潔的替代設計、漏掉的實驗與分期重切

### B1. 提案 1：信箱改用「單檔投遞」或「收件人無 `w` 預設 ACL」（一次解決 E2 毒信、D3 跨 ns chown、以及 Q4 `st_uid` 竄改問題）
- **為什麼現在的 E2 很重**：因為 `aos-post` 投遞的是**子目錄** `tmp/<信>/letter.json`，為了讓收件人之後能刪信，被迫給 `d:u:<收件人>:rwx`，結果：(1) 寄件人能把子目錄 `chmod 0700` 造出刪不掉的毒信（A2）；(2) 收件人拿到 `letter.json` 的 `w` 權限，能原地竄改內容卻保留寄件人 `st_uid`（A3）；(3) 建信箱還得開整段映射 userns 去 `chown`（D3）。
- **更簡單的改法**：
  - 在 Linux VFS 中，刪除（`unlink`）或搬移（`rename`）一個**普通檔案**，只需要對**父目錄**（`new/`、`cur/`）有 `wx` 權限，**完全不需要對檔案本身有任何 `r` 或 `w` 權限**！
  - 只要將沒有附件的一般信件（99% 的控制信、請求信、回信）改為直接投遞單一檔案 `tmp/<信>.json` → `rename` 至 `new/<信>.json`，並將信箱預設 ACL 設為 **`d:u:<收件人>:r--`、`d:u:lorkhan:r--`（唯讀，不給 `w`）**：
    1. **絕對沒有毒信**：寄件人就算把 `<信>.json` `chmod 0000`，收件人與內圈照樣能直接 `unlink` 刪掉。
    2. **`st_uid` 真正不可竄改**：收件人對 `<信>.json` 只有 `r--` 沒有 `w`，無法原地改寫檔案內容；若刪掉重建，`st_uid` 就會變成收件人自己。這時檔案的 `st_uid` 才是核心保證的真寄件人！

---

### B2. 提案 2：為 `sub:N` 自動建立 `<stack>/home` 虛擬家目錄與輕量 Mount Namespace（根治 Q9 祖先夾、點檔案外洩與 Git 報錯）
- **做法**：
  1. **不動 `/home/lorkhan` 的 `0700`**：若使用者不想手動把 `~/aos-home` 搬去 `/srv`，可在 `aos-asuser`（或 daemon）開 userns 時順手加 `CLONE_NEWNS`（免 root），將 `~/aos-home` bind-mount 到固定的 `/tmp/aos-$USER/aos-home`（或僅將工作區與 stack 掛過去），完全不必在 `/home/lorkhan` 打洞。
  2. **專屬 `$HOME` 與 Git 環境**：daemon 啟動 `sub:N` 時，自動建立 `<stack>/home/`，並將子行程環境變數設為：
     - `HOME=<stack>/home`、`XDG_CONFIG_HOME=<stack>/home/.config`、`XDG_CACHE_HOME=<stack>/home/.cache`
     - `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=*`
  3. **好處**：所有工具（Python、git、npm、Claude CLI）讀寫 `~/.config`、`~/.cache`、`~/.gitconfig` 都自然落進該 agent 自己的 stack 內，不會去碰 `/home/lorkhan` 而撞 `EACCES`，也不用擔心家目錄點檔案外洩。

---

### B3. 提案 3：第 4 期 LLM Kernel 不必做「一人一個投遞口」，直接對單一投遞口讀 `st_uid` 即可記帳（大幅簡化 D7）
- **現況痛點**：02 §五與 03 D7 規劃在第 4 期為每隻 agent 在 LLM kernel 開獨立的投遞口（`一人一個投遞口`），這會讓 daemon 每次 `ctl add`/`remove` 都要連動增刪 LLM kernel 的信箱目錄。
- **更簡單的設計**：
  - LLM kernel 跑在內圈（uid 1000），在主機 namespace 裡看得到所有 `sub:N` 的真實 `st_uid`（`100000+N-1`）。
  - 當 `sub:N` 把請求丟進現有的同一個 `requests/new/` 時，因為 `sub:N` 在自己的 userns 裡沒有別的 uid 可 `chown`，信件的 `st_uid` 必然是 `100000+N-1`。
  - LLM kernel 取信時直接 `stat()` 讀 `st_uid`，查 `uids.json` 換成 agent 名稱來記 `budget.senders` 額度即可！**維持單一投遞口、不改信封格式、符合 P1/P3 精神、零動態目錄管理成本**。

---

### B4. 提案 4：用 `/proc/<pid>/status` 的 `Uid`/`Gid` 統一處理 `adopt`、`sweeper` 與強殺殘留行程（升級 D1／`1d`）
- **做法**：
  1. `adopt`：比對 `(pid, starttime)`（`/proc/<pid>/stat` 第 22 欄）＋ `/proc/<pid>/status` 的 `Uid`。
  2. `sweeper`（`aos_sweep_proc.py`）：改掃 `/proc/<pid>/status`（權限 `0444`），只要真實 `Uid` 屬於本 daemon 的 `uids.json` 或 `Gid` 等於本 daemon 的 `sub:G`，且不在活躍 proc 樹中，即判定為孤兒行程並清理。
  3. `tend.cpp`（停用／強殺 agent）：當一隻 `sub:N` agent 被 `stop`/`kill` 時，除了殺 pgrp，還可直接用 `aos-asuser sub:N -- kill -9 -1`！**在 Linux 中，以特定 uid 執行 `kill(-1, SIGKILL)` 會由核心原子性地殺死該真 uid 名下的所有行程（包含 `setsid` 脫離群組的背景孫行程）**，連 cgroup 都沒開時也能做到一鍵全殺！

---

### B5. 提案 5：第 0 期應補做的 4 個關鍵實驗（E3-full、E7、E8、E9）
在進入第 1、2 期改碼前，建議在暫存夾補跑以下 4 個免 root 實測：
1. **E3-full（tmux 雙向實測）**：
   - (a) 在 `aos-asuser sub:5` 內連 uid 1000 的 `tmux -S` socket，驗證 `SO_PEERCRED` 是否拒絕連線；
   - (b) 由 uid 1000 的 tmux pane 跑 `aos-asuser sub:5`，驗證 pane 行程是否脫離 daemon 的 rlimit／cgroup。
2. **E7（ACL Mask 鎖死與毒信實測）**：
   - 在 E2 的目錄下，讓 `sub:6` 用 Python `tempfile.mkstemp()`（`0600`）與 `mkdir("tmp/poison", 0700)` 建檔並丟進 `new/`，驗證 `lorkhan` 與 `sub:5` 是否會因 `ACL_MASK=---` 而無法讀寫與刪除；並測試 `sub:5` 用 `O_WRONLY|O_TRUNC` 原地改寫 `lorkhan` 寄來的 `letter.json` 後 `st_uid` 是否仍為 `1000`。
3. **E8（`sub:N` 內跑 `aos-sandbox` 與 `getpwuid`）**：
   - 在 `aos-asuser sub:5` 內執行 `aos-sandbox`（不帶 `user`），以及執行 `python3 -c "import getpass; print(getpass.getuser())"`，確認巢狀 bwrap 與 `/etc/passwd` 撞號／找不到 uid 的實況。
4. **E9（B6 `aos-run` 與 `.env` 600 相容性實測）**：
   - 驗證頂層目錄 `o-rwx` 後 `aos-run` 綁定是否失敗，以及 `.env` 設 `0600` 後 `sub:5` 跑 `aos-exec` 是否報錯。

---

### B6. 提案 6：重切分期（消除相依倒置，確保每期不壞活樹、可一鍵退回）

| 期別 | 內容（修正後） | 為什麼這樣切 |
|---|---|---|
| **第 0 期：實測補齊** | 已完成 E1、E2、E4；補跑 **E3-full、E5（公司 WSL）、E7（ACL mask／毒信）、E8（巢狀 sandbox／getpwuid）、E9**。 | 把 A1～A8 的核心邊界一次摸清，不留未爆彈進施工期。 |
| **第 1 期：底座整備（不鎖 `.env`、不擋 B6）** | 1. `adopt`＋`sweeper` 改用 `/proc/<pid>/status`（`Uid`/`Gid`）＋`starttime`（B4）。<br>2. `aos-share check` 與 **`aos-share reset -R`**（含 `setfacl -b -R` 與還原 mode，修 A9）。<br>3. `aos-sandbox` 設定檔損壞無條件拒起（獨立小項，不碰 B6，修 A10）。<br>4. `tool_io.py` 的 `write`/`edit` 攔截跨工作區 symlink（修 A10）。<br>5. Chore 腳本：只收緊確定不跨 uid 讀取的私密檔；若對 `~/aos-home` 做 `o-rwx`，同步給 `aos-run` 補 `--x` ACL（修 A5）。 | 完全不改用法、不影響 `ok-release`、不弄壞現有 B6，且為第 2 期準備好真正的退回工具 `aos-share reset`。 |
| **第 2 期：單隻自願換 uid（含環境與金鑰解耦）** | 1. daemon 支援 `limits.user: "sub:N"`、跨 daemon 號段登記防撞（修 A9、`uid_range` 從 `10001` 起避開 `/etc/passwd`）。<br>2. daemon 啟動 `sub:N` 自動配 `<stack>/home` 與 `--git-safe` 環境變數（B2、修 A8），並在安全模式下對 stack 設 `umask 0077`。<br>3. **要換 `sub:N` 的 fsm 角色同步改走內圈 LLM kernel（不直接讀 `.env`）**，此時才將其定義夾 `.env` 與 `exec.json` 鎖為 `0600`（修 A5）。<br>4. 信箱支援單檔投遞或壞信自動 `--fix`（B1、修 A2）。 | 把原第 4 期「agent 不拿 key」與第 2 期「換 uid」對同一隻角色綁在一起落地，避免 `.env 600` 撞死 `sub:N`。退回只需拿掉 `limits.user` 並跑 `aos-share reset`。 |
| **第 3 期：整台開 `security: on`（公開 demo 後）** | 1. 活樹放家目錄外或用 mount ns 隔離（不動 `/home/lorkhan` 700，修 A1）。<br>2. `sub:auto`、鎖 daemon `ctl` 箱（P1）、`knowledge/` 自動對父子 daemon 群組鋪唯讀 ACL（修 A10）。<br>3. **合併原第 4 期額度**：LLM kernel 直接讀 `requests/new/` 信件的 `st_uid` 記 `budget.senders`（B3，免開多投遞口）。 | 所有會動到安裝路徑與全域開關的改動集中在公開 demo 之後。 |
| **第 4 期：專區 L2 簽章與 eca 換 uid（可選）** | 1. 專區回信上 L2 `ed25519` 簽章（修 A3，中圈可離線驗公鑰）。<br>2. eca 身進 `sub:N`：由 daemon 在 `sub:N` 內起獨立 tmux server，提供 `aos-agent attach`（修 A7）。 | 徹底補齊 P7 與內圈 eca 的最後一塊拼圖。 |
| **第 5 期：Root 可選加碼** | R-a～R-c（nftables 按 uid 斷網、quota 等）。 | 有需求才開。 |
