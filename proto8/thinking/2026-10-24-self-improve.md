# 2026-10-24 自我改進流程：給目標與判準，跑、判、沒達到就改

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜程式 [demo/self-improve](../demo/README.md#self-improve自我改進流程10-24)｜測試 `proto8/tests/test_self_improve.py`｜試驗場 `~/code/try/self-improve/`

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。這份是**嘗試性質**，下面的決定全是頂層照推薦定的（使用者 10-24「都按建議做」），可翻案。相關條文：[C-42](../CONCEPTS/05-agent.md)（自我迴圈改進的閉環）、[C-52、C-53、C-54、C-56](../CONCEPTS/01-設計理念.md)、[C-64](../CONCEPTS/01-設計理念.md#檔案權限10-16-使用者定)（借 Linux 權限）、[C-65～C-67](../CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)（stack 與工作區）、[N-43](../NORMS/01-總則.md)（結束碼 0／10／其他）、[P-41](../CONVENTION/02-題目stack停錯腦.md)（腦的工具）。

## 使用者原文（10-24，逐字）

- 前文：「然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試」
- 本題：「還有，我想要一套自我改進流程，也就是給了一個目標，和我們預想達成的結果，然後去跑這個函數，然後如果沒達到結果，那函數自己(或另一個函數)就會去改進函數。」
- 頂層轉來（要拍板的小題）：「我現在沒空管這些小事，都按建議做」——下面一律照推薦定，標「照推薦定、可翻案」。

## 考古：以前說過、這次照著做的

- 10-11 晚口述 [restart 3g.13](2026-10-11-restart/05-第三輪口述後段.md)：aos 的每一樣都是 shell 指令、都是 agent 的工具，「所以自我迴圈改進的基礎就這麼閉環、閉合了」（C-42）→ 這次改進者就是一隻 agent、拿工具改另一個資料夾程式。
- 10-13 [kernel／agent](2026-10-13-kernel-agent/01-使用者原文.md)：目的是「讓 agent 有足夠的自省性——能自己審理自己……讓自己變得更好，也就是自我改進」；「後續做自我改進時，會用 loop＋狀態切換，方便自省」、「預期都以 inst 為基礎」；結論「每步狀態落檔……方便自省、zip／git」→ 外層 aos-loop＋內層 aos-fsm 三格、每一版落一個資料夾。
- 10-14 [json-entry 08](2026-10-14-json-entry/08-fsm拍板與改寫.md)：改表或方法檔下一次生效是「自我改進入口」，「改壞靠 git」→ 這次改成每一版都拍快照、改壞了從最好那版重來，不靠 git。
- proto7-2 學徒實驗（[decisions 10-09](../../proto7-2/notes/decisions-2026-10-09/04-r4.md)）的教訓：審查太嚴擋掉不該擋的、訊息沒說清楚哪裡錯，改進就學不到東西 → 判定的回饋寫清楚「哪組、期望什麼、實際什麼」。

## 做了什麼

```
proto8/demo/self-improve/       資料夾程式：aos-exec --ws <交辦的工作區> proto8/demo/self-improve
  _entry                        exec aos-loop loop.json
  loop.json                     {"exec": "fsm.json"}（不設 max：預算由 judge 管，見代定 6）
  fsm.json                      run → judge → improve → run，三格都是內嵌單子（python3 xxx.py）
  run.py  judge.py  improve.py  三格；common.py 共用（佈局、版本、預算、在暫時複本上跑一次）
  improver/                     改進者：一隻 agent（從 agent-pip 照抄：工具出錯回給腦、不停），多記 token 用量
    tools/read、write、edit     符號連結到 demo/pi-tools（不改它的檔）
    tools/try_run               自己的：拿參數與 stdin 在 target/ 的暫時複本上跑一次
```

**交辦的工作區**（使用者準備的）：`goal.txt`（目標，自然語言）、`target/` 或 `target.json`（要改的函數，aos 資料夾程式或單檔；原版永遠不動）、`judge/`（判準）、`budget.json`（選填）。**成果**：`out/best/`（最好的一版）、`out/report.txt`（每一版從哪版改來、幾分、改了哪些檔幾行、改進者說了什麼）、`out/result.json`。

**判準兩種**（`judge/cases.json` 優先）：
1. **一組例子** `judge/cases.json`：`[{"args", "stdin", "stdout", "code"?, "hidden"?, "timeout_ms"?}]`，每組 `aos-exec 函數 參數...`、餵 stdin、比 stdout（行尾空白、頭尾空行不計），有寫 `code` 也比結束碼。
2. **一支檢查程式** `judge/check`（aos-exec 跑得動的都行）：環境變數 `IMPROVE_TARGET`＝函數暫時複本的路徑，退 0＝達成；它的 stdout 就是給改進者看的回饋（要透露多少由寫檢查的人決定）。

**一輪**：run 格在函數的暫時複本上跑（拍下來的那版不會被函數自己改到；函數拿到乾淨的 `AOS_*`、空的暫時工作區）→ judge 格寫 `verdict.json`（分數＝過了幾組）→ 沒達成就 improve 格：從**最好的那一版**開新的一版，改進者的工作區只有 `new/task.txt`（目標、這版的判定、看得到的失敗例子、之前各版的分數）和 `target/`（複本）→ 改完只收 `target/`、拍成新的一版、寫 `diff.txt` → 回 run。

**結束碼**（N-43）：judge 達成退 10 → loop 以 0 收工；預算用完退 2 → loop 以 2 結束、stderr 一行 `self-improve: BudgetSpent …`；改進者失敗 `ImproverFailed` 退 1（停在 improve，再跑一次從頭改這一輪，半成品搬到 `$AOS_STACK/failed/`）。fsm 只有格退 0 才往下走，所以達成或預算用完之後再跑，停在 judge、說一樣的話；改大 `budget.json` 再跑就接著改。

stack 佈局：`$AOS_STACK/versions/vNNN/{target/, version.json（from、hash、same_as、ignored）, runs.jsonl, verdict.json, diff.txt, answer.txt, improve/{ws/, stack/}}`、`started_at.txt`、`current.txt`、`failed/`，加上 fsm 的 `state.txt`、`trace.jsonl`。

## 決定（照推薦定、可翻案；使用者 10-24「都按建議做」）

1. **改進者＝另一個函數**（`improver/`，一隻 agent），不是函數自己。「函數自己改自己」列在選項。
2. **判準做兩種：例子、檢查程式**；LLM 判官列在選項（沒做）。
3. **防作弊靠「改進者看不到判準」**：判準在交辦的工作區、改進者的工作區在 stack 深處只有任務與複本；read／write／edit 出不了自己的工作區（pi-tools 擋，符號連結也算）；**不給 bash**。例子可以標 `hidden`：失敗時只說「另有 k 組看不到的沒過」，防止對著例子寫死答案。
4. **只收 `target/`**：改進者在別處寫的東西不採用，記在 `version.json` 的 `ignored`、報告裡寫出來。
5. **每一版都留**（`versions/vNNN/` 拍下來就不再改），**新的一版從最好的那版改**——同分取最早的（沒變好就回原本那版重來；`out/best/` 也不會換成同分的新寫法）。改回跟以前某版一模一樣時記 `same_as`、任務說明裡標出來（防震盪）。
6. **預算三種**（`budget.json`，沒寫的照預設）：`rounds`（改進幾輪，預設 5；中途失敗的也算一輪）、`elapsed_ms`（從第一次跑起算，預設 30 分鐘）、`tokens`（改進者問腦的 `usage.total_tokens` 加總，預設 50 萬）。每次 judge 完檢查，任何一種到了就停；loop 不設 `max`（滿了會以 0 結束、跟達成分不出來）。單格另有 `timeout_ms`：run 15 分鐘、judge 1 分鐘、improve 30 分鐘；每組例子預設 10 秒、檢查程式 5 分鐘。
7. **模型**：改進者 `.env` 寫 `chatgpt-gpt-6-luna-low`（同 agent-dan），腦的位置照舊由叫的人給 `AOS_BRAIN_URL`，一路傳下去。
8. **名字**（C-54）：資料夾 `self-improve` 跟 demo 其他資料夾一樣用連字號；格名 `run`／`judge`／`improve`；錯誤代號 `BudgetSpent`、`ImproverFailed`、`JudgeMissing`、`JudgeBad`、`TargetMissing`、`BudgetBad`、`StackBad`、`WsMissing`、`StackMissing`、`LaunchFailed`、`SandboxMissing`（10-24 晚加）；環境變數 `IMPROVE_TARGET`。
9. 改進者從 agent-pip 照抄（不是 agent-dan）：工具出錯（edit 找不到原文、路徑出界）要回給腦，停下來重跑只會卡在同一個呼叫。只改三處：錯誤行的名字、假腦直接答不改檔、每次問腦把 `usage` 記進自己的 `usage.jsonl`。
10. **被改的函數預設關進沙箱**（10-24 真腦實測前定、代定可翻案；條文在 [sandbox S11、S12](2026-10-24-sandbox.md)）：工作區沒放 `sandbox.json` 就用 `demo/self-improve/sandbox.json`，寫 `false`＝不關；找不到 aos-sandbox／bwrap＝`SandboxMissing`。

## 跑一次（10-24，`~/code/try/self-improve/`）

- **LiteLLM 沒開**（localhost:4000 連線被拒、機器上沒有 litellm），所以**用假腦劇本跑**（`fake_brain.py`：一個 OpenAI 相容 server，照「改進者會怎麼做」排三輪；**不是真模型的表現**）。真跑的指令在試驗場的 `README.txt`。
- 題目：`wordfreq`——從 stdin 讀英文、印前 N 個最常出現的字。原版四個錯：N 沒預設（不給參數就當掉）、分大小寫、標點黏在字上、同次數沒照字母排。判準 8 組例子（5 組看得到、3 組藏起來），預算 5 輪。
- 結果（結束碼 0，約 4 秒，假的 token 數 12178）：

| 版 | 從哪版改 | 分數 | 改了什麼（改進者自己說的） |
|---|---|---|---|
| v000 | 原版 | 1/8 | — |
| v001 | v000 | 4/8 | N 沒給時預設 3、讀進來先轉小寫（edit 兩行，try_run 試過） |
| v002 | v001 | 1/8 | 改用 regex 切字、同次數照字母排——但用了 `re` 沒 import，沒試跑就交，整支當掉（改壞了） |
| v003 | **v001**（v002 比較差，丟掉） | 8/8 | import re、`[a-z']+` 切字、排序鍵（次數大到小、字母），try_run 試過 |

  `out/best/` 是 v003；工作區的原版 `target/` 沒動；四版都在 `ws-fake/.stack/versions/`。

## 挖出的邊緣狀況（還沒問使用者）

- **永遠達不到**：只會停在預算（輪數、時間、token 任一）；退 2、`out/best/` 是最好那版。判準本身矛盾（兩組例子互斥）也是這樣，流程看不出「判準有問題」。
- **改壞後更差**：新的一版從最好的那版改，壞的那版留著不用（實跑的 v002）。但改進者每次只拿到最好那版，看不到壞掉那版的程式碼，只看得到分數；同一種壞法可能再犯。
- **判準太鬆被鑽漏洞**：例子只比 stdout，函數照例子寫死就過。`hidden` 只擋得住「看得到的例子寫死」；藏起來的例子少、或判準本身只測一小部分，還是會過。檢查程式寫得鬆也一樣。
- **函數跑起來能讀到判準**：被改的是程式，run 格和 try_run 都會真的跑它，它能讀這個使用者讀得到的任何檔（包括 `judge/cases.json`、甚至用絕對路徑去找）。改進者的工具碰不到判準，但改進者可以**寫一支會去偷看判準的程式**。真要擋得靠 Linux 權限（C-64：判準只給 judge 那個使用者讀、函數用另一個使用者跑）或 bwrap 一類沙箱；這次沒做。
- **改進者改到不該改的**：只收 `target/`，其他地方寫的不採用；但 `target/` 裡可以放任何東西（例如一個符號連結指到判準——pi-tools 的 write 做不出符號連結，try_run 跑的程式做得出來）。改進者也可能把函數改成「改自己」的程式，run 格每次在暫時複本上跑，所以拍下來的版本不會被改到。
- **成本爆掉**：token 預算只算改進者問腦的，函數本身若也叫 LLM、檢查程式若叫 LLM，都沒算進去；一輪裡改進者自己的 loop 另有 `max` 120 次與 improve 格 30 分鐘逾時兜底。時間預算只在每次 judge 完檢查，正在改的那一輪不會被中途打斷（最多超出一輪的時間）。
- **震盪**：A → B → A。同分取最早的那版當底，加上 `same_as` 標出繞回去了；但「分數一樣、寫法不同」的兩版之間來回，現在只能靠任務說明裡的各版分數讓改進者自己看出來。
- **改進者中途失敗**：停在 improve、退 1；再跑一次會重開這一輪（半成品搬到 `failed/`、算一輪、token 照算）。腦一直連不上就一直停在這裡，不會自己重試。
- **判準跑到一半被改**：例子組數跟上次跑的不同＝`StackBad`（請重跑那版）；組數相同但內容改了，舊版的分數不會重算，新舊版之間的比較就不公平。
- **函數有副作用**：每次在空的暫時工作區跑，寫到工作區的東西跑完就丟；它要是寫到別的絕對路徑（家目錄、網路），流程管不到。同時跑兩份 self-improve 用同一個 stack 會互踩（同 P-18）。
- **假腦**：沒設 `AOS_BRAIN_URL` 時改進者直接回「沒改」，每一輪都跟原版一模一樣，跑到預算用完——demo 能走完，但不代表會改進。

## 選項（沒做）

- **函數自己改自己**：函數資料夾裡多一個 `improve/`（或在 `_metainfo` 寫改進者的位置），improve 格改成 `aos-exec` 那個。代價：改進者跟被改的東西在同一個資料夾，它也能改到「改進者」本身，判準的隔離更難；要分清楚哪些檔是「函數」、哪些是「改進的方法」。
- **LLM 判官**：`judge/rubric.txt`＋一個問腦的檢查程式（就是第二種判準的一支特例：讀 `IMPROVE_TARGET` 的輸出、照評分表問模型、分數過門檻退 0）。不用改流程，只要寫一支 check；但判官本身會被「說服」、同一版每次分數不同，要多跑幾次取中位數，token 也要算進預算。
- **分數不只過或不過**：檢查程式現在只有 0／1；可以讓它多寫一個分數（例如 stdout 最後一行 `score: 3/5`），排「最好的一版」更細。
- **給改進者看更多**：各版的 diff 與失敗原因摘要（現在只給分數），可以少犯同樣的錯；代價是 token 變多。
- **真的隔離**：判準檔權限只給 judge、函數與改進者用另一個 Linux 使用者或 bwrap 跑（C-64）。

## 未決

- 上面「選項」都等使用者要不要。
- LiteLLM 開了以後拿真模型跑同一題（`python3 setup_ws.py`、`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ws <repo>/proto8/demo/self-improve`），看真模型幾輪達成、會不會對著例子寫死。
