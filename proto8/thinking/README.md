# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user.md](../../wf/workflows/common/user.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）。整份是 AI 產出的 13 份已刪（10-11 的六份審查／探針打撈、綜合、Fable 獨立抽概念、診斷、隊長想的、壓力測試、「件」與格、一天日記草稿）；其餘五份都已精簡。舊版：10-11 的與 tasks-ticktock 在 git（commit 22285099）；loop-daemon、inst-json、ctl-norms 三份**沒進過 git**，精簡前的原版要另外保存。

| 日期 | 一句話 |
|---|---|
| [2026-10-11](2026-10-11-restart.md) | 為什麼重來：太繁複、做太快；河堤邊的思考 2.1～2.20；3b 對 PLAN §5 的回覆；晚上三輪口述：§3f 從 daemon 重講概念、§3g 實作想法（inst→daemon→tick-tock→kernel→agent→閉環）、§3h 空間存狀態／處理＝變化／求值＝看變化；§4 未決 |
| [2026-10-12](2026-10-12-tasks-ticktock.md) | tasks＝像 lisp 基礎函數的獨立程式（seq／par／if／not，proto8-1）；tick-tock 選甲＝只是時鐘（aos-tick 規格），打包是規範、在 kernel 做；規範比實作重要 |
| [2026-10-12 loop／daemon](2026-10-12-loop-daemon.md) | loop＝包一個 inst（次數、間隔），ctl 是一個宣告式 ctl.json；daemon＝管多個 loop 的表、ctl 是資料夾、自己也是 loop；三個 json 一個手感（`aos-zzz x.json`，loop.json＝外層 key＋`inst` 格、daemon.json 比照）；loop 的退出碼表；daemon 底下的 loop 用子程序（包裝檔、改 ctl／讀 state、SIGTERM 收尾、save／load）；遷移步驟 |
| [2026-10-12 inst 進 json](2026-10-12-inst-json.md) | 結束碼只有 0／非 0 是慣例；inst 只回自己的碼、子程式的碼進 exit 檔；`run(path)` 只收路徑、跟命令列一樣；`timeout_ms`、`grace_ms` 進 inst.json；遷移項；未決三題（監工參數去哪等）；代理人＝一個 loop 跑切狀態機的 inst |
| [2026-10-12 ctl 規範](2026-10-12-ctl-norms.md) | NORMS N-05～N-10 背後的細節：宣告式 ctl.json（`paused`／`stop` 各帶 `{"val","now"}`、沒寫的回初始值、讀的人壞檔維持上一次、state.json 格式）與指令式控制資料夾（`.done`、`ok` 唯一要看、丟的人清）；各條分規範／慣例 |
| [2026-10-13 JSON 路徑](2026-10-13-json-path.md) | JSON 也是檔案系統：命令列 TARGET 吃 `檔#/位置`（決定做，還沒動工）；loop.json 排法不動；不做 AOS_INST_SELF；單檔自指是套娃、定兩個檔；`_metainfo`＝inst 跑下去的特性（九軸、資源），inst 忽略、給 kernel 參考（還沒動工） |
| [2026-10-13 kernel／agent](2026-10-13-kernel-agent.md) | kernel＝能操控東西被執行的就算（標準規範：基於 daemon、決定跑哪些 inst）；任務屬性＝隱性行程／檔案屬性＋九軸，決定演算法隨便；agent＝記憶＋思考中心＋工具的狀態機，自我改進用 loop＋狀態切換（一步落檔、zip／git）；標準版三態等待／思考／工具；工具↔inst、agent 細節待規劃 agent 時再說 |
| [2026-10-14 JSON 統一入口](2026-10-14-json-entry.md) | 使用者想法：POSIX 的 argv 與 LISP 的 list 都是函數的統一入口但跟 JSON 脫節；想把統一入口的參數統一成 JSON，直接對接 LLM 工具、腳本語言、檔案系統；當年資源不足只能 list／array，現在可以用 map；inst 不變、規範建議 argv[1]＝JSON 檔，回傳 stdout 或 argv[2] 未決；stdio 未來作用不大，甚至想到退守 system()；決定：不全面退守，stdin＝參數、stdout／stderr＝結果、exit＝輔助；aos 規範中 stdio 必須是 JSON，exit 檔出現＝寫完；stdio 全是 JSON 串流（放寬：單行或跨行皆可）；串流＝省略外層 [] 的陣列，`檔#/位置` 自然適用；state／ctl＝內部狀態外顯（Plan 9／FUSE 感），位置由 stdin 參數指定；外顯定期同步、沒指定位置就警告、窗名統一、stdio 與 state／ctl 無關；函數看法：stdin＝args、exit＋stdout＝ret、stderr＝途中拋出；想在外顯上延伸出 aos 版 IPC；stdout 設計自由、daemon 照 loop、子程式碼可進 ret；IPC 決定：改名、建資料夾、檔案鎖就夠，窗擴成一族（鎖、信箱、心跳…，NORMS N-14～N-17 草稿），fsync 不強制，FUSE 等效能糟再說；ctl 加 seq 等重做時做；下午：argv 空出來，旗標鏡射設定 key、`--` 可用、重做七題拍板、NORMS 三縫補完（見 04）；稍晚 aos-llm／agent 14 題拍板：N-13 沒給窗連提醒都拿掉（推翻縫二）、D-1 放寬為方便非硬規則（見 05）；傍晚 aos-fsm：使用者提「aos-agent 看狀態查表跑 inst-<state>.json，像 vtable／interface」，拍板抽成通用 aos-fsm、表只明寫、不做繼承、next 走 stdout 回傳、預設 think 非同步（請求丟資料夾、處理者不限）、fsm 可嵌套、一格可指資料夾（見 06～08）；夜間：巢狀三題定案、daemon 借 fsm 紀律（09）、Lisp 組合子視角與表上靜態 next（10）；下班前：使用者坦承很多題憑感覺選，做 ELI5 解說頁與濃縮重寫、列 7 題建議重看與 a～f 未對齊（見 11） |
