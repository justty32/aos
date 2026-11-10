11-10 晚（家機）今晚多了什麼、怎麼玩：每支新指令與給腦的新工具一兩行＋照抄例子，連到整合驗收與試驗場刷新。

← [2026-11-10](../README.md)

# 今晚多了什麼、怎麼玩（11-10 晚，家機）

**一句話**：agent 現在能**看、改自己**（工具、腦設定、對話、hook、狀態、停自己）、能**互相寄信**、能**被時鐘定時叫醒**、能**生子 agent 並調它**、能**讀寫純 JSON 的記憶庫**。給人打的指令有五支新的（或新子命令），給腦的工具十五支，兩種範本（agent-fsm、eca-claude）都預設登記好了。整棵從零起過一遍，假腦十五支全過、gemma 和 haiku 各叫七支都對（[02 整合驗收](02-整合驗收.md)）。

| 檔 | 內容 |
|---|---|
| 本頁 | 每支一兩行＋照抄例子 |
| [02 整合驗收](02-整合驗收.md) | 從零起一棵、十五支各叫一次的結果、接縫、修了什麼、沒修的 |
| [03 試驗場刷新](03-試驗場刷新.md) | 把 `~/code/playground` 換成最新版的一段照抄（先備份；**還沒對原件跑，你看過再決定**） |

## 先準備一棵（照抄）

不想動試驗場的話，在任何空夾起一棵新的（跟 [json-memory 07](../json-memory/07-怎麼玩與刷新試驗場.md) 同一套）：

```sh
export AOS_HOME=~/repo/simple_tools/aos/proto8
for v in $(env | grep -oE '^(CLAUDE[A-Z_]*|AI_AGENT)=' | tr -d =); do unset $v; done   # 要起 eca 才需要
mkdir -p ~/play && cd ~/play && mkdir -p llms something
cp -r $AOS_HOME/kernel/llm-kernel llms/def
aos-json set --str 'llms/def/kernel.json#/endpoints/stupid-fast/model' google/gemma-4-e4b
cp -r $AOS_HOME/templates/daemon-root something/defs
cp -r $AOS_HOME/templates/agent-fsm something/defs/ann
echo '{"model": "stupid-fast"}' > something/defs/ann/llm.json      # 鍵是 model（舊的 endpoint 不認了）；不寫＝假腦
(cd llms && aos-exec --stack stacks/llm def &)
cd something && (aos-exec --stack stacks/root defs > ../root.log 2>&1 &)
aos-agent -d stacks/root ctl add -w . defs/ann
```

之後所有例子都在 `~/play/something` 裡打。**跟 agent 說話的固定兩行**（fsm、eca 都一樣，下面只寫引號裡那句）：

```sh
aos-agent -d stacks/root -t ann say "（一句話）" && aos-agent -d stacks/root -t ann listen
```

eca 那隻：`cp -r $AOS_HOME/templates/eca-claude defs/eb && echo '{"model": "haiku"}' > defs/eb/llm.json && mkdir -p ecaws && aos-agent -d stacks/root ctl add -n eb -w ecaws defs/eb`，然後把上面兩行的 `ann` 換成 `eb`。收工：`aos-daemon-ctl -d stacks/root shutdown && aos-daemon-ctl -d ../llms/stacks/llm shutdown`。

## 給腦的工具（十五支，範本預設登記）

腦自己決定要不要叫；你只要在題目裡講你要什麼。括號裡是腦送的參數長相。

| 工具 | 做什麼 | 照抄一句（fsm、eca 都能用） |
|---|---|---|
| **self_tools** | 看、加、拿掉自己的工具（`{"op":"ls"}`、`{"op":"add","name":"math","path":"…"}`） | `"List your tools, names only."` |
| **self_llm** | 看、改自己的腦設定（`{"op":"set","settings":{"temperature":0.2}}`） | `"Set your temperature to 0.2, then show your brain settings."` |
| **self_history** | 看、刪、摘要、改自己的對話（正在答的這一步鎖著不能動） | `"Summarize your first 4 messages into one line."` |
| **self_hook** | 某件事發生時（工具前後、信進 queue…）自動跑一支程式 | `"Add a hook named log that runs /abs/path/my_hook after every tool call."` |
| **self_state** | 看自己：不給＝十類各一行總覽（who、state、tools、llm、hooks、history、mailbox、children、resources、time）；`parts` 點菜 | `"How many messages are in your history and how many letters wait for you?"` |
| **self_ctl** | 停、暫停、睡、拔掉自己（`stop`／`pause`／`sleep`／`rm`） | `"Pause yourself."`（之後要你 `aos-agent -d stacks/root ctl resume ann`） |
| **mailbox_peek** | 看自己信箱有幾封、誰寄的，不拿走 | `"Do you have any letters?"` |
| **mailbox_read** | 讀最舊一封，預設讀完就刪（`keep` 留在 archive） | `"Read your oldest letter and do what it asks."` |
| **mailbox_send** | 照 inbox 協議寄信（給名字或信箱路徑；六種 STATUS） | `"Send bob a REQUEST titled 'add' asking what 6*7 is."` |
| **clock_register** | 登記「每 N 個 cycle 寄我一封固定的信」＝定時叫醒（不給 box＝寄自己） | `"Every 5 cycles, remind yourself to tell the time."` |
| **agents_children** | 生子 agent 並管它：add、ask、say／listen、stop／start、pause、sleep、rm，還能調子的 tools／llm／history／hook；配額預設 4（`children.json`） | `"Start a child named kid from the agent-fsm template and ask it what time it is."` |
| **agents_ctl** | `aos-agent ctl` 的純包裝，對表上任何一隻、成不成看權限、不記帳 | `"List all agents on your daemon."` |
| **agent_def** | 複製範本成新定義（`template: "agent-fsm"` 短名）、檢查定義合不合格 | `"Copy the agent-fsm template to defs/helper and check it."` |
| **memory** | 讀純 JSON 記憶庫（ls、read、find） | `"Search the memory for DaemonMissing and tell me in one sentence what it means."` |
| **memory_write** | 寫記憶庫（add／set／rm）；**不預設登記**，要手加一格並指一個可寫的庫（出廠那份別寫） | `"Remember in the memory that Amy likes tea."` |

**工具分包**（11-10 深夜 tool-packs）：上面這些加上通用工具，現在一包一包登記，清單在 `proto8/lib/packs/`。小工具 gadgets（**peek_clock** 看 daemon 時鐘第幾 cycle、**peek_now_time** 看 UTC 時間〔舊名 wall_clock〕、math）、事件（clock_register、self_hook）、自我管理（self_*）、子 agent（agents_children、agents_ctl）、定義（agent_def、tools_def）、信箱（mailbox_*）、記憶（memory_read、memory_write）——兩個範本都開；通用四包（看／改／刪／殼）只有 agent-fsm 開。fsm 34 支、eca 19 支。關一包＝從定義 `tools.json` 的 `$override` 串拿掉那一項；看某支從哪包來＝`aos-agent -d stacks/root tools -t ann ls -l` 的 FROM 欄。照抄：`"What cycle is the daemon clock at?"`（叫 peek_clock）。

<details><summary>memory_write 怎麼加（照抄）</summary>

```sh
cp -r $AOS_HOME/knowledge/aos ~/play/kb
cd defs/ann
aos-tools add --replace -n memory --envs AOS_MEMORY=$HOME/play/kb --path-json '{"$env":"AOS_HOME","$path":"/lib/agent/memory"}'
aos-tools add -n memory_write --envs AOS_MEMORY=$HOME/play/kb --path-json '{"$env":"AOS_HOME","$path":"/lib/agent/memory_write"}'
cd ../..
```

已經在跑的那隻不想動定義：把 `aos-tools add` 換成 `aos-agent -d stacks/root -t ann tools add …`（同樣的旗標），下一題生效。

</details>

<details><summary>叫了什麼去哪看</summary>

- fsm：`stacks/root/procs/ann/history.jsonl`（每則 tool 呼叫與結果）；或 `aos-agent -d stacks/root history -t ann ls`。
- eca：`stacks/root/procs/eb/claude/live.jsonl` 裡的 `tool_use`（名字是 `mcp__aos__<工具>`）。
- 整體：`aos-agent -d stacks/root ctl state -t ann`（十類總覽）。

</details>

## 給人打的指令

| 指令 | 做什麼 | 照抄 |
|---|---|---|
| `aos-agent tools` | 看、加、拿掉某隻的工具（寫進它 stack 的覆蓋層，不動定義） | `aos-agent -d stacks/root tools -t ann ls` |
| `aos-agent llm` | 看、改某隻的腦設定（ls／set／rm／reset） | `aos-agent -d stacks/root llm -t ann set temperature=0.2` |
| `aos-agent history` | 看、刪、摘要、改某隻的對話；原文預設搬到 stack 的 `history_removed.jsonl` | `aos-agent -d stacks/root history -t ann ls` |
| `aos-agent hook` | 給某隻掛 hook | `aos-agent -d stacks/root hook -t ann add --on tool_after -n log ./my_hook`（`my_hook`＝你自己寫的一支程式） |
| `aos-agent ctl state` | 十類總覽；給類別＝細節；`all`；`-j` | `aos-agent -d stacks/root ctl state -t ann history mailbox` |
| `aos-mailbox` | 你自己也有信箱（預設 `~/.stack/mailbox`）：寄信給 agent、看、讀回信 | `aos-mailbox send --to ann -d stacks/root --status REQUEST --title hi "What is 6*7?"`，之後 `aos-mailbox peek`、`aos-mailbox read` |
| `aos-clock-register` | 時鐘每 N 個 cycle 寄一封固定的信到某個信箱（例如 agent 的 queue） | `aos-clock-register -c stacks/root/clock add --every 10 --box stacks/root/procs/ann/queue tick "Tell me the time."`（時鐘檔＝根 `.env` 的 `AOS_CLOCK`，範本是 `stacks/root/clock`；agent 被刪時它登記的項不會自動消失，要手動 `rm`） |

<details><summary>小模型（gemma）要注意的</summary>

- **寫不出 `$` 開頭的鍵**：`{"$env": …}` 這種寫法 gemma 會寫壞。生子 agent 用 `agent_def` 的 `template` 短名；`self_tools`、`self_hook` 的 `path_json` 也是 `$` 鍵——題目裡直接給一般路徑（絕對路徑或從工作區算的相對路徑）。
- **工具說明很大，LM Studio 的 context 長度要開夠**：十五支 tooldef 實送約 7 200 tokens（28 748 字元），加 fsm 的 system 約 850，再加對話；`self_tools ls` 一次約 10 000 tokens（使用者回來後已裁改成只列名字＋一句，施工中）。使用者口徑：「小模型裝不下說明，那就是去把lm studio那邊調整一下。真的裝不下的，那就代表這個小模型不適合aos體系，或是只能作爲普通的aos函數。」——在 LM Studio 載模型時把 context 開到至少 16k（家機 gemma 實際載 71 936，沒問題）。
- gemma 會照抄 tooldef 例子的內容（例如 mailbox_send 的 `what`），叫完工具常答空字串——真腦常態。

</details>

<details><summary>eca 要注意的</summary>

- llm.json 寫 `{"model": "haiku"}`；預算看 `cli.json` 的 `print_flags`。
- 起根的殼要先拿掉 `CLAUDE*`、`AI_AGENT`（上面第二行），不然 daemon 底下的 claude 會跟你自己的 Claude Code 混在一起。
- history 隊回報過：**全新工作區第一次開 eca 畫面時，claude 可能停在「信不信任這個資料夾」選單**，題目被打進選單、畫面就關了。今晚整合驗收沒碰到（eca 走 `-p` 一次一輪）。碰到的話：先在那個工作區手動開一次 `claude`、選信任，再讓 agent 接手。

</details>

<details><summary>舊東西換了名字（你手上的舊定義要改）</summary>

- `llm.json` 的 `endpoint` 鍵改成 `model`。
- 舊的 `agents` 工具拆成 `agents_children`、`agents_ctl`、`agent_def` 三支；配額設定檔 `agents.json` 改名 `children.json`；舊帳（`tools/agents/children.json`）不讀。
- 記憶庫改純 JSON 樹（`_index.json` 表、資料夾簡介在 `_description.json`）；舊的 `.md` 節點不認。
- 舊定義沒有今晚的新工具：整份重抄範本最省事（[03 試驗場刷新](03-試驗場刷新.md) 就是這樣做）。

</details>

<details><summary>使用者回來後裁的、正在改的（tonight-rulings）</summary>

- `self_tools` 的 ls 預設只列名字＋一句說明，細項用 get。
- hook 的「改結果」預設改成開（選項名之後可能再改）。
- 人的信箱 stack 環境變數 `AOS_MY_STACK` 改名 `AOS_LINUX_USER_STACK`。
- 範本夾的 `tests/` 搬到範本外。
- `aos-clock register …` 等同 `aos-clock-register …`。
- `aos-agent history summarize` 寫進去的那則改成 `aos: …` 固定格式。

- 再一批（通用工具包，`proto8/thinking/2026-11/10/tool-packs/`）：`lib/base` 的 `bash`→`shell`、`json_edit`→`json_write`、新 `remove`，拿掉「只能動工作區內」；分四包（看／改／刪／殼）範本預設全開，預設工具從 15 支變 30 支上下；`memory` 改名 `memory_read`、`memory_write` 也預設登記，庫指到 `$AOS_HOME/knowledge`（節點路徑前面多一段 `aos/`）。
- hook 的選項與事件改名定案（event、handler、condition、intercept〔預設開〕、async、on_error；before_queue、after_queue、before_tool、after_tool）；`memory_write` 的 add 可以不給 value。
- 各指令的旗標可以寫在所屬那層名字之後的任何位置，`aos-agent ctl stop ann` 這種目標放最後也收。

施工完以前，上面例子照現況寫；施工後以 `proto8/thinking/2026-11/10/tonight-rulings/` 為準。

</details>

## 各線的細節與代定

| 線 | 結果與代定在哪 |
|---|---|
| self-tools（tools／llm、self_tools、self_llm、不認得的鍵報錯） | [self-tools](../self-tools/README.md)（代定在 README、[05](../self-tools/05-llm設定改名與ls.md)） |
| json-memory（memory、memory_write） | [json-memory 05](../json-memory/05-步驟與代定.md)、[07 怎麼玩](../json-memory/07-怎麼玩與刷新試驗場.md) |
| self-family（history、self_history、self_state、self_ctl） | [01](../self-family/01-施工結果.md)、[03](../self-family/03-self_state與self_ctl施工結果.md) |
| hook（aos-agent hook、self_hook） | [hook 01 圖紙](../self-family/hook/01-圖紙.md)、[02 施工結果](../self-family/hook/02-施工結果.md) |
| agents-split（三支） | [agents-split README](../agents-split/README.md)、[03 驗收](../agents-split/03-驗收結果.md) |
| mailbox | [01 設計](../mailbox/01-設計.md)、[02 施工結果](../mailbox/02-施工結果.md) |
| clock-letters | [README](../clock-letters/README.md)、[01 施工結果](../clock-letters/01-施工結果.md) |
