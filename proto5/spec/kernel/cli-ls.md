← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：ls

```
aos-kernel ls [--target K] [--pool P] [--procs] [--json] [-v|--verbose]
```

`ls` 不是 syscall：偷看 `K/info.json`、`K/state.json`、各池 daemon 的 `summary.json`（`--pool` 時加 `kids/`）、kernel cpu 的 `state.json` 與 `requests/`；不放單、不拿鎖，鏈斷了也能看。
文字版與 `--json` 出自同一份資料（`lib/aos_kernel_ls.py` 的 `ls_data()`），判定一樣。第一行 health 的判定在 [health.md](health.md)。
`--pool P`：只看那池（池在 info 與帳本都沒有＝`NotFound` 退 1）。

## 人看的版本

```
health ok
kernel  running  seq 128  daemon alive  tick 1000ms
  kcpu kernel/0  正在跑一格  requests 1
pool    2 個工作池：要 3 顆、忙 2、閒 1
  kernel   want 1  sent 1   daemon k1-kernel: running 1 restarting 0 pending 0 dead 0 failed 0
  default  want 2  sent 2  busy 1  idle 1  draining 0   daemon default: running 2 restarting 0 pending 0 dead 0 failed 0
  llm      want 1  sent 1  busy 1  idle 0  draining 0   daemon llm: running 1 restarting 0 pending 0 dead 0 failed 0
proc    3 個（反覆 2、once 1）：queued 1、running 2
  行程       種類  狀態     runs  fails  回音  備註
  agent-bob  反覆  running    40      1  -     重試中（連敗 1/3）
  （其餘 2 個沒事的沒列；--procs 全列）
queue   1：agent-amy
```

- `kernel` 行：`phase`（沒帳本＝`沒 boot 過`）、`seq`（`last_seq`，沒有＝`-`）、daemon `alive`／`dead`（**kernel 池的 daemon**）、`tick_ms`。
  下一行 kernel cpu：名字、`正在跑一格`（`state.current` 有東西）／`沒在跑`、`requests/` 裡幾份——鏈斷了就是 `沒在跑  requests 0` 而 seq 不動。
- `pool` 標題：工作池數（不含 kernel 池）、要幾顆（`want` 總和）、忙、閒，有收掉中的再加 `、收掉中 D`。
  下面每池一行（縮排 2 格，格式＝[`cpu ls`](cli-cpu.md) 的池行，含尾註；kernel 池也一行、排第一）。
  `--pool P` 時那池下面再縮排 4 格、一顆一行（格式＝`cpu ls --pool`）。
- `proc` 標題：總數、反覆／once 各幾個、各 `status` 幾個（照字母排）。沒行程＝只印 `proc    0 個`。
  下面是對齊表（行程、種類 反覆／once、狀態、runs、fails、回音（`pending` 有東西印 `等`）、備註（agent 的暫停／重試標記：`連敗暫停中`、`手動暫停中`、
  `手動暫停中＋連敗暫停中`、`重試中（連敗 N/3）`、`已解除暫停，等下一次成功`））。
  **預設只列 `bad` 與有暫停／重試標記的行程**，其餘印一行 `（其餘 N 個沒事的沒列；--procs 全列）`；`--procs` 全列（上萬個時很長）。
  `--pool P` 時只列那池的行程。表下面每個列出來的 `bad` 行程一行 `  <名字> 壞了，看 <路徑>`（target 的 inst 有字面 `stderr` 就指它，agent 就是 `<家>/log/agent.err`；
  沒有字面 `stderr`（沒寫、寫成指示詞、不是 JSON）就指 target 本身）。
- `queue` 行：排隊中＝`status` 是 `queued` 的行程（照帳本 `procs` 的順序）；個數＋名字，最多列 8 個，多的寫 `…還有 N 個`；空＝`-`。
- **長的東西不進主表**：行程名超過 24 格寬就砍中間（留頭和尾，中間 `…`）；K、D、chain、kernel cpu 正在跑的那格檔名、每個行程的 target 都只在 `-v`。對齊時中日韓字算 2 格。
- `-v`：kernel 行下面改成 `K`、`D`、`chain`、`kcpu … current <檔名> requests N` 四行；表裡的名字不截；列出來的行程下多一行 `  <名字>  target <路徑>`；queue 全列。

## `--json`（`aos_kernel_ls` 第 2 版）

stdout 只有**一個 JSON 物件加一個換行**；警告與錯誤一律走 stderr。退出碼跟文字版一樣：印得出來＝0；帳本或 info 讀不到＝1（stdout 空，stderr 一行 `aos-kernel: <代號>: …`）；用法錯＝2。
`-v`、`--procs` 對 `--json` 沒作用。

```json
{"_metainfo": {"_type": "aos_kernel_ls", "_version": 2},
 "health": {"code": "ok", "message": "ok"},
 "kernel": {"home": "/abs/K", "chain": "1790…-4242", "phase": "running", "last_seq": 128,
            "daemon": {"home": "/abs/D", "alive": true},
            "cpu": {"name": "kernel/0", "current": "k-1790…-4242-128.json", "requests": 1},
            "settings": {"tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0, "done_exit": 100, "bad_after": 10}},
 "pools": {"default": {"pool": "default", "want": 2, "sent": 2, "busy": 1, "idle": 1, "draining": 0,
                       "daemon": "/abs/D", "dpool": "default", "daemon_alive": true, "summary": {"running": 2, "…": "…"},
                       "declared": true, "removing": false, "moving": false, "new_location": ["/abs/D", "default"],
                       "phase": "running", "pending": null, "error": null, "waiting": [], "gone": false}},
 "procs": [{"name": "agent-bob", "once": false, "pool": "default", "status": "running", "runs": 40, "fails": 1,
            "pending": false, "target": "/abs/bob/tick.json",
            "mark": {"code": "retrying", "text": "重試中（連敗 1/3）"}, "look": null}],
 "queue": ["agent-amy"],
 "counts": {"pools": {"total": 2, "want": 3, "sent": 3, "busy": 2, "idle": 1, "draining": 0},
            "procs": {"total": 3, "repeat": 2, "once": 1, "status": {"queued": 1, "running": 2}},
            "queue": 1}}
```

| 欄 | 型別與意思 |
|---|---|
| `_metainfo` | 固定 `{"_type": "aos_kernel_ls", "_version": 2}`。版本內**固定欄位只加鍵、不改名、不刪、不改型別**；要改就升 `_version`。`counts.procs.status`、`pools` 的池名是資料映射，鍵集合隨內容變，不算在這條承諾裡 |
| `health` | `code`（[health.md](health.md) 那幾個字串）、`message`（跟文字版第一行 `health ` 後面一字不差） |
| `kernel` | 同第 1 版：`home`（K 絕對路徑）；`chain`／`phase`／`last_seq`（沒帳本＝`null`）；`daemon{home, alive}`（kernel 池的 daemon，flock 探測）；`cpu{name, current, requests}`（`name`＝帳本 `kcpu`；`current`＝正在跑的那則檔名或 `null`；`requests` int）；`settings` 固定五鍵（省略的已補預設） |
| `pools` | 物件，池名 → 那池一格（含 kernel 池），欄位同 `cpu ls --json` 的池格：`want`、`sent`、`busy`、`idle`、`draining`（沒宣告過或 kernel 池不適用＝`null`）、`daemon`、`dpool`、`daemon_alive`、`summary`（daemon 的摘要原樣或 `null`）、`declared`（帳本有這格）、`removing`（info 已拿掉）、`moving`、`new_location`、`phase`、`pending`（在途 scale 單或 `null`）、`error`（`{code, message}` 或 `null`）、`waiting`（收掉中那幾顆手上的行程名）、`gone`（摘要不在但 `sent` 不空）。`--pool` 時那格多 `cpus` 陣列，每格 `cpu`（`P/<i>`）、`status`、`proc`、`daemon`（`{state, gen, pid}` 或 `null`）、`declared` |
| `procs[]` | 同第 1 版：帳本 `procs` 的順序；`name`；`once`（bool）；`pool`（不是字串＝`null`）；`status`（不是字串＝`"unknown"`）；`runs`、`fails`（不是整數＝0）；`pending`（bool）；`target`（或 `null`）；`mark`（`{code, text}`，code 是 `paused`／`manual_paused`／`both_paused`／`retrying`／`resuming`，沒有＝`null`）；`look`（`bad` 時要看的檔，否則 `null`）。`--pool` 只留那池的；**不受 `--procs` 影響，一律全列** |
| `queue` | 排隊中的行程名（`status` 是 `queued`） |
| `counts` | `pools{total, want, sent, busy, idle, draining}`（**只算工作池**）；`procs{total, repeat, once, status}`（同第 1 版）；`queue`（個數） |

第 1 版的 `cpus[]`、`counts.cpus` 拿掉（daemon 已沒有孩子表，改看池）。要原始帳本就直接讀 `K/state.json`（§1.2）。
