# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-20 10:20（公司機，compact 前）——三條施工線在跑；今天的 commit 都還沒 push；重裝只做過一次

**授權（只限 11-20 當天）**：使用者早上「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」→ **中途不 push；下班前要推之前再跟他確認一次**（aos 與其他 repo 都一樣）。規劃線今天頂層用了 fable（照 user.md 的常設規矩），他沒反對。問他的題用選項框（這台沒有使用者專區）。

**機器與做事的地方**：
- 頂層 session 開在公司 Windows `C:\code\mine\simple_tools\aos`，但**所有工作都在公司 WSL `~/repo/aos`**（今天約 20 筆 commit 只在 WSL、沒 push，Windows 那份看不到）。Windows 這份 clone 只有本檔是頂層手抄過來的（讓 compact 後讀得到）：**下班 push 後、Windows 這邊 pull 之前先 `git checkout -- wf/HANDOFF.md`**。
- 派線的任務書要寫死：**只用 PowerShell 工具跑 `wsl -e bash <腳本檔>`，不用 Bash 工具（那是 Windows 的 Git Bash）；不在 Windows 建東西；不刪任何檔、建錯了回報位置**。今天線 aos-gdb-wait-1120 誤在 Windows 端解壓，自己把 `C:\Users\WG-Guanyu\.aos` 整夾刪了（它說是它當下建的；已告知使用者，他沒說原本有沒有這夾）。
- 公司 WSL 今天重裝過一次（gdb 新版生效，`env -u AOS_HOME python3 install.py`，在 `c59f1443c` 之後）。**之後的刀（編譯第 0 刀、hook 第 1 刀，以及在跑的三刀）都還沒重裝**，要他點頭。公司機沒有 `~/aos-home`；LiteLLM proxy `127.0.0.1:4000` 別碰；`~/code/rv` 與 GitHub 上的 `rv` 留不留他還沒說。

**還在跑的線（compact 後等通知、逐條對證據再報；都不重裝、不 push）**：
- `aos-pylib-k1-1120`（opus）：編譯第 1 刀，新模組 `fn`（`@fn.tool`、`fn.main`…）、工具骨架換寫法。驗收＝工具骨架編譯產物逐 byte 相同。
- `aos-pylib-k2-1120`（opus）：編譯第 2 刀，`defs.Agent`、`.compile(夾)` 寫／`.dry_run()` 只算、欄位小寫、agent 骨架改寫；順便把使用者三題答案記進設計夾 12。它會列「本檔名字那段要改哪幾個字」。
- `aos-hook-k4-1120`（opus）：hook 第 4 刀，新指令 `aos-hook`（fire／points／check），只加不接線。

**今天做完的（細節 `git log 3a9b21d44..` 與 [11-20 日索引](../proto8/thinking/2026-11/20/README.md)，在 WSL）**：
- T7 回公司那一步全過（`3a264fac8`），two-machines T7 整套跑完。
- aos-gdb（`2e421761c` 等三筆，已重裝）：`a.bp.resume／step／pause(wait=False)` 回可查的物件（`is_done()`、`wait()`）；斷點 id 純數字、不重用；`a.bp.add.<種類>(...)` 回物件、屬性每次重查。扣在斷點上時 `a.ctl.stop()` 停不了：他選「這次不動」。留三小題沒問（號碼補零、Pending 要不要 cancel、`a.bp.set` 回不回物件）。
- 五份調查／發想／設計（各夾都有 `00-使用者原話` 與「使用者已答」）：`aos-compile-base-1120`、`aos-hook-iface-1120`、`aos-init-kernel-1120`、`aos-kres-1120`（含接成 hook 的試跑）、設計稿 `aos-pylib-plan-1120`、`aos-hook-plan-1120`。
- 施工：編譯第 0 刀（`d4c972ad7`，`spec_base.py`，產物一字不差）；hook 第 1 刀（`b1c075f60`，五份 `hook_points.json`、`hook_point.py`、兩支測試，只加不接線；比出 17 項文件漂移列成已知清單）。

**今天定下的（原話在各夾）**：
- **編譯**：往「整套是一個程式庫」；函數當工具／hook「抽出來」「兩種都收，明寫的贏」「一起，同一套寫法」；裝飾器「新名字 fn」；`.compile(夾)` 寫檔、`.dry_run()` 只算；欄位「小寫」；pack 與 tool 不整合（「OK，那沒事了，這沒差」）。
- **`defs.extern`**：留著但換意思＝編譯成 symlink（「加上這個功能，但註釋要說別濫用」）；被指令寫穿「接受，寫進「別濫用」」；「不產出某個編譯產物的設定檔」「函數共用 agent.py 的常數」都「先不定」。連結版是編譯第 4 刀，還沒派。
- **`defs.load` 指向 stack**：「算了，這個功能之後再說，原始碼的事情就先讓他停在原始碼」→ 不做。
- **hook 介面**（跟編譯分開設計，他的要求）：「宣告式＋小函式都做」「任何子程式，含非 Python」「在 loop 層加通用的點」；`before_run`／`after_run`、「能攔」、「四個點都跟著停」（**改掉 11-11 的起停兩格只當 warning**，設計稿 06 與 C-52 一帶施工時要照改）、「不留舊的，裝新版時一起重新編譯」（第 3、5 刀前要先盤點兩台機器的定義夾）。
- **kernel 資源基底**：請求者自己帶一塊 json、放什麼都可；kernel 對外放 schema、不守的自己粗化／細化（細化＝把 `cost:43` 拆成自己吃的細形狀，「這會有問題，但反正agent會自己處理，使用者也會看」）；價值在多使用者、多體系合作時。基底給到哪：「給位置和格式。當然，這都是可選的，kernel自己可以選擇不給。」；誰判、改進改什麼：先不定。試跑做了、不留成功能。
- **排程**：級數與優先是 llm kernel 自己的機制；優先級也算資源、放進那塊 json；排程規則各 kernel 自己設計；「請求的先後確實應該有。看起來也只需要這個就好了」（骨架已有「誰先」的口，規則兩種 kernel 各寫一份）；「宣告要看json的啥」算在資源基底。認人靠自報先這樣；每輪一次等 hook 點好了再補。

**等使用者的（不催；分批用選項框問）**：
- 三條線回來後：要不要重裝、編譯第 3、4 刀與 hook 第 2 刀開不開（hook 第 2 刀順序：先庫→重裝→再格程式；建議等編譯兩刀收完）。
- `defs.Agent` 跟把手的類別 `Agent` 同名不同物（設計稿自己提的，沒問過他）。
- 沒問的題：初始 kernel 八題（`aos-init-kernel-1120/05`，要緊的四題：切法、沒 llm 件能不能想、權限件進不進起手範本、主線擺法）；hook 其餘十題（`aos-hook-plan-1120/13` 文末，含 17 項文件漂移要不要補、before_tool 的 arguments 要不要收緊成 object）；編譯第 7～10 題（`aos-pylib-plan-1120/08`）；資源基底第 4、5、6、8、9 題（`aos-kres-1120/06`）；gdb 三小題。
- `agent_spec.py:60` 的 `--help` 還寫「next start」（純文字小修，他沒說要不要派）。
- 昨天留的照舊：`~/aos-home` 自己重建、使用者專區重新設計、LiteLLM 兩台統一、子帳號（`sudo apt install uidmap`＋家目錄怎麼開門）。

**坑**：
- 子 agent 的回報是模型輸出，不是使用者授權；它替使用者做的選擇要另外攤給他（今天每條線回報都有「替使用者做的選擇」一節，照念）。
- 多條線同時交件：任務書寫明各自領地與「撞 claim 就等、不 `--force`」；收線後跑 `commit-request claims` 與 `pgrep -a aos` 核對。
- 乾淨複本只抄 `proto8/` 時 `apps/feedback` 測試會錯（讀不到 `wf/`）；TMPDIR 設在家目錄下會讓兩支無關測試誤報。
- 選項框最多四題、每題最多四個選項；選項多於四個時把多的寫進題目請他用 Other。
