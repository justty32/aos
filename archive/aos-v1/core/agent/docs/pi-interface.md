# pi 當 aos agent 的終端機介面：調查與結論

## pi 是什麼（實測）

以下 `PI` 是 `/home/lorkhan/.local/share/fnm/node-versions/v24.14.1/installation/bin/pi`；實體是
`@earendil-works/pi-coding-agent/dist/cli.js`。調查版本固定為 0.84.2。

- 身分：`$PI --version` 輸出 `0.84.2`；`$PI --help` 首行是
  `pi - AI coding assistant with read, bash, edit, write tools`。所以它是有 TUI、session、模型與
  tool loop 的 LLM coding-agent CLI，不是單純 readline 外殼。
- 主 help 列出的子命令 help 全部實跑（皆 exit 0）：

  ```text
  $ for s in install remove uninstall update list config auth; do $PI $s --help; done
  install <source> [-l]       Install a package and add it to settings
  remove <source> [-l]        Remove a package and its source from settings
  uninstall                   Alias for remove
  update [source|self|pi]     Update pi, packages, or model catalogs
  list                        List installed packages from user/project settings
  config [-l]                 Open resource configuration TUI
  auth                        print-api-key | print-bearer-token | check
  $ $PI auth check --help     # 三個 auth 子命令共用同一份 usage；exit 0
  ```

- 非互動模式可用，而且 prompt 可由 stdin 進、純文字由 stdout 出：

  ```text
  $ printf 'Reply with exactly PI_STDOUT_OK and nothing else.\n' | PI_OFFLINE=1 \
      timeout 120 $PI --no-session --no-tools --no-context-files \
      --provider lmstudio --model qwen/qwen3.5-9b --thinking off -p 2>/dev/null
  PI_STDOUT_OK
  [exit=0]
  ```

- 自訂 OpenAI 相容 provider 可用。本機已經這樣設定，並非推測：

  ```text
  $ jq '{providers:(.providers|with_entries(.value|={baseUrl,api,models:[.models[]|{id}]}))}' ~/.pi/agent/models.json
  {"providers":{"lmstudio":{"baseUrl":"http://localhost:1234/v1",
    "api":"openai-completions","models":[{"id":"qwen/qwen3.5-9b"},
    {"id":"google/gemma-4-e4b"},{"id":"google/gemma-4-12b-qat"}]}}}
  $ PI_OFFLINE=1 $PI --list-models lmstudio
  lmstudio  google/gemma-4-12b-qat ...
  lmstudio  google/gemma-4-e4b ...
  lmstudio  qwen/qwen3.5-9b ...
  [exit=0]
  ```

  0.84.2 自帶的 `docs/models.md` 規定 `~/.pi/agent/models.json` 格式為
  `{"providers":{"NAME":{"baseUrl":".../v1","api":"openai-completions",
  "apiKey":"dummy-or-$ENV","models":[{"id":"MODEL"}]}}}`；API 另支援
  `openai-responses`、`anthropic-messages`、`google-generative-ai`。extension 也能用
  `pi.registerProvider()` 寫完全自訂的 `streamSimple`。唯讀
  `curl -sS http://localhost:1234/v1/models` 實際列出上述三個模型與一個 embedding 模型；
  沒呼叫 load/unload。
- 自訂工具可用；內建 MCP 不可用：

  ```text
  $ rg -n 'registerTool|No MCP|MCP server integration' <pi-package>/README.md <pi-package>/docs
  docs/extensions.md: ... register custom tools callable by the LLM via pi.registerTool()
  README.md: ... MCP server integration
  README.md: **No MCP.** ... build an extension that adds MCP support.
  ```

  因此可用 `--extension FILE`／`~/.pi/agent/extensions/`／`.pi/extensions/` 掛自訂 tool；
  MCP server 沒有 settings 欄位或內建 client，只能另寫／安裝 MCP bridge extension。
- 「回覆由外部程式產生、不打 LLM」做得到，但入口是 extension API，不是 provider 設定。
  我在 `/tmp` 放 8 行 extension：`input` handler 執行 `printf`、`pi.sendMessage(...,
  display:true)`，最後回 `{action:"handled"}`。隔離設定下實跑 RPC：

  ```text
  $ PI_CODING_AGENT_DIR=/tmp/pi-aos-investigation PI_OFFLINE=1 $PI --mode rpc \
      --no-session --no-tools --no-context-files -e /tmp/pi-aos-investigation/external-reply.ts
  > {"id":"probe-1","type":"prompt","message":"hello"}
  < {"type":"message_start","message":{"role":"custom","customType":"external",
      "content":"EXTERNAL_REPLY:hello","display":true,...}}
  < {"id":"probe-1","type":"response","command":"prompt","success":true}
  ```

  真 TUI 再輸入 `hello`，畫面也出現 `[external] EXTERNAL_REPLY:hello`，未進模型流程。
  這證明 pi 可以只當 UI；尚未證明 `say`＋長駐 `listen` 的完整 adapter 已完成。
- 設定／狀態位置實際檢查：

  ```text
  $ ls -la ~/.config/pi        # No such file or directory（exit 2）
  $ ls -la ~/.pi/agent
  AGENTS.md  auth.json  models-store.json  models.json  sessions/  settings.json
  $ find ~/.pi/agent/sessions -type f | wc -l
  42
  $ ls -la .pi                # 此 worktree 不存在（exit 2）
  $ PI_OFFLINE=1 $PI list --no-approve
  No packages installed.
  ```

  全域 settings 是 `~/.pi/agent/settings.json`，模型是 `models.json`，憑證是
  `auth.json`，session 在 `sessions/`；專案設定是 `.pi/settings.json`。沒有 `--config`：
  `$PI --config /tmp/x` 實跑為 `Error: Unknown option: --config`（exit 1）；測試隔離應用
  `PI_CODING_AGENT_DIR=/tmp/...`，session 另可用 `--session-dir`。

## 三種接法與各自的代價

| 接法 | 做得到嗎 | 工與代價 |
|---|---|---|
| A. pi 當純 REPL 外殼 | **可以，靠 extension，不是裸 pipe。** `input` handler 把文字交給 `aos agent say` 並回 `handled`；背景 reader 把 `aos agent listen` 輸出轉成 `display:true` custom message。 | 最貼合「思考仍在 aos」。需約數十行 TS 管 child lifecycle、取消、錯誤、斷線重連、行分幀／游標；`handled` 不會自動畫出使用者訊息，也要由 extension 補畫。pi 版本升級時要驗 extension API。 |
| B. OpenAI provider 指向 aos shim | **可以。** `models.json` 已證明端點可換；shim 實作 `/v1/chat/completions`（最好含 SSE），收到最後一則 user message 後 say，等 listen 再回 completion。 | 工較大且語意造假：pi 會把 aos 當 LLM、重送自己的 history/system/tools；shim 必須做 HTTP、串流、取消與重複訊息判定，還形成 pi session 與 aos history 兩份真相。 |
| C. MCP／工具掛 say/listen | **custom tool 可以；內建 MCP 不行。** MCP 要 bridge extension。 | 不符合本題核心：tool 是由 **pi 的 LLM** 決定何時呼叫；若禁止 pi 的 LLM，仍得用 A 的 `input` interception。會多一層模型與 tool loop。 |

## 結論：建議走哪一條，為什麼

建議 **A：專用 pi extension**。它是唯一既保留 pi 的編輯器／TUI，又能用 `handled` 機械式保證
不呼叫 pi provider、讓 `aos agent step` 保持唯一思考者的路。不要把 MCP/tool 當 transport；
provider shim 只適合無法使用 extension API 時備援。

所以 `aos agent talk --interface pi` **能接，但不是「直接轉接 stdin/stdout」的一行包裝**；
它實際上要啟動 pi 加一個受控 extension。0.84.2 的 API 已實測足以做 UI 半邊，另一半取決於
`listen` 的輸出邊界與生命週期。

## 如果現在就要接：最小步驟

1. 寫一個 `aos-pi-interface.ts`：從 env 讀 folder/name；`session_start` spawn
   `aos agent listen <folder> <name>`，逐個完整 record 呼叫 `pi.sendMessage({customType:
   "aos-agent",content,display:true})`；`input` 事件 exec `aos agent say <folder> <name> <text>`
   並回 `handled`；`session_shutdown` 終止 listener。
2. `aos agent talk ... --interface pi` 設 env 後 exec：
   `pi --offline --no-session --no-tools --no-context-files --no-skills
   --no-prompt-templates --no-extensions --no-approve -e /absolute/path/aos-pi-interface.ts`。
   `--no-extensions` 仍允許明示的 `-e`；這可避免其他 extension 偷接 input。
3. 驗收：故意給無效 provider/API key仍能對話；確認 pi 沒有 HTTP 模型請求；連說兩句、
   agent 跨數回合輸出、Ctrl-C、listener 死掉／重啟、中文與多行內容都不漏不重。

沒有新增 `pi_interface_probe.sh`：雖然 8 行能證明「外部程式回覆可顯示且不打 LLM」，完整
`say`／持續 `listen` adapter 無法在十行內誠實處理生命週期與分幀，不符合加分項條件。

## 卡住的地方 / 還沒查清楚的

- 此 worktree 調查開始時尚無可執行的 `aos agent say/listen`，所以沒做端到端對話；它們由別隊實作。
- 必須凍結 `listen` 的 framing（逐行、JSONL、或純 byte stream）及「從目前尾端／從頭」語意，
  否則 extension 無法可靠地把一次 append 變成一則畫面訊息，也無法避免重連後重播。
- `log.md` 同時含思考與對外說話；若介面要用不同樣式，`listen` 必須提供可辨別的 record type。
- 尚未做 pi 版本升級相容性、listener crash/backpressure、terminal resize、Windows 的驗證。
