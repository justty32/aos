# proto2 — 從零重來的 aos

← [AGENTS](../AGENTS.md)

## aos-exec：跑一個路徑

`aos-exec <path>`——**檔案**→直接執行，工作目錄＝檔案所在資料夾，退出碼原樣傳回；**資料夾**→讀 `<path>/.aos/inst`（純文字），整段原樣丟給 `os.system()` 跑，工作目錄＝那個資料夾，不解析、不拆行、沒有批次指令。找不到路徑，或資料夾沒有 `.aos/inst`：印一句錯誤到 stderr，退出碼 2。

## aos-loop：反覆跑 aos-exec

`aos-loop [dir] [--steps N] [--interval SEC] [--stop-when-empty] [--keep-inst]`。`dir` 省略就用目前目錄。每一步：讀 `.aos/inst`（不存在＝空字串）、**立刻清空**、再把內容丟給 `os.system()` 跑（去頭尾空白後是空的就不跑）。命令想留下一步，就在自己跑的時候把新內容寫回 `.aos/inst`，下一圈會撿到。

`--steps N` 跑幾步就停（不給＝無限）、`--interval SEC` 每步睡幾秒（預設 1）、`--stop-when-empty` 讀到空的就以 0 退出、`--keep-inst` 不清空 `.aos/inst`。命令退出碼不影響迴圈，但每步印一行到 stderr。

## aos-agent：一個 agent 走一格

**指令分兩種**：`aos-agent` 是 agent 自己跑的狀態機；`aos-user` 是給人說話、聽、看狀態、生小孩的殼。

**一個 agent 就是一個世界資料夾。** `.aos/` 裡只有一句 `inst`，其他都放在本體資料夾（home）。`--home` 相對於世界，不給就是 `.`：

```
xxx/.aos/inst              aos-agent exec . --home agent
xxx/<home>/system-prompt.json   人格 {"role":"system","content":"..."}
xxx/<home>/prompts.json         記憶（OpenAI messages 陣列）
xxx/<home>/tools.json           {"packs": [...], "tools": [...]}
xxx/<home>/llm.json             {"dir": "../llm", "priority": 1, "engine": "..."}（可有可無）
xxx/<home>/state.json           走到哪、旁線 pending、空白回覆數
xxx/<home>/contacts.json        通訊錄（名字 → 世界路徑）
xxx/<home>/parent.json          父是誰（小孩才有）
xxx/<home>/kids.json            小孩名冊
xxx/<home>/inbox/<來源>/*.json       沒讀的信
xxx/<home>/inbox/<來源>/read/*.json  讀過的信
xxx/<home>/outbox/<四位數>.json      它自己說的話
xxx/<home>/llm-result.json      上次 LLM 的整包原始結果
xxx/<home>/kids/<名字>/         它生的小孩（每個都是完整的世界資料夾）
```

`llm.json` 的 `dir` 相對於世界資料夾；沒寫就看 `AOS_LLM_DIR`，再沒有就找 `../llm`。`examples/agent` 的 home 是 `agent`，`examples/agent-flat` 是 `.`。`aos-user` 沒給 `--home` 時會從 `.aos/inst` 撈。

`aos-agent exec <世界> [--home DIR]` 一次走一格，五格輪流走：

| state | 做什麼 | 做完變成 |
|---|---|---|
| `idle` | 掃一遍 `inbox/*/`（不含 `read/`），有沒讀過的信就接進記憶；通知過卻一直沒讀的，閒滿 30 格再提醒一次 | 有信 `llm`，沒信留 `idle` |
| `llm` | 人格＋工具包預設 prompt＋記憶（＋工具清單）寫成請求丟進 LLM 資料夾的 `requests/` | `wait` |
| `wait` | 撿主線 LLM 結果；缺鐘立刻報錯。請求還在 LLM 世界排隊或執行中就一直等（最多 1800 格；等的格不算每題上限），請求不見了結果又沒出現才 60 格放棄。模型把工具呼叫寫成文字：認得的工具救回成正式 `tool_calls`，救不回來就當協定錯誤、同題重送一次 | 撿到 `act`；錯誤回 `idle`；放棄也回 `idle`；重送回 `llm` |
| `act` | 有 `tool_calls` 就跑工具、結果接進記憶；沒有就把話印出來、落一份到 `outbox/` | 有工具 `collect`，有文字 `idle`；只回空白就不寫 outbox、記一次後回 `idle` |
| `collect` | 再掃一次信箱（沒新信也照走） | `llm` |

`llm.json` 可設每題動作格數硬上限 `max_steps_per_question`（預設 60）與每日 `max_tokens_per_day`。睡著空等旁線、主線排隊等模型回，都不算動作格；超過會回一句話等使用者，新 user 信會重置題目格數。`status` 九欄列狀態、等待、缺鐘、最後錯誤、格數、今日用量與最近五題格數。agent 不寫 `.aos/inst`，避免洗掉 shared 小孩。

旁線包只用 `Ctx.send/pending/cancel/sleep_until`。agent 睡著時不叫主線 LLM；共用層獨占 `results/`，保存到 `<home>/side/<kind>/<id>.json` 再叫該包 `on_result`。逾時、失敗、取消、缺鐘都走同一路並回一則聊天錯誤。

### 信箱：一個來源一個資料夾

一封信就是一個 JSON 檔：`{"from": "bob", "time": "...", "content": "..."}`，也可放一個信件陣列。來源就是 `inbox/` 底下的資料夾名。

- `idle` 掃到未讀就去問 LLM，但**不會把信整包塞進 prompt**，只加一句來源摘要，剩下讓模型用信箱工具讀。
- **同一封信只通知一次**（記在 `state.json` 的 `announced`）；信被讀掉就自動掉出清單。
- **來源 `user` 例外**：內容直接當 user 訊息接進記憶（前面加 `[user] `），檔案當場搬進 `read/`。
- 讀過的信搬進該來源的 `read/`，不會再算未讀。

### 工具包：一包一檔

`tools.json` 長這樣：

```json
{"packs": ["mailbox", "communication", "fs", "self", "memory", "kids", "cost"],
 "tools": [{"name": "say", "description": "...", "parameters": {...}, "command": "..."}]}
```

`packs` 列到誰就載誰。**一個工具包就是一個 `.py` 檔**，放在 `packs/<名字>.py`——先找 agent
自己的 `<home>/packs/`，再找 aos 內建的 `proto2/packs/`。一包自帶 `TOOLS`、`PROMPT`、
`run(name, args, ctx)`，也可以帶掛勾。認不得的包名印一句就跳過。

| 包名 | 一句話 | 文件 |
|---|---|---|
| `bigmem` | 送 SQLite 記憶世界，睡到結果回來。 | [docs/bigmem.md](docs/bigmem.md) |
| `branch` | 同時跑幾條思路，齊了只叫一次 join。 | [docs/branch.md](docs/branch.md) |
| `code` | 搜尋、留 checkpoint、看 diff、復原檔案。 | [docs/code.md](docs/code.md) |
| `communication` | 寄信、回信、廣播，並睡到等的信回來。 | [docs/communication.md](docs/communication.md) |
| `cost` | 記每次工具的時間、字數、token 與價錢。 | [docs/cost.md](docs/cost.md) |
| `fs` | 讀寫檔案、改一段文字、列目錄與跑短指令。 | [docs/fs.md](docs/fs.md) |
| `jobs` | 把長指令搬到另一顆鐘，睡到做完。 | [docs/jobs.md](docs/jobs.md) |
| `kids` | 生小孩、派活、看進度、暫停與收掉。 | [docs/kids.md](docs/kids.md) |
| `mailbox` | 讀自己的信箱，讀過就搬進 `read/`。 | [docs/mailbox.md](docs/mailbox.md) |
| `memory` | 整理本體內的短期筆記與舊對話。 | [docs/memory.md](docs/memory.md) |
| `pyshop` | 工作室資產、生 Python 小程式骨架與跑驗收。 | [docs/pyshop.md](docs/pyshop.md) |
| `ref` | 把太大的 JSON 結果收成可重開的指標。 | [docs/ref.md](docs/ref.md) |
| `review` | 回顧成本、失敗、思考與可重用教訓。 | [docs/review.md](docs/review.md) |
| `self` | 看自己的狀態、身分、時間與花費。 | [docs/self.md](docs/self.md) |
| `studio` | 一張單從接單、派工、驗收走到交付。 | [docs/studio-flow.md](docs/studio-flow.md) |
| `team` | 看整隊、分預算與追加共用進度。 | [docs/studio.md](docs/studio.md) |
| `think` | 把難題交給旁線深思，再拿短結論。 | [docs/think.md](docs/think.md) |
| `toolsmith` | 把常用指令做成自己的工具或包。 | [docs/toolsmith.md](docs/toolsmith.md) |

舊包名 `shell` 會自動改載 `fs` 並提醒；說明留在 [docs/shell.md](docs/shell.md)。

**加一包 = 加 `packs/<包>.py` + `tests/<包>.sh` + `docs/<包>.md`。README 只加表裡一行。** 共用接口與掛勾看 [docs/packs-api.md](docs/packs-api.md)。

`tools[]` 是另一條路：**一個工具就是一句 shell 指令**，`command` 不送 LLM，參數 JSON 從 stdin 進去。工具優先規則只寫在 [docs/packs-api.md](docs/packs-api.md)。

`tools.json` 還有兩個省 token 的開關：`"only": ["mail_send", …]` 只把列到的工具送給模型（包照樣載入、掛勾照樣跑；不寫＝全送）；`"inline_mail": ["*"]`（或列來源名）讓那些來源的信像 `user` 一樣整封直接進記憶、當場搬進 `read/`，不用再花兩三輪去讀。

### 子世界：生一個小孩

子 agent 長在 `<home>/kids/<名字>/`，**它自己就是一個完整的世界資料夾**（`.aos/inst` 是
`aos-agent exec .`，本體平鋪在自己底下）。人格是你給的；有模板就用模板工具包，沒模板才抄父的一份。`llm.json` 換算成
指向父用的那個 LLM 資料夾，兩邊共用同一個 LLM。分兩種鐘：**shared**（時間沒脫節）在父的
`.aos/inst` 尾端加一行 `aos-exec <home>/kids/<名字>`，父走一格它就走一格、父不動它也不動；
**own**（時間脫節）建好就自動 `aos-daemon register <子路徑> --no-wait` 要一個自己的時鐘，
沒設 `AOS_DAEMON_DIR` 就只建資料夾、印一句要自己開 `aos-loop <子路徑> --keep-inst`。

人要生就 `aos-user spawn <世界> <子名> <人格> [--clock shared|own] [--template 名字]`（預設 `shared`）；模型自己
生就叫 `kids` 包的 `spawn` 工具——**agent 可以自己生小孩**。子名只准英數字／底線／減號，
名字被佔走、或找不到 LLM 資料夾就回一句話不生。

spawn 也會寫小孩的 `parent.json`、父子雙方的 `contacts.json`、父的 `kids.json`。模板從
`proto2/templates/<名字>/` 找；目錄還不存在就直接略過。

## 給人用的殼：aos-user

`aos-user team new <世界> --preset studio` 一次開八人工作室，`team status` 看全隊（含在途筆數與被擋原因），`team budget [--add JSON]` 看預算／甲方追加，`team why [--member 名字]` 一人一行看誰卡在哪（等模型排第幾、凍住幾格、幾封沒讀、tokens 還剩多少）、`team tail <成員> [-n N]` 看那個人最近幾輪的「模型說／工具回」，`team stop` 收鐘留檔。工作室裡額度是硬閘門、每格都守：個人 tokens 用完（0 就是 0）自己凍住等主管 `team_grant`；整隊任一項用完全隊凍住、只有 sales 問甲方追加。細節見 [docs/studio.md](docs/studio.md)。
`aos-user order <世界> "任務" --budget '{"tokens":200000,"hours":1}' --accept "驗收條件"` 只把訂單交給 sales。

`aos-user say|listen|talk|status|spawn <世界> [--home DIR]`。**這支是暫時的殼**：使用者之後
會被當成一個 agent，這些動作會變成 agent 之間的交流，特殊地位到時再談。

- `say [世界] [文字]`——寫一封信丟進 `<home>/inbox/user/`（省略文字就整段讀 stdin），檔名是時間戳到微秒。
- `listen [世界] [--new] [--once]`——盯著 `outbox/`，每則印 `--- reply 0006 ---` 再印 content；
  預設先補印既有的再每 0.5 秒等新的，`--new` 只等新的，`--once` 印完一次就走；LLM 錯誤與
  等超過 60 格的提示會用 `agent!> ` 印，免得看起來像普通回答。
- `talk [世界]`——互動聊天：`你> ` 打一句（`/quit` 或 Ctrl-D 離開），`outbox/` 冒出新檔就印
  `agent> `。**自己不推格**，要另一個終端機的 `aos-loop`（或 daemon）幫忙轉。
- `status [世界]` 印它的自我統計（就是 `self_status` 那一包）；要看此刻走到哪、在等哪個 request，
  直接看 `<home>/state.json` 的 `state`／`request`。
  `spawn <世界> <子名> <人格> [--clock shared|own]` 生一個小孩。

## LLM 資料夾：aos-llm

LLM 不是誰的私有功能，是**跟 agent 平起平坐的另一個資料夾**，也靠 `aos-loop` 一格一格轉。
資料夾是**平鋪**的，`.aos/` 裡只有一句 `inst`（就是 `aos-llm exec .`），其他全在 `<dir>` 底下：
`engines.json`、`defaults.json`、請求箱 `requests/`、**正在打的** `requests/running/`、做完的
`requests/done/`、完成標記 `requests/running/<名字>.json.done`、回覆 `results/<跟請求同檔名>`、用量 `usage/<YYYY-MM-DD>.json`（外加 worker 丟的
小紙條 `usage/pending/`）、worker 的輸出 `logs/<名字>.log`、走到哪 `state.json`。誰想用 LLM 就往
`requests/` 丟一個檔，**過幾格**結果會出現在 `results/`。**有沒有 `engines.json` 就是「這是不是一
個 LLM 資料夾」。**

`engines.json` 是清單，第一個是預設；一台就是 endpoint、model、`params`、`max_concurrent`。`api_key_env` 有值才送 Authorization。範例裡 deepseek 可同時跑 10 發，本機 LM Studio 跑 1 發。

一台可以寫 `"api": "anthropic"`（不寫＝`openai`，行為完全不變）：**直接打 Anthropic 的 `/v1/messages`**，不用架 LiteLLM 那種轉接器；送出前後由 worker 兩頭翻譯，外面的人還是只看到 OpenAI 的 chat/completions 形狀。header 走 `x-api-key` ＋ `anthropic-version`，`max_tokens` 是必填（`params` 沒寫就 4096）。

```json
{"name": "haiku", "api": "anthropic", "base_url": "https://api.anthropic.com",
 "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY",
 "max_concurrent": 4, "params": {"max_tokens": 4096}}
```

還有一種 `"api": "claude-cli"`：**把 Claude Code 的 headless 模式當引擎**，開一個 `claude -p` 子進程、對話從 stdin 餵進去、要它照 json-schema 吐回一包 `{content, tool_calls}`——**有 Claude 訂閱、沒有 API key 的人就走這條**（`base_url`／`api_key_env` 用不到，`bin` 不寫就是 PATH 上的 `claude`）。用量算在訂閱的五小時窗口裡，每發多兩三秒的進程啟動時間。

```json
[{"name": "cheap", "api": "claude-cli", "model": "haiku", "max_concurrent": 2,
  "params": {"effort": "low"}},
 {"name": "thinking", "api": "claude-cli", "model": "sonnet", "max_concurrent": 2}]
```

同一招還有一種 `"api": "codex-cli"`：**把 OpenAI Codex CLI 的 headless（`codex exec`）當引擎**，給有 ChatGPT 訂閱的人用——工具不是用講的，是把 `aos-mcp-tools` 掛成一台只登記不執行的 MCP server 真的接上去，第一批工具呼叫進來就收工（細節與兩個坑見 [docs/llm-scheduling.md](docs/llm-scheduling.md)）。

`strip_think` 不寫就是 true：寫結果前切掉 content 裡最後一個 `</think>` 以前的內容；`reasoning_content` 原樣保留。

請求檔是 JSON 物件。aos 吃 `priority`、`requester`、`engine`、`params`；沒寫前兩項設定就用 `defaults.json`。其他頂層鍵原樣送 chat/completions，`model` 一律由引擎決定。

`priority` 也可寫成物件，放 `level`、`kind`、`deadline`、`requester`；排程規則見 [docs/llm-scheduling.md](docs/llm-scheduling.md)。usage 帳本分成 `by-model` 與 `by-requester` 兩層。

- `aos-llm exec [dir]`——**每一格做的事**，一格很短、**絕對不等網路**：①tick 加一 ②把
  `usage/pending/` 的紙條折進當天帳本 ③巡 `requests/running/`：完成標記（或舊 worker 的結果）出現了就把請求搬去 `done/`
  （`state.json` 的 `served`／`errors` 在這裡算），pid 死了、又沒完成標記和結果才補一個 `{"error": "worker
  died"}` 的結果一樣搬走、也補一張 `errors=1` 的紙條——**所以沒有人會卡在 running/ 一輩子** ④剩下
  的照（優先級、先來後到）排序由上而下派工，那台引擎還沒跑滿就開一個背景 worker、請求搬進
  `running/`，滿了的等下一格 ⑤印一行摘要 `tick 7 launched 2 running 3 queued 1` 到 stderr，外加每個
  `launch`／`done`／`died` 各一行。壞請求、不認得的引擎當格就回一個 error 結果、一樣搬去 `done/`。
  退出碼永遠 0，除非那個資料夾沒有 `engines.json`（退 1）。
- 真正打 HTTP 的是背景的 `aos-llm worker <dir> <請求檔名>`（人不用自己叫）：打完把整包原始回覆多
  掛一個 `aos`（`engine`／`base_url`／`model`／`priority`／`took_ms`／`usage`）**原子寫**進 `results/`，
  再丟一張用量紙條、最後留完成標記給下一格收尾；打不通（先探 TCP 10 秒，連不上就算）、HTTP 錯一樣是一個帶 `error` 的結果檔。
  `logs/<請求名>.log` 只收 worker 自己印的字，HTTP／連線失敗的原因以結果檔為準，所以 log 可能是空的。帳本是拿來算錢的，
  一個 `"<base_url>|<model>"` 一列累加：**模型回的 `usage` 裡每個數字都會累加**，思考 token、快取
  命中也在內（巢狀的攤成 `completion_tokens_details.reasoning_tokens` 這種點號鍵，外加自己數的
  `requests`／`errors`／`took_ms`）。
- `aos-llm usage [日期]` 印當天用量表；`aos-llm ls` 印**執行中**（engine／pid／跑多久）跟**排隊中**
  （下一格會被派的順序，預設補出來的值印成 `local*`），最後一台引擎一行 `engine local: running 1/1`。
  這兩個要知道資料夾在哪：`--dir`，沒給就看 **`AOS_LLM_DIR`**，都沒有印一句退 2。
- 要丟請求，`import aos_llm` 用 `write_request(<LLM 資料夾>, body, priority=, engine=)`／
  `read_result(<LLM 資料夾>, 檔名)` 最省事（原子寫、拿走就刪，`aos-agent` 就是用它），自己寫檔
  也完全可以——檔案就是介面。

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

- `start` 會等到 `kernel.json` 裡的 pid 真的活著、第一格也跑完才回「起來了」（最多等 5 秒），所以回來後可立刻 register。
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
- `register` 可重複給 `--env K=V`，也可用 `--env-from` 讀 600 權限的檔；時鐘預設不繼承
  kernel 環境，只有 `legacy_env: true` 才整包繼承。細節見 [docs/identity-and-env.md](docs/identity-and-env.md)。
- kernel 停掉後 `ls` 的 `stopped` 那列若還有 pid，那只是上一次的 pid 紀錄，不代表它還活著。
- 幾千個時鐘就是幾千個小 json 檔，現在夠用；管理介面、合併檔案是以後的事，不歸 kernel 管。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先做最小的那句話。另有一篇抒發原文：[2026-09-06 抒發：世界／時鐘／信箱](notes/2026-09-06-world-clock-agent.md)。

## 放進 PATH

`aos-exec`／`aos-loop` 會自動把自己所在的資料夾加進 PATH，`.aos/inst` 裡直接寫工具名就找得到；終端機直接打的 `aos-user`／`aos-llm` 要自己設一次：`export PATH="$PWD/proto2:$PATH"`。`llm.json` 的 `../llm` 相對於**世界資料夾**，agent 跟 llm 要當兄弟目錄一起搬。

## 怎麼玩

```sh
export PATH="$PWD/proto2:$PATH"
export AOS_DAEMON_DIR=~/.aosd
export AOS_LLM_DIR=$PWD/proto2/examples/llm    # aos-llm usage/ls 就不用打 --dir
lms load qwen/qwen3.5-9b                    # 用 LM Studio：先載模型
lms server start --port 1234                # 再開 OpenAI 相容 API server
export DEEPSEEK_API_KEY=你的金鑰             # 沒本機模型、要改用範例的 deepseek-flash 才設
aos-user new /tmp/my-agent --template coder --engine deepseek-flash  # 從模板開 agent
aos-daemon-kernel start                     # kernel 常駐起來
aos-daemon register proto2/examples/llm     # LLM 資料夾一個時鐘
aos-daemon register proto2/examples/agent   # agent 一個時鐘
aos-user talk proto2/examples/agent         # 聊天（另一個終端機 aos-daemon-kernel ls 看誰在跑）
aos-daemon pause proto2/examples/agent      # 凍住它（真的送 SIGSTOP），continue 再放它走
aos-daemon-kernel stop                      # 玩完，時鐘一起收掉
```

`aos-user new` 會列出 home、工具包、引擎與下一步。`aos-mcp` 把 agent、LLM、daemon 變成 MCP stdio 工具。記憶世界用 `aos-exec proto2/examples/memory` 推一格，沒有 `store.sqlite` 時會自己建立。

時鐘的輸出在 `$AOS_DAEMON_DIR/logs/`：agent 沒反應就去那裡看是不是一直「等 LLM」、或「沒有
.aos/inst」；shared 小孩由父的同一個時鐘推，所以父子 stderr 會混在同一份 clock log，而且行上不帶名字。
某一發打不通的原因看 LLM 的結果檔（worker 沒另印字時 `logs/<請求名>.log` 會是空的）。`sh` 工具的
工作目錄是世界根目錄；本體若是 `--home agent`，小孩在 `agent/kids/`，不是根目錄的 `kids/`。不想開
daemon 也行，一個終端機開一個 `aos-loop <資料夾> --keep-inst` 效果一樣。其他跑法：`aos-exec
examples/hello.sh`、`aos-loop examples/loop --stop-when-empty --interval 0`、`bash proto2/test.sh`。
範例的 `prompts.json` 有進 git（空陣列），**玩過就會被寫髒**——`git checkout -- proto2/examples`
就回得去；跑出來的 `state.json`／`inbox/`／`outbox/`／`kids/` 都被 `.gitignore` 擋掉了。

只想問一句話不開 agent：**請求就是自己寫的一個檔**，丟進去、`aos-llm ls` 看它排第幾，過幾格
`results/` 就冒出同名的回覆（拿走記得自己刪）——

```sh
echo '{"priority": 5, "messages": [{"role": "user", "content": "1+1=?"}]}' \
  > proto2/examples/llm/requests/ask.json
```

## 目前刻意不做

鎖、fsync、重試、串流、其他子命令、agent 之間互相講話、批次結構（.aos/inst 就是一段 shell，不是資料）。
並發只做到每台引擎的 `max_concurrent`；HTTP timeout 是 300 秒。退避仍不做。
