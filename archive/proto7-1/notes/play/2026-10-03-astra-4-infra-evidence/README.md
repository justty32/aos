# astra-4 基礎設施證據

主報告：[2026-10-03-astra-4-infra.md](../2026-10-03-astra-4-infra.md)。所有實驗只用自寫離線探針，沒有 kernel／agent、real.py 或模型端點。各組 fragment 是整理素材；分類與需求以合併主報告為準。

| 目錄 | 可重現腳本 | 證據內容 |
|---|---|---|
| scale | scale_probe.py、analyze.py | 10/50/100/200 條、100 ms、每輪三個 10 ms 任務；10 條重跑及 200 空任務兩次對照；原始 monotonic 計時切片、OS 採樣、分析 |
| tasks | probe.py | 14 個有界任務型態案例；before_stop／after_stop 檔案視角與獨立 OS 存活觀察；摘要、清理 |
| time | probe.py | interval、型別錯誤、修改設定、SIGSTOP 遲到、模擬牆鐘、提前 tock；單調計時及產品 log |
| crash | probe.py、sitecustomize.py | 七個精準 SIGKILL／I/O 故障；at_fault、final_files 等保存原檔文字，fault-marker 與 stderr 為探針額外收證 |
| nested | reproduce.py | 三層 TERM／KILL、路二原生反向掛載被拒、明示 re-export 後互 pause 成環與外部 resume |
| readability | snapshot-A/B/C.json、file-only-review.md | 從 tasks before_stop 擷取的三份檔案快照；未讀 OS 真相的另一 subagent 判讀，provenance 記擷取來源 |

在 workspace 根執行；重跑會覆寫各組相應證據，保留本次數據時請先複製本目錄。

```sh
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/tasks/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/tasks/probe.py deletekeep tockdirpeer
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/time/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/crash/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/nested/reproduce.py
```

規模組應等其他探針結束後單獨執行：

```sh
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 10 50 100 200
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 10 --tag=-repeat
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 10 --counts 200 --tasks 0 --tag=-empty
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 200 --tasks 0 --tag=-empty-confirm
python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/scale/analyze.py
```

規模主表採 summary-10-repeat 與 summary-50/100/200；raw timing 分片小於 180,000 bytes。分析以 tick 完成間隔為 S-08 回合間隔；另保留起點間隔。`shutdown_and_analysis_wall_s` 包含離線整理，不能當純停機時間；CPU 粗略等效核的分母也包含這段。最初版本沒有保存精確啟動 epoch，其近似值由第一筆 monotonic 採樣換算；first_status／initial_tick 延遲晚於 Popen 起點，屬下界。各次 empty 對照有明顯變異，沒有把它們合成穩定容量門檻。

tasks 快照將可解析 JSON 解碼成物件；不可解析者可能記 null，原操作可從 probe 重現。out.log 只留 bytes，沒有複製 8 MiB 輸出。crash 的原檔快照則保留文字，包括 tmp、未完成資料。readability 快照循序採集，不具跨檔原子性；也含任務自寫證詞，不能假定產品會代寫它們。

時間探針以 Python datetime 注入偏移，沒有變更 host 時鐘。`clock-permission.json` 記錄非 root、CAP_SYS_TIME 不存在。ENOSPC 僅在 status rename 注入 errno 28；唯讀案是真實 chmod 0555。沒有滿碟、斷電或 fsync 測試。

probe 以 Linux subreaper 接住自己的孤兒方便清理，產品 daemon 沒有因此取得 subreaper 行為。清理先記錄產品停機後仍活的程序，再額外 kill／wait；結果不混淆。`final-check.json` 是主線最終核對；`source-manifest.json` 記本輪產品與規格檔 SHA-256，供重跑辨別版本。所有實驗空間使用 `/tmp/astra4-*`，不保留程序或工作空間。
