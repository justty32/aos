Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.

用 `cp -r $AOS_HOME/templates/eca-claude <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`；要真的 `claude` 指令在 PATH 上），再修改 `cli.json`（怎麼叫 CLI）、`llm.json`（`model`）與 `tools.json`，即可建立另一隻外部 coding agent；各檔的用途、實例＝定義 × 工作區、畫面與完整用法見 [eca-claude 說明](../docs/01-eca-claude.md)。

`_entry` 起 `aos-loop`，`loop.json` 每格叫 `aos-eca-turn`：從 stack 的 `queue/` 認領一批、交給 claude CLI，回答接進 `history.jsonl`；queue 空就退 0、隔 300 毫秒再來。`screen/` 是給 `aos-agent open／close／watch` 的畫面子介面。

**八包、共 34 支；檔案與指令交給 CLI 自己的工具**（[thinking 11-12 eca-file-tools](../../thinking/2026-11/12/eca-file-tools.md)）：`tools.json` 的 `"$override"` 疊五包 agent 工具（[lib/packs](../../lib/packs/README.md)：gadgets〔peek_clock、peek_now_time、math；do_task 只給 agent-fsm，寫 `"do_task": null`〕、events、self、def、mailbox）與 json 包（json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set；[json-tools](../../thinking/2026-11/12/json-tools/01-規劃.md) D20）、jsonx 包（複雜組 jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_get、jsonx_multi_set，認 `$ref`／`$env`；使用者 11-13「eca-1:A*」＝範本掛 jsonx；子 agent 的 `tools_sub.json` 不掛）、index 包（index_view；[index-tools](../../thinking/2026-11/12/index-tools/README.md)），`tools` 裡只剩 `do_task` 那格，經 aos-mcp 給 CLI（工具名 `mcp__aos__peek_now_time`…）。**比 agent-fsm 少通用四包（look、change、delete〔含 trash〕、shell）與 subagent、goal、todo 三包**：11-11 晚使用者「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」、11-12「eca這塊，放寬claude，codex拿掉唯讀沙盒。」「可以先定這樣，然後trash也拿掉。」；11-11 晚「subagent相關的工具都還是別給eca吧，eca本身就有他自己的了，甚至更順手。」「eca基本都有goal，所以goal不用給eca。todo也不用。」（def 包〔agent_def、tools_def〕留著、人下的 `aos-agent goal --target <eca>` 與 aos-eca-turn 丟提醒那段照留，是隊長代定，見 [playground 04](../../thinking/2026-11/11/playground/04-修與第二輪實測.md)）。所以 `cli.json` 開 claude 內建的 `Read,Write,Edit,Glob,Grep,Bash`（另加 `Agent,Skill`，見下段），`--permission-mode dontAsk` 加 `--allowedTools Write,Edit,Bash`（這三支不問就准，其他沒准的照 dontAsk 拒絕；不加全繞過權限的旗標）。codex 版把 `cli.json` 換成 `kind: codex`、`-c sandbox_mode="workspace-write" -c approval_policy="never"`（codex 用自己的指令在工作區讀寫；寫法見 [eca-claude 說明](../docs/01-eca-claude.md)）。關一包＝從那串拿掉那一項；只關一支用 `aos-agent tools rm math`。

**子 agent 與 skill（[thinking eca-task-subagent](../../thinking/2026-11/12/eca-task-subagent.md)）**：使用者「claude code cli自己本身有Task工具，可以的話幫我加入claude eca範本和定義中(Skill也加上)」「將aos mcp切成幾個，一個是給主agent用的，另一個是比較少功能的，給子agent用的」。`cli.json` 的 `--tools` 多 `Agent`（子 agent；舊名 `Task` 還認）與 `Skill`，dontAsk 下不用另外列進 `--allowedTools`。`cli.json` 的 `"tools_sub": "tools_sub.json"`＝**子 agent 那台**：claude 的子 agent 預設會繼承主對話全部 MCP 工具（含 `mcp__aos__*` 34 支），寫了這格就改成——內建的 `general-purpose` 子 agent 看不到 `mcp__aos__*`，改拿另一隻 aos-mcp 接 `tools_sub.json` 的 `mcp__aos_sub__*`（代定只放不改東西的九支：peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_len、json_multi_get、index_view）；主對話看不到 `aos_sub`；其他類型的子 agent（Explore、Plan、外掛或你自己定義的）還看得到 `mcp__aos__*`，但一叫就被擋（回一句說明）。要子 agent 多一支＝改 `tools_sub.json`（格式同 `tools.json`）；不要切＝拿掉 `tools_sub` 那格（子 agent 照 CLI 預設繼承全部）；不要子 agent 或 skill＝從 `--tools` 拿掉 `Agent`／`Skill`。skill 是 claude 自己找的：工作區的 `.claude/skills/`、你帳號的 `~/.claude/skills/` 與外掛。codex 身不認 `tools_sub`（寫了＝`CfgBad`）。

**權限與擋 CLI 自己的工具**（[thinking 11-13 ops-agent-six-suggestions](../../thinking/2026-11/13/ops-agent-six-suggestions.md) 第 1 點）：範本是 `--permission-mode dontAsk` 加 `--allowedTools Write,Edit,Bash`——Bash、Write、Edit **沒有任何人按確認**，全面開放。aos 的 hook（`hooks.json` 的 `before_tool`／`after_tool`）只看得到 aos 自己的工具，看不到 CLI 自己的。**要擋 CLI 自己的工具，用 CLI 自己的 hook**：aos 起的 claude 照讀工作區的 `.claude/settings.json`（[P-43](../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md)「照吃、不隔離」），它的 hook 跟 aos 加的並存。給腦看的完整說明在知識庫 `aos/cli/eca.json#/cli_hooks`（[knowledge/aos/cli/eca.json](../../knowledge/aos/cli/eca.json)）。範本本身不帶任何這種 hook；下面是想擋的人可以照抄的最小例子（11-13 實測過：claude 2.1.323、haiku）。

工作區 `.claude/settings.json`（路徑寫絕對路徑）：

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/path/to/ws/.claude/hooks/host_gate.py"}]}]}}
```

`.claude/hooks/host_gate.py`（指令裡有 ssh／docker 這類字、對象又在正式主機名單上，就要人在畫面上確認）：

```python
#!/usr/bin/env python3
# host_gate - PreToolUse hook for Bash: commands that touch a production host need a person's confirmation on the screen
import json, re, sys
PROD = ("prod-db", "prod-web", "10.0.0.")          # host names or address prefixes that count as production
d = json.load(sys.stdin)
cmd = (d.get("tool_input") or {}).get("command", "")
if re.search(r"\b(ssh|scp|rsync|docker)\b", cmd) and any(h in cmd for h in PROD):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
          "permissionDecisionReason": "this command touches a production host; a person must confirm on the screen"}}))
```

hook 什麼都不印＝照跑、不問人；印 `deny`＝不跑、腦收到理由；印 `ask`＝**畫面開著**（`aos-agent open`）時畫面上跳確認框等人按，畫面沒開（aos 走 `claude -p`）時等於拒絕。同一個檔裡寫權限規則（`permissions.ask`／`permissions.deny`）在 `dontAsk` 下只會拒絕、不跳框。管不到的：人在畫面上自己打的 `!` 指令（不叫 hook）、codex 身。這道閘擋得住「順手就做了」，擋不住存心繞過（腦有 Bash 與 Write，改得到這個檔）。規矩放工作區＝同一個資料夾的所有 Claude Code session 都吃到，包含人自己開的。

**接外部 MCP server**：`cli.json` 加 `"mcp_servers": ["mcp/<名>.json"]`，一台一份 server 檔（http 或 stdio），寫法見 [eca-claude 說明的「接外部 MCP server」](../docs/01-eca-claude.md#接外部-mcp-server11-12-external-mcp)；token 放 server 檔的 `env_file`，不要用 `ctl add --envs`。

`interfaces.json` 宣告畫面、工具、腦設定、history 與 hook 的位置。`_metainfo.json` 宣告估時 `cost.time_ms`（一輪約一分鐘，粗估）與 `llm` 資源，未設定逾時（一輪的上限在 `cli.json` 的 `timeout_ms` 與 `loop.json` 的 `timeout_ms`）。


**hook 預設**（[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)）：`loop.json` 的 `on_start`／`on_stop` 叫 `lib/agent/hook_fire` 發 `after_start`／`after_stop`；`hooks.json` 帶一格 `timer`（`on_clock`、每 300000 ms、handler `lib/agent/hook_noop` 什麼都不做；每次起來、睡醒會先跑一次，之後每 5 分鐘）；另一格 `mail_notify`（`on_clock`、每 60000 ms＝每 1 分鐘、handler `lib/agent/mail_notify`：看自己的信箱，有沒通知過的新信才往 `queue/` 寄一則 `[aos] new_mail: N new letters from A, B. …`、多封合成一句、沒新信不動 history；睡醒時照已通知記錄比：睡前提醒過的不再提、睡著時新到的提醒一次；全新起來（沒有記錄）時已經在等的不提醒；使用者「用on_clock」「預設開」「合成一句」，[mail-notify](../../thinking/2026-11/11/mail-notify.md)；間隔與起來那次：使用者「每 1 分鐘」「只提醒新到的」「睡著時新到的要提」，[backlog-rulings](../../thinking/2026-11/11/backlog-rulings.md)），history 不多任何一則。要定時叫醒腦＝同名換成往 `queue/` 寄信的 handler；不要＝`aos-agent hook -t 名 rm timer`。用法 [aos-agent docs/06](../../cmd/aos-agent/docs/06-hook.md)。
