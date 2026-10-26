← [thinking](README.md)｜月份索引：[2026-10](months/2026-10.md)｜規範：[NORMS N-28](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-17、N-09](../docs/NORMS/05-基礎設施-窗.md)｜實作：[impls/aos-daemon](../impls/aos-daemon/README.md)、[impls/aos-loop](../impls/aos-loop/README.md)

# 2026-10-23 daemon 壓測後的六個問題

## 使用者原文（整理版）

10-23 晚對 C++ 版 aos-daemon 做壓測（10 個到 1 萬個子 loop、子 loop 間隔 1 秒與 10 秒），另測一個不肯退的子 loop，測出六個問題。使用者：

> 都修都處理

修到一半使用者說：

> python版本可以刪掉了。aos-exec/loop/daemon都用C++

所以只改 C++ 版（`proto8/impls`）；`proto8/bin` 的 Python 版 aos-exec、aos-loop、aos-daemon 不再跟著改、要刪。

## 決定與結論（頂層照原則推，沒有方向題）

1. **收子項不阻塞**：表上多出來的子 loop 送 SIGTERM 就往下巡（state 照寫、ctl 照讀、別的子項照起），每次巡的時候看一眼，退了就標 `stopped`、從表上拿掉；滿 10 秒還在才 SIGKILL 整群。收的途中那一列寫 **`stopping`**（N-17 六態之一；「正在收」，C-54 R2）。daemon 自己收工時（不論為什麼）一樣先全部送 SIGTERM，等它們退的這段每秒寫一份 state，頂層 `phase` 是 `stopping`（也在 N-17 的七態裡）。收的途中 ctl 又把同名的放回來：等舊的退了，下一次才起新的（同一個小格）。
2. **子 loop 被 SIGKILL 時自己的 state 停在 `running`**：daemon 不去改它（N-09「一個 state 檔只有被控制的那個東西自己寫」）。讀子 loop 的 state 時，死活照 N-17 看 pid＋`started_at_ticks`（行程不在、或 pid 被別人重用而 `started_at_ticks` 對不上＝死了，`phase` 不算數）；daemon 自己的 state 那一列是準的——daemon 收掉的寫 `stopped`，被 SIGKILL 的 `signal` 9、`code` 137。
3. **一圈的成本**：表是「照加入順序的串列＋名字→那一列的雜湊表」；每圈把期望表的名字收成雜湊集合（`ordered_json` 的查找是逐個比，不用它查）；組 state 的 `loops` 直接接在尾巴（不逐個比 key）。沒有 `run` 的 daemon 一圈只讀一次 ctl、只 tend 一次、只組一次、只寫一次 state。
4. **`at` 間隔穩定**：沒有 `run` 時不寫 `running`（那一刻沒東西在跑），一圈一份 `waiting`，間隔＝`interval_ms`＋這一圈 tend 的時間。有 `run` 的 loop／daemon 每次跑之前寫 `running`、跑完寫 `waiting`（N-17「每次跑之前寫一次」）。
5. **起子項之前先寫一份 state**：用心跳的規則（N-32「最多隔 1 秒」）——起子項之前，離上一份滿 1 秒（或還沒寫過）就先寫一份；一大批起很久時每秒一份。不另開「每批幾個」的 key。
6. **aos-loop 不自己建 `$AOS_STACK`**：建 stack 只在 aos-exec 做（N-59 第 1 件「建 stack……只在這裡做」）；直接跑 aos-loop、`$AOS_STACK` 不在＝state 寫不了＝`WriteFailed` 一行、退 1（N-28 開頭 ③：資料夾不見時當掉是使用者自己承擔）。daemon 一樣：小格只建一層（不用 `mkdir -p`，不會順手建出 `$AOS_STACK`），`$AOS_STACK` 不在＝開了 state 窗就 `WriteFailed`、沒開就 `MkdirFailed`，都退 1。
