← [工具大開發時代](README.md)｜[notes 索引](../README.md)

# 目標：把 `~/repo/workflows` 變成一支 aos agent 團隊

## 1. workflows 是什麼（白話一頁）

**一套以 Markdown 為主的「給 AI agent 照著做的工作手冊」**（另有 JSON／CSV 資料檔、幾支腳本、可選的 skills），複製進任何專案（不限程式）就能用。aos 自己的 `AGENTS.md`＋`wf/` 就是從它導進來的。

- **怎麼用**：agent 從很薄的 `AGENTS.md` 進來 → `WORKFLOWS.md` 照使用者的話挑一條工作流（派發表）→ 讀那條工作流的入口檔照做。每次只讀需要的那一層，context 不會被塞爆。
- **組成**：`template/`＝共用骨架（kernel，現在 v0.6）；`flavors/`＝七個領域包：dev（開發、測試、重構…）、knowledge（寫作、摘要、決策…）、teaching、research、ops、**heartbeat**（定期喚醒：tick、routines、schedule）、**multi-agent**（信箱、團隊分層、資源鎖、派工）；`tools/`＝腳本；`examples/`＝兩個填好的成品。
- **導入**：`bash tools/wf-init.sh --target <專案> --flavor dev,heartbeat [--non-invasive wf]`，然後照 `IMPORT.md` 填掉 `{{…}}` 佔位、處理〔導入判斷〕、刪〔模板說明〕，最後 `tools/wf-lint.sh --strict <專案>` 退 0 才算完成。
- **四種「還沒完的事」**：`SESSION-LOG.md`（我手上的）、`WAIT_USER.md`（等使用者）、`inbox/`（agent 之間的信）、routines／schedule（定期、定時要做的）。SESSION-LOG、WAIT_USER、一次性的 schedule 都**只列還沒完成的**，做完就刪；routines 是例行的，做完改「上次執行」、不刪。
- **信**：地址是對方資料夾的 `inbox/`，檔名 `<時間>-<寄件者>-<STATUS>.md`；STATUS 只准六個：REQUEST、DONE、BLOCKED、NEEDS-USER、FAILED、PROGRESS；**接了事一定要回終局狀態**，卡超過 10 分鐘要回 BLOCKED；處理完把信搬進 `done/`。
- **團隊**：三層——頂層（使用者／調度者）、領導（拆工作、寫交接書）、工人（做事）。（下面的「領隊／工人／審查」是**這次的改編**，不是模板原樣。）交接書的驗收只准三種：**檔案存在、指令回傳、表格填滿**——所以驗收本來就能機械檢查。
- **機械兜底**：`wf-lint` 抓壞連結、壞錨點、超過 8 KB 的檔、超過 1 KB 的條列、沒填的佔位；`tabledb.py` 讀寫 `wf-table/1` 資料檔；`fix_moved_links.py` 搬檔後修連結。
- **本身沒有執行引擎**：heartbeat 要借 `/loop`、cron；multi-agent 要人開好幾個 Claude Code 視窗。**這正是 aos 補得上的洞**：aos 有 kernel（排程）、有 agent（會做事的資料夾）、有工具，缺的只是把這套手冊接上去。

**哪些是純機械**（照 workflows 自己的內容分，詳細清單見調查）：導入腳本、lint、開場的 `grep -c`、投信／讀信／搬信、鎖、「到期了沒」的計算、改「上次執行」、刪已完成的列、`tabledb` 增刪查、Done when 的驗證。
**哪些真的要判斷**：填佔位時查不到的專案事實（事實已經給了的話，照表填是機械的）、〔導入判斷〕、把一句話對到哪條工作流（**但大多數能靠關鍵字先濾**）、寫信的內容、交接書怎麼切、寫作與摘要、錯過很久的行程要不要補做。

## 2. 團隊長怎樣

**三種會想的 agent（角色）＋ 四個不會想的機械員。**不是每件事都要三種都上：門房能處理的不叫領隊，全機械驗收的不叫審查。 機械員**不是 agent**，是 kernel 的反覆工作或一次性工作（[教程 02](../../tutorials/02-kernel-jobs.md) 那種），不問模型。

```text
人 ──aos-team ask "…"──▶ 門房（機械，一次性）
                          ├─ 命中「機械指令」（lint、看信箱、列待辦…）→ 直接跑工具，回話給人，不叫模型
                          ├─ 命中某條工作流句型 → 開單 → 投給 工人
                          └─ 沒命中／命中兩條以上／有否定詞 → 投給 領隊
領隊（agent）──handoff 申請──▶ 郵差開單、派給 工人（agent，可多個）
工人 ──DONE 信──▶ 郵差（機械，反覆）
                   ├─ 提交一次性驗收工作 → 驗收員（機械）跑單上的固定檢查器
                   │    不過 → 郵差寄「REQUEST 修正（第 n 次）＋逐條結果」給工人（不叫模型）；次數用完才 FAILED
                   │    過了、有 judge 條目 → 開審查子任務給 審查（agent）
                   │    過了、沒有 → 單子 done、回報人
                   └─ 書記（機械，同一支）同步 SESSION-LOG／WAIT_USER、看停滯
心跳（機械，反覆，例 60 秒）：看 routines／schedule 到期 → 以開單的方式派給執行者
```

### 2.1 三個 agent

| agent | 做什麼 | 人格（重點；規則儘量放工具不放人格） | 工具 | 記憶 | 模型 |
|---|---|---|---|---|---|
| **領隊** lead | 門房濾不掉的話：判斷要走哪條工作流、切成幾件、開單派給工人；收 BLOCKED、NEEDS-USER、停滯通知決定怎麼辦 | 「你不動手做事，只拆、派、收。派工只用 `handoff`（它會自己寄出去）。」 | `handoff`、`team_say`（回覆、不派工）、`ask_human`、`board`（唯讀看任務表）、唯讀 `read`／`grep`／`ls`（專案）、`wf_doc` | 記憶檔＋`compact`（機械版）；長期的決定經 `md_section` 寫進專案的 `decisions.md` | 聰明的 |
| **工人** worker | 照交接書做一件事：照工作流入口檔做、改檔、跑工具；做完回 DONE，卡住回 BLOCKED | 「照交接書的入口檔做。做完一定 `team_say` 回 DONE；卡住回 BLOCKED 說原因。」 | base（工作根目錄＝專案；bash 第一波關不住）、`wf_doc`、`wf_init`、`wf_lint`、`wf_residue`、`wf_table`、`md_section`、`json_edit`、`verify`（自查）、`team_say`、`ask_human` | 一件事一段；交件後 `compact` 清掉這件的工具輸出 | 便宜的就行 |
| **審查** reviewer | 只判 `judge` 驗收條目（例如「原意沒變」「摘要對不對」）；機械能驗的不歸它 | 「只看審查單列給你的條目，用 `review_result` 逐條回 PASS／FAIL＋一句理由。」 | 唯讀 `read`／`grep`、`board`、`review_result` | 每件清空 | 中等 |

人數：工人可開多個（`worker-1`、`worker-2`…）。**領隊、審查都可省**：門房命中率高到幾乎不落穿就不用領隊；單子全是機械條目就不用審查。

### 2.2 四個機械員（不問模型）

| 機械員 | 跑法 | 做什麼 | 對應 workflows 的哪裡 |
|---|---|---|---|
| **門房** route | `aos-team ask` 時一次性跑 | 用 `WORKFLOWS.md` 的派發表關鍵字＋固定句型（「lint」「看看信箱」「列待辦」「導入 X flavor」）比對。命中機械指令就直接跑、回話；命中工作流就生交接書投給工人；沒命中才給領隊。**這就是 ai_core「LLM 是 switch 的 default」** | AGENTS.md → WORKFLOWS.md 派發 |
| **郵差** postman | kernel 反覆工作，例 1 秒一次 | 把各成員 `team/outbox/<名>/` 的信與申請搬進收件人的 `input/`（跟 `say` 同一個投檔函式）；身分看信在誰的 outbox；格式不合退信；每封留一份投遞紀錄（兼去重憑據）；開單、改任務狀態（**任務表只有它寫**）；NEEDS-USER 轉進人的待辦 | inbox 投遞、PROTOCOL、ROSTER |
| **驗收員** verify | 郵差收到 DONE 時提交成 kernel 一次性工作 | 照單上的條目逐條跑**工具包自帶的固定檢查器**（檔在／表格填滿／殘留為零／lint 過…），不執行專案裡的檔；結果回郵差，由郵差決定寄修正還是結單 | dispatch 收線 checklist、Done when 只准三類 |
| **書記** clerk | 跟郵差同一支 | 開單＝`SESSION-LOG.md` 加一行；結單＝刪那行；NEEDS-USER＝加進 `WAIT_USER.md`（這兩個檔只有它寫）；**看停滯**：收了單、超過 N 分鐘沒進展又不是在等別人，或健康不是 ok（卡在想／跑工具、kernel 壞），就寄一封「觀察到停滯」給領隊與人，同一次只報一次——它只報看到的事，不替工人說 BLOCKED | SESSION-LOG、WAIT_USER、終局狀態規則 |
| **心跳** heartbeat | kernel 反覆工作，例 60 秒 | 讀 `team/routines.json`（唯一來源；間隔、每天幾點、一次性三種），算誰到期；每次到期有自己的 id，派出去就記「在途」、在途不重派；回 DONE 才改「上次執行」／刪一次性列；只有人登記的列會自動跑 | heartbeat 的 tick／routines／schedule |

（書記和郵差合成一支程式、心跳另一支；門房和驗收員是一次性小程式。實際是**四支程式**。）

### 2.3 彼此怎麼交流（用現有的 `say`／`listen`／檔案）

- **投信就是 `say`**：`team_say` 工具把 `{to, status, reply_to, rev, text}` 寫成 `team/outbox/<自己>/` 下的一個 JSON 檔（outbox 放在團隊資料夾、不在成員家裡，第二波關牢時才不會碰到「家是信任資料」）；郵差把它變成收件人 `input/mail-<信 id>.json`——一則 user 訊息，用 `aos-agent say` 的同一個投檔函式（不覆蓋、原子）。收件人看到的開頭固定一行：`【來信 lead → worker-1 · REQUEST · t-0007 rev1 · 09-25 10:03】`。
- **什麼時候看得到**：agent **只在閒著（idle）時收輸入**。它正在想或跑工具時到的信，要等這一輪做完才看到；一次可能收到好幾封，同一次裡照檔名排、不照時間（所以信頭帶時間）。第一版**沒有插話取消**：要喊停用 `aos-team task cancel` 或 `aos-agent pause`。保證只有：不丟、不重複。
- **不自動轉寄回話**：agent 的最後一句話**不會**自動寄出，一定要叫 `team_say`。proto2 的教訓：小孩不知道回話會自動轉寄，自己去找父的路徑，一題乘法繞了 84 格。明確寄信＋書記兜底（沒回終局狀態就替他報 BLOCKED）比較穩。
- **不給「等回信」工具**：proto2 的另一個教訓是模型會原地輪詢、「自己等自己」。這裡 agent 寄完信這一輪就結束，回信到了是一則新輸入、下一輪自然醒來；閒著的 agent 不問模型。
- **人看**：`aos-agent listen --target <某成員> --last` 看單一成員；`aos-team ls` 一行一個成員（health、手上的單號）；`aos-team mail` 一封信一行，**整支團隊做了什麼一眼看完**（人易懂軸）；`aos-team task show t-0007` 看一張單的每一步。
- **交接書是檔案**：`team/tasks/t-0007.json`：`{"id", "rev", "attempt", "workflow": "入口檔", "goal", "facts", "done_when": [{"kind": "file_exists"|"table_filled"|"check"|"judge", …}], "assignee", "status"}`。只有郵差改它；狀態怎麼走見 [catalog T-handoff](catalog.md#t-handoff)。`judge` 那種才給審查，其他驗收員跑。

### 2.4 走一遍驗收例子：「把 workflows 的 heartbeat 包導入一個空專案」

選它的理由：workflows 自己的 `IMPORT.md` 就有機械的 Done when（`{{` 為 0、〔模板說明〕為 0、〔導入判斷〕為 0、`wf-lint.sh --strict` 退 0），又有一點要判斷（處理〔導入判斷〕），小（heartbeat 包約十幾個檔）。
**它只驗「導入文件」這條路**（門房→工人→驗收），不驗心跳引擎、也不驗審查；那兩條另有例子（[plan.md](plan.md#第一波的整體驗收真跑-workflows-小例子功能試跑)）。

1. 人先寫好 `facts.json`（專案一句話、驗證指令、時區、分支慣例、使用者偏好、佈局、flavor；範例區塊一律刪、不自己編）。空專案查不到這些事實，`IMPORT.md` 又禁止瞎填，所以事實要人給；表裡沒有的，工人回 NEEDS-USER。
2. 人：`aos-team ask "把 workflows 導入 ~/tmp/wf-try/p，照 facts.json"`。
3. 門房（機械）：句型「導入 … 照 …」命中 → 開單 `t-0001`（workflow＝快照裡的 `IMPORT.md`；done_when＝`wf_residue`、`wf_lint_strict` 兩個檢查器＋必要檔案都在＋派發表有三列＋事實有寫進去）→ 派給工人。**領隊沒被叫。**
4. 工人（模型）：`wf_doc` 讀 `IMPORT.md` → `wf_init`（機械，先在 staging 跑）→ `wf_residue` 找殘留 → 照 `facts.json` 用 `edit` 填、處理〔導入判斷〕、刪〔模板說明〕→ `wf_lint` → `team_say` DONE。
5. 郵差＋驗收員（機械）：提交驗收 → 都過 → 單子 done、書記刪 SESSION-LOG 那行 → 投一則「t-0001 完成」給人。沒過就寄「REQUEST 修正＋逐條結果」回工人，回到 4；三次都沒過才 FAILED。
6. 六軸打分（[axes.md](axes.md)）：模型只出現在第 4 步的「讀手冊、照表填字、處理判斷段」；派工、驗收、記帳都是機械。
   （更進一步：「照表填已知事實」本身也能寫成機械工具——那是第三波 T-crystal 會提的那種候選。）

## 3. 缺什麼工具才做得到（＝這一波的目標）

現在 aos 有：agent 家、`say`／`listen`／`talk`、base 七支工具、kernel 反覆／一次性工作。**缺的**（細節在 [catalog.md](catalog.md)，順序在 [plan.md](plan.md)）：

| 缺的 | 為什麼 | catalog |
|---|---|---|
| `team.json` 名冊＋`aos-team init/start/stop/ls/ask` | 現在開團隊要 shell `for` 迴圈（教程 05），名冊、誰是誰沒地方寫 | T-team |
| `team_say`＋郵差＋書記 | agent 之間沒有「寄信」這件事，只有人 `say` | T-say、T-post |
| 事件紀錄 | 量六軸要的資料（每批起訖、token）現在沒留 | T-events |
| 門房（派發表前濾網） | 讓大部分的話不經過模型 | T-route |
| 交接書（任務狀態）＋驗收員 | 把「做完了沒」從模型手上拿走 | T-handoff、T-verify |
| workflows 工具包：`wf_doc`、`wf_init`、`wf_lint`、`wf_residue`、`wf_table`＋`md_section`、`json_edit` | 工人要讀手冊、動 workflows 的檔，現在只能用 bash 硬打，而且讀不到專案外的手冊 | T-wf、T-md、T-json |
| `ask_human`＋`aos-team answer` | NEEDS-USER 要有地方放、人要有地方回 | T-ask |
| 心跳 | heartbeat 包要有真的引擎 | T-beat |
| `compact`、`context` | 工人一件接一件，記憶會一直長 | T-compact、T-context |
| `aos-team score` | 六軸要量得出來 | T-score |
