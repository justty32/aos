# 2026-10-24 LLM kernel 第一版：問腦變成請求、kernel 排隊跑

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-15 kernel 截流](2026-10-15-kernel-intercept.md)（閘門／信箱、六題照建議）、[10-15 LLM kernel](2026-10-15-llm-kernel.md)（priority、排序六條）、[10-19 重寫順序 § ⑤、第 3 題](2026-10-19-rewrite-order.md)、[10-21 計畫 § 1.2](2026-10-21-plan.md)、[10-23 agent 與 kernel](2026-10-23-agent-kernel.md)、[10-24 exec 直接放單子](2026-10-24-exec-relative.md)、[10-24 `_metainfo`](2026-10-24-metainfo.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。相關條文：[C-09～C-12、C-38、C-47](../docs/CONCEPTS/04-kernel.md)、[C-20](../docs/CONCEPTS/05-agent.md)、[N-42](../docs/NORMS/09-kernel.md)、[N-14、N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-60](../docs/NORMS/10-基礎設施-定義與工作區.md)、C-54。程式：[aos-kernel-llm](../impls/aos-llm-kernel/README.md)、[aos-gate](../impls/aos-gate/README.md)、[demo/kernel-llm](../demo/README.md)。

## 使用者原文（10-24，逐字）

> 然後可以開始做kernel了

頂層問三份 kernel 稿（LLM kernel、通用 kernel、10-23 在 fsm 上做的那種）做哪個：

> LLM kernel，也就是把brain這塊弄成一個請求，而不是直接打API，請求會被丟到某個地方，由kernel排隊跑

10-24 晚（沙箱裡的 agent 能不能用 kernel）：見 [sandbox 原文](2026-10-24-sandbox.md#使用者原文10-24逐字)。

做到一半，頂層轉述的兩句：

> 我現在沒空管這些小事，都按建議做

> _metainfo好了之後，讓kernel實際去用用看。

10-25（C-54 命名方法 [R6](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)）：「計數這塊，幫我改成counter_*」；上限 `max_*`、served 的 `served_at` 兩題回「都好」（頂層代定、可翻案）。下面的名字已照改。

## 決定

- **做 LLM kernel**（使用者 10-24）：agent 那格不再直接跑腦，而是把「問腦」這張單子當成請求丟進信箱，由 kernel 排隊跑。
- 照用 10-15 已定的：信箱（N-16 Maildir）、閘門；只包腦；排隊算在呼叫者那格的 `timeout_ms` 裡（閘門沒有自己的等待上限）；kernel 重起時 `cur/` 那封回錯不重跑；priority 的三種寫法、`level` 名字與數字、deadline 近的先與過期不跑（`DeadlineMissed`）、濫用先信任、每等 10 次升一級。
- **token 用量**（[rewrite-order 第 3 題](2026-10-19-rewrite-order.md)）：使用者 10-24「都按建議做」＝照推薦**開通道**——kernel 跑信時給環境變數 `AOS_KERNEL_REPORT` 指向那封信小格裡的一個檔，腦願意就把 `usage` 寫進去，額度同時認次數與 token 兩個上限。見下「token 回報與額度」。
- **`_metainfo` 接進 kernel**（使用者 10-24「讓kernel實際去用用看」，照 [metainfo 紀錄 § 5](2026-10-24-metainfo/02-誰讀與kernel接法.md#5-給-llm-kernel-實作者的接法)）：見結論 8、15。

## 結論：照推薦定、可翻案（使用者 10-24「都按建議做」）

1. **兩支 C++，放 impls**：`aos-gate`（寄信、等回信）、`aos-kernel-llm`（跑一次）。信箱與信的格式放在 aos-kernel-llm 的公開標頭 `aos/kernel_llm.hpp`，閘門連它。不做 Python 版（10-23 使用者「都用C++」）。
2. **命令列**：`aos-gate [旗標] 單子.json`、`aos-kernel-llm [旗標] kernel.json`，都是唯一位置參數、可寫 `檔#/指標`、目前沒有旗標。
3. **信箱位置**：閘門讀環境變數 `AOS_KERNEL`（kernel 的慣例、不是 aos 的六個變數，像 `AOS_BRAIN_*`，呼叫方綁，P-39）；kernel 讀 kernel.json 的 `mailbox`（相對的從 `$AOS_STACK` 算，N-14；沒寫＝`mailbox`），兩邊要同一個就寫 `{"$env": "AOS_KERNEL"}`。`AOS_KERNEL` 沒設或不是資料夾＝閘門馬上 `MailboxMissing`；資料夾在、kernel 不在＝信堆著一直等。
4. **信箱長相**：`tmp/`、`new/`、`cur/`、`done/` 四格，一封信一個資料夾；認領、撤信都靠改名（N-14 原子性三招）；`.lock` 用 flock 擋第二個 kernel（`LockFailed`）。信號＝`<UTC 奈秒>.<閘門 pid>.<started_at_ticks>`：字典序＝寄的先後（pid、ticks 只讓名字不撞）。**寄的人還在不在＝信裡 `sender.lock` 有沒有人鎖**（頂層代定、可翻案，依據使用者 10-24「能不能用kernel...那就是看他能不能存取檔案啊……像這種存取控制，我們就是純靠linux」，[sandbox S15](2026-10-24-sandbox.md)）：閘門在 `tmp/.<信號>/` 建信、先 flock（`LOCK_EX`）住 `sender.lock`、拿到行程結束，寫好才改名進 `new/`；kernel 試拿共享鎖（不等），拿得到、檔不在、開不了＝不在。flock 跟著檔走、跨 namespace 有效，沙箱裡的閘門也認得。
5. **信的內容**：`{"inst": 單子, "env": 閘門這一刻的整份環境, "priority": 原樣}`。閘門在自己的環境把單子的指示詞全解掉（先把 `AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置，同 aos-exec 跑 `檔#/指標`），`cwd` 轉絕對（沒寫＝單子檔的資料夾）。kernel 跑時環境**整份換成信裡的**——閘門要透明（C-20），`brain.py` 要的 `AOS_STACK`、`AOS_WS` 都得在。
6. **單子沒寫的串流**：`stdout`／`stderr` 寫進信裡的 `stdout.txt`／`stderr.txt`，閘門原樣吐出；`stdin` 沒寫＝`/dev/null`（閘門不轉自己的 stdin，免得卡在讀不完的管子上）。
7. **一次怎麼跑**：照 § ⑤「一拍一次」——收拾、排隊、取前 `slots` 封、每封 fork 一個子行程交給 aos-exec 的 `run_inst`、**全部跑完才結束**（一次裡不補位）、寫回信。kernel 跟 fsm 一樣是被拍的單子，暫停、收工交給 loop／daemon。
8. **排隊**：級數（level＋等了幾次÷10，不封頂）→ deadline 近的先（有寫的在前）→ `_metainfo.time_ms` 短的先（有寫的在前）→ 等得久的先 → 先寄的先。「等了幾次」記在 kernel 自己的 `$AOS_STACK/queue.json`。
9. **紀錄**：`$AOS_STACK/served.jsonl` 每封一行（`served_at`、`level`、`counter_waited_runs`、`code`／`signal` 或 `error`、`elapsed_ms`、宣告的 `time_ms`、`metainfo_bad`、`counter_tokens`、`report_bad`），行數就是次數。宣告與實際差很多只記錄不處罰（M8），誰要統計自己從 `served.jsonl` 算。
10. **收拾**：寄信的閘門不在了（`sender.lock` 沒人鎖，見 4）——`new/` 的不跑、丟掉；`tmp/`、`done/` 的刪掉；`tmp/` 裡 `.` 開頭的（閘門正在寫）已有 `letter.json` 而沒人鎖才刪、還沒有的不碰。閘門收到訊號撤信：還在 `new/` 就抽回來；已經在跑就讓它跑完，回信留給 kernel 下一次清。
11. **kernel 死掉後重起**：`cur/` 裡有回信就照它交；跑信的子行程（`runner.json`）還活著就讓它跑完、那格這次不給別人；都不是＝回 `RunFailed`、不重跑（10-15 六題 6）。
12. **錯誤代號**（C-54）：閘門 `MailboxMissing`、`PriorityBad`、`LetterMissing`、`ReplyBad`；kernel `LockFailed`、`QueueBad`；回信 `LetterBad`、`DeadlineMissed`（10-15 定的名字，照原名）、`RunFailed`，單子跑不起來照 aos-exec 的 `EntryBad`／`DirectiveBad`／`LaunchFailed`。回信是錯時閘門印成自己的一行 `aos-gate: 代號 原因`、退 1；有碼就以那個碼退。
13. **agent 範本不改**：agent-dan 仍直接問腦；走 kernel 的版本只在 demo（`demo/kernel-llm/agent-ivy`：think 格的 `exec` 是 `aos-gate`，腦那張單子放 `brains/*.json`，哪張由環境變數 `BRAIN` 選）。
14. **demo**：`demo/kernel-llm/`——一個 daemon 管 kernel（`slots` 1、`interval_ms` 300）＋三隻 agent（假腦睡 1 秒；a 普通、b 普通但宣告 `time_ms` 800、c high），三題同時丟；接進 `demo/run.sh`。
15. **`_metainfo` 讀法**（照 metainfo 紀錄 § 5 第一步）：只讀信裡單子的 `_metainfo` 的 `time_ms`、`llm_tokens`（數字或 `{"val", "max"}` 取 `val`）；形狀不對＝那個 key 當沒寫、記進 `metainfo_bad`，照樣跑。`llm_tokens` 只讀不用。全部從 `priority_of` 一個函式讀。

## 邊緣狀況（挖出來的；多數已照上面處理，剩的寫在 [aos-kernel-llm README 已知限制](../impls/aos-llm-kernel/README.md#已知限制)）

- **slots 大於 1 時一次裡不補位**：一封 1 秒、一封 10 秒，那格空等 9 秒；新來的 high 也等這一次結束。
- **kernel 整群被 SIGKILL**：跑信的子行程跟著死，但單子自成行程群組、可能還在跑；下一次回 `RunFailed`，單子實際做了一半沒人收（brain.py 可能已認領題目、寫了一半 history）。只殺 kernel 本體時，子行程跑完照常交回。
- **閘門被 SIGKILL**：來不及撤信，鎖跟著行程放掉，kernel 下一次看寄信的人不在了就丟掉、不跑；已經在跑的跑完回信沒人拿，下一次清掉。
- **包閘門那格逾時**：閘門被 SIGTERM、撤信；那格的碼是 143，agent 照 P-20 停住。kernel 那邊已經在跑的不會停（10-15「已在跑的讓它跑完」），腦的錢照花。
- **信裡帶整份環境**（含 `AOS_BRAIN_KEY` 這種）寫在信箱裡：信箱放自己的 stack，別放共用的地方。
- **`AOS_KERNEL` 寫錯但剛好是個資料夾**：閘門寄進去一直等，直到那格逾時。
- **兩個 kernel 指同一個信箱**：第二個 `LockFailed` 退 1，它那個 loop 就停了（不是排隊等）。
- **單子裡相對的 `stdout` 路徑**：閘門把 `cwd` 轉絕對、串流照 cwd 算，所以結果寫在原地，不會寫到 kernel 那邊。
- **deadline 沒寫時區**：當壞（`PriorityBad`／`LetterBad`），不猜本地時間。
- **宣告了 kernel 沒有的資源、`_metainfo` 裡的 `$ref` 指不到**：前者不看、照跑；後者閘門解指示詞時就 `DirectiveBad`、寄不出去（N-45 真的解不開＝錯）。

## 接點

- **`_metainfo` 再往下**：讀法集中在 `aos/kernel_llm.hpp` 的 `priority_of`；要加 `llm_tokens` 預估額度、閘門多帶 `from`（單子在哪）做按函數統計，都改這裡與 served 那行（metainfo 紀錄 § 5 第二步）。
- **從 agent-dan 抄的 agent**（agent-eve〔含 `tools/pyfix/agent`〕、fay、meg、pip、kai、liv、hal、`talk/member`、`self-improve/improver`）都有 `AOS_KERNEL_REPORT` 那五行（[tool-lib 遷移完成第 10 項](2026-10-24-tool-lib.md#遷移完成10-24-下午照推薦做可翻案)），但直接問腦、不走 kernel；真的走 kernel 的只有 demo/kernel-llm 的 agent-ivy。agent-gus 的 `shared.py`、agent-hal 的 `compact/ask.py` 問腦寫法不同、也沒走 kernel，不動（使用者 10-25「可以直接派人做的就去做」時盤點）；哪隻要改走 kernel，包進 aos-gate、照 agent-dan 的 `brain.py` 抄那五行。

<a id="token-回報與額度10-24-下午"></a>
## token 回報與額度（10-24 下午）

使用者原文：同上「我現在沒空管這些小事，都按建議做」——上面「決定」的 token 那條（[rewrite-order 第 3 題](2026-10-19-rewrite-order.md)推薦：開 `AOS_KERNEL_REPORT`、額度同時認次數與 token）照做。程式：[aos-kernel-llm § token 回報與額度](../impls/aos-llm-kernel/README.md)。

### 結論：照推薦定、可翻案（使用者 10-24「都按建議做」）

1. **回報檔**：kernel 跑每封信時在信帶來的環境上加 `AOS_KERNEL_REPORT`＝`cur/<信號>/report.json`（信裡原本有同名的也蓋掉）。內容＝API 回覆的 `usage` 物件**原樣**，腦先寫 `.report.json` 再改名（N-05）。一封信問好幾次腦＝腦自己加總後寫。
2. **怎麼讀**：`total_tokens`（非負整數）；沒有就 `prompt_tokens`＋`completion_tokens`。檔不在＝沒回報（`counter_tokens` null）；讀不懂、形狀不對＝`report_bad: true`。兩種都**只算次數、照樣交回信**（回報是腦自願的，跟 `_metainfo` 寫壞一樣不擋，M8 的精神）。
3. **什麼算一次**：子行程起來過（`runner.json` 在）的信。`LetterBad`、`DeadlineMissed`、`BudgetMissing` 不算；kernel 死掉後回 `RunFailed` 的那封算（腦可能已經花了錢）。
4. **紀錄**：`served.jsonl` 每行有 `counter_tokens`、`report_bad`；帳本 `$AOS_STACK/used.json`＝`{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}`，每封寫完 served 那行就記（不併進 `queue.json`：那份一次結束才寫，帳要每封記）。讀不懂＝`UsedBad`。
5. **額度設定**：kernel.json 的 `budget`：`max_calls`、`max_tokens`＝每窗上限（沒寫＝那種不限）；`window`＝`hour`／`day`／`all`，沒寫＝`day`（10-15 照建議定的「一天一期歸零」）；窗的起點用 kernel 的本地時間（整點／午夜；台北就是台北的午夜）。`budget` 沒寫也照記帳。
6. **到頂怎麼辦**：`spent` 沒寫＝`refuse`——排著的信不跑、回 `BudgetMissing`（閘門照印、退 1，agent 照 P-20 停）；`spent: "wait"`＝留在 `new/` 等下一窗（排隊時間算在包閘門那格的 `timeout_ms` 裡）。
7. **錯誤代號** `BudgetMissing`（C-54 R10「沒有了」＝`…Missing`）。
8. **到頂的判法**：開下一封之前看——`counter_calls` 已用＋這次已開的＋上一次留下還在跑的 ≥ `max_calls`，或 `counter_tokens` 已用 ≥ `max_tokens`。次數是準的；token 跑完才知道，所以最多超過一次的量。`refuse` 時到頂後這次排著的全回錯（不只 `slots` 那幾封）。
9. **`_metainfo.llm_tokens` 不預先擋**（宣告只記錄不處罰，M8）。未決：要擋的話拿 `val` 還是 `max` 去擋。
10. **「快見底只給 high 過」不做**：那句列在 [NORMS 待定](../docs/NORMS/08-待定.md)，等使用者。
11. **範本**：agent-dan 的 `brain.py` 有 `AOS_KERNEL_REPORT` 就寫 usage（五行，P-23 加註）；demo 的 agent-ivy 也寫，假腦編一份（題目與答案的字數當 token 數），demo 才看得到數字。閘門不改。

### 邊緣狀況（挖出來的）

- **回報是自願、不驗的**：腦少報、不報，token 額度就管不到它；單子裡的子行程也看得到 `AOS_KERNEL_REPORT`，誰最後寫算誰的。
- **時區**：kernel 的 `TZ` 換了、或日光節約，`since` 會變＝當成換窗、歸零一次。
- **`wait` 配 `window: "all"`**：到頂後永遠等，直到有人改 kernel.json 或刪 `used.json`；閘門那邊由那格 `timeout_ms` 收掉。
- **跨窗才跑完的信**：算在跑完那一刻的窗。
- **`used.json` 被刪**：從 0 算（總數也歸零）；`served.jsonl` 還在，要對帳從那裡加。
