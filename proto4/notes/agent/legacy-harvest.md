# 撈遺產：proto2 的 aos-agent 有哪些決定值得帶進 proto4-7

只讀，沒有動任何檔。讀了 `proto4-3/`、`proto4-5/`、`proto4-6/` 三份 README；`proto2/README.md`、`proto2/aos-agent`（605 行）、`proto2/aos_agent.py`（1534 行）、`proto2/aos-user`（890 行）、`proto2/packs/mailbox.py`、`proto2/packs/fs.py`、`proto2/docs/packs-api.md`、`proto2/examples/agent/`；筆記讀了 `notes/2026-09-07-lessons.md`（30 條）、`notes/play/README.md`、`notes/play/2026-09-06-{whole-system,newagent,kids}.md`、`notes/2026-09-06-ideas-vs-proto2.md`；另外掃了 `proto/`、`proto3/`、`proto4-2/`。

## 0. 其他 proto 有沒有 agent

- **`proto/`**：有。`proto/examples/agent`、`examples/agent-real`、`play-agent.sh`（真的接 LM Studio 玩過），agent＝一塊地上的一支 `aos run`，腦是 `brain.py`，工具用文字 `TOOL: ls work` 講。`proto/FINDINGS.md` 有五條 agent 實玩發現，很值錢（見第 3 節）。
- **`proto3/`**：有，但只是輪廓。`proto3/src/agent.janet` 四態 `idle→think→wait→act`，唯一的基礎設施是 `wait-for`（登記「等到什麼算數、等到了做什麼、等幾格放棄」，**時鐘是唯一喚醒者**）。出錯先回 idle（它自己註明是簡化）。另有 `proto3/notes/2026-09-08-backbone-pains.md`，是 proto2 骨幹的解剖圖，寫得比 proto2 自己的文件清楚。
- **`proto4-2/`**：沒有 agent，只有 inst／cpu／daemon／kernel。

## 1. proto2 agent 的骨架

一個 agent 就是**一個世界資料夾**。`.aos/inst` 裡只有一句 `aos-agent exec . --home agent`，其餘全放在本體資料夾（home）。時鐘（`aos-loop` 或 daemon）每格叫一次 `aos-agent exec`，它讀 `state.json` 決定這格做什麼、做完寫回下一格的 state，**一格只走一步、絕不等網路**。LLM 不是它的功能，是隔壁一個平起平坐的資料夾，靠 `requests/` 丟、`results/` 撿。

| state | 做什麼 | 做完變成 |
|---|---|---|
| `idle` | 掃 `inbox/*/`，有沒讀的信就接進記憶；通知過卻沒讀的，閒滿 30 格再提醒 | 有信 `llm`，沒信留 `idle` |
| `llm` | 人格＋各工具包的 PROMPT＋整份記憶＋工具清單，寫成請求丟進 LLM 資料夾 | `wait` |
| `wait` | 撿結果。還在排隊／執行中最多等 1800 格，請求不見了結果又沒出現只等 60 格；LLM 沒鐘立刻報錯 | 撿到 `act`；出錯 `retry` |
| `act` | 有 `tool_calls` 就跑工具、結果接回記憶；沒有就把話印出來、落一份 `outbox/` | 有工具 `collect`，有文字 `idle` |
| `collect` | 再掃一次信箱（沒新信也照走） | `llm` |
| `retry` | 對話尾巴那句沒人回，等著同題重送；照樣掃信箱 | 新信／滿 20 格 `llm`；連錯 5 次 `stuck` |
| `stuck` | 連錯太多次，這句放著，只等新信 | 有新信 `llm` |

**檔案佈局**（都在 `<home>/`）：`system-prompt.json` 人格、`prompts.json` 記憶（OpenAI messages 陣列）、`tools.json` 工具、`llm.json` 指到哪個 LLM 資料夾＋上限、`state.json` 走到哪、`contacts.json`／`parent.json`／`kids.json` 關係、`inbox/<來源>/*.json` 與 `inbox/<來源>/read/`、`outbox/<四位數>.json`、`llm-result.json`（`wait` 寫、`act` 讀，兩格之間就靠這個檔傳話）、`kids/<名字>/`。

**信箱**：一封信一個 JSON 檔 `{"from","time","content"}`（也可以是陣列），來源就是資料夾名。`user` 來源特別：整封直接當 user 訊息接進記憶（前面加 `[user] `）、當場搬進 `read/`；其他來源只在 prompt 裡加一句「你有新信：team 1 封」，內容要模型自己叫 `inbox_read` 去拿。同一封只通知一次（記在 `state.json` 的 `announced`）。

**工具兩條路**。(a) **工具包**：一包一個 `.py`，自帶 `TOOLS`（OpenAI function schema 陣列）、`PROMPT`（會被串進 system）、`run(name, args, ctx)`，可再帶 `on_idle`／`on_act`／`on_reply`／`on_result`／`on_system_prompt` 掛勾；`tools.json` 的 `packs` 列到誰就載誰，先找 `<home>/packs/`，再找 `proto2/packs/`。(b) **`tools[]`**：一個工具就是一句 shell 指令，`command` 不送給模型，參數 JSON 從 stdin 進去、stdout 當結果。同名工具：包排前面的贏，`tools[]` 排最後。另有兩個省 token 開關：`only`（白名單，只把列到的工具送給模型）、`inline_mail`（哪些來源的信整封直接進記憶）。

**`aos-user` 子命令**：`new`（模板開新 agent）、`templates`、`packs`、`say`、`listen`、`talk`、`status`、`spawn`，以及工作室那組 `team new|status|budget|why|tail|stop` 與 `order`。

## 2. 逐條決定表

| 項目 | proto2 怎麼做／為什麼 | 建議 | 理由 |
|---|---|---|---|
| 資料夾佈局 | 世界／home 兩層，`.aos/inst` 一句話決定誰跑；`--home` 相對世界 | **改** | proto4 沒有 `.aos/inst` 那套文字了，kernel 排的是 inst.json、cwd 自己寫死。agent 就一個資料夾，不要兩層 |
| `--home` | 為了「`.aos/` 是機器地盤、本體平鋪」而生，`aos-user` 還要回頭去 inst 撈它 | **不採** | 兩層沒了，這個旗標就沒有存在理由；`resolve_home()` 那段正則解析 inst 是純負債 |
| messages 存法 | `prompts.json` 一份 JSON 陣列，`append_history` 整檔讀＋整檔寫；`memory`／`branch`／`bigmem`／`ref` 四個包還會直接改整檔 | **採（一份陣列），但改所有權** | 陣列最簡單、模型格式原生；但只准 agent 自己寫，工具一律透過回傳值進記憶。寫檔照 proto4 慣例先 `.tmp` 再 rename |
| state 機七格 | 七格裡有三格（`collect`／`retry`／`stuck`）是實玩撞到死路後補的 | **改成四格** | `idle→ask→wait→act`。`collect` 純多餘（`act` 完回 `idle`，`idle` 本來就掃信）；`retry`／`stuck` 改成 `idle` 上的兩個欄位（錯幾次、上次錯在第幾格），行為照舊、狀態圖少一半 |
| retry／stuck 規則 | 20 格重送、連錯 5 次放著只等新信、新信一來清帳；外加 `dangling_turn()` 安全網（要回 idle 但對話尾巴是沒人回的話 → 改 retry） | **採，一條都不要砍** | lessons 第 1～4 條：前三局實玩全死在「回了 idle 但沒有人再叫醒它」。這是整份遺產裡最貴的幾行 |
| 信箱一來源一資料夾 | `inbox/<來源>/` ＋ `read/`，來源就是資料夾名 | **採，但 v1 只開 `user` 一個來源** | 格式本身零成本、以後多 agent 才有意義；v1 沒有別的寄件人，不要先蓋空資料夾 |
| 「只通知不塞內容」＋ 未讀重提醒＋`announced` | 為了省 token 只說「你有新信 1 封」，讓模型自己叫工具讀 | **不採，改成一律整封進記憶** | lessons 第 11 條自己推翻了它：讀一封信 2～3 輪 ≈ 20k token，最後靠 `inline_mail` 繞回來。直接 inline 之後，`announced`、未讀重提醒、`inbox_*` 四個工具**全部消失** |
| outbox 四位數編號 | `%04d.json` 用 `step` 當號，撞名再補 `-%02d` | **改成獨立遞增計數器** | 四位數零填充讓人一眼看得出順序，這點好；綁 `step` 只是為了省一個計數器，代價是要處理撞名 |
| 工具宣告格式（packs／tools.json） | packs 是 Python 模組（TOOLS＋PROMPT＋run＋五種掛勾）；`tools[]` 是一句 shell 指令 | **只採 `tools[]` 那條，形狀換成 inst** | proto4 全線的通貨是 inst.json：一個工具＝一份 inst.json（或一個資料夾），參數 JSON 從 stdin 進、stdout 當結果。這樣工具能用任何語言寫、能單獨 `aos-exec` 測、能被 kernel 排。Python pack 把工具焊死在 agent 進程裡，且掛勾是 proto2 後期複雜度的主要來源 |
| 工具宣告本身 | `{"name","description","parameters"}`（OpenAI function schema） | **採，原封不動** | 模型認得的就這個格式，自己發明一套只會讓救回邏輯更難寫 |
| 工具回傳怎麼接回記憶 | `{"role":"tool","tool_call_id":…,"content":…}`；pack 回 JSON 就 dumps、`tools[]` 回字串就原樣 | **採格式，簡化內容** | 一律拿 stdout 當純文字、超過 N 字截斷（proto2 有 `truncate`，但沒有一致地用）。兩套內容規則沒必要 |
| 模型把 tool call 寫成文字的救回 | `TOOL_CALL_SMELL` 嗅探（`<tool_call>`／`[TOOL_CALLS]`／`<function=`）→ 挖出頂層 JSON 物件，name 對得上就救成正式 `tool_calls`；救不回來當協定錯誤、同題重送一次 | **採簡版** | lessons 第 17、20 條：這是小模型最固定的病，救回只有幾十行。**但 `named_tool_objects()`（```plaintext 裡「工具名: {參數}」）不採**——那條靠正則猜語意，容易誤傷，等真的撞到再加 |
| `max_steps_per_question` | 預設 60，超過回一句話等使用者；新 user 信重置 | **採**，且必須連「等的格不算」一起採 | lessons 第 7 條：不扣掉等待，還沒等到就先撞上限停下來問人。這是 v1 唯一保留的煞車 |
| 空白回覆處理 | 記一次 `empty_replies`、不寫 outbox、**回 idle** | **改成算一次錯，走 retry** | 回 idle 又是一條死路（實測 qwen 常空白）；目前是靠 `dangling_turn()` 安全網撈回來的，不如一開始就誠實算錯 |
| kids | `spawn` 生子世界＋雙向通訊錄＋名冊＋shared／own 兩種鐘 | **不採** | 使用者說先不做。而且 proto4 的 kernel 已經能排任意行程，真要多 agent 時 `aos-kernel add` 一行就有第二顆 cpu，不需要 shared 鐘那套 |
| contacts | `contacts.json` 名字→世界路徑 | **不採** | 只有一個 agent、一個使用者，沒有東西可查 |
| side packs（旁線） | `Ctx.send/pending/cancel/sleep_until`＋`side/<kind>/<id>.json`＋`on_result` | **不採** | 它存在的唯一理由是「一格不能等網路」；proto4-5 的 kernel 排隊＋等檔退 101 就是同一件事的更簡版，而且是地基提供的 |
| MCP | `aos-mcp-tools` 只登記不執行，用來騙 claude-cli／codex-cli 吐真的 `tool_use` | **不採** | 那是為了「借別人的 CLI 當引擎」才需要的；proto4-5 只打 OpenAI 相容端點，模型原生就會回 `tool_calls` |
| 預算（team／budget／auto_grant／`max_tokens_per_day`） | 每格都守的硬閘門、個人與整隊兩層、自動撥款、池子乾了替 sales 喊甲方 | **不採** | 使用者說先不做。lessons 自己的順序也是「先堵死路 → 再量 → 再固化 → 再換模型 → **最後**才調預算」，v1 連第一關都還沒過 |
| LLM 怎麼接 | `llm.json` 的 `dir` 指到 LLM 資料夾，`write_request`／`read_result`（拿走就刪） | **改成 proto4-5** | `aos.llm_submit(K, req, name)` 丟給 kernel、結果在 `K/llm/results/<name>.json`。**結果檔不要拿走就刪**，留著才有帳可對 |
| 請求名字 | `<name>-main`＋時間戳 | **改成 `<agent>-<第幾題>-<第幾步>`** | proto4-5 同名同內容會比對 SHA-256 並冪等，重跑不會重複扣 token；這禮物只有在名字可重現時才拿得到 |
| 一格的退出碼 | 永遠 0，idle 也是 0（空轉） | **改** | 等 LLM 結果、或閒著沒事 → 退 **101**（kernel 記 waiting、有人排隊就讓出 cpu）；使用者喊收工 → 退 **100**。`bad_after` 要在 init 時設 0，不然 agent 的正常錯誤會被丟進 `procs/bad/` |
| 設定檔數量 | 一個 agent 八個小 JSON | **改成一份 `agent.json`** | 人格、K 路徑、工具清單、上限全放一份；`state.json` 與 `messages.json` 另外兩份是會被改寫的，分開合理 |
| `aos-user` | 15 個子命令（含整隊那組） | **只採四個** | `say`／`listen`／`talk`／`status`。`new` v1 用手抄範例就好，`spawn`／`team`／`order` 跟著 kids 與預算一起不採 |

## 3. proto2 玩出來的坑：哪些會再撞、哪些自然消失

**自然消失（新地基已經接住）**

- **兩套等待上限（60 格／1800 格）＋自己去 LLM 資料夾翻請求還在不在**：換成等檔退 101，kernel 記 `waiting` 與 `checks`，`aos-kernel ls` 直接看得到。`do_wait()` 那 77 行裡有一半是這件事。
- **「LLM 的鐘沒在跑，這題先停下來」**：proto4-5 的 CLI 在 kernel 沒活著時直接撤單並明說，不會靜靜排隊等一個不會來的結果。
- **結果所有權競速**（whole-system 玩到的：agent 拿走結果、LLM 那側又補一張 `worker died`，重複錯誤＋灌水用量）：proto4-5 的 requests／running／done／results 由 module 一手管，讀結果不搬不刪。
- **重複送出／重複扣款**：`--name` 同名同內容冪等。
- **「shared 鐘和 own 鐘容易混，漏開一顆只表現成沒回話」**（kids、mcp、whole-system 都撞過）：kernel 一顆、cpu 自己派，沒有「一個世界一顆鐘」這回事了。
- **非原子寫**：proto4 全線先寫 `.tmp` 再 rename。
- **proto/FINDINGS 那條「等 LLM 的 60 秒，從外面看跟卡死一模一樣」**：`aos-kernel llm ls K` 分得出 queued／running／done。

**會再撞（跟地基無關，或地基明說沒做）**

- **模型把 tool call 寫成文字、漏參數、叫錯工具、自己編 id**——這是模型的病，換地基不會好，救回邏輯照抄。
- **小事跑幾十格**：newagent 那輪「用 ls 看看資料夾」跑到 step 66、叫了七次工具；kids 那輪一題 17×23 花 84 格。`max_steps_per_question` 是唯一的煞車。
- **等永遠沒逾時**：proto4-6 自己明說「沒有逾時、一次只等一個檔、kernel 不會叫醒」。proto2 至少有 60／1800 格上限，新地基**反而更沒有**——`checks` 上限要自己加。
- **死路**：kernel 只保證「等的檔到了會再跑一格」，不保證「沒人叫醒的 idle」被救。`dangling_turn()` 安全網還是要自己寫。
- **prompt 占 96% token，其中一半是用不到的工具表**（lessons 第 10 條）：v1 工具少就先不痛，但工具一多就會回來，`only` 白名單的道理要記著。
- **工具輸出整包進記憶**（`fs read` 讀整檔、haiku 一輪 10k→20k）：截斷要一開始就做。
- **狀態不好找**：proto2 的 `status` 一度不顯示當前 state，要人自己拼 `state.json`＋log。lessons 第 13 條的結論是先做看板再修東西。
- **同時跑兩份會互蓋**：proto2 沒鎖，proto4-6 也明說「同一份程式不要同時跑兩次」。kernel 只保證一個行程一顆 cpu，人自己手動再跑一次就爆。
- **reasoning 燒光額度、正文空白**（think、sched、whole-system）。
- **路徑基準搞混**：proto4-3 把它收得比 proto2 嚴（一律以 cwd 為中心），但 agent 呼叫工具時的 cwd 是誰，還是要自己講清楚。

## 4. 我建議的 v1 最小集

1. 一支 `aos-agent step <家>`，一次走一格，state 在 `<家>/state.json`；等 LLM 或閒著退 101、收工退 100，靠 kernel 排（init 時 `--bad-after 0`）。
2. 四態 `idle→ask→wait→act`，加 `dangling_turn()` 安全網＋「錯幾次／上次第幾格錯」兩個欄位（20 格重送、連錯 5 次放著等新信）。
3. 一份 `agent.json`（人格、kernel 家 `K`、工具清單、`max_steps_per_question`），一份 `messages.json`（OpenAI 陣列，只有 agent 自己寫）。
4. 信箱只有 `inbox/user/` 與 `read/`，信整封直接進記憶、當場搬走；`outbox/0001.json` 遞增。
5. LLM 走 `aos-kernel llm K req --name <agent>-<題>-<步>`，結果在 `K/llm/results/`，不刪。
6. 工具＝一份 inst.json，`{"name","description","parameters"}` 送模型，參數 JSON 從 stdin、stdout 當結果、截斷後以 `role:tool` 回記憶。
7. 救回「寫成文字的 tool call」簡版；救不回來同題重送一次；空白回覆算一次錯。
8. `aos-user say|listen|talk|status` 四個，`status` 一行講完：現在哪一格、在等哪個檔、等幾次、上次錯什麼、這題第幾格。
9. 加一個 proto2 沒有的：等檔 `checks` 上限，超過就當一次錯走 retry（新地基沒逾時）。
10. 不做：kids、contacts、旁線、MCP、預算、工具包 Python 模組、模板、team。
