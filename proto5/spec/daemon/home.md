← [daemon](README.md)｜[spec 總導航](../README.md)

# 1. 家

```text
D/
  info.json           身分與設定；人寫的
  state.json          孩子表；daemon 寫的
  requests/ responses/
  .daemon.lock        daemon 家唯一的一把鎖（§6.1；09-24 fix-r4 後 agent 家另有 tick 鎖，見 aos-agent.md §2.1）
```

家由 `--target`，其次 `AOS_DAEMON_HOME`，再其次目前資料夾決定（09-24 fix-r4 改：`--home` 與 `~/.aos-daemon` 預設拿掉；`boot`／`halt` 同一套找法，kernel 的 `--daemon-target` 省略時也一樣）。主人是 `aos-daemon` 這個行程；
外人只能放 request、放 ack，`state.json` 隨便偷看（kernel 就是偷看它來知道孩子活不活）。
孩子的家不在這裡——孩子的家是它自己的目標說了算（kernel 的 cpu 在 `K/cpus/<name>/`）。
（09-24 試玩 r1 補）家裡沒有 `daemon.log`：daemon 的 stderr 跟著啟動它的終端走，要留檔就自己重導（例如 `aos-daemon boot --target D 2>>daemon.log &`）。

**`name` 的範圍是整個 daemon**：兩個 kernel 想共用一個 daemon，cpu 名就不能撞（撞了是 `NameTaken`，§3）。

**外人怎麼知道 daemon 活不活**：對 `.daemon.lock` 試拿非阻塞的**共享** flock——拿不到＝daemon 正持著獨占鎖＝活著；
拿到了立刻放掉＝沒有 daemon。不看 `state.json` 的 pid（daemon 被 KILL 檔不會更新）。

## 1.1 `info.json`

```json
{"_metainfo": {"_type": "daemon", "_version": 1},
 "poll_ms": 20, "restart_delay_ms": 1000, "stop_wait_ms": 5000, "kill_wait_ms": 5000}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `poll_ms` | 正整數 | 20 | 一圈看一次 requests／孩子有沒有死的間隔 |
| `restart_delay_ms` | 非負整數 | 1000 | 孩子死了到再拉之間至少隔多久（擋崩潰迴圈空轉） |
| `stop_wait_ms` | 非負整數 | 5000 | 停機階梯第一段：pipe 說 stop 之後等多久才 TERM |
| `kill_wait_ms` | 非負整數 | 5000 | 第二段：TERM 之後等多久才 KILL |

整份解指示詞，中心是 D；沒有 `$opt`。daemon 啟動時沒有 info 就寫預設的，有就驗。

## 1.2 `state.json`

```json
{"pid": 100, "stopping": false,
 "current": null,
 "children": {
   "k": {"target": "/abs/K/cpus/k/inst.json", "dir_target": ".aos/inst.json", "restart": true,
         "pid": 2345, "alive": true, "state": "running", "exits": 0, "last_exit": null, "since": 1790000000.0}}}
```

| 鍵 | 意思 |
|---|---|
| `pid` | daemon 的 PID；正常停機時寫 0 |
| `stopping` | 整個 daemon 收過 stop（§5） |
| `current` | 正在處理的 request（範式 §2 那格），daemon 也是一個家 |
| `children.<name>` | `spawn` 給的 `target`／`dir_target`／`restart`；現在的 `pid`（死了是上一個）；`alive`；`state` 是 `running`／`killing`／`dead`；`exits` 死過幾次；`last_exit` 上次的退出碼；`since` 這一代拉起來的 epoch 秒 |

孩子表只在變動時寫（spawn、死、重拉、kill、停機），閒著不重寫。表裡的是**身分**（誰、哪個目標、pid、活不活），
重啟後只拿來找上一任的孩子（§6.1），不拿來接手。重拉的倒數、階梯走到哪一段這種**執行中的東西**只在記憶體，
daemon 崩了就沒了，也不需要——重啟後孩子表清空。

（09-24 補）`last_exit` 與重拉判定只用孩子實際的退出碼；exit 檔寫失敗另記 `WriteFailed`，不改退出碼，
也不因此重拉正常退出的孩子。
