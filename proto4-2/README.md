# proto4-2 — inst.json ＋ cpu ＋ daemon ＋ kernel（Python）

這是 [proto4 筆記第 7 節](../proto4/notes/2026-09-08-ideas.md)的最簡原型。

← [proto4-1](../proto4-1/README.md)（那一版 kernel 是「一個進程裡一個 loop，每格 cd 進每個資料夾執行 `./.aos/inst`」）

這一版翻案的兩件事：

1. `.aos/inst` 不再是可執行檔，改成一份**資料**：`inst.json`，嚴格一個 JSON 物件，寫「怎麼叫一次 POSIX 程式」。
2. 「一直跑」這件事從 kernel 身上拿走，交給 **cpu**：一顆 cpu 就是一個 Linux process，反覆執行同一份 inst.json。kernel 自己也只是一個被第一顆 cpu 每秒跑一次的普通程式。

## 三個名詞（第 7.2 節那張表）

| aos 裡的名詞 | 是什麼 | 對應到 Linux |
|---|---|---|
| **指令** | 把某個 `inst.json` 執行一次 | 跑一次程式 |
| **cpu** | 一個一直照 interval 反覆執行同一份 inst.json 的東西 | 一個 Linux process（`aos_cpu.py`，跑著 loop） |
| **proc** | 被 cpu 跑的那個目標（資料夾／inst.json） | 程式本體 |

再往上兩個角色：

- **aos-daemon＝提供基礎**。它管所有 cpu：誰在跑、pid 多少、跑到第幾格、佔多少記憶體。
- **aos-kernel＝做管理**。它每秒被跑一次，去 `requests/` 找使用者丟的請求，翻譯成 daemon 請求掛上去。daemon 一起來就先開第一顆 cpu 跑 kernel，兩個分不開。

## 檔案

- `aos_cpu.py`：執行一次 inst.json（`run_once`）＋ cpu 的 loop。`python3 aos_cpu.py DIR [--interval SEC] [--max-runs N] [--inst REL]`
- `aos_daemon.py`：常駐進程，管所有 cpu。`python3 aos_daemon.py start|run|stop [--home H]`
- `aos_kernel.py`：一次執行做完就退出的管理程式，被第一顆 cpu 每秒跑一次。
- `aos.py`：給人用的 CLI。`start|stop|ls`、`register DIR [NAME] [INTERVAL]`、`unregister NAME`
- `test/`：`python3 -m unittest discover -s test`（8 條，真的開進程，家在 /tmp、跑完自己收）。fixture 在 `test/fx/`。

## inst.json 長什麼樣

預設放在 `<資料夾>/.aos/inst.json`，位置可以換（cpu 的 `--inst my/inst.json`）。內容**只能是一個 JSON 物件**：

```json
{
  "argv": ["sh", "-c", "echo hi; cat"],
  "env": {"GREET": "hi"},
  "cwd": "sub",
  "stdin": "餵給它的字",
  "timeout_ms": 300
}
```

| 欄位 | 意思 | 沒寫時 |
|---|---|---|
| `argv` | **必填**，跑什麼、帶什麼參數；`argv[0]` 走 PATH | 算錯誤，這次不跑 |
| `env` | 額外環境變數，疊在繼承來的環境上（只加不減） | 只有繼承的 |
| `cwd` | 工作目錄，**相對於那個資料夾** | 資料夾本身 |
| `stdin` | 餵進去的字串 | 空 |
| `timeout_ms` | 超過就殺掉整個 process group | 0 ＝不限 |

環境一律多塞兩個：`AOS_DIR`（資料夾絕對路徑）、`AOS_TICK`（第幾次）。

執行完寫兩個檔到那個資料夾的 `.aos/`：

- `last.json`：`{"tick":…, "exit":…, "signal":…, "stdout":…, "stderr":…, "started_at":…, "ended_at":…}`。`exit` 與 `signal` 二擇一非 null；逾時＝`signal` 9。JSON 壞掉、不是物件、`argv` 沒填、程式跑不起來 → 多一個 `error` 欄位，這次不跑，cpu 照活。
- `runs.jsonl`：每跑一次 append 一行同樣的東西（要數次數看這個）。

cpu 每跑完一次還會寫 `.aos/cpu.json`：`{"pid","tick","dir","interval"}`——daemon 就是讀這個知道它跑到第幾格。

## 家目錄長什麼樣

家走 `--home H` 或環境變數 `AOS_HOME`：

```
H/requests/          使用者面的請求。CLI 寫這裡，只有 kernel 讀
H/requests/done/     處理過的搬來這裡
H/kernel/            第一顆 cpu 跑的 proc；.aos/inst.json daemon 自動生
H/daemon/daemon.pid  daemon 的 pid
H/daemon/state.json  每 0.5 秒寫一次：daemon pid ＋ 每顆 cpu 的 pid/alive/tick/rss_kb（ls 讀這個）
H/daemon/cpus.json   登記表
H/daemon/daemon.log  daemon 與各 cpu 的輸出
H/daemon/requests/   daemon 請求。規矩：只有 kernel 可以寫這裡
```

**規矩（沒用程式強制，靠自律）**：使用者與 CLI 只寫 `requests/`；只有 kernel 可以寫 `daemon/requests/`。

請求都是一個 JSON 檔（先寫 `.tmp` 再 rename，別人不會讀到半個），處理完搬到同層的 `done/`，多 `ok`／`result`。

- 使用者面（`requests/`）：`{"op":"register","dir":…,"name":…,"interval":…}`、`{"op":"unregister","name":…}`
- daemon 面（`daemon/requests/`）：`{"op":"spawn","name":…,"dir":…,"interval":…}`、`{"op":"kill","name":…}`、`{"op":"ls"}`

kernel 做的就是把上面那行翻成下面那行。它每次執行還會印一行摘要到 stdout，那行會進 `H/kernel/.aos/last.json`——那就是 kernel 的日誌。

## 怎麼跑

```sh
cd proto4-2
python3 -m unittest discover -s test        # 8 條測試

export AOS_HOME=~/.aos-home
python3 aos.py start                        # daemon 起來，順便開第一顆 cpu 跑 kernel
python3 aos.py register /path/to/folder cnt 1
python3 aos.py ls
python3 aos.py unregister cnt
python3 aos.py stop
```

`ls` 印出來長這樣：

```
daemon  alive  pid=12345  家=/home/me/.aos-home
NAME           PID      ALIVE  TICK   RSS_KB
cnt            12352    yes    6      9088
kernel         12346    yes    7      9216
```

只想試「執行一次 inst.json」或「一顆 cpu」，不用開 daemon：

```sh
python3 aos_cpu.py test/fx/counter --interval 1 --max-runs 3
cat test/fx/counter/.aos/last.json
```

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- 沒有 pause／resume、沒有 user 切換、沒有 config 版本、沒有 `stdout`／`stderr` 導向檔案（一律捕回 last.json）。
- cpu 掛掉不會自動重開；daemon 也不看它為什麼掛。
- daemon 重開不接回原本的 cpu：`cpus.json` 有落地，但 start 不讀它。stop 之後登記就沒了。
- daemon 被 SIGKILL 的話，那些 cpu 會變孤兒，沒人收。
- daemon 沒跑的時候丟請求，沒人撿（proto4-1 會先放著、下次 start 撿走，這版沒做）。
- 停止條件只有兩個：`--max-runs` 跑滿、收到 SIGTERM。沒有「exit code 到了就停」、「檔案出現就停」、「時間到就停」。
- 錯誤只記一條在 `last.json` 的 `error`，沒有重試、沒有退避、沒有通知。
- 請求沒有回覆通道給使用者：CLI `register` 只是把檔案丟出去就回，不等結果（要看結果自己去翻 `requests/done/`）。
- 同名 cpu 重複 spawn＝把舊的收掉換新的，沒有問過任何人。
- 沒有權限檢查：誰都能寫 `daemon/requests/`，規矩只寫在這份 README。
- `runs.jsonl`、`daemon.log` 只長不消，沒有輪替。
