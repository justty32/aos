# node 工作流包（wfnode）

← [modules](../README.md)｜[proto7-2](../../README.md)｜計畫 [續推目標 1](../../notes/plan-2026-10-09-next.md)

**一句話**：替 AI 準備一個「工作筆記資料夾」，並讓你每次收工記一句「停在哪、下一步做什麼」；AI 下次開工先看這句就知道從哪接。

## 第一次跑（約 3 分鐘）

要有 Python 3、bash，和工作流模板 `~/repo/workflows`（沒有就先 `git clone git@github.com:justty32/workflows.git ~/repo/workflows`）。在 aos repo 根照抄這三行；全部只寫到 `/tmp/mynode`，不動 repo：

```bash
proto7-2/modules/wfnode/aos7-wfnode init  /tmp/mynode                              # 1. 裝好資料夾
proto7-2/modules/wfnode/aos7-wfnode state /tmp/mynode '寫完第一版，下一步跑測試'   # 2. 記一句「停在哪」
proto7-2/modules/wfnode/aos7-wfnode check /tmp/mynode                              # 3. 體檢
```

你會看到（數字可能不同）：

```text
裝好了：/tmp/mynode（AI 開場讀 AGENTS.md；人不必讀）
空格：97 處寫著「（未定：…）」＝工具查不到、之後由你或 AI 慢慢補；不影響使用，check 也不檢查它
下一步：aos7-wfnode check /tmp/mynode
已記到 wf/handoffs/2026-10-09/STATE.md（AI 下次開場從這裡接）
待辦清單：AI 手上 0 件（wf/SESSION-LOG.md）、等人做 0 件（wf/WAIT_USER.md）
OK：資料夾沒壞（連結都通、清單沒有做完沒刪的、模板記號都處理了）。「（未定：…）」空格 97 處不在檢查範圍
```

**看到最後一行 `OK` 就成功了。** OK 的意思是「資料夾沒壞」，不是「每個空格都填好了」——那 97 處空格本來就留給之後慢慢補，第一次可以完全不管。

看成果：`proto7-2/modules/wfnode/aos7-wfnode state /tmp/mynode`（不給句子＝印出剛才記的那句）。試完 `rm -rf /tmp/mynode` 即可。

## 只有三個指令

| 指令 | 做什麼 | 什麼時候用 |
|---|---|---|
| `init <資料夾>` | 裝好資料夾；**重跑安全**，只補缺的，你寫過的不動 | 新 node 一次 |
| `state <資料夾> '一句'` | 記一句「停在哪、下一步」；不給句子＝印出最新那份 | 每次收工、被打斷前 |
| `check <資料夾>` | 體檢：印 `OK`（退出碼 0）＝沒壞；不 OK 會指出哪個檔第幾行、該怎麼改 | 隨時 |

## 要懂的三個詞

1. **node**：AI 住的資料夾（就是你給 init 的那個路徑）。
2. **續行點**：你用 `state` 記的那句「停在哪」；一天一份，AI 開場先看最新那份。
3. **空格**：init 查不到的資訊寫成 `（未定：…）`，之後誰知道誰補；不填也能用。

裡面其他檔（`AGENTS.md`、`wf/` 底下一疊 md）是**給 AI 讀的**，人不必讀；想瞄一眼，只看 `AGENTS.md` 最上面「開場與入口」那段就夠。

---

**以下給進階使用與維護者，第一次用不必讀。**

## 進階選項

- **模板放別處**：`export AOS7_WF_HOME=<路徑>`（預設 `~/repo/workflows`）。
- **`--flavor`**：`init --flavor <逗號分隔>` 選要裝的模板包；不給＝`dev,heartbeat,multi-agent`（aos node 標準配備：會寫程式、被 tick 定期喚醒、跟別的 agent 收發信）；`--flavor ''` 只裝最小核心。
- **一鍵示範**：`bash proto7-2/modules/wfnode/examples/minimal/run.sh` 把上面三步跑一遍；只寫到 `mktemp -d` 開的暫存目錄、跑完自動刪，不動 repo。

## 給 AI 的待辦清單（check 會看）

`wf/SESSION-LOG.md`（AI 手上的）和 `wf/WAIT_USER.md`（等人做的）一行一件，格式 `- [標籤] 內容`；**只放還沒做完的**——做完就把那行刪掉。`check` 會抓「打了勾、寫已完成卻沒刪」的行，指出位置。

## init 填了什麼、沒填什麼

- **裝在哪**：node 根只放 `AGENTS.md`、`CLAUDE.md`、`.claude/`，加上 multi-agent 的信箱 `inbox/` 與通訊腳本 `tools/`；其餘全在 `wf/`。
- **填**（查得到的事實）：node 名、驗證指令（本 repo 的 `run_all.py`）、時區（本機）、分支慣例「不 commit main，開分支交人 merge」、`wf/INDEX.md` 的佈局列。
- **不瞎猜**：其餘寫成空格 `（未定：原本要填的東西）`。`〔模板說明〕` 段讀完即刪。
- **〔導入判斷〕**（通常不會碰到）：模板裡有幾段要依環境決定。首次導入時，模板原文**一字不差**的那幾段由工具自動照 aos node 事實改好（單機、沒有離線／CI 差異；喚醒靠 tick；例行／一次性表的資料在 json），不印出來；文字被改過、或重跑時才看到的，一律不動，留給人：init 印「要你決定：N 段」與位置、`check` 不給過，改好後刪掉標記即可。
- **另建**（缺才建）：`wf/handoffs/NEXT-SESSION.md`；`wf/ROSTER.md`（導航到模板的 `workflows/inbox/ROSTER.md`；沒裝 multi-agent 時是空表）；`wf/line-claims.json`（誰能寫哪裡）；`wf/routines.json`、`wf/schedule.json`（routines 包讀寫）。後三者都是 wf-table/1 空表；ROSTER／line-claims 由 mail 包填。

## 契約卡

- **職責**：在 node 上導入並維持工作流樹；記續行點；機械檢查 open 衛生。
- **前置條件**：`~/repo/workflows`（或 `AOS7_WF_HOME`）有 `tools/wf-init.sh`；bash。
- **保證**：首次導入先在 `<node>/.wfnode-tmp/` 裡做完、再搬進 node，`AGENTS.md` 最後到（它在＝導入完成；中途被殺就重跑）；node 原有的檔不覆寫。重跑 `init` 只動還有 `{{`／〔模板說明〕的 md 與缺的三樣，其餘一個位元都不碰。`state` 在鎖內只追加當日 STATE 一行、只改 NEXT-SESSION 的「最新」那一行（原子替換）；同時跑幾個 `state` 也不丟行；不給句子的 `state` 與 `check` 唯讀。
- **明確不管**：不改 `~/repo/workflows` 本身（只呼叫它）；不決定〔導入判斷〕；不填 ROSTER／line-claims（mail 包）；不排程（routines 包）、不壓縮（compact 包）。

## 規則與界線

- 「做完沒刪」用字面判斷：條目行（`- [` 開頭）有 `[x]`、`✅`、刪除線、`已完成`／`已結案`／`已收線`、`DONE` 之類就算。寫法特別的漏網項抓不到，屬已知界線。
- `check` 用 workflows 的 `wf-lint.sh` 判斷壞連結；lint 的其他警告（超標檔、大條列）只印不擋。
- node 名（資料夾名）只能用一般字元：含 `[]{}()<>|` 等 markdown 符號的會被拒絕，免得填進文件變成連結或佔位。

## 測試

`tests/`（`python3 proto7-2/tests/run_all.py modules/wfnode/tests`）；沒有 `~/repo/workflows` 時整組跳過。
