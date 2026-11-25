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

# 現況（2026-11-24 收尾，壓縮前寫）

- 手上沒有進行中的信；eca-aos 寄來的都回了 DONE（最後一封 349a923c3：dev-env/03 的 AOS_DAEMON 改指根、家機之後要搬）。
- 11-24 線 `eca-aos-kb-1124` 交過：6f7f32352、c5016efd2、56de0d0f2、fe1c2e93f、5ab0b0e8a、2a9161dd0、46e0f0e1a、23e65da3a、cd9d62963、47b17122c、fa94b7874、349a923c3。
- ~~還開著：家機 stack 搬完後改文件~~ → 家機 11-24 晚做完，見下面「家機 11-24 晚」。
- core 說之後會改的：沒有還欠的句子（aos-llm ls 整台行、leftovers、ctl ls --deep 都已寫進知識庫）。
- 11-24 下午：eca 別用背景 Bash 排定時，寫在 `aos/clock.md` 的 which way 段尾、`aos/eca_reading.md` 的 clock 那行、`aos/troubleshooting.md` 的 Hooks and timers 段。原因照 core 實測（report-1124-bgmail.md 第 7 節）：`claude -p` 等背景任務結束才退出，回答取最後一個 result。
  - **待更新**：如果程式改成讀到第一個 result 就收（報告修法 7／8，eca-aos 在問使用者），這三處都要改。
  - 只寫了預設那條路。`"live_mail": true` 會一直開著 stdin，回答取每個 result；這種情況下信進不進得來沒驗，所以沒寫。互動畫面開著時也沒驗，也沒寫。
- 11-25 線 `eca-aos-kb-1125`（eca-main-obs-1124 知識庫那半）：五項 11-24 都已寫過。這次只做了三件：
  - 補 packs.md 的 board_ls `scope: deep`；
  - 把 llm_kernel.md「template kernels」改成只指主 kernel 範本（llm-team 是 slots 4、沒有 reserved）；
  - dev-env/03 錯誤表下、daemon-root README 子項 stack 那句後面，各補一段指向知識庫。
  - 範本的 slots／reserved 數字如果再改，llm_kernel.md 那句要跟著對。
- 11-25 線 `eca-aos-kb-1125b`（aos-ns，使用者 11-25「要」）：在名詞表加了一列「std（庫）」。
  - 名詞表只有一份：`docs/CONCEPTS/附錄1-名詞/03-aos-exec到最小實作.md`，加在「標準庫」那列之後；`附錄1-名詞.md` 的分檔目錄也補了詞。知識庫沒有名詞表。
  - std 算 C-74 哪一層照使用者「先留著」，沒寫死。
  - 如果之後 std 搬進 `lib/std/`（03 的第二刀，還沒排），那列的「放哪」要改。
- 我的信箱回信地址：eca-aos 在 `/home/guanyu/aos-home/.stack/procs/repo-aos/procs/eca-aos/mailbox`（stack 11-24 搬家後）。

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
- 信裡的「agent 通常怎樣」先對範本（例：「agent 不帶 priority」對過 templates 沒有一份設 priority，才寫成「the stock agent templates send no priority」）。
- 環境的坑（WSL 網路、WSL_INTEROP）出處是 `wf/workflows/dev-env` 的那條（使用者實測過），知識庫寫成 troubleshooting 一條，不寫哪台機器。
- 不要對 `/` 跑 `find`（WSL 會掃到 /mnt/c，跑不完）；找 stack 先看 `~/repo/aos/.stack`、`~/aos-home`。
- 負責人准了才改 `wf/` 文件（例：11-24 stack 搬家）：只換路徑事實，兩台分開寫（公司搬了、家機沒搬）；家機要不要跟、殼設定檔的值這類沒定的不替使用者選，列在回報裡。改標題前先 grep 有沒有連到那個錨點。
- 公司 WSL 11-24 起 stack 全在 `~/aos-home/.stack`（repo 那棵在 `procs/repo-aos`，`~/repo/aos/.stack` 是 symlink）；我的 stack 也在那底下。
- 範本、程式裡同樣說得比事實強的句子（例：`templates/kits/gather/tools.json` 的 description）只回報，不改。
- **隔離只承諾防失誤**（使用者 11-23 晚「甲，先只防失誤」「可以」）：拿掉工具、ws、kits、aos-sandbox 是防不小心越界、讓越界看得到，不抗刻意繞過。正本是 `aos/rules.md` 的 `What does not enforce these rules` 段（線 kb-guard-level-1123 補的那段），`aos/kits.md` 的「Why a kit cuts tools」改成不說關得住、指過去；別頁寫限制時也不寫成關得住。

## 範圍與回報

- 只改 `proto8/knowledge/`。發現範本、程式、`wf/` 寫錯（例：py/packs/README.md 寫錯 eca-pi 掛哪幾包）就回報 eca-aos，不自己改。
- 不在活 daemon 上下指令；aos 工具只用自己的 self_*。
- 回報寫繁體中文，先寫結論：commit 雜湊、改了哪頁哪句、拿不準沒改的、替使用者做的選擇（逐條列）。
- 知識庫存檔就生效：一頁一次寫完整，寫英文、短句、一句一件事，只寫核對過的事。

## 家機 2026-11-24 晚：home-docs-1124（main 派）

- 交了 `4936939e5`（12 檔）：repo 那棵的 stack 兩台都在 `~/aos-home/.stack/procs/repo-aos`、家機負責人是 `main`（底下 kb／templates／core）。改了 AGENTS.md、wf/tree、dev-env.md、dev-env/01、03、aos-teams.md（第 3、5 段）、06、07、kits site.txt、gather/system.txt、wf/public 活樹旁邊、行程與環境。03「家機照做」那節沒改標題（wf/tree 連過去），開頭改成「家機已做完，這節留當紀錄」。
- 家機查到的事實（只讀）：`~/aos-home` 只剩 `root/`、`llm/`、`.stack/`；`.llm-stack`、`~/aos-home.old-1122/` 都不在；根表 `_clock`、`_sweeper`、`llm`、`repo-aos`、`mod_skyrim`、`repo-vc`、`narr-amber`；repo-aos 表 `_sweeper`、`main`、三個位子；`.bak-trisplit-1124` 用 `find -maxdepth 4` 沒找到。
- **回報給 main、沒改的**：家機的 `repo-aos` 那列定義是 `proto8/templates/daemons/daemon-sub`（cwd 也在那裡），不是文件寫的 `wf/tree/root`；那列的 `as_written` 也沒有 `envs`。wf/tree、03「第一次」那行都還寫 `wf/tree/root`，要不要改等 main。03 常見錯誤表「`.stack` 整個不見了／git clean -fdx」那列已經不適用（stack 不在 repo 裡），沒刪。
- aos-teams 第 49 行「現成 eca 範本只掛到 agent_def」改成照知識庫：現成範本都不帶 `subagent` 包也不帶 def 包（對過 `templates/agents/*/tools*.json` 與 `lib/packs/`）。

- 續（main 轉使用者「好，都如你所說」）：wf/tree/README 第 7 行、dev-env/03「第一次」各註一句「家機那列掛範本 daemon-sub，設定同 wf/tree/root、只差說明文字」（對過：daemon.json 去掉 description 相同、.env 都只有 `AOS_HOME=${AOS_HOME}`、_entry 同 argv）；刪 03 常見錯誤表「.stack 整個不見了」那列（表列沒有錨點，沒人連）；`~/aos-home.old-1122` 不碰清單照舊。還沒改、已回報：aos-teams.md 第 64 行「.stack 被 .gitignore 忽略，git clean -fdx 會連活樹一起刪」也已不適用。
- 續二（使用者「可以啊」，main 轉）：aos-teams.md 第 64 行、06 第 7 條「別跑 git stash／reset --hard／checkout -- .／clean -fdx」的理由換成現在成立的：前三個弄掉別線沒交的改動；clean -fdx 刪被忽略的 temp/ 與 install.py 裝的 proto8/bin/、proto8/lib/（`git check-ignore -v` 對過：.gitignore 的 `bin/`、`/proto8/lib/`、`temp/`）。規矩卡第 7 條沒寫理由、AGENTS.md 沒提，沒改。`.gitignore` 第 36～38 行講 `/.stack/`、`_stack` 的註解是程式區的事，只回報。

## 家機 2026-11-24 晚：home-listen-1124 知識庫跟上（eca-aos-core 來信，main 准）

- 對過 aa8bd9cef、bc8938198、255d6da30（`cmp` py/ 與 lib/ 都一樣＝已裝）。改：`aos/cli/mcp.md` 開頭補 notifications/cancelled、新標題 `# Calls at the same time`（五行）；`aos/cli/talk_settings.md` 範例加一行、`--mailbox DIR` 一段；`aos/agents/subagent.md` 兩條（用信回也結束等待、eca 等著時照樣能叫別的工具）；`aos/me.md` 的 stack 清單加 `observed.jsonl`。
- 核對時抓到 core 草稿沒講的：observed.jsonl 不只 think 列，還有 `compact` 列（wait.py）與 `tool` 列（act.py，欄位 name、code、elapsed_ms、in/out_bytes）；`--mailbox` 不跟 `--last`／`--follow`、空字串＝ArgumentsBad；subagent 帶 `"last"` 時不帶 --mailbox。「等著時能叫別的工具」只寫 eca（aos-mcp 那條路），agent-fsm 沒驗。
- 第 5 件（docs/NORMS N-43 續 第 10 行的種類表少 `listen`）不在範圍，轉給 main。
- 續（main 准）：docs/NORMS N-43 續 第 10 行種類表加 `listen`（照 py/aos/flags.py NOTE_KINDS，只加名字）。
