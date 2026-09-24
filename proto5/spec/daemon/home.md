← [daemon](README.md)｜[spec 總導航](../README.md)

# 1. 家

（2026-09-24 proto5-2 池式納入：孩子表搬出 `state.json`，改成一池一個資料夾、一顆一個小檔，見 [§1.2](pools.md)。）
為什麼改：第 1 版每次有孩子生或死就整份重寫 `state.json`。上萬個孩子時那份有幾 MB，一秒死幾顆就要重寫幾次。

```text
D/
  info.json                       身分與設定；人寫的
  state.json                      只剩 daemon 自己：pid、stopping、current（§1.3）
  requests/ responses/
  .daemon.lock                    daemon 家唯一的一把鎖（§6.1；agent 家另有 tick 鎖，見 aos-agent §2.1）
  pools/<pool>/pool.json          宣告（誰的、要哪幾號、樣板）；收到 scale 才寫
  pools/<pool>/kids/<i>.json      一顆一檔；只在那顆變了才寫
  pools/<pool>/summary.json       摘要（各狀態幾顆）；有變才寫，一圈最多一次
```

家由 `--target`，其次 `AOS_DAEMON_HOME`，再其次目前資料夾決定（`boot`／`halt`／`ls`／`scale`／`kill` 同一套找法）。主人是 `aos-daemon` 這個行程；
外人只能放 request、放 ack；`pools/` 底下的檔與 `state.json` 隨便偷看（kernel 就是偷看 `summary.json` 來知道池裡活了幾顆）。
孩子的家不在這裡——孩子的家是它自己的目標說了算（kernel 的 cpu 在 `K/pools/<P>/cpus/<i>/`）。
家裡沒有 `daemon.log`：daemon 的 stderr 跟著啟動它的終端走，要留檔就自己重導（例如 `aos-daemon boot --target D 2>>daemon.log &`）。

**池名的範圍是整個 daemon**：兩個 kernel 共用一個 daemon，池名（kernel 那邊的 `dpool`）就不能撞；撞了是 `NameTaken`（§3）。

**外人怎麼知道 daemon 活不活**：對 `.daemon.lock` 試拿非阻塞的**共享** flock——拿不到＝daemon 正持著獨占鎖＝活著；
拿到了立刻放掉＝沒有 daemon。不看 `state.json` 的 pid（daemon 被 KILL 檔不會更新）。

daemon 永遠以一般使用者跑，不用 root、不 sudo、不切使用者；隔離交給工具那層的 bwrap 牢（見 §8）。

## 1.1 `info.json`

```json
{"_metainfo": {"_type": "daemon", "_version": 2},
 "poll_ms": 20, "restart_delay_ms": 1000, "restart_max_ms": 60000, "stable_ms": 10000,
 "spawn_per_sec": 50, "max_children": 20000, "stop_wait_ms": 5000, "kill_wait_ms": 5000}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `poll_ms` | 正整數 | 20 | 一圈最多睡多久 |
| `restart_delay_ms` | 非負整數 | 1000 | 重拉等待的起點（第一次死；§4） |
| `restart_max_ms` | 非負整數 | 60000 | 重拉等待的上限；第 1 版 info 沒寫時取 max(60000, `restart_delay_ms`) |
| `stable_ms` | 非負整數 | 10000 | 活超過這麼久才算「穩了」，連死計數歸 0 |
| `spawn_per_sec` | 正整數 | 50 | 整個 daemon 每秒最多拉幾顆（含新拉、重拉） |
| `max_children` | 正整數 | 20000 | 所有池的成員加總上限；實際上限再取 `開檔上限 − 64`（§4） |
| `stop_wait_ms` | 非負整數 | 5000 | 停機階梯第一段：pipe 說 stop 之後等多久才 TERM |
| `kill_wait_ms` | 非負整數 | 5000 | 第二段：TERM 之後等多久才 KILL |

讀驗：`restart_max_ms` ≥ `restart_delay_ms`；bool 不算整數。不合＝`FieldTypeMismatch`、退 1。
`_version` 1 的 info（第 1 版）照樣讀，缺的用預設——只多了鍵，沒改舊鍵的意思。
整份解指示詞，中心是 D；沒有 `$opt`。daemon 啟動時沒有 info 就寫預設的，有就驗。

## 1.3 `state.json`

```json
{"pid": 100, "stopping": false, "current": null}
```

| 鍵 | 意思 |
|---|---|
| `pid` | daemon 的 PID；正常停機時寫 0 |
| `stopping` | 整個 daemon 收過 stop（§5） |
| `current` | 正在處理的 request（範式 §2 那格），daemon 也是一個家 |

第 1 版的 `children`（孩子表）拿掉。舊家的 `state.json` 還有 `children` 的，啟動時那些 pid 一併殺掉，之後 `children` 拿掉（§6.1）。

## 崩了會怎樣

- `pool.json`：宣告，重開後照用。寫一半不會發生（rename）。
- `kids/`：只拿來在**重開時找上一任的孩子**殺掉（§6.1）。重開後全部重寫。
- `summary.json`：從記憶體算出來的，重開後重算。

所以任何一個檔慢一拍都沒關係：真正的狀態是「daemon 記憶體＋`pool.json`」，其餘是給外人看的影子。
重拉的倒數、階梯走到哪一段這種**執行中的東西**只在記憶體，daemon 崩了就沒了，也不需要。
