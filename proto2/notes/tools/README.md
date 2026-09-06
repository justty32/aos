# 工具包發想（2026-09-06）

這是八隊 AI 各想一塊的草稿（第八份 code-editing 是 codex 後補的），不是規格，要使用者拍板才會做。

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

## 七份互相牽扯的地方

- communication 說一般寄信；kids 說小孩每次回話都自動變成父的信。兩邊要共用同一種信件長相，才不會出現兩套收信方式。
- fs-shell-and-toolmaking 的 `sh_bg`，跟 long-running 的 `run_long` 都是把長工作搬去新的鐘。名字、超時、收尾和結果檔還沒統一。
- self-and-memory 的 `self_cost` 看一天總花費；cost-metering 的 `cost_summary` 看每種工具花費。後者的帳要能供前者加總。
- self-and-memory 與 cost-metering 都要在 `engines.json` 放單價，但欄位名字和計價細節不同。實作前要先統一。
- identity-and-env 想鎖住 `.aos/inst`；kids 的 shared 小孩卻要往這個檔加一行，暫停時也要改那一行。先鎖就會讓生小孩和暫停失效。

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

## 建議的實作順序

先做 communication，再補 fs，接著做 self 與 memory。
mailbox、shell、self、kids 已有骨架，這三包最容易接上，也先補齊寄信、做事、看自己和整理記憶。
長工作、身份和成本都會牽動前面幾包，等名字和資料長相拍板後再做。
