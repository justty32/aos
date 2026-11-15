# daemon 與行程

← [README](README.md)

aos-daemon、aos-loop、daemon 表、行程限額（--limits）的意見。

## after_stop 事件分不出是 stop、sleep 還是 rm

- 主題：daemon 與行程
- 哪裡：aos-loop 的 on_stop → `lib/agent/hook_fire` 發的 `after_stop` 事件（`impls/aos-loop/src/engine/loop.cpp` 的 end()、`lib/agent/hook_fire/_entry`）。
- 現象：事件只多 `code`、`signal` 兩欄。`ctl rm`（running）和 `ctl sleep` 都是 daemon 送 SIGTERM，hook 看到的都是 143／15；`ctl stop` 是 0／null，跑滿 max 或 body 退 10 也是 0／null。hook 無法依「為什麼停」做不同的事，例如 rm 想立刻收畫面、sleep 想延後收，只能統一延後，或另讀 daemon 表（走 kernel 時表可能被刪減、daemon 可能不在）。
- 建議：daemon 送 SIGTERM 前把原因寫進 child ctl 檔（例 `{"reason": "sleep"}`），loop 讀到後設 `AOS_LOOP_REASON`，hook_fire 轉成事件的 `reason` 欄（stop、sleep、rm、max、body_exit、signal）。沒有原因時給 null，相容舊 hook。
- 痛的程度：拖慢（設計 hook 要繞路）
- 提出者與日期：ok-kf 2026-11-14
- 出處：wf/temp/ok-kf/aos-advice/after-stop-no-reason.md；wf/temp/ok-kf/cprime/final.md；kf-1114 暫存樹 kf-check/G-cprime-facts.md 第 1 節
- 狀態：已解（75a6ca81e，11-15 Claude 線 claude-b7 接手 ok-limits 交件；設計 ok-devt）。B7：daemon 送 SIGTERM 前寫小格的 stop_cause.json，after_stop 帶 `cause`（stop、sleep、remove、shutdown、stuck、signal、max、body_exit、error；定稿 proto8/thinking/2026-11/14/ok-devt-1114/05-定稿.md 2.3），值表在 aos-loop docs/01。aos-loop、aos-daemon 是 C++，活樹要等換樹編新的 bin 才有。

## 子 agent 不知道是誰生了它

- 主題：daemon 與行程
- 哪裡：daemon 表的列、`aos-agent ctl add`、`lib/agent/subagent`（帳只記在 mom 那邊）。
- 現象：AK17 要讓 worker 額度被拒時通知 lead，查過後發現子 agent 的 stack、daemon 表、環境變數都沒有「mom 是誰」。只能讓 `subagent add` 塞一個 `AOS_NOTIFY_BOX=<mom stack>/mailbox`；用 `agents_ctl add`、`aos-agent ctl add` 直接生的就沒有。ok-skyrim 查證時也得到同樣結論（隊員身上沒記「誰掛的我」，見 ad7983618）。
- 現象（續）：`self_state {"parts":["who"]}`（`cmd/aos-agent/aos_agent/ctl/who.py` 約 51 行）只回 name、stack、ws、def、daemon，沒有 parent。`subagent add` 補的 `AOS_NOTIFY_BOX`（`lib/agent/subagent/_entry` 182 行）agent 自己看不到，也可以被覆寫成空字串。新起的 agent 想知道「做完寄給誰」，只能靠任務書或找原信的 reply_to。
- 建議：daemon 表的列記 `parent`（是誰的 stack 發出 add）；或 `ctl add` 一律給子行程 `AOS_PARENT_STACK`。hook、工具都靠它找上面的人，不用每種用途各發明一個變數。`who` 加一欄 `notify_box`（或 `parent`），照實顯示，並註明不是身分證明。
- 痛的程度：拖慢
- 提出者與日期：ok-astra 2026-11-14；ok-onboard 2026-11-14（who 那段）
- 出處：wf/temp/ok-astra/aos-advice/child-knows-no-parent.md；wf/temp/ok-onboard/aos-advice/who-no-parent.md、proto8/thinking/2026-11/14/onboard-1114/01-備料.md §3；astra-1114 暫存樹 ak17/facts.md Q4；commit 2368ee3af（subagent/_entry 預設 AOS_NOTIFY_BOX）
- 提出者與日期（第十三批併入）：ok-devt 2026-11-14（第 1 期只補得到一半）
- 出處（第十三批併入）：wf/temp/ok-devt/wrapup-1114/建議.md「『誰掛了我』第 1 期只補得到一半，表上應該有這一欄」（引 `proto8/thinking/2026-11/14/ok-devt-1114/05-定稿.md` 第五節、`06-第2期施工清單.md`、commit 83fd2fd39、bcaf76823）
- 第十三批補：第 1 期能做的只有「把 parent 寫進啟動單子的 envs」，而帶 envs 的 add 走的是另一條啟動路（見本檔「帶 --envs 的 add 換了掛法」）。所以不帶 envs 的 add（頂層掛各線的方式）第 1 期查不到 parent。ok-devt 的建議：照 06-第2期施工清單，把 `parent`、`notify_box` 做成列上的兩欄，由 daemon 設環境變數。
- 狀態：未處理（部分已解）。設計 ok-devt；定稿 05 的 1.3／1.4 與第五節：who 加 parent、notify_box（讀表上那列、再讀啟動單子的 envs）；本來就帶 envs 的 add 補 AOS_PARENT_STACK；第 2 期兩格放到列上。第十三批改：第 1 期的 add 那部分已進 main（bcaf76823：帶 envs 的 add 登記 parent 與 notify_box，定稿 1.2、1.7 與修訂 1）；定稿其餘各項進了沒有，整理時沒逐項對；第 2 期（兩格放到列上）還沒施工。11-15 改：ok-limits 收樹，狀態由「已排入」改「未處理（部分已解）」——帶 envs 的 add（subagent、fork）查得到 parent；不帶 envs 的 add 要等第 2 期，第 2 期沒有線接。

## --limits 的 cpu_s 按程序計，擋不住整隻 agent 的總 CPU

- 主題：daemon 與行程
- 哪裡：`subagent add`／`ctl add` 的 `limits.cpu_s`（經 s6-softlimit 設 RLIMIT_CPU）。
- 現象：給 sol 設 `cpu_s: 2`，照常答題。aos-loop 本身累計只 0.19 秒，每格工作都是新子程序，RLIMIT_CPU 各自重算。鍵名看起來像「整隻最多 2 秒」，實際幾乎擋不住。
- 建議：文件寫明 cpu_s 是「每個程序」上限；要管總量就提供 cgroup 版的鍵（例 cpu_max 對應 cpu.max，或總 CPU 秒數），可併入 kernel-limits-1114 的 cgroup 計劃。
- 痛的程度：小不便（沒人靠它，但鍵名誤導）
- 提出者與日期：ok-pilot 2026-11-14
- 出處：wf/temp/ok-pilot/aos-advice/limits的cpu_s按程序計擋不住總量.md；wf/temp/ok-pilot/notes.md 第四輪
- 狀態：未處理（文件部分已解）。f856af0eb 在 wf 07 寫明「cpu_s 只按單一程序計、總量要 cgroup」；50e7a35bc 在 subagent、agents_ctl 工具說明與知識庫 aos/agents/subagent 寫明 mem_mb、cpu_s、file_mb、files 按程序計，mem_total_mb、procs_total 管整隻（B5 1082418f0），沒有總 CPU 的鍵，同 commit 讓 ctl add --limits 也認這兩個 cgroup 鍵。還沒做：總 CPU 的 cgroup 鍵（cpu.max）。活樹的知識庫、lib 複本要等換樹。

## limits 開檔數的鍵叫 files，不叫 nofile

- 主題：daemon 與行程
- 哪裡：`--limits` 的鍵名。
- 現象：`ArgumentsBad unknown key nofile in --limits (keys: mem_mb, cpu_s, procs, file_mb, files, user)`。錯誤本身很清楚。
- 建議：把 `nofile` 收為 `files` 的別名，或在 subagent 工具說明的 limits 例子裡用一次 files。
- 痛的程度：小不便
- 提出者與日期：ok-pilot 2026-11-14
- 出處：wf/temp/ok-pilot/aos-advice/小坑三則.md 第 3 則
- 狀態：已解（50e7a35bc：工具說明與知識庫的 limits 例子改用 files；nofile 照舊 ArgumentsBad、不收別名，ok-devt 同意）。活樹的複本要等換樹。

## daemon 靠 /proc/<pid>/environ 認自己的行程，一換 uid 就認錯

- 主題：daemon 與行程
- 哪裡：aos-daemon 的 adopt（`impls/aos-daemon/src/daemon/adopt.cpp` 的 same_tree，約 54 行）、sweeper（`py/aos_sweep_proc.py` 約 130 行）。
- 現象：兩支都讀 `/proc/<pid>/environ` 的 AOS_STACK／AOS_DAEMON 認自己的行程。adopt 讀不到就回 true（當成自己的）；sweeper 讀不到就不管它。11-14 實測：使用者對 subuid（sub:5＝100004）的行程 kill -0、SIGTERM 都可以，`/proc/<pid>/environ` 卻是 Permission denied。所以一開始換 uid，adopt 會把讀不到的全部收養，sweeper 一隻都清不到。今天全部同一個 uid，還沒發作。
- 建議：adopt 改用 pid＋`/proc/<pid>/stat` 第 22 欄（啟動時間）＋`/proc/<pid>/status` 的 Uid 比對；sweeper 改看 `/proc/<pid>/status` 的 Uid／Gid（人人可讀、`env -i` 洗不掉）。停一隻專屬 uid 的 agent 時可加一步 `aos-asuser sub:N -- kill -9 -1`，連 setsid 跑掉的孫行程一起收。
- 痛的程度：今天小不便（沒發作）；換 uid 那天擋路（任何換 uid 都要先改這個）
- 提出者與日期：ok-sec 2026-11-14
- 出處：wf/temp/ok-sec/aos-advice/daemon認人別靠environ.md；proto8/thinking/2026-11/14/sec-1114/03-計劃.md E1、05-採納表.md A6、B4；實測腳本 ~/code/sec-1114/e12.sh
- 狀態：已排入（ok-sec）；Python 部分 f4ae9fcf0：sweeper 讀不到 environ 時改看 /proc/<pid>/status 的 Uid 對 <daemon stack>/uids.json，沒帳本照舊 left alone（帳本由第 2 期寫）。adopt C++ 在 ~/code/sec-1114/p1 34fb455：same_tree 讀不到時用 status Uid 對表上 limits.user；等 B7 之後交 ok-kf 換樹。換 uid 那天之前兩半都要上。

## 帶 --envs 的 add 換了掛法：表上 exec 變 null、set-def 拒收、as_written 與 --path-json 指示詞掉了

- 主題：daemon 與行程（也碰到指令與工具的 `aos-agent ctl add`／`set-def`）
- 哪裡：`proto8/py/daemon_ctl/entry.py` 的 `add_letter`（約 292～303 行：帶 envs 或 `--dotenv-override` 時把 exec 包成 `{"argv": ["aos-exec", "--", 目標], "envs": …}`）、`written_under`（約 215 行，只認字串和陣列）、`as_written`（約 329～339 行，只記字串目標）；aos-daemon 把包起來的列記成指到小格檔的指標；`proto8/cmd/aos-agent/aos_agent/ctl/set_def.py` 第 51 行。
- 現象：ok-limits 11-14 在暫存樹起隔離 daemon 實測 exec 型、loop 型、`--path-json` 三種掛法，各掛一隻帶 envs、一隻不帶。
  - 兩邊一樣的：body 的 cwd、AOS_* 變數（只多了 envs 給的那幾個）、loop 各鍵、`def` 欄、`ws`，stop／start 之後 envs 照樣生效。
  - 不一樣的有五處：
    1. 表上那列的 `exec` 欄從目標（如 `../def-exec`）變成 `null`；`launch.exec` 變成指到小格的指標（exec 型 `procs/<名>/exec.json#/exec`，loop 型 `procs/<名>/loop.json#/_entry`），envs 只寫在小格檔裡。
    2. 所以 `ctl set-def` 拒收這種列（「was attached with --envs or extra arguments … rm, then ctl add」）。`subagent add` 一律補 `AOS_NOTIFY_BOX`（`lib/agent/subagent/_entry` 182 行），**今天所有 subagent 掛的子都不能 set-def**，只能 rm 再 add。
    3. 使用者打成絕對路徑的目標，帶 envs 時不記進 `as_written.exec`（不帶時有記）。
    4. `--path-json '{"$env": "PROBE_HOME", "$path": "/def-exec"}'`：不帶 envs 時 `as_written.exec` 記使用者的指示詞、每次起都重解；帶 envs 時小格檔裡的目標變成 `{"$env": "AOS_DAEMON", "$path": "../def-exec"}`，使用者的指示詞在 exec 那層不見了（`def` 欄照留）。兩台機器各設各的變數時，語意不一樣。
    5. 多一層 aos-exec 行程：exec 型每起一次多一層，loop 型每一輪多一層。行為沒差，只是成本。
  - 實測輸出摘錄（`probe2.out`，路徑已換成 `<R>`）：
    ```
    row.launch: {"exec": ["../def-exec"]}                      # 不帶 envs
    row.exec: ../def-exec phase: running
    row.launch: {"exec": ["procs/ex1/exec.json#/exec"]}        # 帶 envs
    row.exec: None phase: running
    row.as_written/def: {'ws': '<R>/ws-ex1', 'def': '<R>/def-exec'} ../def-exec   # 少了 exec
    exec.json {"exec": {"argv": ["aos-exec", "--", {"$env": "AOS_DAEMON", "$path": "../def-exec"}], ...}}   # --path-json 帶 envs
    ```
- 建議：
  1. `written_under` 要認包起來的 `argv` 裡的目標，`as_written.exec` 也照記（修現象 3、4）。
  2. set-def 遇到包起來的列，從小格檔讀回原本的 envs（和 `--dotenv-override`）再包一次，不要直接拒收（修現象 2）。
  3. 長期：envs 改記在列上、由 daemon 起行程時設，不包那一層，表上 `exec` 欄就不會變 null。這跟 ok-devt-1114 定稿第 2 期（parent、notify_box 放到列上，見本檔「子 agent 不知道是誰生了它」）是同一條路，可以一起做。
- 痛的程度：拖慢（subagent 掛的子不能 set-def；多機器用 `--path-json` 又帶 envs 時，目標悄悄變了）
- 提出者與日期：ok-limits 2026-11-14
- 出處：wf/temp/ok-limits/aos-advice/帶envs的add換了掛法.md；ok-devt-1114「第 1 期 add 自動填 parent」查核 A（ok-devt 定稿 05 第五節「修訂 1」，83fd2fd39）；ok-limits 寄 ok-devt 的信 01794636733207528989；實測 `~/code/limits-1114/probe-envs-1414/probe2.py`、`probe2.out`（只印 AOS_* 和 envs 的變數名）
- 狀態：未處理（ok-devt 裁定不在 parent 這件裡修，第 1 期不改任何 add 的掛法。整理時查（只讀，HEAD b892fbd83）：`set_def.py` 第 51 行仍拒收 exec 不是字串的列，entry.py 包 aos-exec 那段沒改）

## 部長看不到自己帶的線是忙、閒、還是停了，沒有被允許的唯讀查法

- 主題：daemon 與行程（也碰到指令與工具的 `agents_ctl`）
- 哪裡：分層之後的部長（掛在頂層 kernel 底下的 eca）；工具箱裡的 `agents_ctl ls`／`state`、`self_state`；硬規則第 1 條（不對活樹的 daemon 與 agent 下任何指令，連唯讀的 `ctl ls` 也不行）。
- 現象：
  - 線沒回信時，部長分不出它是忙、在長回合、額度用完還是停了，只能寄信問本人或請頂層代查。head-tools 為 ok-misc 問了頂層三次；head-front 的 ok-view 五十分鐘沒回信（13:23～14:49），頂層查到它卡在等待迴圈；head-core 的 ok-kf 積了 7 封信沒回，分不出是忙還是掛了。
  - 工具在手邊卻不能用：`agents_ctl ls`／`state` 的工具說明寫「Changes nothing」，head-core 開工時用了一次 ls、一次 state 才意識到不該用，有踩線的風險。
- 建議（擇一）：
  1. 給部長一支範圍限定、明確允許的唯讀查詢：只看自己帶的那幾隻的 phase／state、上次活動時刻、信箱未讀數（或全景頁的 API），並寫進部長共通規矩。
  2. 由頂層定時把這張表寄給部長。
  3. 不給的話，把「部長不准用 agents_ctl」寫進任務書，並從部長定義的工具組拿掉。
- 痛的程度：拖慢（head-front 原稿寫「痛」，head-core 寫「小不便，但有踩線的風險」）
- 提出者與日期：head-core 2026-11-14；head-front 2026-11-14；head-tools 2026-11-14
- 出處：wf/temp/head-core/wrapup-1114/建議.md「部長沒有唯讀看活樹的正規管道」（引 `wf/temp/head-core/notes.md` 13:22、13:30，頂層 13:37 回「以後要看活樹狀態，寄信問我」）；wf/temp/head-front/wrapup-1114/建議.md 第 4 則（引 `wf/temp/head-front/notes.md`）；wf/temp/head-tools/wrapup-1114/建議.md「部長看不到自己的線現在是忙、閒、還是停著」（引寄 repo-aos 的彙整信 01794634619803738998.3275581.2320545 等）
- 狀態：未處理。規矩那一半（部長任務書怎麼寫）是 wf 的派工文件，由頂層定；這裡記的是 aos 缺一支範圍限定的唯讀查詢。
- 相關：[kernel與額度](kernel與額度.md)「state 和 ctl ls 看不出隊員是在排腦的隊、額度被拒，還是卡住」（同樣是外面看不出一隻 agent 現在的狀況）。

## daemon 替 proc fork 的那一層命令列跟主 daemon 一樣，pgrep 分不出來

- 主題：daemon 與行程
- 哪裡：aos-daemon fork 出來、還沒 exec 的那一層；`pgrep -u "$USER" -af aos-daemon`（aos-teams/06 第 9 條開工、收尾核對用的指令）。
- 現象：fork 層的命令列跟主 daemon 一模一樣，隨活樹 proc 起落。ok-board-fable-1、-2 收尾核對時都報「少了 aos-daemon」並停手，每次假警報都要人判斷。
- 建議：fork 層改 argv0（例如 `aos-daemon[child]`）；或核對改看「主 daemon pid（ppid 不是 aos-daemon 的那行）＋ repo-aos stack 清單」。後一個改的是 wf 的 06，由頂層定。
- 痛的程度：拖慢
- 提出者與日期：ok-board 2026-11-14
- 出處：wf/temp/ok-board/wrapup-1114/建議.md 第 1 則（引 `wf/temp/ok-board/ok-board-fable-{1,2}/report.md`、`proto8/thinking/2026-11/14/board-1114/` 07 §四）
- 狀態：未處理。整理時查：`proto8/impls/aos-daemon/src` 裡沒有改行程名的程式（沒有 prctl、setproctitle 字樣）；「fork 層命令列跟主 daemon 一樣」是提出者的觀察，整理時沒有對活樹查（不准碰）。

## eca 一輪寫出 result 之後 CLI 行程不退出，aos 不知道、也沒有逾時

- 主題：daemon 與行程（eca 身）
- 哪裡：aos-eca-turn 起 `claude -p` 那一段；aos-loop 判斷「這一輪結束了沒」；`ctl state`、`ctl ls`。
- 現象：ok-pilot 15:35 那輪已寫出 result（success），`claude -p` 卻因為還有背景工作沒退出，掛了約 1 小時 33 分。aos 這邊把它當成一輪還在跑：信進不來（兩封躺在 `mailbox/new/`）、`ctl` 看起來是 running，只能由人去看 live.jsonl 才知道 result 早就寫了。最後 kill 那支 claude，aos-loop 把這輪算失敗，整隻 agent 停掉（state done、code 1），連已經寫出的 result 也沒被當成成功收下。
- 建議：
  1. aos-eca-turn 看到 result 之後給 CLI 一段寬限時間，過了還不退出就自己收掉它，這一輪照 result 算成功。
  2. 至少在 `ctl state`／`ls --long` 顯示「result 已寫、行程還沒退出、已經多久」。
  3. 被外面 kill 時若 result 已經寫出，不要把整隻 agent 停掉。
- 痛的程度：擋路（一條線整個停了，收尾要別人代做）
- 提出者與日期：ok-pilot 2026-11-14（head-tools 代寫；ok-pilot 已停，沒有它本人確認）
- 出處：wf/temp/ok-pilot/wrapup-1114/建議.md 第 1 則（引頂層信 01794643439561828052.2973611.3202521、`~/code/ok-pilot-rm-1114/suite/mine-d7f/` 的 log 時刻）。經過是 head-tools 從信與留下的檔整理的，提出者未逐一核；整理時沒讀 aos-eca-turn 核「看到 result 之後怎麼等」。
- 狀態：未處理
- 相關：[知識庫與文件](知識庫與文件.md)「eca 派的 Claude 子 agent」（背景工作跟回合結束的另一面：那條是回合結束把背景子 agent 收掉，這條是背景工作讓 CLI 不退出）；[信件與溝通](信件與溝通.md)「agent 在長回合裡收不到新信通知」。
