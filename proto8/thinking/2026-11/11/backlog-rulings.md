# backlog-rulings：11-11 使用者一次翻掉的三項代定（mail_notify 間隔與起來那次、llm set system；do_task 帶自己的改動做了又撤）與維持現狀的七題

← [2026-11-11](README.md)｜[thinking](../../README.md)

11-11 下午使用者用選項框把當天幾條線留下的代定一起裁了（線 K 收集）。引號內是他選的選項文字。三項翻案在這裡施工；其餘七題選維持現狀，不動。

## 翻案三項

### 1. 新信提醒 `mail_notify`（原代定見 [mail-notify](mail-notify.md#邊緣代定與確認)）

| 題 | 原代定 | 使用者選 |
|---|---|---|
| 預設間隔 | 10 秒（`every_ms` 10000） | 「每 1 分鐘」 |
| agent 剛起來（含睡醒、重起）時信箱裡沒讀的舊信 | 通知一次（事件 `first` 時不看 notified，全算新的） | 「只提醒新到的」 |

施工：

- 範本 agent-fsm、eca-claude 的 `hooks.json`：`mail_notify` 的 `every_ms` 10000 → 60000；description 改「every minute」並加一句「起來、睡醒時已經在等的信不提醒，只提醒之後到的」。
- `lib/agent/mail_notify/_entry`：事件 `first: true`＝不寄提醒，只把 `new/` 裡現有的信名全寫進 `notified.json`（記成已知）；之後照常只提醒沒記過的。`--help` 跟著改。
- 測試：`lib/agent/tests/test_mail_notify.py` 原「`first` 再通知一次」那段拿掉，新增 `test_first_only_marks_waiting_letters`（起來時兩封在等＝不提醒、記成已知；下一次也不提；新到一封才提醒；notified.json 被刪了再 `first` 也一樣只記不提醒）。`templates/tests/agent-fsm/test_mail_notify_daemon.py` 先驗範本是 60000，再把抄來的那份改成 10000 跑（測試等不了一分鐘），其餘照舊。
- 知識節點：`aos/mailbox.json#/check`（每分鐘、`every_ms` 60000；免打擾例子的「instead of every minute」）、`#/check_hook`（`first` 那條改寫）、`aos/clock.json`、`aos/me/self_hook.json#/clock`、`aos/definition.json#/files`。
- 文件：aos-agent docs/06、範本兩份 README、templates/docs/01、02、lib/docs/03、NORMS 附錄 4 的 `hooks/mail_notify/notified.json` 那列（加「11-11 再註」）、[playground README](playground/README.md)（`sleep 12` → `sleep 65`）。歷史敘述（mail-notify 的實跑「16 秒內」、playground 01 的驗收表）照留；mail-notify 那兩條代定標「11-11 使用者翻案」。

### 2. `llm set system=…`（原代定見 [self-system 02](self-system/02-施工結果與代定.md#代定可翻案) 第 2 條）

| 題 | 原代定 | 使用者選 |
|---|---|---|
| `aos-agent llm set system=…` 與 `self_llm` 給 `system` 鍵 | 照存、stderr 一行提醒改用 `aos-agent system`／`self_system` | 「報錯並指路」 |

施工：

- `aos-agent llm set`：鍵裡有 `system`＝`ArgumentsBad`（`llm set` 的 help 本來就列這個代號），**一個鍵都不存**（同一次給的別的鍵也不存，免得半套），錯誤行：`aos-agent: error: ArgumentsBad system is not a brain setting: change the system text with aos-agent system set (self_system for the brain); nothing stored (usage: aos-agent [--daemon D] system [--target NAME] set [FILE | -])`。help 那句改成「system=... is an error and nothing is stored」。其他不認得的鍵照舊（照存＋warning）。
- `self_llm`：`settings` 裡有 `system`＝自己先擋（不叫下層），`ArgumentsBad`，錯誤行指 `self_system`（`{"op": "set", "text": "..."}`）。tooldef 那句補「a "system" key is refused」。
- 測試：aos-agent `test_system.py::test_llm_set_system_points_here` 改成驗退 1、錯誤行、沒有 warning、`llm.json` 沒建、之後單給 `model=m` 照存；self_llm `test_bad_arguments` 加一格。
- 知識節點：`aos/me/self_llm.json`、`aos/cli/talk_settings.json#/llm`。文件：aos-agent README、docs/07。

### 3. `do_task` 用呼叫者自己的定義時，呼叫者自己改過的東西（原代定見 [do-task-rename](do-task-rename.md#代定) 第 2 條）

| 題 | 原代定 | 使用者選 |
|---|---|---|
| 呼叫者用 `self_tools`／`self_system`／`self_hook` 等改過的（都在呼叫者 stack） | 不帶，小幫手只拿定義 | 「帶過去」（小幫手跟「現在的自己」一樣） |

**這項後來撤掉、沒進 main**：線 K 照「帶過去」做完一版（抄 tools／llm／hooks／system 四份覆蓋、相對路徑重算、新代號 `InterfaceBad`、一支假腦整合測試）後，頂層傳話先暫停，接著使用者重新設計 do_task（fork 單獨拉出成工具、do_task 改成 save／load，原話與裁定見 [do-task-rename](do-task-rename.md) 續記）——fork 一律整份連對話複製，已涵蓋「帶過去」。那一版程式與測試整份還原，不 commit。

## 維持現狀的七題（使用者選了維持，記錄用）

| 題 | 現狀 |
|---|---|
| `mailbox_read` 只讀最舊的 | `{}` 讀最舊一封；`all`／`keep` 照舊 |
| eca 畫面開著改 system | 只印提醒、等重開才生效（[self-system 02](self-system/02-施工結果與代定.md) 代定 1） |
| system 空字串 | 什麼都不送（fsm 不送 system 訊息、eca 不附加；代定 4） |
| claude 每輪重讀 system | 宣告了 system 就一律 `--system-prompt-snapshot off`（代定 7） |
| `agents_ctl` 可刪別人的 subagent | 不管 |
| hook 預設 | 壞掉就停（`on_error` 預設 stop）、逾時 60 秒 |
| `on_clock` 不對齊整數倍 | 「上次」記成這次的 cycle、間隔是「至少 N 格」（[clock-hook 02](clock-hook/02-施工結果.md) 代定 3） |

## 已裁（原「待裁」，11-11 稍後）

1. **睡著時到的信**：照「只提醒新到的」，起來那次把信箱裡在等的全記成已知——所以**睡著（或停著）時寄來的信，醒來後永遠不提醒**（只能自己 peek）。選項：「維持：起來時在等的都不提」／「睡前記過的不提，睡著時新到的醒來提醒一次 (推薦)」（做法＝起來那次照 notified.json 比，不再特別處理 `first`）。
   **使用者選「睡著時新到的要提」**（線 K 施工）：

   - `lib/agent/mail_notify/_entry`：事件 `first` 也照 `notified.json` 比——睡前提醒過的（還在 `new/`、記在裡面）不再提，睡著期間新到、還沒提醒過的提醒一次（合成一句，同平常）。
   - **代定 1（全新起來）**：`notified.json` 不在（或壞了，不是清單）＝沒有記錄、分不出睡前睡後；`first` 那次照原裁「只提醒新到的」，信箱裡在等的只記成已知、不提醒。不是 `first` 時沒記錄＝照舊全算新的（例：小格被人清掉，下一次就提醒一次）。
   - **代定 2（記錄形狀）**：`notified.json` 照舊只存「已通知、還在 `new/` 的信名」——判「這封提醒過沒」夠用（讀掉的離開 `new/`，不會再被當新信）；但原本沒新信、信箱是空的時候不寫檔，於是「起來時信箱空、睡著時寄來第一封」醒來會被當成全新起來而吞掉。改成**每次跑都寫**（沒信箱、沒信也寫 `[]`）：檔在＝「一直在看」，檔不在才是全新。格式沒變。
   - 睡前最後一次檢查之後、睡著之前到的信：沒提醒過，醒來那次照樣提（「還沒提醒過」本來就包含它們）。
   - 測試：`lib/agent/tests/test_mail_notify.py` 加 `test_wake_tells_letters_that_came_while_asleep`（睡前 A 提醒過；睡著時 B、C 到；醒來只提一則「2 new letters from B, C」；再睡再醒不重複）、`test_first_letter_while_asleep_without_mailbox_before`（起來時沒信箱也寫 `[]`；睡著時信箱建好、寄來第一封，醒來提得到）；原 `test_first_only_marks_waiting_letters`（全新起來只記不提醒、notified.json 被刪了再 `first` 也一樣）照留。整夾數字見 [goal 02 的稍後一節](goal/02-裁定與施工結果.md#11-11-稍後使用者裁定與修改)。
   - 知識節點 `aos/mailbox.json#/check_hook`、`aos/me/self_hook.json#/clock`；範本兩份 `hooks.json` 的 description 與 README；templates/docs/02、aos-agent docs/06、lib/docs/03；NORMS 附錄 4 `hooks/mail_notify/notified.json` 那列加「11-11 再註」。
   - 要重建什麼：不用。已建的定義抄出去的 `hooks.json` description 是舊句子（只是說明，不影響行為；行為在 handler 裡，`$AOS_HOME` 下的那支一換就生效）。

## 要重建什麼

- **試驗場（兩台）與任何既有 agent 的 stack**：範本 `hooks.json` 改了 60000，但已建的定義是抄出去的那份——要重抄範本的 `hooks.json`（或 `aos-agent hook --target X add --replace -n mail_notify --event on_clock --every-ms 60000 …`）才會變 1 分鐘；不重抄照 10 秒跑、不壞。`hooks/mail_notify/notified.json` 格式沒變，不用刪。
- 以前用 `llm set system=…` 存進 stack `llm.json` 的 `system` 鍵：身體本來就不讀它，留著無害；要清就 `aos-agent llm --target X rm system`（rm 不擋）。
- tooldef 快取（`~/.cache/aos-mcp-aos/tools.json` 這類）要重刷才看得到 self_llm 的新說明。
