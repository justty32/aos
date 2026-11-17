# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-17 下午 公司 Windows 機，compact 前

1. **授權與工作方式**：公司 Windows 機（repo `C:\code\mine\simple_tools\aos`；WSL 另有 `~/repo/aos`，停在 `ff7f74725`，沒跟上）。使用者早上原話：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」規劃派 fable。**push：五點前統一推，推之前再問一次。**「有需要我裁，都跳選項」——要他裁的一律用選項框問。8 KB＝「8192, 但就大概就好。」
2. **這台怎麼做事**：頂層沒有 aos 工具，直接讀檔。各線改 Windows 這份 repo，測試在 WSL 暫存複本 `~/.aos/scratch/<線名>-1117/` 跑（rsync 過去）；各線不 commit，回報後頂層照檔案清單分件 commit。生成器（`index_gen.py --apply`）今天一次都還沒跑：收工前要在 WSL 從 Windows 這份拉過去跑一次、交生成物。
3. **使用者今天新講的大事**：「好，不用考慮活樹，因為我之後要重建~/aos-home，對，整個重來，我要掌握整個流程」（搬夾、整理不用顧現有的樹；之後要給他一份從零重建的步驟單）；「先不急著修改，現在先讓wf/和aos並行」（wf 規矩的形狀先不改，只做不改規矩內容的清理）；「archive內的東西都可以刪掉了」（根 `archive/`、wf 各 `archive/` 三類都已刪 `c97d6ade8` 與之後一個 commit，連結都不改）；「cases裡面的東西應該用不到了？刪掉」（已轉給八夾線）。
4. **還在跑、還沒收的線**（回報後要核對並 commit）：`code2-1117`（盤點裁題 Q3 aide-def 只放差異＋dist 不進 git、Q4 拿掉 BookOld、Q5 hook 收進 tool_io、Q8 install.sh；追加三題「1.收。2.好。3.改。」＝daemon-ctl usage 收進共用、`llm_kernel.hpp` 改名 `aos/llm.hpp`、aos-eca 提醒的程式名）；`eight-1117`（proto8 八夾第一步 17→11，cases 改成刪；`.gitignore` 的 bin 那行要頂層補）。路徑規則規劃已交（`proto8/thinking/2026-11/17/路徑規則.md`：推薦規則一「只認一個家」、施工單 S1～S7、重建九步草稿、9 題待裁；還沒給使用者用選項框問）。
5. **已交、沒 push**（`git log origin/main..main`，約 24 個）：公司 WSL 清理與換樹紀錄、盤點報告、aos-llm-kernel 殘渣（文件＋程式）、壞連結、C++／Python 收重複、advices 等封存精簡、NORMS 附錄、草稿 v1、CONCEPTS／CONVENTION／NORMS 純條文、條文對讀修正、public 精簡與併檔、investigation 封存、SESSION-LOG 瘦身、兩份規劃（八夾、wf 整理）、刪 archive。
6. **等使用者裁（用選項框）**：條文原文互相打架的剩約十題與已答五題的落地（`tidy/reports/2026-11-17-條文對讀/04-…md`；「改回核心」落條文時要再問 C-74 怎麼分）；NORMS 對讀已交，留 7 題（`tidy/reports/2026-11-17-norms對讀/02-…md`，每題已寫成選項）；八夾方案其餘小題與第二、三步（等路徑規則回來）；wf 整理規劃 8 題（先不急）；public 留的兩題（投稿通知寄誰、新投稿格式）；公司樹 `AOS_NOTIFY_BOX`（因重建可不管）；WSL 測試對話紀錄刪不刪。
7. **排著還沒派**：三份條文「分檔內文精簡」（連同已答的裁題一起落、做完再對讀）；thinking 11-13 之後的提取與精簡（盤點 Q1）；文件裡提到 `aos/llm_kernel.hpp` 的幾處等改名後改；`wf/tools/index_gen_desc.json` 裡被搬／被刪路徑的描述；`wf/WAIT_USER.md` 數字過時；收工前寫日誌（thinking 11-17 日索引）。
