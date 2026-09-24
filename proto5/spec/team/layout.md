← [team](README.md)

# 團隊資料夾

```text
<團隊>/                       aos-team 的 --target（沒給看 AOS_TEAM_HOME，再沒有＝目前資料夾）
  team.json                   名冊（roster.md）。人用文字編輯器改；aos-team init／rm 也會寫
  members/<名>/               各成員的 agent 家（aos-team init 照模板生；input 一律是資料夾 input/）
  members/.removed/<名>-<ns>/ aos-team rm 搬走的家（不刪）
  team/
    outbox/<名>/              成員寄出的信與申請（成員唯一可寫的團隊位置）；human、beat（心跳）也各有一格
    outbox/<名>/done/         郵差處理完的原檔
    outbox/<名>/rejected/     格式、身分、權限不合被退的原檔
    human/                    寄給 human 的信（人的收件匣；aos-team mail 看）
    post/sent/<信 id>.json    郵差的投遞紀錄＝去重憑據（一封一檔；第 2 隊定內容）
    tasks/<單號>.json         任務單（tasks.md）
    wait-user/<q-id>.json     等人回答的問題（ask.md）
    routes.json               門房規則（route.md）
    route.log                 門房每次的結果，一行一個 JSON
    routines.json  schedule.json   心跳（第 2 隊）
    notes/<名>/               長期筆記（第 4 隊）
    events/<名>.jsonl         事件紀錄（第 4 隊定；也可能放在成員家的 log/）
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
| 專案的 `SESSION-LOG.md`、`WAIT_USER.md` | 書記（郵差同一支） | — |
| `team.json`、`routes.json` | 人（文字編輯器）；`aos-team init`、`rm`、`route save` | 模型不能改 |
| 成員的家（`info.json`、人格、記憶、工具、`access.json`） | 人、`aos-agent` 指令；`aos-team init` 第一次生 | 模型改不到（信任資料，[agent access.md](../agent/access.md)） |

## 成員在牢裡看到什麼

每個成員的家都有 `access.json`（templates.md 生），工具關在牢裡跑，看得到的只有：

| 牢裡 | 對到 | 誰有 | 可寫 |
|---|---|---|---|
| `/work/ws`（起點） | 專案資料夾（`team.json` 的 `project`） | 全部 | 工人可寫；領隊、審查唯讀 |
| `/work/outbox` | `team/outbox/<自己>/` | 全部 | 可寫（寄信、寄申請都寫這裡） |
| `/work/board` | `team/tasks/` | 全部 | 唯讀（`board` 工具看任務表） |
| `/work/<其他>` | 名冊或模板多掛的（例：第 3 隊的 `wf` 快照） | 看設定 | 看設定 |

`ws`、`outbox`、`board` 三個名字是保留的。工具程式在 `/opt/tool`（工具包自己的資料夾，唯讀），工具包的 `config.json` 在那裡。
另一隊 L2 正在改「檔案工具的根＝整個 `/work`」：改完後 `read`、`ls` 也看得到 `/work/board`，不影響這裡的約定。
