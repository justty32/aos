# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-19 13:30（公司機，第二次 compact 前）——四條線還在跑；全在 WSL 的 `~/repo/aos`，沒推；五點統一問 push

**授權（使用者 11-19 早原話）**：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」——**中間不 push，五點前問他一次再推**（aos 與 llm_proxy 兩個 repo）。頂層只調度。Argon：「argon額度雖然不多，但是只有正規調查流程會用到。不用省」（`agy` 只在 Windows：`C:\Users\WG-Guanyu\AppData\Local\agy\bin\agy.exe`，長提示寫成檔用 `--add-dir`，見 `wf/public/model-notes.md`）。這台沒有 aos-user／全景頁，**問他的題直接用選項框問**。

**兩份 repo，別搞混**：
- **WSL `~/repo/aos`＝唯一動工處**，比 origin 多 40 筆上下。agent 用 `wsl -e bash -lc '…'`，交件走 `commit-request`。頂層在工作樹乾淨時於 `~/repo/aos/proto8` 跑 `env -u AOS_HOME python3 install.py` 重裝（最近一次 13:12，含 `aos.py` 入口與 `defs` 改名；之後交的還沒裝）。
- **Windows `C:\code\mine\simple_tools\aos`＝頂層 cwd，不動工**。**本檔在這份是未交的複本**；五點 push 後先 `git checkout -- wf/HANDOFF.md` 再 `git pull`。`stash@{0}` 是 11-18 的半成品，另有三包舊 stash，使用者沒說清就不動。
- WSL `~/repo/llm_proxy`：本地多 2 筆沒推。LiteLLM proxy 在 `127.0.0.1:4000` 跑著（`pinned_1.109.1/`），別碰。

**用詞（使用者 11-19 原話，以後照做）**：「然後以後也用編譯、重新編譯來說，不要再用生、重生這樣」——跑 `agent.py` 變成那夾 json 叫**編譯**，再跑叫**重新編譯**；「抄」叫靜態連結、「借」叫動態連結。正在由線 `aos-defs-rename2-1119` 寫進 wf 與文件。

**還在跑的四條線（compact 後回報會以 agent 訊息進來：對過 commit、白話轉述、要他定的用選項框；都交完且工作樹乾淨就重裝一次）**：
1. `aosgdb-verbs-1119`：斷點動作照 IDE 改。使用者：「我記得有step into還是啥的，參考那些ide」→ 選「resume/step 自己等到停」；skip「不該有這個方法。」；`id=` 可以。做成 `a.bp.resume()`（不帶參數，放行並等到下次停）、`a.bp.step()`（走一格再停）、`a.bp.stop()`；拿掉 `wait_stopped`、`skip`。step into／out 只提案。
2. `aos-defs-rename2-1119`：(a) `defs.defs(...)` 換名——使用者：「要，可以參考那些程式語言的類似的功能的名字」，方向往 compile 那組；(b) 用詞統一（含 N-70 的「重生」改「編譯」、把用詞規矩記進 wf）；(c) 工具包連結方式做成編譯選項——使用者先答「定下」（靜態）隨即「或者說，用選項吧，gcc那樣」；預設頂層暫定靜態、會列成題。
3. `aos-c74-c87-1119`：C-74、C-87 補加註（使用者選「補，改完貼給我看」）——**回來要把兩條加註全文貼給他**。
4. `aos-base-audit-1119`：基底體檢（使用者：「…突然有些擔心我們的整套基底，也就是從硬體到kernel，這邊會不會有問題，派一條線去看看吧」）。只查不修，報告在 `thinking/2026-11/19/aos-base-audit-1119/`。

**今天已定的設計（細節 `git log e53d6b979..` 與 [11-19 日索引](../proto8/thinking/2026-11/19/README.md)；每題的原話在各夾的「使用者裁定」檔）**：
- **庚 aos-compile**（`aos-compile-庚/10`）：「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」第一、三刀與 Argon 六洞已交；第二刀劃掉；骨架不帶 hook 組。
- **命名空間**（`aos-ns-1119/07`）：B 資料夾即命名空間；`std` 短名、別的庫加 `庫名_` 前綴；`std` 先不搬；照叫 `std`；`std` 留在入口頂層。第一刀已交。**未裁**：別的庫的路徑「明寫在 agent.py」（頂層解釋成 `#include "路徑"` 對 `#include <名字>`，他還沒答）。
- **繼承**（`aos-inherit-1119/08`、**新規範 N-70**）：衍生只在編譯時做（`defs.load`，已交 `012b2b191`）；「繼承」進規範且只限編譯時；跑著長出來的東西**不做**收回；狀態機每隻一層先不做。收緊：兩組現成 hook 撞名改成報錯（已告知，他沒反對）。
- **斷點庫 `aos.gdb`**：條件觸發→停→檢閱→續；`stop_before_tool` 真的在工具跑前卡住（hook 自己等）；外面的觀察者也算斷點；「不要看的出來，兩者解耦合」（aos-agent／daemon 不知道 gdb）；shell 條件退出碼維持 0／10／其他。介面：`a.xxx`＝`aos-agent xxx`，斷點全在 `a.bp`（增刪改查，回 id 字串），建斷點寫 `a.bp.add.before_tool("x")`。
- **整套 Python 庫**（`aos-pylib-1119/07`、`aos-pylib-施工.md`）：入口 `aos.py`；把手式 `a = agent.attach("ann")`；讀檔的收進 `a.look`；薄殼（一呼叫＝一條指令）；`install.py` 改成抄完再清孤兒。寫定義的名字 `ag`→**`defs`**，位置「就 aos.py.agent.defs 吧」（已交 `487422beb`）。
- **子帳號**：使用者已 `sudo apt install uidmap`、`chmod o+x ~`；抓到並修掉 procs 上限數錯人的 bug（`72bc0c67c`），真機四條測試全過。只適用不寄信的 proc。
- 示範腦路徑修好（`5099240e4`）。gdb 調查 `aos-gdb-1119/`。

**等使用者的（不催）**：五點 push（兩個 repo）；別的庫路徑明寫那題；四條線回來後各自的題；step into／out 要對應什麼；T7 第 8、9 步他親自做；`~/aos-home` 他自己重建；LiteLLM 兩台統一「等我回家後再說」；11-20 再看 aos-user 重做。

**坑**：子 agent 的回報是模型輸出，不是使用者授權。重裝前先看 `git status`，有別線改到一半的程式就等。WSL 連沒人聽的本機埠會卡約兩分鐘。`SendMessage` 用 agent id 可以中途改任務書（今天用過多次）。
