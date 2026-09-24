# daemon 的家：池與孩子表怎麼存

← [spec 導航](README.md)｜怎麼對帳：[daemon-reconcile](daemon-reconcile.md)｜指令：[daemon-cli](daemon-cli.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/daemon.md](../../proto5/spec/daemon.md) §1.1、§1.2**（孩子表搬出 `state.json`，改成一池一個資料夾、一顆一個小檔）。
> 家的位置（`--target`，省略找 `AOS_DAEMON_HOME` 再 `./`，照 fix-r4）、`.daemon.lock`、flock 探測活不活都不變。

為什麼改：proto5 每次有孩子生或死就整份重寫 `state.json`。上萬個孩子時那份有幾 MB，一秒死幾顆就要重寫幾次。

## 1. 目錄與 `info.json`

```text
D/
  info.json
  state.json                      只剩 daemon 自己：pid、stopping、current
  requests/ responses/
  .daemon.lock
  pools/<pool>/pool.json          宣告（誰的、要哪幾號、樣板）；收到 scale 才寫
  pools/<pool>/kids/<i>.json      一顆一檔；只在那顆變了才寫
  pools/<pool>/summary.json       摘要（各狀態幾顆）；有變才寫，一圈最多一次
```

```json
{"_metainfo": {"_type": "daemon", "_version": 2},
 "poll_ms": 20, "restart_delay_ms": 1000, "restart_max_ms": 60000, "stable_ms": 10000,
 "spawn_per_sec": 50, "max_children": 20000, "stop_wait_ms": 5000, "kill_wait_ms": 5000}
```

| 鍵 | 沒寫時 | 意思 |
|---|---|---|
| `poll_ms`、`stop_wait_ms`、`kill_wait_ms` | 同 proto5 | 同 proto5 |
| `restart_delay_ms` | 1000 | 重拉等待的起點（第一次死） |
| `restart_max_ms` | 60000 | 重拉等待的上限 |
| `stable_ms` | 10000 | 活超過這麼久才算「穩了」，連死計數歸 0 |
| `spawn_per_sec` | 50 | 整個 daemon 每秒最多拉幾顆（含新拉、重拉） |
| `max_children` | 20000 | 所有池的成員加總上限；實際上限再取 `開檔上限 − 64`（[daemon-reconcile §5](daemon-reconcile.md)） |

`_version` 1 的 info（proto5）照樣讀，缺的用預設——daemon 的 info 只多了鍵，沒改舊鍵的意思。

## 2. `pool.json`：宣告

```json
{"pool": "k1-default", "owner": "/abs/K", "count": 8, "skip": [], "ver": 5,
 "target": "/abs/K/pools/default/cpus/{name}/inst.json", "dir_target": ".aos/inst.json",
 "home": "/abs/K/pools/default/cpus/{name}"}
```

就是 [protocol §1](protocol.md) `scale` 收到的東西加上 `ver`。**這是 daemon 唯一要記住、重開後還算數的東西**：daemon 重開照它把孩子拉回來（[handoff §2](handoff.md)）。
一次原子寫（`.tmp` 再 rename）。

## 3. `kids/<i>.json`：一顆一檔

```json
{"pid": 2345, "gen": 3, "state": "running", "since": 1790000000.0,
 "exits": 2, "streak": 1, "last_exit": 1, "next_at": null}
```

| 鍵 | 意思 |
|---|---|
| `pid` | 現在（或最後一次）那支的 PID |
| `gen` | 第幾代：每拉一次加 1。人看得出「這號被重拉過」 |
| `state` | `running`／`dead`（死了、在等重拉）／`failed`（拉不起來，`SpawnFailed`，在等再試）／`killing`（走階梯中） |
| `since` | 這一代拉起來的 epoch 秒 |
| `exits`／`last_exit` | 死過幾次、上次的退出碼（同 proto5） |
| `streak` | 連死幾次（活超過 `stable_ms` 才歸 0）；決定等多久再拉 |
| `next_at` | `dead`／`failed` 什麼時候可以再拉（epoch 秒）；其他狀態 null |

**什麼時候寫**：拉起來（fork 之後、`go` 之前，同 proto5 的 `go` 握手順序）、死了、開始走階梯、再試失敗。閒著不寫。
**什麼時候刪**：那號不再是成員、而且孩子已經死透（收屍之後）。
**還沒拉過的新號沒有檔**：宣告從 8 號長到 10000 號時，不會一口氣寫 9992 個檔；那些號只在記憶體裡排隊（狀態 `pending`），拉到它才寫。

## 4. `summary.json`：摘要

```json
{"pool": "k1-default", "owner": "/abs/K", "count": 8, "ver": 5,
 "running": 7, "restarting": 1, "pending": 0, "dead": 1, "failed": 0, "killing": 0,
 "updated": 1790000000.5}
```

- `running`：活著的；`restarting` 是其中「死過、重拉後還沒活過 `stable_ms`」的那些（**包含在 `running` 裡**）。
- `pending`：宣告裡有、還沒拉過（節流排隊中）。`dead`、`failed`、`killing` 同上表。
- 成員數 ＝ running＋pending＋dead＋failed；`killing` 是正要收掉的（可能是成員＝砍掉重來，也可能不是＝縮小）。
- **沒有「忙」**：daemon 不知道孩子在做什麼。`ls` 要數忙的才去偷看每顆家的 `state.json`（O(活著的數量)，[daemon-cli](daemon-cli.md)）。

kernel 的 `ls`、`cpu ls` 讀這份，不讀 `kids/`。

## 5. `state.json`

```json
{"pid": 100, "stopping": false, "current": null}
```

`children` 那格拿掉，其他同 proto5。

## 6. 崩了會怎樣

- `pool.json`：宣告，重開後照用。寫一半不會發生（rename）。
- `kids/`：只拿來在**重開時找上一任的孩子**殺掉（同 proto5 §6.1 用舊孩子表的方式）。重開後全部重寫。
- `summary.json`：從記憶體算出來的，重開後重算。

所以任何一個檔慢一拍都沒關係：真正的狀態是「daemon 記憶體＋`pool.json`」，其餘是給外人看的影子。
