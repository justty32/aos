# wf/public — 公用知識庫

← [wf/INDEX](../INDEX.md)

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
| [tools/](tools/README.md) | 小工具，一個工具一個夾：quiet（安靜時段）、waitdone（背景等 fsm 隊員答完）、doc-run（照字實跑文件、比對抄本指令）、fsm-guard（agent-fsm 的 before_tool 守門）、scan（發佈前掃個人值和金鑰） |
| [recipes.md](recipes.md) | 任務類型→做法（一行一列）的總頁，分三頁：[隊員](recipes-隊員.md)、[交件與驗收](recipes-交件與驗收.md)、[其他](recipes-其他.md) |
| [pitfalls.md](pitfalls.md) | 踩坑的總頁，分兩頁：[shell](pitfalls-shell.md)（zsh 不分詞、指令卡住、工具被擋、pgrep 多列）、[建置與複本](pitfalls-建置與複本.md)（`_main` 目標、乾淨複本怎麼抄怎麼跑、試真東西別碰原件） |
| [patch-and-commit.md](patch-and-commit.md) | 暫存樹改動搬回已往前走的 main、驗收跑全套（含環境沒清的假綠）、commit-request 的坑 |
| [交件與放行.md](交件與放行.md) | claim 的坑、工作樹有未交改動時先交小修、放行看三樣與放行版本、共用計數重算、封存搬檔預設留指標頁 |
| [活樹旁邊.md](活樹旁邊.md) | 哪些檔存檔就生效、怎麼換（備份、順序、預演）、唯讀查看也要點名、查祕密不落地、換樹 pin |
| [審查與實測.md](審查與實測.md) | 獨立審稿員怎麼問、讀 daemon 表要用真的列、真模型跑一輪、改前改後對照、守門程式、瀏覽器層唯讀守門 |
| [設計與查證.md](設計與查證.md) | 派小修前查 main、先問介面、查別人的 bug、蓋到使用者舊裁定、算式先模擬、UX 先量、設計線配施工線、搬信改 reply_to |
| [改文件與知識庫.md](改文件與知識庫.md) | 改寫必讀規矩檔、請新人照索引走一遍、知識庫頁對程式、check_anchors 掃到別線草稿等小坑 |
| [等隊員與讀信.md](等隊員與讀信.md) | 等隊員要帶逾時、長回合讀不到信、不要一直催、信交錯、記時刻先對時鐘 |
| [sol-crew.md](sol-crew.md) | 帶 sol（agent-fsm）隊員：任務書、必讀清單、guard 誤擋、rlimit 與腦額度 |
| [sol-排隊與額度.md](sol-排隊與額度.md) | sol 排隊慢時改派、暫存 kernel 日額、掛法的坑、施工員任務書、縮工具與提示快取 |
| [claude子agent.md](claude子agent.md) | 派 Claude 子 agent：寫最終回答前收齊背景工作（否則 claude -p 不退出、回合掛住）、前景跑加進度檔、可寫路徑寫死、被權限擋會乾等、交回的事實要核、system set 是取代 |
| [model-notes.md](model-notes.md) | 模型使用心得：Argon 一次性審查、claude -p 做到一半再交新話、用本機紀錄算 Claude token |
| [user-zone-mail.md](user-zone-mail.md) | 經使用者專區寄信、讀回信、題目怎麼寫、照授權動手 |
| [team-patterns.md](team-patterns.md) | 隊形與流程心得：大批舊帳逐筆清、設計流程的實際分工、每封信寫截至哪裡、硬規則照授權來源分級 |
| [權限與沙箱.md](權限與沙箱.md) | 換 uid（免 root 的 subuid 實測）、sudo 身分層的坑、用 transient scope 測 cgroup |
| [發佈前檢查.md](發佈前檢查.md) | 給外人看的東西交出去前自己驗：照字實跑文件、無頭瀏覽器截圖、掃個人值 |
| [定義與換定義.md](定義與換定義.md) | 自己寫 agent 定義：eca 關 Claude Code 自動記憶、換定義用 set-def、複製定義後重寫 README |
| [gate與鎖.md](gate與鎖.md) | 帶 kernel_gate 的樹少撞逾時；遊戲、桌面這類自己有死活的獨佔資源不要只靠 aos-lock |
| [入庫紀錄.md](入庫紀錄.md) | 各批審稿收了什麼、併到哪、跳過什麼（流水帳，查來歷才看） |

新類別由審稿子 agent 提、頂層定。一頁超過約 8 KB 就照主題拆，原檔留成總頁（別處連進來的錨點要保住）。

## 格式規矩（審稿時照這些整理）
- 一個工具一個夾 `wf/public/tools/<名>/`，裡面要有 `README.md`（英文，一屏內：做什麼、怎麼用、怎麼裝／拿掉、已知限制、作者與日期）和程式本體；程式輸出一律英文。
- 在 [tools/README.md](tools/README.md) 的表加一列（只追加）。
- 不放秘密、不放只對自己有用的東西、不放會改活樹 lib／py／knowledge 的安裝步驟（要的話寫清楚、交頂層）。
- 頂層也會不定期整理：重複的合併、壞掉的標註、好用的寫進 wf 規矩或建議進 `proto8/`。
