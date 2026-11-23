eca-aos-kb 的工作筆記：使用者交代的知識庫（proto8/knowledge/）寫法規矩，與做過之後學到、下次照做的步驟；接手的人照這份做。

← [我的地盤](README.md)｜[地盤規矩](../../README.md)

# 使用者交代的規矩（逐字原話）

1. **不寫日期註記，量測數字預設刪**（2026-11-22）：「知識庫那邊，這種"日期註記"要刪掉，量測數字，除非很常用很重要的也都刪掉。」
   - 日期註記＝講「什麼時候改的、以前是怎樣」的句子或子句：`Measured 2026-…`、`On 2026-… X was cut`、`since 2026-…`、`before this was fixed`、`in this batch`、docs 裡的「11-21 起」「（11-21）」「原本……也換成 md 了」、`the user chose on 11-19`。
   - 刪法：句子改成只講現況；整句只在講歷史就整句拿掉。拿掉註記後若句子跟現況對不上（例：docs/01 的樹狀圖靠「11-21 起是 md」補說明），順手改成現在的樣子。
   - 不算註記、不動：範例值裡的日期（`"2026-11-13 09:00"`、ls 範例輸出的時間戳）、格式說明、記版本的機制說明、「not yet」「for now」這種講現在還沒有的功能。
   - 量測數字＝某次量到多少（幾支約幾字、幾 token）。只留 agent 做決定時常用又重要的，留下的不帶日期、而且要重量確定現在還對；量不了就刪。上限、門檻、預設值（3,000 字、35%、max_subagents 4）不是量測數字，不動。
2. **原話是例外**（2026-11-22）：「原話和原話的日期可以留。」
   - 「使用者 11-13「……」」這種引了原話的出處，連日期一起留著（docs/ 約 17 處、knowledge/wf/ 約 16 處都是這種）。
   - 沒有原話、只有「使用者某日決定」的，算日期註記，照第 1 條拿掉。
3. **改的句子不標記；拿不準的補上**（2026-11-22）：「改的句子不用標那個，這種東西都刪掉。拿不準的都補上。」
   - 改過的句子不加「since 2026-11-22」「no longer」「used to」這類話，只寫現況。
   - 回報時列成「拿不準」的缺漏，下一次就補上，不要一直留著。
4. **中文映照版不碰**（2026-11-22）：「kb-zn不用管」——`proto8/knowledge-zh-md/` 不讀、不改、不跟著同步。
5. **知識庫使用感想的改法照我的推薦定**（2026-11-22）：「我人還在外面玩，總之先按推薦做」。依據是 [proposals/kb-feedback-1122.md](proposals/kb-feedback-1122.md)，裁定如下：
   - 頁太密＝1c：每頁開頭寫三到五行重點，內文一行只講一件事；不一次改完，用到哪頁才改哪頁。
   - fsm／eca 交錯＝先做 2c，寫一頁 `aos/eca_reading.md`，告訴 eca 該讀哪些、哪些可以跳過；2a 跟著題 1 一起改，同一個主題裡先寫 eca 那行、再寫 agent-fsm 那行，兩邊都適用的放最後。
   - 排錯少＝3c：寫一頁 `aos/troubleshooting.md`，每條寫症狀 → 原因 → 怎麼查，只寫查證過的；誰查出新的故障，就交給 eca-aos-kb 補一條（這條規矩寫在 wf/，由 eca-aos 加）。
   - echo $AOS_HOME＝4c：不改。

# 下次照做

## 範本改了，知識庫跟上

1. `git show --stat <commit>`，再看 `templates/eca-claude`、`templates/eca-pi` 的 `tools.json`、`cli.json` diff；包的內容看 `proto8/py/packs/<包>.json`。
2. grep `proto8/knowledge/`（aos/、wf/、docs/、根目錄的頁）找受影響的工具名、包名、支數；也要搜「eca has」「stock template」「stock agent-fsm」這類講「誰有這支工具」的句子。
3. 每個「X 有某工具」的句子都對照範本的 `tools.json` 確認。eca-claude 和 eca-pi 的 `tools.json` 用 `diff` 比，不要照 README 的說法。
4. 不在範本裡的工具，寫法統一：「no stock template has X (agent-fsm or eca): add it first with `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/X"}}`」。路徑先在 `proto8/lib/` 確認存在：self_hook、clock_register、agent_def、tools_def 在 `/lib/tools/agent/`，jsonx_* 在 `/lib/tools/aos/`。
5. 寫到 eca 的 skills、外掛、settings 來源的地方（aos/body.md 的 CLI 工具清單、aos/cli/eca.md 的 settings 段、aos/definition.md 的 cli.json 欄位），範本那邊還在改的話，先只回報位置，等它交件。

## packs.md 的每包字數表

- 整個知識庫只留這一份量測數字：agent 靠它判斷「加這包划不划算」。kits.md 不另外寫數字，指向 `aos/packs.md#/Tool packs`。
- 不寫量測日期，也不寫某個範本的總字數。
- 工具說明有改動就重量：`python3 -I wf/ws/eca-aos/eca-aos-kb/measure_packs.py $AOS_HOME`（家機 `/home/lorkhan/repo/aos/proto8`、公司 WSL `/home/guanyu/repo/aos/proto8`），印出「包 TAB 支數 TAB 字數」，照著換表上的數字。
- core 改了 `_tooldef.json` 的說明（不只加工具）也會動字數：跟上 core 的信時順手量一次，不用等人叫。
- 量之前先確認 `py/` 和 `lib/` 的 `_tooldef.json`、`packs/*.json` 一樣（`cmp`），不一樣就是還沒跑 install.py，回報，不要自己跑。

## 交件

- `wf/tools/commit-request claim --line <線名> 檔…`，然後 `submit --line <線名> --files 檔… --msg-file 訊息檔`。commit 訊息第二段附使用者原話，訊息檔放 `~/.aos/scratch/<線名>/`（repo 外）。
- 中文檔名：不要直接拿 `git diff --name-only` 的輸出，git 會把中文檔名轉成 `"\346…"` 這種跳脫字串，claim 會拿到錯的路徑、submit 也會失敗（`does not exist`）。改用 `git -c core.quotePath=false diff --name-only`，或手寫路徑。拿錯的 claim 用 `commit-request release --line <線名> <同樣那串路徑>` 放掉（`release --all` 在這裡被權限擋了）。
- 交之前 `git diff -- 檔` 確認只有自己的字；不 push，不刪檔。

## 前端（aos-user）改了，知識庫跟上

- 要跟上的頁：知識庫 `aos/user_zone.md`（含 `aos/_index.json` 那項的一句話），和 `wf/public/user-zone-mail.md`（中文那份）。事實對 `proto8/frontend/aos-user/zone.py` 與它的 README、`aos-user --help`；只讀的 `aos-user door`、`aos-user announce`（不帶字）可以跑。
- 沒 shell 的身走 aos 工具 `user_send`（`proto8/py/tools/agent/user_send/_entry`）：它把 `AOS_STACK` 設成叫它的那隻、再呼叫 `aos-user send`，所以 aos-user 的改動多半也套到它；它的 `_tooldef.json` 說明歸核心程式位子，寫錯只回報。
- 樣板 `DOOR` 改了，真專區的 `door.json` 不會跟著變（`init` 不蓋已有的檔）：知識庫照程式寫，不要照 `aos-user door` 印出的 rules 抄；對不上就回報。
- 不要寫成全景頁（`aos-frontend`）能做專區網頁才有的事（例：逐題留言），也不要寫成 agent 會自動察覺使用者不在：公告只有「去看就看得到」。
- 新加一段就開新標題（例 `# The announcement`），舊標題不改名，別頁的連結不會斷；開頭的條列補一行指過去。

## 要先問方向的工作：只出提案

- progress 條目或任務書寫「改之前先問使用者」，就只出提案，不改 `proto8/knowledge/`。提案放 `proposals/`，示範稿放 `drafts/`，兩者都在我的地盤裡（換台後還要給使用者看，所以不放 `temp/`）。
- 每題寫法：實例（頁、行）、2～3 種改法，每種附好處、代價、要改幾頁，最後給推薦和理由。頁數用 `find`、`grep -l` 實際數出來寫，不要估。
- 使用者定了「邊用邊建」（2026-11-22：「這些都只是初步的調查規劃……一邊用一邊去把它建起來」），所以每題都給一個「用到哪頁改哪頁」的選項。
- 示範稿只用原頁已有的事實，不加新事實；原頁的標題（錨點）保留，因為別頁有連過去（改標題之前先 `grep -rn "頁.md#/"`）。
- 想寫進知識庫但還沒查證的事（例：eca 的 Read 讀不到工作區以外的檔），在提案裡標「待查證」，不寫進知識庫。

## 改一頁時（照第 5 條）

- 開頭一句頁簡介，接著 `Key points:` 三到五行，再接 `More:` 指向各節；內文一行只講一件事。
- 同一個主題裡，先寫 eca 那行、再寫 agent-fsm 那行，兩邊都適用的放最後。
- 標題不改名：改之前先 `grep -rn "aos/<頁>.md#/"`，確認哪些地方連過來。
- 改了某頁的事實，要回頭看 `aos/eca_reading.md`（eca 該讀哪些）和 `aos/troubleshooting.md` 有沒有寫到，有就一起改。
- troubleshooting 的新條目：先在程式或知識庫既有的頁查證，查不了的不寫。條目格式照該頁已有的寫。

## 掃日期註記，不要漏

- `grep` 的結果太長時，會被截斷在一行的前段，句尾的「before this was fixed」就看不到了。c7bc08dae 因此漏掉了 `aos/body.md` 第 19 行。搜尋時用 `grep -o '.{0,40}關鍵字.{0,40}'`，只印關鍵字周圍，逐筆看完。

## 對事實時的坑（2026-11-23 第一件掛 daemon 的工作學到的）

- **信封 sender 不只一種**：aos-post 本身用 `aos::identity()`（`$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ cwd，`cpp/aos-util/src/proc.cpp`）；aos-mailbox 與 mailbox_* 工具先清掉 `AOS_WS`、設 `AOS_STACK`（`py/aos/apps/mailbox/__init__.py` 的 `post`），所以是 stack；腦請求走 `stack_identity()`（`cpp/aos-llm/src/send/send.cpp`）＝stack；`aos-agent ctl`、`aos-daemon-ctl` 走 `py/aos/ws.py run_post`、不動環境＝`$AOS_WS` 優先。寫「sender 是誰」先分是哪條路寄的。
- **任務書的草稿要對**：負責人給的句子是草稿，每句對過程式或範本才寫；草稿沒提到但同一句有別的錯（例：kernel.md 同一列的 sender）一起改。
- **`.aos-source.json` 只有 `archive/` 裡的程式寫**（`archive/aos-home/copy_tree.py`、`archive/tree-swap/`）；`install.py` 不寫。`$AOS_HOME` 通常就是 repo 的 proto8，版本＝git HEAD 加未 commit 的改動。
- 範本 README 有掛法時，知識庫 `aos/cli/parts/daemon.md` 那類「怎麼起」的頁補一行指到範本，細節留在範本 README。
- 程式改了還沒 install.py：知識庫照 `py/` 寫；troubleshooting 的「怎麼查」寫成看 `$AOS_HOME/lib/` 裡實作的一行 grep，裝舊版的人對得上（例：`grep -n 'strict=False' …/llm_http/responses_api.py`）。先 `diff py/… lib/…` 看這台裝了沒；install.py 抄檔保留原檔 mtime，要看時間就看 ctime（`stat -c %z`），不要看 mtime。
- 腦的 pack 怎麼送：`"api": "responses"` 的 pack（start-api 的 gpt 那四個）由 `endpoints/litellm` 叫 `lib/tools/base/llm_http`；換形狀的程式在 `responses_api.py`。
- 新開一頁：照「改一頁時」的格式寫；做法以範本 README 為正本，知識庫只寫大綱並指過去。md 錨點先用 `json_ls` 看真正的路徑（範本 README 的 `## How to use` 在 `# orgs` 底下，是 `#/orgs/How to use`）。`_index.json` 用 json_add 加一列，再用 `index_view` 看得到。eca 用得上的頁，`aos/eca_reading.md` 也加一行。
- templates/ 會重新分層（2026-11-24 起，kits 搬進 agents/）：`aos/orgs.md` 只寫死 `templates/orgs/…`，別的範本指 `templates/README.md`；`aos/kits.md` 還寫著 `templates/kits/`，搬的時候要對。
- 範本、程式裡同樣說得比事實強的句子（例：`templates/kits/gather/tools.json` 的 description）只回報，不改。

## 範圍與回報

- 只改 `proto8/knowledge/`。發現範本、程式、`wf/` 寫錯（例：py/packs/README.md 寫錯 eca-pi 掛哪幾包）就回報 eca-aos，不自己改。
- 不在活 daemon 上下指令；aos 工具只用自己的 self_*。
- 回報寫繁體中文，先寫結論：commit 雜湊、改了哪頁哪句、拿不準沒改的、替使用者做的選擇（逐條列）。
- 知識庫存檔就生效：一頁一次寫完整，寫英文、短句、一句一件事，只寫核對過的事。
