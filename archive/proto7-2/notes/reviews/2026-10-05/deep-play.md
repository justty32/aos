**已確認兩個同族的 daemon 回收缺陷與一個任務包暫存檔清理缺口；長跑及一小時 chaos 因本次立即收尾指示中止驗收，不能宣稱已達成 2000 回合或一小時門檻。**

# proto7-2 長跑與壓力測試報告

## 範圍與完成狀態

所有測試、腳本與證據均使用指定工作複本；沒有修改 `/home/guanyu/projs/aos`，沒有 commit 或 push，也沒有修補產品程式碼。

以下路徑以工作目錄為基準：

```text
/tmp/claude-1000/-home-guanyu-projs-aos/8aa61430-d017-4079-b09f-02620d555dd9/scratchpad/burn/ws/deep-play
```

環境為 Python 3.12.3、Linux／WSL2、8 個邏輯 CPU。環境與起始原始碼雜湊分別存於：

- `evidence/run_context.json`
- `evidence/source_manifest_initial.json`

**收尾限制：**收到指示後未再呼叫工具、執行程式或開啟 subagent。因此沒有執行背景壓測的停止及最後清理；長跑、chaos 與既有重跑程序**可能仍在執行**。以下採用最後已確認的檢查點，不把它們當作最終停機結果。

## 壓測數字

| 項目 | 最後已確認結果 | 判定 |
|---|---|---|
| 既有全套測試 | 364 項；357 通過、7 失敗；1156.296 秒 | 已完成初測，重跑結果尚未全數收齊 |
| 長跑第一階段 | 20 node、80 個常駐任務；每 node 最少 153、中位數 163 回合；合計 3263 回合 | 正常停止，退出碼 0，該階段殘留掃描為空 |
| 長跑第二階段 | 20 node、32 個常駐任務；累計每 node 最少 367、中位數 390.5；合計 7832 回合 | **尚未達每 node 2000 回合** |
| 第二階段最近吞吐 | 約 301.6 秒內，最慢 node 前進 165 回合，約 0.547 回合／秒 | 仍在量測，非最終穩定性結論 |
| 第二階段資源快照 | daemon RSS 17.98 MiB；程序集合 RSS 約 1016.7 MiB；76 個程序；fd 合計 325；觀察到殭屍 0 | 單次快照，不能代替長期趨勢 |
| 第二階段檔案快照 | 核心 329 檔／79,861 bytes；budget 724 檔／542,641 bytes | 已分開核心與帳務保存資料 |
| Chaos | 最後確認已執行約 819 秒；20 node 回合數 73–102 | **尚未達一小時** |
| Chaos 已命中 SIGKILL | 任務 12、daemon 4、tick 9、tock 8 | 有程序身分與命中紀錄 |
| Chaos 工作量 | 1268 次實際任務入口；387 筆 budget 操作，該檢查點 inflight＝0 | 尚未做最終核帳與停機驗收 |
| Step 定向中斷 | 9／9 通過 | 已完成 |
| Budget 九個持久點 × 三次 | 27／27 通過 | 已完成 |

證據：`evidence/baseline/baseline.meta.json`、`baseline.stderr.log`；`evidence/longrun/run-main/`、`evidence/longrun/report.md`；`evidence/chaos/run-01/observations/`、`latest.json`；`evidence/pack_edges/checkpoints-20261005T013934/summary.json`。

長跑最初每 node 都放四個常駐任務，同機 CPU 競爭嚴重，整機 load 曾超過 200。本線也構成負載來源，不能全部歸因於其他線。第一階段先降低排程優先權，後來正常停機、調整為 32 個常駐任務，再以同一空間接續回合；仍保留 sensor→adapt、step→budget 的實際互動。**兩階段不是同一個 daemon 連續跑到終點的證據。**

第一階段曾觀察到回合週期約 p50＝2.31 秒、p95＝4.56 秒，但這是負载變動中的局部統計；完整 p99、最大值及分時比較尚未完成。

## 已確認發現

分類：**M**＝誤用、**X**＝外部故障、**B**＝組件 bug、**G**＝契約缺口。SIGKILL 是注入條件；以下分類依恢復後是否履行契約判定。

### C8-01〔B／高〕取消登記後 daemon 被殺，回收義務永久遺失

**結果：**`unregister` 已接受且預設要求收任務，但 daemon 在回收期間被殺後，舊任務仍存活。重啟 daemon、重送 unregister、最後正常 `stop --kill`，都收不到它。

最小情境只有一個 node、一個 keep 任務。任務忽略 SIGTERM，但保留正常身分，應由一秒寬限後的 SIGKILL 回收。探針等 unregister 成功回條後，在寬限內殺 daemon，沒有修改產品，也沒有使用測試鉤子。

- 原始中斷組 **3／3 漏收**；正常對照 **0／3**。
- 補充觀測組再確認中斷 **1／1 漏收**、正常 **0／1**。
- 原始三組已由獨立檢查器重核 PID、starttime 與非殭屍狀態。
- 各重現案先保存漏收證據，再由測試工具收走；案內 `cleanup.json` 為空。

**原因：**

`proto7-2/lib/aos7_daemon.py:197` 先從 registry 移除 node，`:198` 寫回；後續 retire／回收工作只存在記憶體（`:203`、`:205`）。重啟不會恢復這筆工作；未登記 node 的 unregister 直接返回，最後停止掃描也只包含目前登記的 node。

這違反 `proto7-2/spec.md:62` 的 unregister 收任務語意，以及 `:14` 對中斷後靠證據恢復的要求。回條只代表接受，並不代表完成；本案的問題是**重開後再也沒有組件履行已接受的回收**。

**證據與重現：**

```sh
python3 evidence/repro_unregister.py --repetitions 3
```

- `evidence/repro_unregister/20261005T093634/summary.json`
- 同目錄各 `crash-*/result.json`、`control-*/result.json`
- `evidence/repro_unregister/20261005T095358/`
- `evidence/checker/unregister-review/report.json`

### C8-02〔B／高〕node 替換後中斷回收，新舊任務同時存活

**結果：**node 目錄替換後，舊 daemon 已辨識變更並開始回收；若此時被殺，新 daemon 會啟動新目錄的任務，原任務卻仍存活。

探針先等任務確實 ready、時間線進入 running，才搬移目錄，因此不是規格排除的「起任務途中搬 node」。

- 原始中斷組 **3／3 重現**；正常對照 **0／3**。
- 三個中斷案各有 **30／30 快照**確認新舊工作程序同時存活，觀測跨度為 **8.21–8.98 秒**。
- 補強組保存 `/proc/stat` 原文及 `AOS7_*` 環境，再得到中斷 **30／30 雙活**、正常對照 0。
- 舊新都是 `keeper#1`，但 PID、starttime、node inode 不同；沒有把 runner wrapper 誤算成第二份任務。
- 本案最後正常 `stop --kill` 能收掉兩份，與 C8-01 的永久失管不同。

**原因：**

`proto7-2/lib/aos7_daemon.py:418` 辨識 inode 更換，`:428` 啟動回收；同一代會在 `:434` 等 reaper 完成，才於 `:441` 建立新時間線。但是 reaper、missing 狀態與 `proto7-2/lib/aos7_daemon_timeline.py:84` 的 node inode 身分都只存在記憶體。重啟後等待屏障消失。

直接契約依據是 `proto7-2/spec.md:94` 的 inode 更換須收舊任務，以及 `:96` 的「搬家＝舊 id 的任務全死」。

**證據與重現：**

```sh
python3 evidence/repro_replace.py --repetitions 3
```

- `evidence/repro_replace/20261005T094654/summary.json`
- 同目錄各案 `result.json`
- `evidence/repro_replace/20261005T095214/`：補強原始程序身分
- `evidence/checker/replace-review/`
- `evidence/checker/replace-env-review/`

**C8-01、C8-02 是同一缺陷族：node 回收義務只存在 daemon 記憶體。**分開編號是為了固定不同觸發與驗收案例，不代表兩個無關根因。只補 unregister 的恢復，仍不足以涵蓋已辨識的 node 替換。

### C8-03〔G／中〕任務包槽外暫存檔缺少回收責任

同一個 job、sense 或 budget K 不變，反覆在原子寫 rename 前 SIGKILL writer，每個死 PID 都會留下新的暫存檔。成功恢復不會清掉它們。

| 位置 | 每組注入 | 三次獨立結果 |
|---|---:|---|
| `jobs/demo/.frame.json.tmp.<pid>` | 6 次 | 每組 1→6；正常續跑、close 後仍 6 |
| `in/.temp.json.tmp.<pid>` | 6 次 | 每組 1→6；正式暫存器恢復後仍 6 |
| `budget/demo/gateway/.<kid>.json.tmp.<pid>` | 6 次 | 每組 1→6；同 K 結算、重播及 ledger 重啟後仍 6 |

這些是產品 writer 真正生成的 tmp，並非人工建立假檔；也不是新 K 的帳務歷史。

**分類保留 G：**核心規格明確只清自己的 `.aos/`、槽與 `.aosd/`，三個包沒有明文承諾上述槽外暫存檔的回收期限。因此不能直接判成核心違約 B；但「同一工作反覆中斷，檔數仍不長」的目標目前沒有組件負責。

來源包括：

- `proto7-2/lib/aos7_fs.py:119`、`:129`、`:130`：原子寫及 rename 前窗口。
- `proto7-2/packs/step/aos7_step.py:306`、`:689`：框架保存與 close。
- `proto7-2/packs/adapt/aos7_adapt.py:421`、`:461`：暫存器與框架寫入。
- `proto7-2/packs/budget/aos7_budget_gate.py:96`；`aos7_budget.py:366`：入口寫入與未涵蓋 gateway 的啟動清理。

**證據與最小重現：**

```sh
python3 -B evidence/pack_edges/repro_step_tmp.py
```

- `evidence/pack_edges/repro_step_tmp.json`：三次中斷留下 1、2、3 檔，恢復及 close 後仍為 3。
- `evidence/pack_edges/run-20261005T013739/summary.json`
- `evidence/pack_edges/report.md`

## 已完成的核帳與檢查器工作

獨立檢查器使用標準庫，沒有 import 產品的核帳或程序判定函式。已建立逐筆帳本重建、同 K reserve／settle 唯一性、gateway 證據、backend 效果及歷史不可倒退等檢查。

已完成：

- 15 個檢查器自測，包括故意破壞帳、重複轉移、歷史倒退、程序雙活及核心檔案增加。
- CLI 正例退出碼 0、四個破壞樣本退出碼 1。
- C8-01、C8-02 的獨立正證據複核。
- 長跑 pilot 與部分 chaos 資料的檢查；當時未發現額外不變量破壞。

證據：`evidence/checker/check.py`、`evidence/checker/mutations/results.json`、上述兩項缺陷的 review 目錄。

**限制：**部分 `/proc` 全域掃描有非本次程序的讀取錯誤；週期快照也有觀測間隙。因此「目前未看到雙開」不能當作完整證明。最終停機後的漏收檢查、完整長跑／chaos 核帳及檔案趨勢驗收尚未完成。

Budget 正式歷史則確實會成長，這是規格允許的保存成本。定向測試從 1 個 K 增至 12 個 K：

| 指標 | 1 個 K | 12 個 K |
|---|---:|---:|
| 預算目錄正式檔數 | 7 | 29 |
| ledger bytes | 1,411 | 13,902 |
| backend bytes | 292 | 3,114 |
| available／inflight／used | 99／0／1 | 88／0／12 |

每新增 K 增加兩個 gateway 正式檔，帳平持續成立。這不能與 C8-03 的同 K 死 writer tmp 混算。證據：`evidence/pack_edges/report.md`、`run-20261005T013739/summary.json`；保存契約見 `proto7-2/packs/budget/spec.md` §9、§10。

## 全套失敗與重跑：目前能下的結論

初測七項失敗均保留，沒有改測試來取得綠燈。

| 初測失敗 | 最後已確認重跑／分析 |
|---|---|
| `test_old_run_leftover_not_taken_as_new_run` | 單例 3／3 仍失敗；額外觀測證明多出的 PID 是合法的 dash 子程序 `sleep`，兩者均為 run 2。是測試只允許單 PID 的假設，非舊 run 混入 |
| `test_keep_runner_before_pid` | 單例 3／3 通過 |
| `test_once_after_popen` | 單例 3／3 通過 |
| `test_reaped_before_new_daemon` | 已知前兩次重跑仍在「新 run 必須恰為舊 run＋1」失敗；較前面的舊程序回收斷言已通過 |
| `test_fast_source` | 重跑最終結果未收齊 |
| `test_slow_source` | 重跑最終結果未收齊 |
| `test_backup_end_to_end` | 重跑最終結果未收齊 |

兩個重要的測試假設：

1. `proto7-2/tests/core/test_ctl.py:146` 要求程序清單只有主 PID，但 `aos7_proc.env_procs` 本來就回傳所有符合身分的程序。原始程序證據在 `evidence/baseline/shell-test-observation.json`；觀測腳本為 `observe_shell_test.py`，未修改測試及函式返回值。
2. `proto7-2/modules/subd/tests/test_subd_recover.py:135` 要求 run 恰加一，但 `proto7-2/spec.md:209` 明定 run 取啟動回合數，必要時才用上一個加一。因此 run＝4／5 本身不能證明重啟多次或漏收；當時新 owner 與新 birth 的完整對照尚未另行採集。

其他失敗涉及固定等待與取樣速度；同機高負載下不能直接判為產品 B。完整初測與目前重跑證據在 `evidence/baseline/`，尤其 `baseline.stderr.log`、`reruns.json`。

## 做到一半、尚未驗完

- **20-node 長跑：**尚未達每 node 2000 回合；已換過配置及 daemon 世代。完整延遲分布、RSS／fd／殭屍與檔數分時趨勢未結算。
- **一小時 chaos：**最後確認僅約 819 秒，不能宣稱一小時完成；最終各類隨機操作次數尚未統計。
- **四項不變量的完整驗收：**已有局部檢查與明確反例，尚無整段長跑／chaos 的最終獨立驗收。
- **基線失敗重跑：**既有腳本已啟動，但 21 次單例重跑的完整結果尚未收齊。
- **檢查器交叉審查：**已安排純讀碼審查，最終審查結果尚未收到。

## 沒來得及做

- 壓測最終正常停機、所有本線背景程序的完整殘留確認。
- 長跑結束後的原始碼雜湊比對與全證據索引封存。
- 在長跑及 chaos 停機、較低負載下，再確認仍有疑義的時間敏感測試。
- 針對 C8-01／02 實作持久回收意圖並驗證修補；針對 C8-03 接上槽外暫存回收。此次只調查及重現，沒有產品修補。

已完成的缺陷整理另存於 `evidence/findings.md`；探針自身曾遇到的短暫 phase 取樣及非原子 ready 檔問題，記於 `evidence/probe_notes.json`，均未算作產品缺陷。