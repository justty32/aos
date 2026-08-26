# 三軸分別長成什麼

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

`SESSION-LOG`、`WAIT_USER`、`inbox` 三軸各自的機器狀態候選形狀、什麼動作進出，以及各自不能失去的原意；schedule／tick 作為三軸之外的喚醒條件。

---

## 三軸分別長成什麼

四位都沒有把 `SESSION-LOG`、`WAIT_USER`、`inbox` 混成一個 queue。他們共同抽出的是 open-item，
三軸仍靠 **owner 與語意** 分開：

| 現在的軸 | 機器狀態的候選形狀 | 什麼動作進來／出去 | 不能失去的原意 |
|---|---|---|---|
| **SESSION-LOG：我手上的 open in-flight** | owner=`agent`、phase=`ready|running`，帶 workflow、step、resume | `start` 建立；`resume` 回到這裡；`wait` 移出；`done` 關閉 | 只列 open，不變成完成史；它是「現在做到哪」，不是工作流全文 |
| **WAIT_USER：卡在人** | owner=`user`、phase=`wait-user`，保存 question 與 resume | `wait --question` 進入；收到答覆後 `resume` 回 ready | 等的是人親自做／驗證；不能只用 paused 混掉「誰欠下一步」 |
| **inbox：agent 之間的信** | owner=`peer` 或獨立 mail envelope；可以未讀、忽略、歸檔 | 寄信只進 inbox；只有 `accept` 才轉 task／ready，必要時再 Deliver | **信不是 instruction。**寄失敗／不回原本就容許，不能直接塞 `inst.tempd` 變成必須 claim 的工作 |

研究人員把 SESSION／WAIT 看成依 owner 產生的兩個 view；架構師也用 task 的 owner／phase 表示；
工程師與開發者則偏好 ready、wait-user、mail 三個目錄，讓位置本身就是狀態。語意已接近，尚未定的
是「狀態存在欄位裡」還是「狀態存在路徑裡」。

schedule／tick 是三軸之外的喚醒條件：開發者只存 `next_at`，人或 cron 到點喚醒；工程師要求
Deliver 成功才改 cursor。它不必把 sleeping task 改成一條常駐 loop。
