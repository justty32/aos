# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-13 公司 WSL 頂層（repo-aos）收工草稿

（14:00 前後起草，15:40、16:15、16:35 各補一輪；沒有待補的記號了。）

1. **授權與工作方式**：公司 WSL，頂層就是 `~/aos-home` 樹裡的一隻 eca `repo-aos`（工作區 `~/repo/aos`、只有 `main`）。使用者開場：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」；「都可以用fable帶隊」「fable多多的用，因為明天額度重置」（**只限今天**，明天起回到 user.md 的「fable 盡量少用」）；「都可以清、都可以下載。」「反正有需要我判斷的東西就丟桌面」（要他裁的做成頁放 Windows 桌面）。**`eca_main` 派來的普通工作算使用者的授權；push、刪檔這類不可逆或對外的仍要他本人說**（「1.算。」「2.對。」，已寫進 [AGENTS 鐵律 2](../AGENTS.md)）。停樹、起樹只由使用者自己下（15:13 他同意今天那次由 `eca_main` 代）。**這台公司機 17:00 關機，下一個接手的是家機上的 session**（使用者 16:08：「今天五點下班後，我就是關機，回到家用另一台電腦」）。
2. **push**：收工前由調度者問使用者（他開場說「下班前再統一push」），他說推才推；推了沒看 `git status -sb` 的 ahead 數（沒有 ahead＝推了）。push 前做過兩筆隱私修正（`5a87aa55b`、`233ca54fa`）。
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
   - **家機能做的**：待裁頁使用者 16:13 已答、16:24 補「喔喔，我都看過了，應該算就按照推薦」：21 題裁定、W3／W9／W10 未裁，逐題落地表在 [收工待裁-回覆落地](../proto8/thinking/2026-11/13/收工待裁-回覆落地.md#逐題落地表)，**都還沒施工**——不需要活樹的幾件家機就能照表做（W7、W16、W17、W18、W23；W6 與 W8 動的是公司機的檔、回公司機做）；頁面原稿 [aos-1113-收工待裁.html](../proto8/thinking/2026-11/13/aos-1113-收工待裁.html)（24 題 W1～W23＋W9b，資料檔 `decide_20261113_shougong.json`、批名 `1113-shougong`）與精簡的 [aos-1113-優先裁.html](../proto8/thinking/2026-11/13/aos-1113-優先裁.html)；不需要活樹的 repo 工作（已裁還沒施工兩件：`set-def` 改「停→拔→同一個 stack 掛回」fx-1:B、跑過的 agent 換定義後照「睡醒」提醒在等的信 em-Q2:B；kernel 批 7b、11b、12 等）；[WAIT_USER 02](wait-user/02-真機驗證.md) 的家機題（kernel 問腦那包回家用真腦驗＝批 13、14；fsm 真腦跑一晚）；家機的主 session 改成樹裡的一隻（ms-2）。
   - **家機做不了的**：任何要公司這棵活樹的驗證、下次重抄、workflows 併入第 3、4 塊落檔（備料在公司機的模板 repo `/mnt/c/code/mine/workflows`，`wf-agent` 有沒 push 的 commit、含 `aos-prep`，家機看不到，除非它 push）、kernel 批 5 接線＋6、10（補丁只在公司機 `~/code/kf2-1113/`）。
   - **關機會沒的**：`/tmp` 底下全部（調度者的 scratchpad、`/tmp/kf2f/` 的全套輸出、`wf-agent` 的 scratchpad——它五份報告已抄到 `~/code/wf-agent-scratch-1113/`）；活樹 `~/aos-home` 跟著停。
   - **留在公司機磁碟、家機拿不到的**：`~/code/` 底下 13 個暫存夾（`kf2-1113` 含停樹腳本、備份與三份補丁，`kbuild-1113` 預編的 daemon，`xu-1113`，`wf-agent-scratch-1113`…）、`~/aos-home` 整棵樹與各 agent 的信箱留底、Windows 桌面的 html（兩份待裁頁的原稿進版控）、模板 repo。
   - **公司機下次開工照順序**：① 起樹——`cd ~/aos-home && source env.sh`，在 agent 的 shell 裡起要先清掉全部 `AOS_*`（今天 15:24:54 起錯的原因；`env.sh` 正本在 `proto8/extras/aos-home/`）；② 重抄——帶 `lib` 底下五份 `_index.json`、`knowledge/wf` 第 2 塊、knowledge 補的 `env.sh` 那句、新版 `hooks.py`，要再走一次停樹換料流程（腳本 `~/code/kf2-1113/stop-tree/`，`ST_REF` 另釘、先在乾淨複本跑全套）；③ 收 `wf-agent` 的新 commit 落第 3、4 塊（已放行的只有 kernel 薄流程與 dev 包，其餘五包等使用者裁 W21；計畫在 [workflows-into-aos § 第 3、4 塊落檔計畫](../proto8/thinking/2026-11/13/workflows-into-aos.md#第-34-塊落檔計畫先不落檔等調度者通知)）。
   - **照落地表施工（下次開工，兩台分著做）**：W7 改 AGENTS「單機開發」那句成現況、W16 知識庫 tidy 補第 6 條「收斂優先於拆檔」、W23 三處 `AOS_HOME` 等對齊、W17 檔案格式推薦一句（先查 `aos-json set` 實際輸出）、W18 docs/02 補一句、W6 清個人設定檔的舊信任紀錄（改前備份、動的是 repo 外的檔）、W8 刪暫存夾（刪前名單給使用者看；留 `kf2-1113`、`wf-agent-scratch-1113` 與他點名的）；併入時照做的：W12＝B、W15＝B、W14、W21＝B（只併 kernel、dev 兩批）、W22＝A。
   - **lint／check 要不要留（未裁，方向題）**：使用者「我很討厭wf-lint這東西，很想把它刪掉」「這種check啦，lint啦，之類的測試用的東西都是阻礙開發的。開發初期不該有這種東西。」；調度者擺了三種讀法問他、並問 14:53「檢查工具，wf/的那邊就完全不留」是不是也指 aos 的 `wf/tools`，**他還沒答，答之前照舊**；盤點在 [收工待裁-回覆落地 § lint／check 盤點](../proto8/thinking/2026-11/13/收工待裁-回覆落地.md#lintcheck-盤點)。
   - **wf-agent 備料最終 commit `f3d70ea`**（取代 `7db5ccc`／`158dbd2`；複核報告抄在 `~/code/wf-agent-scratch-1113/prep-audit2.md`）：第 3、4 塊下次在公司機落，沒有卡住的題；它 repo 的 push 它問了使用者、未答；它新增的 for_user 題下次彙整帶上。
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

## 2026-11-12 晚 家機頂層收工

1. **授權與工作方式**：在家（家機 Manjaro，`~/repo/simple_tools/aos` main）。頂層只調度，事情交給 agent：普通 opus、雜活 sonnet、規劃 fable；agent 可以再派子 agent；非雜活先讀 wf/ 規矩。**push：睡前（23:15 關機）一次，推之前頂層先跟使用者說一聲**。使用者：「等一下token額度到上限後別動，我有一個免費的額度重置」（頂層轉述）——額度到上限就停在原地等他，不要自己接著做。之後（頂層轉述）：他說把額度重置了、後天是每週額度重置；接下來的想法都派 fable 隊長、可以找 Argon。
2. **今晚新定的規矩**（都在 [tidy content-trim](workflows/tidy/content-trim.md#清舊不必逐項先問2026-11-12-定) 開頭）：「本來就該按照tidy規矩，把舊的東西清掉」＝tidy 判準涵蓋的清舊直接做、事後列清單；「不存在的東西就刪掉。」＝條文講到已不存在的 key／指令／檔／機制直接刪；「還有，什麼11/5幹了啥，這個也刪掉，以後面的爲準，全部匯總成結論，只留結論」＝**條文與說明只寫現在式結論**，之後寫條文的人也照這條（按日紀錄不適用）。
3. **今晚進 main 的**（約 180 個 commit，都沒 push；細節在 [日誌](session_logs/2026-11/2026-11-12.md)）：
   - **外部 MCP**：fsm 經 aos 匯入九步（`15e7f8225`～`b9ca076fc`；新指令 `aos-mcp-import`＋`sync`、`lib/mcp_client.py` 等）；Q1 不做白名單、Q2 stdio server 一律在 server 檔資料夾起（`8c4d73d15`）→ [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md)
   - **eca**：claude 身開 `Agent`／`Skill`、aos MCP 切主／子兩台（`tools_sub`）`2ab15e1c7`；codex 身只調查 `dc303e087` → [eca-task-subagent](../proto8/thinking/2026-11/12/eca-task-subagent.md)；沒畫面時 `/goal`、`/compact` 失敗不再卡信 `db2018b72`
   - **index 與 `$ref`**：index 每筆可帶 `index`、檔內 `_index` 可為路徑、路徑照 json／檔案系統同像從容器算、收 `#/` 開頭 → [index-link](../proto8/thinking/2026-11/12/index-link.md)；`$ref` 收 `#/`＝寫著它的那份檔 → [ref-hash](../proto8/thinking/2026-11/12/ref-hash.md)
   - **json 工具續行**：aos-json 加 add／ls／search、新工具 `json_len`、`jsonx_multi_get／set`、`json_ls` 的 `depth` → [json-tools 04](../proto8/thinking/2026-11/12/json-tools/04-aos-json下沉與len與jsonx-multi.md)
   - **拆檔與程式碼庫整理**：`aos-eca-turn` 拆成 `aos_eca/`、`cli_session` 拆成八份 `cli_*.py`；fable 領隊整個 proto8 程式整理（行為不變、各批各自 commit，收尾 `ae2fd4e8a`）→ [codebase-cleanup](../proto8/thinking/2026-11/12/codebase-cleanup/README.md)
   - **tidy 三輪**：wf 交接檔瘦身（SESSION-LOG、WAIT_USER 分 `wait-user/`、日誌分月）、conventions 拆檔、C-54／N-28 摺疊、全 docs 沿革只留結論 → [tidy 報告](workflows/tidy/reports/2026-11-12-收尾.md)
   - **thinking→docs 提取**（10-29～11-12）：W1～W7、W9 做完，新條 C-87～C-92、P-47、P-48；W8 等 U1 → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
   - **wf→aos**：對標調查（必須的都有、缺的是小輔助）；主 session 的 aos MCP 登記檔修好（repo 外，10 支）→ [wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)、[wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md)
   - **試驗場**：家機 11-12 21:04 照 main `415cf6a2c` 第三次整個重建（fsm 48 含 fake_echo、eca 各 26、子 agent 那台 9；假腦／gemma／haiku 子 agent／codex luna／index_view／`$ref #/` 都實跑過；樹停著，`edcb5fc70`）→ [playground-home](../proto8/thinking/2026-11/12/playground-home.md)
   - **額度重置後四個新想法**（各派一位 fable 隊長、都找了 Argon、都只調查／想清楚，沒改程式與條文；Argon 提示與回覆原文存在各題夾裡）：`$ref` 跟 index 統一的範圍（`$ref` 資料檔 9 個、程式 7 支約 110 處；統一法五種，傾向共用解析器＋記號）→ [ref-index-unify](../proto8/thinking/2026-11/12/ref-index-unify.md)；`_metainfo` 套客觀／通用觀點／主觀（套得順，卡在執行類的格）→ [metainfo-views](../proto8/thinking/2026-11/12/metainfo-views.md)；kernel 是上面與硬體的橋（四種整理法、圖紙不用重畫）→ [kernel-as-bridge](../proto8/thinking/2026-11/12/kernel-as-bridge/README.md)；linux user 是可互動的對象（linux 事實、對到 aos 現況、五個念頭的讀法）→ [linux-user](../proto8/thinking/2026-11/12/linux-user.md)
   - **收尾修補**：proto8 舊文件壞連結修 21 條 `64b22d69f`；fork 測試 `test_kernel_alone_is_not_a_daemon` 改在空的暫存目錄跑 `6602f453c`（紅的原因是 repo 裡留著 11-02 的空 `proto8/.stack` 夾被 `ctl who` 猜到、不是回歸；那個空夾頂層已 `rmdir`，照公司條「空殼夾准刪」）
4. **使用者今晚的裁定**（原話短引）：
   - 試驗場：「我沒在跑，試驗場那邊也可以全清空。」
   - 全域 MCP：「全域mcp這個我們管不着，只要確定不要干擾到我們的aos就好。」
   - 外部 MCP Q1／Q2：「1.不用，風險自己承擔。2.這個我不是很清楚，如果你覺得要統一那就統一吧，我直覺上感覺OK，反正之後出事再說」；之後「外部MCP，明天再說」（頂層轉述）。
   - index 三題：「1. 甲。2.甲。3.甲，話說ref應該支援#/開頭吧」（都維持現狀；`$ref` 收 `#/` 另做）；index 路徑收 `#/`：「也跟進吧」；資料夾的 `_index.json` 裡寫 `#/` 算不算：「算數。」
   - 拆檔與整理：「東西都弄好後，可以來做重構拆檔+tidy。」「重構拆檔和tidy結束後，派fable領隊，去做整個程式碼庫的整理，架構弄乾淨些。」「盡量做」；tidy 的三句見第 2 點。
   - fsm 真腦跑一晚：「fsm真腦跑一整晚...假日再說。」（頂層轉述）
   - wf→aos 五點：「…4.把人類這個linux user作爲agent，寄信過去就是了。5.對，這個明天開始。」（全句在 [wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)）；「就是說，沒有硬性缺的了，現在wf/的東西，我們拼拼湊湊就能有了。」「以後一定會比wf/好用，放心。寄信這個以後自然就能夠搞定，反正必須的都有了。」
   - 主 session 接 MCP：「好，這些都不是問題。只是主session接mcp這個要處理。邊緣狀況這邊就先這樣，之後踩坑再說。」
   - 四個新想法（同一則訊息，開頭「接下來我會輸出一連串想法，要麻煩你都派fable隊長。」、結尾「這些都可以讓argon幫忙」）：
     - 「首先是$ref這塊，可以的話還是想要跟index統一，去幫我看看牽涉到的範圍有多大。」
     - 「然後是metainfo這東西，就是說，還是今天thinking中所說的，客觀，通用觀點，主觀那套index/description，metainfo其實也是一樣，去想想。」
     - 「然後是kernel這塊我也有新的想法，就是說，我一直說kernel負責排程和資源分配，後來發現linux kernel這個最通用的kernel，他的核心功能其實是作業系統與硬體的橋梁，套用到我們這邊，首先是root daemon本身就是一個kernel，他的所謂硬體對象就是linux，那，如果root daemon底下掛了另一個daemon，那對這個子daemon來說，root daemon就是他的硬體，去幫我想想。」
     - 「再派一個：關於linux使用者，不管背後是人還是agent，他都是一個可以互動的對象。這個很特別，我第一次跨足這塊。首先是root daemon本身掛在一個使用者底下。然後是一個linux user，他對於linux這個硬體來說，他就是一個proc(不管這個proc背後是誰，反正從linux這邊看過去，他就是一個proc)，他其實跟root daemon是平級的。Hmmm，假如是root user的root daemon呢？或者說，一個linux user他搞不好會說某個root daemon那個proc，就代表他？總之先做初步調查。」
   - 四個新想法的回覆（11-12 晚，一則訊息，逐字）：「當然，全都是觀點，全都是參考用，出事了自行負責。_index的obj內要不要再多塞東西...可以，想塞啥塞啥，出事了自己負責。主觀的metainfo的位置也不規定。客觀那個你不管怎麼描述無法描述全，所以能被我們記錄下來的，非私有的，全都是通用視角(公用視角)(自己公開給別人的聲稱)。_metainfo不算index，_metainfo他是描述自身節點的一個子節點，可以塞任何東西來描述自身，因爲index也是一種描述自身的東西，所以也可以塞入其中。$ref這塊，可以用#/指代根obj，同時也算指代自身所在檔案，所以可以用#/key, #/../other.json。kernel這塊，我的請求寄給誰...這個確實有點寬泛，他背後的那個概念(資源排程)和我們的現在的概念有點衝突(硬體橋梁)，linux kernel當然同時包含這兩種概念，但我覺得硬體橋梁比較重要，資源排程這塊linux kernel更像是對硬體的資源進行排程與管理。所以資源排程這塊我覺得還是別叫kernel好了。kernel這塊等等細聊。linux user要等等。然後等等幫我準備好遊樂場。我想試試看用claude eca來初步整理proto8，唯讀的，整理結果放外面。」
     各題去向：`_metainfo`／index 那幾句、`$ref` 那句各有一位 fable 落實中（各自記錄，見 [metainfo-views](../proto8/thinking/2026-11/12/metainfo-views.md)、[ref-index-unify](../proto8/thinking/2026-11/12/ref-index-unify.md)）；kernel 方向已說（硬體橋樑比較重要、資源排程那塊別叫 kernel），細節等細聊、新名字未定，題 1、3 未答（同晚細聊後「資源排程別叫 kernel」收回、名字都不改，見下一步 8） → [kernel-as-bridge § 使用者回覆](../proto8/thinking/2026-11/12/kernel-as-bridge/README.md#使用者回覆11-12-晚)；linux user 等等；遊樂場另有人在準備。
5. **下一步**（依優先）：
   1. 主 session 接 aos（明天）：使用者先重連 aos MCP；接著 Skill 放哪、主 session 身分、always-on 規矩、`todo` 歸誰 → [wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md#明天主-session-開始現在卡在三點)
   2. 外部 MCP 接真的別人寫的 stdio server（明天；要下載先問）＋codex 沙盒對 stdio、`disabled_tools` → [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md)
   3. thinking→docs W8：等使用者裁 U1 → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
   4. 程式碼庫整理剩的（agent-fsm 兩段逐字相同與 `clock_tick`、找 lib 五種寫法、兩處文件舊出處）→ [codebase-cleanup](../proto8/thinking/2026-11/12/codebase-cleanup/README.md#做到哪11-12-晚收線)
   5. 待裁各題（WAIT_USER 01）裁了就照做。
   6. kernel 框架施工與 fsm 真腦跑一晚：假日。
   7. 四個新想法（ref-index-unify、metainfo-views、kernel-as-bridge、linux-user）等他看，各題要他定的在 WAIT_USER 01；都不擋別的。
   8. kernel 細聊：已聊出「手／門」（daemon 是手、kernel 是門）、kernel 是主觀的概念、daemon 也是概念（使用者「好，就是這樣。」）；「資源排程別叫 kernel」收回、名字都不改（「對，收回，名字都不用改。」）；他要頂層多講 daemon、建立自己的心智模型——已講完、他認可（「我覺得這樣就OK了」）；剩：題 1 嚴到哪、題 3 圖紙；`aos-daemon-ctl` 不經判官的出入待給他看 → [kernel-as-bridge 06](../proto8/thinking/2026-11/12/kernel-as-bridge/06-細聊-手與門.md)
   9. 遊樂場：使用者要用 claude eca 唯讀初步整理 proto8、整理結果放外面——`eca_tidy` 已備好、樹開著，等他試（[wait-user/03](wait-user/03-試驗場.md)）。
6. **等使用者的**：都在 [WAIT_USER](WAIT_USER.md)（要你裁的、真機驗證、試驗場、雜事四類）；最急的是 push 與重連 aos MCP。
7. **另一台機器（公司）要注意**：pull 之後①重 build 全部 impls（aos-directive 介面變了；aos-json 沒重 build 的話 `json_ls`／`json_search`／`json_add` 會報 `CommandUnknown`）②重跑 `proto8/install.sh`（新指令 `aos-mcp-import`）③試驗場 `lib／py／cmd／templates/agent-fsm` 整份重抄④`~/.cache/aos-mcp-*/tools.json` 的壞格照 [wait-user/04](wait-user/04-雜事.md) 那行指令清。impls 又重 build 過（`$at`），pull 後要重 build 全部 impls。
8. **踩過的坑**：多條線共用一個工作樹時，`git add` 指名路徑後要馬上 commit，不然別人 staged 的會被一起帶走——今晚發生兩次（json 線帶走 tidy 的刪檔、提取 W2 帶走 W5），另有一次誤 amend、已還原；同時開的 agent 數有上限（約 20）；wf-lint 的數字要先看掃描範圍再比；全套測試要注意起跑目錄——repo 裡若留著空的 `.stack` 夾會被 `ctl who` 猜到（今晚紅一支就是這個）；多條線共用工作樹時不要 `git stash`（會把別人沒提交的改動一起收走）。
9. **測試與 HEAD**：全套最後一次全綠是 61 夾 1244 例（對應 `9da8be804` 的樹；跟先前記的 65 夾 1325 例算法／範圍不同、原因沒查），`lib/aos/measure` 連跑五次全過、先前偶發的紅未重現；之後 aos-sandbox 那輪另跑相關夾 716 例全過、新增 `cmd/aos-sandbox/tests` 8 例；codemap 0 stale；wf-lint 掃 `wf` 為 0。HEAD 與 push：以 origin/main 是否含本條為準（頂層收工時問過使用者後推）。
