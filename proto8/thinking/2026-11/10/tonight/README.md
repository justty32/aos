11-10 晚（家機）今晚多了什麼、怎麼玩：每支新指令與給腦的新工具一兩行＋照抄例子，連到整合驗收與試驗場刷新。

← [2026-11-10](../README.md)

# 今晚多了什麼、怎麼玩（11-10 晚，家機）

**一句話**：agent 現在能**看、改自己**（工具、腦設定、對話、hook、狀態、停自己）、能**互相寄信**、能**被時鐘定時叫醒**、能**生子 agent 並調它**、能**讀寫純 JSON 的知識庫**（knowledge_read／knowledge_write）、能**自己做一支新工具並馬上用**（tools_def＋self_tools，同一輪生效）。給人打的指令有五支新的（或新子命令）；給腦的工具分十一包共 34 支，**兩種範本（agent-fsm、eca-claude）都十一包全開**。第一輪從零起一棵驗過（[02](02-整合驗收.md)），最後一輪用最終名字再驗一次（[04](04-最後一輪整合驗收.md)）。

| 檔 | 內容 |
|---|---|
| 本頁 | 每支一兩行＋照抄例子 |
| [02 整合驗收](02-整合驗收.md) | 從零起一棵、十五支各叫一次的結果、接縫、修了什麼、沒修的 |
| [03 試驗場刷新](03-試驗場刷新.md) | 把 `~/code/playground` 換成最新版的一段照抄；11-10 22:15 對原件跑過一次（備份 `~/code/playground.bak-1110-2215`）；**之後的改名（knowledge_*）原件還沒跟上，要再刷一次**，腳本已更新、在複本上跑過 |
| [04 最後一輪整合驗收](04-最後一輪整合驗收.md) | 改名與列表短版之後從零再起一棵：兩範本工具清單與 token、假腦全工具、gemma 補驗、haiku 抽驗 |

## 直接玩試驗場（已刷新好，照抄）

`~/code/playground` 11-10 22:15 刷新過：員工 `fsm_ann`（34 支工具、十一包）、`eca_bob`（haiku，當時 19 支），stack 都是空的。根表 `_clock llm_kernel daemon _sweeper`，員工掛在領班（`ws/.stack`）。**注意：那次刷新在 memory→knowledge 改名之前**，原件裡的定義還指舊名 `memory_*`、`lib/` 也是舊的——先照 [03](03-試驗場刷新.md) 再刷一次（會清掉 stack、對話、信箱；保留 gemma／haiku 設定），之後 fsm_ann、eca_bob 都是 34 支。

```sh
cd ~/code/playground && source env.sh && unset AOS_DAEMON
setsid nohup aos-exec root > root.log 2>&1 < /dev/null &                   # 起根（背景）
cd ws && aos-daemon-ctl ping --timeout-s 30                                  # 領班回 replied 就好
aos-exec ../agents/fsm_ann && aos-agent ctl add --name eca_bob ../agents/eca_bob
aos-agent llm --target fsm_ann set model=stupid-fast                         # 用 gemma（不打＝假腦）
aos-agent say --target fsm_ann "what time is it?" && aos-agent listen --target fsm_ann --timeout-s 180
aos-agent say --target eca_bob "How many tools do you have? Use self_state." && aos-agent listen --target eca_bob --timeout-s 180
aos-daemon-ctl -d "$PG/.stack" shutdown                                      # 收工
```

下面各表的「照抄一句」放進 `say --target fsm_ann "…"` 就行（試驗場用 `--target`，不用 `-d stacks/root -t`）。知識庫＝試驗場的 `knowledge/`（`AOS_KNOWLEDGE` 指它），下次刷新會被換掉。

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

## 給腦的工具（十一包 34 支，兩範本都預設全開）

腦自己決定要不要叫；你只要在題目裡講你要什麼。括號裡是腦送的參數長相。下表是今晚新的那些；通用四包（看 read ls view stat json_read、改 write edit copy move mkdir json_write、刪 trash remove、殼 shell run_python）和小工具（peek_now_time、peek_clock、math）見表下。

| 工具 | 做什麼 | 照抄一句（fsm、eca 都能用） |
|---|---|---|
| **self_tools** | 看、加、拿掉自己的工具（`{"op":"ls"}` 預設只列名字＋一句說明、`{"op":"get"}` 看細項、`{"op":"add","path":"…"}`）；**加了同一輪就能叫** | `"List your tools, names only."` |
| **self_llm** | 看、改自己的腦設定（`{"op":"set","settings":{"temperature":0.2}}`） | `"Set your temperature to 0.2, then show your brain settings."` |
| **self_history** | 看、刪、摘要、改自己的對話（正在答的這一步鎖著不能動）；ls 預設只給最後 20 則（`"all":true` 全部） | `"Summarize your first 4 messages into one line."` |
| **self_hook** | 某件事發生時自動跑一支程式；事件 `before_queue`、`after_queue`、`before_tool`、`after_tool`，選項 `event`、`handler`、`condition`、`intercept`（預設開＝能改結果）、`async`、`on_error` | `"Add a hook named log that runs /abs/path/my_hook after every tool call."` |
| **self_state** | 看自己：不給＝十類各一行總覽（who、state、tools、llm、hooks、history、mailbox、children、resources、time）；`parts` 點菜 | `"How many messages are in your history and how many letters wait for you?"` |
| **self_ctl** | 停、暫停、睡、拔掉自己（`stop`／`pause`／`sleep`／`rm`） | `"Pause yourself."`（之後要你 `aos-agent -d stacks/root ctl resume ann`） |
| **mailbox_peek** | 看自己信箱有幾封、誰寄的，不拿走 | `"Do you have any letters?"` |
| **mailbox_read** | 讀最舊一封，預設讀完就刪（`keep` 留在 archive） | `"Read your oldest letter and do what it asks."` |
| **mailbox_send** | 照 inbox 協議寄信（給名字或信箱路徑；六種 STATUS） | `"Send bob a REQUEST titled 'add' asking what 6*7 is."` |
| **clock_register** | 登記「每 N 個 cycle 寄我一封固定的信」＝定時叫醒（不給 box＝寄自己） | `"Every 5 cycles, remind yourself to tell the time."` |
| **agents_children** | 生子 agent 並管它：add、ask、say／listen、stop／start、pause、sleep、rm，還能調子的 tools／llm／history／hook；配額預設 4（`children.json`） | `"Start a child named kid from the agent-fsm template and ask it what time it is."` |
| **agents_ctl** | `aos-agent ctl` 的純包裝，對表上任何一隻、成不成看權限、不記帳 | `"List all agents on your daemon."` |
| **agent_def** | 複製範本成新定義（`template: "agent-fsm"` 短名）、檢查定義合不合格 | `"Copy the agent-fsm template to defs/helper and check it."` |
| **tools_def** | 做新工具：`new` 從 Python 骨架抄一支、`check` 驗它（`path` 可以是夾或 `檔.json#/指標`）；做好用 self_tools add，同一輪就叫得到 | `"Make a tool my_tools/mul that multiplies a and b, check it, add it, then use it on 6 and 7."` |
| **knowledge_read** | 讀純 JSON 知識庫（ls、read、find；舊名 memory／memory_read） | `"Search the knowledge base for DaemonMissing and tell me in one sentence what it means."` |
| **knowledge_write** | 寫知識庫（add／set／rm）；add 不給 value＝只把已存在的檔登進表，不存在就報 NodeMissing，加 `"create":true` 建空檔 | `"Remember in the knowledge base that Amy likes tea."` |

**工具分包**：清單在 `proto8/lib/packs/`，十一包＝look、change、delete、shell、gadgets（**peek_clock** 看 daemon 時鐘第幾 cycle、**peek_now_time** 看 UTC 時間〔舊名 wall_clock〕、math）、events（clock_register、self_hook）、self（self_*）、children（agents_children、agents_ctl）、def（agent_def、tools_def）、mailbox（mailbox_*）、knowledge（knowledge_read、knowledge_write）。兩範本都全開（11-10 深夜起 eca 也開通用四包）。知識庫指 `$AOS_HOME/knowledge`（範本 `tools.json` 裡 `AOS_KNOWLEDGE` 那兩格），**別讓 agent 寫 repo 那份**——起一棵玩時先抄一份、改那兩格指過去。關一包＝從定義 `tools.json` 的 `$override` 串拿掉那一項；看某支從哪包來＝`aos-agent -d stacks/root tools -t ann ls -l` 的 FROM 欄（不加 `-l` 只印名字＋一句）。照抄：`"What cycle is the daemon clock at?"`（叫 peek_clock）。

<details><summary>知識庫指到自己的一份（照抄）</summary>

```sh
cp -r $AOS_HOME/knowledge ~/play/kb
aos-json set 'something/defs/ann/tools.json#/tools/knowledge_read/env/AOS_KNOWLEDGE' '"'$HOME'/play/kb"'
aos-json set 'something/defs/ann/tools.json#/tools/knowledge_write/env/AOS_KNOWLEDGE' '"'$HOME'/play/kb"'
```

改定義下一次起那隻才生效；已經在跑的用 `aos-agent -d stacks/root tools -t ann add --replace -n knowledge_write --envs AOS_KNOWLEDGE=$HOME/play/kb --path-json '{"$env":"AOS_HOME","$path":"/lib/agent/knowledge_write"}'`（read 同理），下一題生效。

</details>

<details><summary>叫了什麼去哪看</summary>

- fsm：`stacks/root/procs/ann/history.jsonl`（每則 tool 呼叫與結果）；或 `aos-agent -d stacks/root history -t ann ls`（預設最後 20 則，`-a` 全部）。
- eca：`stacks/root/procs/eb/claude/live.jsonl` 裡的 `tool_use`（名字是 `mcp__aos__<工具>`）。
- 整體：`aos-agent -d stacks/root ctl state -t ann`（十類總覽）。

</details>

## 給人打的指令

| 指令 | 做什麼 | 照抄 |
|---|---|---|
| `aos-agent tools` | 看、加、拿掉某隻的工具（寫進它 stack 的覆蓋層，不動定義）；ls 預設名字＋一句，`-l` 多 FROM 等欄，`--json` 全份 | `aos-agent -d stacks/root tools -t ann ls` |
| `aos-agent llm` | 看、改某隻的腦設定（ls／set／rm／reset） | `aos-agent -d stacks/root llm -t ann set temperature=0.2` |
| `aos-agent history` | 看、刪、摘要、改某隻的對話；原文預設搬到 stack 的 `history_removed.jsonl` | `aos-agent -d stacks/root history -t ann ls` |
| `aos-agent hook` | 給某隻掛 hook | `aos-agent -d stacks/root hook -t ann add --event after_tool -n log ./my_hook`（`my_hook`＝你自己寫的一支程式） |
| `aos-agent ctl state` | 十類總覽；給類別＝細節；`all`；`-j` | `aos-agent -d stacks/root ctl state -t ann history mailbox` |
| `aos-mailbox` | 你自己也有信箱（預設 `~/.stack/mailbox`）：寄信給 agent、看、讀回信 | `aos-mailbox send --to ann -d stacks/root --status REQUEST --title hi "What is 6*7?"`，之後 `aos-mailbox peek`、`aos-mailbox read` |
| `aos-clock-register` | 時鐘每 N 個 cycle 寄一封固定的信到某個信箱（例如 agent 的 queue） | `aos-clock-register -c stacks/root/clock add --every 10 --box stacks/root/procs/ann/queue tick "Tell me the time."`（時鐘檔＝根 `.env` 的 `AOS_CLOCK`，範本是 `stacks/root/clock`；`-d stacks/root` 也行；agent 被刪時它登記的項不會自動消失，要手動 `rm`；時鐘每 100 cycle 自己檢查一次登記檔） |

<details><summary>小模型（gemma）要注意的</summary>

- **寫不出 `$` 開頭的鍵**：`{"$env": …}` 這種寫法 gemma 會寫壞。生子 agent 用 `agent_def` 的 `template` 短名；`self_tools`、`self_hook` 的 `path_json` 也是 `$` 鍵——題目裡直接給一般路徑（絕對路徑或從工作區算的相對路徑）。
- **工具說明很大，LM Studio 的 context 長度要開夠**：分包後 fsm 34 支工具說明實送 47 181 字元（約 11 800 tokens；最後一輪改名、列表短版後量約 5 萬字元≈12 500 tokens）；eca 現在也是 34 支、同一組說明；試驗場 fsm_ann 實問時 LM Studio 回的 `prompt_tokens` 是 12 352～13 152（system＋知識庫根＋34 支說明＋短對話）。**context 至少開 32768**（需求約兩倍，留給對話與回答）。11-10 晚量的時候 LM Studio 載入 gemma-4-e4b 的 context 是 71 936（`lms ps` 看得到），夠，沒動；這個值也存成了該模型的預設（`~/.lmstudio/.internal/user-concrete-model-default-config/google/gemma-4-e4b.json` 的 `llm.load.contextLength`＝71814），重開 LM Studio 或閒置一小時被卸載後再自動載入照樣是它。要手動換值時照抄：`lms unload google/gemma-4-e4b && lms load google/gemma-4-e4b --context-length 32768`（`--context-length` 只管這次載入；要留成預設就在 LM Studio 的模型設定裡改）。使用者口徑：「小模型裝不下說明，那就是去把lm studio那邊調整一下。真的裝不下的，那就代表這個小模型不適合aos體系，或是只能作爲普通的aos函數。」
- gemma 會照抄 tooldef 例子的內容（例如 mailbox_send 的 `what`），叫完工具常答空字串——真腦常態。

</details>

<details><summary>eca 要注意的</summary>

- llm.json 寫 `{"model": "haiku"}`；預算看 `cli.json` 的 `print_flags`。
- 起根的殼要先拿掉 `CLAUDE*`、`AI_AGENT`（上面第二行），不然 daemon 底下的 claude 會跟你自己的 Claude Code 混在一起。
- **全新工作區第一次開 eca 畫面時，claude 可能停在「信不信任這個資料夾」選單**；現在 aos 會認出來、報 `TrustMissing` 而不是把題目打進選單。碰到的話：先在那個工作區手動開一次 `claude`、選信任，再讓 agent 接手（`-p` 一次一輪的走法不會碰到）。

</details>

<details><summary>舊東西換了名字（你手上的舊定義要改）</summary>

- `llm.json` 的 `endpoint` 鍵改成 `model`。
- 舊的 `agents` 工具拆成 `agents_children`、`agents_ctl`、`agent_def` 三支；配額設定檔 `agents.json` 改名 `children.json`；舊帳（`tools/agents/children.json`）不讀。
- 記憶庫改純 JSON 樹（`_index.json` 表、資料夾簡介在 `_description.json`）；舊的 `.md` 節點不認。
- **memory 整家改名 knowledge**：`memory_read／memory_write／memory_export／memory_sync`→`knowledge_*`、包 `lib/packs/memory.json`→`knowledge.json`、`AOS_MEMORY`→`AOS_KNOWLEDGE`、`_memory.json`→`_knowledge.json`、`MemoryMissing`→`KnowledgeMissing`、`--memory`→`--knowledge`（細節 [tonight-rulings 05](../tonight-rulings/05-knowledge改名.md)）。
- hook：`--on tool_after` 這類舊名→`--event after_tool`（事件 before_queue／after_queue／before_tool／after_tool）。
- 人的信箱 stack 變數 `AOS_MY_STACK`→`AOS_LINUX_USER_STACK`；`lib/base` 的 `bash`→`shell`、`json_edit`→`json_write`。
- 舊定義沒有今晚的新工具：整份重抄範本最省事（[03 試驗場刷新](03-試驗場刷新.md) 就是這樣做）。

</details>

<details><summary>使用者回來後裁的（tonight-rulings，都已施工）</summary>

- `self_tools` 的 ls 預設只列名字＋一句說明，細項用 get；`aos-agent tools ls` 一樣，`-l` 多 FROM 等欄。
- hook 改名定案（上面「舊東西換了名字」），`intercept` 預設開。
- `AOS_MY_STACK`→`AOS_LINUX_USER_STACK`；範本夾的 `tests/` 搬到範本外；`aos-clock register …`＝`aos-clock-register …`。
- aos 自己塞進對話的話一律 `[aos] 種類: 內容`（例：summarize 寫進去的那則、時鐘的信）。
- 通用工具包（[tool-packs](../tool-packs/01-施工結果.md)）、tools_def（[tools-def](../tools-def/README.md)）、self_tools 加減同一輪生效。
- memory 整家改名 knowledge（[05](../tonight-rulings/05-knowledge改名.md)）。
- 列表短版（[06](../tonight-rulings/06-列表長短四項.md)）：`lib/base` 的 ls 預設 `名字 TAB 種類`、history ls 預設最後 20 則、agents_children 的 long／json。
- 時鐘每 100 cycle 自檢登記檔、`aos-clock-register -d`；eca 卡在信任選單時報 `TrustMissing`。
- 各指令的旗標可以寫在所屬那層名字之後的任何位置，`aos-agent ctl stop ann` 這種目標放最後也收。

全部條目在 [tonight-rulings README](../tonight-rulings/README.md)。

</details>

## 各線的細節與代定

| 線 | 結果與代定在哪 |
|---|---|
| self-tools（tools／llm、self_tools、self_llm、不認得的鍵報錯） | [self-tools](../self-tools/README.md)（代定在 README、[05](../self-tools/05-llm設定改名與ls.md)） |
| json-memory（現名 knowledge_read、knowledge_write） | [json-memory 05](../json-memory/05-步驟與代定.md)、[07 怎麼玩](../json-memory/07-怎麼玩與刷新試驗場.md) |
| self-family（history、self_history、self_state、self_ctl） | [01](../self-family/01-施工結果.md)、[03](../self-family/03-self_state與self_ctl施工結果.md) |
| hook（aos-agent hook、self_hook） | [hook 01 圖紙](../self-family/hook/01-圖紙.md)、[02 施工結果](../self-family/hook/02-施工結果.md) |
| agents-split（三支） | [agents-split README](../agents-split/README.md)、[03 驗收](../agents-split/03-驗收結果.md) |
| mailbox | [01 設計](../mailbox/01-設計.md)、[02 施工結果](../mailbox/02-施工結果.md) |
| clock-letters | [README](../clock-letters/README.md)、[01 施工結果](../clock-letters/01-施工結果.md) |
