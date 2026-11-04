# 六 agent 長跑證據

重跑：`python3 proto7-1/notes/play/2026-10-03-astra-3-evidence/longrun/reproduce.py`。只用內建 fake；不會發 HTTP。

## 方法

6 個 keep agent 分成 3 組持續 ping，`max_ping=1000000`、`memory=12`，另 1 個 keep kernel；7 條時間線全部 `interval_ms=180`。kernel 的速率與總額上限均設 10¹²，避免本次基準測試被 pause。`AOS7_AUDIT` 關閉。daemon wrapper 只在原本 `run_prog` 前後讀 `perf_counter()`，tick／tock 仍逐次呼叫真正的獨立程序；計時檔位於空間外，不計入資料夾成長。未修改產品程式。

每 2 秒讀 `/proc/<daemon-pid>/status`；達指定最小回合時，以 `os.walk(followlinks=False)` 加總普通檔大小及 `st_blocks × 512`。不計符號連結，配置 bytes 只加普通檔、不含目錄，因此不等同 `du` 整棵精確數字。採樣期間系統仍運行，檔案數與回合有不到一輪的時間差。

## 結果

65.485 秒完成；各 agent 處理 362–363 次 tock，沒有合併掉的 agent tock，705 次假 LLM 呼叫、702 次寄信、699 封已處理信，7 個任務都沒有 restart。5070 次 tick／tock 程序呼叫全部退出碼 0。結束寫 stop+kill 控制檔，最終所有 node `phase=stopped`、`live=[]`，daemon 退出碼 0，6 個 agent 退出碼均 0。

| 最小回合 | 秒數 | 普通檔數 | logical bytes | 配置 bytes（普通檔） | daemon RSS KiB |
|---:|---:|---:|---:|---:|---:|
| 10 | 1.766 | 197 | 64907 | 819200 | 20524 |
| 60 | 10.761 | 638 | 280429 | 2732032 | 20628 |
| 120 | 21.689 | 1172 | 541829 | 5099520 | 20644 |
| 180 | 32.623 | 1718 | 810812 | 7512064 | 20644 |
| 240 | 43.406 | 2255 | 1076647 | 9904128 | 20652 |
| 300 | 54.268 | 2798 | 1344436 | 12283904 | 20660 |
| 360 | 64.973 | 3332 | 1608584 | 14635008 | 20688 |

| 視窗（各節點的回合） | tick 中位／P95 ms | tock 中位／P95 ms |
|---|---:|---:|
| 11–60（各 350 樣本） | 19.688／31.393 | 19.042／27.109 |
| 156–205（各 350 樣本） | 20.758／32.299 | 19.406／29.647 |
| 311–360（各 350 樣本） | 19.052／34.131 | 18.815／31.027 |

本次範圍看不出 tick／tock 中位耗時隨回合單調變慢；晚期 P95 高一些，單次同機量測不足以歸因於檔案成長。第 10→360 回合，RSS 20,524→20,688 KiB（+164 KiB），峰值 VmHWM 20,948 KiB，未見線性洩漏。程序剛 spawn 時的第一筆 RSS 僅 232 KiB，屬載入前，不拿來當穩態起點。

普通檔數 60→360 回合增加 2,694 個，logical bytes 增加 1,328,155；各 node 前進一回合（整組 7 輪）平均增加約 8.98 檔／4,427 bytes，配置普通檔增加約 39,677 bytes。最終收尾後 3,357 檔、1,618,676 logical bytes、14,741,504 配置 bytes。主要內容 bytes 為 daemon log 593,919、rounds 463,541、trace 170,753、out.log 166,462、sent 118,113；小檔配置成本高。

資料夾只增不減已記在 P-12／R-10，本輪只補測量，不當新問題。這是 6 個常駐 agent、每 node 只有 1 個 task 的 360 回合工作負載；不能推論高 restart／`mode=each` 累積大量 task 的效能，也不能推論真模型或開 audit 的空間與延遲。fake 後端不生成 llm.jsonl，本次量的是 trace／sent 等成本。

## 證據與清理

`result.json` 包含設定、7 次磁碟採樣、每 2 秒 RSS、最終 status／agent state／usage／exit，以及統計。`timing-00.jsonl` 至 `timing-03.jsonl` 是全部 5070 筆原始計時，每檔小於 150 KB。`reproduce.py` 可重跑並覆寫這些結果。

原實驗 `/tmp/astra3-long-ukaf2whx` 已刪除，結束時所有任務都已退出。
