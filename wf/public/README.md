# wf/public — 公用知識庫

← [WORKFLOWS](../WORKFLOWS.md)

aos 體系下各 agent 共同能存取的做法與坑（使用者 11-17「wf/public也需要整理精簡，這裡是aos體系下，各agent共同能存取的地方」）：頂層、各 ok-* eca、它們掛的 sol／astra 等 fsm 都能讀、都能投稿；由頂層 repo-aos 管理（使用者 11-14「大家如果自己有弄出好工具，也可以分享出來。你這邊也稍微掌管一下wf/public公用知識庫，wf/public/tools之類」）。

**怎麼查**：要做某件事 → 先看 [recipes](recipes.md)（一行做法＋去哪節）；想知道某一類的坑 → 下表挑主題。每節的標題就是結論，內文是「什麼情況 → 怎麼做」。aos 本身哪裡該改，投 [wf/advices](../advices/README.md)，不放這裡。

## 主題

<!-- wf-nav -->
| 檔 | 收什麼 |
|---|---|
| [recipes](recipes.md) | 任務類型→一行做法的總表：隊員、交件與驗收、其他三段 |
| [pitfalls](pitfalls.md) | shell 與建置的坑：zsh 不分詞、指令卡住、別 pkill -f、工作區外被擋、pgrep 多列；暫存樹編 C++ 執行檔落在哪（`_main` 那條 11-17 起不適用）、乾淨複本帶齊依賴與標準跑法、新鍵斷言、`.orig`、試真東西別碰原件 |
| [建置與相依](建置與相依.md) | 把 C++ 庫匯出給外部用：私有相依漏進匯出、外部消費測試要 `env -u VCPKG_ROOT`、漏標 `AOS_API` |
| [Windows與WSL](Windows與WSL.md) | 公司 Windows 那台：假 python3、不分大小寫、中文檔名 quotepath、`/mnt/c` 全 +x、MSYS 路徑轉換 |
| [行程與環境](行程與環境.md) | 收行程只收自己的、SIGINT 收不到 daemon、先清 `AOS_*`（zsh 會失效）、起樹前先 source env.sh、`pgrep -fc` 多算、killpg 弄掛 WSL、setsid |
| [共用工作樹與git](共用工作樹與git.md) | 同檔只給一條線、別人的 commit 帶走你的字、生成器掃整棵樹、別 autostash、整檔改寫不拆刪加、合併後才刪分支、worktree 起點舊 |
| [patch-and-commit](patch-and-commit.md) | 暫存樹改動搬回往前走的 main、驗收跑全套（含沒清環境的假綠）、commit-request 與 claim 的坑、先交一個小修、檔放回 repo、放行看三樣、共用計數重算、封存搬檔留指標頁 |
| [活樹旁邊](活樹旁邊.md) | 查哪些改動活樹當下就吃到（11-18 起程式要 `install.py` 才生效；knowledge、frontend 存檔即生效）、換這類檔的順序、在 repo 跑 install.py＝換活樹那份、唯讀查看也要點名、查祕密不落地、換樹當晚的 pin |
| [審查與實測](審查與實測.md) | 獨立審稿員怎麼問、讀 daemon 表要用真的列、真模型跑一輪（不騙模型）、故意改壞的快取、外包 diff 逐行審、改前改後逐位元對照、守門程式、瀏覽器層唯讀守門 |
| [設計與查證](設計與查證.md) | 派小修前查 main、先問介面、查別人的 bug、蓋到使用者舊裁定、備註有兩種讀法照小的做、算式先模擬、UX 先量、設計線配施工線、fable 帶原型、搬信改 reply_to |
| [派線與任務書](派線與任務書.md) | 預掃涵蓋全部組別、線推翻交接書、背景與步驟矛盾、禁區寫成唯一准用的做法、任務書 checklist、「檢查過」要附輸出、截止點還原乾淨、舊東西怎麼用、8 核一條線、codex 年代的坑 |
| [改文件與知識庫](改文件與知識庫.md) | 改寫必讀規矩檔、換全場共用工具、請新人照索引走、知識庫頁對程式、改文件的小坑（非貪婪正則、`\b`、fix_moved_links 別重跑） |
| [整理與拆檔](整理與拆檔.md) | 拆檔先 grep 錨點、目錄改名殘留、跳過 code fence、archive 准動什麼、表格類活檔、8192 邊緣、`link_columns`、空行躲門檻、`grep -c` 假通過、多 repo 檢查 |
| [等隊員與讀信](等隊員與讀信.md) | 等隊員要帶逾時、別一直催、信交錯與「截至哪裡」、記時刻先對時鐘、回報寫讀了什麼沒做什麼 |
| [sol-crew](sol-crew.md) | 帶 sol（agent-fsm）：任務書、施工員五句、必讀清單、guard 誤擋、掛法的坑、rlimit 實測與腦額度、暫存 kernel 日額、排隊慢時改派、縮工具與提示快取 |
| [claude子agent](claude子agent.md) | 派 Claude 子 agent：前景跑加進度檔、寫最終回答前收齊背景工作、可寫路徑寫死、被權限擋會乾等、交回的事實要核、system set 是取代 |
| [model-notes](model-notes.md) | Argon 一次性審查、管線叫 `claude -p` 給 `</dev/null`、`claude -p` 做到一半再交新話、用本機紀錄算 Claude token |
| [user-zone-mail](user-zone-mail.md) | 經使用者專區寄信、題目怎麼寫、讀回信與驗、照授權刪檔 |
| [team-patterns](team-patterns.md) | 大批舊帳逐筆清、隊員定義的硬規則照授權來源分級 |
| [權限與沙箱](權限與沙箱.md) | 免 root 換 uid（subuid）、sudo 身分層的坑、用 transient scope 測 cgroup |
| [發佈前檢查](發佈前檢查.md) | 給外人看的東西交出去前：照字實跑文件、無頭瀏覽器截圖、掃個人值 |
| [定義與換定義](定義與換定義.md) | 自己寫 agent 定義：eca 關自動記憶、換定義用 set-def、複製定義後重寫 README |
| [gate與鎖](gate與鎖.md) | 帶 kernel_gate 的樹少撞逾時；遊戲、桌面這類自己有死活的獨佔資源不要只靠 aos-lock |
| [tools/](tools/README.md) | 公用小工具，一個工具一個夾：quiet、waitdone、doc-run、fsm-guard、scan |

## 投稿怎麼走

使用者 11-14：「我們開了這麼多隊伍，我們會需要一個共用的知識庫…建議各隊伍都把他們覺得可以放入的東西交給你，你派claude subagent去審核和整理，放入並建index吧。」

1. **隊伍交稿**：稿放在自己的私有地盤 `wf/ws/<上層>/<名>/public-submit/<題目>.md`（工具就放整夾；地盤見 [wf/ws](../ws/README.md)）。稿頭照舊寫三行：適用情境、驗過沒（誰、哪天、怎麼驗的）、出處（紀錄檔或 commit）；審稿要看這三行，入庫時由頂層拿掉（使用者 11-17 待裁網頁 public-2 選 A）。**不用自己 commit、不用自己改 wf/public**。
2. **通知**：寄任務書指定的對象（部長），title 開頭 `[public-submit]`，what 列稿的路徑；部長收齊交頂層（使用者 11-17 待裁網頁 public-1 選 B）。
3. **審與整理**：頂層成批派 Claude 子 agent 審：有沒有秘密／私人資訊、是不是別隊也用得上、跟現有的重不重複、驗過沒、跟 wf 規矩衝不衝突。過的改寫成庫裡的格式放進來，重複的合併，退的寫原因回給投稿隊伍。
4. **入庫**：頂層走 commit-request 交，並更新上面的主題表。

## 格式規矩（審稿時照這些整理）

- 一條一節：`##` 標題寫結論（「什麼情況：怎麼做」），內文寫適用情況與做法；不寫誰、哪天、哪一批踩到的經過，不留驗過、出處、投稿欄（稿頭那三行入庫時拿掉；原稿與 commit 訊息裡還在）。只踩過一次、沒重現的，在條內註一句。
- 同一件事只寫一處，別處連過來；規矩本身在 wf 工作流裡的（06 硬規則、07、STRUCTURE），這裡只寫做法與坑、連到規矩。
- 一頁超過約 8 KB 就照主題拆，原檔留成總頁（別處連進來的錨點要保住）；新主題由審稿子 agent 提、頂層定。
- 一個工具一個夾 `wf/public/tools/<名>/`，裡面要有 `README.md`（英文，一屏內：做什麼、怎麼用、怎麼裝／拿掉、已知限制、作者與日期）和程式本體；程式輸出一律英文。在 [tools/README.md](tools/README.md) 的表加一列（只追加）。
- 不放秘密、不放只對自己有用的東西、不放會改活樹 lib／py／knowledge 的安裝步驟（要的話寫清楚、交頂層）。
- 頂層不定期整理：重複的合併、過時的拿掉、好用的寫進 wf 規矩或建議進 `proto8/`。
