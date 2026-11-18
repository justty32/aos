# eca-pi：把 pi coding agent 當成一隻 aos agent（kind pi，一問一答）

← [templates/eca-pi](../eca-pi/README.md)｜同類：[01-eca-claude](01-eca-claude.md)｜研究與裁定：[thinking 11-18 eca-pi](../../thinking/2026-11/18/eca-pi/README.md)

使用者 11-18：「1.做成第三種。2.甲。3.先全開。4.我是打算拿它來代替codex。5.對。6.開」，下午改口「算了，不要釘版吧，太麻煩了」。所以：pi 是 eca 的第三種身（跟 claude、codex 並列）、先只做一問一答、權限照 pi 原樣全開、用使用者自己裝的那份 pi、codex 那種身照留。

## 先講結論

- `cli.json` 寫 `"kind": "pi"`，aos 每批信起一次 `pi --mode json`，題目從 stdin 進、讀它的事件流拿回答；同一段對話靠 aos 自己產的 id 接下去。**沒有畫面**、**回答途中不收信**。
- 對話檔放在 aos 的小格裡（`$AOS_STACK/pi/pi-sessions/`），不在 `~/.pi/agent/sessions/`。
- aos 的工具（`mcp__aos__*`）照樣給得到：aos 每輪在小格寫一支一行的 pi 外掛（`pi-aos-mcp.mjs`）去登記 aos-mcp，用 `-e` 帶進去。
- **pi 不問權限、沒有沙盒**：它的 bash、read、edit、write 用你這個 Linux 帳號的全部權限跑。aos 只加 `--no-approve`（不載工作區 `.pi/` 裡的設定與外掛）。

## 要先有的東西

1. **`pi` 與它要的 `node` 都要在 aos 起它的那個環境的 PATH 上**。pi 的啟動檔第一行是 `#!/usr/bin/env node`：只有 `pi` 在 PATH、`node` 不在，會退 127（aos 回 `CliFailed … exit 127: pi, or the node it runs on, is not on PATH`）。公司 WSL 實況（11-18）：`~/.local/bin/pi` → `~/.pi/agent/bin/pi`（使用者自己裝的，1.5.2），`node` 只有 nvm 的 `~/.nvm/versions/node/v24.19.0/bin/node`，非互動的 `bash -lc` 找不到。最省事的做法是在**樹的 `env.sh`**（`~/aos-home/env.sh`，「下面可以加這棵樹自己的 export」那份）加一行，之後起根的視窗都帶著：

   ```sh
   export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$HOME/.local/bin:$PATH"
   ```

   node 換版本時這行要跟著改。不改 `~/.bashrc` 也行；改了 `~/.bashrc` 但起樹的殼沒讀到，一樣找不到。
2. **登入**：用 pi 自己登 ChatGPT 訂閱（使用者 11-18 已在公司 WSL 登過）：在終端機跑 `pi`，打 `/login`，選 OpenAI（Sign in with ChatGPT）。登入檔在 `~/.pi/agent/auth.json`，aos 不讀不改。
3. 想釘版（使用者裁了不釘，這段只當參考）：在一個專用資料夾 `npm install --ignore-scripts --save-exact @earendil-works/pi-coding-agent@<版本>`、留 `package-lock.json`，之後 `npm ci` 重裝，PATH 指那裡的 `node_modules/.bin`；理由與事故表見 [05-供應鏈](../../thinking/2026-11/18/eca-pi/05-供應鏈.md)。

## 一輪怎麼跑（11-18 實測 pi 1.5.2）

aos 起的是：

```
pi --mode json --no-approve --session-dir $AOS_STACK/pi/pi-sessions --session-id <id> [cli.json 的 flags、print_flags] [-e <小格>/pi-aos-mcp.mjs] [--append-system-prompt <system 檔>]   < 題目
```

| 事 | 怎麼做 | 實測 |
|---|---|---|
| 題目 | 只給 stdin、不給參數 | stdin 就是題目 |
| 第一輪 | aos 產一個 uuid 給 `--session-id`，交出去那一刻寫小格的 `session.txt` 與 `.session_home` | pi 在 `pi-sessions/` 建 `<時間>_<id>.jsonl`，stderr 印一行 `Warning: No project session found with id …; creating a new session with that id.`（正常，第一輪都有） |
| 之後 | 同一個 id 再給一次 | 是「接著那段」，不是開新的（送給模型的訊息一輪比一輪多） |
| 回答 | 最後一則 `role` 是 assistant 的 `message_end` | 之後還有 `agent_end`、`agent_settled`，行程隨後結束 |
| 失敗 | 那則 assistant 的 `stopReason` 是 `error`／`aborted`＝`CliFailed`，原因取它的 `errorMessage` | **模型那邊出錯 pi 照樣退 0**；模型名不認得才退 1 |
| 事件 | 一行一行接進小格的 `live.jsonl` | `aos-agent watch` 看得到 |

失敗不分暫時或永久（跟 codex 一樣：這批信記 failed、記冷卻、fire `brain_failed`）；pi 自己會先重試幾次。

## cli.json

```json
{"kind": "pi", "flags": [], "timeout_ms": 0}
```

- `flags`／`print_flags`：照原樣接在後面。aos 自己加、你不能再寫的（寫了＝`CfgBad`）：`--mode`、`-p`／`--print`、`--session`、`--session-id`、`--session-dir`、`--no-session`、`--fork`、`-c`／`--continue`、`-r`／`--resume`、`-a`／`--approve`、`-na`／`--no-approve`。
- 模型：`llm.json` 的 `model` 補成 `--model`（pi 的寫法是 `供應商/id`，`pi --list-models` 列得出來；ChatGPT 訂閱的供應商叫 `openai-codex`，例 `openai-codex/gpt-6.1-sol`）；範本的 `llm.json` 是 `{}`＝用 pi 自己的預設（登入時選的）。
- **改指 OpenAI 相容端點**（例：litellm proxy `http://localhost:4000/v1`）：pi 的 provider 設定在帳號資料夾的 `models.json`。不想動 `~/.pi/agent`，就另開一個帳號資料夾、在起樹的環境設 `PI_CODING_AGENT_DIR`：

  ```json
  {"providers": {"litellm": {"baseUrl": "http://localhost:4000/v1", "api": "openai-completions",
                             "apiKey": "$LITELLM_KEY", "models": [{"id": "<proxy 上的模型名>"}]}}}
  ```

  `llm.json` 寫 `{"model": "litellm/<proxy 上的模型名>"}`。`apiKey` 寫 `$變數名`＝從環境變數讀，不要把值寫進檔。換帳號資料夾＝aos 當成換了一個帳號，下一輪開新對話（帶 aos 的紀錄過去）。
- `system`（`interfaces.json` 宣告了才有）：用 `--append-system-prompt <檔>` 附加；pi 一輪一個行程，所以每輪重讀，改了下一輪就生效。
- `tools`：同 eca-claude（範本是同一份 `tools.json`）。工具名 `mcp__aos__<名>`，直接給模型看（exposure `direct`）。
- `mcp_servers`（外部 MCP）：pi 身還沒接，寫了＝`CfgBad`。`settings`、`tools_sub`、`live_mail`、`a2a` 是 claude 專屬。

## 11-18 實跑（公司 WSL，暫存樹，照[重建步驟單](../../thinking/2026-11/17/重建步驟單.md)起 start-eca 再掛一隻 eca-pi）

- **假端點**（只聽 127.0.0.1、固定回一句的 OpenAI 相容端點，`PI_CODING_AGENT_DIR` 指暫存夾的 `models.json`）：問一句、續問一句（假端點回「這是第 2 則 user」＝同一段對話）、叫 aos 工具 `mcp__aos__peek_now_time`（經外掛接上、拿到時間）、`/status`、`/compact`（history 換成摘要、同一個 id）、`ctl stop`＋`ctl start`、`ctl set-def` 換到另一份定義，之後都接著同一段對話。`aos-agent open`＝`ScreenMissing`（範本沒宣告 screen）。
- **真模型**（使用者自己 `/login` 的 ChatGPT 訂閱，`llm.json` 是 `{}`）：pi 預設用的是 `openai-codex/gpt-6.1-sol`。問一句、續問一句（答得出上一句叫它回什麼）、叫 pi 自己的 bash 列檔、叫 aos 的 `mcp__aos__peek_now_time`，四句都對。

## slash 指令

| 信 | pi 身怎麼做 |
|---|---|
| `/compact [指示]` | json 模式不認（11-18 實測：當成一般題目交給模型）。aos 另起一次 `pi --mode rpc` 接同一段對話、送 `{"type": "compact"}`（帶指示＝`customInstructions`），**等到它回 response 才關 stdin**（先關＝pi 收工、壓縮被取消）。成功＝history 換成 pi 的摘要一則（原文搬到 `history_removed.jsonl`）；pi 嫌對話太短不壓＝history 不動、回它的原因 |
| `/clear` | 同 codex：history 清掉、刪 `session.txt`，下一封開新對話 |
| `/status` | 照常 |
| `/goal …`、`/usage` | 回一句不支援，不交給 pi |
| `/exit` | 沒畫面，回一句 |

## 已知限制

- 沒有畫面：`aos-agent open`＝`ScreenMissing`（範本沒宣告 screen；自己硬加了 screen 的定義開起來＝`ScreenBad`）。要看它做了什麼，看小格的 `live.jsonl` 或 `pi-sessions/` 那份對話檔。
- 回答途中不收信：這輪在答時來的信等下一輪。
- 權限全開：pi 沒有核准模式、沒有白名單，aos 的 `before_tool`／`after_tool` hook 只看得到 aos 的工具。要擋得寫 pi 外掛（TypeScript）或整隻放容器，使用者 11-18 裁「先全開」。
- `--no-approve` 擋不到的：工作區的 `AGENTS.md`／`CLAUDE.md` pi 一律讀。
- `context_wrap`：pi 的事件有 token 數、沒有 context 視窗，要在 hook 格寫 `config.window`；範本沒放這格（pi 快滿時自己會壓）。
- aos 工具的外掛是 aos 每輪生成的一行 JavaScript（`pi-aos-mcp.mjs`，只呼叫 `pi.registerMcpServer`）；pi 的外掛 API 改了它就會壞。
- 失敗不分暫時或永久（同 codex）。
