# proto5-2（已納入 proto5，只剩歷史）

← [INDEX](../wf/INDEX.md)｜現行版本 [proto5](../proto5/README.md)

**2026-09-24 已納入 proto5**：程式在 [proto5/lib](../proto5/lib/README.md)、[proto5/cli](../proto5/cli/)，規範在 [proto5/spec](../proto5/spec/README.md)（kernel 的池表、daemon 的池都寫進那邊）。
要用、要學，一律看 [proto5 README](../proto5/README.md) 與它的[教程](../proto5/tutorials/README.md)。這裡的 `lib/`、`cli/` 已經拿掉，只留兩樣當歷史：

- [spec/](spec/README.md)：池式改版的規範草稿（一個主題一檔，只寫跟當時 proto5 不一樣的地方）。現行版以 proto5/spec 為準。
- [notes/](notes/README.md)：任務書、astra 審查、實作進度、真跑紀錄、71 條實作決定。筆記裡指到 `lib/`、`cli/` 的連結是當時的樣子，現在點不到。

## 這一版做了什麼（一句話版）

kernel 和 daemon 改成**以「池」為單位、宣告式**：kernel 只說「池 P 要 N 顆」，daemon 自己補到 N、死了自己拉（越等越久）、多了自己收；
加 cpu 就是 `aos-kernel cpu add --pool default --count 100`，下一格生效、不用 boot；`aos-daemon boot` 會照上次的宣告把池拉回來。

當時「要使用者拍的」九題（Q1～Q9）由隊長先代為拍板，細節與翻案要改哪裡見 [notes/2026-09-24-impl/decisions.md](notes/2026-09-24-impl/decisions.md) 開頭。
