在前後套用相同穩定性修補的受控比較中，364 項測試的中位耗時由 **190.19 秒降至 65.19 秒，節省 125.00 秒、縮短 65.7%（2.92 倍）**；最終 19 輪驗收全部通過，未觀察到新增 flaky。

## 範圍與比較基準

所有修改、測試與證據均在指定工作複本內完成。未修改 `/home/guanyu/projs/aos`、未 commit、未 push、未呼叫 LLM 端點。最終 patch 涉及 **17 個測試／README 檔案，沒有修改 daemon、tick、tock 等產品程式**。

必須先說明：**原樣複本在這台機器上並非全綠**。原始三輪都執行 364 項，但各只有 359 項通過，因此不能直接將它們當成「364 項全過」的比較基準。

| 原樣複本 | 第一次 | 第二次 | 第三次 |
|---|---:|---:|---:|
| 耗時 | 456.95 秒 | 220.47 秒 | 207.79 秒 |
| 通過數 | 359/364 | 359/364 | 359/364 |

第一輪開始時，8 CPU 主機的 load average 約 73，同機負載影響明顯。所有失敗均保留，沒有刪除後挑選成功樣本。

最終比較使用：

- **改前**：原始快照＋共同穩定性修補＋共同 runner，串行執行。
- **改後**：相同修補，再加入條件等待、fixture 快取及四個 worker，依歷史耗時優先排較慢的檔案。

證據：`evidence/environment.json`、`evidence/runs/baseline-{1,2,3}.log`、`evidence/variant-definition.json`、`evidence/audit-patch-split.json`。

## 前後各三次量測

預先固定順序為「前 1、後 1、後 2、前 2、前 3、後 3」，使用 monotonic 時鐘量完整命令耗時，包含啟動、收集、執行與報告輸出。

| 最終版本 | 第一次 | 第二次 | 第三次 | 中位數 | 每輪結果 |
|---|---:|---:|---:|---:|---|
| 改前，串行 | 189.62 | 192.56 | 190.19 | **190.19 秒** | 364/364 |
| 改後，四 worker＋耗時排序 | 66.76 | 65.19 | 61.22 | **65.19 秒** | 364/364 |

另外完成：

| 驗收條件 | 輪數 | 耗時 | 結果 |
|---|---:|---|---|
| 一般四 worker 平行重跑 | 10 | 中位數 61.56 秒；範圍 57.49～69.07 秒 | 全部 364/364 |
| 限制兩顆 CPU，仍用四 worker | 3 | 80.53、82.30、82.95 秒 | 全部 364/364 |
| 交錯前後比較 | 6 | 如上表 | 全部 364/364 |

最終共 **19 輪、6,916 次案例執行全部通過**；其中加速版本為 16 輪、5,824 次案例執行。

證據：`最終量測與驗證結果`、`evidence/paired-plan.json`。可重現的量測脚本為 `evidence/paired_benchmark.py:12`、`evidence/benchmark.py:37`；純資料驗證為 `python3 evidence/final-summary.py`。

## 加速改動、收益與風險

以下原始碼路徑均相對於工作複本的 `proto7-2/`。各項量測前後各三次；微測節省代表案例或 fixture 的工作量，**不能再加到整套平行節省的 125 秒上**。

| 改動與證據 | 實測節省 | 風險／界線 |
|---|---:|---|
| 每個測試檔獨立程序，最多四個 worker；保留原 suite、class/module fixture。`tests/run_all.py:100`、`tests/_parallel.py:139` | 同一 v1 候選程式的串行／平行中位數 **187.17 → 72.22 秒，省 114.95 秒** | 此項為非交錯分組觀察值，仍受主機負載影響；未來共享固定路徑或外部資源的測試可能互相干擾 |
| 依歷史檔案耗時排序。`tests/_parallel.py:80` | **未單獨歸因**；最終組合量測已包含 | 舊耗時可能失準；只影響排程，不影響收集項目 |
| 等 task 與 runner 都死亡，取代額外 0.1 秒 sleep。`tests/core/test_ctl.py:148` | **0.099 秒** | 必須同時確認兩者，不能只等 task |
| 補槽案例將 `sleep 0.2` 任務改為 `true`。`tests/core/test_tick_tock.py:136` | **0.205 秒** | 此案例驗補槽與重啟，不再提供偶然的長時間重疊執行 |
| 每個 run 使用 release marker，先確認第一次 tock 時仍存活，再放行。`tests/core/test_tick_tock.py:300` | **0.286 秒** | 增加一個測試同步機制；未放行的新一代仍需 cleanup |
| step pause 後等最後 tock 的處理完成。`packs/step/tests/test_step.py:314` | **0.215 秒** | 依賴框架提交順序；保留後續 1.5 秒不變性觀察 |
| adapt pause 後等 register 提交到暫停回合。`packs/adapt/tests/test_adapt_flow.py:319` | **0.281 秒** | 不能只看 daemon 已 paused |
| unknown 狀態後等 step 處理較新的 tock。`packs/adapt/tests/test_adapt_flow.py:392` | **0.209 秒** | 必須確保 step 真有機會讀取 unknown |
| budget pause 後等 completed_tock 關閉。`packs/budget/tests/test_budget_step.py:142` | **0.270 秒** | 保留暫停期間時鐘不變的觀察窗 |
| 用兩次依序回覆的重播請求確認 receipt sweep 完成。`packs/budget/tests/test_budget_ledger.py:459` | **0.934 秒** | 依賴 inbox 處理後才 sweep 的順序；仍核對帳本 seq 未增加 |
| 共用真 CLI 產生的不可變開帳範本，每個案例建立獨立 ledger 與 lock。`packs/budget/tests/budgetcase.py:60` | 實際 fixture setup **1.150 → 0.233 秒，省 0.917 秒** | 未來 init 若新增副作用或環境依賴，須重新檢查快取契約 |

八處等待／短任務改動合計約省 **2.500 秒**；fixture setup 另省約 **0.917 秒**。

Fixture 的實際兩個 budget 測試檔共有 37 項案例、49 次 setup：快取使 fixture CLI init 從 **49 次降至 9 次**，40 次命中；另有四次直接測 CLI init 的呼叫完整保留。前後各三輪皆 37/37 通過。可用 `AOS7_TEST_FIXTURE_CACHE=0` 停用快取。

證據與重現：

- `python3 evidence/core-waits-bench.py`
- `python3 evidence/pack-waits-bench.py --repeat 3`
- `python3 evidence/fixture-suite-profile.py --cache 0 1 --repeat 3`
- 完整逐项數值及風險：`evidence/change-attribution.json`

較早的完整串行量測曾差到 14.51 秒，但獨立小改動只支持約 3.42 秒的工作量節省；**其餘差距未歸因給程式改動**。最終主結論因此採交錯量測。

## 穩定性修補與保留的失敗證據

穩定性修補獨立放在 `stability.patch`，前後兩組共同使用，不列為加速收益。

| 發現 | 處理與證據 |
|---|---|
| shell fixture 多出程序，破壞「恰好一個任務」斷言 | 使用 `exec sleep`，短任務 marker 改用 shell builtin。`tests/core/test_ctl.py:134`、`tests/_matrix.py:136` |
| 恢復測試可能在預定 crash 發生前就開始判定 | 等 runner 真正死亡、任務完成或恢復狀態成立，保留原恢復回合與斷言。`tests/core/test_matrix_once.py:42`、`:73` |
| subd 將 run 誤當連號計數 | 改驗新 run 大於舊 run，且 owner 與新 birth 相符；run 採啟動回合數。`modules/subd/tests/test_subd_recover.py:128` |
| fast-source 把 20/200ms 設定當成實際吞吐保證 | 先確認來源真的發布至少兩個新回合／版本，再放目的端執行一回合；保留步差、skipped、狀態及 age 斷言。`packs/adapt/tests/test_adapt_flow.py:117` |
| subd 讀到舊 run 結束後，下一 run 已清空 out.log | 等非空日誌並斷言取得的同一份字串快照。`modules/subd/tests/test_subd_ownership.py:71` |
| runner 在 `/proc/stat` 與 `cmdline` 讀取之間死亡，被測試誤認為 task | 先等 runner 死亡再掃描，新增 `pid != runner` 斷言。`tests/core/test_matrix_faults.py:118` |

**fast-source 的範圍調整值得特別審閱**：它現在驗證「已建立來源快於取樣的前提時，adapt 正確漏取樣」，不再把自由運轉時的實際速度比例當成保證。這項調整沒有隱藏，且前後組完全一致。

失敗調查過程亦完整保留：

- 原始六個失敗案例各單獨重跑三次，原版共 **11/18 次失敗**；修正版 **18/18 通過**。腳本：`evidence/repeat_isolated.py`；結果：`evidence/isolated/`。
- v1 慢檔優先首輪曾有 fast-source、subd 日誌兩項失敗；後兩輪成功仍未視為穩定。原版與候選版單獨重跑共 **40/40 通過**。證據：`evidence/runs/optimized-prioritized-1-report.json`、`evidence/scheduling-isolated.py`。
- v2 十輪中有兩輪在 orphan `/proc` 案例失敗。單獨重跑原版與 v2 共 **40/40 通過**；可控制時序的真 runner 探針則確實重現舊順序誤選 runner，修正順序後通過。證據：`evidence/core-orphan-race-probe.py`、`evidence/core-orphan-race-probe.json`。
- 另保留兩個「副作用發生前就 crash」探針，覆蓋 once 不重試及 keep 回收後重啟，**2/2 通過**，不灌入正式 364 項。證據：`evidence/stability-pre-effect-probe.py:90`。
- 原始 flood timeout 案例保持不變，未放寬 timeout；單獨三次及最終驗收均通過。位置：`tests/core/test_daemon.py:293`。

## 驗收完整性與限制

全部歷史共跑 **47 次全套**，包含六輪有失敗的舊版紀錄。最終固定版本驗收確認：

- 每輪均為原始 **364 個唯一測試 ID**；沒有刪除、漏跑、重複、skip 或 xfail。
- 最終 19 輪的程式指紋符合各自固定版本，沒有混用修改前後檔案。
- 最終平行 worker 均正常退出；依每輪專用 token 掃描，未發現殘留程序，也未觸發正常測試結束後的保底清理。
- runner **39 項檢查**通過，涵蓋收集、fixture、失敗回報、worker 崩潰、timeout、無效排序資料及啟動期間的 SIGINT／SIGTERM。
- fixture **8 項隔離／快取檢查**通過。

證據：`evidence/runner-integration-audit.json`、`evidence/runner-check-results.json`、`evidence/v3-runner-probes-integrated/results.json`、`evidence/fixture-probe.log`。

驗證環境僅為 **Python 3.12.3、WSL2 Linux、8 CPU**，另測兩 CPU 限制。有限重複只能支持「本次未觀察到新增 flaky」，不能保證所有機器與負載。程序清理依賴 Linux `/proc` 與繼承的 token；父程序遭 SIGKILL 或子程序清空環境仍是限制。

目前平行瓶頸為 `test_subd_recover`，十輪單檔中位數約 **58.34 秒**。若仍維持每檔一個 worker，進一步提高 worker 數的收益有限。證據：`evidence/final-summary.json` 的 `parallel_module_median_s`。

## Patch 與重現方式

工作目錄：

```text
/tmp/claude-1000/-home-guanyu-projs-aos/8aa61430-d017-4079-b09f-02620d555dd9/scratchpad/burn/ws/fast-tests
```

交付檔案：

- `完整 patch`
- `共同穩定性修補`
- `加速改動 patch`
- `最終數據與驗證`
- `全部歷史量測 CSV`

完整 patch 可套至原始快照；亦可依序套用 stability、acceleration。兩種方式均已驗證與最終複本逐位元相同，並通過 `git apply --check`。證據：`evidence/patch-validation.json`、`evidence/audit-patch-split.json`。

在上述工作目錄執行加速版：

```sh
python3 proto7-2/tests/run_all.py -v -j 4 \
  --durations evidence/runs/stable-serial-1-report.json \
  --json-report evidence/reproduce.json
```

`-j` 預設仍為 1；不提供 `--durations` 也可平行執行。所有逐輪命令、時間、負載、退出碼與失敗內容均保存在 `evidence/runs/`。