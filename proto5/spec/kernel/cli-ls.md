← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：ls（09-24 advice-r1 改版）

```
aos-kernel ls [--target K] [--json] [-v|--verbose]
```

`ls` 不是 syscall：偷看 `K/info.json`、`K/state.json`、D 的 `state.json`（D＝info 記的 `daemon`，沒有就 `AOS_DAEMON_HOME`→目前資料夾）、kernel cpu 的 `state.json` 與 `requests/`；不放單、不拿鎖，鏈斷了也能看。
（09-24 advice-r1，使用者要的）人看的版本改成對齊的表，`--json` 改成欄位穩定的一份物件（取代原本整份帳本原樣吐出）。兩個版本出自同一份資料（`lib/aos_kernel_ls.py` 的 `ls_data()`），判定一樣。

## 第一行 health（不變）

文字版第一行一定是 `health <一句>`，`--json` 的 `health: {code, message}` 是同一句。判定順序與句子照舊（[cli-ops.md 的 ls 段](cli-ops.md)）：
`dirs` → `stopped` → `daemon` → `cpus` → `recovering` → `stall` → `ok`；讀不到＝`broken`（這時整支退 1）；kernel `ok` 時再看 agent：`agents_paused` → `retrying` → `resuming`。

## 人看的版本

```
health ok
kernel  running  seq 128  daemon alive  tick 1000ms
  kcpu k  正在跑一格  requests 1
cpu     4 顆：忙 2、閒 1、kernel 1
  池       cpu  工作  行程                      daemon
  default  0    忙    agent-bob                 running
           1    閒    -                         running
  llm      llm  忙    aw-amy-17902…4-775238-3   running
  kernel   k    tick  -                         running
proc    3 個（反覆 2、once 1）：queued 1、running 2
  行程                      種類  狀態     runs  fails  回音  備註
  agent-amy                 反覆  queued     12      0  -
  agent-bob                 反覆  running    40      1  -     重試中（連敗 1/3）
  aw-amy-17902…4-775238-3   once  running     0      0  等
queue   1：agent-amy
```

- `kernel` 行：`phase`（沒帳本＝`沒 boot 過`）、`seq`（`last_seq`，沒有＝`-`）、daemon `alive`／`dead`、`tick_ms`。下一行 kernel cpu：名字、`正在跑一格`（`state.current` 有東西）／`沒在跑`、`requests/` 裡幾份——鏈斷了就是 `沒在跑  requests 0` 而 seq 不動。
- `cpu` 表：info 的 cpu、帳本 `cpus` 的、帳本的 `kcpu` 聯集，**按池分組**（池照第一次出現的順序，同池第二顆起池欄留白）。`工作`：`閒`／`忙`／`忙（rm）`（行程已被 rm、回音到了丟掉）／kernel cpu 是 `tick`；`行程`＝忙的時候是哪個行程；`daemon`＝D 孩子表裡的 `state`（`running`／`dead`／`killing`…，不在表裡＝`missing`）。
  **daemon 沒在跑時**孩子表是舊的：整欄印 `-`，標題行尾加 `（daemon 沒在跑，孩子狀態不明）`（取代 fix-r5 的 `dead（daemon 沒在跑）`）。標題的顆數：全部幾顆；忙／閒只算工作 cpu，kernel cpu 另計。
- `proc` 表：帳本 `procs` 的順序。標題：總數、反覆／once 各幾個、各 `status` 幾個（照字母排）。`種類` 反覆／once；`回音`＝`pending` 有東西印 `等`；`備註`＝agent 的暫停／重試標記（`連敗暫停中`、`手動暫停中`、`手動暫停中＋連敗暫停中`、`重試中（連敗 N/3）`、`已解除暫停，等下一次成功`，fix-r5 的那套），沒有就空。沒行程＝只印 `proc    0 個`。
- 表下面：每個 `bad` 行程一行 `  <名字> 壞了，看 <路徑>`（路徑規則照舊：target 的 inst 有字面 `stderr` 就指它，agent 就是 `<家>/log/agent.err`；否則指 target）。
- `queue` 行：個數＋名字，最多列 8 個，多的寫 `…還有 N 個`；空＝`-`。
- **長的東西不進主表**：行程名超過 24 格寬就砍中間（留頭和尾，中間 `…`）；K、D、chain、kernel cpu 正在跑的那格檔名、每個行程的 target 都只在 `-v`。對齊時中日韓字算 2 格。
- `-v`：kernel 行下面多 `K`、`D`、`chain`、`kcpu … current <檔名>` 四行；表裡的名字不截；proc 表下多每個行程一行 `  <名字>  target <路徑>`；queue 全列。

## `--json`

stdout 只有**一個 JSON 物件加一個換行**；警告與錯誤一律走 stderr。退出碼跟文字版一樣：印得出來＝0；帳本或 info 讀不到＝1（stdout 空，stderr 一行 `aos-kernel: <代號>: …`）；用法錯＝2。`-v` 對 `--json` 沒作用。

```json
{"_metainfo": {"_type": "aos_kernel_ls", "_version": 1},
 "health": {"code": "ok", "message": "ok"},
 "kernel": {"home": "/abs/K", "chain": "1790…-4242", "phase": "running", "last_seq": 128,
            "daemon": {"home": "/abs/D", "alive": true},
            "cpu": {"name": "k", "current": "k-1790…-4242-128-….json", "requests": 1},
            "settings": {"tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0, "done_exit": 100, "bad_after": 10}},
 "cpus": [{"name": "0", "pool": "default", "kernel": false, "busy": true, "proc": "agent-bob",
           "req": "k-…-0.json", "discard": false, "child": "running"}],
 "procs": [{"name": "agent-bob", "once": false, "pool": "default", "status": "running", "runs": 40, "fails": 1,
            "pending": false, "target": "/abs/bob/tick.json",
            "mark": {"code": "retrying", "text": "重試中（連敗 1/3）"}, "look": null}],
 "queue": ["agent-amy"],
 "counts": {"cpus": {"total": 3, "busy": 1, "idle": 2},
            "procs": {"total": 3, "repeat": 2, "once": 1, "status": {"queued": 1, "running": 2}},
            "queue": 1}}
```

| 欄 | 型別與意思 |
|---|---|
| `_metainfo` | 固定 `{"_type": "aos_kernel_ls", "_version": 1}`。版本內**只加鍵、不改名、不刪、不改型別**；要改就升 `_version` |
| `health` | `code`（上面那幾個字串）、`message`（跟文字版第一行 `health ` 後面一字不差） |
| `kernel.home` | K 的絕對路徑 |
| `kernel.chain`／`phase`／`last_seq` | 帳本的值；沒帳本＝`null` |
| `kernel.daemon` | `home`（這次看的 D，絕對路徑）、`alive`（flock 探測，bool） |
| `kernel.cpu` | kernel cpu：`name`（帳本 `kcpu`，沒有＝`null`）、`current`（它正在跑的那則檔名或 `null`）、`requests`（`requests/` 裡幾份，int） |
| `kernel.settings` | info 的 `tick_ms`、`interval_ms`、`timeout_ms`、`done_exit`、`bad_after`（省略的已補預設，int） |
| `cpus[]` | 順序＝info 的 cpu 順序，接著帳本裡多的，最後 `kcpu`（已在就不重複）。`name`；`pool`（info 裡沒有這顆＝`null`）；`kernel`（是不是 `kcpu`）；`busy`（帳本 `req` 有值）；`proc`（忙的時候是哪個行程，閒＝`null`）；`req`（帳本那格原值）；`discard`（bool）；`child`（D 孩子表的 `state`，不在表＝`"missing"`，**daemon 沒活＝`null`**） |
| `procs[]` | 帳本 `procs` 的順序。`name`；`once`（bool）；`pool`；`status`；`runs`、`fails`（int）；`pending`（bool：還有沒回的 add）；`target`（絕對路徑）；`mark`（agent 的暫停／重試標記 `{code, text}`，code 是 `paused`／`manual_paused`／`both_paused`／`retrying`／`resuming`，沒有＝`null`）；`look`（`bad` 時要看的檔，否則 `null`） |
| `queue` | 帳本的 `queue`（行程名的陣列，先進先出） |
| `counts` | `cpus.total`／`busy`／`idle`（**只算工作 cpu**，不含 kcpu）；`procs.total`／`repeat`／`once`、`procs.status`（`status → 個數`）；`queue`（個數） |

要原始帳本就直接讀 `K/state.json`（§1.2）；`ls --json` 不再原樣吐帳本。
