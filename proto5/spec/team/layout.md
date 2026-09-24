← [team](README.md)

# 團隊資料夾

```text
<團隊>/                       aos-team 的 --target（沒給看 AOS_TEAM_HOME，再沒有＝目前資料夾）
  team.json                   名冊（roster.md）。人用文字編輯器改；aos-team init／rm 也會寫
  members/<名>/               各成員的 agent 家（aos-team init 照模板生；input 一律是資料夾 input/）
    log/events.jsonl          事件紀錄（spec/agent/events.md；Layout.events()）
    compact-req/              郵差投進來的 compact 申請；done/ 放 tick 的收據（compact-more.md §5）
  members/.removed/<名>-<ns>/ aos-team rm 搬走的家（不刪）
  team/
    outbox/<名>/              成員寄出的信與申請；human、beat（心跳）也各有一格
    outbox/<名>/done/         郵差處理完的原檔
    outbox/<名>/rejected/     格式、身分、權限不合被退的原檔
    human/                    寄給 human 的信（人的收件匣；aos-team mail 看）
    post/sent/<信 id>.json    郵差的投遞紀錄＝去重憑據（一封一檔；第 2 隊定內容）
    tasks/<單號>.json         任務單（tasks.md）
    wait-user/<q-id>.json     等人回答的問題（ask.md）
    routes.json               門房規則（route.md）
    route.log                 門房每次的結果，一行一個 JSON
    routines.json  schedule.json   心跳（第 2 隊）
    locks/<名>.json           短期獨佔鎖（lock.md；第二波 C 隊，只有郵差寫）
    spawns/s-NNNN.json        生新成員的申請紀錄（spawn.md；第三波 W3-1，只有郵差寫）
    tool-drafts/d-NNNN/       工具草稿：郵差生的包＋draft.json（toolsmith.md；第三波 W3-1，只有郵差寫）
    outbox/<名>/tools-staging/<工具名>/   tool_draft 給模型自己看的副本（郵差不讀）
    notes/<名>/               長期筆記 notes.json（模板 notes: true 的成員才有；init 建）
```

- 名字：成員 `[a-z][a-z0-9_-]{0,31}`；`human`（人）、`post`（郵差自己生的信）、`beat`（心跳，定時器；第 2 隊 2026-09-24 追加）是保留名，不能當成員。
- kernel 用家的資料夾名登記（`agent-<名>`）：**同一個 kernel 上兩支團隊不能有同名成員**（第二支 start 會撞 `AlreadyExists`、說「同名行程是…」）。要跑兩支團隊就把成員名取得不一樣，或各用一個 kernel。
- **團隊資料夾不要放在專案資料夾裡面**：工人把專案掛成可寫，會蓋到成員的家（信任資料）→ `AccessUnsafe`，那一批工具不跑。
- 寫檔一律「暫存檔（`.` 開頭、`.tmp` 結尾）＋rename 或 link」。讀資料夾的程式只看不以 `.` 開頭的 `*.json`。

## 一份資料一個寫的人

| 位置 | 誰寫 | 別人要改怎麼辦 |
|---|---|---|
| `team/outbox/<名>/*.json` | 成員 `<名>` 自己（經工具）；`human` 那格是 `aos-team ask／answer／task cancel…` | — |
| `outbox/<名>/done/`、`rejected/`、`post/sent/`、`human/`、成員的 `input/mail-*.json` | 郵差 | — |
| `team/tasks/*.json`、`team/wait-user/*.json` | 郵差（叫 `aos_team_task`／`aos_team_ask` 的處理函式） | 模型寄申請；人用 `aos-team task …`、`answer`（也是寄申請） |
| `team/locks/*.json` | 郵差（叫 `aos_team_lock.on_lock`，第二波 C 隊） | 模型、人都寄 `kind: lock` 申請（`lock` 工具、`aos-team lock acquire／release`） |
| `team/spawns/*.json`、`team/tool-drafts/` | 郵差（`aos_team_spawn.on_spawn`、`aos_team_toolsmith.on_tool_draft`，第三波 W3-1） | 模型寄 `spawn`／`tool_draft` 申請；人 `aos-team spawn approve`／`tool approve` 只讀它們，改的是名冊與成員的家 |
| 專案的 `SESSION-LOG.md`、`WAIT_USER.md` | 書記（郵差同一支） | — |
| `team.json`、`routes.json` | 人（文字編輯器）；`aos-team init`、`rm`、`route save` | 模型不能改 |
| 成員的家（`info.json`、人格、記憶、工具、`access.json`） | 人、`aos-agent` 指令；`aos-team init` 第一次生 | 模型改不到（信任資料，[agent access.md](../agent/access.md)） |
| `members/<名>/compact-req/*.json` | 郵差建原檔（`compact` 申請）；那個成員的 tick 在 `done/` 放同名收據，**原檔不刪**（郵差靠它去重） | 要清就在成員停著時連收據一起刪 |
| `members/<名>/log/events.jsonl` | 持那個家 tick 鎖的一方（agent 自己、`aos-agent` 指令） | 郵差只看修改時間（post.md 看停滯） |
| `team/notes/<名>/notes.json` | 成員 `<名>` 自己（`note` 工具，牢裡 `/work/notes`） | 人看 `aos-agent notes`；要改就直接編輯（成員停著時） |

## 成員在牢裡看到什麼

每個成員的家都有 `access.json`（templates.md 生），工具關在牢裡跑，看得到的只有：

| 牢裡 | 對到 | 誰有 | 可寫 |
|---|---|---|---|
| `/work/ws`（起點） | 專案資料夾（`team.json` 的 `project`） | 全部 | 工人可寫；領隊、審查唯讀 |
| `/work/outbox` | `team/outbox/<自己>/` | 全部 | 可寫（寄信、寄申請都寫這裡） |
| `/work/board` | `team/tasks/` | 全部 | 唯讀（`board` 工具看任務表） |
| `/work/notes` | `team/notes/<自己>/` | 模板 `notes: true`（領隊、工人） | 可寫（`note` 工具寫 `notes.json`） |
| `/work/mem` | 自己家的 `prompts/`（記憶 `history.json`、壓縮封存 `archive/`） | 模板 `notes: true`（領隊、工人） | 唯讀（`recall` 找原文、`context` 量記憶） |
| `/work/<其他>` | 名冊或模板多掛的（例：第 3 隊的 `wf` 快照） | 看設定 | 看設定 |

`ws`、`outbox`、`board`、`notes`、`mem` 五個名字是保留的。`mem` 掛的是資料夾不是檔：tick 用暫存檔＋改名換掉 `history.json`，掛檔會一直看到舊的那份。成員在團隊資料夾裡可寫的只有自己的 outbox 與 notes 兩格。工具程式在 `/opt/tool`（工具包自己的資料夾，唯讀），工具包的 `config.json` 在那裡。
另一隊 L2 正在改「檔案工具的根＝整個 `/work`」：改完後 `read`、`ls` 也看得到 `/work/board`，不影響這裡的約定。
