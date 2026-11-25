# proto8 討論紀錄：2026-11-25

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [api-agent-slash-1125](api-agent-slash-1125.md) | API agent（agent-fsm）也認 /status、/usage、/exit（使用者 11-25「18.要認」）：照 /clear 的做法在 idle 做、不叫腦；/exit 選 stop 不選 sleep；替使用者定的六條 |
| [9p-proc-1125](9p-proc-1125.md) | 使用者口述 9P 的 aos proc 介面的形狀：ctl／status 純文字、daemon 是 Linux 與 aos 之間的橋、stack＝活著的 proc 的身體、要留的放 persist、活著走 unix socket 掛了走寄信；實測 `/proc/<PID>/cwd` 走得通；ctl 收哪些字、status 有哪些行、socket 上講什麼還沒談；只是討論、沒開工 |
| [aos-proc介面架構規劃-1125](aos-proc介面架構規劃-1125/README.md) | 使用者建議派一批 fable（思考 max）做 9P aos proc 介面的架構規劃：第一波二十一題，Fable 額度將盡時叫停，留下十六份報告（現況盤點、9P 原樣、前例、kernel 與權限的舊規劃對照、衝突檢查、進度掃描、ctl／status 候選、送訊息兩條路）；08、09、11、19、21 與綜合沒做 |
| [daemon當容器-1125](daemon當容器-1125.md) | 使用者 11-25 晚（家機）做減法：procs/<名>/ 底下不規定（ctl、sock 歸之後的 agent 界面）、daemon 當沙箱／container 給底下假的天空、kernel 接特定呼叫；家機 main 實測不用 root 讓天空裡多一支 /usr/bin/draw 接到外面的 kernel 行程，攤三種「攔」（建議把名字交給 kernel）、做減法後剩什麼、順手解掉的與代價；三題等使用者，沒開工 |
