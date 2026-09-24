← [team](README.md)

# 成員模板

`proto5/templates/<名>/`：一個資料夾生一種成員的家。內建 `lead`（領隊）、`worker`（工人）、`reviewer`（審查）三種給團隊用，`coder`（base 工具、不在團隊裡）給單獨的 agent 用。
`aos-team init` 對名冊每一列叫 `aos_agent_init.init_from_template()`；`aos-agent init --template 名` 的旗標由第 4 隊接（同一個函式）。

```text
templates/worker/
  template.json     設定（下表）
  system.md         人格（純文字；{name}、{mail_to}、{members} 會換成實際值）
```

## `template.json`

```json
{"_metainfo": {"_type": "aos_team_template", "_version": 1},
 "description": "工人：照交接書做一件事，做完回 DONE",
 "system": "system.md",
 "team": true,
 "project": "rw",
 "may": ["ask"],
 "llm": {"model": "default", "timeout_ms": 125000},
 "tick": {"interval_ms": 1000},
 "tools": [{"pack": "base"},
           {"pack": "task", "only": ["board", "ask_human"], "team": true},
           {"pack": "team", "only": ["team_say"], "team": true, "optional": true}],
 "mounts": {}}
```

| 鍵 | 意思 |
|---|---|
| `description` | 一句話（`aos-team ls`、`init` 會印） |
| `system` | 人格檔，相對模板資料夾 |
| `team` | true＝只能在團隊裡用（要名冊的資料：名字、能寄給誰）；單獨 `init --template` 會拒絕 |
| `project` | 專案掛進牢的方式：`rw`／`ro`；不在團隊裡＝家裡的 `workspace/`（可寫） |
| `may` | 這種成員能寄哪幾種申請（mail.md）；郵差照這個擋 |
| `llm` | 寫進 `info.json` 的 `llm`（`model` 會被名冊的 `model` 蓋掉）；池固定 `llm` |
| `tick` | `info.json` 的 `tick.interval_ms` |
| `tools` | 依序裝的工具包：`pack`（`proto5/tools/<名>/`）、`only`（只裝這幾支）、`team`（true＝裝完寫團隊設定，下面）、`optional`（true＝那個包還不在就跳過、印一行） |
| `mounts` | 多掛的資料夾：名字 → 路徑或 `{"$opt": "ro", "$val": 路徑}`，相對**模板資料夾**；名冊的 `mounts` 再疊上去 |

## 生出來的家

```text
members/worker-1/
  info.json        tools 列裝好的工具檔；llm、tick 照模板；縮排 2
  state.json       {"input": "input/"}——input 一律是資料夾
  access.json      下面
  prompts/system.json   {"content": system.md 換好變數}
  tools/…          tools add 裝的包（tools/<包>.json＋tools/<包> 連結＋版本資料夾）
  input/ log/
  .aos-template.json    {"template", "member", "complete"}：生到一半崩了，重跑 aos-team init 會補完
```

`access.json`（團隊成員）：

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "../../../p",
            "outbox": "../../team/outbox/worker-1",
            "board": {"$opt": "ro", "$val": "../../team/tasks"}},
 "cwd": "ws", "net": false}
```

- 路徑寫成**相對成員的家**（整個團隊資料夾搬走還能用）；模板的 `mounts` 在 proto5 裡，寫絕對路徑。
- 領隊、審查的 `ws` 是 `{"$opt": "ro", …}`。
- 不在團隊裡（`coder`）：`{"mounts": {"ws": "workspace"}, "cwd": "ws", "net": false}`。
- **一定有 `access.json`**：工具一律關牢，不靠「沒 access.json 也能跑」。
- 名冊或模板**多掛的可寫資料夾**不准碰團隊控制資料：`team.json`、`team/`（別人的 outbox、任務表、問題）、`members/`（所有人的家）、proto5 本身——一個包著另一個也算，`AccessUnsafe`；要看就掛唯讀。
- 自訂模板（名冊寫資料夾路徑）不准放在專案裡（工人改得到它的 `may` 與人格）：`BadTemplate`。換模板要先 `aos-team rm`（`.aos-template.json` 記了是哪個模板，不一樣＝`AlreadyExists`）。
- 生到一半崩了：`.aos-template.json` 的 `complete: false` 在就接著做；工具包算裝好要「工具檔在＋`info.tools` 有那一條」都成立。

## 工具包的團隊設定（`team: true` 的包）

裝完寫 `<家>/tools/<包>/config.json`（工具包原本的 config 保留，這幾個鍵蓋上去）。工具在牢裡從 `/opt/tool/config.json` 讀：

```json
{"member": "worker-1", "mail_to": ["lead", "human"], "members": ["lead", "worker-1", "reviewer"],
 "outbox": "/work/outbox", "board": "/work/board", "tz": "Asia/Taipei"}
```

- `outbox`、`board` 是**工具看到的路徑**（牢裡）；單元測試可以改成主機上的絕對路徑。
- 這份是名冊的**快照**，給工具擋手誤；改了名冊要重跑 `aos-team init`（已在的成員會更新這份設定、補裝新加的包，**不動人格、記憶、access.json**；人格裡的 {mail_to} 要自己改或 `aos-team rm` 後重生）。真正的把關在郵差。
- 工具寫信、寫申請：`<outbox>/<id>.json`，id＝`<epoch ns>-<pid>-<member>`，暫存檔（`.` 開頭）＋rename（mail.md）。
