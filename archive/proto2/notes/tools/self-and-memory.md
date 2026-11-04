# 兩包工具：查看自身狀態（self）與管理自身記憶（memory）

一句話：**self 讓 agent 看得到自己現在什麼樣子，memory 讓它自己動手整理 `prompts.json`。**

現況：`packs/self.py` 已經有一個 `self_status`，`packs/memory.py` 還不存在。以下是建議的樣子。

## self 包

`self_status` 會走整個資料夾算大小，有點慢，別每格都叫；只想知道現在幾點就用 `self_time`。

### self_status（已有，建議擴充）
- 參數：無。
- 回：`step`（被推幾格）、`busy`（真做事幾格）、`started`、`uptime_s`、`history_messages`、
  `history_chars`、**`history_tokens`（新增，就是字數除以 3，估的）**、
  **`history_pct`（新增，佔門檻幾成）**、`folder_bytes`、`last_usage`、`today_usage`。
- 什麼時候用：有人問你「你跑多久了」「你記憶多長」「你占多少空間」，或你自己覺得該整理記憶了。

### self_cost（新增）
- 參數：`day`（選填，`YYYY-MM-DD`，不給就今天）。
- 回：那天你這台引擎的 `prompt_tokens`／`completion_tokens`／`requests`，加上 `cost_usd`（估的）。
- 錢從哪來：**`engines.json` 每台加一個 `price`**，例如
  `"price": {"in": 0.14, "out": 0.28}`（每一百萬 token 幾美金，本機填 0）。沒填就回 `null`，不猜。
- 什麼時候用：有人問你今天花了多少、或你要決定省一點回答。

### self_who（新增）
- 參數：無。
- 回：`name`（世界資料夾名）、`world`（絕對路徑）、`parent`（父的路徑，沒有就 `null`）、
  `clock`（`shared`／`own`）、`kids`（幾個小孩＋名字）、`llm_dir`（你用哪個 LLM 資料夾）。
- 父跟鐘怎麼知道：**`aos-agent-spawn` 多寫一個 `<home>/parent.json`**：`{"parent": "...", "clock": "shared"}`。
  沒有這個檔就是頂層 agent，鐘算 `own`。
- 什麼時候用：有人問你是誰、你歸誰管、你生了誰；或你要決定「這件事我自己做還是叫小孩做」。

### self_time（新增）
- 參數：無。
- 回：`now`（本地時間字串）、`started`、`uptime_s`。很便宜，不掃資料夾。
- 什麼時候用：要寫日期、要算時間差、有人問現在幾點。

## memory 包

記憶就是 `prompts.json` 那串訊息，所以這包全部都在動那個檔。長期筆記另外放
`<home>/memory/notes/*.md`，被丟掉的東西備份到 `<home>/memory/forgotten/<時間戳>.json`（不真的刪）。

### memory_list
- 參數：`offset`（從第幾則，預設 0）、`count`（幾則，預設 20）。
- 回：一列一則：序號、`role`、前 60 字。
- 什麼時候用：要整理記憶之前先看一眼有什麼、確認要摘要／忘掉的是哪幾則。

### memory_summarize_old（第一段）
- 參數：`keep_recent`（最近幾則不動，預設 20）。
- 回：把要被壓縮的那幾則**原文**回給你，外加一句「請寫一段摘要，然後呼叫 `memory_replace_old` 交回來」。
  這一步**不會改到記憶**，只是在 `state.json` 記下 `pending_summary`（要換掉的範圍）。
- 什麼時候用：`self_status` 說記憶太長了，或有人叫你整理記憶。

### memory_replace_old（第二段）
- 參數：`summary`（你寫好的摘要文字）。
- 回：換掉幾則、現在剩幾則。把那段原文搬去 `forgotten/`，原位置塞一則
  `{"role":"user","content":"（前面的對話摘要）…"}`。沒有 `pending_summary` 就回錯誤。
- 什麼時候用：接在 `memory_summarize_old` 後面，同一輪的下一步。

**誰來摘要：agent 自己，分兩格做，不另外丟請求給 LLM。**
現有狀態機本來就是 `act`→`collect`→`llm`→`wait`→`act`，所以第一段的工具結果會自然變成下一輪的輸入，
模型下一輪寫摘要、呼叫第二段——**完全不用改狀態機，也不用新的 state**。
另開一個 LLM 請求也做得到，但那要新的等待狀態跟新的結果檔，先不做。

### memory_forget
- 參數：`from`、`to`（序號，含頭含尾）。
- 回：丟掉幾則、現在剩幾則（原文一樣進 `forgotten/`）。
- 什麼時候用：有一段對話明確沒用了、或有人叫你忘掉某件事。

### note_save
- 參數：`title`、`text`。
- 回：存到哪個檔（`<home>/memory/notes/<title 轉成檔名>-<時間戳>.md`）。
- 什麼時候用：學到一件之後還會用到的事——設定、密碼放哪、某人的偏好、某個做法。摘要之前先把重點存起來。

### note_find
- 參數：`keyword`（選填，不給就只列檔名）。
- 回：符合的檔名，有 keyword 的話再附命中的那幾行。**最土的作法：列檔名＋grep，沒有索引、沒有向量。**
- 什麼時候用：覺得「這個我之前記過」的時候先找一下再回答。

### note_read
- 參數：`name`（檔名）。
- 回：整份內容（太長截斷）。
- 什麼時候用：`note_find` 找到了、要看全文。

### self_note（改 system prompt 的替代品）
- 參數：`text`。
- 回：加到 `<home>/memory/self-note.md` 尾端，附現在總共幾行。
- 建議：**不准直接覆寫 `system-prompt.json`**（人格是使用者給的，被自己洗掉就救不回來）。
  改成 `system_text()` 在人格後面多拼一段 `self-note.md`——想改自己的行為就往這裡加一行，效果一樣，但砍不掉本體。
- 什麼時候用：發現自己老是犯同一個錯、或使用者說「你以後都要這樣做」。

## 「自動」的部分：不做成工具，agent 每格自己判斷

工具是「模型決定要不要用」，門檻檢查應該是「不管模型想不想都會發生」。最小規則，只在 `idle` 那格做：

1. 記憶字數 > **40000**：往 `new-prompts` 塞一則 `user` 訊息「你的記憶太長了，先用
   `memory_summarize_old` 整理一下」，`state.json` 記 `nudged_at_step`，一輪只塞一次。
   接下來就是模型自己走上面那兩段——**自動的只有「提醒」，動手的還是它自己**。
2. 記憶字數 > **80000**（提醒沒用的硬底線）：直接砍掉最舊的那半，原文進 `forgotten/`，
   原位置塞一則「（前面 N 則太長被截掉了）」。不摘要、不問人，就是不讓它爆掉。

門檻先寫死在 `aos_agent.py`，要調再說。

## 跟現有東西怎麼接

- 改 `proto2/packs/self.py`：加 `self_cost`／`self_who`／`self_time`，`PROMPT` 補兩句。
- 新增 `proto2/packs/memory.py`：上面八個工具，`PROMPT` 講「history 就是你的記憶」。
- 改 `proto2/aos_agent.py`：`status_of()` 加 `history_tokens`／`history_pct`；加算錢的函式；
  `spawn()` 多寫 `parent.json`；`system_text()` 尾端拼 `memory/self-note.md`；`idle` 那格加門檻檢查。
- 改 `proto2/examples/llm/engines.json`：每台加 `price`（本機 0）。
- 改 `proto2/examples/agent/agent/tools.json`：`packs` 加 `"memory"`。
- 新資料夾：`<home>/memory/`，底下 `notes/`、`forgotten/`、`self-note.md`。
- `proto2/README.md` 補一小節。

## 現在故意不做

- token 是字數除以 3 估的，跟真的差很多。
- 錢只算 in／out 兩個單價，快取命中、思考 token 另計價一律不管。
- 摘要走到一半模型不呼叫第二段，`pending_summary` 就一直晾著（下次呼叫第一段會蓋掉）。
- 同時有兩個東西改 `prompts.json`（沒有鎖）。
- `forgotten/` 永遠不清，會一直長大。
- 筆記只有 grep，沒有語意搜尋、沒有索引、沒有自動去重。
- `folder_bytes` 對很大的資料夾很慢，也不排除 `__pycache__`。
- 小孩被 daemon `unregister` 掉了，`self_who` 還是說它有那個鐘。

## 要拍板的

1. 錢就在 `engines.json` 每台加 `price: {in, out}`（每百萬 token 美金，本機 0）——這樣做？**建議：做，沒填就不報價。**
2. 摘要用「自己分兩格做」，不另外丟 LLM 請求？**建議：是，狀態機一行都不用改。**
3. 允不允許 agent 改自己的 system prompt？**建議：不准覆寫，只准往 `self-note.md` 加，拼在人格後面。**
4. 自動門檻（40000 提醒／80000 硬砍）先寫死？**建議：先寫死，之後要調再搬進設定檔。**
5. 長期筆記放 `<home>/memory/notes/*.md`、丟掉的進 `<home>/memory/forgotten/`——版面 OK？**建議：OK，先不做索引。**
