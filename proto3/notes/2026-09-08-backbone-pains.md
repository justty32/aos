# proto2 骨幹哪裡不好、proto3 該解什麼

給 proto3 設計用。**工具包（`proto2/packs/*.py`）沿用，這份只講骨幹。**
只讀不改；所有出處都是 `proto2/` 底下的檔案行號、`wf/` 的文件段落，或 git commit。

日期：2026-09-08。程式碼狀態＝`062e5cd`（main，乾淨）。

---

## (a) proto2 骨幹現況一頁圖

### 十二支執行檔，各自負責什麼

| 執行檔 | 行數 | 函式數 | 最長函式 | 一句話 |
|---|---:|---:|---|---|
| `aos-exec` | 41 | 2 | `main` 21 行 | 跑一個路徑：**檔案**就直接執行，**資料夾**就把 `.aos/inst` 整段丟 `os.system()`。順手把自己所在目錄塞進 `PATH`。 |
| `aos-loop` | 75 | 1 | `main` 58 行 | 「一直跑 aos-exec」——但**它自己重做了一次**，沒有真的呼叫 `aos-exec`（`aos-loop:37-58`）。讀 inst → 清空 → `os.system()`。 |
| `aos-daemon-kernel` | 667 | 31 | `do_op` 62 行 | 常駐時鐘總管。每格：處理 `requests/`、巡 `clocks/`、死掉的自動重開。**一個鐘＝一個 `aos-loop` 進程＋一個 process group**。 |
| `aos-daemon` | 132 | 4 | `main` 72 行 | 薄客戶端：把 register／unregister／pause／continue 寫成請求檔丟進 kernel 的 `requests/`，等 `done/` 冒出同名檔。 |
| `aos-agent` | 605 | 18 | **`do_exec` 114 行**、`budget_block` 80、`do_wait` 77、`do_act` 52 | agent 走一格的狀態機（七態）。 |
| `aos_agent.py` | 1534 | **97** | `create_team_world` 106、`team_status_of` 75、`spawn` 65 | 名義上是「共用層」，實際上是**大雜燴**：Ctx、信箱、工具包載入、prompt 組裝、旁線生命週期、工作室預算與建隊、spawn。 |
| `aos-llm` | 1793 | 76 | **`do_exec` 173 行**、`to_anthropic` 82、`codex_run` 79、`from_claude_cli` 73、`do_worker` 61 | LLM 世界的派工員（排序、開 worker、收工）＋**四種引擎接口**（openai／anthropic／claude-cli／codex-cli）＋ worker 本人，全擠在同一支。 |
| `aos_llm.py` | 143 | 7 | `write_request` 38 行 | 請求／結果的檔案介面（`write_request`／`read_result`／原子寫）。骨幹裡最乾淨的一支。 |
| `aos-user` | 890 | 47 | `main` 90、`do_new` 48、`do_team_tail` 43 | 人用的殼。混了：建 agent、**建整隊**、看板（`team why`／`team tail`）、聊天（say／listen／talk）。 |
| `aos-mem` | 150 | 7 | `handle` 44 行 | SQLite 記憶世界，一格吃完 `requests/` 寫 `results/`。 |
| `aos-mcp` | 304 | 15 | `call_tool` 39 行 | 把 agent／LLM／daemon 包成 MCP stdio 工具，讓 Claude 扮演使用者下指令。 |
| `aos-mcp-tools` | 131 | 6 | `handle` 30 行 | **只登記、不執行**的 stdio MCP server；claude-cli／codex-cli 兩種引擎共用它來「騙」出模型的 tool_use。 |

合計骨幹 6421 行（工具包另外 5065 行）。

### 誰寫哪個檔、誰讀

| 檔案 | 誰寫 | 誰讀 |
|---|---|---|
| `<世界>/.aos/inst` | 人、`aos-user new`、`kids` 包 spawn（shared 小孩加一行）、`kids_pause`（把那行註解掉）、**`aos-loop` 自己**（看到 `engines.json` 沒 inst 就補一句，`aos-loop:39-44`） | `aos-exec`、`aos-loop` |
| `<home>/state.json` | `aos-agent do_exec` 每格寫回一次（`aos-agent:581-585`）；**各工具包也直接寫**（`ctx.state["studio_nag_step"]`、`review`、`branch_depth`、`ref_meta`…） | `aos-agent`、`aos-user status／why`、`team_status_of`、`kids_list` |
| `<home>/prompts.json` | `append_history`（`aos_agent.py:1510`）；**`memory`／`branch`／`bigmem`／`ref` 四個包直接改整檔**（`packs/branch.py:349`、`packs/bigmem.py:110`、`packs/ref.py:141`） | `do_llm` 每格整檔讀出來送（`aos-agent:57-58`） |
| `<home>/llm-result.json` | `do_wait`（`aos-agent:249`、287） | `do_act`（`aos-agent:326`）——**兩格之間靠這個檔傳話** |
| `<home>/inbox/<來源>/*.json` | `ctx.put_mail`（任何 agent／包）、`aos-user say`、`aos-mcp` | `scan_inbox`（`aos_agent.py:298`）、`mailbox` 包 |
| `<home>/outbox/????.json` | `ctx.reply`（`aos_agent.py:1372`） | `aos-user listen／talk`；子 agent 的 reply 會自動再轉寄一份到父的 `inbox/kid-<名>/` |
| `<home>/side/<kind>/<id>.json` | `Ctx._finish_side`（`aos_agent.py:1257`） | 該包的 `on_result` |
| `<llm>/requests/` → `requests/running/` → `requests/done/` | agent 主線與旁線用 `aos_llm.write_request` 丟；`aos-llm exec` 搬 | `aos-llm exec`（`aos-llm:391`） |
| `<llm>/results/<同檔名>` | `aos-llm worker`（原子寫）；worker 死了由 `aos-llm exec` 補一個 `{"error":"worker died"}`（`aos-llm:465-470`） | `aos_llm.read_result`（**拿走就刪**）、`Ctx.collect_results` |
| `<llm>/usage/<日期>.json`＋`usage/pending/` | worker 丟紙條、`aos-llm exec` 的 `fold_pending` 折進帳本 | `today_usage_for`（每日 token 上限）、**`team_status_of` 每格每人都讀**（預算閘門）、`cost`／`self`／`review` 包 |
| `$AOS_DAEMON_DIR/{kernel.json, requests/, clocks/<id>.json, logs/<id>.log}` | kernel | `aos-daemon`、**`Ctx.clock_of`（各包看鐘）**、`aos-user why` |
| `<root>/team/{team.json, budget.json, orders/, tasks/, assets/, .lock}` | `studio`／`team` 包、`team_auto_grant`、`team_add_budget`（都在 `team_lock` flock 內，`aos_agent.py:491`） | `budget_block` 每格每人都讀（`aos-agent:383`） |

### 怎麼接起來（一條線）

```
aos-daemon-kernel  ──每格──▶ clocks/<id>.json ──▶ 一個 aos-loop <世界> --keep-inst 進程
                                                     │
                                     每格：讀 .aos/inst → os.system()
                                                     │
                    ┌────────────────────────────────┼──────────────────────────┐
                    ▼                                ▼                          ▼
          aos-agent exec .                  aos-llm exec .              aos-exec <子世界>
       （agent 世界，七態狀態機）        （LLM 世界，派工員）        （shared 小孩：借父的鐘）
                    │                                │
                    │  寫 requests/<name>.json       │ 排序 → 開背景 worker → results/
                    └────────────────────────────────┘
                              只透過檔案，沒有 API
```

- **agent ↔ LLM**：只有檔案。agent 寫 `requests/`、`aos-llm exec` 搬進 `running/`、worker 寫 `results/`、agent 讀走就刪。
- **agent ↔ agent**：只有信箱檔案。
- **agent → daemon**：`Ctx._clock`（`aos_agent.py:1335`）去 **fork 一支 `aos-daemon` CLI 子進程**，不是函式呼叫。
- **agent 不寫自己的 `.aos/inst`**（`proto2/README.md:54`），因為怕洗掉 shared 小孩那行——這是一條靠約定維持的規則，沒有機制擋。

### agent 的七態（`proto2/README.md:42-52`、`aos-agent:531-561`）

`idle → llm → wait → act → collect → llm …`，加上 09-07 晚上補的 `retry`／`stuck` 兩態。
**每格開頭還有兩個不在狀態機裡的閘門**：`budget_block`（`aos-agent:494`，凍住就整格不動、`step` 都不加）與 `hard_limit`（`aos-agent:521`）。

---

## (b) 「補丁堆」清單：實玩踩坑後長出來的東西

排序照結構缺口分組。每條標：補在哪、出處、它其實在補哪個洞。

### 缺口一：**沒有統一的「等待／喚醒」機制**（最貴的一個洞）

proto2 從頭到尾沒有「我在等什麼、什麼事會叫醒我」這個概念，只有一個 `sleeping` 布林（`aos_agent.py:1245`）。
於是每踩一次「沒有人再叫醒它」，就在不同地方加一個計時器。**現在骨幹＋工具包裡有 8 個各自獨立的硬編計時常數：**

| 常數 | 值 | 在哪 | 補哪一次坑 |
|---|---:|---|---|
| `UNREAD_REMIND_TICKS` | 30 | `aos_agent.py:31` | 信通知過、模型第一輪讀失敗，之後永遠沒人叫它（**前三局全死在這**，`journey:11`、`lessons:10`；commit `cfffb2b`） |
| `LLM_WAIT_TICKS` | 60 | `aos-agent:18` | 請求不在排隊裡、結果又沒出現 |
| `LLM_WAIT_TICKS_ALIVE` | 1800 | `aos-agent:19` | 七人共用兩路引擎，排隊超過 60 格被誤判「LLM 沒回應」（`journey:33`，11:48 4a） |
| `LLM_ERROR_RETRY_TICKS` | 20 | `aos-agent:22` | 模型回錯之後直接回 idle，對話尾巴那句永遠不會再送（`journey:150`，15:18 4d；commit `c98dced`） |
| `LLM_ERROR_MAX` | 5 | `aos-agent:23` | 同上，避免無限重送 |
| `BUDGET_NAG_TICKS` | 300 | `aos-agent:21` | 凍住的人喊過一次就不再喊（`journey:40`，12:22 4b；commit `13f03bf`） |
| `AUTO_GRANT_RETRY_TICKS` | 10 | `aos-agent:24` | 300 格太久：天花板抬高了也要等五分鐘（`journey:155`，15:50 4d） |
| `TASK_NAG_TICKS` / `TASK_NAG_LIMIT` | 45 / 3 | `packs/studio.py:802-803` | 做到一半停下來、手上有任務卻閒著（`journey:80`，13:35 4c；commit `66c9b77`＋`67f008c`）——**工具包只好自己再造一次喚醒機制** |

同一族的補丁還有：

1. **睡著的人也要被未讀信叫醒**——`scan_inbox` 的註解直接寫「不然『PM 等 chief 回信、chief 等 PM 補額度』這種互等會卡到旁線逾時才解」（`aos_agent.py:330-331`；commit `a0b74b3`；`journey:39`）。
   → 補的是：`sleep_until` 只記「我在等哪一筆」，沒有「還有什麼別的事也該叫醒我」。
2. **`retry` 也要走未讀提醒那條路**，所以 `do_exec` 造了一個假的 state 視圖騙 `scan_inbox`：
   `view = dict(saved, state="idle") if state in ("retry","stuck") else saved`（`aos-agent:507-510`）。
   → 補的是：「閒著」這件事被寫死成字串 `"idle"`，多一個狀態就要多改一處。
3. **`dangling_turn()` 安全網**（`aos-agent:187-193`、573-580）：任何一格算完要回 `idle`、但對話尾巴還是一句沒人回的話，就強制改成 `retry`。註解自己寫：「哪天又多一條『出錯就回 idle』的路，這裡把它撈回來」。
   → 補的是：狀態機沒有不變式（invariant），只好在出口加一道後驗。這是**補丁的補丁**，作者也知道（README 說「泛用的 stuck 狀態還在做」，`journey:193`）。

**實玩紀錄裡同一族的證據**（都指向「沒有阻塞式等待、沒有死路偵測」）：

- 鏈斷之後 **55 分鐘全是 idle 空轉**，每 5 分鐘 +900 ticks，token 早就靜止；「連續 15 分鐘沒動就算卡死」的規則抓不到，因為 idle 一直加 ticks（`play/2026-09-07-studio-3.md:9`、`:14`、`:16`、`:21`）。**忙碌指標與進度指標是同一個數字。**
- 模型在同一輪不停叫 `inbox_sources` 等結果，但結果只有回 idle 才收 ── **自己等自己**（`play/2026-09-06-bigmem.md:19`）。`think` 等待期間快模型一直叫 `thoughts_list`、不會安靜等（`play/2026-09-06-think.md:44`、`:52`）。
- **缺一個每格都會叫的 `on_tick(ctx)`**：逾時只能等到下一個 idle／工具／回話的格才被發現（`play/2026-09-06-think.md:51`）。`on_idle` 看不到中間的 llm／wait／act 格，`review` 包只好用 `step` 相不相連反推「連續 3 格 idle」（`play/2026-09-06-review.md:6`、`play/2026-09-06-cost.md:6`）。
- **沒有「等齊了再叫我」的集合等待**：`branch` 的 `join` 第一次只收到 2/3 條（共用引擎並發 2），要靠模型自己下一輪再叫一次（`play/2026-09-06-branch.md:13`、`:19`）。
- 等待被實作成「反覆叫 LLM 的忙輪詢」，**等待成本直接變成錢**：4b 的 PM 26 輪有 16 輪在讀信等信；4c 的 sales 27 輪有 24 輪困在開頭編單號的迴圈（`play/2026-09-07-studio-4.md:16`、`:20`）。

### 缺口二：**引擎接口層沒有自己的位置，協定修補塞進 agent 狀態機**

4. **把工具呼叫寫成文字要救回來**：`TOOL_CALL_SMELL`、`_json_objects`、`_balanced_object`、`NAMED_OBJECT`、`named_tool_objects`、`salvage_tool_calls` ——**共約 100 行、5 個函式，佔 `aos-agent` 六分之一**（`aos-agent:25`、74-170、274-295）。三種花樣分三次加：`<tool_call>`／純 JSON（`cfffb2b`）、` ```plaintext 裡「工具名: {參數}」`（`13f03bf`）。
5. **救不回來就同題重送**：`protocol_retries`（`aos-agent:289-295`）。
   → 4、5 補的是：模型輸出的正規化應該在「引擎那一側」（`aos-llm` 的 `strip_think` 就在對的地方），卻做在 agent 裡，因為 agent 才知道自己有哪些工具（`known` 集合，`aos-agent:274`）。**「有哪些工具」這件事沒有下傳到引擎層。**
6. **claude-cli 六條坑全在接口層**（`journey:144-158`、`docs/llm-scheduling.md:110-181`）：`.aos/inst` 沒放、PATH 沒有 `claude`、`--append-system-prompt` 帶著 Claude Code 兩萬 token 身份、`--safe-mode` 連 MCP 一起關、stream 事件要照 `message.id` 合併、haiku 直接發真的 tool_use。
   → 使用者自己的結論是「**分層是對的**，流程層一行沒動」（`journey:162`、`journey:195`）。**這一條是 proto2 做對的地方，但接口的形狀還沒被抽出來當介面**——四種引擎的翻譯碼（`to_anthropic` 82 行、`from_claude_cli` 73 行、`codex_run` 79 行）直接長在 `aos-llm` 這支 1793 行的檔案裡。
7. **worker 打 HTTP 前先探 TCP 10 秒**（commit `cfffb2b`；`journey:24`）：公司 WSL 對關掉的埠會吞 SYN。
7b. **「成功但空」沒有被當成失敗**：模型把工具呼叫吐成殘缺文字（夾雜 `EDIATEK`），HTTP 200、內容非空，agent 當普通回覆送走，不算 error、不重試 ── **B、C 兩局都斷在這一點**（`play/2026-09-07-studio-2.md:31`、`:60`、`play/2026-09-07-studio-3.md:25`）。spawn 時模型回空字串，outbox content 是空的、agent 沒擋也沒補送（`play/2026-09-06-whole-system.md:90`）；`think` 把整個輸出額度吃在 reasoning、最後沒有 content（`play/2026-09-06-think.md:46`，5999 completion token 全是 reasoning）。
   → 補的是：**沒有「協定錯誤」這一態**。只有 HTTP 成功／失敗兩種，所以「回來了但沒用」無處可歸。

### 缺口三：**「格」這個單位沒分清楚「做事／等待／凍住」**

8. **`ticks` 只算 busy 格**（`aos-agent:563-564`、`team_status_of` 讀 `state["busy"]`，`aos_agent.py:695`；`cfffb2b`）——idle 空轉會穿透整隊上限（`play/2026-09-06-studio-2.md`：458/300）。
9. **`question_steps` vs `question_sleep_steps`**（`aos-agent:565-572`）：睡著等旁線、排隊等模型、出錯後等重送都不算「每題動作格」。這條分兩次補（`e938d6c` 一次、`7a2d26a` 15:20 4d 又一次）。
   → 8、9 補的是同一件事，補在**兩個不同的地方**（一個給整隊預算看、一個給每題上限看）。而 `question_sleep_steps` 只被寫、只被顯示（`aos-user:519`、`aos_agent.py:436`），從來沒被判過——它存在只是為了證明「這些格沒被算進去」。
   實玩證據：慢分支會先撞 60 格硬上限、再等使用者說「繼續」（`play/2026-09-06-simplify.md:21`、`:27`，已修於 `play/2026-09-07-simplify-2.md:8`）；`register_clock` 沒有 `no_wait` 時最差等十秒，jobs 把「等 daemon 開鐘」也算進使用者的秒數（`sleep 15` 記成 16 秒，`play/2026-09-06-jobs.md:6`、`:19`）。
9b. **`step` 同時是時間軸又是計數單位**：三個工具在同一格一起跑，ledger 三行 `step` 相同——「格數」跟「呼叫次數」不能混著看（`play/2026-09-06-review.md:37`）。

### 缺口四：**資源上限沒有一致的「誰檢查、誰解除」**

10. **`budget_block` 每格都守**（`aos-agent:378-457`，80 行，是第二長的函式）。裡面疊了六層特例：0 額度＝0 上限、沒事做的人安靜凍著、`budget_told` 只喊一次、每 300 格再喊、每 10 格重試自動撥款、`has_work` 判定要看 `state not in ("idle","stuck")`（`aos-agent:430`）。
11. **`auto_grant`**：閘門自己撥錢、不叫模型（`aos_agent.py:735-780`；`36fde5f`）——因為「撥一次額度 4 輪 ≈ 35k token，而且小模型常把 grant 寫成文字沒真的做」（`studio-efficiency:16`）。
12. **池子乾了替 sales 喊甲方**：`budget_block` 裡直接 `Ctx(sales_world, ...).reply(...)`（`aos-agent:448-456`）——**在自己的閘門裡建別人的 Ctx、替別人說話**。
    → 補的是：agent 沒有「代表另一個 agent 發話」的合法途徑，也沒有「整隊層級的事件」這種東西。
13. **`team_status_of` 每格每人都跑一次**（`aos-agent:383`）：讀整份名冊、每個成員的 `state.json`、整本當日 usage 帳本（`aos_agent.py:658-732`）。八個人＝每秒 64 次檔案掃描。`light=True` 只省掉「量資料夾大小」那一段。
    → 補的是：沒有增量的帳，只有全量重算。而且 `team status` 的 ticks 彙總在併發讀寫下曾**從 6,895 倒退成 5,724 下一次又跳回**（`play/2026-09-07-studio-3.md:20`）——跨世界彙總沒有一致性快照，不能當單調計數器。

**實玩紀錄裡另外三條，proto2 到現在都還沒補：**

13b. **在途的請求追不回**：owner 額度 6,000 直接超到 10,038（67.3%），因為 `max_concurrent=2` 時連續兩筆已經送出去了（`play/2026-09-07-studio-2.md:49`、`:59`）；09-06 那局燒到 120 萬 token 才由人收隊（`play/2026-09-06-studio.md:95`）。
     → 缺口：**沒有預扣（reserve）也沒有取消**。超支的上界＝並發數 × 單筆成本，永遠關不掉。
13c. **閘門原本只守在「正要送 LLM」那一點**，全員 idle 時沒人走到檢查點，帳面從 373 一路漲到 458 才人工 stop（`play/2026-09-07-studio-2.md:50`、`:51`、`:57`）。這才是後來改成「每格都守」（`aos-agent:494`）的由來。
13d. **0 的語意沒定義**：`sales` 的 allocation 是 0，但程式只在 `limit > 0` 時判超額，所以它照樣用了 7,011 tokens ——「尚未分配」被當成「不設限」（`play/2026-09-07-studio-2.md:52`、`:58`，C 局重現於 `play/2026-09-07-studio-3.md:8`）。未設定／無限／禁止三種意思共用一個 `0`。
13e. **引擎沒寫 `price` 時，所有以錢為單位的閘門全體失能**：`cost` 與 `money` 一路 `null`／0（`play/2026-09-06-cost.md:15`、`play/2026-09-06-branch.md:21`、`play/2026-09-06-review.md:34`、`play/2026-09-06-studio.md:9`）。成本模型是選填的，建在流沙上。
13f. **兩本帳口徑不同**：chief 看自己的 ledger 說沒超支，`team status` 才看到全隊已爆（`play/2026-09-06-studio.md:81`、`:96`）；`today_usage` 只取目前 endpoint、名字卻像全日總數，換 engine 後漏算 61,758（`play/2026-09-06-whole-system.md:91`）。

### 缺口五：**共用狀態沒有交易**

14. **`team_lock()` flock**（`aos_agent.py:483-534`；commit `a5cbb30`；`journey:135`）：實測 8 進程各撥 20 次，有鎖 160 筆一筆不掉，沒鎖只剩 23 筆、還把 `budget.json` 寫壞（`write_json_atomic` 的暫存檔名固定會互踩）。
    → 但 `proto2/README.md:282` 到現在還寫著「**目前刻意不做：鎖、fsync、重試**」。**文件與程式已經對不上了**，而且鎖只加在 `team/` 這一層；`prompts.json`、`state.json`、專案檔那層還是靠約定（`journey:111`、`journey:126`）。

**同一個骨幹缺口在六個工具包裡的影子**——`fs`／`code`／`cost`／`review`／`toolsmith`／`selfmem` 各自在自己的紀錄裡報告「沒有鎖，兩個 agent 同時改會互蓋」（`play/2026-09-06-fs.md:44`、`play/2026-09-06-code.md:42`、`play/2026-09-06-cost.md:41`、`play/2026-09-06-review.md:61`、`play/2026-09-06-toolsmith.md:46`、`play/2026-09-06-selfmem.md:53`）。骨幹沒做，於是每個包都痛一次。另外：

14b. **`Ctx` 自己提供的接點就是無鎖的 read-modify-write**：`ctx.contacts()`／`ctx.kids()` 都是整份 JSON 讀出改完寫回，人多時又慢又會掉（`play/2026-09-06-hooks.md:45`）。
14c. **沒有唯一 ID 產生器**：信檔名是時間戳到微秒，同一微秒寄兩封仍會撞（`play/2026-09-06-hooks.md:46`、`play/2026-09-06-communication.md:44`）。而且沒有「先取得 ID 再寫入」的兩段式建立——首封信的 `thread` 要等於檔名，只好先寄再原子補寫（`play/2026-09-06-communication.md:5`、`:27`）。
14d. **沒有 crash-safe 的寫入原語，也沒有一次性語意**：jobs 的結果檔和信不是原子寫，斷電會留半個 JSON；鐘在 `result.json` 寫出前死掉，指令之後會**從頭再跑一次**（`play/2026-09-06-jobs.md:39`、`:41`）。骨幹只提供 `ctx.write_json`（`play/2026-09-06-hooks.md:27`）。
14e. **`pending` 與 `state` 到現在還是沒鎖**，多個時鐘同推一個 agent 就會互蓋（`play/2026-09-07-simplify-2.md:28`、`play/2026-09-06-think.md:75`、`play/2026-09-06-branch.md:41`）——「一個世界只有一個推它的人」是**假設，不是保證**。
14f. daemon 側也有一個：`env_from` 的 600 權限檢查與真正開檔之間有空窗（TOCTOU，`play/2026-09-06-identity.md:62`）。

### 缺口六：**世界沒有型別、路徑沒有統一解析**

15. **`aos-loop` 看到 `engines.json` 卻沒 `.aos/inst` 就自己補一句 `aos-llm exec .`**（`aos-loop:39-44`；`7a2d26a`；`journey:148`）。
    → 補的是：「這是不是一個 LLM 資料夾」靠猜（`README.md:151`：「有沒有 `engines.json` 就是這是不是一個 LLM 資料夾」）。**世界的型別沒有第一級表示。**
16. **`_run_cmd` 把開頭的 `team/` 翻成 `../../`**（`packs/studio.py`；`journey:156`）——因為指令在專案目錄跑、路徑卻寫成從隊根算的。
17. **`code` 包擋「路徑跑到專案外」，但成員家裡的 `team/` 是 symlink**（`journey:37`，12:01 4b）→ 「共用區也算裡面」。
    → 15～17 補的是同一件事：**world／home／專案目錄／隊根／通訊錄別名是五種基準，沒有一個地方統一解析。**`play/README.md:39`、`play/README.md:72` 都點名這條。

**實玩紀錄裡這一族踩了至少八次：**

17b. `llm.json` 的 `dir` 被作者算成相對 home（實際相對世界），**請求投到沒有鐘的資料夾，等滿 60 格才回逾時**（`play/2026-09-06-toolsmith.md:21`）。
17c. `kids` 的 shared 小孩在父的 home 底下，但要改的是父 **world** 的 `.aos/inst`，inst 裡的路徑要從 world 算不能從 home 算（`play/2026-09-06-kids.md:8`）。
17d. `--env-from` 命令列會轉絕對路徑，直接寫進 JSON 的相對路徑卻由 kernel 的工作目錄解讀——**同一個欄位兩條路兩種基準**（`play/2026-09-06-identity.md:7`）。
17e. **別名與路徑是同一個型別**：`put_mail(target, ...)` 同時吃名字和路徑，作者自評最不簡（`play/2026-09-06-hooks.md:33`）；通訊錄別名跟世界資料夾名不同時，信寄得出去，對方照信上的 `from` 回覆卻找不到人（B 第一次 `mail_reply` 就失敗，`play/2026-09-06-communication.md:14-15`、`:20`、`:34`），而且**缺「用世界路徑反查通訊錄名字」的接點**（`:28`）。
17f. **`~`（使用者）不在通訊錄模型裡**：`communication` 包只好在讀通訊錄時自己補一個 `user`（`play/2026-09-06-communication.md:8`）。這正是構想 11 章「通訊錄天然有一格 `~`」（`vs:98`）。
17g. **身分靠絕對路徑固定，不可搬遷**：世界搬家後 contacts／parent／kids 的絕對路徑不會自動修（`play/2026-09-06-hooks.md:47`）。
17h. **「我是誰／我在誰底下」由各包各自推導**：PM 曾被誤認成 owner，第一筆 `team_grant` 從 owner 的救急額度扣（`play/2026-09-06-studio.md:93`）；`kids` 要沿 `parent.json` 往上數才知道自己的深度（`play/2026-09-06-kids.md:6`、`:39`）。
17i. **沒有「共用區」的定址概念**：studio 成員把 `team/projects` 解成自己家的資料夾，PM 連兩次 `ls` 失敗，只好給每個孩子一個 symlink 指回根共用區（`play/2026-09-06-studio.md:92`）——然後 symlink 又害 `code` 包判定「跑到專案外」（(b) 第 17 條）。
17j. **路徑沒有沙箱**：`../`、絕對路徑、symlink 都可能走出世界（`play/2026-09-06-fs.md:46`、`play/2026-09-06-code.md:42`、`play/2026-09-06-newagent.md:44`）；`code` 包想要 `project_path()`／`undo_dir()` 但 `Ctx` 沒有（`play/2026-09-06-code.md:5`、`:25-26`）。

### 缺口七：**非同步結果沒有單一主人 ／ 失敗三態只做了一半**

18. **worker died 的三段判斷**（`aos-llm:428-478`）：只有 pid、完成標記、結果檔三個都不在才算死在半路；還特別加了一條「看到結果但 worker 還活著時先不搶著收」（`aos-llm:437-441`）。
    → 補的是：`play/2026-09-06-whole-system.md` 實撞的「結果所有權競速：agent 拿走結果，LLM 又補 worker died、灌水用量」（`play/README.md:110`）。
19. **失敗三態（還沒好／好了／壞了）只在 LLM 那條線落地**（`notes/2026-09-06-ideas-vs-proto2.md:54`、`:126`）：工具、小孩、job 那三條沒有。小孩的鐘死了父只能靠信箱猜；job 死在結果落盤前就整個重跑（`play/2026-09-06-jobs.md:39`、`:41`）。

**實玩紀錄的其他證據：**

19b. **「排隊中／沒人做／失敗」全部長成同一種「一直沒回」**：拔掉 LLM 的鐘後送一句，`aos-llm ls` 清楚顯示 1 個 queued，但聊天端**沒有任何提示**，agent 卡在 `wait`（`play/2026-09-06-whole-system.md:71-72`，作者列為第二想修：`:113`）。LM Studio 沒起來時 agent 從 wait 回 idle，outbox 也沒有錯誤（`play/2026-09-06-whole-system.md:89`）。
     → 已修一半：旁線的缺鐘改回 `no_clock`、不再假裝成 timeout（`play/2026-09-07-simplify-2.md:9`、`:22`）；**主線還沒有**，主線仍是格數逾時（`aos-agent:18`），而旁線已改成牆上時間（`play/2026-09-07-simplify-2.md:26`）——**逾時基準兩套，骨幹自己都沒統一**。
19c. **逾時之後的孤兒結果不回收**：晚到的主線超時結果會留在 LLM `results/`，現在不清（`play/2026-09-06-hooks.md:48`）。
19d. **主線與旁線的掛勾不對稱**：旁線有 `on_result`，主線本來沒有，`cost` 包只能靠下一個 `on_act`／`on_reply`／`on_idle` 用 `last_usage` 補帳（`play/2026-09-06-cost.md:5`、`:25`）。後來補了 `on_main_result`（`aos-agent:39-48`），但那也是補丁。
19e. **結果進入對話的那一刻沒有攔截點**：`bigmem` 想在旁線結果寫進 `prompts.json` 前替換掉它，只能先存檔、下一輪 `on_system_prompt` 再換（`play/2026-09-06-bigmem.md:6`、`:24`、`:27`）。`branch` 的 `adopt` 改完 `prompts.json` 後，共用的 `act` 還是會追加舊主線的工具結果，只好再用 `on_system_prompt` 清掉（`play/2026-09-06-branch.md:6`、`:26`）。
19f. **旁線結果的路由靠慣例不靠型別**：pending 要自己記 pack 名再載回同一包，作者自評「最繞的地方」（`play/2026-09-06-hooks.md:22`、`:39`）；`on_result` 出錯時只能退回「寄到自己的 `inbox/<kind>/`」以免結果丟掉（`play/2026-09-06-hooks.md:15`）。

### 缺口八：**state.json 是一個沒有命名空間的公共抽屜**

20. 現在有 **44 個鍵**，其中至少 13 個是工具包直接塞的（`studio_nag_step`、`studio_nag_count`、`review`、`branch_depth`、`branch_adopt_cleanup`、`adopted_branch`、`ref_meta`、`pending_ledger`、`pending_summary`、`reminder_open`、`nudged_at_step`、`last_review_*`、`idle_streak`）。
    → 骨幹和工具包共用同一份可變狀態，誰洗掉誰的沒有人擋。`ctx.state` 原本是函式，因為新包需要直接改同一份 dict 才改成屬性；**一個掛勾改另一包的 state 欄位完全沒有隔離，只靠「各包守名字前綴」的約定**（`play/2026-09-06-hooks.md:6`、`:23`、`:49`）。

20b. **同一件事在別的內部檔上也發生**：`kids` 包直接讀 `$AOS_DAEMON_DIR/clocks/*.json` 看 own 鐘有沒有 paused，因為沒有查 daemon 鐘狀態的接點（`play/2026-09-06-kids.md:7`、`:40`）；`parent.json` 沒有 clock 欄，`self_who` 只好去讀父世界的 `.aos/inst` 判斷是不是 shared（`play/2026-09-06-selfmem.md:7`、`:35`）。
20c. **`.aos/inst` 變成事實上的擴充點**：jobs 的完成器只能塞成 inst 第三行的一長串 Python，因為不准新增 `aos-agent job-finish` 子命令（`play/2026-09-06-jobs.md:5`、`:33`）；`kids` 的 pause／resume／kill 是去**編輯父的 inst 文字**（註解掉那行／移掉那行，`play/2026-09-06-kids.md:8`、`:26-28`）。**生命週期控制沒有 API，只有編輯文字檔。**
20d. **信箱投遞沒有對外接點**：`aos-mcp` 想投一封信只能自己解析 `--home` 再原子寫一個 JSON 檔（`play/2026-09-06-mcp.md:7`、`:26`）。
20e. **`Ctx` 連寫文字檔的把手都沒有**，`toolsmith` 的 pack 骨架只好用自己的 `open()`（`play/2026-09-06-toolsmith.md:6`）；到 4d 還缺共用的 `ctx.sh` 與工具執行前的掛勾（`play/2026-09-07-studio-4.md:36`）。

### 缺口九：**介面殼與底層混在一起**（使用者自己說要分，還沒分）

21. `aos_agent.py` 這支「共用層」裡有 `create_team_world`（106 行）、`team_status_of`（75 行）、`team_auto_grant`、`team_add_budget`——**整套工作室建隊與預算邏輯**。`aos-user` 又有 `do_team_new`／`do_team_why`／`do_team_tail`／`do_team_stop`。
    → 使用者續一原話：「後續會把使用界面和底層運行機制分開，目前粗糙原型先這樣」（`notes/2026-09-06-world-clock-agent.md:37`）。`ideas-vs-proto2.md:68` 也記著「沒有分圈」。

### 缺口十：**省 token 的兩個開關是後貼上去的**

22. **`tools.json` 的 `only` 白名單**（`aos_agent.py:92-98`＋`tool_specs` 的 `only` 參數 `aos_agent.py:186-189`；`36fde5f`）：PM schema 13,439 → 2,827 字。
23. **`inline_mail`**（`aos_agent.py:99-109`＋`scan_inbox:308-319`）：列到的來源整封信直接進 prompt，不用再花 2～3 輪去讀。
    → 補的是：**工具表與信箱都是「全給」的預設**，沒有「這一輪這個角色需要看到什麼」的概念。這兩條省下的是最大宗的浪費（見 (d)）。

### 缺口十一：**同名工具誰贏，是清單順序的副作用**

24. 共用載入器永遠讓 `tools.json` 先列的包贏（`aos_agent.py:167-171` 只印一句警告就跳過）。`fs` 和 `shell` 同時列時，**只有把 `fs` 放前面 `sh` 才會由 `fs` 接手**，單靠 `fs` 包無法保證（`play/2026-09-06-fs.md:51`）。自製工具撞到包裡的同名工具時，**包裡的會贏**——使用者自己的東西輸給系統的（`play/2026-09-06-toolsmith.md:49`）。
    → 缺口：沒有「指定誰優先」的接點，衝突解決規則既不可設定也不一致。而且**這一格已載入的工具清單不會變**，`tool_try` 必須自己再讀一次 `tools.json` 才能當格試跑（`play/2026-09-06-toolsmith.md:7`）。

### 缺口十二：**沒有「當前任務／回合」這個一等公民**

25. `on_act` 拿不到任務編號或 tag，`review` 包想算「同類任務平均兩倍」只能在 ledger 已經有 `task_key`／`task_id` 時才算得出來（`play/2026-09-06-review.md:5`、`:41`）；缺「上次任務開始格」的接點，模型只好自己猜 `n_steps`，實玩就猜成 8、看不到稍早的 ledger（`play/2026-09-06-review.md:33`、`:42`）。
    → 缺口：**所有跨格的歸因（花了多少、繞了幾輪、這題有沒有進展）都得靠猜。** 這也是 (b) 缺口一那個「死路偵測」判斷不出來的根因：沒有「這一題」的邊界，就沒有「這一題沒有前進」。

### 缺口十三：**啟動、註冊、成對開鐘全是競速**

26. **kernel start 沒有「就緒」語意**：start 成功後立刻 register 卻說「kernel 沒在跑，請求先放著」，下一格其實成功了（`play/2026-09-06-whole-system.md:40`、`:87`，作者列第三想修 `:114`；已修 `:118`——現在 `cmd_start` 會等到 pid 真的活著且第一格跑完，最多 5 秒，`README.md:217`）。
27. **`ls` 在 kernel 停掉後仍印舊 pid**，第一次看會以為它還活著（`play/2026-09-06-whole-system.md:99`、`README.md:232`）。
28. **註冊參數必須自己持久化**：只在 register 時套環境不夠，鐘死掉或 kernel 重開時要拿回同一份設定，所以 `env`／`env_keep`／`env_from` 得存進時鐘檔（`play/2026-09-06-identity.md:6`）——重啟不是冪等的，要靠額外落檔補。
29. **沒有「成對開鐘」的原子操作**：agent 與 LLM 是兩個世界，要走完一段必須兩邊各 register 一次，**忘一顆就只表現成「一直沒回」**（`play/2026-09-06-mcp.md:5`、`:31`、`play/README.md:37`）。
30. **多步建立沒有交易語意**：spawn 是「先生，再補名冊與第一封信」，中間失敗孩子已經存在、不回滾（`play/2026-09-06-kids.md:56`）；根因是 `ctx.spawn` 沒有 `packs`／`task` 參數（`play/2026-09-06-kids.md:5`、`:38`），**API 參數不足 → 半成品狀態必然存在**。
31. **名冊與實況沒有一致性保證**：`kids_list` 仍列名冊但不回 `alive`，看最後 state 會誤以為它還活著（`play/2026-09-06-kids.md:48`、`:61`）；「有哪些孩子」有資料夾與 `kids.json` **兩個真相來源**（`play/2026-09-06-hooks.md:8`）。父死掉之後的孤兒鐘不處理（`play/2026-09-06-kids.md:61`）。
32. **骨幹能力被誤放在可選工具包裡**：子身分提示與回話轉寄原本綁在 `kids` 包，coder 模板沒載這包整條就不通，後來才搬進共用層（`play/2026-09-06-integration.md:19`）；kid 一度只能用 `fs.write` 直接寫父的信箱（`:15`）。模板與繼承的優先權也沒定義：`spawn(template="coder")` 沒明給 `packs` 時舊實作仍抄父的，模板看似載入、能力卻被蓋掉（`play/2026-09-06-integration.md:6`、`:13`）。
33. **進程／世界沒有可辨識的歸屬標記**：測試把所有名字像 aos 的進程都當殘留，會誤傷正在工作的鐘（`play/2026-09-06-hooks.md:5`、`play/2026-09-06-code.md:7`）；shared 小孩跟父共用同一份 clock log，行上沒有名字（`play/2026-09-06-whole-system.md:98`）。

### 缺口十四：**欄位沒有正本（構想 L-03 拍板過，proto2 沒做）**

34. 已經出現的兩套說法：
    - **`requester`**：排程規格放在 `priority` 裡、計費規格要在請求頂層，實作只好兩邊都讀（`play/2026-09-06-sched.md:5`、`:30`，作者自評最不簡）；而且舊 agent 根本沒傳，只能用**請求檔名前綴**備援（`:7`、`:25`）——正是 `play/2026-09-06-hooks.md:22` 明令禁止的做法。`requester` 還可冒名，這輪照規格故意不防（`:41`）。
    - **token 欄位名**：`self` 規格寫 `in`／`out`，T-06 拍板寫 `input`／`output`／`reasoning`／`cached`（`play/2026-09-06-selfmem.md:8`）。
    - **截斷長度**：`fs` 草稿寫兩邊各截 4000 字，code-editing 拍板寫最後 1500 字（`play/2026-09-06-fs.md:5`）；`agent_status` 真的被截到 4000 字（`play/2026-09-06-mcp.md:21`）。
    - **`contacts.json` 兩種值型別**（純路徑字串 vs 帶 `dir`／`relation` 的物件），讀取端兩種都要吃（`play/2026-09-06-communication.md:7`、`play/2026-09-06-hooks.md:12`）。
    - **同一實體兩個參數名**：`thought_read` 叫 `id`、`conclude` 叫 `thought_id`（`play/2026-09-06-think.md:60`）。
    - **用量檔格式沒有版本標記**：`test.sh` 的舊用量測試直接索引平鋪鍵，跟已拍板的兩層新格式打架（`play/2026-09-06-sched.md:8`）。
    - **設定檔沒有 schema**：`review` 自己往 `llm.json` 塞 `review.daily_cost`／`review.tool_cost`（`play/2026-09-06-review.md:7`）。
    - **「有效設定」沒有共用解析**：`think`／`cost`／`self` 三包各抄一份「讀 agent 的 `llm.json` ＋ LLM 的 `defaults.json` ＋ `engines.json` 才知道會用哪台引擎」（`play/2026-09-06-think.md:6`、`play/2026-09-06-cost.md:7`、`play/2026-09-06-sched.md:6`）。
    - **工具結果沒有結構化的成功／錯誤種類**：`on_act` 只拿到解析後的 args，看不到模型的原字串，也看不出自訂 shell 工具的退出碼（`play/2026-09-06-cost.md:8`、`:26`）。

---

## (c) 構想 13 章：proto2 刻意沒做、或做反了

出處統一是 `proto2/notes/2026-09-06-ideas-vs-proto2.md`（下稱 vs），章節對照 `wf/workflows/ideas/README.md:13-25`。

| 章 | proto2 的處置（一句） | 裁定狀態 |
|---|---|---|
| 01 可預測性的兩把尺（A-04） | 錢量了、**可預測性一把尺都沒有**（沒有固定題、沒有跑幾次看分布）。 | **懸著**（vs:14、vs:89、vs:130） |
| 02 `.aos/` 是機器的地盤、人不碰 | 拿掉了：`.aos/` 只剩一句 `inst`，其他平鋪在本體。 | **使用者已裁定不做**（續四原話，vs:19、`world-clock-agent.md:81`） |
| 03 `aos mv`、搬家後路徑自修（C-04） | 沒做；搬家後 contacts／parent／kids 的絕對路徑不會自己修。 | **懸著**（vs:24、vs:91、`play/README.md:120`） |
| 03 git 快照、`.gitignore` 全域規範 | 沒動。 | **使用者已裁定不做**（「先不管 git」，vs:24） |
| 04 json 指令批、批內沒資料流 | 全部不要，換成一句 shell 的 `.aos/inst` 丟 `os.system()`。 | **使用者已裁定不做**（README「目前刻意不做：批次結構」，`README.md:282`；vs:29、vs:140） |
| 05 寫→編譯→拆平→接力棒、兩種壽命 | **整章不要**。沒有編譯、沒有 `series.json`，agent 沒有「跑完」，靠 idle 空轉。 | **使用者已裁定不做**（「太早考慮邊緣狀況」，vs:34、vs:141） |
| 06 一格有預算、限 PATH 而不是 timeout | 一格有界靠 `sh` 60 秒硬砍（`aos_agent.py:27`），沒有限 PATH（反而**自動把工具目錄加進 PATH**，`aos-exec:94`）；一格預算沒有。 | **懸著**（vs:39、vs:132） |
| 06 「有變動才動」的門鈴（F-03） | 沒有，全是固定 interval 輪詢（預設 1 秒一格）。 | **懸著**（vs:39、vs:94） |
| 06 tick 內卡住怎麼辦 | 只有 `sh` 60 秒硬砍。使用者原話「再想想吧」。 | **懸著**（`world-clock-agent.md:19`、vs:79） |
| 07 daemon | **做得比構想好**，還多了構想沒有的 `pause`（SIGSTOP）。 | ——（vs:41-44） |
| 07 kernel 被 SIGKILL 時鐘變孤兒 | 沒處理。 | **懸著**（vs:44、vs:84） |
| 08 agent 硬上限：格數／呼叫數／token（H-03 已拍板） | 做了一半：`max_steps_per_question`（預設 60）與 `max_tokens_per_day`（`aos_agent.py:448-460`）；**呼叫數沒有**。 | **懸著**（vs:49、vs:90、vs:128、vs:159） |
| 08 「停不是死、有信再醒」、agent 沒事時真的睡 | 反過來：agent **從不睡**，每格都掃一次信箱。 | **懸著**，但使用者傾向先不拉（「一秒一格便宜」，vs:133） |
| 09 失敗三態（還沒好／好了／壞了）（I-02 拍板） | **只在 LLM 那條線落地**；工具、小孩、job 三條沒有。 | **懸著，且筆記自己說「要拉回」**（vs:54、vs:126、vs:92） |
| 09 env 預設不繼承（I-07 拍板） | 已修：`legacy_env` 預設 `false`（`docs/identity-and-env.md:35`）——**但 `ideas-vs-proto2.md:127` 還寫著預設 true，文件之間不一致**。 | **已解，文件待對齊** |
| 09 `footprint.writes` 相交就整格拒跑（I-08） | 沒有。 | **懸著**（vs:141「推翻 09 章整章」） |
| 10 門房（tmpfs → inotify → FUSE） | 完全沒有。`chattr +i` 停在發想（T-27）。 | **使用者已裁定「何時做未定」**（vs:59、vs:96） |
| 11 工具登記表是行為契約、描述帶「代價」（慢／貴／不確定） | 沒了。直接走後端原生 `tool_calls`；慢工具靠模型自己選 `run_long`。叫錯工具只回一句字串。 | **懸著**（vs:64、vs:95） |
| 11 通訊錄天然有一格 `~` | 沒有。 | **懸著**（vs:98） |
| 12 核心分圈、一份正本規範、版面歸屬表 | 沒有分圈、沒有正本；欄位已經出現兩套說法（requester、token 名、截斷長度）。 | **使用者已裁定「先這樣」**（續一），但**筆記說「要拉回一半」**（vs:69、vs:131） |
| 12 介面與底層分開 | 還混著（見 (b) 缺口九）。 | **懸著**（使用者明說要，vs:80） |
| 13 三支串各跑五次、二十幾支重現腳本 | 沒做。play note 有 24 份，但**沒有一條回頭對到 13 章的洞**。 | **懸著**（vs:74） |
| 額外：使用者本人變成一個 agent | 還是殼＋`inbox/user` 短路。 | **懸著**（使用者明說要，vs:81、`world-clock-agent.md:95`） |
| 額外：新鐘／新 agent 設身份與權限 | `user` 欄要 root 才有效，identity 停在建議稿。 | **懸著**（vs:82） |
| 額外：子 agent 自動繼承 `spawn`、孫子還能生 | 深度限 2 層（T-16），但繼承沒擋。 | **使用者說「之後再說」**（`wf/WAIT_USER.md:28` A-6） |

---

## (d) 效能面：token 帳從哪裡漏，骨幹層可以怎麼收

### 量出來的數字（4b 局，`notes/2026-09-07-studio-efficiency.md:7-18`）

| 角色 | LLM 輪 | 平均一輪 prompt | 工具數 | schema 字數 | 真正在做事 |
|---|---:|---:|---:|---:|---|
| pm | 26 | 8,176 | 50 | 13,439 | 5 輪派工；**16 輪只在讀信／等信**；4 輪撥額度 |
| chief | 21 | 8,776 | 64 | 17,895 | 12 輪寫改檔 |
| owner | 11 | 5,707 | 47 | 12,579 | **0**（全在讀信、6 次讀錯 id） |
| sales | 3 | 3,498 | 32 | 7,862 | 1 輪轉信、1 輪回甲方 |

### 七個漏水口

1. **prompt 佔 96% 的 token，回答只佔 4%**（`studio-efficiency:14`、`journey:215`）。優化的槓桿全在送出去那一側。
2. **工具表佔 prompt 一半以上**。骨幹每格都把載入的所有包的 `TOOLS` 攤平送出（`tool_specs`，`aos_agent.py:160-189`）。
   → **已收：`only` 白名單**，PM 13,439 → 2,827 字（`lessons:21`）。但這是後貼的開關（不寫＝全送），而且是**靜態**的：一個角色一份清單，不會隨當下在做什麼變。
3. **對話史整檔重送**。`do_llm` 每格把 `prompts.json` 整份讀出來當 messages（`aos-agent:57-58`）。haiku 的 dev-a 一輪從 10k 漲到 20k、21 輪吃掉 325k（`journey:172`、`journey:183`），原因是 `write` 整檔進了對話史又每輪重送。
   → **還沒收**。`memory` 包有摘要工具（`docs/memory.md:20-25`），但那是**要模型自己想到去叫**，不是骨幹的策略。使用者已把「dev 每個任務開新對話史」列成待決定（`wf/WAIT_USER.md:35`）。
4. **讀一封信 2～3 輪 ≈ 20k**（通知 → `inbox_list` → `inbox_read`）。撥一次額度 4 輪 ≈ 35k。
   → **已收**：`inline_mail`（信整封直接進 prompt，`aos_agent.py:308-319`）＋ `auto_grant`（閘門自己撥、不叫模型，`aos_agent.py:735`）。4c 實測讀信 0 輪、撥款 0 輪，PM 一輪 prompt 從 8k 降到 3k（`journey:86`）。
5. **cache 計價：帳面不等於成本**。claude-cli／anthropic 的 `prompt_tokens` 把 `cache_read` 折進去（`docs/llm-scheduling.md:93-95`），真實價格約 1/10。4d 帳面 841k **一半以上是 cache**（`journey:217`）。
   → 而預算閘門吃的就是這個灌水過的數字：`team_status_of` 直接拿 `used["total_tokens"]`（`aos_agent.py:693-696`），`hard_limit` 也是（`aos-agent:466`）。結果是天花板被 cache 撐爆、人一直被凍住、`auto_grant` 一直重試。**這一條還沒決定要不要打折（`wf/WAIT_USER.md:34`）。**
6. **reasoning 是看不見的支出**。要求只回一句，模型仍可能把整個輸出額度花在 reasoning：`think` 實測 5999 completion token **全是 reasoning、正文空的**（`play/2026-09-06-think.md:20-22`）；`whole-system` 一發 1,177 tokens 裡 1,154 是 reasoning（`play/2026-09-06-whole-system.md:78`）。短 prompt 不代表便宜（`play/2026-09-06-sched.md:20`）。帳本有把巢狀 usage 攤平成 `completion_tokens_details.reasoning_tokens`（`README.md:191-193`），但**閘門沒有針對它的策略**。
7. **成本模型是選填的**：引擎沒寫 `price` 時 `cost`／`money` 一路是 `null`／0，所有以錢為單位的閘門一起失能（見 (b) 13e）。

### 骨幹層可以怎麼收（設計方向）

- **把「這一輪送什麼」變成骨幹的職責，不是模型的自覺。** 一輪的 prompt ＝ 人格 ＋ (動態選出的工具子集) ＋ (壓過的對話史) ＋ (當下相關的信與狀態)。proto2 只有第一項是骨幹決定的。
- **對話史要有分段壽命**：任務級（做完就清）／會話級／長期。`WAIT_USER 12` 問的就是這個，答案應該是骨幹的預設而不是每個包各做一套（`bigmem`／`memory`／`branch`／`ref` 現在各改各的 `prompts.json`）。
- **工具清單要能隨狀態變**：`on_system_prompt` 這個掛勾已經有了（`docs/packs-api.md:112`），但工具表沒有對應的 `on_tools`。工作室裡「PM 現在只需要 `task_assign`」是可以從單子狀態算出來的。
- **帳要分兩欄：帳面 token 與計價 token**。`prompt_tokens_details.cached_tokens` 已經留著了（`docs/llm-scheduling.md:95`），閘門改吃 `prompt − cached + completion` 是幾行的事——只差一句拍板。
- **usage 帳本要能增量讀**。現在每格每人重讀整本（(b) 缺口四第 13 條）。
- **工具 schema 本身也該收**：`(d)` 那輪已經把 16 包的描述砍半（commit `aafd19e`），但 schema 是每包自己寫的字串，骨幹沒有預算概念。
- **預算要能預扣（reserve）與取消**。現在超支的上界＝並發數 × 單筆成本（(b) 13b），因為送出去的請求追不回來。送出前先扣、回來再結算，超支就有界了。
- **等待要真的睡**。4b 的 PM 26 輪有 16 輪只在讀信等信（`studio-efficiency:9`）——這 16 輪的錢是「沒有阻塞式等待」直接換來的。(f) 第 1 件解掉，這一項自然就沒了。

---

## (e) 待使用者拍板的骨幹相關題

### `wf/WAIT_USER.md` 裡的

| 編號 | 題目 | 出處 | 為什麼卡骨幹 |
|---|---|---|---|
| **A-6** | 子 agent 會自動繼承 `spawn`，子孫一路都能生小孩（驗過三層）。要不要擋、要不要限深度？（使用者 09-06 說「之後再說」） | `WAIT_USER.md:28` | 這是「權限／能力怎麼傳給子世界」的原則題，proto3 的 spawn 設計要先知道答案 |
| **A-8** | agent 之間的交流（tell／hear，或子回話自動變父的信）先不做，什麼時候做、走哪種？ | `WAIT_USER.md:29` | 現在只有「信箱檔案」一種 IPC。要不要有同步的呼叫，決定狀態機要不要多一態 |
| **A-9** | 拍板題 T-01～T-77 全照建議做了；要翻案就回編號 | `WAIT_USER.md:30`、`notes/tools/README.md` | 骨幹相關的有：T-13（長指令開子世界 vs 丟背景）、T-16（深度限兩層）、T-19（`kids.json` 名冊 vs 掃資料夾）、T-20（shared 小孩暫停＝註解 inst 那行）、T-21～T-25（長工作自己退鐘、結果走信箱、一小時超時）、T-26～T-30（身份與環境）、T-31～T-34（成本帳）、T-61～T-65（LLM 排隊）、T-70（一個鐘帶整隊） |
| **A-10** | 玩出來的 25 條效能與邊緣狀況、各包想要但沒有的接點，要你看過說哪些現在要做 | `WAIT_USER.md:31`、`play/README.md:102-146`、`docs/packs-api.md:126-128` | **這一條直接就是 proto3 的需求清單**。`packs-api.md` 最後一節列了 8 個「還缺的接點」：bigmem 的安全 `history_read/replace`、送主線 LLM 前的通用攔截掛勾、branch 的 adopt 旗標、code 的 `project_path`／`undo_dir`、首封信自動建 thread、cost 拿原始參數字串、MCP 指定來源投信、review 的 task key／起始格 |
| **11** | **預算要不要對 cached token 打折**——選項：閘門只算 `prompt − cached + completion`；或另開一個「真實成本」欄 | `WAIT_USER.md:34`、`journey:217` | 見 (d) 第 5 條。決定閘門的正確性 |
| **12** | **dev 的對話史**——要不要每個任務開新對話史（做完就清、只留任務說明＋檔案清單） | `WAIT_USER.md:35`、`journey:183` | 見 (d) 第 3 條。決定骨幹要不要管記憶壽命 |
| **13** | **preset 的 `max_per_member`**——100k 對 claude-cli 太低（4d 手動抬到 500k）。改 300k？還是照引擎不同給不同值？ | `WAIT_USER.md:36` | 「上限跟引擎綁」意味著預算策略要知道引擎，現在不知道 |

### 筆記裡「還沒決定 ／ 再想想」的

- **tick 內卡住怎麼辦**——使用者原話「再想想吧，作業系統相關理論應該早就有解決方案了」（`notes/2026-09-06-world-clock-agent.md:19`）。現在只有 `sh` 60 秒硬砍（`aos_agent.py:27`）。相關的是構想 F-05「半途超預算怎麼記」，構想沒答、今天也沒答（`vs:155`）。
- **`.aos/inst` 要不要鎖**（T-28）——先不鎖，否則 shared 小孩會壞（`notes/tools/README.md:81`、`docs/identity-and-env.md:120`）。proto3 若改掉「shared 小孩＝父 inst 加一行」，這題就自然解掉。
- **泛用的 stuck 狀態**——`journey:193` 自己寫「泛用的 stuck 狀態還在做」，現在的 `stuck` 只認 LLM 錯誤。
- **`legacy_env` 文件不一致**——`docs/identity-and-env.md:35` 說預設 false，`ideas-vs-proto2.md:127` 說預設 true 要拉回。程式以 `docs` 為準，但**兩份文件對不起來這件事本身就是「沒有正本」的症狀**（構想 L-03）。
- **可預測性的兩把尺**（A-04 已拍板但沒做）——「三支固定題各跑五次記格數分布，不用改程式」（`vs:130`、`vs:163`）。

---

## (f) 我的判斷

### 重寫骨幹最值得從結構上解掉的 8 件

> 排序＝我建議動手的順序。第 1、2 件不做，後面全部白做（使用者自己的話：「**先堵死路 → 再量 → 再固化 → 再換模型 → 最後才調預算**。前面沒做完就跳到後面，錢一定白燒。」`lessons:5`）。

---

#### 1. 一個統一的「等待／喚醒」原語

- **問題**：proto2 沒有「我在等什麼、什麼會叫醒我」這個概念。每踩一次「沒有人再叫醒它」就加一個計時器，現在有 **8 個獨立硬編常數**（見 (b) 缺口一）。使用者自己的第一條原則就是：「看到任何 `return "idle"` 都要先問一句：**誰會再叫醒它？**」（`journey:193`、`lessons:9`）。
- **proto2 怎麼硬撐**：`sleeping` 一個布林（`aos_agent.py:1245`）＋ 各處計時器 ＋ `dangling_turn()` 這道出口後驗（`aos-agent:573-580`）＋ 工具包自己再造一次（`packs/studio.py:806`）。
- **重寫可以怎麼設計**：agent 每格結束時**必須**產生一個「我在等什麼」的物件——一組喚醒條件（新信／某筆請求回來／某個檔案出現／某個格數到了／某個外部事件），沒有條件就是「跑完了」（一個真正的終態，而不是 idle 空轉）。骨幹只做一件事：每格檢查條件、命中就喚醒。`retry`、`stuck`、未讀提醒、`auto_grant` 重試、`studio` 的 45 格提醒**全部變成同一種東西的不同參數**。順帶解掉的：
  - **一個真正的 `on_tick`**（現在沒有，逾時只能搭 `on_idle` 的便車，`play/2026-09-06-think.md:51`）。
  - **集合等待**（「三條旁線齊了再叫我」，`play/2026-09-06-branch.md:13`），等待責任不再推給模型。
  - **活性指標**：「這一題有沒有前進」變成骨幹算得出來的東西，而不是靠人看 ticks 有沒有漲（`play/2026-09-07-studio-3.md:21`）。這需要第 8 件（任務身分）配合。
- **風險**：條件表達力不夠會退化成「每格都醒」；條件太表達力強會變成另一個 DSL（就是構想 04／05 章被使用者砍掉的東西）。**守住「條件只有五六種、都是資料不是程式碼」這條線**。

---

#### 2. 非同步請求一套生命週期，結果只有一個主人；失敗三態擴到全部四條線

- **問題**：LLM 那條線有三態（`requests/` → `running/` → `done/` ＋ 結果檔帶 `error`），**工具、小孩、job 三條沒有**（`vs:54`、`vs:126`）。而且即使 LLM 那條，結果的所有權還是會競速（agent 拿走結果、LLM 又補 `worker died` 灌水用量，`play/README.md:110`）。
- **proto2 怎麼硬撐**：`aos-llm:428-478` 的三段判斷（pid／完成標記／結果檔三個都不在才算死）＋「看到結果但 worker 還活著先不搶」這條特例；`Ctx.collect_results` 這一側再做一次逾時／缺鐘／取消的判斷（`aos_agent.py:1282-1315`）。小孩鐘死了父只能靠信箱猜；job 死在落盤前整個重跑。
- **重寫可以怎麼設計**：**一種請求、一種狀態機、一個主人**。任何跨界的事（叫 LLM、叫工具、叫小孩、開長工作）都是同一種 request 物件，狀態只有 pending／done／failed 三態，**只有共用層可以搬結果**，發起者只能訂閱。`play/README.md:98`、`play/README.md:150` 兩處都指名這是「如果只修三件」的第一件。要一起做進去的：
  - **失敗要分種類，而且要有出口**：`no_clock`（投到沒有鐘的地方）、`timeout`、`protocol`（回來了但沒用）、`cancelled`、`engine_error`。旁線已經有這一套了（`docs/packs-api.md:80-83`），**主線要照抄**，而且缺鐘要當場就知道、不是等滿 60 格（`play/2026-09-06-toolsmith.md:21`）。
  - **逾時基準統一**：現在旁線是牆上時間、主線是格數（`play/2026-09-07-simplify-2.md:26`）。
  - **可取消 ＋ 可預扣**：解掉「在途請求追不回、超支上界＝並發 × 單筆」（(b) 13b）。
  - **結果進對話前有一個攔截點**（`bigmem`、`branch` 兩個包都在等這個，`play/2026-09-06-bigmem.md:27`、`play/2026-09-06-branch.md:26`）。
  - **孤兒結果會被回收**（`play/2026-09-06-hooks.md:48`）。
- **風險**：把工具呼叫也統一成非同步，會讓「一格內做完」的簡單事變複雜。**折衷是介面統一、實作可以同步完成**（同步的就是「當格就 done」）。

---

#### 3. 「格」的會計：做事／等待／凍住三種，一個地方算、一個地方判

- **問題**：`busy`、`step`、`question_steps`、`question_sleep_steps`、`frozen_ticks`、`wait_ticks` 六個計數器，散在 `aos-agent:563-584`，被 `hard_limit`、`team_status_of`、`aos-user why` 三處各自解讀。踩過兩次坑：idle 空轉穿透整隊 ticks 上限（`play/2026-09-06-studio-2.md`）、等模型的格被算成動作格而撞上限停下來問人（`journey:34`、`journey:150`）。
- **proto2 怎麼硬撐**：兩次分別補在兩個地方（`cfffb2b` 補 `busy`、`e938d6c`＋`7a2d26a` 補 `question_sleep_steps`），而 `question_sleep_steps` 只被寫、從沒被判過。
- **重寫可以怎麼設計**：一格結束時**只記一件事：這格屬於哪一類**（做事／等待／凍住／睡）。所有上限都對「做事格」判。這是一個 enum 加一個計數，不是六個。
- **風險**：分類的邊界會有爭議（「跑工具但工具在等網路」算哪類？）。**規則寫死一條：花了 LLM token 或改了世界的檔案就算做事，其餘都不算。**

---

#### 4. 引擎接口層獨立成一個介面，協定修補全部搬進去

- **問題**：`aos-agent` 這支 605 行的狀態機裡，**約 100 行、5 個函式是在救「模型把工具呼叫寫成文字」**（`aos-agent:25`、74-170、274-295）。而 `aos-llm` 那支 1793 行裡塞了四種引擎的翻譯（`to_anthropic` 82、`from_claude_cli` 73、`codex_run` 79）。
- **proto2 怎麼硬撐**：救回邏輯放在 agent，因為只有 agent 知道「我有哪些工具」（`known` 集合，`aos-agent:274`）——**「有哪些工具」沒有下傳到引擎層**。
- **重寫可以怎麼設計**：定一個**引擎契約**：輸入＝(messages, tools, params)，輸出＝(content, tool_calls, usage{帳面/計價})。所有怪癖（`</think>`、寫成文字的 tool call、cache token 折算、stream 事件合併、MCP 假伺服器）都在引擎那一側處理完。工具清單是契約的一部分，所以救回邏輯天然有 `known`。使用者自己驗過這個分層是對的：4d 六個坑全在接口層、流程層一行沒動（`journey:162`、`journey:195`）。
- **風險**：契約定太窄會擋掉未來的引擎（streaming、多模態、agentic 引擎像 codex 那種「會一直做下去」的）。**先讓契約支援「一發抵一個決定」這一種用法，其他當擴充。**

---

#### 5. 記憶（對話史）是骨幹的職責，不是模型的自覺

- **問題**：`do_llm` 每格把 `prompts.json` 整份送出（`aos-agent:57-58`）。haiku 一個任務 21 輪吃掉 325k，一輪從 10k 漲到 20k（`journey:172`）。使用者的結論：「qwen 是做不出來，haiku 是做得出來但貴；後者的解是**管記憶**」（`journey:211`、`lessons:45`）。
- **proto2 怎麼硬撐**：`memory` 包有摘要工具但要模型自己想到去叫；`memory` 包的 `on_idle` 到 40000 字寄信提醒自己、80000 字硬砍（`docs/memory.md:31-38`，門檻寫死）；`bigmem`／`branch`／`ref` 三個包各自直接改 `prompts.json`（`packs/branch.py:349`、`packs/bigmem.py:110`、`packs/ref.py:141`）——**四個包搶同一個檔，沒有鎖**。
- **重寫可以怎麼設計**：對話史是骨幹管的**有結構的東西**（分段、分壽命、可摺疊），不是一個 JSON 陣列。「這一輪送什麼」是骨幹每格算出來的：人格 ＋ 動態工具子集 ＋ 壓過的歷史 ＋ 當下相關的信。任務級記憶做完就丟（正是 `WAIT_USER 12` 在問的）。包只能透過接點動它。
- **風險**：壓縮策略選錯會丟掉關鍵資訊，而且錯了很難查。**要有「原文一定留得回來」的保證（`forgotten/` 已經是這個形狀）＋ 可以關掉。**

---

#### 6. `Ctx` 是唯一接點：路徑、身分、鐘、狀態命名空間

- **問題**：三件事各自散落：(i) world／home／專案目錄／隊根／通訊錄別名五種基準沒有統一解析（`play/README.md:39`、`journey:37`、`journey:156`）；(ii) 各包直接摸 `state.json`、`clocks/`、`.aos/inst`、`prompts.json`、`engines.json`（`packs/kids.py:125`、`packs/branch.py:97`、`packs/think.py:68`、`packs/self.py:34`…）；(iii) `state.json` 44 個鍵沒有命名空間，骨幹和 13 個包共用一個抽屜。
- **proto2 怎麼硬撐**：`Ctx` 已經做了一半（`clock_of`、`world_of`、`put_mail`、`send`／`pending`／`cancel`），但沒有強制力——包想繞就繞。`play/README.md:129`、`vs:129` 兩處都寫「要拉回」。
- **重寫可以怎麼設計**：包**只拿得到 Ctx**，拿不到裸路徑。`ctx.path(...)` 是唯一的路徑解析器（自動處理 symlink、共用區、專案根）。`ctx.state` 自動加包名前綴。骨幹的內部檔（`state.json`、`prompts.json`、`clocks/`）包根本看不到，只看得到把手。順便把「介面殼與底層分開」（使用者續一，`world-clock-agent.md:37`）一起做掉：`aos-user` 不該有 `create_team_world`。
  一起收進來的還有三件小的，都是實玩點名過的：**(i)** 世界的生命週期要有 API，不要用「編輯父的 `.aos/inst` 文字」當 pause／kill（`play/2026-09-06-kids.md:8`）；**(ii)** 「成對開鐘」要是一個原子操作，忘一顆鐘不該只表現成「一直沒回」（`play/2026-09-06-mcp.md:5`、`:31`）；**(iii)** 同名工具誰優先要可以指定，不能是清單順序的副作用（`play/2026-09-06-fs.md:51`、`play/2026-09-06-toolsmith.md:49`）。
- **風險**：接點不夠時包就沒法做事，proto2 的教訓正是「接點不夠時各包只好自己繞」（`play/README.md:38`）。**所以要把 `packs-api.md` 最後一節那 8 條缺的接點當成 proto3 的第一批需求，先補齊再收緊**——收緊而不補齊，只會逼出更難看的繞法。

---

#### 7. 策略是資料，不是程式碼

- **問題**：8 個計時常數、`max_steps_per_question=60`、`SIDE_TIMEOUT_S=600`、`SH_TIMEOUT=60`、`TEAM_LOCK_TIMEOUT_S=10`、`memory` 的 40000／80000 字門檻——**全是硬編**，而且分散在骨幹與工具包兩層。使用者已經在問「`max_per_member` 要不要照引擎不同給不同值」（`WAIT_USER.md:36`），意思就是策略要能按情境變。
- **proto2 怎麼硬撐**：改一次要動程式碼、要記得改哪一支。好在「一格一個進程、當場改當場生效」（`journey:197`），所以撐得住——但那是原型才有的奢侈。
- **重寫可以怎麼設計**：一份 policy（喚醒間隔、重試次數、逾時、上限、記憶門檻、預算天花板），可以按世界／按角色／按引擎覆蓋。`aos-user why` 要能講出「這個值現在是多少、從哪繼承來的」。
- **風險**：設定爆炸。**上限：一份 policy 不超過 20 個鍵，每個鍵都有預設值，沒人設也能跑。**
- **順帶要定死的**：`0` 到底是「未設定」「無限」還是「禁止」——這個沒定義害 sales 在 0 額度下照樣燒了 7,011 tokens（(b) 13d）。

---

#### 8. 「當前任務／回合」要是一等公民

- **問題**：proto2 沒有「這一題」這個東西。`question_active`／`question_steps` 是最接近的，但那是兩個布林與計數器，不是實體。結果：`review` 包算不出「同類任務平均兩倍」（`play/2026-09-06-review.md:5`、`:41`），模型只好自己猜「上次任務從第幾格開始」、實玩猜成 8（`play/2026-09-06-review.md:33`、`:42`）；`step` 同時當時間軸與計數單位，三個工具同格跑就三行同 step（`play/2026-09-06-review.md:37`）。
- **proto2 怎麼硬撐**：`recent_question_steps` 留最近五題的格數（`aos-agent:338-341`）——只是一個數字陣列，沒有 id、沒有起訖、沒有結果。`studio` 包只好自己在 `team/tasks/` 造一套任務檔（`docs/studio-flow.md`），**於是「任務」這個概念存在於工具包，不存在於骨幹**。
- **重寫可以怎麼設計**：一個 turn／task 有 id、起始格、來源（哪封信／哪個上游任務）、預算、狀態、產出。所有帳（token、格數、工具呼叫、錯誤）都掛在它身上。這樣才算得出：這一題有沒有前進（→ 死路偵測）、這一題花了多少（→ 預算）、對話史哪一段可以丟（→ `WAIT_USER 12`）、模型在同類任務上有沒有變好（→ 構想 A-04 的可預測性尺）。
- **風險**：任務的邊界不好定（一封信算一題？一張單算一題？）。**先只做「一題＝從一則 user／信訊息開始，到 agent 回話或進入終態為止」這一種**，跟現在 `question_active` 的語意一樣，只是升格成有 id 的實體。

---

---

#### 兩件不夠格單獨列、但一定要順手做掉

- **一份說了算的欄位表 ＋ 版本欄**（構想 L-03 拍板過，`ideas/README.md:68`）。proto2 沒有正本，於是 `requester`／token 名／截斷長度／`contacts.json` 值型別／`id` vs `thought_id` 全都各說各話（(b) 缺口十四），連 `legacy_env` 預設值兩份文件都對不起來。**不必寫整套 spec**——`packs-api.md` 當契約、欄位名統一就夠（`vs:131`），但要有版本欄，不然帳本格式一改測試就打架（`play/2026-09-06-sched.md:8`）。
- **可預測性的兩把尺**（A-04 已拍板、一把都沒做，`vs:14`、`vs:130`）。**三支固定題各跑五次記格數分布，不用改程式**（`vs:163`）。proto3 一開始就該有這個，不然「重寫比較好」只是感覺。做完第 8 件（任務身分）之後這件事幾乎是免費的。

### 這些絕對要保留（proto2 做對的 5 件）

1. **一格一個進程 ── 改程式當格生效。**
   每個 agent 每格是一個新開的 `aos-agent exec` 進程（`aos-loop:58` 的 `os.system`）。09-07 一天修二十幾條坑，**沒有重開過任何一局實玩**（`journey:197`、`lessons:16`）。這是「修得動二十幾條」的前提，也是 proto2 之所以能一天跑完四局的原因。**proto3 不管怎麼寫，都要保住「當格生效、不必重啟世界」。**

2. **一切都是檔案。**
   看狀況就 `cat state.json`、`ls inbox/`、`tail monitor.log`，grep 一下就知道誰卡在哪（`journey:117`）。LLM 的 `requests/` → `running/` → `done/` 拔掉鐘一眼看得出排隊沒人做（`vs:116`）。除錯、測試、外部工具介入全靠這個。**沒有隱藏的記憶體狀態。**

3. **`.aos/inst` 就是一句 shell，資料夾就是世界。**
   `aos-exec` 41 行 ＋ `aos-loop` 75 行，比構想 04／05 兩章加起來小一百倍，而且真的跑得動整套（`vs:113`）。使用者親手推翻過 json 指令批、拆平、接力棒（`vs:140`）。**這是整套裡最貴的一次簡化，不要再犯一次。**

4. **LLM 是跟 agent 平起平坐的另一個資料夾。**
   不是誰的私有功能，一樣靠 `aos-loop` 一格一格轉（`README.md:144-145`），怪癖統一在 `aos-llm` 那側收口（`strip_think`、四種引擎翻譯）。這個分層讓「換引擎是一小時的事」（`lessons:43`）——4d 六個坑全在接口層，流程層一行沒改（`journey:195`）。

5. **一包一檔的工具包 ＋ 掛勾 ＋ prompt 覆蓋；規則放工具、不放人格。**
   `packs/<名>.py` 自帶 `TOOLS`／`PROMPT`／`run()`／六個掛勾（`docs/packs-api.md:102-115`），加一包就是加一個檔（`README.md:103`）。而**「規則放工具，不放人格」是 09-07 最重要的一句方法論**（`lessons:30`、`journey:201`）：人格寫的模型會忘，工具擋的它繞不過——小模型五種固定毛病全是這樣一條一條擋掉的。工具包沿用這件事本身就證明這個介面是對的。

> 差一點進榜的兩件，也建議照抄：
> **daemon 直接用 Linux 的輪子**（一個鐘一個 process group、SIGSTOP／SIGCONT 當 pause、pid 認領、dead 自動重開，`README.md:201-233`、`aos-daemon-kernel:463-506`）——構想裡沒有的 `pause` 是白拿的。
> **假 LLM 測試伺服器**（user 訊息寫 `CALL 工具 {json}` 就照做，`journey:119`）——讓流程包不用真模型就能跑整條線，改一個工具幾秒就知道有沒有弄壞別人。
