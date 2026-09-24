← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜上一輪 [one-boot](../2026-09-24-one-boot/README.md)（「下一輪」一節）

# 格與格之間的等待（2026-09-24，P2 隊）

**一句話**：agent 一輪「問模型 → 跑工具」以前九成時間在等排程。先量了每一跳，再改四條便宜的：
kernel 叫醒後同一格就派、agent 做完事退 103「馬上再來」、cpu 等子行程改用 pidfd、kernel 派完工按 cpu 的門鈴。
單 agent 用 add 工具算一題（`say --wait`）從約 11.8 秒降到約 2.1 秒。反覆工作被判 bad 時，`ls` 第一行不再印 ok；登記時也可以寫「壞了寄信給誰」。

**收線狀態（使用者要關機，提早收）**：程式、規範、測試都做完了，全套測試綠。
**沒做**：astra 審查（**沒審**）、團隊例子 1 改後的真跑、kill -9 真跑、故意連錯 10 次的通知信真跑、教程 01／02。下一輪從〈下一輪從哪接〉那節接。

## 1. 每一跳花多少（本輪最重要的表）

**怎麼量**：新增 `lib/aos_hops.py`。環境變數 `AOS_HOPS` 設成一個檔，`aos up` 開的 daemon 會把它傳給 kernel tick、cpu 和工作。
各程式在關鍵點追加一行時間戳：daemon 開格、kernel 讀單／放工作／收回音／放回音、cpu 撿到／做完、agent 一格起訖與送單、aos-llm 的 HTTP 起訖、投輸入的 wake。
沒設這個變數就什麼都不做。
`python3 lib/aos_hops.py report 檔 [--agent 名字]` 把一個 agent 從頭到尾的時間切成一段一段，各段加起來剛好等於總時間。
兩段同時在跑時，照「等模型 > 跑工具 > agent 一格」的順序歸給其中一項。
沒人說話、閒著的時間另列，不算進去。

**場景**：LiteLLM `localhost:4000` 的 deepseek-chat，default 3 顆 cpu、llm 2 顆，`tick_ms`＝`interval_ms`＝1000。
單 agent＝bob 有一支 add 工具，`say --wait "請用 add 工具算 A 加 B"` 三次。每次會問兩次模型：第一次叫工具、第二次回答。
改前＝main `d6603b9`＋量測（行為不變）。改後＝這個分支。表裡是 `base-solo-1` 和改後一次的數字，其他次差不多。

| 這一跳 | 改前合計（毫秒，3 次 say） | 改前每次約 | 改後合計 | 哪條改的 |
|---|---:|---:|---:|---|
| ⑱ agent 做完事退 0，kernel 要等 `interval_ms` 才再派；kernel 每 1 秒才開一格，所以常常等到 2 秒 | 19,146 | 1.0～2.0 秒 | 129（退 103 馬上再派） | ② 103 |
| ⑮ 回音出貨時才叫醒 agent，要等下一格 kernel 才派 | 5,997 | 1.0 秒 | 3 | ① 提交點 D |
| ⑩ 等模型（HTTP） | 4,606 | — | 4,181 | （模型本身） |
| ① 派 agent 之後，cpu 要等輪詢（`poll_ms` 200）才撿到 | 3,066 | 133 | 4 | ④ 門鈴 |
| ⑯ agent 已經退出，cpu 要等下一次看子行程才發現 | 2,688 | 168 | 126 | ③ pidfd |
| ⑦ 放了工作，cpu 要等輪詢才撿到 | 873 | 97 | 2 | ④ 門鈴 |
| ⑫ 模型那支行程已經結束，cpu 要等下一次看才發現 | 594 | 119 | 47 | ③ pidfd |
| ② cpu 撿到 agent → 起 Python（fork＋import） | 730 | 29 | 708 | 沒改 |
| ⑤⑬⑰ 放了單或回音 → daemon 察覺、開 kernel tick 的 Python | 約 1,400 | 38～45 | 約 1,300 | 沒改 |
| ⑥⑭ kernel 一格本身（讀帳本、判、派、存） | 約 220 | 11 | 約 200 | 沒改 |
| ④ agent 一格本身 | 182 | 5 | 171 | 沒改 |
| **總時間（不含閒著）** | **42.9 秒** | | **7.2 秒** | |

**大白話**：真正卡住的是兩個「等 1 秒」，佔了 25 秒：agent 做完事還要白等 `interval_ms`，叫醒後又要等 kernel 下一格。
其次是 cpu 每 200 毫秒才看一次，撿工作、發現工作做完，每跳平均各多 0.1～0.17 秒。
起 Python、kernel 一格本身都只有幾十毫秒，這輪不動。

### 每改一條重量一次（單 agent，各跑一次，三次 say 的秒數）

改動是一條一條疊上去的：v1＝改前＋①，v2＝v1＋②，依此類推。

| 版本 | 三次 say --wait | 總時間（不含閒著） |
|---|---|---:|
| 改前 | 11.8、12.0、11.6（另兩輪：10.8～12.6） | 42.9 秒 |
| v1：＋① 叫醒後同一格派（提交點 D） | 8.1、10.4、9.2 | 33.4 秒 |
| v2：＋② 退 103 馬上再排；跑時被叫醒過也馬上再排；送完單停車 | 4.3、4.5、4.9 | 15.4 秒 |
| v3：＋③ cpu 等子行程用 pidfd | 3.1、3.3、3.9 | 10.9 秒 |
| v4：＋④ kernel 派完按 cpu 門鈴（＝這個分支） | 1.9、2.1、2.3 | 9.5 秒（另一次 7.2） |

### 團隊例子 1（導入，四人名冊，派給 importer-1）

只量了改前 3 次，**改後沒量到**（使用者要關機）。

| 次 | 總秒數 | 其他（排隊與郵差，`aos-team score`） | 等模型 | 等收件 | 等驗收 |
|---|---:|---:|---:|---:|---:|
| 改前 1 | 51.0 | 27.0 | 6.6 | 6.0 | 10.0 |
| 改前 2 | 57.0 | 29.8 | 7.6 | 7.0 | 10.0 |
| 改前 3 | 63.1 | 35.4 | 7.8 | 5.0 | 11.0 |

改前 importer-1 的每一跳（第 1 次）：⑱ 15.4 秒、⑮ 5.6 秒、⑱「退 102 但跑時已被叫醒、照 101 等」3.0 秒、①⑦ 4.5 秒、⑯⑫ 2.8 秒。
這幾跳合計約 31 秒，本輪都改了，所以改後的「其他」預期會降到個位數，但**還沒實測**。
T5 的三人版（改派 worker-1、10 次模型）改前也量了 3 次：84～117 秒，「其他」51～75 秒，其中 ⑱＋⑮ 就佔了 45 秒。

## 2. 閒著 60 秒的 CPU 秒（跟 one-boot 報告同設定：default 2、llm 1、1 個停車中的 agent）

| 版本 | 三次 | 說明 |
|---|---|---|
| 改前 | 3.16、3.08、3.05 | one-boot 報告是 2.31～2.44，量法不同：這次把 cpu 收過屍的孩子也算進去 |
| 改後（門鈴＋pidfd，`poll_ms` 仍是 200） | 2.84、3.00、2.94 | 沒變多 |
| 改後＋`poll_ms` 改 20 | 3.51、3.58、3.79 | 多 0.6～0.8 秒／分鐘（約 +25%） |
| 沒門鈴、只把 `poll_ms` 改 20 | 3.34 | 一次 |

**結論：`poll_ms` 不改，維持 200。** 門鈴已經讓撿工作的等待從約 0.1 秒降到 0.2 毫秒，閒著不多花；改成 20 閒著多花約 25%，換來的只有幾毫秒。

## 3. 改了什麼

| # | 改動 | 程式 | 規範 |
|---|---|---|---|
| ① | **提交點 D**：C 出貨時帶 `wake` 的回音把停著的行程推進 `ready`，同一格再跑一次派工。存帳本之後才放單，而且只放這一輪新派的 | `aos_kernel_engine.dispatch_woken`、`aos_kernel_ledger.readied` | [kernel tick §3 第 10 步](../../spec/kernel/tick.md)、[ledger](../../spec/kernel/ledger.md) |
| ② | **退 103＝馬上再排**。退 0／101／102 時，如果這格跑著時被叫醒過（`woken`），也馬上再排；以前 102 會當成 101 等 `interval_ms`。失敗的情況照舊等。帳本 `features` 加 `again`，`aos-agent start` 會檢查 | `aos_kernel_info.classify` | [echo](../../spec/kernel/echo.md)、[syscall](../../spec/kernel/syscall.md)、[ledger-keys](../../spec/kernel/ledger-keys.md) |
| ② | **agent 退出碼**：結清成功、收完輸入、act 沒 tool_calls、整批都在本地結束 → 103；剛送出一批 → 102 停車；收到一部分、其餘還在途 → 102；問模型失敗、崩潰恢復時重送 → 照舊 0 | `aos_agent.py`、`aos_agent_batch.py`、`aos_agent_inputs.py` | [aos-agent tick §12](../../spec/aos-agent/tick.md)、send／collect／settle／idle／register |
| ③ | **cpu 等子行程用 pidfd**：子行程一結束就醒；拿不到 pidfd 的系統照舊睡 | `aos_exec_run._wait_full` | [cpu lifecycle](../../spec/cpu/lifecycle.md) |
| ④ | **門鈴**：cpu 家多一個具名管道 `wake`。cpu 閒著時「睡 `poll_ms`，或門鈴響、控制 pipe 有字就醒」。kernel 放完派工單就按一下；按不到當沒事 | `aos_home.Doorbell`／`ring`、`aos_exec_cpu._loop` | [cpu §6.5](../../spec/cpu/notify.md)、[layout](../../spec/cpu/layout.md) |
| C① | **有反覆工作 bad，`ls` 第一行就不印 ok**：印 `反覆工作 N 個 bad：…`，code `bad`。`aos up` 最後一行也看得到，但不因此退 1。`aos-agent status` 把它當 ok（壞的是別人） | `aos_kernel_health`、`aos_agent_status` | [health](../../spec/kernel/health.md) |
| C② | **`add` 的 `on_bad`**：判 bad 那格往指定資料夾放一封信，可以順便叫醒收件的 agent。信內容裡的 `{id}{proc}{fails}{at}{look}` 會換成當下的值。寄不出去只記 log，不讓 kernel 那格失敗。命令列 `--on-bad DIR [--on-bad-wake NAME]` | `aos_kernel_ledger`（`letters` 出貨箱）、`aos_kernel_engine`、`aos_kernel_cli` | [syscall](../../spec/kernel/syscall.md) 最後一節 |
| C② | **郵差、心跳預設寄給人**：`aos-team start` 登記時帶 `on_bad`，信直接放進人的收件匣 `team/human/`，不經郵差（壞的可能就是郵差） | `aos_team_post.bad_notice`／`register`：**只動登記那幾行**（加 `bad_notice()`、params 多一鍵） | —（spec/team 是別隊的領地，沒寫） |
| 量測 | `AOS_HOPS` 時間戳 | `aos_hops.py`，各處一兩行 `mark` | 本報告 §1 |

**保住的**：K2 的停車喚醒（102）、T2 的 routine 申請（沒碰）、`ls --json` 第 3 版（沒改欄位）、one-boot 的 sqlite 帳本與鎖、崩潰測試（全綠）。
`ls --json` 第 3 版不用升版：`health.code` 多一個值 `bad`，帳本多一個 meta 鍵 `letters`，都沒改到既有欄位。

## 4. 測試

- 全套：rebase 到 main `162cc59`（90 檔 2520 條）之後 **92 檔 2555 條全綠**（rebase 前在 `d6603b9` 上是 88 檔 2407 條）。
- 新增 `test_hops.py` 6 條、`test_tick_gap.py` 29 條。後者涵蓋：103 與 woken 的判定表、提交點 D（同一格派出去、不重放第一輪的單、崩在 D 之後下一格補放）、派工按門鈴、門鈴本身（沒有 cpu 時按了沒事、響了就醒、讀乾淨、普通檔和 symlink 不寫）、pidfd（子行程一結束就醒、沒 pidfd 照舊、逾時照殺）、真的 cpu 在 30 秒輪詢時被門鈴叫醒、`on_bad` 寄信（換值、叫醒、寄不出去不擋、崩潰後只寄一次、形狀不對退件）、health 的 `bad`、團隊登記帶 `on_bad`。
- 11 個舊測試檔改了退出碼的期望值（子 agent 做的）。改法是把 0 換成新語意的 102／103，沒刪測試、沒放寬斷言。C7 那條反而改得更嚴。
- 時序類斷言都用「遠小於輪詢間隔」：輪詢設 30 秒，斷言 10 秒內完成，機器忙也不會誤判。

## 5. 我代裁的（附預設，都已照做）

1. **新退出碼 103，不讓 agent 一格多做幾步**：一格多做幾步是下一輪的大改。103 只是讓 kernel 別白等。舊 kernel 不認得 103，所以 `start` 要求帳本 `features` 有 `again`，跟 102 的 `park` 同一招。
2. **跑時被叫醒過（woken）就馬上再排，退 0、101、102 都一樣**：叫醒的意思就是「有東西到了」。失敗的情況不看 woken，避免連環重試。
3. **送完單就停車（102）**：每件單都帶 wake，回音到了會被叫醒。回音比 agent 退出還早到時，kernel 已經記了 woken，也會馬上再排。只有崩潰恢復（重送上一格送過的）照舊退 0：它的叫醒可能早就用掉了。
4. **門鈴用具名管道，不用訊號也不用 inotify**：訊號要讀 pid，pid 可能被別的行程重用；inotify 只有 Linux。門鈴不帶內容，單還是只能放進 `requests/`。規範 §6.5 有寫。
5. **`poll_ms` 維持 200**（§2 的表）。
6. **`on_bad` 的信內容由登記的人給**：kernel 不認得團隊信的格式，只替換 `{id}{proc}{fails}{at}{look}` 五個值，而且只換字串或物件第一層。沒給內容就用一句白話，agent 的 `input/` 也收得下。
7. **寄給人的信不經郵差**：壞的可能就是郵差。所以這封信不會出現在 `aos-team mail`，因為 mail 看的是郵差的投遞紀錄。人要看收件匣 `team/human/`，或看 `aos-kernel ls`、`aos-team ls` 的第一行。
8. **郵差、心跳一律寄給 human，不能改**：要讓名冊能改收件人得改 spec/team（別隊的領地），這輪沒做。

## 6. 要你拍的

沒有新題。代裁 7（信不出現在 `aos-team mail`）如果你想讓它出現，要動 `aos_team_mail`，是別隊的領地。

## 7. 下一輪從哪接

1. **團隊例子 1 改後的真跑**：`~/tmp/wf-try-p2/`，腳本在 scratchpad `p2/team4.sh`，量 2～3 次，填 §1 那張表的改後欄。
2. **kill -9 daemon／tick 各一次**：確認提交點 D、門鈴沒讓崩潰恢復退步。測試已經有崩在 D 之後的情況，真跑還沒做。
3. **通知信真跑**：登記一個一定失敗的反覆工作，帶 `--on-bad`，看第 10 次後信有沒有到、`ls` 第一行有沒有變。
4. **astra 唯讀審**：這輪沒審。核心改動是 `aos_kernel_engine.dispatch_woken`、`aos_kernel_info.classify`、`aos_agent_batch.send`／`collect`／`settle` 的退出碼、`aos_home.Doorbell`／`ring`、`aos_exec_run._wait_full`、`aos_kernel_ledger` 的 `letters`。
5. 教程 01／02 補一句 103 與 `--on-bad`（02 的退出碼那段）。
6. 還剩下的跳：daemon 察覺新檔＋起 kernel tick 的 Python（每次約 40 毫秒，每輪 3～4 次），以及 agent 一格起 Python（約 30 毫秒）。再往下就是「agent 一格多做幾步」那種大改。
