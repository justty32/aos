# 閒置停車＋喚醒：實作（2026-09-24）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜提案：[proto5-2 idle-wait](../../../proto5-2/notes/2026-09-24-idle-wait/README.md)、[plan-b.md](../../../proto5-2/notes/2026-09-24-idle-wait/plan-b.md)｜[astra 任務書](review-task.md)｜[astra 回報](review-astra.md)

**一句話**：agent 沒事可做時（在等模型／工具回來、或閒著沒人說話）不再每秒被 kernel 叫起來看一眼，而是**退 102＝停車**；
它等的東西到了，kernel 自己把它叫醒；有人 `say` 了，`say` 順手投一張 `wake` 單叫醒它。都沒人叫，最晚 `park_ms`（預設 5 分鐘）也會自己醒一次。

## 1. 真跑數字（LiteLLM `localhost:4000` 的 deepseek-chat，1 個 agent，default 2 顆、llm 1 顆，`tick_ms`＝`interval_ms`＝1000）

改前＝main `1122f8d` 的程式，改後＝這個分支（修完 astra 之後的最後版本）；同一支腳本、同一台機器。改後跑了三次，數字列最後一次，會晃的另註。

| 量什麼 | 改前 | 改後 |
|---|---:|---:|
| **閒著沒輸入 60 秒內，kernel 派 agent 跑了幾格** | **28** | **0**（停著） |
| 同 60 秒 kernel 自己走了幾格 | 57 | 57（kernel 的鏈照走，跟 agent 無關） |
| 同 60 秒整套用掉的 CPU 秒（daemon、kernel、cpu、tick 全算） | 5.35 | 3.65（三次 3.52～3.65） |
| 等模型寫一篇短文（say 到拿到回話 12～14 秒），這段 agent 被派了幾格 | 6 | 4（三次都是 4） |
| agent 停著（改前是閒著輪詢）時 `say`，到 input 被收走 | 1.23 秒 | 0.23～1.28 秒（三次：1.28、0.23、1.23） |
| 同上，到拿到回話 | 7.6 秒 | 4.4～5.5 秒 |

- 閒著 60 秒從 28 格變 0 格：上千個閒著的 agent 就是每秒少上千次起 Python。
- 等模型那段 6→4：模型只花 12 秒時差不多（送單、醒來收、結清本來就要幾格）；模型越慢差越多——改前每 2 秒一格空轉，改後不管等多久都是「送出、停、被叫醒、收」。
- `say` 之後醒得**不比以前慢**：改後 `wake` 單在下一格第 5 步就把它排上、同一格第 8 步派出去，所以看 `say` 落在一格的哪裡，0.2～1.3 秒；改前是等下一個 `interval_ms`（也是 1 秒上下）。停著不會讓回話變慢。
- 回話時間含模型本身，前後差主要是模型快慢，別太當真。

**kill -9 驗證**（最後一次真跑）：用包一層的 tick（產品程式不變，只把 `KernelLedger.wake` 包起來、而且只在出貨時才停）讓 kernel 在「放好 agent 那張 think 的回音檔、叫醒已改了記憶體、還沒存帳本」時睡著，再 `kill -9` 那格：

| 看到的 | 結果 |
|---|---|
| 被砍那格（seq 93）當下 | 帳本 `replies` 還有那則（帶 `wake: agent-bob`）、回音檔已在、agent 在帳本裡仍是 `queued`＋`parked` |
| 下一格（seq 94） | 第 4 步重放回音（EEXIST 當已放）、重做叫醒，`kernel.log` 有 `wake … how: ready`；被砍那格記成 `tick_error` |
| agent | 醒來收了回話，`say --wait` 退 0、印出整篇（最後一行「收到」），記憶只多兩則（user＋assistant），帳本 `replies` 清空 |

腳本在 scratchpad 跑，沒收進 repo（跟 fold-in 報告同做法）；清場後沒有留下行程。

## 2. 做了什麼

**kernel**
- `add` 多兩個可省的參數：`wake`（要叫醒的反覆行程名）、`park_ms`（這個行程停車最久多久）。
- 這張 add 的最後一則回音，不管是跑完、失敗、被 `rm`（`Removed`）、停機取消（`Stopping`）、還是收單就退件，都帶著 `wake`。**回音檔放好之後**才叫醒，叫醒的結果跟「把這則從出貨箱拿掉」同一次存帳本。
- 回音判定多一列：退 **102** → `runs+1`、`fails` 歸 0、`not_before = 現在 + park_ms`、記 `parked`；但這格跑的時候已經被叫醒過（`woken`）就當成 101（照普通間隔）。判完 `woken` 一律清掉。`done_exit` 先比，設成 102 的 kernel 會把 102 當完成。
- **叫醒一個行程**：不在、`once`、`bad`／`done`、正跑的那格已被 `rm` 標 `discard` → 不做。**不比代數**（見 §5 第 2 條）。
  正在跑 → 記 `woken`；排著而還沒到時間（停著）→ 時間改成現在、推一格進它池的 `ready`（`delayed` 裡那格變舊格，照原本的舊格規則丟）；排著而時間已到 → 不做（免得 `ready` 疊兩格）。
- 新 syscall **`wake`**（`params.name`）：給「投了輸入的人」用。多半當 notification 放（不回音）；帶 id 就回 `{"name"}` 或 `NotFound`。命令列 `aos-kernel wake NAME`。
- `info.park_ms`（預設 300000，`init` 不寫進 info）、`aos-kernel add --park-ms N`。
- 帳本多 `features: ["park"]`（每格讀帳本時補上），給 `aos-agent start` 認。
- `aos-kernel ls`：`proc` 標題多 `；停車 N`；`--json` 的 `procs[]` 多 `parked`、`counts.procs` 多 `parked`（第 2 版內「只加鍵」）。

**agent**
- `tick`：批在途、這格什麼都沒到 → 102；idle 沒輸入（沒有 `intake`、列不到輸入檔、自動壓縮也沒做事）→ 102。門關著、tick 鎖被佔照舊 101（門是外人開的，kernel 叫不到）。
  恢復一個「檔都不在」的舊 `intake`（清掉它）改退 **0**（以前 101）：寫了東西，下一格重看輸入，免得把剛投的輸入的叫醒吃掉（astra 必修 2）。
- 送 think／act 單都帶 `wake: agent-<資料夾名>`。
- `start`：`done_exit` 是 102 也擋；K 的帳本讀得到、有 `chain`（真的 boot 過）而 `features` 沒有 `park` → `KernelIncompatible`（舊 kernel 會把 102 當失敗，十次就 bad）。帳本不在（還沒 boot）或讀不懂不擋。
- `say`／`talk`（同一個 `deliver`）投完話投 `wake`；`drop_new`（T2 的郵差投信、T4 的 compact 申請都用它）投進**有 `tick.json` 的 agent 家**也投 `wake`——同名已在（前一次可能崩在投好、叫之前）也照叫。找 K：先看 `tick.json` 記的，沒有再看 `AOS_KERNEL_HOME`。找不到、放不進去都不算錯。新檔 `aos_agent_wake.py`。

## 3. 改了哪些檔、哪幾行（行號是 rebase 到 main `4c42288` 之後的）

**共用檔（別隊也在動，合併時注意）**

| 檔 | 碰到哪 |
|---|---|
| `lib/aos_agent.py` | 第 16 行加 `PARK_EXIT`；`tick()` 裡 `return collect(run)`、`return intake(run)` 兩行各包一層 `_park(...)`（第 74、81 行，T4 的自動壓縮四行原樣保留、`_park` 包在它後面）；新函式 `_park`（`_compatible` 前 5 行）；`_compatible` 的 `done_exit` 那行多 102、後面加 9 行查帳本 `features` |
| `lib/aos_agent_batch.py` | `send()` 送單那個 `submit` 的 params 多 `wake`（第 251～252 行） |
| `lib/aos_agent_say.py` | 多一行 import；`deliver()` 最後一行前加 `wake(base)`；`drop_new()` 的 link 那段改成記 `made`、之後叫醒（約 6 行）。T2 的 `aos_team_post.py` 呼叫它，介面沒變 |
| `lib/aos_agent_inputs.py` | `intake()` 清空 intake 那個出口 `return 101` → `return 0`，第 62 行（T4 也動過這檔，rebase 沒衝突） |
| `lib/aos_kernel_engine.py` | `dispatch()` 派出去時清 `parked`，一行 |
| `aos_agent_cli.py`、`aos_llm_call.py`、`aos_team_*.py` | **沒碰** |

**只有這隊動的**：`aos_kernel_info.py`（`PARK_MS`／`PARK_EXIT`／`FEATURES`、`park_ms` 讀驗、`new_state` 的 `features`、`classify` 的 102）、`aos_kernel_ledger.py`（`features`、`_reply` 帶 wake、`_wake_of`、`wake`、`_add` 收 `wake`／`park_ms`、`apply_syscall` 的 `wake`、`flush_outboxes` 放好回音後叫醒）、`aos_kernel_ls.py`、`aos_kernel_cli.py`、新檔 `aos_agent_wake.py`。

**測試**：新 `test/test_park_wake.py`（42 條）、`test/test_park_crash.py`（2 條真 SIGKILL）；舊測試裡「idle／批在途退 101」改成 102：`test_agent_tick.py`（9 處改 102、清空 intake 的 2 處改 0、think 單多 `wake`）、`test_agent_crash.py`（1）、`test_agent_integration.py`（2）、`test_agent_memory.py`（T4 的，9 處）、`test_advice_r1.py`（`ls --json` 多 `parked` 鍵）。

**規範（只改句子）**：kernel 的 `syscall.md`（add 兩個參數、`wake` method、叫醒規則兩段）、`echo.md`（102 那列、woken 清掉）、`tick.md`（第 4 步出貨後叫醒、第 5 步認 `wake`）、`ledger.md`（`park_ms`／`woken`／`parked`、`replies` 帶 wake、`features`）、`info.md`（`park_ms` 一列）、`cli.md`（`wake` 子命令、`--park-ms`）、`cli-ls.md`（停車）；
aos-agent 的 `tick.md`（退出碼表多 102）、`send.md`（帶 `wake`）、`register.md`（擋 102、看 `features`）、`collect.md`／`idle.md`／`gate.md`（在等＝102）、`cli-talk.md`（say 投 wake）。

## 4. 崩潰窗口（每個「崩在哪兩步之間」一條測試）

「Crash」＝行程內丟 BaseException（記憶體全丟、磁碟停在那一刻）；「SIGKILL」＝真 daemon＋真 tick、閘門停住後 `kill -9`（借 `test_kernel_crash` 的閘門）。

| 崩在哪兩步之間 | 下一格怎麼接 | 測試 |
|---|---|---|
| 放好回音檔 ↔ 叫醒（還沒呼叫） | 出貨箱還在：第 4 步重放（EEXIST）、叫醒 | `test_kill_after_reply_placed_before_ledger`（SIGKILL，閘門在放檔函式裡，所以切在叫醒之前） |
| 叫醒已改記憶體 ↔ 存帳本（agent 停著） | 同上，叫醒重做，同一格就派 | `test_crash_after_reply_placed_before_ledger`（Crash，切在叫醒之後）、真跑 §1（kill -9，同一個切點） |
| 同上，但 agent 正在跑（`woken` 沒存到） | 重做叫醒記上 `woken`，agent 的 102 當 101 | `test_crash_after_reply_placed_agent_running` |
| 回音待辦（帶 wake）已存 ↔ 放回音檔 | 第 4 步放檔、叫醒 | `test_crash_after_verdict_before_reply_placed`（Crash）、`test_kill_after_verdict_before_reply_placed`（SIGKILL） |
| 收到 agent 的 102、判完 ↔ 提交點 3 | 通知檔還在，重收同一則，只算一次、照樣停 | `test_crash_before_verdict_committed` |
| 第 4 步叫醒（running → `woken`）已存提交點 2 ↔ 提交點 3 | `woken` 留在帳本，重收的 102 仍當 101 | `test_crash_after_commit2_woken_before_commit3` |
| `wake` 單判到一半 ↔ 提交點 3 | 原單還在，重判 | `test_crash_in_wake_syscall_before_commit` |
| `wake` 單已記進 `deletes` ↔ 刪原單 | 只補刪、不重判，agent 不會排兩格 | `test_crash_after_wake_syscall_committed_before_delete` |
| `say` 放好輸入 ↔ 投 `wake`（plan-b §4 的正常窗口） | 輸入留著、沒有 wake 單；最晚 `park_ms` 被派時照收一次 | `test_say_crash_between_input_and_wake`（真的 say 崩）＋`test_park_ms_fallback`（kernel 那半：沒人叫也會到期） |

其他時序（同格收到 102 和它等的回音、act 批兩件分開回來、判定表每一列都清 `woken`、stop／start 的新一代接手舊批、`discard`、`Removed`／`Stopping`／退件也叫、`ready` 不疊兩格、清空 intake 不停車）各有一條，見 `test_park_wake.py`。

## 5. 跟 plan-b 不一樣的地方

1. **plan-b 是照舊 proto5 kernel（每則存一次帳本）寫的**；現在的 kernel 是池式、四個提交點。叫醒放在 `flush_outboxes` 裡「回音檔放好之後」，跟出貨項一起在提交點 2／4 存——plan-b 講的「同一次存」在池式下就是這樣。
2. **拿掉 `wake_gen`（不比代數）**：plan-b 要「同名重登記的新一代不被舊單叫醒」。astra 指出這會漏：`stop` 再 `start` 的新一代本來就**接手舊批**（aos-agent register.md），它看到舊批沒回來就停車，舊批回來卻因為代數不同不叫它，要等 5 分鐘。多叫一格無害，所以改成只看名字。`wake` 記在 once 的 `pending` 裡（`pending` 本來就是「這張 add 還沒回的那則」），`Removed`／`Stopping`／跑完都從 `pending` 帶出來；收單當場就回的直接帶。
3. **多了 `parked` 旗標**（plan-b 沒有）：只給 `ls` 看「停著的有幾個」，不參與判斷。叫醒、派出去、下一次判定都會清掉。
4. **能力標記放在帳本 `features`**，不放 info（info 是人寫的）。`start` 只在「帳本有 `chain` 卻沒 `features`」時擋；還沒 boot 過的 K 不擋（見 §6 第 2 題）。
5. **`wake` 叫醒做成 syscall**（`K/requests/` 的一種單），不是另一種控制前綴；命令列 `aos-kernel wake NAME` 只是替人放這張單、等回音。理由：它要改帳本（進提交點 3），走 syscall 的「先記後出貨」與 `deletes` 去重現成就有。
6. **`drop_new` 也叫醒**（plan-b 只講 say）：T4 的 compact 申請、T2 的郵差（`aos_team_post.py` 投 `<成員家>/input/`）都用它；不叫的話都要等 5 分鐘。判斷法是「投進的資料夾的上一層有 `tick.json`」，所以郵差不用改。
8. **清空舊 `intake` 的出口退 0**（plan-b 沒提）：見 §2 與 astra 必修 2。
7. 調度者追加：`aos-agent status` 的 `kernel` 行，停著時印 `queued（停車：等回音或輸入，最晚 park_ms 自己醒）`（`aos_agent_status.py` 一處、規範 cli-status.md 一句、測試一條）；教程 02 的退出碼說明補 102。

## 6. 已裁決（照預設，調度者 09-24 轉達）

1. **已裁決：`park_ms` 預設 5 分鐘**（`info.park_ms` 可改、每個行程 `add --park-ms` 可改；agent 的 `start` 目前不帶，吃 kernel 的預設）。預設：**300000**。
2. **已裁決：`start` 不擋還沒 boot 過的 K。** 沒帳本時看不出 kernel 認不認得 102。預設：**不擋**（同一份 repo 的 kernel 一定認得；會把 add 留在 `K/requests/` 等 boot）。
3. **已裁決：升級中的 agent 最多多等一次 5 分鐘。**舊批送出時沒帶 `wake`，升級後它在等那批時會停車、最多 5 分鐘才醒（只有第一批）。預設：**接受**；要快就 `aos-agent say` 一句或 `aos-kernel wake agent-<名>`。
4. **已裁決：暫停的 agent 不停車**——連敗暫停、手動暫停中照舊每格輪詢（門關著退 101、手動暫停退 0），沒改成停車。預設：**照舊**——門是外人開的，kernel 不知道什麼時候開；要停車得讓 `continue` 也投 wake，下一輪再說。
5. **已裁決：`ls --json` 留第 2 版、加 `parked` 鍵**（只加鍵、不升版）。預設：**照這樣**。

## 7. 測試數

| 時點 | 條數 |
|---|---:|
| 開工時 main（`167871e`） | 61 檔 1771 |
| rebase 到 `1122f8d`（含 T4 的新測試）＋這隊 | 65 檔 1905（新增 38 條） |
| 再 rebase 到 `325a602`（含 T2）＋astra 修正 | 71 檔 2035（main 69 檔 1991，這隊新增 44 條） |
| 再 rebase 到 `4c42288`（T4 第二輪）＋status 顯示停車 | **71 檔 2044** 全綠（main 69 檔 1999，這隊新增 45 條） |

## astra 審查

必修 2 條、建議 2 條，**全修**（[review-astra.md](review-astra.md)）：

| # | 講什麼 | 怎麼修 |
|---|---|---|
| 必修 1 | stop／start 後新一代接手舊批、停車，舊批回來因代數不同不叫它 | 拿掉 `wake_gen`，只看名字（§5 第 2 條）；測試 `test_new_generation_is_woken_by_old_batch` |
| 必修 2 | 清空舊 `intake` 的出口也退 102，可能把剛投輸入的叫醒吃掉 | 那個出口改退 0（寫了東西），規範 idle.md 同改；測試 `test_empty_intake_recovery_does_not_park` |
| 建議 3 | say 崩潰窗口的測試其實只測期限 | 加真的 say 崩（`deliver` 放好、`wake` 丟例外）的測試；原測試改名 `test_park_ms_fallback` |
| 建議 4 | 補判定表、同格雙回音、act 多件、提交點 2 已存 woken 的測試；SIGKILL 切點講清楚 | 四條都補；§4 表把「放好回音、叫醒前」與「叫醒後、存帳本前」分兩列 |

另外順手改：`drop_new` 同名已在也叫醒（前一次可能崩在投好、叫之前）。
