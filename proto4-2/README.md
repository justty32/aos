# proto4-2 — inst.json ＋ cpu ＋ daemon ＋ kernel（Python）

這是 [proto4 筆記第 7 節](../proto4/notes/2026-09-08-ideas.md)的最簡原型。

← [proto4-1](../proto4-1/README.md)（那一版 kernel 是「一個進程裡一個 loop，每格 cd 進每個資料夾執行 `./.aos/inst`」）

inst.json 的格式與 cpu 的整體時限照[第 10 節](../proto4/notes/2026-09-08-ideas.md)：格式直接搬凍結分支 `core/inst` 那套。

這一版翻案的兩件事：

1. `.aos/inst` 不再是可執行檔，改成一份**資料**：`inst.json`，嚴格一個 JSON 物件，寫「怎麼叫一次 POSIX 程式」。
2. 「一直跑」這件事從 kernel 身上拿走，交給 **cpu**：一顆 cpu 就是一個 Linux process，反覆執行同一份 inst.json。kernel 自己也只是一個被第一顆 cpu 每秒跑一次的普通程式。

## 三個名詞（第 7.2 節那張表）

| aos 裡的名詞 | 是什麼 | 對應到 Linux |
|---|---|---|
| **指令** | 把某個 `inst.json` 執行一次 | 跑一次程式 |
| **cpu** | 一個一直照 interval 反覆執行同一份 inst.json 的東西 | 一個 Linux process（`aos_cpu.py`，跑著 loop） |
| **proc** | 被 cpu 跑的那個目標（資料夾／inst.json） | 程式本體 |

一個 proc 的**本體＝它的 cwd（資料夾）＝唯一標示**：一個資料夾最多一顆 cpu 在跑，沒有另外取名字這回事（[proto4 筆記第 8 節](../proto4/notes/2026-09-08-ideas.md)）。

再往上兩個角色：

- **aos-daemon＝提供基礎**。它管所有 cpu：誰在跑、pid 多少、跑到第幾格、佔多少記憶體。
- **aos-kernel＝做管理**。它每秒被跑一次，去 `requests/` 找使用者丟的請求，翻譯成 daemon 請求掛上去。daemon 一起來就先開第一顆 cpu 跑 kernel，兩個分不開。

## 檔案

- `aos_inst.py`：inst.json 的讀、驗、解指示詞（格式那一層）。
- `aos_cpu.py`：執行一次 inst.json（`run_once`）＋ cpu 的 loop。`python3 aos_cpu.py DIR [--interval SEC] [--max-runs N] [--time-limit SEC] [--inst REL]`
- `aos_daemon.py`：常駐進程，管所有 cpu。`python3 aos_daemon.py start|run|stop [--home H]`
- `aos_home.py`：家目錄的版面（哪個檔在哪）＋ 看 /proc 的小工具，daemon 與 CLI 共用。
- `aos_kernel.py`：一次執行做完就退出的管理程式，被第一顆 cpu 每秒跑一次。
- `aos.py`：給人用的 CLI。`start|stop|ls`、`register DIR [INTERVAL] [TIME_LIMIT]`、`unregister DIR`
- `test/`：`python3 -m unittest discover -s test`（49 條，真的開進程，家在 /tmp、跑完自己收）。fixture 在 `test/fx/`。

## inst.json 長什麼樣

預設放在 `<資料夾>/.aos/inst.json`，位置可以換（cpu 的 `--inst my/inst.json`）。內容**只能是一個 JSON 物件**。格式是凍結分支 `core/inst` 那套直接搬過來的（SPEC §C-3～§C-6，已經被 ctest 和攻擊腳本打過，不重新發明）：八個欄位，只有 `argv` 必填，**沒寫在表上的 key 一律拒絕**——不是忽略，舊的執行檔碰到新欄位寧可硬失敗，也別默默少一個限制。

```json
{
  "argv": ["sh", "-c", "cat; echo $GREET"],
  "stdin": "in.txt",
  "stdout": "out.txt",
  "stderr": {"$opt": "merge"},
  "exit": "code.txt",
  "cwd": "sub",
  "env": {"GREET": "hi"},
  "timeout_ms": 3000
}
```

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 字串陣列 | **必填** | 跑什麼；`argv[0]` 走 PATH（用**疊加後**的 env 裡的 PATH 找） |
| `stdin` | 路徑 | 空＝不餵（`/dev/null`） | 拿這個**檔案**當標準輸入（不是塞字串） |
| `stdout` | 路徑 | 空＝cpu 抓回 `last.json` | 標準輸出寫到這個檔（建立並清空） |
| `stderr` | 路徑或 `{"$opt":"merge"}` | 空＝cpu 抓回 `last.json` | 寫到檔；`merge`＝跟 stdout 走同一條 |
| `exit` | 路徑 | 空＝不寫 | 跑完把結束碼（十進位＋換行）寫進去，fsync 檔案與父目錄 |
| `cwd` | 路徑 | 空＝資料夾本身 | 工作目錄 |
| `env` | 物件 | `{}` | 疊在繼承來的環境上（只加不減）；key 不能空、不能含 `=` |
| `timeout_ms` | 整數 | `0`＝不限 | **這一次**執行的上限（毫秒） |

相對路徑一律從**資料夾**起算（不是從 `cwd`）。環境一律多塞兩個：`AOS_DIR`（資料夾絕對路徑）、`AOS_TICK`（第幾次）。

### 指示詞

`argv` 的每個元素、五個路徑欄位（`stdin`／`stdout`／`stderr`／`exit`／`cwd`）、`env` 的值，都可以不寫字串，改寫一個**指示詞**——剛好一個 key、值一定是字串的物件：

- `{"$env":"NAME"}`：從 **cpu 自己的環境**取值。變數不存在＝錯誤；存在但空＝空字串（兩件不同的事）。
- `{"$ref":"file.json#/a/b"}`：相對於**資料夾**讀那份 JSON，`#` 後面是 RFC 6901 的 JSON Pointer（`~1` 代表 `/`、`~0` 代表 `~`），沒有 `#` 就取整份。**取回來的值就當成本來寫在那裡**：是字串就直接用，又是指示詞就繼續解（可以巢狀），陣列或一般物件＝錯誤。同一條鏈再撞到同一個「檔案 realpath ＋ pointer」＝繞回來了＝錯誤。
- `{"$opt":"merge"}`：只有 `stderr` 能用，等於 shell 的 `2>&1`。

`env` 的 key 與 `timeout_ms` 不吃指示詞。

### 跑完之後

執行完寫兩個檔到那個資料夾的 `.aos/`：

- `last.json`：`{"tick","exit","signal","stdout","stderr","timed_out","started_at","ended_at"}`。`exit` 與 `signal` 二擇一非 null；`stdout`／`stderr` 有導到檔案時這裡記 `null`。格式或解析被拒（JSON 壞掉、不是物件、未知 key、`argv` 空、指示詞解不開、`$ref` 繞圈…）→ 多一個 `error` 欄位，開頭是代號（`UnknownKey:`、`ReferenceCycle:`…），**這次不跑**、cpu 照活。
- `runs.jsonl`：每跑一次 append 一行同樣的東西（要數次數看這個）。

找不到程式＝`exit` 127、沒執行權＝`exit` 126、重導向的檔開不起來＝`exit` 126：這三種都算**跑完了一次**，不是 `error`，stderr 那條會多一行說明。

**逾時怎麼砍**（`timeout_ms` 到，或 cpu 的整體時限到）：先對**整個 process group** 送 SIGTERM，給 2 秒，直接子行程還活著就 SIGKILL 整個 group。`last.json` 記 `timed_out: true`，`signal` 是實際砍中的那個（15 或 9）。逾時一樣算跑完了一次。

cpu 每跑完一次還會寫 `.aos/cpu.json`：`{"pid","tick","dir","interval","time_limit"}`——daemon 就是讀這個知道它跑到第幾格。cpu 要退之前再寫一次，多 `stopped`（`"max_runs"`／`"sigterm"`／`"time_limit"`）與 `ended_at`。

## 家目錄長什麼樣

家走 `--home H` 或環境變數 `AOS_HOME`：

```
H/requests/          使用者面的請求。CLI 寫這裡，只有 kernel 讀
H/requests/done/     處理過的搬來這裡
H/kernel/            第一顆 cpu 跑的 proc；.aos/inst.json daemon 自動生
H/daemon/daemon.pid  daemon 的 pid
H/daemon/state.json  每 0.5 秒寫一次：daemon pid ＋ 每顆 cpu 的 pid/alive/tick/rss_kb/interval/time_limit（ls 讀這個）
H/daemon/cpus.json   登記表
H/daemon/daemon.log  daemon 與各 cpu 的輸出
H/daemon/requests/   daemon 請求。規矩：只有 kernel 可以寫這裡
```

**規矩（沒用程式強制，靠自律）**：使用者與 CLI 只寫 `requests/`；只有 kernel 可以寫 `daemon/requests/`。

請求都是一個 JSON 檔（先寫 `.tmp` 再 rename，別人不會讀到半個），處理完搬到同層的 `done/`，多 `ok`／`result`。

`dir` 一律是資料夾的路徑，翻成 daemon 請求時先 `os.path.realpath()` 正規化過（symlink、`..`、尾巴 `/` 都算同一個）——那就是這顆 cpu 唯一的標示，daemon 的表、`state.json`、`cpus.json` 都拿它當 key：

- 使用者面（`requests/`）：`{"op":"register","dir":…,"interval":…,"time_limit":…}`、`{"op":"unregister","dir":…}`
- daemon 面（`daemon/requests/`）：`{"op":"spawn","dir":…,"interval":…,"time_limit":…}`、`{"op":"kill","dir":…}`、`{"op":"ls"}`

`interval` 是兩次執行之間隔多久（秒，沒給＝1），`time_limit` 是那顆 cpu 的**整體時限**（秒，沒給＝0＝不限）；kernel 原樣翻給 daemon，daemon 開 cpu 時當成 `--time-limit` 傳下去。`cpus.json` 與 `state.json` 每顆 cpu 都記著這兩個。

**同一個資料夾第二次 `spawn`＝拒絕**：daemon 回 `ok:false, result:"already running: <dir>"`，舊的那顆不動。`kill` 一個沒在跑的資料夾也回 `ok:false`。

cpu 自己退掉（時限到、跑滿 `--max-runs`、被 SIGTERM）之後，daemon 每輪 reap 到就把它從 `cpus.json` 與 `state.json` 拿掉，在 `daemon.log` 記一行（哪個資料夾、pid、`cpu.json` 的 `stopped` 是什麼）——那個資料夾才能再 `register`。「cpu 掛掉不自動重開」不變。

kernel 做的就是把上面那行翻成下面那行。它每次執行還會印一行摘要到 stdout，那行會進 `H/kernel/.aos/last.json`——那就是 kernel 的日誌。

## 怎麼跑

```sh
cd proto4-2
python3 -m unittest discover -s test        # 49 條測試

export AOS_HOME=~/.aos-home
python3 aos.py start                        # daemon 起來，順便開第一顆 cpu 跑 kernel
python3 aos.py register /path/to/folder 1        # 每 1 秒跑一次，不限時
python3 aos.py register /path/to/folder 1 60     # 加上整體時限 60 秒
python3 aos.py ls
python3 aos.py unregister /path/to/folder
python3 aos.py stop
```

`ls` 印出來長這樣（欄位：`DIR  PID  ALIVE  TICK  RSS_KB`；kernel 那顆路徑後面標 `(kernel)`）：

```
daemon  alive  pid=12345  家=/home/me/.aos-home
DIR  PID  ALIVE  TICK  RSS_KB
/home/me/.aos-home/kernel  (kernel)  12346  yes  7  9216
/path/to/folder  12352  yes  6  9088
```

只想試「執行一次 inst.json」或「一顆 cpu」，不用開 daemon：

```sh
python3 aos_cpu.py test/fx/counter --interval 1 --max-runs 3
python3 aos_cpu.py test/fx/counter --interval 1 --time-limit 10   # 跑 10 秒就自己退
cat test/fx/counter/.aos/last.json
```

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- 沒有 pause／resume、沒有 user 切換、沒有 config 版本。
- cpu 掛掉不會自動重開；daemon 也不看它為什麼掛。
- 停止條件只有三個：`--max-runs` 跑滿、收到 SIGTERM、`--time-limit` 到（硬時限，正在跑的那次直接當逾時砍掉）。沒有「exit code 到了就停」、「檔案出現就停」。
- 錯誤只記一條在 `last.json` 的 `error`，沒有重試、沒有退避、沒有通知。
- `$ref` 沒有範圍限制（能不能指到資料夾外＝行程權限說了算），也沒有深度上限。
- 請求沒有回覆通道給使用者：CLI `register` 只是把檔案丟出去就回，不等結果（要看結果自己去翻 `requests/done/`）。
- 同一個資料夾第二次 `register` 會被拒絕（daemon 那層看到的是 `spawn`，回 `ok:false`），不會把舊的收掉換新的；不過那顆 cpu 自己退了之後 daemon 會把它從登記表拿掉，就能再登記。
- 沒有權限檢查：誰都能寫 `daemon/requests/`，規矩只寫在這份 README。
- `runs.jsonl`、`daemon.log` 只長不消，沒有輪替。

daemon 的生死是使用者自己手動管的事（[proto4 筆記第 9 節](../proto4/notes/2026-09-08-ideas.md)）：它就是硬體，開機關機壞掉都不歸 aos 管，所以上面那些「daemon 被誰 SIGKILL」「daemon 重開接不接得回」「daemon 沒跑時丟請求誰撿」都不是這裡要解的問題。
