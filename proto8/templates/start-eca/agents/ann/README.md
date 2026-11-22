Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.

用 `cp -r $AOS_HOME/templates/eca-claude <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`；要真的 `claude` 指令在 PATH 上），再修改 `cli.json`（怎麼叫 CLI）、`llm.json`（`model`、思考程度 `reasoning_effort`）與 `tools.json`，即可建立另一隻外部 coding agent；各檔的用途、實例＝定義 × 工作區、畫面與完整用法見 [eca-claude 說明](../docs/01-eca-claude.md)。

`_entry` 起 `aos-loop`，`loop.json` 每格叫 `aos-eca-turn`：從 stack 的 `queue/` 認領一批、交給 claude CLI，回答接進 `history.jsonl`；queue 空就退 0、隔 300 毫秒再來。`screen/` 是給 `aos-agent open／close／watch` 的畫面子介面。

**五包、共 18 支（11-22 起拿掉 events、def、jsonx 三包共 12 支，使用者 11-22「是，就是這個。」；要用時 `self_tools add` 加回，例如 `{"op":"add","path_json":{"$env":"AOS_HOME","$path":"/lib/tools/agent/self_hook"}}`）（self 包比照 agent-fsm 只開 self_tools、self_state，11-21）；檔案與指令交給 CLI 自己的工具**（[thinking 11-12 eca-file-tools](../../thinking/2026-11/12/eca-file-tools.md)）：`tools.json` 的 `"$override"` 疊三包 agent 工具（[py/packs](../../py/packs/README.md)：gadgets〔peek_clock、peek_now_time、math；do_task 只給 agent-fsm，寫 `"do_task": null`〕、self、mailbox）與 json 包（json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set；[json-tools](../../thinking/2026-11/12/json-tools/01-規劃.md) D20）（jsonx 包〔認 `$ref`／`$env` 的 jsonx_* 八支〕使用者 11-13「eca-1:A*」掛上、11-22 拿掉；子 agent 的 `tools_sub.json` 本來就不掛）、index 包（index_view；[index-tools](../../thinking/2026-11/12/index-tools/README.md)），`tools` 裡關掉 `do_task` 與 self_llm、self_system、self_history、self_ctl 四格（比照 agent-fsm，使用者 11-21 對 agent-fsm 選「self 只留兩支」；要用 `self_tools add` 加回），經 aos-mcp 給 CLI（工具名 `mcp__aos__peek_now_time`…）。**比 agent-fsm 少通用四包（look、change、delete〔含 trash〕、shell）與 subagent、goal、todo 三包**：11-11 晚使用者「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」、11-12「eca這塊，放寬claude，codex拿掉唯讀沙盒。」「可以先定這樣，然後trash也拿掉。」；11-11 晚「subagent相關的工具都還是別給eca吧，eca本身就有他自己的了，甚至更順手。」「eca基本都有goal，所以goal不用給eca。todo也不用。」（人下的 `aos-agent goal --target <eca>` 與 aos-eca-turn 丟提醒那段照留，是隊長代定，見 [playground 04](../../thinking/2026-11/11/playground/04-修與第二輪實測.md)；def 包〔agent_def、tools_def〕當時也留著，11-22 拿掉）。所以 `cli.json` 開 claude 內建的 `Read,Write,Edit,Glob,Grep,Bash`（另加 `Agent,Skill`，見下段），`--permission-mode dontAsk` 加 `--allowedTools Read,Glob,Grep,Write,Edit,Bash`（這六支不問就准、不限工作區，其他沒准的照 dontAsk 拒絕；不加全繞過權限的旗標）。codex 版把 `cli.json` 換成 `kind: codex`、`-c sandbox_mode="workspace-write" -c approval_policy="never"`（codex 用自己的指令在工作區讀寫；寫法見 [eca-claude 說明](../docs/01-eca-claude.md)）。關一包＝從那串拿掉那一項；只關一支用 `aos-agent tools rm math`。

**子 agent 與 skill（[thinking eca-task-subagent](../../thinking/2026-11/12/eca-task-subagent.md)）**：使用者「claude code cli自己本身有Task工具，可以的話幫我加入claude eca範本和定義中(Skill也加上)」「將aos mcp切成幾個，一個是給主agent用的，另一個是比較少功能的，給子agent用的」。`cli.json` 的 `--tools` 多 `Agent`（子 agent；舊名 `Task` 還認）與 `Skill`，dontAsk 下不用另外列進 `--allowedTools`。`cli.json` 的 `"tools_sub": "tools_sub.json"`＝**子 agent 那台**：claude 的子 agent 預設會繼承主對話全部 MCP 工具（含 `mcp__aos__*` 18 支），寫了這格就改成——內建的 `general-purpose` 子 agent 看不到 `mcp__aos__*`，改拿另一隻 aos-mcp 接 `tools_sub.json` 的 `mcp__aos_sub__*`（代定只放不改東西的九支：peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_len、json_multi_get、index_view）；主對話看不到 `aos_sub`；其他類型的子 agent（Explore、Plan、外掛或你自己定義的）還看得到 `mcp__aos__*`，但一叫就被擋（回一句說明）。要子 agent 多一支＝改 `tools_sub.json`（格式同 `tools.json`）；不要切＝拿掉 `tools_sub` 那格（子 agent 照 CLI 預設繼承全部）；不要子 agent 或 skill＝從 `--tools` 拿掉 `Agent`／`Skill`。skill 是 claude 自己找的：工作區的 `.claude/skills/`、你帳號的 `~/.claude/skills/` 與外掛。codex 身不認 `tools_sub`（寫了＝`CfgBad`）。

**範本關掉的 skill（11-22）**：`cli.json` 的 `settings.skillOverrides` 關掉 claude.ai 帳號同步來的 `anthropic-skills:chrome-browser`、`docx`、`pptx`、`xlsx` 四支（使用者 11-22「啊對，外掛和skills也交給他，請他調查，這個我確實也想要拿掉」），每次呼叫約少 1.2k token；只影響這份定義的 eca。要用回來刪掉那一格。細節見 [eca-claude 說明](../docs/01-eca-claude.md)。

**權限與擋 CLI 自己的工具**（[thinking 11-13 ops-agent-six-suggestions](../../thinking/2026-11/13/ops-agent-six-suggestions.md) 第 1 點）：範本是 `--permission-mode dontAsk` 加 `--allowedTools Read,Glob,Grep,Write,Edit,Bash`——Bash、Write、Edit **沒有任何人按確認**，全面開放；Read、Glob、Grep 也在白名單上，工作區外的路徑一樣讀得到（使用者 11-21 夜）。aos 的 hook（`hookeds.json` 的 `before_tool`／`after_tool`）只看得到 aos 自己的工具，看不到 CLI 自己的。**要擋 CLI 自己的工具，用 CLI 自己的 hook**：aos 起的 claude 照讀工作區的 `.claude/settings.json`（[P-43](../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md)「照吃、不隔離」），它的 hook 跟 aos 加的並存。給腦看的完整說明在知識庫 `aos/cli/eca.md#/Guarding the CLI's own tools (claude)`（[knowledge/aos/cli/eca.md](../../knowledge/aos/cli/eca.md)）。範本本身不帶任何這種 hook；下面是想擋的人可以照抄的最小例子（11-13 實測過：claude 2.1.323、haiku）。

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

**只想管這隻 agent、不想放工作區**：把同樣的設定寫進這份定義的 `cli.json`，鍵叫 `settings`（物件，或一個 JSON 檔的路徑；11-13 實測過兩條路都擋得住）。aos 把它併進自己加的那個 `--settings`，hook 指令用 `$AOS_CLI_DEF`（這份定義資料夾）找檔：

```json
"settings": {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 \"$AOS_CLI_DEF/host_gate.py\""}]}]}}
```

`flags` 裡不要自己寫 `--settings`（＝`CfgBad`）。細節在 [eca-claude 說明](../docs/01-eca-claude.md)。

**接外部 MCP server**：`cli.json` 加 `"mcp_servers": ["mcp/<名>.json"]`，一台一份 server 檔（http 或 stdio），寫法見 [eca-claude 說明的「接外部 MCP server」](../docs/01-eca-claude.md#接外部-mcp-server11-12-external-mcp)；token 放 server 檔的 `env_file`，不要用 `ctl add --envs`。

`interfaces.json` 宣告畫面、工具、腦設定、history 與 hook 的位置。`_metainfo.json` 宣告估時 `cost.time_ms`（一輪約一分鐘，粗估）與 `llm` 資源，未設定逾時（一輪的上限在 `cli.json` 的 `timeout_ms` 與 `loop.json` 的 `timeout_ms`，範本兩個都是 0＝不限時，11-15 起；一輪很久沒動靜只寫 `$AOS_STACK/quiet.json` 標記、不殺）。


**沒開畫面時中途收信（`live_mail`，預設關）**（[wake-1114](../../thinking/2026-11/14/wake-1114.md)）：`cli.json` 寫 `"live_mail": true`，沒開畫面時 claude 照樣一輪一個 `claude -p`，但 stdin 改用 stream-json、先不關：這一輪還在跑時 queue 又來的信，一封一行寫進去，模型在下一個工具空檔就讀到（不用等整輪講完），回答併進這一輪那一則。一輪最多中途投 5 封、起來 300 秒後不再投，用 `"live_mail_cap": {"letters": N, "seconds": N}` 改；剩的留給下一輪。冷卻剛到期那一輪不投。正在跑的前景指令要等它做完，長指令請讓 CLI 用背景跑。畫面開著時照舊走收件 socket；codex 不走這條。

**畫面延後關**：`screen_linger_start` 是第一格 after_start hook，撤掉舊到期單；`screen_linger_stop` 在 after_stop 排關畫面（兩格 timeout_ms=4000；handler 退 1＝loop 停，跟別的 loop 點 hook 一樣）。定義 cli.json 的 `screen_close_after_s` 非負整數秒，預設 600，0 當場關；停下時讀一次，已排的不因改設定而變。有人正在看也照關，start／wake 撤單；兩格在 stack 的 hookeds.json 設 null＝不自動關。依本機 state.json／proc 身分保護新 loop，不需要 daemon；SIGKILL／OOM 或停著才開畫面沒有 after_stop，第一批沒有後援。`aos-agent ctl stop` 不當場關畫面，全靠這兩格；stack 複本把兩格設 null（或缺了）＝停下後畫面一直開著，要關就 `aos-agent close`。

**hook 預設**（[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)）：`loop.json` 的 `on_start`／`on_stop` 叫 `aos-hook fire -q --stop-on-nonzero --def $AOS_CD` 發 `after_start`／`after_stop`（handler 的碼原樣交給 aos-loop，非 0＝agent 停）；`before_run`／`after_run`（每一輪前後）預設不接；`hookeds.json`（被勾清單；`interfaces.json` 最外層 `"hookeds"` 指它，`"hooks"` 指 aos 帶的三份宣告，只是參考）帶一格 `timer`（`on_clock`、每 300000 ms、handler `py/tools/agent/hook_noop` 什麼都不做；每次起來、睡醒會先跑一次，之後每 5 分鐘）；另一格 `mail_notify`（`on_clock`、每 60000 ms＝每 1 分鐘、handler `py/tools/agent/mail_notify`：看自己的信箱，有沒通知過的新信才往 `queue/` 寄一則 `[aos] new_mail: N new letters from A, B. …`、多封合成一句、沒新信不動 history；睡醒時照已通知記錄比：睡前提醒過的不再提、睡著時新到的提醒一次；全新起來（沒有 `notified.json`，且 agent stack 的 `history.jsonl` 不在或是空的）時在等的只記成已知；跑過的 stack（有非空 history）當睡醒，在等的提醒一次；使用者「用on_clock」「預設開」「合成一句」，[mail-notify](../../thinking/2026-11/11/mail-notify.md)；間隔與起來那次：使用者「每 1 分鐘」「只提醒新到的」「睡著時新到的要提」，[backlog-rulings](../../thinking/2026-11/11/backlog-rulings.md)），history 不多任何一則。要定時叫醒腦＝同名換成往 `queue/` 寄信的 handler；不要＝`aos-agent hook -t 名 rm timer`。用法 [aos-agent docs/06](../../py/aos/apps/agent/docs/06-hook.md)。

**快滿了先收尾再 compact（`context_wrap`，預設開，門檻 35%）**（使用者 11-15：「最好弄個hook，當context到達一定程度的時候跟agent說整理收尾，然後跑compact。」「3.我們做通用的aos判斷，eca的話可以在這個基礎上接上claude hook。」「門檻用35%」）：`hookeds.json` 的 `context_wrap` 格（`on_clock`、每 5000 ms、handler `py/tools/agent/context_wrap`）讀 `aos.agentlib.context_use`（`py/aos/agentlib/context_use.py`）給的用量（最後答完那輪、最後一次呼叫的三種 input token 加總 ÷ context 視窗；claude 身從小格的 `live.jsonl` 讀，讀不到的腦就不動）。到門檻：先往 `queue/` 寄一封 `[aos] context_wrap: … Wrap up now …`（叫它把手上的事與還開著的事寫進交接，沒有交接檔就寫 `<stack>/handoff.md`，寫完回一句 wrap-up done）；這封答完、queue 也空了，再寄一封只有 `/compact` 的信（aos-eca-turn 讓 `/compact` 那封一定自己一批）；壓完要等到後面某輪的讀數低於門檻才會再看。狀態在 `<stack>/hookeds/context_wrap/state.json`。改門檻＝改這格的 `config.percent`（或在 stack 那份 `hookeds.json` 寫同名格蓋過；`self_hook add` 帶 `config` 加 `replace: true` 也行，self_hook 不在範本工具裡、先 `self_tools add` 加回）；不要＝`aos-agent hook -t 名 rm context_wrap`。範本另附 `compact_hook`（Claude Code 自己的 hook 用）：`PreCompact` 印摘要要留什麼、`SessionStart`（matcher `compact`）壓完提醒讀回交接、有 `$AOS_STACK/handoff.md` 就附上；自動壓縮也會跑到它們。**11-21 起它也發 aos 的兩個 hook 點**（使用者「compact的機制不管，但可以試試看提供相應的hook點」）：`PreCompact` 時發 `before_compact`（能改給 CLI 的摘要指示 `instructions`、交一段壓完要接進對話的 `restore`、退 10 攔下不壓），`PostCompact` 時發 `after_compact`（只告知，帶 Claude Code 寫好的 `summary`）；壓縮本身還是 Claude Code 的，細節見 [templates/docs/01「壓縮前後的 hook 點」](../docs/01-eca-claude.md)。範本的 `cli.json` 預設就帶這三個 hook（使用者 11-15「1.開。」；11-13 起範本不帶權限之類的 CLI 設定，壓縮前後的 hook 是唯一例外，測試 `test_shipped_templates_carry_only_compact_hooks` 守著），內容是：

```json
"settings": {"hooks": {"PreCompact": [{"hooks": [{"type": "command", "command": "python3 \"$AOS_CLI_DEF/compact_hook\" pre", "timeout": 60}]}],
                       "PostCompact": [{"hooks": [{"type": "command", "command": "python3 \"$AOS_CLI_DEF/compact_hook\" post", "timeout": 60}]}],
                       "SessionStart": [{"matcher": "compact", "hooks": [{"type": "command", "command": "python3 \"$AOS_CLI_DEF/compact_hook\" start", "timeout": 60}]}]}}
```

手動也可以：寄一封內容只有 `/compact`（或 `/compact 指示`）的信，例 `aos-agent say -t 名 /compact`。
