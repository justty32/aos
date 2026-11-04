← [入口](README.md)｜涵蓋：A. 兩塊比較：aos agent vs 外部 coding agent、各題結論（每條標照哪條原則／決定）｜上一份 [01-前提](01-前提.md)｜下一份 [03-各題結論](03-各題結論.md)

## A. 兩塊比較：aos agent vs 外部 coding agent

把「射後有理」拆成七件事，兩邊的共同點與通用介面怎麼對上（外部 agent 拿 claude code 當代表）：

- **跑起來**：都是一個資料夾程式跑在一個工作區；外部 agent 要能 `aos-exec`，就用一個**定義資料夾**包著它（B）。
- **輸入**：兩邊都是一則一則、有先後的訊息。aos agent 自己去 `$AOS_STACK/queue/` 拿；外部 agent 不會看資料夾，由 adapter（`turn` 格）替它拿。aos-say 一律寄進 `<stack>/queue/`。
- **回答**：aos 這邊一律看 `history.jsonl`；外部 agent 的問與答由 adapter 抄進 history，它自己的 session 檔用 symlink 掛在小格（決定 35）。aos-listen 不用改。
- **一輪的邊界**：外部 agent 的一輪＝「一句進去、到它不再叫工具、吐出最後一句」（使用者 10-27 筆記）。aos agent 的一輪拆得開（格），外部 agent 的一輪是一整塊（決定 12），所以暫停粒度不同。
- **停著等**：兩邊都交給 aos-loop（外部 agent 的 adapter 一次替它答一則），不自己寫循環。
- **暫停／停**：`paused` 對外部 agent＝不餵下一則（新信留 `queue/new/`、手上那則答完）；`stopped`＝這則答完 loop 收工；畫面另外用 hub 管。粒度只到一則訊息，停不進它的工具呼叫中間——黑盒子的天然差異，不補。
- **生命週期**：兩邊同一套（aos-exec、aos-daemon、aos-daemon-ctl）；外部 agent 多的只有**畫面**和**它自己的 session 檔**，這兩樣就是 aos-eca-hub 要做的全部（C）。

**一句話結論**：兩塊的共同點是「有序的訊息進、只附加的紀錄出、一輪一輪、輪與輪之間才停得下來」——就是 P-42 的三樣（queue、history、ctl／state）。差別只有一個：外部 agent 不會自己去 queue 拿、自己寫 history，**要一個 adapter 替它做，這個 adapter 跑在 aos-loop 底下就跟一隻 aos agent 一模一樣**。所以 aos-say／listen 照 P-42 一行不改；外部 agent 的 queue 由 adapter 收、history 由 adapter 寫、`paused` 由包著 adapter 的 aos-loop 認。

## 各題結論（每條標照哪條原則／決定）
