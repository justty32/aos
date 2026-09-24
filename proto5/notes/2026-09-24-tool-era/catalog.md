← [工具大開發時代](README.md)｜[notes 索引](../README.md)

# 工具清單

## 怎麼讀

每個工具一段，欄位固定：

- **給誰**：模型（進工具檔、模型叫）／人（命令列）／兩者（兩邊都有，同一份程式）。
- **輸入輸出**：模型工具照 base 慣例——stdin 收 arguments JSON、成功印純文字退 0、失敗 stdout 最後一行 `{"ok": false, "error": 代號, "message": …}` 退 1（[tools/README](../../tools/README.md)）。人用的照 aos 指令慣例：`--target`、`-h`、`--json`。
- **進牢**：要不要照 [agent-access](../2026-09-24-agent-access/README.md) 進 bwrap。注意那份契約是「**有 access 表就全部工具關牢**」，不能逐支挑著繞過；這裡寫「牢外」的都是**機械員**（郵差、心跳），它們本來就不是 agent 的工具。
- **LLM**：這支工具**自己**會不會叫模型（不是「給模型用」）。整條流程裡模型出現在哪，看 [workflows-as-team](workflows-as-team.md)。
- **六軸**：粗估，照 [axes.md](axes.md)：L＝LLM 參與、S＝穩、R＝資源、F＝快、H＝人易懂、B＝邊界；5 最好。是設計目標，做完要實測改分。
- **難度**：小（半天內，一支程式＋測試）／中（1～2 天，碰 aos-agent 或規範）／大（要新規範或多方配合）。
- **波**：在 [plan.md](plan.md) 哪一波。

共同規則（proto2 教訓，**所有工具都照**）：
1. **規則放工具，不放人格**——人格寫的模型會忘，工具擋的它繞不過。
2. **不給模型「等」的工具**——會原地輪詢、自己等自己；要等就結束這一輪，結果到了是新輸入。
3. **工具描述越短越好**——proto2 的 prompt 佔 96% 的 token，其中一半是用不到的工具表。每個工具包附「最小組」，角色只裝用得到的。
4. **能寫死就寫死**——接單、派工、回報、驗收、交付都是搬東西。
5. **一份資料一個寫的人**（審查 S6）——暫存檔＋rename 只防半截檔，防不了「兩人讀改寫、後寫蓋前寫」。任務表、SESSION-LOG、WAIT_USER、名冊只有郵差寫；模型要改都是寄申請。模型直接改的檔（`json_edit`、`md_section`）帶 `expect_sha`：讀的時候拿到 sha，寫的時候對不上就 `Conflict`。

---

## A. 團隊與交流（workflows 團隊的骨架）

### 團隊資料夾（A 段共用的地基）

```text
<團隊>/
  team.json                名冊（格式在 plan.md）
  members/<名>/            各成員的 agent 家（input 一律是資料夾 input/）
  team/
    outbox/<名>/           成員寄出的信與申請（成員唯一可寫的團隊位置；二波映射成 rw）
    post/sent/<信 id>.json  郵差的投遞紀錄＝去重憑據（一封一檔）
    tasks/<單號>.json       任務表（只有郵差寫）
    wait-user/<q-id>.json   等人回答的
    events/<名>.jsonl       事件紀錄（T-events）
    routes.json  routines.json  schedule.json  route.log
```

**outbox 放團隊資料夾、不放成員家裡**（審查 M11）：成員家是信任資料，二波關牢後工具寫不到家裡；一開始就放外面，二波不用搬。寄件人身分**由郵差看信在哪個 `outbox/<名>/` 認定**，信裡寫的 `from` 只是抄寫，對不上就退回。

### T-team

**`aos-team` 指令＋`team.json` 名冊**。給：人。
指令：`aos-team init --config team.json`（照模板生各成員的家、裝工具包、寫人格）、`start`／`stop`（全員登記／撤銷）、`ls`（一行一成員：health、手上單號、最後一封信）、`ask "…"`（交給門房）、`answer`（T-ask）、`task ls/show/cancel`（T-handoff）、`mail [--follow]`（把 `post/sent/` 照時間排好印，一封一行）、`verify`、`routine`、`score`。
LLM：不叫。依賴：`aos-agent init／start／stop／status`、`tools add`、T-template。
六軸：L5 S4 R5 F5 H5 B4。難度：中。波：一。
取代教程 05 的 `for` 迴圈；proto2 `presets/studio/team.json` 可參考欄位（`only` 白名單），但**不採** proto2 把狀態機寫死在工具裡、由工具推著跑的做法。

### T-say

**`team_say` 工具**（模型寄信）。給：模型。
輸入 `{"to": "lead", "status": "DONE", "reply_to": "t-0007", "rev": 2, "text": "…"}`；輸出 `queued <信 id> DONE → lead`。
只寫 `team/outbox/<自己>/<信 id>.json`（暫存檔＋rename）；`to` 不在自己的 `mail_to`、`status` 不在六個白名單＝`BadArguments`（訊息列出可用的）。**不能用來派工**——派工只能用 `handoff`（審查 M4：避免同一件事派兩次）。
LLM：不叫。依賴：`team.json`。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-post

**郵差＋書記**（一支機械程式，kernel 反覆工作，例 1 秒一次）。給：系統；人看 `aos-team mail`。

**投遞一封信（每步都可重跑，審查 M2）**：
1. 讀 `outbox/<名>/<id>.json`、驗格式與身分；不合＝投一封 `FAILED 退信` 給寄件人、原信搬進 `outbox/<名>/rejected/`。
2. `post/sent/<id>.json` **已在**＝投過了，跳到第 4 步。
3. **投進收件人的 `input/`**：檔名固定 `mail-<id>.json`，用 `aos-agent say` 的**同一個投檔函式**（`link` 不覆蓋；EEXIST＝這封已在，當投過）。投之前先查「這封是不是其實已經投過、被收走了」：收件人 `input/done/mail-<id>.json.*.done` 存在、或收件人 `state.json` 的 `intake.files` 有它＝投過了。都沒有才投。→ 寫 `post/sent/<id>.json`（投遞紀錄：誰寄誰、狀態、單號、時間、投到哪）。
4. 原信搬進 `outbox/<名>/done/`（已在就略過）。
5. **後續動作**（DONE→叫驗收、REQUEST→書記記一行…）寫在投遞紀錄的 `effects` 欄，一個做完勾一個；崩了重跑只做沒勾的。

`mail.log` 不另寫：**投遞紀錄本身就是紀錄**，`aos-team mail` 照時間印出來。所以不會有「投了沒記」。
紀錄保留（審查 S7）：`post/sent/` 預設留 30 天；清之前先確認收件人 `input/` 與 `done/` 都沒有那封（否則留著，免得重投）。

**順序與時機（審查 M3）**：
- agent **只在 idle 收輸入**：它在想或在跑工具時到的信，要等這一輪做完才看到；**第一版沒有「插話取消」**，要中途喊停用 `aos-team task cancel`（郵差寫取消紀錄，並在那人下次 idle 時投一封 `REQUEST 取消 t-0007`）或人 `aos-agent pause`。
- 一次可能收到好幾封（同一次 intake）；同一次裡的順序是**檔名順序，不是時間順序**（`mail-…` 會排在人的 `say-…` 前面）。所以信頭一行一定帶時間：`【來信 worker-1 → lead · DONE · t-0007 rev2 · 09-25 10:03:12】`。保證的只有：**不丟、不重複**。
- 人 `say` 與郵差投同一個 `input/` 不會互蓋：兩邊檔名不同、都用 link 投。

**書記**（同一支程式）：派出 REQUEST＝`SESSION-LOG.md` 加一行；任務 `done`＝刪那行；NEEDS-USER＝`WAIT_USER.md` 加一行，答了刪。**只有它寫這兩個檔**（共同規則 5）。

**看停滯（審查 M5）**：不看「是不是 idle」，看 T-events 的紀錄：派出時間、收件時間（信從 `input/` 消失）、最後進展（記憶變長、寄出信、工具回來）、健康（`aos-agent status` 第一行）。
「收了單、超過 `stale_minutes` 沒進展、也不是在等別人（`waiting_on` 空）」或「健康不是 ok（卡在 think／act、kernel 壞）」＝寄一封 `PROGRESS 觀察到停滯：…（最後進展 10:03）` 給領隊與人；**同一次停滯只報一次**。它只報看到的事，不替工人說 BLOCKED。

驗收**不在郵差裡同步跑**（審查 S2）：DONE 到了就 `aos-kernel add --once` 一份驗收工作，下一輪收回音。
進牢：牢外（機械員）。LLM：不叫。依賴：`say` 的投檔函式、agent `state.md §4.1` 的收件規則、`aos-kernel add`。
六軸：L5 S4 R3（每秒醒一次，實測後改）F5 H5 B3。難度：中。波：一。

### T-route

**門房**（`aos-team ask` 的前濾網）。給：人（間接）。
比對 `team/routes.json`：每條 `{"pattern": 正規式（整句）, "do": "tool"|"handoff", "args"/"template": …, "tests": {"hit": […], "miss": […]}}`。
規則：**整句句型比對，不是關鍵字**；參數要齊（具名群組都有值）；**命中兩條以上或含否定詞（不要、別、取消…）＝落穿給領隊**（審查 S3：「不要導入 heartbeat」不能觸發導入）。每條規則自帶命中／不該命中的例句，`aos-team route test` 全跑過才准存。
`tool`＝直接跑一支機械工具並回話；`handoff`＝照模板開單（T-handoff）；沒中＝原話投給領隊。每次結果記 `team/route.log`。
LLM：不叫（保證範圍只到規則寫明的句型）。依賴：T-team、T-handoff。
六軸：L5 S5 R5 F5 H4 B5。難度：小～中。波：一。

### T-handoff

**交接書＋任務生命週期**。給：兩者（模型 `handoff`；人 `aos-team task`）。

`handoff` 工具（領隊用）：`{"assignee": "worker-1", "workflow": "IMPORT.md", "goal": "…", "facts": "facts.json", "done_when": [{"kind": "file_exists", "path": …}, {"kind": "check", "name": "wf_residue"}, {"kind": "check", "name": "wf_lint_strict"}, {"kind": "judge", "text": "原意沒變"}], "max_attempts": 3, "deadline_minutes": 60}`。
它**只寫一封申請**進自己的 outbox；郵差建單並派送（一步完成，不需要另外 `team_say`）。

**任務狀態（只有郵差改）**（審查 M4）：

```text
queued → sent（投進 input）→ working（信被收走）→ verifying（收到 DONE）
   → reviewing（有 judge 條目：開審查子任務）→ done
任何時候：blocked（收到 BLOCKED，等領隊）／waiting_user（NEEDS-USER）／cancelled（人或領隊取消）
verifying 不過：attempt+1、rev 不變，投一封「REQUEST 修正（第 2/3 次）＋逐條結果」給工人
attempt 用完或超過 deadline：failed，投 FAILED 給領隊與人
```

- 單有 `rev`（交接內容改了就 +1）與 `attempt`。**只有目前 `assignee`、而且 `reply_to`＋`rev` 對得上的回報算數**；舊 rev 的回報記下來、不改狀態。
- `FAILED` 照 workflows 原意＝「終止、不再自己重試」，所以驗收不過**不用 FAILED**，用「REQUEST 修正」。
- `judge` 條目開一張審查子任務 `t-0007.r2`（對應 rev）給審查；審查用 `review_result {"task": "t-0007.r2", "items": [{"i": 0, "pass": true, "why": "…"}]}` 逐條回，**全部 PASS** 才 done，有 FAIL 就跟機械不過一樣走修正。
- 人：`aos-team task ls`、`show t-0007`（狀態、歷次驗收結果、相關信）、`cancel t-0007`、`reassign t-0007 worker-2`（rev+1）。
- 模型看任務表：`board {"op": "ls"|"show", …}`，唯讀（審查 S5）。

LLM：不叫。六軸：L5 S4 R5 F5 H5 B4。難度：中（狀態機＋測試）。波：一。

### T-verify

**驗收員**。給：兩者（郵差提交；人 `aos-team verify t-0007`；模型能叫來預先自查）。
只跑**固定的檢查器**（審查 M1）：`file_exists`（路徑在專案內）、`table_filled`（`wf-table/1` 資料檔或 md 表格某欄全非空）、`check`（名字對到檢查器包裡的一支，例 `wf_residue`、`wf_lint_strict`、`contains`）。
檢查器程式放在**工具包裡、工人寫不到的地方**，不執行專案裡的任何檔（不跑 `p/tools/wf-lint.sh`，跑工具包自帶的那份）；參數只收路徑與固定選項。**沒有「跑任意指令」這種條目**——要跑專案自己的測試，是二波進牢之後的 `cmd_ok`。
檢查器回「過／不過／檢查失敗（讀不到檔等）」三種，不用退出碼猜（審查 M7：`grep -c` 零命中退 1）。輸出每條一行，`--json` 給郵差。
進牢：一波在牢外跑、只跑自帶檢查器；二波開 `cmd_ok` 時那一條進牢。LLM：不叫（`judge` 交給審查 agent，那一段流程有模型）。
六軸：L5 S5 R4 F4 H5 B4。難度：小。波：一。

### T-ask

**`ask_human` 工具＋`aos-team answer`**。給：兩者。
模型：`{"question": "…", "options": ["A", "B"], "default": "A", "reply_to": "t-0007"}` → 寫進自己的 outbox，郵差建 `team/wait-user/q-0003.json`、書記加 `WAIT_USER.md` 一行。
人：`aos-team wait ls`（看有哪些在等）、`aos-team answer q-0003 "B"` → 郵差投回給發問者（信頭 `【人 → worker-1 · 回覆 q-0003】`）、刪待辦。talk 裡的 `/answer` 由 talk 那隊之後接（審查 S5）。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-beat

**心跳**（機械，kernel 反覆工作，例 60 秒）。給：系統；人 `aos-team routine ls/add/rm`。（審查 M8 重寫）

- **唯一資料來源**：`team/routines.json`（`wf-table/1`）。導入後的 `routines.md`／`schedule.md` 改成指向它（workflows 的資料檔規矩本來就允許），`aos-team routine import` 把 md 表抄過來一次。模型要改只能寄申請。
- **兩種時間**：`every`（間隔，例 `6h`）與 `daily`（每天幾點，例 `09:00`），另有一次性的 `at`（絕對時刻）。每列有 `tz`（沒寫＝團隊的時區）。
- **每一次到期有 id**：`<項目>@<該次應跑時刻>`。派出去就記「在途」；**在途時不再派**；回 DONE 才改「上次執行」／刪一次性列；FAILED 或超過 `timeout` 算這次失敗，照 `retries` 重派，用完就報領隊。
- **漏跑**：開機時發現錯過好幾次，**只補最近一次**，並寄一封 PROGRESS 告訴領隊漏了幾次（不自己判斷要不要全補）。
- **授權**：只有人用 `aos-team routine add` 加的列（`added_by: human`）會自動跑；模型提出的列要先過 T-ask，人答應才生效（workflows：使用者親自登記的才算授權）。

LLM：不叫。依賴：T-post、`aos-kernel add`。六軸：L5 S4 R4 F5 H5 B5。難度：中。波：一（可延後，第一個驗收例子用不到）。

### T-lock

**`lock` 工具**（workflows `resources.md` 的 mkdir 鎖）。給：兩者。
`{"op": "acquire"|"release"|"ls", "name": "…"}`；acquire 拿不到立即回 `Busy`＋持有者，**不等**。鎖在 `team/locks/<名>/owner`。
**只有持有者放**（審查 M5）；持有者被 stop 時不自動收：`aos-agent stop` 不會停掉已送出的工具。郵差確認那個成員已撤銷、`state.json` 的 `batch` 是 null（沒有在途工具）之後才收，否則寄給人。
LLM：不叫。六軸：L5 S4 R5 F5 H4 B5。難度：小。波：二（兩個工人才會搶）。

---

## B. 記憶與 prompt history（`/context`、`/compact`）

現況：`talk` 有 `/context`（人格＋記憶＋工具的字數表）、`/history`（規範見 [../../spec/aos-agent/cli-talk-repl.md](../../spec/aos-agent/cli-talk-repl.md)）。記憶是 `prompts/history.json` 整份讀寫、**沒有上限**（agent 規範自己寫「記憶太長怎麼辦之後再說」）。

### T-events

**事件紀錄**（審查 M9：量測要從地基記，不能最後才補）。給：系統；人 `aos-team score`、`aos-agent events`。
每個 agent 家 `log/events.jsonl` 追加一行一事件：`think_start／think_end`（批 id、成敗、原因）、`act_start／act_end`（每個 call 的工具名、成敗、kernel 回音的 `ms`）、`intake`（收了哪些檔）、`compact`。
`aos-llm call` 另外把 HTTP 回應的 `usage`（有的話）追加到 `log/usage.jsonl`，帶批 id——現在它只印 `choices[0].message`，usage 丟掉了（`lib/aos_llm_call.py`）。
**注意**：kernel 的 `ms` 是**經過時間，不是 cpu 秒**；cpu 秒與記憶體只在單元測試裡用 `/usr/bin/time` 另量，沒有就寫 null。團隊成員的紀錄連同 `team/post/sent/` 的時間，才拼得出「一件事的時間花在哪」。
LLM：不叫。六軸：L5 S5 R5 F5 H4 B5。難度：中（碰 tick 與 aos-llm）。波：一（隊 4，最早合）。

### T-context

**`aos-agent context`**（把 talk 的 `/context` 升成子命令）＋模型工具 `context`（唯讀）。給：兩者。
人：`aos-agent context --target 家 [--json] [--by-round]`：送給模型的東西多大（人格、記憶按 role、工具描述、合計；token 用字數估），`--by-round` 每輪一行（哪輪最胖、胖在哪個工具結果）。
模型：`context` 回「你的記憶 N 則、約 K token、最胖的三則是…」。要唯讀看自己家——二波關牢後家看不到，改成 tick 每格把這幾個數字寫進 `team/outbox` 旁的唯讀小檔給它看。
LLM：不叫。依賴：talk 的 `/context` 算法（同一個函式）。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一（人用）／二（模型用）。

### T-compact

**`aos-agent compact`**（機械壓縮記憶）。給：人；模型只能寄 `compact` 申請。（審查 M10 補恢復）

**什麼時候做**：持 `.tick.lock`、`state` 是 idle、`batch`／`intake` 都是 null。人跑指令時鎖被佔＝退 101、不動檔。**自動**的（記憶超過 X token、或收到模型的申請）由 tick 在 idle 那一步**在同一把鎖裡直接叫同一個函式**，不另外拿鎖。

**怎麼做（每步可重跑）**：
1. 讀記憶，算 sha。組新記憶：最後 N 輪原樣；更早的每輪只留「user 原話＋那輪最後一則回話」，中間的工具呼叫與結果換成一行 `[已壓縮：叫了 read×3、bash×1；原文 archive/<sha>.json 第 i～j 則]`。`tool_calls` 與它的 `tool` 結果**成對**處理（拆開會被模型端退 400）。
2. **還有上限**：縮完還超過 X token，就把最舊的幾輪整輪換成一行 `[第 1～5 輪已封存]`，直到低於 X。
3. **沒做完的任務不縮**：信頭寫著某個 `t-xxxx` 還不是 done 的那幾輪原樣保留。
4. 寫 `prompts/archive/<舊 sha>.json`（暫存檔＋rename，已在就略過）→ 再用暫存檔＋rename **替換** `history.json`。永遠不是「先搬走舊的」，所以崩在哪一步，`history.json` 都是完整的新版或舊版；重跑時舊版的 sha 對得上 archive 就接著做。
5. 記一行事件（T-events）。

選項：`--keep-rounds N`、`--max-tokens X`、`--dry-run`（印會變成怎樣、不寫）、`--summarize`（**三波**：交給一個摘要 agent 寫摘要；有模型，結果要過「比原文短、原文關鍵詞還在」等機械檢查）。
取回原文：第一波人用 `aos-agent history --archive [--grep 字]`；模型用 T-recall（二波）。archive 預設全留，`compact --prune-archive 天數` 清。
LLM：預設不叫。依賴：tick 鎖、state 規則、T-events。規範要改 agent 記憶一節（§3.2「記憶太長之後再說」）與 aos-agent idle 一節。
六軸：L5 S4 R5 F5 H4 B4。難度：中。波：一。

### T-notes

**`note` 工具**（長期筆記，跟對話記憶分開）。給：兩者（人 `aos-agent notes ls/show`）。
`{"op": "add"|"find"|"get"|"rm", "key": "…", "text": "…", "tags": […]}`；存成一個 `notes.json`（`wf-table/1`，人和 `tabledb.py` 都讀得懂），**只有這個 agent 寫**（共同規則 5）。`find` 是關鍵字＋tag 比對，不做向量搜尋。
不自動塞進每輪（省 token）；模型要用就 `find`。proto2 的 `self_note` 只能追加、不能改人格——照採。
進牢：一波放 `team/notes/<名>/`；二波映射成 rw（[agent-access](../2026-09-24-agent-access/README.md) 第 2 題的預設是「自己的家唯讀，要寫另映射」）。LLM：不叫。
六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-recall

**`recall` 工具**：在 `prompts/archive/` 與封存的輸入（`done/`）裡找原文。給：模型。
`{"query": "…", "limit": 5}` → 命中的幾段（哪一輪、前後幾行）。純 grep。
進牢：要唯讀看家裡的 archive（二波映射）。LLM：不叫。六軸：L5 S5 R5 F4 H4 B4。難度：小。波：二。

---

## C. 特定檔案修改

### T-json

**`json_edit` 工具＋`aos-json` 指令**。給：兩者。
`{"path": "…", "op": "get"|"set"|"del"|"append"|"merge", "pointer": "/a/b/0", "value": …, "expect_sha": "…"}`；用 JSON Pointer 定位，**不用字串取代**（模型改 JSON 最常壞在逗號、括號）。`get` 回內容＋sha；寫的時候給 `expect_sha`，檔被別人改過就 `Conflict`。改完重新解析一次，是合法 JSON 才寫；保留原縮排風格。
`--check-directives`：改的是 aos 設定檔時用 `lib/aos_directives.py` 解一次，解不過就不寫。
**信任資料不准改**（審查 M1）：不是看檔名，而是看**實際設定**——讀 agent 的 `info.json`，把它、它的 `system`、`history`、`tools` 列到的檔與資料夾、`access.json` 與它 `$ref` 到的檔全部解開成真路徑，目標落在裡面就拒絕。模型版一律關在工作根目錄（跟 base 一樣）。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-md

**`md_section` 工具**：按標題改 Markdown 一節。給：兩者。
`{"path": "…", "heading": "## 3. …", "op": "get"|"replace"|"delete"|"append_item"|"remove_item", "text": "…", "expect_sha": "…"}`。標題要剛好一個（`NotUnique` 列出行號）。`append_item`／`remove_item` 給「一行一項」的清單，照 `- [工作流] 狀態 → 下一步` 格式驗。
（`SESSION-LOG.md`、`WAIT_USER.md` 是書記在寫，工人**不**用這支改它們。）
LLM：不叫。六軸：L5 S5 R5 F5 H5 B4。難度：小。波：一。

### T-wf

**workflows 工具包 `wf`**。給：模型（人本來就能直接跑原腳本）。（審查 M6 重寫）

- **整棵快照**：`wf-init.sh` 靠自己的位置找 `template/`、`flavors/`，還 source 別的 shell 檔，只抄 `tools/` 跑不起來。工具包帶一份**固定版本**的 workflows 必要資料樹（`tools/`、`template/`、`flavors/`、`IMPORT.md`、`README.md`，記 commit 與 kernel 版本戳），放在工具包裡、唯讀。
- `wf_doc {"path": "IMPORT.md", "offset": …}`：唯讀讀快照裡的手冊（工人的 base `read` 只能讀專案，讀不到專案外的 `IMPORT.md`）。
- `wf_init {"flavor": ["heartbeat"], "non_invasive": "wf"}`：**先在 staging 做**：把專案複製到 `<專案>.wf-staging-<id>/`、在那裡跑 `wf-init.sh`；成功才整個換過去（舊的留成 `.wf-backup-<id>/`），失敗就丟掉 staging、專案不動。所以半路失敗重跑不會撞到「AGENTS.md 已存在就拒絕」。回殘留清單。
- `wf_lint {"strict": true}`：跑快照裡的 `wf-lint.sh`，回 `TOTAL …` 那行＋前 50 條問題（全文存檔）。
- `wf_residue {}`：數 `{{`、〔導入判斷〕、〔模板說明〕在哪、各幾處；範圍＝專案裡所有 `.md`（照 `IMPORT.md` 的 grep）；讀不到的檔另列、不當成 0。
- `wf_table {"op": …}`：`tabledb.py`，原樣回 JSON。
以上同時是 T-verify 的檢查器（`wf_residue`、`wf_lint_strict`）。
進牢：一波在工作根目錄跑（信任環境，見 plan）；二波進牢。LLM：不叫。
六軸：L5 S4 R4 F4 H5 B3。難度：中（staging 與快照）。波：一。

### T-directive

**`aos-directives` 指令**：把一個 aos JSON 檔的指示詞（`$env`／`$ref`／`$fmt`／`$opt`）解開印出來、或只驗。給：人（除錯用）。
`aos-directives resolve FILE [--center DIR] [--pointer /x]`、`check FILE`。直接用 `lib/aos_directives.py`。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：一（順手）。

### T-access-req

**`access_request` 工具**：模型**申請**碰某個資料夾，不能自己改 `access.json`。給：模型；人批。
`{"name": "notes", "path_hint": "…", "mode": "ro"|"rw", "why": "…"}` → 走 T-ask 的待辦；人答應後由**人的指令**（牆那隊的 `aos-agent access set`）寫表。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：二（要牆存在才有意義）。

---

## D. agent 創造與修改

### T-template

**`aos-agent init --template NAME`**＋模板資料夾 `proto5/templates/<名>/`（人格、工具包清單、`info.json` 片段、`input` 固定為資料夾）。給：人。
內建：`coder`（base）、`lead`／`worker`／`reviewer`（workflows 團隊用）。`aos-team init` 對名冊每一列叫它。
LLM：不叫。依賴：`init`（規範寫「`init --template` 這輪不做」，要改一節）、`tools add`。
六軸：L5 S5 R5 F5 H5 B5。難度：小～中。波：一。

### T-persona

**改人格**：人格是信任資料，模型不能直接改。給：人（`aos-agent persona show/set/append`）；模型只能 `persona_propose`（申請，人批）。
proto2 的 `improve_prompt` 只能改 `prompt-overrides/`、模型曾拒絕寫使用者要的教訓——照採「提案、人批」。
**其他 agent 設定**（模型代號、排程間隔、工具清單）這一輪只給人改：`info.json` 用 T-json 的人用版、工具用 `tools add/rm`（審查 S5）。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：二。

### T-spawn

**模型生新成員**。給：模型（領隊）。
`{"template": "worker", "name": "worker-3", "reason": "…"}` → 申請；郵差照名冊檢查：只能用允許的模板、人數不超過 `max_members`、新成員的 `mail_to` 與權限不超過申請者。
proto2 `kids` 的教訓：深度、兩種鐘、自動轉寄都搞混過——**一律平的**（沒有父子樹，全是團隊成員）、一律經郵差交流。
LLM：不叫。六軸：L5 S3 R2（每個多一份反覆工作）F4 H4 B3。難度：中。波：三。

---

## E. 造工具的工具

（牆那隊在做的 `aos-agent tools ls/add/rm/alias`，這裡不重複。）

### T-toolnew

**`aos-agent tools new NAME [--lang py|sh]`**：生工具包骨架。給：人。
生 `NAME/NAME.json`（一個工具的範例描述）、`NAME/run`（讀 stdin JSON、照 base 的錯誤格式）、`NAME/_common.py`（base 那份的最小版）、`NAME/test_NAME.py`、`NAME/README.md`（一頁）。
LLM：不叫。六軸：L5 S5 R5 F5 H5 B5。難度：小。波：二（跟 T-tooltest、T-wrap-py 同一隊）。

### T-tooltest

**`aos-agent tools test NAME|DIR [--args JSON] [--case FILE]`**：用跟 aos-agent 一模一樣的方式（cwd＝agent 家、stdin、`_meta` 解指示詞、逾時）跑一次工具，並驗工具檔格式、描述長度（token 估算，對應資源軸）。給：兩者（模型版 `tool_try` 給 T-toolsmith）。
`--case` 吃「輸入→期待輸出片段」清單，跑完印 PASS/FAIL＝穩定軸能自動量。
進牢：跑的是任意程式，牆存在時進牢。LLM：不叫。六軸：L5 S5 R5 F5 H5 B5（進牢後）。難度：小～中。波：二。

### T-wrap-py

**`aos-agent tools wrap-py FILE.py [--only f,g] [--name PACK]`**：讀一個 Python 檔，把裡面的函式變成工具包。給：人（模型版在三波）。（審查 M13 補支援範圍）

- **靜態讀**：用 `ast`，**不 import、不執行**。挑頂層、非底線開頭、**每個參數都有型別註解**的函式。
- **支援的參數**：`str`、`int`、`float`、`bool`、`list[X]`、`dict[str, X]`、`Literal[...]`、`X | None`／`Optional[X]`（X 也要在這張表裡）；一般參數與 keyword-only 都行；有預設值＝非必填。
- **不支援就拒收、說原因**，不猜：沒註解、`*args`／`**kwargs`、自訂類別、`async def`、decorator 改過簽名的。印一張表：每個函式收了／拒收（為什麼）。
- **回傳**：`str` 原樣印；其他要能 `json.dumps`，不能就回 `ResultNotJSON`。例外 → base 的錯誤 JSON（代號 `PythonError`＋例外類別與訊息，不噴 Traceback）。
- **描述**：docstring 第一段 → `description`；參數說明取 Google／NumPy 風格的 `Args:` 段。沒 docstring＝警告，描述用函式名。`--describe-with-llm`（三波）請模型補、人看過才寫入。
- **產出**：`PACK.json`＋`run`（`run <函式名>`：stdin 讀 arguments、import 原檔副本、叫函式）＋原檔副本（記 sha256；原檔的 import 依賴要在跑工具的那個 Python 裡找得到，`tools test` 會先試 import 一次）。
- **沒辦法靜態讀的檔**：人自己寫一份薄 adapter（有註解的包裝函式）再 wrap。
驗收用固定的 fixture（有註解、各型別各一個、該拒收的各一個），**不用** workflows 的 `find_big_lists.py`（它沒註解，會全被拒收）。
進牢：產生時不執行；**跑的時候是任意 Python**，一定要牆。LLM：預設不叫。依賴：T-toolnew、T-tooltest。
六軸：L5 S4 R4（每次呼叫起一個 Python）F4 H5 B5（進牢後）。難度：中。波：二。

### T-wrap-cli

**`tools wrap-cli CMD`**：從一支指令的 `--help` 或 argparse 定義生工具。有 argparse 的 Python 腳本可靜態讀；其他要解析 help 文字——不穩，可能要模型。給：人。
LLM：可能要（解析 help）。六軸：L3 S3 R4 F4 H4 B4（進牢）。難度：大。波：三。

### T-toolsmith

**模型造工具**：`tool_draft {"name", "description", "parameters", "code": "…", "lang": "py"}` 寫進 `team/outbox/<名>/tools-staging/<名>/`，自動在牢裡跑 T-tooltest；**安裝要人**（`aos-agent tools add`）。給：模型。
proto2 toolsmith 自評 9/10、但沒沙箱沒逾時——這裡補：牢裡測、有逾時、裝不裝人決定。
LLM：工具本身不叫（模型是使用者）。六軸：L4 S3 R4 F4 H4 B4。難度：中。波：三。

---

## F. 量測與系統

### T-score

**`aos-team score [--task t-0007]`**：把六軸表能量的部分自動填好。給：人。
**只做彙整**，資料來源都在第一波先記好（審查 M9）：T-events（每批起訖、成敗、工具 `ms`）、`usage.jsonl`（token）、`team/post/sent/`（每封信的時間、誰寄誰）、任務表（attempt、狀態變化）。
印 L（問模型次數、含失敗的）、S（這次成敗；**跑不到 10 次不給 S 分**，只寫「x/y 次過」）、R（token 總量；cpu 秒與記憶體寫 null，另量）、F（牆上時間，拆成：等收件、等模型、跑工具、等驗收、等人）；H、B 留空給人。`--json` 給比較。
LLM：不叫。六軸：L5 S4 R5 F5 H5 B5。難度：小（資料先記好的話）。波：一（收尾隊）。

### T-pool

**工具檔 `_pool` 欄**（[priority-and-shared-cpu 提案](../2026-09-24-priority-and-shared-cpu/README.md)）：某支工具走指定的池（例：GPU 工具一顆 cpu 排隊）。給：人（寫工具檔）。
規範改 agent info §3.3、aos-agent send §5.2；程式十幾行。LLM：不叫。六軸：L5 S5 R4 F4 H5 B5。難度：小。波：二。

### T-crystal

**固化建議**（ai_core §3.6 的「固化引擎」最小版）：讀 `team/route.log` 與領隊開的單，找「門房沒中、領隊每次都開同一種單」的句型，列成 `routes.json` 的**候選**規則給人批。給：人。
第一版純統計，**只提候選、不自動生效**（審查 S3）：候選要附命中例句與至少一句負例，人批之前跑 `aos-team route test`，還要拿沒參與提案的舊句子回測。
LLM：第一版不叫。六軸：L5 S4 R5 F5 H4 B5。難度：中。波：三。

---

## 總表

| 名 | 一句 | 給誰 | 工具本身叫模型 | 牢 | 難度 | 波 | 人用的 CLI |
|---|---|---|---|---|---|---|---|
| T-team | 名冊＋`aos-team` | 人 | 否 | — | 中 | 一 | 本身就是 |
| T-say | 寄信 | 模型 | 否 | 二波寫 outbox 映射 | 小 | 一 | 人用 `say` |
| T-post | 郵差＋書記 | 系統 | 否 | 牢外 | 中 | 一 | `aos-team mail` |
| T-route | 門房 | 人（間接） | 否 | — | 小～中 | 一 | `aos-team ask`、`route test` |
| T-handoff | 交接書＋任務狀態 | 兩者 | 否 | 同 T-say | 中 | 一 | `aos-team task` |
| T-verify | 驗收員（固定檢查器） | 兩者 | 否 | 一波牢外／`cmd_ok` 二波進牢 | 小 | 一 | `aos-team verify` |
| T-ask | 問人／人回 | 兩者 | 否 | 同 T-say | 小 | 一 | `aos-team wait`、`answer` |
| T-beat | 心跳 | 系統 | 否 | 牢外 | 中 | 一（可延） | `aos-team routine` |
| T-lock | 資源鎖 | 兩者 | 否 | 二波映射 | 小 | 二 | 是 |
| T-events | 事件紀錄 | 系統 | 否 | aos-agent 內 | 中 | 一 | `aos-agent events` |
| T-context | 送模型的東西多大 | 兩者 | 否 | 二波給小檔 | 小 | 一／二 | `aos-agent context` |
| T-compact | 機械壓縮記憶 | 人（模型申請） | 預設否 | aos-agent 內 | 中 | 一 | `aos-agent compact` |
| T-notes | 長期筆記 | 兩者 | 否 | 二波映射 | 小 | 一 | `aos-agent notes` |
| T-recall | 找壓縮掉的原文 | 模型 | 否 | 二波唯讀 | 小 | 二 | `aos-agent history --archive` |
| T-json | JSON Pointer 改檔 | 兩者 | 否 | 同 base | 小 | 一 | `aos-json` |
| T-md | 按標題改 md | 兩者 | 否 | 同 base | 小 | 一 | 是 |
| T-wf | workflows 工具包 | 模型 | 否 | 二波 | 中 | 一 | 人跑原腳本 |
| T-directive | 解／驗指示詞 | 人 | 否 | — | 小 | 一 | `aos-directives` |
| T-access-req | 申請碰資料夾 | 模型 | 否 | 同 T-say | 小 | 二 | 牆那隊的 `access set` |
| T-template | 模板生家 | 人 | 否 | — | 小～中 | 一 | `init --template` |
| T-persona | 人格提案／人改 | 兩者 | 否 | 同 T-say | 小 | 二 | `aos-agent persona` |
| T-spawn | 模型生成員 | 模型 | 否 | 同 T-say | 中 | 三 | — |
| T-toolnew | 工具骨架 | 人 | 否 | — | 小 | 二 | `tools new` |
| T-tooltest | 照 aos 的方式試跑工具 | 兩者 | 否 | 進牢 | 小～中 | 二 | `tools test` |
| T-wrap-py | Python 檔 → 工具包 | 人 | 預設否 | 跑時進牢 | 中 | 二 | `tools wrap-py` |
| T-wrap-cli | 指令 → 工具包 | 人 | 可能 | 跑時進牢 | 大 | 三 | `tools wrap-cli` |
| T-toolsmith | 模型寫工具、人裝 | 模型 | 否 | 進牢 | 中 | 三 | — |
| T-score | 六軸自動彙整 | 人 | 否 | — | 小 | 一 | `aos-team score` |
| T-pool | 工具指定池 | 人 | 否 | — | 小 | 二 | 寫工具檔 |
| T-crystal | 固化建議 | 人 | 第一版否 | — | 中 | 三 | `aos-team crystal` |

30 個工具，**工具本身**會叫模型的只有 T-wrap-cli（第三波）；T-compact、T-wrap-py 的模型選項都在第三波、預設關。整條流程裡模型只出現在三個 agent 的「想」那一步（領隊拆派、工人填事實與改檔、審查判 `judge` 條目）。
