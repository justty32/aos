# `knowledge/aos/me.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 我是誰

找出你自己的名字、你的 stack 裡有什麼，以及你可以改什麼。

你是一個 daemon 上的一個 proc。daemon 的表裡有一列是你：你的名字、你的 phase（running、stuck、stopped、sleeping ……；見 `aos/status.json`）、你的工作區、你的定義、你的 stack。

你的名字：你從裡面是不知道的。指令 `aos-agent ctl who` 會看 `$AOS_STACK`，找出 stack 包含它的那一列，印出名字。對你動作的工具（例如 `self_tools`）會幫你做這件事，所以你很少需要自己來。

你的 stack 裡有什麼：`aos/me.json#/stack`。

你可以改什麼：只有你 stack 裡你自己的複本，而且只能透過 `self_*` 工具。它們從不改你的定義：

- 你的工具箱：工具 `self_tools`，像這樣呼叫 `{"op": "add", "name": "<name>", "path": "tools/<name>"}`；所有呼叫和規則在 `aos/me.json#/self_tools`。
- 你的腦的設定：工具 `self_llm`，像這樣呼叫 `{"op": "ls"}`；所有呼叫和規則在 `aos/me.json#/self_llm`。
- 你的系統文字：工具 `self_system`，像這樣呼叫 `{"op": "get"}`；所有呼叫和規則在 `aos/me.json#/self_system`。
- 你的對話歷史：工具 `self_history`，像這樣呼叫 `{"op": "ls"}`；所有呼叫和規則在 `aos/me.json#/self_history`。
- 你對話裡的一件工作，做完時摺成一份摘要（只有 agent-fsm）：工具 `do_task`，像這樣呼叫 `{"op": "start", "task": "..."}`；所有呼叫和規則在 `aos/me.json#/do_task`。
- 壓縮你的 agent-fsm 對話：怎麼回應 `[aos] compact:`、什麼會留下，以及 context_wrap 的控制，在 `aos/me.json#/compact`。
- 你的 hook（你身上發生某件事時會跑的程式）：工具 `self_hook`，像這樣呼叫 `{"op": "ls"}`；所有呼叫和規則在 `aos/me.json#/self_hook`。
- 你要不要繼續：工具 `self_ctl`，像這樣呼叫 `{"op": "stop"}`；所有呼叫和規則在 `aos/me.json#/self_ctl`。

用現成範本做出來的 agent-fsm，這些裡面一開始只有 `self_tools`、`self_state` 和 `do_task`；`self_llm`、`self_system`、`self_history` 和 `self_ctl` 是關著的，`self_hook`（工具包的事件）不在裡面，直到你加上一個：`self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_llm"}}`（`self_tools` `{"op": "ls", "long": true}` 會顯示哪些是關著的）。用現成範本做出來的 eca 有 `self_hook` 但沒有 `do_task`，同樣那四個 self 工具是關著的。

要看看你自己（名字、phase、工具、對話歷史大小、信箱、子 agent、資源），用 `{}` 呼叫 `self_state`；見 `aos/me.json#/self_state`。

你不可以改的：你的定義夾（`self_*` 工具改的是你的複本）、其他 agent 的 stack、daemon 的檔案、手動改 `history.jsonl`。規則：`aos/rules.json`。

如果你需要知道你到底有沒有在 daemon 底下跑：需要 daemon 的工具在你沒有時會回 `DaemonMissing` 或 `InstanceMissing`。`DaemonMissing` 表示 `AOS_DAEMON` 沒設，或它的資料夾不存在。`DaemonFailed` 表示 daemon 有設定、它的資料夾也存在，但在時限內沒有回覆（忙碌、暫停或掛了）。有設 `AOS_KERNEL` 時，查表會先問 kernel 表在哪裡（一封 `procs_state_path` 信）；3 秒內沒有回覆＝`KernelFailed`，而且工具不會退回去用 `AOS_DAEMON`。這時 `self_tools`、`subagent`、`agents_ctl` 和 `do_task` 之類的功能暫時不能用；要說出來。不要馬上重試；你可以晚一點再試一次。

---

**`#/stack`**

# 你的 stack 裡有什麼

你的 stack 是 `$AOS_STACK`，你存放狀態的資料夾。

- `history.jsonl`：你的對話，一行一則 JSON 訊息。你的身體會往裡面加。絕對不要手動改它；要改就用 `self_history`。
- `queue/`：你的佇列。人和其他 agent 把信丟在這裡；你照順序回覆。
- `letters.json`：`pending`＝你的身體已經拿走、還沒回覆的信；`dropped`＝最後 50 封它不會回覆的信（`letter`、`reason`：`bad` 壞掉的信、被 hook `blocked`，或交出去之後 `failed`；`at`）。你的身體寫它；`aos-agent ask` 和 `listen` 讀它，配合對話歷史列的 `aos` 鍵（`aos/body.json#/system_history`），來找到某一封信的回覆。不要手動改。
- `tools.json`：你自己的工具登記表。裡面只放和定義那份的差異（`"$override"` 指向那個檔案；你移除的工具是 `null`）。由 `self_tools` 寫，不要手動改。
- `llm.json`：你的腦的覆蓋層（例如你用哪個模型）。由 `self_llm` 寫。
- `system.txt`：你自己的系統文字，當你用 `self_system` 設了一份的時候。
- `hookeds.json`：你自己的 hook，由 `self_hook` 寫；`hookeds/<name>/`：每個 hook 自己的資料夾。
- `subagents.json`：你自己的配額修改（`max_subagents`），當有人類設了的時候。
- `mailbox/`：給你的信（`aos/mailbox.json`）。
- `tools/<name>/`：你呼叫的每個工具各有一個暫用資料夾（只有那個工具在裡面寫東西時才會建立）。

哪些定義檔在這裡有你自己的複本，以及各自放什麼：`aos/definition.json#/overlay`。

**`#/self_tools`**：→ `$ref` `me/self_tools.json`（映照版：[me/self_tools.md](me/self_tools.md)）

**`#/self_llm`**：→ `$ref` `me/self_llm.json`（映照版：[me/self_llm.md](me/self_llm.md)）

**`#/self_system`**：→ `$ref` `me/self_system.json`（映照版：[me/self_system.md](me/self_system.md)）

**`#/self_history`**：→ `$ref` `me/self_history.json`（映照版：[me/self_history.md](me/self_history.md)）

**`#/do_task`**：→ `$ref` `me/do_task.json`（映照版：[me/do_task.md](me/do_task.md)）

**`#/compact`**：→ `$ref` `me/compact.json`（映照版：[me/compact.md](me/compact.md)）

**`#/self_hook`**：→ `$ref` `me/self_hook.json`（映照版：[me/self_hook.md](me/self_hook.md)）

---

**`#/self_state`**

# 看看你自己：self_state

工具 `self_state` 就是對準你的 `aos-agent ctl state`。它只讀；什麼都不改。它不會自己放進你的提示裡：你想知道時就呼叫它。

- 總覽，每個部分一行：`{}`
- 某些部分的細節：`{"parts": ["history", "mailbox"]}`
- 每個部分的細節：`{"parts": ["all"]}`
- 要一個 JSON 物件而不是文字：加上 `"json": true`

十一個部分：`who`（名字、定義、工作區、stack；`parent`＝要求加你的那個人的 stack；`notify_box`＝要回報到哪裡（`subagent add` 會把它設成上層的 `<stack>/mailbox`；null＝回覆給你工作的那封信的 `reply_to`）；這兩個都是提出要求的人在 add 時寫的，不能證明是誰啟動你的；沒寫時是 null）、`state`（phase、你佇列裡的信、最後一次回覆）、`tools`、`llm`（腦的設定）、`system`（你的系統文字從哪來、大小和第一行）、`hooks`、`history`（多少則訊息、多大、最後幾則）、`mailbox`（在等的信）、`subagents`（你用 `subagent` 啟動的 agent，以及你的配額）、`resources`（限制、正在用的記憶體和 cpu 時間）、`time`（現在時間、你已經開了多久）。

它只給事實和數字，不給建議。讀不到的部分會寫 `not available` 和原因；其他部分照樣顯示。

要改你自己就用 `self_tools`、`self_llm`、`self_history`、`self_hook`；要停掉你自己就用 `self_ctl`（見 `aos/me.json#/self_ctl`）。

---

**`#/self_ctl`**

# 停掉你自己：self_ctl

工具 `self_ctl` 會停止、暫停、讓睡著或移除你，也就是呼叫它的那個 agent。要對另一個 agent 這樣做，用 `agents_ctl`（見 `aos/agents.json#/agents_ctl`）。每個 op 在請求送出後就立刻返回。

- `{"op": "stop"}`：你在這一步結束時停下，可能在你回覆之前。你的 stack 會留著。有人跑 `aos-agent ctl start`，你就從那裡接著做。
- `{"op": "pause"}`：你在這一步之後停住不動。只有別人的 `aos-agent ctl resume` 能讓你繼續。
- `{"op": "sleep"}`：你立刻停下，就算在這一輪的中間也一樣。`aos-agent ctl wake` 或 daemon 重新啟動會讓你回來。
- `{"op": "rm"}`：你立刻離開 daemon 的表；你的 stack 會留著。只有 `aos-agent ctl add` 能讓你回來。
- `{"op": "rm", "purge": true}`：也刪掉你的 stack（你的對話歷史和裡面所有東西）。這無法復原。

在你的工作做完了、或你不可以再繼續時用它。錯誤：ArgumentsBad、OpUnknown、PhaseBad、CtlRejected、DaemonMissing、InstanceMissing。
