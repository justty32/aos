← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 調度者裁決（第 2～3 輪，實作層級）

1. 送件前先把當批寫進 `state.batch`（`sent:false`），全送完才標 `sent:true`；崩了用 §5.2 的四步查「放過沒」，不盲目重送。
2. 收回時先讀驗、把結果寫進 `done`，才 ack；記憶一律寫成「前 `base_len` 則＋這批」，重做不會重複接。
3. `work/` 檔什麼時候刪，看 K 帳本的 `procs` 還有沒有那個名字（§10）；被 `rm` 還在跑的工作跑完前不刪。
4. 子命令化：`aos-agent tick|start|stop [dir]`；`tick.json` 由 `start` 寫，把 `AOS_K` 寫進它的 `envs`。（09-24 fix-r4 後是 `--target DIR` 與 `AOS_KERNEL_HOME`，見 §1、§11）
5. 工作名 `aw-<資料夾名>-<epoch ns>-<pid>-<i>`，think 也帶 `-0`；前綴 `aw-` 避開 `ack-`／`stop-`。
6. 壞模型輸出、`Removed`、`Interrupted`、逾時、非 0 都算一次連敗；`Stopping` 與 `stopped:true` 不算、下次重問。
7. 連敗暫停的訊號檔每次不同名：`continue-<批 id>.json`（第 3 輪；不用分新舊訊號）。
8. 工具 `kind=aos` 給模型固定一句話、指向 cpu.log，不把診斷塞進結果。
