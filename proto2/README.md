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
- **own（時間脫節）**——資料夾建好就自動 `aos-daemon register <子路徑> --no-wait` 跟 daemon 要一個自己
  的時鐘；沒設 `AOS_DAEMON_DIR` 就只建資料夾，印一句要自己開 `aos-loop <子路徑> --keep-inst`。

`aos-agent-spawn <父資料夾> <子名> <人格文字> [--clock shared|own]`（預設 `shared`）。子名只准英
數字／底線／減號，名字被佔走、或父沒有 `llm.json`，就印一句退 2。

範例 agent 的 `tools.json` 附了一個 `spawn` 工具，所以**agent 可以自己生小孩**：跟它說「生一個叫
helper 的子 agent」，它就會挑好 clock 去呼叫 `aos-agent-spawn`，子資料夾直接長在它旁邊。

## daemon：一個常駐 kernel，一個世界一個時鐘

每個資料夾各開一個 `aos-loop` 很快就開不完，所以有 **daemon**：一個一直跑著的進程（kernel），每隔一
小段時間看有沒有人丟請求進來，照請求開／關／暫停時鐘。**一個時鐘就是一個獨立的 `aos-loop <世界>
--keep-inst` 進程**，自己一個 process group——暫停 SIGSTOP、續跑 SIGCONT、關掉 SIGTERM，排程直接用
Linux 的輪子。家在 `AOS_DAEMON_DIR`（例如 `~/.aosd`，**不在 repo 裡**，第一次 start 自己建）：
`kernel.json`（pid／tick）、`kernel.log`、`requests/`（請求檔，處理完搬去 `requests/done/` 多一個
`result`）、`clocks/<id>.json`、`logs/<id>.log`。`id` 是世界絕對路徑的 percent-encoding（`/tmp/a/b` →
`%2Ftmp%2Fa%2Fb`：可逆、不撞名；超過 200 bytes 退成 `sha256(路徑)`），真路徑一律看檔裡的 `dir`——`ls`
印的也是 `dir`。**一個路徑只能有一個時鐘。**

```sh
aos-daemon-kernel start|restart|stop|ls [daemon 目錄]    # 不給就用 AOS_DAEMON_DIR，都沒有退 2
aos-daemon register|unregister|pause|continue <世界> [--config x.json] [--no-wait]
```

- `aos-daemon` 只把請求檔丟進 `requests/`，等 `done/` 冒出同名檔印結果；kernel 沒在跑就不等、請求先放
  著。`--config` 例如 `{"interval": 2, "user": "bob"}`：幾秒一格（預設 1）、用誰的身份跑（不給＝繼承呼
  叫者；要換身份 kernel 得是 root 跑的，內部靠 `runuser`）。`ls` 一行一個時鐘（state／pid／interval／
  restarts／user／dir），第一行是 kernel 自己，沒 kernel 也看得到。
- **stop 只收進程、不改時鐘檔**（kernel 不在時 `ls` 把這種鐘顯示成 `stopped`），下次 `start` 接回
  來：pid 活著就認領、running 而 pid 死了照原設定重開，進度在世界自己的資料夾裡。**掛了也自動重
  開**：kernel 每格巡一遍，running 的進程不見了就再開一個、`restarts` 加一；`dead` 只代表「重開不起
  來」（資料夾不見了之類），下一格還會再試，資料夾回來就自己變回 running。
- **暫停的鐘不受 kernel 開關影響**：一個被 pause 掉的鐘，要麼被重新 register 或 continue 後才會繼續
  跑，否則 kernel 的 start／stop 不會影響到他——`start` 不重開它、巡邏也不標 dead；`continue` 進程還
  在就 SIGCONT，不在就重開一個；register 到 running／paused 的路徑會被擋（叫你用 continue 或先
  unregister）。
- 幾千個時鐘就是幾千個小 json 檔，現在夠用；管理介面、合併檔案是以後的事，不歸 kernel 管。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先做最小的那句話。另有一篇抒發原文：[2026-09-06 抒發：世界／時鐘／信箱](notes/2026-09-06-world-clock-agent.md)。

## 放進 PATH

`aos-exec`／`aos-loop` 會自動把自己所在的資料夾加進 PATH，`.aos/inst` 裡直接寫工具名就找得到；終端機直接打的 `talk`／`say`／`ask` 要自己設一次：`export PATH="$PWD/proto2:$PATH"`。`llm.json` 的 `../llm` 相對於 agent 資料夾，agent 跟 llm 要當兄弟目錄一起搬。

## 怎麼玩

```sh
export PATH="$PWD/proto2:$PATH"
export AOS_DAEMON_DIR=~/.aosd
aos-daemon-kernel start                     # kernel 常駐起來（LM Studio 要先載一顆模型）
aos-daemon register proto2/examples/llm     # LLM 資料夾一個時鐘
aos-daemon register proto2/examples/agent   # agent 一個時鐘
aos-agent-talk proto2/examples/agent        # 聊天（另一個終端機 aos-daemon-kernel ls 看誰在跑）
aos-daemon pause proto2/examples/agent      # 凍住它（真的送 SIGSTOP），continue 再放它走
aos-daemon-kernel stop                      # 玩完，時鐘一起收掉
```

時鐘的輸出在 `$AOS_DAEMON_DIR/logs/`：agent 沒反應就去那裡看有沒有「打不通」（模型沒載或連不上）、是
不是一直「等 LLM」、或「沒有 .aos/inst」。不想開 daemon 也行，一個終端機開一個 `aos-loop <資料夾>
--keep-inst` 效果一樣。其他跑法：`aos-exec examples/hello.sh`、`aos-loop examples/loop
--stop-when-empty --interval 0`、`bash proto2/test.sh`；只想問一句話不開 agent：`echo
'{"messages":[{"role":"user","content":"1+1=?"}]}' | proto2/aos-llm-ask proto2/examples/llm`。

## 目前刻意不做

鎖、fsync、並發、逾時、重試、其他子命令、串流、agent 之間互相講話、批次結構（.aos/inst 就是一段 shell，不是資料）。撞到再說。
