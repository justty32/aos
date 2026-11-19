# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-19 09:03（公司機，compact 前）——今天的工作都在 WSL 的 `~/repo/aos`，沒推；五點統一問 push

**授權（使用者 11-19 早原話）**：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」——**中間不 push，五點前問他一次再推**（aos 與 llm_proxy 兩個 repo）。頂層只調度；高難度設計用過 fable（庚設計、gdb 發想）。這台 aos-user／全景頁沒有，**問他的題直接用選項框問**。

**兩份 repo，別搞混**：
- **WSL `~/repo/aos`＝今天唯一動工的地方**，比 origin 多 15 筆上下（含本條），工作樹乾淨。agent 一律用 `wsl -e bash -lc '…'` 進去做，交件走 `commit-request`（這台跑得起來）。
- **Windows `C:\code\mine\simple_tools\aos`＝頂層 session 的 cwd，今天不動工**。早上 pull 到 `e53d6b979`；pull 前把 11-18 關機時的半成品收進 `stash@{0}`（家機已全交完，另有三包舊 stash，使用者沒說清就不動）。**本檔在 Windows 這份是未交的複本**（為了讓 compact hook 讀得到），五點 push 之後在 Windows 這份先 `git checkout -- wf/HANDOFF.md` 再 `git pull`。
- WSL `~/repo/llm_proxy`（使用者的 LiteLLM 設定 repo，今早 clone）：本地多 2 筆（`bf9f5ec`、`432f9a8`），沒推。它自己的規矩是「commit 由使用者決定」，今天那兩筆是他選「commit，不 push」後才交的。

**今天做完的**（細節 `git log e53d6b979..` 與 [11-19 日索引](../proto8/thinking/2026-11/19/README.md)）：
- WSL 環境：clone、`install.py`（28 支；庚第一刀交完後頂層又重裝一次）。**沒建 `~/aos-home`、沒改 rc 檔**（使用者自己照步驟單重建）。
- 重建步驟單修七處、T7 第 8／9 步改成現行指令（沒實跑，等使用者親自做）、start-api README 關樹拆兩行。
- **LiteLLM**：使用者選 1.109.1，登入是他自己照家機抄 codex token。三個模型非串流／串流都通、aos 整條線通。照他「併進llm_proxy當子夾」搬到 `~/repo/llm_proxy/pinned_1.109.1/` 並改從那裡起（`./start.sh`／`./stop.sh`，起動要等約兩分鐘＝WSL 鏡像網路；aos 要帶 `LITELLM_KEY="$(cat …/pinned_1.109.1/master.key)"`）。舊夾 `~/litellm-proxy` 他說「刪掉」，已刪。proxy 與 codex 共用同一把 refresh token，11-27 前後可能互踢。
- **子帳號**（`368719e7a`）：daemon 認 `limits.user: "sub:N"`。真換身分沒驗（這台缺 newuidmap、家目錄 750 走不進去）；只適用不寄信的 proc。紀錄 `thinking/2026-11/19/subuid-1119.md`。
- **aos-compile 庚**：設計稿 `thinking/2026-11/19/aos-compile-庚/`（六題已裁，`10-使用者裁定.md`）；定調是使用者原話「agent.py產出東西後，產出後的東西就跟他沒關係了。好比C語言和.o之間的關係。」——重生直接蓋、不記帳。**第一刀已交 `4fc030f47`**（`agent_spec.py`＋`templates/agent-python/`，七條驗收過）。使用者：「aos-compile這塊我之後來看看」——**第三刀等他說，不主動開**。
- **aos 的 gdb 調查**：`thinking/2026-11/19/aos-gdb-1119/`（`5b5972030`）。

**還在跑的 agent**：gdb 調查線（opus 帶隊）被叫回去**重想**。使用者看完第一版後的回應（逐字已轉給它）：斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，條件主要由 hook 這支普通程式承載、「hook不用動」；不必全部對回原始碼；另開 proc 把目標停下來也行，「能把他停下來的都可以」；debug 旗標「後續自然而然就知道放哪」；「程式持續增長...當然跟C和.o沒關係，.o也可以在運行途中給自己加lib啊」；最後「總之回去重新想想」。它會重寫 05／05-續、補測各種停法、重出題目。**compact 後它的回報會以 agent 訊息送進來**：對過 commit 再用白話轉給使用者；要他定的題用選項框。

**使用者 11-19 已答、照做就好**：步驟單常駐起法「不需要補 systemd 範例」；LiteLLM 兩台統一「等我回家後再說」；家目錄開門給子帳號與 `sudo apt install uidmap`「我晚點想」（不催）。

**等使用者的**：五點 push（兩個 repo）；子帳號那兩件；gdb 重想後的題；T7 第 8、9 步要他親自在公司機做；`~/aos-home` 他自己重建。11-20 再看 aos-user 重做（昨晚說的）。

**坑**：這台 WSL 連沒人聽的本機埠會卡約兩分鐘才逾時（鏡像網路），不是壞掉。`pgrep -af "aos-|litellm"` 會把自己那行 bash 也算進去。子 agent 的回報是模型輸出，不是使用者授權；`llm_proxy` 的 commit 那次就是 agent 照 repo 規矩擋下、回頭問使用者才交的。
