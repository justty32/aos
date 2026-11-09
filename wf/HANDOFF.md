# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-09 深夜 23:xx 家機頂層（使用者開新 session）

1. **授權與狀態**：同下一條（隨意 push、opus／sonnet 分工、只用 e4b、不 load/unload、顯卡跑到 07:30）。使用者要開新 session。
2. **舊 session 留下的背景工作（新 session 先查還活著沒）**：
   - soak 長跑：腳本 `/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/74d55541-5004-44aa-b8d6-5fec53a393a2/scratchpad/soak/soak.py`（23:0x 剛啟動）；派它的 opus 隊長跟舊 session 一起結束，**沒人收報告**。查 `pgrep -af soak.py`；活著就由新 session 等到早上收、寫 `proto8/thinking/2026-11/09/soak-1109/`；死了就看使用者要不要重派。試驗場備份 `~/code/playground.bak-1109soak`。
   - 本地模型評比：隊長在修 report.py 重跑，同樣隨舊 session 結束，產物看 `proto8/thinking/2026-11/09/local-model-bench/`（可能未 commit）。
   - arcagi：22:30 回 PROGRESS（`wf/inbox/20261109T2230-arcagi-PROGRESS.md`，未處理），N1 蠟模、N2 CUDA 跑到 06:45，07:30 前回 DONE；看板 `~/repo/arcagi/notes/rounds/gpu-night-1109/`。它是使用者自己的 session，不受影響。
   - 23:0x 實測：LM Studio 只載 e4b、閒置，GPU 7%／6 W——整夜負載還沒起來。
3. **已裁（新 session）**：使用者「amber_sword不用跑。差異也不用補。」新 session 已派兩個 opus 接手 soak 與本地模型評比（背景跑，完成通知頂層）。無新條號。

## 2026-11-09 深夜 22:3x 家機頂層（compact 前）

1. **授權與狀態**：使用者在家、本 session 隨意 push；子 agent 普通 opus、雜活 sonnet，派前讀 wf 規矩（雜活除外）。使用者要睡了，要**顯卡跑整夜到明早 07:30**（天冷當暖爐，「不用降低負載」）。**LM Studio 一次只載一個模型照舊**（使用者 22:2x 選「照規矩，大家共用 e4b」）：只用 `google/gemma-4-e4b`；使用者自己開了 LM Studio 與 litellm proxy；他說要下載 qwen3.8 27B，今晚不評（16GB 塞不下、也違反一次一個）。
2. **今晚在跑的（背景子 agent，完成會通知頂層）**：
   - **soak 長跑**（opus 隊長）：家機試驗場 `~/code/playground` 真腦 e4b 三層整夜，注入 kill／sleep／poke／pause／SIGINT，取樣 RSS／fd／檔案大小；開跑前備份 `~/code/playground.bak-1109soak`；報告 `proto8/thinking/2026-11/09/soak-1109/`。
   - **本地模型評比**（opus 隊長）：今晚只評 e4b，題庫＋判準＋一鍵重跑腳本做紮實，其他模型待白天單獨測；報告 `proto8/thinking/2026-11/09/local-model-bench/`。
   - **arcagi**：已寄信 `~/repo/arcagi/wf/inbox/20261109T2228-aos-REQUEST.md`（使用者「兩個都試試看。cuda神經網路也是可以拿來符號邏輯，暴力搜索。」）：(1) 本地 e4b 大量鑄蠟模、比提示法擬合率；(2) CUDA 暴力搜尋雛形；S1 forbid 相依就一起。arcagi 的 agent 是使用者自己開的 session（可能要使用者叫它看信）。
   - **amber_sword**（`~/repo/narratives/amber_sword`，非 git repo、只能讀）：使用者提議「用 aos 知識庫去搞」，頂層誤當決定派了隊長、隨即停掉（沒寫任何檔）；**使用者還沒決定要不要今晚跑**。教訓：使用者說「不如…？」「幫我想想」是要討論，不是派工。
3. **白天的設計線**：使用者手寫大修，起點 repo 根 `impl_cpp/`（C++23、骨架取自 archive/aos-v1、`core/inst` 原封搬 v1，差異在 `impl_cpp/core/inst/差異.md` 待他決定補不補）。無新條號。使用者 22:3x 問「蠟模」是什麼（頂層已白話解釋）。

## 2026-11-09 晚 收工（家機 Manjaro）

1. **授權與狀態**：使用者在家、本 session 隨意 push；子 agent 普通派 opus、雜活派 sonnet，派前讀 wf 規矩。使用者累了、已收工。家機已跟上 11-09（impls 重建、install、試驗場改成只有根帶鐘，假腦自動驗過，`3670feaaa`）。
2. **設計**：使用者開始**親手大修**，起點 repo 根 [`impl_cpp/`](../impl_cpp/README.md)：骨架取自 `archive/aos-v1`、C++23（使用者先說 20、看到 v1 後改 23）、vcpkg（nlohmann-json、catch2）、Ninja preset debug／release／asan、`.vscode`；第一個零件 `core/inst` 照使用者「aos-inst 也從 aos-v1 拿」原封搬 v1 的 exec＋wire Inst 解析，跟現行 proto8 aos-inst 的差異攤在 `impl_cpp/core/inst/差異.md`，**補不補等使用者**。主角是使用者：agent 只搭環境、照吩咐搬，不替他寫核心。大修材料在家機桌面 `~/Desktop/aos-大修材料/`，第四批後 `proto8/` 沒改、免同步。
3. **新定條號與在跑的 agent**：無新條號；子 agent 都收了。
