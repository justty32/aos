# 01 一種 CLI 要當 eca，aos 需要它提供什麼（讀 repo 整理，11-18）

← [入口](README.md)｜下一份 [02-pi是什麼](02-pi是什麼.md)

**結論**：aos 這邊已經是「兩種身」的寫法——`cli.json` 的 `"kind"` 只認 `claude`、`codex`（`py/aos/agentlib/cli_cfg.py` 的 `load_cfg`），各處用 `if kind == "claude" … else …` 分岔。加第三種身＝把這些分岔點各補一支 pi 的。codex 當初就是這樣加的，是最好的範本；claude 身多出來的那幾樣（收件 socket、子 agent 那台、`settings`、暫時錯續做、中途收信）都是 claude 專屬，pi 第一版可以先不要。

讀的檔：`py/aos/apps/eca/`（README、`main_turn.py` 等）、`py/aos/agentlib/cli_session.py`（檔頭的總說明）、`cli_print.py`、`cli_screen.py`、`cli_hook.py`、`cli_cfg.py`、`cli_mcp.py`、`cli_cell.py`、`templates/eca-claude/`、`templates/docs/01-eca-claude.md`。

## aos 要 CLI 給的十件事

| # | 要什麼 | aos 現在怎麼用（claude／codex） | 在哪 |
|---|---|---|---|
| 1 | **一問一答地起** | claude＝`claude -p --output-format stream-json --verbose`；codex＝`codex exec … --json -o last.txt -`，題目從 stdin 進 | `cli_print.print_claude`／`print_codex` |
| 2 | **知道它答完、拿回答** | 一問一答：等行程結束，claude 取最後一行 `result`、codex 讀 `-o` 寫的檔 | 同上 |
| 3 | **續同一段對話** | claude：第一輪 aos 自己產 id 給 `--session-id`，之後 `--resume <id>`；codex：讀輸出的 `thread.started` 拿 id，之後 `exec resume <id>`。id 記在小格 `session.txt`，另記 `.session_home`（哪台機器、哪個工作區、哪個帳號資料夾） | `cli_cell.mark_session`、`session_here` |
| 4 | **找得到對話檔** | 小格 `transcripts/` 放 symlink 指到 CLI 自己存的檔（claude `~/.claude/projects/*/<id>.jsonl`、codex `~/.codex/sessions/**`）；「這段對話還在不在」也靠找檔 | `cli_cell.transcripts`、`link_transcript` |
| 5 | **互動畫面** | tmux 裡起互動 CLI；aos 往畫面送字＝`tmux paste-buffer`＋Enter；講完一輪靠 **CLI 的 hook 叫 `cli_session.py hook <kind> <小格>`**，hook 往 `turns.jsonl` 接一行回答（claude 用 `--settings` 掛 SessionStart／UserPromptSubmit／Stop；codex 用 `-c notify=…`） | `cli_screen._start`、`cli_hook.hook_main` |
| 6 | **權限不卡住** | claude＝`--permission-mode dontAsk`＋`--allowedTools Write,Edit,Bash`（白名單，其他照拒，不問人）；codex＝`approval_policy="never"`＋`sandbox_mode="workspace-write"` | 範本 `cli.json` |
| 7 | **接 aos 工具（MCP）** | 起 CLI 前接上 `aos-mcp`：claude 寫小格 `mcp.json`＋`--mcp-config`＋`--allowedTools mcp__aos`；codex 用 `-c mcp_servers.aos.*`、只對 aos 那台免核准 | `cli_mcp.mcp_argv` |
| 8 | **附加系統提示** | `interfaces.json` 宣告 `system`：claude＝`--append-system-prompt-file`＋`--system-prompt-snapshot off`；codex＝`-c developer_instructions` | `cli_cfg.system_argv` |
| 9 | **換模型** | `llm.json` 的 `model` 補成 `--model` | `cli_cfg` |
| 10 | **壓縮（compact）與 slash** | aos 寄 `/compact`、`/clear`：claude `-p` 認得 `/compact`；畫面上打的由 hook 跟上（claude SessionStart source clear／compact；codex 看 rollout 的 `compacted`）。aos 自己的 `context_wrap` hook 看用量、過門檻先叫收尾再寄 `/compact`——它要讀得到「上一輪 input token」 | `apps/eca/slash.py`、`cli_hook` |

另外兩件是好處、不是必要：**失敗分得出暫時或永久**（只有 claude 做了：`cli_fault.classify_claude` 讀 result 行，429／5xx 進 `retry.json` 冷卻續做；codex 一律 `CliFailed` 停下），與**回答途中收信**（claude 畫面走收件 socket、非互動走 `live_mail`＝stream-json stdin；codex 沒有）。

## 設定檔裡哪些是 claude 專屬

- `cli.json`：`settings`（Claude Code 的 settings 物件）、`tools_sub`（`--agents` 蓋掉 general-purpose 子 agent）、`live_mail`／`live_mail_cap`、`a2a`——四樣 codex 寫了就 `CfgBad` 或不理。`flags` 裡的 `--tools …`、`--permission-mode dontAsk`、`--allowedTools`、`--strict-mcp-config`、`print_flags` 的 `--max-budget-usd 0.5` 全是 claude 的旗標。
- `cli_cfg.AOS_FLAGS`（aos 自己加、你不准寫的旗標）是逐身一張表；pi 要有自己一張。
- 範本的 `compact_hook` 是 Claude Code 自己的 hook（PreCompact／SessionStart compact），pi 沒有這兩個名字。
- `hooks.json` 本身是 aos 的 hook，跟身體無關，大多照用；`brain_notify` 只認 claude 的失敗代號（codex 的被忽略）；`context_wrap` 要讀得到用量。
- `llm.json` 的 `"sonnet"` 是 claude 的模型別名。

## repo 裡以前怎麼想 codex 與別的 CLI

- 10-30 eca 設計時就是「範本 `eca-<CLI 名>`」，原本有 `eca-claude`、`eca-codex` 兩份；codex 範本 11-04 刪掉，只在 `templates/docs/01-eca-claude.md` 開頭留一份 codex 的 `cli.json`。pi 照這招可以不另開範本，只附一段 `cli.json`（或照使用者意思開 `eca-pi`）。
- `aos-mcp` 的 README 第一行就把 pi 寫成會叫 aos 工具的外部 agent 之一；10-24 照 pi 做過 read／bash／edit／write 四支工具（[pi-tools](../../../2026-10/24/pi-tools/README.md)），當時記的是「pi 不做 MCP、不擋權限」——**MCP 這點已經過時**（見 02）。
- 進度檔 `pi-coding-agent` 一條「範圍待確認」，頂層讀法是「做成 eca 的第三種身」。

## 加第三種身要碰的地方（粗估，照 codex 的分岔數）

`cli_cfg`（kind 名單、保留旗標、system 旗標）、`cli_print`（新的 `print_pi`）、`cli_cell`（帳號資料夾、對話檔在哪、認不認得這台）、`cli_mcp`（pi 怎麼接 aos-mcp）、`cli_screen`／`cli_hook`（畫面與 hook，第 3 步才要）、`apps/eca/slash.py`（`/compact`、`/clear` 在 pi 怎麼做）、`apps/eca/__init__.py`／`main_turn.py` 的說明字、`knowledge/aos/cli/eca.json`、`templates/docs/01-eca-claude.md`。`grep -c codex` 數出約 180 處提到 codex，大多是說明與分岔，第 1 步（不含畫面）要動的大約三分之一。
</content>
