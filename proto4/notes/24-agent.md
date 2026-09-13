# proto4 筆記 §24：簡單的 agent，跟 proto2 那樣（2026-09-13 晚，使用者手機）

← [索引](2026-09-08-ideas.md)｜LLM 兩層見 [§22](22-llm-cpu.md)｜逐步執行器見 [§23](23-step-json-python.md)

## 24.1 使用者原話（照錄）

> 可以順便在此基礎上去幫我弄一個簡單的 agent 嗎？就跟 proto2 那樣

「此基礎」＝今天的地基：kernel（proto4-3）、LLM 排程當 kernel module（proto4-5）、逐格執行＋等檔退 101（proto4-6）。

## 24.2 proto2 的 agent 長什麼樣（README 摘要）

一個 agent 就是一個資料夾：`system-prompt.json`（人格）、`prompts.json`（記憶，OpenAI messages 陣列）、`tools.json`（`packs` 列 Python 工具包＋`tools[]` 一句 shell 當工具）、`state.json`、`inbox/<來源>/*.json`（讀過搬 `read/`）、`outbox/0001.json`（它說的話）。`aos-agent exec 世界` 一次走一格，七格：idle（掃信）→ llm（寫請求）→ wait（等結果）→ act（跑工具或說話）→ collect（再掃信）→ llm…，出錯進 retry（每 20 格重送、連錯 5 次 stuck 只等新信）。`aos-user say|listen|talk|status|spawn`。後來長出 18 個工具包、工作室、小孩、預算。撈遺產的逐條決定在 [agent/legacy-harvest.md](agent/legacy-harvest.md)（Opus 撈，任務書 `agent/harvest-task.md`）。

## 24.3 v1 定案（Fable 草稿 → 撈完遺產改定；使用者沒反對就照做）

**一句話**：agent 是一支「一叫走一格」的程式，放進 kernel 就活著；等模型、閒著沒信都退 101 讓 cpu；叫模型走 kernel 的 LLM 排程；工具是資料夾裡的可執行檔，用 aos-exec 跑。

**資料夾**（`proto4-7/`，指令 `aos-agent`、`aos-user`；世界＝本體，沒有 `--home`）：

```
A/agent.json         {"name":"bob","system":"人格一段話","K":"/abs/K","max_steps_per_question":60,"tool_output_limit":8000}
A/messages.json      記憶：OpenAI messages 陣列，system 不放（每次叫模型從 agent.json 補）；只有 agent 自己寫
A/tools/<名字>/tool.json  {"description":"…","parameters":{JSON schema}}（name＝資料夾名）
A/tools/<名字>/run        可執行檔（任何語言）：參數 JSON 從 stdin 進、stdout 當結果、退出碼非 0 也把 stdout＋stderr 當結果回給模型
A/inbox/user/*.json  一封信一個檔 {"from","time","content"}；讀過搬 inbox/user/read/（v1 只有 user 一個來源）
A/outbox/0001.json   它說的話 {"time","content"}，獨立遞增計數器
A/state.json         見下
A/inst.json          放進 kernel：{"argv":["/abs/proto4-7/aos-agent","."],"cwd":"/abs/A","stderr":"err.txt"}
```

`state.json`：`{"state":"idle|ask|wait|act","question":N,"step":N,"request":"K/llm/results/<id>.json"|null,"checks":N,"errors":N,"idle_since_error":N,"stuck":false,"last_error":"…"|null,"outbox_n":N}`。

**四格**（`aos-agent A`；退出碼：0 做了事、101 在等（模型或信）、100 收工（agent.json 有 `"stop":true` 時）、1 這格自己壞了（檔案壞、K 不存在）、2 用法錯）：

| state | 做什麼 | 變成 |
|---|---|---|
| idle | 掃 `inbox/user/`（不含 `read/`），有信：整封以 `{"role":"user","content":"[user] …"}` 接進 messages、搬 `read/`、`question+1`、`step=0`、清 errors／stuck → ask。沒信：對話尾巴若是沒人回的 user／tool 訊息（安全網）且沒 stuck → `idle_since_error+1`，滿 20 就回 ask 重送；其他情況退 101 | ask／101 |
| ask | `step+1`；超過 `max_steps_per_question` → 寫一則 outbox「這題走了 N 格先停，回我一句再繼續」、標 stuck → idle。否則把 system＋messages＋工具清單（OpenAI `tools` 格式，從 `tools/*/tool.json` 生）寫成 `req.json`，`aos-kernel llm K req.json --name <name>-<question>-<step>`（不等；同名同內容冪等，重跑不重扣），記 `request` → wait | wait／idle |
| wait | 結果檔沒出現：`checks+1`，滿 600 當一次錯（見下）；否則退 101。出現了：`ok:false`／沒有 choices／空白回覆 → 算一次錯：`errors+1`、`last_error`、`idle_since_error=0` → idle（idle 會在 20 格後重送；`errors≥5` 標 stuck、寫一則 outbox「這句先放著，等你新信」）。`ok:true` → act | 101／idle／act |
| act | assistant 訊息接進 messages（含 tool_calls）。有 `tool_calls`：每個跑 `tools/<名字>/run`（`aos.call(run, stdin=參數 JSON, capture=True, timeout_ms=60000)`，工具不存在＝結果「沒有這個工具」），stdout 截 `tool_output_limit` 字以 `{"role":"tool","tool_call_id","content"}` 接回 → ask。沒有 tool_calls：寫一則 outbox，退 0 → idle。內容是「寫成文字的 tool call」（`<tool_call>`、`[TOOL_CALLS]`、`<function=` 開頭）→ 挖出頂層 JSON 物件、name 對得上就當正式 tool_calls；救不回來算一次錯 | ask／idle |

不做（撈遺產逐條理由見 [agent/legacy-harvest.md](agent/legacy-harvest.md)）：`collect`／`retry`／`stuck` 三格（併成欄位）；`--home`；Python 工具包與掛勾；「只通知不塞內容」的信箱（信一律整封進記憶，`inbox_*` 工具全免）；`named_tool_objects` 那種靠正則猜的救回；kids／contacts／side packs／MCP／預算／模板／team。**唯一保留的煞車**是 `max_steps_per_question`（等的格不算）；**唯一新加的**是 wait 的 `checks` 上限（新地基沒逾時）。

**`aos-user`**：`aos-user A say "…"`（寫 `inbox/user/<時間戳微秒>.json`；省略文字讀 stdin）、`aos-user A listen [--new] [--once]`（盯 outbox，每則印 `--- 0006 ---` 再印 content）、`aos-user A talk`（`你> ` 打一句＝say，outbox 冒新檔就印 `bob> `；自己不推格，要 kernel 在跑）、`aos-user A status`（一行：哪一格、第幾題第幾步、在等哪個檔等了幾次、錯幾次、stuck 沒、幾封沒讀）、`aos-user A new --name bob --system "…" --K /abs/K`（建骨架＋兩個範例工具 `echo`（原樣回）與 `sh`（跑一句 shell，cwd＝A，60 秒）＋inst.json）。

**跟地基的接點**：agent 不打 HTTP、不排程、不睡；等＝退 101（kernel 標 waiting、有人排隊就讓 cpu）；模型錯誤自己記帳退 0，不會被 `bad_after` 退件（只有檔案壞掉才退 1）；看它在幹嘛＝`aos-user status`＋`aos-kernel ls`＋`aos-kernel llm ls`。

## 24.4 落地順序

1. Opus 撈遺產 → 改了草稿五處：四格、閒著退 101、空白回覆算錯、wait 的 checks 上限、請求名可重現吃冪等。
2. 任務書派 codex：`proto4-7/`、測試（假 LLM 結果檔、假工具）、README（大白話）、遊樂場加第 6 站。
3. 真開 daemon＋LM Studio 跑一次「寫信 → 它用 `sh` 工具 → 回信」。
4. 派試玩 r5（agent 那層）。

## 24.5 落地補記（2026-09-13 傍晚）

codex 一輪做完 `proto4-7/`（`aos-agent`、`aos-user`，28 條測試；任務書 `proto4-7/notes/codex-task-1.md`、回報 `codex-out-1.md`），遊樂場第 6 站跟著上。真開 daemon＋LM Studio（gemma-4-e4b）跑「寫信 → 用 sh 工具 → 回信」踩到兩個地基的坑，都修了：

1. **第一層 `aos-llm` 沒轉 `tools`**：它只把 `params` 塞進 body，agent 放最外層的 `tools` 被丟掉，模型根本不知道有工具，回了一段「我是語言模型不能 ls」。改成 `tools`／`tool_choice` 是 REQ 的正式欄位、原樣轉給模型（proto4-5 測試 64）。
2. **LM Studio 驗工具 schema**：`parameters` 一定要是 object 且有 `properties`，範例 `echo` 工具寫成 `additionalProperties:true` 就被整個請求退 400（`http` 錯）。agent 連錯 5 次 → stuck → outbox「這句先放著」——**stuck 那條路順便真的走過一次**。修法：`echo` 的 schema 補 `properties`，`load_tools` 一律補 `type:object` 與空 `properties`。

修完整條通：`[user] 用 sh 工具看看…` → assistant `tool_calls sh {"cmd":"ls -la"}` → tool 回 `ls` 輸出 → assistant 一句話 → outbox 0001，約 20 秒。gemma-4-e4b 原生會回 `tool_calls`，文字救回那段這次沒用到。

**試玩 r5 之後（fix-r6）**：agent 那站兩個試玩的都說最好玩。改了三處：一題一封信（idle 一次只拿最舊一個檔，其他留著）；`state.epoch`（`--reset` 不刪 state 而是寫回預設並 `epoch+1`，請求名 `<name>-e<epoch>-q<q>-s<s>`，reset 後改問題不撞名）；`listen --once` 只印沒印過的（`.listen-seen`）。stuck 兩句用詞統一含「（stuck）」。
