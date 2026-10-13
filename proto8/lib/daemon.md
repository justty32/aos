# daemon（`aos_daemon.py`）

← [proto8/lib](README.md)｜上一份：[loop](loop.md)｜下一份：[ctl 與 state 的慣例](ctl-state.md)

管很多個 loop 的表；自己也是一個 loop（每一圈＝掃一次控制資料夾）。

三個檔：`aos_daemon.py`（命令列、daemon.json、主迴圈）、`aos_daemon_table.py`（表：`Table`、`DaemonError`）、`aos_daemon_folder.py`（指令 `handle()` 與控制資料夾）；名字都從 `aos_daemon` re-export。

```
python3 proto8/lib/aos_daemon.py DAEMON.json
```

- daemon.json 只在起來時讀一次：`control_dir`（必填）、`load`、`save`、`work_dir`（沒寫＝control_dir 旁的 `loops/`）、`grace_ms`（10000）；比照 loop：`times`（null）、`interval_ms`（200）、`interval_mode`（after；fixed＝固定週期、掃超過一拍就跳拍）、`ctl`（不能在 control_dir 裡）、`ctl_poll_ms`、`state`。
- 自己的 state.json：共同骨架加上 `skipped`、`loops`（表上幾個，只寫個數；要細節用控制指令 `list`／`get`／`state` 查）；`last_error`＝最近一圈印到 stderr 的最後一行錯（ScanFailed、ReplyFailed），那圈沒錯＝null。
- 自己的 ctl.json：paused＝不掃（指令堆著、loop 照跑）；stop＝收工（先 save；now＝底下 loop 當場收掉，沒 now＝替它們寫 stop、等它們跑完）；times 跑完同 stop（不帶 now）。
- 表上每個 loop 是一支子程序 `aos_loop.py`（自成 session）。daemon 只靠兩個檔控制它：寫它的 ctl.json、讀它的 state.json。loop.json 沒寫 ctl／state 的，在 `work_dir/<編號>/` 生包裝檔（每個 key `$ref` 回原檔、補上 ctl／state），移除或收工時刪掉。
- 控制資料夾（NORMS N-10）：放 `名字.json`，處理完變 `名字.json.done`，內容 `{"request", "ok", "result"|"error": {"code", "msg"}}`；`.` 開頭不讀；`.done` 由丟的人清。指令 `{"op", "id", ...}`，id＝loop.json 的絕對路徑，可接 `#/位置`（見[指示詞](directives.md)；save 存的、load 帶的 id 也一樣）（`add` 也收 inst.json：頂層沒有 `inst`、有 `argv` 的，包成只跑一次的 loop `{"inst": {"$ref": 它}, "times": 1}`，id 是那份 inst.json 的 realpath）：`add`、`set`（`how`：times／interval_ms／interval_mode）、`pause`／`remove`（`wait` 預設 true）、`resume`、`add_times`（`delta`）、`state`、`get`、`list`、`save`／`load`（`path`）。
- 次數跑完的 loop 自己退出，留在表上（state `done`），要再跑就 remove 再 add。set／pause／resume／add_times 等 loop 讀到了才回（state.json 的 ctl_mtime 趕上），pause 還要等真的停了，remove 等行程結束；等的期間指令檔留在原地。
- save 存 `[{"loop": realpath, "ctl": 當下 ctl.json}]`；runs 不存。load 全有全無（不在＝NotFound、重複或 state.json 的 pid 還活著＝Exists、格式不對＝FieldType），會把 ctl 內容寫回各 loop 的 ctl.json 再起。
- 收工：SIGTERM＝先 save、對每個 loop 的 session 送 SIGTERM、等 grace_ms、整群 SIGKILL；SIGINT 一樣但不存。巢狀 grace：inst（2000）＜ loop（5000）＜ daemon（10000）。
- 出意外不結束、stderr 印一次：ScanFailed、ReplyFailed、Internal。退出碼 0＝正常、1＝起不來或 save 失敗。
