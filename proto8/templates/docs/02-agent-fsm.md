← [回入口 README.md](../README.md)｜段落：loop／fsm agent 範本 agent-fsm（11-04）｜上一份：[01-eca-claude](01-eca-claude.md)｜下一份：—

## loop／fsm agent 範本 agent-fsm（11-04）

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `llm.json`／`system.txt`／`tools.json` 就是另一隻（四支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`body.json` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；`_entry` 是「把自己掛上 daemon」（11-05，下面）；格是範本裡四支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../../thinking/2026-11/04/loop-fsm-agent/README.md)；問腦 11-04 晚改成寄信給 llm kernel：[think-as-function 03 § 1](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)；條文 P-11、P-19、P-35 的 11-04 註。

**複製出 repo**（11-10 templates-cp，使用者「copy-out能刪就刪」；copy-out 與 `lib/agent/copy_def.py` 當天刪掉）：開一隻新 agent 就 `cp -r`：

```sh
export AOS_HOME=$HOME/repo/aos-tools/proto8   # 每台設一次＝這台 proto8 的位置（改了值重起樹就生效；也可寫進根的 .env）
cp -r $AOS_HOME/templates/agent-fsm bob
```

範本裡指到範本外、落在 proto8 的路徑一律寫成 `{"$env": "AOS_HOME", "$path": "/…"}`（`tools.json` 的工具、`memory_read`／`memory_write` 兩格 `env` 裡的 `AOS_MEMORY`、reviewer 的 `fsm.json` 借 agent-fsm 的格、kernel 範本的 `handler` 與 `endpoints`、daemon.json／loop.json 的 argv），範本裡沒有捷徑；解出來的值不寫回任何檔，每次用到才由讀它的程式解。所以抄到哪、兩台各放哪，檔都一字不差，只要每台的 `AOS_HOME` 對。`AOS_HOME` 三種給法（使用者 11-10 午「要用相對位置、絕對位置、環境變數指定都可」）：

| 給法 | 寫在哪 | 這台要備好 |
|---|---|---|
| 殼裡 export | `export AOS_HOME=…` | 每台設一次 |
| 絕對 | 根 `.env` 那行註解換成 `AOS_HOME=/絕對路徑` | 每台把 proto8 放同一個位置（或在那裡放捷徑） |
| 相對 | 根 `.env` 寫 `AOS_HOME=${AOS_WS}/../aos/proto8`（`AOS_WS`＝起根時站的地方） | 每台同樣的相對擺法 |

殼裡 export 的贏過 `.env`（`.env` 只放預設）。根範本 `.env` 最後一行 `AOS_HOME=${AOS_HOME}`＝三種都沒給就在起根當下報 `aos-exec: error: DotenvBad bad .env: …/defs/.env line N`；agent 範本不帶 `.env`、從根繼承。沒有根、自己在殼裡打 `aos-tools call／ls` 時，那個殼要有 `AOS_HOME`，沒有就是 `DirectiveBad … AOS_HOME is not set`。

換台不用跑任何重建指令：備好 `AOS_HOME` 就直接起。`aos-agent tools add` 照使用者給的寫法存（絕對存絕對、相對存相對覆蓋層），要寫環境變數指示詞用 `aos-tools add --path-json`（[aos-tools](../../cmd/aos-tools/README.md)）。[`templates/tests/test_paths_move.py`](../tests/test_paths_move.py) 在 /tmp 跑三種給法各一輪「`cp -r` 起→問一題→shutdown→git 搬到另一個 HOME 與前綴（A 的 proto8 刪掉）→B 直接起→接著答」，加一輪同機改 `AOS_HOME`。

四支格找共用模組依序看自己的資料夾、自己的 realpath 往上找到的 repo `py/`／`lib/`、標準 `sys.path`（11-06 晚 K-5），抄出 repo 後靠第三條：先跑過 `install.sh`，讓 user site 的 `aos-proto8.pth` 帶入這份 repo 的兩個絕對路徑，或明給 `PYTHONPATH`（換了 `HOME` 就沒有 user site，要靠 `PYTHONPATH`）；介面宣告讀法共用 `lib/agent/agent_files.py`。範本的 `tests/`、`README.md` 會一起抄過去，`tests/` 可以刪。

改完整包（定義＋工作區＋llm kernel）`cp -a`／git 到別處照樣起得來：daemon 表存相對路徑、指到 proto8 的照 `AOS_HOME` 解，`AOS_LLM_KERNEL` 照根 `.env` 的預設（`${AOS_WS}/../llms/stacks/llm`）或在殼裡換成新位置。

```
agent-fsm/
  _entry       {"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}（單子，沒 +x；11-05：aos-exec 這個資料夾＝掛上 daemon）
  body.json    ["aos-loop", "loop.json"]（身體的入口；interfaces.json 的 entry 指它，aos-agent ctl add 掛的是它）
  loop.json    {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}（沒有 max：常駐，靠 ctl 的 stop 收工）
  fsm.json     四格：idle {"0": "think", "10": "idle"}、think（brain.py --system system.txt --memory memory_read）{"0": "wait", "10": "idle"}、
               wait {"0": "act", "10": "wait", "11": "think"}、act（timeout_ms: 1800000）{"0": "think", "10": "idle"}；start: idle
  idle.py      收信：$AOS_STACK/queue/ 全部收進 history.jsonl（接進去就 aos-post done）；有好信退 0、沒有退 10；[--prompt FILE] 開場白
  brain.py     組請求、不碰網路：history（＋system、tools）→ $AOS_STACK/think/request.json（llm kernel 請求信的 body）；退 0；沒事做退 10
  wait.py      寄與收：沒寄＝aos-llm send --reply-to $AOS_STACK/think/reply、名字記進 think/pending.txt、退 10；
               已寄＝aos-llm recv：沒到退 10（loop 照跑）、到了那則 assistant 接進 history 退 0、kernel 回錯退 1（send 失敗＝冷卻、warning、退 10 等）；沒 pending 且請求不在、或寄之前腦設定與請求對不上、請求比 history 舊（最後一則對不上，或 history.jsonl 比 request.json 新＝寄之前被人改過，11-10 self-family）＝退 11 回 think 重組；
               等回信不設期限，寄出（pending.txt 的 mtime）每滿 10 分鐘印一行 agent-fsm: warning、照樣等（記在 think/wait_warned.txt，11-10 坑-74）
  act.py       跑工具：逐個 aos-tools call，照 metainfo 限時；失敗附 stderr 尾，結果各接一則 tool、退 0；沒有 tool_calls（最後答案）退 10
  system.txt   system 訊息（brain.py 的 --system 指到它；每次從檔讀、不存進 history；11-05 晚改英文）
  tools.json   aos-tools 登記檔：幾乎只剩 `"$override"` 一串 [lib/packs](../../lib/packs/README.md) 十一包——通用四包 look、change、delete、shell（15 支，11-10 tool-packs 預設全開），再加七包 gadgets（peek_clock、peek_now_time、math）、events（clock_register、self_hook）、self（self_tools、self_llm、self_state、self_ctl、self_history）、children（agents_children、agents_ctl）、def（agent_def、tools_def）、mailbox（mailbox_peek／read／send）、memory（memory_read、memory_write），共 34 支（11-10 深夜使用者「照包砍」「2.都開吧」）；自己只寫 memory_read、memory_write 兩格的 `env.AOS_MEMORY`（指 `knowledge/`）；關法見範本 README；這隻自己加減的在 $AOS_STACK/ 下同一宣告路徑（此範本宣告 tools.json；覆蓋層，aos-agent tools）
  llm.json     腦設定：{}＝用 kernel 的預設代號；model＝kernel 的 endpoint 包代號（例 "smart-high"；寄信時填進 body 的 endpoint 欄，真正的模型名固定在包上）；
               另認與快取無關的調整鍵 temperature、top_p、max_tokens、seed、presence_penalty、frequency_penalty、stop（放進 request；包的 fixed 照舊蓋過）；
               認哪些鍵寫在 interfaces.json 的 llm_keys（aos-agent llm set 對著提醒，11-10 晚）
  interfaces.json  {"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json", "llm_keys": [model 與七個調整鍵], "history": "history.jsonl", "hooks": "hooks.json"}, "aos-observed": {"file": "observed.jsonl"}}（沒有 screen；11-10 templates-cp 拿掉 memory 鍵與 tools/ 包裝夾）
  children.json  工具 agents_children 的配額設定 {"max_children": 4}（這隻最多同時生幾隻；stack 裡的 children.json 只放改過的鍵＝這隻的覆蓋；誰是我生的另記在 stack 的 tools/agents_children/children.json）
```

**記憶與自稱**（11-07 批 2；11-10 templates-cp 改）：知識庫位置寫在 `tools.json` 的 `memory_read`、`memory_write` 兩格：`"env": {"AOS_MEMORY": {"$env": "AOS_HOME", "$path": "/knowledge"}}`（11-10 深夜起指 `knowledge/` 這一層，根列 `aos/`；工具本身沒有預設位置，沒指定＝`MemoryMissing`、brain.py 開場安靜不帶根）；換庫改這個值。`interfaces.json` 不再宣告 `memory`（`lib/aos/defs` 依它分群，沒宣告＝`memory: null`）。範本 `_metainfo.json` 的 `summary` 與 README 首行一致，`cost.time_ms: 30000` 是估時、`resource: ["llm"]` 是資源；範本本身未宣告頂層 `timeout_ms`。

**覆蓋層位置**（11-06 K-6）：brain／wait 的腦設定、brain／act 的工具登記檔都讀 `interfaces.json` 的 `aos-agent.llm`／`tools` 宣告；定義與 stack 使用同一相對路徑。改成 `cfg/brain.json`、`cfg/my_tools.json` 時，身體與 `aos-agent llm／tools` 讀寫的是同一份，沒有寫死 `llm.json`／`tools.json`。未宣告 tools／llm 就沒有工具／腦設定，不去猜檔名。brain／act 的 `--tools` 明給檔案時照旗標，不套 tools 介面覆蓋層。

**腦＝llm kernel**：think 不自己打端點，wait 把請求寄進 `$AOS_LLM_KERNEL/requests/`（`AOS_LLM_KERNEL`＝[llm kernel](../../kernel/docs/01-llm-kernel.md) 那台 daemon 的 stack，由人設）、之後一拍一拍收回信；寄完 loop 照跑，等回信的期間 `pause`／`stop` 每拍都生效。端點、模型、金鑰都在 kernel 的 `kernel.json`（代號表），agent 只寫代號。範本的 `llm.json` 是 `{}`＝不寫 `endpoint`、用 kernel 的預設（範本 kernel 預設是假腦 `fake`：有工具就先叫 peek_now_time〔包寫 `"tool": "peek_now_time"`；沒有 peek_now_time 就叫第一個〕、再答一句「FAKE ANSWER to: …」），本機沒開 LM Studio 也跑得動。**要真腦**：`llm.json` 寫 `{"endpoint": "stupid-fast"}`（LM Studio 開在 localhost:1234）或 `smart-high`／`luna`／`sol`（LiteLLM），代號要是 kernel 的 `endpoints` 表裡有的（`aos-llm ls` 列出來，[03](../../kernel/docs/01-llm-kernel.md)）；正在跑的那隻只改它自己的就好：`aos-agent llm set endpoint=stupid-fast`（只存改過的鍵、下一題生效、`reset` 回定義）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp）；brain／act 讀的是「定義裡宣告的 tools 登記檔，；`$AOS_STACK/` 下同一宣告路徑有這隻自己那份時改用它（它 `$override` 定義那份，疊法歸 aos-tools，11-10）」（此範本宣告 `tools.json`）（aos-agent `tools add／rm` 只存差異，11-05，[aos-agent docs/03](../../cmd/aos-agent/docs/03-tools覆蓋層.md#tools-覆蓋層)），brain（memory_read 那次）與 act 只傳自己的 stack，小格 `$AOS_STACK/tools/<名>/` 由 aos-tools call 統一算；工具退非 0、逾時、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。act 用同一次 `aos-tools ls --json` 的 `metainfo.timeout_ms`（純數或 `{"val": N}`，單位毫秒）當各工具逾時，沒寫＝不設限；工具自成一群，逾時整群 TERM，2 秒後 KILL（群長先退也收掉群內孫行程）。退非 0 的結果保留 stdout 與結束碼；逾時結果保留已印的 stdout，再加一行 `(tool <名> timed out (N s); its process group was killed)`。兩種失敗的尾巴再附 `stderr (last 2048 bytes at most):` 與該次 stderr 最後 2 KB；成功時不附。這是**比照 aos-mcp 的 C-52／C-53 明文例外**（J4 任務授權；條文由 J7 補），stderr 全文照樣轉印到 act 自己的 stderr。**知識庫**（11-05 晚，[agent-knowledge 03](../../thinking/2026-11/05/agent-knowledge/03-接進agent與工具說明.md)）：think 格的 `--memory memory_read`＝每次組請求前叫一次登記名 `memory_read` 的工具 `{"op": "read"}`，印出來的根（`knowledge/` 的簡介＋目錄，第一格 `aos/`、叫腦先讀它）接在 `system.txt` 後面、同一則 system 訊息；腦要更深的自己叫 `memory_read`。這隻用 `aos-agent tools rm memory_read` 拿掉＝也不帶根；工具沒被指定庫（回 `MemoryMissing`）＝安靜不帶根、不印 warning（11-10 深夜 tool-packs）；叫壞了（起不來、退非 0、30 秒沒叫完）＝`agent-fsm: warning: … asking the brain without the knowledge base` 一行，system 裡改放一句 `Knowledge base is not available right now: <原因>`，照樣問腦、狀態不壞（11-10 TS，two-machines 07 K01；原本是 `MemoryFailed` 停下）。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。stack 裡多一格 `think/`：`request.json`（可重建的這次請求，image 不存）、`pending.txt`（寄出去還沒收的信件名稱）、`reply/`（回信信箱）、`wait_warned.txt`（11-10 坑-74：一個整數＝等這封已提醒到第幾個 10 分鐘；寄新信、收掉回信時刪，brain／idle 不看它）。**等太久只提醒**（坑-74 使用者裁選項 A）：wait 不判失敗、不設期限；從寄出起每滿 10 分鐘 stderr 一行 `agent-fsm: warning: no reply from the brain for 11 minutes to letter <信件名> (llm kernel: <AOS_LLM_KERNEL>); still waiting`，照樣退 10 繼續等（kernel 沒開最常見）。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-fsm／aos-post／aos-llm-kernel／aos-llm、proto8/cmd/aos-tools/bin 的 aos-tools
# 先起 llm kernel 那台 daemon（見 kernel/docs/01-llm-kernel），把它的 stack export 成 AOS_LLM_KERNEL
mkdir -p /tmp/k && (cd /tmp/k && aos-exec --stack . ~/repo/simple_tools/aos/proto8/kernel/llm-kernel &)
export AOS_LLM_KERNEL=/tmp/k
aos-exec --ws ~/proj proto8/templates/agent-fsm/body.json & # 直接跑（不掛 daemon）：stack＝~/proj/.stack/；說話用 aos-post send --ordered ~/proj/.stack/queue
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

# 掛 daemon（AOS_DAEMON＝daemon 的 $AOS_STACK，沒設＝cwd 的 ./.stack；daemon 的環境要有上面的 PATH 與 AOS_LLM_KERNEL；PATH 再加 cmd/aos-agent/bin 的 aos-agent）
# 先起一台跑 agent 的 daemon（同 kernel/docs/03 件 1；它的環境帶著 AOS_LLM_KERNEL，子項才寄得到）：
echo '{"interval_ms": 300}' > ~/daemon.json && mkdir -p ~/proj/.stack
(cd ~ && AOS_STACK=~/proj/.stack/ aos-daemon daemon.json &) && cd ~/proj   # cwd 有 .stack＝aos-agent 找得到這台
aos-agent ctl add --ws ~/proj --name fsm1 proto8/templates/agent-fsm
# 或（11-05）：cd ~/proj && aos-exec <定義資料夾>  ＝跑它的 _entry＝aos-agent ctl add <定義資料夾>（ws＝~/proj、名字＝資料夾名）
export AOS_AGENT=fsm1        # 之後不用每次 --target
aos-agent say 現在幾點 && aos-agent listen
aos-agent ctl pause          # 停在格與格之間；新信留 queue/new/
aos-agent ctl resume         # ctl 下也有 stop／start、sleep／wake（同一個 stack 接著對話）、rm fsm1；頂層另有 chat、tools、llm
```

- **`aos-exec 這個資料夾`＝掛上 daemon**（11-05 [portable-flow 題 4](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)，使用者「介面維持 aos-agent add」）：`_entry` 是一張單子 `aos-agent ctl add <AOS_CD>`、`cwd` 換回 `AOS_WS`（aos-exec 跑入口前會 cd 進定義資料夾，所以要換回來；`AOS_WS`＝`--ws` ＞ 外面的 `$AOS_WS` ＞ 呼叫當下的 cwd）。所以 `cd ws && aos-exec ../agents/bob`＝`aos-agent ctl add --ws ws ../agents/bob`，daemon 用 `ws/.stack` 的（`AOS_DAEMON` 沒設時）。身體的入口另放 `body.json`，`interfaces.json` 用 `entry` 宣告它，`aos-agent ctl add` 掛的是它、表上的 `def` 照樣是定義資料夾。旁支：aos-exec 跑這張單子時新建的空 `.stack/` 跑完會收回（本來就在的不動；11-05）；`aos-exec 資料夾 參數…` 的參數接在 argv 尾巴、ctl add 不收——要 `--name` 等就直接打 `aos-agent ctl add`。不接 daemon、直接跑身體＝`aos-exec body.json`。可翻案：放另一個資料夾程式（例 `up/`）、或回到「`_entry`＝身體」。

- **停著等 vs 射後不理**寫在表上：範本 idle 的 `next` 接住 10＝queue 空就停著等（loop 隔 `interval_ms` 再看）。射後不理＝複製一份，idle 的 `next` 改成字串 `"think"`（10 到 loop＝收工）；`loop.json` 的 `interval_ms` 要留著（11-04 晚起 wait 靠它一拍一拍看回信，拿掉＝空轉）；要開場白就在 idle 的 argv 加 `"--prompt", "prompt.txt"`（相對這個資料夾；history 空、queue 沒好信時投一次）。
- **思考中來的信**留在 `queue/new/`，答完回 idle 才收、跟那批一起答（使用者 11-04「等答完回 idle 再收」）。
- **暫停時改 history**：`pause` 之後用 `aos-agent history -t 名字 ls／rm／summarize／set` 改（11-10 self-family；原文搬到 stack 裡 `history_removed.jsonl`；直接改 `history.jsonl` 也行），要它重答就把 `stage.txt` 寫成 `think` 再 `resume`；不 pause 也能改：還沒寄出去的請求，wait 看到 history 比 request 新就退 11 重組；已經寄出去的不追，回信照樣接在改過的 history 後面。agent 自己改用 `self_history`（正在進行的這一步鎖著）；brain 每次從頭讀，改了就生效（寫新請求時順手刪 `think/pending.txt`，wait 重寄）。最後一則已是答案時 brain 不組請求、退 10 回 idle。
- **hook**（11-10 晚 [self-family/hook](../../thinking/2026-11/10/self-family/hook/README.md)）：`interfaces.json` 宣告 `"hooks": "hooks.json"`，定義那份疊 stack 那份（同名蓋過、null 關掉），每次事件重讀。四格的觸發點：idle＝`before_queue`（好信進 history 之前，可改 `content`／攔下丟掉）、`after_queue`；think（brain）＝`tool_added`（工具清單多了名字）；act＝`before_tool`（可改 `arguments`／攔下不跑）、`after_tool`（可改 `content`）；wait＝`brain_failed`（`BrainFailed`／`SendFailed`／`ReplyBad`）。hook 失敗而 `on_error: stop`＝那格 `agent-fsm: error: HookFailed …` 退 1、停下等人；清單壞＝`HooksBad`。人用 `aos-agent hook`、agent 自己用 `self_hook`；全文 [aos-agent docs/06](../../cmd/aos-agent/docs/06-hook.md)。
- **image 醒在 wait 格**：有 `think/pending.txt` 就繼續收原回信，即使 `think/request.json` 不在也不重寄；沒 pending 且 request 不在＝wait 退 11，沿既有 FSM 轉移回 think，brain 從 history＋目前定義／覆蓋層重組，再到 wait 寄出。image 可以擋 `think/request.json`；`pending.txt`、`think/reply/new/`／`cur/` 仍必須帶走。
- **kernel 停著**：信留在 kernel 信箱的 `new/`，`stage.txt` 停在 `async`、每拍退 10 一直等；kernel 起來就接著答。kernel 回錯（`EndpointFailed`、`BudgetMissing`…）＝wait 退 1、stderr 先是 aos-llm 的 `aos-llm: error: 代號 原因`、再一行 wait 自己的 `agent-fsm: error: BrainFailed aos-llm recv exited 1 (its reason is above)`，loop 停下等人；修好再起，wait 看到沒 pending、`request.json` 還在＝重寄；寄之前比對 `request.json` 的 endpoint 跟現在的 llm.json（定義疊 stack），對不上（人改了或刪了 llm.json）＝退 11 回 think、brain 重組再寄（11-05 edge-agent；原本要手動把 `stage.txt` 寫成 `think`）。
- **wait 自己認的三種殘留**（11-10 TS）：① 有 pending 而 `think/reply/` 缺 `tmp`／`new`／`cur`（clone 後空資料夾不在 git）＝recv 前先 `aos-post init`；② recv 說還沒回、`AOS_LLM_KERNEL` 解得到資料夾（相對＝從 `$AOS_DAEMON` 算，同 aos-llm）而那封信不在 `<kernel>/requests/new/`、`cur/`＝再收一次，還是沒有＝刪 `pending.txt`、印 `agent-fsm: warning: the letter <名> is no longer queued at the llm kernel <路徑>; sending the request again`、下一拍重寄（kernel 那邊只讀不寫；`AOS_LLM_KERNEL` 沒設或解不到＝照舊等）；③ 正要寄時 `request.json` 的 messages 最後一則跟 `history.jsonl` 最後一則不一樣（JSON 正規化後比；請求是從比較舊的 history 組的，例 `git reset` 後留下的）＝退 11 回 think 重組、不寄。另外平常每拍用 `aos-llm recv --quiet`（不印「為什麼還沒回」，免得每拍一行），只有要印 10 分鐘提醒的那一拍不帶，讓 aos-llm 把原因印在提醒那行前面。
- **失敗後冷卻**（11-10 [two-machines 06](../../thinking/2026-11/10/two-machines/06-長跑自動重起.md)，使用者裁「失敗後冷卻」）：wait 遇到外面服務的錯——`BrainFailed`（kernel 回錯）、`SendFailed`（`aos-llm send` 退非 0）——先寫 `$AOS_STACK/cooldown.json`（`lib/agent/cooldown.py`；`failures`、`until`、`at`、`code`、`reason`，`dropped` 一直是 0：重寄同一份請求、不掉信；間隔 30 秒、1、2、4、8、15、30 分鐘，之後固定 30 分鐘，用牆上時鐘），再看是哪一種：`BrainFailed` 照舊退 1；`SendFailed`（11-10 TS，使用者「如果llms那邊我沒開aos daemon，那就是我自己的問題，但我也希望他不要搞壞」）改成印一行 `agent-fsm: warning: aos-llm send exited N (its reason is above); the request stays and is sent again …`、**退 10 留在 wait、不停**——**改了 P-20 在這個情況的行為：kernel 不在＝等它來，不停下**，有沒有 `--auto-restart` 都一樣。寫冷卻時 `AOS_LLM_KERNEL` 解不到資料夾，`reason` 尾巴記 `(llm kernel folder not found)`；之後冷卻中而 `AOS_LLM_KERNEL` 已解得到資料夾＝當作到了、立刻寄（不用等滿 30 分鐘）。冷卻寫不成只多一行 `agent-fsm: warning`、結果照舊。下一次走到「沒 pending、`request.json` 在、endpoint 對得上、正要寄」時：冷卻中＝不寄、退 10 留在 wait（每拍再看）；到了或沒有＝照寄。好的回信接進 history 後刪 `cooldown.json`。`ReplyBad`、`WriteFailed` 這類不是外面服務的錯，不寫冷卻。`BrainFailed` 時，用 [`aos-agent ctl add --auto-restart`](../../cmd/aos-agent/README.md) 掛的：退 1 → daemon 重起 → 在冷卻裡活過 3 秒，不會被三次判停，冷卻到了自己重寄（端點修好就恢復）。沒開的：照舊退 1、表上 `stopped` 停著等人，只是多一個 `cooldown.json` 說明原因；人修好後 `ctl start`，若還在冷卻中，它會在 wait 等到冷卻到期才寄（急的話刪掉 `cooldown.json`）。
- **錯**：stderr 一行 `agent-fsm: error: 代號 原因`、退 1、loop 停下等人（P-20；四格的開頭都是 agent 名 `agent-fsm`，stdio-unify R15）——`SendFailed`（只剩 aos-llm 起不來、或 send 退 0 卻沒印信件名稱；send 退非 0 改成 warning＋等，見上一條）、`BrainFailed`（kernel 回錯）、`ReplyBad`、`CfgBad`（`llm.json` 讀不懂）、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`、`FlagUnknown`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起從停的那格接著做：直接跑的＝`aos-exec` 同一個工作區；掛 daemon 的＝那隻退 1 時留在表上 `stopped`＋`reason`（11-05 使用者裁「留表標 stopped (Recommended)」）；修好後 `aos-agent llm reset`／`tools reset`（或直接改 stack 裡那份）再 `aos-agent ctl start`，同一個 stack 從停的那格接著做；不要了 `aos-agent ctl rm`（`ctl ls`／`ctl state` 看得到原因）。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。idle／brain／wait 的下層 stderr 原樣透出；act 接住工具的 stderr、叫完後原樣轉印，只有失敗時另附尾巴給腦（上述例外）。工具退非 0 不是錯：act 把結果回給腦、stderr 多一行提醒 `agent-fsm: warning: tool <名> exit code N (passed back to the brain)`、照樣退 0。四格的旗標都走 `aos_flags.parse(help=HELP)`：`--help`／`-h` 印英文用法；帶值旗標可寫 `--x V` 或 `--x=V`，空值／缺值＝`ArgumentsBad`，未知旗標＝`agent-fsm: error: FlagUnknown unknown flag --bogus`。`--` 結束旗標，四格不收位置參數，所以其後還有字＝`ArgumentsBad`；help 也只在旗標位置生效。重複旗標取末值，但任一次空值仍報錯。Ctrl-C 退 130；act 收到 Ctrl-C／TERM（退 143）也先整群 TERM、2 秒後 KILL 並回收工具，不留下半則 tool 訊息。

**任務上下文與工具煞車**（11-07 P4）：brain 的 `--history full|task` 預設 `full`，照舊帶完整 history；`task` 只帶最後一封 user 起的訊息，system 照常放最前面，磁碟 history 不裁切。沒有 user 時帶目前全部訊息。`--max-tool-calls N` 接非負整數，按最後一封 user 起的 assistant `tool_calls` 條目總數計算；滿 N 次後，下一次 request 不提供 tools。`0` 從第一個 request 就不提供 tools；未給不限制；同一批多個呼叫照常執行，這個選項只控制下一次請求。兩個旗標互相獨立，在 `fsm.json` 的 brain argv 加上即可。

**實際成本觀測**（11-07 P5）：wait 用 `aos-llm recv --full` 收完整回信，只把原有 `message` 接入 history，額外欄位不混進對話。每次收到成功或失敗回覆，往 `$AOS_STACK/observed.jsonl` 追加 `{kind: "think", letter, endpoint, model, usage, elapsed_ms}`；`letter` 是寄出時 `aos-llm send` 回的信件名（保存在 `think/pending.txt`），與接收該請求的 kernel `ledger.jsonl` 的 `id` 為同一個字串，可直接對帳。`think/sent.json` 記寄出前的時間與 endpoint，耗時包含排隊與逐拍收信等待。endpoint 優先用回信欄位、否則用寄出時保存的請求代號；請求未指定且回信沒帶時為 null，不猜 kernel 預設。失敗回覆或未提供的 model／usage 為 null。舊 pending 沒有時間檔時耗時為 null 並提醒。act 每次實際啟動工具追加 `{kind: "tool", name, def, stack, child?, code, elapsed_ms, in_bytes, out_bytes}`，bytes 是原始 UTF-8 stdin 與 stdout，不含 stderr／附加錯誤說明；code 是子程序原始結束碼（訊號為負數）。重跑時已回覆的工具不重記，未啟動的錯誤（未登記／arguments 壞）沒有實際呼叫觀測。這些觀測寫失敗只印英文 warning，不改格的結果。

共用記帳由 `lib/observed.py` 處理：首寫先補 `self` 行，含 `def`（`AOS_CD`）、`ws`（`AOS_WS`）、UTC 毫秒 `started_at`，設了 `AOS_LLM_KERNEL` 才帶 `llm_kernel`；同時合併 stack 的 `aos-observed` 宣告。工具行的 `def` 是登記路徑的絕對值、`stack` 是相對本 stack 的小格；有子帳時 `child` 指向收子前保存的帳本，相對本 stack。thought／agents_children 只照子 stack 的公開介面抄整棵帳，不猜帳名。

**長跑與知識寫入**：長時間接不同任務的 fsm，在 `fsm.json` 的 think 格、`brain.py` 的 argv 加 `"--history", "task"`，每次只把最後一封 user 起的任務帶給腦，避免舊任務一直累積進請求；磁碟 history 仍完整保留。需要跨任務記住的穩定知識另寫入知識庫。範本預設登記 `memory_read` 與 `memory_write`（11-10 深夜 tool-packs），兩格 `env.AOS_MEMORY` 都指 `{"$env": "AOS_HOME", "$path": "/knowledge"}`＝repo 的 `knowledge/`（使用者「指knowledge/」）：照範本跑，agent 寫了就改到它。要寫自己的庫：改兩格的 `env.AOS_MEMORY`（相對、絕對或 `{"$env": "MY_KNOWLEDGE"}`），或對跑著的那隻 `aos-agent tools add --replace -n memory_write --envs AOS_MEMORY=/x/kb "$AOS_HOME/lib/agent/memory_write"`（`memory_read` 同樣），寫法見範本 README。讀寫看同一個 `AOS_MEMORY`；agent 的寫入指引在 `aos/memory.json`。
