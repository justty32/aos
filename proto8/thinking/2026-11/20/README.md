# proto8 討論紀錄：2026-11-20

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [T7 第 9 步回公司（14-真機驗證）](../10/two-machines/14-真機驗證.md#第-9-步回公司那一步-11-20-實跑) | two-machines T7 第 9 步回公司那一步公司機代跑、全過：pull 到 rv day 2、兩台起來不用換台指令、ann 答 back at office、error: 0 行、git status 只有 stack 狀態檔；T7 全部跑完（第 5 步 codex 先前已跳過），~/code/rv 沒 commit、沒 push |
| [初始 kernel＝llm＋權限沙箱（aos-init-kernel-1120）](aos-init-kernel-1120/README.md) | 調查＋發想：今天灌 kernel 實際只灌 llm kernel；權限那側沒有隨灌 kernel 裝上的東西（站與 kernel_gate 預設不裝，limits／sub:N 在 daemon 本體，guard／sandbox 在 agent 與工具）；四種切法與八題待裁，等使用者 |
| [編譯的通用底座與函數當工具／hook（aos-compile-base-1120）](aos-compile-base-1120/README.md) | 只查只寫：能編譯的只有 agent 與工具、兩支共用 0 行；底座攤五個形狀（甲～戊）；函數當工具／hook 分「抽出來」與「回頭跑」兩大類，小原型兩種都走通；八題待裁，等使用者 |
| [aos-gdb 問答（aos-gdb-問答-1120）](aos-gdb-問答-1120.md) | 使用者問 a.stop() 是不是阻塞、斷點 id 為什麼是 xxxx_1；只讀快查：把手沒有 a.stop，暫停是 a.bp.pause()、停掉是 a.ctl.stop()，正在跑的一格不被打斷、扣在斷點上停不了，id 是施工線順手定的「種類_N」且刪了會重用；選項框四題已答（pause 加 wait=、不等回可查的物件 is_done()、id 純數字搭配屬性待確認、add 回物件），還沒施工 |
