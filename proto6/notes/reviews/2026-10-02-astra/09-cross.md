# kernel／agent／plan9 一致性審查（astra，2026-10-02）

## 一段話結論

**大方向能接，但目前不能直接照三份一起做。** kernel 與 agent 的三種信格式基本一致；grant 走共門或私門，是已明列的分歧。真正卡住的是：暫停效果寫錯、grant 與 summary 會互相叫醒、額度 hook 擋不到當次呼叫、新成員的私門不能靠重讀新增。Plan9 是另一路思想實驗，不能把它的隔離效果算成現有 socket 已有的能力。建議先接通單層、固定成員、自律額度的 POC，再決定多層與新介面。

## 必修

1. **`pause` 不是「整組停住」，也不是「收信不跑」。**

   kernel 說 pause 子 daemon 後整隊停止；agent 說暫停後信進信箱不跑。[kernel／03:92](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:92)、[agent／05:29](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/05-生命週期.md:29)

   現行 pause 不殺正在跑的程序；來信仍能讓暫停項跑一次。因此常駐子 daemon 會繼續叫自己的成員。[程式:145](../../../../proto6/src/py/lib/aos_daemon_ctl.py)、[測試:120](../../../../proto6/src/py/tests/test_mq_send.py)

   **改法：**修正文句與驗收。整组終止可另用 kill 搭配收屍機制；不要把它說成原地暫停、resume 接續。

2. **每格 grant 加每格 summary，正常情況就會一直互相叫醒。**

   kernel 要每格重寄 grant；agent 即使沒事、被擋，也照寄 summary。[kernel／04:68](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:68)、[agent／07:31](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:31)

   每封信都會叫醒收件項，於是形成「grant → 空格 summary → kernel 再跑 → grant」。`ready:false` 切不斷；改私門也只是少叫醒無關的人。[程式:105](../../../../proto6/src/py/lib/aos_daemon_mq.py)

   **改法：**取消無條件每格重寄。先約定 grant 的寄送時機，以及「收信開格」是否等於「准許計算」。目前不能保證 `max_awake`。

3. **`before_kind.llm` 寫擋板，擋不到當次 LLM。**

   agent 把這當成強制額度方案。[agent／07:61](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:61)

   但 tick 先檢查擋板，再跑 `before_kind`，接著直接跑任務。測試也明訂只擋下一項。[程式:163](../../../../proto6/src/py/lib/aos_tick.py)、[測試:91](../../../../proto6/src/py/tests/test_tick_kind.py)

   **改法：**放在 `think` 或獨立前置任務檢查。仍持有金鑰、能自行下指令的 agent，這只能叫配合式檢查；kernel 有 `.aos/` 寫權不等於硬強制。

4. **Plan9 的檔位 1 只限制入口可見性，不會縮小 socket 的能力。**

   提案保留 socket 協議，卻說掛自己的控制門、藏住別人的門就能驗隔離。[plan9／08:30、43、72](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:30)

   現行能連 ctl 就能控制任何項；能連任一 mq 門，就能報別項名字取信。這是已裁定的能力。[裁定:33](../../../../proto6/notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md)、[裁定:64](../../../../proto6/notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md)

   **改法：**檔位 1 改稱「固定路徑、限制可見入口」。分項隔離留給新介面另定；不必因此替現行 POC 加驗身分。

5. **每人一扇私門，接不上「新增成員只需 SIGHUP」。**

   agent 要每成員一扇門，建立流程卻只有加項、訂門、重讀。[agent／07:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:60)、[agent／05:24](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/05-生命週期.md:24)

   現行重讀只認啟動時已有的門。新項訂新門，整份重讀會失敗。[程式:31、50](../../../../proto6/src/py/lib/aos_daemon_reload.py)

   **改法：**POC 先固定成員與門。動態生成員另選預留門、重啟，或正式新增熱開門能力；三份目前都沒交代。

6. **掛齊子 daemon 模組，或加 namespace，都不等於清掉上層環境。**

   agent 建議子 daemon 掛控制與訊息模組；Plan9 說 namespace 能消掉外漏。[agent／06:74](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:74)、[plan9／08:42](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:42)

   現行只覆蓋同名變數，仍複製整份環境。上層 `MQ_MEMBERS`、下層只有 `MQ_TEAM` 時，前者會留下。[程式:154](../../../../proto6/src/py/lib/aos_daemon_run.py)

   **改法：**範本明寫清除、重設哪些 `AOS_DAEMON_*`；需要保留的上層門另命名。不要宣稱加模組或 bind 自動完成。

## 建議

- **介面只留一份共同正本。** kernel 想加三份信 schema，agent 想六種 `type` 共用一份。建議合成一份，兩邊共用範例；避免提案繼續各抄一份。[kernel／05:29](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/05-分階段落地.md:29)、[agent／07:68](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:68)

- **信落盤不要列進第一輪必做。** Plan9 把重開丟信列為值得先解的問題，但現行明訂記憶體信箱，POC 已接受不處理異常。保留成實驗選項即可。[plan9／08:26](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:26)、[現行原則:15](../../../../proto6/spec/daemon/mq.md)

- **方向題沒回答，不等於採納建議。** kernel 與 agent 都寫了未答就按建議實作。這只能套在例行細節，不能套在額度強制、隔離模型等方向題。[kernel／06:5](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/06-待決問題.md:5)、[agent／09:5](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/09-待決問題.md:5)、[使用者偏好](../../../../wf/workflows/common/user.md)

## 疑問

建議照這個順序決定：

| 優先 | 先決定什麼 | 我的建議與依據 |
|---|---|---|
| **1** | kernel 限制的是「開格數」，還是「真正計算數」？grant 何時寄？ | 先允許收信開格，LLM 前才查准許。小隊用私門，只在政策需要時寄 grant。先解必修 2；共門／私門的分歧已在 [agent／07:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:60) 明列。 |
| **2** | 額度先自律，還是不可繞過？數字是總額還是剩餘？ | 先自律。但要補清窗口起點、剩餘量、重寄是否重置、沒新 grant 是否沿用。現在只有 `kernel_seq`、`window_ticks` 和「最新為準」，仍不夠接線；agent 每格清 `work/` 還會清掉 grant。[kernel／04:63](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:63)、[agent／04:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/04-一格做什麼.md:60) |
| **3** | 主管住哪層？由誰切帳號、重讀子 daemon？ | `AOS_DAEMON_PID` 先明訂指「啟動自己的 daemon 主程序」。agent 圖中的主管與子 daemon 並排，拿到的會是共同父 daemon，無法直接重讀子 daemon。建議管理子 daemon 的 kernel 放進它裡面；巢狀 POC 先同帳號。[agent／06:53](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:53)、[帳號邊界:14](../../../../proto6/spec/daemon/account.md) |
| **4** | Plan9 是這輪必要條件，還是之後試玩的介面？ | 先完成現有 socket 版合作流程。namespace 可獨立試；FUSE 與常駐 LLM 服務後決。後者牽涉背景服務的新例外，提案自己也承認，不能當已沿用裁定。[plan9／08:50、55](/home/guanyu/projs/aos/.claude/worktrees/agent-a6aeb0c7833a5d35d/proto6/notes/proposals/2026-10-02-plan9/08-檔位與最小實驗.md:50) |

## 看過的範圍

- 三份提案全部章節：kernel 7 份、agent 11 份、plan9 9 份。
- `AGENTS.md`、使用者偏好、`SESSION-LOG.md`、`WAIT_USER.md`。
- verdicts 11 入口與相關分檔，含最新第二十七批。
- 現行 tick、daemon 控制／訊息／環境／重讀／帳號程式，以及相關 spec、schema、測試。

全程唯讀。未改檔、未 commit、未執行測試；以上判斷來自文件與程式閱讀。