# 使用者定的與我自己選的

← [spec 導航](README.md)｜要使用者拍的在 [proto5-2 README](../README.md)

> 第 1 版，2026-09-24 草稿；未實作。

## 1. 使用者 2026-09-24 定的六點，落在哪

| 點 | 內容（白話） | 落在 |
|---|---|---|
| (a) | cpu 表改池表：池名、daemon 家、daemon 那邊的池名、要幾顆、envs；種類由池 envs 定 | [kernel-info](kernel-info.md) |
| (b) | 宣告式：kernel 只說「P 要 N 顆」，daemon 補、重拉（節流）、收；kernel 不記 pid、只看摘要 | [protocol](protocol.md)、[daemon-reconcile](daemon-reconcile.md)、[kernel-pools](kernel-pools.md) |
| (c) | daemon 內部按池管、可帶多池；指令全帶 `--pool`；孩子表不整份重寫；階梯批次 | [daemon-home](daemon-home.md)、[daemon-cli](daemon-cli.md)、[daemon-reconcile §6](daemon-reconcile.md) |
| (d) | `cpu add／rm／ls` 就是改池數字、看池摘要；`ls` 按池；下一格生效不用 boot | [kernel-cli](kernel-cli.md)。`cpu rm NAME` 的 NAME＝`P/<i>`、永久退休，以及既有池不收 `--env`，是我補的解讀（要使用者拍） |
| (e) | `init --config` 只剩 kernel 參數＋池定義，cpu 可空 | [kernel-cli](kernel-cli.md) `init`（工作池可空；kernel 那顆永遠在） |
| (f) | 每格 O(有事的 cpu)：回音丟通知檔、派工不掃每顆 | **部分做到**：逐顆查檔、逐顆找閒的都拿掉了；帳本仍整份讀寫，是 O(N)（[scale §2](scale.md)，要使用者拍）。[kernel-tick](kernel-tick.md)、[cpu-notify](cpu-notify.md) |

## 2. 我自己選的（沒翻案就照這樣；19～22 是審查後加的）

1. **成員用編號**（`count`＋`skip` → 最小的幾個非負整數），不讓 daemon 取名。kernel 不用問就知道有哪幾顆；任何集合都寫得成這兩格。
   替代：daemon 取名、用事件告訴 kernel 誰起來了——要多一條「事件」協定與它的崩潰窗口。
2. **cpu 的家由 kernel 建、放在 `K/pools/P/cpus/<i>/`**；daemon 只拿到一個含 `{name}` 的 target 樣板，仍然不認識 kernel、不懂 cpu 的家。
3. **每顆 inst 一模一樣、envs 用 `$ref` 指到池的 `envs.json`**：改環境寫一個檔；活著的不換，`kill --all` 才換。
4. **通知靠 cpu 的新 info 欄位 `notify`**，丟到 `K/requests/`、前綴 `resp-`；通知只是提示，另有巡檢（`sweep`）與 `recent` 兜底。
5. **帳本仍是一份 `state.json`**，只記忙的 cpu 與閒的號碼；`procs` 形狀不變以免動 aos-agent；一格最多寫四次（出貨合併寫）。
6. **縮小一律先做完再收**（drain）；沒有 `--now`。
7. **scale 回成功才把新號放進 `free`**；不等 cpu 真的活起來。
8. **daemon 對任何退出碼都重拉**（宣告還要它就拉），退避 1→2→4…→60 秒、活過 10 秒歸零；另有全 daemon 每秒 50 顆的上限。
9. **`kill`＝砍掉重來**（宣告不變）；要真的少一顆用 `scale`／`cpu rm`。
10. **拿掉 daemon 的 `spawn`**；單顆就是 `count: 1` 的池。
11. **kernel boot 交接 kernel 池用「縮到 0 → 等 → 寫帳本 → 拉 1」**，不用 kill（kill 會馬上重拉、跑舊鏈的格）。
12. **kernel halt 用「每池縮到 0」取代往每顆放 `stop-`**。
13. **daemon `halt` 保留 `pool.json`**，重開自動拉回；所以 daemon 重開後通常不用 `aos-kernel boot`。
14. **daemon 每個孩子只留一條 pipe**（fd 0），fd 1 接 `/dev/null`，開檔數減半。
15. **scale 出錯不自動重試**（`Stopping` 例外，每 10 格一次），記在 `pools.P.error` 給 `ls` 看。
16. **池的 owner 是 kernel 家的絕對路徑**；別的 owner 用同一個 daemon 池名＝`NameTaken`；池縮到 0 且收完就從 daemon 消失、名字空出來。
17. **`aos-daemon scale` 預設不准動有 owner 的池**，`--force` 救急用。
18. **工作池 cpu 的 `poll_ms` 預設 200**（kernel 池那顆 20）。
19. **scale 帶 `decl`（送件者序號）**，daemon 擋掉比現有舊的單（`Stale`）；boot 與 `Interrupted` 之後一律整份重送宣告（`redeclare`）。
20. **排隊格帶 `request`、懶刪**；`delayed` 用堆積；帳本加 `on` 反查。
21. **kernel halt 先等工作池縮到 0 都確認，才停 kernel 池**；halt CLI 看池消失或宣告 0，不只看 running 0。
22. **info 的寫入由 `K/.info.lock` 串起來**（CLI 之間）。

## 3. 沿用 proto5 不變的

判定規則（kernel.md §4）、syscall（§2）、鏈與殘格自滅、先放後記／先記後放、出貨箱的冪等、cpu 範式（除了 `notify`）、
daemon 的 `go` 握手、process group、階梯三段與時間、flock 探測、`once` 回音只有執行狀態、agent 那一整條線。
