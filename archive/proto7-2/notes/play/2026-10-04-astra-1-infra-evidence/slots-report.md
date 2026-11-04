# 槽、歷史、控制與掛載的分工報告

## 測法與範圍

`slots-probe.py` 用真 daemon 跑歷史 module 關閉、開啟各 500 回合；`interval_ms=0`。每次設 2 個 keep 長跑槽、3 個 each 長跑槽（逐回合補滿）、1 個 each 快速槽、2 個 keep 快速槽；history 開啟多 1 個 keep 槽。快速槽每回合跑 `true`，長跑槽跑本機 `sleep`，沒有呼叫 LLM。每到 10、50、100、250、400、500 回合，以同名 resume 控制檔設定回合數，確定自動 pause 且 runner 落盤後才量大小，排除換 run 清檔與 atomic write 暫存檔的瞬態。兩組分別耗時 29.631、29.976 秒。每組結束 stop --kill、PID／程序群組收尾後移除自己的測試根；metadata 的 cleanup 檢查全部為真，三支腳本均無殘留執行程序。

## 承諾實測

| 項目 | 判定 | 證據與界線 |
|---|---|---|
| 同名槽重用，檔案數不隨回合長 | 成立 | `slots-off.json`：6 個 checkpoint `.aos` 一律 39 檔、9 子目錄（含 tasks 本身），`.aosd` 一律 8 檔。8 個槽名稱固定，round 最後恰為 500 closed。 |
| 歷史 module 開啟不使核心累積歷史檔 | 成立 | `slots-on.json`：`.aos` 一律 44 檔、`.aosd` 一律 8 檔；只多 history 槽。歷史資料放 node/history，最後 2 檔 28,063 bytes；node JSONL 受 `--max-lines 50` 限制，最後留 451～500，這 50 筆無 gap。不能推論前 450 筆無缺號，因已輪替。 |
| `.aos` 與 `.aosd` bytes 維持常數 | 部分 | 安靜任務下：history off `.aos` 5,229→5,263 bytes（100 之後不變），`.aosd` 1,666～1,725；on `.aos` 6,302～6,487，`.aosd` 1,683～1,751。整數位數、status 欄位造成小幅變動，不是歷史線性積累。但 `slots-output.json` 中同一 run、11 檔固定，out.log 在 round 1/5/10 為 4,096/20,480/40,960 bytes，`.aos` 為 5,907/22,261/42,744；全域 bytes 無上限，符合已接受 W10，不能把「只留上一次」宣稱成總容量有界。任務自有 state、writes.jsonl、不同名控制回條與 log.on 同理有條件。 |
| state/usage 跨 run 留下，刪槽後消失 | 成立 | `slots-targeted.json` 16/16 通過；新探針 `slots-design.json` 真刪除 job#1 槽後重建 job#3，原 state 不在、usage 重新寫成 150。槽重建 run 隨回合上升，非回到 1。 |
| 不變條件三 §8 用量設計 | 部分，可保住已見總額不下降，尚不足以正確累計 | 目前無 kernel。依文件規則模擬：舊槽已見 usage=100；刪槽、重建後 kernel 首次看見新槽已達 150；沒觀察到減少，retired 維持 0，總量算 150，實際兩生命合計 250。不得稱為已實作 kernel bug，但設計須補槽生命期識別／不會隨槽刪掉的累計來源。 |
| restart/reload/指定 run/回條保存 | 成立（所測範圍） | 現有 8 項 TestCtl 全過，涵蓋保留 state、取新 argv、非法 reload 不 kill、stale run 拒絕、回條過新 run 仍在。 |
| 掛載、執行中加掛、reload 合併 | 成立（所測範圍） | 既有 2 項 TestMounts 全過。`slots-extra.json` 真加掛 allowed/dynamic 成功、denied 失敗，兩者成功寫回條後移除請求；reload 從 m#3→m#5，argv sleep60→59、宣告掛載換 allowed/new、動態掛載保留並帶 dyn:true，mount-done 清掉，result.diff 完整。 |

## K 對照

- **K-07：換了形式。** `tasks-old`／purge 已不存在，原來「purge 讓 cap 自動解除」的觸發消失；§8 記最大值可以避免已見量下降，但槽刪除重建的生命期若無明確識別，會漏算跨生命的用量。100→新槽150 的反例在 `slots-design.json`。此結論嚴格區分「現行基礎設施真刪槽」與「未實作 kernel 的規則模擬」。
- **K-09：消失（設計上不存在）。** `lib/aos7_daemon.py:7` 明列 disk/retention 移除；目前沒有按歷史目錄遞迴算 disk 的程式，也沒有 status disk 欄。長跑 `.aosd` 不增加歷史檔，原先同步容量掃描的觸發消失。這不代表所有同步 I/O 控制延遲都不存在，控制目錄本身仍需列舉；此分工未宣稱量測所有 I/O 停頓。

## 新問題候選（供總報告編 A2）

1. **〔bug／設計，較高〕§8 僅靠數字變小偵測槽重建，可能少算用量。** 如上，原累計 100、新生命已 150，算 150 而非 250。即使加上 birth.run，也不能把每次換 run 都當新計量生命，因正常重起的 usage 故意跨 run 累積；需要「槽生命期」識別或槽外 durable 計量來源。這是合作式正常操作，不涉及故意偽造。證據：`slots-design.json`。建議列 K-07「換了形式」而非聲稱已修完。
2. **〔bug，低～中〕history `--max-lines` 未限制 daemon-events.jsonl。** 實呼 `modules/history.py:once` 10 次，每次 status.last_event 不同，`--status --max-lines 3`，node 歷史剩 3 行，事件仍 10 行。程式只在 node 分支 `trim`，status 分支完全沒用此值。模組說明的「--max-lines 超過只留最後 N 行」未限制來源範圍；開了 status 後仍會線性成長。與核心 W9 log.on 明示無輪替不同，這是可選 module 自己的上限漏實作。證據：`slots-design.json`。
3. **〔技術選型／取樣時序，低〕tock 通知先於 last-round 提交，快速 history 也可能固定晚一回合。** `slots-extra.py` 只將真正 tock 寫 last-round 前延後 200ms，真 history 收 round1 時總結不存在；收 round2 時只讀到 round1。round2 完整關閉後，history 最終只有 round1，無 gap，直到下個 tock 才有機會讀 round2。這落在「取樣非完整歷史」的大界線裡，不能要求它回補全部；但目前漏資料不只「module 慢／pause／回合太快」，也因通知比資料早發。建議 module 收通知後等 summary.round 達到通知回合（有停止／逾時規則），或文件明示尾回合會留在核心尚未入歷史。證據是可重現時序注入，不是自然發生率量測。

另外，history 第一次啟動讀到 round100，只記100，不會為1～99標 gap；之後100→110才標101～109。`slots-design.json` 已實測。若 module 可在中途安裝，第一次取樣前非它的觀測範圍是合理選擇，故不單獨報 bug。

## 使用者建議與複雜度

- 槽重用、核心只留上一次與歷史 module 可選都確實落實，真 500 回合證據支持，原 tasks-old/retention/disk 的清理鏈已刪除。
- 「少產檔」不等於「所有 bytes 有界」；W10 長跑 out.log、任務 state 與自行使用不同名控制回條仍可能長。這是承諾應限定範圍，不宜另生大一套核心保留政策。
- 複雜度由舊的歷史目錄／搬移／清理，轉移到 birth/run、舊 run 檔過濾、once launch 與 tasks.json 鎖、slot lifetime、history 取樣與 gap。資料夾管理明顯簡化，但生命期、消費者讀取窗口與累計事實仍需要明確協定。
- restart/reload 的 mounts 合併、同槽 state 延續符合「少找前任」的好處，實際少了一整套跨資料夾接續查找。

## 文件量測供總報告

`slots-metadata.json`：proto7-1 spec 350 行／34,778 字元／58,592 UTF-8 bytes；proto7-2 spec 356 行／20,659 字元／35,177 bytes。行數近似（+1.7%），字元少40.6%、bytes少40.0%。新版以短規則表、三態與生命週期集中敘述，閱讀負擔比長篇來源典故下降；仍需交叉閱讀第4/5/7/8節，尤其 once 的 at-most-once 界線與槽生命期不是「run 一個數」就能理解。README 35→72行，但 bytes 6,160→6,138，內容改成較分散入口與測試表，不能只看行數判定更長。

可供「僅看 README/spec」10條文件實測選用的項目：槽同名重用、keep max_live 一次補滿、each 每回合只補一槽、state 跨 run 留著、刪項後槽延後刪除、once交付物應在槽外、restart 用原定義、reload 用新定義、非法 reload 不 kill、動態掛載經許可且 reload 保留、history 是可選取樣；其中 bytes 宣稱須限定、history 尾回合的行為在文件未說清。
