← [工具大開發時代](README.md)｜[notes 索引](../README.md)

# 工具清單

## 怎麼讀

每個工具一段，欄位固定：

- **給誰**：模型（進工具檔、模型叫）／人（命令列）／兩者（兩邊都有，同一份程式）。
- **輸入輸出**：模型工具照 base 慣例——stdin 收 arguments JSON、成功印純文字退 0、失敗 stdout 最後一行 `{"ok": false, "error": 代號, "message": …}` 退 1（[tools/README](../../tools/README.md)）。人用的照 aos 指令慣例：`--target`、`-h`、`--json`。
- **進牢**：要不要照 [agent-access](../2026-09-24-agent-access/README.md) 進 bwrap。「不用」＝它本身只碰固定位置、模型選不了路徑。
- **LLM**：這支工具**自己**會不會叫模型（不是「給模型用」）。
- **六軸**：粗估，照 [axes.md](axes.md)：L＝LLM 參與、S＝穩、R＝資源、F＝快、H＝人易懂、B＝邊界；5 最好。是設計目標，做完要實測改分。
- **難度**：小（半天內，一支程式＋測試）／中（1～2 天，碰 aos-agent 或規範）／大（要新規範或多方配合）。
- **波**：在 [plan.md](plan.md) 哪一波。

共同規則（proto2 教訓，**所有工具都照**）：
1. **規則放工具，不放人格**——人格寫的模型會忘，工具擋的它繞不過。
2. **不給模型「等」的工具**——會原地輪詢、自己等自己；要等就結束這一輪，結果到了是新輸入。
3. **工具描述越短越好**——proto2 的 prompt 有 96% 是 token，一半是用不到的工具表。每個工具包附「最小組」，角色只裝用得到的。
4. **能寫死就寫死**——接單、派工、回報、驗收、交付都是搬東西。

---

## A. 團隊與交流（workflows 團隊的骨架）

### T-team

**`aos-team` 指令＋`team.json` 名冊**。給：人。
一個團隊＝一個資料夾：`team.json`（成員：名字、角色、agent 家路徑、模型代號、工具包）＋`team/`（`mail.log`、`tasks/`、`routines.json` 等）。
指令：`aos-team init --config team.json`（照角色生各成員的家、裝工具包、寫人格）、`start`／`stop`（全員登記／撤銷）、`ls`（一行一成員：health、手上單號、最後一封信）、`ask "…"`（交給門房）、`answer`（見 T-ask）、`score`（見 T-score）。
進牢：不用（人跑）。LLM：不叫。依賴：`aos-agent init／start／stop／status`、`tools add`。
六軸：L5 S4 R5 F5 H5 B4。難度：中。波：一。
取代教程 05 的 `for` 迴圈；proto2 `presets/studio/team.json` 可參考欄位（`only` 白名單、`inline_mail`），但**不採** proto2 的狀態機寫死在工具裡。

### T-say

**`team_say` 工具**（模型寄信）。給：模型。
輸入 `{"to": "lead", "status": "DONE", "reply_to": "t-0007", "text": "…"}`；輸出 `sent t-0007 DONE → lead (outbox/…json)`。
只寫自己家的 `outbox/`（檔名唯一、先 `.tmp` 再 rename）；`to` 不在名冊、`status` 不在六個白名單＝`BadArguments`（訊息列出可用的）。角色可限制寄給誰（工人只能寄領隊，名冊寫）。
進牢：一波不用（固定寫 `outbox/`）；二波進牢時 `outbox/` 映射成可寫。LLM：不叫。依賴：`team.json`。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-post

**郵差＋書記**（一支機械程式，kernel 反覆工作）。給：系統（人看它的紀錄）。
每次跑：掃所有成員的 `outbox/` → 驗格式 → 投進收件人 `input/`（格式同 `aos-agent say`，開頭加一行 `【來信 A → B · STATUS · 單號】`）→ 原檔搬進 `outbox/done/` → `team/mail.log` 記一行。
收到 DONE 且單號有交接書＝叫 T-verify；NEEDS-USER＝寫進人的待辦（T-ask）；REQUEST 派出＝`SESSION-LOG.md` 加行、DONE 驗過＝刪行。
**看門**：成員手上有單（任務表 `assignee`）、`state` 是 idle、最後一封信之後超過 N 分鐘沒動靜＝替他寄 BLOCKED「接了事沒回終局狀態」給領隊。
崩在半路：每封信「投遞→搬檔→記行」三步都可重跑（收件端檔名＝信的唯一 id，已在就跳過）。
進牢：不用（它在牢外，是牆的一部分）。LLM：不叫。依賴：`aos-kernel add`（反覆）、agent 的 `input` 規則。
六軸：L5 S4 R3（每秒醒一次）F5 H5 B3。難度：中。波：一。

### T-route

**門房**（`aos-team ask` 裡的前濾網）。給：人（間接）。
輸入一句話；比對 `team/routes.json`：每條 `{"match": 正規式或關鍵字, "do": "tool"|"handoff"|"lead", …}`。
`tool`＝直接跑一支機械工具（例 `wf_lint`、列待辦、看信箱）並把輸出當回話；`handoff`＝照模板生交接書投給工人（正規式的具名群組填進模板）；都沒中＝原話投給領隊。每次命中與否記 `team/route.log`（之後 T-crystal 用）。
`routes.json` 初版可從 `WORKFLOWS.md` 派發表半自動抽（觸發詞欄）。
進牢：不用。LLM：不叫。依賴：T-team、T-handoff。
六軸：L5 S5 R5 F5 H4 B5。難度：小～中。波：一。

### T-handoff

**交接書**：`handoff` 工具（領隊開單）＋任務表 `team/tasks/*.json`。給：兩者（人用 `aos-team task ls/show`）。
輸入 `{"assignee": "worker-1", "workflow": "wf/workflows/tidy/README.md", "goal": "…", "done_when": [{"kind": "cmd_ok", "cmd": "…"}, {"kind": "file_exists", "path": "…"}, {"kind": "table_filled", "path": "…", "column": "…"}, {"kind": "judge", "text": "原意沒變"}]}`。
輸出 `t-0007 → worker-1`，同時經 `outbox/` 寄出 REQUEST。`done_when` 只准這四種（workflows「Done when 只准三類」＋一類要人判斷的 `judge`）；空的＝`BadArguments`。
進牢：一波不用（寫 `team/tasks/` 固定位置，透過郵差代寫更好：工具只寫 outbox，郵差建單）。LLM：不叫。依賴：T-say、T-post。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-verify

**驗收員**。給：兩者（郵差叫；人 `aos-team verify t-0007`；模型也能叫來自己先驗）。
跑交接書的機械條目：`file_exists`、`cmd_ok`（`cmd` 是 argv 陣列，不過 shell；逾時預設 120 秒；cwd＝專案根）、`table_filled`（`wf-table/1` 資料檔或 md 表格某欄全非空）。
輸出每條一行 `PASS/FAIL 條目：原因`；有 `judge` 條目時最後一行 `待審查 N 條`。
進牢：`cmd_ok` 要（跑任意指令）；一波先限制 `cmd` 只能是名冊白名單裡的指令（`wf-lint.sh`、`grep -c`、`test -e`…），二波再開放進牢跑任意。LLM：不叫。
六軸：L5 S4 R4 F4 H5 B3（一波）→B4（二波）。難度：小。波：一。

### T-ask

**`ask_human` 工具＋`aos-team answer`**。給：兩者。
模型：`{"question": "…", "options": ["A", "B"], "default": "A", "reply_to": "t-0007"}` → 寫進 `team/wait-user/`，書記同步到 `WAIT_USER.md`。人：`aos-team answer q-0003 "B"`（或 `talk` 裡 `/answer`）→ 以 `【人 → worker-1 · 回覆 q-0003】` 投回給發問的 agent，刪那條待辦。
進牢：不用（固定寫 outbox）。LLM：不叫。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-beat

**心跳**（機械，kernel 反覆工作）。給：系統；人用 `aos-team routine ls/add`。
讀 `team/routines.json`（間隔表：項目、週期、執行者、上次執行）與 `team/schedule.json`（絕對時刻、內容、執行者），用現在時間比；到期就寄 REQUEST 給執行者（經郵差），**回 DONE 才**改「上次執行」／刪列（中途崩了不會算做過）。錯過太久的**不自己判**要不要補，寄給領隊問（workflows 原本也是交給 agent 判斷）。
格式照 heartbeat 包的兩張表，存 `wf-table/1` JSON（>1 KB 走資料檔的規矩）。
進牢：不用。LLM：不叫。依賴：T-post、`aos-kernel add`。
六軸：L5 S4 R4 F5 H5 B5。難度：小。波：一（可延到二，驗收例子用不到）。

### T-lock

**`lock` 工具**（workflows `resources.md` 的 mkdir 鎖）。給：兩者。
`{"op": "acquire"|"release"|"ls", "name": "…"}`；acquire 失敗立即回 `Busy`＋持有者，**不等**。鎖在 `team/locks/<名>/owner`。持有者的 agent 被 stop 或閒著超過 N 分鐘＝郵差回收並通知。
進牢：不用。LLM：不叫。六軸：L5 S4 R5 F5 H4 B5。難度：小。波：二（兩個工人才會搶）。

---

## B. 記憶與 prompt history（`/context`、`/compact`）

現況：`talk` 有 `/context`（人格＋記憶＋工具的字數表）、`/history`（規範 `spec/aos-agent/cli-talk-repl.md` 在 talk 那隊的分支，還沒進 main）。記憶是 `prompts/history.json` 整份讀寫、**沒有上限**（agent 規範自己寫「記憶太長怎麼辦之後再說」）。

### T-context

**`aos-agent context`**（把 talk 的 `/context` 升成子命令）＋模型工具 `context`（唯讀）。給：兩者。
人：`aos-agent context --target 家 [--json] [--by-round]`：送給模型的東西多大（人格、記憶按 role、工具描述、合計；估 token＝字數÷估算係數），`--by-round` 每輪一行（哪輪最胖、胖在哪個工具結果）。
模型：`context` 回「你的記憶 N 則、約 K token、最胖的三則是…」，讓它知道何時該要求壓縮。
進牢：模型那支要唯讀看自己家的記憶——**家是信任資料**，二波要映射成唯讀（或由 aos-agent 在送件前把數字寫進一個小檔給它看）。LLM：不叫。依賴：talk 的 `/context` 算法（同一個函式）。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一（人用）／二（模型用）。

### T-compact

**`aos-agent compact`**（機械壓縮記憶）。給：人；模型只能用 `compact_request` 申請。
做法（預設**不叫模型**）：持 `.tick.lock`、只在 `idle` 且沒 `batch`／`intake` 時做；舊記憶原樣搬到 `prompts/archive/<時間>.json`；新記憶＝最後 N 輪＋前面每輪留「user 原話＋最後一則 assistant 回話」，中間的工具呼叫與結果換成一行 `[已壓縮：叫了 read×3、bash×1，全文在 archive/…]`。**tool_call 與 tool 結果成對刪**（不然模型端會 400）。
選項：`--keep-rounds N`、`--max-tool-chars C`（只截長結果，不刪輪）、`--dry-run`（印會變成怎樣）、`--summarize`（**三波**：交給一個摘要 agent 寫一段摘要當第一則 user 訊息；有模型，結果要過「摘要不能比原文長」等機械檢查）。
模型端：`compact_request {"reason": "…"}` 只寫一個旗標檔，tick 在下次 idle 時照家裡 `info` 設的規則做（模型不能自己選刪什麼）。另可設自動：記憶超過 X token 就在 idle 時做（proto2 是 40000 字提醒、80000 字砍半）。
進牢：人跑不用；模型只寫旗標。LLM：預設不叫。依賴：tick 鎖、`state.json` 規則（`base_len` 要一起改——`batch` 是 null 時才做，所以不衝突）、talk `/compact` 可直接叫它。
六軸：L5 S4 R5 F5 H4 B4。難度：中（碰記憶與 tick 的恢復規則，要改 agent 規範一節）。波：一。

### T-notes

**`note` 工具**（長期筆記，跟對話記憶分開）。給：兩者（人 `aos-agent notes ls/show`）。
`{"op": "add"|"find"|"get"|"rm", "key": "…", "text": "…", "tags": […]}`；存成一個 `notes.json`（`wf-table/1` 格式，人和 `tabledb.py` 都讀得懂）。`find` 是關鍵字＋tag 比對，**不做向量搜尋**（不叫模型、不要額外服務）。
每輪送模型時不自動塞筆記（省 token）；模型要用就 `find`。proto2 的 `self_note` 只能追加、不能改人格——照採。
進牢：要寫到家外的映射（`amy-notes`；[agent-access](../2026-09-24-agent-access/README.md) 第 2 題預設「self 唯讀，要寫另映射」）。一波可先放在工作根目錄底下。LLM：不叫。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一（放工作區）／二（映射）。

### T-recall

**`recall` 工具**：在壓縮掉的 `prompts/archive/` 與封存的輸入（`done/`）裡找原文。給：模型。
`{"query": "…", "limit": 5}` → 命中的幾段（哪一輪、原文前後幾行）。純 grep。
進牢：要唯讀看家裡的 archive（二波映射）。LLM：不叫。六軸：L5 S5 R5 F4 H4 B4。難度：小。波：二。

---

## C. 特定檔案修改

### T-json

**`json_edit` 工具＋`aos-json` 指令**。給：兩者。
`{"path": "…", "op": "get"|"set"|"del"|"append"|"merge", "pointer": "/a/b/0", "value": …}`；用 JSON Pointer（RFC 6901）定位，**不用字串取代**（模型改 JSON 最常壞在逗號、括號）。寫法：暫存檔＋rename；改完重新解析一次確定是合法 JSON；保留原縮排（偵測 2／4 空白或單行）。
`--check-directives`：改的是 aos 設定檔時，順便用 `lib/aos_directives.py` 把指示詞解一次，解不過就不寫。
進牢：跟 base 一樣關在工作根目錄；**永遠不准改信任資料**（`info.json`、工具檔、`access.json`——改這些走 T-access-req 或人手）。LLM：不叫。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一（工作根目錄內）。

### T-md

**`md_section` 工具**：按標題改 Markdown 一節。給：兩者。
`{"path": "…", "heading": "## 3. 逐段處理〔導入判斷〕", "op": "get"|"replace"|"delete"|"append_item"|"remove_item", "text": "…"}`。標題要剛好一個（`NotUnique` 列出行號）。`append_item`／`remove_item` 專給 SESSION-LOG／WAIT_USER 這種「一行一項」的清單（照 `- [工作流] 狀態 → 下一步` 格式驗）。
進牢：同 base。LLM：不叫。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-wf

**workflows 工具包 `wf`**：把 `~/repo/workflows/tools` 的腳本包成模型工具。給：模型（人本來就能直接跑腳本）。
- `wf_init {"flavor": ["heartbeat"], "non_invasive": "wf"}` → 跑 `wf-init.sh --target <工作根目錄>`，回殘留清單。
- `wf_lint {"strict": true}` → 跑 `wf-lint.sh`，回 `TOTAL …` 那行＋前 50 條問題（全文另存檔）。
- `wf_table {"op": "get"|"find"|"add"|"update"|"delete", "file": …, …}` → `tabledb.py`，原樣回 JSON。
- `wf_residue {}` → 數 `{{`、〔導入判斷〕、〔模板說明〕各幾處、在哪（純 grep；IMPORT 的 Done when）。
- `log_line` 用 T-md 的 `append_item`／`remove_item`，不另做。
workflows 的腳本**複製一份進工具包**（記版本戳），不直接指到 `~/repo/workflows`（那邊唯讀、會變）。
進牢：跑 bash 腳本，二波進牢；一波工作根目錄是拋棄式的測試專案。LLM：不叫。
六軸：L5 S5 R4 F4 H5 B3（一波）。難度：小（主要是包裝＋測試）。波：一。

### T-directive

**`aos-directives` 指令**：把一個 aos JSON 檔的指示詞（`$env`／`$ref`／`$fmt`／`$opt`）解開印出來、或只驗。給：人（除錯用）。
`aos-directives resolve FILE [--center DIR] [--pointer /x]`、`check FILE`。直接用 `lib/aos_directives.py`。
進牢：不用。LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：一（順手）。

### T-access-req

**`access_request` 工具**：模型**申請**碰某個資料夾，不能自己改 `access.json`。給：模型；人用 `aos-team answer` 或 `aos-agent access set` 批。
`{"name": "notes", "path_hint": "…", "mode": "ro"|"rw", "why": "…"}` → 走 T-ask 的待辦。批了由**人的指令**寫表（另一隊在做的 `aos-agent access set`）。
進牢：不用。LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：二（要牆存在才有意義）。

---

## D. agent 創造與修改

### T-template

**`aos-agent init --template NAME`**＋模板資料夾 `proto5/templates/<名>/`（人格、工具包清單、`info.json` 片段）。給：人。
內建三個：`coder`（base）、`lead`／`worker`／`reviewer`（workflows 團隊用）。`aos-team init` 就是對名冊每一列叫它。
進牢：不用。LLM：不叫。依賴：`init`（規範已寫「`init --template` 這輪不做」，要改一節）、`tools add`。
六軸：L5 S5 R5 F5 H5 B5。難度：小～中。波：一（跟 T-team 同一隊）。

### T-persona

**改人格**：模型不能直接改（人格是信任資料）。給：人（`aos-agent persona show/set/append`）；模型只能 `persona_propose`（寫提案進待辦，人批）。
proto2 的 `improve_prompt` 只能改 `prompt-overrides/`、模型曾拒絕寫使用者要的教訓——照採「提案、人批」。
進牢：不用。LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：二。

### T-spawn

**模型生新 agent**。給：模型（領隊）。
`{"template": "worker", "name": "worker-3", "reason": "…"}` → 只能從名冊允許的模板生、數量有上限（名冊 `max_members`）、生出來的權限不超過生它的人（邊界不擴大）；實際由郵差（牢外）叫 `aos-team add-member`。
proto2 `kids` 的教訓：深度、兩種鐘、自動轉寄都搞混過——**一律平的**（沒有父子樹，全是團隊成員）、一律經郵差交流。
進牢：不用（寫提案）。LLM：不叫。六軸：L5 S3 R2（每個多一份反覆工作）F4 H4 B3。難度：中。波：三。

---

## E. 造工具的工具

（另一隊在做的 `aos-agent tools ls/add/rm/alias`，這裡不重複。）

### T-toolnew

**`aos-agent tools new NAME [--lang py|sh]`**：生一個工具包骨架。給：人。
生 `NAME/NAME.json`（一個工具的範例描述）、`NAME/run`（讀 stdin JSON、照 base 的錯誤格式）、`NAME/_common.py`（複製 base 那份的最小版）、`NAME/test_NAME.py`、`NAME/README.md`（一頁）。
進牢：不用。LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：一（順手）。

### T-tooltest

**`aos-agent tools test NAME|DIR [--args JSON] [--case FILE]`**：用跟 aos-agent 一模一樣的方式（cwd＝agent 家、stdin、`_meta` 解指示詞、逾時）跑一次工具，並驗工具檔格式、描述長度（token 估算，對應資源軸）。給：兩者（模型版 `tool_try` 給 T-toolsmith 用）。
`--case` 吃一個「輸入→期待輸出片段」的清單，跑完印 PASS/FAIL＝工具的穩定軸自動量。
進牢：跑的是任意程式，二波進牢。LLM：不叫。六軸：L5 S5 R5 F5 H5 B3→B5。難度：小～中。波：一（人用）。

### T-wrap-py

**`aos-agent tools wrap-py FILE.py [--only f,g] [--name PACK]`**：讀一個 Python 檔，把裡面的函式變成工具包。給：人（模型版在三波）。
做法（**不叫模型**）：用 `ast` 讀（**不 import、不執行**），挑頂層、非底線開頭、有型別註解的函式；參數型別 → JSON Schema（`str`/`int`/`float`/`bool`/`list[...]`/`dict`/`Literal`/`Optional`；認不得的＝`string`＋警告）；docstring 第一段 → `description`（沒 docstring＝警告，描述用函式名）；預設值 → 非必填。
產出一個工具包：`PACK.json`＋`run`（`run <函式名>` 從 stdin 讀 arguments、import 原檔、叫函式、回傳值是 str 就原樣印，不是就印 JSON；例外→base 的錯誤 JSON）＋原檔副本（記 sha256，原檔變了 `tools test` 會提醒）。
印一張表：每個函式 → 收了／跳過（為什麼）。`--describe-with-llm`（三波）：沒 docstring 的請模型補描述，人看過才寫進去。
進牢：產生時不執行；**跑的時候是任意 Python**，二波一定進牢（一波只給人在自己信任的檔上用）。LLM：預設不叫。依賴：T-toolnew 的骨架、T-tooltest。
六軸：L5 S4 R4（每次呼叫起一個 Python）F4 H5 B2→B5（進牢後）。難度：中。波：二（要牆）；產生器本身一波就能做、先給人用。

### T-wrap-cli

**`tools wrap-cli CMD`**：從一支指令的 `--help`／argparse 定義生工具（例 `ffmpeg`、`git log`）。有 argparse 的 Python 腳本可靜態讀；其他要解析 help 文字——不穩，可能要模型。給：人。
LLM：可能要（解析 help）。六軸：L3 S3 R4 F4 H4 B2。難度：大。波：三。

### T-toolsmith

**模型造工具**：`tool_draft {"name", "description", "parameters", "code": "…", "lang": "py"}` 寫進 `tools-staging/<名>/`，自動跑 T-tooltest；**安裝要人**（`aos-agent tools add ./tools-staging/<名>`）。給：模型。
proto2 toolsmith 自評 9/10、但沒沙箱沒逾時——這裡補：staging 裡的測試在牢裡跑、有逾時、裝不裝人決定。
進牢：一定。LLM：工具本身不叫（模型是使用者）。六軸：L4 S3 R4 F4 H4 B4。難度：中。波：三。

---

## F. 量測與系統

### T-score

**`aos-team score [--task t-0007]`**：六軸量表自動填能量的部分。給：人。
讀各成員的記憶（問模型次數、工具次數與失敗數）、輸入封存檔名的時間（收話時刻）、`team/mail.log`（每步誰做、幾點）、kernel 回音的 `ms`（有留的話），印 [axes.md §5](axes.md#5-模板複製去填) 那張表的 L、S（本次成敗）、R（cpu 秒、token）、F（牆上時間與「時間花在哪」：等 tick／等模型／跑工具）；H、B 留空給人填。`--json` 給比較用。
進牢：不用。LLM：不叫。六軸：L5 S4 R5 F5 H5 B5。難度：中（資料散在好幾處）。波：一（驗收要用）。

### T-pool

**工具檔 `_pool` 欄**（priority-and-shared-cpu 提案，`notes/2026-09-24-priority-and-shared-cpu/`）：某支工具走指定的池（例：GPU 工具一顆 cpu 排隊）。給：人（寫工具檔）。
規範改 agent info §3.3、aos-agent send §5.2；程式十幾行。LLM：不叫。六軸：L5 S5 R4 F4 H5 B5。難度：小。波：二（驗收例子用不到；T-verify、T-wf 的慢工具可放別池時再用）。
（那份提案在 commit 64a3427，還沒進 main。）

### T-crystal

**固化建議**（ai_core §3.6 的「固化引擎」最小版）：讀 `team/route.log` 與領隊的記憶，找「門房沒中、領隊每次都派到同一條工作流」的句型，列成 `routes.json` 的候選規則給人批。給：人。
第一版純統計（同一條工作流被派 ≥ 3 次、原話共同的關鍵字）；要模型歸納句型的是第二版。
LLM：第一版不叫。六軸：L5 S4 R5 F5 H4 B5。難度：中。波：三。

---

## 總表

| 名 | 一句 | 給誰 | LLM | 牢 | 難度 | 波 | 人也要 CLI |
|---|---|---|---|---|---|---|---|
| T-team | 名冊＋`aos-team` | 人 | 否 | 否 | 中 | 一 | 是（本來就是） |
| T-say | 寄信 | 模型 | 否 | 二波映射 | 小 | 一 | 否（人用 `say`） |
| T-post | 郵差＋書記 | 系統 | 否 | 牢外 | 中 | 一 | `aos-team mail` 看紀錄 |
| T-route | 門房 | 人（間接） | 否 | 否 | 小～中 | 一 | `aos-team ask` |
| T-handoff | 交接書＋任務表 | 兩者 | 否 | 否 | 小 | 一 | `aos-team task` |
| T-verify | 驗收員 | 兩者 | 否 | cmd 要 | 小 | 一 | `aos-team verify` |
| T-ask | 問人／人回 | 兩者 | 否 | 否 | 小 | 一 | `aos-team answer` |
| T-beat | 心跳 | 系統 | 否 | 否 | 小 | 一（可延） | `aos-team routine` |
| T-lock | 資源鎖 | 兩者 | 否 | 否 | 小 | 二 | 是 |
| T-context | 送模型的東西多大 | 兩者 | 否 | 二波唯讀 | 小 | 一／二 | `aos-agent context` |
| T-compact | 機械壓縮記憶 | 人（模型申請） | 預設否 | 否 | 中 | 一 | `aos-agent compact` |
| T-notes | 長期筆記 | 兩者 | 否 | 二波映射 | 小 | 一／二 | `aos-agent notes` |
| T-recall | 找壓縮掉的原文 | 模型 | 否 | 二波唯讀 | 小 | 二 | — |
| T-json | JSON Pointer 改檔 | 兩者 | 否 | 同 base | 小 | 一 | `aos-json` |
| T-md | 按標題改 md | 兩者 | 否 | 同 base | 小 | 一 | 是 |
| T-wf | workflows 工具包 | 模型 | 否 | 二波 | 小 | 一 | 否（人跑原腳本） |
| T-directive | 解／驗指示詞 | 人 | 否 | 否 | 小 | 一 | `aos-directives` |
| T-access-req | 申請碰資料夾 | 模型 | 否 | 否 | 小 | 二 | — |
| T-template | 模板生家 | 人 | 否 | 否 | 小～中 | 一 | `init --template` |
| T-persona | 人格提案／人改 | 兩者 | 否 | 否 | 小 | 二 | `aos-agent persona` |
| T-spawn | 模型生成員 | 模型 | 否 | 否 | 中 | 三 | — |
| T-toolnew | 工具骨架 | 人 | 否 | 否 | 小 | 一 | `tools new` |
| T-tooltest | 照 aos 的方式試跑工具 | 兩者 | 否 | 二波 | 小～中 | 一 | `tools test` |
| T-wrap-py | Python 檔 → 工具包 | 人 | 預設否 | 跑時要 | 中 | 二 | `tools wrap-py` |
| T-wrap-cli | 指令 → 工具包 | 人 | 可能 | 跑時要 | 大 | 三 | `tools wrap-cli` |
| T-toolsmith | 模型寫工具、人裝 | 模型 | 否 | 要 | 中 | 三 | — |
| T-score | 六軸自動量 | 人 | 否 | 否 | 中 | 一 | `aos-team score` |
| T-pool | 工具指定池 | 人 | 否 | 否 | 小 | 二 | 寫工具檔 |
| T-crystal | 固化建議 | 人 | 第一版否 | 否 | 中 | 三 | `aos-team crystal` |

29 個工具裡**只有 T-wrap-cli 可能要模型**，T-compact／T-wrap-py 的模型選項都在第三波、預設關。模型在團隊裡只出現在三個 agent 的「想」那一步。
