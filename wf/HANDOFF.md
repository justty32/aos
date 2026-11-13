# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-13 20:30 家機頂層（樹外的 Claude Code）交棒給樹裡的 repo-aos

1. **授權與工作方式**：在家機（Manjaro）。使用者開場：「事情盡量交給agent做，普通工作交給opus，簡單工作交給sonnet。agent做事前要讀過wf/規矩，簡單工作除外。晚上十一點睡覺前再push。」；「今天的優先目標是幫我架起aos」；「總之先搭好。後面我要把你這個session關掉，咱們走aos」——**之後的頂層是樹裡的 `repo-aos`**，這個樹外的 session 會關掉。fable 照 user.md「盡量少用」。
2. **push**：23:00 睡前推一次，推之前跟使用者說一聲（數量看 `git log origin/main..main`）。
3. **家機今晚定的**（細節 [aos-home-家機](../proto8/thinking/2026-11/13/aos-home-家機.md)、[日誌](session_logs/2026-11/2026-11-13.md)）：
   - **repo 改放 `~/repo/aos`**（「直接放~/repoaos」「~/repo/aos」）：從舊位置 clone、origin 指 GitHub；舊的 `~/repo/simple_tools/aos`（`simple_tools` 的子模組）使用者說「不用刪」，留著、不再當工作 repo。impls 在新位置全部重 build，`~/.local/bin` 25 條 `aos-*` 與 `.pth` 都指 `~/repo/aos`（舊 `.pth` 改名留著）；全套 69 夾 1599 例全綠（公司機那 4 支既有紅與 gitignore-check 在家機都沒紅，原因沒查）。
   - **樹住 `~/aos-home`、從零搭**，陣容 `eca_main`＋`repo-aos`（都 opus；`repo-aos` 工作區 `~/repo/aos`、定義在 `~/aos-home/agents/repo-aos`）。兩隻會答、互寄信收得到、停樹再起 history 在；存檔 `~/aos-saves/aos-home-1113-home`。**驗完樹停著，起樹由使用者自己下**；指令在 [wait-user/03](wait-user/03-試驗場.md)。沒驗：`aos-agent open`（畫面）；`~/aos-home/ws`、`~/repo/aos` 兩處開畫面前要使用者各開一次 `claude` 按信任。
   - **`.zshrc` 自動 source**（使用者「我想要把它加入我的.zshrc」「要」）：舊的 `export AOS_HOME=…/simple_tools/aos/proto8` 換成 `[[ -z $AOS_STACK && -f ~/aos-home/env.sh ]] && source ~/aos-home/env.sh`（agent 底下的 shell 帶 `AOS_STACK` 就跳過）；三項實測都對。實際檔是 `~/dev/dotfiles/zsh/.zshrc`（那個 repo 有一筆沒 commit 的改動、沒代他 commit），備份 `~/.zshrc.bak-1113-aos-home`。
   - **舊 aos MCP 那行已拿掉**（選項框「搭好就拿掉」）：`~/.claude.json` 裡 `~/repo/simple_tools/aos` 專案的 `mcpServers.aos` 刪了，備份 `~/.claude.json.bak-1113-aos-mcp`；`arcagi` 專案那行與 `~/.cache/aos-mcp-*` 兩格沒動（`aos-mcp-arcagi/tools.json` 有 3 處寫死舊 repo 路徑，舊 repo 留著所以還能用）。
   - 收工待裁頁 W7、W16、W17、W18、W23 已施工（`ff97da487`）；wf-lint 刪掉後的補掃做完。
4. **留著的**：
   - `env.sh` 只清三個 Claude Code 變數；從 Claude Code 的 shell 起樹還會帶 `CLAUDE_CODE_SESSION_ID`、`CLAUDE_CODE_MESSAGING_SOCKET` 等給樹裡的 claude，有沒有影響沒驗、正本要不要改沒定。
   - W16「改口摺疊」那節要不要也補進知識庫（WAIT_USER 01）。
   - `wait-user/03` 裡「家機試驗場 11-12 晚……樹開著」那條可能過時；`~/code/playground` 原樣留著。
   - 線家的代定（`repo-aos` 用 `--tools default`、`--auto-restart`、`--on-busy yield`、`system.txt` 用絕對路徑、不抄 `kernel/`）在 aos-home-家機，可翻案。
5. **接下來**（家機能做的，全貌在下一條第 9 點與 [SESSION-LOG](SESSION-LOG.md)）：各 agent 意見整理成題目、workflows 併入第 3、4 塊（模板 repo 在 GitHub）、`set-def` 與「換定義後提醒在等的信」兩件已裁未施工、kernel 批 7b／11b／12、真腦驗證（批 13、14）。公司機那棵樹要的事回公司機做。

## 2026-11-13 公司 WSL 頂層（repo-aos）收工草稿

（14:00 前後起草，15:40、16:15、16:35 各補一輪；沒有待補的記號了。）

1. **授權與工作方式**：公司 WSL，頂層就是 `~/aos-home` 樹裡的一隻 eca `repo-aos`（工作區 `~/repo/aos`、只有 `main`）。使用者開場：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」；「都可以用fable帶隊」「fable多多的用，因為明天額度重置」（**只限今天**，明天起回到 user.md 的「fable 盡量少用」）；「都可以清、都可以下載。」「反正有需要我判斷的東西就丟桌面」（要他裁的做成頁放 Windows 桌面）。**`eca_main` 派來的普通工作算使用者的授權；push、刪檔這類不可逆或對外的仍要他本人說**（「1.算。」「2.對。」，已寫進 [AGENTS 鐵律 2](../AGENTS.md)）。停樹、起樹只由使用者自己下（15:13 他同意今天那次由 `eca_main` 代）。**這台公司機 17:00 關機，下一個接手的是家機上的 session**（使用者 16:08：「今天五點下班後，我就是關機，回到家用另一台電腦」）。
2. **push**：使用者 16:30 前後「可以push」，推了三次（16:30、16:31 到 `43ec0f4eb`；16:35 到 `8b9a3790d`，線洪做完可否直接推他也說「可以」）；之後的文書 commit 推了沒看 `git status -sb` 的 ahead 數（沒有 ahead＝推了）。push 前做過兩筆隱私修正（線宙 `5a87aa55b`、`233ca54fa`）。
3. **今天定下的**（原話與細節都在 [thinking 11-13](../proto8/thinking/2026-11/13/README.md)、[日誌](session_logs/2026-11/2026-11-13.md)）：
   - 公司 WSL 改住 `~/aos-home`、repo 用 `~/repo/aos`，舊遊樂場與舊 repo 全刪（[aos-home](../proto8/thinking/2026-11/13/aos-home.md)）；主 session 四題定案、家機也要改成樹裡的一隻（[main-session-in-aos](../proto8/thinking/2026-11/13/main-session-in-aos.md)）。
   - 三輪裁定：精選 17 題、第二輪 43 題（38 題有裁）、對話裡的 kernel 七題與 ops、a2a 各題——落在哪見 [裁定落地-1113](../proto8/thinking/2026-11/13/裁定落地-1113.md)（它的兩張待施工表比 git log 舊）；條文線辛、線丑、線午、線寅都改完。大頁 128 題還剩 109 題。
   - **kernel 框架開工**：框架分兩層（骨架只有 hook＋判斷；上限、排隊是蓋在上面的包）、找下一站三段 `next`→`AOS_KERNEL`→`AOS_DAEMON`、照規則分流用 hook、`keep_ordered` 與分流可並用（`route_ordered`）、留著等表態（hold）、agent 當門的工具包 `kernel_gate`（「預設不掛」）、問腦那包用 Python 重寫（假腦）（[開工紀錄](../proto8/thinking/2026-11/13/kernel-framework-開工.md)、[eca-as-kernel](../proto8/thinking/2026-11/13/eca-as-kernel.md)、頁 [架構圖](../proto8/thinking/2026-11/13/kernel-framework-架構圖.html)）。目前沒有等使用者裁的 kernel 題。
   - eca 通知改走 a2a（使用者：aos 先不原生支援 a2a 協議、頂多做中轉；history 記不記寄件人「不用」）（[a2a-施工結果](../proto8/thinking/2026-11/13/a2a-施工結果.md)）；ops-agent 六點（「都按照建議」）做了五件（[ops-fixes-施工結果](../proto8/thinking/2026-11/13/ops-fixes-施工結果.md)）；`eca_main` 來信七項修了四項 bug＋`set-def`（[fixes-施工結果](../proto8/thinking/2026-11/13/fixes-施工結果.md)）；工具印的路徑照叫方 stack 算（[tool-stack-path](../proto8/thinking/2026-11/13/tool-stack-path.md)）；外部 MCP 接真 server（[external-mcp-real-server](../proto8/thinking/2026-11/13/external-mcp-real-server.md)）；repo 的 index 照 11-12 門檻（[index-build](../proto8/thinking/2026-11/13/index-build.md)）。
   - 規矩：在跑著的樹旁邊做事的六條坑、任務書必貼的九條硬規則、派線坑 14～20（[aos-teams/06](workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)、[gotchas/05](workflows/common/gotchas/05-在跑著的樹旁邊做事.md)、[lessons/03](workflows/dispatch/lessons/03-坑14-20.md)）；起因是 10:25 子 agent 用 `pkill` 誤停使用者的樹約 4 分 20 秒（[開工紀錄第十一節](../proto8/thinking/2026-11/13/kernel-framework-開工.md#十一事故子-agent-誤停使用者的樹11-13-1025)）。四條教訓 `eca_main` 已收進樹裡的共用知識庫 `~/aos-home/ws/public/`。
4. **進行中與排定的**（領地在 [dispatch/CLAIMS](workflows/dispatch/CLAIMS.md)）：
   - **停樹換檔做完了（線己二）**：15:23:50 `eca_main` 代使用者 shutdown（使用者 15:13「同意」改成由它停樹、起樹，並等全套跑完再停）；15:24:18～24 線己二 `swap.sh` 全過：從釘住的 `159414053`（15:08:14 釘；乾淨複本全套 68 夾 1592 例只紅既有 4 支、`impls/aos-daemon/tests` 90 綠）重抄 `lib`／`templates`／`knowledge`／`py`／`kernel` 五夾（`kernel` 是新夾、`knowledge` 多 `wf/` 一庫）、換上預編的新 `aos-daemon`、清掉 `repo-aos` 那格兩個誤寫檔，備份在 `~/code/kf2-1113/stop-tree/backup-1113-152418/`；15:25:43 起回來，15:29 `verify.sh` ALL PASS（根 3 列、領班 9 列同停樹前、都 running；查詢信兩台都答）；實際停了約 2 分鐘。**起樹事故**：15:24:54 `eca_main` 第一次起樹是在自己的 shell 跑，`~/aos-home/env.sh` 只清 `AOS_DAEMON`／`AOS_KERNEL`／`AOS_CLOCK`、沒清 `AOS_STACK`，root 把 `ws/.stack/procs/eca_main/` 當成 root stack；約 35 秒（到 15:25:30）真的領班與 9 個 agent 掛在錯的 root 底下醒著、看到錯的鐘（`elsa-watch` 15:24:56 掃一次寄信給 `gpt-price`，已正常處理）；它自己用 `aos-daemon-ctl -d` 指那格停掉、`env -u` 清乾淨重起，查過沒有其他後遺症。當時留的兩件（那格殘留五樣、`env.sh` 補清全部 `AOS_*`）15:35 都辦了，見下面。退回沒用到。
   - **線戌做完（批 1b，`56a7fe498`）**：agent 的 `hooks.py` 改用共用引擎，呼叫者與引擎都沒改；唯一差異是同一格兩種錯並存時先報共通鍵那句（使用者「4可以。」）；repo 指令這條路 15:49 起存檔即生效，活樹 `lib` 複本等下次重抄；退回 `git revert 56a7fe498`。
   - **線卯做完（`24df73f61`）**：程式區 8 份 `_index.json` 共 189 項放進 repo（其中 `lib` 底下五份等下次重抄才進樹）；東西超過 15 個的夾各有一份生成的 `_index.json`，加刪檔後跑 `python3 wf/tools/index_gen.py --apply`、查對用 `index_check.py`，規格在 [index-build](../proto8/thinking/2026-11/13/index-build.md)；維護掛不掛進規矩（甲乙）還沒裁。
   - 下午 compact 後新進 main 的：線天（一段文字可寫成字串或字串陣列，[text-as-string-array](../proto8/thinking/2026-11/13/text-as-string-array.md)）、線地（`wf/tools/json_text` 折行修正與拆兩支）、線玄（workflows 模板併入 aos：使用者裁「變成aos的東西」「邊用邊併」，第 1 塊進 `proto8/knowledge/wf/`，[workflows-into-aos](../proto8/thinking/2026-11/13/workflows-into-aos.md)）、線黃（`index_check` 假綠，「都按照推薦」，[index-check-false-green](../proto8/thinking/2026-11/13/index-check-false-green.md)）；線玄第 2 塊（工作流節點骨架＋tidy 一組 → `knowledge/wf/workflows`、`knowledge/wf/knowledge`，`dbefe6fd2`）；線宇（8 KB 三處改成推薦語氣 `9f60cb0d8`、附錄 4 hook 那列 `2a6087735`、`env.sh` 正本進 `proto8/extras/aos-home/` `40dc42b57`）。15:35 `eca_main` 照使用者「1. 刪掉。2. 可以，隨便」刪了它那格殘留五樣、把活樹 `env.sh` 改成清全部 `AOS_*`；它回信說 `me-agent` 重起後定義沒退回、`public/howto.json` 已更新（時鐘兩句一致、新增 `start_tree_env`、`new_1113`）。
   - kernel 沒做的批：5 接線＋6（補丁 `~/code/kf2-1113/a4/`）、10（補丁 `~/code/kf2-1113/a2/`，C++ 沒 build 過）、7b、11b、12、13、14（回家用真腦）。
   - 已裁還沒施工：`set-def` 改「停→拔→掛回」、換定義後照睡醒提醒在等的信、家機主 session 改成樹裡一隻（其餘見 [SESSION-LOG](SESSION-LOG.md)）。
5. **活樹現況**（13:48 `aos-agent ctl ls`）：九列都 running——`_sweeper`、`eca_main`、`ops-agent`、`me-agent`、`repo-aos`、`gpt-price`、`elsa-watch`、`gpt-soap`、`wf-agent`（13:14 使用者新加的）；根 daemon 與領班兩台。15:29 起樹後 verify：根 3 列、領班 9 列跟停樹前一樣、都 running。各 agent 用的定義 `ws/defs/agent` 是今早抄的七包、沒有 `jsonx`，重抄範本也不會自己變。
6. **今天的改動在樹裡生效了沒**（15:24 重抄與換 daemon 之後的狀態；重抄的是 15:00 的 `159414053`，之後才進 main 的不含）：

   | 狀態 | 哪些 |
   |---|---|
   | 已生效（`cmd/`、`py/`、被指令直接 import 的 `lib/agent/*.py` 存檔即生效） | `eca_main` 來信第 7、6、3 項與 `aos-agent ctl set-def`、外部 MCP 的預檢與 `sync` 報改名；a2a 送信（只對接線後才開的畫面）；`aos-mailbox --keep-to`、`cli.json` 的 `settings` 鍵、`flags` 寫 `--settings` 報 `CfgBad`、各 agent 的 `env.json`；`aos-tools call` 多給 `AOS_STACK_IN_CALLER`；通知種類 `kernel_hold` |
   | 15:24 重抄後樹裡已有（agent 的工具每次叫都是新的；開著畫面的那隻要重開畫面才看到工具的新說明） | 定義檢查找 `aos-tools`（第 1 項）、工具印的路徑新寫法（`tool_io` 與各工具夾）、`mailbox_read`／`mailbox_send` 的 `keep` 收檔名、今天所有知識庫與範本的字句（含範本掛 `jsonx`、`stack.gitignore` 的 `env.json`）、kernel 框架整包（`lib/aos/kernel`、`kernel_llm`、`kernel_gate`、新夾 `kernel/`）、`index_view` 認字串陣列的 description、新知識庫 `knowledge/wf/`（現役定義 `ws/defs/agent` 還是七包，範本掛的 `jsonx` 要定義自己加） |
   | 15:24 換了執行檔、15:25 起樹後生效 | 新 `aos-daemon`（認查詢信 `procs_state_path`，verify 兩台都答；要靠它的批 5 接線還沒進 main，所以指令還沒走這條路） |
   | 要使用者把開著的畫面關掉重開 | 時鐘（`AOS_CLOCK` 等環境變數）、a2a 新送法；重抄後工具的新說明（開著畫面的 `aos-mcp` 是長駐的） |
   | 還沒進 main | kernel 批 5 接線、批 6（上線要先清各 agent 的 `tools/subagent/subagents.json` 舊帳）、批 10 |
   | 進了 main、等下次重抄才進樹（15:00 之後的） | 新版 `hooks.py`（樹裡 `lib` 複本那份；repo 指令那條路已生效）、`lib` 底下五份 `_index.json`、`knowledge/wf` 第 2 塊、knowledge 補的 `env.sh` 那一句 |

7. **repo 外的暫存夾**（`~/code/` 底下 13 個——16:05 多了 `tian-1113` 與 `wf-agent-scratch-1113`〔`wf-agent` 五份報告的抄本，`/tmp` 那份重開機會沒〕，都沒刪，要不要刪列在 [wait-user/04](wait-user/04-雜事.md)）：`kf2-1113`（停樹腳本、備份、三份補丁——補丁進 main 前不能刪）、`kbuild-1113`、`xu-1113`（線戌成品）、`you-1113`、`shen-try-1113`、`a2a-build-1113`、`a2a-try-1113`、`mcp-try-1113`、`ops-try-1113`、`si-try-1113`、`six-try-1113`。
8. **測試**：全套今天跑過三次都只紅既有 4 支（早上 66 夾 1354 例、線乙 1357 例、線庚 1412 例）；11:41 線己二試跑一次是 4 夾紅（`cmd/aos-agent/tests`、`extras/gitignore-check/tests`、`lib/aos/box_check/tests`、`templates/tests`，原因沒寫）；kernel tests 整夾 18 次裡第一次紅 1 例、原因沒查到。15:08 釘住的 `159414053` 在乾淨複本跑全套：68 夾 1592 例只紅既有 4 支（aos-agent `test_daemon_down` 2、box_check `test_acceptance` 2）。
9. **下一個接手的是家機**（公司機 17:00 關機；先 `git pull`）：
   - **家機能做的**：待裁頁使用者 16:13 已答、16:24 補「喔喔，我都看過了，應該算就按照推薦」：22 題裁定（W3 16:36 補裁「那就A」＝不用動）、W9／W10 未裁，逐題落地表在 [收工待裁-回覆落地](../proto8/thinking/2026-11/13/收工待裁-回覆落地.md#逐題落地表)，不需要活樹的 W7、W16、W17、W18、W23 已在家機做完（`ff97da487`，線落 11-13 晚），W6 與 W8 動的是公司機的檔、回公司機做；頁面原稿 [aos-1113-收工待裁.html](../proto8/thinking/2026-11/13/aos-1113-收工待裁.html)（24 題 W1～W23＋W9b，資料檔 `decide_20261113_shougong.json`、批名 `1113-shougong`）與精簡的 [aos-1113-優先裁.html](../proto8/thinking/2026-11/13/aos-1113-優先裁.html)；不需要活樹的 repo 工作（已裁還沒施工兩件：`set-def` 改「停→拔→同一個 stack 掛回」fx-1:B、跑過的 agent 換定義後照「睡醒」提醒在等的信 em-Q2:B；kernel 批 7b、11b、12 等）；[WAIT_USER 02](wait-user/02-真機驗證.md) 的家機題（kernel 問腦那包回家用真腦驗＝批 13、14；fsm 真腦跑一晚）；家機的主 session 改成樹裡的一隻（ms-2）。**workflows 併入第 3、4 塊家機也能做**：模板 repo 16:36 已 push 到 GitHub（`justty32/workflows` 的 main＝`0d0091a`），clone 下來就有備料。
   - **家機做不了的**：任何要公司這棵活樹的驗證、下次重抄、kernel 批 5 接線＋6、10（補丁只在公司機 `~/code/kf2-1113/`）。
   - **關機會沒的**：`/tmp` 底下全部（調度者的 scratchpad、`/tmp/kf2f/` 的全套輸出、`wf-agent` 的 scratchpad——它五份報告已抄到 `~/code/wf-agent-scratch-1113/`）；活樹 `~/aos-home` 跟著停。
   - **留在公司機磁碟、家機拿不到的**：`~/code/` 底下 13 個暫存夾（`kf2-1113` 含停樹腳本、備份與三份補丁，`kbuild-1113` 預編的 daemon，`xu-1113`，`wf-agent-scratch-1113`…）、`~/aos-home` 整棵樹與各 agent 的信箱留底、Windows 桌面的 html（兩份待裁頁的原稿進版控）、模板 repo。
   - **公司機下次開工照順序**：① 起樹——`cd ~/aos-home && source env.sh`，在 agent 的 shell 裡起要先清掉全部 `AOS_*`（今天 15:24:54 起錯的原因；`env.sh` 正本在 `proto8/extras/aos-home/`）；② 重抄——帶 `lib` 底下五份 `_index.json`、`knowledge/wf` 第 2 塊、knowledge 補的 `env.sh` 那句、新版 `hooks.py`，要再走一次停樹換料流程（腳本 `~/code/kf2-1113/stop-tree/`，`ST_REF` 另釘、先在乾淨複本跑全套）；③ 落 workflows 第 3、4 塊（家機先做了就不用；備料 `01959ce`）（已放行的只有 kernel 薄流程與 dev 包，其餘五包等使用者裁 W21；計畫在 [workflows-into-aos § 第 3、4 塊落檔計畫](../proto8/thinking/2026-11/13/workflows-into-aos.md#第-34-塊落檔計畫先不落檔等調度者通知)）。
   - **照落地表施工**：W7、W16、W23、W17、W18 已做（`ff97da487`，家機 11-13 晚；知識庫與範本說明下次重抄才進活樹）；剩 W6 清個人設定檔的舊信任紀錄（改前備份、動的是 repo 外的檔）、W8 刪暫存夾（刪前名單給使用者看；留 `kf2-1113`、`wf-agent-scratch-1113` 與他點名的）；併入時照做的：W12＝B、W15＝B、W14、W21＝B（只併 kernel、dev 兩批）、W22＝A。
   - **wf-lint 已刪（11-13 16:32 使用者「wf-lint整支刪掉吧。」；腳本、`/wf-lint` 指令與各文件裡要求跑它的句子都拿掉了）**；其他檢查（index_check、gitignore-check 等）怎麼處理、14:53「檢查工具，wf/的那邊就完全不留」是不是也指 aos 的 `wf/tools`——**仍未裁，答之前其他檢查照舊**；盤點在 [收工待裁-回覆落地 § lint／check 盤點](../proto8/thinking/2026-11/13/收工待裁-回覆落地.md#lintcheck-盤點)。
   - **wf-agent 的模板 repo 已 push、commit 編號全變**：備料最終版 `01959ce`（模板 repo 16:36 已 push 到 GitHub、push 前改寫過歷史所以編號全變：改寫前是 `f3d70ea`；第 1 塊來源 `7db1965`→`019c912`、第 2 塊來源 `7db5ccc`→`584f3f5`；落檔用 origin/main `0d0091a` 或之後；完整對照在 workflows-into-aos 的「commit 編號對照」節）；複核報告抄在公司機 `~/code/wf-agent-scratch-1113/prep-audit2.md`；第 3、4 塊沒有卡住的題；它新增的 for_user 題下次彙整帶上。
   - **wf-lint 刪掉之後**：wf-lint 16:32 刪了（`70e6d4fd8` 線洪；使用者「wf-lint整支刪掉吧。」）——線洪只照 grep 逐句改；11-13 晚家機線落通讀 AGENTS／conventions／aos-teams 06 再全 `wf/`、`.claude/` 掃過，殘句已改（`ff97da487`）；`wf/tools/check_anchors.py`、`find_big_lists.py` 沒刪（dev-env、tidy 有寫怎麼用）；`.claude/commands/` 夾已不在；commit 前現在跑 `codemap_gen.py --apply`、`index_gen.py --apply`、`index_check.py`，md 連結用 `check_anchors.py` 核。
   - **各 agent 的意見**：`eca_main` 彙整的各 agent 意見抄在 [agents-feedback-1113](../proto8/thinking/2026-11/13/agents-feedback-1113.md)，還沒整理成題目、沒排優先序——下次開工做。
   - **文件沒回頭標的**：[裁定落地-1113](../proto8/thinking/2026-11/13/裁定落地-1113.md) 的 em-Q1、cv-P14 兩列與幾處已做沒標的（kf-next、kf-t1、a2a、ms-1），下次動它的人補；其餘 open 看 [SESSION-LOG](SESSION-LOG.md)，`wf/inbox` 是空的。

## 2026-11-12 23:00 家機頂層關機前

（今晚最終現況；全貌看下一條「晚 家機頂層收工」，該條的 push 與試驗場句以本條為準。）

1. **授權與工作方式**：在家機。頂層只跟使用者說話和調度，事情交給 agent（普通 opus、雜活 sonnet、想法派 fable 隊長、可找 Argon；非雜活先通讀 wf 規矩）。說話一次一件、一次一題、白話先結論；要他判斷的題可以直接跳選項框（「有需要我判斷的可以跳選項給我」，已記進 [user/01 說話方式](workflows/common/user/01-說話授權與記憶.md#說話方式)）。23:15 關機。
2. **push**：第一次已推——使用者「可以push」，`main` 推到 `b03968062`（208 個 commit）。之後又多了未推的 commit（`34cc846a9` 起，含本條文書）；**頂層關機前會再問一次 push，以 `git log origin/main..main` 為準**。
3. **今晚 22:10 之後做的**（細節在 [日誌](session_logs/2026-11/2026-11-12.md)）：
   - eca_tidy 產出抽查落檔 → [eca-tidy-review](../proto8/thinking/2026-11/12/eca-tidy-review.md)；使用者「距離睡覺還有四十五分鐘。能修嗎」→ 十條修了九條（1～7、9、10）；第 3 條照選項框「kernel.json 加一個 judge」「同 smart-high（haiku）」（`cc03081e2`）；廢檔 `alt-fable/out2/v4.md` 照「廢檔可以刪。」刪了（`93bd79289`）。
   - 寄信給 eca_tidy（from claude-top，副本 `~/code/playground/tidy/inbox/2026-11-12-claude-top.md`）；它有 mail_notify（on_clock 每 1 分鐘）卻沒讀信工具，照「現在就幫我把工具掛上」掛了 `mailbox_peek`、`mailbox_read`（`7e5e621f9`）；使用者開著它的 session，要在畫面裡 `/mcp` 重連 aos 才看得到新工具。
   - 22:00 前後裁定（metainfo 全是觀點、`$ref`／`$at` 定案、kernel 手／門、linux user 一個帳號一整棵樹）都已進 thinking 與 HANDOFF 下一條，不重講。
4. **測試**：對 `2f51b3d29`～`52b3fa9d2` 之間的樹全套 62 夾 1252 例全綠、measure 連跑三次全過（這台沒裝 pytest，用 `python3 -m unittest discover`）；對最新的樹（`91d9ffd00`）再跑一輪：62 夾 1253 例，61 夾全綠；`proto8/cmd/aos-eca/tests` 的 `test_switch.TtySocket` 4 例紅是暫存路徑太長（AF_UNIX 108 字元上限）造成，換短路徑單獨重跑該夾 92 例全綠——坑：全套測試的暫存目錄別疊太深。
5. **明天接什麼**：① 主 session 接 aos（使用者先重連 aos MCP）→ [wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md)；② eca-tidy 第 8 條 `feedback/*.jsonl` 帶家目錄路徑（使用者「明天再說」）；③ 範本要不要掛 `jsonx`（甲乙丙，[WAIT_USER 01](wait-user/01-要你裁的.md)）；④ eca_tidy 產出剩 SUMMARY 沒做；⑤ 公司機 pull 後重 build 全部 impls、重跑 `proto8/install.sh`、試驗場重抄（細目見下一條第 7 點）。
6. **試驗場的樹**：關機前使用者自己停（`aos-daemon-ctl -d ~/code/playground/.stack shutdown`）。
7. **踩過的坑**：多條線共用工作樹——`git add` 指名路徑後馬上 commit、不 `-A`、不 `git stash`；全套測試從空目錄起跑；唯讀 eca 開 mail_notify 就要掛讀信兩支或關 mail_notify。
