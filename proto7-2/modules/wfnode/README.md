# node 工作流包（wfnode）

← [modules](../README.md)｜[proto7-2](../../README.md)｜計畫 [續推目標 1](../../notes/plan-2026-10-09-next.md)

**一句話**：給一個 aos node 裝上一棵「工作流樹」（`~/repo/workflows` 那套），讓跑在這個 node 上的 AI 每次開場都知道：該讀哪、手上還有什麼沒做完、上次停在哪。

## 第一次跑（約 1 分鐘）

要有 Python 3、bash，和 workflows 模板：預設找 `~/repo/workflows`（沒有就 `git clone git@github.com:justty32/workflows.git ~/repo/workflows`；放別處就 `export AOS7_WF_HOME=<它的路徑>`）。在 aos repo 根照抄：

```bash
proto7-2/modules/wfnode/aos7-wfnode init /tmp/mynode            # 1. 裝好工作流樹
proto7-2/modules/wfnode/aos7-wfnode state /tmp/mynode '寫完第一版，下一步跑測試'   # 2. 記一行「停在哪」
proto7-2/modules/wfnode/aos7-wfnode check /tmp/mynode           # 3. 體檢，印 OK 就對了
```

看成果：`cat /tmp/mynode/AGENTS.md`（AI 的入口）、`cat /tmp/mynode/wf/handoffs/NEXT-SESSION.md`（指向剛才那行）。整段示範也可以直接跑 `bash proto7-2/modules/wfnode/examples/minimal/run.sh`。

## 只有三個指令

| 指令 | 做什麼 | 什麼時候用 |
|---|---|---|
| `init <node> [--flavor heartbeat,multi-agent,dev]` | 裝工作流樹、填好知道的事實、跑檢查。**重跑安全**：已裝過就只補缺的檔、補填還留著 `{{` 的地方，你寫過的內容不動 | 新 node 一次 |
| `state <node> '一行'` | 把「現在停在哪、下一步」記進今天的續行點 | 每次收工、被打斷前 |
| `check <node>` | 連結沒壞、沒有沒填的 `{{`／沒處理的模板標記、清單裡沒有「做完卻沒刪」的項 | 隨時；退出碼 0＝健康 |

`--flavor` 不給＝裝 `dev,heartbeat,multi-agent`（aos node 的標準配備：會寫程式、被 tick 定期喚醒、跟別的 agent 收發信）；`--flavor ''` 只裝最小核心。

## 要懂的四個詞

1. **node**：aos 裡一個 agent 住的資料夾。
2. **工作流樹**（`wf/`）：一疊 md 檔，從 `AGENTS.md` 一層層指下去；AI 只讀它要的那一層。
3. **open 項**：`wf/SESSION-LOG.md`（我手上的）和 `wf/WAIT_USER.md`（等人做的）只列**還沒做完**的，一行一件；做完就刪那行。
4. **續行點**：`wf/handoffs/<日期>/STATE.md` 一天一份，`NEXT-SESSION.md` 指向最新那份；下次開場從那裡接。

## init 填了什麼、沒填什麼

- **裝在哪**：node 根只放 `AGENTS.md`、`CLAUDE.md`、`.claude/`，加上 multi-agent 的信箱 `inbox/` 與通訊腳本 `tools/`；其餘全在 `wf/`。
- **填**（查得到的事實）：node 名、驗證指令（本 repo 的 `run_all.py`）、時區（本機）、分支慣例「不 commit main，開分支交人 merge」、`wf/INDEX.md` 的佈局列。
- **不瞎猜**：其餘佔位寫成 `（未定：原本要填的東西）`，看得出還缺什麼。`〔模板說明〕` 段讀完即刪。
- **〔導入判斷〕**：首次導入時，模板原文**一字不差**的那幾段照 aos node 事實處理（單機、沒有離線／CI 差異；喚醒靠 tick、沒有上下班時機；例行／一次性表的資料在 json）；文字有變、混了別的判斷、或重跑時才看到的，一律不動，留給人：init 列出位置、`check` 不給過。
- **另建**（缺才建）：`wf/handoffs/NEXT-SESSION.md`；`wf/ROSTER.md`（導航到模板的 `workflows/inbox/ROSTER.md`；沒裝 multi-agent 時是空表）；`wf/line-claims.json`（誰能寫哪裡）；`wf/routines.json`、`wf/schedule.json`（routines 包讀寫）。後三者都是 wf-table/1 空表；ROSTER／line-claims 由 mail 包填。

## 契約卡

- **職責**：在 node 上導入並維持工作流樹；記續行點；機械檢查 open 衛生。
- **前置條件**：`~/repo/workflows`（或 `AOS7_WF_HOME`）有 `tools/wf-init.sh`；bash。
- **保證**：首次導入先在 `<node>/.wfnode-tmp/` 裡做完、再搬進 node，`AGENTS.md` 最後到（它在＝導入完成；中途被殺就重跑）；node 原有的檔不覆寫。重跑 `init` 只動還有 `{{`／〔模板說明〕的 md 與缺的三樣，其餘一個位元都不碰。`state` 在鎖內只追加當日 STATE 一行、只改 NEXT-SESSION 的「最新」那一行（原子替換）；同時跑幾個 `state` 也不丟行。`check` 唯讀。
- **明確不管**：不改 `~/repo/workflows` 本身（只呼叫它）；不決定〔導入判斷〕；不填 ROSTER／line-claims（mail 包）；不排程（routines 包）、不壓縮（compact 包）。

## 規則與界線

- 「做完沒刪」用字面判斷：條目行（`- [` 開頭）有 `[x]`、`✅`、刪除線、`已完成`／`已結案`／`已收線`、`DONE` 之類就算。寫法特別的漏網項抓不到，屬已知界線。
- `check` 用 workflows 的 `wf-lint.sh` 判斷壞連結；lint 的其他警告（超標檔、大條列）只印不擋。
- node 名（資料夾名）只能用一般字元：含 `[]{}()<>|` 等 markdown 符號的會被拒絕，免得填進文件變成連結或佔位。

## 測試

`tests/`（`python3 proto7-2/tests/run_all.py modules/wfnode/tests`）；沒有 `~/repo/workflows` 時整組跳過。
