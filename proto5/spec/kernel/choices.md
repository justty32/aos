← [kernel](README.md)｜[spec 總導航](../README.md)

# 10. 我自己選的（等你確認）

沒翻案就照這樣實作。

1. **kernel 跟 daemon 也走資料夾**，不走 pipe——pipe 在 cpu 手上，tick 是孫子。「只有 kernel 能叫 daemon」
   因此是軟性的，換來全系統兩條路一個信封。
2. **tick 用 aos-exec 的普通檔模式**（`target`＝帳本釘的 `cli`、`args` 帶 chain 與 seq），沒有 tick.json：
   chain 釘在 request 裡、不可變，殘格才真的會自滅。
3. **帳本＋四張出貨箱**：行程紀錄收進 state、`procs/` 資料夾拿掉；ack／回音／stop／刪原單先記再放；去重憑據是 `deletes`。
4. **boot 的交接是「叫 daemon `kill` 舊 kernel cpu、等它從孩子表消失」**，不是偷看 `current`；daemon 活不活用 flock 探測。
   代價：boot 最慢等一格做完＋階梯。兩個 boot 同時跑不保證。
5. **`kcpu`／`cli` 釘在帳本**：改 info 的 kernel 池不生效，要重 boot。
6. **`once` 的 add 回音延到跑完才回、內容就是執行結果**；stopping 期間還在排隊的 once 回 `Stopping`；rm 當下回 `Removed`。
7. **quantum／waiting／aos_ticks／last_target 全拿掉**，換 `interval_ms`＋`not_before`＋一次派工一則回音。
8. **cpu 分池用 `pool` 字串**；kernel 自己的池叫 `kernel`，恰好一顆。`info.cpus.<c>.envs` 抄進那顆的 inst。
9. **死掉的 cpu 只等 daemon 重拉**，它手上的單靠範式的開機對帳回 `Interrupted`。
10. **kernel 不讀 target 指的檔**，連在不在都不看；一切都是跑起來的回音。
11. **`ls` 不是 syscall**，直接偷看三個地方。
