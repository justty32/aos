← [2026-09-30 使用者方向（十一）：tick 是 aos 的衡量基準](../11-tick-as-unit.md)（分檔 18/24）｜所在段落：2026-10-01 第十六批：擋板檔只看存不存在｜[上一份](17-1001-第十六批.md)｜[下一份](19-1001-第十七批.md)

### 第十六批（續）：tick 模組 `modules.tasks_blocked`

> 〔第二十批〕模組鍵改名 `tasks-blocked`（跟檔名一樣），展開時機也不再比照 `hooks.after_all`（整份 tasks.json 開格就展開），見[第二十批](22-1001-第二十批.md#2026-10-01-第二十批tasksjson-全部解完模組鍵改名)。下面照當時原文留著。

〔使用者裁定 2026-10-01 晚〕對「發現 tasks-blocked 時要跑的 insts」那個 tick 模組（上一節第 3 段的方向）的五題，使用者原話：「1.modules底下 2.對 3.b 4.對，不記錄進記錄，非0沒影響。 5.對」。五題是：

1. 寫在 `tasks.json` 的 `modules` 底下（不是 `hooks` 的掛點）。
2. 某一項任務之前發現檔案時，當場跑一次，再決定那一項跑不跑。
3. (b) 跑完再看一次檔案：insts 把檔刪了就繼續跑那一項與後面的，還在就照預設（這一項與後面都不跑）。
4. insts 拿得到被擋下那一項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`；結束碼不記進紀錄、非 0 沒影響。
5. 沒掛模組＝現在的預設行為。

已做，正本 [B-636](../../../spec/settled/tick/tasks-blocked.md)、格式 [P-214](../../../spec/settled/protocol/tick.md#p-214tick-模組-tasks-blocked使用者-2026-10-01-第十六批第二十批改名)。

**AI 隊定的細節**（使用者可改）：

1. 寫法 `"modules": {"tasks_blocked": {"insts": [<inst 或 $ref>, …]}}`；每項跟任務表的一項一樣合併頂層預設。**展開時機比照 `hooks.after_all`**：`tasks_blocked`、`insts`、每一元素讀表時各解一層，內部跑到時才展開（`$ref:""`／`#…` 指合併後的這一項）；`modules` 其他鍵照舊整個展開——`tasks_blocked` 是 `modules` 裡唯一的例外。
2. 讀表檢查：`tasks_blocked` 是物件、要有 `insts` 陣列（可以空）、每項是物件、合併頂層預設後有 `argv`；不合＝`bad_table`。
3. 依序全部跑完（不看彼此的結束碼）才重看檔案；insts 自己不看 tasks-blocked。
4. 環境照任務：`AOS_TASK_ID`／`AOS_TASK_INDEX`＝被擋下那一項、`AOS_TICK_CWD`；不給 `AOS_HOOK_*`；不另加變數（檔案路徑從 `AOS_TICK_CWD` 與 `AOS_DIRNAME` 找得到）。
5. 放行之後、後面某一項之前又發現檔（例如某任務又寫了），再跑一次；同一項之前只跑一次（跑完檔還在就擋）。
6. 開不起來照任務：stderr `exec_failed: tasks_blocked/<id>: …`、接著跑下一個；展開失敗照任務與 hook：自然丟錯、tick 回 1（hook 那條使用者說過「先不管」）。
7. 整格最後照樣刪 tasks-blocked。條號：B-636（tick 子篇新一篇 `tick/tasks-blocked.md`）、P-214。

改到的地方：程式 `lib/aos_tick_table.py`（`_tasks_blocked()`、`Table.on_blocked`；`modules` 先解一層、`tasks_blocked` 以外的照舊整個展開）、`lib/aos_tick.py`（`run_on_blocked()`、迴圈）；測試 `tests/test_tick.py` 新 `TasksBlockedModule` 7 條；spec 新 [tick/tasks-blocked.md](../../../spec/settled/tick/tasks-blocked.md)（B-636），改 [tick 核心](../../../spec/settled/tick.md) B-620、[tick 協議](../../../spec/settled/protocol/tick.md) P-202 `modules` 那列、新 P-214、[tick 子篇入口](../../../spec/settled/tick/README.md)、[整理區入口](../../../spec/settled/README.md)、[名詞](../../../spec/settled/terms.md)、[慣例 C-10](../../../spec/settled/conventions.md)、[驗收入口](../../../spec/conformance.md)、[protocol README](../../../spec/protocol/README.md)；schema `tick-tasks`（`modules.tasks_blocked`）、範例 `tasks.tasks-blocked.valid.json`、`tasks.tasks-blocked-no-insts.invalid.json`、`tasks.tasks-blocked-no-argv.invalid.json`；[src/py README](../../../src/py/README.md)。
