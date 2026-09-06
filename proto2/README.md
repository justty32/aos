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

`--steps N` 跑幾步就停（不給＝無限）、`--interval SEC` 每步睡幾秒（預設 1）、
`--stop-when-empty` 讀到空的就以 0 退出（不給的話空的那步不跑、照樣算一步繼續）、
`--keep-inst` 不清空 `.aos/inst`、每圈原樣重跑同一段（寫一次、跑到飽）。命令退出碼不影響
迴圈，但每步印一行到 stderr，例如 `aos-loop: step 2 exit 5`。

## aos-agent：一個 agent 走一格

**指令分兩種**：`aos-agent` 是 **agent 自己跑的時候需要的**（狀態機、工具包）；
`aos-user` 是 **給人方便用的殼**（說話、聽、看狀態、生小孩）。使用者以後也會是一個
agent，那些動作到時候會變成 agent 之間的交流，特殊地位到時再談。

**一個 agent 就是一個世界資料夾。** 世界資料夾的 `.aos/` 裡**只有一句 `inst`**，agent
自己的東西全放在**本體資料夾**（home）底下——home 放哪自己設，`--home` 相對於世界資料夾，
不給就是 `.`（東西直接攤在世界資料夾底下）：

```
xxx/.aos/inst              aos-agent exec . --home agent
xxx/<home>/system-prompt.json   人格 {"role":"system","content":"..."}
xxx/<home>/prompts.json         記憶（OpenAI messages 陣列）
xxx/<home>/tools.json           {"packs": [...], "tools": [...]}
xxx/<home>/llm.json             {"dir": "../llm", "priority": 1, "engine": "..."}（可有可無）
xxx/<home>/state.json           走到哪
xxx/<home>/inbox/<來源>/*.json       沒讀的信
xxx/<home>/inbox/<來源>/read/*.json  讀過的信
xxx/<home>/outbox/<四位數>.json      它自己說的話
xxx/<home>/llm-result.json      上次 LLM 的整包原始結果
xxx/<home>/kids/<名字>/         它生的小孩（每個都是完整的世界資料夾）
```

`llm.json` 的 `dir` 相對於**世界資料夾**（不是 home），所以 `../llm` 一直都是隔壁那個 LLM
資料夾；沒寫就看 `AOS_LLM_DIR`，再沒有就找 `../llm`。範例有兩個：`examples/agent`（home 設成
`agent`）跟 `examples/agent-flat`（home 用預設的 `.`）。**`aos-user` 的子命令不用每次打
`--home`**——沒給就去世界的 `.aos/inst` 把 `--home X` 撈出來用，撈不到就當 `.`。

`aos-agent exec <世界> [--home DIR]` 一次走一格，五格輪流走：

| state | 做什麼 | 做完變成 |
|---|---|---|
| `idle` | 掃一遍 `inbox/*/`（不含 `read/`），有沒讀過的信就接進記憶 | 有信 `llm`，沒信留 `idle` |
| `llm` | 人格＋工具包預設 prompt＋記憶（＋工具清單）寫成請求丟進 LLM 資料夾的 `requests/` | `wait` |
| `wait` | LLM 資料夾的 `results/<請求名>` 出現了就撿回來，assistant 接進記憶 | 撿到 `act`，沒撿到留 `wait`（**結果是幾格後才回來的**），是 `error` 就回 `idle` |
| `act` | 有 `tool_calls` 就跑工具、結果接進記憶；沒有就把話印出來、落一份到 `outbox/` | 有工具 `collect`，沒有 `idle` |
| `collect` | 再掃一次信箱（沒新信也照走） | `llm` |

`step` 是被推了幾格（空轉也算），`busy` 是這裡面真做事幾格；`last_usage` 是上次撿回覆時
LLM 附的那包用量。**這支不寫 `.aos/inst`**——`.aos/inst` 是人（或 spawn）寫一次就固定的
一段，`aos-loop --keep-inst`／daemon 每格原樣重跑；agent 自己去覆蓋它會把 spawn 掛上去的
那行洗掉。

### 信箱：一個來源一個資料夾

一封信就是一個 JSON 檔：`{"from": "bob", "time": "...", "content": "..."}`（多帶別的鍵也行），
一個檔要放一串信也可以（JSON 陣列）。**來源就是 `inbox/` 底下的資料夾名**——`user`、`team`、
`kernel`、別的 agent 的名字都行，第一次收到信才建。

- `idle` 掃到未讀就去問 LLM，但**不會把信整包塞進 prompt**，只加一句「你有新信：team 1 封。
  用信箱工具去讀。」，剩下讓模型自己用信箱工具去讀。
- **同一封信只通知一次**（通知過的記在 `state.json` 的 `announced`）。模型看到摘要卻懶得讀，
  也不會被一直重新叫醒——不然 `idle` 會一輪一輪叫 LLM，錢燒不完。信被讀掉就自動掉出清單。
- **唯一的例外是來源 `user`**：內容直接當成一則 user 訊息接進記憶（前面加 `[user] `），檔案
  當場搬進 `read/`。這樣跟 agent 講話才是一個來回。
- 讀過的信搬進該來源的 `read/`，不會再算未讀。

### 工具包：一包一檔

`tools.json` 長這樣：

```json
{"packs": ["mailbox", "shell", "self", "kids"],
 "tools": [{"name": "say", "description": "...", "parameters": {...}, "command": "..."}]}
```

`packs` 列到誰就載誰。**一個工具包就是一個 `.py` 檔**，放在 `packs/<名字>.py`——先找 agent
自己的 `<home>/packs/`，再找 aos 內建的 `proto2/packs/`。一包自帶三樣東西：`TOOLS`（工具定義）、
`PROMPT`（一段預設 prompt，會併進 system 訊息）、`run(name, args, ctx)`（怎麼跑）。**要加新
工具包就加一個檔、在 `tools.json` 列進去**，不用動 `aos-agent`。認不得的包名印一句到 stderr
就跳過，agent 照樣跑。內建四包：

| 包 | 工具 | 幹嘛的 |
|---|---|---|
| `mailbox` | `inbox_sources`／`inbox_list`／`inbox_read`／`inbox_read_all` | 讀自己的信 |
| `shell` | `sh(command)` | 在世界資料夾裡跑一句 shell（60 秒、輸出截斷） |
| `self` | `self_status()` | 走了幾格、開機多久、記憶多大、資料夾多大、今天用掉多少 token |
| `kids` | `spawn(name, persona, clock)`／`kids_list()` | 生小孩、看小孩 |

`tools[]` 是另一條路：**一個工具就是一句 shell 指令**，`command` 不送 LLM，跑的時候丟 shell、
參數 JSON 從 stdin 進去。同名時工具包贏。

### 子世界：生一個小孩

子 agent 長在 `<home>/kids/<名字>/`，**它自己就是一個完整的世界資料夾**（`.aos/inst` 是
`aos-agent exec .`，本體平鋪在自己底下）。人格是你給的，工具包抄父的一份，`llm.json` 換算成
指向父用的那個 LLM 資料夾，兩邊共用同一個 LLM。分兩種鐘：**shared**（時間沒脫節）在父的
`.aos/inst` 尾端加一行 `aos-exec <home>/kids/<名字>`，父走一格它就走一格、父不動它也不動；
**own**（時間脫節）建好就自動 `aos-daemon register <子路徑> --no-wait` 要一個自己的時鐘，
沒設 `AOS_DAEMON_DIR` 就只建資料夾、印一句要自己開 `aos-loop <子路徑> --keep-inst`。

人要生就 `aos-user spawn <世界> <子名> <人格> [--clock shared|own]`（預設 `shared`）；模型自己
生就叫 `kids` 包的 `spawn` 工具——**agent 可以自己生小孩**。子名只准英數字／底線／減號，
名字被佔走、或找不到 LLM 資料夾就回一句話不生。

## 給人用的殼：aos-user

`aos-user say|listen|talk|status|spawn <世界> [--home DIR]`。**這支是暫時的殼**：使用者之後
會被當成一個 agent，這些動作會變成 agent 之間的交流，特殊地位到時再談。

- `say [世界] [文字]`——寫一封信丟進 `<home>/inbox/user/`（省略文字就整段讀 stdin），檔名是時間戳到微秒。
- `listen [世界] [--new] [--once]`——盯著 `outbox/`，每則印 `--- reply 0006 ---` 再印 content；
  預設先補印既有的再每 0.5 秒等新的，`--new` 只等新的，`--once` 印完一次就走。
- `talk [世界]`——互動聊天：`你> ` 打一句（`/quit` 或 Ctrl-D 離開），`outbox/` 冒出新檔就印
  `agent> `。**自己不推格**，要另一個終端機的 `aos-loop`（或 daemon）幫忙轉。
- `status [世界]` 印它的自我狀態（就是 `self_status` 那一包）；
  `spawn <世界> <子名> <人格> [--clock shared|own]` 生一個小孩。

## LLM 資料夾：aos-llm

LLM 不是誰的私有功能，是**跟 agent 平起平坐的另一個資料夾**，也靠 `aos-loop` 一格一格轉。
資料夾是**平鋪**的，`.aos/` 裡只有一句 `inst`（就是 `aos-llm exec .`），其他全在 `<dir>` 底下：
`engines.json`、`defaults.json`、請求箱 `requests/`、**正在打的** `requests/running/`、做完的
`requests/done/`、回覆 `results/<跟請求同檔名>`、用量 `usage/<YYYY-MM-DD>.json`（外加 worker 丟的
小紙條 `usage/pending/`）、worker 的輸出 `logs/<名字>.log`、走到哪 `state.json`。誰想用 LLM 就往
`requests/` 丟一個檔，**過幾格**結果會出現在 `results/`。**有沒有 `engines.json` 就是「這是不是一
個 LLM 資料夾」。**

`engines.json` 是一個**清單**，第一個是預設，一個引擎就是一個 endpoint＋model 配幾個參數：
`{"name": "local", "base_url": ".../v1", "model": "local", "max_concurrent": 1, "params":
{"temperature": 0.7}}`。`api_key_env` 是環境變數的**名字**，那個變數有值才送 `Authorization:
Bearer`；`params` 原樣帶進 body、不檢查。**`max_concurrent`（不寫＝1）是那台一次最多同時跑幾個
請求**——範例裡 deepseek 開 2、本機 LM Studio 開 1，四個請求進來就三個開跑、一個排著。
**`strip_think`（不寫＝true）**：qwen 那種漏進 `content` 的 `<think>…</think>` 在寫結果檔之前就
切掉（只留最後一個 `</think>` 之後的東西），這是 LLM 這一側的家務、撿結果的人不用自己處理；
`reasoning_content` 這種供應商私有欄位原樣不動。

請求檔是一個 JSON 物件，aos 只吃三個鍵：`priority`（整數，**大的先做**）、`engine`（引擎名字）、
`params`（蓋在引擎 `params` 上）；**沒寫 `priority`／`engine` 就用 `defaults.json`**（`{"engine":
"local", "priority": 0}`，沒這個檔就是 `engines.json` 第一台＋0；認不得的引擎名字還是錯）。
**其他頂層鍵全部原樣當成 chat/completions 的 body 欄位**，所以 agent 丟的請求不用改：body ＝
引擎 `params` ← 請求 `params` ← 請求其他頂層鍵，**`model` 一律引擎說了算**。

- `aos-llm exec [dir]`——**每一格做的事**，一格很短、**絕對不等網路**：①tick 加一 ②把
  `usage/pending/` 的紙條折進當天帳本 ③巡 `requests/running/`：結果出現了就把請求搬去 `done/`
  （`state.json` 的 `served`／`errors` 在這裡算），pid 死了又沒結果就補一個 `{"error": "worker
  died"}` 的結果一樣搬走、也補一張 `errors=1` 的紙條——**所以沒有人會卡在 running/ 一輩子** ④剩下
  的照（優先級、先來後到）排序由上而下派工，那台引擎還沒跑滿就開一個背景 worker、請求搬進
  `running/`，滿了的等下一格 ⑤印一行摘要 `tick 7 launched 2 running 3 queued 1` 到 stderr，外加每個
  `launch`／`done`／`died` 各一行。壞請求、不認得的引擎當格就回一個 error 結果、一樣搬去 `done/`。
  退出碼永遠 0，除非那個資料夾沒有 `engines.json`（退 1）。
- 真正打 HTTP 的是背景的 `aos-llm worker <dir> <請求檔名>`（人不用自己叫）：打完把整包原始回覆多
  掛一個 `aos`（`engine`／`base_url`／`model`／`priority`／`took_ms`／`usage`）**原子寫**進 `results/`，
  再丟一張用量紙條給下一格折帳；打不通、HTTP 錯一樣是一個帶 `error` 的結果檔。帳本是拿來算錢的，
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

`aos-exec`／`aos-loop` 會自動把自己所在的資料夾加進 PATH，`.aos/inst` 裡直接寫工具名就找得到；終端機直接打的 `aos-user`／`aos-llm` 要自己設一次：`export PATH="$PWD/proto2:$PATH"`。`llm.json` 的 `../llm` 相對於**世界資料夾**，agent 跟 llm 要當兄弟目錄一起搬。

## 怎麼玩

```sh
export PATH="$PWD/proto2:$PATH"
export AOS_DAEMON_DIR=~/.aosd
export AOS_LLM_DIR=$PWD/proto2/examples/llm    # aos-llm usage/ls 就不用打 --dir
aos-daemon-kernel start                     # kernel 常駐起來（LM Studio 要先載一顆模型）
aos-daemon register proto2/examples/llm     # LLM 資料夾一個時鐘
aos-daemon register proto2/examples/agent   # agent 一個時鐘
aos-user talk proto2/examples/agent         # 聊天（另一個終端機 aos-daemon-kernel ls 看誰在跑）
aos-daemon pause proto2/examples/agent      # 凍住它（真的送 SIGSTOP），continue 再放它走
aos-daemon-kernel stop                      # 玩完，時鐘一起收掉
```

時鐘的輸出在 `$AOS_DAEMON_DIR/logs/`：agent 沒反應就去那裡看是不是一直「等 LLM」、或「沒有
.aos/inst」；某一發打不通的細節在 LLM 資料夾自己的 `logs/<請求名>.log` 跟那份結果檔裡。不想開
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
並發只做到「一台引擎一次幾個」（`max_concurrent`），逾時只有 worker 那發 300 秒的 HTTP timeout；
更細的（退避、配額、跨資料夾排程）撞到再說。
