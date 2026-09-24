← [daemon](README.md)｜[spec 總導航](../README.md)

# 9. 我自己選的（等你確認）

沒翻案就照這樣實作。1～12 是第 1 版的（被池式取代的標了），13～22 是 2026-09-24 proto5-2 池式納入時選的，23 起是 2026-09-24 one-boot 時 P 隊選的；跟 kernel 兩邊之間的在 [kernel §10](../kernel/choices.md)。

1. ~~重拉只在非 0 退出、且沒被主動叫停~~ → 見 13。`kill`／`stop` 一定贏過重拉（照舊）。
2. ~~重拉節流只有固定 `restart_delay_ms`~~ → 見 14、15。
3. **`go` 握手**：fork → 寫 kids 檔 → `go`。多一行，換掉「沒人記得的孤兒」。
4. **孩子自己一個 process group、同一個 session**：Ctrl-C 只打 daemon，階梯由 daemon 控制；daemon 死了孩子靠 EOF 停，不靠 SIGHUP。
5. **`.daemon.lock` 這把 flock 留著**，而且外人拿它探測 daemon 活不活：綁行程壽命的鎖不是我們要拿掉的那種鎖。
6. **啟動先等上一任的孩子死透**（`kill(pid,0)` 輪詢＋階梯，可能落到硬砍）；~~孩子表從空開始、不收養~~ → 見 17。
7. ~~沒有 `aos-daemon-ctl`、沒有 `ls`~~ → 有 `ls`／`scale`／`kill`（§6.3）；仍沒有另一支 ctl 程式。
8. **`kill` 立刻回、非同步走階梯**；`dead`／`failed` 的清掉等待、馬上重拉。
9. **階梯的 TERM 只給孩子本身、KILL 給整組**：TERM 要讓 cpu 自己做強制停（砍它的子程式、回 `stopped:true`）；KILL 是最後手段才掃整組。
10. ~~`spawn` 同步~~ → 拿掉 `spawn`；`scale` 同步（寫完宣告才回），拉孩子是之後迴圈的事。
11. **重拉每次重讀 target**，不用保存的副本。
12. ~~改綁 daemon 不支援交接；daemon 重啟後 kernel 要重 boot~~ → kernel 改池的 `daemon` 就走搬池流程；daemon 重啟後照 `kernels/` 接著開 tick（one-boot；第 2 版是「鏈多半接得上」）。
13. **任何退出碼都重拉**（宣告還要它就拉）；要它停的唯一方法是移出宣告或 daemon 停機。
14. **退避**：1→2→4…→60 秒，活過 `stable_ms`（10 秒）歸零；`kill` 造成的死不加、不等。
15. **全 daemon 令牌桶** `spawn_per_sec`（預設 50），池之間輪流拿。
16. **每個孩子只留一條 pipe**（fd 0），fd 1 接 `/dev/null`，開檔數減半；fd 預算＝min(`max_children`, 開檔數 − 64)。
17. **`halt` 保留 `pool.json`**，重開自動照宣告拉回；所以 daemon 重開後通常不用 `aos-kernel boot`。
18. **`kill`＝砍掉重來**（宣告不變）；要真的少一顆用 `scale`。
19. **池的 owner**：別的 owner 用同一個池名＝`NameTaken`；`aos-daemon scale` 預設不准動有 owner 的池（`Owned`），`--force` 救急用。
20. **池縮到 0 且收完就拿掉**（刪摘要→宣告→資料夾），名字空出來；連 `decl` 一起忘掉，不做 tombstone（舊鏈晚到的單保證外）。
21. **孩子狀態一顆一檔**，閒著不寫；新號沒拉過不建檔；摘要一圈最多寫一次。
22. **CLI `scale`／`kill` 在 daemon 沒跑時不放單**（`NotRunning`）；`ls` 的 `restarting` 印成 `running` 的括號（子集）。
23. **tick 不走池、不走 cpu**：daemon 直接開 `aos-kernel tick` 當孩子（新 session），不寫 kids 檔、不走階梯；收屍時靠「不在孩子表裡」認出它。
24. **登記一個 kernel 一檔**（`kernels/<id>.json`，id＝K 路徑的 SHA-256 前 16 字元），只在登記、失敗、恢復時寫。
25. **「有新單」只看 `K/requests/` 的修改時間**，變了才列目錄比檔名；不讀內容。
26. **tick 退避沿用孩子的上限 `restart_max_ms`**，起點是 max(`every_ms`, 100)；**不自己放棄**。
27. **停機時正在跑的 tick 給 `stop_wait_ms`＋`kill_wait_ms`**，然後整組 KILL；登記檔留著。
28. **daemon 被 kill -9 留下的孤兒 tick 不殺**：靠 kernel 的 `K/.tick.lock` 與它自己的鬧鐘，新 daemon 開的格撞鎖退 75。
