# `knowledge/aos/_index.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/_index.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（index：鍵 → 一句說明）

| 鍵 | 說明 | index |
|---|---|---|
| `me.json` | 找出你自己的名字、你的 stack 裡有什麼，以及你可以改哪些東西。 |  |
| `me` | aos/me.json 裡較長的幾節，各自放成獨立的檔案（self_tools、self_llm、self_system、self_history、do_task、compact、self_hook）；aos/me.json 用 $ref 指向每一份。 |  |
| `errors.json` | 怎麼看一次失敗的呼叫：`error:` 那行、`warning:` 那幾行，以及結束碼；`#/where` 告訴你哪一頁在講某個代號（PhaseBad、BudgetMissing ...）。 |  |
| `errors` | aos/errors.json 裡較長的幾節，各自放成獨立的檔案（common）；aos/errors.json 用 $ref 指向它。 |  |
| `world.json` | 心中的模型：daemon = 硬體，stack = 記憶體，工作區 = 外部記憶體，定義 = 原始碼，kernel = 你送請求的地方。 |  |
| `definition.json` | 定義夾裡每個檔案是做什麼的（interfaces.json、loop.json、tools.json、hooks.json 與 hookeds.json、cli.json ...），以及哪些是你自己有一份副本的。 |  |
| `body.json` | 兩種身體，agent-fsm 與 eca（claude、codex、pi）：腦、工具、hook、系統文字、對話歷史；怎麼看出你是哪一種。 |  |
| `status.json` | daemon 的表、agent 可能處在的各個 phase，以及每個 phase 對你代表什麼。 |  |
| `brain.json` | 一次腦的請求怎麼傳遞、端點包是什麼，以及優先順序怎麼運作。 |  |
| `agents.json` | 工具 subagent、agents_ctl、agent_def 與 fork：你自己的子 agent、daemon 的表上任何一個 agent、新的定義，以及為了一個目標複製一份你自己。 |  |
| `agents` | aos/agents.json 裡較長的幾節，各自放成獨立的檔案（subagent、fork）；aos/agents.json 用 $ref 指向每一份。 |  |
| `rules.json` | 你不可以做什麼，以及為什麼。做任何會改變系統的事之前，先讀這份。 |  |
| `cli` | 用這些 shell 指令來管理 agent、工具與 daemon 的 proc。 | `cli/_index.json` |
| `mailbox.json` | agent 之間的信：工具 mailbox_peek、mailbox_read、mailbox_send；什麼時候你一定要回覆；定期檢查又不把對話歷史塞滿。 |  |
| `user_zone.json` | 怎麼問使用者：用 aos-user send（或 mailbox_send）把 decide/verify/trial/chore/fyi 信送到使用者區 ~/.aos/user/mailbox，回覆長什麼樣子，以及一個經過檢查的回覆算數到什麼程度。 |  |
| `clock.json` | 計時器：送到你佇列的 clock 信（clock_register），或是不會在你對話歷史裡加任何東西的 on_clock hook；該選哪一個。 |  |
| `tools_def.json` | 做你自己的工具：工具 tools_def（從 Python 骨架開新的、檢查），以及用 fn 把一個工具寫成一個 Python 函式（@fn.tool、fn.main）。 |  |
| `tools` | 每個內建工具一個節點（read、ls、write、edit、trash、shell ...）：什麼時候用它、什麼時候改用哪個工具、附真實輸出的範例、錯誤。在其他頁講的工具（mailbox_send、self_tools、subagent ...）在它的 index 裡是指標列。 | `tools/_index.json` |
| `packs.json` | 你的工具是一包一包來的（look、change、delete、shell、gadgets、events、todo、self、subagent、def、mailbox、goal、json、jsonx、index；comm 由配給包使用，kernel_gate 不在任何內建定義裡）：每個工具一句話，以及怎麼關掉一個工具包。 | `packs.json#/_index` |
| `_description.json` | 一頁講完 aos：aos 是什麼、八個詞、五條規則，以及去哪裡讀更多。 |  |
| `kernel.json` | kernel 是什麼（資源管理與排程，從寄件者的角度看）、新板子的初始 kernel 由什麼組成（最小的主體（minimal core）、llm 部分、可選的權限部分）、請求送去哪裡、範例 kernel、怎麼自己當 kernel（kernel_gate），以及怎麼寫你自己的。 |  |
| `kits.json` | 配給包：為某一個角色（gatherer、reviewer）準備好的系統文字與工具組，疊在一個新的 agent-fsm 定義上；怎麼用、它的各層、為什麼它會砍掉工具。 |  |
