← [kernel](README.md)｜[spec 總導航](../README.md)

# 7. 為什麼這樣就不會重疊

- 同一顆 cpu 一次只做一件（範式 §4.1），kernel 又「先記 `req` 再放檔」、只在 `req` 為 null 時派——
  所以一份行程同時最多在一顆 cpu 上，不用讀任何人的快照。
- kernel 不會有兩格同時跑：格都排在帳本釘死的那顆 kernel cpu 上，那顆一次只做一件；boot 不跑格、先把舊 kernel cpu
  收掉等它從孩子表消失才開新鏈；舊鏈殘格靠 `chain` 自滅。
- 擋不住的：兩個 boot 同時跑（人的規矩）；人用手直接 `aos-cpu`／`aos-exec` 跑同一份 inst（規則一之外）；
  cpu 被 KILL 而子程式還活著（範式 §5.3，保證外）。
