# proto8 討論紀錄：2026-11-25

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [api-agent-slash-1125](api-agent-slash-1125.md) | API agent（agent-fsm）也認 /status、/usage、/exit（使用者 11-25「18.要認」）：照 /clear 的做法在 idle 做、不叫腦；/exit 選 stop 不選 sleep；替使用者定的六條 |
| [9p-proc-1125](9p-proc-1125.md) | 使用者口述 9P 的 aos proc 介面的形狀：ctl／status 純文字、daemon 是 Linux 與 aos 之間的橋、stack＝活著的 proc 的身體、要留的放 persist、活著走 unix socket 掛了走寄信；實測 `/proc/<PID>/cwd` 走得通；ctl 收哪些字、status 有哪些行、socket 上講什麼還沒談；只是討論、沒開工 |
| [aos-proc介面架構規劃-1125](aos-proc介面架構規劃-1125/README.md) | 使用者建議派一批 fable（思考 max）做 9P aos proc 介面的架構規劃：第一波二十一題，Fable 額度將盡時叫停，留下十六份報告（現況盤點、9P 原樣、前例、kernel 與權限的舊規劃對照、衝突檢查、進度掃描、ctl／status 候選、送訊息兩條路）；08、09、11、19、21 與綜合沒做 |
| [daemon當容器-1125](daemon當容器-1125.md) | 使用者 11-25 晚（家機，第 30～39 段）做減法：procs/<名>/ 底下不規定（ctl 等歸之後的 agent 界面）、daemon 當容器只管碰 Linux 權力的五樣（起收行程、組天空、給身分、上鎖、發開關）、名字交給 kernel（靜態的夾也算）、PID namespace 開、天空是共用的路由不是牆、之後訂「aos proc 界面」＝能跟著 daemon 一起重起；九輪的定案、實測與提案；小實驗 sky-1125 十項全過，四題等使用者 |
