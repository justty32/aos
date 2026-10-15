# KISS 審稿：kernel 一族

範圍：NORMS 09-kernel（N-42）、lib `aos_kernel_llm.py`／`aos_kernel_general.py`／`aos_kernel_judge.py`／`aos_kernel_judge_rules.py`／`aos_gate.py`／`aos_mailbox.py`、`kernel_llm.md`／`kernel_general.md`、`demo/kernels/`、`tests/test_gate.py`／`test_kernel_general.py`。只審規範與實作，概念不審。只寫稿，不改檔。

← [討論紀錄](../README.md)｜原則：C-52、C-53，KISS 在它們之上（[原文](../2026-10-15-principles.md)）｜前情：[kernel 截流](../2026-10-15-kernel-intercept.md)、[LLM kernel](../2026-10-15-llm-kernel.md)、[通用 kernel](../2026-10-15-general-kernel.md)、[判官實跑](../2026-10-15-judge-live.md)、[之二](../2026-10-15-judge-live2.md)

一句話總結：**現在是「六支程式、兩種 kernel、三套規則」在做一件事——把一封信排進一格跑掉。收成兩支程式（閘門、kernel）、一套規則（級數→deadline→先來後到）、判官可有可無，就夠。** 下面每條：現況 → KISS 版 → 動哪裡 → 風險。使用者習慣照推薦走，所以每條只給一個推薦。

## 甲、刪（優先）

1. **兩種 kernel → 一種。** 現況：`aos_kernel_llm.py`（一拍挑 `slots` 封跑完）與 `aos_kernel_general.py`（一拍＝忙碌期、問判官），後者已經完整包含前者（`judge` 沒寫＝用前者的 `order`）。KISS：只留一支 `aos_kernel.py`，`judge` 沒寫＝內建規則，這就是「管 LLM 的那種」；`aos kernel llm|general` 子命令收成 `aos kernel`。動：刪 `aos_kernel_llm.py`、`bin/aos`、N-42、`kernel_llm.md`＋`kernel_general.md` 併成 `kernel.md`、兩份 demo 併一份、兩份測試併 `test_kernel.py`。風險：使用者 N-42 原話是「先做兩種」——但兩種是**用途**，不是兩支程式；thinking 通用 kernel 自定點 6 本來就寫「跑順再併」，現在順了。

2. **三套排序規則 → 一套。** 現況：`aos_kernel_llm.order`（deadline 插隊＋級數＋aging＋cost＋先來後到，程式內用）、`aos_kernel_judge.decide_rules`（包一層）、`aos_kernel_judge_rules.py`（獨立腳本，規則**不一樣**：human 先、沒 deadline、沒 aging；`LEVELS`、`level()` 各抄一份）。KISS：規則只有一份、在 kernel 裡（判官錯時本來就要有它）；刪獨立腳本與 `judges/rules.json`，demo 第 1 段改成「不設判官」。動：刪 `aos_kernel_judge_rules.py`、`demo/kernels/general/judges/rules.json`、`judges/schema.json`（只有 aos_tree 的測試用它，v3 已要刪 aos_tree）。風險：失去「規則也能當成一格 inst」的示範——判官格的示範由 `broken.json`、agent 判官留著就夠。

3. **排序只留「級數 → deadline → 先來後到」。** 現況：五層 key——deadline 剩不到 `near_ms` 插隊、有效級數（級數＋等幾拍 // `aging_ticks`）、deadline、`_metainfo.cost`、先來後到；外加 state 窗的 `seen`（每封第一次看到的拍）、log 的 `waited`。使用者只定了「誰先來誰先上」「priority 和 deadline 兩個」，其餘全是 AI 自定（aging、near_ms、cost）；實跑證明 aging 以拍計在一格慢腦下永遠是 0。KISS：`order` 三層，`aging_ticks`、`near_ms`、`_metainfo.cost`、`seen`、`waited` 全刪；deadline 已過照舊 `DeadlineMissed`。動：`aos_kernel.py`、`kernel.md`、demo LLM 段「aging」整段刪、`test_aging`／`test_metainfo_cost_then_fifo`／`test_deadline_jump` 刪或改。風險：low 可能餓死——那是呼叫者自己填 low 的結果，不是 kernel 的事；要急就填 deadline。

4. **閘門的 `wait_ms`／`QueueTimeout` 刪。** 現況：閘門自己再數一次「排隊多久」，到了撤信回 `QueueTimeout`；另有 `poll_ms`。但包閘門的那張 inst 本來就有 `timeout_ms`，逾時 aos_inst 送 SIGTERM，閘門收到就撤信——兩個鐘量同一段等待。KISS：閘門只有一個外層鐘；`wait_ms`、`poll_ms` 與它們的驗證、`QueueTimeout` 都刪，輪詢間隔寫死 50 ms。動：`aos_gate.py`、`kernel.md`、`test_queue_timeout_withdraws` 刪。風險：呼叫端分不出「排太久」跟「跑太久」——它看到的都是 `timed_out`，C-52 說它本來就不該分。

5. **`AOS_PRIORITY`／`AOS_KERNEL` 的後備邏輯刪。** 現況：閘門 `mailbox` 沒寫就讀 `AOS_KERNEL`、`priority` 沒寫就讀 `AOS_PRIORITY`（還先當 JSON 解、解不了當字串），demo 全靠它。KISS：這兩件事 `$env` 指示詞已經會做——gate.json 寫 `"mailbox": {"$env": "AOS_KERNEL"}`、`"priority": {"$env": "AOS_PRIORITY"}` 就是同一個效果；閘門程式裡不認任何環境變數。動：`aos_gate.py`（`_env_priority`、`or os.environ.get`）、demo 四張 gate.json、`kernel.md`、`test_env_priority_and_plain_stdin`。風險：`$env` 變數不存在＝錯（現況是靜靜不填）——demo 本來就一定設，正好符合「入口默認正常」。

6. **kernel 替判官拿掉 `AOS_KERNEL` 這段刪。** 現況：`ask_judge()` 把繼承的 `AOS_KERNEL` 拿掉、判官自己 `envs` 指回本信箱也拿掉（還 `realpath` 比對），防判官的腦排回自己的隊卡死。這是上層伸手改下層的環境——C-52 明確不准，而且跟「卡死就卡死」（使用者定）矛盾。KISS：kernel 跑判官跟跑任何 inst 一樣，一個 key 都不碰；判官作者自己別把腦指回來（寫進 kernel.md 慣例，跟「只包葉子」同一段）。動：`aos_kernel_judge.py`、`kernel.md`、`test_judge_env_has_no_own_mailbox` 刪。風險：判官真的指回來會卡住——跟其他巢狀卡死一樣，不防護。

7. **「便宜的直接跑」那條路刪。** 現況：信的 `_metainfo.resource` 沒寫或 `"none"`＝不佔格、不問判官、直接起跑（`direct`、`k is None` 四處分支、`count.direct`）。會經閘門排隊的 inst 就是要佔格的，沒寫資源是作者漏寫。KISS：資源沒寫＝跟不認得一樣回 `ResourceUnknown`（同一條錯誤路），`"none"` 這個別名也刪。動：`aos_kernel_general.py`、`aos_kernel_judge.resource()`、`kernel.md`、demo `gates/fake.json`、`boss/brain.json` 補一行 `_metainfo.resource`、`test_cheap_runs_without_slot_or_judge` 改。風險：每張被包的 inst 都得寫一行 `_metainfo`——本來就該寫。

8. **「只有一封且有空格＝不問判官直接跑」刪。** 現況：三條省判官的規則：局面沒變不問、沒空格不問、只有一封直接跑（`direct`）。第三條讓判官看不到那封、不能 reject 它。KISS：只留前兩條（都是使用者點頭過的），有信有空格就問。動：`aos_kernel_general.py`、`kernel.md`、`test_single_letter_with_free_slot_skips_judge` 刪。風險：多問判官一次（幾秒）——判官慢是判官的事。

9. **判官回話的 `defer` 刪。** 現況：判官回 `{run, defer, reject}`；但補位做了之後，`defer` 跟「沒點名」一模一樣（空格仍空就被規則補上），純裝飾。KISS：判官只回 `{run, reject}`，沒點名＝不是我挑的。動：`aos_kernel_judge.py`、`kernel.md`、`judges/agent/system.md`、測試裡所有 `defer`。風險：使用者「隨意」定過「只回三種話」——三種話還在（跑、不跑、沒說），少一個沒用的 key。

10. **判官逾時預設 `JUDGE_TIMEOUT_MS`＝30 秒刪。** 現況：判官 inst 沒寫 `timeout_ms` 時 kernel 替它填 30 秒——上層替下層定逾時。KISS：判官 inst 自己寫 `timeout_ms`（demo 三張都有），沒寫＝不限（同 inst 通則）。動：`aos_kernel_judge.py`、`kernel.md`。風險：判官掛住 kernel 這拍就掛住——卡死就卡死。

11. **kernel 設定 `log` 刪。** 現況：每處理一封往 jsonl 追加一行（`decide`／`start`／`done`／`drop`，帶 reason、backfill、cut…），只有 demo 在看。KISS：kernel 的輸出就是 state 窗＋每拍 stdout 一份；demo 從呼叫端看順序（`slots` 1 時回來的順序就是服務順序；通用 demo 在呼叫者回來時印一行）。動：`aos_kernel_*.py`、`aos_mailbox.log`、兩份 demo `run.py`、`kernel.md`。風險：demo 看不到「判官挑的 vs 補位」——真要看，state 窗的 `judge_error` 加上回來的順序夠判斷。

12. **state 窗瘦身。** 現況：loop 骨架＋`queue`、`running`、`slots`、`budget`、`served`（累計數）、`seen`、`judge_error`、`judge_asked`（跨拍的局面簽名）。KISS：留 loop 骨架＋`queue`、`running`、`slots`、`budget`、`judge_error`；`served`（裝飾）、`seen`（隨 aging 走）、`judge_asked`（補位之後跨拍局面不變幾乎不會發生，簽名只在記憶體內比）刪；`queue` 每封只留 `priority`、`_metainfo`、`waited_ms`。動：`aos_kernel_general.py`、`kernel.md`、demo 印 `served` 那行。風險：無。

13. **stdout 摘要瘦身。** 現況：`{runs, served[], dropped[], waiting, budget, judge: {asked, fallback, direct, skipped}}`。KISS：`{runs, served[], dropped[], waiting, budget}`，判官統計刪（出錯看 state 窗 `judge_error`）。動：同上。風險：無。

14. **三個空的錯誤類別刪。** 現況：`GateError`（帶永遠是 1 的 `exit`）、`KernelLlmError`、`KernelGeneralError` 都只是 `CliError` 的空殼。KISS：直接丟 `CliError`。動：`aos_gate.py`、`aos_kernel_*.py`。風險：無。

15. **`slots` 純值糖刪。** 現況：`slots` 收 `{"llm": 1, "cpu": 2}` 也收純值 `n`＝`{"llm": n}`，沒寫＝1。KISS：只收物件、沒寫＝`{}`（來一封有資源的就 `ResourceUnknown`）。動：`aos_kernel_general.check`、`kernel.md`、`test_bad_config`。風險：設定多打六個字。

## 乙、合併

16. **六個檔 → 兩個。** 現況：`aos_gate.py`、`aos_mailbox.py`、`aos_kernel_llm.py`、`aos_kernel_general.py`、`aos_kernel_judge.py`、`aos_kernel_judge_rules.py`，相依鏈五層。KISS：`aos_gate.py`（閘門命令列＋信箱的讀寫認領回信，兩邊共用的「信長什麼樣」只在這裡定）與 `aos_kernel.py`（身體＋規則＋問判官）；kernel 只 import gate。動：刪四檔、`lib/README.md` 相依那行、wf code map。風險：無——上面 1～11 做完，剩下的碼本來就不到兩百行。

17. **判官答案的檢查收成一條。** 現況：多一個不認得的 key、`run`／`defer` 不是字串陣列、同一個 id 出現兩次、reject 少 `msg`… 各自一個 `ValueError` 訊息；「多 key 就錯」還跟 C-48「只處理認得的 key」打架。KISS：判官錯只有一種——「stdout 最後一份不是物件、結束碼非 0、逾時」；是物件就只拿 `run`（認得的 id、重複去掉）與 `reject`（有 `id`、`error.code` 的那些），其他一概忽略。動：`aos_kernel_judge.parse_decision`、`kernel.md`、`test_judge_failure_falls_back` 的五種縮成三種。風險：小模型多回一個 key 以前是「錯、退回規則」，現在照用——更寬鬆，不會更危險。

18. **閘門的 priority 不驗。** 現況：`normalize_priority` 對不是字串／數字／物件的值丟 `FieldType`。KISS：`expand()` 完照抄進信；kernel 的 `level()`、`deadline()` 本來就把看不懂的當 0／None。動：`aos_gate.py`。風險：無（入口默認正常）。

19. **「串流 key 一律由 kernel 填」寫成一句。** 現況：閘門 `letter()` 把 target 的 `stdout`／`stderr`／`exit` 轉絕對路徑抄進信，kernel `run_letter` 再用八個 `False`（`stdin_inherit`、`stdout_append`、`stderr_mkdir`…）跟 `stderr_merge` 特例把它們蓋掉——抄了又蓋。KISS：閘門不抄串流 key；kernel 跑信時把所有 `std*`、`exit` 開頭的 key 去掉再填自己的旁檔，kernel.md 一句「被包的 inst 串流由 kernel 決定，寫了也不算」。動：`aos_gate.letter`、`aos_mailbox.run_letter`、`kernel.md`。風險：target 原本寫 `exit` 檔的人拿不到那個檔——它從來就拿不到（檔會落在 kernel 的 cwd）。

20. **閘門的 `_cleanup`／`outputs`／`withdraw` 三處刪旁檔收成一處。** 現況：三個函數各自處理「回信＋三個旁檔」。KISS：一個 `remove(box, name)`，誰最後碰到誰叫。動：`aos_gate.py`。風險：無。

## 丙、跨層偷看（C-52／C-53 殘留）

21. **kernel 讀 target 的 stdout 旁檔算 token。** 現況：`run_letter` 跑完去讀旁檔、`read_stream` 取最後一份的 `usage.total_tokens`。kernel 在讀被叫者的輸出內容——下層的資料。但額度是使用者定的（「token 消耗量是否見底」），計量只能從這裡來。KISS：**留著**，但寫明這是 kernel 唯一一處往下看、只認 `usage.total_tokens` 一個 key、沒有＝0，別的一概不看；「額度見底只擋 `llm` 資源的信」照舊。動：`kernel.md` 一句。風險：無。

22. **判官的 `ask_judge.py` 四種錯誤代號刪。** 現況：`Usage`、`DefinitionMissing`、`ReturnMissing`、`JudgeFailed`、`JudgeReplyBad`，還從 reply 裡抓第一個 `{` 到最後一個 `}`。kernel 那邊不管哪種都是「判官這拍沒給合法答案」，分五種沒人看。KISS：任何失敗一律退 1、stderr 一份 `JudgeFailed`；reply 原樣印（不是 JSON＝kernel 退回規則，同一條路）。動：`demo/kernels/general/judges/agent/ask_judge.py`。風險：無。順帶：v3 的 E（parent 鏈退場）、G（agent 當工具用 `sh -c 'aos loop; cat ret.json'`）落地後，這支腳本大概可以整個退場、判官 inst 直接用 G 的寫法；這輪先瘦。

## 丁、已在別條線處理、這裡只點一下

- 閘門 `target` 只收內嵌 inst、kernel 的 `judge` 內嵌、閘門與 kernel 命令列零引數（`-`、`--`、`Usage` 錯都走）、demo 三張 `sh -c` 拼 `AOS_DEMO` 的工具 inst：inst-exec v3 的 H、I、G，不重提。
- 閘門把呼叫者 stdin 寫成旁檔 `reply/<名>.stdin`：v3 K 說等 kernel 這條線收——v3 的 D（inst `stdin` 收內嵌）落地後就直接嵌進信、少一個旁檔；判官的 stdin 也一樣不必落暫存檔。這稿算是回覆 K：**要收，跟著 D 一起做**。
- 判官錯濃縮成一條、`max_fails` 拿掉：principles 第 3 條已做。

## 最小核心

從零重寫，kernel 這塊只留：

- **一支閘門 `aos_gate.py`**：讀 gate.json（`mailbox`、`target`、`priority`），把 target 那張 inst 加 `priority`／`reply`／`sent` 寫進信箱 new/，等回信，原樣吐 stdout／stderr、退 target 的碼；收到訊號撤信。信箱＝`tmp/ new/ cur/ reply/` 四格，信長什麼樣只在這個檔定。
- **一支 kernel `aos_kernel.py`**：給 loop 拍的身體，設定只有 `mailbox`、`state`、`slots`、`judge`（選填）、`budget`（選填）。一拍＝忙碌期：殘信回 `KernelRestarted`；讀信——過期、資源不認得、額度見底各回一個錯；有信有空格、局面變了就問判官（沒判官或判官沒給合法答案＝規則），判官的 `run` 先、空格用規則補；一封一條執行緒跑，跑完回信放格。規則一句話：級數高的先、deadline 近的先、先來後到。
- **一份 `kernel.md`**、**一份 demo**（三段：級數與 deadline、三種資源搶格＋壞判官退回規則、巢狀只包葉子）、**一份 `test_kernel.py`**。
- **N-42 一句**：kernel＝給 loop 拍的一張 inst，從信箱挑信、排進格、跑完回信；誰先跑由判官格決定，判官沒寫或答錯＝內建規則；閘門把任何 inst 變成一封信。

不在範圍：CONCEPTS（C-09～C-15、C-28、C-29、C-38、C-47）這次不審、不提刪改。
