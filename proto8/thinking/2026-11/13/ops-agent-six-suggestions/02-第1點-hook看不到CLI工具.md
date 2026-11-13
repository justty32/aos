# 第 1 點：eca 的 hook 看不到 CLI 自己的工具——事實查核、實測、三種收法（11-13，只調查沒施工）

← [ops-agent-six-suggestions](../ops-agent-six-suggestions.md)｜上一份 [01-原信](01-原信.md)｜下一份 [03-第2到5點](03-第2到5點.md)

看的檔是 commit `2fb2c4b5e` 當下的；實測用 claude 2.1.323、模型 haiku，在 `~/code/ops-try-1113/cc/` 自己起的測試 session 上做，沒碰任何現有 session。

## 它說的事實對不對

| 它說的 | 對不對 | 證據 |
|---|---|---|
| eca 的 `before_tool`／`after_tool` 只管 aos 工具 | 對 | 讀碼：這兩個事件在 `aos-mcp` 裡跑（`lib/agent/cli_session.py` 檔頭「before_tool／after_tool 在 aos-mcp 跑」、`cmd/aos-eca/bin/aos-eca-turn` 說明 ⑪）；CLI 自己的工具不經 `aos-mcp` |
| 範本是 `dontAsk` 加 `--allowedTools` 放行 Bash | 對 | 讀檔：`templates/eca-claude/cli.json` 的 flags 是 `--permission-mode dontAsk --allowedTools Write,Edit,Bash`。ops-agent 自己那份更寬（`--tools default`，白名單多了 WebFetch、WebSearch 等） |
| 在 aos 底下 Bash 沒有任何人工確認 | 對 | 實測：非互動（`claude -p`）與畫面兩條路，Bash 指令都直接跑、沒有任何提問。旁證：我自己的測試 agent（haiku）收到「照 notes/patrol.md 巡檢」、找不到那個檔，就自己跑了 `find /` 掃整台機器約兩分鐘，沒有任何東西攔它（唯讀指令，我用 `aos-daemon-ctl shutdown` 收掉暫存樹才停） |
| 不知道 aos 起的 claude 會不會讀工作區的 `.claude/settings.json` | **會讀，hooks 會生效**（見下） | 條文早就寫了：[P-43](../../../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md)「eca 照吃工作區設定……`.claude/settings.json`（hooks、env）……照吃、不隔離」；這次實測確認。知識庫沒寫這句＝文件缺 |

## aos 起的 claude 現在實際帶哪些 hook（讀碼）

- **畫面那條路**（`lib/agent/cli_screen.py` `start`）：`--settings` 帶 `SessionStart`、`UserPromptSubmit`、`Stop` 三個（都叫 `cli_session.py hook claude <小格>`，用來跟上對話 id、記 `busy.txt`、收回答）；定義有 `tools_sub` 時再加一條 `PreToolUse`，matcher 只有 `mcp__aos__.*`（`lib/agent/cli_mcp.py` `guard_hooks`：子 agent 叫主 agent 那台 aos 工具就擋）。
- **非互動那條路**（`lib/agent/cli_print.py`）：只有上面那條 `PreToolUse` guard（有 `tools_sub` 才加），沒有另外三個。
- 兩條路都**沒有任何一條 hook 看得到 Bash、Write、Edit**。
- aos 沒有加 `--setting-sources`，所以使用者層（`~/.claude/settings.json`）、工作區層（`.claude/settings.json`、`.claude/settings.local.json`）照 CLI 預設全部載入。

## 實測結果（這次最要緊的一段）

旗標照範本抄：`--tools Read,Write,Edit,Glob,Grep,Bash,Agent,Skill --permission-mode dontAsk --allowedTools Write,Edit,Bash --strict-mcp-config`，再加一個跟 aos 的 guard 同形的 `--settings`。工作區的 `.claude/settings.json` 放一條 matcher `Bash` 的 `PreToolUse` hook，它把每次呼叫記進 log，指令含某個字就回 deny、含另一個字就回 ask。

| 情況 | 非互動（`claude -p`，畫面沒開時 aos 走這條） | 畫面（tmux 裡的互動 claude） |
|---|---|---|
| 工作區 `.claude/settings.json` 的 hook 有沒有被叫 | 有，三次都記到（log 裡 `permission_mode` 是 `dontAsk`） | 有（要先過「信任這個資料夾」那一關；現有的 eca 都過了） |
| 跟 `--settings` 並存 | 並存，兩邊的 hook 都算數 | 同左 |
| hook 沒意見的指令 | 直接跑，沒有提問 | 同左 |
| hook 回 **deny** | 沒跑；模型收到「PreToolUse:Bash hook error: 理由」 | 同左 |
| hook 回 **ask** | **沒跑、直接當拒絕**（沒有人可以問） | **畫面跳出確認框**「Hook PreToolUse:Bash requires confirmation…Do you want to proceed? 1. Yes 2. No」，等人按；我按 No，指令沒跑 |
| 工作區設定寫權限規則 `permissions.ask`（例 `Bash(ssh:*)`） | 沒跑，模型收到「session is in don't-ask mode」 | **也是直接拒絕、不跳框**（跟 hook 回 ask 不一樣） |
| 工作區設定寫 `permissions.deny` | 沒跑 | 沒跑 |
| 人在畫面上自己打 `! 指令` | 不適用 | **hook 完全沒被叫**（log 空的），指令照跑 |
| 命令列給兩個 `--settings` | **只有最後一個算數**，前一個整個不見 | 沒另測，同一支 CLI |

白話結論：

1. **「只教人用 CLI 自己的 hook」這條退路現在就走得通**，不用等 aos 改任何東西。
2. `dontAsk` 底下「問人」這件事只有一個做法會真的問到人：**hook 回 ask，而且畫面要開著**。畫面沒開（非互動）時 ask 等於拒絕。
3. 人親手在畫面上打的 `!` 指令不經過 hook——這跟 aos 自己的說法「人在畫面上打的不算」一致，硬閘只擋模型、不擋人。
4. **意外發現的坑**：`cli.json` 的 `flags` 如果自己寫了 `--settings`，會被 aos 接在後面的那個 `--settings` 整個蓋掉、沒有任何提醒（畫面那條路一定蓋；非互動那條路在有 `tools_sub` 時蓋）。`lib/agent/cli_cfg.py` 第 18 行的註解把 `--settings` 列在「可重複，不擋」，跟 CLI 實際行為不符。所以「在定義裡用 flags 帶 hook」這條路現在是斷的。

## 「硬」到什麼程度（先講清楚，免得期待錯）

不管哪種收法，這道閘擋得住的是「模型忘了規矩、順手就做了」，擋不住「模型存心繞過」：它手上有不受限的 Bash 和 Write，可以改 `.claude/settings.json`、可以用 `self_hook` 把定義的 hook 設成 null。要真的改不掉，只能放到它寫不到的地方（例如要 root 才能寫的 CLI 受管設定檔），那是機器管理層的事，不在 aos 範本的範圍。對 ops-agent 的需求（動正式主機前多一道人按的確認）來說，「擋住順手」已經是它要的。

## 分類

- **文件缺**：知識庫沒寫「要擋 CLI 自己的工具用 CLI 自己的 hook」、沒寫「工作區 `.claude/settings.json` 照讀」。條文 P-43 兩句都有，知識庫沒跟上。
- **bug（小）**：`cli.json` flags 裡的 `--settings` 被靜默蓋掉。
- **設計題（要使用者裁）**：要不要做「橋」。

## 文件怎麼改（純文件，可以馬上做）

正本在 `proto8/knowledge/aos/`；`~/aos-home/knowledge` 是複本，改完要重抄才到 ops-agent 手上。

1. `body.json#/brain_tools` 的 Hooks 那句，現在是：
   > eca: `before_tool` / `after_tool` only for aos tools; the CLI's own tools and what a person types on the screen are not seen. `on_clock` is checked at the start of each cell (agent-fsm) or of each turn (eca).

   改成（後半句的 on_clock 改法見[第 6 點](04-第6點-on_clock每天幾點.md)）：
   > eca: `before_tool` / `after_tool` only for aos tools; the CLI's own tools (Bash, Write, Edit ...) and what a person types on the screen are not seen. To check or block the CLI's own tools, use the CLI's own hooks: `aos/cli/eca.json#/cli_hooks`.

2. `cli/eca.json` 加一個 key `cli_hooks`（`_description` 末尾加一句指過去），內容：
   > # Guarding the CLI's own tools (claude)
   >
   > aos starts claude in your workspace without isolating it: `CLAUDE.md`, `.claude/settings.json`, `.claude/settings.local.json`, skills and commands there are read as in any Claude Code session, and their hooks run next to the ones aos adds. The stock template runs with `--permission-mode dontAsk` and Bash allowed: no command is ever confirmed by a person.
   >
   > To put a gate on Bash, add a `PreToolUse` hook with matcher `Bash` to the workspace `.claude/settings.json`. What its answer does:
   >
   > - `deny`: the command does not run; you get the reason.
   > - `ask`: with the screen open, a confirmation box appears on the screen and waits for a person; without a screen (aos runs `claude -p`), it counts as deny. So "ask the user first" needs the screen open.
   > - A permission rule (`permissions.ask` / `permissions.deny` in the same file) only refuses; it never shows a box in this mode.
   >
   > Not covered: commands a person types on the screen with `!`; codex. Do not put `--settings` in `cli.json` flags: aos adds its own `--settings` after it and only the last one counts. A settings change is picked up by the next CLI start (close and open the screen).

   （最後一句「下次起 CLI 才生效」是保守寫法：非互動每輪都是新行程一定生效；畫面上已開著的 session 會不會即時吃到新設定這次沒測。）

3. `templates/eca-claude/README.md` 權限那段加一句同樣的指路，附一份 10 行的 hook 範例（下面「現在就能用的避法」那份）。

## 現在就能用的避法（給 ops-agent）

工作區 `.claude/settings.json`（ops-notes 現在只有 `settings.local.json`，兩個檔都行；要進 git 給人看就用 `settings.json`）：

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/host_gate.py\""}]}]}}
```

`.claude/hooks/host_gate.py`（指令裡出現 ssh／docker 而且對象在正式主機名單上，就要人確認）：

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

`$CLAUDE_PROJECT_DIR` 這個寫法沒在這次實測裡用（我測的是寫死絕對路徑）；不確定就寫絕對路徑。行為照上表：畫面開著＝使用者在畫面上看到確認框；畫面沒開＝被拒絕，agent 應該回報「請開畫面」，不是換個寫法繞過去。子 agent 叫的 Bash 也會經過同一條 hook（hook 輸入帶 `agent_id`；這次只看到主對話的 `agent_id: null`，子 agent 那邊沒測）。

一個要先知道的邊緣狀況：畫面開著但沒人接著看的時候，確認框會一直等。aos 這邊等到 `cli.json` 的 `timeout_ms`（範本 10 分鐘）報 `ReplyMissing`（原因句已經寫了「may be stuck on a permission or trust prompt; attach to look」）、進冷卻，那封信算已收、不會自動重答（P-43「交給 CLI 就算完成」）。也就是說「等人確認」現在沒有通知使用者的管道，要靠人自己去看畫面。

## 要不要做「橋」：三種收法

| | 甲：不做橋，只補文件與範例 | 乙：讓定義帶 CLI 自己的設定 | 丙：做橋，接進 aos 的 `before_tool` |
|---|---|---|---|
| 怎麼做 | 上面三處文件；規矩寫在工作區 `.claude/settings.json` | `cli.json` 多一個選填 key（例 `settings`：一個物件或檔名），aos 把它的 hooks、permissions 併進自己那個 `--settings`；順手把 flags 裡寫 `--settings` 改成 `CfgBad`（現在是靜默蓋掉） | aos 在 `--settings` 多掛一條 `PreToolUse`（matcher 排掉 `mcp__aos`），叫一支新程式把 CLI 的 hook 輸入轉成 aos 的 `before_tool` 事件（`name`＝`Bash` 這類 CLI 工具名），跑 `lib/agent/hooks.py` 的 `fire`，再把結果翻回 CLI 的格式 |
| 規矩放哪 | 工作區（同一個資料夾的所有 session 都吃到，包含人自己開的 Claude Code） | 那隻 agent 的定義（跟著定義走，不影響同工作區的別人） | aos 的 `hooks.json`／`self_hook`（定義一層、stack 一層，agent 自己可以動態加減） |
| 「擋」的語意 | CLI 原生：deny／ask／allow | 同甲 | handler 退 10＝deny（stdout 當理由）；回 `{"arguments": …}`＝改參數；**aos 的 hook 回答裡沒有「問人」這一種，要新增**（例 `{"ask": "理由"}`）。畫面開著才問得到人，非互動＝拒絕 |
| `after_tool` | CLI 原生 PostToolUse | 同甲 | 接不完整：CLI 的 PostToolUse 改不了內建工具的結果，只能加註；`after_tool`「可改 content」對 CLI 工具做不到 |
| 人在畫面上打的 `!` | 不管 | 不管 | 不管（CLI 根本不叫 hook） |
| codex 身 | 不適用（另寫 codex 自己的設定） | 不適用 | 不適用（codex 沒有對應的 hook 點）→ 同一個 `before_tool` 在兩種身行為不一樣，文件要標 |
| 既有行為會不會變 | 不變 | 不變 | 會：現在沒寫 `condition` 的 `before_tool` hook 只收到 aos 工具，做了之後連 Bash、Read、Write 每一次都會叫到；每次工具呼叫多起一支 python（幾十毫秒） |
| 動哪些檔 | knowledge 兩份、範本 README | `lib/agent/cli_cfg.py`、`cli_screen.py`、`cli_print.py`、`cli_mcp.py`、測試、knowledge、`templates/docs/01`、P-43 一句 | `cli_mcp.py`、`cli_session.py`（新入口）、新檔 `cli_pretool.py`、`hooks.py`（事件表與 ask 回答）、`cli_screen.py`／`cli_print.py`、測試、knowledge `body.json`／`me/self_hook.json`、範本 `hooks.json` 說明、P-43 hook 那句 |
| 工作量 | 一人一兩個小時 | 一人半天 | 一隊一天到一天半 |
| 跟原則 | 最貼：P-43「eca 用自己的基礎工具，aos 只給專屬的——CLI 自己就有、而且更順手的不給」「eca 照吃工作區設定……全部都是自己要承擔的風險」；C-56 KISS（不養第二套做同一件事的機制） | 貼；順便修掉一個靜默失效 | 跟 P-43「它內部是黑盒子，aos 只碰它的 stack 三樣」有張力（aos 開始管 CLI 內部每一次工具呼叫）；兩套 hook 做同一件事（C-56）。好處是規矩一套寫法管兩種身、agent 可以用 `self_hook` 自己加 |

**寫手的建議：先做甲（馬上），乙排進施工（半天，順便修 bug），丙不做。** 理由：甲現在就能解 ops-agent 的痛點；乙補上「規矩要跟著 agent 定義走、不想汙染工作區」的缺口；丙要新增「問人」這種回答、改既有 hook 的涵蓋範圍、還只對 claude 身有效，換來的只是「寫法統一」，照 P-43 與 C-56 推不出要做。但 ops-agent 把這點列為最在意，要不要升到丙是方向題，留給使用者。

## 跟今天 a2a 裁定的連動

使用者 11-13 對 a2a 的裁定（[eca-a2a-notify](../eca-a2a-notify.md#要使用者裁的2-題)）：`say`／`chat` 進來的話被 CLI 當成「不是使用者打的、不可當成批准」，「真的有要的話，就自己open進去說」。這跟上面實測的結果是同一個方向、可以直接接上：

- hook 回 ask 的確認框**只出現在畫面上**，只有接上畫面的人按得到；`say`／`chat`、別的 agent 的信、a2a 訊息都按不到它。所以「動主機前先問使用者」落在「使用者本人 open 進去按 Yes」，正好是裁定那句話的做法。
- 反過來的後果也要認：使用者用 `aos-agent say` 遠端叫 ops-agent 動正式主機，在畫面沒開時會被拒絕；要嘛他 open 進去，要嘛那類指令就是做不了。這是裁定的本意，但對「人不在位子上、想用手機遠端下令」的情境是一個限制。
- a2a 施工後訊息「馬上送」進正在跑的那一輪；確認框等人的期間，新訊息會不會擠進來、框會不會被蓋掉，沒測，列進 a2a 那條線的冒煙測試比較合適。
