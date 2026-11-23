頂層 agent `eca-aos` 自己的筆記：正在做什麼、還開著什麼、決定了什麼；壓縮後先讀這份。

# eca-aos 筆記

← [地盤 README](README.md)｜規矩：[wf/ws](../README.md)、[AGENTS.md](../../../AGENTS.md)

## 我是誰、在哪

- `eca-aos`：範本 `proto8/templates/eca-claude`，工作區 `~/repo/aos`，stack `~/repo/aos/.stack/procs/eca-aos`，掛在子 daemon `repo-aos` 底下；用第二帳號（`CLAUDE_CONFIG_DIR=~/.claude-alt`）。
- 這台是公司 WSL（Ubuntu）。樹：根 `~/aos-home/.stack`（`_clock`、`_sweeper`、`llm`、`repo-aos`、`eca_main`），底下 `~/repo/aos/.stack`（`_clock`、`_sweeper`、`eca-aos`）。
- aos 工具只有 json、index、mailbox、math、peek、self_state、self_tools 這幾包；檔案與指令用 Claude Code 自己的。
- 這台沒有 `~/.aos/user/`（使用者專區沒建）：要問使用者的題目放 `wf/user`（使用者 11-23「沒有~/.aos/user，那就放wf/user。」，已抄進 `common/user.md` 與規矩卡）。
- 根 daemon 上的 `eca_main`（工作區 `~`）、`mine_arena`（子 daemon，工作區 `/mnt/c/code/mine/arena_cheater`，底下 agent `main`）是使用者自己開的，不是我的東西，不碰。

## 2026-11-23 上午（第一個 session）

- 使用者第一句：「嗨，請先大致掌握aos體系。」→ 只讀、沒動任何東西。
- 讀過：AGENTS.md、知識庫 `_description`／`world`／`body`／`rules`／`eca_reading`／`cli/eca`／`user_zone`、`common/user.md`、規矩卡、aos-teams 短卡、WORKFLOWS、HANDOFF、proto8/README、`wf/ws` 與 `wf/user` 的 README、`wf/user/待答-1122.md`、progress 的標題。
- 三軸：信箱空、`wf/inbox` 空；progress 31 條 open（多半「等使用者」）；`wf/user` 沒有沒交的改動，讀到 `d5e9a39e4`（記在 `user-seen.json`）。
- 發現：本地 `origin/main` 跟 HEAD 同一個 commit（`d5e9a39e4`），HANDOFF 寫的「都沒 push」看來已經過時（沒 fetch 驗過遠端）。

## 2026-11-23 上午：滾輪調查

- 使用者：「我剛剛用aos-agent新開了一個claude eca 互動畫面，然後滑鼠滾輪又不能用了。」「那個eca的位置是在~/aos-home/.stack/proc/mine_arean/proc/main」（實際路徑 `~/aos-home/.stack/procs/mine_arena/procs/main`）。
- 派了一隻 opus 的 Claude 子 agent 做只讀調查（查舊紀錄、起 tmux 的程式、活的 tmux 選項）；派的時候還不知道是 `mine_arena/main`，任務書寫的是「多半是 eca_main，自己確認」。回來後要對它有沒有查到對的那個畫面。

- **結果（12:15 回來，關鍵幾項我自己對過）**：不是 tmux 的問題。範本 `proto8/templates/eca-claude/cli.json` 的 flags 從 11-22 的 `9d738cc77` 起帶 `--setting-sources project,local`，claude 不讀 `~/.claude/settings.json`；主帳號那份的 `"tui": "fullscreen"` 被跳過，主帳號預設是舊式畫法，不跟終端要滑鼠，滾輪沒人接。第二帳號 `~/.claude-alt` 沒設也是全螢幕（原因不明，推測是帳號層級的開關）。`mine_arena/main` 11:50 用主帳號開（壞），11:58 用第二帳號重開（好）；根 daemon 那棵不帶 `CLAUDE_CONFIG_DIR`，所以不特別帶就是主帳號。
- 修法選項：① 範本 `cli.json` 的 `settings` 加 `"tui": "fullscreen"`（推薦；子 agent 在暫存 tmux 用 `--settings '{"tui":"fullscreen"}'` 驗過會變全螢幕、能捲）；② `cli_screen.py` 的 `TMUX_CONF` 加 `set -g mouse on`（要 `install.py`，會搶滑鼠選字，沒實測）；③ 都做。使用者 11-23 選「1」：三份 `cli.json`（`eca-claude`、`eca-claude-alt`、`start-eca/agents/ann`）的 `settings` 加了 `"tui": "fullscreen"`，`test_cli_settings.py` 放行這一鍵，兩份 README 與 `templates/docs/01-eca-claude.md` 補了說明；在乾淨複本跑 `test_cli_settings`、`test_eca_claude_alt`、`test_start` 都過，`claude -p` 帶這項照常回答。**還沒在真的畫面驗**：要使用者用主帳號重開一個畫面試滾輪。
- 沒找到「上次」的紀錄（repo、git log、兩個帳號的對話都搜過）。
- 子 agent 留下的：`~/.claude/.claude.json`（998 bytes，12:04，實驗時帶 `CLAUDE_CONFIG_DIR=~/.claude` 生出來的，平常不會被讀）、`~/.claude/backups/` 一份 84 bytes、兩個帳號 `projects/-home-guanyu-repo-aos/` 可能多幾段短對話；scratch 在 `…/scratchpad/wheel/`。刪不刪要使用者說。
- **痕跡刪了**（使用者 11-23「滾輪可以用了，那幾個痕跡刪掉吧」）：`~/.claude/.claude.json`、那份 84 bytes 的備份、六段實驗對話（主帳號 4、第二帳號 2，在 `projects/-home-guanyu-repo-aos/`）與它們的 `session-env/` 夾。兩份 `history.jsonl` 裡六行 `!seq 1 300` 沒動（活著的畫面一直在寫那兩個檔）。子 agent 說「沒叫模型」不對：六段對話各跑了一小輪模型（讀 AGENTS.md，一段還跑了唯讀的 ls／cat／git status），沒寫任何檔。
- 滾輪：使用者 11-23 回報「滾輪可以用了」，真畫面驗過。

## 2026-11-23 上午：建這台的使用者專區

- 使用者接著說：「然後~/.aos/user看起來還是必要的，開一個claude subagent去弄吧」。
- 派了第二隻 opus 的 Claude 子 agent：照 `aos-user init` 建 `~/.aos/user/`、驗 `door`、不寄測試信進真專區；`aos-user tick` 的 timer、全景頁、殼設定檔只查不做，回來報選項。只准寫 `~/.aos/user/` 與 scratch。
- **建好了**（子 agent 回報，我 `ls`、`aos-user door` 對過）：`~/.aos/user/` 在，`aos-user` 在 PATH（`proto8/frontend/bin/aos-user`）。真專區沒收發過信；整條只在假專區跑通。
- 我的 stack 原本沒有 `mailbox/`，`aos-user send` 會報 `MailboxMissing`；已跑 `aos-post init $AOS_STACK/mailbox` 補上。
- **這台要問使用者的題目改回寄專區**（`aos-user send --kind decide`，回信 `aos-user verify`）；`common/user.md` 那句「沒有專區的機器放 wf/user」是通則，照留。
- 沒做、等使用者說：tick 的 timer（子 agent 推薦先不裝，跟家機 11-22 選的一樣；這台沒有 `notify-send`）；全景頁沒在跑（他要看題目得自己起 `AOS_DAEMON=~/repo/aos/.stack aos-frontend serve`，或用 `aos-user ls`／`show N`／`answer N q1:a`）。
- 文件漏寫「寄件人自己的 `mailbox/` 要先存在」：`eca-aos-kb` 這台沒掛，沒地方寄，記在 progress `aos-user-home` 第 ④ 件。
- HANDOFF 那句與 progress `aos-user-home` 已更新。

## 還開著的（從 HANDOFF 接的）

1. 使用者要細說「把stack一起隨機器搬遷，不是一個好主意」那塊。
2. 早上「先處理這個，然後我們再來」後面要做的事，他還沒說。
3. progress `company-wsl-1123-verify`（真模型端點、第二帳號沒驗）、`sol-high-pack`。
4. 家機還是舊樣子，pull 之後要照 03-換機「家機照做」。

## 2026-11-23 下午：mine_arena 的 main 來信（已回，信 `01795412174548591287.752207.2015641`）

- 信 `01795411651598235449.693262.1963346`（留底在我 stack 的 `mailbox/archive/`），寄件人 `mine_arena` daemon 上的 `main`（使用者自己開的 eca，專案 `/mnt/c/code/mine/arena_cheater`），回信寄 `/home/guanyu/aos-home/.stack/procs/mine_arena/procs/main/mailbox`、`in_reply_to` 填那封信名。
- 內容：第一輪多 agent（main 加五個 agent-fsm 部門）的回顧。兩個焦點，信上說使用者之後會親自找我討論：① 上層約束下屬現在只靠文字，工具層擋不住（絕對路徑、`self_tools` 自己加回、`tools_def`、`fork`、`subagent`）；② 跨 agent 的資源分配（整個 mine_arena 同時只准一件 Node.js，現在靠 `flock` 自律）。回顧原文在 `/mnt/c/code/mine/arena_cheater/wf/notes/investigations/org-retro-1/`。
- 它問三個事實題（不要我改 aos）：路徑層級的存取限制有沒有、怎麼用；`subagent tools` 拿掉 shell／run_python／self_tools／tools_def 之後下屬還有什麼路拿回能力；跨 agent 的共用配額、排程、租約有沒有。
- 派了一隻 opus 的 Claude 子 agent 只讀查證（讀知識庫加對程式，不起 daemon、不叫模型）。回來後：我對過關鍵幾項 → `mailbox_send` 回 main（status DONE）→ 跟使用者報。兩個焦點是方向題，等使用者來談，我不先提方案。
- **回了（DONE）**，三題的結論（子 agent 讀文件加對程式，我抽對過 write 檔頭、fork 的 ctl add、cgroup.cpp、shell-boxed 範例、aos-lock／aos-sandbox／bwrap 在不在）：
  1. 路徑限制：工具收絕對路徑、kernel 不管路徑、guard hook 的 README 自己寫「審查中，先別拿來限制 agent」；擋得住的只有 `aos-sandbox`（bwrap），一支工具一支工具包，沒有整隻 agent 的開關。這台沒有 s6-softlimit，沙箱設定寫 `mem_mb`／`cpu_s`／`file_mb` 會報 `CommandMissing`。`sub:N` 只是換 uid，自己的 stack 仍可寫。
  2. 拿掉四支工具關不住：任何收絕對路徑的寫入工具都能改自己 stack 的 `tools.json`／`hookeds.json`；`self_hook`、`subagent`、`agents_ctl`、`agent_def`（換名字）、`mailbox_send` 都是路。`fork` 拿不回工具，但分身那列不帶 `--limits`。要關住得一起拿掉 change、delete、json 寫入、jsonx、events、subagent、def、shell 幾包，只留 look、json 讀、mailbox、gadgets 加一支包沙箱的 shell。
  3. 共用配額：`mem_total_mb`、`procs_total` 走 cgroup，寫在 sub-daemon 那列就是底下共用（要 `"cgroup": "on"` 且上層 daemon 用 `systemd-run --user --scope -p Delegate=yes` 起；沒實跑）。「同時只准一件」沒有現成的：kernel 站 `max_running`＋`queue` 只管起 proc；`aos-lock` 跟 flock 一樣是約定。
- 順帶發現、還沒處理：子 agent 說文件寫「公司 WSL 無 systemd」，但這台 systemd user 在跑、有 memory 與 pids 控制器（哪份文件沒記下，要查再 grep）。

## 2026-11-23 下午：開 `wf/org`（工作室組織）

- 使用者（逐字）：「他那邊是我的試驗田。那邊現有的aos體系感覺不錯，你這邊也學他吧，在wf/開一個org，但是你這邊我預期會是小型工作室，所以主力會是eca claude，人手精簡，fsm gpt則會是打雜工。」接著：「然後你也可以開claude subagent fable，去規劃你這邊自己的團隊組織架構」。
- 樣板我自己看過：`/mnt/c/code/mine/arena_cheater/wf/org/`（README：部門表、標準流程、東西放哪裡、agent 形態；每部門一張角色卡四段：職責、讀寫範圍、交接、模型；`letters.md`）與 `wf/aos/`（定義的 system 指向角色卡、不重抄）。
- 派了一隻 fable 的 Claude 子 agent：只准寫 `wf/org/`，交第一版（README 加角色卡）；回覆裡要給要使用者拍板的題（最多 7）、跟現有文件打架的地方（aos-teams、team-model、user.md 的模型分工）。提案要標成提案，不寫成既定事實。
- 回來後我要做：看過稿 → 交件（`wf/org/` 是新夾）→ WORKFLOWS.md 加一列指過去 → 把拍板題帶給使用者（這台有專區了，但全景頁沒起，他人在終端，就當面問）。打架的句子等他定了再改。
- **稿回來了，我讀過六個檔**：`wf/org/README.md`、`places.md`、`lead/`、`kb/`、`templates/`、`chore/` 各一張卡。架構（全是提案）：負責人 `eca-aos` 加兩個專職位子（kb、templates），全是 eca claude，不設部長；位子＝角色卡加地盤筆記，有活才掛、沒掛時派 Claude 子 agent 讀卡與筆記代班；`aos-eca-frontend` 職責沒定、不寫卡；fsm gpt 打雜工用到才掛。使用者後來那兩句（蒐集算打雜、重要施工尤其寫程式用 Claude）fable 自己從我的筆記讀到、已寫進去。`WORKFLOWS.md` 加了一列指到 org。
- **等使用者答的七題**（當面問了，沒寄專區：全景頁沒起）：① 位子常駐還是有活才掛（推薦有活才掛）② 三個既有位子留哪幾個、frontend 要不要定成前端（推薦定、開工才掛）③ `proto8/py`／`cpp` 要不要開位子（推薦不開、按件派）④ 不重要的施工歸誰（推薦寫程式一律 Claude、機械式的可給 fsm gpt）⑤ 蒐集雜活先給 fsm gpt 還是 sonnet（推薦 fsm gpt、端點通之前 sonnet）⑥ 沒部長後誰放行 commit（推薦位子範圍內先交後報）⑦ eca-aos 能不能親手做小件（推薦只限活狀態、抄原話、wf/org）。
- **答完要改的舊文件**（fable 列的 16 條，還沒動）：`aos-teams.md` 第 9、10、11、15、35、52、74 行；`aos-teams/07` 第 13、63～66 行；規矩卡第 29、54、59 行；`user.md`「子 agent 模型」列 11-14 那句移到已被取代、「工作模式」列加指標；`team-model.md` 第 31、43、67、80 行（只動本專案那幾句）；`kits/card.md` 第 13、14 行；`dispatch/README.md` 第 10、78 行；`AGENTS.md` 加指到 org 的一條。
- 打雜工在這台掛得起來前要過四關：真模型端點、`sol-high` 包名、配給包 `.env` 的 `AOS_LLM_KERNEL`、我要先有 `subagent` 與 `agent_def` 工具。
- 使用者接著補（逐字）：「蒐集算打雜，但施工這塊，如果是重要的部分，那確實還是得用claude」，再補「尤其是寫程式」。fable 派出去時還沒有這句：稿子回來要對——蒐集歸 fsm gpt、重要的施工歸 Claude；「不重要的施工歸誰、怎麼分重要不重要」他沒說，別替他定，列成題目。這句已抄進 `common/user.md`「子 agent 模型」那列（還沒交件，等 org 稿一起交）；`aos-teams.md`、規矩卡裡「蒐集和施工用 sol」那幾句等對完再改。

## 2026-11-23 下午：使用者答七題、叫我用專區

- 使用者（逐字）：「都按照推薦。但py/cpp可以開了，這是aos本體程式庫，是重要對象。舊文件可以更新了。公司體制這塊放著，我就是拿來看看，當參考。對了，~/.aos/user好了嗎？可以用一下」。
- 七題結果：① 有活才掛 ② `aos-eca-frontend` 定成 `proto8/frontend/` 的位子、大修開工才掛 ③ **開** py／cpp 的核心程式位子（他改的，不是推薦）④ 寫程式一律 Claude，機械式施工可給 fsm gpt ⑤ 蒐集雜活先 fsm gpt、掛不起來 sonnet 補位 ⑥ 位子範圍內先交後報，跨範圍等先問我 ⑦ 我只親手做活狀態、抄原話進規矩、`wf/org`，其餘照派。公司體制七題：放著當參考，不追。
- 派了兩隻 opus 的 Claude 子 agent（都不 commit，回來我看 diff 再交）：
  - A：`wf/org/` 從提案改成已定，新開 `core/`、`frontend/` 兩張卡，建地盤 `wf/ws/eca-aos/eca-aos-core/`（名字 `eca-aos-core` 是我取的），改 `wf/ws` 兩份 README 與 frontend 地盤 README 第一行。
  - B：改舊文件（`aos-teams.md`、`aos-teams/07`、`03-使用者原話`、規矩卡、`user.md` 與 `user/01`、`team-model.md`、`kits/card.md`、`dispatch/README.md`、`AGENTS.md`）；被取代的使用者原話收進留底，不刪。
- **專區第一封真信**：`01795412855625216943.823276.2083748`（decide，三題：q1 tick 的 timer 裝不裝〔推薦 a 不裝〕、q2 `MailboxMissing` 怎麼補〔推薦 b 改程式讓 send 自己建〕、q3 六行輸入歷史清不清〔推薦 a 不清〕）。`aos-user ls` 看得到。回信會進我的 mailbox，要 `mailbox_read` 後跑 `aos-user verify <留底夾>` 看到 `ok: matches` 才算數。

- **專區整條走通了**：使用者用 `aos-user answer` 回了（q1:a 不裝 timer、q2:b 改程式讓 send 自己建信箱、q3:a 六行不清），回信 `01795413060186315333.845299.2104205`，`aos-user verify` 印 `ok: matches`（reply_id `64c0e59b2a3266ff`）。
- q2:b 派了第三隻 opus（代班前端位子）：改 `proto8/frontend/aos-user` 的 `send`，只在回信地址是預設的自己 stack 的 `mailbox/` 時自動建；先在乾淨複本改好測好再寫回（frontend 存檔活樹就在用）；不 commit。回來要：看 diff、交件、把它給的那一句轉進知識庫 `aos/user_zone.md` 與 `wf/public/user-zone-mail.md`（派代班）、更新 progress `aos-user-home`。
- 使用者問「只能選 abcde 嗎、不能逐題留言嗎」：現在不能逐題寫，`answer` 只收 `id:代號`；可以 `--note`（整封一格）或那題答 `other` 加 `--note`（`zone.py` 的 `parse_answers`）。要不要加「逐題留言」等他說。
- A、B 兩隻回來了，我看過 diff：A 改 `wf/org` 六檔、新開 `core/`、`frontend/` 兩張卡與地盤 `eca-aos-core/`、改 `wf/ws` 三份 README；B 改舊文件十個檔（被取代的原話收進 `aos-teams/03` 與 `user/01` 的留底）。我只改了一處：lead 卡「要查的也派一隻唯讀的」改成「一兩下查得到的自己答、要跨檔讀的才派」。
- **沒處理的尾巴**（記進 progress `org-1123`）：規矩卡 9206 bytes 超過 8 KB（改之前就 8919）；`wf/public/` 七個檔、`user/03`、`aos-teams/04` 還寫「部長」；`aos-teams.md` 與 07 檔頭說舊原文在「本夾 `archive/`」但那個夾不在；`AGENTS.md`、`user/01` 各有一條原本就斷的連結；打雜工四關；「有活才掛」每次掛人要不要再問使用者（現在照鐵律 2 每次問）。
