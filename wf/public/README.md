# wf/public — 公用知識庫

← [wf/README](../README.md)

所有 agent（頂層、各 ok-* eca、它們掛的 sol／astra 等 fsm）都能讀，也都能投稿的公用區。由頂層 repo-aos 管理（使用者 11-14「大家如果自己有弄出好工具，也可以分享出來。你這邊也稍微掌管一下wf/public公用知識庫，wf/public/tools之類」）。

| 夾 | 放什麼 |
|---|---|
| [tools/](tools/README.md) | 別的 agent 也用得上的小工具：一個工具一個夾 |
| [recipes.md](recipes.md) | 要做某件事時該用哪支、照哪一節：任務類型→做法的表，各線摸出來的；寫任務書時從這裡抄 |

## 投稿規矩
- 一個工具一個夾 `wf/public/tools/<名>/`，裡面要有 `README.md`（英文，一屏內：做什麼、怎麼用、怎麼裝／拿掉、已知限制、作者與日期）和程式本體；程式輸出一律英文。
- 在 [tools/README.md](tools/README.md) 的表加一列（只追加）。
- 不放秘密、不放只對自己有用的東西、不放會改活樹 lib／py／knowledge 的安裝步驟（要的話寫清楚、交頂層）。
- 投稿照一般 commit 規矩（排隊機制上線後走排隊）；fsm 不 commit，交給掛它的 eca。投稿後寄一封給 xiaosi，title 開頭「[public]」。
- 頂層會不定期整理：重複的合併、壞掉的標註、好用的寫進 wf 規矩或建議進 `proto8/`。
