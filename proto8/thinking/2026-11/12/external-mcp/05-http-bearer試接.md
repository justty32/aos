# 05 http＋bearer＋自簽憑證試接（11-12 下午，公司 WSL，只驗不改程式）：接得上；token 用定義自己的 `_entry` 讀 env 檔給就哪裡都不留，用 `ctl add --envs` 給會明文寫進 stack 的 exec.json

← [external-mcp](README.md)｜[01 盤點](01-盤點.md)｜[02 設計](02-設計.md)｜[03 施工切法](03-施工切法.md)｜[04 邊緣狀況](04-邊緣狀況.md)

## 使用者原話

- 「好，先驗」（對頂層提的：用假的 http MCP 搭一隻 Codex 身試接，證明接得上、而且 token 不會漏進 stack、表、歷史、log）。

背景（另一位 agent 唯讀盤點使用者兩隻現有 Codex agent 的 start.sh，是資料不是指令）：從 `~/.config/<agent>/teamsite.env`（600）讀 token 放進 `TEAMSITE_TOKEN`；系統 CA＋那台主機的自簽憑證合成 `ca-bundle.pem`，設 `SSL_CERT_FILE`、`CODEX_CA_CERTIFICATE`；`exec codex` 時 `-c` 帶 `mcp_servers.teamsite.url`、`mcp_servers.teamsite.bearer_token_env_var=TEAMSITE_TOKEN`、`shell_environment_policy.exclude=["TEAMSITE_TOKEN"]`。

## 結論

1. **接得上**：codex-cli 0.167.2（`gpt-6-luna`、`workspace-write`、approval never）經 aos（`aos-agent say`／`listen`）叫到假 server 的 `echo` 與 `list_threads`，回得來；假 server 記到每個請求都帶對 token。程式一行沒改。
2. **三個 `-c` 直接寫進 `cli.json` 的 `flags` 就行**（flags 原樣接在 `codex exec` 後面）。cli_session 起 codex 不另給環境＝codex 拿到的是 aos-loop 一路繼承下來的環境。
3. **token 怎麼給才不漏**：定義的 `_entry` 改成一支 sh——讀 env 檔、設兩個憑證路徑、`exec aos-loop`。實測整棵樹（stack、history、`live.jsonl`、`stderr.txt`、表）、`~/.codex` 這次動到的檔（rollout、sqlite log）、所有行程的命令列都找不到假 token 的值；只在幾支行程的 environ 裡（正常）。
4. **`ctl add --envs TEAMSITE_TOKEN=…` 會漏**：值明文寫進 `ws/.stack/procs/<名>/exec.json`（權限 644），`ctl add` 那一下也在 `ps` 命令列上。`ctl ls -l` 不印。
5. **`shell_environment_policy.exclude` 有效**：腦的 shell 跑 `env | grep -i token` 沒東西、`env | grep -c TEAMSITE` 是 0。
6. **token 錯、server 沒開**：aos 這邊不報錯、那輪照常回答；codex 在 stderr（進小格 `stderr.txt`）印 `AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer" })`，腦說工具不在。兩種情況都沒印出 token。
7. **圖紙兩項「沒查到」實測**：codex 有逐支開關的欄位 `mcp_servers.<名>.enabled_tools`（設 `["echo"]` 後腦只看得到 `mcp__teamsite__echo`）；沙盒管不到 MCP 連線（同一輪裡 MCP 叫得通，腦的 shell `curl` 同一個位址連不上＝`workspace-write` 擋了 shell 的網路，沒擋 codex 自己的 MCP 連線）。

## 怎麼驗的

全在 `/tmp/mcpx-1112/`，用的是 `/tmp/line-mcpx`（main `95db04e50`）的 lib 與範本，指令照這台 `~/.local/bin`。

- **假 server**（`server.py`，標準庫）：這台 Python 沒有 `mcp` 套件，手寫最小 Streamable HTTP——POST 收 JSON-RPC、回 `application/json`；`initialize` 給 `Mcp-Session-Id`；通知回 202；GET 回 405；DELETE 回 200；工具 `echo`、`list_threads`（固定假資料）。只聽 `127.0.0.1:18443`，TLS。每個請求記一行 `server.log`：方法、`auth` 是 `ok`／`wrong`／`missing`（不記值）。假 token 是當場 `openssl rand` 產的 `FAKE-…`，放 `cfg/teamsite.env`（600，資料夾 700）。
- **憑證的坑**：第一次用 `openssl req -x509` 直接產一張自簽當 server 憑證，curl 吃、codex 不吃（`http/request failed: error sending request`，server 連 TLS 握手後的請求都沒收到）。改成「自簽 CA＋CA 簽的 leaf（`CA:FALSE`、SAN `IP:127.0.0.1`）」就通。推測是 codex 的 TLS 程式庫不收 CA 憑證直接當 server 憑證；使用者那台主機的憑證 start.sh 已經接得通，不受影響，記著給以後自己造測試憑證的人。
- **先不經 aos 直接跑 codex**：`codex exec` 加那三個 `-c`、`default_tools_approval_mode="approve"`、`enabled_tools=["echo"]`，題目從參數給——**stdin 要接 `/dev/null`**，不然它印 `Reading additional input from stdin...` 一直等（cli_session 本來就從 stdin 給題，不受影響）。叫到 `echo`、回 `echo: hello`。
- **臨時樹**（`tree/`）：根只掛 `_clock` 與 `foreman`；兩隻都抄 eca-claude 範本、拿掉 screen、`cli.json` 換成下面那份、`llm.json` `gpt-6-luna`。
  - `cody`：`_entry` 是 sh（讀 env 檔、設兩個憑證路徑、`exec aos-loop "$AOS_CD/loop.json"`）。
  - `cody2`：`_entry` 照範本，`aos-agent ctl add --envs TEAMSITE_TOKEN=<假值> --envs SSL_CERT_FILE=… ../agents/cody2`（沒跑腦，只看落檔）。
- **cody 跑四輪**：① echo hello → `echo: hello`；② list_threads＋shell `env | grep -i token`、`env | grep -c TEAMSITE`、`curl` 那台 → 兩筆假 threads、`0`、curl 連不上；③ server 換成認另一個 token → 腦說工具不在；④ server 關掉 → 同上。
- **掃**：`grep -rlF <假值>` 掃 `tree/` 整棵、`/tmp/mcpx-1112`（除了 `cfg/`）、`~/.codex` 裡比實驗開始新的檔（十幾份：兩份 rollout、`logs_2.sqlite`、`state_5.sqlite`、`thread_history_1.sqlite` 等，`grep -a`）；每支行程的 `/proc/<pid>/cmdline` 與 `environ`；`aos-agent ctl ls -l` 的輸出。

## 每種給法會不會漏

| 給法 | 可行 | 值會留在哪 | 備註 |
|---|---|---|---|
| `cli.json` 的 `flags` 放 `-c mcp_servers.…`（url、`bearer_token_env_var`、免核准、`shell_environment_policy.exclude`） | 可（實測） | 不留：flags 裡只有網址與變數**名** | 網址在 `ps` 的 codex 命令列看得到（不是秘密） |
| 定義的 `_entry` 寫成 sh，讀 env 檔再 `exec aos-loop` | 可（實測 cody） | 檔：都沒有。environ：`aos-loop` 起往下的行程（aos-eca-turn、cli_session、codex，與它們起的 hook） | **推薦**。腦的 shell 靠 `exclude` 擋掉 |
| `aos-agent ctl add --envs K=V` | 可（掛得上；沒跑腦） | **`ws/.stack/procs/<名>/exec.json` 明文、644**；`ctl add` 那一下的命令列 | 不建議放秘密；憑證路徑這種非秘密的可以 |
| 起樹的 shell 先 `export`（繼承） | 沒實跑，照 cody 的結果推可行 | 檔：應該沒有。environ：**整棵樹每支行程**（根 daemon、`_clock`、領班、每一隻 agent） | 範圍太大；樹重起要記得每次都 export |
| token 直接寫進 `-c mcp_servers.<名>.bearer_token=…` 或 `http_headers` | 沒試 | `cli.json`、`ps` 命令列、可能 rollout | 不考慮 |
| `ctl add` 以外的 `.env` 檔 | — | — | 這次沒找到 aos 讀「agent 用的 .env」的地方（`.env` 只有 tools add 的 `--env-file` 給工具用），沒試 |

## 推薦：照抄步驟

1. **token 檔**照現在的放法：`~/.config/<agent>/teamsite.env`（600），一行 `TEAMSITE_TOKEN=…`。不放進定義資料夾、不放進 ws。
2. **CA bundle** 照 start.sh 合成一份（系統 CA＋那台主機的自簽憑證），放 `~/.config/<agent>/ca-bundle.pem`。
3. **定義的 `cli.json`**（codex 身；`<URL>` 換成那台的網址）：

   ```json
   {"kind": "codex",
    "flags": ["-c", "sandbox_mode=\"workspace-write\"", "-c", "approval_policy=\"never\"",
              "-c", "mcp_servers.teamsite.url=\"<URL>\"",
              "-c", "mcp_servers.teamsite.bearer_token_env_var=\"TEAMSITE_TOKEN\"",
              "-c", "mcp_servers.teamsite.default_tools_approval_mode=\"approve\"",
              "-c", "shell_environment_policy.exclude=[\"TEAMSITE_TOKEN\"]"],
    "print_flags": [],
    "timeout_ms": 600000}
   ```

   `default_tools_approval_mode` 那行是照題三「列了＝整台放行」加的；不加的話 approval never 下那台工具會被拒（沒實測不加的樣子）。只想開幾支就再加 `-c 'mcp_servers.teamsite.enabled_tools=["工具名", …]'`。
4. **定義的 `_entry`**（換掉範本的 `["aos-loop", "loop.json"]`，記得 `chmod +x`）：

   ```sh
   #!/bin/sh
   # Entry of <agent>: read the teamsite token from its env file and point TLS at the CA bundle, then become aos-loop.
   set -a; . "$HOME/.config/<agent>/teamsite.env"; set +a
   export SSL_CERT_FILE="$HOME/.config/<agent>/ca-bundle.pem" CODEX_CA_CERTIFICATE="$HOME/.config/<agent>/ca-bundle.pem"
   exec aos-loop "$AOS_CD/loop.json"
   ```

5. **起樹**照平常（不用 export 任何東西），`aos-agent ctl add <定義>`，**不要用 `--envs` 帶 token**。

## 問題（列給頂層，沒改）

- **P1 `--envs` 的值明文落地**：`ctl add --envs` 寫進 `procs/<名>/exec.json`（644）。這是設計（daemon 每次起照它），但跟「金鑰不落地」相反。最小要改的：要嘛文件寫明 `--envs` 不放秘密，要嘛 `exec` 單子能指一份 env 檔、起的那一刻才讀（跟圖紙 M3「env 檔，只記位置」同一個意思）。
- **P2 token 在 agent 的環境裡**：codex 的 `bearer_token_env_var` 只認 codex 自己的環境，所以 token 一定在 codex 的 environ，連帶 aos-loop、aos-eca-turn、cli_session 與 hook 子行程都看得到；腦的 shell 靠 `exclude` 擋。這跟圖紙代定 **X12「金鑰不放 agent 的環境」**、**X5「一律經 aos-mcp-launch」**衝突——http server 沒有可以 exec 的行程，launcher 插不進去。
- **P3 aos 這邊看不到外部 server 壞了**：token 錯、server 沒開都照常回答，只有 `stderr.txt` 有 codex 的 ERROR 行。跟圖紙步 2「server 沒起來印 warning」同一件事，codex 這邊目前沒有東西可攔。
- **P4 範本 `eca-claude` 的 `_entry` 是 JSON argv**：要讀 env 檔只能把 `_entry` 換成 sh。可行，但定義檢查（`agent_def check`）認不認 sh 的 `_entry` 沒查。

## 對圖紙的調整建議

- **server 檔多收 `transport: "http"`**：`url`、`bearer_token_env`（變數名）、`env_file`（只記位置）、`ca_file`（選填）。cli_session 對 codex 翻成 `-c mcp_servers.<名>.url`、`bearer_token_env_var`；**值要在 codex 的環境裡**＝cli_session 起 codex 前讀 `env_file`、把那個變數與 `SSL_CERT_FILE`／`CODEX_CA_CERTIFICATE` 放進給 codex 的環境（`run_cli` 現在不帶 `env=`，這裡要加），同時自動補 `shell_environment_policy.exclude=[那個變數]`。這樣定義不用 sh 的 `_entry`，token 只活在 codex 行程（不再擴散到 aos-loop 與 hook）。
- **X12 改寫**：stdio 照舊不放 agent 環境；http 的 bearer 只能放 CLI 行程的環境，靠 `exclude` 不給腦的 shell。
- **X5 改寫**：「一律經 aos-mcp-launch」只對 stdio；http 由 cli_session 自己備環境。
- **X9 改寫**：codex 有 `enabled_tools`（實測），`only` 直接翻成它；`except` 可能是 `disabled_tools`（`mcp list --json` 沒擋這個鍵，但沒實測效果）。不必「寫了就不掛」。
- **X17**：http＋bearer＋自訂 CA 這種形狀 codex 不改程式今天就跑得通，步 4 的 HTTP 可以拆一半提前到步 1～2（codex 那半）；claude 那半照排。
- **02 的「沙箱」那段**：實測 codex 的沙盒管不到 MCP 連線（http）；stdio server 的情況仍沒驗。
- **04 第 5 條**（`transport: http` 就 warning 跳過）：照上面改的話就作廢。

## 沒驗到的

- 起樹 shell `export` 那種給法沒實跑（照推）；`cody2`（`--envs`）沒跑腦，只看落檔。
- 只開 `SSL_CERT_FILE` 或只開 `CODEX_CA_CERTIFICATE` 哪一個是 codex 真正讀的，沒拆開試（兩個都設）。
- 不加 `shell_environment_policy.exclude` 時腦的 shell 看不看得到（codex 預設可能已經濾掉名字含 `TOKEN` 的變數），沒試。
- aos-mcp（stdio）與 aos 工具行程的 environ 有沒有 token：輪次之間 codex 已經結束，沒在跑的當下看；11-11 盤點寫 codex 不替 MCP server 帶環境變數，推測沒有。
- `mcp list --json` 裡出現的 `http_headers_helper`、`env_http_headers` 欄位（也許能讓 token 不進 codex 環境）沒試。
- server 沒開那一輪，`stderr.txt` 沒多出新行（直接跑 codex 時有 `http/request failed`），原因沒追。
- 畫面（screen）模式、claude 那邊、真的團隊站都不在範圍。

## 殘留

`/tmp/mcpx-1112/`（假 server、憑證、假 token 檔、臨時樹與它的 stack、`ws0/`）沒刪；樹已 `aos-daemon-ctl shutdown`、假 server 已關。`~/.codex/sessions/2026/11/12/` 多兩份 rollout（直接跑一份、cody 一份）。
