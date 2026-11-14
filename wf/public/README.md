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
| [recipes.md](recipes.md) | 任務類型→做法（一行一列） |
| [pitfalls.md](pitfalls.md) | 踩坑與解法：建置（`_main` 目標）、乾淨複本跑 wf/tools 測試要連 proto8 一起抄、隊長的 shell（zsh 不分詞、卡到逾時、別 pkill -f）、試真東西別碰原件、`pgrep -af aos-daemon` 多列的是看顧子行程、封存搬檔預設留指標頁不帶 `--rm` |
| [patch-and-commit.md](patch-and-commit.md) | 暫存樹改動搬回已往前走的 main、驗收跑全套（含環境沒清的假綠）、commit-request 的坑 |
| [sol-crew.md](sol-crew.md) | 帶 sol（agent-fsm）隊員：任務書、必讀清單、guard 誤擋、rlimit 與腦額度 |
| [model-notes.md](model-notes.md) | 模型使用心得：Argon 一次性審查（headless 沒產出怎麼辦）、claude -p 做到一半再交新話（stdin stream-json） |
| [user-zone-mail.md](user-zone-mail.md) | 經使用者專區寄信、讀回信、照授權動手 |
| [team-patterns.md](team-patterns.md) | 隊形與流程心得：大批舊帳逐筆清、設計流程的實際分工、每封信寫截至哪裡、硬規則照授權來源分級 |
| [權限與沙箱.md](權限與沙箱.md) | 換 uid（免 root 的 subuid 實測）、sudo 身分層的坑、用 transient scope 測 cgroup |
| [發佈前檢查.md](發佈前檢查.md) | 給外人看的東西交出去前自己驗：照字實跑文件、無頭瀏覽器截圖、掃個人值 |
| [定義與換定義.md](定義與換定義.md) | 自己寫 agent 定義：eca 關 Claude Code 自動記憶、換定義用 set-def、複製定義後重寫 README |
| [gate與鎖.md](gate與鎖.md) | 帶 kernel_gate 的樹少撞逾時；遊戲、桌面這類自己有死活的獨佔資源不要只靠 aos-lock |

（新類別由審稿子 agent 提、頂層定；11-14 第一批審稿提了上面六份，頂層可改名或併。第三批（11-14，ok-sec、ok-limits 4 份稿）新開「權限與沙箱」收 3 份，1 份併進 patch-and-commit。第四批（11-14，ok-release 3 份稿）新開「發佈前檢查」收 3 份，其中照字實跑附的程式收成 tools/doc-run。第五批（11-14，ok-release 1 個工具夾）收成 tools/scan，「發佈前檢查」掃個人值那節改連到它。第六批（11-14，ok-pilot、ok-kb、ok-limits 共 9 份稿）只有 2 份是新內容，都收進 pitfalls：新開一節「乾淨複本跑 wf/tools 測試要連 proto8 一起抄」（ok-pilot），「隊長的 shell」的 zsh 那條擴成「zsh 不分詞」（ok-kb 建議稿）；其餘 7 份（ok-limits 3 份、ok-pilot 4 份）第一到第三批已收，內容沒有新的，跳過。第七批（11-14，ok-wake 2 份稿）都是新內容：「claude -p 做到一半再交新話」收進 model-notes，「pgrep 多列看顧子行程」收進 pitfalls。recipes、patch-and-commit 已近 8 KB，這批沒往裡加。第九批（11-14，ok-kb 2 份建議稿）沒有新條目：「zsh 不分詞」那份第六批已收進 pitfalls「隊長的 shell」，連 heredoc 那筆驗過也在，跳過；照 ok-kb 的清理清單對了三處新舊說法：recipes「必讀清單」那列改成「施工的」sol、指到蒐集員看包那列，sol-crew「必讀清單」開頭加「先看角色」指到 kits，sol-crew「腦額度」補 window all 不重試直接停（313ce20ec），limits 的鍵補 `mem_total_mb`、`procs_total`（50e7a35bc）；本檔回上層的連結改指 wf/INDEX（wf/README 不存在）。第十批（11-14，ok-kb 1 份建議稿）沒有新條目：recipes 第 19 列「回報給頂層」改成「回報」、寄「任務書指定的對象（11-14 起是各部部長）」，不再寫寄 xiaosi；出處連結先留 07 舊段「頂層的雜務自動化」（當時三條標題規矩還在那節；c913897a6 改寫後這節已不在，第十一批改指 07「回報」）。recipes 仍超過 8 KB（8393 位元組），這批沒刪別人的列。第十一批（11-14，ok-kb 2 份建議稿）新增 1 條：pitfalls 新開一節「封存或搬檔：預設留指標頁，不帶 `--rm`」，照頂層 11-14 的裁定寫（預設留指標頁；只有使用者明說要移除舊路徑才照 97cda3435、10a75ac53 帶 `--rm`，那種交件排使用者親跑）；另照稿把 c913897a6 改寫 07 後失效的段名修好：recipes「交 commit」改指 07「commit」、「回報」改指 07「回報」與「寄信怎麼寫」、「等隊員做完」那列原本的「07 頂層提醒」（稿外，同樣失效）改指 aos-teams 入口第 4 件，patch-and-commit 開頭改指 07「commit」，sol-crew「必讀清單」改指 aos-teams 入口「讀規矩」；稿裡第二件（本檔返回連結）第九批已改，跳過。第十二批（11-14，skyrim-agent 1 份稿 7 件）7 件都是別隊也用得上的新內容，全收：「每封信寫截至哪裡」「硬規則分級」收進 team-patterns（後者照 AGENTS.md 鐵律 2 把 push 從「上游信可放行」移到「要使用者本人說」，跟投稿不同處寫在條內）；recipes、pitfalls 都已超過 8 KB，另外新開兩份：「定義與換定義」收 eca 關自動記憶、set-def、複製後重寫 README 三件，「gate與鎖」收帶 gate 的樹、自己有死活的獨佔資源兩件（gate 那件補上 c3c1877ea 起唯讀查詢已自動放行）。skyrim 專屬的部分（skyrim 自己的 lock.sh、hold 程式）只當出處，不寫成做法。）

## 格式規矩（審稿時照這些整理）
- 一個工具一個夾 `wf/public/tools/<名>/`，裡面要有 `README.md`（英文，一屏內：做什麼、怎麼用、怎麼裝／拿掉、已知限制、作者與日期）和程式本體；程式輸出一律英文。
- 在 [tools/README.md](tools/README.md) 的表加一列（只追加）。
- 不放秘密、不放只對自己有用的東西、不放會改活樹 lib／py／knowledge 的安裝步驟（要的話寫清楚、交頂層）。
- 頂層也會不定期整理：重複的合併、壞掉的標註、好用的寫進 wf 規矩或建議進 `proto8/`。
