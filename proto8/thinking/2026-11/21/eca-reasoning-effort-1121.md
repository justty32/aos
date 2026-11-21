eca 跟上今天的改動：思考程度 `reasoning_effort` 接成 claude 的 `--effort`、pi 的 `--thinking`；另外比照 agent-fsm 縮預設工具包、替 eca-claude 接上壓縮前後的 hook 點，並列出今天其他改動 eca 吃到了沒（線 `top-1121-ecaeffort`）。

← [2026-11-21](README.md)｜前情：[llm-effort-1121](llm-effort-1121.md)（agent-fsm／llm kernel 那邊怎麼做）、[tool-desc-瘦身-1121](tool-desc-瘦身-1121/README.md)、[compact-改進規劃-1121](compact-改進規劃-1121/README.md)｜說明：[templates/docs/01「思考程度」](../../../templates/docs/01-eca-claude.md)

線 `top-1121-ecaeffort`，11-21 家機（claude 2.1.330、pi 1.5.2）。

## 使用者原話（逐字）

- 「啊對了，eca也都有跟上嗎？reasoning eff那些」
- 頂層回報 eca 沒跟上思考程度、問要不要派線「先查兩支 CLI 怎麼調思考程度，查得到對應的參數就接上，查不到的那支就回報」，他答：「去」。
- 加碼（頂層轉逐字）：「能做的先做，盡量做。compact的機制不管，但可以試試看提供相應的hook點」

## 兩支 CLI 怎麼調思考程度（以實物與官方文件為準）

| | claude（Claude Code 2.1.330） | pi（1.5.2） |
|---|---|---|
| 起動旗標 | `--effort <level>`：「Effort level for the current session (low, medium, high, xhigh, max)」（`claude --help`） | `--thinking <level>`：「Set thinking level: off, minimal, low, medium, high, xhigh, max」（`pi --help`） |
| 級別 | `low`、`medium`、`high`、`xhigh`、`max`；模型不支援的級別往下退到它有的最高一級（[model-config](https://code.claude.com/docs/en/model-config)「Unsupported levels」） | `off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`；「clamped to the model's capabilities」（pi 套件的 `docs/cli.md`）；`get_available_thinking_levels` 這台 claude-opus-5-5 回 `low`～`max` |
| 其他管道 | 環境變數 `CLAUDE_CODE_EFFORT_LEVEL`（優先序最高，`auto`／`unset`＝不送）、互動中 `/effort`、設定檔 `effortLevel`／`modelSettings`（都不收 `max`）；優先序：環境變數 ＞ 畫面裡選的 ＞ `--effort` ＞ 設定檔 ＞ 模型預設（同一頁） | 互動中 `/thinking`（`docs/slash-commands.md`）、rpc 指令 `set_thinking_level`（`docs/rpc-commands.md`）、設定 `defaultThinkingLevel`、`modelThinkingLevels`（`docs/settings.md`）、`--model 名:級別` 尾碼 |
| 不認得的值（實測） | `--effort none`／`bogus`：stderr 一行「Warning: Unknown --effort value 'none' — ignoring it and using the default effort. Valid values: low, medium, high, xhigh, max.」，照跑（測時 `ANTHROPIC_BASE_URL` 指到不通的埠，沒打到 API） | `--thinking none`／`bogus`：stderr「Warning: Invalid thinking level」，`get_state` 的 `thinkingLevel` 是預設（這台 `high`）；`--offline --no-session`，沒叫模型 |
| 跟對話的關係 | `-p` 每輪是新行程；程度不記在對話裡 | 「A session records model and thinking-level changes. Resuming the session restores them」（`docs/models.md`）；原始碼 `dist/main.js`：有給 `--thinking` 就蓋過對話記的，沒給就照對話記的 |

codex（0.170.0）的 `codex exec --help` 沒有程度旗標，這次沒查它的設定檔寫法、沒接。

## 做法（第 1 筆：思考程度）

- `py/aos/agentlib/cli_cfg.py`：每輪讀 `llm.json`（定義疊 stack）時，`reasoning_effort` 補成 claude 的 `--effort`、pi 的 `--thinking`（`cli.json` 的 flags 已寫同一個旗標就換掉它的值，`--旗標=值` 的寫法也換）；值不是非空字串、不是那支 CLI 收的級別、或 kind 是 codex＝`CfgBad`（在認領信之前就停、信留在 queue）。錯誤句列出那支 CLI 收哪些級別。
- 三份範本（eca-claude、eca-pi、start-eca 的 ann）的 `interfaces.json`：`llm_keys` 加 `reasoning_effort`，`aos-agent llm set reasoning_effort=high` 不再跳警告；`agent.py` 編譯 eca 版照夾裡的 `llm_keys` 驗，`agent_spec_parts.LLM_KEYS` 本來就有這個鍵（`b20abe44b`）。
- `/status` 有設時多寫 `reasoning_effort X`。
- `aos-agent llm set --help` 加一行例子；說明、知識庫（`aos/me/self_llm.json`、`aos/cli/eca.json` 的 turn 與 pi）、三份 README、`templates/docs/01`、`03`、`py/docs/05-commands/05`、`apps/agent/README` 跟著改。

### 怎麼用

```sh
aos-agent llm --target myproj set reasoning_effort=high     # 下一輪起 claude 帶 --effort high（pi 帶 --thinking high）
aos-agent llm --target myproj ls -l                          # reasoning_effort=high  agent
aos-agent llm --target myproj rm reasoning_effort            # 回定義的值；範本沒寫＝CLI 自己的預設
aos-json set --str <定義>/llm.json#/reasoning_effort medium   # 改定義那份
```

### 什麼時候生效

- **沒開畫面**：下一輪（每輪重讀 `llm.json`、重起 CLI）。
- **畫面開著**：畫面帶的是開畫面那一刻的旗標，改了要 `aos-agent close` 再 `open` 才換；或在畫面裡打 CLI 自己的 `/effort high`（claude）、`/thinking`（pi），那只算那個畫面，aos 不知道、`llm ls` 也看不到。
- **pi 拿掉之後**：同一段對話照用上次記的程度（pi 自己記在對話檔），開新對話（`/clear`）才回 pi 的預設。claude 拿掉就回預設。

## 替使用者做的選擇（第 1 筆）

1. **級別名對不上時：只收那支 CLI 認得的名字，其他＝`CfgBad`**（不原樣照傳、不在 eca 這層對照轉換）。理由：兩支 CLI 遇到不認得的值都只印 warning、改用預設照跑（實測），原樣照傳＝寫錯了也看不出來；對照表（例 llm kernel 的 `none` 轉 pi 的 `off`）是替你定義兩邊名字的對應，`low`～`max` 三邊本來就同名，只差 `none`／`off`／`minimal`，少到不值得藏一層轉換。代價：寫錯會讓那隻停下（跟 `model` 寫成空字串一樣），`llm set` 改對或 `llm rm` 後再起。
2. **`CfgBad` 在每輪讀設定時擋，`aos-agent llm set` 當下不擋**：`aos-agent` 不認身體（值一律字串、照存），跟 agent-fsm 的程度由 llm kernel 擋同一個位置（問的那一刻）。
3. **codex 寫了＝`CfgBad`**，不靜靜忽略；沒查它的設定寫法。
4. **畫面開著時不替你打 `/effort` 進畫面**：畫面是人在看的，aos 主動改它的設定要另外設計；寫明「關掉重開才換」。
5. 範本的 `llm.json` 不寫程度（照 CLI 的預設），跟 agent-fsm 範本一樣。

## 測試（第 1 筆）

`git archive HEAD`（87ad225a5）兩份乾淨複本 `~/.aos/scratch/top-1121-ecaeffort/{base,mine}`，各自 `install.py`，清掉 `AOS_*` 後 unittest 逐夾：`py/tests` 746 → 754（新 `test_cli_reasoning_effort.py` 8 支）；`py/tests/apps/eca` 227 → 229（`test_pi` 加 pi 帶 `--thinking`、壞級別在認領前就停；`test_slash` 加 claude 每輪帶 `--effort`、stack 那份下一輪蓋過、`/status` 寫出來），兩邊都是同樣 4 支紅（`test_switch.TtySocket`，暫存路徑太長，原本就紅）；`apps/agent` 226、`apps/hook` 20、`templates/tests` 30、`defs` 28、`agent_def` 32、`self_hook` 6 兩邊都過。

## 第 2 筆：預設工具包比照 agent-fsm、系統提示寫知識庫在哪

使用者 11-21 對 agent-fsm 選了「只留一兩句＋指去知識庫」與「self 只留兩支」（[tool-desc-瘦身 04](tool-desc-瘦身-1121/04-使用者已答.md)）。工具說明是同一份 `_tooldef.json`，eca 已經吃到短說明；沒跟上的是下面兩件：

- 三份範本（eca-claude、eca-pi、start-eca 的 ann）的 `tools.json` 同樣寫 `"self_llm": null, "self_system": null, "self_history": null, "self_ctl": null`：34 → 30 支。aos-mcp 真的回給 CLI 的 `tools/list` 從 44,316 → 40,778 bytes（−8%；乾淨複本實量）。子 agent 那份 `tools_sub.json` 本來就沒有 self 工具（9 支、5,176 bytes），沒動。
- 三份範本新加 `system.txt`（兩段：自己是 aos agent、知識庫在 `$AOS_HOME/knowledge/` 要先 `echo $AOS_HOME` 取全路徑、`More: aos/...` 指的就是那裡）。eca 的 `interfaces.json` 本來就宣告 `system`、只是範本沒有這個檔；有了它 claude 多帶 `--append-system-prompt-file`（接在 Claude Code 自己的系統提示後面）、pi 多帶 `--append-system-prompt`。
- 知識庫 `aos/packs.json`（eca 30 支、比照關掉哪四支）、`aos/definition.json`（system.txt 那句）、`templates/docs/01`、`03`、三份 README 跟著改；`py/tests/agent_spec_helpers.py` 的 eca 版 agent.py 例子一起關掉那四支（`test_eca_templates` 比對編譯結果跟範本一樣）。

### 替使用者做的選擇（第 2 筆）

6. **eca 也關掉同樣四支 self 工具**（self_llm、self_system、self_history、self_ctl）：你選的是 agent-fsm 範本的預設，這裡照同一句話套到 eca。要用的時候 `self_tools add` 加回（self_tools 的說明寫了怎麼加）。eca 的 CLI 自己也有 `/model`、`/effort`、`/compact` 這類指令，但那是 CLI 畫面裡人打的，腦叫不到，所以不構成「CLI 有同名機制、不必比照」。
7. **新加 `system.txt`**：比照 agent-fsm 那句「知識庫在哪」。只寫兩段，不搬 agent-fsm system.txt 其他段（回信格式、只做被交代的事…）：那些 Claude Code、pi 自己的系統提示都有對應的規矩，疊上去可能打架。
8. **eca 才掛的四包沒瘦**（events、def、jsonx 與子 agent 用的 subagent 不在 eca）：瘦身線當時寫明「不在這次範圍」，寫新說明要照五條規矩逐支過、`self_hook` 的說明還被 `test_hook_points_match` 逐欄比對，不是比照就能做完的事。現在多大見下面對照表。

### 測試（第 2 筆）

同一份 `mine` 複本疊上第 2 筆：`py/tests` 754 兩邊一樣（第一次跑 `test_agent_spec_script.NoFsm.test_eca_templates` 兩支紅，是測試裡的 eca agent.py 例子還沒關那四支；改 `agent_spec_helpers.py` 後過），`apps/eca` 229（同樣 4 支 TtySocket 紅）、`apps/agent` 226、`apps/hook` 20、`templates/tests` 30（含 `test_start`：start-eca 的 ann 跟 eca-claude 逐字相同）、`defs` 28、`agent_def` 32、`self_hook` 6 都過。

## 第 3 筆：壓縮前後的 hook 點（eca-claude）

使用者：「compact的機制不管，但可以試試看提供相應的hook點」。壓縮是 Claude Code 自己的；這筆只把它給的 hook 時刻接成 aos 的點，名字跟 agent-fsm 規劃的（[compact-改進規劃 03](compact-改進規劃-1121/03-壓完補回走hook.md)）一樣，欄位照 CLI 給得出來的。

### Claude Code 給什麼（[hooks 文件](https://code.claude.com/docs/en/hooks) 的 PreCompact、PostCompact、SessionStart 三節）

- `PreCompact`：輸入 `trigger`（`manual`／`auto`）、`custom_instructions`（/compact 後面的字，沒有＝null）；退 2 或 `"decision": "block"`＝不壓；退 0 時 stdout 當摘要的指示。
- `PostCompact`：輸入 `trigger`、`compact_summary`；「no decision control. They can't affect the compaction result」。
- `SessionStart`（matcher `compact`）：stdout 進壓縮後的 context。
- 沒有讓 hook 直接給摘要的口子。

### 做成什麼樣

| Claude Code 的 hook | aos 的點 | 欄位 | hook 能做什麼 |
|---|---|---|---|
| `PreCompact` | `before_compact` | `trigger`、`asked`、`instructions`（起始＝範本那段「要留什麼」）、`restore`（null） | 改 `instructions`、交 `restore`、退 10 攔下 |
| `PostCompact` | `after_compact` | `trigger`、`summary` | 只告知 |
| `SessionStart` compact | （不發） | | 印提醒、`handoff.md`、`restore`（印一次就刪） |

- 宣告加在 `py/aos/apps/eca/hook_points.json`（provider `eca`，照現行格式；使用者今天定了新格式，換格式時一起換）。eca 三種身體都宣告了這兩個點，但只有 claude 身、`cli.json` 掛了 `compact_hook` 的才發，pi、codex 不發（`when` 寫明）。
- `templates/eca-claude/compact_hook`（start-eca 的 ann 同一份）經 `$AOS_HOME/bin/aos-hook fire --agent $AOS_CLI_DEF --stack $AOS_STACK` 發；`cli.json` 多掛 `PostCompact`，三個 hook 的 `timeout` 10 → 60 秒。少環境變數、`aos-hook` 起不來或報錯＝一行 warning、照沒有 hook 的樣子做。
- 手抄的清單跟著補：`self_hook` 的說明與 enum、知識庫 `aos/me/self_hook.json`、`aos/cli/eca.json`、`aos-agent hook --help`、`apps/agent/docs/06-hook.md` 的 eca 表、三份範本 `hooks.json` 的 description、`templates/docs/01`（新一節「壓縮前後的 hook 點」）、兩份 README、`apps/eca/README`。
- `test_hook_points_match`：原本「兩種身體的點一模一樣」改成「eca 多這兩個、agent-fsm 少這兩個」；gdb 的「before 點都要能扣住」排除 `before_compact`（它在 Claude Code 的 hook 裡跑、有 60 秒上限，gdb 對它用暫停，不扣住）。`test_cli_settings` 允許範本多 `PostCompact`。新測試 `templates/tests/test_eca_compact_hook.py` 4 支。

### 實跑（暫存，真的叫 Claude Code，haiku）

`~/.aos/scratch/top-1121-ecaeffort/trees/t1`：定義＝改後的 eca-claude（`llm.json` 寫 `{"model": "haiku", "reasoning_effort": "low"}`），掛一支測試 handler：`before_compact` 在指示後面加「keep the word PINEAPPLE-7」、交 `restore`「RESTORE-MARK-42…」，有 `block` 檔就退 10。直接跑 `aos-eca-turn --on-empty idle`（沒起 daemon）。

| 輪 | 送的 | 結果 |
|---|---|---|
| 1 | Reply with exactly: OK-1 | 答 OK-1；Claude Code 的對話檔記 `"effort":"low"`、`"perTurnEffort":"low"`（`--effort` 有送到） |
| 2 | /compact keep the reply OK-1 | `before_compact`、`after_compact` 都發了（`asked`＝keep the reply OK-1、`summary` 是摘要全文）；摘要開頭就是 PINEAPPLE-7（改過的指示有效）；history 換成摘要 |
| 3、4 | OK-2，再 /compact | 第一版把 `restore` 放在 `after_compact`，結果補回的字沒進對話：對話檔裡 `SessionStart` compact 03:11:15.057 先跑、`PostCompact` 那次的檔 15.111 才寫。改成 `before_compact` 交之後，第 4 輪 `SessionStart` 的輸出帶了 RESTORE-MARK-42、小格的檔印完刪掉 |
| 5 | 不用工具，context 裡有沒有 RESTORE-MARK 的數字 | 答 42（補回的字腦看得到） |
| 6 | /compact（`block` 在） | 答「Compaction blocked by PreCompact hook: … compact blocked by hook t_before_compact: not now, test block」；退 0、沒冷卻、沒 CliFailed，history 沒被換 |

真模型這輪 5 次（1、2、3、4 的壓縮、5；第 6 輪被攔、沒叫模型），都是 haiku、`low`。沒實跑：畫面開著時在畫面裡壓、自動壓縮、`/compact` 以外的 `manual`。

### 能做到多深、卡在哪

- 使用者對 agent-fsm 的 hook 深度答「都開」（調、補、換）。eca 這邊：**調**＝改 `instructions`（做到）；**補**＝`restore`（做到，但只能在壓之前交，見上）；**攔**（做到）；**換**＝hook 直接給摘要，Claude Code 沒有這個口子，做不到（要做得自己攔下再用 `aos-agent history` 改，那就不是 Claude Code 的壓縮了，沒做）。
- **pi**：有對應的外掛事件——`session_before_compact`（可 `cancel`、可直接給一份摘要 `compaction.summary`）、`session_compact`（帶摘要）、`session_compact_failed`（pi 套件 `docs/extensions.md`）。接法會是在 aos 每輪生成的那支一行外掛 `pi-aos-mcp.mjs`（與畫面的 `pi_aos_screen.mjs`）裡掛這兩個事件、用 `spawnSync` 叫 `aos-hook`。這次沒做：pi 的事件沒有「改指示」的口子（`customInstructions` 是讀的），能做的是攔與給摘要，欄位跟 claude 這邊不一樣；假 pi（`fake_pi`）不跑外掛，要測得叫真模型；而且 hook 點格式馬上要換。要做的話是下一刀。

### 替使用者做的選擇（第 3 筆）

9. **兩個點宣告在 eca 共用的 `hook_points.json`**，不另開一份只給 eca-claude 的：`self_hook` 的事件清單從 aos 自帶的提供者算，另開一份腦就掛不上去。代價：eca-pi 的定義也「宣告」了這兩個點但永遠不發（`when` 與 eca-pi 的 hooks.json 說明都寫了）。
10. **`restore` 放在 `before_compact`**，`after_compact` 只告知：照實測的先後（上面第 3、4 輪）。跟 agent-fsm 規劃稿（`restore` 在 `after_compact`）不一樣，之後要共用時得對齊。
11. **欄位名**：`instructions`、`restore`、`summary` 跟規劃稿同名；`trigger`、`asked` 是 eca 才有的（規劃稿的 `instructions` 是 /compact 後面的字，這裡那個叫 `asked`，因為使用者打的字 Claude Code 自己會用、aos 拿不掉，hook 能改的只有 compact_hook 加給它的那段）。`letters`、`mid_turn`、`foldable`、`clear`、`mode`、`by`、`replaced`、`cleared` 這些 Claude Code 給不出來，沒有。
12. **三個 hook 的 timeout 10 → 60 秒**：要給 handler 跑的時間；Claude Code 等的就是這麼久。
13. **攔下 `/compact` 那封信照一般回答收**：沒在 aos-eca-turn 加特別處理（沒改它的行為），回答是 Claude Code 自己那句。

### 測試（第 3 筆與全套）

`mine3`＝`git archive` 9aab22baf 疊上第 2、3 筆，各自 `install.py`、清掉 `AOS_*`：相關夾 `py/tests` 754、`apps/eca` 229（同樣 4 支 TtySocket 紅）、`apps/agent` 226、`apps/hook` 20、`apps/mcp` 17、`templates/tests` 30 → 34（新 `test_eca_compact_hook` 4 支）、`defs` 28、`agent_def` 32、`self_hook` 6 都過。

**交件前全套一輪**（unittest 逐夾，基準 `base`＝87ad225a5 原樣，對 `mine3`）：全部 3,140 → 3,154 支（+14：第 1 筆 10、第 3 筆 4），沒有新的紅。兩邊一樣紅的：`apps/eca` 4 支（TtySocket）、`apps/feedback` 1 支，`templates/tests/image-move-check`、`templates/kernel/tests` 不是 unittest（0 支、退 5），都是原本就這樣、複本環境的關係。

## 今天其他改動 eca 吃到了沒（查實；第 2、3 筆之外只查、沒動手）

| 今天的改動 | eca | 說明 |
|---|---|---|
| 思考程度 `reasoning_effort` | 本線接上（第 1 筆） | claude `--effort`、pi `--thinking` |
| `aos-hook fire` 與 loop 的四個點（after_start、after_stop、before_run、after_run） | 有 | 三份 eca 範本的 `loop.json` 四個都經 `aos-hook fire -q --agent`（`test_hook_points_match` 的 `test_templates_wire_*` 守著）；eca 的 before_run／after_run 沒有 `stage`／`next_stage` |
| `aos-agent` 省略 `-t`／`-d` | 有（同一支 `aos-agent`） | 沒 eca 特有的差別。CLI 的 Bash 在工作區跑：stack 是 `<工作區>/.stack` 時 `./.stack` 認得；掛 daemon 的 eca 的 stack 在 daemon 的 `procs/` 底下，CLI 裡打 `aos-agent` 仍要 `-t` 或 `AOS_AGENT`（沒有程式會自動設它）。沒實跑 |
| `aos-agent history -n K` | 有（通用） | 照 `interfaces.json` 的 `history` 找檔。腦用的 `self_history` 第 2 筆起預設關，要用先 `self_tools add` |
| 工具說明瘦身 | 大半有 | 說明是共用的 `_tooldef.json`，eca 已吃到短說明；self 四支第 2 筆比照關掉。**eca 才掛的三包沒瘦**：aos-mcp 給 CLI 的 30 支 40,778 bytes 裡，`self_hook` 約 6.9 KB、`clock_register` 2.8 KB、`agent_def` 3.1 KB、`tools_def` 3.4 KB、jsonx 八支合計約 11.7 KB，約佔七成。claude 有自己的前綴快取，第二輪起便宜，但每段新對話、每次壓縮後照付。要不要瘦、要不要比照 agent-fsm 把 events／def／jsonx 改成選掛，是你的決定 |
| compact 先清工具輸出（第 1 刀） | 不適用 | eca 的壓縮是 CLI 自己做的（Claude Code 文件說它自己也會先清舊的工具結果），aos 不碰；第 3 筆只加 hook 點 |
| `session_key`（llm kernel 的快取鍵） | 不適用 | eca 的腦不經 llm kernel；`AOS_LLM_KERNEL` 只轉給 aos 工具（aos-mcp 底下要問腦的工具）用。快取是 CLI 自己的 |

## 收尾

- 三筆 commit：第 1 筆 `9aab22baf`（思考程度）、第 2 筆 `661801492`（工具包與 system.txt）、第 3 筆見 git log（壓縮 hook 點）。
- 進度條 `llm-effort` 還開著（等使用者點頭更新 `~/aos-home`），沒劃掉；第 3 筆交件時在它的 `what`、`next`、`see` 補上 eca 這條線與 eca 定義夾要換的檔。
- 暫存：`~/.aos/scratch/top-1121-ecaeffort/`（`base`、`mine`、`mine3` 三份複本、`trees/t1` 實跑那隻、`rel-*.txt`、`suite-*.txt` 測試結果）；沒起 daemon，實跑的 `aos-eca-turn` 與 claude 都是跑完就退，收尾 `pgrep` 沒有殘留。
- 沒在 repo 跑 `install.py`、沒碰 `~/aos-home`、沒改 `~/.claude*`（Claude Code 照常把實跑的對話記在使用者帳號的 projects 夾）。
- **要吃到**：repo 跑 `python3 install.py`（`cli_cfg.py`、`hook_points.json`、self_hook 說明在 `lib/`）；`~/aos-home` 裡的 eca 定義夾是範本的抄本，要另外換上新的 `interfaces.json`（`llm_keys`）、`tools.json`、`system.txt`、`cli.json`（PostCompact）、`compact_hook`。
