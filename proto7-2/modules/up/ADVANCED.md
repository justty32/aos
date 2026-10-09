← [up](README.md)

## 操作與契約

Python 3.11+、純標準庫；在 repo 根跑。缺工作流模板時先裝
`git clone git@github.com:justty32/workflows.git ~/repo/workflows`，或設 `AOS7_WF_HOME`。

`--help` 只列三個指令（起、ask、status）；下面這些照樣能用，只是不列：

- `aos7-up /tmp/aos/bob -d`：背景跑，確認 bob 被叫醒後印三行離開。
- `aos7-up stop /tmp/aos/bob`：停整個房子的心跳與它起的全部任務，包含其他 node；不刪任何檔。
- `aos7-up /tmp/aos/real --model chatgpt-gpt-6-sol-high -d`：真 AI。
- `aos7-up /tmp/aos/bob --interval 0.5 --early`：改心跳節拍（見下「心跳節拍」）。
- `brain`：心跳替 node 起的任務入口（argv 見下），人不直接跑。

### 心跳節拍：`--interval`、`--early`／`--fixed`

預設每 1 秒一回合、固定節拍（回合裡的事做完了也等滿 1 秒）。有人要固定、有人要快，可以自己設：

- `--interval 秒`：每回合間隔，0.01～86400 秒，可帶小數，例如 `--interval 0.5`。
- `--early`：回合裡起的事都做完就提早進下一回合（核心 `early_tock`）；`--fixed` 改回固定節拍。兩個只能給一個。

```sh
aos7-up /tmp/aos/bob --interval 0.5 --early   # 快
aos7-up /tmp/aos/bob --fixed                  # 改回固定，間隔沿用 0.5
```

給過的值記在 `up.json`（`interval_ms`、`early_tock`），之後重跑不帶參數就沿用；從沒給過就不寫這兩欄、也不碰 `timeline.json`（核心預設 1 秒固定）。給過以後，每次 up 都把這兩欄寫回 `<node>/.aos/timeline.json`（其他欄保留），手改 timeline.json 的這兩欄會被蓋回——要改就用 up 的參數。心跳已經在跑時改節拍，下一回合生效（up 會順便叫醒 node）。

快多少（2026-10-09 [EF2](../../notes/play/2026-10-09-real-ai/ef2.md) 量的作者工作「結算→結束」，離線平均）：1 秒固定 2.7 秒、1 秒＋`--early` 2.1 秒、0.5 秒固定 1.8 秒、0.5 秒＋`--early` 1.43 秒。代價：間隔短，心跳與常駐任務醒得更勤；`--early` 時回合中送來的 wake 不起作用，回合長短跟著工作走、不再整齊。

壞值（不是數字、超出範圍、`--early` 與 `--fixed` 同給）退 2、什麼都沒動。

### 真 AI：`--model` 填什麼

不給 `--model` 就是假 AI（不連網、不花錢、照抄你的信）。要真 AI：

先起你自己的 LiteLLM（OpenAI 相容端點，預設 `http://localhost:4000/v1`；別處設 `AOS7_LITELLM_URL`，要金鑰設 `AOS7_LITELLM_KEY`，見 [llmcall](../../packs/llmcall/README.md)）。

`--model` 填 **LiteLLM 設定裡的模型名**（它對外的 `model_name`），不是廠商原名；查有哪些：`curl -s http://localhost:4000/v1/models`。本機 2026-10-09 實測用過 `chatgpt-gpt-6-sol`、`chatgpt-gpt-6-sol-high`、`chatgpt-gpt-6-luna`、`chatgpt-gpt-6-astra`（[試玩紀錄](../../notes/play/2026-10-09-real-ai/README.md)）。

假 AI 起過的 node 不能改成真 AI（退 2），另起一個名字，例如 `aos7-up /tmp/aos/real --model chatgpt-gpt-6-sol-high`；真 AI 之間可換模型。
- 已有心跳只接上看；Ctrl-C 只停觀看，停心跳用 stop。入口自己起的前景心跳在 Ctrl-C／SIGTERM 後收掉。
- `ask`／`brain` 交給同目錄 `aos7_up_brain.main([子命令, …])`（ask 在 `aos7_up_ask.py`，回信邏輯與 prompt 在 `prompts/`）。

安裝只透過各包公開 CLI。brain 用 llmcall 必須有帳，因此保留 budget-llm。
compact 在工作簿變厚時自動整理。routines 只裝它的 keep 任務、不加任何例行列（表空就什麼都不做；之後 `aos7-routines add` 才有事）。跨包副作用一律由 up 做：各包自己不再裝任務、不替別人建 events/。

## 建了什麼、停了什麼

- `<node>/AGENTS.md`、`CLAUDE.md`、`.claude/`、`wf/`：工作簿模板與入口。AGENTS.md 是導入完成的標記，已有它就不再 init。
- `<node>/inbox/`、`tools/`：信箱與工作流工具；`<node>/events/`：信的提醒通道（mail 用）。
- `<node>/skills/`：三本技能連結與 `index.json`；已有同名項（含壞連結）不改。
- `<node>/budget/llm/`：grant、ledger 與帳的證據；假／真 AI 已開帳後不能互換，換名字另起。
- `<node>/.aos/`：`tasks.json`、`up.json`、`up.lock` 與核心執行證據。
- `<node>/llmcall/`、`brain/`、`compact/`：之後執行任務時產生。
- `<房子>/you/inbox/`、`you/events/`：人的回信箱與提醒通道。
- `<房子>/.aosd/`：心跳的鎖、紀錄、狀態與 `up-daemon.log`。
- 常駐程式：心跳一個，node 上 `budget-llm`、`brain`、`compact`、`routines` 四個 keep 任務（brain 的 argv 凍結為 `python3 <proto7-2>/modules/up/aos7-up brain <node>`）。

stop 收掉心跳與它起的全部任務，不刪任何檔；前景 `aos7-up <node>` 看到心跳被別處停掉時退 1，說「心跳被別處停掉了…再跑 aos7-up <node> 就接上」（從沒跳過才說「心跳沒跑起來」）。status 與 stop 的最後一行是「要收掉：…」：心跳還活著時先叫你在視窗 1 按 Ctrl-C（用 `-d` 背景跑的改用 stop），心跳停了只給 `rm -r`。房子裡只有 up 的 node、`you/`、`.aosd/` 時叫你「刪掉整個資料夾：`rm -r <房子>`」（會刪房子裡全部 node、`you/` 與 `.aosd/`），否則說「刪掉這幾個資料夾：…」；房子裡有別的東西時只列 `rm -r <node>`，房子裡沒別的 node（有 `.aos/` 的資料夾，不論是不是 up 起的）才加 `<房子>/you <房子>/.aosd`。

## 設定與重接

安裝與啟動拿 `<node>/.aos/up.lock`；up 自己寫的 JSON 都用暫存檔＋rename。
重跑只補缺的 grant、ledger、技能連結與任務，更新技能 index，保留原信件。
SIGKILL 心跳後重跑，核心接手收掉舊任務；不重新開帳。up 只在給過節拍時寫 timeline 的 `interval_ms`、`early_tock` 兩欄。

`<node>/.aos/up.json` 必須是完整物件：

| 欄位 | 意思 |
|---|---|
| `v` | 固定 1 |
| `node`、`house`、`name` | 絕對 node 路徑、上一層房子路徑、資料夾名 |
| `you`、`mail_root` | 固定人的名字 you、房子路徑 |
| `model` | 字串或 null；null 是假 AI；不給 --model 保留原值 |
| `litellm_url` | 環境變數 AOS7_LITELLM_URL 有設優先，其次舊值，再預設 http://localhost:4000/v1 |
| `budget`、`holder` | 固定 budget/llm、brain |
| `max_prompt_chars` | 每回合提示字數上限，預設 12000；先砍軌跡再砍技能全文，保留結案目錄 |
| `gateway` | llm.fake 或 llm.litellm，依 model 選 |
| `interval_ms`、`early_tock` | 可有可無：給過 `--interval`／`--early`／`--fixed` 才有；整數毫秒 10～86400000、布林；沒給沿用舊值 |

grant 固定 1000 萬 token，已有 grant 永不改。真 AI 同 gateway 可以換模型。
名字只准英數、`.`、`_`、`-`，不能以 `.` 開頭，you 留給人。

register 後最多等 15 秒（節拍超過 1 秒時多等那一拍；心跳已在跑時順便 wake），必須看到 node 的 round.json 回合號 ≥1 且大於開始前。
持鎖不是醒來的證據。自己起的心跳在交接前任何失敗都送 SIGINT，等 30 秒，逾時 SIGKILL。
前景觀看中中斷且收乾淨退 0；收尾逾時退 3，可能仍有工作在跑，下次 up 由核心接手。
子指令獨立 process group；中斷送整組 SIGTERM，等 5 秒再 SIGKILL，不留孫程序。
所有 Python 子程序使用 -B，不在程式目錄留 __pycache__。

status 唯讀，平常六行，只用新手五個詞（node、心跳、工作簿、信、技能）與白話。心跳行說「已叫醒 bob N 次」（N＝node 的回合數），停了說「共叫醒 N 次」與再起的指令；技能行附「AI 自己挑來用」。工作簿那行「最後記下」是最後一筆 STATE 去掉時間、信／call 的 id 換成信的標題（找不到標題寫「一封信」）、「回合」說成「步」；SESSION-LOG／WAIT_USER 有 open 行才接「還有 N 件事沒做完」，`aos7-wfnode check` 沒過才在那行尾加「工作簿有地方寫壞了（看哪裡：…）」，過了不提。AI 行沒設模型時寫「假 AI（不連網、不花錢，照抄你的信回你）」。信那行先說 node 一共收到幾封（REQUEST，含已辦完的）、回了幾封（含說卡住的）、正在辦、排隊幾封，再說人的信箱（`you/inbox`）有幾封回信還沒看、其中幾封要你決定、幾封說卡住了（有這兩種時附信箱位置「打開照信做」）。brain 正在等一筆不確定的 AI 回覆時，信那行下面多一行「卡住了：信「…」問了 AI，不確定 AI 回了沒，已等 X 秒；你不用動手，滿 L 秒 bob 會寄信到你的信箱說怎麼辦，再接著辦下一封」，這時共七行。AI 行的「來回共約 N 字」是 budget status 的 used（token 數，對中文約等於字數），讀不到印「來回字數不明」。

給人看的輸出不出現英文狀態詞：ask 的回信 DONE 不標、BLOCKED 標「卡住了」、NEEDS-USER 標「要你決定」、FAILED 標「沒辦成」；JSON 與信件欄位照舊是英文。

### brain 一封信跨回合

AI 每回合回三種之一：`回信：`（做完，回 DONE）、`繼續：`（這回合的成果，下回合接著做）、`要你決定：`（回 NEEDS-USER 結案）。一回合最多問一次 AI；第 k 回合的 call 是 `<信 id>-s<k>`（第 1 回合沿用信 id），被殺後重起照 llmcall 規則接同一個 call，不重問。

說「繼續」時，每回合記這些（重跑同一回合不重記），最後才寫 `brain/task.json`（信 id、下一回合、上回合停在哪、連續沒進展數、最近 8 回合的停在哪與成果前 200 字、挑到的技能）：

- `brain/last.md`：這回合的成果（最多 4000 字），下回合放進提示。
- `notes/journal.jsonl` 一行（`by`、`re`、`step`，拿 `compact/write.lock`）；STATE 一行「第 k 回合 <信 id>：<停在哪>」。
- SESSION-LOG 第一個 `## ` 段下一行 `- [brain] 信 <id>：…`，結案就刪。
- 每 `progress_every` 回合（up.json，預設 5，0＝不寄）寄 PROGRESS 給寄件人，同回合不重寄。
- 每回合跑一次 `aos7-compact now`（要不要整理、門檻與檔案清單照 compact 自己的設定，預設含 STATE；沒事不寫；up.json `compact: false` 關）。
- 第 1 回合本機挑一本技能，之後每回合附上那本 SKILL.md。

挑技能經沒帳的 `brain/.pick` 視角呼叫 `aos7-skills pick`，所以不問 AI、不花錢，紀錄照樣在 `skills/.pick/log.jsonl`。提示不用 `ref://` 折疊：AI 沒有工具展開，折起來等於看不到；每回合提示只多「最近 8 回合各一行＋上回合成果」，有上限，不隨回合數變長。

task.json 壞掉就刪掉從第 1 回合重播（每回合的 call 已有回條，不重問、不重記）；讀不到就這回合不動。沒有進行中的任務時，殘留的 brain open 行與暫存一併清掉。

每回合的配額是「最多處理一封請求、最多問一次 AI」；不是請求的信（DONE、PROGRESS 等回信）不問 AI，每回合讀到就直接歸檔，不算在配額裡。brain 只讀自己的信箱，不讀必讀通道（events），所以不會替別人標已處理。

停在哪連續 `stall`（預設 3）回合沒變，或做到 `max_steps`（預設 40）回合還沒完，回 NEEDS-USER 結案。一次只做一封信，做完才換下一封（FIFO）。假 AI 照信的標題演：含「N 回合」就分 N 回合做完，含「沒進展」就一直停在同一處，含「要你決定」就一回合要你決定（測試用）。範例 [examples/multiround/](examples/multiround/README.md)。

brain 對 llmcall 的退出：0 回信；4 也回信，回合行註「AI 用量還沒對清」；3 不回信、不寫 pending、信留在 inbox，下回合用同一個 call 接續（見下段的期限）；1、2 與其他回 BLOCKED。

**不確定的期限**（2026-10-09 頂層定，問題見[長任務實跑](../../notes/play/2026-10-09-longtask/README.md)問題 1）：退 3 而那筆沒有 raw（AI 回沒回不確定，例如 brain 連同 llmcall 在傳輸中被殺）時，brain 在 `brain/unsure.json` 記下這筆 call 第一次不確定的時間；連續不確定滿 up.json 的 `deadline` 秒（沒設：假 AI 60、真 AI 600）就**不重送**，把這封信回 BLOCKED 結案，接著照 FIFO 辦下一封。期限用 deadline 是因為傳輸本身最多等 deadline 秒：被殺前已送出的孤兒 llmcall 到那時一定已經回來或放棄。傳輸逾時造成的不確定，從逾時那刻起再等一個 deadline，最多約兩倍。退 3 但 raw 已在（AI 回了、帳沒回）不計時，照舊下回合再看。

卡住的回信用白話寫：哪封信、問 AI 時被打斷、不知道它回了沒，以及兩條路：①什麼都不做（這封停著，不影響別的信）；②再寄一次這封信＝從頭重問（假 AI 不花錢；真 AI 若上次其實回了，可能多付一次）。正文不露 call id 與回合。信尾「進階（給維護者）」一段才寫哪一筆（call id、第幾回合）、帳上預留多少，以及要放掉預留時在 node 裡照信跑的一行：`aos7-llmcall adopt …--raw brain/stuck/<call>/reply.json && aos7-llmcall call …--request brain/stuck/<call>/request.json --reserve R`（心跳要開著；reply.json 預設記「沒扣費」，後台查到實際用量就改成 `{"status":"error","billed":true,"body":"","usage":{"total_tokens":N}}`；第二段退 1 是正常的）；還沒送出給 AI 的那種則是 `aos7-budget cancel … && aos7-budget settle …`。已送出（llm 有 intent）時 `aos7-budget cancel` 退 3、放不掉，所以不用它。

SESSION-LOG 的 brain 行會把 AI 寫的「停在哪」裡會讓 `aos7-wfnode check` 誤判成「做完沒刪」的字（已完成、DONE、✅ 等）換成中性字，進行中的行不讓體檢變「有問題」。

`up.json` 的 `fake_delay`（秒，只對假 AI）讓假 AI 每次回覆前等這麼久，給測試與 [longtask](examples/longtask/README.md) 重現「傳輸中被殺」用。
觀看直接掃信件，包含 you/inbox/done 回信，不更新 mail 的讀取快照。

### brain 跨信記憶

結案回信全文存進 `notes/done/<id>.md`；`INDEX.md` 留最新 50 行，較舊的先搬到 `INDEX-old.md`。每回合附目錄（最多 2000 字）；信提到前件時再附一份全文（最多 3000 字）。每回合也附最新一份 STATE（最多 1200 字，太長留摘要行＋最近幾行）。`notes/journal.jsonl` 不進提示，壓縮它只為了檔案變小。AI 也能只回 `要檔案：<id>`，多用一回合拿全文；同樣受卡住與回合數上限保護。

`up.json` 可設 `max_prompt_chars`（預設 12000）：提示超過時依序砍回合軌跡、技能全文、STATE，再截前件全文，最後縮短上回合成果（至少留 200 字）；目錄永遠保留。砍完還超過（信或工作簿本身太長）就回 BLOCKED，說把信拆短或調大上限。寫全文與寄信之間被 SIGKILL，重起不重寫、不重加目錄、不重寄。假 AI 遇到標題含「要檔案」且還沒附前件，就演一次要檔案。

## 錯誤與退出

錯誤 stderr 一行 `aos7-up: 發生什麼。怎麼辦`，不印 traceback。

| 退出 | 意思與處理 |
|---|---|
| 0 | 做到了；前景正常停也算 |
| 1 | 做不到：缺模板、子指令確定失敗（附 stderr 最後一行）、心跳起不來（附 log）；照訊息處理 |
| 2 | 參數不對：名字、換假／真 AI、節拍壞值、up.json 形狀錯、status 沒 node；修正再跑 |
| 3 | 不確定：準備中斷、子指令退 3、讀寫故障（含讀不到 up.json）、ask 寄信或讀信半路出錯、停不下來或沒看到 node 醒來；檔案留著，照原樣再跑會接續 |

`ask` 等滿 60 秒還沒回信退 0（等過了算做到），stdout 說「還沒回」與用 status 再看。

up.json 壞了時刪掉該檔再 up。未知結果不清檔、不重送。

## 程式與驗證

| 檔案 | 職責 |
|---|---|
| `aos7-up` | 薄入口 |
| `aos7_up.py` | 冪等安裝、起停、起動證據與回收 |
| `aos7_up_cli.py` | 參數、錯誤與 ask／brain 分派 |
| `aos7_up_brain.py`、`aos7_up_ask.py`、`prompts/`、`examples/` | brain 一回合（一封信可跨回合）與 ask（測試 `tests/test_brain*.py`、`tests/test_up_brain_multi.py`） |
| `aos7_up_memory.py` | brain 跨信記憶：結案存 `notes/done/`、目錄輪替、挑前件、要檔案、提示上限裁切（測試 `tests/test_up_memory.py`） |
| `aos7_up_status.py` | 六（卡住時七）行狀態、觀看、設定驗證、子指令與 atomic |
| `tests/test_up.py` | 起停、信與已花預算 SIGKILL 重接、唯讀摘要 |
| `tests/test_up_model.py` | 模型、端點保存、拒絕 gateway 變更、經 up 的 ask 假 AI 一圈 |
| `tests/test_up_beat.py` | 節拍生效、沿用、壞值退 2 |
| `tests/test_up_edges.py` | 重跑保信、壞設定、共享心跳、訊號、並行與唯讀 |
| `tests/test_up_errors.py` | 子指令摘要、未知讀寫、stop 逾時、壞名字無副作用、「最後記下」去 id 與回合、體檢只在壞時出現、要收掉那行 |
| `tests/test_up_dispatch.py` | 分派、真檔觀看事件、啟動／收尾逾時、中斷與程序組 |

從 repo 根跑：

```sh
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/up/tests
bash wf/tools/wf-lint.sh proto7-2/modules/up
```

缺模板會 skip 整合測試；交付前應確認沒有 skip。
