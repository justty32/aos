# 11-07 五份設計的實作規劃（fable 一次性規劃）

← [impl-plan](README.md)｜主材料：[01-簡報](01-簡報.md)｜原話：[kb-ideas](../kb-ideas/README.md)、[隊形 03](../../../../../wf/workflows/dispatch/aos-teams/03-使用者原話.md)｜條文：[C-84](../../../../docs/CONCEPTS/05-agent/03-C-84.md)、[N-68](../../../../docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md)

## 白話總結

本線（只動 `proto8/`）排成 **9 批**，一個 codex 串行做、每批一個 commit。順序是「先把雜活與地基清掉，再把帳、量、換上這三樣早點交給 arknights 線用，審視者放中段，C++ kernel 放後段，審視者的進階招數放最後」。第 1 批是晚審五件 R 待辦加 `memory find` 認 tag；第 2 批是 `_metainfo` 改格式（最吵的一批，35 份檔）；第 3～5 批是帳、量、換上，做完 arknights 就能接 E17；第 6 批審視者＋watch；第 7～8 批 kernel；第 9 批工具權限與定義樹。**E15、E16、A6 這輪不做**（要試驗場做滿三個地點、有真的 kept 輪才驗得了）。最大風險兩個：第 2 批改格式與第 3 批搬 `observed.py` 會讓正在跑的試驗場斷掉，解法是「同 commit 附一次性改檔腳本、交棒檔寫清楚、arknights 隊長挑空檔跑一次」；第 7 批動 C++ kernel 會影響正在跑的 llm kernel，解法是「建好不裝、arknights 隊長說可以才重啟」。跟原則有衝突的三處（R8 塞進 promote、E1 的 `calls` 跟 N-68 的 `counter_calls` 不同名、E5／T5 讀子帳）下面都給了做法，不用再問。

## 一、位置與名字（簡報說「待定」的，這裡定）

| 東西 | 放哪、叫什麼 | 理由 |
|---|---|---|
| measure | `lib/aos/measure/`（含 E8 門、T6 consistency） | 它量的是「定義」，跟 `aos_json`、`judge`、簡報已排的 `defs`、`llm_forward` 同類（lib/aos＝對 aos 自己的東西動手）；`lib/agent/` 留給 agent 管自己（memory、thought、agents、self_tools）。 |
| promote／rollback | `lib/aos/promote/`、`lib/aos/rollback/` 兩個工具夾，共用一個小模組 | 腦看到兩個動詞最直觀（C-54 好懂）；rollback 本質是「把 `.prev/` 換回來」，共用碼很短。 |
| watch | `lib/aos/watch/`，純腳本、不用 LLM | C-22 能寫死的換成程式；E13 的判準是算術（任一門不過→退；3 個 case 平均貴 >10%→退），做成工具審視者叫它，判準改在工具的 `_metainfo.json#/rules`，不改 prompt。 |
| metainfo_check、shell_report | **改放 `lib/aos/`**（簡報寫 lib/agent） | 同上理由：它們檢查的是定義的自稱與它的帳，不是 agent 自己的記憶；同類排一起（C-54）。 |
| review.json、watch.json | `$AOS_WS/reviews/<定義名>/<ISO 時間>/` | 不進定義夾：ad-5 要定義樹能整批抽出去用在別的遊戲，定義夾裡不能混跑的紀錄；複數夾裝同類（C-54）。 |
| 前版 | `<定義>/.prev/`（簡報原案） | 退回只看自己旁邊，不跨層找。 |
| case 夾 | 新頂層 `proto8/cases/<名>/`（`box-probe`、之後 `review-poshan`） | 它是量用的考題資料，不是 lib 也不是 templates；複數名。 |
| 子帳抄本 | 自己 stack 小格內 `observed/<子名>/`，**不進 agent 定義夾** | ltn-5「stack 照刪、刪前抄子帳」：stack 一刪就清掉，等於 te-2 的定期清理；repo 與試驗場 `.gitignore` 加 `observed/`、`observed.jsonl`。 |

## 二、分批（串行，一批一個 commit；gpt 只照圖施工，圖＝每批的「做什麼」＋簡報該步的內容）

### 批 1：雜活清場（R2、R3、R4、R6、R7、E10）

- 做什麼：五件晚審待辦照簡報 R 節；E10 `memory find` 認 tag（節點 `tags`、夾 `_tags.json`，多 tag 交集）、`read "a/b#/c/1"` 回 JSON 指標處、`_tooldef` 補寫法。
- 完成判準：`py/daemon_ctl` 的 prune 原始碼裡沒有 `/proc`；`stopping` 的 proc 送 `sleep` 後 state 顯示 `stopped`；`agents ask` 原始碼沒有秒數上限、等法與 `thought/_entry:133` 同形；`locking.py` 不讀 `AOS_TICK`；`rm /` 回 `PathBad`；手做一個含 `tags` 的節點與一個 `_tags.json`，`memory find --tag a --tag b` 只回交集，`read "x/y#/c/1"` 回該指標處的值，指標不在回 `PathBad`。
- 風險：低。E10 的 `#/` 若跟現有 `aos_json` 指標寫法重複，直接 import 它的解析、不另寫一套（KISS）。

### 批 2：`_metainfo` 改格式（E1、E2、T2、A1、A2）

- 做什麼：`lib/metainfo.py`（讀 `cost`／`timeout_ms`、`eval_cost` 只做 `cal`，拒 `__`／import／屬性）；全 repo 35 份改 `time_ms.val→cost.time_ms`、`time_ms.max→timeout_ms`；act.py、aos-mcp 改讀 `timeout_ms`；五支任意執行工具加 `arbitrary_exec: true`；範本 `interfaces.json` 加 `memory`、範本加 `_metainfo.json`。**改檔用一支一次性腳本，腳本進 commit（`wf/tools/metainfo_migrate.py`），給試驗場再跑一次。**
- 完成判準：`grep -rl '"time_ms"' proto8 --include=_metainfo.json` 只剩 `cost` 底下的；`python3 -c` 叫 `eval_cost({"cal":"min(4000+in_bytes*1.2, 9e6)"}, {"in_bytes":1000})` 得 5200，`{"py":"..."}` 回「沒有估值」（None），`{"cal":"__import__('os')"}` 回 `CalBad`；手設一個 `timeout_ms: 1000` 的工具跑 `sleep 5`，act 格在 1 秒多殺掉並回逾時；`metainfo_migrate.py` 對同一棵樹跑兩次結果一樣（冪等）。
- 風險：**高（撞試驗場）**。試驗場的工具是捷徑引用 lib，act.py 一換，試驗場自己寫的 `_metainfo.json` 還是舊格式→逾時變成「沒設」。緩解：N-68 本來就不強迫有 metainfo，所以沒 `timeout_ms`＝不逾時，不會炸、只會沒上限；commit 後在交棒檔寫「跑 `metainfo_migrate.py ~/code/playground-ak`」，arknights 隊長在兩個地點之間跑。

### 批 3：帳（E3、E4、E5、T1、K9）

- 做什麼：`observed.py` 搬成 `lib/observed.py`，首寫補 `self` 行（含 `llm_kernel`）；act 的 `tool` 行加 `def`、`stack`；`call(name, target, stdin)` 給腳本記帳；thought／agents 收子 agent 前抄子帳到自己小格 `observed/<子名>/`、`tool` 行帶 `child`；bash／run_python 記 `cmd` 行，沒 `AOS_STACK` 不記，寫失敗 `LogFailed` 不跑；範本 `interfaces.json` 加 `aos-observed`；`.gitignore` 加 `observed/`、`observed.jsonl`。`templates/agent-fsm/observed.py` 刪掉，不留轉接（不做相容）。
- 完成判準：跑一隻範本 agent 叫一次 bash、一次子 agent（子再叫一次 bash）：父 stack 的 `observed.jsonl` 第一行 `kind: self` 且有 `llm_kernel`；bash 那行 `kind: tool` 有 `def`、`stack`；bash 自己小格有 `kind: cmd` 行且 `exit`＝內層碼；父的 `observed/<子名>/observed.jsonl` 存在且裡面含孫的 `cmd` 行；`AOS_STACK` 不設跑 bash，沒有檔也沒有錯；`AOS_STACK` 指到唯讀夾，退碼非 0、stderr 一行 `LogFailed`。
- 風險：**高（E3 搬檔）**。試驗場若有 `from observed import` 或捷徑指到範本那支，會立刻斷。緩解：commit 前 `grep -rn observed ~/code/playground-ak --include=*.py -l` 列出來寫進交棒檔；試驗場的改接是 E17（arknights）。E5 讀子帳是上層看下層，只准經 `interfaces.json` 的 `aos-observed` 宣告找帳的路徑，不准猜路徑（C-52「可認公開介面」）。

### 批 4：量（E7、E8、T6、E14）

- 做什麼：`lib/aos/measure/`：讀 case 夾、跑 `repeat` 次、翻帳成 `tree`、根成本＝子成本加總、`size_bytes`；門：內建逐 byte 比對＋自訂比對器（`min_score`），比對器的帳記 `check.cost`；`consistency`（`samples[1..]` 各比 `samples[0]`，三樣分開報）；`lib/aos/metainfo_check/` 回 `close`／`off`／`unclaimed`（0.8～1.25 算 close）。measure **只印 JSON 到 stdout、不寫檔**，寫到哪是叫它的人的事（C-52）。
- 完成判準：手寫 `cases/smoke/`（目標 `lib/base/math`，兩題有固定答案）：`measure --repeat 3` 的 stdout 是一份 JSON，`tree` 根 `cost.time_ms` 等於子加總、`samples` 有 3 個、`passed: true`；把一題的 expect 改錯→`passed: false` 且列出哪題；指定一支「永遠回 0.5」的自訂比對器＋`min_score 0.6`→不過，且輸出有 `check.cost`；`consistency` 三個分項都在；對一個 `cost.time_ms` 寫 10 但實測 1000 的定義，`metainfo_check` 回 `off`，沒寫的回 `unclaimed`。
- 風險：中。measure 要起小格跑 case，走的是 aos-exec 與 `call()`，不自己 fork 程序（否則帳記不到）。case 夾格式（`input`、`expect`、`check?`）這批定死，寫進 `cases/README.md`，之後 E9、T7 都照它。

### 批 5：換上（E11、E9）

- 做什麼：`promote`：副本換上正式定義、前版留 `.prev/`，有 proc 正用著回 `DefBusy` 什麼都不動（判「正用著」只讀 daemon 的公開 `procs_state.json` 窗，不讀 pid、不讀 `/proc`，與 N-17 同調）；`rollback`：`.prev/` 換回來、`.prev/` 清空；`templates/judge/`：agent 型比對器，讀 expect／got／input 印 `{score, diff, why}`，走批 4 定的比對器契約。
- 完成判準：對一個定義 `promote <副本>`→正式夾內容＝副本、`.prev/` 是舊的；再 `rollback`→內容＝舊的、`.prev/` 空；先起一隻 proc 用著它再 `promote`→退碼非 0、stderr `DefBusy`、兩夾都沒動；`measure --check templates/judge` 跑 `cases/smoke` 一題答對一題答錯，judge 的 `score` 一高一低、`why` 非空，且 `check.cost.token` 有數。
- 風險：中。judge 要真的叫 LLM（吃額度），判準只跑 2 題、用便宜模型；promote 在試驗場的用法是 E17，這批只在 repo 內的測試 ws 驗。

### 批 6：審視者與盯（E12、E13、R8）

- 做什麼：`templates/reviewer/`：`system.txt` 一輪七步、`ladder.json`、`downgrade` 全自動、`fix`／`split` 只開處方；產 `$AOS_WS/reviews/<定義>/<時間>/review.json`；`lib/aos/watch/`：讀同夾歷史 review.json＋換上後 measure 結果，品質任一門不過→叫 `rollback`，成本看 3 個 case 平均貴 >10% 才退，不滿 3 個只記不退；**R8 做成 `ladder.json` 的 `promote_by: "self" | "claude"`**，gpt 腦的審視者定義寫 `claude`，它到了要換上那步只寫 `review.json#/pending_promote`、不叫 promote。
- 完成判準：拿批 5 的定義與 `cases/smoke` 跑審視者一輪（便宜模型）：產出 `review.json` 有七步各一節、`action` 是 `downgrade`／`prescribe` 之一；`downgrade` 那條走完有 `.prev/`；`watch` 對手造的三份 review.json（成本 +5%、+15%、+15%）輸出 `keep`，四份平均 +12%→輸出 `rollback` 並真的退了；手造一份品質門不過→立刻 `rollback`；`promote_by: claude` 的審視者跑完 `.prev/` 不存在、`pending_promote` 有值。
- 風險：**高（額度）**。真跑一輪審視者要多次 LLM 呼叫；判準裡只跑一輪、其餘用手造 review.json 驗 watch。審視者自己正在跑時不會被換（C-84）：promote 的 `DefBusy` 已擋。

### 批 7：kernel 嵌套 C++（K1、K2、K3、K4）

- 做什麼：aos-llm-kernel：`request.json` 頂層 `priority {level, deadline}`（deadline＝min(信 deadline, 掛上時間＋timeout_ms)，epoch 秒；排程仍只看 `level`）、`proc.json` 記 `seen_at`；收成品 stdout 有 `child` 就進 ledger、回信拿掉；ledger 每行加 `seen_at`／`code`／`child`／`switched`；退非 0 而 `reply.json` 是合格 `{"error":{"code","msg"}}` 原樣回；aos-llm `ask --full`／`recv --full` 成功加 `letter`、失敗 stdout 印錯誤 body。
- 完成判準：cmake build 過；用 `llm_fake` 當 endpoint 寄一封有 `deadline` 的信，kernel 收下後 `request.json` 有 `priority.deadline` 且等於較小那個；endpoint 印含 `child` 的 stdout→回信無 `child`、ledger 該行有 `child`、`seen_at`、`code: 0`；endpoint 退 2 並寫合格 `reply.json`→寄信方收到同一份 error、碼 2；`aos-llm ask --full` 成功輸出含 `letter`，失敗 stdout 是 error body。
- 風險：**高（正在跑的 kernel）**。試驗場 llm kernel 是常駐 daemon，裝新二進位＝要重啟。緩解：這批只建、只在 repo 的測試 kernel 驗；交棒檔寫「arknights 隊長在地點之間重啟」，K11 改接歸他。

### 批 8：轉交與多包（K5、K6、K7、K8）

- 做什麼：`lib/aos/llm_forward/`（必填 `to`、`kernel`；只對子行程設 `AOS_LLM_KERNEL`；priority 原樣帶；成功把 `letter` 換成 `child`；下層錯原樣印、同退出碼）；kernel 認 `backends.<名>.{slots,max_packs}` 與包的 `backend`、`queue.json` 加 `backends`、換包第一封 `switched: true`；同級黏著同一包；範本 `kernel/llm-team/`、主 kernel 範本本機包掛 `backends`、kernel 定義夾加 `interfaces.json`（`aos-ledger`）。
- 完成判準：兩層 kernel（上層 endpoint＝llm_forward→下層），寄一封上去，下層 ledger 有那封、上層 ledger 該行 `child` 指到下層；下層 endpoint 退 3→上層寄信方收到同 error、碼 3；設 `backends.local.slots: 1`、兩個包都 `backend: local`，各寄 3 封→ledger 顯示先做完同一包再換、換包那封 `switched: true`，且任何時刻只有一個包在跑；`llm-team` 範本用 `aos-grow` 長出來就能起。
- 風險：中。黏著與互斥是排序邏輯，判準用 `llm_fake` 加 sleep 做可觀察的順序；本機 LM Studio「一次一模型」就是 `slots: 1`，不另加旗子。

### 批 9：工具權限與定義樹（T4、T5、T7、A3、A4、A7）

- 做什麼：`cmd/aos-sandbox/examples/bash-boxed/` 改讀自己 `_metainfo.json#/sandbox`、底層縮小、白名單逐支放；`lib/aos/shell_report/` 回 `open`／`boxed`／`none`、列 `arbitrary`、指令歸形狀；`cases/box-probe/`＋比對器；`agents new` 加 `reason`／`review`，寫 `lineage {from, reason, review?}`；`lib/aos/defs/` `ls --match`／`dup`／`refs`／`check`；`defs/README.md` 處方頁（specialize 四步、retire 四步）。
- 完成判準：bash-boxed 跑白名單外指令退非 0、白名單內可跑，白名單只在 `_metainfo.json#/sandbox`；對三隻手造定義（有 bash、bash-boxed、都沒有）`shell_report` 分別回 `open`／`boxed`／`none`；`measure` 跑 `cases/box-probe` 對 open 定義不過、對 boxed 定義過；`agents new --reason x` 後新定義 `_metainfo.json` 有 `lineage.from` 與 `reason`；`defs dup` 對兩隻只差 prompt 的定義報同質（ad-2 差一軸就算不同質）、`defs refs` 列出誰引用誰、`defs check` 對缺 `interfaces.json` 的回非 0。
- 風險：低～中。sandbox 改法只動 examples，不動 aos-sandbox 本體；A5、T9 的審視者判準（specialize／differentiate／retire／merge_into、extract／box／unshell）跟著這批**只加進 `ladder.json` 與 system.txt 當處方**，不加自動動作——自動要等 E15。

## 三、這輪不做的

| 步 | 不做理由 |
|---|---|
| E15、A6 | 審視者放手寫副本要「做滿三個地點」（C-84），試驗場第三輪才在做第 7、8 個地點的 kb，但審視者還沒上線盯過任何一個；沒 3 個 case 的 review.json 就驗不了。等批 6 上線、arknights 跑過三個地點再排。 |
| E16 | 好答案要從真 review.json 被 watch 轉正（kept）的輪挑（evo-C），現在一輪都沒有。 |
| T9 的自動 `box`／`unshell` | 依賴 T5、T7 與 E13 都跑過真資料；批 9 只放處方。 |
| K10、A9、L 的條文補寫 | 是 opus 的文件活，不占 codex 批；opus 在批 3（aos-observed 四種行）、批 4（case 與比對器契約、measure 格式）、批 6（review／watch 格式）、批 8（K10）各 commit 後補一次，跟程式同步。 |
| 想法 16 的「complexity」抽象指標 | 使用者自己說留第四、五輪。 |

## 四、跟原則的衝突與原則推不出的方向

1. **R8 塞進 promote 違反 C-52**（簡報 R 節「接進 E11 promote」）。promote 要知道「這份副本是 gpt 腦改的」就得認下層身份；C-52 加嚴「不認身份、可認公開介面」。建議（已排進批 6）：換成審視者定義自己的 `ladder.json#/promote_by`，gpt 腦的審視者定義寫 `claude`，自己不叫 promote、只留 `pending_promote`，由 Claude 審視者或隊長叫 promote。promote 本身不看腦。
2. **E1 的 key `calls` 跟 N-68 不同名**。N-68 已定 `token`／`counter_calls`／`time_ms`（計數一律 `counter_`，C-54）。簡報寫 `calls` 是筆誤，批 2 一律用 `counter_calls`；`eval_cost` 變數名同理（`in_bytes`、`counter_calls`）。
3. **E5、T5 讀下層的帳**是上層看下層。不算衝突，因為 ltn-5 與 `aos-observed` 介面就是 C-52 說的「另外的機制」；但施工只准照 `interfaces.json` 宣告的路徑找帳，不准硬編 `$AOS_STACK/observed.jsonl` 的相對位置去猜子的 stack。
4. **K5 透明轉交（下層錯原樣印、同退出碼）是 C-53 的例外**（kn-5:B 使用者已裁）。程式照做；opus 在 K10 把它記進 C-52 例外表當 ⑥，不然下次審會被當違規。
5. **E2 不做相容 vs 同時在用的試驗場**。原則（11-05「一律當成沒有舊版」）沒錯，衝突是時間差。做法見批 2、3：同 commit 附一次性腳本、交棒檔列出會斷的檔、arknights 隊長挑地點之間跑；本線不去改試驗場。
6. **watch 的 3 個 case 平均**要跨好幾輪才湊得到；中間單點變貴不退（E13 原案）。原則推不出「不滿 3 個算什麼」，定：只記不判。
7. **measure 寫不寫檔**：原則推不出。定：不寫，只印 stdout（C-52 每層只管自己；寫到 `reviews/` 是審視者的事）。
8. **promote 怎麼判「正用著」**：N-17 不開 pid 例外，定只讀 daemon 公開的 `procs_state.json` 窗（跟 no-pid P7 同一招）。沒 daemon 的 ws 就當沒人用。
9. **`cases/` 要不要進 repo**：定進（`proto8/cases/`），因為 E9、T7 的判準都靠它；試驗場自己的 case 放試驗場。
10. **lib/aos 與 lib/agent 的界線**：簡報把 `metainfo_check`、`shell_report` 放 lib/agent，這裡改放 lib/aos（理由見一）。這是 fable 代定，opus 覺得 lib README 的分層說法不合可以翻，但要在批 4 前翻。

## 五、每批交棒要寫的

每批 commit 後在 [arknights-kb 交棒檔](../arknights-kb/README.md) 補一行：批號、哪些介面已可用（批 2 後 `timeout_ms`＋改檔腳本；批 3 後 `lib/observed.py` 與 `aos-observed`；批 4 後 `measure`；批 5 後 `promote`／`rollback`／`judge`；批 6 後 `reviewer`；批 8 後 `llm_forward`）、哪些試驗場檔會斷。commit 前照鐵律 3 跑 `python3 wf/tools/codemap_gen.py --apply`；程式輸出英文；新工具每夾 README 第一行 NAME 一句話。
