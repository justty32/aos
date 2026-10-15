# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-15 深夜（使用者關 session 前）

1. **授權**：當晚在家；「可以隨意的 push」；事情交給子 agent、頂層只跟使用者交流；需要思考的派 fable。新 session 照 user.md 重問 push。
2. **正在討論**：inst 路徑／stdin／TARGET 重設計，已定與未定見 [SESSION-LOG 最新進度第一條](SESSION-LOG.md#最新進度) 與稿 [inst-exec](../proto8/thinking/2026-10-15-inst-exec.md)。要點：aos-inst 只吃 stdin、TARGET 全拿掉、aos-exec 當語法糖、`$ref` 從所在檔（symlink 所在處）算、呼叫機制不依賴指示詞（C-48）、刪 aos_tree。compact 後我曾忘記 N-12（stdin 才是標準）與 C-48（指示詞不進正規設計），被使用者拉回——設計題先讀這兩條。
3. **當晚新定**：C-52～C-55、N-43 改寫、abbr.json；改名批次（val、P1～P7、M1～M9）已推。
