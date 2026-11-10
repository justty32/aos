← [回入口 README.md](../README.md)｜段落：hook（11-10 晚）｜上一份：[05-gitignore指南](05-gitignore指南.md)

# hook：事件發生時，跑你指定的 aos 函數

**一句話**：在 agent 身上掛「某件事發生時跑這支」——信要進對話、工具要跑／跑完、腦叫失敗、多了工具；被跑的那支從 stdin 收到一份事件 JSON，想的話還能改掉或攔下那件事。

使用者 11-10 晚：「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。」設計在 [圖紙](../../../thinking/2026-11/10/self-family/hook/01-圖紙.md)；讀清單、挑、跑、解回話全在 [lib/agent/hooks.py](../../../lib/agent/hooks.py)，四個格、aos-eca-turn、aos-mcp、`aos-agent hook` 共用它。

## 事件

| 事件 | 什麼時候（agent-fsm） | 事件 JSON 多的欄位 | `match` 比什麼 | 能改 |
|---|---|---|---|---|
| `queue_before` | idle：信從 queue 拿出來、進 history 之前 | `letter`、`content` | 不收 match | 改 `content`、丟掉這封 |
| `queue_after` | idle：信進 history 之後 | `letter`、`content` | 不收 match | 不能 |
| `tool_before` | act：工具要跑之前 | `name`、`id`、`arguments`（解開的 JSON） | 工具名 | 改 `arguments`、攔下不跑 |
| `tool_after` | act：工具跑完、結果進 history 之前（被攔下的不觸發） | 上面三個＋`content`、`code`（逾時＝null）、`timed_out` | 工具名 | 改 `content` |
| `brain_failed` | wait：`BrainFailed`／`SendFailed`／`ReplyBad` 那一刻 | `name`（代號）、`reason` | 代號 | 不能 |
| `tool_added` | think：工具清單多了名字（一個名字一次；第一次只記不觸發） | `name`、`path` | 工具名 | 不能 |

每份事件 JSON 都有 `event`、`hook`（這個 hook 的名字）、`stack`（agent 的 stack 絕對路徑）。同一事件多個 hook＝照名字排序一個一個跑，前一個改過的後一個看得到，被攔下就不往下。連鎖（hook 寄信給自己又觸發）不檢測，自行承擔。

## 回話協定

只有設了 `change: true` 的 hook 才看它的回話；沒設＝純通知，stdout 丟掉。

| 結束碼 | 意思 |
|---|---|
| 0 | 放行。`change` 而且 stdout 非空＝stdout 是一個 JSON 物件，認得的鍵（`content`／`arguments`）拿來改；stdout 空＝不改 |
| 10 | 攔下（`queue_before`＝這封信收掉；`tool_before`＝工具不跑，腦看到的結果＝hook 的 stdout，空就給 `(tool NAME blocked by hook HOOK)`）；別的事件的 10＝當 0 |
| 其他、逾時、起不來、該是 JSON 卻不是 | hook 自己失敗：`on_fail` 決定 |

## 選項

| 鍵（`add` 的旗標） | 意思 | 預設 |
|---|---|---|
| `on`（`--on`） | 事件名，必填 | — |
| `exec`（XXX 或 `--path-json`） | 目標：aos-exec 跑得動的東西（工具夾、JSON、執行檔）；相對路徑從寫它的那份檔的資料夾算 | — |
| `match`（`--match`，可重複） | 只在工具名／代號完全相等時跑 | 全部 |
| `change`（`--change`） | 看不看它的回話 | false |
| `wait`（`--no-wait`＝false） | 等不等它跑完；不等的＝放出去不管、不能配 `change` | true |
| `on_fail`（`--on-fail`） | `stop`＝那格印 `agent-fsm: error: HookFailed …`、agent 停下等人；`continue`＝一行 warning、當沒這個 hook | stop |
| `timeout_ms`（`--timeout-ms`） | 等它的上限，到了整群收掉、算失敗 | 60000 |

不能改的事件（`queue_after`、`brain_failed`、`tool_added`）寫 `--change`、`--change` 配 `--no-wait`、queue 事件給 `--match`＝`add` 直接 `ArgumentsBad`（由 `hooks.validate_entry` 說原因）。

## 兩份檔怎麼疊

- **宣告**：定義的 `interfaces.json` 寫 `{"aos-agent": {"hooks": "hooks.json"}}`。沒宣告＝這隻沒有 hook（`aos-agent hook` 說 `HooksMissing`）。
- **定義那份** `<定義>/hooks.json`、**這隻自己那份** `<stack>/hooks.json`，形狀一樣：`{"hooks": {"名字": {格} 或 null}}`。讀法＝定義那份疊上自己那份：同名的蓋過去、`null`＝關掉定義裡那一個。
- `aos-agent hook` **只寫自己那份**（先寫暫存再改名），定義不動；每次事件都重讀，改了下一個事件就生效。改定義＝直接編 `<定義>/hooks.json`。

## 指令

```
aos-agent hook -t bob                       # = ls：NAME TAB EVENT TAB EXEC
aos-agent hook -t bob ls -l                 # 多 MATCH WAIT ON_FAIL CHANGE TIMEOUT_MS FROM，也列被設成 null 的
aos-agent hook -t bob ls --json             # 一個 JSON 陣列（補完預設、帶 name 與 from）
aos-agent hook -t bob get guard             # 一格的 JSON
aos-agent hook -t bob add --on tool_before --match agents --change hooks/guard
aos-agent hook -t bob add --on brain_failed --on-fail continue --no-wait -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob rm guard              # 定義裡有的＝寫 null；自己加的＝刪掉那格
aos-agent hook -t bob reset -y              # 刪自己那份，回到定義的
```

- 名字預設＝XXX 的檔名／夾名；`--path-json` 時一定要 `--name`。名字不能空、不能有 `/`、不能 `.` 開頭（`NameBad`）。
- XXX 相對目前資料夾、不存在＝`PathMissing`；存法：絕對存絕對、相對存成「相對 stack 那份檔的資料夾」。
- 同名已在生效清單裡＝`HookExists`（加 `--replace`）；`rm`／`get` 沒這個名字＝`HookMissing`；清單壞＝`HooksBad`。
- agent 自己改用工具 [self_hook](../../../lib/agent/self_hook/_entry)（`aos-agent hook --target 自己` 的純包裝）。

## 最小 hook 範例

擋掉腦叫 `agents` 工具時 `op` 是 `new` 的呼叫（生新 agent）（`add --on tool_before --match agents --change hooks/no_spawn`）：

```python
#!/usr/bin/env python3
# no_spawn - tool_before hook: block agents {"op": "new"}
import json, sys
ev = json.load(sys.stdin)
if isinstance(ev["arguments"], dict) and ev["arguments"].get("op") == "new":
    print("spawning is turned off by hook %s" % ev["hook"])   # what the brain sees as the tool result
    sys.exit(10)
sys.exit(0)                                                  # empty stdout = no change
```

只想記一筆、不改什麼的（不設 `change`）：

```sh
#!/bin/sh
# log_letters - queue_after hook: append each letter to a log
cat >> "$HOME/letters.jsonl"
```

## eca（縮水版）

eca 的腦是外面的 CLI，aos 只看得到經過自己手的東西（圖紙 § 6）：

| 事件 | eca | 在哪 |
|---|---|---|
| `queue_before`／`queue_after` | 有 | aos-eca-turn 讀信、交給 CLI 之前／信接進 history 之後 |
| `tool_before`／`tool_after` | 只有經 aos-mcp 叫的 aos 工具 | aos-mcp 的 tools/call |
| `brain_failed` | 有（`name`＝`CliFailed`／`ReplyMissing`） | aos-eca-turn |
| `tool_added` | 有（看 aos 登記檔的名單） | aos-eca-turn 每輪開頭 |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos |
