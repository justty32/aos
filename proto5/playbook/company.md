# 當作開公司：組織圖

← [playbook README](README.md)

使用者的說法：整件事就當做是開公司，業務是產出 narratives（劇透設定集這類東西）。組織設計由總裁（使用者）拍板，這份是**定稿骨架**。現在是「施工期」——公司還在蓋，蓋公司的是 Fable 派的 Claude 隊；蓋好以後是「運轉期」——公司自己開工，開工的是 aos 裡的 agent 團隊、笨模型、確定性程式。**這是打比方幫忙理解分工，不是要另外造一套公司管理程式。**

## 總表

| 單位 | 做什麼 | 現在誰在做（施工期） | 目標誰在做（運轉期） | 對應的現有東西 |
|---|---|---|---|---|
| 董事會 | 出資、給方向、拍板、抽查 | 使用者本人 | 使用者本人（永遠是人，不會被自動化掉） | `proto5/advice.md`（使用者的方向日記，不在此次改動範圍）、[wf/WAIT_USER.md](../../wf/WAIT_USER.md) |
| 總裁 | 把董事的話翻成任務書、派隊、合併、匯報 | Fable（調度者）親自做 | aos 裡的團隊自己讀 advice.md 派工，Fable 只監督 | — |
| 總裁辦公室 | 交接、進度追蹤、雜務清理 | Fable 派的 Sonnet 文件隊 | aos 團隊裡類似郵差兼書記的角色 | [wf/SESSION-LOG.md](../../wf/SESSION-LOG.md)、[wf/WAIT_USER.md](../../wf/WAIT_USER.md)、`brief/` |
| 業務部 | 接單、交貨、彙整客戶問題 | Fable 派的 Claude 隊依單分派 | `aos-team` 的門房＋領隊 | [spec/team/route.md](../spec/team/route.md)、[spec/team/verify.md](../spec/team/verify.md) |
| 製造部 | 真正把貨做出來 | Fable 派的強模型 Claude 隊（手工線） | aos 團隊裡笨模型／程式接手（半自動→自動） | [proto5/examples/arknights/](../examples/arknights/) |
| 品管部 | 檢查貨做得好不好 | Fable 派的 Claude 隊寫評分器、做審查 | `aos-team verify` 驗收員＋評分器自動跑，人只抽查 | 評分器程式 `proto5/examples/arknights/eval/`（[說明](../notes/2026-09-25-arknights/eval/README.md)）、[spec/team/verify.md](../spec/team/verify.md) |
| 研發部 | 造工具、改流程、改內核 | Fable 派的 Claude 隊 | aos 團隊裡的工人角色（toolsmith） | [proto5/tools/](../tools/README.md)、`aos-agent tools new／wrap-py／wrap-cli`、`spec/kernel/`、`spec/daemon/` |
| HR | 決定團隊編制、人格、模板、薪資（模型選型） | Fable（調度者）人工決定 | `aos-team spawn`＋`aos-team score` 自動決定 | [spec/team/roster.md](../spec/team/roster.md)、[spec/team/spawn.md](../spec/team/spawn.md)、[templates/](../templates/) |
| 圖書館 | 全公司共用的知識，不屬於單一產線 | Fable 派的文件隊（像本隊） | aos 層圖書館員團隊自動維護 | 這個 [playbook/](README.md)、`spec/team/commons.md`（施工中，另一隊，還沒併進來） |
| 財務 | 算 token 花多少錢、每張單成本、額度 | **尚未成立** | 待建 | 無 |
| 支援單位（資安／總務） | 守牢、擋越權；開機關機、health、壞掉通知人 | Fable 派的審查隊（astra 唯讀審查）＋內建牆機制 | `aos-team` 門房牆與心跳自動運作 | [spec/team/wall.md](../spec/team/wall.md)、`aos up`／`aos down` |

## 各單位

**董事會**——使用者一人，出資人。給方向（`proto5/advice.md`，使用者自己維護的方向日記，這次不動它）、拍板（[wf/WAIT_USER.md](../../wf/WAIT_USER.md)）、抽查（每段挑 3 個詞條看，不用每條都看）、出錢（token 額度）。日常只看 `brief/` 日記，這就是**董事會簡報**——不用讀完整交接書。

**總裁**——Fable（調度者）。把董事的話翻成任務書、派隊給 Opus／Sonnet／gpt-6-astra、合併分支、跟董事匯報，**不親手做事**（頂層不要做太多事）。目標是總裁自己也變成 aos 裡的一個團隊：讀 `advice.md` 自己派工，Fable 到那時候只剩監督。

**總裁辦公室**——交接書 [wf/SESSION-LOG.md](../../wf/SESSION-LOG.md)、[wf/WAIT_USER.md](../../wf/WAIT_USER.md)、`brief/` 日記、worktree 清理，這些瑣事現在派 Sonnet 文件隊做（像本隊）。

**業務部**——面對客戶（使用者本人，只有一個）接單、交貨。接單＝`aos-team ask "一句話"`（門房整句句型比對，命中直接做，沒命中落穿給領隊）；交貨＝通過 `aos-team verify` 驗收的產出；客戶的問題彙整成一批一起問（而不是零星打斷），對應到用 AskUserQuestion 這類方式一次收斂。

**製造部**——一條產品線配一個 aos 團隊（領隊／寫手／審查員／驗收員）。第一條產線是 arknights（[proto5/examples/arknights/](../examples/arknights/)）。產線分三級：**手工**（強模型，現在這級）→**半自動**（笨模型）→**自動**（確定性程式），往下一級走不走，看品管部打的分數決定，不是憑感覺。

**品管部**——獨立於製造部，不能球員兼裁判。現有：評分器程式 `proto5/examples/arknights/eval/`（[說明](../notes/2026-09-25-arknights/eval/README.md)，機械檢查、證據行號檢查、評審、量測四道關）、驗收規則 [spec/team/verify.md](../spec/team/verify.md)、使用者自己的抽查制度。**鐵律：評審一律用別家模型**（不能自己評自己的作業），且評審要校準過（造壞版本測試抓不抓得到）。

**研發部**——三組：工具坊（`aos-agent tools new／wrap-py／wrap-cli`、toolsmith 造工具草稿）、流程組（單子與 `done_when` 樣板、門房路由規則）、內核組（daemon／kernel／tick-gap 這些排程底層）。造出來的工具、改完的流程都是研發部的產出。

**HR**——名冊 `team.json`（[spec/team/roster.md](../spec/team/roster.md)）、人格模板（[templates/](../templates/) 的 `lead`／`worker`／`reviewer`／`coder`／`importer`）、生工人 `aos-team spawn`、六軸考核（`aos-team score`）。**薪資表**＝「哪個位置最低能用哪顆模型」（`llm.json` 代號），**降級實驗**（強模型換笨模型看分數會不會掉）就是 HR 在幫每個職缺調薪。

**圖書館**——全公司共用、不屬於單一產線的知識放這裡。兩塊：aos 層的 commons（另一隊正在做 `spec/team/commons.md`，還沒併進 main，等它進來再補連結）＋ 這個 [playbook/](README.md)。每隊收尾的「沉澱」四樣（經驗、團隊架構、工作流架構、可複用工具）都交這裡。

**財務**——**尚未成立**。算 token 花多少錢、每張單成本、額度控管，目前完全沒有對應程式，列為下一段要建的部門。

**支援單位**——資安：門房、牆（[spec/team/wall.md](../spec/team/wall.md)）、`cmd_ok` 白名單、逃逸測試，擋越權操作。總務：`aos up`／`aos down` 開機關機、`health` 狀態、`--on-bad` 壞掉通知人。

## 公司節奏

一段＝一季：**接單 → 製造 → 品管打分 → 沉澱進圖書館 → HR 調薪（試降級）→ 董事會簡報**。董事每季只看 3 個詞條抽查、拍幾個要他決定的題目，不用逐條盯著看。
