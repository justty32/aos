# proto8/demo — 兩隻 agent 跑一遍

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon，C++）、[bin/README](../bin/README.md)（aos-tick）｜慣例：[CONVENTION](../CONVENTION.md)

```
sh proto8/demo/run.sh      # 在 WSL／Linux 跑
```

`run.sh` 各建一個暫時工作區、放一題 `new/q1.txt`（10-23 改名，原 `inbox/`）、`cd` 進去跑 agent-bob 與 agent-ann（慣例用法 `aos-exec <agent資料夾>`），再跑一次 daemon、最後跑一次 tick（見下）〔10-23 加 agent-dan（假腦），共五段：bob、ann、dan 三隻 agent，加 daemon、tick〕，印工作區內容（`out/`、`done/`；跑完 `new/`、`cur/` 是空的）與整棵 stack 樹（`$AOS_WS/.stack/`，10-23 改名，原 `.aos/`）（每檔印內容），最後把暫時資料夾刪掉，repo 裡不留東西。**PATH 由 `run.sh` 自己放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），agent 裡寫的 `aos-loop`、`aos-fsm`、`aos-exec`、`aos-daemon`、`aos-tick` 要呼叫端事先放進 PATH——`run.sh` 開頭就這麼做：10-23 起前四支是 C++ 的 `proto8/impls/<名>/bin/`（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python；要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)），aos-tick 是 `proto8/bin/`；沒建好 `run.sh` 會先停、說要先建。自己手動跑也一樣（例：`PATH=$PWD/proto8/impls/aos-exec/bin:$PWD/proto8/impls/aos-loop/bin:$PWD/proto8/impls/aos-fsm/bin:$PATH aos-exec --ws <工作區> proto8/demo/agent-bob`）。預設假腦；`AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）指到遠端才用真腦〔10-23：agent-dan 的模型名在它自己的 `.env`（`AOS_BRAIN_MODEL`），只要給 `AOS_BRAIN_URL`，見下〕。**這台電腦不要跑本機模型**（10-19 LM Studio 讓整台 Windows 當機，使用者定「放棄跑本機模型」，[ideas § 6](../thinking/2026-10-19-ideas.md)）。

## agent-bob（混合範本，叫 cathy、cathy 叫 stamp：四層）

入口 `_entry`（預設 `$AOS_ENTRY`；10-19 晚改，原 `.aos/exec`；10-23 改名，原 `_exec`）＝`exec aos-loop loop.json`（10-21 傍晚：設定檔是 aos-loop 唯一的位置參數）；`loop.json`＝`{"exec": "fsm.json", "max": 20}`（`exec` 是 aos-exec 的目標，10-21；10-23 統合一度改叫 `val`、同晚改回 `run`，深夜再改 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」））；`fsm.json` 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`（`AOS_CF`＝aos-exec 實際跑的那份檔），所以它本身就是 aos-exec 的入口、每次 `aos-exec -- fsm.json`（10-21 計畫第 3 段）；表一份看完：idle／act 是子資料夾 `idle/`、`act/`（shell），think 是內嵌單子——10-24 起直接寫在 `exec`：`"exec": {"argv": ["python3", "brain.py"], "stdout": …, "timeout_ms": 120000}`（`python3 brain.py`、stdout 導到 `$AOS_STACK/plan.txt`、逾時 120 秒，aos-fsm 在自己行程內當監工；使用者 10-24「不過exec本來就應該要可以直接放內嵌單子吧」，[thinking 2026-10-24](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)。10-21～10-23 寫成 `"exec": "fsm.json#/states/think/body"`、單子放那格的 `body`、由 aos-exec 跑；fsm 格 10-23 深夜改名，原 `val`）。idle 在 `new/` 空時回 10 讓 loop 停。`brain.py` 挑 `new/` 第一題、搬到 `cur/` 認領（Maildir 的 new → cur）、題名寫 `current.txt`、答案印到 stdout。

act 把 `plan.txt` 當題目交給 `act/tools/cathy/`（另一隻完整 agent，同一套範本；P-32、P-33）：在她的小格 `$AOS_STACK/cathy/` 裡備 `ws/new/<題名>`、`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/cathy`、從 `$sub/ws/out/<題名>` 拿答案寫進 `$AOS_WS/out/`、題目從 `cur/` 搬 `done/`；cathy 失敗（非 0）bob 的 act 說「cathy 失敗」並退 1。cathy 的 act 再經 `act/tools/cathy/act/tools/stamp`（工具，自己的 stack 在 `$AOS_STACK/stamp/`，前面加一行 UTC 時間戳、`runs.txt` 計次）寫她的 out。一次跑完是四層：bob 的 loop／fsm → act → cathy 的 loop／fsm → 她的 act → stamp；`aos-exec --ws <工作區> proto8/demo/agent-bob/act/tools/cathy` 也能單獨跑 cathy。

stack 樹＝呼叫樹：`.stack/{state.txt,current.txt,plan.txt,trace.jsonl}`、`.stack/cathy/{…,ws/{out,done}/q1.txt,stamp/runs.txt}`（P-38）。

## agent-ann（全內嵌對照）

跟 bob 做同一件事（一題一答），零子資料夾：入口 `_entry`＝`exec aos-exec loop.json`，`loop.json` 是 `{"_entry": ["aos-loop", {"$env": "AOS_CF"}], "exec": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}`（10-24 起單子直接寫在 `exec`，原 `"exec": "loop.json#/body"`＋`body`）——loop.json 自己帶 `_entry`，`aos-exec loop.json` 就把 loop 跑起來（10-21 傍晚；跟 bob 的 `exec aos-loop loop.json`、`"exec": "fsm.json"` 對照，兩種都行），`fsm.json` 三格全是單子（10-24 起直接寫在 `exec`，原 `"exec": "fsm.json#/states/<名>/body"`、單子放 `body`），各指一支小腳本——`idle.py`（`new/` 空退 10）、`brain.py`（同 bob 的那份，複製）、`act.py`（`plan.txt` 寫 out、題目從 cur 搬 done）。資料夾裡只有 `_entry`、`loop.json`、`fsm.json`、三支 `.py`，和一份 `.env` 範例（10-22，全是註解、不設任何東西：示範 API key 與 `PATH=${AOS_CD}/bin:${PATH}` 怎麼寫。10-22 起 `.env` 預設不蓋環境裡已有的名字，PATH 那行要從外面叫 `aos-exec --dotenv-override agent-ann` 才生效；旗標只管那一次，入口的 `aos-exec loop.json`、loop 每次、fsm 每格三層照樣各讀一次這份檔但不蓋，所以格裡的 PATH 只多一份 `${AOS_CD}/bin`——原本是四份；10-24 起 loop、fsm 在自己行程內跑單子，loop 每次、fsm 每格那兩層不再經 aos-exec、不再讀這份檔）。適合「格全是一行、不叫工具」的小 agent；要叫工具、要用 sh 搬檔，就回到 bob 的混合寫法。

## agent-dan（真腦＋工具，10-23）

會問真模型、會用工具的問答 agent（範本，混合寫法接 bob：idle 是資料夾，think／act 是內嵌單子）。慣例是 [P-41](../CONVENTION/02-題目stack停錯腦.md)，設計結論在 [thinking 2026-10-23-tool-calls](../thinking/2026-10-23-tool-calls.md)。圖解版（ELI5）：https://claude.ai/artifact/4mhycShcVdr7jJskGWc92V ——agent-dan 改了就跟著更新（新 session 用 Artifact 的 `read` 拿回最新 HTML 再改、照同一網址重發；使用者 10-23「做成artifact。之後我們慢慢做好，這個artifact也會跟着更新」）。

```
agent-dan/
  _entry              #!/bin/sh、exec aos-loop loop.json
  loop.json           {"exec": "fsm.json", "max": 40}
  fsm.json            三態 idle → think → act → idle；think、act 的 exec 直接是單子（逾時 120 秒、60 秒；10-24）
  .env                AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low（模型名；不蓋外面已設的）
  system.txt          核心人格：每次問腦時當 system 訊息送、不進 history
  idle/_entry         同 bob：cur/ 或 new/ 有題退 0，沒題退 10
  brain.py            think 格：認領題目、把 tools/*/tool.json 組成 tools、帶 history 問腦、回覆接一行
  act.py              act 格：有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案
  tools/math/         工具：stdin 收 {"expr": "17*23"}、stdout 印 391（只做四則運算）
  tools/clock/        工具：stdin 不讀、stdout 印 UTC 時間
  tools/*/tool.json   給模型看的說明（OpenAI function 物件去掉 name；工具名＝資料夾名）
```

一題的流程：think 把題目接成一則 user、問腦；腦要叫工具，act 就跑工具（`arguments` 從 stdin 進、stdout 整段是結果，小格 `$AOS_STACK/<名>/`）、把結果接回 history、退 0 回 idle；題目還在 `cur/`，所以 think 帶著 history 再問一次；腦不叫工具了，act 才把回答寫進 `out/<題名>`、題目搬 `done/`。trace 是 `idle think act idle think act idle`。對話在 `$AOS_STACK/history.jsonl`（一行一則 OpenAI message，只附加）。

think、act 兩格的 `exec` 直接寫單子：`{"argv": ["python3", "brain.py"], "timeout_ms": 120000}`（act 同理），aos-fsm 在自己行程內跑、跑的期間 `AOS_CF`＝這份 `fsm.json`、`AOS_CO`＝`/states/think/exec`（10-24 稍晚，使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 2026-10-24](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）。同一天早一點是寫成 `{"$env": "AOS_CF", "$path": "#/states/think/body"}`＋`body`（使用者「先改成不寫死檔名的寫法」），現在不必再指回自己。

**假腦**（沒設 `AOS_BRAIN_URL`，demo 與測試用）：history 最後一則是 user 且有 `clock` 工具就叫一次 `clock`，拿到結果後回 `FAKE ANSWER to: 題目`——不連網也走得完「想 → 工具 → 想 → 答」。

**真腦**：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-dan`（家機的 LiteLLM，不用 key；PATH 照上面放好）。模型名在 `.env`，要換就在那一行前面加 `AOS_BRAIN_MODEL=…`。真跑的工作區放 `~/code/try/agent-dan/`（使用者 10-23「試驗場放在~/code/try」）。

**錯**（都是 stderr 一行 `agent-dan: 代號 原因`、退 1、state 不動、history 不接；修好再跑一次從同一格接著做）：`BrainFailed`（腦連不上、HTTP 非 2xx）、`ReplyBad`（回覆不是 OpenAI 的形狀）、`ToolUnknown`（叫了 `tools/` 裡沒有的工具）、`ArgumentsBad`（`arguments` 不是 JSON）、`ToolFailed`（工具退非 0）。

## agent-eve（agent 當工具，10-24）

把一隻 agent 包成另一隻 agent 的腦可以叫的工具（嘗試性質；使用者 10-24「把agent當做工具拿去給agent呼叫，比如一個專精於修改python程式的agent」）。設計、代定、邊緣狀況在 [thinking 2026-10-24-agent-as-tool](../thinking/2026-10-24-agent-as-tool.md)。

```
agent-eve/                主 agent：照抄 agent-dan（brain.py、act.py 只改錯誤訊息開頭），act 逾時放寬到 30 分鐘
  system.txt              改 Python 的事交給 pyfix、task 寫清楚、回答前看 diff
  tools/pyfix/
    tool.json             給 eve 的腦看：task（必填）、dir（相對於工作區，預設 .）
    _entry                轉接（python3）：stdin 的 task → 子 agent 的 new/task.txt；跑完把 out/task.txt＋實際 diff 印到 stdout
    agent/                子 agent（pyfix-agent）：也是一整隻 agent-dan 範本，自己的 system.txt、.env、loop.json（max 60）
      tools/              list_files、read_file、write_file、edit_file、run_python（只碰 $PYFIX_DIR；run_python 逾時預設 30 秒）
```

每次呼叫 pyfix 開一個新小格 `$AOS_STACK/pyfix/runs/<三位數>/`：`ws/`（子 agent 收題、交答案）、`stack/`（它的 history、trace）、`before/`（改之前的備份）；子 agent 要改的程式碼是 `PYFIX_DIR`＝`$AOS_WS/<dir>`。子 agent 用 `aos-exec --dotenv-override` 叫，所以模型用它自己 `.env` 的。子 agent 失敗＝`pyfix: AgentFailed …`、退 1，eve 的 act 當 `ToolFailed` 停下（同 agent-dan）；其他代號 `AnswerMissing`、`DirBad`、`ArgumentsBad`、`StackMissing`，子工具沒設 `PYFIX_DIR`＝`DirMissing`（路徑跑出去、edit 對不上這類模型的錯，照實回給模型、不算失敗）。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-eve`；試驗場 `~/code/try/agent-as-tool/`（`setup_ws.py` 建一個有 bug 的 `proj/`，LiteLLM 沒開時用 `fake_brains.py` 劇本）。沒設 `AOS_BRAIN_URL`＝假腦，eve 沒有 clock 工具、會直接答 `FAKE ANSWER`，不會叫 pyfix。測試 `test_eve.py`。

## agent-fay（claude／codex CLI 當工具、人可以接進去，10-24）

接 agent-dan 的範本，腦有兩個工具 `claude`、`codex`：腦給一段話（`{"prompt": "..."}`），工具交給 Claude Code／Codex CLI 做、把回答交回。同一個工具一直接著同一段對話（id 在小格的 `session.txt`）。人可以**接進那段對話的互動畫面**跟它直接講話，再跳出、畫面留在背景，agent 之後照樣用。設計與實跑：[thinking 2026-10-24-cli-tools](../thinking/2026-10-24-cli-tools.md)（使用者 10-24「讓claude cli的呼叫變成工具，還有codex cli的也是……我可以透過一些指令接入操作」「都按建議做」）。

```
agent-fay/
  _entry、loop.json、fsm.json、.env、idle/、brain.py、act.py   同 agent-dan（假腦改成把題目交給 claude 工具；act 逾時 15 分鐘）
  system.txt          腦的人格：有 claude、codex 兩個幫手，看檔或程式判斷就交代給它們
  cli_session.py      做法：畫面沒開＝非互動（claude -p --resume／codex exec resume）；畫面開著＝tmux 貼字、等 hook 回答
  attach              接進某個工具的互動畫面：attach claude｜attach -d codex（只開不接）｜attach（列狀態）
  tools/claude/       _entry（stdin {"prompt"} → stdout 回答）、tool.json（給模型看）、cli.json（怎麼叫 CLI：保守旗標）
  tools/codex/        同上
```

**接進去**（在工作區裡打，不是 agent 資料夾）：`cd <工作區> && <repo>/proto8/demo/agent-fay/attach claude` → 進到 Claude Code 的畫面（沒開就先開、`--resume` 接上 agent 用過的那段）→ 直接打字 → **Ctrl-\ 跳出**（畫面留在背景）；在畫面裡 `/exit` 才是真的關掉。畫面是 tmux，socket 在 `$AOS_WS/.stack/<工具名>/tty.sock`。有人接著時 agent 叫工具會停下（`SessionBad`），跳出後再跑一次 agent。

**權限**（`cli.json`，要放寬就改那份）：claude 只給 `Read,Glob,Grep`、`--permission-mode dontAsk`、不載 MCP、`--model sonnet`、非互動 `--max-budget-usd 0.5`；codex `sandbox_mode="read-only"`、`approval_policy="never"`。CLI 在 `$AOS_WS` 裡跑。

**錯**：stderr 一行 `cli_session: 代號 原因`、退 1（act 當 `ToolFailed` 停下）——`PromptBad`、`CliMissing`、`CliFailed`、`ReplyMissing`、`SessionBad`、`CfgMissing`／`CfgBad`。測試 `test_fay.py` 用假的 claude／codex，不花額度；要 tmux。

## pi-tools 與 agent-pip（仿 pi coding agent 的基本工具，10-24）

`pi-tools/` 是一套可重用的寫程式工具，仿 [pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent) 預設的四個：`read`（讀檔，最多 2000 行或 50KB、提示 offset 接著讀）、`write`（建檔或整份蓋掉）、`edit`（`edits: [{old_text, new_text}]`，每段對原檔比、要唯一、不重疊，全有或全無）、`bash`（在 `$AOS_WS` 裡跑一行指令，留最後 2000 行或 50KB，逾時預設 30 秒、上限 300 秒、整群停）。每個都是資料夾程式＋`tool.json`（P-41），arguments 從 stdin 進、stdout 是結果。read／write／edit 的路徑從 `$AOS_WS` 算、不能跑出去（`PathBad`，符號連結也算）；bash 的指令本身擋不住。錯：stderr 一行「工具名: 代號 原因」、退 1，同一行也印在 stdout 給腦看。

`agent-pip/` 是掛上這套（與下面的 file-tools）的 coding agent：從 agent-dan 照抄，`tools/` 裡是十二個指到 `../../pi-tools/<名>`、`../../file-tools/<名>` 的符號連結，`system.txt` 照 pi 的精神寫短版。跟 agent-dan 只差一條：**工具出的問題回給腦、不停**（工具退非 0、叫了沒有的工具、arguments 不是 JSON，都接成一則 tool 訊息），因為 edit 找不到原文是常事、停下來重跑會卡在同一個呼叫。真跑：`AOS_BRAIN_URL=http://localhost:4000/v1 AOS_STACK=<工作區外的資料夾>/ aos-exec --ws <工作區> proto8/demo/agent-pip`（stack 放工作區外，免得腦用工具改到自己的對話）。試驗場 `~/code/try/pi-tools/`。設計與 pi 的調查在 [thinking 2026-10-24-pi-tools](../thinking/2026-10-24-pi-tools.md)；測試 `tests/test_pi_tools.py`。

`file-tools/` 是資料夾與檔案的漸進工具（使用者「資料夾修改和檔案這兩個工具我需要特別設計」），**輸出一律 JSON**：`ls`（子項陣列：型別、大小、時間、子項數、`aos` 標記哪些有 `_entry`／`.env`／`tool.json`…、JSON 檔的頂層 key；分頁）、`stat`（單一個的屬性）、`view`（JSON 照 `pointer` 一層層展開、小的直接給值；大文字檔先給大綱再看 `start`／`end` 那段）、`json_edit`（`set: {指標: 值}`、`del: [指標]`，先檢查再交給 aos-json 原子寫入）、`mkdir`、`move`、`copy`（目的地有東西就不做）、`trash`（刪除＝搬進 `$AOS_WS/.trash/<時間>/`，可救回）。路徑限制同 pi-tools；共用碼在 `file-tools/common.py`。json_edit 要 PATH 上有 `aos-json`（`proto8/impls/aos-json/bin`）。測試 `tests/test_file_tools.py`。

## agent-meg（記憶庫，10-24）

照抄 agent-dan 的問答 agent，多一個跨對話保留的**記憶庫**（heap）：對話（stack）清空了，記得的事還在。設計與考古在 [thinking 2026-10-24-memory](../thinking/2026-10-24-memory.md)（使用者「還有在記憶庫裏存放各類東西」「我記得proto7就有那些，去看看那些方法」「都按建議做」）。

```
agent-meg/
  brain.py            同 agent-dan，只多一件事：每次問腦前把記憶庫的偏好（全部）＋跟題目有關的 5 筆接在 system 後面（不進 history）
  act.py、fsm.json、loop.json、idle/   同 agent-dan
  system.txt          教腦什麼該存、只存確認過的、衝突以現在說的為準
  tools/memory/       唯一的工具：op＝save（同類同標題＝覆蓋）／search（關鍵字）／read／forget（搬去 archive）
    heap.py           記憶庫的讀寫（brain.py 也用它）

$AOS_HEAP/            記憶庫（沒設＝$AOS_WS/.heap/）：index.json（頂層，wf-table/1）→ <類>/index.json → <類>/001.md
                      六類 prefs、facts、outcomes、gotchas、snippets、skills；forget 的搬 archive/<類>/；寫入持 .lock
```

位置由叫的人給（像 stack，C-67）：兩隻 agent 的 `AOS_HEAP` 指同一個＝共用記憶，各指各的＝私有。人也能直接叫工具：`echo '{"op": "search", "query": "縮排"}' | AOS_HEAP=<庫> proto8/demo/agent-meg/tools/memory/_entry`。錯：模型的錯照實回給它；庫的索引壞了＝`HeapBad`（工具退 1、或 think 退 1）。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-meg`；試驗場 `~/code/try/memory/`（`run.py`：第一題記兩件事、換全新 stack 問第二題；LiteLLM 沒開自動用 `fake_brain.py`）。沒設 `AOS_BRAIN_URL`＝假腦，直接答 `FAKE ANSWER`（附上記憶的字數）。測試 `test_meg.py`。

## agent-gus（小念頭，10-24）

先規劃、再把每一步 fork 成「小念頭」、回來只帶結論的 agent（照抄 agent-dan，多兩格；嘗試性質）。設計、考古（proto7-2 的 step 包）、照推薦定的、邊緣狀況在 [thinking 2026-10-24-thoughts](../thinking/2026-10-24-thoughts.md)（使用者「讓agent先規劃一件事的steps，然後每個steps都fork出去，回來只帶結論」「fork出去的東西，又可以繼續steps」「都按建議做」）。

```
agent-gus/
  fsm.json            idle → plan → fork → think → act → idle（plan 120 秒、fork 1 小時、think 120 秒、act 180 秒）
  plan.py             認領題目、接進 history、請腦回 {"context", "steps": [{id, goal, needs}]} → $AOS_STACK/steps.json；
                      腦回 steps: []＝不拆；到深度上限或額度不夠＝不問腦、不拆
  fork.py             每步起一個小念頭＝再跑一次自己（aos-exec --ws <小格>/ws .），needs 齊了才起、同時最多 THOUGHT_PARALLEL 個；
                      小念頭 out/ 裡那段答案＝結論，全到齊後一步一則接進 history：「小念頭 sN 的結論（目標：…）：…」
  brain.py、act.py    think／act 同 agent-dan（act 交答案時 steps.json 收進 plans/）
  thought.json        給別的程式叫一個小念頭：stdin {"goal", "context"?, "needs"?: [{id?, goal, conclusion}]} → stdout 只有結論
  shared.py           各格共用；tools/run_python/ 工具：stdin {"code"} → 結束碼與輸出
  .env                模型名＋上限：THOUGHT_MAX_STEPS 4、THOUGHT_MAX_DEPTH 2、THOUGHT_MAX_TOTAL 10、THOUGHT_PARALLEL 3、
                      THOUGHT_TIMEOUT_S 900、THOUGHT_MAX_CHARS 1500（深度 THOUGHT_DEPTH、額度 THOUGHT_BUDGET 由 fork 往下帶）

$AOS_STACK/thoughts/<id>/   小格：ws/（小念頭的工作區，題目 new/<id>.txt、答案 out/<id>.txt）、stack/（它自己的，可能又有 thoughts/）、log.txt
$AOS_STACK/budgets/<plan_id>/  整棵念頭樹的額度（一個檔＝一個小念頭）；usage.jsonl 每次問腦一行（usage、送出字數）
```

**別的程式叫一個小念頭**（JSON 工具集「找到要修改的 key → 提供值」那種）：`echo '{"goal": "找到要修改的 key", "context": "…"}' | AOS_STACK=<小格>/ aos-exec proto8/demo/agent-gus/thought.json`，stdout 只有結論、過程在 `<小格>/runs/NNN/`；下一步把這次的結論放進 `needs` 再叫一次。錯：`agent-gus: StepBad`（stdin 不對）、`ThoughtFailed`，退 1。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-gus`；沒設＝假腦（第 0 層拆兩步、s2 帶 s1 的結論，答 `FAKE ANSWER … （彙整了 2 個小念頭的結論）`）。試驗場 `~/code/try/thoughts/`（`run.sh` 用 `fake_brains.py` 跑排序比較題、`measure.py` 印念頭樹與 context 省多少）。錯：同 agent-dan，另有 `PlanBad`（規劃不是 JSON、超過步數、needs 指錯或繞圈）、`ThoughtFailed`（小念頭退非 0、逾時、沒交答案；同批其他的照跑完，重跑只補失敗的、在原小格接著做）。測試 `test_gus.py`。

## agent-kai（按意圖組 context，10-24）

照抄 agent-dan，只改「送給腦的是什麼」：`$AOS_STACK/history.jsonl` 照舊完整、只附加，但問腦時不送整份，而是按這題的意圖現組一份工作 context（使用者 10-24「現在history.jsonl就是一直累積，但問題在於那太多冗餘資訊了，我希望AI能夠按照意圖去做」）。設計、對比數據、邊緣狀況在 [thinking 2026-10-24-intent-context](../thinking/2026-10-24-intent-context.md)。

```
agent-kai/
  brain.py            組 context：system.txt ＋ 先前對話的目錄（一題一行）＋〔有記憶庫就附幾筆〕＋ 挑出來的舊題（只有問題與結論）＋ 這題的完整訊息
                      挑：上一題、指代詞（剛剛、那個…）再加一題、「第 N 題」、字面重疊最多兩題；整份粗估 ≤ KAI_FULL_UNDER（1500 token）就全送
  act.py              同 agent-dan，只多給工具 RECALL_HISTORY＝自己的 history.jsonl
  system.txt          告訴腦它看到的不是全部、不夠就 recall 或重查、回答把關鍵寫完整
  tools/recall/       op＝search（關鍵字找舊題）／read（展開一題；detail=true 連當時的工具原始輸出）
    turns.py          把 history 切成題、照意圖挑（brain.py 也用它）
  tools/read          → ../../pi-tools/read（符號連結）；math、clock 同 agent-dan
  （選配）tools/memory → ../../agent-meg/tools/memory：放了就每題自動 search 記憶庫 3 筆附進 system

$AOS_STACK/context.jsonl   每次組了什麼：mode（full／intent）、picked（[題號, 原因]）、粗估 token、整份全送的話多少
```

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-kai`；沒設＝假腦（同 agent-dan）。對比腳本 `python3 proto8/tests/bench_intent_context.py [--upstream http://localhost:4000/v1]`：15 題跳來跳去的對話，各跑 dan（整份）、kai、kai0（kai 拿掉 recall），結果放 `~/code/try/intent-context/runs/<時間>/`。10-24 LiteLLM 沒開、用「照證據回答」的假腦：粗估 token 合計 dan 67K、kai 42K（−37%）、kai0 31K（−54%），答對 15／15／14。錯：同 agent-dan；recall 自己的 `recall: HistoryMissing`（沒設 `RECALL_HISTORY`）、`HistoryBad`。測試 `test_kai.py`。

## self-improve（自我改進流程，10-24）

給一個目標和「預想的結果」（判準），跑函數、判定、沒達到就讓改進者改，直到達成或預算用完（嘗試性質；使用者 10-24「我想要一套自我改進流程，也就是給了一個目標，和我們預想達成的結果，然後去跑這個函數，然後如果沒達到結果，那函數自己(或另一個函數)就會去改進函數。」）。設計、代定、邊緣狀況在 [thinking 2026-10-24-self-improve](../thinking/2026-10-24-self-improve.md)。

```
self-improve/             aos-exec --ws <交辦的工作區> proto8/demo/self-improve
  _entry、loop.json        exec aos-loop loop.json；loop 不設 max（預算由 judge 管）
  fsm.json                 run → judge → improve → run（三格都是內嵌單子）
  run.py judge.py improve.py common.py
  improver/                改進者：從 agent-pip 照抄的 agent（工具出錯回給腦），多記 token 用量；.env 模型 chatgpt-gpt-6-luna-low
    tools/read、write、edit   符號連結到 ../../../pi-tools
    tools/try_run          在 target/ 的暫時複本上跑一次，回結束碼、stdout、stderr
```

交辦的工作區：`goal.txt`（目標）、`target/` 或 `target.json`（要改的函數，原版不動）、`judge/cases.json`（一組例子 `[{"args", "stdin", "stdout", "code"?, "hidden"?, "timeout_ms"?}]`，`hidden` 的失敗時只說幾組沒過）或 `judge/check`（檢查程式，`IMPROVE_TARGET`＝函數複本，退 0＝達成、stdout＝給改進者的回饋）、`budget.json`（選填 `{"rounds": 5, "elapsed_ms": 1800000, "tokens": 500000}`）。成果：`out/best/`（最好的一版）、`out/report.txt`（每一版從哪版改、幾分、改了什麼、改進者說了什麼）、`out/result.json`。每一版拍在 `$AOS_STACK/versions/vNNN/`（`target/`、`verdict.json`、`diff.txt`、改進者那次的 `improve/ws`、`improve/stack`），新的一版一律從最好的那版改（同分取最早的）。

改進者的工作區只有 `new/task.txt`（目標、這版的判定、看得到的失敗例子、各版分數）和 `target/` 複本，判準不在裡面、工具出不去、沒有 bash；改完只收 `target/`。結束碼：達成 0（judge 退 10）、預算用完 2（`self-improve: BudgetSpent …`，改大 `budget.json` 再跑接著改）、改進者失敗 1（`ImproverFailed`，再跑重開這一輪）。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/self-improve`；試驗場 `~/code/try/self-improve/`（`setup_ws.py` 建有 bug 的 wordfreq＋8 組例子，LiteLLM 沒開時用 `fake_brain.py` 劇本：1/8 → 4/8 → 改壞 1/8 → 從 v001 重來 8/8）。沒設 `AOS_BRAIN_URL`＝假腦，改進者直接答、不改檔，跑到預算用完。測試 `test_self_improve.py`。

## daemon（一個 daemon 同時管 bob、ann，10-20）

`daemon/_entry`＝`exec aos-daemon daemon.json`；`daemon.json` 是 `{"max": 10, "interval_ms": 200, "ctl", "state", "loops": {"bob": …, "ann": …}}`（`loops` 10-23 統合前叫 `children`），每個子項是一份 loop 設定：`{"exec": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}, "max": 1}`（ann 同樣；10-24 起單子直接寫在子項的 `exec`，子 loop 在自己行程內跑它。相對路徑照舊從 daemon 的 cwd＝`demo/daemon/` 算：子 loop 經 aos-exec 起、cwd 是小格，所以 daemon 寫小格時給單子補上 `"cwd": <daemon 的 cwd>`（相對的 `$ref` 也轉成絕對）。10-21～10-23 寫成 `"exec": "daemon.json#/loops/bob/body"`＋`body`，daemon 寫小格時把那個目標轉成絕對路徑）——子 loop 跑一次那隻 agent，工作區是 `$AOS_WS/bob`、`$AOS_WS/ann`。`run.sh` 最後一段建暫時工作區、在 `bob/new/`、`ann/new/` 各放一題、`aos-exec` daemon：它跑 10 次（約 2 秒）就結束、結束前收掉子項。stack 樹：`.stack/state.json`（daemon 的 state，`loops` 表）、`.stack/bob/`、`.stack/ann/`（各子項的小格：daemon 寫的 `loop.json`（單子補了 `cwd`、帶 `_entry`）、子 loop 的 `state.json`、`stderr.txt`，以及那隻 agent 自己的 `state.txt`、`current.txt`、`plan.txt`、`trace.jsonl`…——agent 的 stack 就是小格，因為 `AOS_STACK` 已經有值、aos-exec 沿用）。子 loop 結束後不重起，所以表上兩項最後都是 `done`（子 loop 自己結束；daemon 收掉的才是 `stopped`，10-23 統合前兩種都叫 `exited`）、`code` 0。state.json 長這樣：`{"kind": "state", "phase": "done", "runs": 10, "max": 10, …, "loops": {"bob": {"pid", "started_at_ticks", "phase": "done", "code": 0, "signal": null}, …}, "code": 0, "pid", "started_at_ticks", "boot_id", "at": "2026-10-23T02:46:30.317+00:00"}`；各 agent 的 `trace.jsonl` 一行 `{"at": "…T02:46:27.633+00:00", "state": "idle", "code": 0, "signal": null, "elapsed_ms": 14}`。

## tick（時鐘，10-21 晚）

`tick/_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"exec": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tick.txt"}]}, "max": 5}`——loop 跑 5 次，每次在自己行程內跑那張單子 `aos-tick $AOS_STACK/tick.txt`（10-24 起；原 `"exec": "loop.json#/body"`＋`body`、每次 `aos-exec -- loop.json#/body`），所以跑完工作區的 `.stack/tick.txt` 是 `5`（C-44：tick-tock 就是一個時鐘；N-01 大家抬頭讀這個檔）。節奏、停交給 loop：要隔多久走一格就在 loop.json 加 `interval_ms`，要能暫停就加 `ctl`、寫 `{"paused": true}`。程式見 [bin/README 的 aos-tick](../bin/README.md)。

## 測試

`python3 -m unittest discover -s proto8/tests`（10-23 起跑 impls 的 C++ 四支＋bin 的 aos-tick，先建 impls）：`test_loop.py`（直接叫 aos-loop：訊號、PATH、`interval_ms`／`ctl`／`state` 窗、命令列（10-21 傍晚：設定檔是唯一的位置參數、`exec` 陣列、`檔#/指標`））、`test_daemon.py`（aos-daemon）、`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與 cathy／stamp 巢狀）、`test_exec_rules.py`（aos-exec 的新規則：命令列旗標（10-21）、找入口、`#/`、四種入口、`AOS_CF`／`AOS_CD`）、`test_inst.py`（inst 單子：經 aos-exec 跑；10-23 前另直接叫 Python 的 aos_inst 庫）、`test_fsm.py`（aos-fsm）、`test_tick.py`（aos-tick 與 demo/tick）、`test_dan.py`（agent-dan，10-23：用一支假 server 照劇本回 `tool_calls`／答案；連真模型的案例在 LiteLLM 不在時 skip）。

舊的 demo（daemon、fsm、paint、kernels、tasks、tick、once、`aos-demo`）10-19 進 git 歷史（daemon 10-20、tick 10-21 晚照新做法重做，見上），見 git 5546be29（刪除前的最後一個樣子）。
