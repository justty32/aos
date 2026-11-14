# wf/public — 公用知識庫

← [wf/README](../README.md)

所有 agent（頂層、各 ok-* eca、它們掛的 sol／astra 等 fsm）都能讀，也都能投稿的公用區。由頂層 repo-aos 管理（使用者 11-14「大家如果自己有弄出好工具，也可以分享出來。你這邊也稍微掌管一下wf/public公用知識庫，wf/public/tools之類」）。

內容索引見下方「索引」。

## 投稿怎麼走（11-14 起：隊伍交稿 → 頂層派 Claude 子 agent 審與整理 → 入庫建索引）

使用者 11-14：「我們開了這麼多隊伍，我們會需要一個共用的知識庫…建議各隊伍都把他們覺得可以放入的東西交給你，你派claude subagent去審核和整理，放入並建index吧。」

1. **隊伍交稿**：把稿放在自己工作區 `wf/temp/<線名>/public-submit/<題目>.md`（工具就放整夾）。稿頭三行：適用情境、驗過沒（誰、哪天、怎麼驗的）、出處（紀錄檔或 commit）。**不用自己 commit、不用自己改 wf/public**。
2. **通知**：寄 xiaosi，title 開頭 `[public-submit]`，what 列稿的路徑。xiaosi 收齊轉頂層。
3. **審與整理**：頂層成批派 Claude 子 agent 審：有沒有秘密／私人資訊、是不是別隊也用得上、跟現有的重不重複、驗過沒、跟 wf 規矩衝不衝突。過的改寫成庫裡的格式放進來，重複的合併，退的寫原因回給投稿隊伍。
4. **入庫**：頂層走 commit-request commit，並更新下面的索引。

## 索引

| 夾／檔 | 放什麼 |
|---|---|
| [tools/](tools/README.md) | 小工具，一個工具一個夾：quiet（安靜時段）、waitdone（背景等 fsm 隊員答完） |
| [recipes.md](recipes.md) | 任務類型→做法（一行一列） |
| [pitfalls.md](pitfalls.md) | 踩坑與解法：建置（`_main` 目標）、隊長的 shell、試真東西別碰原件 |
| [patch-and-commit.md](patch-and-commit.md) | 暫存樹改動搬回已往前走的 main、驗收跑全套（含環境沒清的假綠）、commit-request 的坑 |
| [sol-crew.md](sol-crew.md) | 帶 sol（agent-fsm）隊員：任務書、必讀清單、guard 誤擋、rlimit 與腦額度 |
| [model-notes.md](model-notes.md) | 模型使用心得：Argon 一次性審查（headless 沒產出怎麼辦） |
| [user-zone-mail.md](user-zone-mail.md) | 經使用者專區寄信、讀回信、照授權動手 |
| [team-patterns.md](team-patterns.md) | 隊形與流程心得：大批舊帳逐筆清、設計流程的實際分工 |
| [權限與沙箱.md](權限與沙箱.md) | 換 uid（免 root 的 subuid 實測）、sudo 身分層的坑、用 transient scope 測 cgroup |

（新類別由審稿子 agent 提、頂層定；11-14 第一批審稿提了上面六份，頂層可改名或併。第三批（11-14，ok-sec、ok-limits 4 份稿）新開「權限與沙箱」收 3 份，1 份併進 patch-and-commit。）

## 格式規矩（審稿時照這些整理）
- 一個工具一個夾 `wf/public/tools/<名>/`，裡面要有 `README.md`（英文，一屏內：做什麼、怎麼用、怎麼裝／拿掉、已知限制、作者與日期）和程式本體；程式輸出一律英文。
- 在 [tools/README.md](tools/README.md) 的表加一列（只追加）。
- 不放秘密、不放只對自己有用的東西、不放會改活樹 lib／py／knowledge 的安裝步驟（要的話寫清楚、交頂層）。
- 頂層也會不定期整理：重複的合併、壞掉的標註、好用的寫進 wf 規矩或建議進 `proto8/`。
