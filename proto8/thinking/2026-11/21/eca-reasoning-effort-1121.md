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
