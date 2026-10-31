← [入口](../proto8.md)｜涵蓋：外部 coding agent（eca，claude／codex 當平級 agent）的一輪 `proto8/bin/aos-eca-turn`（10-30 是 `proto8/lib/eca/turn` 格，10-31 改名＋升 bin）、範本 `proto8/demo/eca-*` 與它們的測試，10-30｜同層：[09-lib](09-lib.md)（`lib/agent/cli_session.py` 在那裡）、[12-agent-round](12-agent-round.md)（aos agent 的格）

> 設計：[thinking 2026-10-30 eca](../../../../../proto8/thinking/2026-10-30-eca.md) B 結論 2、實作第 4 步；條文草稿 P-43。

| 哪裡 | 負責什麼 |
|---|---|
| `bin/aos-eca-turn` | 10-31 改名＋升 bin（使用者「aos eca turn」，C-54 R13；`git mv` 自 `lib/eca/turn/turn.py`，`lib/eca/turn/_entry` 與 `lib/eca/` 整層刪了；+x、python3 shebang；`aos_flags.parse` 解旗標，從 `../lib/agent/` import `cli_session`）。外部 agent 的一輪：`aos-eca-turn [--one] [--on-empty stop\|idle] [--on-busy yield\|answer] <定義資料夾絕對路徑>`；`queue/cur/` 有信先接（`current.txt` 列過＝user 已在 history），否則 `aos-post claim` 一封（history 空＋queue 空＋定義有 `prompt.txt`＝先投開場白）；body 不是 `{"role": "user", "content": 非空字串}`＝壞信丟掉、trace 記 `letter_warning`；user 接進 history → `cli_session.ask` 的兩條路問 CLI（小格 `$AOS_STACK/<kind>/`，畫面開著貼字、沒開 `-p --resume`）→ assistant 接進 history → `aos-post finish`、清 `current.txt`；trace 一行 `{"unit": "aos-eca-turn", "question", "code", …}`（10-30 是 `"turn"`）；`--on-busy yield`（沒給）＝`SessionBad` 退 0 信留 `cur/`、不寫 trace，`answer`＝不退讓（`ask`／`live` 的 `on_busy` 照傳）；queue 空照 `--on-empty`（取代 `ECA_ON_EMPTY`，不再讀）stop（沒給）退 10／idle 退 0，壞值或跟 `--one` 一起＝`ArgumentsBad`（10-30 的 `SettingBad` 拿掉）；`eca.json`（kind、ws、template）；`--one`＝工具形，`cli_session.call_main(定義資料夾, on_busy)`；錯 `aos-eca-turn: 代號 原因` |

範本（第 5 步；說明在 [demo/README](../../../../../proto8/demo/README.md) 的「外部 coding agent 範本」）：

| 哪裡 | 負責什麼 |
|---|---|
| `demo/eca-claude/`、`demo/eca-codex/` | `_entry`＝`["aos-loop", "loop.json"]`（JSON、不給 +x）；`loop.json`＝停著等版（10-31 起 `["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}]`、`timeout_ms` 900000、`interval_ms` 300、ctl／state 窗、沒有 max；aos-daemon-ctl 的 pin_cd 照樣換 `$env AOS_CD`）；`parts.json` 10-31 刪了（10-30 是一格 turn → `../../lib/eca/turn`、env `ECA_ON_EMPTY` idle）；`cli.json` 抄 `lib/agent/claude`／`codex` 的保守旗標 |

測試：

| 哪裡 | 負責什麼 |
|---|---|
| `tests/test_eca_turn.py` | 10-31 起測 `bin/aos-eca-turn`（加 `--on-empty`／`--on-busy` 的案：stop／idle／壞值／跟 `--one` 一起、`ECA_ON_EMPTY` 設了沒作用、`--on-busy` 壞值；`answer` 時 lock 被拿著＝等放開後答、`busy.txt` 在＝等它消失再答〔真 tmux＋假 claude，沒 tmux skip〕、有人接在畫面上＝照樣答〔pty attach，沒 tmux skip〕）。借 test_fay 的假 claude／codex（`FAKE_TRANSCRIPTS` 寫假對話檔）、aos-say 投信：say 一封 turn 一次＝history 兩則、信不見、trace、eca.json、transcripts symlink、第二封 `--resume`；codex；`cur/` 列過的先接、沒列的補接、答完沒收的只收信；四種壞信；queue 空 stop／idle（10-30 是 `ECA_ON_EMPTY`＋`SettingBad`）；`prompt.txt` 開場白只投一次；lock 被拿著＝SessionBad 退 0、放開再答；CLI 失敗退 1、trace 有 error、信留 `cur/`；`AgentBad`、`CfgMissing`；`--one` 進出與錯誤開頭；10-30 11 個，10-31 加 6 個共 17 個 |
| `tests/test_eca.py` | 範本：形狀（_entry 一行 argv 不給 +x、loop.json 停著等版、cli.json kind；10-30 還驗 parts.json 一格 turn idle，10-31 改成叫 `bin/aos-eca-turn` 與 `--on-empty`）；射後不理（複本改 stop）claude、codex 各 say → aos-exec 收工退 0 → listen 拿到回答、state `done`、transcripts symlink、工作區不長東西；範本本身背景跑：答兩句同一段對話、ctl paused 後第三句留 new/、`--status` 印 paused、恢復後答、stopped 退 0；3 個 |
