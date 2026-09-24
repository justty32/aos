← [team](README.md)

# `team.json`：名冊

```json
{
  "_metainfo": {"_type": "aos_team", "_version": 1},
  "project": "../p",
  "tz": "Asia/Taipei",
  "members": {
    "lead":     {"template": "lead",     "mail_to": ["worker-1", "reviewer", "human"]},
    "worker-1": {"template": "worker",   "mail_to": ["lead", "human"]},
    "reviewer": {"template": "reviewer", "mail_to": ["lead", "human"]}
  },
  "limits": {"stale_minutes": 10, "max_members": 6}
}
```

縮排 2、用文字編輯器改。改完跑 `aos-team init`：新加的成員會生家，已在的成員不動（要照新設定重生，先 `aos-team rm 名字` 再 init）。

| 鍵 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 可省 | 有寫就要 `{"_type": "aos_team", "_version": 1}` |
| `project` | 字串 | 是 | 專案資料夾；相對路徑從 **team.json 所在的資料夾**算，可用 `~`。要先存在 |
| `tz` | 字串或 null | 否 | IANA 時區（信頭時間、任務單時間用）；沒寫＝本機 |
| `members` | 物件 | 是 | 名字 → 成員（下表）；至少一個 |
| `limits.stale_minutes` | 整數 | 否（10） | 書記看停滯的門檻（第 2 隊用） |
| `limits.max_members` | 整數 | 否（6） | 成員數上限；超過＝整份不收 |
| `post.interval_s` | 整數 | 否（5） | 郵差多久巡一次信箱（秒，1～3600；第 2 隊 2026-09-24 追加）；改了要 `aos-team stop`、`start` |

頂層其他鍵＝`FormatInvalid`（抓 `member`、`limit` 這類手誤）。

## 成員

| 鍵 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `template` | 字串 | 是 | 模板名（`proto5/templates/<名>/`）或含 `/` 的模板資料夾路徑（templates.md） |
| `model` | 字串或 null | 否 | `llm.json` 裡的模型代號；沒寫＝模板的 `llm.model`，再沒有＝`default` |
| `mail_to` | 名字陣列 | 否（`[]`） | 能寄信給誰：其他成員名或 `human`；不能寫自己、不能寫名冊外的 |
| `mounts` | 物件 | 否 | 多掛進牢的資料夾：名字 → 路徑字串或 `{"$opt": "ro", "$val": 路徑}`；相對路徑從團隊資料夾算。`ws`／`outbox`／`board` 是保留名 |
| `tools` | 陣列 | 否 | 多裝的工具包（格式同模板的 `tools` 元素，templates.md） |

- 名字 `[a-z][a-z0-9_-]{0,31}`，不能是 `human`、`post`。
- `mail_to` 是給工具擋手誤用的（`team_say` 寄給名冊外＝`BadArguments`），郵差投信前**再驗一次**；人（`human`）能寄給任何成員。
- 派工（`handoff`）的負責人要在開單人的 `mail_to` 裡。
- 誰能寄哪種申請看**模板**的 `may`（templates.md），不看名冊——名冊是人手改的，權限不跟著手誤走。

## 讀法

`aos_team_format.load_roster(團隊資料夾)` 讀驗、補預設，回 `{"project", "tz", "members": {名: {"template", "model", "mail_to", "mounts", "tools"}}, "limits"}`；錯＝`TeamError`（`FormatInvalid`、`JsonSyntax`、`NotFound`、`ReadFailed`），白話帶檔名與欄位位置（例：`team.json.members.worker-1.mail_to：boss 不在名冊裡（也不是 human）`）。
