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
進去）、引擎 `engine.json`（`{base_url, model, api_key_env}`）、收新訊息的地方 `new-prompts/`
（收走搬進 `new-prompts/archived/`）、上次回覆 `llm-result.json`、走到哪 `state.json`。每次執行
只做一格：

| state | 做什麼 | 做完變成 |
|---|---|---|
| `idle` | 收 `new-prompts/` 頂層的檔，每個變一則訊息，寫進 `new-prompts.json` | 有信 `llm`，沒信留 `idle` |
| `llm` | `[人格]＋記憶＋new-prompts` 打 `{base_url}/chat/completions`，回覆併進記憶 | `act` |
| `act` | `tool_calls` 非空就照 `command` 跑工具、結果收進 `new-prompts`；沒有就印出它說的話 | 有工具 `collect`，沒有 `idle` |
| `collect` | 再收一次 `new-prompts/`，接在既有的 `new-prompts.json` 後面（沒新信也照走） | `llm` |

`new-prompts/` 裡每個檔要是 `{"role": "user", "content": "..."}` 這種 JSON 物件，原樣當一則
訊息用；讀不成 JSON 或不是物件的檔印一行到 stderr 跳過但一樣搬走。**`idle` 開新一輪前先清空
`archived/`**（`collect` 中途補收不清，這一輪收的留到輪完）。每格結束都把 `<aos-agent-step
絕對路徑> .` 寫回 `<dir>/.aos/inst`，讓 `aos-loop` 回來看有沒有新信；`--no-write-inst` 就不
寫。打不通 LLM：印一行 stderr、state 不動、退出碼 1，下一圈再試。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先做最小的那句話。

## 怎麼玩

```sh
proto2/aos-exec proto2/examples/hello.sh
proto2/aos-loop proto2/examples/loop --stop-when-empty --interval 0
bash proto2/test.sh
```

範例 agent（`engine.json` 預設指 LM Studio，`model` 改成你載的那顆）：
```sh
mkdir -p proto2/examples/agent/.aos
echo "$PWD/proto2/aos-agent-step . --no-write-inst" > proto2/examples/agent/.aos/inst
proto2/aos-loop proto2/examples/agent --keep-inst --interval 1
```

寫一次 `.aos/inst`、`--keep-inst` 不清空，agent 就一直轉；往 `new-prompts/` 丟 `{"role":"user","content":"..."}` 這種檔，下一圈就撿走。

## 目前刻意不做

鎖、崩潰恢復、fsync、並發、逾時、重試、daemon、其他子命令、串流、批次結構（.aos/inst 就是一段 shell，不是資料）。撞到再說。
