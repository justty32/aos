← [回入口 README.md](../README.md)｜段落：loop／fsm agent 範本 agent-fsm｜上一份：[01-eca-claude](01-eca-claude.md)｜下一份：—

## loop／fsm agent 範本 agent-fsm

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `llm.json`／`system.txt`／`tools.json` 就是另一隻（四支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`body.json` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；`_entry` 是「把自己掛上 daemon」（下面）；格是範本裡四支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../../thinking/2026-11/04/loop-fsm-agent/README.md)；問腦＝寄信給 llm kernel：[think-as-function 03 § 1](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)；條文 P-11、P-19、P-35 的 11-04 註。

**複製出 repo**（templates-cp，使用者「copy-out能刪就刪」）：開一隻新 agent 就 `cp -r`：

```sh
export AOS_HOME=$HOME/repo/aos/proto8   # 每台設一次＝放 lib、templates、knowledge 的那個資料夾（proto8 本身或它的抄本；改了值重起樹就生效；也可寫進根的 .env）
cp -r $AOS_HOME/templates/agent-fsm bob
```

範本裡指到範本外、落在 proto8 的路徑一律寫成 `{"$env": "AOS_HOME", "$path": "/…"}`（`tools.json` 的工具、reviewer 與起手範本 `start-api/agents/ann` 的 `fsm.json` 動態連結 agent-fsm 的格、kernel 範本的 `handler` 與 `endpoints`、daemon.json／loop.json 的 argv），範本裡沒有捷徑；解出來的值不寫回任何檔，每次用到才由讀它的程式解。所以抄到哪、兩台各放哪，檔都一字不差，只要每台的 `AOS_HOME` 對。`AOS_HOME` 三種給法（使用者 11-10 午「要用相對位置、絕對位置、環境變數指定都可」）：

| 給法 | 寫在哪 | 這台要備好 |
|---|---|---|
| 殼裡 export | `export AOS_HOME=…` | 每台設一次 |
| 絕對 | 根 `.env` 那行註解換成 `AOS_HOME=/絕對路徑` | 每台把 proto8 放同一個位置（或在那裡放捷徑） |
| 相對 | 根 `.env` 寫 `AOS_HOME=${AOS_WS}/../aos/proto8`（`AOS_WS`＝起根時站的地方） | 每台同樣的相對擺法 |

殼裡 export 的贏過 `.env`（`.env` 只放預設）。根範本 `.env` 最後一行 `AOS_HOME=${AOS_HOME}`＝三種都沒給就在起根當下報 `aos-exec: error: DotenvBad bad .env: …/defs/.env line N`；agent 範本不帶 `.env`、從根繼承。沒有根、自己在殼裡打 `aos-tools call／ls` 時，那個殼要有 `AOS_HOME`，沒有就是 `DirectiveBad … AOS_HOME is not set`。

換台不用跑任何重建指令：備好 `AOS_HOME` 就直接起。`aos-agent tools add` 照使用者給的寫法存（絕對存絕對、相對存相對覆蓋層），要寫環境變數指示詞用 `aos-tools add --path-json`（[aos-tools](../../py/aos/apps/tools/README.md)）。[`templates/tests/test_paths_move.py`](../tests/test_paths_move.py) 在 /tmp 跑三種給法各一輪「`cp -r` 起→問一題→shutdown→git 搬到另一個 HOME 與前綴（A 的 proto8 刪掉）→B 直接起→接著答」，加一輪同機改 `AOS_HOME`。

四支格找共用模組依序看自己的資料夾、`$AOS_HOME/lib`（11-17 路徑規則一：不往上找旁邊的夾；共用模組在 lib 頂層）；沒設 `AOS_HOME` 又缺模組＝`agent-fsm: error: HomeMissing …`、退 1，所以定義抄到哪都起得來，只要 `AOS_HOME` 有傳下來；介面宣告讀法共用 `py/aos/declared_files.py`。範本的 `tests/`、`README.md` 會一起抄過去，`tests/` 可以刪。

改完整包（定義＋工作區＋llm kernel）`cp -a`／git 到別處照樣起得來：daemon 表存相對路徑、指到 proto8 的照 `AOS_HOME` 解，`AOS_LLM_KERNEL` 照根 `.env` 的預設（`${AOS_WS}/../llms/stacks/llm`）或在殼裡換成新位置。

```
agent-fsm/
  _entry       {"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}（單子，沒 +x；aos-exec 這個資料夾＝掛上 daemon）
  body.json    ["aos-loop", "loop.json"]（身體的入口；interfaces.json 的 entry 指它，aos-agent ctl add 掛的是它）
  loop.json    {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json", "on_start": …, "on_stop": …}（on_start／on_stop＝`aos-hook fire -q --stop-on-nonzero --def $AOS_CD` 發 after_start／after_stop；before_run／after_run 預設不接，要掛照 on_start 的樣子加 on_before_run／on_after_run 再重起）（沒有 max：常駐，靠 ctl 的 stop 收工）
  fsm.json     四格：idle {"0": "think", "10": "idle"}、think（brain.py；system 照 interfaces.json 宣告的 system.txt）{"0": "wait", "10": "idle"}、
               wait {"0": "act", "10": "wait", "11": "think"}、act（timeout_ms: 0＝不限時，11-15 起；以前 1800000）{"0": "think", "10": "idle"}；start: idle
  idle.py      收信：$AOS_STACK/queue/ 全部收進 history.jsonl（接進去就 aos-post done）；有好信退 0、沒有退 10；[--prompt FILE] 開場白；
               沒信、腦停下來（最後一則是沒有 tool_calls 的 assistant）、$AOS_STACK/goal.json 是 active＝接一則 [aos] goal: … 退 0（goal）
  brain.py     組請求、不碰網路：history（＋system、tools）→ $AOS_STACK/think/request.json（llm kernel 請求信的 body）；退 0；沒事做退 10
  wait.py      寄與收：沒寄＝aos-llm send --reply-to $AOS_STACK/think/reply、名字記進 think/pending.txt、退 10；
               已寄＝aos-llm recv：沒到退 10（loop 照跑）、到了那則 assistant 接進 history 退 0、kernel 回錯退 1（send 失敗＝冷卻、warning、退 10 等）；沒 pending 且請求不在、或寄之前腦設定與請求對不上、請求比 history 舊（最後一則對不上，或 history.jsonl 比 request.json 新＝寄之前被人改過）＝退 11 回 think 重組；
               等回信不設期限，寄出（pending.txt 的 mtime）每滿 10 分鐘印一行 agent-fsm: warning、照樣等（記在 think/wait_warned.txt）
  act.py       跑工具：逐個 aos-tools call，照 metainfo 限時；失敗附 stderr 尾，結果各接一則 tool、退 0；沒有 tool_calls（最後答案）退 10
  atomic_file.py  idle、wait 共用的寫檔（先寫暫存再改名；寫不成＝那格的 WriteFailed）
  cell_common.py  四格共用的開頭幾步：on_clock 看時鐘（四格）；讀 history.jsonl、決定用哪份工具登記檔（brain、act）；錯誤交那格的 die
  system.txt   system 訊息（interfaces.json 宣告 "system": "system.txt"，self-system；$AOS_STACK/system.txt 在就整份用那份〔aos-agent system set／self_system〕；每格從檔讀、不存進 history；內容是英文）
  tools.json   aos-tools 登記檔：幾乎只剩 `"$override"` 一串 [py/packs](../../py/packs/README.md) 十一包——通用四包 look、change、delete、shell（17 支，預設全開），再加 gadgets（peek_clock、peek_now_time、math、do_task）、todo（todo）、self（預設只開 self_tools、self_state；self_llm、self_system、self_history、self_ctl 四支在 `tools.json` 用覆蓋層 `"名": null` 關掉，要用就 `self_tools add` 或改 `tools.json` 把那列拿掉）、mailbox（mailbox_peek／read／send）、goal（goal）、json（json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set）、index（index_view），共 36 支（使用者「照包砍」「2.都開吧」；11-14「tools40: a」；11-21「self 只留兩支」，原 40 支）；選掛四包 events（clock_register、self_hook）、subagent（subagent、agents_ctl、fork）、def（agent_def、tools_def）、jsonx（jsonx_* 八支）範本不掛，要用的定義在做的時候往自己 `tools.json` 的 `"$override"` 加一項（例 `{"$env": "AOS_HOME", "$path": "/lib/packs/subagent.json"}`），不靠 agent 執行中 `self_tools add`；關法見範本 README；這隻自己加減的在 $AOS_STACK/ 下同一宣告路徑（此範本宣告 tools.json；覆蓋層，aos-agent tools）
  llm.json     腦設定：{}＝用 kernel 的預設代號；model＝kernel 的 endpoint 包代號（例 "smart-high"；寄信時填進 body 的 endpoint 欄，真正的模型名固定在包上）；
               另認與快取無關的調整鍵 temperature、top_p、max_tokens、seed、presence_penalty、frequency_penalty、stop（放進 request；包的 fixed 照舊蓋過）；
               認哪些鍵寫在 interfaces.json 的 llm_keys（aos-agent llm set 對著提醒）
  interfaces.json  {"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json", "llm_keys": [model 與七個調整鍵], "history": "history.jsonl", "system": "system.txt"}, "hooks": [{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"}, "hooks.json"], "hookeds": "hookeds.json", "aos-observed": {"file": "observed.jsonl"}}（沒有 screen；hooks＝hook 點的宣告〔只是參考〕，hookeds＝被勾清單）
  subagents.json  工具 subagent 的配額設定 {"max_subagents": 4}（這隻最多同時生幾隻；stack 裡的 subagents.json 只放改過的鍵＝這隻的覆蓋；誰是我生的另記在 stack 的 tools/subagent/subagents.json）
```

**自稱**：範本 `_metainfo.json` 的 `summary` 與 README 首行一致，`cost.time_ms: 30000` 是估時、`resource: ["llm"]` 是資源；範本本身未宣告頂層 `timeout_ms`。

**覆蓋層位置**（K-6）：brain／wait 的腦設定、brain／act 的工具登記檔都讀 `interfaces.json` 的 `aos-agent.llm`／`tools` 宣告；定義與 stack 使用同一相對路徑。改成 `cfg/brain.json`、`cfg/my_tools.json` 時，身體與 `aos-agent llm／tools` 讀寫的是同一份，沒有寫死 `llm.json`／`tools.json`。未宣告 tools／llm 就沒有工具／腦設定，不去猜檔名。brain／act 的 `--tools` 明給檔案時照旗標，不套 tools 介面覆蓋層。

**腦＝llm kernel**：think 不自己打端點，wait 把請求寄進 `$AOS_LLM_KERNEL/requests/`（`AOS_LLM_KERNEL`＝[llm kernel](../kernel/docs/01-llm-kernel.md) 那台 daemon 的 stack，由人設）、之後一拍一拍收回信；寄完 loop 照跑，等回信的期間 `pause`／`stop` 每拍都生效。端點、模型、金鑰都在 kernel 的 `kernel.json`（代號表），agent 只寫代號。範本的 `llm.json` 是 `{}`＝不寫 `model`、用 kernel 的預設（範本 kernel 預設是假腦 `fake`：有工具就先叫 peek_now_time〔包寫 `"tool": "peek_now_time"`；沒有 peek_now_time 就叫第一個〕、再答一句「FAKE ANSWER to: …」），本機沒開 LM Studio 也跑得動。**要真腦**：`llm.json` 寫 `{"model": "stupid-fast"}`（LM Studio 開在 localhost:1234）或 `smart-high`／`luna`／`sol`（LiteLLM），代號要是 kernel 的 `endpoints` 表裡有的（`aos-llm ls` 列出來，[03](../kernel/docs/01-llm-kernel.md)）；正在跑的那隻只改它自己的就好：`aos-agent llm set model=stupid-fast`（只存改過的鍵、下一題生效、`reset` 回定義）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp）；brain／act 讀的是「定義裡宣告的 tools 登記檔，；`$AOS_STACK/` 下同一宣告路徑有這隻自己那份時改用它（它 `$override` 定義那份，疊法歸 aos-tools）」（此範本宣告 `tools.json`）（aos-agent `tools add／rm` 只存差異，[aos-agent docs/03](../../py/aos/apps/agent/docs/03-tools覆蓋層.md#tools-覆蓋層)），act 只傳自己的 stack，小格 `$AOS_STACK/tools/<名>/` 由 aos-tools call 統一算；工具退非 0、逾時、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。act 用同一次 `aos-tools ls --json` 的 `metainfo.timeout_ms`（純數或 `{"val": N}`，單位毫秒）當各工具逾時，0＝不限，沒寫或壞了＝不設限（壞了 stderr 多一行 `agent-fsm: warning: tool <名>: … skipped; no time limit`）；工具自成一群，逾時整群 TERM，2 秒後 KILL（群長先退也收掉群內孫行程）。退非 0 的結果保留 stdout，再加一行 `[aos] tool: <名> exit code N.`；逾時結果保留已印的 stdout，再加一行 `[aos] tool: <名> timed out after N s; its process group was killed.`。兩種失敗的尾巴再附 `[aos] tool: <名> stderr (last 2048 bytes at most):` 與該次 stderr 最後 2 KB（aos 塞進對話的話一律 `[aos] 種類: 內容`，使用者「2.好，統一。」，`py/aos/flags.py` 的 `aos_note`）；成功時不附。這是**比照 aos-mcp 的 C-52／C-53 明文例外**（J4 任務授權；條文由 J7 補），stderr 全文照樣轉印到 act 自己的 stderr。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。stack 裡多一格 `think/`：`request.json`（可重建的這次請求，image 不存）、`pending.txt`（寄出去還沒收的信件名稱）、`reply/`（回信信箱）、`wait_warned.txt`（一個整數＝等這封已提醒到第幾個 10 分鐘；寄新信、收掉回信時刪，brain／idle 不看它）。**等太久只提醒**（坑-74 使用者裁選項 A）：wait 不判失敗、不設期限；從寄出起每滿 10 分鐘 stderr 一行 `agent-fsm: warning: no reply from the brain for 11 minutes to letter <信件名> (llm kernel: <AOS_LLM_KERNEL>); still waiting`，照樣退 10 繼續等（kernel 沒開最常見）；同時寫 `$AOS_STACK/quiet.json`（`what: "brain_reply"`，`pid`＝state.json 的 aos-loop pid；`py/aos/agentlib/quiet.py`，11-15 使用者「很久沒動靜算黃色，不殺掉」），只標記，這封了結或寄新的一封時刪掉。

```sh
# PATH 要有 cpp 的 aos-exec／aos-loop／aos-fsm／aos-daemon／aos-post／aos-directive／aos-llm、proto8/py/aos/apps/tools 的 aos-tools；AOS_HOME＝proto8（llm kernel 的身體是 py/tools/aos/kernel_llm）
# 先起 llm kernel 那台 daemon（見 templates/kernel/docs/01-llm-kernel），把它的 stack export 成 AOS_LLM_KERNEL
mkdir -p /tmp/k && (cd /tmp/k && aos-exec --stack . ~/repo/aos/proto8/templates/kernel/llm-kernel &)
export AOS_LLM_KERNEL=/tmp/k
aos-exec --ws ~/proj proto8/templates/agent-fsm/body.json & # 直接跑（不掛 daemon）：stack＝~/proj/.stack/；說話用 aos-post send --ordered ~/proj/.stack/queue
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

# 掛 daemon（AOS_DAEMON＝daemon 的 $AOS_STACK，沒設＝cwd 的 ./.stack；daemon 的環境要有上面的 PATH 與 AOS_LLM_KERNEL；PATH 再加 py/aos/apps/agent 的 aos-agent）
# 先起一台跑 agent 的 daemon（同 templates/kernel/docs/03 件 1；它的環境帶著 AOS_LLM_KERNEL，子項才寄得到）：
echo '{"interval_ms": 300}' > ~/daemon.json && mkdir -p ~/proj/.stack
(cd ~ && AOS_STACK=~/proj/.stack/ aos-daemon daemon.json &) && cd ~/proj   # cwd 有 .stack＝aos-agent 找得到這台
aos-agent ctl add --ws ~/proj --name fsm1 proto8/templates/agent-fsm
# 或：cd ~/proj && aos-exec <定義資料夾>  ＝跑它的 _entry＝aos-agent ctl add <定義資料夾>（ws＝~/proj、名字＝資料夾名）
export AOS_AGENT=fsm1        # 之後不用每次 --target
aos-agent say 現在幾點 && aos-agent listen
aos-agent ctl pause          # 停在格與格之間；新信留 queue/new/
aos-agent ctl resume         # ctl 下也有 stop／start、sleep／wake（同一個 stack 接著對話）、rm fsm1；頂層另有 chat、tools、llm
```

- **`aos-exec 這個資料夾`＝掛上 daemon**（[portable-flow 題 4](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)，使用者「介面維持 aos-agent add」）：`_entry` 是一張單子 `aos-agent ctl add <AOS_CD>`、`cwd` 換回 `AOS_WS`（aos-exec 跑入口前會 cd 進定義資料夾，所以要換回來；`AOS_WS`＝`--ws` ＞ 外面的 `$AOS_WS` ＞ 呼叫當下的 cwd）。所以 `cd ws && aos-exec ../agents/bob`＝`aos-agent ctl add --ws ws ../agents/bob`，daemon 用 `ws/.stack` 的（`AOS_DAEMON` 沒設時）。身體的入口另放 `body.json`，`interfaces.json` 用 `entry` 宣告它，`aos-agent ctl add` 掛的是它、表上的 `def` 照樣是定義資料夾。旁支：aos-exec 跑這張單子時新建的空 `.stack/` 跑完會收回（本來就在的不動）；`aos-exec 資料夾 參數…` 的參數接在 argv 尾巴、ctl add 不收——要 `--name` 等就直接打 `aos-agent ctl add`。不接 daemon、直接跑身體＝`aos-exec body.json`。可翻案：放另一個資料夾程式（例 `up/`）、或回到「`_entry`＝身體」。

- **停著等 vs 射後不理**寫在表上：範本 idle 的 `next` 接住 10＝queue 空就停著等（loop 隔 `interval_ms` 再看）。射後不理＝複製一份，idle 的 `next` 改成字串 `"think"`（10 到 loop＝收工）；`loop.json` 的 `interval_ms` 要留著（wait 靠它一拍一拍看回信，拿掉＝空轉）；要開場白就在 idle 的 argv 加 `"--prompt", "prompt.txt"`（相對這個資料夾；history 空、queue 沒好信時投一次）。
- **goal**（[thinking goal](../../thinking/2026-11/11/goal/README.md)，使用者「當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他」）：`$AOS_STACK/goal.json` 是 active、idle 收不到信、history 最後一則是沒有 `tool_calls` 的 assistant＝idle 直接接一則 user `[aos] goal: <目標> (reminder N of LIMIT. …)` 進 history、退 0 去 think（不走 queue、不觸發 before_queue／after_queue；信永遠優先）。上次提醒之後腦叫過 `goal` 以外的工具＝計數歸零；連續 LIMIT 次（預設 10）沒進展＝最後丟一則 `[aos] goal: reminder limit N reached; goal paused …`、goal 改 paused。腦自己用工具 `goal`（get／set／done／pause／resume），人與父 agent 用 `aos-agent goal`；暫停中來信不自動 resume；只有 agent 自己暫停、history 最後 262144 bytes 仍找得到最近的 goal 工具呼叫且之後有新訊息、答完又停下時，idle 才補一次 `[aos] goal: paused …` 提示讓腦選 resume／done／繼續等，碰到既有 goal 提醒或 summary 就不補，外面或 aos 設的暫停與 goal.json 都不動。
- **思考中來的信**答完回 idle 才收、跟那批一起答（使用者 11-04「等答完回 idle 再收」）；一般信通常留在 `queue/new/`，輪中收 `/compact` 時可能一起認領到 `cur/`，但不交給腦，仍等 idle。`/compact` 是例外：工具結果齊了就能在輪中壓縮，見「context 快滿與 /compact」。
- **暫停時改 history**：`pause` 之後用 `aos-agent history -t 名字 ls／rm／summarize／set` 改（self-family；原文搬到 stack 裡 `history_removed.jsonl`；直接改 `history.jsonl` 也行），要它重答就把 `stage.txt` 寫成 `think` 再 `resume`；不 pause 也能改：還沒寄出去的請求，wait 看到 history 比 request 新就退 11 重組；已經寄出去的不追，回信照樣接在改過的 history 後面。agent 自己改用 `self_history`（正在進行的這一步鎖著）；brain 每次從頭讀，改了就生效（寫新請求時順手刪 `think/pending.txt`，wait 重寄）。最後一則已是答案時 brain 不組請求、退 10 回 idle。
- **hook**（[self-family/hook](../../thinking/2026-11/10/self-family/hook/README.md)）：`interfaces.json` 最外層 `"hookeds": "hookeds.json"`（被勾清單），定義那份疊 stack 那份（同名蓋過、null 關掉），每次事件重讀；`"hooks"` 指 hook 點的宣告（範本的 `hooks.json`＋aos-loop 的 `loop_hooks.json`），只是參考。四格的觸發點：idle＝`before_queue`（好信進 history 之前，可改 `content`／攔下丟掉）、`after_queue`；think（brain）＝`tool_added`（工具清單多了名字）；act＝`before_tool`（可改 `arguments`／攔下不跑）、`after_tool`（可改 `content`）；wait＝`brain_failed`（`BrainFailed`／`SendFailed`／`ReplyBad`／`BudgetMissing`）；`/compact`＝`before_compact`、`after_compact`（規矩在 `compact.py`，見「context 快滿與 /compact」的「壓縮前後的 hook」）。時鐘（[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)）：每格最開頭 hook 遙控器 `H.clock_tick()`（`agentlib/hook_clock.py`）判 `on_clock`（時鐘走到了才起 handler）；起來／停下＝loop.json 的 `on_start`／`on_stop` 叫 `aos-hook fire --def` 發 `after_start`／`after_stop`（handler 的碼原樣交給 aos-loop，非 0＝agent 停）；after_stop 的事件只有共通三欄，handler 讀環境變數 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE`（為什麼停：`stop`／`sleep`／`remove`／`shutdown`／`stuck`／`signal`／`max`／`body_exit`／`error`，舊版 aos-loop 沒給＝空；`cause` 跟表上的 `reason` 不同，`reason` 是給人看的一句話；撞限額沒有獨立的值，看表上的 `limit_hit`；`error` 只是停止的分類，不是錯誤代號；值表見 [aos-loop 01](../../cpp/aos-loop/docs/01-用法.md)）。`hookeds.json` 預設一格 `timer`（`on_clock`、`every_ms` 300000、handler `py/tools/agent/hook_noop` 什麼都不做）當掛點，另一格 `mail_notify`（`every_ms` 60000＝每 1 分鐘、handler `py/tools/agent/mail_notify`：有沒通知過的新信才往 queue 寄一則 `[aos] new_mail: …`；起來那次〔`first`〕照已通知記錄比：睡著時新到的提醒一次、全新起來〔沒有 `notified.json`，且 agent stack 的 `history.jsonl` 不在或是空的〕只記成已知；跑過的 stack〔有非空 history〕當睡醒，在等的提醒一次，[backlog-rulings](../../thinking/2026-11/11/backlog-rulings.md)；`timeout_ms` 10000〔0＝不限時〕）：history 不多任何一則，要叫腦就換成往 `queue/` 寄信的 handler（同名蓋過）；不要就 `aos-agent hook rm timer`。hook 失敗（退 0／10 以外、逾時、起不來、stdout 不合）：能攔的點（`before_queue`、`before_tool`）＝那格 `agent-fsm: error: HookFailed …` 退 1、停下等人；其他點（含 `before_compact`）＝一行 warning；清單壞＝`HooksBad`。人用 `aos-agent hook`、agent 自己用 `self_hook`；全文 [aos-agent docs/06](../../py/aos/apps/agent/docs/06-hook.md)。
- **image 醒在 wait 格**：有 `think/pending.txt` 就繼續收原回信，即使 `think/request.json` 不在也不重寄；沒 pending 且 request 不在＝wait 退 11，沿既有 FSM 轉移回 think，brain 從 history＋目前定義／覆蓋層重組，再到 wait 寄出。image 可以擋 `think/request.json`；`pending.txt`、`think/reply/new/`／`cur/` 仍必須帶走。
- **kernel 停著**：信留在 kernel 信箱的 `new/`，`stage.txt` 停在 `async`、每拍退 10 一直等；kernel 起來就接著答。kernel 回錯（`EndpointFailed`…；`BudgetMissing` 例外，見下一段「額度拒絕」）＝wait 退 1、stderr 先是 aos-llm 的 `aos-llm: error: 代號 原因`、再一行 wait 自己的 `agent-fsm: error: BrainFailed aos-llm recv exited 1 (its reason is above)`，loop 停下等人；修好再起，wait 看到沒 pending、`request.json` 還在＝重寄；寄之前比對 `request.json` 的 endpoint 跟現在的 llm.json（定義疊 stack），對不上（人改了或刪了 llm.json）＝退 11 回 think、brain 重組再寄（edge-agent）。
- **wait 自己認的三種殘留**（TS）：① 有 pending 而 `think/reply/` 缺 `tmp`／`new`／`cur`（clone 後空資料夾不在 git）＝recv 前先 `aos-post init`；② recv 說還沒回、`AOS_LLM_KERNEL` 解得到資料夾（相對＝從 `$AOS_DAEMON` 算，同 aos-llm）而那封信不在 `<kernel>/requests/new/`、`cur/`＝再收一次，還是沒有＝刪 `pending.txt`、印 `agent-fsm: warning: the letter <名> is no longer queued at the llm kernel <路徑>; sending the request again`、下一拍重寄（kernel 那邊只讀不寫；`AOS_LLM_KERNEL` 沒設或解不到＝照樣等）；③ 正要寄時 `request.json` 的 messages 最後一則跟 `history.jsonl` 最後一則不一樣（JSON 正規化後比；請求是從比較舊的 history 組的，例 `git reset` 後留下的）＝退 11 回 think 重組、不寄。另外平常每拍用 `aos-llm recv --quiet`（不印「為什麼還沒回」，免得每拍一行），只有要印 10 分鐘提醒的那一拍不帶，讓 aos-llm 把原因印在提醒那行前面。
- **額度拒絕**（11-14 AK17，[astra-kernel-1114](../../thinking/2026-11/14/astra-kernel-1114.md)）：kernel 回 `BudgetMissing`＝不停下：先觸發 `brain_failed`（`name = BudgetMissing`、`reason`＝kernel 的 `error.msg`），記 `cooldown.json`（同代號），印一行 `agent-fsm: warning: BudgetMissing …`、退 10 留在 wait，冷卻到期重寄同一份 `request.json`；冷卻檢查通過、正要寄出時，若 `priority.deadline` 可解為有限 epoch 秒數或帶時區的 ISO 時間，且已過或 5 秒內到期，wait 只印 warning、不寄出，退 11 回 think 重組，不觸發 `brain_failed`、不改 `request.json`／`cooldown.json`，解不開的 priority 仍交 kernel 判斷（出廠 brain.py 目前不寫 deadline）。好回信清冷卻，因 llm.json 改變退 11 重組時也先清 `BudgetMissing` 冷卻。範本 `hookeds.json` 帶一格 `brain_notify`（`brain_failed`、條件 `BudgetMissing`、[py/tools/agent/brain_notify](../../py/tools/agent/brain_notify/_entry)）：往 `AOS_NOTIFY_BOX` 寄一封 BLOCKED 信，同一段拒絕只寄一次；`subagent add` 沒給這個變數時預設成 mom 的 `<stack>/mailbox`。kernel 的 error 帶 `resets_at`（未來）＝冷卻到那一刻＋5 秒而不照間隔表；`window` 是 `all`（永不重置）＝觸發 `brain_failed` 後退 1 停下（不記冷卻、`request.json` 留著，加額度再起），`brain_failed` 事件另帶 `error` 欄，`brain_notify` 據此改寫標題與說明（waiting until <時間>／stopped）。**auto_restart 注意**：開了 `auto_restart` 的列碰到 `all` 退 1 會被 daemon 重起，重寄的請求立刻又被拒（不耗 token），由 daemon 的重起退避擋著；subagent 沒有 `auto_restart`。詳見 [agent-fsm README](../agent-fsm/README.md)。

寄之前 `AOS_LLM_KERNEL` 沒設或只有空白＝觸發 `brain_failed` 後以 `LlmKernelMissing` 停下、不記冷卻、保留 `request.json`，要帶變數重掛；有設但 kernel 資料夾不在仍照下面的 `SendFailed` 冷卻等待。

- **失敗後冷卻**（[two-machines 06](../../thinking/2026-11/10/two-machines/06-長跑自動重起.md)，使用者裁「失敗後冷卻」）：wait 遇到外面服務的錯——`BrainFailed`（kernel 回錯）、`SendFailed`（`aos-llm send` 退非 0）——先寫 `$AOS_STACK/cooldown.json`（`py/aos/agentlib/cooldown.py`；`failures`、`until`、`at`、`code`、`reason`，`dropped` 一直是 0：重寄同一份請求、不掉信；間隔 30 秒、1、2、4、8、15、30 分鐘，之後固定 30 分鐘，用牆上時鐘），再看是哪一種：`BrainFailed` 退 1；`SendFailed`（TS，使用者「如果llms那邊我沒開aos daemon，那就是我自己的問題，但我也希望他不要搞壞」）印一行 `agent-fsm: warning: aos-llm send exited N (its reason is above); the request stays and is sent again …`、**退 10 留在 wait、不停**——**這是 P-20 在這個情況的例外：kernel 不在＝等它來，不停下**，有沒有 `--auto-restart` 都一樣。寫冷卻時 `AOS_LLM_KERNEL` 解不到資料夾，`reason` 尾巴記 `(llm kernel folder not found)`；之後冷卻中而 `AOS_LLM_KERNEL` 已解得到資料夾＝當作到了、立刻寄（不用等滿 30 分鐘）。冷卻寫不成只多一行 `agent-fsm: warning`、結果不變。下一次走到「沒 pending、`request.json` 在、endpoint 對得上、正要寄」時：冷卻中＝不寄、退 10 留在 wait（每拍再看）；到了或沒有＝照寄。好的回信接進 history 後刪 `cooldown.json`。`ReplyBad`、`WriteFailed` 這類不是外面服務的錯，不寫冷卻。冷卻檔另有兩欄（cooldown-1118，使用者 11-18 裁「寫進狀態檔」）：`retry`＝這格之後會不會自己重送（`SendFailed`、`BudgetMissing`、`retry` true 的 `BrainFailed`＝true；退 1 停下的 `BrainFailed`＝false），`error`＝kernel 回信的 `{code, msg}`（例 `EndpointFailed`／`HTTP 400 …`，解得到才寫）；`ctl ls -l` 的 LAST ERROR 接上 `error`、`ctl ls --json` 照帶兩欄（`aos-agent listen` 不看這兩欄，照舊讀 stderr 結尾的錯誤行帶原話，使用者 11-18 裁「前綴補回」）。`BrainFailed` 時，用 [`aos-agent ctl add --auto-restart`](../../py/aos/apps/agent/README.md) 掛的：退 1 → daemon 重起 → 在冷卻裡活過 3 秒，不會被三次判停，冷卻到了自己重寄（端點修好就恢復）。沒開的：退 1、表上 `stopped` 停著等人，只是多一個 `cooldown.json` 說明原因；人修好後 `ctl start`，若還在冷卻中，它會在 wait 等到冷卻到期才寄（急的話刪掉 `cooldown.json`）。
- **錯**：stderr 一行 `agent-fsm: error: 代號 原因`、退 1、loop 停下等人（P-20；四格的開頭都是 agent 名 `agent-fsm`，stdio-unify R15）——`SendFailed`（aos-llm 起不來、或 send 退 0 卻沒印信件名稱；send 退非 0＝warning＋等，見上一條）、`BrainFailed`（kernel 回錯）、`ReplyBad`、`CfgBad`（`llm.json` 讀不懂）、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`、`FlagUnknown`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起從停的那格接著做：直接跑的＝`aos-exec` 同一個工作區；掛 daemon 的＝那隻退 1 時留在表上 `stopped`＋`reason`（使用者裁「留表標 stopped (Recommended)」）；修好後 `aos-agent llm reset`／`tools reset`（或直接改 stack 裡那份）再 `aos-agent ctl start`，同一個 stack 從停的那格接著做；不要了 `aos-agent ctl rm`（`ctl ls`／`ctl state` 看得到原因）。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。idle／brain／wait 的下層 stderr 原樣透出；act 接住工具的 stderr、叫完後原樣轉印，只有失敗時另附尾巴給腦（上述例外）。工具退非 0 不是錯：act 把結果回給腦、stderr 多一行提醒 `agent-fsm: warning: tool <名> exit code N (passed back to the brain)`、照樣退 0。四格的旗標都走 `aos_flags.parse(help=HELP)`：`--help`／`-h` 印英文用法；帶值旗標可寫 `--x V` 或 `--x=V`，空值／缺值＝`ArgumentsBad`，未知旗標＝`agent-fsm: error: FlagUnknown unknown flag --bogus`。`--` 結束旗標，四格不收位置參數，所以其後還有字＝`ArgumentsBad`；help 也只在旗標位置生效。重複旗標取末值，但任一次空值仍報錯。Ctrl-C 退 130；act 收到 Ctrl-C／TERM（退 143）也先整群 TERM、2 秒後 KILL 並回收工具，不留下半則 tool 訊息。

**任務上下文與工具煞車**（P4）：brain 的 `--history full|task` 預設 `full`＝帶完整 history；`task` 只帶最後一封 user 起的訊息，system 照常放最前面，磁碟 history 不裁切；壓縮那次改送完整 history，壓完會保留適用的摘要，規則見「context 快滿與 /compact」。沒有 user 時帶目前全部訊息。`--max-tool-calls N` 接非負整數，按最後一封 user 起的 assistant `tool_calls` 條目總數計算；滿 N 次後，下一次 request 不提供 tools。`0` 從第一個 request 就不提供 tools；未給不限制；同一批多個呼叫照常執行，這個選項只控制下一次請求。兩個旗標互相獨立，在 `fsm.json` 的 brain argv 加上即可。

**實際成本觀測**（P5）：wait 用 `aos-llm recv --full` 收完整回信，只把原有 `message` 接入 history，額外欄位不混進對話。每次收到成功或失敗回覆，往 `$AOS_STACK/observed.jsonl` 追加 `{kind: "think", letter, endpoint, model, usage, elapsed_ms}`（壓縮那次記 `kind: "compact"`，不當成一般 think 的用量讀數）；`letter` 是寄出時 `aos-llm send` 回的信件名（保存在 `think/pending.txt`），與接收該請求的 kernel `ledger.jsonl` 的 `id` 為同一個字串，可直接對帳。`think/sent.json` 記寄出前的時間與 endpoint，耗時包含排隊與逐拍收信等待。endpoint 優先用回信欄位、否則用寄出時保存的請求代號；請求未指定且回信沒帶時為 null，不猜 kernel 預設。失敗回覆或未提供的 model／usage 為 null。舊 pending 沒有時間檔時耗時為 null 並提醒。act 每次實際啟動工具追加 `{kind: "tool", name, def, stack, child?, code, elapsed_ms, in_bytes, out_bytes}`，bytes 是原始 UTF-8 stdin 與 stdout，不含 stderr／附加錯誤說明；code 是子程序原始結束碼（訊號為負數）。重跑時已回覆的工具不重記，未啟動的錯誤（未登記／arguments 壞）沒有實際呼叫觀測。這些觀測寫失敗只印英文 warning，不改格的結果。

共用記帳由 `py/aos/observed.py` 處理：首寫先補 `self` 行，含 `def`（`AOS_CD`）、`ws`（`AOS_WS`）、UTC 毫秒 `started_at`，設了 `AOS_LLM_KERNEL` 才帶 `llm_kernel`；同時合併 stack 的 `aos-observed` 宣告。工具行的 `def` 是登記路徑的絕對值、`stack` 是相對本 stack 的小格；有子帳時 `child` 指向收子前保存的帳本，相對本 stack。do_task／subagent 只照子 stack 的公開介面抄整棵帳，不猜帳名。

**長跑**：長時間接不同任務的 fsm，在 `fsm.json` 的 think 格、`brain.py` 的 argv 加 `"--history", "task"`，每次只把最後一封 user 起的任務帶給腦（壓縮後也帶適用的摘要），避免舊任務一直累積進請求；這個旗標不裁切磁碟 history。

## context 快滿與 /compact

**預設 35%，收尾與壓縮一起做**。新範本掛 `context_wrap`：`on_clock`、每 5000 ms 檢查一次、`config {"percent": 35, "wrap": false}`；到門檻直接往 agent 的 queue 寄 `/compact`，不另寄收尾信、不等 queue 空。腦用當時的完整對話寫交接摘要，body 同時存進 history 與 `<stack>/handoff.md`，不是先要求它結束手上任務。

### 讀數、門檻與關法

fsm 讀數取 `<stack>/observed.jsonl` 最後 256 KiB 中最近一則有有效 usage 的 `think`：`used` 是 `usage.prompt_tokens`（已含快取），沒有此鍵才加總 `input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`（至少一鍵存在，缺項當 0），不加 completion。失敗或用量無效的列略過。壓縮那次記 `kind: "compact"`，不把拿掉 tools 後的讀數當成真的降下來，避免反覆觸發。

比例是 `used ÷ window × 100`；視窗讀 `think/brain_wait.json` 指的 kernel 公開 `endpoints.json` 裡該 pack 的 `context`，hook 的 `config.window`（正整數）可蓋過它。兩邊都沒有、沒有效用量或讀不到檔，就安靜不觸發，不用 history 位元組數猜。共用讀法仍依序先看 `context_usage.json`、Claude 讀法，最後才看 fsm observed。

- 改門檻：改定義或 stack 的 `hookeds.json` 同名格裡的 `config.percent`（1～100）；或 `self_hook add` 帶 `config` 與 `replace: true` 整格換掉。
- 關掉自動壓縮：`self_hook` `{"op":"rm","name":"context_wrap"}`（即 `self_hook rm context_wrap`），或在 stack 的 `hookeds.json#/context_wrap` 寫 `null`。`self_hook` 屬選掛 events 包，範本預設沒有這支工具。
- 看讀數：`context_wrap --reading <stack>`；可加 `--window 272000` 核對指定視窗，印一行讀數或讀不到的原因，不改 state。

hook 格如下（pack 沒有 `context` 時可在 config 補 `"window": 272000`）：

```json
"context_wrap": {
  "event": "on_clock",
  "every_ms": 5000,
  "config": {"percent": 35, "wrap": false},
  "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/context_wrap"},
  "timeout_ms": 20000
}
```

### 寄 /compact 會怎樣

對 agent 寄 `/compact`（或 `/compact` 後接空白與摘要重點）即可手動要求壓縮；不必等過門檻。這是 body 指令，不跑 `before_queue`／`after_queue`。`/clear` 不在這個功能裡，仍是普通文字。

1. idle 把同一批一般信照常收完，批內的 `/compact` 合成一次壓縮要求；做到一半則由 brain 在下一步組請求前認信，僅在 history 尾端是 user，或最後一組工具結果已齊時插入要求，不切斷工具配對。一般信不因而在輪中交給腦。
   夠摺時先發 **`before_compact`**（11-21 compact 第 4 刀，見下面「壓縮前後的 hook」）：hook 可攔下、改指示、不清工具輸出、或直接交一份摘要（那就不叫腦，跳到第 4 步）。
2. **先清舊的工具輸出**（11-21 compact 第 1 刀，[紀錄](../../thinking/2026-11/21/compact-第1刀-1121.md)）：`role: tool` 列的內容換成一行 `[aos] tool output cleared (N chars from TOOL); the original is in history_removed.jsonl`，列本身留著（工具配對不斷）；最後 3 則工具輸出、最後一組工具呼叫的結果、短於 300 字的、已經是佔位的不清，工具呼叫與 arguments 不動。原文接進 `history_removed.jsonl`（`op: "clear_tools"`）。改 history 照摺的做法（寫暫存、沒變才改名），一直在變三次或讀不了＝放棄清、記一行 warning、照舊往下。目的只是讓下一步那次請求變小（真模型兩份長對話 prompt 少七成多），壓完的樣子不變。
3. body 接一則 `[aos] compact:` user，要求只回摘要（有清時多一句清了幾則、原文在哪）；那次送完整 history、**不帶 tools**。摘要要寫全接著做需要的資訊：誰要什麼、信名與回信處、已做與做到哪、下一步、所有未結事項、重要路徑、規則與決定、todo／goal。
4. 收到有效摘要，先發 **`after_compact`**（hook 可改摘要、交補回的字），之前的對話換成一則 `[aos] summary:` user（有補回的字就緊接一則 `[aos] restored after compact: …` user），接一則 `compact done: …` assistant（只答 `/compact` 那幾封），再接留下的 user 列。**沒答的信原文保留**；緊貼要求前的連續 user 提醒也保留，舊 summary 除外。摺掉的原文先接進 `<stack>/history_removed.jsonl`，摘要再接進 `<stack>/handoff.md`。
5. 做到一半插的要求帶 `mid_turn: true`，壓完尾端多一則 user：`[aos] compact: done. Go on with the work in progress described in the summary above; letters you have not answered yet are above.`。所以不經 idle，直接接著做；idle 發起的則沒有這列，有沒答的信就接著想，沒有就回 idle。

壓縮進行中 idle 不再收信，來信等壓完再收。同批多封 `/compact` 一起處理；可摺列數是「要求之前的列數扣掉會原文留下的列」，**不到 4 則就不叫腦、不摺**，當成正常做完（使用者 11-20「當成正常做完」）：history 接一則 assistant `compact not needed: only N messages to fold (it takes at least 4); nothing was folded`（形狀同 compact done，`aos` 多 `skipped: true`），那幾封記成答完，ask／listen 拿到這句；不寫 `mailbox_warning.txt`、不記 dropped。這則寫在同一批普通信之前，普通信照常往下答。這種回答不算可摺列，所以剛壓完連寄幾封 `/compact` 都只會各得一句、不會自己湊滿 4 則。

摘要空白、帶 tool_calls、要求列不見或 history 無法安全摺時，放棄該次，移除要求列、信 drop `failed`、記 warning，不接入那份無效回答；改寫 history 遇到持續變動、連移除要求都重試 3 次失敗時，停在 `WriteFailed`，保留 asked 供重起接續。腦呼叫本身失敗則沿用原本冷卻／停下規則，保留壓縮要求。handler 不會在讀數仍高時一直重寄；要重試可以再手動寄 `/compact`。

### 資料格式

| 位置 | 誰寫 | 格式與用途 |
|---|---|---|
| `<stack>/observed.jsonl` | wait | `{kind: "think"｜"compact", letter, endpoint, model, usage, elapsed_ms}`；只有有效 think 供用量讀數 |
| `<kernel>/endpoints.json` | kernel | `{pack: {speed, context?, …}}`；公開 pack 視窗 |
| hook 格 `config` | 人 | `{percent: 1～100, wrap: bool, window: 正整數}`；都選填，預設 percent 35、wrap true；fsm 格明寫 wrap false |
| `<stack>/hookeds/context_wrap/state.json` | handler | `{phase, letter, turn, percent}`；phase 為 idle／wrapping／compacting／compacted |
| `<stack>/compact.json` | body | asked：`{phase: "asked", letters: [信名…], asked_at, mid_turn: bool, cleared, cleared_chars, by, restore?}`；done：`{phase: "done", letters, done_at, replaced, kept, summary_chars, cleared, cleared_chars, by, restored_chars}`（`cleared`＝清掉幾則工具輸出、`cleared_chars`＝原本幾字、`by`＝`brain` 或交摘要的 hook 名、`restore`＝`before_compact` 交的補回字）；failed：`{phase: "failed", letters, failed_at, reason}`；blocked：`{phase: "blocked", letters, blocked_at, hook, mid_turn}` |
| history 的 compact done 列 | body | `{role: "assistant", content: "compact done: …", aos: {answer_to: [壓縮信名…], compact: true}}`；`aos.compact` 供 task 模式辨識，送端點前剝掉 aos；太短沒壓的那則是 `compact not needed: …`，aos 多 `skipped: true`（不算可摺列）；被 `before_compact` 攔下的那則是 `compact blocked by hook …`，aos 多 `skipped: true`、`blocked: hook 名` |
| `<stack>/history_removed.jsonl` | body | `{removed_at, op: "clear_tools"｜"compact"｜"compact_failed", line, message}`；UTC 毫秒 Z、原行號與原訊息，只接不刪 |
| `<stack>/handoff.md` | body | 每次接一節 `## compact <UTC> (<n> messages)` 與摘要；不是工作區的 notes.md |

### 壓縮前後的 hook

11-21 compact 第 4 刀（[紀錄](../../thinking/2026-11/21/compact-第4刀-1121.md)；使用者「2.都開」：調、補、換都開；「compact這塊，反正各agent有需要的，可以自訂自己的compact程式和流程」）。宣告在範本的 `hooks.json`，規矩寫在 `compact.py`（引擎只負責叫 handler）；範本預設一個都不掛，用 `aos-agent hook add --event before_compact …`／`self_hook` 掛。

| 點 | 什麼時候 | 事件欄位 | 能做的 |
|---|---|---|---|
| `before_compact` | 夠摺（不到 4 則的 `compact not needed` 不發）、清工具輸出與加要求之前；idle 或輪中的 brain | `letters`、`asked`（/compact 後面的字）、`instructions`（要求會帶的額外指示，起始＝`asked`）、`mid_turn`、`foldable`、`clear`（true）、`summary`（null）、`restore`（null） | 退 10＝攔下；stdout 物件改 `instructions`（字串，空＝不給）、`clear`（false＝不清工具輸出）、`summary`（非空字串＝不叫腦、不清，當場用它摺）、`restore`（交給 `after_compact` 當起始值） |
| `after_compact` | 摘要好了、history 改寫之前；wait（或 hook 交摘要時的 idle／brain） | `letters`、`summary`、`by`（`brain` 或交摘要的 hook 名）、`mid_turn`、`cleared`、`restore` | stdout 物件改 `summary`（非空字串）、`restore`（字串或 null；非空＝摘要那則後面接一則 `[aos] restored after compact: …`，不多叫一次腦） |

- 多個 hook 照名字排，**後一個看得到前一個改過的值**；`restore` 是整段換掉，要接在後面就自己把收到的串上。
- hook 失敗（退 0／10 以外、逾時、起不來、stdout 不是物件或鍵的型別不對）兩個點都只是一行 warning、跳過它、下一個照跑，壓縮照常做。
- 攔下：idle 那次＝不清不摺不叫腦，那幾封得到一則 `compact blocked by hook H: <它的 stdout>; nothing was folded`（形狀同 `compact not needed`，`aos` 多 `blocked: H`）、記成答完；輪中那次＝信留在 queue 的 `cur/`、不認領，這輪照常做完，回 idle 時 idle 再發一次 `before_compact`（`mid_turn` false）。`compact.json` 記 `phase: "blocked"`。`context_wrap` 寄的那封被攔下也算答完，它就停在 compacted，等讀數降下來再升上門檻才會再寄。
- 交摘要：照舊加要求列再摺（同一條 `fold`，摺掉的原文照樣進 `history_removed.jsonl`、摘要照樣進 `handoff.md`），`compact.json` 的 `by` 記那個 hook 名。handler 可以自己叫便宜的模型寫，也可以完全不用模型。

### goal、do_task 與 task history

- `goal.json`、todo 清單不動。輪中壓縮有尾端 continue user，直接續做，不經 idle，也不多記 goal 沒進展；idle 壓縮若沒有待答信，以 compact done 結尾，goal 提醒照常來，壓後第一次提醒可能因舊工具呼叫已摺掉而多算一次沒進展，有工具進展後歸零。
- 開著的 `do_task` 起點可能被摺掉，`tasks.json` 不改；之後 `do_task end` 回 `MarkerMissing`、關任務而不再摺，是正常結果。摘要要先保存還需要的資訊。
- `--history task` 壓縮那次仍送全份。壓完下一步從最後 user 往前找 summary，若 summary 到起點間的 assistant 都是 `aos.compact: true` 的 compact done，起點改成該 summary，避免任務原文或 continue 把摘要切掉；之後有真正回答則不沿用這條延伸規則。

### 舊 agent 怎麼換上

由管理該 agent 的人操作，不用重掛：先 pause（或確認 idle），在那棵樹用的 proto8 跑過 `install.py`（11-21 起 `compact.py` 要 lib 裡的 `aos/agentlib/tool_clear.py`，沒有它 idle 一收 `/compact` 就停），再把新範本的 `compact.py`、`idle.py`、`brain.py`、`wait.py` **四檔換進定義夾**（11-21 第 4 刀動了 `compact.py`、`idle.py`、`brain.py`，用 lib 裡已有的 `aos.hook_run`、`agent_hooks`，不必為它多跑 `install.py`；要宣告的話 `hooks.json` 一起換）；若那份定義改過這些檔，先比對。同一定義的其他 agent 也會一起換上。再把上面的 hook 格加到該 agent stack 的 `hookeds.json#/context_wrap`（希望整份定義都有才改定義 hookeds.json），pack 尚無 context 時在 config 補 window，最後 resume，用 `context_wrap --reading <stack>` 核對。**先換檔、後掛 hook**：舊 body 會把 `/compact` 當普通文字。

repo 的這些更新不會自行換掉既有樹；共用 `context_use`／`context_wrap`、範本、docs、知識庫要先抄進該樹才生效，kernel 的 pack 也要有 context 或另給 window。活樹換檔須由有權管理的人取得同意後做，不是 agent 自己改別人的 stack。

### 已知限制

- act 跑長工具時不檢查（格還沒結束，不跑 on_clock）；下一步才查，一步之內 context 不會再漲。
- 單次工具結果把用量從 30% 推到 100% 救不了，要另處理工具輸出上限。
- 清過舊工具輸出再摘要，摘要會少一些只出現在那些輸出裡的細節（例：開工時讀檔讀到的規矩、確切值）；11-21 兩份長對話實測評為小幅變差、接著做要的狀態都在。
- 摘要品質靠模型；保底是未答信原文、`history_removed.jsonl` 全文與累積摘要的 `handoff.md`。
- 壓完仍高於門檻會留在 compacted，不重寄；等下一次真正 think 的新讀數低於門檻才回 idle。用 `--reading` 查數字，必要時調 percent。