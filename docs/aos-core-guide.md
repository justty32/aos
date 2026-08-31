# aos core 使用指南

這份文件描述目前 `main` 工作樹裡實際存在的功能。指令面以現有 17 個子命令、CLI parser、測試與已保存的真實 help dump 為準；舊 `core/inst`、`core/llms`、`core/tooljson` 文件已封存，不代表現在的 CLI。

## 1. 一分鐘總覽

`aos` 把一個普通資料夾當成一個「世界」。世界的機器狀態放在 `<folder>/.aos/`；外部程式把 instruction JSON 投進 `.aos/inbox/`，`aos run` 每回合收走當下的一批 instruction、並行執行、保存結果，再把回合號加一。

```text
生產者 ──deliver──> .aos/inbox/*.json
                          │
                     aos run（一回合）
                          │
          .aos/batch/<turn>/{insts,out}/ + state.json + turn
```

`.aos/every/` 是常駐 instruction：檔案不會被收走，而是在到期回合複製一份執行。agent 就靠這個機制每回合跑一次 `aos agent step`；heartbeat 也靠同一機制定期跑 `aos tick`。沒有獨立的 `init` 子命令：`run`、`deliver`、`agent init`、`heartbeat init` 都會按需建立版面。

目前有七個 core 小專案：

| 小專案 | 現在負責什麼 |
|---|---|
| `core/exec` | 純函式庫。POSIX `fork/exec` 批次執行器；一批全啟動後統一等待，收集 exit/signal、stdout/stderr、時間與 timeout。 |
| `core/wire` | 純函式庫。`Inst`、`Outcome`、`State` 與 JSON 互轉。 |
| `core/loop` | 世界版面、投遞、回合匯聚、並行執行、狀態、daemon 與停止；提供 `run`、`deliver`、`stop`。 |
| `core/llm` | 非串流 OpenAI-compatible `/chat/completions` client，加上跨行程 LLM 槽位；提供 `llm`。 |
| `core/tool` | 世界層工具 registry 與 agent 通訊錄；提供 `tool`、`contact`。 |
| `core/agent` | 一個資料夾一隻的回合制 agent、對話、信箱、工具往返與 LM Studio／pi engine；提供 `agent`、`say`、`listen`、`inbox`、`talk`、`state`、`chat`。 |
| `core/tick` | heartbeat、固定循環與一次性行程；提供 `tick`、`heartbeat`、`routine`、`schedule`。 |

`common/` 是共用 export header 與私有相依，`app/` 只把各小專案登記的子命令組成唯一的 `aos` 執行檔，兩者不是小專案。`modules/` 是可選擴充的容器，目前沒有實際 module。

## 2. 怎麼建置

### 平台與 WSL

根 `CMakeLists.txt` 在 `WIN32` 直接 `FATAL_ERROR`；這台 Windows 不能原生建置，必須在 WSL Ubuntu 內從 repo 根目錄執行：

```powershell
wsl -d Ubuntu -e bash -lc "cd /mnt/c/code/mine/simple_tools/aos && cmake --preset default && cmake --build --preset default && ctest --preset default"
```

目前 preset 明確使用 `Unix Makefiles`，不需要 Ninja。需求是 CMake 3.25+ 與 C++23 compiler；這台 WSL 的 CMake 3.28、g++ 13、make、ctest 可用。

### vcpkg 與 tests feature

這是 vcpkg manifest project。toolchain 的尋找順序是：呼叫者給的 `CMAKE_TOOLCHAIN_FILE`、`$VCPKG_ROOT`、`~/dev/vcpkg`。`nlohmann-json` 與 `curl[ssl]` 是基礎相依；Catch2 只在 manifest 的 `tests` feature。

presets 已帶 `VCPKG_MANIFEST_FEATURES=tests`。若不用 preset、又開著測試，必須自己加上它：

```powershell
wsl -d Ubuntu -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && cmake -S . -B build-manual -DCMAKE_BUILD_TYPE=Debug -DVCPKG_MANIFEST_FEATURES=tests && cmake --build build-manual -j$(nproc) && ctest --test-dir build-manual --output-on-failure'
```

漏掉 `-DVCPKG_MANIFEST_FEATURES=tests` 時，configure 會在根 `CMakeLists.txt` 的 `find_package(Catch2 3 CONFIG REQUIRED)` 失敗。只要不建測試，可用：

```powershell
wsl -d Ubuntu -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && cmake -S . -B /tmp/aos-build -DCMAKE_BUILD_TYPE=Release -DAOS_BUILD_TESTS=OFF && cmake --build /tmp/aos-build -j$(nproc)'
```

執行檔固定落在 `<builddir>/bin/aos`，共享／靜態函式庫落在 `<builddir>/lib/`。只能從 repo 根目錄 configure；各 core 子目錄不是獨立 CMake project。

## 3. 指令表

共同退出碼慣例是 `0` 成功、`1` 執行或資料錯誤、`2` 用法錯；下表只額外列出 parser 定義的差異。`75` 是暫時拿不到 LLM 槽，供下一回合重試，不算永久失敗。

| 指令 | 一句話用途 | 關鍵參數 | 退出碼 |
|---|---|---|---|
| `run` | 推進世界 N 回合或啟動 loop | `[folder] --step N --interval MS --daemon` | 0/1/2；訊號收線 130 |
| `deliver` | 原子投遞一條 instruction | `[folder] <inst.json>` 或 `[folder] -- <argv...>` | 0/1/2 |
| `stop` | 停掉該世界的無限 loop | `[folder]` | 0/1/2；沒在跑仍是 0 |
| `llm` | 呼叫 OpenAI-compatible endpoint | `--system --messages --url --model --timeout-ms --engine --priority --slots` | 0/1/2/75 |
| `tool` | 管理世界工具 registry | `add/ls/rm`、`--folder`、`--json` | 0/1/2 |
| `contact` | 管理／查看通訊錄 | `add/ls/rm/status`、`--folder-root`、`--json` | 0/1/2 |
| `agent` | 初始化或明確操作某隻 agent | `init/step/say/listen/talk/state` | 0/1/2；`step` 可回 75 |
| `say` | 對目前 agent 或聯絡人投遞訊息 | `[--to NAME] <text...>` | 0/1/2 |
| `listen` | 印出並跟讀對話 log | `[--once]` | 0/1/2 |
| `inbox` | 不叫 LLM 地列信、讀信、標已讀 | `ls [--json]`；`read [id] [--all] [--keep]` | 0/1/2 |
| `talk` | 從 stdin 逐行對話 | `[--interface pi]` | 0/1/2 |
| `state` | 輸出目前唯一 agent 的綜合 JSON 狀態 | 無參數 | 0/1/2 |
| `chat` | 建 agent、說一句、推到有回覆 | `--engine --provider --model --timeout` | 0/1/2 |
| `tick` | 機械式檢查一次到期事務 | `[folder] [--dry-run]` | 0/1/2 |
| `heartbeat` | 安裝常駐 tick instruction | `init [folder] [--interval D]` | 0/1/2 |
| `routine` | 管理固定循環事務 | `add/ls/rm`、`--every`/`--slot`、`--ask`/`-- argv` | 0/1/2 |
| `schedule` | 管理一次性行程 | `add/ls/rm`、`--at`、`--ask`/`-- argv` | 0/1/2 |

help 行為並不完全一致：`run`、`deliver`、`llm`、`tool`、`contact`、`agent`、`say`、`listen`、`talk`、`state` 的 `--help` 回 0；`inbox`、`chat`、`tick`、`heartbeat`、`routine`、`schedule` 沒有獨立 help 分支，`--help` 只會印 usage 並回 2；`stop` 根本沒有 help flag，`aos stop --help` 會把 `--help` 當 folder。

## 4. 逐個指令的用法

以下假設 `AOS=/path/to/build/bin/aos`，並在 POSIX shell 執行。省略 folder 時，多數世界層命令依序採用非空的 `AOS_FOLDER`、從 cwd 往上找到的最近 `.aos/` 世界、cwd。

### `run`

```sh
$AOS run [folder] [--step N] [--interval MS] [--daemon]
$AOS run ./world --step 3 --interval 500
```

預設一回合；`--step 0` 一直跑到訊號中斷。`--interval` 是沒有新投遞時兩回合間最長等待，前景預設 100 ms、daemon 預設 1000 ms；inbox 或 agent `say/` 有新檔時會提早醒。`--daemon` 隱含 `--step 0`。重複的 `--step`／`--interval` 會警告並採第一個值。

明確給的 folder 必須已存在且是資料夾。執行會建立／更新 `.aos/{inbox,every,agents}/`、`turn`、`state.json`、`run.lock`；有 instruction 才建立 `batch/<turn>/{insts,out}/`。無限 loop 另有 `run.pid`；daemon 把輸出 append 到 `run.log`。同一世界同時只能有一條 runner，靠 `flock(.aos/run.lock)` 保證。

### `deliver`

```sh
$AOS deliver ./world -- printf 'hello\n'
$AOS deliver ./world ./job.json
```

`--` 後每個 shell token 原樣成為 `argv`；自動 id 是 `d-<epoch_ms>-<pid>-<seq>`。檔案形式讀 instruction JSON；JSON 沒有 `id` 時採來源檔名去掉 `.json`。folder 位置只有在該參數當下確實是資料夾時才會被辨認，所以先 `mkdir world`。

成功時沒有 stdout，會按需建立世界版面，先寫 `.aos/inbox/<id>.json.tmp` 再 rename 成 `.json`。同 id 會覆蓋既有 inbox 檔。

### `stop`

```sh
$AOS stop ./world
```

讀 `.aos/run.pid`，先送 `SIGTERM`，每 100 ms 檢查一次；5 秒仍活著就送 `SIGKILL`。之後移除 `run.pid`。沒有 pid、pid 壞掉或行程已死時會清除陳舊 pid 並回 0；`run.lock` 與 `run.log` 不刪。

### `llm`

```sh
$AOS llm --slots
printf '只回一個字：好' | $AOS llm --system '回答要短。'
$AOS llm --messages messages.json --model qwen/qwen3.5-9b
```

一般模式把 stdin 全部當一則 user message；`--messages` 改讀 OpenAI messages array，且不能和 `--system` 並用。它非串流 `POST <base>/chat/completions`，只印 `choices[0].message.content`。

預設 URL `http://localhost:1234/v1`、model `qwen/qwen3.5-9b`、timeout 120000 ms；可用 `AOS_LLM_URL`、`AOS_LLM_MODEL`、`AOS_LLM_KEY` 覆寫。`--engine`/`AOS_LLM_ENGINE` 是槽位 CPU 名，不會改 endpoint；`--priority` 數字越大越先取槽。使用者層 `<AOS_HOME>/cpus.json`（未設時 `~/.aos/cpus.json`）與世界層 `.aos/llm.json` 控制 `max_inflight`/`wait_ms`。一般呼叫會短暫建立 `<AOS_HOME>/slots/<cpu>/` 的鎖與排隊檔；`--slots` 只查看、不呼叫 endpoint。

### `tool`

```sh
$AOS tool add echoer --description '印出參數' --no-probe -- /usr/bin/printf
$AOS tool ls --json
$AOS tool rm echoer
```

`add <name> [options] -- <argv...>` 先確認 `argv[0]` 可執行。預設執行 `<argv> --metainfo` 探測；結構化 JSON 可提供 description 與欄位，否則取 stdout 第一個非空白行。探不到時必須 `--description`；`--no-probe` 可完全跳過。`--probe metadata` 會在 `--metainfo` 失敗後再試 `--metadata`。同名預設拒絕，`--replace` 才覆寫。

常用欄位：`--args list|string|none`、`--stdin none|text`、`--cwd`、`--timeout-ms`、`--predictability high|medium|low`、`--network/--no-network`。`add` 寫 `.aos/tools/<name>.json`，`rm` 刪該檔；`ls` 不改磁碟。這個命令只登記工具，不直接執行正式工作；lmstudio agent 看到模型回覆末行的工具 JSON 後才會把它投成下一回合 instruction。

### `contact`

```sh
$AOS contact add alice ../alice-world --agent alice --note '部署'
$AOS contact ls
$AOS contact status --json
$AOS contact rm alice
```

`add` 同名即更新；folder 字串原樣保存，使用時相對目前世界解析。`--folder-root F` 可改成操作另一世界的通訊錄。`ls` 會額外顯示合成聯絡人 `~`（`$HOME` 的使用者信箱），但不把它寫入檔案。`status` 隔離讀取每個世界，彙整 agent、status、turn、現場未讀數與 last error；單一壞聯絡人不會拖垮整張表。

`add`/`rm` 原子改寫 `.aos/contacts.json`；`ls`/`status` 不改磁碟。

### `agent`

```sh
mkdir -p world
$AOS agent init world --name bob --persona '你是精簡的檔案助理。' --engine lmstudio --priority 5
AOS_TURN=1 $AOS agent step world bob
$AOS agent say world bob '你好'
$AOS agent listen world bob --once
$AOS agent state world bob
```

`init` 的 folder 預設是 cwd，不走向上尋找；folder 必須已存在，而且一個世界只准一隻 agent。名稱預設是 folder basename。engine 可為 `lmstudio` 或 `pi`；pi 預設 provider/model 是 `deepseek`/`deepseek-v4-flash`。初始化建立 agent 的 persona、engine、history、status、pending、log 與信箱，安裝 `sh`、`ls`、`cat`、`say` 工具，並寫 `.aos/every/agent-<name>.json`。

`step` 通常讓 loop 呼叫；沒有新訊息或工具結果時不叫 LLM，只更新狀態。有訊息時，lmstudio engine 直接呼叫 `aos::llm`；若模型最後一個可解析 JSON 行要求已登記工具，step 投遞一條工具 instruction，下一回合執行、再下一回合把 outcome 放回模型。pi engine 則在一次 step 內執行外部 `pi -p --mode json` 及 pi 自己的工具。

舊式 `agent say/listen/talk/state` 要明確給 folder/name；日常操作用下列頂層捷徑較短。

### `say`

```sh
cd world
$AOS say '請列出目前檔案'
$AOS say --to alice '請回報部署狀態'
```

不帶 `--to` 時投到目前世界唯一 agent；`--to` 從 `.aos/contacts.json`（或合成的 `~`）找目標。訊息寫到目標的 `agents/<name>/say/<ns>-<pid>-<seq>.md`；寄給 `~` 則寫 `$HOME/.aos/say/`。正文包含 `from: <寄件世界絕對路徑>`。只有第一個參數位置的 `--help` 算 help，後面的 `--help` 是訊息文字。

### `listen`

```sh
cd world
$AOS listen --once
$AOS listen
```

先印現有 `log.md` 與未讀摘要；`--once` 立即離開，否則每 200 ms 跟讀新增 log。一般 agent 世界只讀不消費未讀信。若目前解析到 `$HOME` 使用者世界，`listen` 會把 `$HOME/.aos/say/*.md` 併入 `$HOME/.aos/log.md` 並刪除原信。

### `inbox`

```sh
$AOS inbox ls --json
$AOS inbox read                 # 讀最舊一封並標已讀
$AOS inbox read 172500 --keep   # id 可用唯一前綴，只看不消費
$AOS inbox read --all
```

完全不呼叫 LLM。`ls` 不改磁碟。`read` 預設把選中的 `say/<id>.md` 搬到同一 agent 的 `read/<id>.md`，agent 不會再處理；`--keep` 才保留。空信箱、找不到 id 或前綴不唯一回 1。

### `talk`

```sh
cd world
$AOS run --daemon
printf '你好\n請再說一次名字\n' | $AOS talk
$AOS stop
```

先用 `run.lock` 確認已有 runner；沒有就回 1 並提示啟動方式。它逐行建立 say 訊息，等待該行之後的新 assistant log，再印出來。會改動 `say/`，而外部 runner 隨後改 history/log/status/batch。`--interface pi` 目前只回報 adapter 尚未內建並 exit 2。

### `state`

```sh
cd world
$AOS state
```

只接受零參數。輸出是一份合成 JSON：保存的 `detail/status/turn/updated_at/last_error`，加上現場計算的 `unread` 與 `engine/model`；有未讀且不是 error 時，顯示 status 會變成 `pending`。只讀磁碟。現有 `docs/usage.md` 所寫的 `aos state --json` 並未由目前 parser 實作。

### `chat`

```sh
mkdir -p bob && cd bob
$AOS chat --engine lmstudio --model qwen/qwen3.5-9b --timeout 300000 '你叫什麼名字？'
```

若世界沒有 agent，以 folder basename 初始化；若已有 agent，沿用它並忽略新給的 engine/provider/model（stderr 會提醒）。然後投遞訊息：已有活著的 `run.pid` 就等它處理，否則本行程自己反覆 `run_turn`，直到 history 最後出現 assistant 回覆、LLM 失敗或 timeout。預設 timeout 五分鐘。它會建立／更新完整 agent 世界、batch、history、log、status；需要可用的 LM Studio endpoint，或已安裝且有相應 API key 的 pi。

### `tick`

```sh
$AOS tick ./world --dry-run
$AOS tick ./world
```

讀 heartbeat config、routines 與 schedule，機械式判定到期；自己不叫 LLM。argv 型投成 `.aos/inbox/hb-<id>-<turn>.json`；ask 型只在世界剛好一隻 agent 時寫入它的 `say/`。成功的 routine 更新 `last_run`；成功的到期 schedule 刪列；超過 `missed_after` 的 schedule 不執行原工作，而是通知 agent 後刪列。事件追加到 `.aos/heartbeat/log.md`，無事不寫 log。`--dry-run` 只印計畫，不投遞、不改表、不寫 log。

### `heartbeat`

```sh
$AOS heartbeat init ./world --interval 30m
```

期間格式是單一正整數加 `d/h/m/s`。建立空的 `routines.json`、`schedule.json`（若不存在），並覆寫 `.aos/every/tick.json`：其中 `every_ms` 控制 loop 多久才再次投遞 tick。該常駐 instruction 的 argv 是裸的 `aos tick`，所以 runner 的 `PATH` 必須找得到正確的 `aos`。

### `routine`

```sh
$AOS routine add ./world --every 30m --id lint --note '檢查程式' -- sh -c 'make test'
$AOS routine add ./world --slot '09:30 11111..' --id standup --ask '整理今日進度'
$AOS routine ls ./world
$AOS routine rm ./world lint
```

`--every` 與 `--slot` 恰選一個；run 則在 `--ask TEXT` 與 `-- argv...` 恰選一個。duration 不接受 `1h30m`；slot 是 `HH:MM` 或七字元週一到週日 mask。id 字元集是 `[A-Za-z0-9_.-]`，最長 64；省略時自動產生。`add`/`rm` 原子改寫 `.aos/heartbeat/routines.json`，`ls` 只讀。

### `schedule`

```sh
$AOS schedule add ./world --at '2026-09-01 17:00' --id report --ask '整理本日回報'
$AOS schedule ls ./world
$AOS schedule rm ./world report
```

`--at` 只接受 `YYYY-MM-DD HH:MM`，依 `.aos/heartbeat/config.json` 的 IANA `tz` 解讀；不接受相對時間或寬鬆日期。run、id、note 與 routine 相同。`add`/`rm` 原子改寫 `.aos/heartbeat/schedule.json`，`ls` 只讀。

## 5. 資料夾與檔案格式

### `.aos/` 版面

```text
<folder>/.aos/
├── inbox/<id>.json                 一次性 instruction；下一回合搬走
├── every/<stem>.json               常駐 instruction
│   └── .last/<stem>                every_ms 上次投遞 epoch ms
├── batch/<turn>/
│   ├── insts/<id>.json             該回合實際收到的 instruction
│   └── out/<id>.json               每條 outcome
├── turn                             下一個回合號；初值 1
├── state.json                       loop phase/running/agent 鏡射
├── run.lock                         單 runner 的 flock 目標
├── run.pid                          只在 --step 0 存在
├── run.log                          daemon stdout/stderr
├── llm.json                         選填，世界層 LLM 槽上限
├── tools/<name>.json                工具 registry
├── contacts.json                    通訊錄 JSON array
├── agents/<name>/
│   ├── engine.json / persona.md
│   ├── history.json / status.json / pending.json
│   ├── log.jsonl                    對話正典 journal
│   ├── log.md                       由 journal 重畫的人讀版本
│   ├── say/*.md / read/*.md         未讀／已讀訊息
│   └── tools.json                   選填的工具名稱白名單
└── heartbeat/
    ├── routines.json / schedule.json
    ├── config.json                  選填 tz、missed_after
    └── log.md
```

### instruction

最小格式只有非空 `argv`：

```json
{"argv":["printf","hello\\n"]}
```

完整欄位：

```json
{
  "id": "compile",
  "argv": ["sh", "-c", "cat && printf '%s\\n' \"$MODE\""],
  "env": {"MODE": "debug"},
  "cwd": "src",
  "stdin": "input text\n",
  "timeout_ms": 5000
}
```

`id` 缺少時由投遞來源補；`env` 疊加在 runner 環境上；`cwd` 由 loop 相對世界解讀；`timeout_ms: 0` 表示不限。loop 會覆寫同名的 `AOS_FOLDER` 與 `AOS_TURN`。未知 JSON key 會被 `wire` 忽略。instruction 是可信程式碼，不是安全 sandbox：它可指定任意 executable、環境與 cwd。

outcome 固定包含 id、恰好一個非 null 的 `exit`/`signal`、stdout/stderr 與 UTC 起訖時間：

```json
{
  "id": "compile",
  "exit": 0,
  "signal": null,
  "stdout": "ok\n",
  "stderr": "",
  "started_at": "2026-08-31T00:00:00.000Z",
  "ended_at": "2026-08-31T00:00:00.010Z"
}
```

命名規則：argv 投遞用 `d-<epoch_ms>-<pid>-<seq>`；every 複本強制為 `<stem>-<turn>`；agent 工具為 `agent-<name>-tool-<turn>-0`；heartbeat 為 `hb-<id>-<turn>`；say mail 為 `<epoch_ns>-<pid>-<seq>.md`。

### heartbeat 表與 git

`routines.json`、`schedule.json` 使用 `wf-table/1` JSON；前者 rows 欄位是 `id/kind/every/slot/last_run/run/note`，後者是 `id/at/run/note`。`run` 是 `{"argv":[...]}` 或 `{"ask":"..."}`。`config.json` 預設等價於：

```json
{"tz":"Asia/Taipei","missed_after":"6h"}
```

`.gitignore` 的政策不是整個 `.aos/` 都丟掉：

- 預設忽略 `.aos/*`，因此 batch、inbox、every、agent 對話、state、pid、lock、daemon log 等動態執行狀態不入版控。
- 重新納入 `.aos/heartbeat/` 的 JSON 清單／config、`.aos/tools/` 與 `.aos/contacts.json`，讓世界的靜態設定可提交。
- `.aos/heartbeat/log.md` 明確再次忽略，因為它是執行紀錄。

不要把 `AOS_LLM_KEY`、`DEEPSEEK_API_KEY` 等秘密寫進上述設定；實作從環境變數讀取。

## 6. 端到端走一遍

這個案例不需要 LLM 或網路。它建立 folder、投遞固定 id 的 instruction、跑一回合、讀工作副作用與 outcome。

```sh
rm -rf -- /tmp/aos-demo
mkdir -p /tmp/aos-demo
printf '%s\n' \
  '{"id":"demo","argv":["sh","-c","printf hello-from-aos; printf file-created > result.txt"],"timeout_ms":5000}' \
  > /tmp/aos-demo/job.json

/tmp/aos-build/bin/aos deliver /tmp/aos-demo /tmp/aos-demo/job.json
find /tmp/aos-demo/.aos -maxdepth 2 -type f -printf '%P\n' | sort
```

投遞成功不印字；此時應看到：

```text
inbox/demo.json
turn
```

推進並讀結果：

```sh
cd /tmp/aos-demo
/tmp/aos-build/bin/aos run --step 1
cat result.txt
cat .aos/batch/1/out/demo.json
```

輸出形狀是：

```text
turn 1: 1 insts, <實際毫秒> ms
file-created
{
  "id": "demo",
  "exit": 0,
  "signal": null,
  "stdout": "hello-from-aos",
  "stderr": "",
  "started_at": "<實際 UTC 時刻>",
  "ended_at": "<實際 UTC 時刻>"
}
```

落盤後 `inbox/demo.json` 已不在；原 instruction 在 `.aos/batch/1/insts/demo.json`，outcome 在 `.aos/batch/1/out/demo.json`，`turn` 內容變成 `2`，`state.json` 是 `phase: idle`，而 instruction 的 cwd 預設是世界根，所以 `result.txt` 在 `/tmp/aos-demo/`。

上面這段已用 WSL Ubuntu 建出的 Release binary 實跑驗證過，逐項吻合：`deliver` 靜默回 0、
`run --step 1` 印 `turn 1: 1 insts, 2 ms`、`result.txt` 內容為 `file-created`、outcome 七個
欄位齊全、`turn` 變 `2`、`inbox/` 清空、instruction 落在 `batch/1/insts/demo.json`。毫秒數
與時間戳每次都不同，所以正文保留 placeholder。實跑當次的 `state.json` 是：

```json
{
  "turn": 1,
  "phase": "idle",
  "running": [
    { "id": "demo", "argv0": "sh", "pid": 1600, "started_at": "...", "status": "done", "exit": 0 }
  ],
  "agents": {}
}
```

注意 `state.json` 的 `turn` 是**剛跑完的**回合號（1），`.aos/turn` 檔則是**下一個**回合號（2），
兩者差一不是 bug。回合結束後 `.aos/` 底下還會有一個 `run.lock`（flock 目標，不會被清掉）。

## 7. 目前還沒做的／已知限制

- **平台：** POSIX only；Windows 原生 configure 直接失敗。macOS 雖未被擋，但主要實作與測試使用 Linux/POSIX API。
- **沒有 loop 崩潰恢復：** SIGKILL、斷電或 crash 可能留下已搬到 `insts/`、尚未產生 `out/` 的回合；下次不會自動補跑。沒有 `recover`、`check` 或 loop 層 `status` 子命令。`wf/workflows/roadmap.md` 提過這些名稱，但目前完整 17 指令表中不存在。
- **沒有 `fsync`：** 多數檔案採 `.tmp + rename` 保證名稱發布原子性，不保證斷電耐久。
- **instruction 無 sandbox／大小上限：** 可執行任意程式；stdout/stderr 整份讀入 RAM，超大輸出可耗盡記憶體。timeout 直接 `SIGKILL` process group；自行脫離群組的孫行程不一定殺得到。
- **壞 instruction 與 id 衝突：** inbox/every JSON 解析失敗會留在 `insts/`、只在 stderr 報錯，沒有 outcome；相同 id 的 deliver 直接覆寫。wire 對未知 key 寬鬆忽略。
- **agent 限一隻／folder：** 多 agent 必須用不同世界與 contacts 連接。lmstudio 工具一次只接受模型最後段的一個工具 JSON，往返需要三個回合。
- **pi 的信任邊界較寬：** pi engine 不走世界工具白名單，內建 read/bash/edit/write 在單次 step 直接操作世界；它只靠 prompt 約定不碰 `.aos/`，不是 OS sandbox。需要外部 `pi`、網路、provider key；session 綁 cwd，搬世界可能失去舊 session。`aos talk --interface pi` 的 TUI adapter 仍是 stub。
- **LLM client 很薄：** 只做非串流 chat completions，不管理模型載入；需要外部相容 endpoint。端點實際回報不同 model 時，文字仍印出但命令回 1。
- **heartbeat 有競態與 at-least-once 窗口：** `tick` 與 `routine/schedule add/rm` 同時改整張表沒有鎖；deliver 成功、寫表前 crash 會重投。投出即視為完成，不追 outcome 或 agent 是否真的做完。routine 與 schedule 若同 id、同回合都到期，會產生相同 `hb-<id>-<turn>`，可能覆蓋。
- **heartbeat 的可執行檔解析：** `every/tick.json` 寫的是裸 `aos`，不像 agent init 會盡量寫目前 binary 的絕對路徑；daemon 的 `PATH` 不正確時會 exit 127。
- **排程時間：** 只接受 IANA timezone 與固定格式；DST 空缺／重疊一律選較早解，非 Asia/Taipei 的結果未保證符合人的直覺。
- **文件漂移：** `core/tick/README.md` 尾段仍寫 loop 不讀 `every_ms`，但目前 `core/loop/src/aggregate.cpp` 已實作；`docs/usage.md` 寫 `state --json`，目前 parser 未實作。本指南採 source、tests 與 17 指令 help dump 的現況。
- **舊架構不是現在功能：** `core/inst` 與其 `docs/*.md` 已不存在；舊 `aos-folder`、`inst-directives`、roadmap 文件位於 `docs/archive/`。不要把其中的 `aos init`、`aos exec`、`$opt/$env/$ref`、`tooljson`、`llms` 當成目前功能。
