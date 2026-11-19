線 aos-base-fix-1119（11-19）紀錄：照使用者選的四個小洞修了四刀（P2 一封認領不了的信不再堵信箱、P5 額度帳本壞了從流水帳重算並上表、P12 auto_restart 越重起等越久並上表、P18 daemon 不在時死掉的 proc 留 stopped 不下表），另把「kernel 忙就卡 3 秒」與「同帳號沒有邊界」寫進知識庫。

← [11-19 日索引](README.md)｜問題出處 [基底體檢](aos-base-audit-1119/README.md)、[問題清單](aos-base-audit-1119/02-問題清單.md)、[Argon 採納表](aos-base-audit-1119/06-Argon審與採納.md)

## 使用者原話（11-19 下午選項框，頂層轉）

- 題「基底體檢：除了已經派出去的「錯誤記錄只讀檔尾」，還有幾個不牽涉方向的小洞。要修哪些？」（複選）選：「一封壞信堵死信箱」「斷電後 agent 從表上消失」「額度帳本壞掉全樹卡住」「會死的 proc 無限重起」。各選項的說明：
  - 壞信＝「認領信時碰到一封權限不對的，現在整次報錯，daemon 和 kernel 的信箱全停。改成跳過那一封。」
  - 斷電＝「沒正常收工就斷電或重開機，用 ctl add 掛上、沒帶自動重起的 agent 整列不見。改成留在表上並標明死了。」
  - 帳本＝「帳本檔壞一次，所有 agent 的腦就無聲等待，表上看起來正常。改成從流水帳重算並在表上報錯。」
  - 重起＝「撐過 3 秒才掛的 proc 會被一直重起，表上永遠顯示在跑。改成越重起等越久，並在表上看得到次數。」
- 題「…「我是誰」、讀自己信箱、設鬧鐘現在都要經過 kernel。kernel…3 秒不回，底下的 agent 這些事全部失敗。要怎麼處理？」選：「維持現狀，只寫明」。
- 題「…同一個 Linux 帳號底下，agent 之間沒有真的邊界…要收多緊？」選：「維持，只寫明 (Recommended)」。
- 稍早：「整塊板子只有 daemon 一個管理員 <- 自行承擔風險。重新編譯這塊，我更願意稱其為"特性"。」

## 交了什麼

| 刀 | commit | 改的檔 |
|---|---|---|
| P2 信箱 | 2093df09f | aos-post 庫 take／take_all、命令列、help、README、docs/01；aos-daemon mailbox.cpp、docs/05、08；測試 aos-post/tests/test_take_skip.py（新）、aos-daemon/tests/test_bad_letter.py（加一支） |
| P5 帳本 | 400f9775d | kernel_llm budget.py、ledger.py、docs/01–03；aos-daemon-ctl ls（py/aos/apps/daemon_ctl/main.py）；aos-llm send.cpp 的提醒；知識庫 cli/daemon.json；測試 kernel_llm/tests/test_used_recount.py（新）、py/tests/apps/daemon_ctl/test_ls_body.py（新）、aos-llm/tests/test_send_hint.py（加一支） |
| P12 重起退避 | 0b23509a1 | aos-daemon daemon.hpp、child/child.hpp、child/child.cpp、tend.cpp、reconcile.cpp、docs/03、04；測試 tests/test_restart_backoff.py（新） |
| P18 斷電留表 | 36602ed9b | aos-daemon adopt.cpp、docs/08；測試 tests/test_adopt_dead.py（新） |
| 文件 | （本筆） | 知識庫 kernel.json、errors.json、rules.json；體檢 README「使用者已答」補一節；本紀錄、日索引、progress |

修前修後都用體檢的重現腳本（`aos-base-audit-1119/repro/`，抄到本線暫存、路徑換成本線）在 `git archive` 抄出的乾淨複本上跑：修前＝HEAD 沒改動的那份，修後＝疊上改動 install 過的那份。

## P2：一封認領不了的信跳過，不堵整箱

- **改了哪**：`aos::post::take(mb, skipped)`／`take_all(mb, skipped)`：某一封 rename 失敗而且不是競爭（ENOENT／ENOTEMPTY／EEXIST 照舊是競爭、安靜跳過）＝記進 `skipped`（名字＋「代號 訊息」）、接著認領後面的。命令列每封跳過的印一行 `aos-post: warning: skipped letter <名> (cannot claim it, left in new/): WriteFailed …`；aos-daemon 記 `mailbox_warning`＝`cannot take letter <名>, skipped[ (and N more)]: …`。kernel 站、llm kernel、aos-mailbox、eca 都是叫 `aos-post take`／`take-all`，一起好，不用改。
- **自己定的**：
  - `skipped` 做成**必給的參數**（不是選填）：呼叫者一定得接，避免「跳過了卻沒人說」。
  - 結束碼照認領到的算：認領到就 0，只剩認領不了的就 10（帶 warning）——N-43 只要求有 error 行不退 0，warning 可以配 0／10。
  - 那封**留在 `new/`、每次再試、每次再提醒**；沒做「移到壞信夾」（那是選項 (b)，使用者選的是跳過）。代價：kernel 站每輪一行 warning 進它的 stderr（P1 修過，大了也不拖垮 daemon；清道夫會截）。
  - daemon 只記第一封＋數目，不列全部（`mailbox_warning` 本來就是「最後一個問題」一句話）。
  - 指定名字的 `take(mb, name)`（aos-llm 收回信用）不改：那是一封指定的信，出錯就該報錯。
- **修前**（`daemon_ctlbox_bad.sh`）：權限 555 的信夾排在前面，後面的 good2 不套，`mailbox_warning`＝`cannot take letters: WriteFailed …`，`ping` 3 秒 `DaemonFailed`；`daemon_ctlbox_stuck_after.sh`：同一圈先搬進 `cur/` 的 good3 卡在 `cur/`，要 daemon 重起才套。
- **修後**：good2 當圈套上、`mailbox_warning`＝`cannot take letter 00000000000000000001.x.y, skipped: WriteFailed …`、`ping` 68 ms 回；good3 當圈套上、`cur/` 清空。
- **測試**：test_take_skip 4 支（take-all 跳過並提醒、take 跳到下一封、只剩卡住的退 10 帶提醒、沒卡住時安靜）；test_bad_letter 加 test_unclaimable_letter_is_skipped（ping 回信、`mailbox_warning`、ctl add 照套、daemon 照跑）。

## P5：used.json 壞了從 ledger 重算，算不了就上表

- **改了哪**：`budget.read_used` 讀到 used.json 在但讀不懂（不是 JSON、形狀不對）＝`_recount`：用 `ledger.read_rows` 讀整份 `ledger.jsonl`（照 ledger 文件的讀法：跳過壞行、同 `id` 只算最後一行），這一窗＝`finished_at` 在窗起點之後的行，`counter_all_*`＝全部行；token、`packs`、`senders` 跟記帳同一套算法。壞檔改名 `used.json.bad-<UTC>` 留底，新帳多一格 `recounted`，stderr 一行 warning，這輪照常做。
- **上表**：`aos-daemon-ctl ls` 的 `# daemon:` 那行在 `state.json` 的 `body_code`（daemon 本來就記的身體最後一次結束碼）不是 0 時加 `; its body failed last round (code N; the reason is in the daemon's stderr)`，`ls -j` 多 `body_code`；`aos-llm send`／`recv` 的提醒多認「daemon 活著但 body_code 非 0」。這兩處對所有有身體的 daemon（框架站也是）都有效，不只帳本。
- **自己定的**：
  - **不從 0 算**（Argon A17：等於額度歸零、繼續花錢）。ledger 不在或讀不了＝重算不了＝照舊每輪 `UsedBad`、不動壞檔——這時就靠上面的「上表」被看到。
  - ledger 有壞行照跳過（ledger 文件本來就這樣叫讀者做），跳了幾行寫進 warning 與 `recounted`。ledger 寫失敗本來只提醒，所以重算**只會少算**；寫進文件。
  - `recounted` 那格這一窗都帶著（每次寫回都保留），換窗拿掉——新窗的數不是重算來的。
  - 重算成功那輪 body 退 0，所以表上的 `# daemon:` 行不會變；證據在 stderr 那行、`used.json` 的 `recounted`、`used.json.bad-*`。「表上報錯」做在重算不了的那種（那才是無聲卡住的情況）。
  - 讀不了 used.json（權限等 OSError）不重算，照舊 `UsedBad`（不是「壞了」，是讀不到，改名多半也不成）。
- **修前**（`llmk_budget.sh`「corrupt used.json」段）：每輪 `UsedBad`、`aos-llm ask` 一直等到 `timeout` 收掉（退 124），`ls` 看起來正常。
- **修後**：當輪 warning `… kept it as used.json.bad-20261119T060605Z and recounted from ledger.jsonl: 4 calls, 300 tokens in this window …`（跟壞掉前的帳一樣），額度照擋：`ask` 1 秒內回 `BudgetMissing`、退 1。
- **測試**：test_used_recount 4 支（重算數字含去重與窗外與半行、留底檔內容、下一輪不再重算；重算後額度照擋；重算後照常記帳；沒 ledger 照舊 UsedBad 且不動檔）；test_ls_body 2 支（真 daemon、身體退 3 時那行與 `-j`；身體退 0 時安靜）；test_send_hint 加 1 支。
- budget.py 變 341 行，過了 300 行「該考慮拆」的門檻，沒拆（拆法：把 `_recount` 搬去 ledger.py 會讓 ledger 反過來 import budget，要再想）。

## P12：auto_restart 越重起等越久，表上看得到

- **改了哪**：tend.cpp 的 auto_restart 分支：每次自己退了算一次「重起」，連著（每一輩子都沒撐過 60 秒）的次數決定等多久：第 1 次同一拍起（跟以前一樣）、第 2 次等 1 秒，之後每次加倍（2、4、8…），最多 60 秒；有一輩子撐過 60 秒＝重算。等的期間列 `sleeping`、`reason`＝`auto_restart: restart <N> in <秒>s (<連著幾次> in a row; last: <上一次怎麼退>)`；reconcile.cpp 到時間才起，起來的 `running` 列 `reason`＝`auto_restart: restarted <N> times; last: …`；列多一欄 `counter_restarts`。原本「連 3 次都在 3 秒內退＝stopped」不動。
- **參數怎麼定的**（daemon.hpp 的三個常數，寫死、不開設定）：
  - 起始 1 秒、加倍、上限 60 秒：常見的指數退避；上限 60 秒＝一個壞掉的常駐 agent 一小時最多起 60 次左右，又不至於修好後要等太久。
  - 「健康」門檻 60 秒：跟上限同一個數，撐過一個最長等待就算恢復；比 3 秒的「起不來」門檻寬很多，專抓「撐過 3 秒才掛」這種（P12 本身）。
  - 第 1 次不等：偶發一次（腦一時失敗、agent 自己退）照以前同一拍回來，平常的行為不變。
  - 沒開成 daemon.json 的設定：NORMS N-28 寫「沒有 backoff」，要不要讓人調是方向題，先寫死、列成題。
- **自己定的其他細節**：次數與等待只在記憶體（同 `quick_exits`），人 `start`／`add`、daemon 重開都歸 0；daemon 重開時等待中的列照 `sleeping` 第一圈就起。等待中下 `wake` 不會提早起（`wake` 寄的 `procs_woken` 跟這段等待分不開）。退 0 的寫 `exited with code 0`、拿不到碼的寫 `exited, code unknown`，非 0 的用 daemon 原本的失敗原因句（含 stderr 最後一行）。running 列有 `reason` 以前只在 stuck 時出現，現在多這一種。
- **修前**（`t02_autorestart.sh`）：撐 3.3 秒才退的 d33 20 秒內起了 7 次，表上一直 `running`、`reason` 空。
- **修後**：同樣 20 秒起 4 次（0、1、2 秒的等待），20 秒那一刻列是 `sleeping`、`reason`＝`auto_restart: restart 4 in 4s (4 in a row; last: failed while running: exited with code 1: die33 at …)`；`ls` 的 REASON 欄看得到。3 秒內就退的 d1、d0 照舊 3 次後 stopped。
- **測試**：test_restart_backoff 2 支（等待 0／1／2 秒的間隔、sleeping 列的 reason、running 列的 reason 與 `counter_restarts`、`ls` 看得到；人 stop 再 start 歸 0）。「撐過 60 秒重算」沒寫測試（要跑一分多鐘），只讀程式。

## P18：daemon 不在時死掉的 proc 留 stopped，不下表

- **改了哪**：adopt.cpp：表上 `running`、行程已不在、沒寫 auto_restart、不是收工途中、不是別棵樹的列，原本直接跳過（下表），改成留 `stopped`＋`reason`、進 stopped 集合（要人 `start`）。同一次開機＝`ended while the daemon was not running (exit code unknown); start it to run it again`；表上 `boot_id` 跟這次開機不同（重開機、`wsl --shutdown`）＝`the machine restarted while it was running (exit code unknown); start it to run it again`。stderr 一列一行 warning。
- **狀態名**：用現有的 `stopped`（「行程不在、要人 start」），不另加狀態；死因寫在 `reason`。文件 08 寫明。
- **自己定的**：
  - daemon.json 寫的列**照舊**交給後面照宣告再起（以前就是這樣，不是 P18 說的那種會消失的列；改成 stopped 反而會讓宣告的常駐列不起）。procs_ctl 宣告的列 adopt 時還沒讀（每圈才讀），照新規則留 stopped——列成待確認。
  - 不分起法、不分它是不是自己做完退 0 的：拿不到結束碼就一律留表，讓人決定。代價：一次性的、本來就會自己退 0 的 proc，若剛好在 daemon 不在時做完，重開後會多一列 stopped，要人 `rm`。
  - 接回時還活著、之後在新 daemon 底下退的（`own=false`，拿不到碼）照舊下表——那是 daemon 醒著看到的結束，不是 P18；N-28 寫的「adopt 接回的拿不到結束碼，退了照樣下表」講的是它。
- **P8 順手對到的部分**：P8 的「stack 一時寫不了、第一份窗寫不成就退 1、退前把接回的健康子項送 TERM」——**送 TERM 那半沒改**（在 table.cpp／loop.cpp 的收工路徑，不是同一段）；但「修好再起後用信加的列整列消失」那半，因為那些列在表上是 running、行程已不在，現在走上面這條留 `stopped`＋reason，**不再消失**（沒另外實測 P8 的腳本）。
- **修前**（`t03_crash_adopt.sh`、`t09_table_truth.sh`）：daemon 被 kill -9 期間殺掉的 sl、sl2、c，重開後整列不見。
- **修後**：sl、sl2、c 都留 `stopped`、`reason`＝`ended while the daemon was not running (exit code unknown); start it to run it again`；接回的 lp、auto_restart 的 ar 照舊。
- **測試**：test_adopt_dead 3 支（daemon 不在時死掉＝stopped＋reason＋warning、不自己起、start 能起；改 boot_id 模擬重開機＝「machine restarted」；daemon.json 寫的列照舊再起）。真的重開機沒測。

## 只寫明的兩件（知識庫）

- `knowledge/aos/kernel.json` 的 where_to_send 加「When the kernel is slow or busy」：設了 `$AOS_KERNEL` 時 mailbox_peek、mailbox_send、clock_register（給了 box 也一樣）、self_*、aos.gdb 的 say／listen 都先問 kernel「我是誰」、等 3 秒，不回＝`KernelFailed`；kernel_gate 的 kernel 是 agent，長回合或睡著時底下全卡；這是現狀、使用者 11-19 選維持；該怎麼做（等一下再試一次、一直不行就回報、不繞過去直接寄 daemon）。`errors.json` 的「Where a Code is explained」補 `KernelFailed` 一列（體檢說錯誤頁查不到它）。
- `knowledge/aos/rules.json` 加「What does not enforce these rules」：同一個 Linux 帳號、Linux 不擋 agent 之間互讀互寫；每支 proc 拿到整份環境（含人 export 的 API key，不准印、抄、寄）；信封的 sender 寄件人自己填、沒人驗；`sub:N` 是把它關住、不是保護別人；前提是單人使用、模型可信，使用者 11-19 選維持只寫明。沒寫任何 key 的值。
- 體檢 README「使用者已答」補一節記上面三題的原話與選項（只加字）。
- aos-daemon docs/08「reason 的細節」照頂層轉來的話補一句 P1 的事實：只看 stderr 記錄檔尾 64 KB 內的最後一個非空行，最後一行超過 64 KB 時取到的是它的後段。

## 測試總結

- 每刀在 `git archive HEAD` 的乾淨複本疊改動、複本裡 install、經清環境腳本（unset 全部 `AOS_*`）跑；暫存只在 `~/.aos/scratch/aos-base-fix-1119/`。
- 最後一次全跑（四刀都疊上）：cpp/*/tests、py/tests、py/tools/**/tests、templates/tests、archive 共 286 個測試檔、2833 個 case；283 檔全過，3 檔紅都是跑法或環境、跟本線無關：archive/aos-home/test_copy_tree（封存的舊工具找不到 aos_flags 模組）、py/tests/apps/feedback（暫存路徑被縮成 ~，體檢 05 已記）、review_round/test_suggestions（當腳本跑缺 aos 套件路徑，體檢 05 已記）。frontend 5 支沒跑（拒絕在有 AOS_* 的環境跑，本線沒碰 frontend）。
- 用假腦（llm_fake 與重現腳本的假端點），沒叫真模型；沒碰 `~/aos-home`、沒在 repo 跑 install.py、沒用 pkill／killall。

## 沒做、沒驗到的

- P8 的「寫不了窗就退前送 TERM 給健康子項」沒改（不同段）；P8 腳本沒重跑。
- P12「撐過 60 秒重算」沒有測試；真重開機（P18 的重開機那半）只用改 boot_id 模擬。
- 13:51 前後整個 `~/.aos/` 被清空過（不是本線做的），本線的暫存跟著不見，重建後重跑；體檢線的暫存（`aos-base-audit-1119/`）也不在了，重現腳本照 repo 裡那份抄。

## 要使用者定的

1. **NORMS 跟新行為對不上兩處**（規範條文沒動）：N-28「05-adopt與結束」寫「沒有 backoff…daemon 照舊沒有 backoff」「自己退了…同一拍照表重起」，現在 auto_restart 有退避；同一條「adopt 接回的（拿不到結束碼）下表（代定）」，現在 daemon 不在時死掉的改留 stopped。要不要照 11-19 的選項改條文？
2. 退避參數（1 秒起、加倍、上限 60 秒、撐過 60 秒重算）寫死；要不要開成 daemon.json 或列上的設定？
3. procs_ctl 宣告的列在 daemon 不在時死掉，現在也留 stopped（daemon.json 的照舊再起）；要不要跟 daemon.json 一樣照宣告再起？
