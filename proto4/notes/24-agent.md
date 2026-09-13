# proto4 筆記 §24：簡單的 agent，跟 proto2 那樣（2026-09-13 晚，使用者手機）

← [索引](2026-09-08-ideas.md)｜LLM 兩層見 [§22](22-llm-cpu.md)｜逐步執行器見 [§23](23-step-json-python.md)

## 24.1 使用者原話（照錄）

> 可以順便在此基礎上去幫我弄一個簡單的 agent 嗎？就跟 proto2 那樣

「此基礎」＝今天的地基：kernel（proto4-3）、LLM 排程當 kernel module（proto4-5）、逐格執行＋等檔退 101（proto4-6）。

## 24.2 proto2 的 agent 長什麼樣（README 摘要）

一個 agent 就是一個資料夾：`system-prompt.json`（人格）、`prompts.json`（記憶，OpenAI messages 陣列）、`tools.json`（`packs` 列 Python 工具包＋`tools[]` 一句 shell 當工具）、`state.json`、`inbox/<來源>/*.json`（讀過搬 `read/`）、`outbox/0001.json`（它說的話）。`aos-agent exec 世界` 一次走一格，七格：idle（掃信）→ llm（寫請求）→ wait（等結果）→ act（跑工具或說話）→ collect（再掃信）→ llm…，出錯進 retry（每 20 格重送、連錯 5 次 stuck 只等新信）。`aos-user say|listen|talk|status|spawn`。後來長出 18 個工具包、工作室、小孩、預算。撈遺產的逐條決定在 [agent/legacy-harvest.md](agent/legacy-harvest.md)（Opus 撈，任務書 `agent/harvest-task.md`）。

## 24.3 v1 定案（Fable 提、使用者沒反對就照做）

**一句話**：agent 是一支「一叫走一格」的程式，放進 kernel 就活著；等模型的時候退 101 讓 cpu；叫模型走 kernel 的 LLM 排程；工具用 aos-exec 跑。

**資料夾**（`proto4-7/`，指令 `aos-agent`、`aos-user`）：

```
A/                       一個 agent 一個資料夾（世界＝本體，不分 --home）
A/agent.json             {"name":"…","system":"人格一段話","K":"/abs/K","llm_name_prefix":"…"（可省，預設用資料夾名）}
A/messages.json          記憶：OpenAI messages 陣列（system 不放這裡，每次叫模型時從 agent.json 補上）
A/tools/<名字>/tool.json  工具宣告：{"description":"…","parameters":{JSON schema}}
A/tools/<名字>/inst.json  或普通可執行檔 run：aos-exec 跑它，參數 JSON 從 stdin 進、stdout 當結果
A/inbox/<來源>/*.json    一封信一個檔 {"from","time","content"}；讀過搬 inbox/<來源>/read/
A/outbox/0001.json       它說的話 {"time","content"}，四位數遞增
A/state.json             {"state":"idle|llm|wait|act|stuck","request":"K/llm/results/<id>.json"|null,"turn":N,"errors":N,"asked_at":…}
A/inst.json              放進 kernel 用：{"argv":["/abs/proto4-7/aos-agent","."],"cwd":"/abs/A","stderr":"err.txt"}
```

**一格做什麼**（`aos-agent A`，退出碼：0 做了事、101 在等模型、1 這格失敗、2 用法錯）：

| state | 做什麼 | 變成 |
|---|---|---|
| idle | 掃 `inbox/*/`（不含 `read/`），有信就以 `{"role":"user","content":"[from bob] …"}` 接進 messages、搬進 `read/`；沒信什麼都不做、退 0 | 有信→llm；沒信留 idle |
| llm | 把 system＋messages＋工具清單（OpenAI `tools` 格式，從 `tools/*/tool.json` 生）寫成請求，`aos-kernel llm K req.json --name <prefix>-<turn>`（不等）；記 `request` 路徑 | wait |
| wait | 結果檔還沒出現→退 **101**（跟逐步執行器一樣，kernel 會標 waiting、讓 cpu）；出現了就讀：`ok:false`→errors+1，errors≥3 進 stuck，否則回 llm 重送（新名字）；`ok:true`→act | 101／llm／stuck／act |
| act | 有 `tool_calls`：每個都跑 `tools/<名字>/`（aos-exec，參數 JSON 走 stdin，stdout 截 8 KB 當 `tool` 訊息接回 messages；工具不存在或退非 0 也照樣把錯誤當結果接回去）→ llm；沒有 tool_calls：assistant 文字接進 messages、寫一則 outbox、退 0 → idle；空白回覆：不寫 outbox，記一次 → idle | llm／idle |
| stuck | 連錯 3 次，這句先放著；只掃信箱，有新信才回 llm | idle-ish |

不做：七格縮成五格（collect 併進 idle、retry 併進 wait 的錯誤分支）；`--home`（世界就是本體）；packs（工具就是資料夾，跟 inst 同一套）；文字 tool call 救回（先看 gemma-4 會不會乖，不乖再說）；每題步數上限與預算（kernel 的 `bad_after` 已經擋住連續失敗）；kids／contacts／side packs／MCP。

**`aos-user`**（給人的殼）：`aos-user A say "…"`（寫一封 `inbox/user/<時間戳>.json`）、`aos-user A tail [-n N]`（印 outbox 最近幾則）、`aos-user A status`（state、turn、在等哪個 request、幾封沒讀）、`aos-user A new --name X --system "人格"`（建資料夾骨架＋兩個範例工具 `echo`、`sh`＋inst.json）。`talk` 互動模式先不做（`say` 完 `aos-kernel ls` 看它跑就好）。

**跟地基的接點**：agent 自己不打 HTTP、不排程、不等——全交給 kernel：等模型＝退 101；連續失敗＝`bad_after`；看它在幹嘛＝`aos-kernel ls`＋`aos-kernel llm ls`。

## 24.4 落地順序

1. Opus 撈遺產（在跑）→ 對照上表，改的地方補進 24.3。
2. 任務書派 codex：`proto4-7/`、測試（假 LLM 結果檔、假工具）、README（大白話）、遊樂場加第 6 站。
3. 真開 daemon＋LM Studio 跑一次「寫信 → 它用 `sh` 工具 → 回信」。
4. 派試玩 r5（agent 那層）。
