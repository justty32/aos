# aos 現況（讀程式＋假腦實跑）：一支 agent 跑起來之後，人看得到什麼、停得在哪、gdb 的十來件事今天做不做得到

← [README](README.md)｜上一份：[01-對照表](01-對照表.md)｜續：[02-續-插入與Python](02-續-插入與Python.md)｜下一份：[03-別人怎麼做](03-別人怎麼做.md)

實跑在公司 WSL 的暫存樹 `~/.aos/scratch/aos-gdb-1119/tree/`（`cp -r templates/start-api`，假腦 `fake`），repo HEAD `2f7e94d5a` 的 `install.py` 成品；腳本與 log 同夾（`01-start.sh`～`11-tooladd-shutdown.sh`、`*.log`）。行程都用 `aos-daemon-ctl shutdown` 收掉了。

## 先講結論

1. **看**：今天就很夠。`aos-agent ctl state` 一句印十一類；stack 是普通檔，停掉後全留著（天生的 core dump）。
2. **停**：有三種，都實測過——`ctl pause`（這輪做完才停）、手打 `aos-exec fsm.json`（一次一格）、**一支會等的 `before_tool` hook**（真的停在「腦決定叫工具、工具還沒跑」那一刻，等人放行；實測停了 0.5 秒到 20 多秒都照常接續）。
3. **缺的是三件**：停住時**沒有任何地方標示「它停在斷點上」**（`ctl state` 照寫 running）；**沒有符號表**（停在哪一格、哪個工具，對不回原始碼哪一行）；**沒有可 import 的除錯 API**（全是命令列）。
4. **使用者說的「下一步看不到」是真的，但不是全看不到**：fsm 的格和轉移表事前寫死、看得到；腦要叫哪個工具、要叫幾次，事前看不到，只能在 `before_tool` 那一刻知道。見第二節。

## 一、各種 pu 的「一步」是什麼、事前看得到哪些

使用者的話：「cpu他未來要執行哪個指令，其實是看的到的……但是我們的aos中，pu多種多樣，好比aos loop/fsm，他就是持續執行單一指令，但是它具體會做啥我們不知道」。對照程式：

| pu（處理單元） | 它的「一條指令」 | 「一步」 | 事前看得到 | 只能當下或事後看 | 出處 |
|---|---|---|---|---|---|
| `aos-loop` | 一直重跑同一個 `exec`（agent-fsm 是 `fsm.json`） | 一拍：跑一次 body | 拍與拍之間隔 `interval_ms`；結束碼 0 續、10 停 | body 這拍做了什麼 | `cpp/aos-loop/`，`aos-loop --help` |
| `aos-fsm` | 依 `stage.txt` 跑那一格的 `exec`，依結束碼查 `next` | 一格 | **全部格名、每格跑什麼、每個結束碼走哪**（`fsm.json` 寫死） | 這次結束碼是幾（取決於腦） | `cpp/aos-fsm/`；`templates/agent-fsm/fsm.json` |
| agent-fsm 四格 | idle（收信）→ think（組請求）→ wait（問腦、收回答）→ act（照腦點名跑工具） | 一格 | 格的順序 | **wait 之後腦點了哪些工具、參數、要不要再想一輪** | `templates/agent-fsm/*.py` |
| 一次工具呼叫 | 一個工具夾，吃 JSON、吐 stdout | 一次呼叫 | 工具清單（`tools.json`＋疊層）——「可能叫誰」 | **實際叫誰、參數**：`before_tool` 那一刻才知道 | `act.py` 第 183 行 `fire("before_tool", …)` |
| 腦（llm kernel 後面的模型） | 一封問腦信 | 一次回答 | 送出去的整份請求（`think/request.json`） | 回答內容：**同一份請求每次可能不同** | `py/tools/aos/kernel_llm/` |
| eca 身（claude、codex 當腦） | 一回合：把排隊的信交給外部 CLI、等它答完 | 一回合 | 交出去的信 | CLI 內部的每一步。**它自己的工具（Bash、Edit…）aos 看不到**；`before_tool`／`after_tool` 只對經 `aos-mcp --hooks` 服務的 aos 工具有效（讀 `py/aos/apps/eca/__init__.py` 第 44～47 行、`main_turn.py` 第 67 行，未實測） | `py/aos/apps/eca/` |
| kernel 站 | 一輪：看信箱、判每封信 | 一封信 | 規則表（白名單、`max_running`、額度） | 判決結果 | `py/tools/aos/kernel/round.py` |

白話：**真 CPU 像照食譜做菜，下一步寫在下一行；aos 的 fsm 像一張流程圖，格子事前都畫好了，但「這格做完走哪條箭頭」要等廚師（腦）決定。** 所以「斷點下在哪」只能下在**邊界**上：某一格開始前、某個工具要跑前、某封信要進對話前、某封信到 kernel 時。這些邊界的**名字**事前都知道（格名、工具名、事件名），**會不會走到**事前不知道。

這也決定了 gdb 的幾個詞在 aos 要重新定義（細節在 [05](05-發想.md)）：
- **step**＝走到下一個邊界（下一格、下一次工具呼叫、下一封信），不是下一行。
- **backtrace**＝「怎麼走到這裡」：今天只有 `history.jsonl`（對話＋工具呼叫）和 `observed.jsonl`（每次想、每次工具）；**格的走法沒有記**（`stage.txt` 只留現在）。
- **斷點的位置**＝事件名＋條件（例：`before_tool` 且 `name == write`），不是行號。

## 二、看得到什麼（實測）

| 指令 | 看到什麼 | 實測 |
|---|---|---|
| `aos-daemon-ctl -d .stack ls`（`-j` 出 JSON） | 每個 proc：NAME PHASE PID CODE WS REASON；daemon 停了也能看，並註明「這是它留下的表」 | 01-start.log |
| `aos-agent ctl state -t ann [部分…\|all]` | 十一類：who、state、tools、llm、system、hooks、history、mailbox、subagents、resources（記憶體、CPU、行程數，讀 `/proc`）、time；daemon 停了也能看 | 01、09 |
| `aos-agent ctl ls -l` | 多 QUEUE、RESTARTS、COOLDOWN、LAST ERROR 四欄 | 01 |
| `aos-agent history ls` | 對話編號列表（user、assistant 的工具呼叫、tool 結果） | 09 |
| `aos-agent hook ls`、`tools ls`、`llm ls`、`system get`、`goal get` | 現在生效的設定（定義＋疊層） | 09、10 |
| `aos-agent open`、`peek` | **只有 eca 身有畫面**；agent-fsm 沒宣告 screen，回 `ScreenMissing` | 03b-peek.log |
| llm kernel 的 `ledger.jsonl` | 每次問腦一行：誰、哪個端點、等多久、用量（像 strace） | 03-files.log |

stack 夾裡的檔（`tree/.stack/procs/ann/`），用「記憶體／暫存器」的比喻分：

| 類比 | 檔 | 是什麼 |
|---|---|---|
| 暫存器（後寫的算、沒有歷史） | `stage.txt` | 現在在哪一格（程式計數器），內容就一個字，例 `act` |
| | `state.json` | loop 寫的 phase、paused、pid、`interval_ms`；關掉後 `phase: stopped, code: 143` |
| | `ctl.json`／`state_flux.json` | 控制窗（人寫 `{"cmd":"pause","seq":1}`）／回應窗（loop 回 ctl_seq 與時間） |
| | `think/brain_wait.json` | 正在等哪封腦信、在哪個 kernel |
| 記憶體（累積的狀態） | `history.jsonl` | 對話全文 |
| | `observed.jsonl` | 觀測流水：self、think（端點、用量、耗時）、tool |
| | `think/request.json` | 最後一次送給腦的整份請求（實測 53 KB，最大的檔） |
| | `queue/new/`、`letters.json` | 還沒取的信、在途與被丟的信 |
| | `hooks/<名>/event.json` | 每個 hook 最近一次收到的事件 |
| 疊層（這隻自己的設定） | `tools.json`、`hooks.json`、`system.txt`、`llm.json` | 只記這隻改過的；沒改就不存在 |
| 日誌 | `stderr.txt` | proc 與 hook 的 stderr；滿 1 MiB 由清道夫歸檔 |
| 失敗紀錄 | `cooldown.json` | 腦出錯才有（這次沒出錯，沒這檔） |

小出入：教學說關機會留 `stop_cause.json`，這次 `shutdown`（讓 proc 睡著）後**沒看到**；程式裡 `stop_cause.json` 由 daemon 寫（`cpp/aos-daemon/src/daemon/daemon.hpp`），可能只在 stop／rm 那條路寫，未追。

## 三、停得在哪（實測）

1. **一拍：`ctl pause`**（04.log）。下指令後約 0.16 秒 loop 回應；`state.json` 變 `paused`，行程沒死。停著時 `say` 照寄，信堆在 `queue/new/`，`listen` 4 秒逾時回 `AnswerMissing`；`resume` 後 5.7 秒內答完。`stage.txt` 停在上一輪最後那格。
2. **一格：手打 `aos-exec fsm.json`**（05.log）。自寫三格玩具 a→b→c，每打一次推一格，`stage.txt` 依結束碼照表走。真 ann 用獨立 stack 手推：idle 把信搬進 history、think 寫出 `request.json`、wait 卡在 `LlmKernelMissing`（沒設 `AOS_LLM_KERNEL`；重打同一格一直同錯、不會壞）。
3. **一次工具呼叫：會等的 `before_tool` hook**（09.log，本線隊長補做）。hook `bp.sh` 把事件存成檔，然後每 0.2 秒看一次有沒有「放行檔」，最多等 60 秒：
   - 寄出「breakpoint test」後 4 秒看：hook 已收到 `{"event":"before_tool","name":"peek_now_time","id":"call_fake_18","arguments":{}}`，`stage.txt` 是 `act`，history 最後一則是 `assistant -> peek_now_time({})`——**腦已決定、工具還沒跑，停在這裡**。
   - 停著時 `ctl state` 照寫 `running`、`ctl ls -l` 也沒有任何標記。**從外面看不出它停在斷點上**，只能看 hook 自己留的檔。
   - 停著時再 `say` 一句：信照收。放行第一個斷點後，第二封信的工具呼叫**又撞上同一個斷點**（`call_fake_22`），`listen` 等 20 秒逾時；放行第二個後才答完。
   - hook 回 `{"arguments": …}` 就能改參數（`py/aos/hook_run.py` 的 `_changes`），回 10 就擋掉（06.log 實測：腦收到 `[aos] hook: tool peek_now_time blocked by hook rec_bt.`）。
   - 逾時：hook 預設 60 秒；`timeout_ms: 0` 是不限時（`hook_run.py` 第 149 行）。逾時或出錯預設 `on_error: stop`，agent 會停下。
4. **一封給 kernel 的信**：kernel 的 `after_verdict` hook 可回 `hold`，但只有「包有 `held`」的站才收（`py/tools/aos/kernel/round.py` 第 62 行）；本線沒實測。

## 四、gdb 會做的十來件事，今天怎樣

| gdb 的事 | 今天做得到嗎 | 怎麼做 | 差在哪 |
|---|---|---|---|
| attach（接上在跑的） | 做得到（天生） | `aos-agent -t <名>`、`-d <stack>` | 不用附身：狀態本來是檔 |
| break（下斷點） | 半 | `aos-agent hook add --event before_tool --condition <工具名> <會等的腳本>`；**下一個事件就生效，不用重起**（實測） | 沒有現成「會等的 hook」；只能下在邊界（格、工具、信），不能下在行 |
| step（走一步） | 半 | 格：手打 `aos-exec fsm.json`（要先讓 loop 不跑）；工具：斷點放行到下一個斷點 | 兩種「一步」沒統一；手打要另設環境變數 |
| next（跨過一步） | 半 | 同上，放行後只在下一次同類事件停 | 沒有「跨過子 agent」 |
| continue | 做得到 | `ctl resume`；斷點 hook 放行 | — |
| print | 做得到 | `ctl state`、`history ls`、直接讀 stack 檔 | 散在十幾個檔，沒有一頁 |
| backtrace | 半 | `history.jsonl`、`observed.jsonl` | 沒有格的走法紀錄；跨 agent 的「誰叫誰」只有 `ctl state who` 的 parent |
| watch（值變就停） | 做不到 | — | aos 全輪詢、沒用 inotify；也沒有「某檔一變就停」的機制 |
| 改變數再繼續 | 做得到（分散） | 停著時改 `stage.txt`、`aos-agent tools/llm/system/history`、斷點回 `arguments`、`after_tool` 改結果 | 改了沒有記一筆（事後分不出是人改的） |
| core dump 事後看 | 做得到（天生） | 停掉後 stack 全留（07.log） | 只有「最後那一刻」；沒有每步快照 |
| 對到原始碼行 | 做不到 | — | 沒有 `_from` 或任何出處；庚的生成物也還沒有 |
| 重跑／倒帶 | 做不到 | — | 素材在（history、ledger、request.json），劇本腦（`llm_fake`＋`script`）能照固定劇本答，但沒人把兩者接起來 |
