← [daemon](README.md)｜[spec 總導航](../README.md)

# 9. 我自己選的（等你確認）

沒翻案就照這樣實作。

1. **重拉只在非 0 退出、且沒被主動叫停**：退 0＝孩子自願停（kernel 的 stop、pipe EOF），daemon 不跟它作對；
   `kill`／`stop` 一定贏過重拉。
2. **重拉節流只有固定 `restart_delay_ms`**，沒有上限、沒有退避；一直死就看 `exits`。
3. **`go` 握手**：fork → 寫表 → `go`。多一行，換掉「沒人記得的孤兒」。
4. **孩子自己一個 process group、同一個 session**（舊版是 `setsid` 開新 session）：Ctrl-C 只打 daemon，
   階梯由 daemon 控制；daemon 死了孩子靠 EOF 停，不靠 SIGHUP。
5. **`.daemon.lock` 這把 flock 留著**，而且外人拿它探測 daemon 活不活：綁行程壽命的鎖不是我們要拿掉的那種鎖。
6. **啟動先等上一任的孩子死透**（`kill(pid,0)` 輪詢＋階梯，可能落到硬砍），孩子表從空開始、不收養。
7. **沒有 `aos-daemon-ctl`、沒有 `ls`**：放檔就是 ctl，偷看 state 就是 ls。
8. **`kill` 立刻回、非同步走階梯**；`dead` 的直接拿掉。
9. **階梯的 TERM 只給孩子本身、KILL 給整組**：TERM 要讓 cpu 自己做強制停（砍它的子程式、回 `stopped:true`）；
   KILL 是最後手段才掃整組。
10. **`spawn` 同步**：拉起來、登記、`go`、回音；失敗不登記；等價鍵是 `target`＋`dir_target`，`restart` 不同就更新。
11. **重拉每次重讀 target**，不用保存的副本。
12. **改綁 daemon 不支援交接**，先停舊的；**daemon 重啟後 kernel 要重 boot**。
