← [team](README.md)

# 門房：`team/routes.json`

`aos-team ask "一句話"` 先過門房：**整句句型比對**，命中就不叫模型。這是 ai_core「LLM 是 switch 的 default」那句。

```json
{"_metainfo": {"_type": "aos_team_routes", "_version": 1},
 "negations": ["不要", "別", "取消", "不用", "勿", "不准"],
 "routes": [
  {"name": "tasks", "pattern": "(列|看)(一下)?(任務|單子)", "do": "tool", "run": ["task", "ls"],
   "tests": {"hit": ["列任務", "看一下單子"], "miss": ["列任務給 bob 看", "把任務刪掉"]}},
  {"name": "import", "pattern": "把 workflows 導入 (?P<project>\\S+)，照 (?P<facts>\\S+)",
   "do": "handoff",
   "handoff": {"assignee": "importer-1", "workflow": "IMPORT.md", "goal": "把 workflows 導入 {project}",
               "facts": "{facts}", "done_when": [{"kind": "check", "name": "wf_residue"}]},
   "tests": {"hit": ["把 workflows 導入 p，照 facts.json"], "miss": ["把 workflows 導入 p"]}}]}
```

## 規則

- `pattern`：Python 正規式，跟**整句**比（`fullmatch`，前後空白先去掉）。不是找關鍵字。
- 具名群組（`(?P<名>…)`）都要有值才算命中；`handoff` 與 `run` 裡字串的 `{名}` 換成群組的值（只換名字對得上的；`run` 那種 2026-09-24 收尾隊加，例：`每 2m 數一次 md 檔` → `routine add … --every 2m`）。
- **命中兩條以上**或**句子含否定詞**（`negations`，沒寫用上面那六個）＝不自己做、**落穿給領隊**（「不要導入 heartbeat」不能觸發導入）。
- 沒命中＝落穿：原話當一封 `REQUEST` 從 `human` 寄給領隊（名冊第一個 `template: lead` 的成員；沒有領隊＝退 1、說清楚）。
- 每次結果記一行進 `team/route.log`：`{"at", "text", "result": "tool"|"handoff"|"lead"|"none", "route": 名或 null, "why"}`（`none`＝該落穿但隊裡沒有領隊，退 1、代號 `NoLead`）。
  （第三波 W3-2）`result` 是 `lead` 的那行多一格 `"letter"`：投給領隊的那封 REQUEST 的 id（只加欄位，讀舊格式的程式不受影響；舊 log 沒有這格）。`aos-team crystal`（[crystal.md](crystal.md)）靠它對回「落穿之後領隊開了什麼單」，從常落穿的句型提候選規則給人批。

## `do` 三種

| `do` | 欄位 | 做什麼 |
|---|---|---|
| `tool` | `run`：aos-team 子命令與參數（例 `["task", "ls"]`、`["wait", "ls"]`） | 在同一個行程跑那個子命令，輸出原樣印給人；**不寫任何成員的 `input/`** |
| `tool` | `tool`：`"<包>/<工具>"`（`proto5/tools/<包>/<包>.json` 裡的一支）、`args`：物件、`project`?：`ro`（預設）／`rw` | 照工具檔的 `_meta.argv` 跑那支程式，**關在牢裡**（第二波 B 隊，[wall.md](wall.md)）：只看得到專案（`/work/ws`，起點；預設唯讀，寫 `"project": "rw"` 才可寫）、不上網、清環境；stdin 給 `args`、60 秒逾時；輸出原樣印。只跑 `proto5/tools/` 裡的包。沒有 bwrap＝退 1（`NoBwrap`），不退回不關牢 |
| `handoff` | `handoff`：同 handoff 申請的欄位（mail.md） | 往 `team/outbox/human/` 放一份 handoff 申請（開單人是 human）；郵差開單、派出 |

`handoff` 規則可以多一格 `if_missing`（真跑 09-25 加）：`{"path": "aos-drafts/{name}/", "goal"?: "…", "facts"?: "…"}`。`path` 是專案裡的相對路徑（可用 `{群組}`；不准 `/`、`~` 開頭或 `..`）；**不在或是空資料夾**時，單子的 `goal`／`facts` 換成這裡寫的（沒寫 `facts`＝「無草稿、從原文起（<path> 不在或是空的）」）。門房（`aos-team ask`）與公司總機都照這條。用途：「補人物 X」寫死「讀 aos-drafts/X/ 的草稿」，草稿不在時寫手照樣從原文寫、總裁卻在結案信說「依草稿寫成」。

`handoff` 的 `done_when` 裡有 `cmd_ok`、又用了 `{群組}`（例 `lore/characters/{name}.md`）時，`team.json` 白名單那條要寫 `"pattern": true`、同一個位置寫 `{name}`（[wall.md §4](wall.md)）；寫死人名的白名單只對那幾個人能開單，換個人郵差就 `NotAllowed` 退件（09-25 市場真跑 §7 第 4 條）。

## 例句：全過才准存

每條規則要有 `tests.hit`（至少一句）與 `tests.miss`（至少一句）：

- `hit` 的每一句：**整個門房**的判決要是「這一條」（不能因為命中兩條、有否定詞而落穿）。
- `miss` 的每一句：不能命中這一條。

`aos-team route test [--file F]` 全跑、逐條印 PASS／FAIL，全過退 0（沒給 `--file`＝測 `team/routes.json`，不在＝`NotFound`）；`aos-team route save F` 先跑同一套，全過才原子地換成 `team/routes.json`。
（第二波 A 隊）`aos-team route try "一句話" [--file F]`：拿一句話試，印判決（命中哪條、抓到的群組、`tool` 會跑的完整指令、`handoff` 會派給誰與目標、落穿的原因與哪位領隊）＋「只是試，什麼都沒做」；不跑工具、不開單、不寄信、不寫 `route.log`；規則檔例句沒全過時多印一行提醒（真的 `ask` 會退 1）。退 0；`--file` 給的檔不在＝`NotFound`，沒給話＝用法錯。
人直接用文字編輯器改 `routes.json` 也行：`aos-team ask` 每次都先跑一遍例句，**沒全過就退 1（`RoutesFailed`）、叫你跑 `route test`**，不會拿壞規則去判。
