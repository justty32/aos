# daemon（`aos_daemon.py`）

← [proto8/lib](README.md)｜上一份：[loop](loop.md)｜下一份：[ctl 與 state 的慣例](ctl-state.md)

daemon＝一個 loop（同一個拍引擎 `aos_loop.Loop`），每拍多做「收屍、掃控制資料夾、套策略格」，同時顧著一群長壽的子 loop。照 NORMS N-12 重做、候選 g 拍板（10-14）：**daemon.json＝loop.json 的嚴格超集**，一份合法的 loop.json 丟給 aos-daemon 也能跑（見 [NORMS N-28](../NORMS/05-命令列與daemon-N21至N28.md)）。

三個檔：`aos_daemon.py`（命令列、daemon.json、`Daemon` 類別）、`aos_daemon_table.py`（表：`Table`、子項六態、table 窗、策略格、`DaemonError`）、`aos_daemon_folder.py`（指令 `handle()` 與控制資料夾）。

```
python3 proto8/lib/aos_daemon.py [--key 值 ...] [DAEMON.json | -]
```

- 設定從哪來同 loop（`aos_cli`）：DAEMON.json、`-`＝stdin、外層純量 key 有同名旗標；`--` 不收。
- **跟 loop 同名的 key 同義**：`inst`（daemon 自己每拍跑一次的身體，**選填**；跑法同 loop，阻塞到它結束）、`ctl`、`state`（**必填**，N-19；ctl 不能在 control_dir 裡）、`times`（預設 null＝不限，跟 loop 的 1 不同）、`interval_ms`（200）、`interval_mode`、`ctl_poll_ms`、`error_wait_ms`、`grace_ms`（10000）、`id`。
- **daemon 多的**：`children`（初始表，每項＝一個 loop 設定的 TARGET：路徑、`檔#/位置` 或內嵌物件；起來時等同逐個 add）、`policies`（`{"child_exit": inst TARGET}`）、`control_dir`（**選填**，沒給＝不掃資料夾）、`table`（table 窗，選填）、`load`（true＝起來時讀 table 窗接回）、`work_dir`（沒寫＝state 窗旁的 `loops/`）。
- **每拍**：掃控制資料夾 → 跑 `inst`（有的話）；收屍、退避到點的重起每一圈都做。`runs`＝拍數。stdout 同 loop：每拍一份 `{run, code, ms}`、結束一份總結。
- 自己的 ctl 窗：paused＝不拍（指令堆著、子項照跑）；stop＝收工（now＝子項當場收掉；沒 now＝替它們寫 stop、等它們跑完）；times 跑完同 stop（不帶 now）。state 窗：共同骨架加 `skipped`、`last_code`、`loops`（表上幾個）；`last_error`＝inst 出錯那行，沒有就是最近一圈掃資料夾的錯（ScanFailed、ReplyFailed）。
- **子項**：一支子程序 `aos_loop.py -`（自成 session），設定從 stdin 灌（`id`＝原 TARGET 的 id）。每個子項一格 `work_dir/N/`：沒寫 ctl／state 的放這裡，子 loop 的 stdout／stderr 落 `ret.json`、`err.json`（`times: null` 時會一直長，見 NORMS 待定）。daemon 只靠兩個窗控制它：寫它的 ctl（帶流水號 `seq`）、讀它的 state（`ctl_seq` 趕上＝讀到了）。
- **子項六態** `phase`：starting／running／exited／backoff／stopping／removed，寫在 **table 窗** `{"kind": "aos-daemon-table", "children": [{id, target, times, work_dir, ctl, state, pid, started, phase, exits, last_code}]}`；先寫表、再 Popen。table 窗就是存檔（暫定 d）。
- **策略格** `policies.child_exit`：子項結束（不是 remove、不是收工）時跑那格 inst，stdin＝`{id, code, exits, last_state}`，stdout 最後一份＝`{action: restart|leave|remove, after_ms}`；restart＝退避 after_ms 再起（phase backoff）。沒設、格出錯＝leave；`exits ≥ 5` 強制 leave。
- **接回**（`load: true`）：讀 table 窗；pid＋啟動時間（/proc）對得上的認領、不重起；對不上的下一圈當 exited 走策略格；backoff 的馬上重起。收工時表與 `work_dir/N` 留著；`remove` 才刪那格。
- **控制資料夾**（N-10）：放 `名字.json`，處理完變 `名字.json.done`，內容 `{"request", "ok", "result"|"error": {"code", "msg"}}`；`.` 開頭不讀；`.done` 由丟的人清。指令 `{"op", "id", ...}`，id＝loop.json（或 inst.json，包成只跑一次的 loop）的絕對路徑，可接 `#/位置`：`add`、`set`（`how`）、`pause`／`remove`（`wait` 預設 true）、`resume`、`add_times`（`delta`）、`state`、`get`（state 窗＋`phase`）、`list`。舊的 `save`／`load` 指令拿掉（併進 table 窗）。
- set／pause／resume／add_times 等子 loop 讀到了才回，pause 還要等真的停了，remove 等行程結束；等的期間指令檔留在原地。
- 收工：SIGTERM／SIGINT＝子項整群 SIGTERM、等 grace_ms、整群 SIGKILL。巢狀 grace：inst（2000）＜ loop（5000）＜ daemon（10000）。
- 出意外不結束、stderr 吐一份警告（同一件事一次）：ScanFailed、ReplyFailed、PolicyFailed、RestartFailed、TableWriteFailed。退出碼 0＝正常收工（含收到訊號）、1＝起不來；最後一拍 inst 自己出錯＝沿用它的碼。
