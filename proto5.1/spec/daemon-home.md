# daemon 家與請求格式

← [README](../README.md)｜程式：[aos-daemon](aos-daemon.md)

家由 `AOS_DAEMON_HOME` 決定，沒寫是 `~/.aos-daemon`；`--home PATH` 可覆蓋。
內容都是字面值，不解指示詞。檔案原子寫入使用同目錄唯一 `.tmp` 再 replace，沒有 fsync。

```text
D/
  info.json
  requests/<epoch ns>-<pid>-<random 4 hex>.json
  requests/done/<同名>.json
  runners/<epoch ns>-<random 4 hex>/
    run.json
    ctl.json      # 控制者有需要才寫
  state.json
  daemon.pid
  daemon.log
  .daemon.lock
```

info.json 的身分固定為 `{"_metainfo":{"_type":"daemon","_version":1}}`，版本必須是整數 1，bool 不算。
daemon 啟動時沒有 info 就建，有就驗，不覆寫錯誤身分；ctl 與 kernel 認家先驗它。
daemon 建立缺少的家、requests／done；每次 add 另外建一個 runner 家，不重用舊家的控制檔與快照。
runner 退出後家保留供觀察。run.json／ctl.json 格式見 [run-home](run-home.md)。
ctl 不建立 daemon 家：缺 info／身分不合或缺 requests／done 為 NotAHome；版本不合為 UnsupportedVersion。
.daemon.lock 是持續存在的 flock 檔；daemon 執行期間持獨占鎖，防止同家兩支 daemon。
daemon.pid 只放十進位 PID 加換行，正常停機移除；log 接 runner 的 stdout／stderr。

## 請求與回音

只處理 requests 第一層的 `.json` 檔，只認三個 op：

| op | 欄位 | 成功 result |
|---|---|---|
| `add` | target 必填；args 缺省 []；kill_tree 是布林，缺省 false | 新增 entry |
| `remove` | target 必填 | runner 完全退出後的 entry，state=stopping |
| `stop` | 無 | 所有 runner 退出、state 清空、pidfile 移除後回 `{stopped:true}` |

target 必須是非空的絕對 `.json` 路徑，以 abspath 正規化並作為 runs 的 key；不解符號連結，
所以 kernel 的 cpus/N.json 換人後仍是同一支 runner。可登記尚未存在的 JSON，由 runner 重試。
args 是旗標與整數值配對的字串陣列，只接受 --interval-ms、--timeout-ms、--max-runs、--stop-exit。
前三種是非負整數，stop-exit 是 0～255，可重複。home 由 daemon 指定，kill_tree 另外一格傳入。
同 target 已登記（包含 stopping）回 AlreadyRunning；remove 不在表裡的 target 回 NotRunning。

```json
{"op":"add","target":"/abs/x.json","args":["--interval-ms","100"],"kill_tree":false}
```

成功回音是原請求物件加 `ok:true` 與 result，未知欄位原樣保留。
所有失敗回音都只有 `{"ok":false,"code":"代號","msg":"白話"}` 三格，包括壞 JSON 或非物件請求。
檔案請求不接受 ls；ctl ls 直接讀 state。

順序固定：執行 op → 先寫 done → 再刪原請求。done 寫失敗則原單留著；重掃看見已有 done
只刪原單，不重做 op。請求與 done 同名，done 保留、不自動清理。
這不是副作用與回音的交易：崩在建立 runner 後、發布 done 前仍可能留下孤兒或重複動作。

## state.json

```json
{"pid":1234,"runs":{"/abs/x.json":{"pid":2345,"target":"/abs/x.json","args":[],
 "state":"running","home":"/abs/D/runners/1790000000000000000-abcd"}}}
```

entry 只有五格：pid／target／args／state／home。state 只認 running／stopping，
表示 daemon 還管理它或已請它停止；這不是目前 inst 的 busy 狀態。
home 是 runner 家的絕對路徑；busy／target／runs／last_*／held 直接讀那裡的 run.json，
daemon 不重抄快照。剛 add 時 run.json 可能尚未建立。
runner 收屍後 entry 移除，家仍保留。正常停止後 state 是 `{"pid":0,"runs":{}}`，ctl ls 仍可讀。

daemon state 不是排程互斥鎖，實際判斷見 [aos-kernel](aos-kernel.md)。
daemon 不收養崩潰前存活的 runner，不承諾崩潰恢復或 exactly-once。
