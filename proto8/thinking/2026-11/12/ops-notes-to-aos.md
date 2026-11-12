# ops-notes-to-aos：把 ops-notes 與兩隻 Codex agent 搬到 WSL 走 aos 跑——盤點完：整套只需要一台 http MCP（團隊站），建議先搬兩隻 gpt-*、ops-notes 主 session 暫不搬；下一步是使用者拿真 token 起第一隻

← [2026-11-12](README.md)｜[thinking](../../README.md)｜接法 [external-mcp 06 § 照抄步驟](external-mcp/06-施工結果.md#搬一隻現有-codex-agent-進-aos-的照抄步驟佔位符)

## 使用者原話（11-12 下午）

- 「Hmmm，我說說我打算做啥，你指導我一步一步準備好。是這樣的，去看看C:/code/guanyu/ops-notes (他的東西比較多，建議用inbox協議敘述你的問題，只取得你要的答案)，還有C:/code/agents。我打算把這套體系放到WSL，走aos跑。這需要mcp。」
- 「好，先驗」（對頂層提議先用假 http MCP 試接 → [external-mcp 05](external-mcp/05-http-bearer試接.md)）

## 盤點（回信 agent 盤點、頂層未自行核對）

另一位 agent 全程唯讀、不碰 secrets，照對方的 inbox 協議以直接訊息回信。以下是它回信的摘要；主機名與網址不寫，用「LAN 主機 A」「團隊站」代稱。

- **ops-notes**＝Claude Code 主 session，管區網機器（LAN 主機 A 等）的維運，沒用任何 MCP。重度依賴 Windows 的 ssh.exe（WSL 原生 ssh 被多台主機拒絕）、Windows 上的 MariaDB；`C:\` 與 `/mnt/c` 路徑在數百個檔裡混用。鐵律含「動區網機器前一律先問」「使用者每天下班關機、WSL 整晚不在，跨夜工作的指揮不可放 WSL」。
- **`C:\code\agents` 下兩隻 Codex（gpt-price、gpt-soap）**：在團隊站論壇幫同事，只碰論壇 MCP、不碰主機。現在是使用者手動在 WSL 跑 start.sh（讀 `~/.config/<agent>/` 的 token 檔與合成的 CA bundle，用 `-c` 帶 server 網址、bearer_token_env_var、shell_environment_policy.exclude）。鐵律「沒說開始不准自己找事、發文、跑循環」；論壇有限速。gpt-price 還沒有任何 commit，gpt-soap 有未提交的改動。
- **整套唯一的 MCP**＝團隊站：http、Bearer token、自簽憑證。這正是 [external-mcp 05](external-mcp/05-http-bearer試接.md) 試接、06 施工做的那條路。

## 頂層給使用者的準備步驟

1. 兩隻先各 commit 一次現況。
2. 搬到 WSL 家目錄（不留 `/mnt/c`），原資料夾直接當工作區（Codex 會讀裡面的 AGENTS.md）。
3. 正式的樹起在 `~/`（不用試驗場）。
4. 接團隊站 MCP：照 [external-mcp 06 的照抄步驟](external-mcp/06-施工結果.md#搬一隻現有-codex-agent-進-aos-的照抄步驟佔位符)，token 不用 `--envs`。
5. 不掛定時，天然就符合「待命」；使用者說開始＝chat；要定期巡才登記 clock（注意論壇限速）。
6. 每天關機：早上一行起樹，對話接得回。
7. ops-notes 主 session 暫不搬：權限模型不同（它是動機器先問，eca 範本的 Bash 不問）；它還用到 Claude Code 的 session 間訊息與 /loop。它的知識直接讀原資料夾，不複製。

## 未定／沒查到

- `~/.codex/config.toml` 的沙盒與核准預設。
- 團隊站 MCP 的完整工具清單。
- ops-notes 主 session 主要在 Windows 還是 WSL 的 Claude Code 跑。

## 另記一件（頂層提過、使用者未回）

試驗場的 eca opus 自己用了 Claude Code 的記憶功能：存在 `~/.claude/` 底下、跟著工作區路徑走、不在 stack 裡，`ctl rm --purge` 與重刷都清不到。
