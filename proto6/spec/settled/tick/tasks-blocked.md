# tick 模組 `tasks-blocked`：發現 tasks-blocked 時先跑一串 inst

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜[hooks（B-635）](hooks.md)｜格式：[P-214](../protocol/tick/06-P-213-tasks-blocked與P-214.md#p-214tick-模組-tasks-blocked使用者-2026-10-01-第十六批第二十批改名)

**狀態：已實作**（2026-10-01，`lib/aos_tick.py` 的 `run_on_blocked()`、`lib/aos_tick_table.py` 的 `_tasks_blocked()`）。本篇只有 B-636。

依據：[verdicts 11 篇末「2026-10-01 第十六批」](../../../notes/verdicts/11-tick-as-unit/17-1001-第十六批.md#2026-10-01-第十六批擋板檔只看存不存在)；現行程式 [src/py README](../../../src/py/README.md)（有出入以程式為準）。

## B-636：tick 模組 `tasks-blocked`〔使用者 2026-10-01 第十六批；第二十批改名〕

〔使用者 2026-10-01 第二十批：「模組的鍵改成 tasks-blocked」〕模組鍵原本叫 `tasks_blocked`，改成跟檔名一樣；寫舊名就是陌生的模組鍵，不掛。

使用者原話：「我們可以弄一個tick的module，用於設定讀取tasks-blocked的時候，要做的事情，類似hook，但是是在發現有tasks-blocked這個檔案之後，要做的insts」；細節：「1.modules底下 2.對 3.b 4.對，不記錄進記錄，非0沒影響。 5.對」。

**核心每一項跑之前看 tasks-blocked（[B-620](../tick.md)「tasks-blocked 與擋板檔」）；掛了這個模組，看到時不直接擋下，先跑一串 inst，跑完再看一次。**

- **寫在哪**：任務表 `tasks.json` 頂層 `modules` 底下（不是 `hooks` 的掛點）：`"modules": {"tasks-blocked": {"insts": [...]}}`。沒寫＝原本的預設行為（看到就擋下）。
- **什麼時候跑**：某一項任務跑之前發現 tasks-blocked 時，當場依序把 `insts` 全部跑一次，再決定那一項跑不跑。
- **跑完再看一次**：檔被刪了＝放行，這一項與後面照常跑；還在＝照預設，這一項與後面都不跑（紀錄 `blocked_before`，stderr 不印）。
- **同一項之前只跑一次**：跑完檔還在就擋下，不重跑。放行之後，後面某一項之前又發現檔（例如某任務又寫了），那一項之前再跑一次。
- **結束碼不記進紀錄、非 0 沒影響**：不算進 `ran`、不進 `tasks`，誰回幾都只看檔在不在。彼此之間也不看結束碼，一律全部跑完。
- **環境變數**：照任務的規則——`AOS_TASK_ID`、`AOS_TASK_INDEX` 是**被擋下的那一項**的，加上 `AOS_TICK_CWD`；不給 `AOS_HOOK_*`。tasks-blocked 的路徑從 `AOS_TICK_CWD` 與 `AOS_DIRNAME` 找得到，不另給變數。
- **tasks-blocked 的內容**〔使用者 2026-10-01 第十八批：「3.對，我就不想了。」〕：tick 永遠不讀；要放什麼、怎麼解讀，由這一串 insts 自己讀檔決定（路徑 `$AOS_TICK_CWD/<狀態資料夾>/tick/tasks-blocked`）。
- **insts 自己不看 tasks-blocked**；它們之間寫了、刪了都只在全部跑完後那一次看。
- **寫法比照 `hooks.after_all`**（[B-635](hooks.md)）：每一項是 inst（可以整項 `$ref`），合併任務表頂層預設。〔使用者 2026-10-01 第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」〕開格時跟任務、hook 一樣整份展開（已知的鍵整個展開、`_metainfo` 與陌生鍵不解，`$ref:""`／`#…` 指整份 tasks.json），不再是 `modules` 裡的例外；~~原本讀表時只解一層、內部跑到時才展開~~。
- **讀表檢查**：`tasks-blocked` 要是物件、要有 `insts` 陣列、每項是物件、合併頂層預設後有 `argv`；不合＝`bad_table`、回 1。`insts` 是空陣列可以（掛了但什麼都不跑，檔還在就擋）。
- **開不起來**（找不到程式、cwd 不對…）照任務：stderr 一行 `exec_failed: tasks-blocked/<id>: …`，接著跑下一個；指示詞展開失敗開格就是 `bad_table`；合併後不合 inst 規則照任務與 hook：自然丟錯、tick 回 1。
- **整格最後照樣刪 tasks-blocked**（B-620）。`after_all` 照常在最後跑。

AI 隊定、使用者可改：寫法 `{"insts": [...]}`、依序全部跑完才重看、不給 `AOS_HOOK_*` 也不另加變數、同一項之前只跑一次、開不起來與展開失敗照任務與 hook。

**驗收：**掛了模組，`a` 寫 tasks-blocked：`b` 之前跑那一串，拿得到 `AOS_TASK_ID=b`、`AOS_TASK_INDEX=1`、沒有 `AOS_HOOK_POINT`；一串裡有一項刪檔（自己回 7）：`b`、`c` 照跑，紀錄 `ran:3`、`tasks:[]`、沒有 `blocked_before`。一串不刪檔：只跑一次，`b` 被擋下、`blocked_before:"b"`。放行後 `b` 又寫：`c` 之前再跑一次。格與格之間放的：第一項之前就跑。沒有 tasks-blocked 時一串不跑。開不起來印 `exec_failed: tasks-blocked/<id>`。`tasks-blocked` 不是物件；insts 內部的指示詞壞了開格就 `bad_table`、沒有 `insts`、某項缺 `argv`：`bad_table`、回 1。沒掛模組：看到就擋下（B-620）。測試見 `proto6/src/py/tests/test_tick.py` 的 `TasksBlockedModule`。
