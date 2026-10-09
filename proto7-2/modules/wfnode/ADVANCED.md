# wfnode 進階

← [README（第一次用）](README.md)｜[proto7-2](../../README.md)｜計畫 [續推目標 1](../../notes/plan-2026-10-09-next.md)

日常只要 README 的三個指令。這份給要用全部選項、要寫腳本判斷結果，或要維護本包的人。

## 進階選項

- **模板放別處**：`export AOS7_WF_HOME=<路徑>`（預設 `~/repo/workflows`）。
- **`--flavor`**：`init --flavor <逗號分隔>` 選要裝的模板包；不給＝`dev,heartbeat,multi-agent`（aos node 標準配備：會寫程式、被 tick 定期喚醒、跟別的 agent 收發信）；`--flavor ''` 只裝最小核心。
- **一鍵示範**：`bash proto7-2/modules/wfnode/examples/minimal/run.sh` 把 README「第一次跑」那三步跑一遍；只寫到 `mktemp -d` 開的暫存目錄、跑完自動刪，不動 repo。

## 給 AI 的待辦清單（check 會看）

`wf/SESSION-LOG.md`（AI 手上的）和 `wf/WAIT_USER.md`（等人做的）一行一件，格式 `- [標籤] 內容`；**只放還沒做完的**——做完就把那行刪掉。`check` 會抓「打了勾、寫已完成卻沒刪」的行，指出位置。

## init 填了什麼、沒填什麼

- **裝在哪**：node 根只放 `AGENTS.md`、`CLAUDE.md`、`.claude/`，加上 multi-agent 的信箱 `inbox/` 與通訊腳本 `tools/`；其餘全在 `wf/`。
- **填**（查得到的事實）：node 名、驗證指令（本 repo 的 `run_all.py`）、時區（本機）、分支慣例「不 commit main，開分支交人 merge」、`wf/INDEX.md` 的佈局列。
- **不瞎猜**：其餘寫成空格 `（未定：原本要填的東西）`。`〔模板說明〕` 段讀完即刪。
- **〔導入判斷〕**（通常不會碰到）：模板裡有幾段要依環境決定。首次導入時，模板原文**一字不差**的那幾段由工具自動照 aos node 事實改好（單機、沒有離線／CI 差異；喚醒靠 tick；例行／一次性表的資料在 json），不印出來；文字被改過、或重跑時才看到的，一律不動，留給人：init 印「要你決定：N 段」與位置、`check` 不給過，改好後刪掉標記即可。
- **另建**（缺才建）：`wf/handoffs/NEXT-SESSION.md`；`wf/ROSTER.md`（導航到模板的 `workflows/inbox/ROSTER.md`；沒裝 multi-agent 時是空表）；`wf/line-claims.json`（誰能寫哪裡）；`wf/routines.json`、`wf/schedule.json`（routines 包讀寫）。後三者都是 wf-table/1 空表；ROSTER／line-claims 由 mail 包填。**routines.json／schedule.json 的欄位格式歸 [routines 包](../routines/README.md) 管**：本包只照它建空表（欄位寫在 `aos7_wfnode.py` 的 `supplement`），那邊改欄位要兩邊一起改。

## 退出碼與錯誤訊息

寫腳本判斷結果時用；全 aos 共用同一套（[blueprint-errors](../../notes/blueprint-errors.md)）。

| 碼 | 意思 | wfnode 什麼時候 |
|---|---|---|
| 0 | 做到了 | 裝好、記好、體檢 OK |
| 1 | 做不到 | 體檢沒過（壞連結、做完沒刪、模板記號還在）；init 裝完仍有壞連結或 `{{` 殘留；模板安裝腳本失敗 |
| 2 | 你給的不對 | 參數錯（含 `--flavor` 寫錯）、還沒 init、找不到模板、node 名含符號、進度不是一行、`AOS7_WFNODE_NOW` 格式錯；什麼都沒動 |
| 3 | 不知道 | 連結檢查（wf-lint）沒跑完、讀寫檔案出錯（含檔案不是 UTF-8）；init／check 照原樣再跑會接續，state 先不帶句子看一下記上沒 |

非 0 時 stderr 只有一行 `aos7-wfnode: 發生什麼。怎麼辦`（退出 3 以 `不確定：` 開頭）；明細（BROKEN 行、`檔:行:` 位置、模板腳本的輸出）都在 stdout。成功時 stderr 不印。體檢同時有確定問題與 lint 沒跑完時退 1（已確定沒過）。

## 契約卡

- **職責**：在 node 上導入並維持工作流樹；記續行點；機械檢查 open 衛生。
- **前置條件**：`~/repo/workflows`（或 `AOS7_WF_HOME`）有 `tools/wf-init.sh`；bash。
- **保證**：首次導入先在 `<node>/.wfnode-tmp/` 裡做完、再搬進 node，`AGENTS.md` 最後到（它在＝導入完成；中途被殺就重跑）；node 原有的檔不覆寫。重跑 `init` 只補缺的三樣（NEXT-SESSION、ROSTER、line-claims；有例行／排程時含 routines.json、schedule.json），已存在的檔一個位元都不碰（含 `inbox/` 裡的信）；node 根的 `inbox/` 是信件，`init`／`check` 都不掃。`state` 在鎖內只追加當日 STATE 一行、只改 NEXT-SESSION 的「最新」那一行（原子替換）；同時跑幾個 `state` 也不丟行；不給句子的 `state` 與 `check` 唯讀。
- **明確不管**：不改 `~/repo/workflows` 本身（只呼叫它）；不決定〔導入判斷〕；不填 ROSTER／line-claims（mail 包）；不排程（routines 包）、不壓縮（compact 包）。

## 規則與界線

- 「做完沒刪」用字面判斷：條目行（`- [` 開頭）有 `[x]`、`✅`、刪除線、`已完成`／`已結案`／`已收線`、`DONE` 之類就算。寫法特別的漏網項抓不到，屬已知界線。
- `check` 用 workflows 的 `wf-lint.sh` 判斷壞連結；lint 的其他警告（超標檔、大條列）只印不擋。
- node 名（資料夾名）只能用一般字元：含 `[]{}()<>|` 等 markdown 符號的會被拒絕，免得填進文件變成連結或佔位。

## 測試

`tests/`（`python3 proto7-2/tests/run_all.py modules/wfnode/tests`）；沒有 `~/repo/workflows` 時整組跳過。
