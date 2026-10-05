本輪已確認 11 項缺陷或契約缺口；`97191272` 修正了原本的平手取整，但引入兩項回歸，而三次全套測試尚未完成，不能宣告回歸通過。

# proto7-2 第七輪對抗式回歸（astra-7）

依你的最新指示立即收尾。本報告只採用已讀取、已核對的結果；未再執行程式、補跑或清場。

## 1. 範圍與證據位置

- 受測來源 HEAD：`6daebe2ef8227021745def649f4e3d86a3a8038c`，包含小修 `97191272`。
- 環境：Python **3.12.3**、Linux／WSL2、8 個 CPU。
- 工作目錄：

  ```text
  /tmp/claude-1000/-home-guanyu-projs-aos/8aa61430-d017-4079-b09f-02620d555dd9/scratchpad/burn/ws/play7
  ```

下文程式與證據路徑均相對此目錄。開場比對的 **671 個 tracked 檔案，複本與來源 SHA-256 全部相同**。未修改來源 repo、未 commit、未 push；共用 `proto7-2/` 產品程式未修改。舊版對照與實驗產物放在 `evidence/`。

證據：`evidence/meta/baseline.json`、`evidence/meta/source-copy-comparison.json`、`evidence/meta/dispatch.md`。

分類依 `proto7-2/notes/component-contracts.md`：M 誤用、X 外部故障、B 組件保證未兌現、G 契約缺口。**注入故障本身不算缺陷；故障後違反承諾的行為才列 B。**

## 2. 全套測試與 flaky 狀態

執行命令為：

```sh
python3 proto7-2/tests/run_all.py -v
```

| 輪次 | 已確認結果 | 實際耗時 |
|---|---|---:|
| 第一次 | **352 通過／364 項；12 failures、0 errors** | **1,356.559 秒** |
| 第二次 | 已啟動，最後查看時仍在執行；未取得完成結果 | 未結算 |
| 第三次 | 尚未開始 | — |

原始證據：`evidence/regression/suite-1.log`、`suites.json`、`parsed.json`；執行器為 `evidence/regression/run_suites.py`。

第一次的 12 個失敗：

| 範圍 | 測試 |
|---|---|
| 程序身分／啟動交接 | `test_old_run_leftover_not_taken_as_new_run`、`test_keep_runner_before_exit`、`test_keep_runner_before_pid`、`test_once_after_popen` |
| subd | `test_reaped_before_new_daemon` |
| adapt 長跑／流速 | `test_long_run_file_count`、`test_fast_source`、`test_same_rate`、`test_slow_source` |
| adapt 恢復／pause | `test_daemon_kill9_restart`、`test_pause_stall_3`、`test_pause_stall_null` |

共享機器的 load average 曾超過 **200**；紀錄在 `evidence/regression/load.jsonl`。subd 那項失敗是生命週期的 `owner.run` 得到 `"4"`、測試固定期待 `"2"`，不是原任務仍存活的斷言失敗。

**尚未完成上述 12 案的單獨重跑，因此不能把它們全部判為 flaky，也不能全部判成產品 bug。** 本輪沒有改作者測試或放寬斷言，原始失敗完整保留。

## 3. `97191272` 小修驗收

### adapt：原問題修好，但有副作用

正負平手及十進位案例正確，包括 `2.5→3`、`-2.5→-3`、`2.675→2.68`。獨立 Fraction oracle 的 **390 個一般數值案例全部通過**，既有 adapt 單元測試 **16／16**。

但新增兩個回歸：

- Decimal 預設精度讓合法輸入拋例外：A8-01。
- 無條件轉 float 改變大整數並突破誤差界：A8-02。

兩者均以 **`97191272` 的精確前版**與真任務對照，不能判為「修正正確且無副作用」。

證據：`evidence/adapt/numeric-matrix.json`、`numeric-live.json`、`old-source-origin.json`、`summary.md`。

### subd：只是文件補前置，沒有新增倒鐘防護

該 commit 在 `proto7-2/modules/subd/README.md:48` 明列牆鐘不倒退，以及倒鐘可能誤認 stop、重開回收任務的後果；**沒有修改 subd 實作**。

本輪沒有重新完成倒鐘實驗，不把前輪結果冒稱本輪驗證，也不將已明訂的倒鐘前置違反重列 B。另找到與倒鐘無關的回條寫入故障問題，見 A8-09。

## 4. 已確認發現

### A8-01〔B／adapt，中〕Decimal 精度不足，合法來源使任務反覆退出、留下舊 `ok`

合法宣告：

```json
{"mul":1,"q":5e-13,"round":12,"as":"c"}
```

來源 `x=1e16` 即觸發 `decimal.InvalidOperation`。另一例是 `x=1e28、round=0、q=0.5`。

真 keep 任務連續三次退出碼 1；目的 node 已走到 r2～r4，暫存器仍停在 r1 的 `state:ok,c:1`。即使 `max_age=0`、來源鐘持續前進，也沒有更新成過期 unknown。精確前版能正常處理相同輸入。

- **根因／契約**：`proto7-2/packs/adapt/aos7_adapt.py:36–39`、`:213`、`:457`；`packs/adapt/spec.md:41`、`:50`、`:77`。
- **最小重現**：`python3 evidence/adapt/numeric_minimal.py`。
- **真任務證據**：`evidence/adapt/numeric-live.json`、`snapshots/current_precision/extreme_input/`。
- **範圍**：52 個精度邊界案例中，26 個只有新版拋例外；沒有故障注入。**此項由 `97191272` 引入。**

### A8-02〔B／adapt，中〕取整後強轉 float，合法整數失真且突破誤差界

來源 JSON 整數 `9007199254740993`，設定 `mul=1,q=0.5,round=0`：

- 新版輸出 `9007199254740992.0`。
- 實際誤差 **1，大於宣告的 0.5**。
- 接 step 條件 `value.c >= 9007199254740993`，新版停在 wait；精確前版保留整數並完成工作。

- **根因／契約**：`proto7-2/packs/adapt/aos7_adapt.py:39`、`:213–217`；`packs/adapt/spec.md:41`、`:102`。
- **最小重現**：`python3 evidence/adapt/numeric_minimal.py`。
- **證據**：`evidence/adapt/numeric-live.json`、`snapshots/current_integer_step/step_outcome/`、`snapshots/before_97191272_integer_step/step_outcome/`。
- **判定**：來源讀入時仍是精確整數；失真發生於 adapt。**此項由 `97191272` 引入。**

### A8-03〔B／adapt，中〕浮點端點塌縮，跨門檻的誤差帶被判成確定答案

`x=10000、mul=1、q=5e-13、round=12`，門檻也是 `10000`。

精確區間為：

```text
[9999.9999999999995, 10000.0000000000005]
```

四種比較都應落在誤差帶；實作的兩個 float 端點卻都變成 `10000`，使 `ge/gt/le/lt` 分別硬判為 `true/false/true/false`。真任務的 `ge` 輸出 `state:ok,high:true`。

- **根因／契約**：`proto7-2/packs/adapt/aos7_adapt.py:179–187`、`:220`；`packs/adapt/spec.md:42`、`:79`。
- **重現**：`python3 evidence/adapt/numeric_matrix.py`。
- **證據**：`evidence/adapt/numeric-matrix.json`、`snapshots/threshold_band_collapse/actual/`。
- **判定**：精確前版也有，屬本輪新發現的既存缺陷。

### A8-04〔B／adapt，中〕有限輸入乘法溢位，仍發布 `ok/Infinity`

有限來源 `1e308`，設定 `mul=2,q=0`、不指定 round，真任務寫出：

```text
state: ok
value.c: Infinity
err.c: 0
```

原始暫存器含非標準 JSON literal `Infinity`，卻標成可使用的 `ok`。

- **根因／契約**：`proto7-2/packs/adapt/aos7_adapt.py:207–217`、`:352–356`；`packs/adapt/spec.md:41`、`:92–103`。
- **最小重現**：`python3 evidence/adapt/numeric_minimal.py`。
- **證據**：`evidence/adapt/numeric-live.json`、`snapshots/finite_overflow/actual/register.json`。
- **判定**：既存缺陷；來源本身是合法有限數值，不是來源先提供 Infinity。

### A8-05〔B／daemon，中〕登記持久化失敗後，正常重送仍回成功卻不修復磁碟狀態

register／unregister 在 `nodes.json` 提交遇 EACCES 或 ENOSPC 時，先改了記憶體 registry。故障解除後，新請求因記憶體已改而直接回「已登記／沒有登記」，不再保存。

- register：回成功、時間線持續跑，但磁碟仍空；daemon 重開後登記消失。
- unregister：回成功，但磁碟仍有該 node，既有時間線也繼續跑；重開又載入它。

這不是只把第一件請求的「部分成功」當缺陷；關鍵是**第二件無故障的成功請求仍無法完成操作**。

- **根因／契約**：`proto7-2/lib/aos7_daemon.py:174–209`；`proto7-2/spec.md:25–26`、`:62`。
- **重現**：`python3 -B evidence/core_faults/probe_registry.py 新前綴`。
- **證據**：`evidence/core_faults/registry-initial.stdout`、`registry-rerun.stdout`、`runs/registry-rerun-*/result.json`。
- **重複性**：初跑四案＋獨立複跑四案，**8／8**；含真正 daemon 中斷後重開。主線另一次複核撞到等待兩回合的測具逾時，保留於 `evidence/review/registry.log`，未混算成功。

### A8-06〔G／槽 kill，中〕啟動中的 run 回報 kill 成功後，仍可開始同一次工作

精確暫停尚未 Popen 任務的 runner；birth 已記錄 runner 身分。公開槽 kill 經真 tock 執行，回：

```text
ok: true
msg: no process
run: job#1
```

恢復該 runner 後，**同一 run 1 才啟動任務並寫出副作用**。期間沒有新 tick、沒有新增 once。

- **實作位置**：`proto7-2/lib/aos7_task.py:186–206`、`lib/aos7_proc.py:122–143`、`:210–232`、`lib/aos7_run.py:68–88`。
- **契約位置**：`proto7-2/spec.md:243–247`；`notes/component-contracts.md:99–100`。
- **重現**：`python3 -B evidence/core_faults/probe_runner_kill.py 新前綴`。
- **證據**：`evidence/core_faults/runs/runner-kill-initial/result.json`、`runs/runner-kill-rerun/result.json`，**獨立重現 2 次**。

此处保守列 G：現行文字的成功條件偏向檢查「當時的任務程序已不在」，沒有完整定義啟動交接中的取消。如果 kill 原意是終止整次 run，則此行為應歸 B。不能將本案延伸成尚未執行的 daemon `stop --kill` 結論。

### A8-07〔B／tick 動態加掛，中〕連結已建立、birth 尚未提交，中斷後無法冪等恢復

合法動態加掛在建立 `mnt/newmount` 後、提交 birth 前遇 ENOSPC 或 SIGKILL，留下正確 symlink，但 birth 沒有掛載紀錄。

解除故障後，原請求或同內容重送都再次建立 symlink，得到 EEXIST；連續兩次重送仍失敗，無法補完 birth／dyn 紀錄。

- **根因／契約**：`proto7-2/lib/aos7_mount.py:58–63`、`:96–100`、`:156–167`；`proto7-2/spec.md:14`、`:185–188`。
- **重現**：`python3 -B evidence/core_faults/probe_mount_commit.py 新前綴`。
- **證據**：`evidence/core_faults/runs/mount-commit-initial-enospc/result.json`、`runs/mount-commit-initial-sigkill/result.json`。
- **範圍**：兩種故障各一次，每案兩次恢復後重送；SIGKILL 退出碼 -9。symlink 是核心建立，不是人手改生命週期檔的 M。

### A8-08〔B／budget call，中〕共同 I/O 未知邊界仍漏掉兩條路徑

**已結算重播讀不到入口回條：** 真 EACCES／注入 EIO 下，accepted 仍回 rc 0，failed／rejected 仍回 rc 1；原本非空的 `response` 變成 `null`，`--out` 也被覆寫。恢復權限後原 response 又能讀回。

**合法 payload 暫時讀不到：** 回 rc 2、stdout 空，沒有承諾的 unknown JSON／rc 3。此分支影響較低，發生於預留前。

- **根因／契約**：`proto7-2/packs/budget/aos7_budget_gate.py:169–172`、`:185–188`；`packs/budget/aos7_budget.py:224–231`；`packs/budget/spec.md:74–80`。
- **重現**：

  ```sh
  python3 evidence/budget/repro_read_boundaries.py --out 新證據目錄
  ```

- **證據**：`evidence/budget/reads-first/results.json`；主線独立複核為 `evidence/review/budget-read-boundaries/results.json`。
- **影響界線**：沒有重扣；帳、backend、gateway 的雜湊不變。缺陷是將未知變成終局，以及丟失回應內容。壞 JSON／不存在的 payload 只當輸入對照，不混列 X。

### A8-09〔B／subd，高〕合法 no-kill stop 的回條寫失敗，重開後誤收應保留任務

完整父 tick→subd→子 daemon→四包布局中，子根 `ctl-done/` 暫時 EACCES：

1. 合法 stop、不帶 kill，已實際完成；status 是 `stopped:true`。
2. 核心記錄「已執行，但回條寫不進去」，刪掉原請求。
3. 原 sensor、adapt、ledger、step 四個任務仍活。
4. 權限恢復、父 node resume 後，新子 daemon 出現時，原四個 PID／starttime 全部已被回收。

- **根因／契約**：`proto7-2/modules/subd/README.md:23–24`、`:48`；`modules/subd/aos7-subd:141–176`、`:264–268`；`lib/aos7_daemon.py:308–312`、`:370–372`。
- **契約衝突**：subd 假定「控制檔 stop 一定留回條」，但核心 §2.3 明訂處理例外可能刪請求。此處缺陷在 subd 的保留保證依賴了核心未提供的保證，不另把核心已文件化的例外規則列 bug。
- **重現**：

  ```sh
  QA_TIMEOUT_SCALE=5 python3 evidence/integration/probe.py stop_receipt_eacces --tag 新標籤
  ```

- **證據**：`evidence/integration/runs/r2-stop_receipt_eacces/stop-receipt-failure.json`；獨立精簡案為 `evidence/subd/receipt-failure.json`。
- **限制**：沒有聲稱帳本或檔案遺失；確認的是本應保留的活任務被破壞性回收。主線另一次精簡複跑等待新 daemon 逾時，未計成功。

### A8-10〔G／step＋budget，中〕budget 的非終局 rc 3，被 step 當成一般失敗結案

budget 遇暫時 backend EACCES，輸出 unknown／rc 3，留下 reserve＋intent。step-result 卻將所有非零退出碼發布為有效的 `ok:false` 結果，step 因此走 fail，**不會進入 `on_unknown:resend`**。

有 fail→end 分支時，恢復權限再走八個真回合，仍留 inflight=1；`resume --resend` 被拒絕，因工作已 ended。直接用原 K 呼叫 budget 才能接完，沒有重扣。

- **契約／實作**：`proto7-2/packs/budget/spec.md:74–81`、`packs/budget/README.md:55`；`packs/step/spec.md:70`、`:80–85`；`packs/step/aos7_step_result.py:75–77`、`aos7_step.py:447–457`、`:569–577`。
- **重現**：

  ```sh
  QA_TIMEOUT_SCALE=5 python3 evidence/integration/probe.py backend_unknown --tag 新標籤
  ```

- **證據**：`evidence/integration/runs/r2-backend_unknown/`、`runs/r3-backend_unknown/events.json`。
- **對照**：合法 `not_yet` 也重現；沒有 fail 分支時會 halted failed，人工 resend 可以同 K 的 a2 完成，證據在 `runs/r2-not_yet_halt/`。
- **歸類理由**：兩包局部規則各自成立，但建議接法沒有定義非終局結果如何跨過包裝層；不能籠統指責通用 step 對非零退出碼的既定規則。

### A8-11〔B／timeline，低〕有限的大整數 interval 讓設定驗證拋例外、node 不開回合

合法 JSON 的 `interval_ms: 10^309` 在 `math.isfinite` 的 int→float 轉換拋 `OverflowError`。純函式與真 daemon 都已確認；daemon 接受 register 後 node 停在 error、尚未建立 round.json。

- **根因／契約**：`proto7-2/lib/aos7_daemon_timeline.py:67–70`、`:160–170`；`proto7-2/spec.md:29`。
- **重現**：`python3 -B evidence/core_faults/probe_numeric.py 新前綴`。
- **證據**：`evidence/core_faults/runs/numeric-initial/result.json`、`numeric-initial.stderr`。
- **未驗完部分**：公開設定改回 0 後，原測具的 15 秒恢復等待逾時。主線後來啟動的較長等待複核尚未讀取結果，不能宣稱恢復通過。若把此數值視為不合，也應依契約採預設並記錯，而非卡住 node。

## 5. 已完成且未見退化的檢查

| 檢查 | 已確認結果 | 證據 |
|---|---|---|
| 四包正常流程 | 790 等待、800 誤差帶不扣、801 才消耗一次；close 後同 K 重播仍一次效果 | `evidence/integration/runs/r1-normal/` |
| 後端效果已提交後中斷 | 真 SIGKILL 後同 request 的 a2 完成，reserve／settle／效果各一次 | `evidence/integration/runs/r1-crash_call/` |
| pause＋父 daemon 中斷接管 | dst 狀態凍結，重開接回原 wrapper／子 daemon，resume 後完成交易 | `evidence/integration/runs/r1-pause_restart/` |
| 在途交易＋子代回收 | 舊任務回收、dst pause 保留、原 request 保留，人工重送後 used=1、inflight=0 | `evidence/integration/runs/r1-subd_recovery/` |
| budget 持久化窗口 | 12 次真 SIGKILL＋1 次 intent rename 前 EIO 完成；34 份狀態、57 筆跨快照轉移核帳通過 | `evidence/budget/persistence-first/results.json`、`audits.json`、`final-inventory.json` |
| adapt 故障恢復 | 六組恢復案例完成；EIO 六次命中、提交間 SIGKILL 一次命中，另有真 EACCES | `evidence/adapt/recovery-live.json`、`recovery-fault-hits.json` |
| adapt 長跑 | 初始 r1 後追加 1,000 個已關核心回合，止於 r1001；1,001 份暫存器、兩次任務中斷接回；檔名集合每圈不變 | `evidence/adapt/longrun-live.json`、`longrun-audit.json` |
| 極端回合起點 | 六組，含 `2^53`、`2^63` 附近與 `10^100`；真核心加一、budget 效期／水位／重播、adapt 耐性皆通過 | `evidence/review/large-rounds-v2/results.json` |
| 大回合獨立核帳 | 六份正對照通過；五種破壞資料的負對照全部抓到 | `evidence/review/large-round-audit.json` |

極端回合測試是**合成起點後執行真正核心／包函式**；不是 daemon 真正累積跑過 `10^100` 回合。其牆鐘跳動僅替換測試程序內的 `now` 回傳值，未改主機時間。

## 6. 做到一半、尚未驗完

### 全套與失敗重跑

第二輪尚未讀到完成結果；第三輪未開始；第一次 12 個失敗尚未逐案單獨重跑。這是原任務最重要的未完成項。

### subd 的 `recovering.prev` 遞迴成長

實作每次恢復失敗，都把完整前份 life 放入 `prev`：

- 子線完成 **74 次真程序 EIO 命中**，life 深度 75、43,107 bytes。
- 主線另以同程序執行原始 `subd.main`，不啟子程序，驗資料層重試；最後核對時深度已 **767**、**3,375,749 bytes**。
- **尚未讀到 RecursionError 或解除故障後永久無法恢復的完成結果，不能列成已確認 B。**

證據：`proto7-2/modules/subd/aos7-subd:266–267`、`evidence/subd/summary.md`、`evidence/review/subd_recovery_depth.py`、`evidence/review/subd-depth/`。

### 四包真 daemon 長跑

目標是新增 530 個已關 dst 回合。最後收到的完整進度為：

- dst **r284、closed**；
- **75 個 K、used=75、inflight=0**；
- 已完成第一段 250 個新增回合，後段仍在跑。

尚未取得最終長跑、完整核算與清場結果，不能把目標回合數當成果。證據：`evidence/integration/runs/r3-longrun/`、`summary.md`。

### 其他未完成

- budget 持久化矩陣共列 37 案，只完成 13 案；其餘 24 案不能計入結果。
- timeline 正常設定恢復的單獨複核尚未讀取完成輸出。
- runner／跨包分類的追加唯讀交叉審查，尚未收到終局回覆。
- 本輪統一最終 SHA／程序清場稽核尚未執行。

## 7. 沒來得及做的

- 三轮全套完成後，對所有時間敏感失敗逐案重跑並裁定 flaky。
- 新一輪 subd G3 十次壓力及完整多世代停止矩陣。
- 對所有 tick／tock 寫入與刪除持久點的全面中斷掃描。
- 真硬體磁碟故障、斷電後持久性、Python 3.11 的另版驗證。
- 修補建議的實作與修後回歸；本輪沒有修改產品來驗修法。

三條子代理曾收到服務端風險攔截，之後改為整理既有證據；未完成的故障矩陣沒有混算成通過。最新的立即收尾指示則中止了後續核驗。

## 8. 建議修法與優先順序

1. **先處理 A8-09 的誤回收。** 補足「stop 已生效、回條未提交」的可靠交接；未知不能直接轉成可回收。不要靠解析錯誤文字建立新保證。
2. **修正 A8-01／02 的取整回歸。** Decimal 精度依量級與小數位配置；避免無條件轉 float，並確保表示誤差包含於 `err`。
3. **修正 A8-05／07 的半提交恢復。** registry 持久化成功才提交記憶體；同名同目標的核心掛載連結要能補完 birth。
4. **補清 A8-06／10 的交接契約。** 定義啟動中 run 的 kill 成功語意，以及 budget 非終局 rc 3 如何接到 step 的有限重送。
5. **補 A8-03／04／08 的數值與未知分支。** 保留非零誤差帶、拒絕發布非有限 `ok` 值，並讓所有已承諾的讀取故障一致回 unknown／3。
6. **補 A8-11 的設定驗證，再完成 flaky 核驗。** 不應先放寬測試來換取全綠；先辨明是測試固定時序假設、環境壓力，還是產品保證失效。

**收尾狀態：** adapt、budget、core_faults、subd 子線各自已回報清場；但主線後續複核、第二輪全套與整合長跑的最後程序狀態尚未確認。依你的指示，本次未再執行任何檢查或清理，因此不能保證先前啟動的背景程序都已結束。