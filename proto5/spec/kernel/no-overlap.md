← [kernel](README.md)｜[spec 總導航](../README.md)

# 7. 為什麼這樣就不會重疊

- 同一顆 cpu 一次只做一件（範式 §4.1），kernel 又「先記 `busy` 再放檔」、只派 `free` 裡（不在 `busy`）的號——
  所以一份行程同時最多在一顆 cpu 上，不用讀任何人的快照。
- kernel 不會有兩格同時跑（2026-09-24 one-boot 改；第 2 版靠「格都排在同一顆 kernel cpu 上」）：兩道關——
  (1) **daemon 同時只開一格**：同一個 kernel 家，上一格還沒退出就不開下一格（[daemon §10](../daemon/ticks.md)）；
  (2) **`K/.tick.lock`**：每格一開始非阻塞拿這把 flock，拿不到就退 75、什麼都不做。人手跑的 tick、daemon 被 kill -9 後留下的孤兒 tick、新 daemon 開的 tick，都靠這把鎖排開。
  行程死了（含 kill -9）鎖自己消失，不會卡住。boot 寫帳本時也拿這把（[§6 boot](boot.md)）；舊 kernel cpu 裡的舊格帶 `--chain` 就直接退 0。
- 擋不住的：兩個 boot 同時跑（人的規矩）；人用手直接 `aos-cpu`／`aos-exec` 跑同一份 inst（規則一之外）；
  cpu 被 KILL 而子程式還活著（範式 §5.3，保證外）。
- 一格跑太久：daemon 過了 `tick_timeout_ms` 就整組 KILL（算一次失敗）；tick 自己另設 2×`tick_timeout_ms` 的鬧鐘，只給 daemon 被殺後的孤兒用；鎖跟著行程消失，下一格照開。
