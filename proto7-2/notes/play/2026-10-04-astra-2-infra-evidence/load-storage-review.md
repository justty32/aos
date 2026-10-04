# 儲存／history 回歸與負載分工紀錄

## 舊項回歸

| 舊項 | 判定 | 本輪證據 |
|---|---|---|
| A2-07 | 原重現已修；故障類別仍有遺漏 | 原 `storage-crashes.py` 除輸出名外原樣重跑：20 次不同 PID 於 last-round rename 前 SIGKILL，20 次 rc=-9；每次下次 tock 先 sweep，因此最後僅剩最後一次的 1 個 tmp；健康恢復＋10 回合後 0。新增巢狀 mount 基礎設施路徑仍漏清，見下。 |
| A2-09 | 規格層已修；kernel 尚不存在，不能稱實作已驗證 | 原 `design_probes()` 真刪槽與重建仍得到 run 1/usage100、run 3/usage150。舊規則合計150的反例不變；新 §8 按 job#1、job#3 各取最大再相加=250，並明說已觀測下界、精確 cap 交合作式任務。`usage-spec-review.json` 分開記錄舊反例與新規則算術。 |
| A2-10 | 已修 | 原 `design_probes()` 的 max_lines=3、10 筆 node 與 daemon 事件，現在兩份都3行。 |
| A2-12 | 已修 | 舊 slots-extra 的真 history 任務＋last-round 寫前延後200ms，僅把舊探針 `tock.json['round']` 改成 nullable（因為修好後那時檔案尚不存在）。r1發布前無通知，r2發布前通知仍r1，最終history有r1、r2。另 `history-replay.py` 真 SIGKILL 在總結已提交而通知未寫時，重播補通知，history收到r1，回合close。 |

完整可重跑證據：`storage-crashes-rerun.py/json`、`slots-design-rerun.py/json`、`slots-extra-rerun.py/json`、`history-replay.py/json`、`usage-spec-review.json`。

## 矩陣審查（本分工範圍）

- `test_matrix_misc.TestTmp` 預置死 PID／活 PID 檔，以及 `tmp:last-round.json` 連殺；後者 test_point 在 JSON 寫完、關檔後、`os.replace` 前，等同真 crash 窗口。本輪舊腳本攔真 `os.replace` 再 SIGKILL，結果一致。
- 掃描範圍只驗 `.aos/` 與槽頂層；daemon 測 `.aosd/`、ctl。沒有驗 `mount-req/`、`mount-done/`。這是「測試綠，但其他同類真故障仍漏」的具體反例。
- history max-lines 測到了兩份輸出上限，舊實測一致。無需把取樣本來會漏、首次從r100開始沒有1～99 gap，誤稱本次修復失敗。
- A2-12 矩陣只 mock 記錄 write_json 呼叫順序，不能直接證明真讀者在commit之前沒有醒；本輪保留真 module＋延後提交驗證，並加上「提交完成→SIGKILL→重播通知」組合，均通過。
- A2-09 沒有 kernel，矩陣再多也不能證明精確額度累計。新規格以採樣下界換掉舊錯誤模型，應讓將來 kernel 的契約測試直接驗 run key 和已觀測總數。

## 新問題候選：巢狀掛載基礎設施暫存檔漏清

〔bug，中〕`sweep_tmp` 本身只處理指定目錄；tick/tock 呼叫 `.aos/` 與槽頂層，未涵蓋 `mount-req/`、`mount-done/`。但 `aos7_mount.request`、`serve` 都在這兩處使用同一 `write_json` 產生帶寫者 PID 的 dot tmp。掛載請求長期由 keep 任務使用，因此不能假設下一回合一定換 run 清掉。

`storage-nested-crashes.py` 建立真 keep sleep 任務，在 mount-done 回條的真 `os.replace` 前連殺5個tick（每次用tock關掉中斷回合），再在官方 `aos7_mount.request` 的 `os.replace` 前連殺5個寫者。全部rc=-9，留下10個dot tmp。請求能正常接受、同run=1健康再跑10回合，10個仍全部存在。證據 `storage-nested-crashes.json`。

建議只把兩個已知基礎設施子目錄納入死寫者sweep；不要通用遞迴清理任務自有資料。這是原A2-07修復範圍遺漏，尚不影響執行身分／冪等核心。

## 新問題候選：重播收尾吞掉通知寫入錯誤

〔bug，低至中〕`notify-replay-error.py/json` 用真目錄佔住 keep 槽的 `tock.json`，讓 `os.replace` 產生 EISDIR。正常收尾會將失敗寫入 `round.json.notify_errors`；相同故障在 `tock-summary` 真SIGKILL後重播，`aos7_tock._replayed` 捕捉OSError直接pass，最後照常關回合，`notify_errors` 不存在、summary.errors也空。既已接受通知失敗可關回合，不必改成整node卡死；至少兩條收尾路徑應提供一致錯誤證據。它是可觀測性邊角，優先度低於身分與重播的執行正確性。

## 長跑方法

`load-probe.py` 使用真daemon、真每回合tick/tock程序、真檔案。先以nodes/paused檔設置初始登記及pause，透過正式ctl/請求逐node resume --rounds；每個checkpoint等待所有node暫停，才量檔數/bytes，避免將瞬時原子tmp當洩漏。每200ms讀status，保存uncertain樣本及原因計數，checkpoint再讀last-round errors和tasks_error。

CPU來自daemon `/proc/<pid>/stat` 的utime+stime及cutime+cstime；後者包含已wait的tick/tock程序。未被daemon wait的runner與任務不完整納入，所以含任務數字是CPU下界，不宣稱整棵程序樹成本。200ms輪詢與status更新週期也意味「未觀察到」不能證明短暫狀態從未出現。延遲是checkpoint各node完成等待及抽樣最後一回合tick_at→tock_at，不是每回合完整p99。

短跑校準：50×100空任務約35.7秒、固定456檔；10×100（每node sleep keep＋true each，n00另history max-lines25）9.271秒、固定183檔。含任務看到兩次同一run的「剛起」uncertain，之後正常前進，沒有last_error，history末筆100；這是正常spawn交接期可見的暫態，不應當成需要人工的卡死。

正式長跑結果見 `load-long-empty.json`、`load-long-tasks.json`（50×1000空任務；10×1000含任務）。所有腳本使用副本evidence內 TemporaryDirectory；程序先以所屬PID/PGID收尾，再刪自己的暫存根，各結果有cleanup欄。

| 正式工作量（16 logical CPU） | wall 秒 | CPU 秒（daemon＋已wait子程序） | 檔案／容量（r10→r1000） | 最末 checkpoint round tick→tock 延遲 |
|---|---:|---:|---|---|
| 50 node×1000、空任務；50000 node-round | 330.520 | 72.06＋4844.80＝4916.86 | 固定456檔；79709→80109 bytes | min31ms、median104ms、max198ms |
| 10 node×1000、keep sleep＋each true；n00另history；10000 node-round | 83.242 | 10.30＋786.10＝796.40（runner CPU未完整包含） | 固定183檔；32843→39975 bytes | min30ms、median34.5ms、max43ms |

空任務每回合約0.0983 CPU秒，總吞吐約151.28 node-round/s；這揭露每回合兩個Python程序的固定成本，不能用本機16核結果推估單核也能維持同吞吐。含任務history在r10只有10筆，到25筆保留上限後仍有事件歷史逐步填滿及數字位數增加，所以bytes不宣稱常數；檔數與dot tmp確實穩定。

空任務1643次status輪詢皆無uncertain；含任務417次輪詢中累計42筆槽觀測是 `why=剛起`（包含重複讀到同一status，並非42個不同故障），沒有其他原因，沒有last_error。每個checkpoint的summary.errors和tasks_error皆空，最後每node keep run=1、each run=1000，沒有停止進度。history留25筆、最後round1000、保留範圍內gap0；這不能倒推已被trim的全部歷史都無漏取樣。

`load-storage-cleanup.json` 核對4個負載暫存根全部移除、相符AOS7_ROOT程序0、evidence內aos72-test-/storage-work-目錄0。未在副本外建立/tmp資料夾。
