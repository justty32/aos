# astra-4：step 驗收

A4-03、A4-04、A4-07 的原反例都不再成立；F47 的漏通知探針未造成 step 契約外行為。真 daemon 的 CSV 工作跑滿 450 個已關回合、完成 112 次工作，結束階段每次皆 10 個檔案；本線沒有新的 B／G 發現。

## 原探針驗收

| 舊項目 | 結果 | 實測 |
|---|---|---|
| A4-03 | 修好 | 合格 start=w、patience=2，r1 建框架 since=1，r4 因 4−1>2 進 timeout；run→wait 對照仍正常。 |
| A4-04 | 修好 | start=[]、ok=[]、result.ok=[] 各 rc1、stdout 為 JSON 診斷陣列、stderr 空；scalar step 也正常報錯；全域 on_timeout:kill 配 wait 被拒。 |
| A4-07 | 修好 | run 步 wake:true check rc0；timeout kill 的 halt.kind=timeout，kill 帶正確 run；與現 spec §2、§5.5 一致。 |
| A4-09 | X，已按契約處理 | 意圖寫後 SIGKILL、超過一回合才恢復會停 unknown、派工0；兩次未知只到 attempt2，第三次不派；進行中 close 拒絕。 |
| A4-10 | M，界線一致 | 手改 frame 刪 pc 仍會 KeyError；現 spec §7 已明講此誤用，不列發現。 |

證據：[step-probes.json](step-probes.json)、[重跑腳本](probe_step.py)。腳本複製 astra-3 同名檔後改用修後斷言，沒有改舊 evidence。

## F47 對 step 的後果

[probe_f47.py](probe_f47.py) 使用真 tick／tock、真 keep 直譯器、真 once 子工作。只在本程序執行的 tock.write_json 對目標直譯器 tock.json 丟 EIO，不手改生命週期檔；每次注入都記 operation／path／round 並斷言命中恰1次。

- 結果持久性：r2～r5 的 4 次通知寫失敗，round.json 每次記 notify_errors；直譯器框架仍停 r1。子工作 a 已寫槽外結果，once 槽隨後正常刪除。對已關回合重跑 tock 只有 skipped，下一 tick 也沒有補送 r1 之後的通知。r6 通知成功後，直譯器仍採用原 request／attempt，工作正常結束，a／b 各只起1次。
- 耐性：初始 wait 的 since=1；漏 r2～r4 共3次通知，r5 收到通知後即依本地回合差 timeout，沒有重設耐性。漏通知會延後執行檢查，符合「每收到一次 tock」的職責；未承諾每個關回合即時執行。

[實際命中與結果](f47-step.json)。這些 EIO 分類 X；沒有反例推翻 README「同一嘗試不派第二次」、spec §5 的證據與耐性規則，也無須要求核心恢复補送。

## 450 回合長跑

原 CSV 範例：5列，convert→stats→end；restart_on_end:true、wake:false、interval 20ms。真 daemon；450 指 node 已關回合數，不是工作輪數。

| 指標 | 結果 |
|---|---:|
| 已關回合／耗時 | 450／25.124秒 |
| r0～r450 回合樣本 | 451 |
| 不同 inst 工作結束 | 112 |
| 完成工作 report 列數與 convert request 正確 | 112／112 |
| 每步 attempt=1 | 112／112 |
| halt／error | 0 |
| 同為 ended 階段的工作目錄檔数 | 每次10 |
| ended 工作目錄 bytes | 4,381～4,397 |
| 全階段工作／node／root 檔数範圍 | 4～11／7～27／8～34 |

瞬間暫存檔與不同階段會讓檔數不同，不把 min/max 差值當成累積。112 個同階段快照没有檔數成長；範圍僅本次450回合。證據：[longrun.json](longrun.json)、[複製的長跑腳本](run_comparison.py)。

## 重跑與清場

從 repo 根執行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/step/probe_step.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/step/probe_f47.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/step/run_comparison.py --mode longrun --rounds 450
```

探針第一次開發時，F47 使用的 Fault context manager／rename hook 不受支援，判為探針錯誤；修正後7次 EIO 均實際命中，以上只採修正後結果。所有自建 /tmp 測試根皆由 cleanup 收掉；逐 PID／AOS7_ROOT 環境與 ps 核對沒有殘留程序。[清場證據](cleanup.json)，各 F47／長跑紀錄亦有逐 PID ps。未改既有程式／測試／文件、未 commit／push、未用 LLM、未動 scratchpad。
