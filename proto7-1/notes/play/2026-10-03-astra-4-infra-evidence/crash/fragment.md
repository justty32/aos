# 崩潰與 I/O：可併入主報告的片段

## 方法與界線

先讀 `proto7-1/README.md`、`spec.md`，再沿入口讀核心 spec、known problems 與三輪 play。沒有 kernel、agent、real.py 或 LLM。重現指令：`python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/crash/probe.py`。

七案都是一條 200 ms 時間線。`sitecustomize.py` 只在指定程序、指定 `os.remove`／`os.replace` 次數前後 `SIGSTOP`，控制器再 `SIGKILL`；這是精準放大真實 crash window，不是隨機壓測，也沒有修改產品。重開的 daemon 不帶 hook。唯讀案直接以 uid 1000 `chmod .aosd 0555`；ENOSPC 案只模擬 status rename 遇到 errno 28，未填滿實體磁碟／未測斷電持久性。每份 JSON 的 `at_fault`、`before_*`、`after_*`、`final_files` 是原檔文字快照；`fault-marker.json` 與 `*.stderr` 是探針補的證據，不是產品本來會提供的檔。

全七案 `cleanup.remaining_children=[]`、`root_exists=false`。探針以 subreaper 收回強殺造成的孤兒，實驗空間 `/tmp/astra4-crash-*` 全刪除。證據每檔 < 10 KB（腳本亦 < 10 KB）。

## 數字與結果

| 故障窗口 | SIGKILL 對象／I/O 故障 | 重開後的觀察 | 證據 |
|---|---|---|---|
| tick 刪除 spawn，尚未 start_task | tick | 跑到 round 5；零 birth、零任務、零請求回條，請求永久消失 | `spawn-loss.json` |
| tock 已寫 ended，尚未寫 summary | tock | ended 指 round 1；summary 僅 round 2、3 且 ended 均空 | `ended-loss.json` |
| runner exit 暫存已完成，尚未 rename | aos7-run | 暫存 code 23；正式 exit 為 code null/lost true | `runner-exit.json` |
| tick 最後一次 round rename 前 | daemon；舊 tick 存活 | 新 daemon 完成 round 2；舊 tick 恢復後 round 倒退成 1/open true，status 留 2 | `stale-tick.json` |
| tock 最後 round rename 前 | daemon；舊 tock 存活 | 新 daemon 完成 round 2；舊 tock 恢復後 round 倒退成 1/open false，status 留 2 | `stale-tock.json` |
| 執行中將 `.aosd` 改 0555 | 真實 EACCES | daemon exit 1；sleep 任務仍活；恢復寫權、重開後能接管並以 TERM 收掉 | `readonly.json` |
| daemon status rename | 注入 ENOSPC | daemon exit 1；沒有產品 error／stop 紀錄；重開後可繼續 | `enospc.json` |

## 新問題

### C1. 舊 tick／tock 在新 daemon 啟動後仍有寫入權，回合會倒退〔bug〕

**重現：** 在第一回合 tick 最後一次 `round.json` rename 前停住 tick；kill -9 daemon；同 root 重開 daemon，讓它完成 round 2，寫 pause 等 status 顯示 paused；恢復舊 tick。另一案改在 tock 最後一次 round rename 前停住，做相同步驟。

**觀察：** 同 root flock 確實只容許一個 daemon，但不攔舊 daemon 留下的動作程序。兩案 `round.json` 均由 2 倒退 1，新的 status 繼續顯示 round 2；tick 案还把已關的回合改成 open。tock 案 rounds.jsonl 明確有 round 1、2，但 round.json 回到 1。這不是已知 P-08 的缺號：是舊執行者覆蓋新執行者已提交的狀態。若再恢復執行，`tick` 依磁碟 +1 的設計會再使用較小回合數；本案直接實測到倒退與三份檔不一致，未把後續重複回合當作已測數據。

**牽涉：** S-03、S-06、S-08、S-01。最小要求是新 daemon 接手後，上一代動作不能再提交；核心沒有規定 epoch／鎖的方案。證據 `stale-tick.json`、`stale-tock.json` 的前後快照。

### C2. spawn 請求先刪後生任務，tick 崩潰會無痕吞工作〔bug〕

**重現：** 寫 `.aos/spawn/once.json`，內容 `{"name":"once","argv":["/bin/true"]}`；在 tick 的 `os.remove(spawn/once.json)` 返回後停住並 kill -9 tick；等 daemon 到 round 3，再 kill/restart daemon，跑到 round 5。

**觀察：** daemon log 有 tick rc -9，接著回合均正常；但 once 請求、birth、任務與請求回條全無，五個 summary 的 started 都空。重新讀檔能知道某次 tick 被殺，不能知道丟掉哪個工作或重送什麼。細部 spec 寫「起完就刪掉」，實作先刪再啟動，故屬 bug；避免重送重複執行的方法另屬技術選型。

**牽涉：** S-01、S-06、S-09、S-10；細部 spec §4。證據 `spawn-loss.json`。

### C3. tock 的 ended 標記先提交，crash 令結束事件永久不進任何回合摘要〔bug〕

**重現：** tick 起 `/bin/true`，等 exit.json code 0；執行 tock，在 ended.json rename 成功後停住並 kill -9 tock；清空 tasks 表避免新任務混淆，起 daemon 跑到 round 3。

**觀察：** 任務 ended.json 宣稱 round 1 已記結束，但 round 1 摘要不存在；round 2、3 的 ended 都空。後來的 tock 看到 ended.json 便永久略過它。任務的 exit 原檔還在，所以全盤掃描可找回 code 0；只讀回合摘要的人會漏掉這次結束。不同於已知 P-08 的回合缺席，這次 `ended` 的消費標記已落盤，修補回合／重新執行 tock 也不會自然補回事件。

**牽涉：** S-01、S-06、S-08；細部 spec §3、§7。證據 `ended-loss.json`。

### C4. 單次 status 寫入故障使整個 daemon 直接退出，任務繼續且產品檔不記故障〔bug〕

**重現：** daemon 起 keep `/bin/sleep 30`，等 pid.json 後 `chmod .aosd 0555`；等待 daemon 結束。另一案在 daemon status rename 單次注入 `OSError(28)`。

**觀察：** 兩案 daemon 都 exit 1；唯讀案 task_alive_after_failure=true。產品 log 沒有 error、stopping、stop；唯讀案原有 log.jsonl 檔仍可 append（0555 只撤目錄寫入權），所以不是完全無法記錄。錯誤僅在探針自行接走的 daemon stderr traceback。恢復 0755、重开 daemon 後，原任務可被接上與 TERM 結束。這不是重報 P-04 的強殺孤兒／舊 status，而是一般可捕捉 I/O 例外也走無清理退出，且故障只落在啟動者的 stderr。

**牽涉：** S-03、S-05、S-06、S-01。核心未要求磁碟壞時仍可服務；必要的是可辨識的降級／停止與存活程序處置。選重試、降級或停機是技術選型。證據 `readonly.json`、`enospc.json`。

### C5. runner 原子寫保住正式 JSON 格式，但未提交的真 exit code 沒有恢復策略〔技術選型；P-07 新證據〕

**重現：** task `raise SystemExit(23)`；runner 把完整 exit JSON 寫完暫存、尚未 rename 時 kill -9 runner；重開 daemon。

**觀察：** 正式 exit.json 由 tock 補成 `code:null,lost:true,round:2`，旁邊 `exit.json.tmp.<runner pid>` 仍是完整 `code:23,round:1`。沒有半截正式 JSON，原子檔寫在這個窗口有效；但重啟既不整理暫存，也不標示有更具體的未提交結果。不能直接信任任意 tmp 作真碼，因缺少 generation／提交標誌；應明確說明 tmp 證據與 authoritative 狀態的關係。

**牽涉：** S-01、S-03、S-06；核心把結束碼可見方式留給技術選型。證據 `runner-exit.json`。不把既有 lost 補碼本身當新 bug。

## daemon／tick 需求

| 優先度 | 必須提供的能力／驗收標準 | 核心對應 | proto7-1 現況 | 本輪證據 |
|---|---|---|---|---|
| 必要 | daemon 接手有世代隔離；舊 tick／tock 不得覆蓋新世代狀態，已提交回合不得倒退 | S-03/S-06/S-08 有責任與回合概念；無具體恢復協議 | 未做到；root flock 只管 daemon 本體 | C1，stale-tick／stale-tock |
| 必要 | spawn 控制請求有可復原狀態、識別碼與結果；崩潰後能判斷待執行、已啟動或失敗，不能無痕刪除 | S-01/S-06/S-10；協議未定 | 未做到；刪除早於 start_task，無 spawn receipt | C2，spawn-loss |
| 必要 | tock 多檔提交可重做／校對；ended 標記與回合摘要不能永久分岔 | S-01/S-06/S-08；交易方案未定 | 未做到；每個 JSON 原子不等於整個 tock 原子 | C3，ended-loss |
| 必要 | I/O 失敗有明確降級／停機路徑及殘存程序處置；能記錄時輸出結構化錯誤，不讓一般 OSError 無清理退出 | S-03/S-05/S-06 明確責任；細節未定 | 未做到；status I/O 故障直接退出 | C4，readonly／enospc |
| 應該 | 啟動時盤點遺留 tmp、未完成回合與無結果任務；給出檔案可讀的 recovered／aborted／unknown 與來源 | S-01/S-06；恢復政策不在核心 | 部分：lost 可補，但 tmp 不處理，無 recovery report | C5，runner-exit；C1/C3 |
| 應該 | 由檔案明確呈現 canonical 回合、狀態 generation 與一致性；新 LLM 能辨識衝突而不必猜 status/round/summary 誰準 | S-01 直接對應 | 未做到；三份檔各自有效 JSON，仍互相矛盾 | C1；C3；C5 |

本輪不要求跨所有檔案的重型交易；先做到「接受的控制不消失、重啟可判別、舊寫入者不能倒退進度」，選 WAL、原子目錄切換、冪等 ID、世代 token 或更粗的動作鎖都屬技術選型。
