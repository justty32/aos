# 晚審必修 1～9：daemon 不分類（B）、prune 與判官的程式錯和文件對不上

← [入口](README.md)｜下一份 [02 必修 memory 與條文](02-必修-memory與條文.md)

## 1. rm 途中碰上 daemon 收工，被移除的 proc 變成 sleeping，下次開門又起來

- **檔:行**：`proto8/impls/aos-daemon/src/daemon/tend.cpp:251`（`c.nap = !c.soft;`）
- **問題**：rm 走的是 `term()`，所以 soft 是 false。收工時 finish 把它設成 nap，它退了就留成 sleeping，開門被 wake。這是 B 帶進來的回歸：B 之前只對 `running` 的列設 nap。審查員 A1 用真 daemon 重現過。
- **對照**：N-28 `02-N-28.md:44`「名單早就要拿掉、收工時才退的一樣拿掉」（B 沒有翻這句）；C-56 寫什麼就做什麼。
- **建議**：nap 只給 `phase == "running"` 的列；stop 途中照舊留 stopped，rm 途中照 rm 拿掉。test_lifecycle 補一格「rm 後馬上收工」。

## 2. daemon 收工途中被 kill -9，重開時不看 `stop_mode`，使用者的 stop 和 rm 都變成 sleeping 再叫醒

- **檔:行**：`proto8/impls/aos-daemon/src/daemon/adopt.cpp:162`（`if (finishing || mode == "sleep")`）、`:181`、`:185`
- **問題**：正常收工的路徑在隊長審 diff 時補了「stop 途中留 stopped」，當機復原這條路沒有跟著改，同一件事因此有兩種結果。B 新加 `stop_mode` 本來就是為了不靠猜，這裡卻被 `finishing` 旗標蓋過，等於兩套機制在決定同一件事。A1 重現過。
- **對照**：`proto8/thinking/2026-11/07/arknights-kb/07-停不下與消失.md:53`「收工時正在 stop 的照 stop 留 stopped」。
- **建議**：stopping 的列只看 `stop_mode`。`finishing` 只留給「表上還是 running」的列。補一格「收工途中 kill -9」測試，stop、rm 各一。

## 3. prune 把「add＋sleep／stop 剛登記、還沒建 stack」的列當成無限久，`--apply` 會直接移除

- **檔:行**：`proto8/py/daemon_ctl/table.py:221`（`changed is None or …` 算入選）、`:172-173`
- **問題**：照設計，add＋stop／sleep 同時寄的列本來就不建 stack（`reconcile.cpp:172-185`）。prune 卻把「缺 stack」當成「很久沒動」，任何 `--older-than` 都會選到它。A1 重現過。
- **對照**：使用者原話是「清理上次修改是很久以前的」（`proto8/thinking/2026-11/07/daemon-prune/README.md`），剛登記的不算很久以前。
- **建議**：缺 stack 的一律不選，只在自檢裡印出來；自檢也排除 pid、code 都是 null 的待起列。

## 4. 「收工時誰睡下」在文件裡有三種說法，跟程式不合

- **檔:行**：`proto8/impls/aos-daemon/docs/06-結束碼等.md:12`、`08-當機復原與已知限制.md:10`、`proto8/cmd/aos-agent/README.md:96`、`proto8/knowledge/aos/cli/daemon.md:11`、`proto8/thinking/2026-11/07/arknights-kb/08-daemon不分類實作結果.md:82`。另外 `docs/03-起-停-暫停.md:26` 已由 `92ee2e713` 改了一半，還沒涵蓋 rm 途中。
- **問題**：08:82 是 codex 原版（含 stopping 一律睡下），07:53 記的是隊長改過的版本，程式照 07 做，五份文件卻跟著 08。
- **對照**：conventions「程式碼 > code map > 文檔」。
- **建議**：先照第 1、2 條把程式定案，再把這六處統一成一句：「收工時 running 的睡下，stop 途中的留 stopped，rm 途中的拿掉；收工途中被 kill -9 也一樣」。

## 5. 信箱文件還把「stop／start 寫到 exec 型」列為壞信

- **檔:行**：`proto8/impls/aos-daemon/docs/05-信箱.md:27`
- **問題**：B 已經刪掉這一項（N-54 `03-N-54.md:12` 有註），只有這一行漏改。
- **建議**：刪掉這一項；同檔 `:10` 的「（loop 型）」也一起拿掉。

## 6. aos-daemon docs/01 的 adopt 段還是 B 之前的寫法

- **檔:行**：`proto8/impls/aos-daemon/docs/01-用法.md:39`（「哪一型看…有沒有 daemon 寫的 `loop.json`」）、`:40`（「其他列（`stopping`）不接」）
- **問題**：兩句都跟程式相反。adopt 現在讀表上的 `launch`、`phase`、`stop_mode`，stopping 的列也會接回（`adopt.cpp:98-113`、`:150-171`）。
- **建議**：改成跟 `docs/08:9-11` 同一套說法，或直接連過去。

## 7. N-66、N-17 還寫「之後改成寄信者給的旗標與 `queue_wait_ms`」

- **檔:行**：`proto8/docs/NORMS/05-基礎設施-窗/08-N-66.md:8`、`06-N-17.md:5`（句尾）
- **問題**：aos-agent 的這部分已經實作。aos-daemon-ctl 11-07 起永遠直寄（`55bf74e55`），也拿掉了 `--queue-wait-s`。sol 審查 `02-條文-lift-to-norms/02a-NORMS-1～5.md` 點過這件事，到現在還沒修。
- **建議**：兩處都補「已實作（aos-agent）；aos-daemon-ctl 11-07 起永遠直寄、不帶 `queue_wait_ms`」。

## 8. 判官的回信箱裡只要有一封壞信，判官就永遠卡死

- **檔:行**：`proto8/lib/aos/judge/_entry:204-206`（`see` 不是 0 就 `die PostFailed`）
- **問題**：壞信一直留在 `judge_replies/cur/`，判官每輪都死在同一封，後面的收件和轉寄一輪都跑不到，所有 procs_* 請求都會停擺。只要有 `judge_replies/` 這個資料夾就會跑到這段，keep_ordered 關著也一樣。主迴圈遇到壞信是「提醒一行、丟掉」（`:362-365`），兩處做法不一致。審查員 B1 重現過。
- **對照**：判官檔頭 `:17`「壞信＝stderr 一行、丟掉」；sol 審查 10-修正結果 #5 的理由「壞窗不整輪退 1」。
- **建議**：`code == 1` 時改成 warn＋done 丟掉，其他碼才 die。

## 9. 已經轉寄給 daemon 的信，判官重起後可能回「沒掛」，daemon 卻照樣套用

- **檔:行**：`proto8/lib/aos/judge/_entry:380-383`、`:400-403`、`:426-429`（到期檢查與格子判斷），都排在防重檢查 `:233-236` 前面
- **問題**：判官在「已送出、還沒 done」之間死掉。重起時如果期限已過，或格子剛好滿了，寄件人會收到 `applied:false`，daemon 那邊卻照樣掛上。另外 keep_ordered 關著時，防重只看 ctl 的 `new/`；daemon 已經把信收進 `cur/` 的話就查不到，這條重送路還在。edge-1107 E2 寫成「已修」（`proto8/thinking/2026-11/07/edge-1107/README.md:75`），這兩個窗口卻沒有記。B1 重現過。
- **對照**：使用者 E2 裁定「若會丟信或回信對不上，選代價最小的順序並記下」。
- **建議**：把「轉寄過了嗎」的檢查移到期限檢查之前。關著時 `new/`、`cur/` 都要看，開著時查對照表；查到就直接 done。做不到的話，就在 `kernel/docs/02-kernel-modes.md` 和 E2 寫明這兩個窗口。
