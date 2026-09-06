# proto2 — 從零重來的 aos

← [AGENTS](../AGENTS.md)

## aos-exec：跑一個路徑

`aos-exec <path>`——**檔案**→直接執行，工作目錄＝檔案所在資料夾，退出碼原樣傳回；**資料夾**→
讀 `<path>/.aos/inst`（純文字），整段原樣丟給 `os.system()` 跑，工作目錄＝那個資料夾，不解析、
不拆行、沒有批次指令。找不到路徑，或資料夾沒有 `.aos/inst`：印一句錯誤到 stderr，退出碼 2。

## aos-loop：反覆跑 aos-exec

`aos-loop [dir] [--steps N] [--interval SEC] [--stop-when-empty] [--keep-inst]`。`dir` 省略就
用目前目錄。每一步：讀 `.aos/inst`（不存在＝空字串）、**立刻清空**、再把內容丟給 `os.system()`
跑（去頭尾空白後是空的就不跑）。命令想留下一步，就在自己跑的時候把新內容寫回 `.aos/inst`，下一圈會撿到。

- `--steps N`：跑幾步就停（退出碼 0）；不給就無限跑。
- `--interval SEC`：每步之間睡幾秒，預設 1。
- `--stop-when-empty`：讀到空的就以 0 退出；不給的話空的那步不跑、照樣算一步繼續。
- `--keep-inst`：不清空 `.aos/inst`，每圈原樣重跑同一段（寫一次、跑到飽）。

命令退出碼不影響迴圈，但每步結束印一行到 stderr，例如 `aos-loop: step 2 exit 5`。

## aos-agent-step：一個 agent 走一格

`aos-agent-step [dir] [--no-write-inst]`。agent 本體就是一個資料夾，東西全在 `<dir>/.aos/agent/`：
人格 `system-prompt.json`、記憶 `prompts.json`（OpenAI messages 陣列，assistant 訊息只留
`role`／`content`／`tool_calls`）、這輪要加的話 `new-prompts.json`、工具 `tools.json`（`{name,
description, parameters, command}`；`command` 不送 LLM，跑的時候丟 shell、參數 JSON 從 stdin
進去）、LLM 在哪 `llm.json`（`{"dir": "../llm"}`，相對於 agent 資料夾本身）、收新訊息的地方
`new-prompts/`（收走搬進 `new-prompts/archived/`）、上次回覆 `llm-result.json`、走到哪
`state.json`。**agent 自己不打 HTTP**：要問 LLM 就寫一個請求檔丟進隔壁 LLM 資料夾，下一格再去撿。
每次執行只做一格：

| state | 做什麼 | 做完變成 |
|---|---|---|
| `idle` | 收 `new-prompts/` 頂層的檔，每個變一則訊息，寫進 `new-prompts.json` | 有信 `llm`，沒信留 `idle` |
| `llm` | `[人格]＋記憶＋new-prompts`（＋工具）組成 body，丟進 LLM 資料夾的 `requests/`，檔名記進 `state.json` 的 `request` | `wait` |
| `wait` | LLM 資料夾的 `results/<request>` 出現了就讀進 `llm-result.json`、把結果檔拿走、回覆併進記憶 | 撿到 `act`，沒撿到留 `wait`，結果是 `error` 就回 `idle` |
| `act` | `tool_calls` 非空就照 `command` 跑工具、結果收進 `new-prompts`；沒有就印出它說的話、順手落一份到 `replies/` | 有工具 `collect`，沒有 `idle` |
| `collect` | 再收一次 `new-prompts/`，接在既有的 `new-prompts.json` 後面（沒新信也照走） | `llm` |

`state.json` 的 `step` 是被推了幾格（空轉也算），`busy` 是這裡面真做事幾格（`idle` 沒信、`wait`
還沒等到不算）——shared 鐘的子 agent 沒人跟它說話時，`step` 一直漲但 `busy` 不會動。

記憶是在 `wait` 真的撿到回覆才更新的（`prompts.json` 接上 `new-prompts`、清空 `new-prompts.json`），
不是丟請求那格——中途撿不回來的話，這輪講的話才不會憑空消失。

`new-prompts/` 裡每個檔可以是 `{"role": "user", "content": "..."}` 這種 JSON 物件（算一則），
也可以是一串這種物件的 JSON 陣列（照順序各算一則）；陣列裡不是物件的項、或整個讀不成 JSON
的檔，印一行到 stderr 跳過但一樣搬走。沒工具可跑那格說的話會寫成 `.aos/agent/replies/<step
四位數>.json`（`{"role":"assistant","content":...}`），旁邊的人撿得到。**`idle` 開新一輪前先清空
`archived/`**（`collect` 中途補收不清，這一輪收的留到輪完）。每格結束都把 `<aos-agent-step
絕對路徑> .` 寫回 `<dir>/.aos/inst`，讓 `aos-loop` 回來看有沒有新信；`--no-write-inst` 就不寫。

## LLM 資料夾：aos-llm-step／aos-llm-ask

LLM 不是誰的私有功能，是**跟 agent 平起平坐的另一個資料夾**，也靠 `aos-loop` 一格一格轉。
東西全在 `<dir>/.aos/llm/`：引擎 `engine.json`（`{base_url, model, api_key_env}`）、請求箱
`requests/`（一個檔一個請求，內容就是 chat/completions 的 body，至少有 `messages`，可以有
`tools`，但**不含 `model`**——那是 engine.json 的事）、處理完的 `requests/done/`、回覆
`results/<跟請求同檔名>`。誰想用 LLM，就往 `requests/` 丟一個檔，下一格自然會有結果。

- `aos-llm-step [dir]`——走一格：拿 `requests/` 頂層排序後**最舊的那一個**，補上 model 打
  `{base_url}/chat/completions`，整包原始回覆寫進 `results/`、請求搬去 `requests/done/`；沒請求就
  印 `idle` 什麼都不做。打不通：印一行 stderr、請求留在原地下一格再試、退出碼 1。請求讀不成
  JSON：照樣搬走，結果檔寫 `{"error": "..."}`，免得丟請求的人等到天荒地老。
- `aos-llm-ask [dir] [--no-wait]`——從 stdin 讀整包 body 丟進 `requests/<時間戳>.json`，然後每
  0.5 秒看 `results/` 有沒有同名檔，有就把整包印到 stdout、**把結果檔刪掉**（拿走就沒了）；
  Ctrl-C 退出 130。`--no-wait` 只丟不等，把檔名印出來就走。

## 跟 agent 說話：say／listen／talk

- `aos-agent-say [dir] [text]`——把 `text`（省略就整段讀 stdin）寫成一則 `user` 訊息丟進
  `<dir>/.aos/agent/new-prompts/`，檔名是時間戳到微秒，寫到哪印在 stderr。
- `aos-agent-listen [dir] [--new] [--once]`——盯著 `replies/`，每則印 `--- reply 0006 ---` 再印
  content；預設先補印既有的再每 0.5 秒等新的，`--new` 只等新的，`--once` 印完一次就走。
- `aos-agent-talk [dir]`——互動聊天：`你> ` 打一句（`/quit` 或 Ctrl-D 離開），等 `replies/` 冒出
  新檔就印 `agent> `。自己不推格，要另一個終端機的 `aos-loop` 幫忙轉。

## 子世界：aos-agent-spawn

**子 agent 就是父資料夾底下的一個子資料夾**，裡面有它自己的 `.aos/agent/`（人格、記憶、工具、
`state.json`），工具抄父的一份，`llm.json` 換算成指向父用的那個 LLM 資料夾——父是 `../llm`，
子就是 `../../llm`，兩邊共用同一個 LLM。分兩種鐘：

- **shared（時間沒脫節）**——在父的 `.aos/inst` 尾端加一行 `aos-exec <子名>`，父走一格它就跟著
  走一格，父不動它也不動，子自己沒有 loop。
- **own（時間脫節）**——只建資料夾，父不推它。父有 `.aos/agent/daemon.json` 就自動登記給那個
  daemon（名字 `<父名>-<子名>`，子也抄一份），生出來就有人推；沒有就要自己開 `aos-loop
  <子路徑> --keep-inst` 才會走。

`aos-agent-spawn <父資料夾> <子名> <人格文字> [--clock shared|own]`（預設 `shared`）。子名只准英
數字／底線／減號，名字被佔走、或父沒有 `llm.json`，就印一句退 2。

範例 agent 的 `tools.json` 附了一個 `spawn` 工具，所以**agent 可以自己生小孩**：跟它說「生一個叫
helper 的子 agent」，它就會挑好 clock 去呼叫 `aos-agent-spawn`，子資料夾直接長在它旁邊。

## daemon：一個 loop 推所有資料夾

每個資料夾各開一個 `aos-loop` 很快就開不完，所以有 **daemon**：它自己也只是一個資料夾（`.aos/inst`
寫 `aos-daemon-step .`，靠 `aos-loop` 轉），照登記表把別人各推一格。東西在 `<dir>/.aos/daemon/`：
登記表 `registry/<名字>.json`（`{"dir": "路徑", "every": 1}`，`dir` 可絕對可相對——相對是相對於
daemon 資料夾；`every` 是幾格推一次，缺就 1）、走到哪 `state.json`（`{"tick": N}`）。

一格：`tick` 加一，登記表照檔名排序，輪到的就 `aos-exec <那個資料夾>`，每個印一行
`aos-daemon-step: tick 3 llm exit 0`（沒輪到印 `skip`，讀不了或不見印一行跳過）。daemon 永遠回 0。

```sh
proto2/aos-daemon-register proto2/examples/daemon 某個資料夾 [--name 名字] [--every N]
proto2/aos-daemon-unregister proto2/examples/daemon 名字
```

名字省略就用目標資料夾的 basename，`dir` 一律寫絕對路徑（daemon 從哪被叫都不會錯），同名已經
登記過退 2。agent 生 own 的子 agent 時會自己來登記，不用人工補。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先做最小的那句話。另有一篇抒發原文：[2026-09-06 抒發：世界／時鐘／信箱](notes/2026-09-06-world-clock-agent.md)。

## 放進 PATH

`aos-exec`／`aos-loop` 會自動把自己所在的資料夾加進 PATH，`.aos/inst` 裡直接寫工具名就找得到；終端機直接打的 `talk`／`say`／`ask` 要自己設一次：`export PATH="$PWD/proto2:$PATH"`。`llm.json` 的 `../llm` 相對於 agent 資料夾，agent 跟 llm 要當兄弟目錄一起搬。

## 怎麼玩

`examples/daemon` 的登記表已經登記好 `../llm` 跟 `../agent`，所以**只要兩個終端機**：

```sh
proto2/aos-loop proto2/examples/daemon --keep-inst   # 1：daemon 輪流推 llm 跟 agent（LM Studio 要先載一顆模型）
proto2/aos-agent-talk proto2/examples/agent          # 2：聊天
```

也可以各開各的 loop（llm 一個、agent 一個），daemon 只是幫你省終端機。

`examples/agent/.aos/agent/llm.json` 是 `{"dir": "../llm"}`、`daemon.json` 是 `{"dir": "../daemon"}`，
三個資料夾要當兄弟目錄一起搬。agent 沒反應時，先看終端機 1 有沒有印 `打不通`（模型沒載或連不上）、
是不是一直印 `等 LLM`，或 `沒有 .aos/inst`（資料夾沒附心跳指令）。不想開 agent、只想問一句話：
`echo '{"messages":[{"role":"user","content":"1+1=?"}]}' | proto2/aos-llm-ask proto2/examples/llm`。

其他跑法：
```sh
proto2/aos-exec proto2/examples/hello.sh
proto2/aos-loop proto2/examples/loop --stop-when-empty --interval 0
bash proto2/test.sh
```

## 目前刻意不做

鎖、崩潰恢復、fsync、並發、逾時、重試、其他子命令、串流、agent 之間互相講話、批次結構（.aos/inst 就是一段 shell，不是資料）。撞到再說。
