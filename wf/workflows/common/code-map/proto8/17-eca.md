← [入口](../proto8.md)｜涵蓋：外部 coding agent（eca，claude／codex 當平級 agent）的格 `proto8/lib/eca/` 與它的測試，10-30｜同層：[09-lib](09-lib.md)（`lib/agent/cli_session.py` 在那裡）、[12-agent-round](12-agent-round.md)（aos agent 的格）

> 設計：[thinking 2026-10-30 eca](../../../../../proto8/thinking/2026-10-30-eca.md) B 結論 2、實作第 4 步；條文草稿 P-43。

| 哪裡 | 負責什麼 |
|---|---|
| `lib/eca/turn/_entry` | 一行 argv `["python3", "turn.py"]`（JSON 入口、不給 `+x`，同 agent-nia 的 `_entry`） |
| `lib/eca/turn/turn.py` | 外部 agent 的一輪：`aos-exec <turn> <定義資料夾絕對路徑>`；`queue/cur/` 有信先接（`current.txt` 列過＝user 已在 history），否則 `aos-post claim` 一封（history 空＋queue 空＋定義有 `prompt.txt`＝先投開場白）；body 不是 `{"role": "user", "content": 非空字串}`＝壞信丟掉、trace 記 `letter_warning`；user 接進 history → `cli_session` 的兩條路問 CLI（小格 `$AOS_STACK/<kind>/`，畫面開著貼字、沒開 `-p --resume`）→ assistant 接進 history → `aos-post finish`、清 `current.txt`；trace 一行 `{"unit": "turn", "question", "code", …}`；`SessionBad`＝退 0 信留 `cur/`、不寫 trace；queue 空照 `ECA_ON_EMPTY` stop 退 10／idle 退 0；`eca.json`（kind、ws、template）；`--one`＝工具形，直接 `cli_session.call_main(定義資料夾)` |

測試：

| 哪裡 | 負責什麼 |
|---|---|
| `tests/test_eca_turn.py` | 借 test_fay 的假 claude／codex（`FAKE_TRANSCRIPTS` 寫假對話檔）、aos-say 投信：say 一封 turn 一次＝history 兩則、信不見、trace、eca.json、transcripts symlink、第二封 `--resume`；codex；`cur/` 列過的先接、沒列的補接、答完沒收的只收信；四種壞信；queue 空 stop／idle、`SettingBad`；`prompt.txt` 開場白只投一次；lock 被拿著＝SessionBad 退 0、放開再答；CLI 失敗退 1、trace 有 error、信留 `cur/`；`AgentBad`、`CfgMissing`；`--one` 進出與錯誤開頭；11 個 |
