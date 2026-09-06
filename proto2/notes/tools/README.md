# 工具包發想（2026-09-06）

這是十四份 AI 發想草稿（code-editing 是 codex 後補的），不是規格，要使用者拍板才會做。

| 檔名 | 一句話講這包是什麼 | 提議的工具名 |
|---|---|---|
| [communication.md](communication.md) | 寄信、回信，也能看自己認識誰。 | `mail_send`, `mail_reply`, `mail_broadcast`, `mail_who`, `mail_wait` |
| [self-and-memory.md](self-and-memory.md) | 看自己的狀況，也能整理對話和長期筆記。 | `self_status`, `self_cost`, `self_who`, `self_time`, `memory_list`, `memory_summarize_old`, `memory_replace_old`, `memory_forget`, `note_save`, `note_find`, `note_read`, `self_note` |
| [fs-shell-and-toolmaking.md](fs-shell-and-toolmaking.md) | 讀寫檔、跑指令，也能替自己做新工具。 | `read`, `write`, `ls`, `edit`, `sh`, `sh_bg`, `tool_add`, `tool_list`, `tool_remove`, `tool_try` |
| [kids.md](kids.md) | 生小孩、派工作、看進度、暫停或收掉。 | `spawn`, `kids_list`, `kids_pause`, `kids_resume`, `kids_kill`, `kids_tell` |
| [long-running.md](long-running.md) | 把長工作搬到新的鐘，做完再寄信回來。 | `run_long`, `jobs_list`, `job_peek`, `job_cancel` |
| [identity-and-env.md](identity-and-env.md) | 管時鐘用誰的身份跑、能看到什麼，也保護重要檔案。 | 無，主要是調整時鐘和生小孩的做法 |
| [cost-metering.md](cost-metering.md) | 記下每次叫工具花的時間、字數、用量和錢。 | `cost_summary`, `cost_recent` |
| [code-editing.md](code-editing.md) | 改程式碼特有的動作：看骨架、找、檢查語法、反悔；讀寫改沿用 fs。 | `code_outline`, `code_search`, `code_check`, `code_checkpoint`, `code_undo`, `code_diff` |
| [deep-thinking.md](deep-thinking.md) | 借更會想的模型，分幾格想完難題，只把短結論拿回來。 | `think`, `think_steps`, `critique`, `conclude`, `thoughts_list`, `thought_read` |
| [big-memory-and-ref.md](big-memory-and-ref.md) | 把少用的原文存到外面，對話只留需要時才展開的指標。 | `mem_put`, `mem_find`, `mem_get`, `mem_forget`, `mem_archive_history`, `ref_expand`, `ref_collapse`, `ref_list` |
| [branching.md](branching.md) | 同一題開幾條線一起想，再把短結論收回主線。 | `fork`, `join`, `adopt` |
| [self-review.md](self-review.md) | 回頭看做過的事、成本和錯誤，把能改進下次的教訓留下來。 | `review_recent`, `review_patterns`, `review_thoughts`, `lesson_add`, `lessons_list`, `improve_prompt` |
| [llm-scheduling.md](llm-scheduling.md) | 讓 LLM 排隊兼顧急迫、久等、公平和預算。 | 無，主要是調整 `aos-llm` 的排隊方式 |
| [ai-group.md](ai-group.md) | 用主管和小孩組成一隊，共用名冊、預算、筆記和排隊區。 | 無，先新增 `team` 工具包，工具名還沒定 |

## 十四份互相牽扯的地方

- communication 說一般寄信；kids 說小孩每次回話都自動變成父的信。兩邊要共用同一種信件長相，才不會出現兩套收信方式。
- fs-shell-and-toolmaking 的 `sh_bg`，跟 long-running 的 `run_long` 都是把長工作搬去新的鐘。名字、超時、收尾和結果檔還沒統一。
- self-and-memory 的 `self_cost` 看一天總花費；cost-metering 的 `cost_summary` 看每種工具花費。後者的帳要能供前者加總。
- self-and-memory 與 cost-metering 都要在 `engines.json` 放單價，但欄位名字和計價細節不同。實作前要先統一。
- identity-and-env 想鎖住 `.aos/inst`；kids 的 shared 小孩卻要往這個檔加一行，暫停時也要改那一行。先鎖就會讓生小孩和暫停失效。
- deep-thinking 和 branching 都要讓 `wait` 分流收結果，也都會留下私有思考資料。`thoughts/`、`branches/` 和狀態欄位要一起定，才不會互相卡住。
- self-review 要吃 cost-metering 的帳。帳裡要先有成功、錯誤種類、請求歸屬、token、錢、格數和時間，回顧才算得出有沒有變好。
- llm-scheduling 的「主管先排」就是 ai-group 的主管在排。兩份要共用同一個 `llm-queue/`、名字、優先度和降級理由。
- big-memory 的 `$ref` 和 self-and-memory 的摘要要排好先後。先收起大原文，再做摘要；摘要裡要留得住歸檔 id。
- ai-group 也想先限兩層，跟 kids 的 T-16 是同一個限制。不能兩邊各算一套深度。

## 要使用者拍板的題目

### communication.md

- T-01 寄信要寫名字，還是直接寫路徑？ → 建議：寫名字，再由 `contacts.json` 找路徑。
- T-02 agent 對使用者的回話，要不要也自動變成寄給使用者的信？ → 建議：要，原本的 outbox 也保留。
- T-03 廣播沒指定對象時，要寄給誰？ → 建議：只寄給父和直接的小孩。
- T-04 孫子要不要直接認識爺爺？ → 建議：不要，只認直接的父和小孩。
- T-05 寄給不存在的人，要報錯還是直接丟掉？ → 建議：報錯，讓 agent 知道要改。

### self-and-memory.md

- T-06 單價要放 `engines.json`，還是另開檔案？（出自 self-and-memory.md、cost-metering.md） → 建議：放在每台引擎旁，統一用 `input`、`output`、`reasoning`、`cached`，沒填就不估錢。
- T-07 舊對話要不要由 agent 自己分兩格摘要？ → 建議：要，不必改現有走法。
- T-08 agent 能不能改自己的 system prompt？ → 建議：不能覆寫，只能追加 `self-note.md`。
- T-09 記憶到 40000 字提醒、80000 字硬砍，要先寫死嗎？ → 建議：先寫死，以後再搬到設定。
- T-10 長期筆記和丟掉的對話，要照提議的資料夾放嗎？ → 建議：照提議放，先不做搜尋目錄。

### fs-shell-and-toolmaking.md

- T-11 讀寫檔和跑指令，要合成一包還是拆兩包？ → 建議：合成 `fs` 一包。
- T-12 要不要做只換掉唯一一處文字的 `edit`？ → 建議：要，能少傳很多全文。
- T-13 長指令要開子世界，還是直接丟到背景？ → 建議：開子世界，仍由 daemon 管。
- T-14 自製工具要放自己家，還是放全域工具包？ → 建議：放自己家，不影響別人。
- T-15 生小孩時，要不要連自己的工具包一起抄過去？ → 建議：要，避免小孩找不到工具包。

### kids.md

- T-16 生小孩的深度先限兩層，夠不夠？ → 建議：夠，數字留著可改。
- T-17 小孩每次回話，要不要自動變成父的一封信？ → 建議：要，父就不用一直去看小孩的 outbox。
- T-18 收掉小孩時，預設要不要保留資料夾？ → 建議：保留，明說才刪。
- T-19 要加 `kids.json` 名冊，還是每次掃資料夾猜？ → 建議：加名冊，鐘和暫停狀態才看得準。
- T-20 shared 小孩暫停時，先用註解 `.aos/inst` 那一行的做法嗎？ → 建議：先這樣，簡單就好。

### long-running.md

- T-21 長工作做完後，要自己退鐘，還是讓 daemon 多一種只跑一次的鐘？ → 建議：自己退鐘，daemon 不加新規則。
- T-22 長工作的結果要寄到信箱，還是當成工具返回值？ → 建議：寄到信箱，工具當場等不到結果。
- T-23 長工作預設一小時超時，並由工作自己計時，夠不夠？ → 建議：夠，不讓 daemon 猜它是不是卡住。
- T-24 `jobs/` 要放 agent 家裡，還是獨立成服務世界？ → 建議：先放 agent 家裡。
- T-25 `sh` 超時後只提示改用長工作，不自動搬過去，可以嗎？ → 建議：可以，自動搬會弄不清前半段做了什麼。

### identity-and-env.md

- T-26 現在所有鐘都先用同一個 Linux user 跑嗎？ → 建議：是，換身份的欄位先留著。
- T-27 要不要用 `chattr +i` 鎖住 `system-prompt.json` 和 `llm.json`？ → 建議：鎖，主人要改時再手動解開。
- T-28 `.aos/inst` 要不要一起鎖？ → 建議：先不鎖，否則 shared 小孩會壞。
- T-29 daemon 要不要只給乾淨的基本環境，其餘由三個設定欄位加入？ → 建議：要，別把主人整包環境交給 agent。
- T-30 API 金鑰要不要只放在權限 600 的 `~/.aosd/llm.env`？ → 建議：要，而且只交給 LLM 的鐘。

### cost-metering.md

- T-31 工具後面那一輪 LLM 用量，要整包算給這次工具呼叫嗎？ → 建議：要，多個工具就照返回字數分攤。
- T-32 工具帳放 agent 家裡，模型總帳留在 LLM 資料夾，可以嗎？ → 建議：可以，兩邊各管一種帳。
- T-33 每日用量要改成按模型、按使用者兩層嗎？ → 建議：改，趁現在舊檔還少。
- T-34 要不要每輪都自動把成本摘要塞進對話？ → 建議：不要，需要時再叫 `cost_summary`。

### code-editing.md

- T-35 世界就直接是專案資料夾，home 用 `.aos-agent/`？ → 建議：是，路徑最單純。
- T-36 精準修改和整檔寫入沿用 `fs`，`code` 不重做？ → 建議：是，工具越少越好。
- T-37 第一版不提供套 patch，只用多次 `edit`？ → 建議：是，小模型比較不會卡在格式。
- T-38 checkpoint 用 `.aos-undo/` 複製檔案，不碰專案 Git？ → 建議：是，不污染原本歷史。
- T-39 Python 語法由模型每次小改後主動檢查，不在寫檔時自動跑？ → 建議：是，回合比較清楚。

### deep-thinking.md

- T-40 thinker 由 `engines.json` 的 `role` 指定，不放 `llm.json`？ → 建議：是。
- T-41 一次上限用 6000 輸出 token、三步、等待 120 格、0.10 美元？ → 建議：先這樣。
- T-42 深思沿用 `wait`，靠 `request_kind` 分流，不新增第六個狀態？ → 建議：是。
- T-43 多步思考只把原問題和上一步短結論送進下一步？ → 建議：是。
- T-44 只有 `conclude` 把結論放進記憶，整個 `thoughts/` 不進 git？ → 建議：是。

### big-memory-and-ref.md

- T-45 先做 B，再做 A？ → 建議：是，先立刻省 context，也先定好共同指標。
- T-46 記憶世界用自己的 `venv + pymongo`？ → 建議：是，`mongosh` 只給人檢查。
- T-47 所有 agent 共用一個 collection，再用 `agent` 欄位區分？ → 建議：是。
- T-48 大 JSON 超過 6000 字就摺到本地，長期內容才進 MongoDB？ → 建議：是。
- T-49 40000 字先歸檔原文再摘要，80000 字停問模型並硬歸檔？ → 建議：是。
- T-50 沒有 MongoDB 時先做 SQLite 退路？ → 建議：是，先不做純 JSON 主庫。

### branching.md

- T-51 第一版預設用 `llm`，只有需要工具或多輪時才用 `kid`？ → 建議：是。
- T-52 一次最多三條、每條 1500 輸出 token、總共最多 4500？ → 建議：先這樣。
- T-53 `join` 每條最多帶回 800 個中文字，不帶思考過程？ → 建議：是。
- T-54 要做 `adopt`，讓選中的整段記憶取代主線？ → 建議：做。
- T-55 第一版禁止巢狀分支，也不加評審請求？ → 建議：都先不要。

### self-review.md

- T-56 用「連續 3 格 idle，而且累積 10 次新工具呼叫」才提醒回顧？ → 建議：是，規則小，也不會每次閒著都吵。
- T-57 system prompt 帶最近 20 條教訓，`lessons.md` 上限 100 條、一次歸檔最舊 20 條？ → 建議：是。
- T-58 `improve_prompt` 只准改已開啟工具包的自己那份覆蓋？ → 建議：是，範圍最清楚。
- T-59 帳本加 `ok`、`error_kind` 和不含原文的參數記號？ → 建議：加，不然看不出哪裡常錯與打轉。
- T-60 回顧只提出並保存改法，不自動刪工具或改其他設定？ → 建議：是，先讓每次改動都能單獨撤回。
- T-60a 回顧的成本門檻寫死，還是放 `llm.json`？ → 建議：放 `llm.json`，不同世界可以用不同預算。
- T-60b 無效教訓自動刪掉，還是留著標記？ → 建議：留著標「無效」，免得下次又試同一個沒用的改法。

### llm-scheduling.md

- T-61 `priority` 改成物件，舊數字一律當成 `{"level": n}`？ → 建議：是。
- T-62 採用「過期先行，再照固定分數，每次開工後重算」？ → 建議：是。
- T-63 集團內的小孩一律先進主管的 `llm-queue/`，不直接投 LLM 世界？ → 建議：很多小孩共用本機模型時才強制。
- T-64 主管平常只用規則，超過 20 筆才偶爾借便宜模型排一次？ → 建議：是。
- T-65 限額八成先壓低深思與背景，用滿就直接回錯？ → 建議：是。

### ai-group.md

- T-66 集團直接沿用「主管加 `kids/`」，共用區只放在主管的 `team/`，可以嗎？ → 建議：可以。
- T-67 第一版仍限 2 層，不為集團放寬深度，可以嗎？ → 建議：可以。
- T-68 `inbox/team/` 只收主管廣播，成員之間直寄且不自動抄送主管，可以嗎？ → 建議：可以。
- T-69 成員的 LLM 請求一律先進集團佇列，再照主管訂的規則投遞，可以嗎？ → 建議：可以。
- T-70 預設主管一個鐘、直屬成員共用它，只有長工作才另開鐘，可以嗎？ → 建議：可以。
- T-71 用一份 `team.json` 一次建整隊，收隊只停鐘並保留全部檔案，可以嗎？ → 建議：可以。

## 建議的實作順序

先做一輪「掛勾輪」，把 `wait` 分流、工具帳欄位、`requester`／`priority`、共用 home 接點加好。
掛勾輪完，其餘十幾包就能並行，不再一包等一包。
晚一點的只有：branching 等 deep-thinking 的等待與思考檔接法穩定；self-review 等 cost-metering 的帳可讀。
big-memory 的 B 可以先做，A 要等 self-and-memory 的 memory 摘要與歸檔接法。
llm-scheduling 先做 A；主管先排的 B 要和 ai-group 一起定。
ai-group 最晚，因為它依賴 kids、communication、cost-metering 和 llm-scheduling。
