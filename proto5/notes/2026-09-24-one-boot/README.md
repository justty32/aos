← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜[計畫](plan.md)｜[astra 任務書](review-task.md)｜[astra 回報](review-astra.md)｜第二輪 [任務書](review2-task.md)、[回報](review2-astra.md)

# 開機合一、家不合一＋kernel 帳本換 sqlite（2026-09-24，P 隊）

**一句話**：現在一條 `aos up` 開機、一條 `aos down` 停機。kernel 不再有自己的 cpu：**daemon 替它定時開一格 `aos-kernel tick`**，有新單時也馬上開一格。kernel 帳本從 `K/state.json` 換成 `K/ledger.sqlite`。`D/` 和 `K/` 仍是兩個家。

使用者 09-24 拍板的依據：[daemon-split-review 裁決](../2026-09-24-daemon-split-review/README.md)、WAIT_USER 的 one-program I 隊五題。

## 1. 改了什麼

| 以前 | 現在 |
|---|---|
| `aos-daemon boot`（放背景）＋`aos-kernel boot` 兩步 | `aos up`：daemon 沒在跑就開（stderr 進 `D/daemon.log`），再 boot，等第一格跑完、印 `health` |
| `aos-kernel halt`＋`aos-daemon halt` | `aos down`：kernel 停好，daemon 沒別人要用就一起停 |
| kernel 池那顆 kernel cpu 跑 tick，每格先把下一格放進去（tick 鏈） | **拿掉**。daemon 定時（`tick_ms`）或 `K/requests/` 出現新檔時開一格當孩子，不等它 |
| boot 交接：kernel 池縮 0 → 等 → 寫帳本 → 拉 1 → 放第 1 格 | boot＝拿 `K/.tick.lock` → 寫帳本 → 向 daemon 登記「請替我開 tick」 |
| 同時只有一格靠「鏈只有一條」 | daemon 同一個 K 同時只開一格，再加 `K/.tick.lock`（flock，kill -9 後自己解開；拿不到退 75） |
| 帳本 `K/state.json`，一格最多整份寫四次 | `K/ledger.sqlite`，一格最多三筆交易，每筆只寫變了的列 |
| aos-agent 直接打開 `K/state.json` | 走 `aos_kernel_store`；人和程式用 `aos-kernel proc NAME --json` 查一筆 |

`aos-daemon`、`aos-kernel` 的子命令都還在，給人 debug。規範：[daemon §10 開 tick](../../spec/daemon/ticks.md)、[daemon §11 aos up／down](../../spec/daemon/up.md)、[kernel 帳本](../../spec/kernel/ledger.md)、[kernel boot](../../spec/kernel/boot.md)、[一格 tick](../../spec/kernel/tick.md)。

**兩條已拍板前提改了**（規範的「已拍板的前提」那節有註明「2026-09-24 P 審查後使用者改的」）：
- daemon「不認識 kernel」→ 只認得 kernel 家在哪、多久開一格；**不讀 kernel 家任何檔的內容**（只 stat `K/requests/`、列檔名）、不用 root。
- kernel「在 kernel cpu 上一格接一格」→ daemon 定時或有新單時開一格，同時只准一格。
- 另外「kernel 的家照 cpu 範式、帳本是 state.json」只對帳本放寬（I 隊④）；`requests/`、`responses/`、cpu 家、信箱仍是檔案。

## 2. 帳本結構（`K/ledger.sqlite`，第 3 版）

| 表 | 一列是什麼 | 欄 |
|---|---|---|
| `meta` | 一個小鍵 | `key`、`value`（JSON）：version、chain、cli、ticker（替它開 tick 的 daemon）、last_seq、last_tick_at、phase、halting、features、recent、stale、ready、delayed、四個出貨箱 |
| `procs` | 一個行程 | `name`、`status`、`pool`、`body`（跟以前 `procs.<名>` 同形） |
| `pools` | 一個池 | `name`、`body` |
| `busy` | 一顆忙的 cpu | `cpu`、`ord`（巡檢輪轉的順序）、`proc`（有索引）、`body` |

- `on`（行程在哪顆）不存了，讀的時候從 `busy` 反推；`kcpu`、kernel 池拿掉。
- 一格照舊整份讀進記憶體；存檔時只寫變了的列、一筆交易。崩在交易中間＝整筆沒發生。
- WAL 模式、`synchronous=NORMAL`：跟以前的 `write_json` 一樣只保證行程崩潰，不保證斷電。
- 舊的 `K/state.json`（第 2 版）：boot 時先把舊 kernel 池縮到 0、等舊 tick 停妥，再重讀、整份匯入，改名 `state.json.v2-old`。只要 `state.json` 還在就算還沒換好。

## 3. 量測（同一台機器、同一支腳本，各跑 3 次）

設定：default 2 顆、llm 1 顆、`tick_ms`＝`interval_ms`＝1000、1 個 agent（停車中）。改前＝main `c56044d`，改後＝這個分支。

| 量什麼 | 改前 | 改後 |
|---|---:|---:|
| 開機指令本身（改前 daemon boot＋kernel boot；改後 `aos up`） | 0.10～0.12 秒 | 1.12～1.14 秒（多等了第一格跑完、各池第一張宣告有回音） |
| **開機到第一張 once 單回來** | **3.29～3.31 秒** | **1.6 秒** |
| **投一張 add 到收到回音**（20 次平均；最慢） | **0.46～0.55 秒**（最慢 1.03） | **0.040～0.044 秒**（最慢 0.052） |
| 閒 60 秒整套 CPU 秒（daemon、cpu、tick 全算） | 2.74～3.10 | 2.31～2.44 |
| 閒 60 秒 kernel 跑幾格 | 56～57 | 60 |
| 閒 60 秒 agent 被派幾格 | 0 | 0 |

- 投單延遲少了一個數量級：daemon 看到 `K/requests/` 有新檔就馬上開一格，不用等下一個 `tick_ms`。cpu 回音的通知也丟在那裡，所以回音也收得比較快。
- 開機快：以前要等 kernel cpu 拉起來、鏈接上。`aos up` 本身變慢是因為它多等了「第一格跑完＋池的宣告有回音」。daemon 自己家的回音不算 K 的新檔，所以要等下一個 `tick_ms`，約 1 秒。
- 閒著的 CPU 少一點（少了一顆每 20 ms 掃資料夾的 kernel cpu）；kernel 照樣每秒一格。
- **沒壓測**：上千顆 cpu、上萬個行程都沒量。帳本讀仍是整份（O(行程數)），寫變成只寫變了的列。

## 4. 真跑（LiteLLM `localhost:4000` 的 deepseek-chat；沒碰 LM Studio／ollama）

腳本在 scratchpad 跑，沒收進 repo。最後的程式跑了 3 次，每次都走完：`aos up` → agent init／start → `say --wait` → kill -9 一顆 cpu → kill -9 一格 tick → kill -9 daemon 再 `aos up` → 停車後 `say` 喚醒 → `aos down` → `pgrep` 空。節錄（第 1 次）：

```text
=== init + aos up
up K=…/real-1/K  daemon …/real-1/D（新開）  2 個池、3 顆 cpu
health ok
=== say --wait #1
1+1 等於 2。                                  took 3.9s
=== kill -9 一顆 cpu（default/0）
default/0 重拉成 pid 1756809
=== kill -9 一格 tick
aos-daemon: TickFailed: K=…/K 這格退出 137（連敗 1，1000 ms 後再試）
health ok
integrity ok procs ['agent-bob']
=== kill -9 daemon，再 aos up
health daemon 沒在跑：…/D（aos up；…）
up K=…/K  daemon …/D（新開）  2 個池、3 顆 cpu
integrity ok procs ['agent-bob']
proc agent-bob True queued runs 4
=== 等停車
kernel agent-bob  queued（停車：等回音或輸入，最晚 park_ms 自己醒）
停車中 10 秒 agent-bob 被派 0 格
=== say 喚醒 #2
2+2 等於 4。                                  took 4.9s
=== aos down
stopped agent-bob
stopped
stopped
pgrep: （空）
```

教程組照改好的教程 01～07 從空的資料夾整套真跑兩遍（07 的 claude／codex 要花錢的步驟沒跑），全過。

真跑挖到並修掉的：
- `aos up` 碰到池名撞了（`NameTaken`）還印 up、退 0 → 現在等各池第一張宣告有回音，印 `health`，壞了退 1。
- 撞名的 K `aos down` 會卡 30 秒逾時 → halt 不再等「從沒被 daemon 確認過」的池位置。
- `aos down` 留著 daemon 時訊息黏字；check 的「daemon 沒在跑」改指 `aos up`。

## 5. 崩潰與時序測試

新檔 `lib/test/test_one_boot.py`（14 條，真 daemon＋真 tick；要停在帳本交易提交前時用 `aos_kernel_store.crash_hook`，只有測試設環境變數才會停）：

| 情況 | 結果 | 測試 |
|---|---|---|
| tick 寫帳本交易中間 kill -9 | 交易回滾：帳本沒那筆、原單還在；下一格重判，只登記一次、只回一次；`integrity_check` ok | `test_kill9_inside_ledger_transaction_rolls_back` |
| tick 卡住超過 `tick_timeout_ms` | daemon 整組 KILL、記 `TickFailed …逾時`、退避後再開；那格的決定沒發生、重做一次；連敗之後歸零 | `test_stuck_tick_is_killed_counted_and_retried` |
| daemon 被 kill -9 時有一格卡著 | 那格變孤兒、還握著鎖；新 daemon 開的格退 75（不算失敗）；孤兒的鬧鐘（2×逾時）到了自己死；帳本對得上、cpu 由新 daemon 拉回 | `test_daemon_kill9_while_tick_running_then_restart` |
| 連續失敗 | 記 log、退避、不自己停；修好後連敗歸零、格繼續走；`ls` 報 `tick 連敗 N 次` | `test_consecutive_failures_back_off_and_never_stop`、`test_health_reports_failing_ticks` |
| 停 daemon 時有一格卡著 | 等 `stop_wait_ms＋kill_wait_ms` 再 KILL 整組；daemon 退 0；登記留著 | `test_daemon_halt_kills_stuck_tick` |
| `aos up`→`aos up`→`aos down` | 再跑一次 up 等於重 boot；down 後登記撤掉、沒有殘留行程 | `test_aos_up_then_down_leaves_nothing` |
| 新檔觸發、同時一格 | `tick_ms` 60 秒時投 add 一秒內處理；閒著不空轉；人手跑 tick 撞上正在跑的那格退 75 | `Triggers` 兩條 |
| 舊 `state.json` | tick 拒絕（`LedgerVersion`）；boot 匯入、改名 | `test_v2_state_json_is_imported_on_boot` |
| astra 必修 2～4 的回歸 | 見 §6 | `AstraFixes` 三條 |

另外：`test_daemon.TickTest` 4 條（假 kernel cli：登記驗證、定時與新檔觸發、75、退避、逾時、daemon 重開接著開、停機中拒登記）；`test_agent_ledger.py` 13 條（aos-agent 的相容檢查、`kernel_proc` 看得到 discard、sweep 在 K 沒帳本時不刪）；舊的 C-7／C-8 閘門崩潰測試全部改成 daemon 開 tick 的版本照跑，K2 停車喚醒的崩潰測試（`test_park_crash`）沒改就綠。

**刪掉的測試**（只為舊設計存在）：

| 測試 | 為什麼 | 誰蓋到 |
|---|---|---|
| `test_kernel_recovery::test_next_tick_placed_before_last_seq_record_is_idempotent` | 「先放下一格再記 last_seq」的提交點 1 不存在了 | last_seq 跟提交點 B 一起存：`test_kernel_tick2::test_at_most_three_writes` |
| `test_kernel_recovery::test_tick_request_uses_plain_cli_args_and_no_timeout` | 不再往 kernel cpu 放 tick 單 | 登記內容：`test_kernel_recovery::test_first_boot…`、`test_daemon::TickTest` |
| `test_kernel_recovery::test_reloaded_tick_ms_controls_sleep` | tick 不再睡 `tick_ms` | `test_one_boot` 的 `Triggers`、`test_daemon::TickTest` |
| `test_kernel_boot2::test_boot_moves_kernel_pool` | 沒有 kernel 池可以搬 | 沒有對應（舊 info 的 kernel 池 daemon 當開 tick 的 daemon：`test_kernel::test_legacy_kernel_pool_is_skipped`） |

其餘改名、改寫成等價版本的（例如 kernel 池撞名 → 登記被拒、kernel cpu 不在 → tick 沒登記）不算刪。

**測試數**：開工時 main 71 檔 2044 條；rebase 到 main `10a89fc`（72 檔 2068）之後，**74 檔 2106 條全綠**（約 170 秒）。

## 6. astra 審查（gpt-6-astra，唯讀）

必修 5 條**全修**，建議 2 條**都做**（[回報](review-astra.md)）：

| # | 講什麼 | 怎麼修 |
|---|---|---|
| 必修 1 | 匯入舊 `state.json` 時，舊程式的 tick（沒有 `.tick.lock`）在 boot 等舊 kernel 池收乾淨期間還可能提交 | 先只從舊帳本找 kernel 池、等停妥，**再重讀**整份匯入；測試 `test_legacy_import_rereads_after_old_tick_stopped` |
| 必修 2 | sqlite URI 沒跳脫 `%`，字面的 `%2F` 會開到別的家 | 改用 `Path.as_uri()`；測試 `test_percent_in_path_does_not_alias_another_home` |
| 必修 3 | daemon 崩在「記下 current、還沒處理」之間，撤登記單會被丟掉，daemon 永遠替停好的 K 開空格 | 停好之後還被開格、而 `D/kernels/` 還有登記就再送一張；測試 `test_stopped_kernel_resends_untick_while_still_registered` |
| 必修 4 | 撤登記後馬上重登記，舊那格還在跑時會多開一格 | 重登記沿用還在跑的那格；測試 `test_reregister_while_old_tick_running_keeps_one_at_a_time` |
| 必修 5 | 規範說「有 sqlite 就只認它」，程式是「state.json 還在就算舊的」 | 規範改成跟程式一樣 |
| 建議 | `aos down` 應該也看帳本記的 daemon；COMMIT 失敗也要收掉交易 | 都做了 |

其他自己或子隊挖到的：tick 結束時沒關鬧鐘（同一個行程直接呼叫 tick 時會被 SIGALRM 殺，已修）；daemon 停機時砍掉的那格不算失敗；health 的連敗在 stopping 也判；`knows()` 碰到壞的 `replies` 報 ReadFailed；aos-agent 的 sweep 在 K 沒 boot 過時照舊先留著。

## 7. 碰到別隊地盤的地方

- `lib/aos_team_post.py`：**兩行**讀 `K/state.json` 的 procs 改成 `aos_kernel_store.peek_procs(k)`、`aos_kernel_store.peek_proc(kernel, name)`，加一行 `import aos_kernel_store`（`kernel_has` 與 `register` 裡那兩處）。
- `lib/test/test_team_post.py`：一條測試寫假帳本那一行改成寫 sqlite。
- `templates/cli-agents/kernel2.json` 與它的 README：拿掉 `kernel` 池（init 現在拒絕這個保留名，教程 07 會壞）。
- `proto5/README.md`、`lib/README.md`、`wf/workflows/common/code-map.md`：只改講 kernel cpu、state.json、boot 的句子，插新檔的列，沒重排。

## 8. 我代裁的（附預設，都已照做）

1. **什麼時候開一格**：時間到（上一格開始後 `tick_ms`）或 `K/requests/` 出現上一格開始時沒有的 `.json` 檔。daemon 自己家的回音（scale 單的回音）不算，所以池的宣告確認要等下一個 `tick_ms`。
2. **有新檔就開，沒有最小間隔**：忙的時候一格接一格（一次只一格，每格一次 Python 起動）。
3. **退 75＝鎖被佔（別人在跑），不算失敗**，`tick_ms` 後再試。
4. **連敗**：stderr 記一行，退避 min(max(`tick_ms`, 100 ms)×2^(連敗−1), `restart_max_ms`（預設 60 秒）)，退避中新檔也不觸發，**不自己停**；重登記（`aos up`）連敗歸零。登記檔只在登記、失敗、恢復時重寫。
5. **`tick_timeout_ms` 預設 60000**：逾時 daemon 整組 KILL、算失敗；tick 自己設 2 倍的鬧鐘，只給 daemon 被殺後的孤兒用。
6. **daemon 停機時卡著的那格**：等 `stop_wait_ms＋kill_wait_ms` 再 KILL，不算這個 kernel 的失敗；登記留著，下次開 daemon 照開。
7. **登記存在 daemon 家** `D/kernels/<id>.json`（id＝K 路徑的 SHA-256 前 16 字元）。開 tick 的 daemon＝info 頂層 `daemon`（舊 info 的 kernel 池寫了 daemon 就用它）。每個池都自己寫 daemon、頂層沒寫的 info 現在 boot 會 `NoDaemon`。
8. **帳本四張表**、`on` 反推、WAL＋`synchronous=NORMAL`。
9. **提交點四個變三個**（A 出貨完、B 決定完、C 出貨完）。被砍、沒存到 B 的那格，下一格會用同一個序號；檔名撞到都當「已放」，無害（astra 看過）。
10. **舊 `state.json` 自動匯入**、改名 `state.json.v2-old`；舊 kernel 池縮到 0。第 1 版照舊拒絕。
11. **`kernel` 變保留名**：init 的 config 寫了就拒絕；舊 info 裡的讀得過、略過（check 會 warn）。
12. **`ls --json` 升第 3 版**：`kernel.cpu` 換成 `kernel.tick {registered, every_ms, fails, last_exit, last_at}`，池表不再有 kernel。kernel cpu 不存在了，留著會說謊；第 2 版承諾不刪不改名，所以升版。沒有程式在讀第 2 版。
13. **`aos-kernel proc NAME --json`**：`{_metainfo: aos_kernel_proc 第 1 版, name, found, proc, cpu, discard}`；沒這個行程退 1（`--json` 照印 `found: false`）。
14. **`aos up` 每次都重 boot**（冪等：換 boot 編號、整份重送宣告、重新登記、連敗歸零），所以每天開機就是 `aos up`；開 daemon 用 setsid、stdout／stderr 附加到 `D/daemon.log`、PATH 前面補 `proto5/cli`；等第一格＋池的第一張宣告（最多 5 秒）；最後印 `health`，池出錯、daemon／tick 有問題退 1。
15. **`aos down`**：`aos-kernel halt` → 等撤登記（最多 5 秒）→ 用到的 daemon 沒別的 kernel 登記、沒池了才停；`--keep-daemon` 只停 kernel。
16. **停好那格請 daemon 撤登記**；之後還被開格而登記還在就再送一張。
17. **`aos-agent start` 的相容檢查**：以前看帳本 `features` 有沒有 `park`。現在：`done_exit` 102 照擋；K 還是舊 `state.json`＝`KernelIncompatible`（叫你 `aos up`）；sqlite 帳本有 chain 卻沒 `park`＝同；沒 boot 過不擋。
18. **halt 不等從沒被 daemon 確認過的池位置**（撞名那種）。

## 9. 要你拍的（附預設；都已照預設做）

1. **`proto5/cli/aos` 跟 repo 的 C++ 主程式 `aos` 同名**。PATH 把 `proto5/cli` 放前面時會蓋過 C++ 那支。預設：照任務書叫 `aos`（C++ 那支平常在 `build/`，不在 PATH）；要避開就改名，例如 `aos5`。
2. **新單觸發沒有最小間隔**。忙的時候 kernel 一格接一格，每格一次 Python 起動（約 0.05～0.1 秒 CPU）。預設：不設，等上千顆時再量。
3. **機器崩過之後 `aos down` 印 `not running`，但帳本還寫 `running`**（daemon 不在，沒人跑 halt 那幾格）。下次 `aos up` 就對了。預設：不管。

## 10. 六軸自評

| 軸 | 評 | 一句 |
|---|---|---|
| LLM 參與 | 不變 | 只動框架；agent、模型呼叫沒改 |
| 穩定 | 好一點 | 少了一顆 kernel cpu 與開機交接這串最容易出錯的地方；帳本改成交易；鎖在 kill -9 後自己解開。多了「daemon 替 kernel 開 tick」這段新程式，靠 14＋4 條真 daemon 測試與 3 次真跑撐著 |
| 資源 | 好一點 | 閒 60 秒 CPU 從約 3.0 秒降到約 2.4 秒；少一顆常駐行程 |
| 速度 | 好很多 | 投單到回音 0.5 秒 → 0.04 秒；開機到能用 3.3 秒 → 1.6 秒 |
| 人好懂 | 好很多 | 一條 `aos up`、一條 `aos down`；`ls` 第二行直接說 tick 誰在開、上一格多久前；查一筆行程有正式入口 |
| 邊界 | 持平 | daemon 仍不讀 kernel 家的內容、不用 root；帳本換 sqlite 後別的程式要看請用 `proc`／`ls --json`，不要自己開檔。沒壓測上千顆 |

## 追加：試玩七件

新手試玩（[報告](../play/2026-09-24-one-boot-opus.md)，5/4/4/4/4，沒卡住）挖到七件，全部處理：

| # | 試玩看到 | 怎麼處理 | 測試（`lib/test/test_play_one_boot.py`） |
|---|---|---|---|
| 1 | `aos-kernel ack` 什麼都不印、檔要下一格才消失，以為沒成功 | 印 `acked NAME（ack 已放進 K/requests/，下一格 tick 刪掉回音）`；教程 02 補一句 | `test_ack_says_what_happens` |
| 2 | 池名跟別的 kernel 撞，`check` 全 ok、`aos up` 才報 `NameTaken` | `check` 多一項 `pools/<池>`：那池在 daemon 家已有 `pool.json` 而 owner 不是這個 K＝bad，提示寫 `dpool`。跟 daemon 一樣直接比 owner 字串；daemon 沒開也查得到 | `test_check_reports_pool_owned_by_another_kernel`、`test_check_compares_owner_like_daemon`、`test_check_quiet_when_pool_is_ours` |
| 3 | kill -9 daemon 後 `ls`：health 說 daemon 不在，同一張表卻印 `running 2`、kernel `running` | daemon 不在時：kernel 行 `running（帳本這樣寫；daemon 不在，其實沒在跑）`、tick 行 `tick 沒人開（daemon 沒在跑；aos up）`、池行 `不明（daemon 沒在跑；摘要是舊的…）`。`--json` 不變（看 `daemon.alive` 自己判）。上一輪第 3 題（崩過之後 `aos down` 說 not running）一起處理：見第 5 件 | `test_ls_after_daemon_killed_is_consistent` |
| 4 | 模型問到一半 kill -9 daemon，舊 cpu 和 `aos-llm call` 還活著，好像新舊並存 | **判定為刻意**（孩子不綁 daemon 的命，one-program 調查提過），不改程式。真跑量過：下一任開機**先收掉舊的、死透才拉新的**（三次都是舊 cpu 死後 8～13 ms 新的才起來），不會兩個主人。寫進 [daemon §6.1](../../spec/daemon/lifecycle.md)（保證外：沒爸爸那段多長）與教程 01「底下在幹嘛」。被打斷的那件回 `stopped`（或 `Interrupted`），不重派 | `test_new_daemon_waits_for_old_cpu_before_spawning`（新的一出現當場查舊的已死、被打斷的 once 單有回音） |
| 5 | `aos down` 打兩次都印 `stopped stopped` | `aos down` 自己印摘要，照 halt 回報的結果：`kernel … 剛停／本來就停了／沒 boot 過／沒在跑：帳本還寫 running，但 daemon 不在（或沒登記）…下次 aos up 會接上`；每個 daemon `剛停／本來就沒在跑／留著（--keep-daemon）／沒停：還有…` | `test_aos_down_twice_and_after_crash`、`test_down_reports_what_stop_saw` |
| 6 | 開機、kill -9、再開好幾輪，`D/daemon.log` 還是 0 位元組（daemon 只在出錯時寫 stderr） | 開機一行 `aos-daemon: Boot: <時間> 開機 pid N`（上一任沒正常停就加 `（上一任 pid M 沒正常停，先收它留下的 K 顆孩子）`）；正常停機存好 `pid 0` 後一行 `Stopped`。被 kill -9 那一刻寫不了，由下一任的 Boot 行記 | `test_daemon_log_has_boot_crash_and_stop_lines` |
| 7 | 用 `pgrep -f aos` 驗清場永遠不空（repo 路徑有 aos、別的 session 也在跑） | 教程 01 關機那段改成看 `aos-daemon ls` 第一行 `daemon not running`；真要 pgrep 就篩自己的 `$W` | 教程（不是程式） |

另外兩條舊測試跟著改（`ack` 以前斷言什麼都不印）：`test_kernel_cli::test_ack_by_name_or_path`、`test_kernel_integration::test_cli_once_without_wait_prints_response_path`。沒刪任何測試。

**真跑**（LiteLLM deepseek-chat，沒碰 LM Studio）：模型寫短文寫到一半 kill -9 daemon → 1 秒後舊 cpu 與 `aos-llm call` 都還活著 → `aos up`（0.7 秒）→ 新 daemon 先收掉舊的（`aos-llm call` 先死、舊 cpu 5 ms 後死）、8～13 ms 後拉起新的 → agent 自己重送，`listen --wait` 拿到完整短文 → `aos down` 印「剛停」兩行、再 `aos down` 印「本來就停了／本來就沒在跑」→ `daemon.log` 有兩行 Boot（第二行註明上一任沒正常停）、一行 Stopped → `pgrep` 篩 `$W` 空。跑了 3 次，三次都一樣。

**astra 第二輪**（[回報](review2-astra.md)）：必修 3 條全修——① check 的 owner 比法改成跟 daemon 一樣比字串（以前 `abspath` 會把 `K/` 當成自己、daemon 卻說撞名）；② `aos down` 以前是停之前先偷看一次，中間狀態變了會印錯，改成照 halt 自己回報的結果印，並分開「daemon 不在」和「沒登記」；③ 規範與教程說「被打斷的會重派」不對，改成照實際（`stopped`／`Interrupted` 回給交件者，不重派）。建議 3 條：Stopped 改在存好 `pid 0` 之後才印（做了）；「沒正常停」是依 `state.json` 有效的舊 pid 推定，規範寫明（做了）；舊 cpu 死亡要在新的出現當場查、並驗被打斷那件的回音（做了），其餘 mock 分支沒補。

**我代裁的**：第 4 件判刻意、不改程式（理由：daemon 死、孩子不跟著死是當初「崩了互不拖累」的設計；接手時已經先收舊的再拉新的，不會兩個主人）；`--json` 在 daemon 不在時不改（給程式的欄位不動，程式自己看 `alive`）；`aos down` 碰到崩過的 K 不去改帳本（改帳本要 tick 跑、daemon 不在沒人跑，下次 `aos up` 會接上）。

**測試數**：main `699399d` 74 檔 2106 條 → 75 檔 2115 條全綠（新增 `test_play_one_boot.py` 9 條）。

## 追加二：偶發測試（T5 回報）

`test_kernel_recovery::test_first_boot_initializes_missing_ledger_and_writes_raw_envs` 全套跑時偶發紅一次（`answered` 0 != 1）。
**原因在測試，不是程式**：boot 把「登記」的回音 ack 掉之後才回來，但假 daemon 的背景執行緒要等 `fake.stop()` 才停；機器忙的時候，它在這中間多跑一圈，把 ack 和回音都處理掉了，測試卻斷言「回音還在、ack 還沒處理」。
**改測試**：先讓假 daemon 把剩下的處理完，再驗「登記單處理過、回音與 ack 都清乾淨」，跟時序無關。產品程式沒動。

負載下（背景同時跑 `test_agent_tick`、`test_kernel_crash`、`test_exec*`）各跑 20 次：`test_kernel_recovery` 20/20、`test_one_boot` 20/20、`test_daemon` 20/20，沒有別條偶發。

## 下一輪（T5 報告給 P 隊的兩件，這次不修）

1. **每輪「問模型 → 跑工具」約六成時間花在格與格之間**（T5 例子 1：一件 170 秒裡約 106 秒不在模型也不在工具）。
   我的想法：一輪要走 agent 一格 → kernel 一格 → llm cpu 撿單 → kernel 一格叫醒 → agent 一格……每一跳都有「cpu 每 200 ms 才看一次資料夾（`cpu.poll_ms`）」加「起一支 Python（agent tick、aos-exec、kernel tick 各一次）」。
   先量每一跳花多少（kernel.log 已有派工與回音，agent 那邊補時間戳），再從便宜的下手：kernel 放派工單後順手叫醒那顆 cpu（像 `resp-` 通知反過來），或把 `poll_ms` 調回 20 看 CPU 代價；再來才是 agent 一格裡多走幾步、少起 Python。
2. **反覆工作連錯 `bad_after` 次變 `bad` 之後沒人知道**。現在只寫進 `kernel.log`、`ls` 列出來，health 還是 `ok`。
   我的想法：分兩步。先讓 `aos-kernel ls` 第一行在有 `bad` 行程時不是 `ok`（例如 `procs：N 個 bad（…）`），`aos up` 也會印到；再讓 `add` 可以帶一個「壞了通知誰」（丟一張檔進某個 agent 家的 `input/`，跟郵差同一招），kernel 在判 `bad` 那格出貨時放。第二步要不要做給使用者拍。
