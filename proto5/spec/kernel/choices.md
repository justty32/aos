← [kernel](README.md)｜[spec 總導航](../README.md)

# 10. 我自己選的（等你確認）

沒翻案就照這樣實作。1～11 是第 1 版的（被池式取代的標了），12～30 是 2026-09-24 proto5-2 池式納入時選的（kernel 與兩邊之間的部分；daemon 自己的在 [daemon §9](../daemon/choices.md)），31 起是 2026-09-24 one-boot 時 P 隊選的（使用者拍板的三條在 [§9](README.md)；被 one-boot 取代的標了）。

1. **kernel 跟 daemon 也走資料夾**，不走 pipe——pipe 在 cpu 手上，tick 是孫子。「只有 kernel 能叫 daemon」
   因此是軟性的，換來全系統兩條路一個信封。
2. ~~**tick 用 aos-exec 的普通檔模式**（`target`＝帳本釘的 `cli`、`args` 帶 chain 與 seq），沒有 tick.json：
   chain 釘在 request 裡、不可變，殘格才真的會自滅。~~ → one-boot：tick 由 daemon 直接開，見 31。
3. **帳本＋出貨箱**：行程紀錄收進 state、`procs/` 資料夾拿掉；ack／回音／刪原單／放別人家的單先記再做；去重憑據是 `deletes`。（池式：`stops` 換成 `sends`）
4. ~~boot 交接是「叫 daemon `kill` 舊 kernel cpu、等它從孩子表消失」~~ → 見 22。
5. **`cli` 釘在帳本**、~~kernel 池的設定~~開 tick 的設定（daemon、`tick_ms`、`tick_timeout_ms`）要重 boot 才換（one-boot 改）。
6. **`once` 的 add 回音延到跑完才回、內容就是執行結果**；stopping 期間還在排隊的 once 回 `Stopping`；rm 當下回 `Removed`。
7. **quantum／waiting／aos_ticks／last_target 全拿掉**，換 `interval_ms`＋`not_before`＋一次派工一則回音。
8. **cpu 分池用 `pool` 字串**；~~kernel 自己的池叫 `kernel`，恰好一顆~~（one-boot：沒有 kernel 池，`kernel` 只剩保留名）。（池式：環境改由池的 `envs.json` 給，見 14）
9. **死掉的 cpu 只等 daemon 重拉**，它手上的單靠範式的開機對帳回 `Interrupted`。
10. **kernel 不讀 target 指的檔**，連在不在都不看；一切都是跑起來的回音。
11. **`ls` 不是 syscall**，直接偷看。
12. **成員用編號**（`count`＋`skip` → 最小的幾個非負整數），不讓 daemon 取名。kernel 不用問就知道有哪幾顆；任何集合都寫得成這兩格。
    替代：daemon 取名、用事件告訴 kernel 誰起來了——要多一條「事件」協定與它的崩潰窗口。
13. **cpu 的家由 kernel 建、放在 `K/pools/P/cpus/<i>/`**；daemon 只拿到一個含 `{name}` 的 target 樣板，不懂 cpu 的家（one-boot 起 daemon 多認得 kernel 家在哪、多久開一格，但不讀裡面的檔）。
14. **每顆 inst 一模一樣、envs 用 `$ref` 指到池的 `envs.json`**：改環境寫一個檔；活著的不換，`aos-daemon kill --all` 才換。
15. **通知靠 cpu 的新 info 欄位 `notify`**，丟到 `K/requests/`、前綴 `resp-`；通知只是提示，另有巡檢（`sweep`）與 `recent` 兜底。
16. ~~**帳本仍是一份 `state.json`**~~（one-boot 換 sqlite，見 35），只記忙的 cpu 與閒的號碼；`procs` 形狀不變以免動 aos-agent；~~一格最多寫四次~~一格最多存三次（出貨合併寫）。
17. **縮小一律先做完再收**（drain）；沒有 `--now`。
18. **scale 回成功才把新號放進 `free`**；不等 cpu 真的活起來。
19. **`kill`＝砍掉重來**（宣告不變）；要真的少一顆用 `cpu rm`。
20. **拿掉 daemon 的 `spawn`**；單顆就是 `count: 1` 的池。
21. **scale 出錯不自動重試**（`Stopping` 例外，每 10 格一次），記在 `pools.P.error` 給 `ls` 看。
22. ~~**boot 交接 kernel 池用「縮到 0 → 等（running、killing、draining 都 0，或池消失）→ 重讀帳本 → 寫新鏈 → 拉 1」**，不用 kill（kill 會馬上重拉、跑舊鏈的格）。~~ → one-boot 沒有交接；「縮到 0 → 等」只剩舊帳本升級時收舊 kernel cpu 用（[§6 boot](boot.md) 第 3 步）。
23. **halt 用「每池縮到 0」取代往每顆放 `stop-`**；先等工作池縮到 0 都確認，~~才停 kernel 池~~才撤 tick 登記（one-boot）；CLI 看池消失或宣告 0，不只看 running 0。
24. **池的 owner 是 kernel 家的絕對路徑**；別的 owner 用同一個 daemon 池名＝`NameTaken`；池縮到 0 且收完就從 daemon 消失、名字空出來。
25. **工作池 cpu 的 `poll_ms` 預設 200**（~~kernel 池那顆 20~~，one-boot 沒有了）。
26. **scale 帶 `decl`（送件者序號）**，daemon 擋掉比現有舊的單（`Stale`）；boot 與 `Interrupted` 之後一律整份重送宣告（`redeclare`）。
27. **排隊格帶 `request`、懶刪**；`delayed` 用堆積；帳本加 `on` 反查。
28. **info 的寫入由 `K/.info.lock` 串起來**（CLI 之間）。
29. **退休號只增不減**（`skip` 寫入時不丟任何一號；09-24 裁定）。
30. **池刪掉後舊鏈晚到的 scale 單把池建回來，列保證外**，不做 tombstone（09-24 裁定，[§5](daemon-link.md)）。
31. **daemon 直接開 `aos-kernel tick --target K`**（當孩子、新 session、stdout 接 /dev/null、stderr 跟 daemon），不經 cpu、不經 aos-exec。
32. **「有新單就開」只看 `K/requests/` 的修改時間**，變了才列一次目錄比檔名；daemon 不讀 kernel 家任何檔的內容。`wake`、cpu 的回音通知都是往這裡丟檔，所以都會馬上觸發。
33. **鎖被佔退 75**，daemon 不算失敗、`tick_ms` 後再開；其他退出碼（含逾時被 KILL）算失敗、退避、**不自己停**。
34. **`tick_timeout_ms` 預設 60 秒**，daemon 砍、tick 自己也設鬧鐘（孤兒 tick 也會死）。
35. **帳本 sqlite：tick 仍整份讀、只寫變了的列、一筆交易**；`on` 不存、讀時從 `busy` 反推；別人讀帳本走同一支 lib 或 `aos-kernel proc`／`ls --json`。
36. **舊 `state.json` 由 boot 匯入後改名 `state.json.v2-old`**，不刪；舊 kernel 池先縮到 0、收乾淨才寫新帳本。
37. **撤登記由停好那格自己排進 `sends`**（跟停機判定同一次提交），不由 CLI 送；所以 `aos-kernel halt` 不用知道 daemon 在哪。
38. **`ls --json` 升第 3 版**（`kernel.cpu` → `kernel.tick`），不在第 2 版裡偷偷改。
