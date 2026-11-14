# sec-1114 08：Argon 審 07（Q10 施工計劃）原文

> agy `Gemini 4 Argon (High)` `--mode plan`，11-14 下午。prompt＝06＋07＋sol-5＋sol-6 原文（`/tmp/ok-sec-argon-q10/prompt.txt`）。下面一字不改；採不採見 [09 採納表](09-Q10採納表.md)。

以下為 Argon 對 `07-Q10施工計劃.md` 的審查意見，分 **(A) 施工計劃問題審查** 與 **(B) 簡化與安全替代方案** 兩部分。

---

## (A) `07-Q10施工計劃.md` 具體問題審查

### 一、Linux 系統呼叫、檔案系統語意與 Crash Windows

#### 1. `renameat2(..., RENAME_NOREPLACE)` 在認領競爭時回傳 `EEXIST` 而非 `ENOENT`，且不支援時的 `errno` 不只 `EINVAL`
- **章節**：一（新格式：投遞、認領、歸檔、撤信）
- **嚴重度**：**Blocking**
- **問題**：
  1. **Linux VFS 檢查順序（`fs/namei.c:do_renameat2`）**：核心先檢查 `if ((flags & RENAME_NOREPLACE) && d_is_positive(new_dentry)) return -EEXIST;`，**之後**才檢查 `if (d_is_negative(old_dentry)) return -ENOENT;`。當兩個消費者同時認領同一封 `new/<名> → cur/<名>`，A 成功後 `cur/<名>` 已存在、`new/<名>` 已消失；此時 B 呼叫 `renameat2(new/<名>, cur/<名>, RENAME_NOREPLACE)` 會拿到 **`EEXIST`**，而非 `ENOENT`（舊版一般 `rename` 夾時 B 拿到 `ENOENT`）。若 `take()` 只把 `ENOENT` 視為「已被他人認領」而把 `EEXIST` 當成 `LetterExists` 拋錯，並行認領會直接炸開。
  2. **Fallback `errno` 不完整**：檔案系統、舊核心、容器 seccomp 或 WSL/FUSE/NFS 不支援 `renameat2` 或 `RENAME_NOREPLACE` 時，除了 `EINVAL` 外，還會回傳 **`ENOSYS`** 或 **`EOPNOTSUPP`（`ENOTSUP`）**。只接 `EINVAL` 會在這些環境直接失敗。
  3. **`LetterExists` 的 `errno` 來源改變**：舊版夾對非空目標夾 `rename` 失敗回 `ENOTEMPTY`（或 `EEXIST`）；改成單檔加 `RENAME_NOREPLACE` 後只會回 **`EEXIST`**，`send.cpp` 若只判 `ENOTEMPTY` 會漏轉 `ErrorCode::LetterExists`。
- **修法**：
  1. Fallback 條件改為 `errno == EINVAL || errno == ENOSYS || errno == EOPNOTSUPP`。
  2. 在 `take()`（`new → cur`）若 `renameat2` 回 `EEXIST` 且 `lstat(new/<名>)` 為 `ENOENT`，視為已被其他消費者認領（等同 `ENOENT` 跳過），不拋 `LetterExists`。
  3. `send.cpp` 將 `EEXIST` 明確映射為 `ErrorCode::LetterExists`。

#### 2. 退回 `link` + `unlink` 在跨 UID（`fs.protected_hardlinks=1`）會 `EPERM`，且具非原子視窗
- **章節**：一（新格式）
- **嚴重度**：**Blocking**
- **問題**：
  1. **跨 UID 硬連結限制**：現代 Linux（含 Ubuntu/WSL2）預設 `sysctl fs.protected_hardlinks = 1`。Q10 的目標正是為第 2/3 期跨 UID 信箱鋪路；當收信端或 daemon（不同 UID，無 `CAP_FOWNER`）對寄信人擁有的信檔做 `new → cur` 或 `cur → archive` 時，若信檔非收信端可讀寫，呼叫 `link()` 會被核心 `may_linkat()` 以 **`EPERM`** 拒絕（而 `rename()` 只看目錄寫入權限與 sticky bit，不看檔案 owner）。
  2. **非原子與 Crash Window**：`link(src, dst)` 成功到 `unlink(src)` 完成之間，`st_nlink == 2`，檔案同時存在於 `tmp/` 與 `new/`（或 `new/` 與 `cur/`）。若行程死在兩步之間，信件會在兩格重覆出現且共用同一個 inode；若 `regret()` 在此視窗對 `new/<名>` 做 `unlink`，寄信人以為撤信成功，收信端卻同時在 `cur/<名>` 拿到信。
- **修法**：
  - **投遞（`tmp → new`）**：由寄信人自己執行（同 UID），`renameat2` 不支援時退回 `link` + `unlink` 可行（若 `unlink` 前 crash，收信端認領後只剩 `cur/`）。
  - **認領（`new → cur`）與歸檔（`cur → archive`）**：不應退回 `link` + `unlink`。若 `renameat2(RENAME_NOREPLACE)` 回 `EINVAL/ENOSYS/EOPNOTSUPP`，應退回 `lstat(dst)` 確認不存在後直接 `rename(src, dst)`（單一收信人或持 `.flock` 的 kernel 絕對安全）。

#### 3. `send_prepared` / `send_held` 的 fd 生命週期與寫入 Flush 順序
- **章節**：一、二（2a 寄信人鎖）
- **嚴重度**：**Blocking**
- **問題**：
  1. **關檔掉鎖**：2a 寫「callback 拿到已開好的 fd 和 tmp 路徑，寫信封仍由 aos-post 做。aos-llm 的 `hold_sender` 改成在這個 fd 上 flock，並把 fd 留著」。若 `aos-post::send_prepared` 寫完信封後照常 `close(fd)`（或用 RAII 關閉），因為 `hold_sender` 拿的是同一個 fd 整數，**`close(fd)` 會直接釋放 `flock`**（甚至導致 `aos-llm` 留著的 fd 編號被後續 `open` 重用）！
  2. **未 flush 即 rename**：若 `send_prepared` 另開 `std::ofstream(tmp_path)` 寫信封，或在寫入後未 `flush` / `close` 寫入流就呼叫 `renameat2(tmp, new)`，讀信端在 `new/` 會讀到 0 byte 或半截 JSON。
  3. **錯誤清理漏 fd**：若 `hold_sender` 已複製/保存 fd，但後續寫檔或 `renameat2` 失敗拋出 `Error`，該 fd 若未關閉會洩漏至行程結束。
- **修法**：
  - `send_prepared` 以 `O_CREAT|O_EXCL|O_RDWR|O_CLOEXEC` 開 `tmp/.<id>`，呼叫 `prepare(fd, tmp_path)`；`hold_sender` 用 `fcntl(fd, F_DUPFD_CLOEXEC, 0)` 複製出自己的 `held_fd` 並上 `flock(held_fd, LOCK_EX|LOCK_NB)`。
  - `send_prepared` 用自己的 `fd` 完整寫入（`write` 迴圈寫滿）後 `close(fd)`（`held_fd` 仍持有同一個 open file description，故 `flock` 不掉），再 `renameat2` 至 `new/<id>`；若 `renameat2` 失敗，caller 負責任關掉 `held_fd`。

#### 4. `flock` 跨 `rename`、唯讀 fd 與 NFS / WSL 9p 行為邊界
- **章節**：二（2a）
- **嚴重度**：**Important**
- **問題**：
  - 在 Linux 原生檔案系統（ext4、xfs、tmpfs）上，`flock` 綁在 kernel `struct file` 與 `struct inode` 上，跨同檔案系統 `rename` 不掉鎖，且 `O_RDONLY` fd 可正常 `flock(LOCK_SH|LOCK_NB)`。
  - **但有兩個系統陷阱**：
    1. **NFS（Linux 2.6.12+ 將 `flock` 轉為 POSIX `fcntl` 鎖）**：在同一行程內，只要對同一個 inode 做 `open` + `close`（例如寄信端做 `--keep-to` 重開剛寄出的信檔再關掉），POSIX 鎖語意會把該行程持有的 `flock` **整把釋放**！
    2. **WSL2 9p（DrvFs，如 `/mnt/c`）**：被持鎖或開啟中的檔案做 `rename` 或 `RENAME_NOREPLACE` 在 Windows host 層會回 `EACCES` 或 `EINVAL`。
- **修法**：在 N-16 與知識庫明訂信箱必須位於 Linux 本地檔案系統（ext4/tmpfs/xfs），不支援 NFS 與 WSL DrvFs（`/mnt/c`）；且寄信端在持有 `held_fd` 期間不得以同一行程再次開啟又關閉該信檔。

#### 5. `done()` 與 `regret()` 沿用 `cur/new → tmp → drop` 對單檔是多餘且危險的
- **章節**：一、二（2c）、三
- **嚴重度**：**Important**
- **問題**：
  - 舊版因信是「非空資料夾」無法原子 `rmdir`，才必須先 `rename` 到 `tmp/<名>` 再 `remove_tree`。
  - 改成單檔後，`unlink("cur/<名>")` 與 `unlink("new/<名>")` 本身就是單一 VFS 原子操作。若仍先用 `RENAME_NOREPLACE` 搬去 `tmp/<名>`，一旦 `tmp/<名>` 有同名殘骸就會因 `EEXIST` 導致刪信或撤信失敗！
- **修法**：
  - `regret(名)`：直接 `unlink(new/<名>)`；成功回 `true`，`ENOENT` 回 `false`（代表已被認領進 `cur/`）。`aos-llm/src/wait/wait.cpp:147` 訊號撤回亦同，直接 `unlink(new/<id>)` 即可，不必先搬 `tmp/`。
  - `done(名, keep=false)`：若 `cur/<名>` 是一般檔（或 symlink/FIFO），直接 `unlink(cur/<名>)`；僅當 `lstat` 發現是舊版資料夾時，才 `rename` 至 `tmp/.drop.<ns>.<pid>` 後 `remove_tree`。

#### 6. `see()` 與直接讀信端未用 `lstat` 檢查 `S_ISREG`，存在 FIFO 阻塞與 Symlink 漏洞
- **章節**：一（壞信定義）、三（讀信端）
- **嚴重度**：**Blocking**
- **問題**：計劃只寫「格子裡的項目是資料夾（舊版信）＝壞信」。在跨 UID 信箱下，若惡意或異常寄信人在 `new/` 放入 **FIFO（named pipe）**、device node 或 **symlink**，讀信端（`aos-post see`、`aos-llm-kernel`、`aos-mailbox peek`、`user_verify`）只判 `!is_directory` 就直接 `open()` 讀取：
  - 讀到 FIFO 會**永久阻塞（DoS 整個 daemon 或 kernel）**；
  - 讀到 symlink 會跨權限讀取目標檔或讀 `/dev/zero` 撐爆記憶體。
- **修法**：所有讀信端開檔前必須 `lstat(path)`（或 `open(..., O_RDONLY|O_NOFOLLOW|O_NONBLOCK)` 後 `fstat`），**只允許 `S_ISREG(st.st_mode)`**。舊資料夾回報 `old folder letter`，其餘非一般檔（symlink/FIFO/socket）一律判為壞信 `not a regular file` 並直接 `unlink`，絕不讀取內容。

#### 7. Python 端 `os.rename` 認領會靜默覆蓋 `cur/<名>`
- **章節**：一、三（`daemon_ctl._claim`、ok-board C1）
- **嚴重度**：**Minor**
- **問題**：計劃稱「信名是奈秒加 pid，cur/ 有同名檔本來就是異常」。但 `aos-post` 允許自訂信名與重排回 `new/`；對一般檔而言，`os.rename(new/<名>, cur/<名>)` 若遇 `cur/<名>` 已存在會**靜默覆寫**正在處理中的信（舊版資料夾時 `os.rename` 會因 `ENOTEMPTY` 失敗保護）。
- **修法**：Python 端 `_claim` 若在單一消費者情境下，至少先 `if os.path.lexists(dst): raise FileExistsError(...)`（或呼叫 `aos-post take <名>`）。

---

### 二、寄信人 / Kernel / 收信人競爭與 `work/` 恢復漏洞

#### 8. `sweep()` 在 `tmp/`「讀不成 JSON 就跳過」導致死信永久洩漏與讀寫競爭
- **章節**：二（2a `sweep` 規則）
- **嚴重度**：**Blocking**
- **問題**：
  1. **永久殘骸漏洞**：2a 規定「`tmp/` 裡點開頭的檔，如果讀不成 JSON（空檔或寫到一半），就跳過」。若 `send_held` 在步驟 1（`open(tmp/.<id>)`）後、或步驟 3 寫 JSON 寫到一半時被 `SIGKILL` / OOM / `ENOSPC` 殺死，該 `tmp/.<id>` 是 0 byte 或半截 JSON，**`sweep()` 會永遠跳過它，永遠清不掉**！
  2. **順序顛倒**：`send_held` 在步驟 2（寫任何 byte 之前）就已經對 `tmp/.<id>` 上了 `flock(LOCK_EX)`！因此只要寄信人還活著正在寫，該檔**一定已經鎖著**。先讀 JSON 再測鎖，不僅多此一舉，還會在寄信人 `write()` 途中去讀半截檔案。
  3. **一般信 `tmp/<名>` 的處理未定義**：`sol-5` C 指出 `sweep()` 會掃 `tmp/` 全部項目。一般非同步 `aos-post send` 在 `tmp/<名>`（非點開頭）寫信時不上 `flock`；若 `sweep()` 掃到正在寫的 `tmp/<名>`，必須確保不會誤刪。
- **修法**：
  - `tmp/` 中點開頭的 `tmp/.<id>` 專屬於 `send_prepared`（即 `send_held`）：`sweep()` **先測 `flock(LOCK_SH|LOCK_NB)`**，不讀 JSON！
    - 若回 `EWOULDBLOCK`：寄信人活著（正在寫或準備 rename），跳過。
    - 若沒鎖住（拿到鎖）：代表寄信人已死，或處於步驟 1 `open` 到步驟 2 `flock` 之間的微秒視窗。此時只要 `mtime` 距今超過 2 秒（或已能解析出完整 JSON），直接 `unlink(tmp/.<id>)`。
  - `tmp/` 中非點開頭的一般檔 `tmp/<名>`：若無鎖且 `mtime` 超過逾時門檻（例如 60 秒）亦應清掉，避免一般 `send` 死在 `tmp/` 留下永久孤兒檔。

#### 9. `work/<信名>/` 回復漏洞一：退回 `new/` 的清理順序相反，重認領時 `mkdir work/<名>` 會 `EEXIST`
- **章節**：二（2b 工作目錄）
- **嚴重度**：**Blocking**
- **問題**：2b 寫「兩個都沒有＝把信搬回 `new/`，並清掉 `work/<名>/`」。
  1. 若 kernel 把 `cur/<名>` 搬回 `new/<名>` 後、還沒刪 `work/<名>/` 就 crash，下次重啟時 `collect` 掃 `cur/` 看不到 `<名>`；接著若 `scan` 先於 `work/` 清理跑（見 `sol-5` C：順序為 `collect → sweep → scan`），`scan` 認領 `new/<名> → cur/<名>` 後執行 `mkdir work/<名>/` 會直接因 **`EEXIST`** 失敗！
  2. 即使沒 crash，若 `work/<名>/` 殘留前一次的 `request.json` 或半截檔案，沒先清乾淨就重跑會污染狀態。
- **修法**：
  1. 回復搬回 `new/` 時，**必須先 `remove_tree(work/<名>)`，再 `rename(cur/<名>, new/<名>)`**。
  2. 認領 `new/<名> → cur/<名>` 後準備建 `work/<名>/` 時，先執行 `remove_tree(work/<名>)` 再 `mkdir(work/<名>)`。
  3. 孤兒 `work/` 的清理放在 `sweep()` 階段（`scan()` 之前）執行。

#### 10. `work/<信名>/` 回復漏洞二：收尾死在「寄出回信後、刪 `cur/<名>` 前」會重覆寄出回信
- **章節**：二（2b 工作目錄）
- **嚴重度**：**Blocking**
- **問題**：2b 規定收尾順序：「寄出回信，把 `reply_letter.txt` 寫進 `work/`，接著先刪 `cur/<名>`，再刪 `work/<名>/`」，而回復規則寫「只有 `reply.json`＝補寄」。
  - 若 kernel 在寄出回信並寫入 `work/<名>/reply_letter.txt` 之後、`unlink(cur/<名>)` 之前 crash：
  - 重啟後 `cur/<名>` 還在，`work/<名>/reply.json` 也還在！若回復只看 `reply.json` 存在就補寄，收信人會**收到兩封回信**！
- **修法**：回復檢查 `work/<名>/` 時，若 `reply_letter.txt` 已存在，代表回信**已經寄出**，不可再補寄；只需檢查 `!sender_alive(cur/<名>)` 時對 `reply_letter.txt` 記載的回信執行 `regret`，然後直接刪 `cur/<名>` 與 `work/<名>/`。

#### 11. `work/` 每拍清理的「也沒有正在跑的 proc」判準不明確
- **章節**：二（2b 工作目錄）
- **嚴重度**：**Important**
- **問題**：2b 寫「kernel 每拍掃一次 `work/`：`cur/<名>` 不在、也沒有正在跑的 proc，就清掉」。但 kernel 的 `collect` 只掃 `cur/`！當 `cur/<名>` 已不在時，kernel 記憶體中根本沒有該項目的執行狀態；若不讀 `work/<名>/proc.json` 檢查 PID，怎麼知道「有沒有正在跑的 proc」？反之，正常流程中只有 `finish` 收尾完才會刪 `cur/<名>`（`cur/<名>` 是唯一的 claim 憑證）。
- **修法**：明訂規則：掃到 `work/<名>/` 但 `cur/<名>` 不存在時，若 `work/<名>/proc.json` 存在且該 PID 仍存活（例如有人手動誤刪了 `cur/<名>`），先 kill 該 proc（或等其結束），再 `remove_tree(work/<名>)`；否則直接 `remove_tree(work/<名>)`。

---

### 三、漏算的讀寫端與跨線衝突

#### 12. C++ 與 Python LLM kernel 的 `scan` / `sweep` 仍寫死 `is_directory` 過濾
- **章節**：二、三
- **嚴重度**：**Blocking**
- **問題**：`sol-5` C 指出 `aos-llm-kernel/src/serve/serve.cpp:88`、`scan.cpp:75` 以及 `lib/aos/kernel_llm/llm_rules.py:254,267` 在掃描 `new/` 時，都**明確只挑「非隱藏目錄（`is_directory` / `is_dir`）」**！第 07 號計劃只提改 `has_sender` / `sender_alive` 與拿掉 `/letter.json`，漏寫把 `new/` 過濾條件從 `is_directory` 改為 `is_regular_file`（否則所有單檔信都會被 `scan` 與 `sweep` 略過）。
- **修法**：`serve.cpp`、`scan.cpp`、`llm_rules.py` 掃 `new/` 與 `cur/` 時，將 `is_directory` 改為 `is_regular_file`（非一般檔依問題 6 視為壞信清理）。

#### 13. `extras/kernel-chain-check/check.py` 改成「列一般檔」會誤抓 `order.json`、`.flock` 與 `work/`
- **章節**：三（`kernel-chain-check`）
- **嚴重度**：**Important**
- **問題**：`check.py:331,400,415,424,629` 原本用 `glob("*/letter.json")` 或 `glob("*/*/letter.json")` 是靠檔名 `letter.json` 過濾出信件。改成無副檔名單檔後，若直接在信箱根或格內「列一般檔」，會把 `<box>/order.json`、`<box>/order.lock`、`<box>/.flock` 以及 `<box>/work/<信名>/*.json` 全部當成信件讀進來！
- **修法**：`check.py` 必須明確限定只列 `<box>/{new,cur,archive}/*` 下**非點開頭的一般檔（`is_file()` 且 `not name.startswith('.')`）**，絕不可掃 `<box>/` 根目錄或 `tmp/`、`work/`。

#### 14. `lib/aos/kernel/letters.py` 與 `round.py` 的工作目錄耦合，以及與 `ok-llmk2` 的隱性衝突
- **章節**：二（2b）、三、六（要對口的線）
- **嚴重度**：**Blocking**
- **問題**：
  1. **通用 kernel 庫**：第 三 節將 `lib/aos/kernel/letters.py` 列為「只列名字、查存在的，不用改」。但 `lib/aos/kernel/tests/test_kernel.py`、`test_kernel_hooks.py`、`test_limits_rule.py`（見 `sol-6` B）都透過通用 kernel 跑 job！當 `runner.py` 改成使用 `work/<信名>/` 時，傳給 `runner.py` 與 hook 的路径是由 `round.py` / `letters.py` 還是 `llm_rules.py` 組裝？若 `letters.py` / `round.py` 仍把 `cur/<信名>` 當目錄傳給 `runner.py` 或 hook，通用 kernel 測試會全部因 `NotADirectoryError` 失敗。
  2. **與 `ok-llmk2` 的語意衝突**：第六節說「`ok-llmk2` 動 `budget.py` 和 `used.json`；我們動 `llm_rules.py` 和 `runner.py`。檔案不重疊，但同一包；換樹前誰先上，誰就 rebase」。但 endpoint 寫出的 `used.json` 原本在 `cur/<信名>/used.json`，單檔化後搬到了 **`work/<信名>/used.json`**！這不會產生 git merge conflict，但若 `ok-llmk2` 在 `budget.py` 或測試裡讀 `cur/<信名>/used.json`，rebase 後執行期必壞。
- **修法**：
  1. 核對 `lib/aos/kernel/{letters,round,runner}.py` 的 job 目錄界面，統一由 kernel 層提供 `work_dir(name) -> <box>/work/<name>`。
  2. 立即透過 xiaosi 知會 `ok-llmk2`：`used.json` 位於 job 工作目錄（`work/<信名>/used.json`），勿在 `budget.py` 或測試寫死 `cur/<信名>/used.json`。

#### 15. `附錄4-持久檔.json` 漏列 `work/` 內部持久檔與 `sender.flock` 移除
- **章節**：四（文件）
- **嚴重度**：**Minor**
- **問題**：`sol-6` C 指出 `附錄4-持久檔.json:508` 登記了 kernel 信件工作目錄下的持久檔（`request.json`、`proc.json`、`state.json`、`reply.json`、`reply_letter.txt`、`stderr.txt`）與 `sender.flock`。
- **修法**：第四節文件清單明列更新 `附錄4-持久檔.json:278,281,508`：移除 `sender.flock`，並將工作檔路徑從 `cur/<信名>/...` 改為 `work/<信名>/...`。

---

### 四、換樹上線步驟（Live Tree）與測試缺口

#### 16. 換樹步驟五：只停 `aos-daemon` 並先 `commit` 再 `build C++` 會打壞活樹，且漏清 `tmp/`
- **章節**：五（怎麼上）
- **嚴重度**：**Blocking**
- **問題**：
  1. **只停 `aos-daemon` 不夠**：活樹上還有 `aos-llm-kernel`（及正在跑的 endpoint 子行程）、定時觸發的 `wf/tools/autoreply_tick.py`、`quiet_tick.py`、以及專區 `xiaosi`。由於 repo＝活樹，一旦執行 `commit`，所有 Python 讀信端立即切換成讀單檔，而在 `build C++` 完成前，舊 `aos-post` / `aos-llm` 仍在寫資料夾！這段編譯時間內只要 `autoreply_tick.py` 或 `aos-mailbox send --keep-to` 跑起來，就會對資料夾呼叫 `open()` 拋出 `IsADirectoryError`！
  2. **漏清 `tmp/`**：步驟 5 寫「清空並重建所有信箱的 `new/`、`cur/`、`archive/`、`work/`」，**漏了 `tmp/`**！舊版留在 `tmp/` 的殘骸是資料夾，`sweep()` 改成 `unlink` 後會因 `EISDIR` 刪不掉。
  3. **清空 `archive/` 與專區舊信的矛盾**：第三節強調要保住「專區信讀後在 `archive/` 還找得到、`user_verify` 驗得了」，但第五節步驟 5 卻把所有信箱的 `archive/` 清空；若不清 `archive/`，舊的歸檔夾又會被新版 `user_verify`（只認一般檔）拒絕。
- **修法**：
  1. 換樹停機清單必須包含：`aos-daemon`、所有 `aos-llm-kernel` 與 endpoint 行程、cron/tick（`autoreply_tick`、`quiet_tick`）、專區工具。
  2. 先在暫存樹或編譯目錄預編好 C++ binary（或停齊所有行程後再 commit + install binary），消除新 Python 配舊 C++ 的混血視窗。
  3. 清信箱時一併清空 **`tmp/`**。
  4. 專區 `archive/` 與 `rejected/` 若需保留舊信供 `user_verify` 驗證，換樹腳本可順手跑一行將專區 `archive/<名>/letter.json` 攤平為 `archive/<名>`（只搬一個檔案，極簡單），或明確由使用者拍板清空。

#### 17. 測試缺口
- **章節**：四（測試）
- **嚴重度**：**Important**
- **問題**：計劃列的 6 支新測試漏掉以下關鍵邊界：
  1. `send_held` 死在 `tmp/.<id>` **尚未寫完 JSON（0 byte 或半截 JSON）**時，`sweep()` 能否在逾時後收掉（驗證問題 8）。
  2. 兩個消費者同時對同一封 `new/<名>` 呼叫 `take(名)` 時，後到者在 `cur/<名>` 已存在時不會因 `RENAME_NOREPLACE` 回 `EEXIST` 而拋 `LetterExists`（驗證問題 1）。
  3. Kernel 收尾寄出回信並寫好 `work/<名>/reply_letter.txt` 後、刪 `cur/<名>` 前 crash，重啟回復**不會重覆寄第二封回信**（驗證問題 10）。
  4. `new/` 或 `cur/` 中出現 symlink 或 FIFO 時，`see()` 與 `scan()` 不會阻塞或跟隨 symlink，且 `done()` 能正常清除（驗證問題 6）。
  5. `send_held` 呼叫 `send_prepared` 返回後，外部行程對 `new/<id>` 試 `flock(LOCK_SH|LOCK_NB)` 確實拿到 `EWOULDBLOCK`（驗證問題 3 `send_prepared` 沒把鎖關掉）。

---

## (B) 更簡單或更安全的替代方案提案

#### 提案 1：信檔命名維持「無副檔名 `<信名>`」，但嚴格定義格子純淨度
- **比較**：加 `.json`（`<信名>.json`）雖方便 `glob("*.json")`，但會迫使 `names_in()`、`in_reply_to`、`user_verify <信名>`、CLI 參數與 `is_ordered()` 到處做 `.json` 拆裝，改動面倍增。
- **建議**：維持計劃的**無副檔名 `<格>/<信名>`**，但在 N-16 補一條硬規則：「`{tmp, new, cur, archive}` 四格內只放信檔，禁止放任何控制檔（`order.json`、`order.lock`、`.flock` 只能放在 `<信箱>/` 根目錄）」，且所有讀者列信一律用「`{new,cur,archive}` 下非點開頭之一般檔（`S_ISREG`）」。

#### 提案 2：簡化 `held` 判準——`tmp/.<id>` 直接靠 `flock` 判生死，不必在 `tmp/` 解析 JSON
- **比較**：計劃 2a 為了在 `tmp/` 判斷 `held`，要求 `sweep()` 先把 `tmp/.<id>` 讀成 JSON，結果製造出「寫到一半死掉就永遠跳過」的漏洞。
- **建議**：
  - 在 `new/` 與 `cur/`：信檔已完整寫入並原子 rename 完成，讀信封 `"held": true` 搭配 `flock(LOCK_SH|LOCK_NB)` 非常乾淨。
  - 在 `tmp/`：因為只有 `send_prepared`（即 `send_held`）會建點開頭的 `tmp/.<id>`，`sweep()` 對 `tmp/.<id>` **完全不必讀 JSON**——直接試 `flock(LOCK_SH|LOCK_NB)`：拿不到鎖（`EWOULDBLOCK`）＝活著跳過；拿得到鎖且 `now - st_mtime >= 2s`＝寄信人已死，直接 `unlink`。既省 I/O 又徹底消滅半截 JSON 殘骸。

#### 提案 3：按「轉移階段」區分檔案操作，不要四種動作全綁死 `RENAME_NOREPLACE` + `link/unlink`
- **建議**：將信箱的四種檔案動作拆開處理，既簡單又避開 `EEXIST` 與 `protected_hardlinks` 陷阱：
  1. **投遞（`tmp/<名> → new/<名>`）**：用 `renameat2(..., RENAME_NOREPLACE)`（不支援時同 UID 退回 `link` + `unlink`），撞名回 `EEXIST` 轉 `LetterExists`。
  2. **認領（`new/<名> → cur/<名>`）與歸檔（`cur/<名> → archive/<名>`）**：用 `renameat2(..., RENAME_NOREPLACE)`，但若 `new → cur` 回 `EEXIST` 且 `new/<名>` 已不存在，視為「已被他人認領」（同 `ENOENT`）；若檔案系統不支援 `renameat2`，退回 `lstat(dst)` 不存在後直接 `rename(src, dst)`，**不退回 `link` + `unlink`**（避開跨 UID `EPERM` 與雙份信件視窗）。
  3. **撤信（`regret`）與刪信（`done` 不保留）**：對一般檔**直接 `unlink("new/<名>")` / `unlink("cur/<名>")`**，廢除先搬去 `tmp/` 的多餘步驟。

#### 提案 4：`work/<信名>/` 狀態機改為「`cur/<信名>` 唯一憑證 ＋ 認領前必清 `work/`」
- **比較**：與其維護 `cur/` 與 `work/` 雙邊對帳，不如把不變量定死：
  1. **只有 `cur/<信名>` 存在才算有效工作**：只要 `cur/<信名>` 不存在，`work/<信名>/` 就是垃圾，`sweep()` 無條件清掉。
  2. **建 `work/<信名>/` 前必先 `remove_tree(work/<信名>)`**：無論是新認領還是回復退回 `new/`，都保證不會撞上舊 `work/<信名>/`。
  3. **`reply_letter.txt` 作為已回信標記**：寫入 `work/<信名>/reply_letter.txt` 後若 crash，重啟回復看到 `reply_letter.txt` 就跳過補寄，直接做收尾刪除。

#### 提案 5：零混血視窗的換樹順序與專區舊信一行攤平
- **建議換樹順序**：
  1. 在 `~/code/sec-1114/q10/` 完成 rebase、全套測試並確認 C++ 編譯通過。
  2. **停齊所有讀寫行程**：`aos-daemon`、`aos-llm-kernel`（含子行程）、`autoreply_tick` / `quiet_tick`、專區常駐工具。
  3. 專區 `archive/` 與 `rejected/` 若有需保留的舊信夾，跑一行轉換將 `<格>/<名>/letter.json` 搬為 `<格>/<名>` 並刪空夾（無狀態、1 秒完成，不必丟失專區歷史紀錄）；其餘信箱清空並重建 **`tmp/`、`new/`、`cur/`、`archive/`、`work/`**。
  4. Commit 上 `main`、立即安裝編好的 C++ binary 與新版 `aos-user verify`。
  5. 啟動 `aos-daemon` 與各服務。全程沒有任何一刻存在「新 Python + 舊 C++」或「新程式 + 舊信夾」並存。
