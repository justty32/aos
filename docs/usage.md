# 使用 aos

← [文件索引](README.md)｜[總覽](overview.md)｜[建置細節](build.md)

## 建置與安裝

從 repo 根目錄執行：

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
```

執行檔會在 `build/bin/aos`；安裝方式、平台、vcpkg、preset 與產物見
[build.md](build.md)。

## 推進世界：`run`

```text
aos run [folder] [--step N] [--interval MS] [--daemon]
```

| 選項 | 行為 |
|---|---|
| `--step N` | 推進 N 回合；預設 1，`0` 表示持續執行直到中斷 |
| `--interval MS` | 沒有新投遞時，回合之間最長等待的毫秒數；前景預設 100，daemon 預設 1000 |
| `--daemon` | 脫離終端在背景執行，隱含 `--step 0`，stdout／stderr 附加到 `.aos/run.log` |

等待期間若 `inbox/` 或 agent 的 `say/` 出現新投遞，會立刻開始下一回合，不必等滿
`--interval`。同一個世界由 `.aos/run.lock` 的非阻塞獨佔鎖保證只有一條 loop；持續執行時
另寫 `.aos/run.pid`，供 `aos stop` 找到背景 loop。

省略 `folder` 時，先看 `AOS_FOLDER`，再從目前工作目錄往上找最近的 `.aos/`；都找不到
時使用目前工作目錄。前景持續推進一個世界：

```bash
aos run ./bob --step 0 --interval 500
```

在背景推進目前世界：

```bash
aos run --daemon
```

## 停止背景 loop：`stop`

```text
aos stop [folder]
```

`aos stop` 讀 `.aos/run.pid`，先送 `SIGTERM`；五秒後仍未停止才送 `SIGKILL`。沒有正在
執行的 loop 時會清除陳舊 pid 檔並成功結束，因此可重複呼叫。這個子命令沒有旗標。

```bash
aos stop ./bob
```

## 投遞一條指令：`deliver`

```text
aos deliver [folder] <inst.json>
aos deliver [folder] -- <argv...>
```

第一種讀取既有的指令 JSON，第二種直接把 `--` 後面的參數做成指令。兩者都先寫暫存檔再
原子改名到 `.aos/inbox/`，等待後續回合執行。省略 `folder` 時使用與 `run` 相同的解析規則。

```bash
aos deliver ./bob -- printf 'hello\n'
```

## 把 LLM 當成一條指令：`llm`

```text
aos llm [--system TEXT] [--messages FILE] [--url U] [--model M]
        [--timeout-ms N] [--engine CPU] [--priority N] [--slots]
```

prompt 從 stdin 進，回覆文字從 stdout 出。`--messages FILE` 改為直接送出檔案內的 OpenAI
messages 陣列；`--system TEXT` 加上 system prompt。預設 timeout 是 120000 毫秒。

```bash
echo '只回一個字：好' | aos llm --system '回答要簡短。'
```

連線與排隊設定如下：

| 選項或環境變數 | 用途 | 預設 |
|---|---|---|
| `--url U`／`AOS_LLM_URL` | OpenAI 相容 base URL | `http://localhost:1234/v1` |
| `--model M`／`AOS_LLM_MODEL` | 模型名稱 | `qwen/qwen3.5-9b` |
| `AOS_LLM_KEY` | 選填的 Bearer token | 無 |
| `--engine CPU`／`AOS_LLM_ENGINE` | 取槽使用的 CPU 名稱 | `lmstudio` |
| `--priority N`／`AOS_LLM_PRIORITY` | 排隊優先度，數字越大越優先 | `0` |
| `--slots` | 只顯示各 CPU 的槽狀態，不讀 stdin、不呼叫端點 | — |

使用者層的 `<AOS_HOME>/cpus.json` 設定各 CPU 的 `max_inflight` 與 `wait_ms`；未設定
`AOS_HOME` 時位置是 `~/.aos/cpus.json`。世界層 `.aos/llm.json` 可把使用者層的
`max_inflight` 往下限，並可覆寫 `wait_ms`。沒有設定上限就不取槽。查看槽位：

```bash
aos llm --slots
```

完整設定格式與兩層上限規則見 [core/llm/README.md](../core/llm/README.md)。

## 建立與推進 agent：`agent`

```text
aos agent init [folder] [--name N] [--persona TEXT] [--engine lmstudio|pi]
               [--provider P] [--model M] [--priority N]
aos agent step [folder] [name]
aos agent say <folder> <name> <text...>
aos agent listen <folder> <name> [--once]
aos agent talk <folder> <name> [--interface pi]
aos agent state <folder> <name>
```

`init` 建立世界與一隻 agent，並在 `.aos/every/` 放入每回合執行 `step` 的常駐指令。
省略 `folder` 時直接在目前資料夾建立；`step` 通常由 loop 呼叫。`--engine` 選擇
`lmstudio` 或 `pi`，其餘選項設定人格、provider、模型與排隊優先度。

```bash
mkdir bob && cd bob && aos agent init --engine lmstudio --model qwen/qwen3.5-9b
```

舊形式的 `agent say|listen|talk|state` 可明確指定世界與 agent；目前世界只有一隻 agent 時，
通常直接使用下列頂層捷徑。

## 對 agent 說話：`say`

```text
aos say [--to <名字>] <text...>
```

不帶 `--to` 時，訊息投到目前世界唯一 agent 的 `say/`。`--to` 會從目前世界的通訊錄找
名字，跨世界投遞；成功時印出真正的收件匣路徑。

```bash
aos say "你叫什麼名字"
```

跨世界投遞：

```bash
aos say --to alice "可以幫我看一下嗎"
```

## 跟讀對話：`listen`

```text
aos listen [--once]
```

`listen` 先印現有記錄與未讀訊息；預設每 200 毫秒跟讀新增內容，`--once` 則印完立即結束。
它只顯示未讀，不會刪除。

```bash
aos listen --once
```

## 逐行交談：`talk`

```text
aos talk [--interface <名字>]
```

`talk` 從 stdin 逐行讀取訊息，等待外部 loop 推進，並印出該次新增的記錄。它會先確認
runner 存在；沒有 runner 時會提示如何啟動並結束。`--interface pi` 目前尚未內建。

```bash
printf '你好\n再說一次你的名字\n' | aos talk
```

## 查看 agent 狀態：`state`

```text
aos state
```

輸出包含 agent、目前狀態、上一回合，以及現場計算的 `unread`、`engine`、`model`。
有未讀且狀態不是 `error` 時顯示 `pending`；失敗回合顯示 `status=error`，並帶最近一次的
單行 `last_error`。`status.json` 內也會保存寫入時的 `unread` 快照，成功回合會清除
`last_error`。

`state` 沒有旗標；輸出本身就是 `status.json` 的內容加上現場計算的欄位。

```bash
aos state
```

## 一步建立、發話並等回覆：`chat`

```text
aos chat [--engine lmstudio|pi] [--provider P] [--model M]
         [--timeout MS] <text...>
```

`chat` 可從空資料夾完成建立世界、初始化同名 agent、投遞一句話，再於前景自行推回合，
直到出現 assistant 回覆。預設最多等待五分鐘；`--timeout MS` 可改等待時間。若世界已有
活著的 loop，`chat` 只等待它處理，不會同時搶 inbox。

```bash
mkdir bob && cd bob && aos chat --engine lmstudio "你叫什麼名字"
```

## 不呼叫 LLM 讀信：`inbox`

```text
aos inbox ls [--json]
aos inbox read [<id>] [--all] [--keep]
```

`ls` 直接列出目前 agent 的 `say/*.md`，不呼叫 LLM，也不消費訊息。`--json` 改印 JSON。

```bash
aos inbox ls
```

`read` 省略 id 時讀最舊一封；`<id>` 可用唯一前綴，`--all` 讀全部，`--keep` 只讀不搬。
沒有 `--keep` 時，讀完會把訊息搬進同層的 `read/`，agent 之後不會再掃到。只想查看、仍要
讓 agent 回覆時，應使用 `ls` 或：

```bash
aos inbox read --all --keep
```

## 登記世界工具：`tool`

```text
aos tool add <name> [選項...] -- <argv...>
aos tool ls [--folder F] [--json]
aos tool rm <name> [--folder F]
```

每個登記寫在 `.aos/tools/<name>.json`；`add` 的 `--` 後面是執行時固定使用的 argv 前綴。
這一層負責登記、讀寫與探測，不負責執行工具。子命令真名是 `ls` 與 `rm`。

| `add` 選項 | 用途 |
|---|---|
| `--folder F` | 指定世界資料夾 |
| `--description TEXT` | 手動指定工具表述 |
| `--args MODE` | 參數模式：`list`、`string` 或 `none` |
| `--stdin MODE` | stdin 模式：`none` 或 `text` |
| `--cwd DIR` | 工具執行目錄 |
| `--timeout-ms N` | 工具逾時毫秒數 |
| `--predictability P` | `high`、`medium` 或 `low` |
| `--guarantee TEXT` | 保證說明 |
| `--lifecycle TEXT` | 生命週期說明 |
| `--state TEXT` | 狀態說明 |
| `--stage TEXT` | 階段說明 |
| `--network`／`--no-network` | 宣告需要或不需要網路 |
| `--replace` | 覆寫同名登記 |
| `--no-probe` | 不探測工具表述 |
| `--probe metadata` | `--metainfo` 沒探到時再試 `--metadata` |

預設執行 `<argv> --metainfo`。若行程成功但 stdout 不是可用的 metainfo JSON，取 stdout
第一個非空白行作為表述；兩者都拿不到時，需用 `--description` 手動提供。登記一支工具：

```bash
aos tool add formatter --args list --stdin text --probe metadata -- formatter
```

列出與移除：

```bash
aos tool ls --json
aos tool rm formatter
```

格式與探測降級規則見 [core/tool/README.md](../core/tool/README.md)。

## 管理通訊錄：`contact`

```text
aos contact add <name> <folder> [--agent A] [--note TEXT] [--folder-root F]
aos contact ls [--folder-root F] [--json]
aos contact rm <name> [--folder-root F]
aos contact status [--folder-root F] [--json]
```

通訊錄存於 `.aos/contacts.json`。`--folder-root F` 指定通訊錄所在世界；`add --agent A`
指定對方 agent 名稱，`--note TEXT` 加上備註。`$HOME` 是天然的 `~` 聯絡人，不必寫進檔案，
可配合 `aos say --to ~` 投遞給使用者。

```bash
aos contact add alice ../alice-world --note "負責部署"
aos contact ls
aos contact status
aos contact rm alice
```

`status` 一次列出自己與全通訊錄的狀態、回合及現場未讀數；單一聯絡人的資料夾不存在、
沒有 agent 或狀態檔損壞時，只在該列顯示原因。

## 安裝心跳：`heartbeat`

```text
aos heartbeat init [folder] [--interval 30m]
```

`init` 建立 `.aos/heartbeat/` 的兩張清單，並在 `.aos/every/tick.json` 登記 `aos tick`。
`--interval` 預設 `30m`，會換算成常駐指令的 `every_ms`。

```bash
aos heartbeat init ./bob --interval 30m
```

## 跑一次心跳：`tick`

```text
aos tick [folder] [--dry-run]
```

`tick` 檢查 `routines.json` 與 `schedule.json`，把到期的 argv 型事務投進 inbox，或把 ask
型事務交給世界唯一的 agent，然後更新清單與 `.aos/heartbeat/log.md`。它本身不呼叫 LLM。
`--dry-run` 只計算並印出結果，不投遞、不說話、不改表也不寫 log。

```bash
aos tick ./bob --dry-run
```

## 登記固定循環：`routine`

```text
aos routine add [folder] (--every D | --slot S) [--id ID] [--note 文字]
                (--ask 文字 | -- argv...)
aos routine ls [folder]
aos routine rm [folder] <id>
```

`--every D` 接受 `Nd`、`Nh`、`Nm` 或 `Ns`；N 是正整數且只能有一個單位，例如 `90m`，
不能寫 `1h30m`。`--slot S` 接受 `HH:MM`，或 `HH:MM <遮罩>`；七字元遮罩依序代表
週一到週日，`1` 表示該日執行，`.` 表示不執行，例如 `09:30 11111..` 是平日 09:30。

argv 型循環把 `--` 後面的參數投進 inbox；ask 型則把文字交給 agent。新增、列出與移除：

```bash
aos routine add ./bob --slot "09:30 11111.." --id standup --ask "整理今天的工作"
aos routine ls ./bob
aos routine rm ./bob standup
```

## 登記一次性行程：`schedule`

```text
aos schedule add [folder] --at 時刻 [--id ID] [--note 文字]
                 (--ask 文字 | -- argv...)
aos schedule ls [folder]
aos schedule rm [folder] <id>
```

`--at` 只接受 `YYYY-MM-DD HH:MM`，依世界 heartbeat 設定的時區解讀；不接受「今晚 8 點」
等相對時間。到期且成功投遞後會從一次性清單移除。

```bash
aos schedule add ./bob --at "2026-09-01 17:00" --id report --ask "整理本日回報"
aos schedule ls ./bob
aos schedule rm ./bob report
```

心跳清單格式、到期與錯過規則見 [core/tick/README.md](../core/tick/README.md)。
