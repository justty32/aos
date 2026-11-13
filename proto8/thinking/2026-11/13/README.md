# proto8 討論紀錄：2026-11-13

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [aos-home](aos-home.md) | 公司 WSL 改住 `~/aos-home`、repo 用 `~/repo/aos`（重 build、install 連結全換、全套 66 夾 1354 例只紅既有 4 支）；`~/aos-home` 從零重搭一隻 opus `eca_main`（26 支、讀得到 knowledge、存讀檔都過）；遊樂場、舊 aos-home、`~/repo/aos-tools`、`~/repo/simple_tools/aos` 照使用者刪掉，`~/repo/simple_tools` 有 8 個沒推的 commit 沒刪；桌面手冊 [aos-home-手冊.html](aos-home-手冊.html) |
| [main-session-in-aos](main-session-in-aos.md) | 主 session 接 aos 四題：公司 WSL 的主 session 已經是樹裡的一隻 eca proc `repo-aos`，四題照現況與原則定案（只規劃、沒施工）；留的兩題 11-13 已裁：`eca_main` 派的普通工作算數、不可逆的仍要使用者本人說，家機也改成樹裡的一隻 |
| [eca-a2a-notify](eca-a2a-notify.md)（分檔夾 [eca-a2a-notify/](eca-a2a-notify/01-盤點.md)：01 盤點、[02 a2a 機制與實測](eca-a2a-notify/02-a2a機制與實測.md)） | eca 的通知改走 a2a（只調查沒施工）：外部行程可以直接投 Claude Code 的 session socket、寄件人可寫「aos通知中心」（實測）；兩題 11-13 已裁：照建議全部改走 a2a、`say` 補寄件人，忙的時候也馬上送（各題對法是頂層的讀法） |
| [external-mcp-real-server](external-mcp-real-server.md) | 外部 MCP 接真的別人寫的 stdio server（官方 everything／time／filesystem 三台）：eca 兩身與 agent-fsm 都叫得到，codex 的 `disabled_tools` 有效；codex 沙盒管不到 stdio server、CLI 自己接的 server 壞了 aos 看不到（P3 仍在） |
| [eca-main-six-fixes](eca-main-six-fixes.md) | `eca_main` 來信七項的評估：四項是 bug（修法與 patch 草稿備好）、兩項是新功能、一項與 `AOS_HOME` 的意思是設計題；Q1～Q4 要使用者裁 |
| [line-b-cleanup](line-b-cleanup.md) | 線乙四批整理的結果（舊路徑、agent-fsm 重複收一支、說明清舊、do_task 摺疊被砍重複）；代定 4 條、未決 6 題要使用者裁 |
| [kernel-framework-開工](kernel-framework-開工.md) | 通用 kernel 框架開工計畫：圖紙十四步拆 17 批、領地、對跑著的樹的影響；使用者「kernel框架現在就可以開工了。只是說我們現在只有eca能用。」；新題兩題未裁（問腦那包現在開不開工、什麼時候能停樹） |
| [aos-wu-1113-待你裁.html](aos-wu-1113-待你裁.html)、資料檔 [decide_20261113_wu.json](decide_20261113_wu.json) | 把 wait-user「要你裁的」每條拆成小題的大頁，128 題；已答 19 題（精選 17 題＋主 session 兩題），其餘未答 |
| [aos-wu-1113-top-待你裁.html](aos-wu-1113-top-待你裁.html)、資料檔 [decide_20261113_wu-top.json](decide_20261113_wu-top.json)、回覆 [decide_20261113_wu-top.reply.txt](decide_20261113_wu-top.reply.txt) | 從 128 題挑出先看的 17 題（題號跟大檔相同）；使用者 11-13 已回，回覆檔是原文一行 |
| [裁定落地-1113](裁定落地-1113.md) | 11-13 裁定落地：精選 17 題（16 題有選、N-17 先不選但留一句原則）＋對話裡答的主 session、a2a、kernel 開工；每題裁定已寫回原文件，「裁定後待施工」清單都還沒動手；K-F50 的備註追問後結案（框架站 `next` 留著、問腦總機看 `AOS_KERNEL`）；C-81、C-42、a2a 第 2 題的備註讀法不只一種，照列沒選邊 |
