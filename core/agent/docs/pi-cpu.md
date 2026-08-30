# pi 當 aos agent 的 LLM CPU：實測與接法

這裡的「pi 當 LLM CPU」是指：世界仍以 inst 推進回合，只是在一條
`aos agent step` inst 裡呼叫本機的 `pi` 程式完成一次思考與工具操作。這個方向取代
[pi-interface.md](pi-interface.md) 把 pi 當成「介面／TUI」的規劃；pi 現在是第二顆思考引擎，
不是包在既有 agent 外面的終端介面。

## 調查：provider 怎麼選的

調查時使用的 pi 與版本是：

```text
$ which pi
/home/lorkhan/.local/share/fnm/node-versions/v24.14.1/installation/bin/pi

$ pi --version
0.84.2
```

使用者指定的 DeepSeek provider 已可用，pi 也能列出兩個模型：

```text
$ PI_OFFLINE=1 pi auth check --provider deepseek
ready

$ PI_OFFLINE=1 pi --list-models deepseek
provider  model              context  max-out  thinking  images
deepseek  deepseek-v4-flash  1M       384K     yes       no
deepseek  deepseek-v4-pro    1M       384K     yes       no
```

憑證來自環境變數 `DEEPSEEK_API_KEY`。`~/.pi/agent/auth.json` 沒有 deepseek 條目，
只有 anthropic、lmstudio 與 openai-codex，因此可確定是 pi 自己讀取環境變數；不需要傳
`--api-key`。**執行 `aos agent step` 的行程（也就是 loop）必須在環境裡有
`DEEPSEEK_API_KEY`，否則 pi 會失敗。** 不要把 key 的值寫進設定檔或紀錄。

備案是本機 `lmstudio` provider：`~/.pi/agent/models.json` 的 `baseUrl` 已設為
`http://localhost:1234/v1`，`pi auth check --provider lmstudio` 也是 `ready`，並有
`qwen/qwen3.5-9b` 等三個模型。離線路徑可走，但這次依使用者決定採 DeepSeek。

## `pi -p --mode json` 的輸出

stdout 是 JSONL（一行一個事件），不是單一 JSON。實跑「在目前資料夾建一個
hello.txt 內容是 hi，然後說你做了什麼」得到 85 行、47 KB；
`message_update` 的數十筆串流增量可以全部忽略。事件骨架如下：

```jsonl
{"type":"session","version":3,"id":"f5ff17b3-4bd0-44d8-a288-b4beacb2c10d","cwd":"<world>"}
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"user","content":[{"type":"text","text":"在目前資料夾建一個 hello.txt 內容是 hi，然後說你做了什麼"}]}}
{"type":"message_update", ...}
{"type":"message_end","message":{"role":"assistant","content":[
    {"type":"text","text":"I'll create the file."},
    {"type":"toolCall","id":"call_00_61QLKWEewOEnYNveXNU62194","name":"write","args":{"path":"hello.txt","content":"hi"}}]}}
{"type":"tool_execution_start","toolCallId":"call_00_...","toolName":"write","args":{"path":"hello.txt","content":"hi"}}
{"type":"tool_execution_end","toolCallId":"call_00_...","toolName":"write","result":{"content":[{"type":"text","text":"Successfully wrote 2 bytes to hello.txt"}]},"isError":false}
{"type":"turn_end","message":{"role":"assistant","content":[...]}}
{"type":"turn_start"}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"我在目前資料夾（<world>）建立了一個 `hello.txt`，內容是 `hi`。"}]}}
{"type":"agent_end","messages":[ ... 這一次跑的完整對話 ... ]}
{"type":"agent_settled"}
```

取最終回覆的規則是：找到**最後一個 `turn_end` 事件**，把其中
`message.content` 所有 `type == "text"` 的區塊依序接起來。要觀察 pi 用過哪些工具，則讀
`tool_execution_start` 的 `toolName` 與 `args`。這次實跑的 exit code 是 0。

prompt 由 stdin 餵入，不放進 argv：

```sh
printf '...' | pi -p --mode json ...
```

實測連以 `--` 開頭的 prompt 都不會被誤認為選項；輸入
`--這行以兩個減號開頭，請直接回覆「收到」` 時，pi 正常回覆「收到」。

## session 記憶實測

同一 cwd、同一個 `--session-id` 連跑兩次：

```text
$ # 第一輪
$ printf '在目前資料夾建一個 hello.txt 內容是 hi，然後說你做了什麼' | pi -p --mode json ... --session-id $SID
→ 最後一個 turn_end：「我在目前資料夾（…）建立了一個 `hello.txt`，內容是 `hi`。」
→ real 2.1s，exit=0，世界資料夾真的多了 hello.txt（內容 hi）

$ # 第二輪，同一個 SID
$ printf '剛才建了什麼檔？' | pi -p --mode json ... --session-id $SID
→ 最後一個 turn_end：「剛才建了 `hello.txt`，內容是 `hi`（2 bytes）。」
→ real 1.0s，exit=0
```

第二輪 usage 顯示 `cacheRead: 1664`，表示 pi 確實帶回上一輪 context。session 記憶成立，
aos 不必自己維護供 pi 使用的對話歷史。

第一次使用某個 session id 時，stderr 會出現：

```text
Warning: No project session found with id '<uuid>'; creating a new session with that id.
```

這是正常訊息，exit 仍是 0。session 存在 `~/.pi/agent/sessions/`，以「專案（cwd）＋
session id」定位。

## 跟 `.aos/` 的互動

argv 加上 `--no-context-files`，pi 就不讀世界裡的 `AGENTS.md` 或 `CLAUDE.md`；system
prompt 另明講「不要去動 `.aos/`」作為保險。實測結束後用 `find <world>` 檢查，
`.aos/` 底下沒有任何檔案被 pi 改動，pi 只建立任務要求的 `hello.txt`。

這是目前的隔離約定，不是作業系統層的權限邊界：pi 的工具仍在世界資料夾內直接讀、寫與
執行命令。

## aos 怎麼接的

每個 agent 的引擎選擇放在 `<world>/.aos/agents/<name>/engine.json`。LM Studio 格式是：

```json
{"engine": "lmstudio"}
```

pi 格式是：

```json
{"engine": "pi", "provider": "deepseek", "model": "deepseek-v4-flash",
 "session_id": "<v4 uuid>"}
```

`engine.json` 不存在時視同 `lmstudio`，讓舊世界維持原行為；未知的 engine 值會報錯。
初始化選項如下：

```text
aos agent init [folder] [--name N] --engine pi [--provider P] [--model M]
```

不傳 `--engine` 時仍是 lmstudio。選 pi 時，provider 預設 `deepseek`，model 預設
`deepseek-v4-flash`，並自動產生一個 v4 UUID 作為 `session_id`。

engine=pi 時，`step` 走 `src/engine_pi.cpp` 的獨立 `step_pi` 分支：讀取 `say/*.md`；
沒有新訊息就直接寫 `status.json` 收工以節省 token；有訊息才組 prompt 並執行 pi；把最終
回覆寫進 `log.md` 與 `history.json`，最後寫 `status.json`。pi 失敗時會在 `log.md` 留下：

```text
> pi 失敗（exit=N）：…
```

失敗後 agent 仍靠 `.aos/every/` 活著，不會靜默死亡。這條分支不讀 `tools.json`，不呼叫 `aos llm`，也不做
pending 工具往返；read／bash／edit／write 等工具由 pi 在同一次呼叫內自行完成。

aos 實際執行的 argv 是：

```text
<AOS_PI_BIN 或 pi> -p --mode json
  --no-context-files --no-skills --no-prompt-templates --no-extensions
  --thinking off
  --session-id <engine.json 的 session_id>
  --provider <engine.json 的 provider>
  --model <engine.json 的 model>
  --append-system-prompt <persona 組出來的 system prompt>
```

cwd 是世界資料夾，prompt 從 stdin 傳入，timeout 為 10 分鐘。`AOS_PI_BIN` 是測試插銷，
可指向假的 pi 腳本；平常不設定就從 PATH 找 `pi`。

## 怎麼自己試一次

先確認執行 loop 的環境已有 `DEEPSEEK_API_KEY`，再從 repo 根目錄執行：

```sh
mkdir /tmp/W && cd /tmp/W
aos agent init --engine pi          # 一個資料夾一隻 agent，名字預設＝資料夾名
aos say "在這個資料夾建一個 hello.txt 內容是 hi"
aos run --step 1
aos listen --once
```

第一次建立 session 時看見「creating a new session」警告是正常的；應再檢查回覆、
`/tmp/W/hello.txt`，以及 agent 的 `log.md` 與 `status.json`。

agent 的存活靠 `.aos/every/agent-<name>.json`（loop 每回合複製一條 `step`），
pi 分支跟 lmstudio 分支一樣**不自我投遞**。

## pi 當 CPU 跟 `aos llm` 當 CPU 的差異與不順手處

兩條路都由 `aos agent step` 這條 inst 啟動思考，但工具迴圈、可觀測性與信任邊界不同。

| | `aos llm`（lmstudio） | `pi` |
|---|---|---|
| 工具 | aos 的 `tools.json` ＋ inst，三回合完成一次往返 | pi 自帶，一回合內做完 |
| 記憶 | `history.json`，aos 自己管理、看得到、可編輯 | pi 的 session，aos 只留鏡射 |
| 觀測 | 每次工具呼叫都是 inst，落在 `batch/<turn>/` | pi 內部做完才吐結果，中間 aos 看不到 |
| 可控 | 工具白名單就是 `tools.json` | pi 可以自行執行 bash 等工具 |
| 成本 | 本機、免費 | 呼叫 DeepSeek，要 API key、要付費 |
| 速度 | 依本機模型而定 | 本次實測約 1～4 秒 |

- **兩份真相：** 對話同時存在 pi session 與 aos `history.json`；後者只是鏡射，手動修改不會影響 pi。
- **inst 被繞過：** `step` 仍是 inst，但 pi 的工具動作不是 inst，不會出現在 `batch/<turn>/`。世界裡因此有一段 aos 看不見的行為，這是最大取捨，應由使用者決定能否接受。
- **session 綁 cwd：** 世界資料夾搬家後，同一 `session_id` 找不到舊 session，pi 會另開新 session。
- **沒有工具白名單：** 目前不限制 pi 能執行什麼；`--no-tools`／`--tools` 雖可收窄，但尚未接進 `engine.json`。
- **要錢、要網、要 key：** DeepSeek 路徑和本機 LM Studio 的離線、免費性質完全不同。
