> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# F2 路徑一：OS 當 agent——handy ＋ unipath 采風（2026-08-30）

← [ai-core-field](README.md)｜隊長 Fable，隊員 codex ×3（agent-base＋try_0802／try_impl＋util／unipath）。
只讀，不改 ai_core、不改 aos 程式。路徑縮寫：`H/`＝`~/repo/ai_core/sub_projs/handy/`，`U/`＝`~/repo/ai_core/sub_projs/unipath/`，`aos/`＝`~/repo/simple_tools/aos/`。

## ① 那塊在講什麼（白話）

**handy** 是「把整個 OS 當成一個 agent」的試驗田，北極星是**工具集、不是單體**（`H/README.md` 開頭）。四條線各講一件事：

- **agent-base**：一個資料夾＝一個 agent；`main.py` 就是「每秒 poll 一個收件檔 → 讀進來、rename 搬走 → 連上下文丟給 endpoint → 照回覆執行指令」的普通迴圈。**一次性是核心，常駐＝`while True: sleep(1); 一次性()`**；時間／次數／資源三種限制是同一組參數，形態只是特例（`H/agent-base.md` §兩種執行形態、§額外的執行方式）。收件匣用檔案的價值：**沒發明協定，直接繼承 OS 全部寫檔手段**。
- **try_impl＋util/metainfo**：一支可執行檔要算「函數」只需兩條：`--metainfo` 印自述（排在所有驗證前、退出 0）＋**自述即契約**（宣告了就要做到，沒宣告＝沒說、外部不准補預設）。實現 `--metainfo` 就必須連帶吃 `--metaconf x.json`／`--metaconf.k v`（解析硬性、理會可選）。**argv 就是 lisp 的 list，旗標就是 keyword**——不另造第二套協議（`H/try_impl/README.md`）。自述＝`description`（唯一必填）＋九軸（`entries`／`lifecycle`／`state`／`state_dirs`／`resources`／`interruptible`／`guarantee`／`dry_run`／`nondeterministic`）＋活值 `reliability`；`entries` 一律 filepath（Plan 9）（`H/try_impl/metainfo.md`）。
- **try_0802**：A（產出）／B（改 A 的規則表）／C（零 LLM 評分）三段迴圈用 Janet 真跑通，A 的 completion token **721 → 10 → 0**。`sh.janet` 讓 **`.`／`/` 開頭的 symbol ＝ 執行那個檔案**，後面的 list 就是 argv，回 `@{:cmd :status :out :err}`。⚠ 自己標明：規則表退化成常數，**只證明迴圈機械部分會動，沒證明規則能取代 LLM**（`H/try_0802/README.md` 警告框）。
- **notes/2026-08-06（最新一份想法）**：LLM ＝**把意圖翻成 s-expression 動作序列的翻譯器**；tool 為核心，「一個可執行檔＝一個 tool，argv 天然是 tool arg，stdin/out/err 是特殊 tool arg，全是文字」；**普通指令交給 shell，特定環境變數指定的資料夾下的東西才登記成 LLM 可用 tool**；「先前說要做 metainfo，現在覺得不需要了——程式都是文字腳本，LLM 自己讀」；複製人＝讀一份 `.json` 取得環境（tool 清單、權限、模型設定）；inbox＋一秒輪詢做交流。

**unipath** 是更底層的一刀：「先歸一於路徑、後成局」——把正在跑的 process 執行態暴露成可 `ls`／`cat`／`echo` 的路徑樹，每個節點三個約定檔 **`data`／`ctl`／`status`**（Plan 9 慣例，用「多一個檔」取代「多一個動詞」），線協議是真 9P2000（Python／C++／Fennel 三種 server 互通＝「規範＝會講 9P」）；時間靠 `tick` 外掛，規則（Janet 腳本）本身也住在樹裡可 `echo` 改（`U/OVERVIEW.md`、`U/docs/現況-已實作操作.md`）。誠實邊界：活樹目前只有 counter／list／dict 示範，**真 pid、argv、stdio、exit 都還沒做成節點**（`U/up_world.py:16-22`）；**沒有任何 callable／tool 登記機制**，只有節點級自述（`ctl` 讀出命令說明、`status` 讀出型別）。

## ② aos 已承接的

| handy／unipath 的東西 | aos 現況（證據） |
|---|---|
| 一個資料夾＝一個 agent／世界；上下文外部化成檔案 | `<folder>/.aos/`、`agents/<name>/{history,status,tools}.json`（`aos/wf/workflows/dispatch/proto/PROTOCOL.md` §1；`core/agent/README.md`） |
| 收件匣 rename 原子搬走（agent-base「改成搬走」） | 兩段 rename：生產者 `.tmp→.json`，loop `inbox→batch/<turn>/insts/`（PROTOCOL §1、§5）——比 handy 單一收件檔完整 |
| 一次性是核心、常駐是薄殼；限制參數 | `aos run --step N --interval MS`（`--step 0`＝無限）；inst 的 `timeout_ms`（PROTOCOL §2、§6） |
| 每秒輪詢別換 inotify | loop 回合間隔輪詢，`every/` 每回合複製 agent step（PROTOCOL §1） |
| argv 是 list、不經 shell | inst JSON `argv` 陣列直接 fork/exec，`argv[0]` 走 PATH（PROTOCOL §2）——handy `sh.janet` 只認 `.`／`/` 開頭，aos 反而更廣 |
| 結果封套 `@{:cmd :status :out :err}` | `out/<id>.json` `{exit, signal, stdout, stderr, started_at, ended_at}`（PROTOCOL §3） |
| tool 白名單、模型只點菜單上的 | `tools.json` `{name, description, argv}`，system prompt 列 `name: description`，回覆最後一行 `{"tool","args"}`、未知工具拒絕（`core/agent/src/tools.cpp:29-53,107-146`） |
| tick ＝ 吸收影響 → 快照 → 同步轉移 | 回合＝匯聚 → 並行 fork/exec → 等完 → 落檔 → `turn+1`（PROTOCOL §5） |
| unipath `status` 節點 | `state.json` 鏡射 `agents/*/status.json`，含 running 的 pid（PROTOCOL §4） |
| 「LLM 是另一台跑同協定的機器」（08-06 翻譯器＋跨資料夾投遞） | [top-down-cli](../top-down-cli.md) §三：思考＝投遞到 llm pu 資料夾 |

另外 aos 曾有一份完整的 tool 格式 `reference/llmkit/tooljson/`（OpenAI tool JSON＋`_extra` exec recipe，`position`／`flag`／`repeat`、不經 shell、`set_approver`），**使用者已判定失敗作**（`wf/salvage/05` 第八節、`ideas/README.md`）——本篇不建議回頭抄它，理由見 ④。

## ③ aos 漏掉／走偏的

1. **`{args}` 是單一字串，把 argv-as-list 這條主軸折斷了。** `expand_argv` 只在某個 argv 元素裡逐字取代 `{args}`（`tools.cpp:92-105`），所以 `["ls","{args}"]` 收到 `"-la ."` 會變成**一個**參數 `"-la ."`；真正能吃這形狀的只有 `sh -lc`。handy 兩邊都說「argv 就是 list、旗標就是 keyword」（`H/try_impl/README.md` §形式、`H/try_0802/sh.janet` 檔頭）；aos 自己的 inst 協定也是 list（PROTOCOL §2）——**登記表是全系統唯一把 list 壓回字串的地方**。
2. **tool 身份住錯層。** 現在 `tools.json` 住 `agents/<name>/`、由 `agent init` 硬寫三項（`init.cpp:45`、`tools.cpp:29-35`），沒有 `aos tool add/ls` 指令。handy 08-06 的分工是：**世界（或環境變數指定的資料夾）持有 tool；複製人的 `.json` 只記「我能用哪些」＋權限**。aos 把「世界有什麼工具」和「這隻 agent 獲准用哪些」綁成一份。
3. **沒有從程式自述生成登記項的路。** handy 整條規範線的價值就是「外部不先跑一次就知道它是什麼」（`H/util/metainfo/README.md` §兩條契約）；aos 讀取器只認 `name/description/argv`，其他欄位寫了也不用（`tools.cpp:58-85`）。但要注意 08-06 已把 metainfo 降級：「相關資訊記錄到程式中，LLM 自己讀」——**兩種來源都得收（自述 JSON／檔頭文字），不是二選一**。
4. **限制參數只做了一半。** `--step`／`--interval`／`timeout_ms` 是世界與單條指令的；agent-base 那組「總時限、最多幾次、token、權限」（`H/agent-base.md` §額外的執行方式）在 aos 沒有落點——[top-down-cli](../top-down-cli.md) 開放問題 5、6（agent 靜默死亡、怎麼停）正是缺這一層。
5. **「認得出缺口卻不會變成動作」沒被接住。** handy 實測：模型知道自己缺檔案內容，卻要護欄明講「可以去拿」下一輪才會 `READ`（`H/try/v1/README.md` §觀察；`H/llm-nature.md` 末段）。aos 現在「沒有那行 JSON＝正常回話」、未知工具只記一行忽略（`tools.cpp:42-53`、`step.cpp:183-186`），沒有結構化退回重選。
6. **stdout/stderr 全內嵌字串 vs `entries` 一律 filepath。** `out/<id>.json` 把 stdout/stderr 整段塞進 JSON（PROTOCOL §3）；handy 的立場是大內容／binary 走路徑、控制 JSON 只帶路徑與短預覽（`H/try_impl/metainfo.md` §entries）。小原型沒事，`cat` 一個大檔就撞。
7. **執行中的 process 不可讀。** `state.json` 只在回合開頭與結尾整檔換掉（PROTOCOL §4）；unipath 的關鍵增量是 **process-backed read**——同一路徑此刻讀到此刻的值（`U/OVERVIEW.md` 核心概念 5）。aos 沒有 `running/<id>/{stdout,status,ctl}` 這種回合中間能看的樹。反過來 unipath 也沒有 aos 的耐久批次帳本與 exit/signal 封套——**兩邊互補，不是誰包含誰**。

## ④ 對 tool 登記表與表述的具體建議

**判斷原則**（隊長裁）：跟著 08-06 走「簡單到隨便一支腳本都能登記」，**不要**回頭抄 tooljson 那套 OpenAI schema＋`position/flag` 綁定——那正是使用者判失敗的方向；但要修 ③-1 的 list 斷點、把 tool 搬到世界層、留一條從自述自動生成的路。

**住哪：一個資料夾＝一個 tool**（跟「一個資料夾＝一個 agent」同構，也是 unipath「一個元素＝一個目錄＋約定檔」的形狀）：

```text
<folder>/.aos/tools/<name>/
├── tool.json        必有。登記項本體（下表）
├── metainfo.json    選。`<argv> --metainfo` 的原樣輸出，一個字不改、不補預設
└── help.txt         選。`--help` 或檔頭 docstring 的擷取，給模型按需 cat（08-06「LLM 自己讀」）
<folder>/.aos/agents/<name>/tools.json   → 退成 allowlist：["sh","ls","cat"]；缺檔＝全部可用
```

**`tool.json` 欄位**：

| 欄位 | 值 | 為什麼 |
|---|---|---|
| `name` | 字串，＝目錄名 | 模型點菜用的名字，人定 |
| `description` | 一句話：做什麼、吃什麼、何時用 | handy 標準規格唯一必填；Gap B1 |
| `argv` | 陣列，**固定前綴**（如 `["git","log"]`） | 沿用 aos inst；`argv[0]` 走 PATH |
| `args` | `"list"`（預設）｜`"string"`｜`"none"` | `list`：模型給的陣列**逐項接在 `argv` 後面**；`string`：只給 `sh -lc` 這類、整串當一個元素（現行 `{args}` 語意）；`none`：不收參數 |
| `stdin` | `"none"`（預設）｜`"text"`｜`"path"` | 08-06「stdin 是特殊 tool arg」；`path` 時模型給檔名，loop 自己開檔餵進去（entries=filepath 的最小版） |
| `cwd`、`timeout_ms` | 同 inst JSON | 直接投影到 PROTOCOL §2，不另造 |
| `source` | `"metainfo"`｜`"header"`｜`"manual"` | description 從哪來；決定可信度，不決定行為 |
| `traits` | 從 `metainfo.json` **抄過來**的子集：`lifecycle`、`interruptible`、`guarantee`、`state_dirs`、`nondeterministic` | 全選填、缺席＝「沒說」不＝「安全」。**現在 loop 只該用兩個**：`lifecycle: persistent` → 拒絕當一回合內的 tool；`interruptible: safe/graceful` → 逾時先 SIGTERM 再 SIGKILL，否則照現行直接殺。其餘先存不用 |

**怎麼生成**（`aos tool add <name> [--description ...] -- <argv...>`，全部寫入走 `.tmp`＋rename）：

1. 跑 `<argv> --metainfo`（帶 timeout，`stdin` 關掉）。退出 0 且 stdout 是 JSON object 且有非空 `description` → `source: metainfo`，原樣落 `metainfo.json`，`description` 與 `traits` 直接抄；未知欄位保留。
2. 退出 0、非空 UTF-8 但不是 JSON → handy「最小規格」：第一行當 `description`、`source: header`，`traits` 空。
3. 否則（多數既有 POSIX 程式）：`argv[0]` 是文字腳本就擷取檔頭註解／docstring 進 `help.txt` 與 `description`（`source: header`）；不是就要求 `--description`（`source: manual`）。**絕不掃整條 PATH 自動登記**——08-06 說得很清楚：PATH 交給 `sh`，只有指定資料夾下的才登記成 tool。
4. `agent init` 不再硬寫三項，改呼叫同一生成器登記 `sh`（`args: string`）、`ls`、`cat`（`args: list`）。
5. 規範二（宣告了就要做到）**從外面驗不了**（`H/try_impl/README.md` §還沒定的）——登記器只驗自述形狀，不承諾行為。

**表述給模型**（維持現行「一行一工具」的精簡，只加參數形狀）：

```text
- ls (args: list, stdin: none): 列出資料夾內容。args 是選項與路徑，例如 ["-la","."]
- sh (args: string): 用 sh -lc 執行一行 shell 指令
- cat (args: list): 印出檔案內容。args 是檔案路徑
```

呼叫行：`{"tool":"ls","args":["-la","."]}`；`args: string` 的工具維持 `"args":"..."`。解析器照 `tool.json` 的 `args` 型別驗，**型別錯／未知工具下一回合送一則結構化 tool 訊息要求重選**，不再靜默忽略（接 ③-5）。完整 `metainfo.json`／`help.txt` 不進 prompt，模型要就 `cat .aos/tools/<name>/help.txt`——這正好也是 unipath「先精簡投影、細節留在樹上按需讀」的用法。

**不在這輪做但要記著**：agent 層的 `limits.json`（`deadline_ms`／`max_tool_calls`／`max_tokens`／allowlist，agent-base 那組）；`running/<id>/` 回合中可讀的 process 樹（unipath）；大輸出落檔改帶路徑（entries=filepath）。

## ⑤ 值得直接抄的檔案

| 檔 | 為什麼 |
|---|---|
| `H/util/metainfo/README.md` | 兩條契約＋`--metaconf` 的邊界寫得最完整，可直接當 `aos tool add` 探測步驟的語言中立底稿 |
| `H/try_impl/metainfo.md` | 「最小／標準」兩個等級＋九軸速查表，就是 `traits` 欄位說明與降級登記的依據 |
| `H/util/metainfo/metainfo.py` | 「只抽自己的 token、其餘 argv 原樣交回」的掃描法——aos 若要讓自家子命令也合規（`aos llm --metainfo`）照這個抄 |
| `H/try_0802/sh.janet` | 「路徑＋list＝一次呼叫」的介面與 `@{:cmd :status :out :err}` 結果表；stdout/stderr 並行收取那條坑 aos exec 也會踩 |
| `H/try_0802/abc/a_gen.janet` | 一支真的實作了 `--metainfo`／`--metaconf.k v` 的程式長什麼樣（自述 dict 在檔頭），是 `source: metainfo` 那條路的測試對象 |
| `H/try_0802/bench/scene.json` ＋ `abc/c_check.janet` | 「輸入＋期望輸出＋機判規則」同一份 fixture、C 零 LLM 評分——08-06「改進使用＝輸入配期望輸出」的現成形狀，aos 日後驗 tool 用得上 |
| `H/try/v1/README.md` | 護欄分類（結構性終止／零動作／斷路器）與「prompt 說過不等於模型會做」的實證，是 ③-5 的設計依據 |
| `H/agent-base.md` | 限制參數是一組、形態是特例；rename 收件匣；「先會痛的是上下文不是 tool」 |
| `H/notes/2026-08-06.md` | 使用者最新的 tool 觀（翻譯器、PATH vs 指定資料夾、`.json` 記 tool 與權限、複製人／員工四級）——④ 的判斷全靠它對齊 |
| `U/up_world.py` ＋ `U/up_env.py` | `data/ctl/status` 節點契約與 walk/stat/readdir/read/write 核心，不到 150 行，要做 `running/<id>/` 樹時照翻 |
| `U/docs/現況-已實作操作.md` | 「tick 只要讀值、改值、走樹三樣」的動詞檢查表，防止 aos 路徑介面長出多餘動詞 |
