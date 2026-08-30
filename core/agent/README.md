# agent：回合制資料夾 agent

`aos agent` 把 agent 的對話、狀態與工具往返保存在 `<folder>/.aos/agents/<name>/`，
而 `.aos/every/agent-<name>.json` 讓 loop 每回合複製一條 `step`。一個資料夾只住
一隻 agent，cwd 就是世界；`aos agent init` 省略 folder 時直接在 cwd 建世界，其他
子命令才會從 cwd 往上找最近的 `.aos/`。agent 直接連結
`aos::llm`，不會啟動另一個 `aos llm` 子行程。

## 快速使用

```sh
mkdir bob && cd bob
aos agent init --priority 7
# 另一個視窗也在 bob/ 裡啟動世界：
aos run --step 0
# 回到第一個視窗：
aos say "你叫什麼名字"
aos listen

# 從通訊錄把訊息送到另一個世界：
aos contact add alice ../alice-world
aos say --to alice "可以幫我看一下嗎"
```

頂層的 `aos say`、`aos listen`、`aos talk`、`aos state`、`aos inbox` 都自動解析
世界與唯一的 agent。`aos say --to <名字> <文字...>` 會查目前世界的
`.aos/contacts.json`，把訊息投到聯絡人的世界與 agent。`talk` 會逐行讀 stdin，等待外部
loop 推進後印出該次新增的 log；`listen` 在 log 還是空的時會指向未讀信箱或下一步，
不帶 `--once` 時每 200 ms 印出新增內容。舊的
`aos agent say|listen|talk|state <folder> <name>` 形式仍可使用。
`aos agent talk --interface pi` 的整合限制與建議
adapter 見 [docs/pi-interface.md](docs/pi-interface.md)；目前 CLI 會清楚回報它尚未內建。
`aos agent init` 另接受 `--engine lmstudio|pi`、`--provider P`、`--model M` 與
`--priority N`；priority 是可為負數的整數，0 不寫進 `engine.json`。lmstudio 可用
`--provider P` 指定取槽用的 CPU 名；兩種 engine 都會把 `--model M` 寫進
`engine.json`，lmstudio step 會用它覆蓋 `AOS_LLM_MODEL`。初始化寫進
`.aos/every/agent-<name>.json` 的 `argv[0]` 會盡量解析成這一支 `aos` 的絕對路徑
（依序看 `AOS_BIN`、`/proc/self/exe`、PATH，最後才退回 `aos`）。

`aos state`／`aos agent state` 除了既有狀態，也輸出 `unread`、`engine` 與 `model`；
有未讀且目前不是 `error` 時，顯示狀態會是 `pending`。在 agent 世界中，`aos listen` 印完 log 後會再列
`## 未讀 (N)`，只顯示、不刪除。`aos talk` 讀 stdin 前先以 `.aos/run.lock` 確認 runner
存在，沒有就立即指示如何啟動並回 1。跨世界 `aos say --to` 成功時印真正的收件匣路徑，
失敗時則以解析後的絕對路徑分辨資料夾不存在、不是 aos 世界或尚無 agent。
`say`／`listen`／`state`／`talk`／`aos agent` 的 `-h`／`--help` 都印到 stdout 並回 0；
頂層 say 只把第一個位置的 help 當選項，其餘位置仍是訊息內容。

`aos state` 預設印出 agent、目前狀態、現場計數的 `say/` 未讀封數，以及上一回合
成功或失敗；`aos state --json` 才印 `status.json` 原文。`status.json` 每次寫入都包含
`unread` 快照，最近一次 step 失敗時另含單行 `last_error`，成功回合會清掉該欄位。
若 lmstudio completion 失敗，這回合的新 user 訊息仍留在 `say/`，不會先寫進 history
或 log；端點恢復後可在下一回合安全重試。

`aos inbox ls [--json]` 直接列出 `say/*.md`，不會呼叫 LLM；
`aos inbox read [<id>] [--all] [--keep]` 省略 id 時讀最舊一封，也接受唯一的 id 前綴。
預設讀完會把訊息搬到同層的 `read/`，因此 agent 不會再處理它；只想查看、仍要留給
agent 回覆時加 `--keep`。

## 使用者也是一格 agent

通訊錄天然有一格 `~` 代表使用者，地址是 `$HOME` 的絕對路徑。使用者不是真的 agent，
只使用扁平的 `~/.aos/say/` 信箱與 `~/.aos/log.md`，沒有 persona、history、status、
engine 等 agent 版面。其他世界可以直接寄信，使用者則在 `~` 底下收信：

```sh
aos say --to ~ "回報完成"
cd ~
aos listen
```

CLI 寄出的每則 say 訊息都包含寄件世界的絕對路徑；不在任何世界時寄件人就是 `~`
所代表的使用者世界：

```text
from: /home/alice/work/report-world

回報完成
```

這個 `from` 標頭是訊息正文的一部分。一般 agent 的 `step` 不另外解析它，訊息會連同
標頭一起進入 agent 的 history，讓 agent 直接看見寄件者。

## 工具往返

世界層工具登記表是一項一檔的 `.aos/tools/<name>.json`；agent 自己的
`agents/<name>/tools.json` 若存在，只是工具名稱白名單。白名單不存在表示世界裡的工具
全部可用，`[]` 表示全部停用。送給模型時，每個工具固定表述成一行：

```text
- <name> — <description> (args: <list|string|none>, stdin: <none|text>)
```

模型只能在回覆末段的一個獨立 JSON 行要求一個已登記工具。`args: list` 使用字串陣列，
逐項接到登記的 argv；`args: string` 使用單一字串，代入 argv 裡所有 `{args}`（沒有占位符
時當一個 argv 接在後面）；`args: none` 省略 `args`。例如：

```json
{"tool":"ls","args":["-la","."]}
```

工具在第 N 回合投遞，第 N+1 回合執行，第 N+2 回合才從
`batch/<N+1>/out/` 收結果。執行結果與未知工具／參數形狀錯誤都會以一行固定形狀 JSON
寫成 `tool` 訊息，包含 `call_id`、`tool`、原始 `args`、`ok`、`result`，失敗時另有
`error.type`／`message`／`retryable`；模型會在下一次適合的回合接著處理。沒有新 user 訊息
或新工具結果時，`step` 不呼叫 LLM，
但 `.aos/every/` 仍讓它在下一回合被執行，不會浪費 LLM token。

```json
{"call_id":"agent-bob-tool-11-0","tool":"ls","args":["-la"],"ok":true,"result":{"exit":0,"signal":null,"stdout":"alpha\n","stderr":""}}
{"call_id":"agent-bob-tool-7-0","tool":"nope","args":[],"ok":false,"result":null,"error":{"type":"unknown_tool","message":"沒有登記工具 nope","retryable":false}}
```

## 函式庫

公開 API 在 `<aos/agent.hpp>`。`aos::agent::step` 接受可選的 completion callback；
未提供時呼叫 `aos::llm::complete()`，測試則可注入固定回覆，全程離線。

## 訊息可靠性與 log 稽核

lmstudio 與 pi 都會先成功取得 LLM 回覆，之後才把這回合讀到的 `say/*.md` 寫入 history
並刪除；LLM 或 pi 失敗時訊息會留在原處供下一回合重試。失敗會把 `status.json` 寫成
`error`，並在 log 留下 `> 第 N 回合失敗：…` 或 pi 的 exit；連線失敗會附端點位址指引，
pi 的 `No API key` 會指出對應的 `<PROVIDER>_API_KEY`。pi 失敗回 1，只有等不到槽回 75。

`agents/<name>/log.jsonl` 是 log 的正典稽核紀錄，每行一則
`{"turn":N,"role":"user|assistant|tool|note","content":"…"}`。每次追加會先原子更新
journal，再由它重畫整份 `log.md`；`read_log()` 發現兩者不符時會在 stderr 警告並還原
`log.md`。沒有 `log.jsonl` 的舊世界則維持直接讀 `log.md` 的相容行為。

## 用 pi 當 LLM CPU

除了預設的 LM Studio 引擎，也可以讓一次 `aos agent step` 在世界資料夾裡執行一次
本機 pi coding agent：

```sh
mkdir bob && cd bob
aos agent init --engine pi
aos say "在這個資料夾建一個 hello.txt 內容是 hi"
aos run --step 1
aos listen --once
```

`--engine pi` 預設選 `deepseek`／`deepseek-v4-flash`；需要時可在 init 加上
`--provider P --model M --priority N`。初始化後的
`.aos/agents/<name>/engine.json` 會是：

```json
{"engine":"pi","provider":"deepseek","model":"deepseek-v4-flash",
 "session_id":"<自動產生的 v4 UUID>","priority":7}
```

執行 loop（也就是實際跑 `aos agent step`）的行程必須有 `DEEPSEEK_API_KEY`；pi 會
自行從環境變數讀取，不需要把 key 寫進檔案。不傳 `--engine` 時仍使用 lmstudio，舊世界
沒有 `engine.json` 也視同 lmstudio。

pi 引擎不走世界工具登記表／agent 白名單、`aos llm` 或 pending 的三回合工具往返；pi 自帶的
read／bash／edit／write 工具會在一次 step 內直接操作世界資料夾。對話記憶由 pi session
保存，`history.json` 只是 aos 端的鏡射。實測、argv、隔離方式與這條路的取捨見
[docs/pi-cpu.md](docs/pi-cpu.md)。

lmstudio 與 pi 的一次 step 都算一個 LLM 呼叫，呼叫前都會取槽。lmstudio 的 CPU 名
優先使用 `engine.json` 的 `provider`，沒有就讀 `AOS_LLM_ENGINE`，再沒有就是
`lmstudio`；pi 使用 `provider`，預設 `deepseek`。上限設在
`<AOS_HOME>/cpus.json`，格式見 [`core/llm/README.md`](../llm/README.md)。

兩條 engine 的優先度都先讀 `engine.json` 的非 0 `priority`；可用
`aos agent init --priority N` 寫入。沒有或為 0 時改讀 `AOS_LLM_PRIORITY`，再沒有就是
0。取不到槽時，step 會在吃掉 `say/` 訊息之前把 status 寫成 `waiting-llm`；直接執行
`aos agent step` 時 stderr 只印一行 `waiting-llm` 並以 75 結束。這不算失敗，下回合
`every` 再投一次就會自然重試。沒設 `cpus.json` 時回傳空槽、不佔也不等，行為與以前
一樣。

端到端 smoke：`bash core/agent/tests/smoke_user.sh`（離線、`HOME`／`AOS_HOME` 指暫存目錄）。
