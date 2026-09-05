這是玩的原型，不是正式實作。

## 怎麼跑

```sh
python3 proto/aos.py <子命令> …
```

需要 Python 3.11+，純標準庫，不用裝任何東西。

## 子命令一覽

| 子命令 | 幹嘛的 | 旗標 |
|---|---|---|
| `init <地>` | 建一塊地：寫 `.aos/layout.json`、`.aos/config.json` | `--force`（地已經在也重寫）、`--with-example`（順手放一份最小的 `main.aos.json`） |
| `compile <地>` | 把頂層 `*.aos.json` 原稿編成 `.aos/program/` 底下的模板 | 無 |
| `exec <地>` | 走一格：讓這塊地上所有跑著的串各推進一步，順便處理收件匣 | `--timeout <ms>`（這一格每筆指令的逾時上限）、`--json` |
| `run <地>` | 反覆 `exec`，走法有三種：固定次數、隔一段時間、到閒著為止 | `--steps N`、`--every <ms>`、`--until idle`、`--budget N`（超過就停並寫停止原因檔）、`--timeout <ms>`（預設 60000）、`--register`（順手寫進登記表）、`--json`、`--quiet` |
| `status <地>` | 看這塊地的批、串、游標、暫存器、停止原因、收件匣待處理數 | `--json` |
| `deliver <地> <json>` | 投遞一個 json 到這塊地的收件匣；`<json>` 可以是一段字串、一個檔名、或 `-`（從 stdin 讀） | `--sender <地>`（投遞者是誰，預設目前目錄） |
| `reset <地>` | 清掉狀態是 `failed`／`stopped` 的串，也清掉停止原因檔 | 無 |
| `stop <地>` | 請一塊地在這一格跑完就停 | `--kill`（不走控制收件匣，直接對登記表上的 pid 送 SIGKILL） |
| `daemon <op> [地]` | 看管者：`start`／`stop`／`ls`／`exec`／`status` | `--foreground`、`--every <ms>`（預設 500）、`--json` |
| `llm <op> [其餘…]` | LLM 世界：`init`／`serve`／`tick`／`ls`／`ask` | `--land <地>`（預設 `$AOS_HOME/.aos/llm`）、`--until idle`、`--steps N`、`--every <ms>`（預設 200）、`--json` |

## 一塊地長什麼樣

一塊地＝一個裡面有 `.aos/` 的資料夾。頂層放人（或 LLM）寫的原稿，`.aos/` 是機器的地盤：

- `main.aos.json`（頂層）：原稿，程式的入口
- `.aos/layout.json`：這塊地的版面版本，`aos init` 寫的
- `.aos/config.json`：這塊地的設定（PATH 白名單、並行上限、指令逾時、收件匣上限……）
- `.aos/program/`：編譯器吐出來的模板，跑起來的一步步動作
- `.aos/series.json`：接力棒，記著這批有哪幾條串、各跑到哪一步、暫存器是什麼
- `.aos/inbox/`：收件匣，別人投給這塊地的東西，下一格才被取走
- `.aos/ticks/<N>/`：第 N 格跑的每筆指令與執行結果
- `.aos/calls/`：呼叫記錄，父開子地時寫的一筆
- `.aos/stopped.json`：`run` 停下來時寫的停止原因檔
- `.aos/lock`：獨佔鎖，一塊地同時只准一支 `exec`／`run`

## 每個範例怎麼跑

`proto/examples/` 底下每個資料夾一個範例，各自的 `README.md` 有一句話講「跑了會看到什麼」跟怎麼跑：

- [`examples/hello`](examples/hello/README.md)：三步一串，寫檔、讀檔、印出來
- [`examples/call-sync`](examples/call-sync/README.md)：父地同步呼叫子地，子把結果寫到父指定的結果落點
- [`examples/call-async`](examples/call-async/README.md)：父地脫節呼叫子地，子自己有鐘，父用 `await` 等結果
- [`examples/llm-echo`](examples/llm-echo/README.md)：投一筆請求給 LLM 世界，假後端把 prompt 原樣回話

每個範例資料夾都有 `run.sh`，可以一鍵重跑（先清乾淨、`init`、走格、印結果）。`proto/run-all.sh` 會把全部範例跟測試一起跑一遍。

## `AOS_HOME` 怎麼用

`$AOS_HOME`（預設是使用者的 `~`）是「家」：登記表 `registry.json`、使用者層設定 `config.json`、帳簿 `ledger.jsonl`、daemon 的 pid、LLM 世界都住在 `$AOS_HOME/.aos/` 裡。

**測試與範例一律把 `AOS_HOME` 指到暫存目錄**，不要用真正的 `~`：

```sh
export AOS_HOME="$(mktemp -d)"
```

`proto/examples/` 裡凡是會碰到登記表或 LLM 世界的範例（`call-async`、`llm-echo`），`run.sh` 都會自己把 `AOS_HOME` 指到範例資料夾底下的 `.home/`，跑完也不會弄髒別的地方。

## LLM 真後端怎麼切

預設每個處理單元（`unit`）的 `endpoint` 是假後端 `"echo:"`：不打任何網路，把 prompt 原樣回、前面加一行標記。**測試與範例的 `run.sh` 一律用這個假後端，不打真後端。**

要打真的模型，改 `$AOS_HOME/.aos/config.json` 的 `units`，把某個單元的 `endpoint` 換成本機 LM Studio：

```json
{"name": "lmstudio", "endpoint": "http://localhost:1234/v1", "model": "<模型名>", "tier": "smart", "max_parallel": 1}
```

再跑 `aos llm tick` 或 `aos llm ask` 就會真的打過去。

## 跟正式實作的關係

這是照 WRITER-BRIEF 第 4 節釘死的檔名與欄位名做的原型，目的是**撞出 spec 的問題**，不是先跑先贏的正式版。撞到的東西（多餘的動作、看不見的狀態、錯誤不指路、spec 沒講清楚的地方）都記在 `proto/FINDINGS.md`。
