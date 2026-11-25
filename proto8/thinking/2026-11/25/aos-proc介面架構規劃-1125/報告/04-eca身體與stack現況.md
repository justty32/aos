eca（拿 Claude Code 當身體的 agent）今天的 stack 逐檔盤點、一輪怎麼跑、照新模型分類，並拿 11-25 換帳號事故當案例：eca 不是一個行程，是「aos 的 loop」加「外面的 Claude Code」；stack 幾乎全是該留的，對話本體卻在 aos 手外的帳號資料夾裡。

# eca 的身體與 stack 現況（Claude Code 當身體）

← [架構規劃入口](../README.md)

第 04 隻子 agent（fable）寫的。全程只讀，實驗只在 `~/.aos/scratch/aos-proc-arch-1125/04/`。三種話的標法：使用者說的引原話並註出處；查到的附 `檔名:行號` 或指令與輸出；我推的標「推論」。路徑沒寫開頭的從 `proto8/` 算；`agentlib/`＝`proto8/py/aos/agentlib/`，`apps/eca/`＝`proto8/py/aos/apps/eca/`。「小格」＝`<stack>/claude/`，aos 替一段 CLI 對話開的那個夾。

## 1. 結論

1. **eca 不是一個行程。** 它是「aos 的 loop」加「外面的 Claude Code」。Claude 有兩種活法：沒開畫面時一輪起一隻 `claude -p`；開了畫面就是 tmux 裡一隻長命的 `claude`。畫面那棵不是 daemon 的子孫，loop 停了它還活著。所以「`/proc/<PID>` 就是它的 stack」對 eca 只能指 loop 那個 PID。
2. **今天的 stack 照新說法幾乎全是 persist。** 真正「活的身體」那一小撮，大致就是 `stack.gitignore` 擋掉的那些（11-06 起已經用「進不進 image」分過一次），NORMS 附錄 4 也有「持久／暫時」欄。不用從零分。
3. **對話本體不在 aos 手上**：在 Claude Code 的帳號資料夾，鑰匙是「機器＋帳號夾＋工作區路徑＋對話 id」四樣。aos 這邊只有指標和一份縮水抄本。它是第三類：外面的 persist。
4. **11-25 事故我獨立對過**：換帳號夾 → aos 認不出是同一處的對話 → 開新對話（設計如此）。新對話是人先開口的，aos 的前情一個字都沒送進去；aos 抄本裡的摘要還是前一次壓縮的（慢一拍）。接回來靠的是 agent 自己寫在工作區的筆記，不是 aos 留的東西。
5. **ctl**：今天 stop＝這輪答完才停、pause＝不餵下一則、sleep＝直接送訊號。一輪不限時，loop 等這一輪時不讀 ctl，所以連「收到」都要等這輪結束。畫面裡的 Claude 不歸這三個動作管：pause 碰不到它，stop 與 sleep 只是排一張 600 秒後關畫面的單。
6. **status 與 token**：不改程式就湊得出二十多行 status（實測）。`context_use.py` 給的是「context 現在多滿」，不是「累計用了多少」；累計值只有 `-p` 那條路的輸出裡有。eca 的腦不經 llm kernel，所以它自己報的是唯一一份帳。
7. **衝擊面**：讀寫小格的 165 處裡絕大多數經過 `Cell` 一個類別，好改。難的是寫死在長命行程裡的路徑（畫面裡的 Claude 與它帶的 aos-mcp），和用小格路徑算出來的 socket 名。
8. **108 bytes**：今天是把 socket 放到 `/run/user/<uid>/` 底下、用雜湊當檔名繞開。`/proc/<PID>/cwd` 短路徑對 tmux 也行得通（實測），但畫面的 socket 不能掛在 loop 的 PID 底下。

## 2. 查到的事實

### 2.1 一隻 eca 有哪些行程

活樹 `eca-aos`，11-25 12:0x 用 `ps -eo pid,ppid,cmd` 與 `readlink /proc/<PID>/cwd` 看的：

| 行程 | 誰起的 | 活多久 | 站在哪個夾 |
|---|---|---|---|
| `aos-loop loop.json`（PID 2243） | repo-aos 的 daemon（2239） | 起樹到 stop／sleep | **定義夾** `templates/agents/eca-claude` |
| `aos-eca-turn`（Python） | aos-loop；閒著時大約每秒起三次（`loop.json` 的 `interval_ms: 300`） | 一輪 | 承襲 loop 的（推論，沒抓到現行的） |
| `claude -p …` | aos-eca-turn | 一輪；自成一個行程群組 | 工作區（`agentlib/cli_print.py:124`） |
| `tmux … new-session`（1584127） | 開畫面那個人的殼（`aos-agent open`） | 父行程是 WSL 的 `/init`（3117），不在 aos 的行程樹裡；loop、daemon 停了都還在（清道夫的說明也這樣寫，`py/aos/apps/sweeper/README.md:35`） | `<定義>/screen` |
| `claude …`（互動，1584129） | 那個 tmux | 同上 | 工作區 |
| `aos-mcp`（1584631） | 那隻 claude | 跟著 claude | 工作區 |

- **沒有任何一隻站在 stack 裡。** Claude 一定得站在工作區（它用 cwd 認專案、找 `CLAUDE.md` 與 `.claude/`，對話檔的夾名也是從 cwd 算的）。
- **小格是好幾棵行程樹共用的夾**，寫它的有六種：loop 這棵（aos-eca-turn）；畫面那棵（Claude Code 叫起來的 hook、`compact_hook`、aos-mcp 與工具）；開畫面的人的殼（`aos-eca-screen`、`aos-agent tools／llm／history／goal`）；tmux 排程的到期關畫面；daemon（`ctl.json`、`stop_cause.json`、`stderr.txt`）；別的 agent（`queue/`、`mailbox/`）。它們靠小格裡的 `lock`（flock）與「先寫暫存再改名」互相不踩。
- loop 與畫面的環境變數是兩個來源。loop 的是一路繼承下來的：根 daemon 表上 repo-aos 那一列的 `exec.json` 帶 `CLAUDE_CONFIG_DIR`，repo-aos 這台 daemon 與它底下每隻 loop 就都是 `~/.claude-alt`（`/proc/<PID>/environ` 對過）。畫面的來自開畫面那個殼，aos 只替它補 `AOS_*` 那幾個（`agentlib/cli_mcp.py:182-227`），不補帳號夾（`templates/agents/eca-claude-alt/README.md:31`）。

### 2.2 一輪怎麼跑、兩條路怎麼切

1. aos-loop 每一輪結束後隔 300 毫秒，再起一次 `aos-eca-turn --on-empty idle --on-busy yield <定義夾>`（`templates/agents/eca-claude/loop.json`）。
2. aos-eca-turn（`apps/eca/turn.py:19-92`）：跑到點的 on_clock hook → 冷卻中就退 → 把 `queue/new` 的信全部認領到 `queue/cur` → 一封一封讀、過 `before_queue` hook → 看 `history.jsonl` 有沒有被人改過。
3. 交給 `cli_ask.ask`（`agentlib/cli_ask.py:143-189`）：先拿小格的鎖，然後**當場決定走哪條路**，判準是 `cell.alive()`：畫面的 socket 檔在，而且 `tmux has-session` 有回（`agentlib/cli_cell.py:131-137`）。
   - **畫面沒開 → `claude -p`**（`agentlib/cli_print.py:216-279`）。先認這段對話是不是這裡的（`session_here`，`cli_cell.py:251-270`）：`.session_home` 記的機器、帳號夾、工作區路徑都一樣，而且對話檔找得到。是＝`claude -p --output-format stream-json --verbose … --resume <id>`；不是或沒有＝自己產一個 id 用 `--session-id`，題目前面接一段從 `history.jsonl` 整理的前情（上限 48000 bytes，`apps/eca/reseed.py:47-87`）。題目從 stdin 進，輸出一行一個事件、邊收邊接進 `live.jsonl`。**讀到第一個 `result` 行就算答完**；3 秒內 claude 沒自己退，就把它整個行程群組連子孫收掉（先 TERM、2 秒後 KILL；`cli_print.py:65-66,91-113,116-182`，11-25 commit `6f8fd99a6`，已裝進 `lib/`）。
   - **畫面開著 → 往畫面送**（`cli_ask.py:37-133`）。小格的 `a2a.json` 記著 Claude Code 自己的收件 socket（`/run/user/<uid>/cc-socks/<claude 的 PID>.sock`）就往裡寫：一封信一行 JSON、包一個署名信封（使用者 11-13「馬上送，eca他會自己處理」，`apps/eca/main_turn.py:31`）。這條 socket **不回話**（`cli_a2a.py:9`），收到沒有要靠畫面 hook 在 `a2a_acks.jsonl` 記的回執；回答從 `turns.jsonl` 拿（畫面 hook 每講完一輪接一行）。沒記到 socket、連不上、閒著 30 秒沒回執＝退回舊路，用 `tmux load-buffer`、`paste-buffer`、`send-keys Enter` 把字貼進畫面。
4. **交出去那一刻就收信**：信接進 `history.jsonl`、從 queue 刪掉（`apps/eca/handoff.py:26-46`；使用者 11-03「對於eca來說，他收到信後，丟給claude之類的，然後這封信就算是完成了」，`apps/eca/main_turn.py:36`）。之後 CLI 掛了，那批信不重答。
5. 回答回來接成一則 assistant 進 `history.jsonl`，更新 `letters.json`、`.history_sum`，清冷卻（`turn.py:109-122`）。

兩條路怎麼切：

- 每一輪自己看畫面開沒開，沒有開關要設。
- 開畫面（`aos-agent open` → `aos-exec … <定義>/screen open` → `aos-eca-screen` → `agentlib/cli_screen.py:106-123`）先等小格的鎖，也就是等正在跑的那輪 `claude -p` 答完，再在 tmux 裡起 `claude … --resume <同一個 id>`（`cli_screen.py:49-85`）。兩條路接的是**同一段對話**。
- 關畫面（`aos-agent close`、畫面裡 `/exit`、停下 600 秒後自動關）之後，下一輪回到 `-p`。
- 畫面的 tmux socket 不在小格裡，在 `${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/<小格真實路徑的 sha256 前 16 碼>.sock`（`cli_cell.py:20-81`）。我核對過：`eca-aos` 小格真實路徑 64 bytes，算出 `9db3a6cf7b61f650`，就是 `/run/user/1000/aos-tty-1000/` 裡那個檔，也是 tmux 行程命令列上的那個。
- 判錯的後果：畫面其實開著、aos 卻以為沒開，就會另起一隻 `claude -p --resume` 跟畫面寫同一段對話。11-24 搬 stack 時差點發生（`wf/ws/eca-aos/notes.md:469,476`）。

### 2.3 stack 裡每個檔：誰寫、誰讀、掉了會怎樣

「新分類」欄的字：**身**＝活的身體（行程在才有意義，重起就重建）；**留**＝persist；**設**＝settings；**外寫**＝別人會來寫；**外**＝不在 aos 手上；**記**＝只給人看的紀錄。這一欄是我的推論，其餘欄是查的。

**表 A：stack 頂層**（活樹 `procs/repo-aos/procs/eca-aos-kb/` 與 `eca-aos/` 對著程式看）

| 檔／夾 | 誰寫 | 誰讀 | 掉了會怎樣 | 新分類 |
|---|---|---|---|---|
| `ctl.json` | daemon、`aos-agent ctl`、人 | aos-loop（每跑一次讀一次） | 沒新指令 | 外寫（＝新的 `ctl`） |
| `state.json`、`state_flux.json` | aos-loop | daemon、`aos-agent`、到期關畫面、on_clock、「很久沒動靜」、aos-idle（都拿裡面的 pid＋開機 id 認「是不是這次的 loop」） | loop 起來當第一次，`paused` 忘了 | 身（＝新的 `status`）；`paused` 那欄要留 |
| `exec.json`（有的列才有：活樹上子 agent 那五列有、`eca-aos` 沒有；規則見 `02-aos-daemon現況.md`）、`stop_cause.json`、`stderr.txt` | daemon | aos-exec、aos-loop、人 | 下次起會重寫 | 身；`exec.json` 的 envs 屬於設 |
| `queue/`（`tmp new cur`、`order.json`） | `aos-agent say／chat／ask`（人與別的 agent）、時鐘、自己的 hook（`mail_notify`、`context_wrap`） | aos-eca-turn（認領、交給 CLI、刪）、aos-idle | 還沒交出去的信沒了，寄的人不知道 | 外寫＋留 |
| `mailbox/`（含 `archive/`） | 別的 agent 的 `mailbox_send`；自己讀信時搬動 | 自己的 `mailbox_*` 工具（經 aos-mcp）、`mail_notify` | 沒讀的信沒了 | 外寫＋留 |
| `history.jsonl` | aos-eca-turn 附加；畫面 hook 在 `/clear`、`/compact` 時整份換；`aos-agent history`、`self_history` | `aos-agent listen／ask／ctl state`、開新對話時的前情、goal、`mail_notify`、aos-idle | 拿不到回答；下次換對話沒有前情 | 留 |
| `history_removed.jsonl` | 上一列換掉東西時 | 人、`ask` 找被搬走的回答 | 少了被換掉的原文 | 留 |
| `letters.json` | aos-eca-turn | `aos-agent ask／listen` | 對不出「這封信的回答是哪則」 | 留 |
| `retry.json` | aos-eca-turn（暫時 API 錯時欠著的信） | aos-eca-turn、aos-idle | 欠的信不會再答 | 留 |
| `goal.json` | `aos-agent goal`（人）、aos-eca-turn 記次數 | aos-eca-turn、aos-idle | 目標沒了 | 留＋外寫 |
| `tools.json`、`llm.json`、`system.txt`、`hookeds.json`（只存跟定義的差異） | `aos-agent tools／llm／system／hook` 或 `self_*` 工具 | 每輪起 CLI 前重讀；aos-mcp | 回到定義原樣 | 留 |
| `handoff.md` | agent 自己 | `compact_hook` | 壓縮完少附一段 | 留 |
| `notes_path` | 上層或人 | `compact_hook` | 壓縮完不提醒讀筆記 | 設 |
| `cooldown.json`、`quiet.json`、`mailbox_warning.txt` | aos-eca-turn | `ctl ls`、`listen`、aos-idle | 冷卻忘了，下一輪照常 | 身 |
| `hookeds/<名>/`（`event.json`、`on_clock.json`、各 hook 自己的記號）、`hook_tools_seen.json` | hook 執行器與各 handler | 同左 | 當成第一次：多提醒一次 | 身（可重建） |
| `daemon_reply/` | daemon（回這隻下的 ctl 信） | 這隻叫的工具 | 那次呼叫等不到回信 | 身＋外寫 |
| `tools/<工具名>/` | 經 aos-mcp 叫的工具 | 同左 | 看工具；`tools/subagent/subagents.json`（我開了哪些子 agent）要留 | 混 |
| `idle_gate.json`、`idle_gate.log`（11-25 新增，還沒交） | aos-idle | aos-idle | 多放行一拍 | 身 |
| `context_usage.json` | **沒有人寫**（位子留好了，只有測試寫） | `context_use` 的第一順位 | — | — |

**表 B：小格 `claude/`**

| 檔 | 誰寫 | 誰讀 | 掉了會怎樣 | 新分類 |
|---|---|---|---|---|
| `session.txt` | `-p`：交出去那一刻；畫面：hook 在第一輪與換對話時 | 每輪決定 `--resume` 誰；`context_use` | 下一則開新對話（帶前情）；手刪它是正式的「重開」用法 | 留（指標） |
| `.session_home` | 跟 `session.txt` 一起寫、一起刪：`{"session","ws","home","machine"}` | `session_here` | 對話檔找得到就補寫，找不到就開新對話 | 留（只在本機有效） |
| `.history_sum` | 每輪結束記 `history.jsonl` 的 sha256 | 下一輪比「history 被人改過沒」 | 這次不比 | 留（跟 history 一對） |
| `transcripts/claude-<id>.jsonl` | 拿到 id 時建的 symlink，絕對路徑指進帳號資料夾 | `context_use` 第一順位、人 | 改去帳號資料夾找 | 留（指標），指到外面 |
| `tool.txt`、`ws.txt`、`stack.txt` | 每輪（相對小格的路徑：定義、工作區、stack） | 重開畫面、畫面 hook 找 stack 與工作區、到期關畫面 | 開畫面報 `CellBad`（跑過一輪會重寫） | 設 |
| `env.json` | 每輪記 loop 手上的 `AOS_HOME`、`AOS_DAEMON`、`AOS_CLOCK`、`AOS_LLM_KERNEL` 等（絕對路徑） | 開畫面時照它給環境 | 畫面改用開畫面那個殼的 | 設（今天不記帳號夾） |
| `lock` | 只拿來 flock | 一輪、開畫面、關畫面、slash、到期關畫面 | 重建 | 身 |
| `live.jsonl` | `-p` 那條每個事件一行，只接不清 | `aos-agent watch`、`context_use`（用量與視窗大小）、「很久沒動靜」 | watch 沒得看；只在畫面上講過的讀不到視窗大小 | 記（但 token 數字只落在這裡） |
| `turns.jsonl` | 畫面 hook 每講完一輪一行，只接不清 | 等回答的 aos-eca-turn，**回答就是從這裡拿** | 等的那一輪拿不到回答 | 身（畫面回話給 loop 的管道） |
| `busy.txt` | 畫面 hook：送出時寫、講完時刪 | 貼字那條路判忙、slash 不打斷 | 殘留＝貼字那條路以為一直在忙 | 身 |
| `a2a.json`、`a2a_acks.jsonl` | 畫面 hook：抄下 Claude 的收件 socket 路徑、記回執；開畫面時先刪 | `cli_ask.live_a2a` | 退回貼字 | 身 |
| `mcp.json` | 每次起 CLI 前重寫（絕對路徑；帶使用者自己設的 MCP 時可能有金鑰，權限 0600） | claude `--mcp-config` | 重寫 | 身 |
| `tmux.conf` | 開畫面時 | tmux | 重寫 | 身 |
| `screen_close.json` | `after_stop` hook 排的「幾秒後關畫面」單 | 到期那支 | 不關了 | 身 |
| `compact_restore.txt` | `compact_hook pre` | `compact_hook start`（印完就刪） | 壓縮完少補一段 | 身 |

**表 C：不在 stack 裡、但一輪要用到的**

| 東西 | 誰的 | 誰讀 | 掉了會怎樣 | 新分類 |
|---|---|---|---|---|
| `/run/user/<uid>/aos-tty-<uid>/<雜湊>.sock` | 畫面的 tmux 伺服器 | 判畫面開沒開、接上去看、貼字 | 畫面當作沒開，改走 `-p` | 身（畫面那棵的） |
| `/run/user/<uid>/cc-socks/<claude 的 PID>.sock` | Claude Code 自己建、自己收（實測五個檔都對得到活的 claude） | aos 往裡寫署名訊息 | 退回貼字 | 身（Claude 的，不是 aos 的） |
| `<帳號夾>/projects/<由工作區路徑變來的夾名>/<id>.jsonl`（實例：夾名 `-home-guanyu-repo-aos`） | Claude Code | `--resume`、`context_use`、壓縮摘要、goal 進展、`/status` | **對話沒了**，下一輪開新的 | 外 |
| `<帳號夾>/.claude.json`、登入憑證 | Claude Code、人 | 起 claude、`cli.json` 的 `claude_mcp` | 要重新登入 | 外 |
| `<工作區>/.claude/settings.json`、`CLAUDE.md`、`.mcp.json` | 人 | Claude Code | — | 外（工作區） |
| `<定義>/cli.json`、`loop.json`、`hookeds.json`、`compact_hook` 等 | 人 | 每輪 | — | 定義 |

活樹上的大小：整棵 `~/aos-home/.stack` 84 MB，其中 14 份 `live.jsonl` 佔 30 MB（`eca-aos-kb` 那份 33 輪就 4.5 MB）。清道夫第一版刻意不碰它（`py/aos/apps/sweeper/README.md:40`）。

### 2.4 這個專案已經分過兩次

- **`py/aos/apps/agent/stack.gitignore`**（11-06 起，多條註明是使用者裁的）：第 5 行寫明擋的是「只在這台、這一刻有意義」的東西；留的是「醒來要接著用」的。擋的：`lock`、`*.sock`、`busy.txt`、`a2a.json`、`a2a_acks.jsonl`、`env.json`、`mcp.json`、`tmux.conf`、`cooldown.json`、`hookeds/`、`daemon_reply/`、`stderr.txt`、`live.jsonl`、`turns.jsonl`、`transcripts/`、所有點開頭的檔。這份清單大致就是 eca 的「活的身體」。差三樣：`.session_home`、`.history_sum`、`transcripts/` 被擋是因為「帶到別台沒用」，但同一台重起還要用，照新模型算要留的（只在本機有效）。
- **`docs/NORMS/附錄4-持久檔.json`**（70 列：持久 46、暫時 24），欄位有誰寫、誰讀、進不進 image、壞了怎麼反應，小格那幾列都在。
- **image 那份說明早就寫了同一個邊界**（`py/aos/apps/agent/docs/04-搬家/02-image保存與邊界.md:8`）：eca「的對話本體在那台的 `~/.claude/projects/…`，image 裡只有 `session.txt` 的 id」，換台就開新對話、拿 `history.jsonl` 當開場白。
- 三種身體在這一點上不一樣：pi 身的對話檔在小格的 `pi-sessions/`（`pi --session-dir`，`templates/docs/03-eca-pi.md:12`）；claude、codex 的在帳號資料夾。Claude Code 2.1.332 的 `--help` 裡沒有搬對話檔位置的旗標，只有 `--session-id`、`--resume`、`--fork-session`、`--no-session-persistence`。

### 2.5 11-25 事故：我自己對過的數字

使用者原話（`wf/ws/eca-aos/notes.md:552`）：「嗨，先看看self history。」「就是說，剛剛我是用另一個CLAUDE_CONFIG_DIR，另一個帳號。」「所以這邊...你能接上嗎」

| 時間（本地） | 發生什麼 | 我看的證據 |
|---|---|---|
| 11-24 16:21 起 | `eca-aos` 的畫面用的是 `~/.claude`（開畫面的殼沒設帳號夾），對話 `93e7c7ab…` 在那裡 | 小格 `transcripts/` 的連結指向 `~/.claude/projects/-home-guanyu-repo-aos/`；`notes.md:566` |
| 同時 | loop 這邊帶的是 `~/.claude-alt` | `/proc/2243/environ` 的 `CLAUDE_CONFIG_DIR` |
| 11-25 08:41 | 第一次壓縮。`history.jsonl` 沒動（eca-aos 查的原因：畫面 hook 去對話檔找摘要時還沒寫進去，`notes.md:555-556`） | 對話檔第 556、557 行是這次壓縮；`history_removed.jsonl` 沒有這個時刻的紀錄 |
| 10:57 | 第二次壓縮。hook 讀到的是**上一次**的摘要，拿它換掉 118 則 | `history.jsonl` 第一則長 8334 字＝開頭「[aos] summary: lines 1-118, 118 messages. 」42 字＋08:41 那則摘要 8292 字（10:57 那則是 9460 字）；`history_removed.jsonl` 只有一筆 compact，02:57:04.488Z、118 列 |
| 10:59:32 | 使用者用 `~/.claude-alt` 的殼重開畫面。`cli_screen.py:50-53` 比到帳號夾不同，刪掉 `session.txt`，不帶 `--resume` 起 claude | `tmux.conf` 的修改時間；`.session_home` 的 `home` 現在是 `~/.claude-alt`；新對話 `830121d0…` |
| 10:59:58.7 | 使用者在畫面上打第一句「嗨，先看看self history。」。0.2 秒後 hook 把新 id 記進 `session.txt` | 新對話檔那一則的時間戳；`session.txt` 的修改時間 10:59:58.94 |
| 之後 | aos 的前情**一個字都沒進新對話** | 新對話檔 1616 行裡，前情那句固定開頭（`this conversation continues in a new session`）出現 0 次 |

為什麼前情沒進去：前情只在「aos 送信時發現 `session.txt` 是空的」才接（`cli_ask.py:166-172`）。人先開口，hook 就把 `session.txt` 填上了（`agentlib/cli_hook.py:285-287`），之後 aos 再送信看到的是「有對話」。就算接了，畫面那條路上限只有 8000 bytes（`agentlib/cli_base.py:10`），接進去的也是那則過期摘要。

摘要慢一拍的原因在 `cli_hook.py:282-283`，eca-aos 已派 core 修（線 `eca-aos-core-1125f`）；我寫這份時工作樹裡 `cli_hook.py` 還沒動。

當時 aos 這邊留著什麼：`history.jsonl` 三則（過期摘要、一封新信通知、一則回答）；`history_removed.jsonl` 160 列；`turns.jsonl` 183 輪的回答（沒有題目）。使用者整個早上在畫面上打的話不在這三個檔裡，因為「人在畫面上自己打的話不進 history」（`apps/eca/main_turn.py:105`）。舊對話檔 3.0 MB 還在 `~/.claude/` 底下、讀得到，只是換了帳號夾 `--resume` 不到。eca-aos 自己的筆記寫它是靠三樣接回來的：筆記最後一節、`wf/HANDOFF.md`、舊對話檔裡那則摘要（`notes.md:553`）。

### 2.6 token 用量今天落在哪

`agentlib/context_use.py` 的 `read(stack)` 回的是「最後答完那一輪、最後一次呼叫的輸入 token ÷ context 視窗」，也就是 **context 現在多滿**（`context_use.py:7-8`）。讀法照順序試（`:350`）：通用檔 `context_usage.json`（`:55-66`，沒人寫）→ claude 身：有對話檔就讀對話檔，沒有才讀 `live.jsonl`（`:242-246`）→ pi → agent-fsm。eca 這邊在用它的只有 `context_wrap` 這個 on_clock hook（範本每 5 秒看一次、門檻 35%）。

我對活樹只讀跑了一次（12:0x，`context_use.explain`，每隻 4～63 毫秒）：`eca-aos-kb` 23.9%（239088／1000000）、`eca-aos` 19.4%、`eca-aos-core` 78.5%、`eca-aos-templates` 沒有讀數（它回的原因：最後一次壓縮之後還沒有答完的一輪）。

「累計用了多少」是另一個數字，`context_use` 沒有：

| 數字 | `-p` 那條路 | 畫面那條路 |
|---|---|---|
| 這段對話累計 token、金額 | `live.jsonl` 最後一個 `result` 行的 `modelUsage`、`total_cost_usd`。實測是**累計值**：`eca-aos-kb` 33 個 result 從 1.77 單調升到 29.43，跨 `--resume` 照樣累計 | 沒有 result 行。要把對話檔裡 assistant 行的 `usage` 依 `message.id` 去重後加總（實測 153 行只有 66 則） |
| 這一輪用了多少、跑多久 | 同一行的 `usage`、`num_turns`、`duration_ms` | 同上自己算 |
| 帳號額度 | `rate_limit_event` 行：七天視窗用了 33%、何時重置 | 沒有；`/usage` 另起一次 `claude -p` 問得到一段文字（`apps/eca/slash.py:146-171`） |

金額是照牌價估的（`modelUsage` 裡 `costBasis: "list"`），不是帳單。

### 2.7 實測：畫面的 socket 能不能走 `/proc/<PID>/cwd`

tmux 3.4，小格真實路徑做成 172～187 bytes（超過 108）：

| 做法 | 結果 |
|---|---|
| `tmux -S <真實路徑>/tty.sock new-session` | 失敗：`File name too long` |
| 站在小格裡，`tmux -S tty.sock`（相對名字） | 建得起；一樣站在小格裡就連得上，從別處用真實路徑連不上 |
| 另一隻行程站在身體夾裡，`tmux -S /proc/<它的 PID>/cwd/claude/tty.sock new-session`（33 bytes） | 建得起，socket 檔落在小格裡；`has-session`、`send-keys` 都通 |
| 同上，把那隻行程 `kill -9` | 那條路馬上 `No such file or directory`。**tmux 還活著**，但它記得的 socket 路徑就是那條已經斷的路 |
| tmux 伺服器自己站在小格裡起，別處用 `/proc/<tmux 伺服器 PID>/cwd/tty.sock`（26 bytes） | `has-session`、`capture-pane`、`kill-server` 都通；伺服器沒了那條路就斷，socket 檔還留在小格裡 |

<details><summary>最小重跑程式（只碰自己旁邊的暫存夾；`~/.aos/scratch/aos-proc-arch-1125/04/tmux_min.py`）與輸出</summary>

```python
import os, shutil, subprocess, tempfile, time
base = tempfile.mkdtemp(prefix="tmux-cwd-", dir=os.path.dirname(os.path.abspath(__file__)))
cell = os.path.join(base, *(["procs", "a-rather-long-daemon-name"] * 3), "procs", "kid", "claude")
os.makedirs(cell)
env = {k: v for k, v in os.environ.items() if k != "TMUX"}
def tmux(sock, *args, cwd="/"):
    r = subprocess.run(["tmux", "-S", sock, *args], capture_output=True, text=True, cwd=cwd, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()[-40:]
real = os.path.join(cell, "tty.sock")
print(len(real), "bytes; real path     ->", tmux(real, "new-session", "-d", "-s", "cli", "sleep 60"))
print("relative name, cwd=cell      ->", tmux("tty.sock", "new-session", "-d", "-s", "cli", "sleep 60", cwd=cell))
pid = tmux("tty.sock", "display-message", "-p", "#{pid}", cwd=cell)[1]
short = "/proc/%s/cwd/tty.sock" % pid
print(len(short), "bytes; via server's cwd ->", tmux(short, "has-session", "-t", "cli"))
print("real path from elsewhere     ->", tmux(real, "has-session", "-t", "cli"))
print("kill-server via short path   ->", tmux(short, "kill-server"))
time.sleep(0.3)
print("short path afterwards        ->", tmux(short, "has-session", "-t", "cli"))
shutil.rmtree(base)
```

```
187 bytes; real path     -> (1, 'kid/claude/tty.sock (File name too long)')
relative name, cwd=cell      -> (0, '')
26 bytes; via server's cwd -> (0, '')
real path from elsewhere     -> (1, 'kid/claude/tty.sock (File name too long)')
kill-server via short path   -> (0, '')
short path afterwards        -> (1, 'cwd/tty.sock (No such file or directory)')
```

</details>

## 3. 對新介面的含意

以下除了引文與出處，都是推論。

### 3.1 對著「定了的」逐條

| 定了的（`9p-proc-1125.md`） | 放到 eca 身上 |
|---|---|
| 介面基於 9P，支援這套的就是 aos proc | Claude Code 不是我們寫的，不會自己擺出 `ctl`、`status`。替它擺的是外面那層殼，今天的 aos-loop 加 aos-eca-turn 就是這層殼。eca 當 aos proc＝讓這層殼擺出新介面。 |
| `ctl` 吃純文字，寫回來＝收到 | 殼在等一輪時不讀 ctl，見 3.4。 |
| `status` 一行一個「名稱: 值」，目前只給一個檔 | 行表見 3.5。 |
| token 用量 proc 自己報；kernel 的帳在 kernel | eca 的腦是 CLI 自己，不經 llm kernel（`templates/docs/01-eca-claude.md:59`），沒有任何 kernel 有它的帳。另外多一個跨 proc 的讀數：帳號額度。 |
| daemon＝橋，多一個 `procs` 夾 | 畫面那棵（tmux、claude、aos-mcp）不是 daemon 起的，daemon 不知道它的 PID。它算誰的，見第 5 節第 4 題。 |
| 入口是根 daemon 的 PID，大家走 `/proc/<PID>/cwd` | loop 得改成站在自己的身體裡。eca 的 Python 這邊靠 cwd 的只有三處：`_entry` 的 `loop.json`、`screen/_entry` 的 `--eca ..`、`AOS_WS` 沒設時拿 `.` 當工作區（`apps/eca/__init__.py:117`、`main_screen.py:142,317`）。Claude 自己一定站工作區，不能拿它的 PID 當入口。 |
| `.stack` 沒有了；stack＝活的身體 | 今天 `AOS_STACK` 一個變數同時指「身體」與「要留的」。小格要分兩半，見 3.2。 |
| 要留的放 `procs/<名>/persist`，位置 proc 自己說；預設在 `/tmp` | eca 要留的都得過重開機（history、指標、queue），預設那塊不夠，一定要自己挑硬碟位置。殼是 C++ 的 aos-loop 加一拍一拍的短命 Python，「自己挑、寫進 `settings`」得有人在 loop 起來那一刻寫（`loop.json` 的 `on_start` 那格做得到）。 |
| 活著走 unix socket，掛了問信箱改寄信 | eca 已經有一個「活著走 socket」的實例：畫面開著時往 Claude Code 自己的 socket 寫。踩過的坑見第 4 節第 7 點。 |
| 問信箱時要不要順手叫醒 | eca 的「醒」有兩層：loop 有沒有在跑，CLI 有沒有在跑。今天最接近的是 `mail_notify`：每分鐘看一次信箱，有新信就往 queue 丟一句通知。 |

### 3.2 分類結果，與「對話本體」算什麼

- **活的身體**：鎖、`busy.txt`、`a2a.json`、`a2a_acks.jsonl`、`turns.jsonl`、`mcp.json`、`tmux.conf`、`screen_close.json`、`compact_restore.txt`、`cooldown.json`、`quiet.json`、`hookeds/<名>/`、`daemon_reply/`、`state.json` 裡 pid 那幾欄，加上 stack 外的兩種 socket。
- **persist**：`history.jsonl` 與 `history_removed.jsonl`、`queue/`、`mailbox/`、`letters.json`、`retry.json`、`goal.json`、四份覆蓋檔、`handoff.md`、`tools/subagent/subagents.json`、`state.json` 的 `paused`；小格裡的 `session.txt`、`.session_home`、`.history_sum`、`transcripts/`。
- **settings**：今天沒有這樣一個檔，散在六處：daemon 表那一列（def、ws、stack）、`exec.json` 的 envs（`AOS_NOTIFY_BOX`、`AOS_PARENT_STACK`、有的列還有 `CLAUDE_CONFIG_DIR`）、行程的環境變數、小格的 `tool.txt`／`ws.txt`／`stack.txt`、`env.json`、`notes_path`。
- **別人會來寫的**：`ctl`、`queue/`、`mailbox/` 三樣是介面。另外有一批「主人的工具直接改檔」：`aos-agent goal／history／tools／llm／system／hook`。
- **只給人看的紀錄**：`live.jsonl`、`stderr.txt`、`mailbox_warning.txt`。
- **外面的**：帳號資料夾、工作區的 `.claude/`。

**對話本體**：它不是身體（行程死了它還在），也不在 aos 的 persist（aos 搬不動、改不了、壽命由 Claude Code 決定；`agentlib/cli_session.py:33` 寫「CLI 會自己清舊對話」）。它是 CLI 自己的 persist，放在 aos 手外。aos 的 persist 裡跟它有關的只有兩樣：

- 一個**地址**：`session.txt` 加 `.session_home`，剛好記齊四把鑰匙（機器、帳號夾、工作區路徑、id）。這個記號檔已經是對的形狀，只是今天它被當成「絆線」用，不是當設定用。
- 一份**縮水抄本**：`history.jsonl`，只有經 aos 送進去的題目和每輪最後的回答，沒有工具來回，也沒有人在畫面上打的話；壓縮之後只剩 Claude 寫的摘要。

所以「重起＝新的身體接回舊的 persist」這句話（`9p-proc-1125.md` 邊緣那節，eca-aos 寫的），對 eca 要分兩段說：身體接回 aos 的 persist，一定做得到；接回同一段 Claude 對話，要四把鑰匙全中，中不了就只能拿抄本與筆記重新開場。

小格分兩半最省的做法：165 處讀寫都經過 `Cell.file(名字)`，在 `Cell` 裡放一張「這個名字在身體還是在 persist」的表，其餘程式不動。再更省的第一步是 `9p-proc-1125.md` 邊緣那節已經寫的：整個現有的夾先當 persist，身體夾裡放一個指過去的 `persist`。

把上面的分類畫成一張圖（只是示意，檔名與格式都還沒談）：

```
procs/eca-aos/             loop 站的夾＝身體
  ctl  status  usage       純文字：今天的 ctl.json、state.json，加一個還沒有的用量檔
  _metainfo  settings      定義帶來的／我的東西放哪（persist、定義、工作區、帳號夾、上層、回報信箱）
  claude/                  小格活的那半：lock、busy.txt、a2a.json、turns.jsonl、mcp.json、tmux.conf
  persist/                 → 自己挑的硬碟位置
    history.jsonl  queue/  mailbox/  letters.json  retry.json  goal.json  四份覆蓋檔
    claude/  session.txt  .session_home  .history_sum  transcripts/
```

### 3.3 事故當案例：靠 persist 的什麼接回來，現在缺什麼

接得回來要三樣：對話的地址（上面那四把鑰匙）；夠新的前情（抄本或筆記）；還在路上的工作（`queue/`、`mailbox/`、`letters.json`、`retry.json`、`goal.json`）。第三樣今天是好的。缺的是：

| # | 缺什麼 | 現況 | 可以怎麼補 |
|---|---|---|---|
| 1 | 帳號夾不是這隻 proc 的設定，是「誰起它就用誰的環境」 | loop 與畫面兩個來源，`env.json` 不記；`eca-claude-alt` 範本用兩份 `.env` 手動對齊 | 寫進 `settings` 一行，開畫面照它，不看開畫面那個殼 |
| 2 | 人先開口的新對話拿不到前情 | 前情只在 aos 送第一封信、而且 `session.txt` 空著時才接 | 畫面的 SessionStart（source 是 startup）就印一段：你是誰的接續、筆記在哪、抄本在哪、上一段對話檔在哪。`compact_hook start` 已經會在壓縮後印類似的東西 |
| 3 | 抄本沒有畫面上的對話 | 設計如此。對主要跟人在畫面上談的位子，抄本幾乎是空的 | 前情改從舊對話檔取（aos 已經在五個地方讀它的格式），或讓 Stop hook 把每輪的題目也記下來 |
| 4 | 抄本的摘要慢一拍 | 已派修 | — |
| 5 | 對話檔只有一份，在帳號夾裡 | 小格只有 symlink | 見第 5 節第 1 題 |
| 6 | 「這段對話現在接不接得上」從外面看不到 | 要等下一輪才判 | status 給一行，見 3.5 |

第 1 項補上，這次事故不會發生；真的要換帳號時（額度用完會這樣換），要靠第 2、3 項。

### 3.4 ctl 的 stop、pause 怎麼對到 Claude Code

| 動作 | 今天怎麼落到身體上 | 一輪答到一半 | 背景任務 | 畫面 |
|---|---|---|---|---|
| pause | 寫 `ctl.json`，loop 在兩輪之間停手（`py/aos/apps/agent/ctl/phase.py:247-257`） | 這輪照跑完、回答照記 | 不動 | 完全不受影響：人照樣能打字、Claude 照樣做事，只是 aos 不再送信進去。on_clock 也跟著停（它在 aos-eca-turn 裡跑），所以 `context_wrap`、`mail_notify` 都不看了 |
| stop | daemon 往 `ctl.json` 寫 stop，loop 這輪結束後退出、跑 `after_stop` hook（`phase.py:156-183`） | 等這輪答完，表上顯示 `stopping`，可能幾十分鐘 | `-p`：答完 3 秒後整群收 | 不當場關。`after_stop` 排一張單，`screen_close_after_s`（預設 600）秒後 `tmux kill-server`；期間再 start 就不關。到期時不看畫面是不是正在忙（`agentlib/cli_linger.py:143-177`；讀程式得到的，沒實跑） |
| sleep（今天不是 ctl 的字，是 daemon 送 SIGTERM） | loop 把訊號轉給 aos-eca-turn，它當場死；`claude -p` 靠「父死、子收 TERM」跟著收（`cli_print.py:13-32`） | 那批信已經收了、沒有回答、醒來不重答（`phase.py:205-207` 會提醒一行） | 平常收背景任務的 `stop_group` 來不及跑；claude 自己開的背景任務誰收，沒驗 | 同 stop |
| rm、換定義 | 同 sleep | 同上 | 同上 | 當場關（`apps/eca/README.md:16`） |

對「寫 ctl 回來算收到」這一條（使用者原話「1.寫ctl回來，算是收到。」，`9p-proc-1125.md` 第 4 段）：

- aos-loop 每跑一次才讀一次 ctl（`cpp/aos-loop/docs/02-窗.md:9`；`cpp/aos-loop/src/engine/loop.cpp` 主迴圈頂端的 `read_ctl()`）。eca 一輪不限時（使用者 11-15「AI一輪跑個二三十分鐘都很正常，eca也是可能長時間不回應，逾時這東西應該要默認爲0，也就是不限時間，除非是一些有特殊需求的。」，`templates/docs/01-eca-claude.md:114`），所以今天下 stop 之後，要等這輪結束 loop 才知道。
- 落檔的實作：檔一定寫得進去，「寫回來」沒有資訊量，生效了沒只能看 status。要讓「收到」有意義，殼得在等那一輪的同時也收 ctl。
- 今天沒有「現在就打斷這一輪、但別停掉這隻」的動作。最接近的是 sleep，它連 loop 一起收。`-p` 那條要做很便宜（`stop_group` 已經有了）；畫面那條是送一個中斷鍵。要不要有這個字，見第 5 節第 3 題。
- 背景任務的規矩已經有使用者的裁定：`-p` 那條答完就連背景任務一起收（11-24，`wf/ws/eca-aos/notes.md:488-492`；`cli_print.py:119-121`）。畫面那條 aos 收不到也看不到：我寫這份時，aos 看 `eca-aos` 是閒著（`busy.txt` 不在、最後一輪 12:05 講完），它其實還有這一批背景子 agent 在跑，我是其中一隻。

### 3.5 status 能報什麼

我用一支只讀的小程式（`~/.aos/scratch/aos-proc-arch-1125/04/eca_status.py`；只讀 stack 的檔與 `/proc`，不拿鎖、不叫 tmux 與 aos 指令）對活的 `eca-aos` 跑出來的：

```
name: eca-aos
kind: claude
phase: running
paused: false
pid: 2243
turn: idle
screen: open (tmux pid 1584127, claude pid 1584129)
screen_mail: socket
conversation: 830121d0-1da2-4e66-81d5-8eaa43a0825c
account_dir: ~/.claude-alt
queue_new: 0
queue_cur: 0
letters_pending: 0
retry_owed: 0
mailbox_new: 0
history_messages: 3
context_used: 293153
context_window: 1000000
context_percent: 29.3
goal: -
cooldown_until: -
quiet_since: -
as_of: 2026-11-25T04:13:43Z
```

| 行 | 今天從哪裡知道 | 要注意的 |
|---|---|---|
| `phase`、`paused`、`pid` | loop 的 `state.json`、daemon 的表 | `kill -9` 之後檔還寫著 running；新模型由活的行程回答就沒這問題 |
| `turn`（idle／answering／cooling） | 有沒有 `claude -p` 子行程、`busy.txt`、`cooldown.json`、`retry.json` | 畫面上人自己打的那輪也算 answering；背景子 agent 看不到，idle 不等於沒在動 |
| `screen`、`screen_mail` | 畫面 socket 與 tmux 行程、`a2a.json` | — |
| `conversation`、`account_dir` | `session.txt`、`.session_home` | 該多一行「接不接得上」。`session_here` 今天會順手補寫記號檔，要一個純讀的版本 |
| `queue_*`、`letters_pending`、`retry_owed`、`mailbox_new` | 數資料夾、讀 `letters.json`、`retry.json` | — |
| `history_messages` | `history.jsonl` 行數 | — |
| `context_*` | `context_use.read()` | 剛壓縮完到下一輪答完之間沒有讀數 |
| `goal`、`cooldown_until`、`quiet_since` | `goal.json`、`cooldown.json`、`quiet.json` | — |

今天 `aos-agent ctl state` 已經把差不多的東西分成 11 類（who、state、tools、llm、system、hooks、history、mailbox、subagents、resources、time；`py/aos/apps/agent/ctl/state.py:16`），可以當 status 行表的底。字表與格式見 `18-ctl、status、settings的候選寫法.md`。

### 3.6 token 用量做成身體夾裡的純文字檔，要動哪裡

1. **加一支寫檔的函式**（放 `agentlib/context_use.py` 旁邊）：組「名稱: 值」，先寫暫存再改名。
2. **三個叫它的點**：
   - `apps/eca/turn.py` 的 `finish()`（`:109-122`）：`-p` 那條，與畫面上由 aos 送信的那輪，都會走到這裡。
   - `agentlib/cli_hook.py` 的 Stop 那段（`:314-319`）：人在畫面上自己打的那輪，只有這裡有 aos 的程式在跑。hook 不准拖慢或弄壞 CLI，要寫得很保守。
   - 壓縮之後（`cli_hook.py:282`）：把 context 那幾行改成沒有讀數。
   - 不想動核心的話：掛一格 on_clock handler 定時重寫。範本 `hookeds.json` 的 `timer` 那格就是留給這種用途的。
3. **累計數字要新寫讀法**：`-p` 讀最後一個 result 行；畫面要增量加總對話檔，並記下讀到哪。
4. **讀的那邊**：`context_use.from_file`（`:55-66`）今天吃的是 json 的 `context_usage.json`。要嘛讓它也吃新的文字檔，要嘛文字檔只給外面看、內部照舊。
5. **跟著改**：`stack.gitignore`、NORMS 附錄 4、知識庫 `aos/me.md` 的「What is in your stack」、`py/tests/test_context_wrap.py`。

報哪幾個數字要使用者定（第 5 節第 5 題）。他的原話是「能否給出別的？比如token消耗量之類」（`9p-proc-1125.md` 第 2 段），字面是「消耗量」，而今天現成的只有「context 多滿」。

### 3.7 `AOS_STACK` 與小格路徑的衝擊面

| 哪一類 | 多少 | 在哪 | 換模型時 |
|---|---|---|---|
| 讀環境變數 `AOS_STACK` | eca 這條路 13 處（整個 `proto8/py` 45 處） | `apps/eca/__init__.py:113`、`main_screen.py:133,175`、`cli_ask.py:216`、`cli_cfg.py:126`、`agent_tool.py:18`、`apps/hook/main.py:108`、`apps/mcp/main.py:114`、三支 hook handler、`compact_hook:90,158` | 一個變數拆成「身體」與「要留的」兩個意思 |
| 拼出小格 `<stack>/<kind>` | 10 處建 `Cell` | `apps/eca/turn.py:26`、`main_screen.py:137,182`、`cli_linger.py:115,120,148`、`apps/agent/ctl/set_def.py:138`、`cli_hook.py:264`、`cli_ask.py:228`、`agent_tool.py:25` | 改 `Cell` 一處 |
| 經 `Cell` 讀寫小格的檔 | 165 處、18 個檔 | `cli_ask` 23、`cli_hook` 18、`cli_cell` 18、`slash` 17、`cli_screen` 17、`cli_linger` 12… | 在 `Cell` 裡放一張分類表，其餘不動 |
| 繞過 `Cell` 直接寫路徑 | 9 處 | `context_use.py:96,156,214,325`、`compact_hook:93,167`、`apps/agent/system.py:130`、`apps/agent/ctl/ls.py:83,89` | 逐處改 |
| 寫進檔的絕對路徑 | 7 種 | `mcp.json`、`env.json`、`.session_home`、`transcripts/` 的連結、`hookeds/*/event.json` 與 `on_clock.json`、到期關畫面排給 tmux 的那行指令 | 身體換位置就失效；多數下一輪會重寫 |
| **寫死在長命行程裡的路徑** | 畫面那棵 | claude 的環境變數 `AOS_STACK`、`--mcp-config <小格>/mcp.json`、三個 hook 指令帶的小格路徑（`cli_screen.py:29-30,57`）、aos-mcp 的 `--stack`、tmux 的 `-f <小格>/tmux.conf` | 不會跟著變，只能關掉重開。給它們的路徑要是真實路徑，不能是 `/proc/<loop 的 PID>/cwd/…`（實測：tmux 會把那條路當成自己的 socket 位置記住） |
| 用小格位置算出來的名字 | 1 | 畫面 socket＝小格真實路徑的 sha256 | 身體換位置，雜湊就變，舊畫面認不得 |
| 測試手排 stack 與小格的版面 | 17 個 `test_*.py` | `py/tests/`、`templates/tests/` 等 | 跟著改 |
| 文件與知識庫提到小格檔名 | 17 份 | `knowledge/aos/cli/eca.md`、`templates/docs/01-eca-claude.md`、NORMS 附錄 4 等 | 跟著改 |

重跑用的指令（在 repo 根；四行依序回 45 行、10 行〔扣掉 `class Cell` 那行〕、18 個檔共 165、9 行）：

```sh
rg -n --glob '!**/__pycache__/**' --glob '!**/tests/**' 'environ(\.get)?[\(\[]["'"'"']AOS_STACK' proto8/py
rg -n --glob '!**/__pycache__/**' --glob '!**/tests/**' 'Cell\(' proto8/py | grep -v 'class Cell'
rg -c --glob '!**/__pycache__/**' --glob '!**/tests/**' 'cell\.(file|read|write|tmux|lock|alive|sock|turns|clients|path)\b' proto8/py
rg -n --glob '!**/__pycache__/**' --glob '!**/tests/**' 'path\.join\((stack|a\.stack|s)[^\n]*("claude"|"pi"|"busy\.txt"|, kind\)$)' proto8/py proto8/templates/agents/eca-claude | grep -v 'Cell('
```

順手看到一個像是錯的地方：`aos-agent ctl ls` 的忙碌欄找的是 `<stack>/busy.txt` 與 `<stack>/tools/<名>/busy.txt`（`apps/agent/ctl/ls.py:83,89`），但 eca 的 `busy.txt` 在 `<stack>/claude/busy.txt`；測試 `py/tests/apps/agent/test_ls_health.py:55` 把假檔放在 stack 頂層，所以測試是綠的。照程式讀，eca 畫面在忙時這一欄看不出來。我沒跑指令驗（鐵則不准叫 ctl）。這正好說明版面的知識散在好幾處、搬一次就漏一處。整體的 `AOS_STACK` 衝擊面見 `06-路徑、環境變數與命名現況.md`、`13-文件、測試與活樹的遷移衝擊.md`。

### 3.8 108 bytes：今天怎麼繞，`/proc/<PID>/cwd` 幫不幫得上

今天的繞法（`agentlib/cli_cell.py:20-81`）：socket 不放小格，放 `${XDG_RUNTIME_DIR}/aos-tty-<uid>/`（公司這台是 `/run/user/1000`，tmpfs、權限 700），檔名用小格真實路徑的 sha256 前 16 碼，整條 49 bytes。沒有 `XDG_RUNTIME_DIR` 或太長就退到 `/tmp/aos-tty-<uid>/`，找的時候兩處都看。當初搬出小格的頭號理由其實不是長度，是 `/mnt/c` 上建不了 socket（11-10 實測 `bind` 回 `EOPNOTSUPP`，`thinking/2026-11/10/two-machines/fs_features.json`）。長度是 11-09 談 daemon 的鈴時另外記過的，那時就提過用 `/proc/self/fd/N/…` 這種短路徑來連（`thinking/2026-11/09/daemon-interrupt/03-衝突與邊緣.md:27`）。今天活樹最深的小格如果把 socket 放回去是 85 bytes，再多一層就超過。

Claude Code 自己的做法跟新模型很像：socket 放 `/run/user/<uid>/cc-socks/`、檔名就是自己的 PID（36 bytes），行程在才有。連 `claude -p` 也有一條（開場事件的 `messaging_socket_path`，33 次都有）。

`/proc/<PID>/cwd` 幫得上的：

- 連的那一邊：2.7 的實測，172 bytes 連不上的 socket，走 26～33 bytes 的短路徑連得上。
- 建的那一邊：站在那個夾裡用相對名字建，或經短路徑建，都可以。
- 「死了馬上知道」：行程一死那條路就不見，不用另外判。

幫不上的：

- socket 檔所在的檔案系統不支援時照樣建不起來（`/mnt/c`）。今天各棵的 stack 都在 `~/aos-home/.stack`（ext4），只有工作區在 `/mnt/c`，沒事；以後身體放哪要留意。
- **畫面的 socket 不能掛在 loop 的 PID 底下**：loop 一停路就斷，畫面還活著（2.7 第四列）。畫面要嘛自己站在自己的格裡、用自己的 PID 當入口（2.7 第五列），要嘛照舊放 `/run/user`。
- Claude Code 自己那條 socket 的位置是它定的，aos 改不了，也不需要改。
- 不同 Linux 帳號走不進去（`9p-proc-1125.md` 已記）。

## 4. 邊緣狀況

1. **loop 停了、畫面還活著**（最多 600 秒；兩格 hook 設成 null 就一直活）。照 `/proc` 那條路這隻 proc 已經不在，但 Claude 可能還在做事、還在花 token。
2. **idle 不等於沒在動**。畫面那條路 aos 只知道 Stop hook 來了。背景子 agent、背景 Bash 做完時 Claude 會自己再開一輪，那輪的回答進 `turns.jsonl`，但沒有信在等它，不進 history。
3. **停下 600 秒後關畫面，不看畫面在不在忙**。人自己打的那一輪、還在跑的背景子 agent，會被一起收掉（3.4 表；有人接著看也照關是已經定的規則，`apps/eca/README.md:16`）。
4. **畫面判錯**。socket 名跟著小格真實路徑變，`XDG_RUNTIME_DIR` 有沒有設也會讓兩邊算出不同的夾。新模型裡身體換位置是常態，畫面的身分要掛在不變的東西上（名字，或 persist 的位置）。
5. **身體放記憶體時**：`live.jsonl` 只接不清（2.3 末的數字），會一直吃記憶體；`mcp.json` 可能有金鑰，`/tmp` 預設那塊要開成只有自己進得去（`9p-proc-1125.md` 已提）。
6. **eca 有兩個收件口**。`queue/`：送進去就是對話裡的一輪。`mailbox/`：信，腦自己決定何時讀。今天 `aos-agent say` 對停著的 eca 也照樣排進 queue。新模型的「活著走 socket、掛了寄信箱」跟這兩個口怎麼對，見 `05-信與IPC現況.md`、`20-送訊息兩條路的細節.md`。
7. **現成那條 socket 的經驗**：它不回話，寫進去得不到任何回應，aos 靠 hook 另外寫回執檔；閒著 30 秒沒回執就當這版不吃、整個畫面退回貼字；對方忙的時候無限等（`wf/ws/eca-aos/eca-aos-core/report-1124-bgmail.md`）；信封是 Claude Code 沒寫進文件的內部字樣，改版就壞。它跟「寫了有回應」的那種 socket 不是同一種。
8. **sleep 打斷一輪**：信已經收了、沒有回答、不重答；`letters.json` 裡那幾封會一直掛在 pending（讀程式推的：只有丟例外那條路會把它們改記成 failed，被訊號打死走不到）。
9. **pause 期間 on_clock 不跑**：人在畫面上繼續用，`context_wrap` 也不會叫它收尾，只剩 Claude Code 自己的自動壓縮。
10. **兩個帳號夾共用一個工作區**：登入、額度、`claude mcp add` 設的 MCP 各看各的；`cli.json` 的 `claude_mcp` 讀的是「這次起的那隻 claude 的帳號夾」。
11. **`--on-busy yield`**：有人接在畫面上、而且信只能用貼的時，這輪退讓、信留在 `queue/cur`。status 的 `turn` 要分得出「在等人離開畫面」。

## 5. 要問使用者的

**第 1 題：Claude Code 的對話檔在帳號資料夾，aos 的 persist 要不要管它？**

- a. 不管。persist 只放地址與 aos 自己的抄本；對話接不上就開新的，但保證前情一定送得進去（補 3.3 的第 2、3 項）。
- b. persist 另存一份對話檔（每輪或停下時抄），換帳號夾、換位置時抄回去再 `--resume`。
- c. 每隻 eca 一個自己的帳號資料夾，放在 persist 裡。

推薦 a。理由：這次事故敗在前情沒送進去，不是敗在對話檔搬不動；b 靠的是 Claude Code 的內部檔案格式，抄過去能不能續我沒驗（見第 6 節）；c 每隻都要登入一次。

**第 2 題：帳號資料夾算誰的設定？**

- a. 寫進 proc 自己的 `settings`，loop 與畫面都照它，開畫面那個殼設什麼都不算。
- b. 照現在：誰起它就用誰的環境，要另一個帳號就用 `eca-claude-alt` 範本的兩份 `.env`。

推薦 a。理由：這次事故的直接原因就是 loop 與畫面各看各的環境變數。

**第 3 題：對 eca 下 stop，是等這輪答完，還是現在就停？**

- a. 照現在：答完才停，等的時候 status 顯示 stopping；pause 只停送信，不凍住 Claude。
- b. stop 改成現在就收，答到一半那批算掉。
- c. 兩個字都給：`stop` 照現在；另加一個字（名字待定）＝打斷這一輪，`-p` 整群收、畫面送中斷鍵，但這隻不停。

推薦 c。理由：兩種需求都真的有，現在想打斷只能用 sleep，連 loop 一起收，而且背景任務沒人收。

**第 4 題：畫面（tmux 裡那隻長命的 Claude）在新模型算什麼？**

- a. 算 eca 身體的一部分：loop 停，畫面當場一起收。
- b. 算 eca 底下的一個子 proc：eca 自己多一個 `procs` 夾（像一台小 daemon），畫面有自己的目錄、自己的 status。
- c. 照現在：不算 proc，只是給人看的窗，停下後延後關；status 多報一行畫面開沒開。

推薦先 c、留路給 b。理由：a 會推翻 11-14 定的延後關畫面（`py/aos/apps/agent/ctl/phase.py:157`）；b 最合「daemon 是橋、底下有 procs 夾」的形狀，也剛好解掉畫面 socket 該掛在誰的 PID 底下，但要先有 daemon 那套才做得動。

**第 5 題：token 那個檔，報哪幾個數字？**

- a. 只報 context 現在多滿（現成）。
- b. 再加這段對話的累計 token 與估的金額（`-p` 那條現成；畫面那條要自己加總）。
- c. 再加帳號額度（七天視窗用了幾成、何時重置；只有 `-p` 那條看得到，而且是整個帳號共用的，不是這一隻的）。

推薦 b。理由：原話是「消耗量」；c 那個數字屬於帳號，掛在每隻 proc 底下會讓十隻報同一個數，比較像某個 kernel 該報的。

## 6. 沒查到／沒把握的

- **把對話檔抄到另一個帳號夾能不能 `--resume`**：沒試。要叫真的模型，還要寫進使用者的帳號資料夾，超出這次只讀的範圍。最小驗法：在暫存工作區用甲帳號 `claude -p --session-id X` 講一句 → 把 `projects/<夾>/X.jsonl` 抄到乙帳號同名夾 → 乙帳號 `claude -p --resume X` 問它上一句是什麼。
- **Claude Code 多久清一次舊對話**：程式註解只說會清。我記得預設 30 天、可用 `cleanupPeriodDays` 調（憑記憶，沒查證）。
- **`-p` 的累計值含不含中間在畫面上講的那幾輪**：只驗了連續 `-p` 會累計。
- **sleep 時 claude 開的背景任務會不會變孤兒**：讀程式推的，沒實測。
- **到期關畫面不看忙不忙**、**`ctl ls` 忙碌欄看不到 eca**：都是讀程式得到的，沒實跑。
- **往 `claude -p` 的那條 messaging socket 投信行不行**：沒試。
- **codex 身**：只順帶提，沒有逐檔查；pi 身只查了對話檔放哪。
- `aos-eca-turn` 自己站在哪個夾：沒抓到正在跑的，寫的是承襲 loop 的。
- agent-fsm 與 eca 共用的那些檔（`queue/`、`history.jsonl`、`letters.json`、`cooldown.json`、`goal.json`、`hookeds/`）在 agent-fsm 那邊的細節，見 `03-agent-fsm身體與stack現況.md`；aos-loop 的窗見 `01-aos-loop現況.md`。

我做過、貼近只讀邊線的事，一併交代：對活樹的六個畫面 socket 各跑過一次 `tmux has-session`（只查詢）；讀了 `/proc/<PID>/environ` 裡指定的幾個變數；讀了兩個帳號資料夾裡三份對話檔的行數、時間戳與長度，沒有抄內容。沒叫任何 aos 指令，沒留背景行程；暫存檔四支都在 `~/.aos/scratch/aos-proc-arch-1125/04/`。
