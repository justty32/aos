# sol-3 答案（宣傳素材與現有說明頁），11-14
> 存檔註（11-14 commit 前）：家目錄絕對路徑換成 `~`、帳號名換成 `<帳號名>`；其餘是 sol 原文。


結論：已找到三組素材：「資料夾＝函數／程式」的核心介紹、「任意資源作業系統」的定位，以及「逐步降低 LLM 依賴」的願景；公司部門則是全景操作介面的比喻。這些是使用者原話與構想，不能直接當成已驗證的產品能力。（`proto8/user-advice/20261027.md:1`、`proto8/user-advice/20261113.md:5`、`proto8/user-advice/20261113.md:13`、`proto8/user-advice/20261114.md:7`）

以下路徑均相對於 `~/repo/aos/`。

## A. 五份意見稿摘要

| 文件 | aos 是什麼、想做成什麼、賣點與比喻 |
|---|---|
| `proto8/user-advice/README.md` | 描述從 Claude Code CLI 節點，轉成 aos loop/fsm agent，再拆出工具、函數與子 agent 的逐步優化過程；目標是在保有使用者好評下降低 token 消耗。評判器、優化器與普通樹可以共存。比喻是「節點＝神經元」，但文末仍在反思 `_improve` 是否應解耦，並非完整定案。出處：`proto8/user-advice/README.md:14`、`proto8/user-advice/README.md:16`、`proto8/user-advice/README.md:27`、`proto8/user-advice/README.md:46`。 |
| `proto8/user-advice/20261027.md` | 核心是「資料夾作為函數」：功能透過 POSIX 呼叫與資料夾綁定，旁邊放相關資訊；agent 的一輪動作也視為函數。起步可以納管現成 Claude Code CLI，再透過 aos-mcp 接入 aos 函數；文中另提出實例查詢、開啟、暫停與閒置回收構想。出處：`proto8/user-advice/20261027.md:1`、`proto8/user-advice/20261027.md:6`、`proto8/user-advice/20261027.md:25`、`proto8/user-advice/20261027.md:33`。 |
| `proto8/user-advice/20261106.md` | 把檔案系統當可編程介質，強調 LLM 原生理解與操作檔案的能力，以及 Linux 權限、跨語言與現有生態。比喻是 aos-exec／loop／daemon 對應 CPU 指令／CPU／硬體板子，kernel 在其上管理資源；遠期目標是用 RSI 逐步減少 LLM 呼叫，把工作轉入工具，降低不確定性與 token 消耗。出處：`proto8/user-advice/20261106.md:6`、`proto8/user-advice/20261106.md:9`、`proto8/user-advice/20261106.md:29`、`proto8/user-advice/20261106.md:34`、`proto8/user-advice/20261106.md:45`、`proto8/user-advice/20261106.md:56`。 |
| `proto8/user-advice/20261113.md` | 明說全名是 akatosh operating system，定位為「基於任意資源」而非僅硬體的作業系統；資源用 JSON 表示，可自由細化、粗化並交給 AI 處理。賣點包括 AI 容易掌握、把人類可理解性也納入優化，以及支撐大量 agent 與自我改進函數。開發體驗比喻為 Lisp 的理想狀況；把 agent 逐步換成確定程式是願景，不是成果證明。出處：`proto8/user-advice/20261113.md:5`、`proto8/user-advice/20261113.md:9`、`proto8/user-advice/20261113.md:13`、`proto8/user-advice/20261113.md:19`、`proto8/user-advice/20261113.md:27`。 |
| `proto8/user-advice/20261114.md` | 轉向人如何掌握與操作整個 agent 組織：用網頁看全景、看團隊與員工狀態，並能說話、寄信；公司部門可嵌套，LLM 呼叫比喻為公司的電力基礎設施。另明確提出公開 demo、GitHub Pages 產品頁、安裝／使用手冊、範例與教學，並希望外人 clone 後能立即使用。出處：`proto8/user-advice/20261114.md:5`、`proto8/user-advice/20261114.md:7`、`proto8/user-advice/20261114.md:19`、`proto8/user-advice/20261114.md:35`、`proto8/user-advice/20261114.md:45`。 |

## B. 宣傳文案原話：22 句

引文均為原文連續摘錄，未改字；「用途」只是素材標籤，不代表發佈定稿。涉及任意目標、零 token、RSI、完全確定性者，保留為願景素材。（`proto8/user-advice/20261106.md:34`、`proto8/user-advice/20261106.md:45`、`proto8/user-advice/20261113.md:13`）

1. 【一句話介紹】「我們將資料夾作爲函數。」
   出處：`proto8/user-advice/20261027.md:1`

2. 【特色】「資料夾內因爲可以有多個檔案，所以可以擺放該函數的各類其他資訊。」
   出處：`proto8/user-advice/20261027.md:3`

3. 【特色】「評判器，優化器兩棵樹，可以和普通樹，共存在同一根節點下。」
   出處：`proto8/user-advice/README.md:14`

4. 【標語】「我認爲這是the new age of programming。」
   出處：`proto8/user-advice/20261106.md:3`

5. 【一句話介紹】「我們把filesystem作爲lua來使用，一個簡單的手段就是準備一個程式aos-exec，這個程式可以把資料夾當做檔案來執行，只需要資料夾內有一個_entry檔案即可。」
   出處：`proto8/user-advice/20261106.md:6`

6. 【特色】「第一個好處就是能夠白嫖linux的檔案權限機制，其次就是能夠跨程式語言實作功能。不過最重要的，是agent原生就有操控資料夾的能力。」
   出處：`proto8/user-advice/20261106.md:6`

7. 【特色】「OK，總之，我這邊要強調的就是檔案系統之於LLM的原生理解性與原生可操作性。」
   出處：`proto8/user-advice/20261106.md:9`

8. 【特色】「而在這個基礎上，我們實作了aos loop/fsm agent。秉承unix哲學與傳統，沿襲plan9理想，各種東西都盡量以檔案表示，其本體程式盡量簡短。」
   出處：`proto8/user-advice/20261106.md:10`

9. 【一句話介紹】「後續的比喻就不多說了，總之在這個比喻下，我們有了aos-exec/loop/daemon，分別對應cpu指令/cpu/硬體板子。」
   出處：`proto8/user-advice/20261106.md:29`

10. 【願景】「所以aos系統的目標就是優化任意目標。」
    出處：`proto8/user-advice/20261106.md:34`

11. 【願景】「在aos體系的幫助下，實現以RSI方式，持續降低token消耗直至0，並且提升AI智商的路途。」
    出處：`proto8/user-advice/20261106.md:45`

12. 【願景】「要降低這個函數的不確定性，自然就是減少llm呼叫，盡量讓工作都堆積到tools。」
    出處：`proto8/user-advice/20261106.md:56`

13. 【標語】「RSI的飛輪，自此而始」
    出處：`proto8/user-advice/20261106.md:61`

14. 【一句話介紹】「就是說，aos的全名，就是akatosh operating system，這個操作系統很特別，他並非基於硬體，而是基於任意資源。」
    出處：`proto8/user-advice/20261113.md:5`

15. 【願景】「所以我們的aos能處理很多東西，也讓很多東西變成了可能。」
    出處：`proto8/user-advice/20261113.md:5`

16. 【特色】「ps.aos技術棧還有一個好處，就是AI能輕鬆掌握。」
    出處：`proto8/user-advice/20261113.md:9`

17. 【願景】「下一步，aos既然能處理很多東西，那我們的目標就可以稍微廣泛一些，首先是人類的可理解性這類，就可以透過aos kernel來優化了。」
    出處：`proto8/user-advice/20261113.md:9`

18. 【願景】「對，我就是不要使用LLM，簡單說我的目標，就是把一個agent，逐步替換掉成純粹的，沒有幾率性可言的程式函數。」
    出處：`proto8/user-advice/20261113.md:13`

19. 【一句話介紹】「在aos體系下開發軟體的體驗有點類似lisp的理想狀況。」
    出處：`proto8/user-advice/20261113.md:19`

20. 【願景】「你先從一個能幫你開發函數的函數開始，然後改進這個函數，使其變得能更好的開發函數，如此下去，直到他開發的函數達到你的預期。」
    出處：`proto8/user-advice/20261113.md:19`

21. 【願景】「可能是互相成就吧，我們優化管理了這些，就能開發更大更神奇的軟體，而爲了開發更大更神奇的軟體，我們也就有了更多樣的優化管理需求，如此螺旋上升。」
    出處：`proto8/user-advice/20261113.md:27`

22. 【願景】「讓我掌握全景這塊，我這邊還有個餿主意：就像是管理公司一樣，要讓我這個董事長掌握狀況，所以就是分部門這樣」
    出處：`proto8/user-advice/20261114.md:7`

## C. 現有說明頁與 artifact

下表的「可取用部分」是現有內容盤點，不是產品頁設計決定。

| 路徑／出處 | 一句話內容與可取用部分 |
|---|---|
| `README.md:3` | 已有「資料夾＝程式」的一句話介紹、本體位置與技術組成；建置安裝入口在 `README.md:7`，可作對外 README 的既有文字底稿。 |
| `proto8/README.md:19` | 頂層角色、元件與文件導航總覽，可取用元件分類與入口說明，但目前是開發者導覽。 |
| `proto8/README.md:38` | 記載兩份 10-20 artifact：「概念層」與「實作想法」，連結 ID 分別為 `QJjGNnKFhKeS7r1f5bHzu7`、`ATizWpsmAa2qutXWZ2owjm`；外部頁面內容未查到，README 所指 `scratchpad/pages/proto8-concepts.html`、`scratchpad/pages/proto8-impl.html` 在本次指定 repo 路徑下不存在。 |
| `proto8/docs/README.md:5` | 概念／規範／慣例三份正式條文的總覽，可作手冊的參考文件入口。 |
| `proto8/thinking/2026-11/13/aos-home-手冊.html:38` | 公司 WSL 的操作手冊，含樹狀 SVG、起停、聊天、備份還原與新增 agent，可取用圖解和操作主題；它綁定私人環境，且含覆蓋／刪除指令，不是可原封公開的通用手冊。 |
| `proto8/thinking/2026-11/13/kernel-framework-架構圖.html:75` | 用圖解說明「daemon 是手、kernel 是門」、請求鏈、hook 與 agent 當門，可取用概念圖與白話結論；頁面明標是 11-13 的程式快照。 |
| `proto8/kernel/README.md` | 已有 kernel 範本總覽、資源管理、排隊、hook、請求轉寄及使用方式，可供特色與進階手冊取材。 |
| `proto8/templates/README.md` | 已有 eca-claude／agent-fsm 範本、複製與掛載方式、工具骨架及裁判範本說明，可供範例與教學盤點。 |
| `wf/tools/progress_board/web/guide.html:20` | aos × arcagi 圖解入門，含「資料夾＝程式」、學習循環與範例；可取用案例呈現方式，但文中含 arcagi 專屬成果及施工中項目，不能當通用 aos 能力證據。 |
| `wf/tools/progress_board/web/guide-detail.html:20` | arcagi 的流程、指令、格式、環境變數與名詞表，可取用文件分層形式；內容仍依賴另一份 repo。 |
| `wf/tools/progress_board/web/guide-play.html:20` | 11 題小樹的逐步帶玩，含原指令與歷史實跑輸出，可作教學素材參考；依賴 `~/code/playground-arc-play`，不是 clone 本 repo 即可重現的證明。 |
| `wf/tools/progress_board/README.md:3` | 開發進度看板的說明，含各線進度、待裁題、細節與輪次；屬內部協作工具，不是 aos 公開產品介紹。 |
| `proto8/thinking/2026-11/13/aos-1113-優先裁.html:163`、`proto8/thinking/2026-11/13/aos-1113-收工待裁.html:163` | 分別是 7 題與 24 題的內部裁決頁，屬決策紀錄而非產品文案。 |
| `proto8/thinking/2026-11/13/aos-wu-1113-待你裁.html:164`、`proto8/thinking/2026-11/13/aos-wu-1113-top-待你裁.html:164`、`proto8/thinking/2026-11/13/aos-wu-1113-r2-待你裁.html:164` | 分別是 128 題、精選 17 題與第二輪 43 題的裁決頁，能辨認文件演進問題，但不是對外說明頁。 |
| `archive/proto7-2/notes/status/architecture.html:168`、`archive/proto7-2/notes/status/proto7-2-status.html:97`、`archive/proto7-2/notes/status/2026-10-09.html:52` | 舊原型的架構、狀態與當日成果頁；可辨認歷史圖解素材，但不能用作 proto8 現況說明。 |

## D. `proto8/docs` 頂層骨架

實際頂層為三個資料夾 `CONCEPTS/`、`NORMS/`、`CONVENTION/`，加上三份同名入口 Markdown 與 `README.md`；現有文件採「入口＋同名分檔資料夾」。（`proto8/docs/README.md:5`）

| 頂層目錄與入口 | 一句話定位／既有涵蓋範圍 |
|---|---|
| `proto8/docs/CONCEPTS/`；入口 `proto8/docs/CONCEPTS.md` | 「aos 怎麼看世界」：設計理念、時空、基礎設施、kernel、agent，加上名詞與板子比喻；可對應手冊的概念與名詞參考部分。出處：`proto8/docs/CONCEPTS.md:12`。 |
| `proto8/docs/NORMS/`；入口 `proto8/docs/NORMS.md` | 「從概念推出來、大家都要守的」：執行、環境變數、loop／daemon、窗、投遞、指示詞、fsm 與 kernel 等契約；可對應手冊的行為規則與格式參考部分。出處：`proto8/docs/NORMS.md:7`、`proto8/docs/NORMS/主題.md:8`。 |
| `proto8/docs/CONVENTION/`；入口 `proto8/docs/CONVENTION.md` | 「自己人寫 agent 時照抄的標準形狀，不要求別人守」：佈局、入口、queue、stack、停錯、腦與工具、MCP、信箱及巢狀；可對應手冊的 agent 編寫慣例與範例部分。出處：`proto8/docs/CONVENTION.md:5`、`proto8/docs/CONVENTION.md:24`。 |

實際已讀必讀清單：1（`_description.json` 全文及資料夾 `index_view`）、2（`AGENTS.md`）、3（`common/user.md`）、4（`aos-teams.md`）、5（06）、6（07），全部讀完。