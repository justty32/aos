# wf/advices — 對 aos 本身的意見庫

← [INDEX](../INDEX.md)

各隊做事時對 **aos 本身**（daemon、mailbox、kernel、fsm、工具、指令、知識庫、文件）冒出的改進意見，收在這裡。之後要改進 aos，先從這裡找參考。由頂層 repo-aos 管理。

使用者 11-14：「然後大家做一做，會有一些對於aos的意見，也請你收下，並另外派claude subagent整理，並放入wf/advices，之後有要改進aos，我們就可以從中找到參考」

跟 [wf/public](../public/README.md) 的分別：public 收「怎麼用 aos 做事」的做法、工具、心得；advices 收「aos 哪裡該改」的意見。

## 投稿怎麼走

1. **隊伍交稿**：稿放在自己工作區 `wf/temp/<線名>/aos-advice/<題目>.md`，一個意見一份。每份寫這幾樣：
   - 哪裡：哪支指令、哪個元件、哪份文件。
   - 現象：遇到什麼，最好附實際指令和輸出。
   - 建議：想怎麼改。
   - 痛的程度：擋路、拖慢、小不便，三選一。
   - 出處：紀錄檔或 commit。
   隊伍不用 commit，也不要自己改 wf/advices。
2. **通知**：寄信給 xiaosi，title 開頭寫 `[aos-advice]`，what 列出稿的路徑。xiaosi 收齊後轉給頂層。
3. **整理**：頂層成批派 Claude 子 agent 整理：
   - 查有沒有秘密或私人資訊。
   - 同一件事的意見合成一條，保留每個投稿隊伍和出處。
   - 按主題歸檔。
   - 查 repo 裡是不是已經改好了，改好的標「已解」並附 commit。
4. **入庫**：頂層走 commit-request commit，並更新下面的索引。

## 每條意見的格式

`## <一句話標題>`，下面列：主題、哪裡、現象、建議、痛的程度、提出者與日期（可以有多個）、出處、狀態。狀態只有四種：未處理、已排入（附線名）、已解（附 commit）、不採納（附原因）。

## 索引

第一批（11-14，五隊 15 份稿）整理後共 16 條（小坑三則拆成三條）。第二批（11-14，三隊 6 份稿）新增 4 條、合併 2 份進舊條（MCP 60 秒、子 agent 不知道誰生了它），新開「知識庫與文件」。第三批（11-14，三隊 4 份稿、5 個意見）新增 4 條、合併 1 個意見進舊條（MCP 60 秒，加 ok-board）。第四批（11-14，三隊 3 份稿）新增 2 條（fsm 範本「預設 55 支工具的說明成本」、kernel 與額度「kernel 沒開時 listen 只會逾時」），1 份是狀態更新：「mailbox_read 預設刪信」改已解（ace14088d8）。第五批（11-14，兩隊 3 份稿）新增 3 條：fsm 範本「sol 可寫範圍寫在兩份清單」（已排入 ok-fsm）、「before_tool 擋下標 is_error:false」，信件與溝通「回答對不到是哪封信」（「aos-agent 沒有 ask」那條的後續，開成新條，舊條改指過來）。第六批（11-14，ok-kb 1 份稿）新增 1 條：指令與工具「四支工具的 tooldef 說明跟程式不符」（查過 3274da594、1e67c58ff 只改知識庫頁，tooldef 還沒改，未處理）。第七批（11-14，ok-board、ok-kf 各 1 份稿）新增 2 條：新開「安全」收「原型把整份環境寫進檔，帶出 API key」（只有第 4 條「daemon 起 proc 用環境白名單」轉 ok-sec 當候選，標已排入、附註其餘未處理）；指令與工具「commit-request claim 把 git 轉義過的中文路徑原樣存下」（查過 commit_queue.py 還沒改，未處理）。主題由整理的子 agent 提，頂層定。

| 主題檔 | 收什麼 | 未處理 | 已排入 | 已解 |
|---|---|---|---|---|
| [daemon與行程](daemon與行程.md) | daemon、aos-loop、daemon 表、--limits、認行程 | 4 | 0 | 1 |
| [信件與溝通](信件與溝通.md) | mailbox、aos-post 信件格式、專區信、say／ask／listen、回答配對信名 | 4 | 0 | 3 |
| [kernel與額度](kernel與額度.md) | llm kernel、腦額度、找 kernel、kernel hook | 3 | 0 | 1 |
| [fsm範本](fsm範本.md) | agent-fsm 範本、工具包、system 文字、guard 與可寫範圍、before_tool 擋下的標法、wait 與冷卻、goal | 5 | 2 | 2 |
| [指令與工具](指令與工具.md) | aos-agent、aos-view、建置、wf/tools（含 commit-request）、工具說明（tooldef） | 3 | 0 | 3 |
| [知識庫與文件](知識庫與文件.md) | 知識庫頁、元件 docs 跟程式對不上 | 0 | 0 | 1 |
| [安全](安全.md) | 密鑰外洩面、proc 環境繼承、暫存檔權限 | 0 | 1 | 0 |

合計 33 條：未處理 19、已排入 3、已解 11（「部分已做／部分已解」的仍算未處理；「安全」那條只有一部分排入，照使用者指定的狀態算已排入）。第一批實際入庫 17 條，上面「16 條」是當時的筆誤，照各檔實數。
