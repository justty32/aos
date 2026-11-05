# proto8 討論紀錄：2026-11-05

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-11-05 早 無痛遷移的使用者旅程（portable-flow，fable 規劃）](portable-flow/README.md) | 使用者「我把一些基本的aos工具安裝好……複製一個agents資料夾(其中附帶一個daemon資料夾)……cd到ws……aos-exec把daemon叫起來……aos-daemon-ctl sleep bob……ctrl-c把daemon停掉……把daemon的stack、ws一起直接複製到另一個地方。實現無痛遷移」＋七段補充：**已定**——sleep／wake 開放成指令（翻 11-03）、PATH≈env.sh、搬家含跨電腦與 git pull、**存的路徑相對「管我的 daemon」**（不在 daemon 下不管、指外面自擔、子 daemon 就是 proc、不找最近的上層）、image 模型（daemon＝硬體、stack＝記憶體、ws＝外置記憶體、定義＝source、daemon 下的 stack＝實例）、stack 不存定義副本、總原則「①複製 ②沒有才起 daemon ③環境變數盡量少 ④aos-exec 開跑」；旅程八步六步今天能走，卡在整份搬走續跑（WSL `/tmp` 實測：表沒改會回舊位置醒來互踩、手改路徑能續、git 來回只掉空資料夾且自癒）；**要使用者看**：衝突 3（sleep／wake 與 start／stop 怎麼分、tools 副本 vs 不存副本、定義沒搬醒不來要不要留列）、方向題 5（基準點 stack／定義／ws、daemon stack 留不留 `ws/.stack`、`AOS_DAEMON` 誰設、第 3 步寫 aos-agent add 還是 aos-exec --daemon、`AOS_KERNEL` 由 daemon .env 帶）；步 0～7 給隊長；**沒改程式** |
