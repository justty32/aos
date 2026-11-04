← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：ls `--json`

（2026-09-24 one-boot 從 [cli-ls.md](cli-ls.md) 拆出來；文字版在那邊。）

## `aos_kernel_ls` 第 3 版

**為什麼升第 3 版**（2026-09-24 one-boot）：kernel cpu 不存在了，第 2 版的 `kernel.cpu` 留著只會說謊；可是第 2 版承諾過「固定欄位不刪、不改名」，所以升版。
跟第 2 版只差兩處：`kernel.cpu` 拿掉、換成 `kernel.tick`；`pools` 不再有 kernel 池。其他照第 2 版。讀的程式先看 `_metainfo._version`。

stdout 只有**一個 JSON 物件加一個換行**；警告與錯誤一律走 stderr。退出碼跟文字版一樣：印得出來＝0；帳本或 info 讀不到＝1（stdout 空，stderr 一行 `aos-kernel: <代號>: …`）；用法錯＝2。
`-v`、`--procs` 對 `--json` 沒作用。

```json
{"_metainfo": {"_type": "aos_kernel_ls", "_version": 3},
 "health": {"code": "ok", "message": "ok"},
 "kernel": {"home": "/abs/K", "chain": "1790…-4242", "phase": "running", "last_seq": 128,
            "daemon": {"home": "/abs/D", "alive": true},
            "tick": {"registered": true, "every_ms": 1000, "fails": 0, "last_exit": null, "last_at": 1790000128.4},
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
| `_metainfo` | 固定 `{"_type": "aos_kernel_ls", "_version": 3}`。版本內**固定欄位只加鍵、不改名、不刪、不改型別**；要改就升 `_version`。`counts.procs.status`、`pools` 的池名是資料映射，鍵集合隨內容變，不算在這條承諾裡 |
| `health` | `code`（[health.md](health.md) 那幾個字串）、`message`（跟文字版第一行 `health ` 後面一字不差） |
| `kernel` | `home`（K 絕對路徑）；`chain`／`phase`／`last_seq`（沒帳本＝`null`）；`daemon{home, alive}`（**開 tick 的 daemon**：帳本 `ticker`，沒有就照 info；flock 探測）；`tick{registered, every_ms, fails, last_exit, last_at}`（第 3 版新增，取代第 2 版的 `cpu`）：`registered`＝bool，daemon 登記著這個 kernel；`every_ms`＝登記的 `tick_ms`；`fails`＝連敗次數（0＝沒事）；`last_exit`＝最近一次失敗那格的退出碼（逾時被 KILL＝137；開不起來、從沒失敗過＝`null`；失敗後恢復＝0）；`last_at`＝帳本 `last_tick_at`（epoch 秒，沒有＝`null`）。沒登記時 `every_ms`／`fails`／`last_exit` 是 `null`，`last_at` 照帳本；`settings` 固定五鍵（省略的已補預設） |
| `pools` | 物件，池名 → 那池一格（第 3 版起**沒有** kernel 池），欄位同 `cpu ls --json` 的池格：`want`（info 的 count，info 已拿掉＝0）、`sent`／`idle`／`draining`（帳本沒這格＝`null`）、`busy`（帳本沒這格＝`0`）、`daemon`、`dpool`、`daemon_alive`、`summary`（daemon 的摘要原樣或 `null`）、`declared`（帳本有這格）、`removing`（info 已拿掉）、`moving`、`new_location`、`phase`、`pending`（在途 scale 單或 `null`）、`error`（`{code, message}` 或 `null`）、`waiting`（收掉中那幾顆手上的行程名）、`gone`（摘要不在但 `sent` 不空）。`--pool` 時那格多 `cpus` 陣列，每格 `cpu`（`P/<i>`）、`status`、`proc`、`daemon`（`{state, gen, pid}` 或 `null`）、`declared` |
| `procs[]` | 同第 1 版：帳本 `procs` 的順序；`name`；`once`（bool）；`pool`（不是字串＝`null`）；`status`（不是字串＝`"unknown"`）；`runs`、`fails`（不是整數＝0）；`pending`（bool）；`target`（或 `null`）；`mark`（`{code, text}`，code 是 `paused`／`manual_paused`／`both_paused`／`retrying`／`resuming`，沒有＝`null`）；`look`（`bad` 時要看的檔，否則 `null`）；（09-24 停車，加鍵）`parked`（bool，退 102 停著）。`--pool` 只留那池的；**不受 `--procs` 影響，一律全列** |
| `queue` | 排隊中的行程名（`status` 是 `queued`） |
| `counts` | `pools{total, want, sent, busy, idle, draining}`（**只算工作池**）；`procs{total, repeat, once, status, parked}`（同第 1 版；`parked` 是 09-24 停車加的鍵）；`queue`（個數） |

第 1 版的 `cpus[]`、`counts.cpus` 拿掉（daemon 已沒有孩子表，改看池）。第 2 版的 `kernel.cpu` 在第 3 版拿掉（見上）。
要一個行程的原始帳本那筆，用 `aos-kernel proc NAME --json`（[cli.md 的 proc](cli.md)）；帳本本身是 sqlite（§1.2），別直接讀。
