# 時間探針（合併素材）

入口先讀 `proto7-1/README.md`、`spec.md`，再讀它們連到的核心 spec、problems 與三輪 play 報告；沒有使用 kernel、agent、real.py 或 LLM。執行 `python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/time/probe.py` 可重跑。七組實驗約 6.1 秒。外部 wrapper 記錄實際 tick/tock 程序呼叫起訖的 monotonic 秒數；只有故障組注入 SIGSTOP、時鐘组用 `sitecustomize` 改 `datetime.datetime.now()`，沒有改產品檔或 host 時鐘。數字包含 Python 程序啟動；其他低負載探針同機，未隔離 CPU。所有工作空間 `/tmp/astra4-time-*` 已刪除，所有 daemon 正常 stop＋kill 返回；真正 worker 只出現在 early 組，keep worker 由 daemon 收掉。

## 數字

| 情境 | 樣本／設定 | 實際 tick 呼叫起點間隔 | 備註／證據 |
|---|---|---|---|
| 極短 | 空任務，1 ms，33 tick | 中位 32.086 ms（30.657–34.176 ms） | `interval.json`；不會追趕虛構的 1 ms 回合 |
| 零／負值 | 0／−10 ms，各 33 tick | 中位 32.134／32.218 ms | 都靜默夾成 1 ms；與 1 ms 同樣受兩支 Python 程序成本限制 |
| 一般 | 空任務，100 ms，11 tick | 中位 100.056 ms | 同時有三條極短時間線 |
| 極長 | 空任務，一天（86,400,000 ms） | 觀察 1.05 秒只開 1 回合 | 沒等一天；空任務仍提早 tock |
| interval 改小 | 1,000→100 ms，第一回合已 tock 後改 | 1,000.060、100.060、100.070 ms | `change.json`：改值要到下個 tick 前才讀 |
| 很長 interval 改小 | 一天→10 ms，再送 rescan | 300 ms 觀察仍第 1 回合 | `longchange.json`；SIGTERM 至退出 31.33 ms，可停止 |
| 模擬 tick 排程遲到 | interval 100 ms，首 tick SIGSTOP 350.87 ms 再 SIGCONT | 首 tick 執行 367.11 ms；下一 tick 相距 382.83 ms，之後 100.08 ms | `stall.json`；首 tick 返回 0，tock 0.093 ms 後呼叫，15.628 ms 後完成；無补回合／追趕風暴 |
| 模擬牆鐘跳動 | interval 100 ms；0→+1 h→−1 h→0，11 tick | 中位 100.062 ms，範圍 100.005–100.079 ms | `clock.json`；實際計時未變，檔案 `at` 真的倒退兩小時 |

以上「間隔」是 tick **呼叫起點**到下次起點，並非 S-08 定義的 tick 動作完成到完成；完整兩端時間都存於 evidence。可用 `end` 重算，不拿牆鐘時間量延遲。

### 提前 tock 的實測控制組（P-16 已知，不另報新問題）

設定 500 ms，各跑 3 回合，`early.json`：

- 空任務：tick 完成後約 0.10 ms 呼叫 tock，約 16 ms 完成。
- 每回合新起 `sleep(0.01)`：tick 完成後約 40.3 ms 呼叫 tock，約 56.3 ms 完成；10 ms 任務本體不是完整「起程序→runner→退出觀測」耗時。
- 一個 keep sleeper：第 1 回合 tick 完成後約 483 ms 才呼叫 tock；第 2／3 回合約 0.1 ms 就呼叫 tock，sleeper 仍活著。再確認提前條件是「本回合新起的任務都結束」，不是「全部活任務結束」。

## 新問題

### T-1 無效 interval 永久停掉時間線，修正與 rescan 都無法恢復〔bug〕

**重現：** 建正常對照 `good`（100 ms），另建 `null`、`text`、`nan`、`inf`、`overflow`，分別設 `interval_ms` 為 `null`、`"bad"`、NaN、Infinity、10^309。NaN/Infinity 是 Python JSON 擴充，不是標準 JSON；`null`、字串及巨大整數本身都是合法 JSON，也足以重現。起 daemon；250 ms 後把五條全部改成 100 ms，寫 `{"op":"rescan"}`；再等 300 ms。

**看到：** 五條 round 一直 0、`phase:stopped`，`paused:false`；good 從第 3 到第 6 回合正常。rescan 記 `ok:true`，五條不再產生 tick。`status.json` 沒有任何 `last_error`；真正 TypeError/ValueError/OverflowError 只在 `log.jsonl ev:error`。檔案改正後原 timeline 物件仍留在 daemon 字典，scan 只啟動「新 node」，因此不會替已死 thread 重啟（此為程式路徑佐證，不把 300 ms 實測假稱無限等待）。

**影響：** 一份可修復的設定錯誤變成需要重啟 daemon 或移除再重建 node 的故障；其他時間線雖被隔離保護，但單線沒有恢復協議。S-01（目前狀態缺錯誤）、S-05／S-06（多時間線隔離與故障收斂）。證據：`invalid.json` 的修正前後 status、rescan 與 error 事件；`aos7_daemon_timeline.interval/run`、`aos7_daemon.scan`。

### T-2 interval 更新沒有生效回條、既有長 deadline 無法由 rescan 縮短〔技術選型〕

**重現：** `interval_ms:1000` 空 node 第 1 回合 tock 後改 100；另一次 `86400000` 改 10 並寫 daemon rescan。

**看到：** 前者第 2 個 tick 仍等滿 1,000.06 ms；後續才每 100.06 ms。後者 300 ms 內 round 保持 1，rescan 成功但不喚醒既有 deadline。原始迴圈是在每個 tick 前讀設定一次，整個 idle 的 deadline 已固定；「最久要等舊 interval」是依程式推論，沒有實等一天。正常 stop 能在 31.33 ms 結束。

**影響：** 只讀 timeline.json 會看到 10 ms，卻看不到 daemon 實際仍使用的一天 deadline；用寫檔操作的人無法判斷已生效、待生效、故障或只是慢。核心 S-08 明說不準時無妨，本項**不是**硬即時違約，應決定 hot reload 的生效邊界並寫明。S-01、S-06、S-08。證據：`change.json`、`longchange.json`。

### T-3 時鐘跳動不擾調度，但現有記錄無法可靠算經過時間〔技術選型；新證據〕

**重現：** 以 probe 的 `sitecustomize` 對全部 daemon／tick／tock Python 程序同時注入 `datetime.now()` 偏移 0、+3600、−3600、0 秒；monotonic 不改。

**看到：** 100 ms 實際間隔中位 100.062 ms；第 5 回合 tick_at 為 15:49:41.117，第 6 回合變 13:49:41.218。daemon、rounds 現有紀錄只有牆鐘 at，没有 monotonic duration、clock epoch／session；沒有外部 probe 的 times.jsonl，就無法從這些檔區分時鐘校正與相隔兩小時的真實事件。round 能排同 node 次序，但不能還原跨 node 的經過時間。

**影響：** 邏輯已符合細部 spec「不依賴牆鐘」，但 S-01 的故障判讀與延遲量測缺證據。建議保留人可讀時間，再補 daemon session、單調事件序號／duration；跨重啟的 monotonic 絕對值不能直接比較。S-01、S-03、S-08。證據：`clock.json`。這是模擬牆鐘跳，不是實際更改系統時鐘。

## daemon／tick 需求（交主報告整合）

| 優先度 | 必須提供什麼 | 證據 | 核心對應 | proto7-1 目前 |
|---|---|---|---|---|
| 必要 | 每條時間線設定有型別／範圍檢驗；拒絕異常值需可讀錯誤，保留前一個有效值或明確停止；修正後可恢復 | T-1 五個壞設定隔離成功、卻修好仍不跑 | S-01、S-05、S-06 有原則；恢復策略未定 | 部分：隔離有，驗證／恢復無；status 不顯示 thread 錯誤 |
| 必要 | deadline、等待 timeout 用單調時鐘；牆鐘調整不能重複／跳過回合 | T-3，±1 h 時仍約 100 ms | S-08 原則有；具體時鐘未定 | 已做到（monotonic），只有記錄用牆鐘 |
| 應該 | 檔案狀態列 configured/effective interval、生效回合、下一 deadline 或相對剩餘量；動態修改是否喚醒等待需明文 | T-2，一天→10 ms rescan 成功仍待舊 deadline | S-01、S-06；hot reload 細節無 | 沒有；只有檔案設定，下一回合才讀 |
| 應該 | 記錄 tick/tock 呼叫起訖、單調 duration、deadline lateness、early reason；session/epoch 讓重開前後能分辨 | T-3 牆鐘倒退；stall 延遲需要外部 wrapper 才量得出 | S-01、S-08；診斷欄位無 | 只有 at／round／early bool；無 duration、expected deadline、reason |
| 應該 | 遲到後採有界恢復策略、別補起無界回合；保留遲到證據 | 首 tick 停 350.87 ms，下一回合382.83 ms，之後恢復100.08 ms | S-06、S-08，且 S-08 不要求準時 | 有界恢復已做到，遲到證據沒記 |
| 應該 | 明示提前 tock 的判斷集合，與跨回合任務是否相關 | early 空／each／keep 控制組 | S-09、S-11 有；精確策略未定 | 已在細部 spec 寫「本回合起的」；P-16 使用者決策仍未解，不當本輪新問題 |
| 可以 | 公開最小可達 cadence 或 saturation 指標，避免 1 ms 設定被當承諾 | 1 ms 實際32.086 ms；0／負值靜默夾值 | S-01、S-08；核心不保證即時 | 無 effective cadence 指標；約16 ms tick＋16 ms tock 是本機最低成本 |
