# eca-pi：把 pi coding agent 當成一隻 aos agent（kind pi，rpc 一輪＋畫面）

← [templates/agents/eca-pi](../agents/eca-pi/README.md)｜同類：[01-eca-claude](01-eca-claude.md)｜研究與裁定：[thinking 11-18 eca-pi](../../thinking/2026-11/18/eca-pi/README.md)

使用者 11-18：「1.做成第三種。2.甲。3.先全開。4.我是打算拿它來代替codex。5.對。6.開」，下午改口「算了，不要釘版吧，太麻煩了」，傍晚「codex身留下，pi coding agent要做畫面，去吧。每輪生一行外掛，目前就先這樣。…接著做乙丙吧。」所以：pi 是 eca 的第三種身（跟 claude、codex 並列）、權限照 pi 原樣全開、用使用者自己裝的那份 pi、codex 那種身照留；非互動那條走乙案（`pi --mode rpc`，回答途中收信），另有丙案的畫面（tmux＋aos 的 pi 外掛）。甲案（`--mode json`）沒留：乙完全涵蓋甲。

## 先講結論

- `cli.json` 寫 `"kind": "pi"`，aos 每批信起一次 `pi --mode rpc`，題目送一則 `prompt`，讀它的事件流拿回答；同一段對話靠 aos 自己產的 id 接下去。
- **回答途中又來的信**：一封一則 `steer` 送進去，pi 在下一次叫模型之前讀到，回答是每段接起來（`"live_mail": false` 關掉）。
- **有畫面**：`aos-agent open` 在 tmux 裡起互動的 `pi`（同一段對話），多帶一支 aos 的 pi 外掛：每講完一輪通知 aos，畫面開著時 aos 的信經它送進對話。
- 對話檔放在 aos 的小格裡（`$AOS_STACK/pi/pi-sessions/`），不在 `~/.pi/agent/sessions/`。
- aos 的工具（`mcp__aos__*`）照樣給得到：aos 每輪在小格寫一支一行的 pi 外掛（`pi-aos-mcp.mjs`）去登記 aos-mcp，用 `-e` 帶進去。
- **pi 不問權限、沒有沙盒**：它的 bash、read、edit、write 用你這個 Linux 帳號的全部權限跑。aos 只加 `--no-approve`（不載工作區 `.pi/` 裡的設定與外掛）。

## 要先有的東西

1. **`pi` 與它要的 `node` 都要在 aos 起它的那個環境的 PATH 上**，開畫面的那個殼也一樣。pi 的啟動檔第一行是 `#!/usr/bin/env node`：只有 `pi` 在 PATH、`node` 不在，會退 127（aos 回 `CliFailed … exit 127: pi, or the node it runs on, is not on PATH`）。最省事的做法是在**樹的 `env.sh`**（「下面可以加這棵樹自己的 export」那份）加一行，之後起根的視窗都帶著；node 換版本時這行要跟著改：

   | 機器 | node 在哪（11-18） | env.sh 那行 |
   |---|---|---|
   | 公司 WSL | nvm：`~/.nvm/versions/node/v24.19.0/bin`；pi 在 `~/.local/bin/pi` | `export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$HOME/.local/bin:$PATH"` |
   | 家機 | fnm：`~/.local/share/fnm/node-versions/v24.14.1/installation/bin`（pi 也在這裡） | `export PATH="$HOME/.local/share/fnm/node-versions/v24.14.1/installation/bin:$HOME/.local/bin:$PATH"` |

2. **登入**：用 pi 自己登 ChatGPT 訂閱：在終端機跑 `pi`，打 `/login`，選 OpenAI（Sign in with ChatGPT）。登入檔在 `~/.pi/agent/auth.json`，aos 不讀不改。**pi 自己的預設模型要是登入過的供應商**，不然寫明 `llm.json` 的 `model`：家機 11-18 的 pi 預設是 `deepseek`、又留著一份過期的 anthropic 登入，`llm.json` 是 `{}` 時第一輪就 `CliFailed`（原因是 anthropic 的 `Refresh token expired`），改寫 `{"model": "openai-codex/gpt-6.1-sol"}` 就好。
3. 想釘版（使用者裁了不釘，這段只當參考）：在一個專用資料夾 `npm install --ignore-scripts --save-exact @earendil-works/pi-coding-agent@<版本>`、留 `package-lock.json`，之後 `npm ci` 重裝，PATH 指那裡的 `node_modules/.bin`；理由與事故表見 [05-供應鏈](../../thinking/2026-11/18/eca-pi/05-供應鏈.md)。

## 一輪怎麼跑（沒開畫面；11-18 實測 pi 1.5.2）

aos 起的是：

```
pi --mode rpc --no-approve --session-dir $AOS_STACK/pi/pi-sessions --session-id <id> [cli.json 的 flags、print_flags] [-e <小格>/pi-aos-mcp.mjs] [--append-system-prompt <system 檔>]
```

| 事 | 怎麼做 | 實測 |
|---|---|---|
| 題目 | stdin 寫一行 `{"type": "prompt", "message": …}` | 回 `response`（disposition started） |
| 第一輪 | aos 產一個 uuid 給 `--session-id`，交出去那一刻寫小格的 `session.txt` 與 `.session_home` | pi 在 `pi-sessions/` 建 `<時間>_<id>.jsonl`，stderr 印一行 `Warning: No project session found with id …; creating a new session with that id.`（正常，第一輪都有） |
| 之後 | 同一個 id 再給一次 | 是「接著那段」，不是開新的 |
| 回答途中又來的信 | 一封一則 `{"type": "steer"}` | 回 `queued`；工具跑到一半送＝同一則回答把兩件事一起答，講字途中送＝另開一段；全部在 `agent_settled` 之前送到 |
| 收工 | 等到 `agent_settled`（`agent_end` 不是終點）；還有沒送的就 `clear_queue` 再補一則 `prompt`，最後關 stdin | 行程隨後結束 |
| 回答 | 每則 user（題目或中途的信）到下一則 user 之間，最後一則講完的 assistant 的字；各段用空行接起來 | — |
| 失敗 | 最後一則 assistant 的 `stopReason` 是 `error`／`aborted`＝`CliFailed`，原因取它的 `errorMessage`；`prompt` 被拒（`success false`）也是 `CliFailed` | **模型那邊出錯 pi 照樣退 0**；模型名不認得才退 1 |
| 事件 | 一行一行接進小格的 `live.jsonl` | `aos-agent watch` 看得到 |

失敗不分暫時或永久（跟 codex 一樣：這批信記 failed、記冷卻、fire `brain_failed`）；pi 自己會先重試幾次。

## 畫面（`aos-agent open`）

- 起的是互動的 `pi`（不帶 `--mode`、`print_flags`），同一個對話資料夾、同一個 id（還沒有對話＝不帶 id，pi 自己開新的、外掛回報）、`--tui-mode regular`（一般捲動，跳出再接回看得到前面的字），另外多帶一支 `-e <小格>/pi-aos-screen.mjs`：aos 開畫面時寫的一行外掛，叫 `lib/aos/agentlib/pi_aos_screen.mjs`、帶這格的設定。
- 外掛做的事：`session_start`（startup／new／resume／fork）、`agent_start`、`agent_settled`（連同這輪的 messages）、`session_compact` 各叫一次 `cli_session.py hook pi <小格>`；aos 那邊跟上對話 id、把每輪的回答記進小格的 `turns.jsonl`、畫面打 `/new`＝aos 的 history 清掉、pi 壓縮＝history 換成摘要。
- **畫面開著時 aos 的信**：寫進小格的 `pi_inbox/`（一封一個 `.json`），外掛每 0.5 秒看一次，讀了就刪、用 `pi.sendUserMessage` 送進對話（正在答＝`deliverAs: "steer"`），再回報收據；回答從 `turns.jsonl` 拿（同 claude 畫面的收件口）。
- tmux 設定是小格自己那份（`-f <小格>/tmux.conf`，不讀 `~/.tmux.conf`），pi 身多兩行：`set -g extended-keys on`、`set -gq extended-keys-format csi-u`（pi 開場會提醒；後者 tmux 3.5 起才有，`-q`＝舊版不認也不報錯）。
- `Ctrl-]` 跳出、畫面留著；`aos-agent close` 關。`ctl stop` 之後畫面留 `screen_close_after_s` 秒（預設 600）再關，`ctl start` 會取消（`hookeds.json` 的 `screen_linger_start`／`screen_linger_stop`，同 eca-claude）。

## cli.json

```json
{"kind": "pi", "flags": [], "timeout_ms": 0}
```

- `flags`／`print_flags`：照原樣接在後面（`print_flags` 只給非互動那條）。aos 自己加、你不能再寫的（寫了＝`CfgBad`）：`--mode`、`-p`／`--print`、`--session`、`--session-id`、`--session-dir`、`--no-session`、`--fork`、`-c`／`--continue`、`-r`／`--resume`、`-a`／`--approve`、`-na`／`--no-approve`。
- `live_mail`（預設開）、`live_mail_cap`：同 claude，管回答途中收信。
- `screen_close_after_s`：同 eca-claude。
- 模型：`llm.json` 的 `model` 補成 `--model`（pi 的寫法是 `供應商/id`，`pi --list-models` 列得出來；ChatGPT 訂閱的供應商叫 `openai-codex`，例 `openai-codex/gpt-6.1-sol`）；範本的 `llm.json` 是 `{}`＝用 pi 自己的預設（見上面「登入」那條的坑）。`reasoning_effort` 補成 `--thinking`（`off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`，其他＝`CfgBad`；pi 的對話會記程度，拿掉之後同一段對話照用上次的；見 [01「思考程度」](01-eca-claude.md)）。
- **改指 OpenAI 相容端點**（例：litellm proxy `http://localhost:4000/v1`）：pi 的 provider 設定在帳號資料夾的 `models.json`。不想動 `~/.pi/agent`，就另開一個帳號資料夾、在起樹的環境設 `PI_CODING_AGENT_DIR`：

  ```json
  {"providers": {"litellm": {"baseUrl": "http://localhost:4000/v1", "api": "openai-completions",
                             "apiKey": "$LITELLM_KEY", "models": [{"id": "<proxy 上的模型名>"}]}}}
  ```

  `llm.json` 寫 `{"model": "litellm/<proxy 上的模型名>"}`。`apiKey` 寫 `$變數名`＝從環境變數讀，不要把值寫進檔。換帳號資料夾＝aos 當成換了一個帳號，下一輪開新對話（帶 aos 的紀錄過去）。
- `system`（`interfaces.json` 宣告了才有；範本的 `system.txt` 兩段短文，寫知識庫在哪，同 eca-claude）：用 `--append-system-prompt <檔>` 附加；pi 一輪一個行程，所以每輪重讀，改了下一輪就生效。
- `tools`：同 eca-claude（範本是同一份 `tools.json`）。工具名 `mcp__aos__<名>`，直接給模型看（exposure `direct`）。
- `mcp_servers`（外部 MCP）：pi 身還沒接，寫了＝`CfgBad`。`settings`、`tools_sub` 是 claude 專屬。

## slash 指令

| 信 | 沒開畫面 | 畫面開著 |
|---|---|---|
| `/compact [指示]` | rpc 的 `prompt` 不認 slash：aos 另起一次 `pi --mode rpc` 接同一段對話、送 `{"type": "compact"}`（帶指示＝`customInstructions`），**等到它回 response 才關 stdin**（先關＝pi 收工、壓縮被取消）。成功＝history 換成 pi 的摘要一則（原文搬到 `history_removed.jsonl`）；pi 嫌對話太短不壓＝history 不動、回它的原因（`Nothing to compact (session too small)`） | 照打進畫面（帶指示），外掛收到 `session_compact` 就換 history；pi 不壓時沒有事件，aos 等滿 120 秒才回「history 沒變」 |
| `/clear` | 同 codex：history 清掉、刪 `session.txt`，下一封開新對話 | 打成 pi 的 `/new`，外掛回報新 id、aos 清 history |
| `/status` | 照常 | 照常（寫 `screen open`） |
| `/goal …`、`/usage` | 回一句不支援，不交給 pi | 同左 |
| `/exit` | 沒畫面，回一句 | 關畫面（有人接著時不關） |

## 11-18 實跑

**公司 WSL（甲案時，暫存樹，照[重建步驟單](../../thinking/2026-11/17/重建步驟單.md)起 start-eca 再掛一隻 eca-pi）**：假端點（`PI_CODING_AGENT_DIR` 指暫存夾的 `models.json`）上問、續問、叫 aos 工具、`/status`、`/compact`（history 換成摘要、同一個 id）、`ctl stop`＋`ctl start`、`ctl set-def`；真模型（ChatGPT 訂閱）問、續問、pi 自己的 bash、aos 的 `mcp__aos__peek_now_time` 四句都對。

**家機（乙＋丙案，pi 1.5.2、tmux 3.7c、ChatGPT 訂閱的 `openai-codex/gpt-6.1-sol`；暫存夾 `~/.aos/scratch/eca-pi-home-1118/`，本機 HEAD 的 clone 套這條線的改動、`install.py`、start-eca 換掛一隻 eca-pi，`-w ws`）**：

| 步 | 結果 |
|---|---|
| 問一句 | `llm.json` 是 `{}` 時 `CliFailed`（pi 預設的供應商沒登入，見「登入」）；寫明模型後回 `APPLE` |
| 續問 | 答得出上一句（同一段對話） |
| 回答途中再寄一封 | 第一封叫它 `sleep 25` 再回，12 秒後寄第二封「最後加 BANANA」：一則回答 `DONE1\nBANANA`，history 記成同時答了兩封 |
| aos 工具 | `mcp__aos__peek_now_time` 回時間 |
| `/compact`（沒畫面） | 對話太短，pi 不壓，回原因、history 不動（壓成功那條只在公司假端點試過） |
| `aos-agent open` | 接著同一段（畫面上看得到前面的問答）；畫面裡打字＝外掛回報、`turns.jsonl` 多一行 |
| 畫面開著時寄信 | 經 `pi_inbox/` 送進畫面、畫面上答、`listen` 拿到回答、history 有這一問一答 |
| 畫面正在答時寄信 | 畫面裡叫它 `sleep 20`，6 秒後 aos 寄「最後加 KIWI」：同一則回答 `DONE2\nKIWI`，aos 那封拿到這則 |
| 畫面開著 `/compact`、`/clear`、`/goal`、`/status` | `/compact`：pi 不壓（太短），等滿 120 秒回「history 沒變」；`/clear`：畫面 `New session started`、aos 記新 id、history 清掉；`/goal` 回不支援；`/status` 寫 `screen open` |
| `aos-agent close` 後一問一答、再開畫面 | close 後的一問一答開了新對話（畫面 `/new` 開的那段還沒講過話，pi 沒建檔，aos 認不得就開新的）；之後一問一答兩句接得上；再開畫面接著那段，畫面裡問「剛剛的代號」答得出 |
| `ctl stop` 延後關 | `screen_close_after_s` 設 8：stop 後畫面還在、14 秒時已關 |
| `ctl set-def` 換到另一份定義 | 接著同一段對話（答得出代號） |
| `ctl rm` | 沒跑（這輪的權限設定擋了含 `rm` 字樣的指令） |

## 已知限制

- **畫面上人打的字不進 aos 的 history**：記在 `turns.jsonl` 與 pi 的對話檔；aos 寄進畫面的信才照常記一問一答。
- **畫面開著時 `/compact` 遇上 pi 不壓**：pi 不發事件，aos 要等滿 120 秒才回。
- **收件夾送進對話的信不署名**：模型看到的就是那段字，看不出是 aos 哪封信、誰寄的。
- **`pi_aos_screen.mjs` 綁 pi 的外掛 API**（`pi.on` 的事件名、`ctx.sessionManager.getSessionId`、`ctx.isIdle`、`pi.sendUserMessage` 的 `deliverAs`）；aos 工具那支 `pi-aos-mcp.mjs` 綁 `pi.registerMcpServer`。pi 改了這些就會壞；沒釘版，pi 一更新就可能碰到（11-18 家機 pi 1.5.2 實跑過）。
- **開畫面那個殼也要有 node 與 pi 的 PATH**（`aos-agent open` 是在你打它的殼起 tmux）。
- 畫面上 `/new` 之後還沒講話就關畫面，下一次一問一答開新對話（那段空的，不影響內容）。
- 權限全開：pi 沒有核准模式、沒有白名單，aos 的 `before_tool`／`after_tool` hook 只看得到 aos 的工具。要擋得寫 pi 外掛（TypeScript）或整隻放容器，使用者 11-18 裁「先全開」。
- `--no-approve` 擋不到的：工作區的 `AGENTS.md`／`CLAUDE.md`，與帳號資料夾的 `~/.pi/agent/AGENTS.md`，pi 一律讀。
- `context_wrap`：pi 的事件有 token 數、沒有 context 視窗，要在 hook 格寫 `config.window`；範本沒放這格（pi 快滿時自己會壓；使用者 11-18「這個得再去想想辦法」）。
- 失敗不分暫時或永久（同 codex）。
