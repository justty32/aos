# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-19 晚（家中 Manjaro 新 session）

1. **授權**：使用者 /goal 原文「事情盡量交給agent做，簡單工作和雜活交給sonnet。你就負責和我交流。可以隨意push」（fable 太貴，不再預設派，見 user.md 子 agent 模型）——本 session 每個 commit 後直接 push。在家中 Manjaro：本機 git 已是 justty32（justty32@gmail.com），remote origin 是 SSH（git@github.com:justty32/aos.git），直接 `git push origin main` 即可；公司 Windows 才要走 WSL＋SSH（舊做法見 git 歷史）。頂層只負責跟使用者交流，事情交給子 agent。
2. **現況**：proto8-2 已併進 proto8（[session log 10-19](session_logs/2026-10/2026-10-19.md#proto8-2-併進-proto810-19)），現行以 proto8 的 CONCEPTS／NORMS／CONVENTION 為準；10-16 那套（食譜與廚房、門房、`.aos` 捷徑等）已作廢，舊 lib 在 git aa2fec1f。
3. **今天下午定的**（[session log 10-19 下午](session_logs/2026-10/2026-10-19.md#下午-session健檢重寫順序資料夾比喻四題入口改-_exec10-19)）：C-71 資料夾用 table 比喻、C-72 JSON＝單檔 table、C-41 元素求值由 entry 決定（quote）、C-43「編譯」＝用 lua／lisp 生成資料夾佈局；入口預設改 `_exec`（工作區 stack 仍 `.aos/`）。
4. **下班前口述**（ideas § 14～§ 19）：entry／aos-exec 新規則、`#/` 尋址、`AOS_CF`／`AOS_CD`，已落實：impls 與 proto8/bin 兩版都照 ideas § 14～§ 21 做完，條文同步（見 SESSION-LOG）。
5. **待辦**：daemon、兩種 kernel、tasks、tick、腦的工具呼叫待照新做法重寫，等使用者說先做哪個（[NORMS 待定](../proto8/NORMS/08-待定.md)）。重寫順序稿已排好（[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)），使用者「這些都是實作細節，之後再說沒關係。我還在高空飛。」——他在想大方向，別拿實作細節打斷。信箱、WAIT_USER 皆空。
6. **`proto8/impls/`（未追蹤）**：使用者假日（10-17～18）自己做的 C／C++ 實作（aos-loop／aos-daemon＋util／directive／schema，aos-fsm 只開頭；aos-inst 已刪（使用者確認），aos-loop／daemon 因此建不起來，先放著；新增 impls/aos-exec：庫＋公開 API＋CLI），照已刪的舊 Python lib（git aa2fec1f）寫、沒跟上 `_exec`／`AOS_STACK` 新做法。使用者 10-19 晚：「impls那些是我在假日的時候做的，可以參考」→ 當參考，不刪、不 git add，只此一份。
