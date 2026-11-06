← [回入口 README.md](../README.md)｜段落：loop／fsm agent 範本 agent-fsm（11-04）｜上一份：[01-eca-claude](01-eca-claude.md)｜下一份：—

## loop／fsm agent 範本 agent-fsm（11-04）

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `llm.json`／`system.txt`／`tools.json` 就是另一隻（四支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`body.json` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；`_entry` 是「把自己掛上 daemon」（11-05，下面）；格是範本裡四支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../../thinking/2026-11/04/loop-fsm-agent/README.md)；問腦 11-04 晚改成寄信給 llm kernel：[think-as-function 03 § 1](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)；條文 P-11、P-19、P-35 的 11-04 註。

**複製出 repo**（11-05 晚試驗場回報）：四支格找 `aos_flags.py` 先找 `../../py`、再找 PATH 上 `aos-tools` 的真位置推 `proto8/py`（跑過 `install.sh` 或 PATH 放了 `proto8/cmd/aos-tools/bin` 就找得到）；相對 repo 的五處要自己改成絕對路徑——`tools.json` 的 `../../lib/…`、`tools/memory/_entry` 單子裡的 `../../../../lib/agent/memory/_entry`、`tools/memory/_memory.json` 的 `base`，還有 `tools/memory/` 裡的兩個捷徑 `_tooldef.json`、`_metainfo.json`（`cp -r` 照原樣抄相對捷徑，出了 repo 就斷；沒改＝第一題 `aos-tools: error: ToolDefMissing tool memory (…) … needs _tooldef.json inside`、`agent-fsm: error: ToolsBad`，那隻留 `stopped`；11-05 夜第二輪邊緣）。照做一遍（`P`＝repo 的 proto8 絕對路徑）：

```sh
cp -r $P/templates/agent-fsm bob && rm -rf bob/__pycache__
sed -i "s#\"\.\./\.\./lib/#\"$P/lib/#g" bob/tools.json
echo "[\"$P/lib/agent/memory/_entry\"]" > bob/tools/memory/_entry
echo "{\"base\": \"$P/knowledge/aos\"}" > bob/tools/memory/_memory.json
for f in _tooldef.json _metainfo.json; do ln -sfn $P/lib/agent/memory/$f bob/tools/memory/$f; done
```

改完整包（定義＋工作區＋llm kernel）`cp -a` 到別處照樣起得來：daemon 表存相對路徑、上面五處是 repo 的絕對路徑（repo 沒搬就對），只要把 `AOS_LLM_KERNEL` 換成新位置。

```
agent-fsm/
  _entry       {"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}（單子，沒 +x；11-05：aos-exec 這個資料夾＝掛上 daemon）
  body.json    ["aos-loop", "loop.json"]（身體的入口；interfaces.json 的 entry 指它，aos-agent ctl add 掛的是它）
  loop.json    {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（沒有 max：常駐，靠 ctl 的 stop 收工）
  fsm.json     四格：idle {"0": "think", "10": "idle"}、think（brain.py --system system.txt --memory memory）{"0": "wait", "10": "idle"}、
               wait {"0": "act", "10": "wait", "11": "think"}、act（timeout_ms: 1800000）{"0": "think", "10": "idle"}；start: idle
  idle.py      收信：$AOS_STACK/queue/ 全部收進 history.jsonl（接進去就 aos-post done）；有好信退 0、沒有退 10；[--prompt FILE] 開場白
  brain.py     組請求、不碰網路：history（＋system、tools）→ $AOS_STACK/think/request.json（llm kernel 請求信的 body）；退 0；沒事做退 10
  wait.py      寄與收：沒寄＝aos-llm send --reply-to $AOS_STACK/think/reply、名字記進 think/pending.txt、退 10；
               已寄＝aos-llm recv：沒到退 10（loop 照跑）、到了那則 assistant 接進 history 退 0、kernel 回錯退 1；寄之前腦設定與請求對不上＝退 11 回 think 重組
  act.py       跑工具：逐個 aos-tools call，照 metainfo 限時；失敗附 stderr 尾，結果各接一則 tool、退 0；沒有 tool_calls（最後答案）退 10
  system.txt   system 訊息（brain.py 的 --system 指到它；每次從檔讀、不存進 history；11-05 晚改英文）
  tools.json   aos-tools 登記檔：clock、self_tools（改自己的工具）、agents（生子 agent）、memory（查知識庫，11-05 晚）（"../../lib/…"；跟 eca-claude 同一份；後兩個 11-05 使用者裁「內建」）；這隻自己加減的在 $AOS_STACK/tools.json（覆蓋層，aos-agent tools）
  llm.json     腦設定：{}＝用 kernel 的預設代號；只認一個鍵 endpoint（kernel 的 endpoint 包代號，例 "smart-high"；model、temperature 等屬性固定在包上，llm.json 不寫、信裡也不帶 model）
  interfaces.json  {"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json"}}（沒有 screen）
  tools/memory/  memory 的包裝資料夾：_tooldef.json／_metainfo.json 捷徑指回 lib/agent/memory，_entry 是一行單子
               ["../../../../lib/agent/memory/_entry"]（不能是捷徑：aos-exec 解開捷徑後 AOS_CD 會是 lib 那格，找不到這裡的設定），
               _memory.json {"base": "../../../../knowledge/aos"}＝這隻的知識庫（換庫改這行；agent-knowledge 01）
  agents.json  工具 agents 的設定 {"max_children": 4}（這隻最多同時生幾隻；stack 裡的 agents.json 只放改過的鍵＝這隻的覆蓋）
```

**腦＝llm kernel**：think 不自己打端點，wait 把請求寄進 `$AOS_LLM_KERNEL/requests/`（`AOS_LLM_KERNEL`＝[llm kernel](../../kernel/docs/01-llm-kernel.md) 那台 daemon 的 stack，由人設）、之後一拍一拍收回信；寄完 loop 照跑，等回信的期間 `pause`／`stop` 每拍都生效。端點、模型、金鑰都在 kernel 的 `kernel.json`（代號表），agent 只寫代號。範本的 `llm.json` 是 `{}`＝不寫 `endpoint`、用 kernel 的預設（範本 kernel 預設是假腦 `fake`：有工具就先叫 clock〔包寫 `"tool": "clock"`；沒有 clock 就叫第一個〕、再答一句「FAKE ANSWER to: …」），本機沒開 LM Studio 也跑得動。**要真腦**：`llm.json` 寫 `{"endpoint": "stupid-fast"}`（LM Studio 開在 localhost:1234）或 `smart-high`／`luna`／`sol`（LiteLLM），代號要是 kernel 的 `endpoints` 表裡有的（`aos-llm ls` 列出來，[03](../../kernel/docs/01-llm-kernel.md)）；正在跑的那隻只改它自己的就好：`aos-agent llm set endpoint=stupid-fast`（只存改過的鍵、下一題生效、`reset` 回定義）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp）；brain／act 讀的是「定義的 `tools.json` 疊這隻的覆蓋層 `$AOS_STACK/tools.json`」（`aos-tools --overlay`，aos-agent `tools add／rm` 只存差異，11-05，[aos-agent docs/03](../../cmd/aos-agent/docs/03-tools覆蓋層.md#tools-覆蓋層)），brain（memory 那次）與 act 只傳自己的 stack，小格 `$AOS_STACK/tools/<名>/` 由 aos-tools call 統一算；工具退非 0、逾時、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。act 用同一次 `aos-tools ls --json` 的 `metainfo.time_ms.max`（正數毫秒）當各工具逾時，沒寫＝不設限；工具自成一群，逾時整群 TERM，2 秒後 KILL（群長先退也收掉群內孫行程）。退非 0 的結果保留 stdout 與結束碼；逾時結果保留已印的 stdout，再加一行 `(tool <名> timed out (N s); its process group was killed)`。兩種失敗的尾巴再附 `stderr (last 2048 bytes at most):` 與該次 stderr 最後 2 KB；成功時不附。這是**比照 aos-mcp 的 C-52／C-53 明文例外**（J4 任務授權；條文由 J7 補），stderr 全文照樣轉印到 act 自己的 stderr。**知識庫**（11-05 晚，[agent-knowledge 03](../../thinking/2026-11/05/agent-knowledge/03-接進agent與工具說明.md)）：think 格的 `--memory memory`＝每次組請求前叫一次登記名 `memory` 的工具 `{"op": "read"}`，印出來的根（aos 一頁簡介＋目錄）接在 `system.txt` 後面、同一則 system 訊息；腦要更深的自己叫 `memory`。這隻用 `aos-agent tools rm memory` 拿掉＝也不帶根；叫壞了＝`agent-fsm: error: MemoryFailed …` 停下。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。stack 裡多一格 `think/`：`request.json`（這次的請求）、`pending.txt`（寄出去還沒收的信件名稱）、`reply/`（回信信箱）。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-fsm／aos-post／aos-llm-kernel／aos-llm、proto8/cmd/aos-tools/bin 的 aos-tools
# 先起 llm kernel 那台 daemon（見 kernel/docs/01-llm-kernel），把它的 stack export 成 AOS_LLM_KERNEL
mkdir -p /tmp/k && (cd /tmp/k && aos-exec --stack . ~/repo/simple_tools/aos/proto8/kernel/llm-kernel &)
export AOS_LLM_KERNEL=/tmp/k
aos-exec --ws ~/proj proto8/templates/agent-fsm/body.json & # 直接跑（不掛 daemon）：stack＝~/proj/.stack/；說話用 aos-post send --ordered ~/proj/.stack/queue
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

# 掛 daemon（AOS_DAEMON＝daemon 的 $AOS_STACK，沒設＝cwd 的 ./.stack；daemon 的環境要有上面的 PATH 與 AOS_LLM_KERNEL；PATH 再加 cmd/aos-agent/bin 的 aos-agent）
# 先起一台跑 agent 的 daemon（同 kernel/docs/03 件 1；它的環境帶著 AOS_LLM_KERNEL，子項才寄得到）：
echo '{"tick": true, "interval_ms": 300}' > ~/daemon.json && mkdir -p ~/proj/.stack
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
- **暫停時改 history**：`pause` 之後改 `history.jsonl`（例：刪掉最後一則答案），要它重答就把 `stage.txt` 寫成 `think` 再 `resume`；brain 每次從頭讀，改了就生效（寫新請求時順手刪 `think/pending.txt`，wait 重寄）。最後一則已是答案時 brain 不組請求、退 10 回 idle。
- **kernel 停著**：信留在 kernel 信箱的 `new/`，`stage.txt` 停在 `wait`、每拍退 10 一直等；kernel 起來就接著答。kernel 回錯（`EndpointFailed`、`BudgetMissing`…）＝wait 退 1、stderr 先是 aos-llm 的 `aos-llm: error: 代號 原因`、再一行 wait 自己的 `agent-fsm: error: BrainFailed aos-llm recv exited 1 (its reason is above)`，loop 停下等人；修好再起，wait 看到沒 pending、`request.json` 還在＝重寄；寄之前比對 `request.json` 的 endpoint 跟現在的 llm.json（定義疊 stack），對不上（人改了或刪了 llm.json）＝退 11 回 think、brain 重組再寄（11-05 edge-agent；原本要手動把 `stage.txt` 寫成 `think`）。
- **錯**：stderr 一行 `agent-fsm: error: 代號 原因`、退 1、loop 停下等人（P-20；四格的開頭都是 agent 名 `agent-fsm`，stdio-unify R15）——`SendFailed`（aos-llm send 失敗，例 `AOS_LLM_KERNEL` 沒設＝它先印 `aos-llm: error: LlmKernelMissing …`）、`RequestMissing`、`BrainFailed`（kernel 回錯）、`ReplyBad`、`CfgBad`（`llm.json` 讀不懂）、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`、`FlagUnknown`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起從停的那格接著做：直接跑的＝`aos-exec` 同一個工作區；掛 daemon 的＝那隻退 1 時留在表上 `stopped`＋`reason`（11-05 使用者裁「留表標 stopped (Recommended)」）；修好後 `aos-agent llm reset`／`tools reset`（或直接改 stack 裡那份）再 `aos-agent ctl start`，同一個 stack 從停的那格接著做；不要了 `aos-agent ctl rm`（`ctl ls`／`ctl state` 看得到原因）。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。idle／brain／wait 的下層 stderr 原樣透出；act 接住工具的 stderr、叫完後原樣轉印，只有失敗時另附尾巴給腦（上述例外）。工具退非 0 不是錯：act 把結果回給腦、stderr 多一行提醒 `agent-fsm: warning: tool <名> exit code N (passed back to the brain)`、照樣退 0。四格的旗標都走 `aos_flags.parse(help=HELP)`：`--help`／`-h` 印英文用法；帶值旗標可寫 `--x V` 或 `--x=V`，空值／缺值＝`ArgumentsBad`，未知旗標＝`agent-fsm: error: FlagUnknown unknown flag --bogus`。`--` 結束旗標，四格不收位置參數，所以其後還有字＝`ArgumentsBad`；help 也只在旗標位置生效。重複旗標取末值，但任一次空值仍報錯。Ctrl-C 退 130；act 收到 Ctrl-C／TERM（退 143）也先整群 TERM、2 秒後 KILL 並回收工具，不留下半則 tool 訊息。
