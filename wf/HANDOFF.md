# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-04 夜收工（家機 Manjaro；明天開新 session 接）

1. **授權**：今晚隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。push 時好時壞被 GitHub 拒（publickey），重試就過。
2. **今晚做完並 push（main）**：四元素 08 步 5～8；tidy 收斂多批（[報告](workflows/tidy/reports/2026-11-03-收斂.md) 05～08：send_message／memory 與 resident-bob 封存、整份 AI 產出的 thinking 刪、P-23／P-28／P-42／C-61／N-14／P-20 裁定落實、2026-11/03 thinking 精簡完）；aos-agent `where` 預設 `--stack`、`--ws` 另指；**思考是 aos 函數**（[think-as-function](../proto8/thinking/2026-11/04/think-as-function/README.md)：問腦＝寄信給 llm kernel、收回信，kernel.json 代號表、`aos-llm` 成基礎工具、`AOS_BRAIN_*` 退場；05 四題使用者全選推薦；換腦只留 `llm.json` 代號、`AOS_KERNEL` 只當 hub；舊信處理完就刪 `6a2e0880`）；試驗場 `~/code/playground` 照新做法備好＋桌面 `/home/lorkhan/Desktop/aos-試驗場教學.html`；邊緣狀況三條線（A llm kernel [08](../proto8/thinking/2026-11/04/think-as-function/08-邊緣狀況實測.md)、B daemon／aos-agent [four-elements 09](../proto8/thinking/2026-11/04/four-elements/09-邊緣狀況實測-11-04-夜.md)、C 基礎積木 [edge-basics](../proto8/thinking/2026-11/04/edge-basics/README.md)）共修十幾個 bug。使用者口徑「很多都是自己要承擔的風險」「風險自擔」，只有 add 被拒照推薦（`AddRejected`，`cac45dc0`）。
3. **明天要接**：
   - **impls 還沒重建**：C 線改了 aos-exec、aos-post、aos-tools、aos-json 原始碼（`3a28f5fa`、`c193edbb`、`5183b00a`、`78822851`），aos-loop、aos-fsm、aos-daemon、aos-llm-kernel 把 aos-exec／aos-post 編在裡面；使用者在打遊戲沒跑。明天從 repo 根 build 一次、impls 全部重建（[testing](workflows/testing.md)），試驗場才吃到新版。
   - edge-basics 題 1（aos-mcp 工具失敗時要不要把 stderr 尾巴給 Claude，牽涉 C-56 例外）等使用者 → [WAIT_USER](WAIT_USER.md)。
   - 使用者親手試試驗場真腦（LM Studio／LiteLLM）與 `aos-agent open` → WAIT_USER。
   - kernel 的 `served.jsonl` 還留著：使用者說「舊信根本不用留，就是刪」，頂層解讀不含這行紀錄，待他確認 → WAIT_USER。
   - `ask` 被打斷時回信殘留在 `$AOS_KERNEL/reply/new/` 的窄縫已記成已知限制（08 題 3 定案段），不追。
4. **雜項**：桌面 `/home/lorkhan/Desktop/aos-進度-11-04晚.html` 是進度頁，已過時、可刪（repo 外，沒動）。收工時查過：沒有留著的 aos-loop／aos-daemon／aos-llm-kernel／假伺服器背景程序。

## 2026-11-04 傍晚下班（公司 Windows；回家開新 session 接）

1. **授權**：今天隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。**鐵律 1 已刪**（使用者「這個鐵律刪掉，不用ctest」）：驗證＝build 得過＋手跑，見 [testing](workflows/testing.md)。多個 agent 同工作樹一律用 `GIT_INDEX_FILE` 暫存 index 建 commit；不少 agent 直接 push、不動本機 main ref，頂層要自己把本機 main 對齊 origin。
2. **今天做完並 push**：aos-post 改版收尾與全套驗證；tidy 補對讀、round 條文 13 條照建議落；demo 只留 eca-claude、archive/topdown 刪；aos-eca-turn 開場白改 `--prompt`（沒給＝沒開場白）；thinking 改「月/日/子項」結構並拆大檔；proto8／wf 大檔拆分；舊 proto1～7 封存到根 `archive/`、活文件連結拿掉、code map 舊分冊移出；loop/fsm agent（`demo/agent-fsm`）；**aos-agent 統一介面**（`extras/agent/bin/aos-agent`、`interfaces.json` 宣告、screen／tools／llm 子介面、副本 vs 定義〔`aos-tools`／新 `aos-llm` 改定義〕、`--target`／`AOS_AGENT`、chat、`using-aos-agent.sh`、`AOS_DAEMON_STACK`→`AOS_DAEMON`、daemon 表多 `exec` 與 `def` 欄）；aos-say／aos-listen／aos-eca 刪；四元素審查（[four-elements](../proto8/thinking/2026-11/04/four-elements/README.md)）十題裁定、07 前 5 步做完；**全部測試與 ctest 刪光**（c90f8617）。說明頁 https://claude.ai/artifact/AqwFbS1gLPCwJriyjAdKNA （使用者通勤 review）。
3. **明天要接**：
   - 四元素 08 步 5～8（4 步：aos-tools 題 1／8、daemon 題 6／5 後半／3、daemon-ctl add 看 json 題 4、N-63 表題 2）：aos-agent 已收工、可以做，使用者「明天再說」 → [08](../proto8/thinking/2026-11/04/four-elements/08-實作步驟-等aos-agent後.md)。
   - `AOS_BRAIN_*` 改放哪：11-04 晚已照 [think-as-function](../proto8/thinking/2026-11/04/think-as-function/README.md) 推薦實作（四題可翻案，見 [07](../proto8/thinking/2026-11/04/think-as-function/07-實作結論.md)）；剩使用者看一眼與試驗場親手試（WAIT_USER）。
   - 使用者 review artifact（設計總覽 https://claude.ai/artifact/AqwFbS1gLPCwJriyjAdKNA 、指令參考 https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ）後的回饋；試驗場 `env.sh` 第 13 行使用者自己改成 `AOS_DAEMON`（WAIT_USER）。
4. **雜項**：LM Studio 伺服器頂層用 `lms server start` 開在 localhost:1234（qwen3-1.7b），試驗場 `agents/fsm_ann` 用它；WSL clone 已到 f56635ab、aos-daemon 已重建。eca-claude-dir 調查使用者裁「全部都是自己要承擔的風險」。
