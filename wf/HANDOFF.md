# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-04 傍晚下班（公司 Windows；回家開新 session 接）

1. **授權**：今天隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。**鐵律 1 已刪**（使用者「這個鐵律刪掉，不用ctest」）：驗證＝build 得過＋手跑，見 [testing](workflows/testing.md)。多個 agent 同工作樹一律用 `GIT_INDEX_FILE` 暫存 index 建 commit；不少 agent 直接 push、不動本機 main ref，頂層要自己把本機 main 對齊 origin。
2. **今天做完並 push**：aos-post 改版收尾與全套驗證；tidy 補對讀、round 條文 13 條照建議落；demo 只留 eca-claude、archive/topdown 刪；aos-eca-turn 開場白改 `--prompt`（沒給＝沒開場白）；thinking 改「月/日/子項」結構並拆大檔；proto8／wf 大檔拆分；舊 proto1～7 封存到根 `archive/`、活文件連結拿掉、code map 舊分冊移出；loop/fsm agent（`demo/agent-fsm`）；**aos-agent 統一介面**（`extras/agent/bin/aos-agent`、`interfaces.json` 宣告、screen／tools／llm 子介面、副本 vs 定義〔`aos-tools`／新 `aos-llm` 改定義〕、`--target`／`AOS_AGENT`、chat、`using-aos-agent.sh`、`AOS_DAEMON_STACK`→`AOS_DAEMON`、daemon 表多 `exec` 與 `def` 欄）；aos-say／aos-listen／aos-eca 刪；四元素審查（[four-elements](../proto8/thinking/2026-11/04/four-elements/README.md)）十題裁定、07 前 5 步做完；**全部測試與 ctest 刪光**（c90f8617）。說明頁 https://claude.ai/artifact/AqwFbS1gLPCwJriyjAdKNA （使用者通勤 review）。
3. **明天要接**：
   - 四元素 08 步 5～8（4 步：aos-tools 題 1／8、daemon 題 6／5 後半／3、daemon-ctl add 看 json 題 4、N-63 表題 2）：aos-agent 已收工、可以做，使用者「明天再說」 → [08](../proto8/thinking/2026-11/04/four-elements/08-實作步驟-等aos-agent後.md)。
   - `AOS_BRAIN_*` 改放哪：使用者 11-04 晚給了方向（問腦＝寄信給 llm kernel、非同步、aos-llm／aos-tools 當基礎工具），fable 設計與步驟在 [think-as-function](../proto8/thinking/2026-11/04/think-as-function/README.md)，等使用者看 05 的兩衝突兩方向題。
   - 使用者 review artifact（設計總覽 https://claude.ai/artifact/AqwFbS1gLPCwJriyjAdKNA 、指令參考 https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ）後的回饋；試驗場 `env.sh` 第 13 行使用者自己改成 `AOS_DAEMON`（WAIT_USER）。
4. **雜項**：LM Studio 伺服器頂層用 `lms server start` 開在 localhost:1234（qwen3-1.7b），試驗場 `agents/fsm_ann` 用它；WSL clone 已到 f56635ab、aos-daemon 已重建。eca-claude-dir 調查使用者裁「全部都是自己要承擔的風險」。

## 2026-11-03 晚收工（家機 Manjaro；明天開新 session 接）

1. **授權**：今晚隨意 push、普通事 opus、簡單與雜活 sonnet、規劃 fable、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent；新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。commit 一律 `git commit --only -- 路徑` 或 GIT_INDEX_FILE 暫存 index（今晚頂層一次不帶路徑的 commit 把 tidy 兩批包走：eb4dea91）。
2. **今晚做完並 push（main）**：三 commit 合跑全套已驗；daemon 收工 sleeping／開門 wake（`68c4e258`，不開放 sleep／wake 指令）；wake 後 ws 欄修好、`--enable-logs` 與 Ctrl-C 收工寫進 README（`6d42a264`）；封存瘦身候選到 `proto8/archive/`、刪 agent-fay（`c3cbf617`）；刪 round 那套 agent 與 aos-ai 只留概念（`cb6b49e0`，`proto8/archive/agent-round-concepts/`；aos-mcp、aos_ws、aos-say／listen 留著，使用者選「先留著」等 aos-agent）；tidy 收斂多批（W0～W4、P5、N-28 與 P1-1 摺 NORMS、P4-A～C thinking 精簡，狀態全在[收斂報告](workflows/tidy/reports/2026-11-03-收斂.md)）；家機試驗場 `~/code/playground` 清空重建成只玩 eca（daemon＋bob〔claude haiku、clock 工具〕，README 一步步）；aos-eca-turn 手冊頁 https://claude.ai/artifact/GsAZQHDCN7wHDUP3vvS78h 。
3. **明天要接**：
   - **aos-post 改版**（使用者「都照建議」，[thinking](../proto8/thinking/2026-11/03/aos-post/README.md) 檔末「實作進度（11-03 晚收工）」）：步驟 1～8 已在 main（`5e2fe35e`，已 push）。**併進 main 時沒跑驗證**（使用者「不用測試，總之先弄進去」），明天補跑全套與主工作樹 impls 重建（試驗場用的 bin 還是舊版）；剩步驟 9 條文加註（N-14～16、C-48、C-54 `…Exists`、P-42／P-43）、10 的舊名 grep 檢查。
   - **tidy 收斂**：照報告接；P4-D／P4-E 12 份 thinking 精簡未對讀就進了 main（`6c960429`，使用者「不對讀，直接進 main」「反正有需要的話再去翻舊的commit」），明天補對讀；P2 CONVENTION 的心得已記報告；NORMS 05（N-14～17）與 C-54 等 aos-post 加註完再摺；round 已刪後沒實作對應的條文清單在 SESSION-LOG，要給使用者看。
   - 使用者說「明天我通勤時候看」：aos-eca-turn 手冊頁。
4. **雜項**：試驗場兩個 daemon 同資料夾＝使用者「這是使用者自己要承擔的風險」；寫 ctl.json stop 同內容第二次不生效＝使用者選收工用 Ctrl-C。公司那邊：WSL clone 裡 `ask_round/_tooldef.json` 的改動直接丟（ask_round 已刪）、Windows 兩檔舊改動丟掉、`agents/amy` 刪。

