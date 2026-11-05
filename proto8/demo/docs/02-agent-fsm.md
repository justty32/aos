← [回入口 README.md](../README.md)｜段落：loop／fsm agent 範本 agent-fsm（11-04）｜上一份：[01-eca-claude](01-eca-claude.md)｜下一份：—

## loop／fsm agent 範本 agent-fsm（11-04）

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `llm.json`／`system.txt`／`tools.json` 就是另一隻（四支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`body.json` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；`_entry` 是「把自己掛上 daemon」（11-05，下面）；格是範本裡四支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../../thinking/2026-11/04/loop-fsm-agent/README.md)；問腦 11-04 晚改成寄信給 llm kernel：[think-as-function 03 § 1](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)；條文 P-11、P-19、P-35 的 11-04 註。

```
agent-fsm/
  _entry       {"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}（單子，沒 +x；11-05：aos-exec 這個資料夾＝掛上 daemon）
  body.json    ["aos-loop", "loop.json"]（身體的入口；interfaces.json 的 entry 指它，aos-agent ctl add 掛的是它）
  loop.json    {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（沒有 max：常駐，靠 ctl 的 stop 收工）
  fsm.json     四格：idle {"0": "think", "10": "idle"}、think（brain.py --system system.txt）{"0": "wait", "10": "idle"}、
               wait {"0": "act", "10": "wait"}、act {"0": "think", "10": "idle"}
  idle.py      收信：$AOS_STACK/queue/ 全部收進 history.jsonl（接進去就 aos-post done）；有好信退 0、沒有退 10；[--prompt FILE] 開場白
  brain.py     組請求、不碰網路：history（＋system、tools）→ $AOS_STACK/think/request.json（llm kernel 請求信的 body）；退 0；沒事做退 10
  wait.py      寄與收：沒寄＝aos-llm send --reply-to $AOS_STACK/think/reply、名字記進 think/pending.txt、退 10；
               已寄＝aos-llm recv：沒到退 10（loop 照跑）、到了那則 assistant 接進 history 退 0、kernel 回錯退 1
  act.py       跑工具：最後一則 assistant 的 tool_calls 逐個 aos-tools call，結果各接一則 tool、退 0；沒有 tool_calls（最後答案）退 10
  system.txt   system 訊息（brain.py 的 --system 指到它；每次從檔讀、不存進 history）
  tools.json   aos-tools 登記檔，只登記 clock（"../../lib/base/clock"；跟 eca-claude 同一份寫法）；這隻自己加減的在 $AOS_STACK/tools.json（覆蓋層，aos-agent tools）
  llm.json     腦設定：{}＝用 kernel 的預設代號；鍵 endpoint（kernel 的代號，例 "local-qwen"）、model（臨時換同一端點的模型）
  interfaces.json  {"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json"}}（沒有 screen）
```

**腦＝llm kernel**：think 不自己打端點，wait 把請求寄進 `$AOS_LLM_KERNEL/mailbox/`（`AOS_LLM_KERNEL`＝[llm kernel](03-llm-kernel.md) 那台 daemon 的 stack，由人設）、之後一拍一拍收回信；寄完 loop 照跑，等回信的期間 `pause`／`stop` 每拍都生效。端點、模型、金鑰都在 kernel 的 `kernel.json`（代號表），agent 只寫代號。範本的 `llm.json` 是 `{}`＝不寫 `endpoint`、用 kernel 的預設（範本 kernel 預設是假腦 `fake`：有工具就先叫第一個、再答一句「FAKE ANSWER to: …」），本機沒開 LM Studio 也跑得動。**要真腦**：`llm.json` 寫 `{"endpoint": "local-qwen"}`（LM Studio 開在 localhost:1234）或 `luna`／`sol`（LiteLLM），代號要是 kernel 的 `endpoints` 表裡有的；正在跑的那隻只改它自己的就好：`aos-agent llm set endpoint=local-qwen`（只存改過的鍵、下一題生效、`reset` 回定義）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp）；brain／act 讀的是「定義的 `tools.json` 疊這隻的覆蓋層 `$AOS_STACK/tools.json`」（`aos-tools --overlay`，aos-agent `tools add／rm` 只存差異，11-05，[aos-agent docs/03](../../extras/agent/docs/03-tools覆蓋層.md#tools-覆蓋層)），工具小格 `$AOS_STACK/tools/<名>/`；工具退非 0、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。stack 裡多一格 `think/`：`request.json`（這次的請求）、`pending.txt`（寄出去還沒收的信件名稱）、`reply/`（回信信箱）。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-fsm／aos-post／aos-llm-kernel／aos-llm、proto8/bin 的 aos-tools
# 先起 llm kernel 那台 daemon（見 03-llm-kernel），把它的 stack export 成 AOS_LLM_KERNEL
mkdir -p /tmp/k && (cd /tmp/k && aos-exec --stack . ~/repo/simple_tools/aos/proto8/demo/llm-kernel &)
export AOS_LLM_KERNEL=/tmp/k
aos-exec --ws ~/proj proto8/demo/agent-fsm/body.json &    # 直接跑（不掛 daemon）：stack＝~/proj/.stack/；說話用 aos-post send --ordered ~/proj/.stack/queue
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

# 掛 daemon（AOS_DAEMON＝daemon 的 $AOS_STACK，沒設＝cwd 的 ./.stack；daemon 的環境要有上面的 PATH 與 AOS_LLM_KERNEL；PATH 再加 extras/agent/bin 的 aos-agent）
aos-agent ctl add --ws ~/proj --name fsm1 proto8/demo/agent-fsm
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
- **kernel 停著**：信留在 kernel 信箱的 `new/`，`stage.txt` 停在 `wait`、每拍退 10 一直等；kernel 起來就接著答。kernel 回錯（`EndpointFailed`、`BudgetMissing`…）＝wait 退 1、stderr 一行 `aos-llm: 代號 原因`、loop 停下等人；修好再起，wait 看到沒 pending、`request.json` 還在＝重寄；寄之前比對 `request.json` 的 endpoint／model 跟現在的 llm.json（定義疊 stack），對不上（人改了或刪了 llm.json）＝退 11 回 think、brain 重組再寄（11-05 edge-agent；原本要手動把 `stage.txt` 寫成 `think`）。
- **錯**：stderr 一行 `agent-fsm: 代號 原因`、退 1、loop 停下等人（P-20）——`SendFailed`（aos-llm send 失敗，例 `AOS_LLM_KERNEL` 沒設＝它先印 `aos-llm: LlmKernelMissing`）、`RequestMissing`、`ReplyBad`、`CfgBad`（`llm.json` 讀不懂）、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起從停的那格接著做：直接跑的＝`aos-exec` 同一個工作區；掛 daemon 的＝那隻退 1 時留在表上 `stopped`＋`reason`（11-05 使用者裁「留表標 stopped (Recommended)」）；修好後 `aos-agent llm reset`／`tools reset`（或直接改 stack 裡那份）再 `aos-agent ctl start`，同一個 stack 從停的那格接著做；不要了 `aos-agent ctl rm`（`ctl ls`／`ctl state` 看得到原因）。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。
