# 第 2 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/wrap-up.md)｜[R3 →](../round-3/wrap-up.md)

這一輪的收尾：題目那三個數字收到什麼答案、評委上一輪交辦的事做到了沒、以及仍然不知道的。

## 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 回 **1**，並固定分列 1 份實作、9 個靜態呼叫點、每案 8 次 commit、0 次人工 rename，題目只取第一欄；這比上一輪的 9／6 雙口徑硬。Armstrong persona 回 **1** 個 rename_noreplace() 實作，另列 2 個靜態 commit call sites、基線 12 個 transaction／receipt、0 次 shell mv、0 次手造半批 instruction；口徑延續上一輪，但把各欄分開，證據更完整。Cantrill persona 回 **9** 筆成功三回合的 Publish transaction，其中 3 筆 Deliver、6 筆非 Deliver；它把 transaction 明定成唯一主口徑，並以更正後的 9／3／6 統計支持，但這個口徑不是實作份數。Thompson persona 回 **4** 個靜態 temp→commit 實作位置：delivery helper 1 個、no-aos model-call／tool result／final 3 個；hard-link no-replace 原型不計，較上一輪只報 1 份 helper 多列出三個呼叫者自行實作的位置。

因此本輪收到的第一項原始答案是 **1／1／9／4**，但四位分別數原始碼實作份數、no-replace primitive、實際 transaction、靜態 temp→commit 位置，仍不是同一單位。p1 依評委要求已把四欄鎖死；p2 也完整分欄；p3、p4 各自選了唯一主口徑，但彼此仍不可直接橫比。

**② 哪種「不知道做了沒」本機補不回來。** 四位都回 **1 類**：provider 可能已接受，但 committed response／result 不存在，且 provider 不能依 key 查詢。Carmack persona 有不看 oracle 的同命令處置與事後 accepted／dropped 對照；Armstrong persona 有 abandon 保持 ledger 1、retry 令 ledger 1→2、result-ready 可安全 adopt 的 transition 證據；Cantrill persona 在 model／tool 兩點重現；Thompson persona 的 no-aos blind restart 讓 effect 1→2。答案數字沒變，但本輪多了明示 resolve、transition 與 no-aos 同命令重開，證據比上一輪更硬。Armstrong persona 另報一個 Deliver consumed-before-receipt 的本機 ambiguous window，但將它與遠端 Effect unknown 分開，沒有把題目數字改成 2。

**③ 有沒有第二個要同時管的工作。** 四位都回 **0**。Carmack persona 仍是一個 world、一條 loop、一筆 instruction。Armstrong、Cantrill、Thompson persona 雖都啟動兩個 producer 做競爭或壓力測試，但明列它們是短命 writer／contention，不是第二個長壽 agent、lane、join 或 scheduler。本輪比上一輪多了真實 multi-producer 證據，但 concurrent logical agent job 的數字仍是 0。

## 5. 評委上一輪要他們做的事，做到了沒

**Carmack persona。** 做到固定四欄計數，並以私有 Publish／Deliver／Effect 重跑原故障類型；每案都有恢復前狀態、單一具名命令與恢復後 ledger，accepted／dropped 的決策沒有偷看 oracle，人工 rename 為 0。第一版 baseline 與 recovery 各失敗一次，修正後另跑乾淨案例。

**Armstrong persona。** 做到 stable key＋receipt 的可重入 Publish、pending → done | unknown 與 adopt | retry | abandon，逐 transition 注入；九案各最多一條高階恢復命令，搬檔與半批 instruction 重造都是 0，明示 retry 的 ledger 由 1 變 2。另打出評委未明列的 consumed-before-receipt 缺口。

**Cantrill persona。** 做到修 harness 並留下獨立 aos exit、instruction exit、queue／temp／final 等一致欄位；合法／非法名稱、same-target 重投與雙 producer 都已測，Publish／Deliver 的拒絕、no-replace 與錯誤可見性也有輸出。第一版背景 SIGINT 與第一次 receipt 統計作廢後有更正重跑。

**Thompson persona。** 做到讓 no-aos 鏈承受同樣三刀且只用同一命令重開，結果在 effect 後重做副作用；也完成兩個 producer 各 1,000 件，shared-slot 有 1,000 遺失，global-ID 五項結果全綠。依這些失敗點收出窄 Deliver 契約，並撤回上一輪「連 Deliver 都別加」的結論。

## 6. 仍然不知道的

第一個數字仍沒有跨四人的共同單位。p1 已按評委要求固定四欄，p2 也分列 primitive／call site／transaction／人工操作；p3 的唯一主口徑是 9 筆 transaction，p4 是 4 個靜態實作位置。因此本輪能看出每份回報內部的計數比上一輪穩定，仍不能把 **1／1／9／4** 當成同一尺度排序。

仍不知道不靠操作員 adopt-consumed 時，Deliver 要如何跨越「target 已 commit、aggregate 已 claim／刪除、receipt 尚未 commit」的窗口。四份回報都顯示 queue target 消失後 key 歷史會失憶；本輪沒有 consumer acknowledgment 或共享 commit layout 的完成實驗，也沒有證明這份 ledger 應放在 Deliver 私有層或 aggregate／core。

仍不知道真實 power cut、NFS、非 Linux filesystem、虛擬磁碟與裝置快取下的結果。p2 只證明 file fsync／directory fsync 的 syscall path 有跑；其餘原型只承諾 visibility atomicity。renameat2(RENAME_NOREPLACE) 的非 Linux 替代契約、跨 filesystem 行為與孤兒 temp 的容量／清理政策也沒有答案。

仍不知道正式 Deliver 如何共用 core/inst 的 canonical parser，而不長出第二套 schema。兩份 Python validator 與一份 shell prototype 都是窄版；現有 aos 對錯 delivery 名稱的 silent ignore、child 失敗但回合 exit 0、通用 .runi recovery／status 仍未改變。

仍不知道無 query provider 的 unknown 最後應由誰、依什麼權限選 abandon 或 retry。這輪證明命令與 ledger 可以保存決策，也證明 retry 會重複 effect；沒有任何一路補出 provider 真相或 exactly-once。四份回報依然沒有真模型、真 provider 或第二個長壽 logical work 的現場。
