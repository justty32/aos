# eca 不給基礎檔案工具：施工結果（11-12，公司 WSL）

← [11-12 日索引](README.md) ・ 前情：[11-11 playground 04 § eca 不給基礎檔案工具](../11/playground/04-修與第二輪實測.md#eca-不給基礎檔案工具使用者-11-11-晚-2300-前裁明天施工)

## 使用者原文

- 11-11 晚：「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」
- 11-12 早（針對 04 的兩個前提：claude 的 `--tools` 只開讀、codex 沙盒唯讀）：「eca這塊，放寬claude，codex拿掉唯讀沙盒。」
- 11-12（看完代定後）：「可以先定這樣，然後trash也拿掉。」

## 決定

1. **eca 範本 35 → 20 支**：`templates/eca-claude/tools.json` 不再疊 look、change、delete、shell 四包，拿掉 read、ls、view、stat、grep、glob、write、edit、copy、move、mkdir、trash、remove、shell、run_python 共 15 支。aos 專屬的 json_read、json_write 在 `tools` 裡單獨登記。剩下的 20 支：json_read、json_write、peek_clock、peek_now_time、math、clock_register、self_hook、self_tools、self_llm、self_system、self_state、self_ctl、self_history、agent_def、tools_def、mailbox_peek、mailbox_read、mailbox_send、knowledge_read、knowledge_write。
2. **trash 也拿掉**（使用者「trash也拿掉」）。
3. **放寬 claude**：`cli.json` 的 flags 改成 `--tools "Read,Write,Edit,Glob,Grep,Bash" --permission-mode dontAsk --allowedTools "Write,Edit,Bash" --strict-mcp-config`。
4. **codex 拿掉唯讀沙盒**：eca 的 codex 版 `cli.json` 改成 `-c sandbox_mode="workspace-write" -c approval_policy="never"`。repo 裡沒有獨立的 eca-codex 範本（11-04 刪了），寫法放在 [templates/docs/01-eca-claude](../../../templates/docs/01-eca-claude.md) 開頭那段。
5. fsm 範本（agent-fsm）不動，還是 41 支。

## 代定（使用者「可以先定這樣」＝已認可，可翻案）

- **「拿掉唯讀」＝`workspace-write`**，不是 `danger-full-access`。codex 能用自己的指令讀寫工作區，工作區外照 codex 沙盒的規則。
- **claude 開 Write、Edit，也開 Bash**。04 擔心「dontAsk 加 Bash，claude 跑指令不必問」，但拿掉以前，aos 的 `shell` 已經經 aos-mcp 免問就能跑任何指令（`--allowedTools mcp__aos`），所以換成 claude 自己的 Bash 不會多出權限，只是工具換成更順手的那支。所以 aos 的 shell、run_python 一起拿掉。
- **權限照 dontAsk 加白名單**：Write、Edit、Bash 三支列進 `--allowedTools`，其他沒列的照 dontAsk 拒絕。不用 acceptEdits，因為畫面開著時沒准的工具會停在詢問、卡住那一輪。**沒加任何全繞過權限的旗標**（`--dangerously-skip-permissions`、bypassPermissions）。
- cli_session 自己加的 `--allowedTools mcp__aos` 照舊，兩個 `--allowedTools` 會合併，真腦實測 aos 工具照樣叫得到。
- lib/agent/codex（給腦叫的 codex 工具）的沙盒**照舊唯讀**。那是另一件東西，不在這次範圍。

## 真腦實測（11-12 上午，公司 WSL）

在 `/tmp/eca-1112` 起臨時定義與工作區，不掛 daemon，直接跑 `aos-eca-turn`。題目都是：用自己的工具讀 `seed.txt`，把內容轉大寫寫進 `out/<名>.txt`，列出 `out/`，再叫 aos 的 peek_now_time。

| 腦 | 結果 | 用到的工具 |
|---|---|---|
| claude haiku | ✅ `out/claude.txt` 是 `HELLO FROM SEED`，答 `ls out: claude.txt · Time: 2026-11-12T00:10:16Z`；permission_denials 是空的；$0.0016 | Read、Write、Bash、`mcp__aos__peek_now_time` |
| codex gpt-6-luna | ✅ `out/codex.txt` 是 `HELLO FROM SEED`，答 `out: claude.txt, codex.txt — time: 2026-11-12T00:11:05Z` | codex 自己的 command_execution，加 aos 的 peek_now_time（mcp_tool_call） |

`claude -p` 沒有卡在信任資料夾的選單。畫面版（tmux）這次沒驗。

## 要重建什麼

試驗場的 eca 定義要照新範本重抄。eca_cody 的 `cli.json` 要照 01-eca-claude 那份改成 workspace-write。`~/.cache/aos-mcp-aos/tools.json` 不受影響。
