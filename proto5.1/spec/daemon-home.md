# daemon 家與請求格式（第 1 版）

← [README](../README.md)｜程式：[aos-daemon](aos-daemon.md)

家由 `AOS_DAEMON_HOME` 決定，沒寫是 `~/.aos-daemon`；程式可用 `--home PATH` 覆蓋。
所有內容都是字面資料，不解指示詞。檔案原子寫入用同目錄唯一 `.tmp` 再 replace，沒有 fsync。

```text
D/
  requests/<epoch ns>-<pid>-<random 4 hex>.json
  requests/done/<同名>.json
  state.json
  daemon.pid
  daemon.log
  .daemon.lock
```

`aos-daemon` 建立缺少的家與 requests／done。ctl 不建立家：缺目錄為 `NotAHome`。
`.daemon.lock` 是持續存在的 POSIX flock 檔，daemon 執行期間持獨占鎖，防止同家兩支 daemon；
`daemon.pid` 只放十進位 pid 加換行，正常停機移除。log 接 runner 的 stdout／stderr。

## 請求與回音

請求是物件，只留四個 op，未知欄位原樣保存在回音；程式只處理 requests 第一層 `.json` 檔。

| op | 欄位 | 成功 result |
|---|---|---|
| `add` | `target` 必填，絕對 `.json` 路徑；`args` 缺省 `[]` | 新增的 entry |
| `remove` | `target` 同上 | runner 完全退出後的最後 entry，running=false、state=stopping |
| `ls` | 無 | `{pid,runs}` 快照；ctl 直接讀 state，不必交件 |
| `stop` | 無 | 所有 runner 退出、state 清空、pidfile 移除後回 `{stopped:true}` |

`target` 用 realpath 正規化，並作為 runs 的 key；可登記尚未存在的 `.json`，由 runner 反覆嘗試。
`args` 是旗標與整數值配對的字串陣列，只接受 `--interval-ms`、`--timeout-ms`、`--max-runs`、
`--stop-exit`（可重複）。前面三種是非負整數，stop-exit 是 0～255；status-fd 由 daemon 接管。
同 target 已登記（包括 stopping）回 `AlreadyRunning`；remove 不在表裡的 target 回 `NotRunning`。

```json
{"op":"add","target":"/abs/x.json","args":["--interval-ms","100"]}
```

回音為**原請求物件加** `ok` 布林與 `result`。失敗 result＝`{"code":"代號","msg":"白話"}`。
壞 JSON 無法保留原物件，回 `{"request":null,"ok":false,"result":...}`；非物件 JSON 保留於 request。

順序固定：執行 op → **先寫 done → 再刪原請求**。done 寫失敗時原單留著；重掃看見 done 同名
只刪原單，不重做 op。ctl 檔名使用 epoch ns＋pid＋隨機四位十六進位；同名 done 留存，不自動清理。
此順序避免「刪原單後還沒寫回音」的失單窗口，**並非跨副作用與 done 的交易**：
崩在建立 runner 後、發布 done 前仍可能重複或留下孤兒。

## state.json

```json
{"pid":1234,"runs":{"/abs/x.json":{"pid":2345,"target":"/abs/x.json","args":[],
 "state":"running","ready":true,"running":false,"runs":3,"last_exit":0,"last_kind":"child"}}}
```

entry **只有九格**：pid／target／args／state／ready／running／runs／last_exit／last_kind。
state 只有 `running`／`stopping`；ready、running 是布林；runs 是非負整數，初始 0；
last_exit 初始 null，之後是整數；last_kind 初始 null，之後 child／aos／usage。
ready 代表收到 runner ready；running 代表收到 start、尚未收到 done。runs／last_exit／last_kind
從 done 事件取得，不把 aos-run 自己退出碼混進來。runner 收屍後 entry 移除，不留完成清單。
正常停止後 state 是 `{"pid":0,"runs":{}}`，ctl ls 仍可讀。

快照可能落後實際 runner，不能拿 `running:false` 當排程互斥鎖；kernel 的安全換檔程序見
[aos-kernel](aos-kernel.md)。daemon 不收養崩潰前存活的舊 runner，不宣稱崩潰恢復或 exactly-once。
