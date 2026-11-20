線 aos-plain-terms-1120 的紀錄：把文件裡指 kernel、daemon 與零件的比喻用詞換成直接稱呼（純改文件）。

# aos-plain-terms-1120

頂層派。依據：使用者 11-20「拜託，手、門只是比喻，幫我乖乖用kernel/daemon稱呼好ㄇ」；頂層選項框「文件裡現有的比喻用詞要不要派線清掉？」他選「指 kernel／daemon 的「手」「門」,「把手」改叫「物件」,其他比喻也清」。

## 第 1 步：偏好寫進 wf/

- `wf/workflows/common/user/01-說話授權與記憶.md`「說話方式」一節，接在 11-19 編譯那段後面加一段（日期、原話逐字、怎麼做、對照表）。對照表只列他明說的兩列：手、門→kernel／daemon；把手→物件。
- `wf/workflows/common/rules-card.md`「說話」那條補一句（改後 7953 bytes，仍在 8 KB 內）。
- `wf/workflows/common/user.md`「回覆風格」那格補一句。

第 1 步更正（第二筆）：頂層轉來使用者 11-20 的話「hook物件...這有點像是一個遙控器的感覺？你用"物件"，我會聯想到物件導向。」，「把手→物件」暫停。三處改成「把手改叫什麼待定，定之前不動」；文件裡的「把手」本線一處都沒改。

第 1 步定案（第三筆）：頂層轉來後續兩問與答（原話逐字）：
- 頂層問文件裡要叫什麼（遙控器／直接寫英文 handle／維持「把手」／物件），他答：「我覺得handle不錯，但又感覺跟常見的函數callback的handler相衝，搞得好像hook會呼叫這個handler一樣。還有其他嗎？感覺這又有點類似hook的操控器？拿到了之後我們可以手動觸發hook這樣？」
- 頂層再問（操控器／遙控器／控制器／先維持「把手」；註明「觸發器」gdb 已拿去指別的東西），他選「操控器」；隨後更正：「操控器...還是用遙控器吧」。
- 所以對照表寫「把手（翻 handle）→ 遙控器」，並記下不用「物件」「handle」的原因；rules-card、user.md 同步。

## 第 2 步：盤點

交 [01-盤點](aos-plain-terms-1120/01-盤點.md)＋逐檔分布 [01-盤點-分布.csv](aos-plain-terms-1120/01-盤點-分布.csv)。坑：`git ls-files` 預設把中文檔名加引號轉義，第一輪數字漏了所有中文檔名的檔，改用 `git -c core.quotepath=off ls-files` 重數。

## 第 3 步：改明確的

只改三種，其餘列進 [02-要他定的詞](aos-plain-terms-1120/02-要他定的詞.md)。做法：`~/.aos/scratch/aos-plain-terms-1120/apply.py`（逐條替換、受保護字串不動），改完逐處看 word diff，讀不通的手改。程式識別字、檔名、錨點不動（只有兩個標題換字，連結跟著改）。檔的執行權限沒變（`git diff --summary` 沒有 mode 行）。

1. **把手 → 遙控器**（翻 handle）：`py/aos/agentlib/agent_hooks.py`、`hooks.py`（hook 那個寫「hook 遙控器」）、`py/aos/py/__init__.py`、`py/aos/py/agent/__init__.py`、`py/aos/py/daemon_ctl.py`、`py/aos/gdb/__init__.py`、`look.py`、`py/aos/apps/gdb/README.md`、`py/aos/apps/hook/README.md`、`py/README.md`、教學 `06-接著開發-3`、測試檔頭與註解 `test_aos_py.py`、`test_aos_py_live.py`、`apps/gdb/test_gdb_live.py`、`test_gdb_trigger.py`。「把手上的事」（eca 範本 README，「把 手上的事」）是普通用法，不動。
2. **指 kernel 的「門」→ kernel**：`templates/kernel/docs/02-kernel-modes.md`（「門房」那格改「daemon 自己就是 kernel，來者不拒」；標題「agent 當門」→「agent 當 kernel」）、`templates/kernel/README.md`（權限件「門：」→「決定」；連到上面標題的錨點跟著改）、`py/packs/README.md`、`py/aos/flags.py` 註解、`wf/workflows/dispatch/CLAIMS.md`（同一個錨點）、CONCEPTS、NORMS 見下表。
3. **總機 → llm kernel**（指跑它的那台 daemon 時寫 llm daemon）：cpp 各 README 與 docs、`llm.hpp`、`post.hpp` 檔頭、CONCEPTS、NORMS、教學 01～04、06-1、07、08、`py/docs/02`、`py/aos/apps/agent/docs/04-搬家`、`py/aos/apps/sandbox/README.md`、`py/tools/aos/kernel_llm/README.md`、templates（daemon-root、kernel、start-api、start-eca、tests）、`wf/knowledge/code-map.json`、`wf/workflows/common/conventions/01-程式碼慣例.md`。教學 07 標題「1. 總機那邊」→「1. llm kernel 那邊」（查過沒有連結指它）。

CONCEPTS、NORMS 逐條只換稱呼、不動意思：

| 檔 | 條 | 改了哪幾個字 |
|---|---|---|
| CONCEPTS/01-設計理念/01-C-01～C-48 | C-48 一帶 | 問腦總機→llm kernel |
| CONCEPTS/01-設計理念/02-C-51 | C-51 | 問腦總機→llm kernel |
| CONCEPTS/01-設計理念/03-續-C-52-例外 | C-52 表 ③ | 問腦總機→llm kernel |
| CONCEPTS/01-設計理念/05-布局成長與檔案權限 | val 那句 | 問腦總機→llm kernel |
| CONCEPTS/04-kernel | 檔頭實作 | 「LLM kernel 是問腦總機 [路徑]」→「LLM kernel 在 [路徑]」 |
| CONCEPTS/04-kernel/02-續-C-47 | C-47 ② | 問腦總機→llm kernel ×2、「當門」→「當 kernel」×2、「隊 kernel → 總機」→「→ llm kernel」；使用者原話「問腦總機要收進框架」與錨點不動 |
| NORMS/00-規範-3 | kernel 位置 | 問腦總機→llm kernel |
| NORMS/05/N-09 state與計數器、state_flux與讀不了、N-15、N-16、N-16/02 | 各 1 處 | 問腦總機→llm kernel（N-16 的連結文字＝檔名，不動） |
| NORMS/08-待定/01 | 待定之一 | 「是問腦總機」→「在」、問腦總機→llm kernel |
| NORMS/09-kernel | 檔頭、N-42 | 問腦總機→llm kernel ×3（原話與錨點不動） |
| NORMS/09-kernel/01-N-42-1、02-N-42-1 | 各 1 處 | 問腦總機→llm kernel |
| NORMS/09-kernel/03-N-42-2 | aos-daemon-ctl 那句 | 「唯一的門」→「只能經過 kernel」 |
| NORMS/10/07/01-N-63、03-AOS_ 變數 | 4 處 | 問腦總機→llm kernel |
| NORMS/主題 | LLM kernel 列 | 刪「問腦總機」四字（後面就是路徑） |
| NORMS/命名-續/02 | 1 處 | 問腦總機→llm kernel |

驗收：
- 改完再 grep「總機、把手、當門、門房、唯一的門、kernel 的門、操控器」：剩下的都在使用者原話引號內、檔名與錨點、兩句打比方、`CONCEPTS/附錄3-條號表/02-各批出處/02-11月.md` 的出處紀錄「C-47 ② 補問腦總機收進框架」（記那天加了什麼，照舊）、「把手上的事」、別線 claim 的 `agent_spec_agent.py`，與下面不改的三個 wf 檔。「操控器」只剩 `wf/workflows/common/user/01`、`user.md` 記原話的引號裡。
- 測試：`git archive HEAD` 抄兩份（一份原樣、一份蓋上本線改的檔），各跑 `install.py` 後跑 `test_hook_points_match`、`test_index_view`、`test_tool_io_keys`、`test_aos_py`、kernel `test_kernel_cut`、kernel_gate `test_triage`、guard `test_guard`、gdb `test_gdb_trigger`、kits `test_kits`、`py/tests` 整夾 discover：兩份全部 OK（discover 都是 OK、skipped=1），前後一樣。複本在 `~/.aos/scratch/aos-plain-terms-1120/copy-base-140051`、`copy-mine-140053`。

交件：第 1 步 15784a0c7、a2f7ca377（撤回「物件」）；第 1 步定案＋第 2 步 52a697d96；第 3 步第一批（把手）1781997d3、第二批（門、總機、02）53ffda6bc；本紀錄收尾另一筆。

沒改、各有理由：
- `wf/progress.json`（把手 5 處）：活狀態，只能用 `--op progress_upsert` 整條換，那幾條是別線的。
- `wf/HANDOFF.md`（把手 1 處）：頂層的交接。
- `wf/tools/index_gen_desc.json`：生成器從檔頭抄的，源頭改了排隊重生。
- `wf/workflows/common/` 三份偏好檔裡的「把手」「操控器」「物件」：都在記原話的引號裡。
- 打比方的兩句「像一台專門打電話的總機」（教學 03 第 7 行、`templates/kernel/docs/01-llm-kernel.md` 第 8 行）：解釋用，列在 02 第 18 題。
- 被別線 claim 跳過：`py/aos/agent_spec_agent.py`（把手 1 處，aos-pylib-k4-1120）。

替使用者做的選擇：
- 「總機」指那台 daemon 的地方（「領班、總機」「共用一台總機」「總機 daemon」）寫 llm daemon，其餘寫 llm kernel；大小寫一律小寫 llm（start-api 範本的寫法）。
- 「唯一的門」是頂層 11-12 提的說法、不是使用者原話（他只回「kb-ctl:A*」），所以照新規矩改成「只能經過 kernel」。
- 「門房」那格改寫成「daemon 自己就是 kernel，來者不拒」，意思沒變。
- 同一節原有「術語第一次出現用日常比喻帶過」（09-01 起）。新段落寫明兩者的分界：第一次解釋時可以打比方，比喻不拿來當東西的名字。這是我對兩條原話的調和，他若不同意改那句即可。
- 程式裡的中文註解算「文件」，照新說法改（任務書這樣定）。
