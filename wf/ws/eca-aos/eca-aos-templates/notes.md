eca-aos-templates（改 `proto8/templates/` 的 subagent）的筆記：使用者給這份工作的規矩，與做這份工作學到、下一個人該照做的事。

← [地盤](README.md)

## 使用者給的規矩

（使用者原話逐字；經 eca-aos 轉來的標「轉述」。）

- 2026-11-22（轉述，eca-aos 傳話）：「自動記憶那塊幫我清空，然後不理他，agent愛寫就寫，之後我們再想辦法解決這塊。」→ Claude Code 自動記憶不用特別避開，也不用特別寫；要留給下一個人的寫在這裡。
- 2026-11-22（轉述）：「我人還在外面玩，總之先按推薦做」→ [notes-hook 提案](notes-hook-提案.md)四題照推薦定：1＝A（stack 的 `notes_path`）、2＝只印路徑、3＝A＋b（b 是 `wf/tools/compact_reload.sh`，不歸我，eca-aos 另派）、4＝a（上層寫 `notes_path`；寫進地盤規矩也由那邊做）。`notes_path` 格式：一行、相對 `AOS_WS`，例 `wf/ws/eca-aos/<名>/notes.md`；要改格式先問 eca-aos。
- 2026-11-22（轉述）：「install.py可以跑。」——講的是那一批的 py/tools 改動；當時 eca-aos 說由它跑。repo 裡的 install.py 還是照任務書：沒交代就不跑。

## 做這份工作學到的

- **乾淨複本要在複本裡跑 install.py**：`git archive` 抄出來的沒有 `proto8/lib/`（install 產生、gitignore），`aos-tools` 類測試會 `PathMissing …/lib/packs/…`。做法：unset 所有 `AOS_*`、在複本 `python3 install.py -j 8`、`PATH=$PWD/bin:$PATH`、再跑 unittest。只寫進複本自己的 bin/lib/include。
- **抄改過的檔進複本**：檔名有中文時 `git diff --name-only` 會加引號，用 `git -c core.quotepath=false diff --name-only -z HEAD | while IFS= read -r -d '' f; do cp …; done`。
- **範本之間有「要一樣」的測試**：`templates/tests/test_start.py` 要 `start-eca/agents/ann` 逐字等於 `eca-claude`（改 eca-claude 任何檔都要重抄 ann）；`test_eca_pi.py` 要 eca-pi 的 `tools.json` 等於 eca-claude 的。`py/tests/test_cli_settings.py` 限制範本 `cli.json` 的 `settings` 只能有哪些鍵。
- **`daemon-sub` 要跟 `daemon-root` 一樣**（11-23 起，`templates/tests/test_daemon_sub.py`）：檔名一樣；`_entry` 的 argv、`daemon.json` 去掉 `_clock` 與說明句之後逐鍵一樣；`.env` 只設 `AOS_HOME=${AOS_HOME}`（跟 root 最後一行同）。改 daemon-root 的 `_sweeper`、`procs_requests`、`_entry` argv 要同步抄過去。
- **改 `daemon-root/README.md` 會連動起手範本**：`start-api/root`、`start-eca/root` 是 daemon-root 的逐字抄本（`test_start.py` 只放過 `.env`），README 改了要重抄兩份；那兩份在 `start-*/root/` 底下，README 裡寫 `../daemon-sub/` 這種相對連結抄過去會斷，指別的範本寫 `$AOS_HOME/templates/名`。
- **子 daemon 的環境**（11-23 在暫存樹實測）：上層傳下來的 `AOS_CLOCK`、`AOS_LLM_KERNEL` 贏過子定義 `.env` 的同名行，所以子 daemon 多帶 `_clock` 只會多寫一份自己 stack 的 `clock`、沒人讀；子項 stdout 接 `/dev/null`，`--enable-logs` 在子 daemon 看不到；子項不給 `-w` 就用它那台 daemon 的 ws；`aos-daemon-ctl -d <上層> stop <名>` 停子 daemon（底下全睡下、不被 auto_restart 拉起），`start` 後底下自己醒。不叫模型的探針：`{"exec": {"argv": ["bash", "-c", "…寫 $AOS_STACK/…"]}, "interval_ms": 2000}` 用 `aos-daemon-ctl add` 掛上，看它寫出的檔（只寫 `AOS_*` 變數名與要看的那個值）。
- **乾淨複本裡跑 `env.sh` 會先抱怨沒裝**（`aos-exec not installed yet`），照樣往下跑 install.py 就好；`templates/tests` 頂層 discover 約 5 分鐘（48 條，會起真 daemon），放背景跑；等它跑完別用 `while pgrep -f "<命令字串>"`，那個迴圈自己的命令列也含那串、會比到自己一直等下去。收尾 `pgrep -af aos-daemon` 多出來的先看 `ps -o ppid=` 與 `readlink /proc/<pid>/cwd`，活樹自己新掛的列（11-23 收尾時 `~/aos-home` 多了 `mine_paper`）不是你起的。
- **量 claude 每次固定佔多少**：看 `claude -p … --output-format stream-json --verbose` 的 result `usage`（input＋cache_creation＋cache_read），不要看 `/context` 的分類表（skill 少了、System tools 會跟著變多，總數幾乎不動）。init 那則列 skills、plugins、agents、mcp_servers。
- **`--disable-slash-commands` 會讓 `claude -p "/compact"`、`/context` 回「isn't available」**：aos 交給 claude 的 `/compact`（context_wrap）、`/usage` 都靠它，別加（使用者 11-22 也裁不做）。
- **開互動 claude 驗畫面**：新資料夾會跳信任詢問（按了會寫 `~/.claude.json`），借已信任的暫存工作區；用私用 tmux socket（`tmux -L 名字`），看完 kill-session。
- **commit-request**：claim 過的檔交完會放，但 `wf/progress.json` 若 claim 了卻沒交到，要自己 `release --line 舊線名`，否則下一條線 claim 被擋。
- **eca 的 claude 與它的 hook 拿得到哪些環境變數**：`AOS_STACK`、`AOS_WS`、`AOS_PARENT_STACK`（subagent 才有值，指上層的 stack）、`AOS_CLI_DEF`、`AOS_HOME`…；在自己的 Bash 跑 `env | grep ^AOS_` 就看得到，不用碰 daemon。compact_hook 要知道「我是不是 subagent」就看 `AOS_PARENT_STACK`。
- **compact 之後**：repo 的 `wf/tools/compact_reload.sh` 會貼頂層的 `wf/HANDOFF.md`，那是 eca-aos 的、不是我的；我先讀這份 notes.md（見 [compact 後讀筆記的提案](notes-hook-提案.md)）。
