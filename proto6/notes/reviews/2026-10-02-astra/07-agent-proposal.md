# agent 架構提案 審查（astra，2026-10-02）

## 一段話結論

**五項一步可以用現有零件組起來，但提案還不能直接照做。** JSON 結構沒有發現 schema 錯誤；問題主要在執行順序、路徑與控制語意。最重要的是：`before_kind.llm` 擋不到本次 LLM、`pause` 擋不住寄信叫醒、新增私人門不能只靠 SIGHUP。這些都是正常使用就會碰到的接線問題，不是要求 POC 補邊緣處理。

以下「提案」指指定 worktree 裡的 `2026-10-02-agent/`；程式證據均取自主工作樹。

## 必修

1. **額度 hook 放錯時機，擋不到本次 LLM。**  
   提案 [07-kernel介面.md:61](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:61) 說 `before_kind.llm` 寫 `tasks-blocked` 就能擋。實際是先檢查擋板，才跑 hook，再跑任務：[aos_tick.py:163](../../../../proto6/src/py/lib/aos_tick.py)。[測試:91](../../../../proto6/src/py/tests/test_tick_kind.py) 也明確驗證只擋下一項。  
   **改法：**把檢查掛在 `after_task.think`，提前寫 `{"kinds":["llm"]}`。

2. **換成政策 hooks 後，summary 會消失。**  
   提案 [03-agent長相.md:63](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/03-agent長相.md:63) 把整個 `hooks` 換成 `$ref`，但 [10-範例JSON.md:91](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/10-範例JSON.md:91) 的政策檔只有 budget、meter、git。現行 [aos_tick_table.py:128](../../../../proto6/src/py/lib/aos_tick_table.py) 不會合併原本的 hooks。  
   **改法：**政策檔保留 summary，或只引用個別政策掛點。本地留下 `after_all`。

3. **工具 inst 的工作目錄與輸入輸出位置對不上。**  
   提案 [10-範例JSON.md:48](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/10-範例JSON.md:48) 把 `cwd` 指回 agent 家，卻保留 `stdin:"args.json"`、`stdout:"out"`、`exit:"exit"`。這些路徑全部相對 `cwd`：[aos_inst.py:123](../../../../proto6/src/py/lib/aos_inst.py)。因此讀不到放在呼叫目錄的 arguments。04 篇若不補 `cwd`，又會找不到 `tools/wc.sh`。  
   **改法：**固定 `cwd` 為 agent 家，三個輸入輸出欄位改成本次呼叫目錄的完整路徑。

4. **`pause`、`kill` 被當成了更強的停止機制。**  
   提案 [05-生命週期.md:29](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/05-生命週期.md:29) 說暫停後「信照收、不跑」。但 [測試:120](../../../../proto6/src/py/tests/test_mq_send.py) 明測寄信仍跑一次。提案 [06-多agent與上下層.md:68](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:68) 又把 `kill` 說成停整組；實際只殺當次，仍會照週期再開：[aos_daemon_ctl.py:15](../../../../proto6/src/py/lib/aos_daemon_ctl.py)。  
   **改法：**寫清 `pause` 只停週期排程，`kill` 只殺當次。LLM 限制靠 grant／擋板；永久移除排程要拿掉設定項。`max_awake:1` 不能只靠 kernel 少叫一個來保證。

5. **新增成員的私人門，不能只靠 SIGHUP。**  
   提案 [05-生命週期.md:24](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/05-生命週期.md:24)、[06-多agent與上下層.md:63](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:63) 說改設定再重讀即可。但 `modules.mq` 不熱套用，新訂閱仍按啟動時的門驗：[aos_daemon_reload.py:50](../../../../proto6/src/py/lib/aos_daemon_reload.py)。[測試:75](../../../../proto6/src/py/tests/test_mq_doors.py) 直接涵蓋新增門被拒。  
   **改法：**POC 先預建門，再熱加成員；增加門就重開 daemon。子 daemon 範本也要列 `modules.reload`。

6. **daemon 範例把相對路徑起點說錯了。**  
   提案 [03-agent長相.md:80](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/03-agent長相.md:80) 說 `"."` 就是設定檔所在。實際省略 `cwd` 時，用的是 daemon **啟動目錄**：[aos_daemon_config.py:155](../../../../proto6/src/py/lib/aos_daemon_config.py)。  
   **改法：**範例加上 kernel 家的絕對 `cwd`。這也固定 inst 與 socket 的起點。

7. **「閒置 agent 只佔磁碟」不符合現行程式。**  
   提案 [02-方案取捨.md:40](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/02-方案取捨.md:40)、[06-多agent與上下層.md:79](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:79) 漏算常駐資源。現行每個 inst 一條執行緒，每扇門再一條：[aos_daemon_run.py:167](../../../../proto6/src/py/lib/aos_daemon_run.py)、[aos_daemon_ctl.py:52](../../../../proto6/src/py/lib/aos_daemon_ctl.py)。一小時的保底週期也仍會叫醒。  
   **改法：**改成「沒有常駐 agent 程序，但 daemon 仍保留執行緒與信箱」。撤掉已能承載萬人的推論；分成小隊不會消除這些成本。

8. **human 門的權限範例接不通。**  
   提案 [06-多agent與上下層.md:27](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:27) 在 `guanyu 0700` 目錄下另開 `0730` 子門。其他帳號仍穿不過母目錄。範例 daemon 又降成 `aos` 才建立 socket：[aos_daemon.py:148](../../../../proto6/src/py/lib/aos_daemon.py)。  
   **改法：**把投遞門放在可穿越的共同目錄。明列寄信帳號的穿越權與 daemon 帳號的建檔權。

9. **共用門不是大家搶同一封信。**  
   提案 [06-多agent與上下層.md:79](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:79) 用「take 取走就沒了」否定共用門。實際每個訂戶各拿一份副本，take 只清自己的信箱：[aos_daemon_mq.py:93](../../../../proto6/src/py/lib/aos_daemon_mq.py)。  
   **改法：**不是給自己的副本可以丟掉。保留「共用門會叫醒全員」作為採私人門的理由即可。

## 建議

五項接力的正確落點如下。這張表可取代各篇重複描述。

| 階段 | 現有零件與欄位 | 核對結果 |
|---|---|---|
| inbox | `insts.<項>.mq` 訂門；`aos-mq take <門>`；`AOS_DAEMON_INST` 指定信箱 | 可接。同 daemon 選一扇可連的門，take 一次就取完，不必逐門取 |
| think | `tasks[].kind:"llm"`；提前寫 `.aos/tick/tasks-blocked` 的 `kinds` | 可只跳過 llm；全擋則用空檔 |
| llm | 普通任務的 `argv`、`envs`；request／response 檔接力 | 可接，但 `aos-llm` 要新造。非零退出不會阻止後面的 act |
| act | `aos-exec`＋inst 的 `argv/cwd/stdin/stdout/exit` | 可接，須修上述路徑 |
| remember | 寫 history／status；`aos-ctl wake --keep-schedule` | 可自叫。省略 inst 時用 daemon 提供的控制 socket 與 inst 變數 |
| summary | `hooks.after_all`；`aos-mq send "$AOS_DAEMON_MQ_KERNEL" <JSON>` | tasks-blocked 後照跑；硬擋板、busy、壞表則不跑 |

證據：[MQ client:50](../../../../proto6/src/py/lib/aos_mq.py)、[tick 主流程:158](../../../../proto6/src/py/lib/aos_tick.py)、[ctl client:56](../../../../proto6/src/py/lib/aos_ctl.py)。

另外三處可簡化：

- **inbox 與 summary 共用「還有待辦」的判斷。** [04:22](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/04-一格做什麼.md:22) 只列新信，卻在 [07:33](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:33) 把落檔未處理的舊信算成 ready。建議 inbox 也檢查它，避免額度擋過後又被誤判沒事。
- **history 只交給 remember 寫。** [04:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/04-一格做什麼.md:60) 又說 think 把工具結果「吃進 history」。建議 think 只組 request，remember 統一追加與清除已消費內容。
- **合併叫醒的驗收要寫投遞時點。** [08:21](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/08-分階段.md:21) 的「連寄三封只跑一格」太絕對。開跑前可合併；跑到一半收到信會再補一次。見 [aos_daemon_mq.py:7](../../../../proto6/src/py/lib/aos_daemon_mq.py)。

## 疑問

1. **grant 是額度通知，還是准許下一格開跑？**  
   agent 每格寄 summary；對方 [kernel 契約:68](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:68) 又說每格重寄 grant。兩種信都會叫醒收件者，照字面可能形成「grant → summary → grant」空轉。  
   **建議：**只向本次獲准執行的成員寄 grant；收到 `ready:false` 不因而重寄。把這條補進兩邊契約。

2. **跨格額度存哪裡，沒 grant 時怎麼辦？**  
   [07:47](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/07-kernel介面.md:47) 配的是多次呼叫、多格窗口；[04:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/04-一格做什麼.md:60) 卻每格清掉包含 grant 的 `work/`。扣帳、替換與到期也尚未定清楚。  
   **建議：**grant 與已用量放 `state/`，由 kernel 決定窗口。需拍板的是：有 kernel 卻沒 grant，要先等，還是用預設額度。

3. **主管怎麼取得兄弟子 daemon 的 PID？**  
   [06:53](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:53) 中，主管與子 daemon 是上層的兩個不同項。即使新增 `AOS_DAEMON_PID`，主管拿到的仍是上層 PID。  
   **建議：**補上子 daemon 回報 PID 的檔案或訊息接線，並明訂由同帳號主管送 HUP。只新增環境變數還沒接完。

4. **巢狀 daemon 要保留哪些上層門？**  
   [06:74](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/06-多agent與上下層.md:74) 建議掛 control＋mq 解決外漏。但 [aos_daemon_run.py:154](../../../../proto6/src/py/lib/aos_daemon_run.py) 只覆寫同名變數，上層獨有的門仍會留下。  
   **建議：**明列哪些是刻意保留的跨層地址。其餘先清掉再補，別把「掛模組」當成完整隔離。

5. **普通文字回答由誰寄回？多封信怎麼分輪？**  
   [05:60](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/05-生命週期.md:60) 畫的是 act 自動寄回普通回答；[04:25](/home/guanyu/projs/aos/.claude/worktrees/agent-af6407b4622efc9cd/proto6/notes/proposals/2026-10-02-agent/04-一格做什麼.md:25) 主要只定工具呼叫。  
   **建議：**POC 先一次處理一封對話信，保留 `reply_door/ref`；沒有 tool_calls 的回答由 act 寄回。這樣不必先造多對話排程。

## 看過的範圍

- 指定提案全部 **11 份**。另讀同日 kernel 提案的介面與推薦方案，核對對接主張。
- 現行 spec 的 tick、hooks、tasks-blocked、daemon 各模組、慣例與協議；對照 Python 實作及相關測試原碼。
- **16 個 JSON 區塊均可解析。** 五項 tasks、回聲 tasks、daemon 設定、環境變數 inst 通過現行 schema 靜態核對。新 agent 格式尚無現行 schema，不能宣稱已驗證。
- **未改檔、未 commit、未執行測試或啟動 daemon。** 驗證限閱讀與不寫檔的靜態解析。