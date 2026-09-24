← [team](README.md)

# 成員模板

`proto5/templates/<名>/`：一個資料夾生一種成員的家。內建 `lead`（領隊）、`worker`（工人）、`reviewer`（審查）三種給團隊用，`coder`（base 工具、不在團隊裡）給單獨的 agent 用。
（第二波 A 隊）另有 `importer`（導入工人）：只做「把 workflows 手冊導入專案」，只裝 base 的 read／edit／ls、wf 的 wf_doc／wf_init／wf_fill／wf_residue／wf_lint、ask_human、team_say 共 10 支，工具表約 5,600 字元（worker 20 支約 12,700）；沒有 notes、compact。要用就在名冊加一列（例 `"importer-1": {"template": "importer", "mail_to": ["lead", "human"]}`），門房的導入規則 `assignee` 改成它。
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
 "notes": true,
 "may": ["ask", "compact"],
 "llm": {"model": "default", "timeout_ms": 125000},
 "tick": {"interval_ms": 1000},
 "tools": [{"pack": "base"},
           {"pack": "task", "only": ["board", "ask_human", "compact_me"], "team": true},
           {"pack": "team", "only": ["team_say"], "team": true, "optional": true},
           {"pack": "notes"}],
 "mounts": {}}
```

| 鍵 | 意思 |
|---|---|
| `description` | 一句話（`aos-team ls`、`init` 會印） |
| `system` | 人格檔，相對模板資料夾 |
| `team` | true＝只能在團隊裡用（要名冊的資料：名字、能寄給誰）；單獨 `init --template` 會拒絕 |
| `project` | 專案掛進牢的方式：`rw`／`ro`；不在團隊裡＝家裡的 `workspace/`（可寫） |
| `notes` | true＝多掛 `notes` → `team/notes/<名>/`（可寫，只有自己那格；init 建資料夾），給 `notes` 包的 `note` 工具（牢裡預設寫 `/work/notes/notes.json`）。只給團隊模板；內建的領隊、工人有，審查沒有 |
| `may` | 這種成員能寄哪幾種申請（mail.md）；郵差照這個擋。領隊、工人有 `compact`（`compact_me` 工具縮自己的記憶） |
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
            "board": {"$opt": "ro", "$val": "../../team/tasks"},
            "notes": "../../team/notes/worker-1",
            "mem": {"$opt": "ro", "$val": "prompts"}},
 "cwd": "ws", "net": false}
```

- 路徑寫成**相對成員的家**（整個團隊資料夾搬走還能用）；模板的 `mounts` 在 proto5 裡，寫絕對路徑。
- 領隊、審查的 `ws` 是 `{"$opt": "ro", …}`；審查沒有 `notes`、`mem`。
- `mem`＝自己家的 `prompts/`，**唯讀**（notes 包的 `recall`、`context` 在牢裡讀 `/work/mem`）；它跟信任資料重疊，唯讀才准（[agent-access contract §3](../../notes/2026-09-24-agent-access/contract.md)）。
- `outbox`、`notes`、`mem` 是 init 內建的掛點（保留名，名冊與模板的 `mounts` 用不了），只指自己那格，所以不受下一條限制。
- 已生的舊家重跑 `aos-team init`：模板 `notes: true` 而 `access.json` 缺 `notes` 或 `mem`＝只補缺的那格（印「access.json 補掛 …」），其他掛載不動。
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
- 這份是名冊的**快照**，給工具擋手誤；改了名冊要重跑 `aos-team init`（已在的成員會更新這份設定、補裝新加的包，**不動人格、記憶、access.json**；人格裡的 {mail_to} 要自己改或 `aos-team rm` 後重生）。
  access.json 唯一的例外：模板 `notes: true` 而 access.json 還沒有 `notes` 掛載（notes 之前生的舊家）＝補這一格、建資料夾、印「補掛 notes」；其他掛載不動，`notes` 已被人改指別處也不動。真正的把關在郵差。
- 工具寫信、寫申請：`<outbox>/<id>.json`，id＝`<epoch ns>-<pid>-<member>`，暫存檔（`.` 開頭）＋rename（mail.md）。
