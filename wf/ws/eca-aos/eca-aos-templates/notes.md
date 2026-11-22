eca-aos-templates（改 `proto8/templates/` 的 subagent）的筆記：使用者給這份工作的規矩，與做這份工作學到、下一個人該照做的事。

← [地盤](README.md)

## 使用者給的規矩

（使用者原話逐字；經 eca-aos 轉來的標「轉述」。）

- 2026-11-22（轉述，eca-aos 傳話）：「自動記憶那塊幫我清空，然後不理他，agent愛寫就寫，之後我們再想辦法解決這塊。」→ Claude Code 自動記憶不用特別避開，也不用特別寫；要留給下一個人的寫在這裡。
- 2026-11-22（轉述）：「install.py可以跑。」——講的是那一批的 py/tools 改動；當時 eca-aos 說由它跑。repo 裡的 install.py 還是照任務書：沒交代就不跑。

## 做這份工作學到的

- **乾淨複本要在複本裡跑 install.py**：`git archive` 抄出來的沒有 `proto8/lib/`（install 產生、gitignore），`aos-tools` 類測試會 `PathMissing …/lib/packs/…`。做法：unset 所有 `AOS_*`、在複本 `python3 install.py -j 8`、`PATH=$PWD/bin:$PATH`、再跑 unittest。只寫進複本自己的 bin/lib/include。
- **抄改過的檔進複本**：檔名有中文時 `git diff --name-only` 會加引號，用 `git -c core.quotepath=false diff --name-only -z HEAD | while IFS= read -r -d '' f; do cp …; done`。
- **範本之間有「要一樣」的測試**：`templates/tests/test_start.py` 要 `start-eca/agents/ann` 逐字等於 `eca-claude`（改 eca-claude 任何檔都要重抄 ann）；`test_eca_pi.py` 要 eca-pi 的 `tools.json` 等於 eca-claude 的。`py/tests/test_cli_settings.py` 限制範本 `cli.json` 的 `settings` 只能有哪些鍵。
- **量 claude 每次固定佔多少**：看 `claude -p … --output-format stream-json --verbose` 的 result `usage`（input＋cache_creation＋cache_read），不要看 `/context` 的分類表（skill 少了、System tools 會跟著變多，總數幾乎不動）。init 那則列 skills、plugins、agents、mcp_servers。
- **`--disable-slash-commands` 會讓 `claude -p "/compact"`、`/context` 回「isn't available」**：aos 交給 claude 的 `/compact`（context_wrap）、`/usage` 都靠它，別加（使用者 11-22 也裁不做）。
- **開互動 claude 驗畫面**：新資料夾會跳信任詢問（按了會寫 `~/.claude.json`），借已信任的暫存工作區；用私用 tmux socket（`tmux -L 名字`），看完 kill-session。
- **commit-request**：claim 過的檔交完會放，但 `wf/progress.json` 若 claim 了卻沒交到，要自己 `release --line 舊線名`，否則下一條線 claim 被擋。
- **eca 的 claude 與它的 hook 拿得到哪些環境變數**：`AOS_STACK`、`AOS_WS`、`AOS_PARENT_STACK`（subagent 才有值，指上層的 stack）、`AOS_CLI_DEF`、`AOS_HOME`…；在自己的 Bash 跑 `env | grep ^AOS_` 就看得到，不用碰 daemon。compact_hook 要知道「我是不是 subagent」就看 `AOS_PARENT_STACK`。
- **compact 之後**：repo 的 `wf/tools/compact_reload.sh` 會貼頂層的 `wf/HANDOFF.md`，那是 eca-aos 的、不是我的；我先讀這份 notes.md（見 [compact 後讀筆記的提案](notes-hook-提案.md)）。
