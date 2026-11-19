# d-mailkern 體檢報告：中間層（信箱、aos-exec、aos-loop／aos-fsm、hook、時鐘）與 kernel 層

隊員 d-mailkern｜2026-11-19｜程式版本＝乾淨複本 `src/`（HEAD 3c4cc4c52）｜所有指令經 `bin/clean`｜只用假腦（`llm_fake` 與自寫的 `eps/fk`），kernel.json 先換成只有假包，腳本有防呆（看到 localhost／127.0.0.1／:4000 就拒跑），沒碰 127.0.0.1:4000。

暫存 daemon／kernel 全在 `d-mailkern/run/<名>/`；重現腳本在 `d-mailkern/repro/`（`common.sh`、`llmk_common.sh` 是共用函式，其餘每支 `bash repro/<名>.sh` 就能跑，內部一律經 `clean`）。

## 先講結論（嚴重的四條）

1. **信箱裡只要有一個「認領不了」的項目，整個信箱就停擺**（daemon 的 ctl 信箱、kernel 站、llm kernel、agent 自己的信箱都一樣）。原因：`aos-post take／take-all` 改名碰到 ENOENT／ENOTEMPTY／EEXIST 以外的錯（例如 EACCES）就整次丟錯，不跳過那一封。
2. **daemon 認領到一半丟錯時，已經搬進 `cur/` 的好信不會被套、也不回信，一直擱到 daemon 重起**。
3. **llm kernel 每輪都出錯（壞 `used.json`、上面第 1 條…）時，所有問腦都無聲卡住**：表上、`state_flux` 看不出來，`aos-llm ask` 沒有逾時，寄件端也不提醒。
4. **kernel 把所有端點失敗都標 `retry: true`，agent-fsm 就會無限冷卻重送**，端點程式本身壞掉（永久錯）也一樣，不會停下來讓人知道。

## 開工與收尾的行程

- 開工 `pgrep -af aos-`：除了我自己那一行 bash 外沒有我的行程（記在 `pgrep-start.txt`；當時有 b-tests 的 `sleep 90`，不是我的）。
- 收尾：我起的每台 daemon 都用 `aos-daemon-ctl -d <我的 stack> shutdown` 收掉；做 kill -9 實驗的那幾台，kill 前都 `readlink /proc/<pid>/cwd` 確認在 `d-mailkern/run/` 底下，之後重起再 shutdown。收尾檢查（`pgrep-end.txt`，並逐一比對 sleep／python／aos-loop／aos-fsm 的 cwd）沒有任何 cwd 在 `d-mailkern` 底下的行程，沒有 `sleep 600`、`eps/fk`、hook 程式殘留。機器上其他 aos 行程都是別隊的，沒碰。

---

## 發現（照嚴重度排）

### F1 一個認領不了的信夾讓整個信箱停擺（會卡死）

- **現象**：信箱 `new/` 裡只要有一個 rename 會拿到 EACCES 的項目（例：信夾本身不可寫——跨 Linux 帳號寄進來、對方 umask 022 建的 755 信夾就是這樣；或有人故意 `mkdir -m 555`），`aos-post take／take-all` 就整次失敗、不跳過它，排在它後面（以及同一次的）所有信都拿不到：
  - daemon 的 ctl 信箱：之後的 `add`／`rm`／`stop`／`ping` 全部沒反應（`ping` 回 `DaemonFailed no reply ... within 3 s`），`state_flux.json` 的 `mailbox_warning` 寫 `cannot take letters: WriteFailed cannot rename ... Permission denied`。
  - kernel 站（daemon-kernel 範本）：每輪 `kernel: error: PostFailed cannot take letters from mailbox …`，所有掛 proc 請求都停；daemon 的 `mailbox_warning` 是 `None`（站的信箱不是 daemon 的），表上看不出來。
  - llm kernel：每輪 `kernel_llm: error: WriteFailed cannot rename …`，所有問腦都卡住（見 F3）。
  - agent／人的信箱：`aos-mailbox read` 每次都 `WriteFailed`，後面的好信永遠讀不到。
  - 拿掉那一夾（或改回可寫）後立刻恢復。
- **怎麼重現**：`bash repro/daemon_ctlbox_bad.sh`（daemon ctl 信箱＋ping）、`bash repro/mail_badletters.sh`（最後「perm 000」段）、`bash repro/kstation2.sh`（最後一段）、`bash repro/llmk_crash.sh`（最後一段）。模擬方式都是 `mkdir -m 555 <信箱>/new/<名>`。
- **嚴重度**：會卡死。
- **影響到今天哪個上層東西**：sub:N（子帳號往主帳號的信箱寄信，信夾屬於子帳號、權限照子帳號 umask——推測，沒有真的跨帳號測；sandbox 的 `setup.sh --mailbox` 用預設 ACL 避開了，但只在照它建的信箱上有效）；agent.py 重生／defs、aos.py、aos.gdb 只要經 daemon ctl 信箱或 kernel 站掛 proc 的，都會跟著卡；agent-fsm 問腦（llm kernel）。
- **建議處理方向**（擇一或並用）：(a) `aos::move` 在 take 時把 EACCES／EPERM 也當「這封跳過」、記一行 warning，繼續認領下一封；(b) 認領不了的移到別處或改名成 `.` 開頭隔離；(c) 不改程式，在文件寫明「跨帳號信箱一定要 ACL／setgid 群組可寫，否則一封就卡死整個信箱」，並讓這類訊息也出現在 kernel 站／llm kernel 看得到的窗。
- **依據**：實測。daemon：`mailbox_warning: cannot take letters: WriteFailed cannot rename …/procs_requests/new/00000000000000000001.x.y -> …/cur/…: Permission denied`，`ping` 退 1；改回 755 後 `good2 running`。程式：`cpp/aos-util/src/dirs.cpp:51-60`（`move` 只把 ENOENT／ENOTEMPTY／EEXIST 當「跳過」，其他一律丟 `WriteFailed`）、`cpp/aos-post/src/take/take.cpp`（`take`／`take_all` 迴圈直接呼叫，例外穿出）、`cpp/aos-daemon/src/daemon/mailbox.cpp:50-58`、`py/tools/aos/kernel/letters.py:32-34`（take-all 非 0／10 就 `die PostFailed`）。

### F2 daemon 認領到一半丟錯，已搬進 cur/ 的好信擱到重起才套（會丟資料：延到重起，寄件人拿不到回信）

- **現象**：同一圈裡好信排在前、認領不了的排在後時，`take_all` 先把好信 rename 進 `cur/`，碰到後面那封丟例外；daemon 只記 `mailbox_warning`，**剛搬進 `cur/` 的好信不在這圈的名單裡，之後每圈也不再看 `cur/`**（`cur/` 只在開門時收進 `redo_`）。結果那封 `procs_added` 不套、不回信；就算把擋路的那封拿掉，它還是一直躺在 `cur/`，直到 daemon 重起才被套上。
- **怎麼重現**：`bash repro/daemon_ctlbox_stuck_after.sh`（輸出：解除後 `cur:` 仍有那封、表上沒有 `good3`；重起後 `good3 running`、`cur:` 清空）。
- **嚴重度**：會丟資料（請求在 daemon 這次執行期間等於丟了；寄件人逾時以為失敗，重起後卻又冒出來）。
- **影響到今天哪個上層東西**：任何經 daemon ctl 信箱的 add／rm／stop（aos-agent ctl、subagent、agent.py 重生、aos.py）；觸發條件同 F1，或任何讓 `take_all` 中途丟錯的狀況（磁碟滿、權限）。
- **建議處理方向**：(a) `take_all` 改成逐封收、出錯的那封跳過，已拿到的照回傳；(b) daemon 每圈（或丟錯那圈之後）重掃 `cur/`，把沒處理的收進 `redo_`；(c) 至少在 `mailbox_warning` 說「有 N 封留在 cur/，重起才會套」。
- **依據**：實測（上面腳本輸出）＋讀程式：`cpp/aos-daemon/src/daemon/mailbox.cpp:42-45`（只有 `open_mailbox` 把 `cur/` 收進 `redo_`）、`:47-58`（`take_all` 的回傳在例外時整個丟掉）。

### F3 llm kernel 每輪出錯時，問腦全部無聲卡住（會卡死）

- **現象**：kernel 的輸入一壞（實測：`used.json` 壞 → `UsedBad`；F1 的認領不了 → `WriteFailed`），kernel 每 300 ms 跑一次、每次都退 1，所有問腦請求停在 `new/`：
  - `aos-llm ask` 沒有自己的逾時，一直等（實測用外層 `timeout 8` 才停）。
  - 寄件前的提醒只看 llm daemon 的 `state.json` 與 pid：daemon 活著，所以不提醒。
  - daemon 表、`state_flux.json`（`mailbox_warning` 等全是 `None`）看不出 kernel 壞了；只有 daemon 的 stderr 印一次 `body daemon.json#/exec failed (code 1), retrying next round`，kernel 自己的錯誤行每輪印一次（stderr 會一直長）。
  - agent-fsm 那邊照文件停在 `wait` 格，10 分鐘才印一次提醒。
- **怎麼重現**：`bash repro/llmk_budget.sh`（最後「corrupt used.json」段：`ask-exit=124`，stderr 連續 `UsedBad`）、`bash repro/llmk_crash.sh`（最後一段）。
- **嚴重度**：會卡死（整台電腦共用的 llm kernel 一壞，所有 agent 一起停在等腦）。
- **影響到今天哪個上層東西**：agent-fsm 問腦、subagent；aos.py／aos.gdb 若經 agent 問腦（推測）。
- **建議處理方向**：(a) 身體連續失敗時 daemon 把原因寫進窗（例如 `state_flux` 多一欄），`aos-llm send／ask` 與 agent 的 `wait` 讀它提醒；(b) `aos-llm ask` 給選填的 `--timeout-s`；(c) 壞的 `used.json`／`queue.json` 改成「改名留證據、從 0 算、印 warning」而不是每輪退 1（要使用者裁：會多給額度）。
- **依據**：實測：`kernel_llm: error: UsedBad …/used.json must be {…} (delete it to count from 0)` 每輪一行，`aos-daemon-ctl ls` 照樣 `# daemon: running`。程式：`py/tools/aos/kernel_llm/budget.py:200,212`、`cpp/aos-daemon/src/daemon/body.cpp:60`。

### F4 端點的所有失敗都被標成 retry，agent 無限冷卻重送（會誤導）

- **現象**：kernel 把「端點非 0 結束的純文字錯、`ReplyBad`、逾時、掛不上、重掛兩次沒結果」一律加 `retry: true`。agent-fsm 的 `wait` 照 `retry: true` 走「冷卻後重送同一份請求、不限次數」（30 秒起、加倍到 30 分鐘）。所以**端點程式本身壞掉（永久錯：import 錯、`HomeMissing`、語法錯）也會一直重試**，agent 在表上永遠是 `running`，只有 stderr 的 warning（`attempt 2, the same request is sent again in 60 s`）和 `brain_notify`（要設 `AOS_NOTIFY_BOX` 才有人收；沒設時印 `nobody is told`）。`wait.py` 檔頭寫的「retry 非 true＝退 1 停下等人」，對一般端點失敗實際走不到。
- **怎麼重現**：`bash repro/agent_cooldown.sh`（`model=fail`：端點只在 stderr 印錯、退 1；35 秒內被叫 2 次、`ann running`、warning `attempt 2 …`）。
- **嚴重度**：會誤導（看起來在跑，其實在空轉重試；真模型時每次重送都可能花錢）。
- **影響到今天哪個上層東西**：agent-fsm、subagent（子 agent 問腦壞了，母 agent 只會收到 BLOCKED 信——有設通知箱的話）。
- **建議處理方向**：(a) 維持現狀，只在 agent 文件與 `aos-agent ctl ls` 明示「在冷卻重試中」；(b) kernel 只對逾時／掛不上標 retry，端點非 0 的純文字錯不標（讓端點自己用 JSON error 說能不能重試）；(c) agent 端連續 N 次同一個錯就停下（`stopped`＋reason）。這是方向題，給使用者選。
- **依據**：實測（上述）；程式 `py/tools/aos/kernel_llm/llm_rules.py:273-301`（每種失敗都 `extra={"retry": True}`）；`py/tools/aos/kernel_llm/README.md:72` 有寫這件事（照設計），但上層 `templates/agent-fsm/wait.py:9` 的說法會讓人以為會停。

### F5 `aos-daemon-ctl stop` 說會等，其實寄了就回；卡在身體裡的 loop 永遠停不下（會誤導）

- **現象**：help 的子命令表寫 `stop NAME  write its public ctl and wait for exit (row stays as stopped)`，上面的表也寫 `writes its ctl, waits`；實際 0.27 秒就回 0（只等 daemon 收信），列停在 `stopping`。身體卡住（`sleep 600`）的 loop 不會在兩次之間讀 ctl，所以 `stop` 永遠收不掉，要 `sleep`（SIGTERM）才收，收完列是 `stopped`、code 143。
- **怎麼重現**：`bash repro/fsm_fail.sh`（最後一段：`stop` 後 `"phase": "stopping"`，`sleep` 後 `"phase": "stopped", "code": 143`）。
- **嚴重度**：會誤導。
- **影響到今天哪個上層東西**：aos-agent ctl stop（同一套信）；aos.py 若照 help 以為 stop 回來就停好了（推測）。
- **建議處理方向**：(a) 改 help 成「寄出 stop、daemon 收下就回；看 ls 等它變 stopped」；(b) 或真的等到 `stopped`（加 `--timeout-s`，逾時提示改用 sleep）。
- **依據**：實測；`py/aos/apps/daemon_ctl/main.py:9,19`（help）對 `:545-554`（`phase_cmd` 只 `deliver` 信）。

### F6 daemon-kernel 範本的 max_running 把自己的 _sweeper 也算進去（會誤導）

- **現象**：框架站數 `count_daemon` 表上所有 `running`／`stuck` 的列，範本那台 daemon 自帶 `_sweeper` 一列，所以 `max_running: 5` 實際只能掛 4 個；我設 `max_running: 2` 時只掛得上 1 個，第 2 個進排隊、帶期限的回 `SlotMissing`。
- **怎麼重現**：`bash repro/kstation.sh`（第一段：w1 `applied`、w2 進 `queue.json`；第二段 w3 `SlotMissing queued 2650 ms`）。
- **嚴重度**：會誤導。
- **影響到今天哪個上層東西**：kernel_gate、procs-kernel／daemon-kernel 範本使用者；鐘列、清道夫、問腦 proc 都會佔名額。
- **建議處理方向**：(a) 文件寫明「表上每一列都算，含 `_sweeper`、`_clock`」；(b) 或站只數經過它放行的名字、或排除 `_` 開頭的列（要使用者裁）。
- **依據**：實測；`py/tools/aos/kernel/procs_rules.py:83`。

### F7 shutdown 後在途問腦醒來重打端點，但額度只記一次（會誤導）

- **現象**：llm daemon 正常 `shutdown` 時，在途的問腦 proc 被收成 `sleeping`，重起後從頭再跑：端點實際被叫 2 次，`used.json` 的 `counter_calls` 與 `ledger.jsonl` 只記 1 次。文件有說「睡醒可能多花一次腦」，但沒說額度帳會少算。（對照：kill -9 llm daemon 時，在途的問腦 proc 不受影響、跑完照收，端點只叫 1 次、帳 1 次、ledger 沒重複——這點很好。）
- **怎麼重現**：`bash repro/llmk_shutdown_two.sh`（`endpoint calls: {sd2: 2, sd1: 2}`、`ledger rows 2`、`used 2`）；kill -9 的對照 `bash repro/llmk_crash.sh`。
- **嚴重度**：會誤導（真模型時 `budget` 擋不住真實花費）。
- **影響到今天哪個上層東西**：無直接（budget 範本預設不開；llm-team 每天 3000 次那格會少算）。
- **建議處理方向**：(a) 文件補一句「重跑那次不進 used.json／ledger」；(b) 醒來重跑時也加進計數。
- **依據**：實測。

### F8 reason 只抄最後一行＝包裝行，真正原因在上一行（只是醜）

- **現象**：fsm 表壞、stage 指到不在表上的狀態、入口找不到時，表上的 reason 都是 `aos-loop: error: RunFailed run 1: loop.json#/exec failed with exit code 1`，真正的 `aos-fsm: error: CfgBad state a: next zz is not in the table`／`StateUnknown …` 在 `stderr.txt` 上一行。文件（aos-daemon docs/03 第 75 行，K-2「不跳過包裝行」）明說這樣做。
- **怎麼重現**：`bash repro/fsm_fail.sh`（前半）。
- **嚴重度**：只是醜。
- **影響到今天哪個上層東西**：無直接；看表的人（aos.gdb？推測）要多讀一個檔。
- **建議處理方向**：(a) 維持；(b) reason 抄最後兩行；(c) aos-loop 的 RunFailed 行把身體最後一行帶進來。
- **依據**：實測。

### F9 auto_restart 的「慢失敗」無限重起、沒有退避（只是醜）

- **現象**：每次撐過 3 秒才退 1 的 proc，`auto_restart` 的「連 3 次 3 秒內退就停」永遠不成立，約每 3.6 秒重起一次、一直重起。文件（aos-daemon docs/03 第 49 行）照寫「中間撐過 3 秒就重算」。
- **怎麼重現**：`bash repro/loop_fsm_fail.sh`（`l_exit1_ar_slow`，25 秒內 4 次以上，停 daemon 前一直在跑）。
- **嚴重度**：只是醜（花 CPU、灌 stderr；身體若每次都打外部服務就不只是醜）。
- **影響到今天哪個上層東西**：llm kernel 範本的 `_sweeper`、根的 `_clock`、開 `auto_restart` 的 agent（wait.py 註解說 BrainFailed 會靠它重起）。
- **建議處理方向**：(a) 維持；(b) 加退避（重起間隔加倍）；(c) 連續失敗 N 次（不論多久）就停。
- **依據**：實測。

### F10 peek／mail_notify 把壞信算成新信（只是醜）

- **現象**：`new/` 裡的壞信（壞 JSON、空夾、一般檔、`letter.json` 是夾…）在 `peek` 列成 `? ? ?`，`mail_notify` 也算進去：`[aos] new_mail: 11 new letters from USER, ?.`；`read` 時才逐封丟掉（印 warning），agent 白被叫醒一次。
- **怎麼重現**：`bash repro/mail_badletters.sh`（前半）。
- **嚴重度**：只是醜。
- **影響到今天哪個上層東西**：agent-fsm／eca 的 mail_notify（多一次腦）。
- **建議處理方向**：peek 標出壞信、mail_notify 不算壞信；或維持。
- **依據**：實測。

### F11 信沒有大小上限，大信吃記憶體（只是醜）

- **現象**：5 MB 正文 send 0.5 秒、35 MB RSS；50 MB 正文 `aos-post send` 2.5 秒、258 MB RSS，`aos-mailbox read` 220 MB。沒有上限也沒有警告；`mail_notify` 每分鐘 `peek` 會把每封 `letter.json` 整份讀進來。1000 個附件檔的信讀完後整夾刪乾淨。
- **怎麼重現**：`bash repro/mail_volume.sh`（後半）。
- **嚴重度**：只是醜。
- **影響到今天哪個上層東西**：無直接。
- **建議處理方向**：(a) 文件寫「大東西放檔案、信裡寫路徑」；(b) send 加上限；(c) peek 只讀頭。
- **依據**：實測（`/usr/bin/time` 的 `%M`）。

### F12 `aos-daemon-ctl add` 對沒 +x 的腳本只說「不是 JSON」（只是醜）

- **現象**：`add` 一個沒執行權的 `nox.sh`，回 `EntryBad … is not JSON: Expecting value …`；直接 `aos-exec ./nox.sh` 才說清楚 `not executable (+x) and not JSON`。
- **怎麼重現**：`bash repro/exec_fail.sh`（輸出前兩行）。
- **嚴重度**：只是醜。
- **影響到今天哪個上層東西**：無直接。
- **建議處理方向**：ctl 的訊息比照 aos-exec。
- **依據**：實測。

### F13 llm kernel 身體偶發退 141（SIGPIPE）一輪（只是醜）

- **現象**：四種壞信＋一個同步 ask 落在同一輪時，連續三次各出現一次 `aos-daemon: warning: body daemon.json#/exec failed (code 141), retrying next round`，下一輪 `ok again`、所有信照答；之後重跑、拆開單獨試都沒再出現，觸發原因沒找到。
- **怎麼重現**：`bash repro/llmk_badletters.sh`，看 `run/llmk10/daemon.err`（偶發）。
- **嚴重度**：只是醜（只延一輪）。
- **影響到今天哪個上層東西**：無直接。
- **建議處理方向**：追是哪個子行程寫到斷掉的管子；或接受。
- **依據**：實測（偶發），原因未查明。

---

## 測試表

### 信箱

| 項目 | 預期（依據） | 實際 | 差在哪 |
|---|---|---|---|
| `aos-mailbox send --to` 收件人在跑 | 投進 `<stack>/mailbox/new/`（knowledge cli/mailbox.json） | 投進、退 0 | 無 |
| 收件人停著（stopping／stopped） | 表上有列就投（help：`--to NAME the agent's name on a daemon table`） | 投進、退 0，寄件人不會知道對方沒在跑 | 無（照文件） |
| 已 rm（stack 還在）／rm 且 stack 刪掉／不存在的名字 | `InstanceMissing` | 三種都 `InstanceMissing … not on the daemon table`、不寄 | 無 |
| `--box` 不存在 | `MailboxMissing` | `MailboxMissing mailbox not found` | 無 |
| 從別的 cwd 寄（表上 stack 是相對的） | 照表解 | 投對地方（`daemon_ctl.state` 會解相對路徑） | 無 |
| 一個行程連寄 200 封 | 照名字＝寄出先後；不丟不重（aos-post 01） | 200 封、200 個不同、順序對；200 封 38 秒（每封約 0.19 秒，多半是 Python 起動） | 無 |
| 兩個行程同時各寄 150 封（無序） | rename 原子、不重 | 300 封、各 150、各自順序對 | 無 |
| 兩個行程同時各寄 100 封 `--ordered` | 序號不重、可能缺號 | 序號 1～200 全有、不重，`order.json` 200 | 無 |
| 5 MB／50 MB 正文、1000 附件 | 文件沒寫上限 | 都成功；記憶體見 F11；附件讀完一起刪 | F11 |
| 壞信（壞 JSON、缺 sender、二進位、空夾、半寫、`new/` 裡一般檔、`letter.json` 是夾、陣列） | `read` 丟掉不卡；`done` 丟壞信（aos-post 01「壞信」） | 逐封 warning 丟掉、好信照讀、不重讀、`new/cur/tmp` 都清空；body 是字串的照讀（title 是 None） | peek／mail_notify 見 F10 |
| 半寫的信 | 協定是先寫 `tmp/` 再 rename，`new/` 不會有半封 | 手塞進 `new/` 的半封＝壞信丟掉 | 無 |
| 信夾認領不了（權限） | 文件沒寫 | 整個信箱停擺 | **F1、F2** |
| daemon ctl 信箱的壞信 | 丟掉、`mailbox_warning` 記最後一封、同圈好信照套（aos-daemon 05） | 照文件（只留最後一封的原因） | 無 |
| 信箱上限 | 文件沒寫 | 數到 300 封沒上限、沒變慢 | 無（沒灌更多） |

### aos-exec（掛成 daemon 的 exec 型 proc）

| 項目 | 預期（aos-exec docs/05、aos-daemon docs/03 第 75 行） | 實際（表上 reason） | 差在哪 |
|---|---|---|---|
| 程式不存在（`["/no/such/prog"]`） | `EntryMissing` | `failed to start: exited within 3s … (code 1): aos-exec: error: EntryMissing entry not found: /no/such/prog` | 無 |
| PATH 上找不到（`{"argv": ["nosuchcmd-xyz"]}`） | `LaunchFailed`（`CommandMissing`） | `LaunchFailed inst cannot run: CommandMissing program not found` | 無 |
| 沒執行權、也不是 JSON | `EntryBad not executable (+x) and not JSON` | ctl add 先擋：`is not JSON` | F12 |
| argv 空／不是字串 | `EntryBad` | `EntryBad inst argv must be a non-empty array of strings` | 無 |
| envs 值不是字串／envs 是陣列 | `EntryBad` | `EntryBad inst envs must be {name: string}` | 無 |
| cwd 不存在 | `LaunchFailed`（`CwdMissing`） | `LaunchFailed inst cannot run: CwdMissing …` | 無 |
| stdout 上層夾不存在 | `LaunchFailed OpenFailed …(add stdout_mkdir)` | 同 | 無 |
| 跑了、退 3 | 留 stopped＋code | `stopped code 3 failed to start: exited within 3s (code 3)` | 無（「failed to start」字面有點怪，但 aos-daemon docs/08 第 28 行明寫） |
| 目標檔不存在 | — | ctl add 先擋 `PathMissing` | 無 |

### aos-loop／aos-fsm／hook

| 項目 | 預期（aos-loop docs/01、aos-fsm docs/01、aos-daemon docs/03） | 實際 | 差在哪 |
|---|---|---|---|
| loop 身體退 1 | loop 結束、表 stopped＋reason（裁定 B） | 同 | 無 |
| 身體逾時（單子 timeout_ms 500） | 那次 143、loop 結束 | `code 143 … exit code 143` | 無 |
| 身體卡住不回、沒設期限 | 一直跑；stuck 要有刺激才判 | 一直 running；設了 `stuck_after_ms` 也不判（沒人戳它） | 無（照 aos-daemon docs/04 第 40 行） |
| 對卡住的 loop 下 stop | help 說「等它退」 | 立刻回、列停在 stopping；sleep 才收 | **F5** |
| 身體退 10 | `body_exit`、退 0、下表 | 下表 | 無 |
| on_start 退 7 | warning、照開跑 | `on_start … exited 7`、身體照跑 | 無 |
| on_stop 卡住 | 5 秒後整群收、warning | `on_stop … exited 143`、loop 照常結束 | 無 |
| auto_restart 快失敗 | 連 3 次 3 秒內退就停 | `restarted 3 times in a row … not restarting again` | 無 |
| auto_restart 慢失敗 | 撐過 3 秒就重算 | 無限重起 | F9 |
| loop 設定檔壞（ctl add 一份壞 JSON） | — | ctl 先擋 `EntryBad … is not JSON` | 無 |
| fsm 一格退 1（字串 next） | state 不動、fsm 以 1 退 → loop 停 | stage 留在起點、表 stopped | reason 見 F8 |
| fsm 一格退 1、`"*"` 導回同格 | fsm 不擋不數 | 5 秒跑 51 次、一直跑 | 無（照文件；只有 loop 的 max 擋） |
| fsm 一格逾時 | 143 | 143 | 無 |
| fsm next 指到不在的狀態／fsm.json 壞 JSON／stage.txt 指到不在表上的 | `CfgBad`／`CfgBad`／`StateUnknown`，不跑格 | 同（在 stderr.txt 上一行） | F8 |
| agent hook 卡住（before_queue，timeout 2000，on_error continue） | 收整群、warning、照常往下 | `did not finish in 2000 ms (its process group was killed); going on without it`；回答多等約 2 秒；hook 行程不殘留 | 無 |
| agent hook 退 1（on_error stop） | `HookFailed`、這格退 1 | agent `stopped`；那則訊息留在 `queue/cur/`；拿掉 hook、`start` 後照答，沒丟 | 無 |

### 時鐘

| 項目 | 預期（knowledge clock.json、cli/clock.json） | 實際 | 差在哪 |
|---|---|---|---|
| `--every 4` | 格數整除 4 時寄 | cycle 4、8、12…都到 | 無 |
| `--after 6` | 一次、之後自刪 | cycle 10 到一封、ls 不見 | 無 |
| `--at +5s` | 一次、最多晚一格 | cycle 12 到、帶 `due …` | 無 |
| 收件 proc 停著 | 信在它的 queue 等 | 照到 `queue/new` | 無 |
| 收件 stack 被刪 | 每次一行 warning、不重試；每 100 格清登記 | 每 2 格一行 `cannot send … MailboxMissing`；短時間內登記還在 | 無（照文件） |
| daemon 收工期間 | 鐘不走；`at` 醒來後補寄一次 | 收工時鐘停在 22；重起後補寄 `at-while-down` 一次 | 無 |
| daemon 重起後登記 | 檔在 stack，留著 | `ev`、`g2` 都在、照寄 | 無 |

### kernel 層

| 項目 | 預期（kernel_llm docs/01、02、04，templates/kernel） | 實際 | 差在哪 |
|---|---|---|---|
| llm kernel 照範本掛（`cp -r llm-kernel def`、`aos-exec --stack . def`） | 起得來、假腦答 | `FAKE ANSWER to: hi-fake` | 無（kernel.json 換成只有假包） |
| 端點退 1（純文字） | `EndpointFailed endpoint function exited with code 1: <第一行>` | 同 | retry 見 F4 |
| 端點退 1、印 JSON error | 原樣回 | `EndpointFailed simulated 503`（帶 retry） | 無 |
| 端點退 0、印垃圾 | `ReplyBad` | 同 | 無 |
| 端點超過 timeout_ms | `EndpointFailed … timed out` | 4 秒時限、約 5.2 秒回 `timed out (4000 ms)`；卡住的端點被整群收、不殘留 | 無 |
| 範本預設 `timeout_ms: 0` | 不限時 | （讀文件）卡住的端點會永遠佔一格 | 無（照設計；提醒：範本＋卡住的端點＝那格永遠不放） |
| 包額度 `once`（max_calls 1） | 第二封 `BudgetMissing endpoint once: …` | 同 | 無 |
| 寄件人額度 | 第二封 `BudgetMissing budget.senders key …` | 同 | 無 |
| 總額度 4（window all） | 第 5 封起 `BudgetMissing`，帶 scope／window、resets_at null | 同（`recv --full` 看得到整個物件）；拒絕的不記 ledger | 無 |
| 記帳檔 | `$AOS_STACK/used.json`、`ledger.jsonl` | 在；ledger 每封一行、只追加，清道夫不碰（sweeper README 第 43 行） | 無（會一直長，文件已寫「人清理」） |
| used.json 壞 | `UsedBad`（刪掉從 0 算） | 每輪 UsedBad、問腦全停 | **F3** |
| kill -9 llm daemon（3 封在飛、2 封在 down 時寄到） | 在途歸 daemon 管、重起收 | 在途 3 封跑完、重起後全回；down 時寄的 2 封也答；端點各 1 次、ledger 不重複、帳 5 | 無（很好） |
| kernel 不在時同步 ask | 寄前提醒、一直等 | `llm daemon is not running … letter … was written anyway`，一直等 | 無（照文件） |
| shutdown 時在途 | 睡、醒來重跑 | 端點各 2 次、帳 1 次 | F7 |
| 同一個 stack 起第二台 | — | `DaemonExists a daemon is already running on this stack`、退 1 | 無 |
| 兩台 kernel 各自 stack | 各管各的 | 各自答 | 無 |
| 壞信進 llm kernel（壞 JSON、空夾、缺 request、回信箱已刪） | 回 `LetterBad`／丟掉／warning、信照刪 | 同；後面的 ask 照答 | 偶發 F13 |
| agent-fsm 掛在 llm kernel 上、kernel 被 kill -9 | wait 格等、提醒 | `aos-agent ask` 印 `ann is waiting for its brain, but the llm kernel … is not running`，20 秒 `AnswerMissing`；kernel 重起後自己接上 | 無（很好） |
| agent 冷卻（retry true） | 30 秒起加倍，`cooldown.json` 記 retry／error | 照記（`failures 2`、`retry true`、`error EndpointFailed`） | F4 |
| 框架站白名單 | `NameUnknown` | `bad not in allowed` | 無 |
| 框架站 max_running＋期限 | 排隊、期限到 `SlotMissing` | 同；但 `_sweeper` 也算一格 | F6 |
| hold 有期限沒人表態 | `SlotMissing … nobody decided in time` | 同 | 無 |
| hold 沒期限 | 一直留著（`hold.json`） | 留著；寫 `decisions/<信>.json` pass 後轉寄、`applied: true` | 無 |
| 框架站 kill -9、期間寄來的請求 | 下一輪接手 | 重起後照套、回 `applied: true` | 無 |
| 站的 requests 有認領不了的項目 | — | 整站停 | **F1** |

## 可以放心的（測了、跟文件一致）

- 信箱的投遞是原子的：大量、並發、`--ordered` 都不丟、不重、順序對；壞信在 `aos-mailbox read`、daemon ctl 信箱、llm kernel 都會被丟掉，不會卡住或一直重讀。
- `aos-mailbox send --to` 對 rm 掉／不存在的收件人明確報 `InstanceMissing`，不會錯投到殘留的 stack。
- aos-exec 的每種起不來，表上 reason 都帶著那行 `aos-exec: error: 代號 …`，看得懂。
- loop／fsm 的失敗一律「停、留 stopped＋reason」，不會默默跳過；`stage.txt` 失敗時不動，重起從同一格再來。
- hook：卡住會被整群收（不留孤兒），`continue` 照往下、`stop` 讓 agent 停但訊息不丟。
- 時鐘：every／after／at、停著的收件人、收工期間到期、重起後登記都照文件。
- llm kernel 被 kill -9 的處理很穩：在途照收、不重打端點、帳與 ledger 不重複；agent 那邊提醒清楚，kernel 回來自己接上。
- 額度三層（總、包、寄件人）與結構化的 `BudgetMissing` 都照文件。
- 同一個 stack 不會起兩台 daemon（`DaemonExists`）。
- 框架站的 hold／decisions／期限、kill -9 後接手都照文件。

## 沒測到的＋原因

- **真的跨 Linux 帳號寄信（sub:N）**：要另一個帳號與 sudo，規則不准；用 `mkdir -m 555` 模擬「信夾不可寫」，跨帳號的情形是推測（F1）。
- **kernel_llm 寄回信與刪信之間被 kill -9（ledger 半行／重複、多一封回信）**：時間窗只有幾毫秒、每輪是新行程，沒有打得準的注入辦法；只讀文件（kernel_llm docs/04 已列這條）。
- **queue.json／counter 壞**：讀程式推跟 used.json 同一類（`QueueBad` 每輪退 1），沒另外實測。
- **換窗（過午夜、TZ 改變）**：要等時間或改 TZ，沒做。
- **llm kernel 的 hook（before_verdict／after_verdict hold）**：只在框架站測了 hold；llm kernel 用同一個骨架，沒另測。
- **kernel_gate（agent 自己當門）**：要真的 agent turn 去表態，時間不夠，沒測。
- **eca 身體**：會叫外部 CLI，不在本題範圍、也不准叫真模型。
- **信箱上限**：照規則只數到數百封（300），沒灌爆。
- **cgroup 相關**：機器沒有 systemd user。

## 重現腳本一覽（`d-mailkern/repro/`）

| 腳本 | 測什麼 |
|---|---|
| `common.sh` | 共用：起／收暫存 daemon、`c`＝經 clean 跑 |
| `mail_recipients.sh` | `--to` 收件人在跑／停著／rm／stack 刪掉／不存在、`--box` 不存在 |
| `mail_volume.sh` | 200 封順序、兩行程並發、`--ordered` 並發、5 MB／50 MB、1000 附件（F11） |
| `mail_badletters.sh` | 各種壞信、peek／mail_notify、權限 000 的信夾（F1、F10） |
| `daemon_ctlbox_bad.sh` | daemon ctl 信箱的壞信、認領不了的信夾、ping（F1） |
| `daemon_ctlbox_stuck_after.sh` | 好信排在認領不了的前面：卡在 cur/ 到重起（F2） |
| `exec_fail.sh` | aos-exec 各種起不來在表上的樣子（F12） |
| `loop_fsm_fail.sh` | loop 退非 0、逾時、卡住、on_start／on_stop、auto_restart 快／慢失敗（F9） |
| `fsm_fail.sh` | fsm 格失敗、`*` 導回、表壞、stage 壞；stop 卡住的 loop（F5、F8） |
| `clock.sh` | every／after／at、停著、刪掉、收工期間、重起 |
| `llmk_common.sh` | 共用：抄 llm-kernel 範本、換成只有假包的 kernel.json、起／收、ask |
| `llmk_basic.sh` | 端點失敗、壞回信、逾時、卡住、記帳檔位置 |
| `llmk_budget.sh` | 總／包／寄件人額度、壞 used.json（F3） |
| `llmk_crash.sh` | kill -9 在途與剛收的信、認領不了的信（F1、F3） |
| `llmk_shutdown_two.sh` | shutdown 重打端點、同 stack 第二台、兩台 kernel（F7） |
| `llmk_badletters.sh` | llm kernel 壞信（F13 偶發） |
| `agent_kernel_dead.sh` | agent-fsm 掛在 kernel 上、kernel 死掉再回來 |
| `agent_hooks.sh` | agent hook 卡住（continue）與退 1（stop） |
| `agent_cooldown.sh` | retry 錯的冷卻與永久錯也重試（F4） |
| `kstation.sh` | 框架站白名單、max_running＋期限（F6） |
| `kstation2.sh` | 框架站 hold、kill -9、認領不了的信（F1） |
