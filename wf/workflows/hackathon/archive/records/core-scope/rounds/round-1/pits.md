# 第 1 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/pits.md)

現行 aos 的行為，第 1 輪按「幾位獨立撞到」排序。

## 2. 坑的總表

**四位都撞到：`.runi` 不是 instruction-level checkpoint。** 它只表示整批沒有正常收尾，不能說批內哪一筆已完成、外部 effect 有沒有發生。事故後直接重開被拒：

```text
aos exec: refusing <world>: .aos/inst.json.runi already exists
restart_exit=3
```

恢復不是「從中間續跑」：要封存／搬開 `.runi`（或留作法醫證據），再自行重造只含剩餘 instruction 的 delivery；整批 replay 會讓已發生的 effect 再跑。

**四位都撞到：rename 前留下 `.temp` 時，`aos` 不讀半成品，也不替 producer 完成提交。** temp 在、ready 不在；重開可能 no-op 回 0，也可能被 `.runi` 擋住。恢復要人先檢查內容再手動 rename。

**四位都撞到：外部 effect 已接受、回覆尚未落地時，本機沒有足夠資訊還原答案。** accepted／dropped 兩案本機 snapshot SHA-256 相同、外部 ledger 1／0；盲重試讓同一 request 在 ledger 出現兩次。只有 provider 可 query 時能補回，而那資訊來自故障域外。

**三位撞到：只看 `aos exec` 的退出碼，會把斷鏈或缺下一輪看成成功。** 工具 process group 被殺（tool exit 137）、下一步失敗（schedule exit 66），`aos` 仍回 0 並清掉 `.runi`。要知道 loop 有沒有繼續，得另讀 per-instruction exit、queue、result、`.temp`、final。

**三位撞到：只中止 `aos` parent 時，子行程可能繼續。** parent 已停、child effect 後來完成、child exit 永遠沒回寫。

**三位在正常路徑看到 queue delivery 以外的 publish。** model response、effect request、attempt、tool result、final 都要寫 temp 後 rename；例如成功基線 11 次 atomic publish 只有 3 次是 delivery。

**delivery 檔名會被安靜忽略。** `delivery-turn1.timestamp.pid.json` 這種多一個點的名字，`aos exec` 連跑三次都 exit 0、檔案原封不動、沒有錯誤訊息；實作只接受從第一個 `.` 起恰好是 `.json` 的名稱。

**量測時要注意**：Ctrl-C 的 PTY wrapper 可能一起被終止而拿不到 `aos` 自己的退出碼；沒有換行的檔用 `wc -l` 會數成 0，要看原始 bytes；`tee` 的目錄要先建好，否則 transcript 不會留下；場地複製品的 git metadata 不完整、`git status` 不能用，改用全樹 SHA-256 或時間戳稽核。

**沒測斷電 durability。** 本輪只測 process signal／rename window；私有 helper 證明的是 process crash 下 temp／ready 的可見性，不外推到 power loss、page cache、fsync 或跨 filesystem rename。
