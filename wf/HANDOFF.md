# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-16（公司 WSL）

1. **授權**：今天「隨意 push」；在公司 WSL；事情交給子 agent、頂層只交流；需要思考的派 fable。
2. **使用者叫停 KISS 批次**：撤回 10-15 深夜「都照推薦」、要重看（「我後悔惹QQ，等一下我想要重新看過」）。批次 1 已做可逐項翻案、批次 2～6 暫停 → [kiss/README 開頭註記](../proto8/thinking/2026-10-15-kiss/README.md)。
3. **C-56 本條改寫成「KISS 也是最後原則」**（使用者：不算子原則、合併進本條）：先滿足各類需求與其他原則，最後回頭把多餘的清掉；不拿「最乾淨、規則最少」抄近路 → [10-16 稿](../proto8/thinking/2026-10-16-kiss-last.md)。
4. **定義與工作區（食譜與廚房）已定、已寫進概念與規範，程式待改**：稿 [agent-inherit § 四](../proto8/thinking/2026-10-16-agent-inherit.md#四使用者決定10-16) 是唯一的決定清單（其餘節是 AI 提案）。新條 C-57～C-61、N-46～N-51（[分檔](../proto8/NORMS/10-基礎設施-定義與工作區.md)，草稿）；C-46、C-50 改字；N-27 後半被 N-50 取代、N-21～N-24 歸語法糖；沒點頭的 10 條在 [NORMS 待定](../proto8/NORMS/08-待定.md)。早上另定 C-56「最高也是最後原則」＋「寫什麼就做什麼」、N-26 `*_inherit` 還原。KISS 批次 2～6 要依新設計重看。
5. **KISS 重審五件拍板（10-16）已寫進概念與規範，程式待改**：[稿末尾](../proto8/thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)。新條 **N-52**（收到 SIGTERM＝優雅收工、做完該做的再結束、退 0；總則）、**N-53**（aos 的 agent 被外面 loop 一拍一拍驅動、定義不含 loop、連錯不數）、**N-54**（daemon 子項寫在 ctl 的 `children`）、**C-62**（agent 的定義＝一台狀態機，怎麼跑由誰跑不管）；**N-10 刪**；N-28 改（`adopt` 預設開、table 窗併進 state 窗）；N-43 改（翻 10-15 晚「loop 退 1」）；N-42 維持兩支。新待定 5 條在 [NORMS 待定](../proto8/NORMS/08-待定.md) 末段。

## 2026-10-15 晚收工（使用者：明早再來）

1. **授權**：當晚「今天可以隨意push」——**明早新 session 照 user.md 重問 push**。事情交給子 agent、頂層只交流；設計思考派 fable，且先通讀 CONCEPTS／NORMS（[proto8 README 規矩](../proto8/README.md)）；交稿頂層先對 N-12、C-48／N-45、C-56 KISS、層徹底切割、少用 sh。**不要一言不合改 workflow／memory**——要寫規矩先問寫哪。
2. **已定**：inst-exec 第四版 [v4](../proto8/thinking/2026-10-15-inst-exec-v4.md)——「C-50 選 a（JSON 是正本、資料夾只是拆檔），其他都按照推薦」：一個 agent 定義＝一張 inst（一份大 JSON）、aos-exec TARGET 必填不寫檔、`stdin_inline: true` 才內嵌、工具一律走 frame（args.json 進 ret.json 出）、agent 當工具 argv 直接 `aos loop`、frame.json 退場。KISS 彙整 [kiss/README](../proto8/thinking/2026-10-15-kiss/README.md) 六批全照推薦（含★翻案）；PLAN「刪掉」。
3. **批次 1「純刪」做完、已推**（含 C-50 改寫、刪 PLAN、proto8-1 併進 proto8/lib；四個 commit 見 git log，彙整總表已標「已做」；自定 8 條在 [10-15 session log](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)，最要看的是 `aos-demo` 的 AOS_DEMO 留到批次 2）。接著批次 2（v4 實作）→3 loop／daemon／窗→4 fsm／agent→5 kernel→6 文件，**依序、不平行**。
4. **當晚新定**：C-56 KISS 最高原則、C-52 加嚴、N-45（設計假設沒有指示詞，JSON 大沒關係）、user.md「少用 sh」、N-37 `next: null`、N-28／N-38／N-40 切乾淨。畫家 demo LiteLLM 實跑通過（[paint-live](../proto8/thinking/2026-10-15-paint-live.md)）。

## 2026-10-15 深夜（使用者關 session 前）

1. **授權**：當晚在家；「可以隨意的 push」；事情交給子 agent、頂層只跟使用者交流；需要思考的派 fable。新 session 照 user.md 重問 push。
2. **正在討論**：inst 路徑／stdin／TARGET 重設計，已定與未定見 [SESSION-LOG 最新進度第一條](SESSION-LOG.md#最新進度) 與稿 [inst-exec-v3](../proto8/thinking/2026-10-15-inst-exec-v3.md)（第三版，未決 A～L 等使用者看；第二版被打回）。要點：aos-inst 只吃 stdin、TARGET 全拿掉、aos-exec＝最小語法糖（不 cd、不寫檔、不認得 agent）、agent 定義隨 inst 走（frame.json 退場）、工具＝黑箱 inst；使用者追加 KISS 最高原則、層徹底切割。compact 後我曾忘記 N-12（stdin 才是標準）與 C-48（指示詞不進正規設計），被使用者拉回——設計題先讀這兩條。
3. **當晚新定**：C-52～C-56（C-56 KISS＝最高原則，深夜；C-52 加嚴成「切乾淨、沒機制不碰、上層不知道下層是什麼」）、N-43 改寫、N-37 多 `next: null`、N-38／N-40／N-28 依切乾淨改、abbr.json；改名批次（val、P1～P7、M1～M9）已推。
