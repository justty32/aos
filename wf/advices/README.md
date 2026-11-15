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

第一批（11-14，五隊 15 份稿）整理後共 16 條（小坑三則拆成三條）。第二批（11-14，三隊 6 份稿）新增 4 條、合併 2 份進舊條（MCP 60 秒、子 agent 不知道誰生了它），新開「知識庫與文件」。第三批（11-14，三隊 4 份稿、5 個意見）新增 4 條、合併 1 個意見進舊條（MCP 60 秒，加 ok-board）。第四批（11-14，三隊 3 份稿）新增 2 條（fsm 範本「預設 55 支工具的說明成本」、kernel 與額度「kernel 沒開時 listen 只會逾時」），1 份是狀態更新：「mailbox_read 預設刪信」改已解（ace14088d8）。第五批（11-14，兩隊 3 份稿）新增 3 條：fsm 範本「sol 可寫範圍寫在兩份清單」（已排入 ok-fsm）、「before_tool 擋下標 is_error:false」，信件與溝通「回答對不到是哪封信」（「aos-agent 沒有 ask」那條的後續，開成新條，舊條改指過來）。第六批（11-14，ok-kb 1 份稿）新增 1 條：指令與工具「四支工具的 tooldef 說明跟程式不符」（查過 3274da594、1e67c58ff 只改知識庫頁，tooldef 還沒改，未處理）。第七批（11-14，ok-board、ok-kf 各 1 份稿）新增 2 條：新開「安全」收「原型把整份環境寫進檔，帶出 API key」（只有第 4 條「daemon 起 proc 用環境白名單」轉 ok-sec 當候選，標已排入、附註其餘未處理）；指令與工具「commit-request claim 把 git 轉義過的中文路徑原樣存下」（查過 commit_queue.py 還沒改，未處理）。第八批（11-14，ok-fsm 3 份稿）新增 1 條：fsm 範本「sol 讀完必讀後只回一句『我會照做』就結束回合」（未處理）；2 份是狀態更新：「goal 是 paused 時來了信」改已解（38271da3b，沒採自動 resume、改成提醒一次），「蒐集用 sol 的工具包寫不了純文字檔」部分已解（建議 1 ws-write 包 38271da3b、建議 2 和 3 已寫進 aos-teams/07，`aos-agent history last` 沒做），仍算未處理。第九批（11-14，ok-kb 4 份稿＋1 份清理清單）新增 3 條：指令與工具「stat 遇到讀不了的資料夾會丟 traceback」「ctl add 的 --help 對 --limits 寫錯」、fsm 範本「llm_settings.py 註解說 fixed 欄位照舊蓋過」（三條都查過程式還沒改，未處理）；「四支工具的 tooldef」那份第六批已收、內容沒新的，查過 tooldef 仍沒改；照 ok-kb 清理清單改了 3 條的狀態：「信件一封一個夾」改已排入（ok-sec，Q10 使用者選 2）、「aos-post 沒有認領指定的一封」補一句 Q10 後 aos-post 會動、「範本預設掛 55 支工具」改部分已解（產品版 kits 3ed649b09、fdfbc5515，仍算未處理）。第十批（11-14，ok-limits、ok-kf 各 1 份稿）新增 1 條：daemon與行程「帶 --envs 的 add 換了掛法」（表上 exec 變 null、set-def 拒收、as_written 與 --path-json 指示詞掉了；查過 set_def.py 仍拒收，未處理）；ok-kf 那份是第七批「commit-request claim 把 git 轉義過的中文路徑原樣存下」的補充，只補了 submit 的 495 行與 claims.json 所在夾，在 HEAD b892fbd83 再查 commit_queue.py 仍沒改，未處理。第十一批（11-14，ok-onboard 1 份、ok-pilot 1 份、ok-fsm 3 份稿，加 skyrim-agent-agentctl 筆記裡的 3 件）新增 7 條：指令與工具「`#` 在 json 工具和檔案工具裡意思不同；keep 的說明寫從工作區」（下層不限工作區是使用者 11-10、11-13 裁的設計，這條只記說明跟行為不符，未處理）、「commit-request claim 一個資料夾蓋不到夾裡的檔」（跟「claim 把轉義路徑原樣存」根源相同但改法不同，分開記、互標相關，未處理）；fsm 範本「eca 沒有 goal 暫停後來信的提醒」（未處理）、「eca-claude 範本在 dontAsk 下沒放行 Read／Glob／Grep」（skyrim 那邊在自己的定義改了，aos 範本沒改，未處理）；kernel與額度「eca 當 gate 時唯讀查詢也被 hold」（已解 c3c1877ea，活樹待換樹）、「gate 站掛在主人的 on_clock，主人長回合時下屬逾時」（設計使然，已排入 ok-kf）、「subagent add 後馬上 ask，工人被從名冊刪掉」（已解 c3c1877ea，活樹待換樹）。ok-fsm 另 2 份：「冷卻後重寄的請求可能已過 deadline」改已解（3b02a41c4）；「取隊員最後回答沒有現成指令」是「蒐集用 sol 的工具包寫不了純文字檔」沒做的那半，併進那條，仍算未處理。第十二批（11-14，skyrim-agent 1 份稿共 11 個意見，加頂層交代 2 件）新增 11 條：指令與工具「ctl stop／rm 遇到正在答題的 eca 回 SessionBad busy answering」「agents_ctl add 掛的 agent 不在 subagent ls」「agent_def new 複製定義時 README 的相對連結全斷」「aos-lock：名牌只記一個身分」「glob 掃兩層也照整棵樹走」；fsm 範本「eca-claude 範本沒關 Claude Code 的自動記憶」「fsm 隊員沒有 user_send／user_verify」；kernel與額度「kernel_hold 通知分不出工人要移除自己」，和頂層交代的「提示快取命中率低：llm kernel 沒送固定的 session id」（已解 7ce38e7cf，活樹要換樹後由頂層在 llm-gpt 的 sol-high 包開 session_key）；信件與溝通「信會在路上交錯」（跟「回答對不到是回哪封信」相近，但改的地方和負責的線不同，分開記、互標相關；`mailbox_send` 已有 in_reply_to）；知識庫與文件「gate 頁沒寫 triage 只收 home_roots 底下的路徑」。除了 session id 那條已解，其餘查過程式都還沒改，未處理。稿開頭列的三件（gate 逾時、subagent 忘掉工人、dontAsk 下 Read 被拒）第十一批已收，跳過；「硬規則別寫死 never commit」那件建議改 aos-teams/06，但 06 是本 repo 的派工文件、不是 aos 本身，06 也沒寫死 never commit，不收進這裡，做法收進 wf/public team-patterns。頂層交代的另一件：fsm 範本「蒐集用 sol 的工具包寫不了純文字檔」的建議 1 補上後續 c2eced25c（ws_write 也擋鄰居 stack 與任何 .stack 夾），狀態不變。第十三批（11-14，各線與四位部長收尾時寫的 `wf/temp/<名>/wrapup-1114/建議.md` 共 19 份，加 ok-devt 2 份 aos-advice 稿）新增 43 條、併進舊條 9 條；多線提同一件的合成一條、列全部提出者。新增分在：daemon與行程 3（部長沒有被允許的唯讀查法、fork 層命令列跟主 daemon 一樣、eca 寫出 result 後 CLI 不退出）；信件與溝通 6（sent_at 是 UTC、不能一次寄多人、長回合裡收不到新信〔live_mail 已做一部分〕、授權回信沒有機器可讀的範圍、reply_to 是相對路徑、各元件寫死 letter.json）；kernel與額度 5（看不出在排腦的隊還是卡住、掛 proc 的寄信人不會晚點再試、帳本看不出快取命中率、live 測試在乾淨複本跑不了、Claude 用量沒有入口〔已排入 ok-llmk2〕）；fsm範本 6（system.txt 沒給知識庫路徑、eca-claude 預設權限全開〔這兩條頂層 11-14 裁定今天不改、明天併一題問使用者〕、brain_failed 兩種身的欄不同、kernel_dir 沒去空白、self_tools 不能加一整包、eca 的 cli.json 不能只替一隻覆寫）；指令與工具 12（生效方式沒處查、clock 不能略過下一次、`--rm` 被權限模式擋、claims 不能篩、check_anchors 掃進別線草稿、subagent 的 system set 整份取代、含空白的參數錯誤訊息誤導、aos-daemon-ctl 的 rm 說明、沒有換檔共用工具、advice 小修撞單、scan 的 0 files、history set 不保留附加鍵）；知識庫與文件 8（stack 檔案佈局、Claude 子 agent 沒有一頁講、預設工具包散在好幾頁、8000 bytes 上限、表與事件的欄位清單、複本落後不自知、鍵一行一整段、hook 的 AOS_STACK 是小格）；安全 3（exec.json 重寫回 644、aos-share check 對 ACL 誤報、aos-share reset 沒防呆）。併進舊條的 9 條：「eca-claude 在 dontAsk 下沒放行 Read／Glob／Grep」（加 head-comm、head-core、ok-kmsg）、「信會在路上交錯」（加 head-core、head-tools、ok-kb）、「`#` 與 keep」（加 head-front）、「子 agent 不知道是誰生了它」（加 ok-devt；狀態補第 1 期 bcaf76823 已進 main）、「sol 的可寫範圍寫在兩份清單」（加 ok-fsm 的沙箱 `$env`）、「gate 站掛在主人的 on_clock」（加 ok-kf 的程式位置與三個方案）、「claim 一個資料夾」（加 ok-llmk2）、「sol 只回會照做就停」（加 ok-view）、「漏設 AOS_LLM_KERNEL」（加 ok-view；repo 已解、活樹待換樹）。稿裡只指回舊稿的（ok-kf 第 1、3 則，ok-limits 第 2 則，ok-llmk2 前 3 則，ok-onboard 第 1 則，各稿開頭的「已投過」清單）不重收。沒收的兩件：head-tools「換樹的 pin 不能跳過單一 commit」只要求改 aos-teams/06 和部長任務書，是本 repo 的派工文件、不是 aos 本身；ok-kb `to-top/06`（06 第 9 行 `proto8/py` 兩邊都列、活樹在哪台、「codex 也一樣」）要改的是 AGENTS.md、06、gotchas/05，同樣是頂層的字，不屬 advices 也不屬 public，它查到的事實引在指令與工具「生效方式沒處查」那條。各條查過程式的寫在狀態欄的「整理時查」，沒核的照實標。主題由整理的子 agent 提，頂層定。

| 主題檔 | 收什麼 | 未處理 | 已排入 | 已解 |
|---|---|---|---|---|
| [daemon與行程](daemon與行程.md) | daemon、aos-loop、daemon 表、--limits、認行程、帶 envs 的 add 掛法、部長唯讀看自己的線、fork 層命令列、eca 寫出 result 後 CLI 不退出 | 6 | 1 | 2 |
| [信件與溝通](信件與溝通.md) | mailbox、aos-post 信件格式（含 reply_to、letter.json 路徑）、專區信（含授權範圍）、say／ask／listen、回答配對信名、信件交錯、信的時區、一次寄多人、長回合裡收信 | 9 | 2 | 3 |
| [kernel與額度](kernel與額度.md) | llm kernel、腦額度、找 kernel、kernel hook、kernel_gate（hold、站跟主人的鐘、hold 通知）、只設 AOS_KERNEL 的 subagent、提示快取與 session id、排腦的隊看不看得出來、帳本與 Claude 用量、kernel_llm 的 live 測試 | 6 | 2 | 6 |
| [fsm範本](fsm範本.md) | agent-fsm 範本、工具包（含 user 包、加一整包）、system 文字（含知識庫路徑）、guard 與可寫範圍、before_tool 擋下的標法、wait 與冷卻、goal、sol 第一輪只說不做、llm_settings 註解、brain_failed 事件兩種身、eca-claude 範本（goal 提醒、dontAsk 放行、預設權限、自動記憶、cli.json 覆寫） | 14 | 2 | 5 |
| [指令與工具](指令與工具.md) | aos-agent（含 ctl stop／rm 碰到答題中、agents_ctl 與 subagent 名冊、history set）、aos-view、建置、wf/tools（commit-request 的 claim／claims／--rm／錯誤訊息、check_anchors、換檔工具、生效方式）、工具說明（tooldef）、工具錯誤代號、--help 字樣（含 aos-daemon-ctl rm）、路徑裡的 `#` 與 keep、agent_def 複製、aos-lock、glob 掃描上限、clock_register、subagent 的 system set、wf/public/tools 的 scan | 23 | 1 | 3 |
| [知識庫與文件](知識庫與文件.md) | 知識庫頁、元件 docs 跟程式對不上或該寫沒寫（gate 的 home_roots、stack 檔案佈局、表與 hook 事件的欄位、hook 的 AOS_STACK、Claude 子 agent）、知識頁大小上限與鍵的寫法、複本落後 repo | 9 | 0 | 1 |
| [安全](安全.md) | 密鑰外洩面、proc 環境繼承、暫存檔與小窗檔權限、aos-share | 3 | 1 | 0 |

合計 99 條：未處理 69、已排入 9、已解 21（11-15 claude-b7 逐檔數「狀態：」行重算：daemon與行程的 B7 改已解、「子 agent 不知道是誰生了它」改未處理（部分已解）；之前第十三批也是這樣重算；「部分已做／部分已解」的仍算未處理；「安全」那條只有一部分排入，照使用者指定的狀態算已排入）。第一批實際入庫 17 條，上面「16 條」是當時的筆誤，照各檔實數。
