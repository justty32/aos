← [daemon](README.md)｜[spec 總導航](../README.md)

## 1.2 池：宣告、一顆一檔、摘要

（2026-09-24 proto5-2 池式納入，取代第 1 版 `state.json` 的 `children` 孩子表。）

### `pool.json`：宣告

```json
{"pool": "k1-default", "owner": "/abs/K", "count": 8, "skip": [], "ver": 5, "decl": [1790000000000000000, 41],
 "target": "/abs/K/pools/default/cpus/{name}/inst.json", "dir_target": ".aos/inst.json",
 "home": "/abs/K/pools/default/cpus/{name}"}
```

就是 [§3 `scale`](methods.md) 收到的東西加上 `ver`。**這是 daemon 唯一要記住、重開後還算數的東西**：daemon 重開照它把孩子拉回來（§6.1）。
一次原子寫（`.tmp` 再 rename）。開機讀到壞的 `pool.json`＝整個不開（`ReadFailed`、退 1），不猜、不默默丟掉宣告。

### `kids/<i>.json`：一顆一檔

```json
{"pid": 2345, "gen": 3, "state": "running", "since": 1790000000.0,
 "exits": 2, "streak": 1, "last_exit": 1, "next_at": null}
```

| 鍵 | 意思 |
|---|---|
| `pid` | 現在（或最後一次）那支的 PID；從沒拉成功過＝null（`since` 也是 null） |
| `gen` | 第幾代：每次**拉成功**加 1，從 1 起。daemon 重開不歸零（kids 檔留著）；那號被移出宣告、檔刪掉之後再加回來才從 1 重算 |
| `state` | `running`／`dead`（死了、在等重拉）／`failed`（拉不起來，`SpawnFailed`，在等再試）／`killing`（走階梯中）／`pending`（重開或 halt 後、還沒拉） |
| `since` | 這一代拉起來的 epoch 秒 |
| `exits`／`last_exit` | 死過幾次、上次的退出碼（只用孩子實際的退出碼） |
| `streak` | 連死幾次（活超過 `stable_ms` 才歸 0）；決定等多久再拉。活滿 `stable_ms` 時只改記憶體，檔要到下次寫才更新 |
| `next_at` | `dead`／`failed` 什麼時候可以再拉（epoch 秒）；其他狀態 null |

**什麼時候寫**：拉起來（fork 之後、`go` 之前，[§2](spawn.md) 的 `go` 握手順序）、死了、開始走階梯、再試失敗。閒著不寫。
fork 之後 kids 檔寫不進去：不送 `go`、直接關 fd 0（孩子讀到 EOF 自己退），當成死了（dead、加 streak）。
**什麼時候刪**：那號不再是成員、而且孩子已經死透（收屍之後）。
**還沒拉過的新號沒有檔**：宣告從 8 號長到 10000 號時，不會一口氣寫 9992 個檔；那些號只在記憶體裡排隊（狀態 `pending`），拉到它才寫。

### `summary.json`：摘要

```json
{"pool": "k1-default", "owner": "/abs/K", "count": 8, "ver": 5,
 "running": 7, "restarting": 1, "pending": 0, "dead": 1, "failed": 0, "killing": 0, "draining": 0,
 "updated": 1790000000.5}
```

- `running`：活著的；`restarting` 是其中「死過、重拉後還沒活過 `stable_ms`」的那些（**包含在 `running` 裡，不另外算**）。
- `pending`：宣告裡有、現在沒有孩子（還沒拉過，或 kill 之後等重拉）。`dead`、`failed` 同上表。
- `killing` 是成員、正在砍掉重來的；`draining` 是已經移出宣告、正在收的。
- **成員數 ＝ running＋pending＋dead＋failed＋killing**；`draining` 不算成員。
- **沒有「忙」**：daemon 不知道孩子在做什麼。`ls` 要數忙的才去偷看每顆家的 `state.json`（O(活著的數量)，[§6.3](cli.md)）。
- 寫失敗就留著下一圈再寫。daemon `halt` 之後摘要是 `count N`、各格 0（成員都「拿掉」了），重開再算。

kernel 的 `ls`、`cpu ls` 讀這份，不讀 `kids/`。

**池拿掉**：`count: 0` 的宣告收完全部孩子後，daemon 依序刪 `summary.json` → `pool.json` → 資料夾；前一步沒成功不做下一步，每圈重試到資料夾消失。
外人把「`summary.json` **確定不在**」（檔或池資料夾不存在）當成「池已完全拿掉」；讀不到、壞 JSON 一律當「還在」（`aos_daemon.pool_summary_state` 回 `gone`／`ok`／`unknown`，只有 `gone` 算消失）。
開機時看到沒有 `pool.json` 的池資料夾（崩在拿掉池的中途）：裡面 kids 檔的舊 pid 照樣殺，然後整個資料夾刪掉。
