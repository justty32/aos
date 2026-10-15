# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-15 晚（新 session）

1. **授權**：「今天可以隨意push」；事情交給子 agent、頂層只交流，需要思考的派 fable。
2. **正在跑**：inst-exec 第三版（fable，`proto8/thinking/2026-10-15-inst-exec-v3.md`；使用者要 `aos-exec TARGET 旗標 -- argv`、aos-exec 不寫檔不懂 agent、「整套重新思考」）；principles 2／4／5／6 切乾淨＋**KISS 納進最高原則**（fable，改規範與程式）；畫家 demo LiteLLM 實跑（sonnet）；KISS 全面審視 8 份稿（fable ×8，`proto8/thinking/2026-10-15-kiss/`，只寫稿、索引待彙整）。
3. **使用者新定**：KISS 最高原則；層徹底切割（agent 不知道工具內部、fsm 不讀格 stderr、daemon 不驗子 inst、上層不知道格是不是 fsm；「想要看子層的東西請另外透過其他機制，沒機制就別碰」）。

## 2026-10-15 深夜（使用者關 session 前）

1. **授權**：當晚在家；「可以隨意的 push」；事情交給子 agent、頂層只跟使用者交流；需要思考的派 fable。新 session 照 user.md 重問 push。
2. **正在討論**：inst 路徑／stdin／TARGET 重設計，已定與未定見 [SESSION-LOG 最新進度第一條](SESSION-LOG.md#最新進度) 與稿 [inst-exec-v3](../proto8/thinking/2026-10-15-inst-exec-v3.md)（第三版，未決 A～L 等使用者看；第二版被打回）。要點：aos-inst 只吃 stdin、TARGET 全拿掉、aos-exec＝最小語法糖（不 cd、不寫檔、不認得 agent）、agent 定義隨 inst 走（frame.json 退場）、工具＝黑箱 inst；使用者追加 KISS 最高原則、層徹底切割。compact 後我曾忘記 N-12（stdin 才是標準）與 C-48（指示詞不進正規設計），被使用者拉回——設計題先讀這兩條。
3. **當晚新定**：C-52～C-56（C-56 KISS＝最高原則，深夜；C-52 加嚴成「切乾淨、沒機制不碰、上層不知道下層是什麼」）、N-43 改寫、N-37 多 `next: null`、N-38／N-40／N-28 依切乾淨改、abbr.json；改名批次（val、P1～P7、M1～M9）已推。
