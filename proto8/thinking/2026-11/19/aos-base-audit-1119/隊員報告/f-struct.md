# f-struct 報告：基底的結構性疑慮（aos-base-audit-1119）

隊員 `f-struct`。範圍：`src/proto8/cpp/`（aos-daemon、aos-loop、aos-post、aos-lock、aos-util、aos-llm）、kernel 站（`py/tools/aos/kernel`、`py/tools/aos/kernel_llm`、`templates/kernel`）與信箱。以讀程式為主，做了三個小實驗（`repro/e1`～`e3`，都經 `bin/clean` 跑）。只查不改。

檔名一律相對 `~/.aos/scratch/aos-base-audit-1119/src/proto8/`。「實測」＝我在自己子夾跑出來的；其餘都是「讀程式推的（推測）」。

## 先講結論

基底的「寫檔」「認行程」「鎖」這三塊做得紮實（見「可以放心的」）。真正有份量的問題有三個，都實測到：

1. **一支 proc 的 `stderr.txt` 太大，會讓整台 daemon 以 `Internal std::bad_alloc` 退 1、底下所有 proc 一起被收掉**（F1）。
2. **daemon 的身體在跑的時候，daemon 什麼都不顧**：不重起、不收信、不回 ping。kernel 站正是掛在身體上跑的（F2）。
3. **daemon 被 kill -9 而表又用不上時，exec 型的 proc 會被再起一份**，舊的那支還活著、不在任何表上（F3）。

其餘是靜默失敗、沒人清的東西、同帳號下的邊界，多數已在文件寫成「已知／風險自擔」，我只標出文件沒講到的部分。

## 發現

### F1　一支 proc 的 stderr.txt 很大時，它一失敗 daemon 就把整份讀進記憶體；記憶體不夠＝整台 daemon 退 1

- **現象**：proc 退非 0 時 daemon 要從它的 `stderr.txt` 取最後一行當 reason，做法是把**整份檔**讀進記憶體。1 GB 的 stderr.txt 讓 daemon 記憶體尖峰到 2.1 GB、那一列約 10 秒後才顯示 stopped（這段時間 daemon 不顧別的）。把 daemon 的位址空間限在 600 MB 時，daemon 直接 `aos-daemon: error: Internal std::bad_alloc` 退 1，旁邊無辜的 proc 也被收掉。
- **怎麼重現**：`cd ~/.aos/scratch/aos-base-audit-1119/f-struct && ../bin/clean python3 repro/e1_big_stderr.py 1024`（看尖峰）；`../bin/clean python3 repro/e1_big_stderr.py 1024 600`（看 daemon 死掉）。
- **嚴重度**：會卡死（整台 daemon 停；它管的 proc 全部被收）。
- **影響到今天哪個上層東西**：全部掛在那台 daemon 上的東西（agent-fsm、eca、kernel 站）。最容易中的是「被上一層用 `limits.mem_mb` 限住的子 daemon」與沒掛 `_sweeper` 的 daemon；有外部監管自動重起時，那列若在 daemon.json 裡會再起、再失敗、再讀，變成打轉（推測）。
- **建議處理方向**（選一）：(a) 只讀檔尾（例如最後 64 KB）取最後一行；(b) 讀之前看大小，超過門檻就不取 reason 尾巴、只寫結束碼；(c) 維持現狀，文件 08 的已知限制補一句「沒掛清道夫時 stderr 太大會拖垮 daemon」。
- **依據**：實測。
  - 不限記憶體：`job stopped after 14.1s reason='failed while running: exited with code 3: boom'`、`VmHWM_kB: 2099992`（身體 4 秒就退了）。
  - `RLIMIT_AS` 600 MB：`daemon alive: False exit: 1`、`d.err: aos-daemon: error: Internal std::bad_alloc`、另一支 `ok`（`sleep 600`）最後一份表是 `stopping`、行程已不在。
  - 程式：`cpp/aos-daemon/src/daemon/failure.cpp:22`（`read_file` 整份）、`:37`、`:45`（再複製）；`cpp/aos-util/src/files.cpp:138-164`（`read_file` 沒有上限）；`cpp/aos-daemon/src/main.cpp:61-62`（`std::exception`＝Internal 退 1）。
- **順帶看到的小毛病**（實測，只是醜）：舊內容**不以換行結尾**時，reason 會變成 300 個空白加 `...`，真正的最後一行 `boom` 不見；記憶體尖峰也升到 5.2 GB。原因在 `failure.cpp:28-35`：起點退回行首時退到檔頭。

### F2　daemon 的身體在跑時，daemon 不顧任何事；kernel 站就跑在身體裡

- **現象**：daemon 在每圈最後同步跑自己的身體，沒有時間上限。身體跑多久，daemon 就停多久：自動重起、收信、回 ping、看子項死活都等它。`daemon-kernel`、`llm-kernel`、`llm-team` 三個範本都把 kernel 站寫在身體（`exec`）上，所以站的一輪多久，那台 daemon 就凍多久。站的 hook 預設期限 60 秒，寫 `timeout_ms: 0` 是不限時；站自己叫 `aos-post`、`aos-directive` 也沒設期限。
- **怎麼重現**：`cd ~/.aos/scratch/aos-base-audit-1119/f-struct && ../bin/clean python3 repro/e2_body_blocks.py`（身體 `sleep 12`、`interval_ms` 100、一支跑 4 秒就退的 `auto_restart` proc）。
- **嚴重度**：會卡死（身體卡住＝那台 daemon 永久不動；身體只是慢＝延遲）。
- **影響到今天哪個上層東西**：經 kernel 站掛 proc 的一切（agent.py 重生、subagent、sub:N 的 `users` 表填號），以及問腦（llm kernel 那台 daemon 凍住時，在飛的問腦 proc 結束了也沒人收）。
- **建議處理方向**：(a) 身體加時間上限（daemon.json 一個 key，逾時照 `on_start` 那套 TERM→KILL）；(b) kernel 站改掛成 loop proc（`procs-kernel` 那種擺法），不放身體；(c) 維持現狀，文件寫明「身體要短；hook 的 `timeout_ms: 0` 會凍住整台」。文件 08 目前只寫「身體跑的期間 poke 不打斷」，沒講重起與收信也停。
- **依據**：實測。輸出：`ping answered after 10.1s (interval_ms is 100)`、`flap starts: 3 gaps: ['12.1', '12.1']`（沒有身體時間隔約 4 秒）。程式：`cpp/aos-daemon/src/daemon/body.cpp:28`（`run_once(body_)`，沒帶期限）、`cpp/aos-daemon/src/daemon/tend.cpp:297-299`（tend 最後跑身體）、`cpp/aos-loop/src/run/folder.cpp:94-116`（`timeout_ms`＝0 時 `poll` 無限等）、`py/aos/hook_run.py:30`、`:149`（預設 60000、0＝不限）、`py/tools/aos/kernel/runner.py:63-64`（`subprocess.run` 沒有 timeout）。

### F3　daemon 被 kill -9、表又用不上時，exec 型 proc 會多起一份

- **現象**：daemon 再起時只有「子 loop」能靠小格裡自己的 state 窗認回來；exec 型（字串、陣列、只有 `exec` 的物件）沒有 state 窗，表上沒有它就當沒在跑、照 daemon.json 再起一份。舊的那支還活著、不在任何表上，`shutdown` 也收不到它；清道夫只認孤兒 loop，不認這種。
- **怎麼重現**：`cd ~/.aos/scratch/aos-base-audit-1119/f-struct && ../bin/clean python3 repro/e3_lost_table_dup.py`（起一支 exec 型、一支 loop 型；kill -9 daemon；把 `procs_state.json` 寫壞；再起）。
- **嚴重度**：會誤導（兩支同名 proc 共用一個 stack；會不會寫壞資料看那支程式自己，這點是推測）。
- **影響到今天哪個上層東西**：eca、agent.py 這類 exec 型常駐的 agent；kernel 站替問腦掛的工作（`max: 1` 的 loop 型，不受影響）。
- **建議處理方向**：(a) exec 型也在小格留一張「誰在跑」的字條（pid＋ticks＋boot_id），再起前比對；(b) 清道夫把「環境的 `AOS_STACK` 指到這台小格、卻不在表上」的行程也報出來；(c) 維持現狀，文件 08 補寫「exec 型接不回」。
- **依據**：實測（用「表壞掉」當替身）。輸出：`after restart job pids: [338583, 338586, 338782] alive: [338583, 338586, 338782]`、`table: {'once': (338782, 'running'), 'looped': (338584, 'running')}`、`adopt_warning: procs_state.json is unreadable (invalid JSON); kept it as … and started with an empty table`；`shutdown` 後 338583 還活著，是我手動收的。程式：`cpp/aos-daemon/src/daemon/adopt.cpp:96-121`（`live_in_cell` 只看 state 窗）、`:138-142`（表壞＝空表開始）。
- **推測的另一個入口**：一次起一大批時表最多每 200 毫秒寫一次（`cpp/aos-daemon/src/daemon/reconcile.cpp:14` `FLUSH_MS`）；這 200 毫秒內 daemon 被 kill -9，剛起、還沒進表的 exec 型也是同樣下場。沒實測（時間窗太小）。

### F4　單點清單：誰掛了全倒、怎麼回來

| 東西 | 掛了的後果 | 自動回來嗎 | 依據 |
|---|---|---|---|
| 根 daemon | 底下 proc 繼續跑但沒人顧（不重起、不收信）；寄給它的信堆在 `new/`，寄件人只會等到逾時 | 不會。文件明寫「壞了就壞了」，要人手或外部 systemd／s6；兩種監管器都沒做端到端驗證 | `cpp/aos-daemon/docs/10-根daemon.md`（驗證範圍那段） |
| 子 daemon（例 llm 那台） | 同上，範圍是它那棵 | 會，前提是上一層那列寫了 `auto_restart: true`；再起時照表接回 | `cpp/aos-daemon/src/daemon/tend.cpp:195-207` |
| kernel 站（身體） | 站退非 0 不拖垮 daemon，下一圈再跑；這段時間 `requests/` 沒人判 | 會（下一圈） | `templates/kernel/docs/02-kernel-modes.md:274` |
| llm kernel 的 `used.json` | 檔壞＝每一輪 `UsedBad`，問腦全停 | 不會，要人刪檔（訊息有寫 `delete it to count from 0`）。檔是原子寫的，要外力才會壞 | `py/tools/aos/kernel_llm/budget.py:189-212` |
| `procs_state.json` | 壞＝留證、空表開始（見 F3） | 半自動 | `cpp/aos-daemon/src/daemon/adopt.cpp:138-142` |
| `state_flux.json` 被刪 | 舊 `ctl.json` 的 stop 會被重做，一起來就停 | 不會，文件已寫明 | `cpp/aos-daemon/docs/08-當機復原與已知限制.md` |
| 時鐘 `_clock` | 沒深查 | — | — |

- **嚴重度**：只是醜（都是設計上的選擇，多數文件已寫）。列在這裡是因為題目問「誰掛了全倒」。
- **建議處理方向**：根 daemon 這一格值得使用者決定要不要補一份驗過的 systemd／s6 範例；其餘照舊即可。

### F5　信箱裡沒人清的東西

- **現象**：
  1. 寄信寫到一半死掉，殘骸留在 `tmp/`；程式註解明寫「收屍歸寄信人的上一層，這裡不做」，清道夫也不掃 `tmp/`。
  2. 處理完的信是先搬到 `tmp/` 再刪；剛搬完就死，同樣留在 `tmp/`。
  3. 寄給暫停中、停止中、已死的 daemon 的信一直留在 `new/`，沒有上限也沒有過期。
  4. `aos-post done --keep` 的 `archive/` 只進不出。
  5. kernel 站裡「留著等表態」而且沒帶期限的信永遠留著（文件已寫）。
- **怎麼重現**：讀程式即可；未實測。
- **嚴重度**：只是醜（慢慢長，不會馬上壞）。daemon 每圈會列 `new/` 並排序，信堆到很多時每圈變慢（推測）。
- **影響到今天哪個上層東西**：無直接。
- **建議處理方向**：(a) 清道夫多一項「`tmp/` 裡超過 N 分鐘的殘骸」；(b) 信可帶過期時間；(c) 不管。
- **依據**：讀程式推的（推測）。`cpp/aos-post/src/send/send.cpp:9`（註解）、`cpp/aos-post/src/take/take.cpp:136-140`、`cpp/aos-daemon/src/daemon/tend.cpp:254-265`（暫停／收工那圈不認領）、`py/aos/apps/sweeper/main.py`（說明第 1～5 項沒有信箱）、`templates/kernel/docs/02-kernel-modes.md:275`。

### F6　會一直長、沒有輪替的檔

| 檔 | 誰寫 | 有沒有清 | 長大後誰會慢 |
|---|---|---|---|
| 各 proc 的 `stderr.txt` | proc 自己（附加） | 有，`_sweeper` 每 10 分鐘把 ≥1 MiB 的封存再截 0；**沒掛那列的 daemon 沒人清** | daemon 自己（F1） |
| daemon 自己的 stderr、`--enable-logs` 的 stdout | daemon | 沒有。清道夫明寫跳過 daemon 自己那份（歸上一層）；根 daemon 的由使用者自己導去哪就在哪 | 沒有人讀 |
| proc 的 stdout | — | 不存：daemon 起的 proc stdout 一律接 `/dev/null`（見 F8） | — |
| llm kernel 的 `ledger.jsonl` | 站每封回信附加一列 | 沒有；清道夫明寫不碰 ledger | 站本身不讀它（記帳用 `used.json`），所以不會拖慢站 |
| `history.jsonl`、`history_removed.jsonl`、`live.jsonl`、`turns.jsonl`、`gdb/log.jsonl`、`aos-mcp-logs.jsonl` | 上層（eca、agent、gdb、mcp） | 清道夫明寫不碰 history | 不在我的範圍，只列名；讀整份的程式會跟著變慢（推測） |
| `*.bad-*` 留證檔 | daemon 接表失敗時 | 不清（使用者 11-09 裁「只數不碰」） | — |
| 記憶體裡的表 | daemon | 每圈整張表組一次比有沒有變 | 文件已寫：4300 列、`interval_ms` 10 時閒著 82% CPU |

- **嚴重度**：只是醜（除了第一列，那是 F1）。
- **依據**：讀程式推的（推測）。`cpp/aos-daemon/src/child/child.cpp:139`、`py/tools/aos/kernel_llm/ledger.py:9-28`、`py/aos/apps/sweeper/main.py`（`*.bad-* evidence files, history, observed, ledgers and .trash are never touched`）、`cpp/aos-daemon/docs/08-當機復原與已知限制.md`。

### F7　同帳號下的安全邊界：哪些是洞、哪些是還沒做

現況一句話：**沒寫 `sub:N` 的 proc 之間沒有任何邊界；寫了 `sub:N` 的 proc 是「它被關住」，不是「它被保護」。**

| 項目 | 現況 | 算什麼 | 依據 |
|---|---|---|---|
| 任何同帳號 proc 直接寄信進 daemon 的 `procs_requests`，繞過 kernel 站加／拔別人的 proc | 可以 | 已知、使用者裁「風險自擔」 | `templates/kernel/docs/02-kernel-modes.md:47-52` |
| 信上的 `sender` | 寄件人自己從環境變數填的，收件人不驗 | **基底的洞**（今天同帳號下本來就擋不住；但 llm kernel 的「每個寄件人的額度」是拿這個字串記帳，換個 `AOS_STACK` 就換一本帳） | `cpp/aos-post/src/send/send.cpp:138`、`py/tools/aos/kernel_llm/budget.py:228-239` |
| 排隊期限 `queue_wait_ms` 從信上的 `sent_at` 起算 | `sent_at` 也是寄件人寫的 | 小洞（同上，寄件人可以自己改長短） | `py/tools/aos/kernel/queue_fifo.py:54-59`（合併列號 408-413） |
| 改別隻的 stack、定義、`ctl.json`、站的 `decisions/<信>.json`（替「留著等表態」的信放行）、`used.json` | 同帳號都寫得進去 | 還沒做的功能（K10 收緊活樹權限） | `thinking/2026-11/19/subuid-1119.md`「沒做」 |
| `sub:N` 的小格 | 起之前改成 700＋ACL：它和使用者進得去，別的 `sub:M` 進不去 | 補上了 | `cpp/aos-daemon/src/child/subuid.cpp:254-268` |
| `sub:N` 讀別人的東西 | 家目錄 751、repo 755、一般小格 755／檔 644：對它是「其他人可讀」，所以讀得到沒換身分的 agent 的 stack、定義、使用者專區裡沒特別收的檔 | **還差的**（文件沒明講這個方向；只擋寫、不擋讀） | `cpp/aos-daemon/src/child/child.cpp:104-117`（小格照預設權限建）、`cpp/aos-util/src/files.cpp:103`（檔 0666 再過 umask） |
| 沒換身分的 proc 改 `sub:N` 的小格 | 可以（預設 ACL 給了使用者 rwx） | 設計如此（使用者要能管） | `cpp/aos-daemon/src/child/subuid.cpp:262-263` |
| `sub:N` 寄信 | 寄不出去（信箱沒開給它） | 已知沒做（K16） | 同上「沒做」 |
| 用信夾擁有者認寄件人 | 沒做 | 已知沒做（K9）。**做了之後上面 `sender` 那個洞才補得起來** | 同上 |
| 清道夫看 `sub:N` 行程的環境 | 讀不到，只報不收 | 已知沒做 | `py/aos/sweep_proc.py:51-52` |

- **嚴重度**：會誤導（`sender` 與每人額度那一條：看起來有分帳，其實寄件人自己說了算）；其餘只是還沒做。
- **影響到今天哪個上層東西**：sub:N、llm kernel 的 `budget.senders`。
- **建議處理方向**：K9（信夾擁有者認寄件人）排在 K16（開信箱給 sub:N）之前或同時做；在那之前文件寫明「`budget.senders` 只防呆、不防人」。
- **依據**：讀程式推的（推測）；sub:N 真換身分我沒有另外實測，照該線自己的紀錄。

### F8　出事時看不看得出來：靜默的失敗

| 情況 | 看得到嗎 | 依據 |
|---|---|---|
| proc 的 stdout | **看不到**：daemon 起的 proc stdout 一律 `/dev/null`。三個 kernel 範本的 `_entry` 都寫 `aos-daemon --enable-logs`，掛在別台 daemon 底下時這些 log（子項起停、接表警告）直接丟掉 | 實測（e2）：`flap pid … stdout -> /dev/null stderr -> …/procs/flap/stderr.txt`；`cpp/aos-daemon/src/child/child.cpp:53-56`、`templates/kernel/llm-kernel/_entry` |
| `auto_restart` 的 proc 每隔幾秒掛一次 | **幾乎看不到**：只有「連 3 次都在 3 秒內退」才停下並寫 reason；活超過 3 秒再掛就無限重起、沒有退避，表上沒有重起次數，只有 pid 在換 | `cpp/aos-daemon/src/daemon/tend.cpp:195-207`、`cpp/aos-daemon/src/child/child.cpp:342-415`（列上沒有次數欄） |
| 壞信 | 只留**最後一封**的原因在 `mailbox_warning`，前面的被蓋掉；信封壞的不回信 | `cpp/aos-daemon/src/daemon/mailbox.cpp:96-98` |
| 回信寄不出去、信收不掉 | **完全靜默**（例外直接吞掉，沒有 warning） | `cpp/aos-daemon/src/daemon/mailbox.cpp:176-188` |
| 信寄給暫停／停止／已死的 daemon | 寄件人只會逾時；要自己去讀對方的 `state.json` | `cpp/aos-daemon/docs/05-信箱.md`（paused 那圈不認領） |
| kernel 站拒絕 | 看得到：回一封帶 `error` 的信。但寄件人是 `sub:N` 時收不到（F7） | `py/tools/aos/kernel/round.py:119-121`（合併列號 341-343） |
| kernel 站自己一直失敗 | 看得到但很淡：`state.json` 的 `body_code`，stderr 只在碼變了才印一行 | `cpp/aos-daemon/src/daemon/body.cpp:58-62` |
| limits 命中 | 看得到：`limit_hit`（cpu、檔案大小、cgroup 的記憶體與行程數）。沒開 cgroup 時記憶體只有 `limit_suspect`（猜的） | `cpp/aos-daemon/src/child/child.cpp:308-334` |
| proc 卡住 | 預設**不判**（`stuck_after_*` 沒寫＝0＝永不判）；`stop` 也沒有時間上限，列會一直 `stopping` | `cpp/aos-daemon/src/daemon/daemon.hpp:70`（合併列號）、文件 08 |
| daemon 自己凍住（F2） | 從外面只看得到 `state.json` 很久沒變；上一層沒設 `stuck_after_*` 就不會判它卡住 | 同 F2 |

- **嚴重度**：會誤導（前四列）。
- **建議處理方向**：(a) proc 的 stdout 也接進小格一個檔（或文件寫明「要留 log 就自己導」並把範本的 `--enable-logs` 拿掉或改導向）；(b) 表上加一欄重起次數與上次退出碼；(c) `mailbox_warning` 改成最近幾封，回信寄不出去至少印一行 warning。

### F9　幾個小的競態與卡點（都沒實測）

1. **daemon 替 `sub:N` 對號碼時同步等、沒有期限**：`recv` 等子行程、`waitpid` 等 `newuidmap`／`newgidmap`。helper 卡住＝daemon 卡住。`cpp/aos-daemon/src/child/subuid.cpp:273`、`:140`。嚴重度：會卡死（機率低）。
2. **切檔的表先清舊分檔、後寫主檔**：`clean_parts(now)` 在 `write_window(主檔)` 之前叫；主檔那一下寫不成（磁碟滿）時，「上一次用到的分檔」的記錄已經換成這次的，磁碟上主檔指著的舊分檔下一輪起會被當成退役、2 秒後刪掉。這時 daemon 再死＝表解不開＝空表開始（接 F3）。要超過 100 列＋寫失敗＋當機三件事同時，機率很低。`cpp/aos-daemon/src/daemon/windows.cpp:235`、`:240`、`:188`。嚴重度：會誤導。
3. **daemon 的 stop 與別人寫同一份 `ctl.json`**：daemon 寫 `{"cmd":"stop"}` 到 proc 的 ctl，`aos-agent ctl`／`aos-daemon-ctl` 也寫同一份（pause／resume）。各自原子寫，但後寫的蓋前寫的；stop 被蓋掉時那列一直 `stopping`（stop 沒有時間上限）。`cpp/aos-daemon/src/daemon/tend.cpp:119-136`、`py/aos/daemon_ctl/ctl.py:100-112`。嚴重度：會卡死（那一列；可再下 `sleep` 解）。
4. **`cur/` 重做**：daemon 在「套了信、還沒收信」之間死掉，再起會把 `cur/` 的信重做一次。對「加一支跑一次就結束的 proc」的信，若那支已經跑完下表，會再跑一次；回信也可能重複。`cpp/aos-daemon/src/daemon/mailbox.cpp:42-45`、`:48-50`。嚴重度：會誤導。
5. **提醒行寫到關掉的管子**：`--enable-logs` 那條路有擋 SIGPIPE，但 stderr 的 `warn` 沒有；daemon 的 stderr 是管子、讀的人先走了，下一行 warning 會把 daemon 打死（等同 kill -9，再起照接回）。`cpp/aos-util/src/io.cpp:130-132`（合併列號 405-407）、`cpp/aos-loop/src/engine/window.cpp:137-143`。嚴重度：會卡死（機率低）。

## 測試表

| 項目 | 預期（依哪份文件哪一句） | 實際 | 差在哪 |
|---|---|---|---|
| proc 出錯結束，stderr.txt 1 GB | 08「stderr.txt 沒有上限、不輪替……交給清道夫」：沒說 daemon 會受影響 | daemon 尖峰 2.1 GB、約 10 秒不顧別的 | 文件沒講 daemon 會整份讀 |
| 同上，daemon 記憶體受限 600 MB | 08「一個 proc 的 stack、信箱出問題時不整台停」 | 整台 `Internal std::bad_alloc` 退 1 | 跟標題那句相反 |
| 身體跑 12 秒時 ping | 05「回信 1 秒內出現在 BOX/new/」 | 10.1 秒 | 文件只說 poke 不打斷，沒說信也等 |
| 身體跑 12 秒時 auto_restart | daemon.hpp「退了同一拍重起」 | 間隔 12.1 秒（該是約 4 秒） | 同上 |
| daemon 起的 proc 的 stdout | 沒找到文件講 | `/dev/null` | 文件沒講 |
| kill -9＋表壞，loop 型 | 08「公開 state 窗對得上＝接回、不另起」 | 接回了，pid 不變 | 一致 |
| kill -9＋表壞，exec 型 | 08 同一句（寫的是「起任何 proc 前」） | 另起一份，舊的成孤兒 | 文件說「任何 proc」，實際只有 loop 型 |
| daemon 以 Internal 退出時收不收子項 | N P-36「不論為什麼結束都先收掉所有子 loop」 | 有收（`ok` 列 stopping、行程不在） | 一致 |

## 可以放心的

- **寫檔都是原子的**：三扇窗、信、`order.json`、切檔的分檔都是「寫同夾暫存→（fsync）→改名」，暫存名帶 pid，多人同寫不互踩。`cpp/aos-util/src/files.cpp:100-136`、`:248-273`；kernel 站的 Python 寫檔同一套（`py/tools/aos/kernel/runner.py:28-44`）。沒找到直接開檔截斷再寫的窗。
- **一個 stack 只會有一台 daemon**：flock 鎖 stack 資料夾，fork 出去的子行程一律先關掉這把鎖。`cpp/aos-daemon/src/daemon/daemon.cpp:257-283`。
- **認行程不會認錯人**：pid＋啟動 ticks＋boot_id，再看 `/proc/<pid>/environ` 是不是這棵樹；自己生的子項用 `waitpid` 收，沒收之前 pid 不會被重用。`cpp/aos-daemon/src/daemon/adopt.cpp:56-121`、`:197-199`、`:277-281`；`cpp/aos-daemon/src/child/child.cpp:287-340`。
- **aos-lock 的收屍**：函式庫的鎖帶 flock 存活標記，持有者死了別人就收得掉；多人同時收用 `.reaping` 牌子擋，寫名牌用目錄 fd 不會寫進別人的新鎖。`cpp/aos-lock/src/lock/lock.cpp:107-133`、`:162-190`、`cpp/aos-lock/src/holder/holder.cpp:86-98`、`:133-135`。有序寄信用的就是帶 flock 的那種（`cpp/aos-post/src/send/send.cpp:69`），寄信人死在鎖裡不會卡死後面的人。
- **信箱的認領與投遞**：都是資料夾改名，處理者只會看到完整的信；認領後沒收完就死，下次從 `cur/` 重做。`cpp/aos-post/src/send/send.cpp:196-205`、`cpp/aos-post/src/take/take.cpp:38-47`。
- **kernel 站同一個收件箱只會有一個在跑**（`requests/.flock`），`queue.json` 壞了會提醒並從 `cur/` 重排。`py/tools/aos/kernel/round.py:64-72`（合併列號 285-293）、`py/tools/aos/kernel/queue_fifo.py:27-37`（合併列號 381-395）。
- **問腦工作的資料夾收完就刪**，不會堆。`py/tools/aos/kernel_llm/llm_rules.py:270`。
- **`--enable-logs` 寫到關掉的管子不會死**。`cpp/aos-loop/src/engine/window.cpp:132-160`。
- 實測一致的：loop 型接回、daemon 內部錯誤退出時照樣收子項（見測試表）。

## 沒測到的＋原因

- **sub:N 真換身分**：只讀程式與該線紀錄，沒自己起；我的題目重點在邊界分析，真機那幾條該線已驗。
- **cgroup**：這台沒有 systemd user。
- **磁碟滿、唯讀 stack**：照硬規則 5 不灌磁碟；F9 第 2 條因此只有推測。
- **超過 100 列的切檔**：沒起那麼多 proc。
- **真的 kernel 站 hook 卡住**：用一支 `sleep` 當身體代替（e2），機制同一條路（`run_body`）；沒有起真的站。
- **200 毫秒窗內 kill -9**（F3 的另一個入口）：時間窗太小，沒有穩定重現法，用「表壞」當替身。
- **pid 重用、開機後撞號**：做不出來，只讀程式。
- **aos-exec、aos-fsm、aos-json、aos-directive、aos-inst**：沒逐行讀，只看了 daemon 叫到的那幾處；`_clock` 與時鐘檔沒深查。
- **F5、F7、F8 的大部分、F9 全部**：只讀程式。

## 行程交代

- 開工前 `pgrep -af aos-`：當時沒有任何 aos 行程（只有我自己的 bash）。
- 我起過的：e1 兩台 daemon（pid 321695、323805 及先前兩次失敗嘗試的 316xxx）、e2 一台（326903）、e3 兩台（338581 及重起的那台）。都是 `aos-daemon-ctl -d <我的 stack> shutdown` 收的，或自己退的（e1 第二種是 daemon 自己 bad_alloc 退出）。
- e3 留下一支不在表上的 `sleep 300`（pid 338583，就是 F3 的孤兒），腳本確認 cwd 在我的子夾後 SIGTERM 收掉。
- 收尾 `pgrep` 逐一比 cwd：沒有任何行程的 cwd 在 `f-struct/` 底下。機器上其他 aos 行程是別的隊（`e-upper`、`b-tests`）與別條線（`ok-fsmwrap`）的，沒碰。
- 留下的檔：`f-struct/e1-1024-0/`、`e1-1024-600/`、`e2/`、`e3/`（現場，1 GB 的假 stderr.txt 已刪）、`repro/` 三支腳本、本報告。
