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
- 狀態：未處理

## 子 agent 不知道是誰生了它

- 主題：daemon 與行程
- 哪裡：daemon 表的列、`aos-agent ctl add`、`lib/agent/subagent`（帳只記在 mom 那邊）。
- 現象：AK17 要讓 worker 額度被拒時通知 lead，查過後發現子 agent 的 stack、daemon 表、環境變數都沒有「mom 是誰」。只能讓 `subagent add` 塞一個 `AOS_NOTIFY_BOX=<mom stack>/mailbox`；用 `agents_ctl add`、`aos-agent ctl add` 直接生的就沒有。ok-skyrim 查證時也得到同樣結論（隊員身上沒記「誰掛的我」，見 ad7983618）。
- 現象（續）：`self_state {"parts":["who"]}`（`cmd/aos-agent/aos_agent/ctl/who.py` 約 51 行）只回 name、stack、ws、def、daemon，沒有 parent。`subagent add` 補的 `AOS_NOTIFY_BOX`（`lib/agent/subagent/_entry` 182 行）agent 自己看不到，也可以被覆寫成空字串。新起的 agent 想知道「做完寄給誰」，只能靠任務書或找原信的 reply_to。
- 建議：daemon 表的列記 `parent`（是誰的 stack 發出 add）；或 `ctl add` 一律給子行程 `AOS_PARENT_STACK`。hook、工具都靠它找上面的人，不用每種用途各發明一個變數。`who` 加一欄 `notify_box`（或 `parent`），照實顯示，並註明不是身分證明。
- 痛的程度：拖慢
- 提出者與日期：ok-astra 2026-11-14；ok-onboard 2026-11-14（who 那段）
- 出處：wf/temp/ok-astra/aos-advice/child-knows-no-parent.md；wf/temp/ok-onboard/aos-advice/who-no-parent.md、proto8/thinking/2026-11/14/onboard-1114/01-備料.md §3；astra-1114 暫存樹 ak17/facts.md Q4；commit 2368ee3af（subagent/_entry 預設 AOS_NOTIFY_BOX）
- 狀態：未處理（目前只有 subagent 路徑的 AOS_NOTIFY_BOX；who 仍沒有 parent／notify_box 欄）

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
- 狀態：未處理（adopt.cpp 仍是「讀不到＝照舊」回 true，aos_sweep_proc.py 仍讀 environ；sec-1114 採納表已列，未施工）

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
