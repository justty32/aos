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

## 從零搭一棵小樹：一個 daemon＋一隻懂 aos 的 opus eca（使用者自己做）

使用者原話（11-12 傍晚）：「emmm，說是要移植，但不是說完全移植。我會更傾向於在wsl開闢一個空間，然後從一個daemon、一個懂aos的fable eca開始，一步一步慢慢把東西建立起來」、「不用幫我，告訴我怎麼一步一步做。我自己來」、「啊，其實不用fable啦，opus就夠了」

下面每一步的指令 11-13 在公司 WSL 照 main `2e8eb6736` 真搭一次 `~/aos-home` 跑過（掛上 agent、`tools` 26 支、opus 問一句、停樹、存檔讀檔都過，見 [11-13 aos-home](../13/aos-home.md)；repo 是 `~/repo/aos`）。例子用 `~/aos-home` 和 `eca_main`，兩個名字都可以自己取，換的話整份一起換。

### 先要有的

- `aos-*` 指令在 PATH。今天多了一支 `aos-mcp-launch`（外部 MCP 用），先跑一次 install（已經有的會跳過）：

```sh
~/repo/aos/proto8/install.sh
```

  做完最後一行是 `done: …`（今天這台會多連一支、其餘 already）；`command -v aos-exec` 印出 `~/.local/bin/aos-exec` 就對了。
- claude CLI 已登入（隨便一個資料夾打 `claude -p --model opus 'Reply with the single word: hi'` 會回 `hi`；這一句會花一點錢）。

### ① 建資料夾

整棵樹放家目錄底下（不放 `/tmp`、不放 `/mnt/c`）。`root/` 放根 daemon，`daemon/` 放管 agent 的那台（領班），`agents/` 放 agent 定義，`ws/` 是工作區。

```sh
mkdir -p ~/aos-home/root ~/aos-home/daemon ~/aos-home/agents ~/aos-home/ws && ls ~/aos-home
```

看到：`agents  daemon  root  ws`

### ② 把 main 的程式抄進來

抄 `lib`、`py`、`templates`、`knowledge` 四夾，再刪掉快取和已拆工具留下的空殼夾。

```sh
cd ~/aos-home && R=~/repo/aos/proto8 && cp -r $R/lib $R/py $R/templates $R/knowledge . && find lib py templates knowledge -name __pycache__ -prune -exec rm -rf {} + && find lib py templates knowledge -type d -empty -delete && ls
```

看到：`agents  daemon  knowledge  lib  py  root  templates  ws`

### ③ 寫 env.sh

每個視窗開始前 source 它。最重要的是 `AOS_HOME`＝這棵樹（定義裡的工具路徑都從它算）。

```sh
cat > ~/aos-home/env.sh <<'EOF'
# aos-home environment: run "cd ~/aos-home && source env.sh" in every window first.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT
unset AOS_DAEMON AOS_KERNEL AOS_CLOCK
export AOS_HOME=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
command -v aos-exec >/dev/null || echo "env.sh: aos-exec not on PATH; run ~/repo/aos/proto8/install.sh once" >&2
EOF
```

確認：

```sh
cd ~/aos-home && source env.sh && echo $AOS_HOME
```

看到：`/home/<你>/aos-home`

### ④ 根 daemon 的定義

從範本 `templates/daemon-root` 抄 `_entry` 和 `daemon.json`；`.env` 只寫時鐘那一行（範本的 `.env` 還帶問腦總機的設定，eca 用不到）；`daemon.json` 的 `procs` 多加一格 `foreman`，讓根把領班帶起來、工作區給 `ws/`。

```sh
cd ~/aos-home && cp templates/daemon-root/_entry templates/daemon-root/daemon.json root/ && printf '%s\n' 'AOS_CLOCK=${AOS_STACK}/clock' > root/.env && aos-json set root/daemon.json#/procs/foreman '{"exec": "../daemon", "stack": "../ws/.stack", "ws": "../ws", "auto_restart": true}' && aos-json get root/daemon.json#/procs
```

看到：一行 JSON，裡面有 `_clock`、`_sweeper`、`foreman` 三格。

### ⑤ 領班（管 agent 的那台）

兩個檔：`_entry` 換到工作區再變成 daemon；`daemon.json` 帶一格清潔工。

```sh
cat > ~/aos-home/daemon/_entry <<'EOF'
#!/bin/sh
# Foreman entry: cd to the workspace the root gave (AOS_WS) and become the agent daemon (exec keeps the pid).
cd "$AOS_WS" && exec aos-daemon --enable-logs "$AOS_CD/daemon.json"
EOF
```

```sh
chmod +x ~/aos-home/daemon/_entry && echo '{"interval_ms": 200, "procs_requests": "procs_requests", "procs": {"_sweeper": {"exec": {"argv": ["aos-sweeper", "--retention-days", "7", "--report", {"$env": "AOS_STACK", "$path": "sweeper_report.json"}]}, "interval_ms": 600000, "auto_restart": true, "stuck_after_ms": 600000}}}' > ~/aos-home/daemon/daemon.json && ls -l ~/aos-home/daemon
```

看到：`_entry`（有 x 權限）和 `daemon.json`。

### ⑥ eca 那隻的定義

從範本 `templates/eca-claude` 抄一份叫 `eca_main`。模型寫在 `llm.json`（`opus`＝claude CLI 認的別名，這台實際跑 `claude-opus-5-5`）。花費上限在 `cli.json` 的 `print_flags`：`[]`＝不設限；要設上限就寫 `["--max-budget-usd", "3"]`（管的是「claude 跑一次」＝一輪；超過時那輪報 `CliFailed`、沒有回答）。其他旗標照範本，不要加全繞過權限的旗標。

```sh
cd ~/aos-home && cp -r templates/eca-claude agents/eca_main && echo '{"model": "opus"}' > agents/eca_main/llm.json && aos-json set agents/eca_main/cli.json#/print_flags '[]' && cat agents/eca_main/cli.json
```

看到：`"print_flags": []`、`"tools_sub": "tools_sub.json"`，flags 是 `--tools Read,Write,Edit,Glob,Grep,Bash,Agent,Skill`、`--permission-mode dontAsk`、`--allowedTools Write,Edit,Bash`、`--strict-mcp-config`。

### ⑦ 讓它找得到 knowledge

範本的 system 沒提 knowledge 在哪，在**這隻自己的定義**放一份 `system.txt`（範本的 `interfaces.json` 已經宣告這個檔名，會附加在 claude 自己的 system 後面）。路徑從工作區 `ws/` 算，所以是 `../knowledge`。

```sh
cat > ~/aos-home/agents/eca_main/system.txt <<'EOF'
Shared knowledge about aos is in ../knowledge (paths are relative to your workspace).
Start with ../knowledge/aos/_description.json; use the aos tool index_view on ../knowledge/aos to see what else is there, and json_get to read a file.
EOF
```

### ⑧ 第一次的信任提示

`ws/` 是新路徑。只用 chat（下面 ⑪）不會問；要開畫面（`open`）之前，先在那個資料夾開一次 claude、按「信任」、打 `/exit` 離開：

```sh
cd ~/aos-home/ws && claude
```

### ⑨ 起樹

視窗一，前景跑著（Ctrl-C＝整棵停）：

```sh
cd ~/aos-home && source env.sh && aos-exec root
```

另一個視窗確認：

```sh
cd ~/aos-home && source env.sh && aos-daemon-ctl -d .stack ls
```

看到：`_clock`、`_sweeper`、`foreman` 都是 `running`。

### ⑩ 把它掛上

在 `ws/` 裡打（之後跟它有關的指令都在 `ws/` 裡打）：

```sh
cd ~/aos-home && source env.sh && cd ws && aos-agent ctl add ../agents/eca_main && aos-agent ctl ls
```

看到：`eca_main	running	/home/<你>/aos-home/ws	0	-`。再確認工具：`aos-agent tools --target eca_main ls | wc -l` 是 `26`。

### ⑪ 跟它講話

一行一句、等它回（Ctrl-C 離開，樹照跑）：

```sh
cd ~/aos-home && source env.sh && cd ws && aos-agent chat -t eca_main
```

看 claude 的互動畫面（要先做過 ⑧）：

```sh
cd ~/aos-home && source env.sh && cd ws && aos-agent open -t eca_main
```

### ⑫ 確認它懂 aos（兩句，在 chat 裡貼）

```
Use the aos tool index_view on ../knowledge/aos and tell me in one line how many entries it shows.
```

應該回 20 項上下（今天 main 是 20）。

```
List the names of your aos tools (mcp__aos__*) and count them.
```

應該是 26 支，有 `json_get`、`index_view`、`mailbox_send`、`self_system`…，沒有 read、write、shell。

### ⑬ 停樹

```sh
aos-daemon-ctl -d ~/aos-home/.stack shutdown
```

看到：`daemon at …/aos-home/.stack stopped …; 3 procs asleep, they wake when it starts again`。下次照 ⑨ 起，它自己醒、對話還在，不用再 add。

### ⑭ 存檔與讀檔

存檔＝停樹後整份抄（不做自動存檔）：

```sh
mkdir -p ~/aos-saves && cp -a ~/aos-home ~/aos-saves/aos-home-$(date +%m%d-%H%M)
```

讀檔＝停樹後換回來（`<存檔名>` 換成 `ls ~/aos-saves` 看到的那個）：

```sh
rm -rf ~/aos-home && cp -a ~/aos-saves/<存檔名> ~/aos-home
```

### ⑮ 加第二隻（例：`eca_two`，樹起著也能加，在 `ws/` 裡打）

```sh
cp -r ~/aos-home/templates/eca-claude ~/aos-home/agents/eca_two && echo '{"model": "opus"}' > ~/aos-home/agents/eca_two/llm.json && aos-json set ~/aos-home/agents/eca_two/cli.json#/print_flags '[]' && aos-agent ctl add ../agents/eca_two
```

要它也找得到 knowledge，把 ⑦ 那份 `system.txt` 抄過去：`cp ~/aos-home/agents/eca_main/system.txt ~/aos-home/agents/eca_two/`。

### ⑯ repo 更新後只重抄 lib 或 knowledge

`aos-*` 指令是 symlink，repo 一改就生效；抄進來的四夾不會，要重抄。工具改了抄 lib，說明檔改了抄 knowledge（agent 每次讀都是現讀，不用停樹）：

```sh
cd ~/aos-home && rm -rf lib && cp -r ~/repo/aos/proto8/lib . && find lib -name __pycache__ -prune -exec rm -rf {} + && find lib -type d -empty -delete
```

```sh
cd ~/aos-home && rm -rf knowledge && cp -r ~/repo/aos/proto8/knowledge . && find knowledge -name __pycache__ -prune -exec rm -rf {} +
```

### ⑰ 之後要接外部 MCP

照 [external-mcp 06 § 搬一隻現有 Codex agent 進 aos 的照抄步驟](external-mcp/06-施工結果.md#搬一隻現有-codex-agent-進-aos-的照抄步驟佔位符)（那份是 codex 身的例子，佔位符換成自己的）。

### 常見卡住的地方

- **`TrustMissing`**（`ctl ls` 或開畫面時）：那個工作區 claude 沒信任過，照 ⑧ 開一次 claude 按信任。
- **`InstanceExists`**：同名已經掛著了（停樹再起也還在），不用再 add；真要重來先 `aos-agent ctl rm --purge -y eca_main`（會刪它的對話）。
- **不在 `ws/` 裡打 `aos-agent`**：它會找不到領班（`aos-agent` 看的是目前資料夾的 `./.stack`）。
- **樹在跑時不要整夾重抄 agent 的定義**：先停樹；只重抄 lib／knowledge 可以不停。
- `aos-agent ctl add --envs` 不要放 API key 之類的秘密（會寫進 stack 的檔）。
- 從 Windows 用 `wsl -d Ubuntu -- bash -lc '…'` 打指令時，`$變數` 可能被吃掉；在 WSL 終端機裡直接打就沒事。
- eca 一句話都算一題、都花錢；hook（例如 `on_clock`）不要掛在 eca 上。
