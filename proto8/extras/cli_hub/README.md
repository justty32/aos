# cli_hub — aos-hub：常駐 kernel 管所有 claude／codex 實例；接進畫面、收起、結束歸檔；代答 stack 裡 queue 的訊息

← [extras](../README.md)｜設計：[thinking 2026-10-28-hub-adapter](../../thinking/2026-10-28-hub-adapter.md)（協議、適配表、副產物）、[10-28 hub-kernel](../../thinking/2026-10-28-hub-kernel.md)（使用者定的 14 條）、[10-30 agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md)（queue、close、session 檔接管；第 6 步）、[10-27 claude-switch](../../thinking/2026-10-27-claude-switch.md)（第一版）｜接的是 [lib/agent/cli_session.py](../../lib/agent/cli_session.py)｜測試 `proto8/tests/test_hub.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」10-28：「其實應該還是要aos-hub。因為不只claude code cli，可能也要包括pi coding agent, codex之類。」「aos-say/listen是面對aos agent的，或許可以提取出相關協議，然後讓hub實作之類。」

## 是什麼

| 檔 | 做什麼 |
|---|---|
| `bin/aos-hub-kernel` | 常駐 kernel：開 `$AOS_HUB/kernel.sock`，記著所有實例；替「代答」的實例收 `<資料夾>/.stack/queue/` 的訊息（`aos-post claim`→user 接進 `history.jsonl`→交給 claude／codex 工具→assistant 接進 `history.jsonl`→`aos-post finish`） |
| `bin/aos-hub` | 給人用的指令，全部經 kernel |
| `bin/hub_ipc.py` | 兩支共用：找 `$AOS_HUB`、跟 kernel 講一句 |
| `reap.json` | 自動收起：aos-loop 每分鐘跑 `aos-hub close --idle 30` |

| 指令 | 做什麼 |
|---|---|
| `aos-hub ls [--json]` | 列出全部：編號、狀態、哪種 CLI、工作區、對話 id 前 8 碼 |
| `aos-hub state [資料夾\|編號]` | 這裡是不是納管的實例；不是＝`InstanceMissing`、退 1。「對話檔」一行＝小格的 symlink 指到哪；指不到就說「CLI 自己的對話檔已不在」（退 0） |
| `aos-hub add [--kind claude\|codex \| --tool 工具資料夾] [資料夾]` | 納管、不開畫面：`aos-post init 資料夾/.stack/queue`，kernel 開始替它回答那裡的訊息 |
| `aos-hub open [-d] [--kind …\|--tool …] [資料夾\|編號]` | 接進畫面；沒開就開、收起的用 `--resume` 叫回；還沒納管就先 add。`-d` 只開不接 |
| `aos-hub close [資料夾\|編號]`／`close --idle 分` | 收起：關畫面、對話留著（照樣收題、用 `--resume` 答）；出錯的實例 close 一次＝重新收題。10-30 由 `pause` 改名（跟 `open` 成對；`paused` 留給 N-07「不起新的一次」） |
| `aos-hub stop [資料夾\|編號]` | 結束：關畫面，小格搬到 `<stack>/hub_archive/<工具名>-<UTC>/`，`transcripts/` 裡的 symlink 換成真的複製，從清單拿掉 |
| `aos-hub watch [資料夾\|編號]` | 跟著看非互動那次在做什麼（讀了哪個檔、說了什麼、花多少），一次回答結束就走 |

- **`AOS_HUB` 沒設＝`HubMissing`；kernel 沒在跑＝`KernelMissing`**，都退 1（不給預設路徑、不自動重開）。
- 畫面裡 **Ctrl-]（或 Ctrl-\\）＝跳出、實例不結束**。
- 狀態：`收起了`、`畫面開著`、`在答題`、`出錯`；後面標「（只登記）」的是 agent 叫 claude／codex 工具時登記進來的格——列得到、接得進，**不替它收題**（那個工作區的題是 agent 的）。
- `--kind` 沒給＝claude；工具資料夾預設 `proto8/lib/agent/<kind>`（旗標在它的 `cli.json`：claude 只給 Read／Glob／Grep、sonnet、每次 0.5 美元）。要別的模型、權限，複製一份工具資料夾改 `cli.json`，用 `--tool` 指。
- 失敗（腦、CLI 出錯）：信留在 `queue/cur/`、實例標「出錯」、不再收題；stack 的 `trace.jsonl` 那行記著哪封（`question`＝信號）、原因一行。修好後（要改題目就改 `cur/<信號>/letter.json` 的 `body`）`aos-hub close` 一次重新收。人接在畫面上時信等著（5 秒再試一次）。
- **壞信**：queue 只收 OpenAI message 物件 `{"role": "user", "content": 非空字串}`（agent-lifecycle 衝突 5）；不是的照 N-16 丟掉、`trace.jsonl` 那行記 `letter_warning`、不算出錯。
- **CLI 自己存的對話檔**（agent-lifecycle C-14～C-17、方向題 3）：cli_session 拿到 session id 就在小格建 `transcripts/<kind>-<id>.jsonl`，symlink 指到 claude 的 `~/.claude/projects/*/<id>.jsonl`（`CLAUDE_CONFIG_DIR` 有設就在那底下）或 codex 的 `~/.codex/sessions/**/*<id>.jsonl`（`CODEX_HOME`）；agent 叫工具的格也建。`stop` 才換成複製（claude 會自己清舊 session）。CLI 自己清掉了、或沒存（`--no-session-persistence`）＝`state`／`ls` 說一句、不補、不擋答題。

## 對它說話

資料夾＝claude 工作的地方（例如程式專案），**對話放在 `資料夾/.stack/` 裡**（使用者 10-28「放Stack比較好。」、10-30 agent-lifecycle A-2）：資料夾本身不長東西，queue、history、trace、小格、歸檔全在 `.stack/`。

- **輸入**＝`.stack/queue/`：一個 N-16 的有順序信箱（`aos-post send --ordered`），一封信＝一則訊息，`body` 是一則 OpenAI message `{"role": "user", "content": …}`。
- **回答**＝`.stack/history.jsonl` 最新那則 assistant（一則 user、一則 assistant 各接一行；沒有 `out/`）。信還在 `queue/new/` 或 `queue/cur/`＝還沒答，不見了＝答案已在 history。

```sh
aos-hub add ~/code/myproj                       # 納管（aos-post init .stack/queue）
cd ~/code/myproj
echo '{"role": "user", "content": "讀 src/calc.py 說說裡面有什麼"}' | aos-post send --ordered .stack/queue   # 印信號
tail -1 .stack/history.jsonl                    # 答完：最新那則 assistant（畫面開著＝打進畫面、沒開＝--resume 問一次）
```

aos-say／aos-listen 改走 `$AOS_STACK/queue/`（agent-lifecycle 第 4 步）之後，上面兩行就是 `N=$(aos-say 話)`、`aos-listen "$N"`；那之前的 say／listen 還認舊的 `new/`、`out/`，對不上 hub。

## 怎麼試（WSL）

試驗場 `~/code/try/hub-say/`（10-28 實跑過，haiku 四題合計約 $0.001）：

```sh
cd ~/code/try/hub-say && . ./env.sh              # 拿掉外層 Claude Code 的環境變數、設 AOS_HUB、PATH（含 ~/.local/bin 的 claude／codex）
aos-hub-kernel 2>kernel.err &                    # kernel 從這個 shell 繼承 PATH：claude／codex 要找得到
aos-hub add --tool tools/claude ws-c             # tools/claude 是 haiku 版的 cli.json；信箱在 ws-c/.stack/
N=$(aos-say --ws ws-c "讀 notes.txt，魔術數字是多少"); aos-listen --ws ws-c "$N"   # say／listen 改走 queue 之後
aos-hub open ws-c                                # 接進畫面（第一次會問信任這個資料夾，選 Yes）；Ctrl-] 跳出
N=$(aos-say --ws ws-c "乘以二？"); aos-listen --ws ws-c "$N"   # 畫面開著：打進畫面，再 open 進去看得到
aos-hub close ws-c && aos-hub ls                 # 收起；再問一句照樣答（--resume）
aos-hub state ws-c                               # 「對話檔」一行：ws-c/.stack/claude/transcripts/claude-<id>.jsonl → ~/.claude/projects/…
aos-hub add --kind codex ws-x                    # codex 也一樣
aos-hub stop ws-c                                # 結束：看 ws-c/.stack/hub_archive/（transcripts/ 是真檔）
aos-hub add --tool tools/claude proj && cd proj && aos-say 'src/calc.py 的函式叫什麼'   # 程式專案也行：proj 頂層只多一個 .stack/
```

## 已知限制

- **kernel 的 PATH**：kernel 用自己啟動時的環境叫 claude／codex 與 aos-post。從沒有 `~/.local/bin` 的 shell 起 kernel，每題都 `CliMissing`（10-28 實跑撞到）；沒有 aos-post（`proto8/impls/aos-post/bin`）＝`add` 就 `PostMissing`。
- **新資料夾第一次開畫面，claude 會先問「信任這個資料夾嗎」**：人 `open` 接進去回答就好；但 `open -d` 之後馬上丟題，題目會被貼進這個提問、Enter 可能選到「No, exit」，畫面關掉、那題出錯（`close` 一次就改走 `--resume` 答）。非互動（`-p`）沒有這個提問。
- **kernel 重開＝清單清空**：工作區、小格、對話都還在，重新 `add` 就接得上（同一個 `session.txt`）。kernel 記的跟實際不符（人在畫面裡 `/exit`、tmux 被砍）時以 kernel 記的為準（使用者 10-28：遇到再說）；agent 的工具呼叫本身照樣會挑對的路。
- queue 放在 `.stack/` 裡：一個資料夾若同時有 aos agent 用 `<資料夾>/.stack/` 當 stack、又被 aos-hub 納管，兩個會搶同一個 queue（一個工作區一個 agent，P-18）。stop 只搬小格，`.stack/queue` 還在，之後丟的信沒人答。
- 題目資料夾裡的附檔（N-16「其他檔隨意」、P-13）不交給 CLI：只送 `body` 的 `content`。
- 只登記的格要在 kernel 跑著時被用過才列得到；kernel 沒跑時 cli_session 不報錯、只是不登記。
- codex 沒有「正在跑一輪」的訊號：人在畫面上送出、還沒講完就跳出，kernel 這時送字會插進去（10-24 舊坑）。
- `watch` 只讀 `live.jsonl`（非互動那條路）；畫面上那幾輪看不到，要 `open` 進去看。
- `live.jsonl` 只接不重寫，會一直長；清理是人的事。
- 「閒了幾分」看格裡檔案最後被動的時間：人只是捲畫面、打字沒送出，不算動作。
- 收起＝`tmux kill-server`：人打到一半沒送出的字會丟。
- `history.jsonl` 是 kernel 照它送給 CLI 的、CLI 回的寫的；人在畫面上直接打的那幾輪不在裡面（在 CLI 自己的對話檔，`transcripts/` 指過去）。
- 你自己在終端機開的 claude 不在裡面，用 Claude Code 內建的 `claude agents` 看。
