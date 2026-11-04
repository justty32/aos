# proto4-7 — 簡單的 agent

這是一支一次只走一格的 agent。`aos-agent` 收信、把問題交給 kernel 的 LLM 排程、跑工具、回信；模型還沒回或目前沒信時就退出 101，把 CPU 讓出去。它不自己連 HTTP、不排程，也不在一格裡睡著等網路。`aos-user` 是人用來建 agent、寫信、收信和看狀態的介面。

## 資料夾長什麼樣

```text
A/agent.json              名字、system、K、每題格數與工具輸出上限
A/messages.json           OpenAI messages 記憶；system 每次另外補
A/tools/<名字>/tool.json  工具說明與 JSON schema
A/tools/<名字>/run        可執行檔；stdin 收參數 JSON，stdout 回結果
A/inbox/user/*.json       使用者來信
A/inbox/user/read/        已讀來信
A/outbox/0001.json        agent 回話，獨立遞增
A/state.json              四格狀態與錯誤、等待計數
A/inst.json               放進 kernel 的指令
```

`state.json` 會記 `state`、`epoch`、`question`、`step`、`request`、`checks`、`errors`、`idle_since_error`、`stuck`、`last_error`、`outbox_n`。所有會改寫的 JSON 都先寫 `.tmp`，再用 rename 發佈。

## 四格

| 格子 | 這格只做什麼 | 下一格 |
|---|---|---|
| `idle` | 一次只收 `inbox/user/` 最舊的一個檔並搬到 `read/`；檔內若是陣列，整個陣列算同一題。沒信就等 | `ask` 或留在 `idle` |
| `ask` | step 加一，組 system＋記憶＋工具表，送 `aos-kernel llm`；到上限會回「stuck，回一句就從頭算」 | `wait` 或 `idle` |
| `wait` | 看結果檔；未到就退 101，第 600 次算錯；連錯五次會回「stuck，回一句再試」 | `act`、`idle` 或留在 `wait` |
| `act` | 接 assistant 訊息；有 tool calls 就逐一跑工具，沒有就寫 outbox | `ask` 或 `idle` |

每次呼叫 `aos-agent A` 就只走上面一格。`aos-agent A --status` 把 `state.json` 印成一行；
`--reset` 會寫回乾淨狀態並把 `epoch` 加一，不動記憶與 outbox。LLM 請求名是
`<name>-e<epoch>-q<question>-s<step>`；底層的同名同內容冪等只限同一個 epoch，reset 後不會撞舊單。

## aos-user 用法

先建一個 agent：

```sh
proto4-7/aos-user /tmp/bob new \
  --name bob --system "你是個簡潔、會用工具的助手" --K /abs/K
```

它會建空記憶、信箱、outbox、`echo`／`sh` 兩個工具與 `inst.json`，並印出下一步。平常用法：

```sh
aos-user /tmp/bob say "看看資料夾裡有什麼"  # 省略文字就從 stdin 讀
aos-user /tmp/bob listen --once              # 只印上次 listen 後的新回話；沒有就明說後退出
aos-user /tmp/bob listen --new --once        # 等啟動後的下一則，再印出並退出
aos-user /tmp/bob listen --new               # 只聽啟動後的新回話，一直不退出
aos-user /tmp/bob talk                       # 你> / bob> 互動介面
aos-user /tmp/bob status                     # 一行看格子、題目、等待、錯誤、未讀信
```

`listen` 本身不推進 agent；kernel 必須在跑。已看進度存在 agent 根目錄的 `.listen-seen`，
不塞進 agent 的 `state.json`。

## 放進 kernel

`new` 產生的 `inst.json` 已用絕對路徑指向本版 `aos-agent`，cwd 也是 agent 的絕對路徑：

```sh
aos-kernel add /abs/K /tmp/bob/inst.json --name bob
aos-kernel ls /abs/K
aos-kernel llm ls /abs/K
```

請用 `bad_after=0` 的 kernel，讓模型錯誤由 agent 自己記帳；檔案壞掉仍會退 1，方便看出真正的程式錯誤。

## 寫一個工具

工具名就是資料夾名。譬如 `tools/sh/tool.json`：

```json
{
 "description": "在 agent 資料夾執行一句 shell 指令",
 "parameters": {
  "type": "object",
  "properties": {"cmd": {"type": "string"}},
  "required": ["cmd"]
 }
}
```

同資料夾的 `run` 要可執行，從 stdin 讀參數 JSON，把結果寫 stdout。任何語言都可以；非 0 結束時 stderr 前 500 字也會回給模型。先不用 agent 就能單獨試：

```sh
cd /tmp/bob
echo '{"cmd":"ls"}' | tools/sh/run
```

工具輸出超過 `tool_output_limit` 會截斷。模型把 tool call 寫成 `<tool_call>`、`[TOOL_CALLS]`、`<function=` 或整段 JSON 時，程式會嘗試救回；工具名對不上就當一次模型錯誤。

## 退出碼

| 碼 | 意思 |
|---:|---|
| 0 | 這格做了事，或模型錯誤已由 agent 記帳 |
| 101 | 正在等結果，或閒著等信 |
| 100 | `agent.json` 的 `stop` 是 true，收工 |
| 1 | agent／state／messages／工具設定或 K 壞了 |
| 2 | 命令列用法錯 |

## 沒做什麼

沒有 `--home`、Python 工具包與掛勾、kids、contacts、side packs、MCP、預算、模板或 team；沒有鎖，同一個 agent 不要同時跑兩份。信件一律整封進記憶，不做「只通知有信」；結果檔保留在 K，不代替 LLM 排程清帳。

## 測試與出處

測試用假的 kernel、假的結果檔與本機 shell 工具，不打真 LLM：

```sh
cd proto4-7
python3 -m unittest discover -s test
```

定案在 [`proto4/notes/24-agent.md`](../proto4/notes/24-agent.md) §24.3；舊版採捨見 [`proto4/notes/agent/legacy-harvest.md`](../proto4/notes/agent/legacy-harvest.md)。地基契約見 [`proto4-3`](../proto4-3/README.md)、[`proto4-5`](../proto4-5/README.md) 與 [`proto4-6`](../proto4-6/README.md)。
