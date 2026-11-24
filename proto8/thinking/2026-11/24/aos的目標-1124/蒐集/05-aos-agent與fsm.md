# 05 aos agent 與 fsm（蒐集隊員報告）

範圍：只讀 repo。說法標 **[讀到]**（有檔案行號）或 **[推測]**。路徑都在 `/home/lorkhan/repo/aos/` 底下，下文省略開頭。`P` = `proto8`。

術語先說一句：
- **定義夾（definition）**：一個資料夾，裡面是 agent 的「原始碼」。
- **stack**：一隻 agent 跑起來之後的狀態夾（記憶、history、信箱）。
- **workspace（ws）**：agent 工作的那個資料夾，環境變數 `$AOS_WS`。
- **overlay（覆蓋層）**：stack 裡只放「跟定義不同的地方」的小檔。
- **cell（格）**：fsm 的一個狀態，跑一支程式。

## 一、現況

### 1.1 三者關係

- 官方心智模型一行：「daemon = hardware, stack = memory, workspace = external memory, definition = source code, kernel = where you send requests」。**[讀到]** `P/knowledge/aos/world.md:3`
- 表：stack = 一隻在跑的 proc 的 RAM（`$AOS_STACK`）；ws = 「the disk you work on; shared with other agents when they are given the same ws」；definition = 「the program's source code; running it makes an instance (a stack under a daemon)」。**[讀到]** `P/knowledge/aos/world.md:8-12`
- 「One definition can run as many instances. Each instance has its own stack. Changing a stack never changes the definition.」**[讀到]** `P/knowledge/aos/world.md:17`
- 掛上去的指令 `aos-agent ctl add XXX`：XXX 是定義夾；`-w` 指 ws（預設是 `$AOS_WS` 或目前目錄）；`-s` 指 stack（預設 `<daemon stack>/procs/<name>/`）。**[讀到]** `P/py/aos/apps/agent/ctl/add.py:19,36-37`
- ws 不存在就報 `WsMissing`。**[讀到]** `P/py/aos/apps/agent/ctl/add.py:157-160`
- 範本的 `_entry` 就是「把自己掛上 daemon」：`aos-agent ctl add $AOS_CD`，cwd 是 `$AOS_WS`。**[讀到]** `P/templates/agents/agent-fsm/_entry:1`
- 舊文件寫過另一個預設：eca 文件說 stack 預設 `<工作區>/.stack/`；`aos-exec` 文件也寫 `$AOS_WS/.stack/`（沒給 `--stack` 時）。**[讀到]** `P/templates/docs/01-eca-claude.md:59`、`P/cpp/aos-exec/docs/03-環境變數.md:9`。與上一條 `add` 的預設（`procs/<name>/`）是不同入口的預設，不矛盾，但容易搞混。**[推測]**

### 1.2 實例化：抄什麼、指什麼

結論：**定義夾不會被抄進 stack。** 跑的時候直接從定義夾跑，環境變數 `AOS_CD`（定義夾）指著它。stack 只收「這隻自己的東西」。

- 每格 argv 用 `{"$env": "AOS_CD"}` 或 `{"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/xxx.py"}` 寫，每次用到才解，解出來的值「不寫回任何檔」。**[讀到]** `P/templates/docs/02-agent-fsm.md:14`、`P/templates/agents/agent-fsm/fsm.json:4-10`
- 這是「動態連結」：四格程式（idle/brain/wait/act）不在定義夾，在 `$AOS_HOME/lib/aos/apps/agent_fsm/`，所有 agent-fsm 共用一份。11-24 剛從範本夾搬過去。**[讀到]** `P/py/aos/apps/agent_fsm/README.md:3-5,20`
- 要靜態（整份抄走）：把九個檔抄進定義夾、argv 改相對檔名。靜態的格仍經 `$AOS_HOME/lib` 載入 `aos.*`，lib 介面變了會壞。**[讀到]** `P/py/aos/apps/agent_fsm/README.md:22`
- 範本的工具清單：`tools.json` 用 `"$override"` 疊十一包（look、change、delete、shell、gadgets、todo、self、mailbox、goal、json、index），每包路徑都是 `{"$env":"AOS_HOME","$path":"/lib/packs/…"}`。**[讀到]** `P/templates/agents/agent-fsm/tools.json:1-12`
- 沒找到 symlink 的用法：範本與 `agent_def new` 都是 `cp -r`（「The copy is the folder as it is, like `cp -r`」）。有一個叫 `defs.extern` 的東西把某欄「編成一個連結指到你手寫的檔」，`agent_def check` 會查斷掉的連結。**[讀到]** `P/knowledge/aos/agents.md`（agent_def 段）、`P/templates/README.md`（agent-python 段）。這個「連結」是不是真 symlink：**沒查到實作，沒找到**。
- `$ref` 在 agent 範本的 json 本身沒用到（只在 README 與 `start-api/llm/kernel.json` 出現）；範本用的是 `$env`、`$path`、`$override`。**[讀到]**（grep `\$ref`，agents 下只有 README 命中）
- 掛上去之後，daemon 表記的 `exec`、`def`、`ws`、`stack`：絕對路徑原樣存，相對的存成相對 daemon stack；也可存成指示詞（`--ws-json`、`--stack-json`、`--path-json`）。**[讀到]** `P/py/aos/apps/agent/ctl/add.py:28-32,146-166`
- stack 裡有什麼：`history.jsonl`、`queue/`、`letters.json`、`tools.json`（差異）、`llm.json`（差異）、`system.txt`（整份）、`hookeds.json`、`subagents.json`、`mailbox/`、`observed.jsonl`、`tools/<名>/`。**[讀到]** `P/knowledge/aos/me.md`（What is in your stack）
- fsm 的「目前在哪一格」記在 `$AOS_STACK/stage.txt`。**[讀到]** `P/cpp/aos-fsm/README.md:7`

### 1.3 overlay 規則（stack 與定義怎麼疊）

| 檔 | stack 那份放什麼 | 用什麼改 |
|---|---|---|
| `tools.json` | 只放差異（拿掉的工具寫 null） | `self_tools` |
| `llm.json` | 只放改過的鍵 | `self_llm` |
| `system.txt` | 整份，取代定義的 | `self_system` |
| `hookeds.json` | 依名字（null＝關） | `self_hook` |
| `subagents.json` | 只放改過的鍵 | 人 |

出處 **[讀到]** `P/knowledge/aos/definition.md`（Your own copy (overlay)）。「`reset` 刪掉你那份，定義那份就又算數」同處。`interfaces.json`、`loop.json`、`fsm.json`、`cli.json` 等**沒有** overlay，要改只能做新定義（`agent_def`）。同處。

- brain 每格重讀「定義的 llm 疊 stack 的同路徑檔」「stack 有 system.txt 就整份用那份」「stack 有 tools 就用那份（`$override` 指回定義那份）」，所以改了「下一格／下一題」生效。**[讀到]** `P/py/aos/apps/agent_fsm/brain.py:5-14`

### 1.4 fsm 長怎樣

四格，`start: idle`，`aos-loop` 每 300 ms 叫 `aos-fsm` 跑一次「現在那格」。`aos-fsm` 一次只跑一格，退 0 才換格，物件型 `next` 照結束碼查。**[讀到]** `P/templates/agents/agent-fsm/fsm.json:1-11`、`loop.json:1`、`P/cpp/aos-fsm/README.md:7`

| 格 | 做什麼 | 結束碼 → 下一格 | 出處 |
|---|---|---|---|
| idle | 把 `queue/` 的信全收進 `history.jsonl`；沒信但最後是沒 tool_calls 的 assistant 且 goal 在，就丟一則 goal 提醒 | 0→think，10→idle | `idle.py:1-5,22-26`、`fsm.json:4-5` |
| think | 用 history + system + tools 組請求，寫 `think/request.json`，**不碰網路** | 0→wait，10→idle | `brain.py:1-3`、`fsm.json:6-7` |
| wait | 把請求寄給 llm kernel（信），每拍看回信到沒；到了就把 assistant 接進 history | 0→act，10→wait，11→think | `wait.py:1-14`、`fsm.json:8-9` |
| act | 依序呼叫工具，結果接進 history；`timeout_ms: 0` | 0→think，10→idle | `act.py:1-3`、`fsm.json:10-11` |

（路徑都在 `P/py/aos/apps/agent_fsm/`、`P/templates/agents/agent-fsm/`。）

- 問腦＝寄信給 llm kernel，不是直接連 API。**[讀到]** `P/templates/README.md`（agent-fsm 那句）、`wait.py:1-14`
- wait 遇到腦或 kernel 的錯會寫 `cooldown.json` 等 30 秒～30 分鐘；`aos-agent ctl retry` 刪掉它。**[讀到]** `P/py/aos/apps/agent/README.md`（ctl retry 段）
- hook 點：`before_queue/after_queue/before_tool/after_tool/brain_failed/tool_added/before_compact/after_compact` 等。**[讀到]** `P/py/tools/agent/self_hook/_tooldef.json`（description）

### 1.5 agent 怎麼改自己（`self_*` 工具）

這些工具都寫「自己 stack 裡的 overlay」，不寫定義。實作在 `P/py/tools/agent/<名>/`。

| 工具 | 能做什麼 | 範本預設有嗎 |
|---|---|---|
| `self_tools` | ls / get / add / rm / reset 自己的工具；「Changes work at once」 | 有 |
| `self_state` | 只讀：who、state、tools、llm、system、hooks、history、mailbox、subagents、resources、time | 有 |
| `self_llm` | ls / set / rm / reset 腦設定；「a broken model stops you, so ls first」 | **關（null）** |
| `self_system` | get / set（整份）/ reset；「each change costs one prompt-cache miss; a text that stops you working needs a human to reset it」 | **關** |
| `self_history` | ls / rm 一段 / summarize 一段 / set 一行；進行中的那步不能改 | **關** |
| `self_ctl` | stop / pause / sleep / rm（`purge` 連 stack 一起刪、無法復原） | **關** |
| `self_hook` | 在自己的事件上掛程式；在 `events` 包，不在 self 包 | **不在範本裡** |

- 範本把四支關掉：`"tools": {"self_llm": null, "self_system": null, "self_history": null, "self_ctl": null}`。**[讀到]** `P/templates/agents/agent-fsm/tools.json:12`
- `self_tools` 自己的說明寫了怎麼把被關的加回來（`add` 一個 `path_json`）。**[讀到]** `P/py/tools/agent/self_tools/_tooldef.json`
- 11-21 使用者選單決定 self 只留 `self_tools`、`self_state`，其餘改選掛。**[讀到]** `P/thinking/2026-11/21/tool-desc-瘦身-1121/README.md:30`
- 另外 `do_task`（把一個任務摺成摘要）算 self 一家，agent-fsm 才有。**[讀到]** `P/knowledge/aos/me.md`
- 「改 stack 裡的檔」：改自己 stack 的 overlay，用 `self_*`；history 不准手改，要用 `self_history`（它把刪掉的留在 `history_removed.jsonl`）。**[讀到]** `P/knowledge/aos/rules.md` 第 1、3 條
- 改了不影響定義夾、也不影響別隻共用同一定義的 agent。**[讀到]** `P/knowledge/aos/me.md`；有測試報告：「共用一個定義夾時，`tools add`、`system set` 只改自己的 stack，另一隻完全不受影響，而且會印『別人也用這份』的提醒」`P/thinking/2026-11/19/aos-base-audit-1119/隊員報告/e-upper.md:165`
- 想改定義：用 `agent_def`（`new` 複製、`tools`/`llm`/`system` 三個細 op、`check`）。「Editing a definition affects every agent that uses it.」**[讀到]** `P/knowledge/aos/agents.md`（New definitions: agent_def）

### 1.6 agent-fsm 與 eca-claude 的差別

| | agent-fsm | eca-claude |
|---|---|---|
| 入口 | `_entry`＝`aos-agent ctl add`；`body.json`＝`aos-loop loop.json` | `_entry`＝`["aos-loop","loop.json"]` |
| 一拍跑什麼 | `loop.json` 的 `exec: fsm.json` → 四格 | `loop.json` 的 `exec` 是 `aos-eca-turn --on-empty idle --on-busy yield $AOS_CD`（一支程式，整批一輪） |
| 有 `fsm.json` 嗎 | 有 | **沒有**（目錄裡沒這個檔） |
| 腦 | llm kernel（寄信）| 外部 CLI（`cli.json` 的 `kind: claude`，Read/Write/Edit/Bash/Agent/Skill，`--permission-mode dontAsk`）|
| 暫停粒度 | 一格 | 一批信（CLI 是黑盒） |
| `tools.json` | 十一包 | 五包，tools 經 aos-mcp 給 CLI 用 |
| 畫面 | 無 | 有 `screen/` |

出處 **[讀到]** `P/templates/agents/agent-fsm/{_entry,body.json,loop.json,fsm.json}`、`P/templates/agents/eca-claude/{_entry,loop.json,cli.json,tools.json}`、`P/thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md`（「兩邊一樣」「兩邊不一樣」兩張表）。

**eca-claude 是不是把 Claude Code 包成 aos proc？是。** README 第一句：「Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.」`P/templates/agents/eca-claude/README.md:1`。**還算 fsm 嗎？** 從檔案看不算：沒有 fsm.json、沒有狀態表，狀態機在 Claude Code 裡面（對 aos 是黑盒）。**[讀到]**（無 fsm.json）+ **[推測]**（「不算」是我的判讀；文件沒有用這個詞裁定）。兩者「對外同形」：`_entry`＝aos-loop、queue / history / ctl / state、同一份 `tools.json`。**[讀到]** `P/templates/README.md`（前言段）

其他範本：`agent-python`（用一支 `agent.py` 編出定義的檔；不給 fsm 時可先複製 eca-claude/eca-pi）、`eca-pi`、`eca-claude-alt`（第二個 Claude 帳號）、`reviewer`（重用 agent-fsm 的格）、`kits`（配給包，不是範本）。**[讀到]** `P/templates/README.md`

### 1.7 workspace 的定義 vs「第一個可訪問的外部記憶體位置」

- 知識庫入口：「workspace (ws): the folder you work on (your external memory). Yours is `$AOS_WS`. Paths you give to tools are relative to it.」**[讀到]** `P/knowledge/aos/_description.md:11`
- 「外部記憶體」這個比喻 **對得上**（world.md 同樣說 workspace = external memory）。
- 「第一個可訪問」：ws 是**掛上去時指定的那一個**資料夾，工具的相對路徑從它算。但它**不是唯一可及的**：規則寫「File tools also take absolute paths and do not stop you at the workspace edge: what you can reach is what your Linux user can」。**[讀到]** `P/knowledge/aos/rules.md`（Always 段）。所以「第一個」可以讀成「起點」，不是「圍欄」。**[推測]**（使用者那句是否有意當圍欄，原話沒說）
- ws 可被多隻共用（world.md 同一格）；沒找到把 ws 當存取控制邊界的實作。

## 二、以前說過什麼

1. 使用者 11-24 口述（原話）：「這不必多說，就是 fsm，一個簡單的東西。」「其核心可以想成是一個 source code，也就是一坨定義好的資料夾；然後指定他要被實例化到哪（stack），指定其第一個可訪問的外部記憶體位置（workspace），然後讓他成爲 aos proc，讓他去跑。」「一方面是爲了承接先前的架構；另一方面也是讓這個 agent 回歸原始本質，輕量化；同時也讓 agent 好修改自身。」「當然，這會有些缺點，這個之後再說。」（上半是代寫整理版，兩邊對不上以原話為準）`wf/user/advice/20261124.md:43-54`；原話整段在同檔 `:72` 之後。
2. 使用者 11-05 午（逐字）：「讓agent給自己改tool」。當時定「改的對象＝自己的覆蓋層，定義永遠不動」，並寫下：「**同一隻跑久了行為會跟定義漂移**」，`ctl state` 順手多印一行覆蓋層改了多少。`P/thinking/2026-11/05/feat-proto/01-self-tools.md:3,8,38-39`（C-46 條文；「定義＝函數本體」）。
3. 使用者 11-10 晚 agents-split（逐字，引在別檔）：「第二塊：同樣拆兩塊，一個創造或修改定義，一個改自身。啥定義都可改，只要有權限，包括改自身定義。粗細的話，先做粗的，細的之後慢慢添加」。`P/thinking/2026-11/12/agent-def-fine-lineage.md:9`
4. 使用者 11-19（逐字）：「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」「程式持續增長...當然跟C和.o沒關係，.o也可以在運行途中給自己加lib啊。」`P/thinking/2026-11/19/aos-inherit-1119/00-使用者原話.md`（「相關的定調」段）
5. 使用者 11-23（引在文件裡）：「3.a」＝把 agent-fsm 的四格程式搬出 templates、放進 lib；使用者 11-20「起手範本確實該改成要借的」。`P/py/aos/apps/agent_fsm/README.md:5`、`P/templates/README.md`（start-api 段）
6. 使用者 11-10：「copy-out能刪就刪」→ 範本改成「複製出去，路徑指回 `$AOS_HOME`」。`P/templates/README.md`（templates-cp 段）
7. 使用者 11-21 選單（tool-desc 瘦身）：self 只留 `self_tools`、`self_state`。`P/thinking/2026-11/21/tool-desc-瘦身-1121/README.md:30`
8. 使用者 11-04：「這個好了之後，就可以綜合eca和這個的特性，弄出統一的aos-agent介面」（引在 eca 對照文件）。`P/thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md:5`

## 三、差距

1. **「就是 fsm」vs eca 兩個身。** eca-claude / eca-pi 沒有 fsm.json，狀態機不在 aos 裡。使用者說「aos agent 就是 fsm」，現況是「對外同形的兩種身體，只有一種是 fsm」。證據：`P/templates/agents/eca-claude/` 無 `fsm.json`；`loop.json:1`。**[讀到]**
2. **「定義夾＝一坨資料夾＝source code」vs 現況其實把 fsm 程式搬到 lib。** 四格程式不在定義夾，在 `$AOS_HOME/lib/…`，共用一份。定義夾只剩 `fsm.json` 的表與設定。要靜態才抄進來。證據：`P/py/aos/apps/agent_fsm/README.md:3-5`。**[讀到]** 副作用：lib 升級會一起影響所有 agent（見四）。
3. **「指定要被實例化到哪」：沒有真的實例化動作。** 沒有把定義抄進 stack；實例＝daemon 表上一列（name、def、ws、stack）＋ stack 夾。證據：`add.py:191-195`、`world.md:17`。**[讀到]**
4. **「讓 agent 好修改自身」vs 範本預設關掉大部分。** 預設只有 `self_tools`、`self_state`；改腦、改 system、改 history、自停、掛 hook 都要先自己 `self_tools add`。證據：`tools.json:12`、`me.md`（“An agent-fsm made from the stock template starts with…”）。**[讀到]** 另外「改自己」只改 overlay；fsm.json、loop.json、interfaces.json 沒有 overlay，agent 改不了自己的**狀態表**，只能 `agent_def new` 做新定義。證據：`definition.md`（overlay 表末句）。**[讀到]**（這一條與「fsm 可以自改」的直覺有落差，**[推測]**）
5. **規則 vs 強制。** 知識庫規定「Never edit a definition by hand」，但同一份文件承認「The rules above are kept by you, not by the system」，agent 與人同一個 Linux 帳號，file tools 不會被擋在 ws 邊。證據：`rules.md`（Never 1、What does not enforce）。**[讀到]**
6. **ws「第一個可訪問」。** 實作上 ws 是起點與相對路徑基準，沒找到邊界。見 1.7。**[讀到]/[推測]**
7. **預設 stack 位置兩套說法。** `<ws>/.stack/`（aos-exec、eca 文件）vs `<daemon stack>/procs/<name>/`（`ctl add`）。證據同 1.1。**[讀到]**
8. **「第一個」可被撤換：** 沒找到執行中換 ws 的工具（`ctl set-def` 保留同一 ws、stack）。證據：`P/py/aos/apps/agent/README.md`（set-def 段）。**[讀到]**；「沒有」**[推測]**（只查了這一處）。

## 四、已知的缺點與沒解的問題

使用者原話只說「這會有些缺點，這個之後再說」（`wf/user/advice/20261124.md:54`），沒列。下面是我從 repo 讀到的、與這題相關的已記載風險，**不是使用者列的清單**。

1. **自改搞壞自己，要人救。** `self_llm`：「a broken model stops you」；`self_system`：「a text that stops you working needs a human to reset it」；tools 檔被刪＝整隻停 `stopped`＋`reason`，人 `tools reset` 再 `ctl start`。`P/py/tools/agent/self_{llm,system}/_tooldef.json`、`P/thinking/2026-11/05/feat-proto/01-self-tools.md`（「改壞了怎麼救」）。**[讀到]**
2. **每次改 system / 加工具都讓對話快取失效。** `self_system`：「each change costs one prompt-cache miss」；tool-desc 瘦身那串就是因為 self 工具太肥。`P/thinking/2026-11/21/tool-desc-瘦身-1121/README.md:30`。**[讀到]**
3. **stack 與定義漂移。** 同一份定義跑久了，stack 的 overlay 可能與定義差很多。已有的緩解：`ctl state` 的 tools 行（`own: N listed, M set to null …`）、共用定義時印提醒；「定義改了照疊」。`P/py/aos/apps/agent/ctl/state.py:344-366`、`P/py/aos/apps/agent/docs/02-已知限制.md` 末條、`P/docs/CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md:22`。沒找到「把 overlay 合併回定義」的動作。**[讀到]/沒找到**
4. **改定義影響所有共用者。** `agent_def` 直接改定義夾＝每隻用它的 agent 都變。`agents.md`（Rules 末條）。**[讀到]**
5. **動態連結的代價。** 四格在 lib，改 `py/` 要重跑 `install.py` 才生效（AGENTS.md 第 3 行），所有 agent 同時吃到；靜態抄走的格在 lib 介面變時會壞。`P/py/aos/apps/agent_fsm/README.md:22`。**[讀到]**
6. **改名/搬動斷連結。** 範本的相對路徑「leads out of the folder 則複製後可能指向別處」；`agent_def check` 把斷掉的連結算一個問題。`agents.md`（New definitions 的 Rules）。**[讀到]**
7. **沒有強制的權限邊界。** 見差距 5。aos「assumes one person and models that person trusts」。`rules.md`。**[讀到]**
8. **eca 身的自改範圍更窄且權限全開。** eca 範本 Bash/Write/Edit 沒人按確認；aos hook 看不到 CLI 自己的工具；擋閘「擋得住順手就做了，擋不住存心繞過（腦有 Bash 與 Write，改得到這個檔）」。`P/templates/agents/eca-claude/README.md`（權限段）。**[讀到]**
9. **未知。** 使用者「之後再說」的缺點具體是哪幾條：**沒找到**他列過。上面八條是 repo 內相關已記載風險，不要當成他指的那些。

## 觀察（非建議）

- 「fsm」目前是 agent-fsm 的四格＋一張 json 表；使用者說的「一個簡單的東西」與 `idle.py` 一個檔就近 400 行、`wait.py` 近 650 行的規模，看起來有距離。**[觀察]**（行數 `wc -l`）
- 「定義夾 / stack / workspace」三者在文件裡的用語很一致，但「實例化」一詞沒有對應的單一指令；最接近的是 `aos-agent ctl add`。**[觀察]**
