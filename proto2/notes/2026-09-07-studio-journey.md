# 2026-09-07 工作室從卡死到自己跑完：一天的過程筆記

← [play/README](play/README.md)｜設計說明 [studio-efficiency](2026-09-07-studio-efficiency.md)｜流程 [docs/studio-flow](../docs/studio-flow.md)

這份是給以後參考的：一個七人 LLM 工作室，從「三輪都交不出東西」到「自己走完接單→交付」，中間踩了什麼、怎麼修、怎麼精簡。按時間順序寫，大白話。

## 0. 起點（09-06～09-07 早上）

- 工作室 preset 七個角色（owner／sales／pm／chief／dev-a／dev-b／qa），一張 todo.py 的單。
- 三輪實玩都沒交付：09-06 燒 120 萬 token 只寫出 spec.md；09-07 早上 6 萬預算與 500 萬預算兩局都在幾分鐘內卡死。
- 三局卡死的點**都一樣**：PM 收到信、系統通知過「你有新信」，模型第一輪工具呼叫壞掉（寫成文字）沒讀成，之後系統再也不叫醒它。預算給多少都沒用。
- 另外看到的：ticks 上限被 idle 空轉穿透（不做事也在加）；個人額度 0 被當成「不設限」；owner 光讀信就燒光額度。

## 1. 任務 D：先把「卡死」修掉（中午）

改法五條，全在 `aos-agent`／`aos_agent.py`（測試 `tests/gate.sh`）：

1. **額度閘門每格都守**：agent 每走一格先看帳。整隊任一項用完→全隊凍住（每人原地不動、鐘照轉但不做事），只有 sales 對甲方回一句「要追加請跑 `aos-user team budget <世界> --add …`」；追加後下一格自動解凍。個人 tokens 用完→自己凍住、報主管一次，主管 `team_grant` 後自動解凍。
2. **0 額度＝0 上限**，preset 先分 5% 給 sales（不然它連接單都動不了）。
3. **ticks 只算 busy 格**（真的做事的那格），idle 空轉不算，閘門才守得住。
4. **模型把工具呼叫寫成文字→救回或重送**：`<tool_call>{…}</tool_call>`、整段 JSON、後來又加上 ```plaintext 裡「工具名: {參數}」三種形式，認得的工具就救成正式 tool_calls 真的跑；救不回來就當協定錯誤同題重送一次，壞文字不進記憶。
5. **已通知但沒讀的信，閒滿 30 格再提醒一次**——這一條就是前三局的死因。

順手修的：`aos-user team status` 多了在途筆數與被擋原因；`team budget --add` 給甲方追加；worker 打 HTTP 前先探 TCP 10 秒（公司 WSL 對關掉的埠會吞 SYN，那 5 條紅測試從此綠）。

## 2. 實玩 4a／4b：修一條、冒一條（12:00～12:45）

用公司 146 那台 ollama（qwen2.5:14b 當 cheap、qwen3:32b 當 chief 的 thinking）。每個新坑都是**當場改程式、當場生效**（agent 每格是新進程），不用重開：

| 時間 | 看到什麼 | 改什麼 |
|---|---|---|
| 11:47 4a | 開隊當下四個 0 額度的人同時寄「額度用完」給主管，owner／PM 還沒收單就燒 2 萬 token；PM 只給 1000 token（一輪 prompt 就超） | 沒事做的人安靜凍著，有人派活才喊；prompt 寫「一次至少 20000」 |
| 11:48 4a | 七人共用 2 路引擎，排隊超過 60 格就被判「LLM 沒回應」，放棄後又重送，舊請求還在燒 | 請求還在 LLM 世界排隊／執行中就一直等（上限 1800 格），等的格不算每題上限 |
| 11:50 4a | sales 等模型等到「這題跑了 60 格要不要繼續」 | 主線等模型的格不算每題動作格 |
| 11:53 4b | PM 派工給 chief 沒先撥額度→chief 凍住喊→PM 收到後模型吐亂碼 `iNdEx="` | 靠「30 格提醒」拉回來，PM 讀信後真的撥了 5 萬——前三局的斷點第一次自己走過去 |
| 11:57 4b | owner 每封小孩回話都自動收到、讀錯 id 六次、10% 額度燒光 | 工作室成員的回話不再自動轉 owner；`inbox_read` 給錯 id 時把真的 id 列回去 |
| 12:01 4b | chief 存 checkpoint 被 `code` 包擋「路徑跑到專案外」——成員家裡的 `team/` 是 symlink | 共用區也算裡面 |
| 12:05 4b | **第一個專案檔落地**：todo.py（1.4KB）、test_todo.py；chief 自己跑測試發現 3 條 TypeError，開始改 | — |
| 12:17 4b | 互等死結：PM 讀錯 id 後決定「等 chief 回信」睡著，chief 在等 PM 補額度 | 睡著的人也照樣被未讀信提醒叫醒 |
| 12:22 4b | PM 醒了，卻把 `team_grant` 寫在 ```plaintext 裡當「計畫」沒真的呼叫；chief 喊過一次就不再喊 | 救回「工具名: {參數}」寫法；凍住的人每 300 格再喊一次 |
| 12:28 4b | 救回機制生效：PM 的 plaintext 三個呼叫都執行了 | — |
| 12:38 4b | **todo.py 三條測試全過**（chief 改到配合測試） | — |
| 12:45 4b | PM 自己的額度也用完、owner 早就用完，撥錢的兩個人都凍住，整隊總額卻沒到，沒人問甲方 | 收局；記成缺口，下一輪做「自動撥、池子乾了替 sales 問甲方」 |

4b 最後：52 萬 token、53 分鐘，todo.py + 測試都能跑，但**沒走到 qa 驗收與交付**（PM 26 輪裡 16 輪在讀信等信）。

## 3. 量一下 token 花在哪（12:45）

| 角色 | LLM 輪 | 一輪 prompt | 工具數 | schema 字數 | 真正在做事 |
|---|---:|---:|---:|---:|---|
| pm | 26 | 8,176 tok | 50 | 13,439 | 5 輪派工；16 輪讀信等信；4 輪撥額度 |
| chief | 21 | 8,776 tok | 64 | 17,895 | 12 輪寫改檔；3 輪讀信；2 輪跑測試 |
| owner | 11 | 5,707 tok | 47 | 12,579 | 0（全在讀信、6 次讀錯） |

結論：**prompt 占 96%，其中一半以上是工具 schema；讀一封信 2～3 輪 ≈ 20k token；撥一次額度 4 輪 ≈ 35k。** LLM 做的大多是「搬信、記帳、轉達」這種根本不需要判斷的事。

## 4. 提效：LLM 只做要判斷的事（13:00 前後，四個 agent 並行）

設計說明在 [studio-efficiency](2026-09-07-studio-efficiency.md)。分工：核心我自己改，流程包（opus）、人格重寫（sonnet）、說明瘦身（sonnet）、資產包（opus）四個 agent 同時做，各管各的檔。

- **核心**（`aos_agent.py`／`aos-agent`／preset）：`tools.json` 加 `only` 白名單（每人只送 5～17 個工具，PM schema 13,439→2,827 字）、`inline_mail`（信整封直接進 prompt、當場搬進 read/，不再花兩三輪去讀）、`team.json` 加 `auto_grant`（成員有活但額度用完，閘門直接從 pm→owner 撥 5 萬、記一筆 auto、當格解凍；池子乾了才替 sales 對甲方喊追加）、preset 的 `assets/` 開隊時整包進 `team/assets/`。
- **流程包 `studio`**：單子 `team/orders/`、任務 `team/tasks/` 都是檔案，狀態機寫死；九個工具各一次做完一串動作（`order_accept` 開單＋轉 PM＋回甲方確認單；`task_assign` 撥額度＋寄整份 spec；`task_report` 跑測試＋記檔案＋通知 pm 與 qa；`qa_run`／`qa_verdict`；`deliver` 複製成品＋交付單）。越權（dev 呼叫 deliver）擋掉。
- **資產包 `pyshop`**：snippets（argparse CLI 骨架、json store、unittest 樣板、README 樣板）、標準檢查（`run_tests.sh`、`smoke_cli.sh`）；`scaffold` 一次生骨架、`run_checks` 一次跑完檢查。snippets 自己就是能跑的小專案。
- **人格**：七份各 6～10 行，只講「你是誰、收到什麼就呼叫哪個工具、不要做什麼」。
- **說明瘦身**：16 包的 PROMPT／TOOLS 描述總字數減半。

## 5. 實玩 4c：新流程（13:09 起，同一張 todo.py 單，300k 預算）

| 時間 | 看到什麼 | 改什麼 |
|---|---|---|
| 13:10 | sales 自己編了單號「新的訂單號」叫 `order_accept`，連錯五輪，撞到每題 60 格上限停下來問我 | 給錯單號就自動接最新那張；人格加「不用給單號、別自己編」 |
| 13:13 | sales 想 `mail_send` 給「甲方」 | 找不到人的錯誤直接說「跟甲方說話不用寄信、直接回文字」 |
| 13:14 | **`order_accept` 一步做完**：開單、轉 PM、固定格式確認單回甲方 | — |
| 13:15 | PM 第一步要「派 chief 定架構」，但 `task_assign` 只認已存在的任務（要 chief `plan_set` 之後才有）——雞生蛋 | 沒 task_id 就在單上開新任務 |
| 13:17 | chief 拆任務：t1 dev-a 寫程式、t2 qa 驗收；額度自動撥給 chief／dev-a／qa，沒人再喊 | `plan_set` 改成接著編號、首席自己那項算 passed |
| 13:20 | PM 派 qa 時沒給 task_id，又開了一個 t3 跟 t2 重複 | 同一人已有還沒派的任務就派那一項，不再開新的 |
| 13:21 | dev-a 用 `scaffold` 一步生出三個檔 | — |
| 13:25 | dev-a `run_checks` 明明 3 條 ERROR，照樣 `task_report` 說「全部通過」 | `task_report` 的 test_cmd 沒過就退回、任務不算完成 |
| 13:29 | 撥錢池子乾了→sales 對我喊追加→我補 10 萬給 PM→全隊解凍（owner 還自己撥了 2.5 萬給 PM） | 上限從 30 萬降到 10 萬：開頭 sales 迴圈時自動撥款餵了它兩次 10 萬 |
| 13:35 | dev-a 改到一半回了句話就算結束，qa 在等回報，全隊閒著 | `on_idle`：手上有任務卻閒著，45 格後寄信提醒自己 |
| 13:40 | 提醒是收到了，但 qwen2.5 只回一段「我接下來要…」不叫工具 | 提醒講明「現在就 read → write 整檔 → run_checks → task_report」，三次沒動改寄主管「我卡住了」 |
| 13:43 | 講清楚的提醒有效：dev-a 真的 write＋run_checks | — |
| 13:45 | dev-a 一個任務吃掉 17 萬（整檔 write 讓對話史一輪 8.6k）；自動撥款撞每人 10 萬上限、改寄主管 | 上限就是煞車，照設計 |

14:00 收局：50 分鐘、486k token（含我追加的 25 萬），t1 done、t2 passed、t4 還在改，沒交付；各局數字在 [play/studio-4](play/2026-09-07-studio-4.md)。

跟 4b 比：接單 1 輪（4b 要 3 輪＋人工）、派工 1 輪、撥額度 0 輪（自動）、讀信 0 輪（直接進 prompt）；PM 一輪 prompt 3k（4b 8k）。**沒解決的是工程師本身**：qwen2.5:14b 改程式配測試會繞好幾輪，`edit` 常對不上原文、`write` 整檔又把對話史撐大。這一段要嘛換強一點的模型給 dev，要嘛把「寫 todo.py 這種小程式」也做成資產（模板夠好就不用改）。
→ 已解：4d 換 haiku／sonnet 就寫出來了（第 10 節）；剩下的問題變成「貴」，不是「做不出來」。

## 6. 給以後的人

- **先把「永遠不會再被叫醒」的路堵死**，再談預算與效能。三局卡死都是同一條路，修法只有幾行。
- **小模型會把工具呼叫寫成文字**，而且花樣很多（`<tool_call>`、純 JSON、plaintext 圍欄）；救回比重送便宜，重送比放棄好。
- **每格都可以改程式**：agent 一格一個進程，坑當場修當場生效，實玩不用重開。
- **量了才知道**：以為是模型慢，其實是 prompt 裡一半是用不到的工具表；以為是預算不夠，其實是撥錢的流程要四輪。
- **能寫死就寫死**：接單、派工、撥額度、回報、驗收、交付這些「搬東西」的動作做成一個工具一次做完，LLM 只剩「拆任務、寫程式、判定過不過」三個要判斷的地方。
- 核心還缺的接點（流程包作者提的）：工具執行前的掛勾（擋越權）、共用的「跑指令」把手、`ctx.put_mail` 失敗沒原因、便宜的單人剩餘額度查詢、`team/` 沒鎖。
  → `team/` 沒鎖已解（第 9 節 `team_lock` flock）；其餘四條還在。

## 7. 傍晚：使用者拍板，加第八個人（tester）

三題都有答案了：push 推上去了；dev 換 qwen3:32b（preset 的 dev-a／dev-b 改走 `thinking` 檔）；qa 不能又寫又驗。

第三題的做法沿用白天那條原則——**規則放工具，不放人格**：

- `plan_set`／`task_assign` 派給 qa 直接回錯，叫他派給 tester。
- tester 的 `task_report` 裡 `files` 一定要有檔名含 `test` 的檔，不然退回；tester 不帶 `test_cmd`（主程式可能還沒好，紅是正常的，先確認 py_compile 過）。
- `qa_verdict(passed=true)` 要任務檔上至少一筆 exit 0 的測試紀錄（`task_report` 的 `test_cmd` 或 `qa_run` 留的），沒有就擋回去叫他先 `qa_run`。白天 4c 就看過 qa「看過了」就判過的樣子。

新的順序：chief 拆「寫程式→dev」「寫測試→tester」兩項；兩邊各自回報；qa `qa_run` 跑 tester 的測試、再判。八人配置還沒實玩過，下一局（4d）要看的是：dev 跟 tester 同時動 `test_<名>.py`（scaffold 會生一份骨架）會不會互蓋——目前只叫 dev 別動測試檔、tester 別動主程式，沒有鎖。
→ 已解（一半）：4d 八人跑完整條到交付，dev 與 tester 沒互蓋（第 10 節）；`team/` 那層有 flock 了，專案檔那層還是靠約定。

## 8. 操作手感（使用者問的：你自己操作順不順手）

順手的：
- **一格一個進程**：改程式不用重開，下一格就生效。今天二十幾條修正都是實玩不停改出來的。
- **一切都是檔案**：看狀況就 `cat state.json`、`ls inbox/`、`tail monitor.log`，不用學新介面；grep 一下就知道誰卡在哪。
- **加工具便宜**：一個包一個檔，`TOOLS`＋`run()`，寫完丟進 `only` 白名單就掛上；規則想「寫死」的時候，幾行就能擋住一種小模型毛病。
- **假 LLM 測試伺服器**：`CALL tool {json}` 劇本讓流程包不用真模型就能跑整條線，改一個工具幾秒就知道有沒有弄壞別人。

不順手的：
- **看「現在在幹嘛」要拼三個地方**（09-07 晚上開工做 `team why`／`team tail`）：state.json（狀態機）、monitor.log（誰在等誰）、inbox（信有沒有讀）。想要一個 `aos-user team why <世界>`，一句話講出每個人卡在哪（等 LLM？等信？額度凍住？睡著？）。
- **除錯要讀模型講了什麼**：`history` 是 JSON，一輪幾 k 字，用 python 撈才看得到 assistant 那段；想要 `aos-user team tail <成員>` 印最近三輪的「模型說／工具回」。
- **協調靠直接改檔**：要插手時（解迴圈、補錢）我是直接 `put_mail`／改 budget.json。其實 `aos-user say <任一成員資料夾>` 就能對任何人講話（使用者提醒的，我原本以為只能對 owner），該用它；補錢已有 `team budget --add`。
- **實玩會弄髒測試**：有背景實玩時 `test.sh` 一定紅一條（殘留進程），而且 `git stash` 一下就污染正在跑的測試；應該讓 test.sh 帶自己的 `AOS_DAEMON_DIR`，跟實玩隔開。
- **共用檔沒鎖**：兩個人同時寫同一張單會互蓋，今天沒踩到，是運氣。

→ 這五條當晚全做掉了，見第 9 節（`team why`／`team tail`、`team/` 加鎖、test.sh 隔離；`aos-user say` 本來就有）。

## 9. 晚上：把「不順手」的四條做掉，外加兩種引擎

四個 agent 並行（各管各的檔，事先講好誰不能碰哪個檔），結果：

- **`aos-user team why <世界>`**：一人一行——狀態、在等什麼（LLM 排第幾位等幾格／哪封信的回信／額度凍住等撥款幾格）、未讀幾封、tokens 剩多少。**`team tail <世界> <成員> -n 3`**：印最近幾輪「模型說／→ 工具／← 工具回」。以後看局不用再翻 state.json＋monitor.log＋inbox。
- **`team/` 加鎖**：`team_lock(root)` 在 `team/.lock` 上 flock，10 秒逾時，進程內可重入；studio 包整支工具包鎖，但跑測試那段（最多 60 秒）放掉鎖再重讀。量出來：8 個進程各撥 20 次款，有鎖 160 筆一筆不掉；沒鎖只剩 23 筆，而且 `write_json_atomic` 的暫存檔名固定，互踩之後 budget.json 直接壞掉。今天沒踩到真的是運氣。
- **test.sh**：從 proto2/ 裡面跑會一條包測試都不跑還印「全部通過」（glob 用相對路徑）——改成以腳本位置定根目錄、找不到檔就紅；殘留進程檢查只看這輪自己的 daemon 目錄，跟實玩隔開。
- **引擎**：aos-llm 多 `api: anthropic`（直連 Messages API，工具呼叫、usage、cache token 都轉成 OpenAI 形狀）與 `api: claude-cli`。後者是給沒有 API key、只有 Max 訂閱的人用的：`claude -p --safe-mode --no-session-persistence --output-format json --tools "" --json-schema … --append-system-prompt …`，對話史從 stdin 餵，`structured_output` 直接就是 `{content, tool_calls}`。踩到一個坑：`--bare` 只認 `ANTHROPIC_API_KEY`，會把 OAuth 登入踢掉，所以用 `--safe-mode`。
  → 這串當天晚上就作廢了：`--safe-mode` 會把 MCP 一起關掉，`--json-schema` 那套「用文字描述工具呼叫」對會用工具的模型也沒用。最後的形狀是 MCP＋`--max-turns 1`，見第 10 節。這條路是「拿 Claude Code headless 當引擎」，用量算訂閱的五小時窗口；當試強模型的路，不當長期方案。

派工的心得：opus 做的三件（why/tail、鎖、引擎）一次到位、回報清楚；sonnet 做 test.sh 隔離時三次停下來「等背景測試」不會自己接著跑，得推兩次，還同時開了三份全套。**簡單任務給 sonnet可以，但要在指令裡寫死「前景跑、不要等通知」。**

## 10. 實玩 4d：八人＋claude-cli（haiku／sonnet），15:16 起

場地 `play-4d`，同一張 todo.py 單，預算 600k。一開局就連踩四條，都是「新東西第一次真的跑」才會冒出來的：

| 時間 | 坑 | 修法 |
|---|---|---|
| 15:17 | 新開的 LLM 資料夾沒放 `.aos/inst`，鐘空轉、請求排著沒人打 | aos-loop 看到 `engines.json` 沒 inst 就自己補「aos-llm exec .」 |
| 15:17 | 鐘是 daemon 開的，PATH 沒有 `~/.local/bin`，worker 找不到 `claude` | engines.json 寫死 `bin`；文件註明 |
| 15:18 | 模型回錯之後 agent 直接回 idle，信已標讀、對話尾巴那句永遠不會再送（跟早上「未讀信不再喚醒」是同一族的坑） | 記 `llm_errors`，20 格後重送，連錯 5 次放著喊一次，新信來重來 |
| 15:20 | 出錯後閒著的格被算成「每題動作格」，60 格就撞 steps 上限、`limit_pause` 等人 | 閒著不動的格算睡眠格 |
| 15:25 | `--append-system-prompt` 留著 Claude Code 自己那兩萬 token 的身份：一發 30k prompt、繞五輪回「無法執行工作流工具」 | 改 `--system-prompt` 整個換掉：2.6k、兩輪 |
| 15:30 | haiku 看到工具清單就發真的 tool_use（`task_assign`），Claude Code 回 No such tool，繞三輪放棄；json-schema 那套「用文字描述工具呼叫」對會用工具的模型沒用 | 改走 MCP：aos-mcp-tools 把請求的工具表當 MCP 工具給它，`tools/call` 只登記不執行，`--max-turns 1` 第一輪就停，從 stream-json 撿 tool_use 當 tool_calls（opus agent 做的，當天就落地在 `aos-llm`＋新檔 `aos-mcp-tools`） |

| 15:50 | dev-a、tester 各八輪就撞每人 100k 天花板（haiku 一輪 prompt 10～19k，對話史帶整檔 edit 長很快）；天花板抬了也要等 300 格才再試撥款 | 凍住喊過之後每 10 格再試一次自動撥款；這局天花板抬到 250k |
| 15:55 | dev-a 的 `test_cmd` 寫 `bash team/assets/checks/run_tests.sh`，但指令在專案目錄跑，exit 127 繞了三輪 | `_run_cmd` 把開頭的 `team/` 翻成 `../../`；退回訊息講清楚路徑 |
| 16:00 | 600k 池子 45 分鐘見底（dev-a 一個人 237k）；owner 自己燒 20k 想「要不要撥」最後說不 | `team budget --add 400k --to pm`。要記：claude-cli 的 prompt_tokens 把 cache_read 也算進去，帳面比真實成本高很多，之後預算要不要對 cached 打折是個決定 |
| 15:53 | `--safe-mode` 連 `--mcp-config` 一起關掉、模型改寫假 XML；一則 assistant 訊息在 stream-json 是好幾個事件 | 改 `--setting-sources "" --disable-slash-commands`；照 message id 合併事件 |

走通的部分：sales 一發 `order_accept`、pm 一發 `task_assign` 給 chief（3.9k）、chief（sonnet）一發 `plan_set` 拆成 dev-a 寫程式＋tester 寫測試、自己的定架構自動算過。跟 qwen 比：同樣的事 qwen 要三到五輪、還會編單號；haiku 一輪。

一個想法：這局每個坑都是「換引擎」帶出來的，跟流程無關。流程層今天下午已經穩了，剩下的都是引擎接口層的事——這代表分層是對的。

### 4d 收局（16:07 交付）

**第一次整條鏈自己走到交付**：sales 接單 → pm 派 chief → chief（sonnet）拆 dev-a 寫程式＋tester 寫測試 → 兩人各自回報（dev-a 第一次 test_cmd 路徑錯被退回，改對再報）→ qa 跑 run_checks＋qa_run、三項判過 → pm deliver → sales 把交付單回給甲方。成品：todo.py 99 行、test_todo.py 155 行 13 條測試，我手動跑 add/list/del 都對。50 分鐘，中間我插手四次（補 inst、寫死 bin、重寄兩封信、抬天花板＋追加預算）。

帳（帳面 token，claude-cli 把 cache_read 也算進 prompt）：

| 角色 | 請求 | tokens | 備註 |
|---|---:|---:|---|
| dev-a（haiku） | 21 | 325k | 一輪 10k→20k，對話史帶整檔 |
| pm（haiku） | 18 | 210k | 其中兩輪是引擎壞掉那段 |
| qa（haiku） | 14 | 120k | |
| tester（haiku） | 9 | 107k | |
| chief（sonnet） | 6 | 39k | 一發拆對 |
| owner（haiku） | 4 | 28k | 兩輪在想「要不要撥錢」 |
| sales（haiku） | 4 | 13k | |
| 合計 | 76 | 841k | haiku 49 發、sonnet 27 發 |

交付漏了一個檔：dev-a 的 files 寫整條 `team/projects/<單號>/todo.py`，deliver 只認相對專案目錄的名字，只交了 test_todo.py。工具端修掉（前綴剝掉）。

跟 4c（qwen）比：流程一樣、卡點完全不同。qwen 卡「做不出來」；haiku 做得出來，卡的是「額度帳面被 cache token 灌水」和「對話史越滾越大」。下一個要決定的是預算要不要對 cached token 打折，以及 dev 要不要每個任務開新對話史。


## 11. 感想與原則（收工）

16:07 那行 `delivered` 是今天真正的分界：**第一次「它做、我看」**——我沒動一行程式，一條鏈自己從接單走到把成品交回甲方。下面是這一天累積下來、下次還會用到的東西。

### 系統設計原則

- **先堵「永遠不會再被叫醒」的路，這比預算、比模型好壞都重要。** 前三局全卡在同一個地方（PM 信通知過、沒讀成，之後系統再也不叫它），修法只有幾行。模型會犯錯不奇怪，可怕的是犯錯之後沒人再喚醒它。
- **同一族的坑今天踩了兩次**：早上是「信讀了沒人再叫醒」，晚上是「模型出錯就回 idle、對話尾巴那句永遠不會再送」。所以以後看到任何 `return "idle"` 都要先問一句：**「誰會再叫醒它？」** 沒有答案就是死路。（已根治：`aos-agent` 未讀信 30 格重提醒；`llm_errors` 20 格重送、連錯 5 次才放著、新信來重來；`dangling_turn()` 當安全網——閒著而對話尾巴是沒人回的話，就不准放著。泛用的 stuck 狀態還在做。）
- **LLM 愈少參與愈穩，比原本想的更對。** 接單、派工、撥錢、回報、驗收做成工具之後，模型只剩「拆任務、寫程式、判過不過」三件要動腦；其他都是搬東西，寫死就好。
- **分層是對的，換引擎那一小時就是證據。** 4d 六個坑全在引擎接口層（`.aos/inst` 沒放、PATH 沒有 `claude`、`--append-system-prompt` 留著 Claude Code 兩萬 token 的身份、`--safe-mode` 會把 MCP 一起關掉、stream 事件要照 message id 合併、haiku 直接發真的 tool_use），流程層一行沒動。
- **不要跟模型的習慣打架，順著它然後在系統端收口。** 原本想讓模型「用 JSON 描述它想叫的工具」，這是跟本能作對——會用工具的模型看到工具名就直接叫。正解是真的給它工具（MCP），但那台 MCP 只登記不執行、`--max-turns 1` 第一輪就停，呼叫由我們自己跑。
- **一格一個進程很好用。** 每個坑都是實玩不停、當場改程式、下一格生效，一天修二十幾條，不用重開任何一局。

### 模型的毛病怎麼擋

小模型的毛病很固定，可以一條一條用工具擋掉——**規則放工具，不放人格**：

| 毛病 | 擋法 |
|---|---|
| 自己編單號（sales 連錯五輪） | 給錯單號就自動接最新那張（`packs/studio.py` `order_accept`） |
| 把工具呼叫寫成文字（`<tool_call>`、純 JSON、```plaintext 裡「工具名: {參數}」） | 認得的救回來當正式呼叫、救不回來同題重送一次（`aos-agent`） |
| 測試紅字視而不見，照樣報「全部通過」 | `task_report` 帶的 `test_cmd` 沒全過就退回，任務不算完成 |
| 被空泛提醒只回一段計畫不動手 | 提醒直接寫「現在就 read → write 整檔 → run_checks → task_report」，三次沒動改寄主管「我卡住了」 |
| qa 又寫又驗 | 派工不能派給 qa；沒有一筆 exit 0 的測試紀錄不能判過 |

- **qwen 跟 haiku 是兩種病。** qwen2.5:14b 是**做不出來**（改程式配測試繞二十輪、`edit` 常對不上原文）；haiku 是**做得出來但貴**（對話史帶整檔，一輪 10k 漲到 20k，每輪重送）。前者的解是換模型，後者的解是管記憶——兩件事不要混在一起想。

### 帳要怎麼算

- **量了才知道錢花在哪。** 原本以為是模型慢、預算給太少；算完帳才發現 **96% 的 token 是 prompt**，其中一半以上是根本用不到的工具表（PM schema 13,439→2,827 字），而 PM 那 26 輪裡有 16 輪只是在讀信、等信（讀一封信 2～3 輪 ≈ 20k、撥一次額度 4 輪 ≈ 35k）。
- **量的東西要先確認真的量到了。** 我從 `proto2/` 裡面跑 `test.sh`，看到「全部通過」就信了——其實一條包測試都沒跑（glob 用相對路徑）。已改成以腳本位置定根目錄、找不到包測試就紅。
- **帳面不等於成本。** claude-cli／anthropic 的 `prompt_tokens` 把 `cache_read` 也算進去，4d 帳面 841k 裡一半以上是 cache（真實價格約 1/10）。預算閘門要不要對 cached 打折，還沒決定（[WAIT_USER 11](../../wf/WAIT_USER.md)）。
- **天花板就是煞車，但要跟引擎配。** `max_per_member` 100k 對 qwen 剛好，對 claude-cli 太低（4d 手動抬到 250k～500k）。凍住之後也不能等 300 格才再試，改成每 10 格重試一次自動撥款。

### 派工與自己操作的教訓

- **開 agent 並行真的快，但前提是規格先寫死、各管各的檔。** 今天兩批各四個 agent 同時做，事先講好誰不能碰哪個檔，都沒撞到。
- **opus 跟 sonnet 要用不同的講法。** opus 做的三件（why/tail、加鎖、引擎）一次到位，每件回報都有量測、還會主動說「我沒驗到什麼」；sonnet 做得對，但三次停下來等背景測試、還同時開三份全套。給 sonnet 的指令要寫死：**前景跑、不要等通知、不要平行開測試。**
- **我自己兩個失誤都是同一種：明知道有東西在跑還去動它。** 一是上面那條「看到全部通過就信」；二是明知 agent 正在跑測試，還去 `git stash` 動工作樹，差點污染人家的結果。
- **這套開始有手感了**：`team why` 一眼看出誰卡在哪，`team tail` 三行看出模型在幹嘛，坑當格修當格生效，一切都是檔案（`cat state.json`、`ls inbox/`、`tail monitor.log`）。

一頁版的清單在 [lessons](2026-09-07-lessons.md)。
