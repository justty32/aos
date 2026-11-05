# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-05 收工（公司 Windows＋WSL；明天開新 session 接）

1. **授權**：今天隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable（fable 可再開 fable）；做事的 agent（雜活除外）先讀 wf 規矩。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。WSL clone 與 Windows 工作樹都對齊 origin；**一律在 WSL 改檔**（Windows 端改會掉 +x）；殺程序只用自己記的 pid，別用 `pkill -f`（B 線誤殺過別 session 的程序）。Windows 工作樹 stash 有兩筆舊副本（內容都比 origin 舊，可丟）。
2. **今天做完並 push**：portable-flow（相對 daemon stack、sleep/wake、DaemonRunning、tools 只存差異、ctl 收進 `aos-agent ctl`）；kernel-daemon（llm kernel 一台 daemon、`AOS_LLM_KERNEL`＝它的 stack、問腦掛 daemon 下 proc、判官兩模式）；兩輪邊緣測試（edge-llm／daemon／agent／round2，約 30 處修）；feat-proto 五件（self_tools、能力包、priority 排程、agents new／add＋配額、limits）；層級式記憶 `memory`＋`proto8/knowledge/aos/`；程式輸出全英文＋三扇門與結束碼統一（stdio-unify）；say 讀 stdin；新規矩：proto8 沒有舊版、輸出格式只在共用介面改。試驗場 `~/code/playground`（WSL）與桌面 `aos-試驗場教學.html` 已更新到 317a88f9 前狀態；桌面另有 `aos-三扇門與結束碼.html`。**每日進度頁「本日進度」**：https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd （之後每天更新這份，用 `url` 參數）；新功能說明頁 https://claude.ai/artifact/LoFTkSuuFREyGksrEzfpqy 。
3. **明天要接**：lib 工具 die 收成共用模組（使用者已裁「收成共用模組」）→ [stdio-unify](../proto8/thinking/2026-11/05/stdio-unify/README.md#剩下的)；知識庫接三種 agent、工具說明改寫 K1～K8 → [agent-knowledge](../proto8/thinking/2026-11/05/agent-knowledge/README.md)；`thought` 工具實作 T1～T6 → [small-thought](../proto8/thinking/2026-11/05/small-thought/README.md)；之後找時段做架構大重構（先 fable 規劃）。等使用者：真腦（LM Studio）、`aos-agent open` 畫面 → WAIT_USER。

## 2026-11-04 夜收工（家機 Manjaro；明天開新 session 接）

1. **授權**：今晚隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。push 時好時壞被 GitHub 拒（publickey），重試就過。
2. **今晚做完並 push（main）**：四元素 08 步 5～8；tidy 收斂多批（[報告](workflows/tidy/reports/2026-11-03-收斂.md) 05～08：send_message／memory 與 resident-bob 封存、整份 AI 產出的 thinking 刪、P-23／P-28／P-42／C-61／N-14／P-20 裁定落實、2026-11/03 thinking 精簡完）；aos-agent `where` 預設 `--stack`、`--ws` 另指；**思考是 aos 函數**（[think-as-function](../proto8/thinking/2026-11/04/think-as-function/README.md)：問腦＝寄信給 llm kernel、收回信，kernel.json 代號表、`aos-llm` 成基礎工具、`AOS_BRAIN_*` 退場；05 四題使用者全選推薦；換腦只留 `llm.json` 代號、`AOS_KERNEL` 只當 hub；舊信處理完就刪 `6a2e0880`）；試驗場 `~/code/playground` 照新做法備好＋桌面 `/home/lorkhan/Desktop/aos-試驗場教學.html`；邊緣狀況三條線（A llm kernel [08](../proto8/thinking/2026-11/04/think-as-function/08-邊緣狀況實測.md)、B daemon／aos-agent [four-elements 09](../proto8/thinking/2026-11/04/four-elements/09-邊緣狀況實測-11-04-夜.md)、C 基礎積木 [edge-basics](../proto8/thinking/2026-11/04/edge-basics/README.md)）共修十幾個 bug。使用者口徑「很多都是自己要承擔的風險」「風險自擔」，只有 add 被拒照推薦（`AddRejected`，`cac45dc0`）。
3. **明天要接**：
   - **impls 還沒重建**：C 線改了 aos-exec、aos-post、aos-tools、aos-json 原始碼（`3a28f5fa`、`c193edbb`、`5183b00a`、`78822851`），aos-loop、aos-fsm、aos-daemon、aos-llm-kernel 把 aos-exec／aos-post 編在裡面；使用者在打遊戲沒跑。明天從 repo 根 build 一次、impls 全部重建（[testing](workflows/testing.md)），試驗場才吃到新版。
   - edge-basics 題 1（aos-mcp 工具失敗時要不要把 stderr 尾巴給 Claude，牽涉 C-56 例外）：**11-05 使用者選「附 stderr 尾巴（推薦）」，已落實**（例外寫在 C-52／C-53）。
   - 使用者親手試試驗場真腦（LM Studio／LiteLLM）與 `aos-agent open` → WAIT_USER。
   - kernel 的 `served.jsonl` 還留著：**11-05 使用者選「也刪」，已落實**（kernel 不再寫）。
   - `ask` 被打斷時回信殘留在 `$AOS_KERNEL/reply/new/` 的窄縫已記成已知限制（08 題 3 定案段），不追。
4. **雜項**：桌面 `/home/lorkhan/Desktop/aos-進度-11-04晚.html` 是進度頁，已過時、可刪（repo 外，沒動）。收工時查過：沒有留著的 aos-loop／aos-daemon／aos-llm-kernel／假伺服器背景程序。
