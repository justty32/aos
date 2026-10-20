# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-20（公司 Windows session）

1. **授權**：使用者「照舊，這個 session 內可以隨意 push」→ 每個 commit 後直接 `git push origin main`。分工照 [user.md 子 agent 模型](workflows/common/user.md) 10-20 版：普通工作 opus、簡單與雜活 sonnet、高難度思考與規劃 fable（盡量少用）；頂層只跟使用者交流；派出去的 agent（雜活除外）要先通讀 wf/ 規矩。公司這台：python／wf-lint 走 WSL（`wsl -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && …'`），`git add` 加 `-c core.ignorecase=false`（[gotchas](workflows/common/gotchas.md)）。
2. **正在討論的設計**：指示詞與 argv 第一個元素已拍板 D1～D8（[ideas 10-20](../proto8/thinking/2026-10-20-ideas.md)），bin 版已做；晚上指示詞改版也做完推上（同檔 § 8 D9～D15：`path` 改 `$path`、加 `$prefix`、寫法寬容，真的解不開仍報錯＝環境變數沒設、檔讀不到、指不到、繞圈），`$fmt` 未決（§ 9）。daemon 重寫五點「照預設」，bin 版已做（[ideas § 25](../proto8/thinking/2026-10-19-ideas.md)）。兩者的 impls（C／C++）版待回家那台對齊（impls 不在公司這台），指示詞那邊要多對齊 `$path`／`$prefix`／寬容規則。agent 自定的邊界、`$prefix` 與 C-56 的張力已報給使用者，他回「好，沒事了」→ 留在原處不追。tidy 第二輪剩 7 條待裁定（[WAIT_USER](WAIT_USER.md)）。
3. **當天動到的條目**：N-17、N-28、N-33、N-54（daemon，10-20 註）；N-45、N-58、N-59、N-61、N-62（指示詞／argv，N-45、P-31 隨改版同步）；proto8 的 CONVENTION／NORMS／CONCEPTS 拆成分檔、thinking 清掉 AI 分析段。aos-fsm 盤點：bin 版完整、14 組測試（Windows 直接跑會 WinError 193，要走 WSL）、impls 待回家對齊。沒有還在跑的子 agent。細節 → [session log 10-20](session_logs/2026-10/2026-10-20.md)。

## 2026-10-19 晚（家中 Manjaro 新 session）

1. **授權**：使用者 /goal 原文「事情盡量交給agent做，簡單工作和雜活交給sonnet。你就負責和我交流。可以隨意push」（fable 太貴，不再預設派，見 user.md 子 agent 模型）——本 session 每個 commit 後直接 push。在家中 Manjaro：本機 git 已是 justty32（justty32@gmail.com），remote origin 是 SSH（git@github.com:justty32/aos.git），直接 `git push origin main` 即可；公司 Windows 才要走 WSL＋SSH（舊做法見 git 歷史）。頂層只負責跟使用者交流，事情交給子 agent。
2. **現況**：proto8-2 已併進 proto8（[session log 10-19](session_logs/2026-10/2026-10-19.md#proto8-2-併進-proto810-19)），現行以 proto8 的 CONCEPTS／NORMS／CONVENTION 為準；10-16 那套（食譜與廚房、門房、`.aos` 捷徑等）已作廢，舊 lib 在 git aa2fec1f。
3. **今天下午定的**（[session log 10-19 下午](session_logs/2026-10/2026-10-19.md#下午-session健檢重寫順序資料夾比喻四題入口改-_exec10-19)）：C-71 資料夾用 table 比喻、C-72 JSON＝單檔 table、C-41 元素求值由 entry 決定（quote）、C-43「編譯」＝用 lua／lisp 生成資料夾佈局；入口預設改 `_exec`（工作區 stack 仍 `.aos/`）。
4. **下班前口述**（ideas § 14～§ 19）：entry／aos-exec 新規則、`#/` 尋址、`AOS_CF`／`AOS_CD`，已落實：impls 與 proto8/bin 兩版都照 ideas § 14～§ 21 做完，條文同步（見 SESSION-LOG）。
5. **`proto8/impls/`（未追蹤）**：使用者假日（10-17～18）自己做的 C／C++ 實作（aos-loop／aos-daemon＋util／directive／schema，aos-fsm 只開頭；aos-inst 已刪（使用者確認），aos-loop／daemon 因此建不起來，先放著；新增 impls/aos-exec：庫＋公開 API＋CLI），照已刪的舊 Python lib（git aa2fec1f）寫、沒跟上 `_exec`／`AOS_STACK` 新做法。使用者 10-19 晚：「impls那些是我在假日的時候做的，可以參考」→ 當參考，不刪、不 git add，只此一份。備份放 proto8/impls/backup/（使用者 10-19 晚：「備份就放這個資料夾底下」）。 **（更新）** 使用者「重寫吧，fsm一起做」（[ideas § 23](../proto8/thinking/2026-10-19-ideas.md)）→ impls 的 aos-loop 已重寫（照 bin 版，run／max，小庫＋薄 CLI，23 組測試）、aos-fsm 新做（22 組＋整合測試），aos-exec Result 加 `received` 欄位；PATH 只放 impls 三支 bin 跑 bob、ann，結果與 bin 線完全一樣；舊 aos-loop／aos-fsm／aos-daemon 備份在 proto8/impls/backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz；aos-daemon 仍建不起來、待重寫。兩版差異新增：impls 的 loop／fsm 會擋 SIGINT／SIGTERM／SIGHUP 轉給正在跑的那拍（bin 版不會，收到就死、字串格變孤兒）。待使用者裁：字串 run 時 PATH 前面加的是 aos-loop／aos-fsm 自己的 bin、不是 aos-exec 的（P-39 寫「loop／fsm 重寫後再定」）。 **（§ 24 結論）** 使用者「1.好。2.不要主動加」「也套用，都不動path吧」→ 上面那題消失：bin 版 loop／fsm 也轉訊號，aos 的程式（兩版 aos-exec、aos-loop、aos-fsm）都不動 PATH，demo／測試由呼叫端自己放 PATH；impls 只剩 aos-daemon 待重寫。
