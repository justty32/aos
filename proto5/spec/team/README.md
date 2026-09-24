← [spec 總導航](../README.md)｜規劃：[工具大開發時代](../../notes/2026-09-24-tool-era/README.md)｜分工：[plan.md](../../notes/2026-09-24-tool-era/plan.md)

# team：一支 agent 團隊的資料夾、名冊、信、任務單與問人

一句話：**一支團隊＝一個資料夾**：`team.json` 名冊、`members/<名>/` 每個成員的 agent 家、`team/` 裡放信、任務單、等人回答的問題。
成員（會想的 agent）只會往自己的 `team/outbox/<名>/` 放檔；搬信、開單、改狀態都是**郵差**這支機械程式做，不問模型。

> 第 1 版，2026-09-24（工具大開發時代第一波第 1 隊）。這一份是**跨隊共用的契約**：第 2 隊（郵差、驗收、心跳）、第 3 隊（檔案與 workflows 工具包）、第 4 隊（記憶與紀錄）照這裡的格式做；要改格式寫進自己的報告，不要自己改這裡。
> 實作：讀驗 [`lib/aos_team_format.py`](../../lib/aos_team_format.py)、任務狀態機 [`lib/aos_team_task.py`](../../lib/aos_team_task.py)、問人 [`lib/aos_team_ask.py`](../../lib/aos_team_ask.py)、申請登記表 [`lib/aos_team_requests.py`](../../lib/aos_team_requests.py)、指令分派 [`lib/aos_team_cli.py`](../../lib/aos_team_cli.py)＋[`cli/aos-team`](../../cli/aos-team)。

## 已拍板的前提（使用者定的）

1. 隊形：三種會想的 agent（領隊 lead、工人 worker、審查 reviewer）＋四個機械員（門房、郵差兼書記、驗收員、心跳），機械員不問模型。
2. 規則放工具、不放人格；不給模型「等」的工具；一份資料一個寫的人。
3. 權限牆（[agent access.md](../agent/access.md)）已在：每個成員的家都附 `access.json`，工具一律關牢跑。**不依賴「沒 access.json 也能跑」**。
4. 模型只走 LiteLLM `http://localhost:4000/v1` 的 `deepseek-chat`；機械的部分一律不叫模型。

## 各節

| 檔 | 內容 |
|---|---|
| [layout.md](layout.md) | 團隊資料夾長怎樣、每個位置誰寫、成員在牢裡看到什麼（`/work/ws`、`/work/outbox`、`/work/board`） |
| [roster.md](roster.md) | `team.json` 名冊：專案、時區、成員（模板、模型、能寄給誰、多掛的資料夾）、上限 |
| [mail.md](mail.md) | 信與申請：outbox 檔名與 id、欄位、六個 STATUS、郵差怎麼投（`input/mail-<id>.json`、信頭一行）、申請種類與處理函式的約定 |
| [tasks.md](tasks.md) | 任務單（交接書）：欄位、十個狀態、事件、後續動作、審查子單、冪等 |
| [ask.md](ask.md) | 問人：`ask_human` → `team/wait-user/q-NNNN.json` → `aos-team answer` → 投回發問者 |
| [templates.md](templates.md) | 成員模板 `proto5/templates/<名>/`：人格、工具包、`access.json`、工具包的 `config.json` |
| [route.md](route.md) | 門房 `team/routes.json`：整句句型、命中兩條或有否定詞就落穿給領隊、例句全過才准存 |
| [cli.md](cli.md) | `aos-team` 子命令一覽、哪一隊做、共同慣例（`--target`、退出碼） |
| [post.md](post.md) | 郵差兼書記 `aos-team post`：kernel 反覆叫，每次走一輪（投信、收驗收結果、看停滯與期限、書記同步 SESSION-LOG／WAIT_USER），不叫模型 |
| [verify.md](verify.md) | 驗收員 `aos-team verify`：照任務單 `done_when` 跑固定的檢查器，每條回過／不過／檢查器壞 |
| [beat.md](beat.md) | 心跳 `aos-team beat`、`aos-team routine`：kernel 反覆叫（預設 60 秒一輪），照 `team/routines.json` 算誰到期、以開單方式派出 |
| [wall.md](wall.md) | 團隊的牆（第二波 B 隊）：誰關在牢裡（成員工具、門房 `tool`、驗收的 lint 與 `cmd_ok`）、成員的映射、郵差再驗什麼、`cmd_ok` 白名單、保證外的 |
| [score.md](score.md) | 六軸彙整 `aos-team score`：把六軸表（axes.md §4 團隊欄）能自動量的部分讀紀錄填好，只讀、不叫模型 |
| [examples/](examples/) | 每種檔一份範例；`python3 lib/aos_team_format.py 檔…` 驗得過 |

## 最小驗證程式

```sh
python3 proto5/lib/aos_team_format.py proto5/spec/team/examples/*.json   # 每檔一行 ok／錯在哪，全對退 0
```

它看 `_metainfo._type`（名冊、任務單、問題、模板、門房規則）或欄位（有 `kind`＝申請、有 `status`＋`to`＝信）決定用哪一種驗。

## 誰做什麼（第一波）

| 部分 | 誰 | 在哪 |
|---|---|---|
| 這份規範、名冊、`aos-team init／start／stop／ls／rm`、模板、門房、任務單狀態機、`handoff`／`board`／`review_result`／`ask_human` 工具、`task`／`wait`／`answer` 指令 | 第 1 隊 | `lib/aos_team*.py`（郵差除外）、`proto5/templates/`、`proto5/tools/task/` |
| `team_say` 工具、郵差兼書記（投信、呼叫處理函式、做後續動作、SESSION-LOG／WAIT_USER、看停滯）、驗收員、心跳、`aos-team mail／post／verify／routine／beat` | 第 2 隊 | `proto5/tools/team/`、`lib/aos_team_post.py`、`aos_team_verify.py`、`aos_team_beat.py` |
| `wf_*`、`json_edit`、`md_section`（工人的工具；wf 快照唯讀掛成 `/work/wf`） | 第 3 隊 | `proto5/tools/wf/`、`proto5/tools/files/` |
| 事件紀錄、`context`、`compact`、`note`、`aos-agent init --template` 的旗標 | 第 4 隊 | `lib/aos_agent_*.py` |
| README／索引彙整、`aos-team score`、`compact_me`（task 包第五支）、模板 `notes: true`、成員模板人格定稿、`route.md` 的 routes 例子、教程 08（一支小團隊） | 收尾隊（第 5 隊） | `lib/aos_team_score.py`、`proto5/tools/task/compact_me`、`proto5/templates/`、`proto5/tutorials/08-team.md` |
