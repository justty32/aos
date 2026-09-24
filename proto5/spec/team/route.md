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
   "handoff": {"assignee": "worker-1", "workflow": "IMPORT.md", "goal": "把 workflows 導入 {project}",
               "facts": "{facts}", "done_when": [{"kind": "check", "name": "wf_residue"}]},
   "tests": {"hit": ["把 workflows 導入 p，照 facts.json"], "miss": ["把 workflows 導入 p"]}}]}
```

## 規則

- `pattern`：Python 正規式，跟**整句**比（`fullmatch`，前後空白先去掉）。不是找關鍵字。
- 具名群組（`(?P<名>…)`）都要有值才算命中；`handoff` 裡字串的 `{名}` 換成群組的值（只換名字對得上的）。
- **命中兩條以上**或**句子含否定詞**（`negations`，沒寫用上面那六個）＝不自己做、**落穿給領隊**（「不要導入 heartbeat」不能觸發導入）。
- 沒命中＝落穿：原話當一封 `REQUEST` 從 `human` 寄給領隊（名冊第一個 `template: lead` 的成員；沒有領隊＝退 1、說清楚）。
- 每次結果記一行進 `team/route.log`：`{"at", "text", "result": "tool"|"handoff"|"lead", "route": 名或 null, "why"}`。

## `do` 三種

| `do` | 欄位 | 做什麼 |
|---|---|---|
| `tool` | `run`：aos-team 子命令與參數（例 `["task", "ls"]`、`["wait", "ls"]`） | 在同一個行程跑那個子命令，輸出原樣印給人；**不寫任何成員的 `input/`** |
| `tool` | `tool`：`"<包>/<工具>"`（`proto5/tools/<包>/<包>.json` 裡的一支）、`args`：物件 | 照工具檔的 `_meta.argv` 跑那支程式，stdin 給 `args`、`AOS_TOOL_ROOT`＝專案資料夾、cwd＝團隊資料夾、60 秒逾時；輸出原樣印。只跑 `proto5/tools/` 裡的包（人自己寫進 routes.json 的） |
| `handoff` | `handoff`：同 handoff 申請的欄位（mail.md） | 往 `team/outbox/human/` 放一份 handoff 申請（開單人是 human）；郵差開單、派出 |

## 例句：全過才准存

每條規則要有 `tests.hit`（至少一句）與 `tests.miss`（至少一句）：

- `hit` 的每一句：**整個門房**的判決要是「這一條」（不能因為命中兩條、有否定詞而落穿）。
- `miss` 的每一句：不能命中這一條。

`aos-team route test [--file F]` 全跑、逐條印 PASS／FAIL，全過退 0；`aos-team route save F` 先跑同一套，全過才原子地換成 `team/routes.json`。
人直接用文字編輯器改 `routes.json` 也行：`aos-team ask` 每次都先跑一遍例句，**沒全過就退 1、叫你跑 `route test`**，不會拿壞規則去判。
