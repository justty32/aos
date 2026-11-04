# 2026-11-02 state 窗改「啟動寫一次、有變動才更新」、daemon 的 state 改名 `daemon_state.json`、每次的紀錄進 log

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜出發點：使用者 11-02 看試驗場 daemon 的 `.stack/`（[11-02 試驗場 daemon](playground-daemon.md)）｜條文：[N-09、N-13、N-14、N-17、N-32、N-33](../../../docs/NORMS/05-基礎設施-窗.md)、[N-28](../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-39](../../../docs/NORMS/07-基礎設施-組合子.md)（fsm 的 `trace.jsonl`）、[P-38](../../../docs/CONVENTION/06-巢狀.md)｜實作：[impls/aos-loop](../../../impls/aos-loop/README.md)（`src/engine/window.cpp`、`loop.cpp`）、[impls/aos-daemon](../../../impls/aos-daemon/README.md)（`src/daemon/windows.cpp`）｜同天的另兩份規劃：[11-02 stack-tools](stack-tools.md)（隊長正在落地）、[11-02 daemon-env](daemon-env/README.md)（控制口，命名未定）

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。規劃節是 fable 的原規劃，**以決定節為準**（log 檔、心跳進 log 等沒做）；11-02 已實作，結論在文末「實作結論」。

## 使用者原文（11-02，逐字）

> daemon寫state.json...幫我改成寫daemon_state.json。然後我感覺loop/daemon可以稍微再改一下，就是說他們現在都是連續覆寫state.json之類的檔案，我覺得這樣不好。應該要遵照慣例，會持續變動的就寫在log。state.json就是初始的時候寫下，有變動的時候更新，ctl也是。比如loop_state，我覺得它的定位應該改成"啟動的時候寫一次，後面有變動的時候才更新，有變動的時候包括phase有變化，處理ctl時候的各階段"，json格式不用動(雖然我覺得那個"kind"沒啥用)，但可以添加一個updated_at，表述這是啥時候更新的。

## 決定（11-02，使用者）

使用者原文（11-02，逐字）：

> 然後log這塊，要給argv讓使用者選擇是否要印出。kind沒人在用，那就拿掉。心跳這塊就直接看pid就好，從檔案判斷...檔案的更新本來就會受到多方面因素影響，這其實不太好，應該說，要看一個proc是否還活著，除去linux底層proc機制外，我們的aos-daemon-ctl問詢也是一個方式，兩者並存。2.要。3.對。4.收掉。5.log...daemon和loop他們就是把log輸出到stdout，默認是開著的

- **log**：daemon 與 loop 把 log **印到 stdout**，**預設開著**；給 argv 讓使用者選擇關掉（取代規劃裡的 `log` key 與 `log.jsonl` 檔）。旗標名實作時照慣例定。
- **`kind` 拿掉**（沒人在用）。
- **衝突 1（心跳）**：拿掉心跳。判斷 proc 活著＝看 pid（Linux 的 proc 機制），**另外**用 aos-daemon-ctl 問詢，兩者並存；不從檔案的更新時間判斷（「檔案的更新本來就會受到多方面因素影響」）。
- **方向題 1**：daemon 的 `ctl.json` 也改名 `daemon_ctl.json`（要）。
  - **11-02 晚推翻**：控制自身的窗不加前綴，daemon 自己的改回 `ctl.json`／`state.json`，見 [ctl-state-names](ctl-state-names.md)。
- **方向題 2**：`counter_runs` 不算變動（對）。
- **方向題 3**：`recorded_at` 收掉，只留 `updated_at`。
- **方向題 4**：見上 log（stdout、預設開）。
- 前綴原則見 [exec 像繼承 § 結論](exec-inheritance.md#結論11-02跟使用者討論後)：daemon 自己的東西用 `daemon_*`、loop 的用 `loop_*`。

## 決定（11-02 晚，使用者；實作中陸續裁的）

使用者原文（11-02，逐字，依先後）：

> 把--kind刪掉，XXX後面可以接-- ... 也就是附加argv參數。改成子項結束後不留名單。然後跟我說說aos-daemon-ctl ls,rm兩個指令。

> running/waiting確實不該算變動。loops_ctl這邊，可以收斂成added/removed，不區分loops/exec。loops這塊保留，但裡面兼容execs。loops_state.json這邊，kind刪掉，loops/execs仍分開，letter_warning改成mailbox_warning，然後告訴我daemon.json如何指定信箱模式...我希望信箱和loops_ctl共存，或者說兩者都可以在daemon.json中設定

> 喔等等，那還是不要合併了

> 信件也不要跟著改

> loops這塊...也弄個execs吧

> loops_mailbox改名為loops_ctl_mailbox。寫null就是不開窗，ctl/ctl_mailbox可以一起不開

> daemon.json中的ctl/state，如果指定null，那就是不開窗

> aos體系下，stdin/out/err都可以任意指定，混在一起就是使用者自己要處理的，不用管太多。

> aos-loop XXX -- ...應該是可以這樣用的，代表後面的argv轉給裡面的exec？這樣可以嗎？

> 1. 是的，就應該這樣，也就是aos-XXX ... ... -- ...，第一個...就是aos-XXX本身的旗標，大多都是--aaa bbb或-c，第二個...就是目標檔案，或是目標字串陣列，後面就是純參數。

> aos-loop和aos-daemon他們印出的log感覺都沒啥用，應該要改成默認不印。

（daemon 的 execs 要不要也收內嵌單子）「6.要。」——原文與決定記在 [loop-stdio](loop-stdio.md)。

決定：
- **aos-daemon-ctl `add`**：`--kind`（含 `max1`）拿掉，只剩自動識別；`add [--name N] [--ws WS] XXX -- 參數...`，`--` 後面當附加 argv。
- **子項結束後不留名單**（loop 型、exec 型都是）：退了就從 `loops_state` 的表拿掉，小格照留。
- **running ⇄ waiting 不算變動**。
  - **11-03 補**：loop 的 ctl.json 11-03 改成一道指令（`cmd`），「ctl 有變才算變動」照舊、只是形狀換了，見 [11-03 ctl-commands](../03/ctl-commands.md)。
- `loops_state`：`kind` 刪、`loops`／`execs` 兩張表照舊分開、`letter_warning` 改名 `mailbox_warning`。
  - **11-03 推翻**（[11-03 procs](../03/procs.md)，使用者 11-03「連名單也合一」）：上面「喔等等，那還是不要合併了」與這句「兩張表照舊分開」→ `loops`／`execs` 合成一份 `procs`，窗改 `procs_ctl`／`procs_state`／`procs_ctl_mailbox`。「子項結束後不留名單」**照舊**（使用者 11-03「照舊拿掉」），只多一個例外：daemon 自己下的 stop 退了的列留成 `stopped`。
- loops_ctl **不**收斂成 added／removed（使用者撤回）；信的 body 也不改；loops_ctl 多認一個 **`execs`**（跟 `loops` 對稱，整份取代）。
- daemon.json 的 `loops_mailbox` 改名 **`loops_ctl_mailbox`**；它跟 `loops_ctl` **可以同時開**，寫 null＝不開，兩個都不開也行。
- `ctl`／`state`（以及 `loops_ctl`、`loops_state`、`loops_ctl_mailbox`）寫 null＝不開窗。
- log 跟身體的 stdout 混在一起是使用者自己的事，不另外分；log **改成預設不印**（翻掉同日稍早的「預設開」）。
- 命令列 **`aos-XXX [旗標...] 目標 -- 參數...`**：aos-loop／aos-daemon 的 `設定檔 -- 參數...` 每次接到 exec 後面。通則只記原文，其他指令這輪不改。

## 通稱統一 mailbox_warning（11-02 晚，使用者）

頂層問：「要不要統一成 mailbox_warning？」（daemon 的 `letter_warning` 白天已改 `mailbox_warning`，agent queue 與 eca 那側還是舊名。）使用者：「要」。

決定：壞信警告一律叫 `mailbox_warning`——agent queue 的 `$AOS_STACK/letter_warning.txt` → `mailbox_warning.txt`（`lib/agent/queue`、`aos-listen --status`）、aos-eca-turn 的 trace 欄位 `letter_warning` → `mailbox_warning`；N-16 通稱跟著改（上面「帶給使用者的」那條的 N-16 就此結案）。代定（可翻案）：舊名不留別名、`aos-listen --status` 不讀舊的 `letter_warning.txt`（同 AOS_DAEMON 改名的原則；舊 stack 裡殘留的舊檔只是不再顯示，下一封壞信就寫新名）。

## 現況（查清的，不是規劃）

### 誰在寫、寫什麼、多久寫一次

- **aos-loop 的 state 窗**（`src/engine/window.cpp` `write_main`）：`{kind, phase, counter_runs, max, interval_ms, paused, ctl_seq, ctl_warning, (info()), code(結束時), pid, started_at_ticks, boot_id, recorded_at}`。寫的時機（`loop.cpp` `main_loop`）：每次跑之前寫一份 `running`、要睡就寫一份 `waiting`／`paused`、睡著時每滿 1 秒再寫一份（`beat`，N-17 心跳）、結束寫一份帶 `code`。**沒有身體的 daemon 一圈只寫一份 `waiting`**（200 ms 一份）。
  - **每圈都變的欄位**：`counter_runs`（沒身體的 daemon 每圈也加 1，`max` 靠它）、`recorded_at`（寫的那一刻）、`phase`（有身體時 running ⇄ waiting 來回）。
  - **只在 phase 變／處理 ctl 時才變的**：`phase`（paused／stopped／done）、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`（ctl 採用／不採用那圈）、`code`（結束）。
  - `pid`、`started_at_ticks`、`boot_id` 整個行程不變。
- **aos-daemon**：繼承 Loop，所以自己的 `state.json` 跟上面一樣；另一扇 `loops_state.json`（`src/daemon/windows.cpp` `write_more`）＝`{kind, ctl_seq, ctl_warning, letter_warning(信箱模式), loops 表, execs 表, 心跳四欄}`，**Loop 每寫一份 state 就跟著寫一份**（同一份心跳），所以也是每圈一份；表超過 100 列切進 `loops_state_loops/<雜湊>.json`（內容雜湊當檔名，內容沒變就不重寫；主檔照樣每圈重寫）。表的每列 `{pid, started_at_ticks, phase, code, signal, ws?}` 只在起、收、退時變。另外 `reconcile` 起一大批前、`finish` 等子項退時每秒 `beat()` 一份 `stopping`。
- **ctl 窗**（`ctl.json`、`loops_ctl.json`）是別人寫、程式只讀，每圈讀一次；壞的不採用、原因進 state 的 `ctl_warning`（N-08）。
- **檔名由誰定**：aos-loop／aos-daemon 的 `ctl`／`state` 是**選填 key、沒寫就不開**（N-09、N-13），程式沒有預設檔名；「daemon 寫 state.json」是因為所有 daemon.json 的作者都寫 `"state": "state.json"`——demo 五份（daemon、daemon-2、daemon-3、llm-kernel、talk/team）、`extras/ai_tools/bin/aos_ai_daemon.py:15`（它自己生的 daemon.json）、測試（test_daemon、test_aos_daemon_ctl、test_eca_hub、impls 兩份 test_cli）、README 範例。只有 `loops_ctl`／`loops_state` 有程式預設檔名（沒寫＝`loops_ctl.json`、`loops_state.json`）。daemon 幫子 loop 補的 `state.json`（`child.cpp:141`）是**子 loop 自己的窗**，跟本題無關、不動。
- **`kind` 欄**：N-14「窗內自述種類（`kind`）」，值一律 `"state"`。讀者：**沒有任何程式讀它**（grep 全 proto8：只有測試斷言它等於 `"state"`、欄位順序表）。使用者說「不用動」→照留，不處理。

### 誰在讀、靠哪些欄位

| 讀者 | 讀哪扇 | 靠什麼 | 靠「每圈變」的欄位嗎 |
|---|---|---|---|
| `bin/aos-daemon-ctl ls` | `loops_state.json` 兩張表 | 每列 `phase`／`pid`／`code`／`ws` | 否 |
| `extras/eca_hub/bin/aos-eca-hub` | `loops_state.json` | **判 daemon 活著＝頂層 `pid`＋`started_at_ticks` 對 /proc**；每列 `phase`／`code` | 否 |
| `extras/ai_tools/bin/aos_ai_base.py` `Daemon.running()` | daemon 的 `state.json`＋自己寫的 `up.json` | `pid`＋`started_at_ticks` 活著、`phase` 不是 done／stopped；`wait_seq` 等 `loops_state` 的 `ctl_seq` 回音 | 否 |
| `aos_ai_daemon.py status` | daemon 的 `state.json` | 顯示 `phase`、`code`、`recorded_at` | **只顯示**（不拿它判斷） |
| `lib/aos/aos_ws.py loop_state`、`extras/human/aos-listen --status`、`aos_ai_agents.py` | agent 的 `state.json`（aos-loop） | `phase`（看 paused） | 否 |
| `demo/talk/team/quiet.py` | 子項小格 `loops/<名>/state.json` | `phase`＋`code` | 否 |
| daemon 自己 `adopt` | 上一份 `loops_state.json` | 每列 `phase`＝running、`pid`＋`started_at_ticks` | 否 |
| 測試 | 兩扇 | `impls/aos-daemon/tests/test_cli.py:405-493`（量 `recorded_at` 間隔、「一次只寫一份」用 `counter_runs` 去重）、`:869`（暫停中 `recorded_at` 要變＝心跳照跳）、aos-loop `test_cli.py:356`／`tests/test_loop.py:125`（欄位順序表）、`test_demo.py:57`（抹掉 `recorded_at` 等會變的欄位） | **是**——全是心跳的測試，要改 |

結論：**沒有任何程式靠 `recorded_at` 新不新或 `counter_runs` 在動來判活著**；活著一律已經走 N-17 的確定法（pid＋`started_at_ticks`）。要改的讀者只有測試和 `aos_ai_daemon.py status` 的顯示欄。

### 「會持續變動的就寫在 log」這個慣例在哪

- **N-39**（fsm）：每次在 `$AOS_STACK/trace.jsonl` **追加一行** `{"at","state","code","signal","elapsed_ms"}`，**trace 不設上限**；state 檔只放現在狀態名。**P-38**：每個 fsm 層有自己的 `trace.jsonl`，每行帶 `started_at`（ISO 8601 UTC 到毫秒）對時間線。**P-19**：「要知道有沒有跑滿看 `trace.jsonl` 行數」。
- agent 範本：`history.jsonl` 只附加（P-42 的 10-28 補）；`$AOS_STACK/letter_warning.txt` 另放。
- **N-16 的 10-28 刪**：「JSONL 追加檔＝一條流」不寫進 aos **標準**、要用由 proc 自己定——所以本題的 log 是 aos-loop／aos-daemon **自己的檔**（N-13 名字格式程式自訂），不是新的一種窗、也不立新條號。
- **N-14（10-29 改口）**：窗＝只看最新那份算數的固定檔、**判斷變化比內容或序號，不比 stat**——使用者這次要的「有變動才更新」就是把這條用在**寫的那一邊**：內容沒變就別重寫。
- **N-17／N-32**（心跳）：「內容沒變也每隔一段碰一下」「超過 3 倍間隔沒動靜算疑似死亡（確定要看 pid＋啟動時間）」「睡著時最多隔 1 秒寫一次」——這條**跟新規矩正面相撞**，見衝突 1。

## 規劃（fable，照原則定的細節，可翻案）

### 1. 名字

- daemon 自己那扇 state 的**慣用檔名**改 `daemon_state.json`（C-54：主題放前面，跟 `loops_state.json` 同一個格式）。因為程式本來就沒有預設名，「改」＝把 demo 五份 daemon.json、`aos_ai_daemon.py` 生的 daemon.json、`aos_ai_base.py:190` 讀的路徑、測試、README、N-28 範例裡的 `"state": "state.json"` 全改成 `"state": "daemon_state.json"`；**aos-daemon 程式不加預設名**（N-09「沒給就不開、不提醒」照舊）。子 loop 的 `loops/<名>/state.json`、agent 的 `state.json` 不動（那是 aos-loop 的窗）。
- daemon 的 `ctl.json` 要不要跟著改 `daemon_ctl.json`：使用者只說 state，照原則（C-54 同一組名字同一個格式）**建議一起改**，列成方向題 1。`loops_ctl.json`／`loops_state.json` 已經是主題前置，不動。

### 2. 寫入時機：啟動寫一次、有變動才更新

- **規則一句話**：每次「要寫 state」的時候，先組好這份 JSON（不含時間欄），跟上一份寫出去的比；**不一樣才寫**、一樣就不碰檔（N-14 的「比內容」搬到寫的一邊）。啟動後的第一份一定寫。結束那份一定寫（帶 `code`）。
- 什麼算變動（照這個規則自然得出，跟使用者舉的例子對得上）：
  - `phase` 變（running／waiting／paused／stopping／stopped／done）。
  - **處理 ctl 的各階段**：讀到新的好 ctl → `ctl_seq`／`max`／`interval_ms`／`paused` 生效值變；讀到壞 ctl → `ctl_warning` 從 null 變成原因；再讀到好的 → 清回 null；daemon 過渡期提醒 `ctl_note_` 同理。暫停中照樣每圈讀 ctl、有變就寫（現有測試 `test_cli.py:869` 那條「暫停中 loops_ctl 的 seq 回音」行為不變）。
  - daemon 的 `loops_state.json`：表有列起、退、收、拿掉、`letter_warning` 變、`ctl_seq`／`ctl_warning` 變。起一大批時每起一個就是一列變→照寫（原本 `beat()` 每秒一份的用意——讓人看得到進度——自然保留，而且更細）。`finish` 等子項退：進入 `stopping` 寫一份，之後每退一個寫一份，不再每秒一份。
  - 使用者原文的「ctl也是」：ctl 是別人寫的、程式只讀，不存在「程式寫 ctl」；這裡解讀成「ctl 相關的欄位有變才算變動」（上一點），不另立規矩。
- **`counter_runs` 不算變動**（方向題 2，fable 先這樣定）：它每次都加 1，若算變動，有身體的 loop 每次照寫兩份（跟現在一樣多）、沒身體的 daemon 每圈照寫（200 ms 一份，等於沒改），使用者的抱怨沒解。所以窗裡的 `counter_runs`＝「`updated_at` 那一刻的次數」，一份快照；準確的每次計數看 log（下節）。有身體的 loop 因為 `phase` 每次 running ⇄ waiting，仍是每次寫兩份——這是真的變動，照使用者原文（「phase 有變化」）就該寫；`interval_ms` 0 的 loop 連 `waiting` 都沒有、只有 `running`，一次一份。
- **心跳拿掉**（衝突 1）：不再「內容沒變也每秒碰一下」。活著照 N-17 的確定法看 `pid`＋`started_at_ticks`（＋`boot_id`），所有現有讀者本來就這樣做。`Loop::beat()` 保留當「要寫就寫」的入口但不再帶 1 秒計時（或整個拿掉，實作者定）。

### 3. 每次都會變的東西進 log

- **開法**：loop.json／daemon.json 多一個**選填 key `log`**＝檔名、在 `$AOS_STACK` 底下、沒寫＝不開（跟 `ctl`／`state` 同一條線 N-11、同一套路徑規則、同樣 `StackMissing`）。不借 `state` 這個 key 順便開第二個檔（C-56「寫什麼就做什麼」）。daemon 幫子 loop 補 `ctl`／`state` 時**不補 `log`**（使用者沒要求、子 loop 自己的 loop.json 要就寫）。
- **慣用檔名**：loop 寫 `log.jsonl`、daemon 寫 `daemon_log.jsonl`（跟 `daemon_state.json` 同一組）。不用 `trace.jsonl`：agent 的 fsm 跟它的 aos-loop **共用同一個 `$AOS_STACK`**（agent-bob 的 `.stack/` 裡 `state.txt`、`trace.jsonl` 是 fsm 的，`state.json` 是 loop 的），叫 `trace.jsonl` 會撞。
- **格式**：JSONL、**一次一行、那次結束時追加**（同 N-39 fsm 的做法）：`{"started_at": 這次開始的 UTC 時間(ISO 8601 到毫秒，P-38), "counter_runs": N, "code": 子程式的碼, "signal": 訊號或 null, "elapsed_ms": 跑了多久}`——欄位名照 N-30／N-39 現成的。**沒有身體的 daemon 沒有「次」可記，log 不寫行**（它的每圈只有 `counter_runs` 加 1，沒有值得記的事；子項的起退已經在 `loops_state.json` 列上）。結束不寫 log 行（結束碼在 state 的 `code`）。
- **上限／輪替**：跟 N-39「trace 不設上限」、N-28「aos 不保證子項輸出不無限長、使用者自行承擔」一致——**不設上限、不輪替**；要輪替自己在外面接 logrotate。一行約 120 bytes，一天跑 10 萬次才 12 MB。
- 寫法：`fopen` append、一行一次 `fwrite`＋`fclose`（一行小於 PIPE_BUF 的追加在 POSIX 上是原子的，不需要 N-05 的改名）；寫不了＝`WriteFailed` 一行、退 1（同 N-39 ③④）。

### 4. `updated_at`

- 兩扇窗（`state.json`／`daemon_state.json`、`loops_state.json`）都加 **`updated_at`**＝這份寫出去的那一刻，格式同 `recorded_at`（ISO 8601 UTC 到毫秒，`aos::utc_now_ms()`；C-54 R6「時間點＝`<發生了什麼>_at`」）。放在最後一欄（`recorded_at` 之後），現有欄位順序不動。
- `recorded_at` 照使用者「json 格式不用動」**留著**；心跳拿掉之後它跟 `updated_at` 永遠同值——這點列成方向題 3（要不要順手把 `recorded_at` 收掉），fable 不自己動。
- `kind` 照留；誰在用見現況（沒人讀，只有測試）。

### 5. 讀者怎麼改

- 判活著：**不改**——aos-eca-hub、aos_ai_base、adopt 全是 pid＋`started_at_ticks`。N-17 的「超過 3 倍間隔沒動靜算疑似死亡」那句失效、從條文拿掉（衝突 1）。
- 看進度：有身體的 loop 看 `log.jsonl` 行數／最後一行（P-19 本來就這樣說 fsm）；`counter_runs` 在窗裡是快照。沒身體的 daemon 看 `loops_state.json` 的表。
- `aos_ai_daemon.py status` 的 `recorded_at` 顯示欄改 `updated_at`。
- 測試：心跳間隔那幾條改成「睡著 1.5 秒窗的 `updated_at` **不變**、mtime 不變」「暫停中 loops_ctl 的 seq 變了 loops_state 照寫」；欄位順序表加 `updated_at`；`test_demo.py` 抹掉的欄位加 `updated_at`、demo 小格檔案表加 `log.jsonl`（若 demo 開了 log）。

## 要使用者看的衝突與方向題

### 衝突 1：N-17／N-32 的心跳（10-20 使用者「照預設」定）vs「有變動才更新」

- **條文**：N-17「state 帶 pid、啟動時間、開機 id；**內容沒變也每隔一段碰一下**；超過 3 倍間隔沒動靜算疑似死亡（確定要看 pid＋啟動時間）」、N-32「睡著時最多隔 1 秒寫一次 state……一圈裡很久的工作也照『最多隔 1 秒』寫」。這是 10-14 定、10-20 使用者「照預設」、10-22 定稿的。
- **衝突**：新規矩說內容沒變就不寫，心跳的定義就是「沒變也寫」，兩個不能同時成立。
- **各自後果**：
  - 照新規矩（fable 建議）：一個睡著的 daemon 檔案系統上**完全沒動靜**，光看 `.stack/` 的 mtime 看不出它活著，要看 `pid`＋`started_at_ticks`（現有讀者全都已經這樣做，沒有人靠 mtime 或 `recorded_at`）。N-17 改寫成「活著只看 pid＋啟動時間＋開機 id；窗有變才寫」，拿掉 3 倍間隔那句；N-32 的「每秒一份」改成 log 與變動。
  - 保留心跳：等於不改，使用者的抱怨（連續覆寫）在沒身體的 daemon 上完全沒解。
  - 折衷「心跳進 log」：每秒一行、一天 86,400 行，又是「持續變動的檔」，只是換個檔連續寫；不建議。

### 衝突 2：N-28「state 窗就是 save 檔」——daemon 重起靠 `loops_state.json` 接回子項

- 不是真衝突，但要說一聲：有變動才寫之後，`loops_state.json` 仍然在每次表變時寫，adopt 讀到的永遠是最新的表，**接回不受影響**。唯一差別：daemon 被 SIGKILL 時最後一份不再是「1 秒內的」而是「最後一次表變時的」，但表沒變的話兩者內容一樣。

### 方向題 1：daemon 的 `ctl.json` 要不要跟著改 `daemon_ctl.json`

使用者只說 state。照 C-54 一組名字同一格式（`daemon_ctl.json`／`daemon_state.json` 對 `loops_ctl.json`／`loops_state.json`）建議一起改；代價是 demo、README、ai_tools、測試多一輪 `"ctl": "ctl.json"` → `"daemon_ctl.json"`，程式一行不動。(a) 一起改（fable 建議）；(b) 只改 state。

### 方向題 2：`counter_runs` 算不算「變動」

每次都加 1 的計數若算變動，沒身體的 daemon 每圈照寫 200 ms 一份、等於沒改。fable 定：**不算**，窗裡的 `counter_runs`＝`updated_at` 那一刻的快照，每次的準確計數看 `log.jsonl`。替代：(b) 算變動——有身體的 loop 行為跟現在差不多（每次寫），沒身體的 daemon 改成「`counter_runs` 不加、`max` 對它無意義」才省得下來，但這改了 daemon `max` 的語意（現有測試 `max: 15` 沒身體的 daemon 跑 15 圈結束）；(c) 把 `counter_runs` 從窗搬去 log（動 json 格式，使用者說不動）。

### 方向題 3：心跳拿掉後 `recorded_at` 跟 `updated_at` 永遠同值，要不要順手收掉 `recorded_at`

使用者原文「json 格式不用動……可以添加一個 updated_at」。照字面＝兩欄同值留著（fable 照字面做）。另一邊，使用者一向不喜歡冗餘（「審」的範圍）；收掉只動一個欄位名，讀者只有 `aos_ai_daemon.py status` 顯示和測試的欄位表。(a) 照字面兩欄都留；(b) `recorded_at` 改名 `updated_at`（只有一欄）。

### 方向題 4：log 要不要在 demo 與 ai_tools 的 daemon.json 裡預設打開

`log` 是選填、沒寫不開。demo 五份與 `aos_ai_daemon.py` 生的 daemon.json 要不要都加 `"log": "daemon_log.jsonl"`（沒身體的 daemon 其實不會寫任何一行，加了只是示範）；agent 的 loop.json（demo/agent-*）要不要加 `"log": "log.jsonl"`。fable 建議：**有身體的**（demo/daemon、llm-kernel、agent 範本）加，純監工的不加。

## 實作步驟表（給隊長；每步都要先 pull）

**前提與交集**：
- 另一位 Opus 隊長**正在落地** [11-02 stack-tools](stack-tools.md) 步驟 6（拿掉擋名字；working tree 裡 `daemon.cpp`／`daemon.hpp`／`windows.cpp`／`test_cli.py`／`test_daemon.py`／README／N-28 都有未 commit 的改動）。**實作者等那輪 commit 進 main、`git pull` 之後再開工**，否則 `windows.cpp` `write_more`、`daemon.cpp` `finish`／`reconcile`、兩份 test、README 的「兩個手把兩扇窗」段會打架。
- [11-02 daemon-env](daemon-env/README.md)（控制口；使用者已定「daemon.json 明寫才切到控制口，沒寫照舊跟 stack 一起」，命名未定）：它的步驟 1～2 改 `aos-daemon-ctl`／`aos-eca-hub`（本題不碰）、步驟 3 改同一批 README、步驟 4 改 N-28 同一段、步驟 9（方案 C）寫新的 demo daemon.json。**建議本題先做**（檔名定了，daemon-env 的新 demo 直接用 `daemon_state.json`／`daemon_ctl.json`）；若 daemon-env 先落，本題步驟 3、6 多改它新加的那份 demo 與 README 段落。兩題 C++ 不重疊（daemon-env 只動 `child.cpp run_child`）。

| # | 改哪 | 做什麼 | 驗證 |
|---|---|---|---|
| 1 | `impls/aos-loop/src/engine/window.cpp`、`loop.cpp`、`config.cpp`、`engine.hpp`、`include/aos/loop.hpp` | `write_main`：組 doc（不含時間欄）跟 `last_main_` 比，不同才加 `recorded_at`＋`updated_at` 寫；`write_state` 回「寫了沒」給子類別；`beat` 拿掉 1 秒計時（或整個刪）；`config.cpp` 認選填 key `log`（同 `ctl`／`state` 的路徑規則與 `StackMissing`）；`main_loop` 每次 `run_once` 回來追加一行 `{started_at, counter_runs, code, signal, elapsed_ms}`（`Run` 若沒有 elapsed 就用 steady_clock 自己量）；檔頭註解同步 | `cd proto8/impls/aos-loop && cmake --build build && ctest --test-dir build`；`tests/test_cli.py` 改心跳那幾條（睡 1.5 秒 `updated_at` 不變；欄位順序表加 `updated_at`；新增 log 一次一行、沒 `log` key 不建檔、`StackMissing`） |
| 2 | `impls/aos-daemon/src/daemon/windows.cpp`、`daemon.cpp`、`daemon.hpp` | `write_more`：組 doc（表、ctl_seq、ctl_warning、letter_warning）跟 `last_more_` 比，不同才寫分檔＋主檔（`clean_parts` 只在真的寫了才跑）；`reconcile`／`finish` 的 `beat()` 改成單純「有變就寫」；檔頭註解「每寫一份 state 就跟著寫」改掉；README 範例 `"state": "daemon_state.json"`（方向題 1 選 (a) 連 `"ctl": "daemon_ctl.json"`） | `impls/aos-daemon` ctest；`tests/test_cli.py:405-493、869` 改寫（沒身體的 daemon 1.5 秒內 `daemon_state.json` 的 `updated_at` 與 mtime 不變；暫停中 loops_ctl seq 變→loops_state 照寫；起一批子項每起一個表多一列）；`test_demo.py` 抹掉欄位加 `updated_at`、demo 小格檔案表 |
| 3 | demo：`demo/daemon/daemon.json`、`daemon-2/daemon.json`、`daemon-3/daemon.json`、`llm-kernel/daemon.json`、`talk/team/daemon.json`、各 README；（方向題 4）有身體的加 `"log"` | `"state": "state.json"` → `"daemon_state.json"`（ctl 同理）；README 裡 `.stack/` 目錄樹同步 | `bash proto8/demo/run.sh`；`impls/aos-daemon/tests/test_demo.py` |
| 4 | `extras/ai_tools/bin/aos_ai_daemon.py:15、58`、`aos_ai_base.py:190`、`aos_ai_make.py` explain 文案、`extras/ai_tools/bin/aos-ai` 檔頭目錄樹、`extras/ai_tools/README.md`、`claude_skill/aos/concepts.md` | 生的 daemon.json 與讀的路徑改 `daemon_state.json`；status 顯示 `updated_at` | `proto8/tests/test_ai_tools.py` |
| 5 | `proto8/tests/test_daemon.py`、`test_aos_daemon_ctl.py`、`test_eca_hub.py`、`test_loop.py`、`test_talk.py` | daemon.json 的 `"state"` 名、欄位順序表加 `updated_at`；加一條「沒身體的 daemon 睡著時窗不動」 | proto8 pytest 全套（11-01 基準 803 OK／8 skip，[testing/01-proto8](../../../../wf/workflows/testing/01-proto8.md)） |
| 6 | 條文：`NORMS/05-基礎設施-窗.md` N-09（補一句「有變才寫」）、N-13（例子加 loop 的 `log.jsonl`）、N-17／N-32（11-02 改口：心跳拿掉、活著只看 pid＋啟動時間＋開機 id、窗有變才寫、`updated_at`）、N-33 不動；`NORMS/04` N-28（範例檔名、「心跳照 N-17／N-32 留」改讀、`log` key、一次一行）；`NORMS.md` 命名段與總表、附錄 1 條號表、附錄 2 各批出處加一列；`CONCEPTS/附錄1-名詞` 若列了 state 檔名 | 照本檔「規劃」寫，標「11-02 改口」＋連回本檔 | `/wf-lint` |
| 7 | code map：`wf/workflows/common/code-map/proto8/14-aos-daemon.md`（`write_more`、`finish` 那兩格）、`code-map/proto8/01-impls與舊lib.md`（aos-loop `window.cpp`／`loop.cpp`／`config.cpp` 那幾格加 `log`）、`code-map/proto8/02-tests*.md`（案數） | 跟程式對一遍 | — |
| 8 | 使用者親手試（`wf/WAIT_USER.md` 一條） | 在試驗場起 daemon，`watch -n1 ls -l --time-style=full-iso .stack/`：睡著時 `daemon_state.json`、`loops_state.json` 的 mtime 不動；`aos-daemon-ctl add` 一個子項後兩扇窗各動一次；`cat .stack/daemon_state.json | jq .updated_at`；有身體的 loop `tail -3 .stack/log.jsonl` | 使用者回報 |
| 9 | 收尾 | 本檔「決定」補使用者對衝突 1、方向題 1～4 的答案；[months/2026-11](../README.md) 那列由頂層加；日誌一行；repo 根 `cmake --build --preset default && ctest --preset default` 全綠（鐵律 1）；一個 commit（程式＋測試＋demo＋README＋條文＋code map 同一個） | — |

## 實作結論（11-02）

照兩個「決定」節做完（commit `278b7bd1` 程式＋測試＋demo＋code map；條文另一個 commit）。驗證：impls ctest 全過（aos-loop 72 組、aos-daemon 71＋demo）、repo 根 ctest 8/8、proto8 pytest 812 案（只剩已知的 `test_eca_turn.test_one_on_busy` error；`test_human` 負載下偶紅、單跑 22 案過）、`demo/run.sh` 0。

- **窗**：aos-loop 的 state、daemon 的 `daemon_state.json` 與 `loops_state.json` 拿掉 `kind`、`recorded_at`，最後一欄 `updated_at`；組好的內容（不含 `updated_at`、`counter_runs`，running⇄waiting 當同一個）跟上一份一樣就不寫；第一份、結束那份一定寫。心跳（`beat`）拿掉。
- **判活**：pid＋`started_at_ticks`＋`boot_id`；`aos-daemon-ctl ls` 另外對 /proc 判，daemon 不在跑時 stderr 一句「注意 daemon 沒在跑（pid N）；表是它最後寫的」，照樣列、退 0。
- **log**：`--enable-logs` 才印到 stdout。有身體：每跑完一次一行 `{started_at, counter_runs, code, signal, elapsed_ms}`；daemon：子項起來一行、結束一行 `{at, name, table, phase, pid, code, signal(, ws)}`。stdout 寫不了就停印、不退出（寫的那一下擋 SIGPIPE，不改處置、子行程不受影響）。
- **子項結束後不留名單**，本次執行不再起；再起的路：信箱同名再 add（或信）、ctl 模式讓名單有一圈沒有它。
- 信箱 key `loops_ctl_mailbox`、可與 `loops_ctl` 共存；loops_ctl 認整份 `execs`；execs 收內嵌單子；窗寫 null＝不開；`設定檔 -- 參數`。
- **試驗場**（WSL `~/code/playground`）：`daemons/main/daemon.json` 改 `daemon_ctl.json`／`daemon_state.json`／`loops_ctl_mailbox`。在拷貝 `~/.cache/aos-c8a7-f-tools/pg-daemon` 實跑：睡著 3 秒 `daemon_state.json`、`loops_state.json` mtime 都不動；`aos-daemon-ctl add --name nap /bin/sleep -- 2` 後 loops_state 動了、跑完從表上消失；同名再 add 照樣重跑；整段 daemon_state 不動；`--enable-logs` 的 stdout 有 clock／nap 起退共 6 行；不帶旗標 stdout 0 bytes；SIGINT 後 ls 印出「注意 daemon 沒在跑」；沒有殘留程序。使用者 11:38 起的那隻 daemon（pid 266490）13:22 已經結束（它最後的 state：`stopped`、code 130＝Ctrl-C），不是這輪碰的。

### 代定（可翻案）

1. 開關名 `--enable-logs`（跟 aos-mcp 一致；不帶值）。旗標要放在設定檔前，所以經 `aos-exec 資料夾` 起的 daemon 要開 log 得把旗標寫進 `_entry`（例 `["aos-daemon", "--enable-logs", "daemon.json"]`），或直接叫 aos-daemon。
2. `heartbeat()` 改名 `proc_fields()`（不帶時間欄）；`beat` 整個拿掉，daemon 表變了自己寫。
3. running⇄waiting 不算變動的結果：有身體的 loop 窗會停在第一份 running，直到 paused／stopped／done 或 ctl 有變。
4. ctl 模式「本次已結束」集合 `ended_`：只記自己結束（done）的；某圈算出的名單裡沒有它才放掉。被收掉（stopped）的不記。
5. 信箱與 loops_ctl 共存：信改「底」（起來時＝daemon.json＋只開信箱時 adopt 接回的名字）、loops_ctl 每圈疊在底上（有 `loops`／`execs` 就整份取代底的那張，再＋added－removed）；同一圈先套信再疊；疊完 loops 與 execs 同名＝那封是壞信。
6. 舊 key `loops_mailbox` 照「其他 key 忽略」：不開信箱、不報錯。
7. `設定檔 -- 參數`：設定檔後的 `--` 剝掉（aos-exec 則原樣交給入口，所以 `aos-exec 資料夾 -- 題` 接得起來）；單子 exec 的 argv 要直接是陣列，否則 CfgBad；沒有 exec 卻給參數＝ArgumentsBad。
8. execs 的單子只能寫成 `{"exec": 單子}`，daemon 寫進小格 `exec.json` 再 `aos-exec 小格/exec.json#/exec`（AOS_CF 指小格，不指回 daemon.json 或 ctl）。
9. aos-daemon-ctl：loop 型帶 `-- 參數`＝ArgumentsBad（「loop 型不收參數；參數寫進 loop.json 的 exec」）；判活注意句 `--json` 時也印（只在 stderr）。
10. aos-eca-hub：表上沒有、小格的子 loop `state.json` 是 done 且結束碼非 0＝「出錯停了」；aos_ai `start` 不在跑就先從 loops_added 拿掉、等回音、再加回。

### 帶給使用者的（條文工人列的，沒自己定）

- N-14 通則「窗內自述 `kind`」、N-16 通稱 `letter_warning`（agent queue 那支照舊）、C-54 R1 範例「state.json 每跑一次寫一次」、附錄 1 N-31 作廢說明「loop 不吐 stdout」、N-11「設定檔是唯一的位置參數」：這輪只加註，要不要改通則待使用者。
- 使用者通則 `aos-XXX [旗標] 目標 -- 參數` 跟現有指令的差異：aos-exec 目標後面原樣全收（不剝 `--`）；aos-fsm、aos-llm-kernel、aos-llm-send 沒有附加參數；aos-daemon-ctl `add` 照通則；這輪只改了 aos-loop／aos-daemon。
