# aos 概念速成（給 AI）

每節＝一個概念：一句白話、最小範例、常見錯、出處（proto8 的條號：C-＝CONCEPTS、N-＝NORMS、P-＝CONVENTION）。
`aos-ai explain <節名>` 印一節，`aos-ai explain` 列節名；`aos-ai explain --here [目標]` 算出「現在 aos-exec 它」的具體值。
內容照 proto8 條文寫，條文是草稿、以 proto8/CONCEPTS.md、NORMS.md、CONVENTION.md 為準。

## overview

一句：**資料夾＝程式**。aos 本身只保證六個環境變數和一支 `aos-exec`，其他（loop、fsm、daemon、agent 的形狀）都是在這上面疊出來的（C-68～C-70、N-57）。
範例：`cd 工作區 && aos-exec ../agent-dan`＝在這個工作區跑 agent-dan 這個資料夾程式。
常見錯：以為 aos 有 `aos run`、`.aos/` 世界——那是更早的一代（repo 根的 core/），proto8 不用。
出處：C-68～C-73、N-57～N-62。

## env

一句：六個環境變數分三類（P-39）——**繼承的**（`AOS_WS`、`AOS_STACK`：照 Linux 原樣往下傳）、**每跳 aos-exec 覆寫的**（`AOS_CF`、`AOS_CD`、`AOS_CO`）、**挑入口用的**（`AOS_ENTRY`，aos-exec 不 export）。
範例：`aos-exec --ws /w agent` 之後，入口看到 `AOS_WS=/w`、`AOS_STACK=/w/.stack/`、`AOS_CF=…/agent/_entry`、`AOS_CD=…/agent`、`AOS_CO=`（空）。
常見錯：以為 aos-exec 會改 PATH——不會，aos 的程式都不動 PATH，呼叫者要自己把 aos-exec、aos-loop… 放上去（N-59、ideas § 24）。
出處：N-57、N-59、P-39。細節看 `explain AOS_WS` 等各節。

## AOS_ENTRY

一句：入口在資料夾（或 JSON 物件）裡叫什麼名字，**預設 `_entry`**。資料夾裡是檔 `_entry`，JSON 裡是 key `"_entry"`（同一個名字）。
誰設：呼叫者或 `.env`；aos-exec **讀完那一層的 `.env` 才挑入口**，所以 `.env` 設的有效（沒被外面設過時）。aos-exec 不 export 它。
範例：`agent-dan/_entry`（shell 小殼 `exec aos-loop loop.json`）；`fsm.json` 裡 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`。
常見錯：寫成 `_exec`、`.aos/exec`（舊名）；以為入口一定要 `+x`——沒 `+x` 的會當 JSON 讀（N-61）。
出處：N-57、N-59 第 4 件、N-61、C-73。

## AOS_WS

一句：**工作區**＝使用者的檔與成品在哪（題目 `new/`、答案 `out/`…）。
誰設：`aos-exec --ws WS` ＞ 外面已有的 `$AOS_WS` ＞ `.env`（預設不蓋）＞ cwd；aos-exec 轉成絕對路徑、export，之後原樣往下傳（巢狀多深都同一個）。
範例：`aos-exec --ws ~/try/w ../agent-dan` → 入口裡 `$AOS_WS=/home/me/try/w`。
常見錯：在程式裡寫死相對路徑當工作區（起跑 cwd 是入口的資料夾，不是工作區）；以為子程式的 `--ws` 會穿過字串轉向——旗標只管那一跳（N-58）。
出處：N-55、N-58、C-65。

## AOS_STACK

一句：**被叫的程式自己放執行中狀態的地方**（state、草稿、紀錄、小格），預設 `$AOS_WS/.stack/`。定義資料夾不被寫（P-15）。
誰設：沒設＝aos-exec 設預設值並建資料夾；有設就沿用（所以叫別人時要自己給它一個**小格** `AOS_STACK=$AOS_STACK/<名>/`，P-17）。
範例：agent-dan 的 `$AOS_STACK/state.txt`（fsm 現在在哪格）、`trace.jsonl`、`history.jsonl`；叫工具 `AOS_STACK=$AOS_STACK/math/ aos-exec tools/math`。
常見錯：叫工具時沒給小格（工具的檔會跟你的混在一起）；aos-loop／aos-daemon **不自己建** stack（不在＝`WriteFailed`），經 aos-exec 跑才會被建。
出處：N-57、N-59 第 1 件、P-15～P-18、C-67、C-70。

## AOS_CF

一句：**實際被執行的那個檔**的絕對路徑（解開捷徑、不帶 `#/…`）。每跳 aos-exec 覆寫。
範例：`aos-exec fsm.json` → 入口 `aos-fsm` 看到 `AOS_CF=/…/agent/fsm.json`，所以 `_entry` 寫 `["aos-fsm", {"$env": "AOS_CF"}]` 就能讀到自己。內嵌單子在 loop／fsm 行程內跑時＝寫著它的設定檔（`explain inline`）。
常見錯：以為它帶 `#/指標`——指標在 `AOS_CO`；以為 `.env` 改得到它——預設不蓋，要那一跳 `--dotenv-override`。
出處：N-57、N-62。

## AOS_CD

一句：`AOS_CF` 所在的資料夾＝aos-exec cd 進去的地方＝**起跑時的 cwd**。程式 cd 走之後靠它找回自己的東西。
範例：`cd "$AOS_WS" && aos-exec "$AOS_CD/tools/stamp"`；`.env` 裡 `PATH=${AOS_CD}/bin:${PATH}`（要 `--dotenv-override` 才蓋得了 PATH）。
常見錯：在 `.env` 改 `AOS_CD` 以為會再 cd——不會，cd 已經做了。
出處：N-57、N-59 第 4 件。

## AOS_CO

一句：**入口在那份 JSON 檔裡的位置**（JSON 指標、不帶 `#`）；入口不是 JSON（可執行檔）或整份檔就是入口＝空字串。
範例：`aos-exec fsm.json` → `AOS_CO=/_entry`；`aos-exec x.json#/a`（`/a` 是沒 `argv` 的物件）→ `/a/_entry`；fsm 在行程內跑 think 格的單子時＝`/states/think/exec`。
常見錯：拿 `{"$env": "AOS_CO"}` 當「這一格」——在 fsm 解格的時候它是 fsm 自己的入口位置（`/_entry`），不是那一格（thinking 10-24 exec-relative）；指示詞也拼不了 `AOS_CF`＋`AOS_CO` 兩個變數。
出處：N-57、thinking 2026-10-24-exec-relative。

## entry

一句：`aos-exec [旗標] XXX [args]` 怎麼從 XXX 找到入口（N-61）：
1. XXX 是資料夾 → cd 進去、讀 `.env` → 找 `XXX/$AOS_ENTRY`（是資料夾就再走進去）→ 沒有再找 `XXX/$AOS_ENTRY.json`。
2. XXX 是檔（或 `檔#/指標`）→ cd 到它的資料夾、讀 `.env`；不在又沒副檔名 → 試 `XXX.json`。
3. 找到的檔：有 `+x`＝可執行檔、直接 exec；沒 `+x` 當 JSON 讀：有 `argv`＝**單子**（行程內跑）、非空陣列＝**argv**（exec）、字串＝**轉向**（全新的一跳 aos-exec）、沒 `argv` 的物件＝當資料夾、取 `js[$AOS_ENTRY]` 一路往下。
範例：`aos-exec agent-dan`（資料夾）、`aos-exec loop.json`（JSON 帶 `_entry`）、`aos-exec cfg.json#/tools/stamp`（指標）。
常見錯：`aos-exec loop.json` 但 loop.json 沒有 `_entry`——aos-exec 不認 loop 設定，要寫 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`；`#` 後面不是 `/`＝入口壞；資料夾帶 `#/`＝入口壞。
出處：N-58、N-59、N-61、N-62、C-73。

## dotenv

一句：aos-exec 每走進一個資料夾（或沒 `argv` 的 JSON 物件的 `.env` key）就讀那裡的 `.env`，有效到真正開跑；**預設不蓋環境裡已有的名字**，`--dotenv-override` 才蓋（只管那一跳）。
範例：agent-dan 的 `.env`：`AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low`（外面設過就用外面的）。
常見錯：在 `.env` 設 `AOS_WS`（有旗標的變數，風險自負，建議別碰）；以為 loop／fsm 行程內跑的單子會讀 `.env`——不會。
出處：N-58、N-59 第 4 件、N-60。

## inst

一句：**單子**＝一張「跑一個程式」的 JSON，只認 10 個 key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`、`timeout_ms`、`grace_ms`；其他 key 忽略。aos-exec 在行程內跑它、當監工（逾時整群收掉、轉訊號、以子程式的碼結束）。
範例：`{"argv": ["python3", "brain.py"], "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}, "timeout_ms": 120000}`
常見錯：`argv` 寫成字串；以為 `cwd_mkdir`、`stderr_merge` 有效（被忽略）；`argv[0]` 帶 `/` 又不是可執行檔時，會被當成 `aos-exec <它>`（N-61），PATH 上要有 aos-exec。
出處：N-04、N-59 第 5 件、N-61、impls/aos-exec README「inst 單子」。

## loop

一句：`aos-loop loop.json`＝一次一次地跑 `exec`，看結束碼決定下一步；**0＝下一次、10＝正常停（loop 以 0 結束）、其他＝以那個碼結束**。
範例：`{"exec": "fsm.json", "max": 40}`；選填 `interval_ms`、`ctl`、`state`；要能 `aos-exec loop.json` 就加 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`。
常見錯：`max` 沒寫＝**不限**；`exec` 的相對路徑照 cwd（＝loop.json 的資料夾）算；loop 不管逾時（要逾時把 exec 寫成單子加 `timeout_ms`）。
出處：N-28、N-54、P-06、P-19、impls/aos-loop。

## fsm

一句：`aos-fsm fsm.json`＝**一次只跑一格**：讀 `$AOS_STACK/state.txt`（沒有＝`start`），跑那格，格退 0 才把狀態換成 `next`、以格的碼結束。外面靠 loop 一次一次驅動（N-53）。
範例：`{"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "idle", "states": {"idle": {"exec": "idle", "next": "think"}, "think": {"exec": {"argv": ["python3", "brain.py"]}, "next": "idle"}}}`；每次在 `$AOS_STACK/trace.jsonl` 追加一行 `{"at","state","code","signal","elapsed_ms"}`。
常見錯：每一格都要有 `next`（開跑時查整張表，缺了＝`CfgBad`）；格失敗時 state 不動、下一次重跑同一格（P-20）；格之間傳東西寫 stack 裡的檔、不走 stdout（P-10）。
出處：N-36、N-38、N-41、P-07～P-10、impls/aos-fsm。

## daemon

一句：`aos-daemon daemon.json`＝顧一群子 loop（`loops`），每個子項一個小格 `$AOS_STACK/<名>/`；daemon.json 是 loop.json 的超集。
範例：`{"interval_ms": 500, "ctl": "ctl.json", "state": "state.json", "loops": {"bob": {"exec": {"argv": ["aos-exec", "--ws", "/w/bob", "/agents/bob"]}, "interval_ms": 2000}}}`
常見錯：子 loop 結束後**不自動重起**（停在表上 `done`；要再起就從 ctl 拿掉再放回）；子項名字不能跟 ctl／state 撞名；PATH 上要有 aos-loop 和 aos-exec。
出處：N-28、N-54、impls/aos-daemon。

## window

一句：**ctl／state 兩扇窗**（`$AOS_STACK` 底下的檔）：ctl 誰都能寫、loop 只讀（宣告式：`paused`、`stopped`、`max`、`interval_ms`、`seq`；daemon 多 `loops`、`loops_added`、`loops_removed`）；state 只有 loop 自己寫（`phase`、`counter_runs`（跑過幾次；計數一律 `counter_<被數的東西>`）、`ctl_seq` 回音、`ctl_warning`、`pid`、`started_at_ticks`、`recorded_at`）。
範例：叫停 `{"stopped": true, "seq": 2}`；加一隻 `{"seq": 3, "loops_added": {"carl": "agent-carl"}}`，等 state 的 `ctl_seq` 變 3＝讀到了。
常見錯：寫 ctl 沒先寫暫存再改名（N-05）；壞的 ctl 整份不採用、原因在 `ctl_warning`；拿掉 `loops_added`＝加進來的會被收掉（宣告，不是指令）。
出處：N-06～N-09、N-13、N-17、N-32、N-54。

## exit

一句：結束碼 **0＝正常、10＝正常停（請外面的 loop 別再跑）、其他非 0＝有錯**；aos 的程式自己的錯一律退 1、stderr 一行 `程式名: 代號 原因`；被訊號停掉＝128＋訊號（SIGTERM＝143）。正常退出不寫 stderr。
範例：idle 格 `new/` 空了 `exit 10` → fsm 退 10 → loop 以 0 結束；`aos-exec: EntryMissing 入口不存在：nope` 退 1。
常見錯：把 10 當錯；以為 loop 會轉述下層的錯——每層只說自己的（loop 只說「第 N 次 誰 失敗，結束碼 C」）。
出處：N-43、N-60、P-19、P-21、C-53、C-54（代號：主詞＋Missing／Unknown／Bad／Failed）。

## directive

一句：**指示詞**＝JSON 裡帶 `$env` 或 `$ref` 的物件，整個換成它指到的值；可帶 `$path`（字串接在後面）、`$prefix`（接在前面）。`$ref` 可以是 `檔#/指標`，也可以是陣列（幾份照順序合成一份）。每支程式只解自己讀的格。
範例：`{"$env": "AOS_STACK", "$path": "plan.txt"}`、`{"$ref": "common.json#/max"}`、`{"$env": "AOS_CF", "$path": "#/states/think/body"}`。
常見錯：以為會字串內插（`"$AOS_WS/x"` 不會被換）；`$env` 沒設＝錯（跑的時候才報）；寫法不合（例 `{"$env": 3}`）會被原封不動留著，多半是打錯（`aos-json check` 抓得到）。
出處：N-45、C-48。

## inline

一句：loop／fsm／daemon 的 `exec` 可以**直接放單子物件**（10-24），由它們在**自己行程內**跑（同 aos-exec 跑單子那套：`timeout_ms`、訊號、結束碼）；跑的期間 `AOS_CF`＝寫著它的設定檔、`AOS_CD`＝那份檔的資料夾（相對路徑的基準）、`AOS_CO`＝`/exec` 或 `/states/<名>/exec`；不讀 `.env`；`AOS_WS`／`AOS_STACK` 照外層的。
範例：fsm 格 `"think": {"exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000}, "next": "act"}`。
常見錯：單子壞（`argv` 不對、指示詞解不開）＝loop／fsm 自己的錯、退 1；舊寫法 `"exec": "fsm.json#/states/think/body"` 也還能用（普通的 aos-exec 目標）。
出處：thinking 2026-10-24-exec-relative、P-06、P-07、P-22。

## metainfo

一句：**`_metainfo`＝函數的特性**（跑多久、吃多少資源…），作者自報、給 kernel 與人看；aos-exec、loop、fsm、daemon 都不讀、不因它改行為。放在跟 `_entry` 並列的地方（資料夾裡的 `_metainfo` 檔、JSON 物件或單子的 `_metainfo` key）。
範例：`{"summary": "把 .py 照 PEP8 排版", "time_ms": {"val": 300, "max": 5000}, "resource": "cpu", "side_effect": true, "idempotent": true}`；通用 key 全選填：`summary`、`time_ms`、`resource`、`mem_mb`、`gpu_mem_mb`、`llm_calls`、`llm_tokens`、`lock`、`cost`、`side_effect`、`idempotent`、`deterministic`、`interrupt`（safe／unsafe／resumable）、`parallel`。
常見錯：拿 `time_ms` 當逾時（強制的是單子的 `timeout_ms`）；寫 `priority`（跟著請求、不放這）；跟 `tool.json` 混（那是給模型看的）。
出處：thinking 2026-10-24-metainfo（M1～M10，照推薦定、待落條文）。

## agent

一句：aos 的 agent＝一個資料夾程式＋一台被 loop 一次次驅動的狀態機（三態 `idle → think → act → idle`）。定義資料夾不被寫；跑的東西都在工作區與 stack。
範例（agent-dan）：
```
agent-dan/  _entry（exec aos-loop loop.json）、loop.json、fsm.json、.env、system.txt、idle/_entry、brain.py、act.py、tools/<名>/{tool.json,_entry}
工作區      new/<題名>（題目）→ cur/（認領）→ out/<題名>（答案）、done/（做完的題目）
$AOS_STACK  state.txt、current.txt、trace.jsonl、history.jsonl（一行一則 OpenAI message）、<工具名>/（工具的小格）
```
常見錯：答案找 stdout（結果只在工作區，P-11）；任一格失敗＝整隻停下等人，修好再跑一次從同一格接著做（P-20）；工具不靠 PATH，寫 `aos-exec tools/<名>`（N-50、P-25）。
出處：N-53、P-05～P-26、P-41。

## tool

一句：給腦叫的工具＝`tools/<名>/` 資料夾程式，裡面多一份 `tool.json`（OpenAI function 物件去掉 `name`：`{"description", "parameters"}`），**工具名＝資料夾名**；模型給的 `arguments` 從 stdin 進、stdout 整段是結果。
範例：`tools/math/tool.json`＝`{"description": "算一個算術式子", "parameters": {"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]}}`。
常見錯：在 `tool.json` 寫 `name`（不用，程式填）；沒 `tool.json` 的資料夾不算工具；工具退非 0：agent-dan 範本把 stdout 那行加上結束碼回給腦、不停（10-24 起；所以錯要印在 stdout，腦才看得到原因）。
出處：P-41、N-50、C-61。

## heap

一句：**記憶庫**＝跨對話保留的東西（agent-meg 範本慣例，不是 aos 保證的那六個變數）：位置 `$AOS_HEAP`，沒設＝`$AOS_WS/.heap/`；兩隻 agent 指同一個＝共用記憶。
範例：`$AOS_HEAP/index.json` → `<類>/index.json` → `<類>/001.md`，六類 prefs、facts、outcomes、gotchas、snippets、skills；工具 `memory`：`{"op": "save"|"search"|"read"|"forget", …}`。
常見錯：跟 stack 搞混——stack 換了就忘，heap 跨 stack 留著；forget 是搬去 `archive/`、不是刪。
出處：thinking 2026-10-24-memory、demo/README § agent-meg。
