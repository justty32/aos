# runner 家與控制格式

← [proto5 README](../README.md)｜程式：[aos-run](aos-run.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

```text
R/
  run.json
  ctl.json       # 控制者有需要才寫
```

兩份 JSON 都是字面值。run.json 由 runner 寫同目錄唯一 `.tmp`，再 rename；
讀者不會讀到半份 JSON，沒有 fsync，不承諾斷電持久化。一個家只供一支 runner 使用。

## run.json

```json
{"pid":1234,"busy":false,"target":"/abs/procs/a.json","runs":3,
 "last_target":"/abs/procs/a.json","last_exit":0,"last_kind":"child","last_ms":42,"held":false}
```

run.json 固定九格：pid 是 runner 的 PID；busy 是不是正在嘗試跑一次；target 是本次選定的
絕對目標路徑；runs 是已完成次數；last_target／last_exit／last_kind／last_ms 是上次完成的
目標、對外碼、種類與耗時毫秒；held 是不是被 hold 擋住。啟動時 busy=false、target=null、
runs=0、四個 last_* 都 null、held=false。

last_kind 之後是 child／aos／usage；last_ms 是非負整數。busy=false 時 target 保留剛完成目標；
開始下一次時 target 先清成 null，last_* 仍保留上次完成結果。因此即使 busy=true，
也能用 last_target 對應 last_exit。選定目標失敗時，該次 last_target 可以是 null。
停止後保留最後快照；檔裡有 pid 不代表 runner 還活著。

## ctl.json

```json
{"op":"hold"}
```

只認 `stop` 與 `hold`：stop 請 runner 不再開下一次；hold 暫停開跑，held=true。
檔案不見或 op 不再是 hold 就解除 hold。壞 JSON、非物件、未知 op 或讀不到，當沒有控制命令。
runner 不刪 ctl.json；誰寫誰刪。控制者也應原子替換，避免半份檔案被當作沒有。
