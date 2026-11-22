`knowledge/aos/_index.json` 的中文映照版，也是這一夾（中文映照版）自己的 index：一項「名字: 一句話」，名字是本夾裡的檔名或子夾名。

> 正本：`proto8/knowledge/aos/_index.json`，跟到正本 commit `65bb2891f`（正本這份最後一次改動）。英文說明譯成中文，路徑照原樣。正本是 json 表，這裡寫成清單，讓 `index_view`／`index_check` 讀得出來（使用者 11-21「幫我處理，重寫」）。改請改正本，再照 [README](../README.md) 的做法跟上這份。

- `me.md`: 找出你自己的名字、你的 stack 裡有什麼，以及你可以改哪些東西。
- `me`: aos/me.md 裡較長的幾節，各自放成獨立的檔案（self_tools、self_llm、self_system、self_history、do_task、compact、self_hook）；aos/me.md 用 $ref 指向每一份。
- `errors.md`: 怎麼看一次失敗的呼叫：`error:` 那行、`warning:` 那幾行，以及結束碼；`#/where` 告訴你哪一頁在講某個代號（PhaseBad、BudgetMissing ...）。
- `errors`: aos/errors.md 裡較長的幾節，各自放成獨立的檔案（common）；aos/errors.md 用 $ref 指向它。
- `world.md`: 心中的模型：daemon = 硬體，stack = 記憶體，工作區 = 外部記憶體，定義 = 原始碼，kernel = 你送請求的地方。
- `definition.md`: 定義夾裡每個檔案是做什麼的（interfaces.json、loop.json、tools.json、hooks.json 與 hookeds.json、cli.json ...），以及哪些是你自己有一份副本的。
- `body.md`: 兩種身體，agent-fsm 與 eca（claude、codex、pi）：腦、工具、hook、系統文字、對話歷史；怎麼看出你是哪一種。
- `status.md`: daemon 的表、agent 可能處在的各個 phase，以及每個 phase 對你代表什麼。
- `brain.md`: 一次腦的請求怎麼傳遞、端點包是什麼，以及優先順序怎麼運作。
- `agents.md`: 工具 subagent、agents_ctl、agent_def 與 fork：你自己的子 agent、daemon 的表上任何一個 agent、新的定義，以及為了一個目標複製一份你自己。
- `agents`: aos/agents.md 裡較長的幾節，各自放成獨立的檔案（subagent、fork）；aos/agents.md 用 $ref 指向每一份。
- `rules.md`: 你不可以做什麼，以及為什麼。做任何會改變系統的事之前，先讀這份。
- `cli`: 用這些 shell 指令來管理 agent、工具與 daemon 的 proc。（index：`cli/_index.md`）
- `mailbox.md`: agent 之間的信：工具 mailbox_peek、mailbox_read、mailbox_send；什麼時候你一定要回覆；定期檢查又不把對話歷史塞滿。
- `user_zone.md`: 怎麼問使用者：用 aos-user send（或 mailbox_send）把 decide/verify/trial/chore/fyi 信送到使用者區 ~/.aos/user/mailbox，回覆長什麼樣子，以及一個經過檢查的回覆算數到什麼程度。
- `clock.md`: 計時器：送到你佇列的 clock 信（clock_register），或是不會在你對話歷史裡加任何東西的 on_clock hook；該選哪一個。
- `tools_def.md`: 做你自己的工具：工具 tools_def（從 Python 骨架開新的、檢查），以及用 fn 把一個工具寫成一個 Python 函式（@fn.tool、fn.main）。
- `tools`: 每個內建工具一個節點（read、ls、write、edit、trash、shell ...）：什麼時候用它、什麼時候改用哪個工具、附真實輸出的範例、錯誤。在其他頁講的工具（mailbox_send、self_tools、subagent ...）在它的 index 裡是指標列。（index：`tools/_index.md`）
- `packs.md`: 你的工具是一包一包來的（look、change、delete、shell、gadgets、events、todo、self、subagent、def、mailbox、goal、json、jsonx、index；comm 由配給包使用，kernel_gate 不在任何內建定義裡）：每個工具一句話，以及怎麼關掉一個工具包。（index：`packs.md#/_index`）
- `_description.md`: 一頁講完 aos：aos 是什麼、八個詞、五條規則，以及去哪裡讀更多。
- `kernel.md`: kernel 是什麼（資源管理與排程，從寄件者的角度看）、新板子的初始 kernel 由什麼組成（最小的主體（minimal core）、llm 部分、可選的權限部分）、請求送去哪裡、範例 kernel、怎麼自己當 kernel（kernel_gate），以及怎麼寫你自己的。
- `kits.md`: 配給包：為某一個角色（gatherer、reviewer）準備好的系統文字與工具組，疊在一個新的 agent-fsm 定義上；怎麼用、它的各層、為什麼它會砍掉工具。
- `eca_reading.md`: 你是 eca（claude、codex、pi）時：哪些頁、哪幾節是給你的，哪些要用到時再讀，哪些可以跳過（只有 agent-fsm 用得到）。
- `troubleshooting.md`: 常見的失敗：症狀、原因、怎麼查（帶 $AOS_HOME 的路徑、剛加上的工具、畫面上的 ClockMissing、KernelFailed、全景頁的 ctl ls 失敗 ...）。
