# proto8 討論紀錄：2026-11-25

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [api-agent-slash-1125](api-agent-slash-1125.md) | API agent（agent-fsm）也認 /status、/usage、/exit（使用者 11-25「18.要認」）：照 /clear 的做法在 idle 做、不叫腦；/exit 選 stop 不選 sleep；替使用者定的六條 |
| [9p-proc-1125](9p-proc-1125.md) | 使用者口述 9P 的 aos proc 介面的形狀：ctl／status 純文字、daemon 是 Linux 與 aos 之間的橋、stack＝活著的 proc 的身體、要留的放 persist、活著走 unix socket 掛了走寄信；實測 `/proc/<PID>/cwd` 走得通；ctl 收哪些字、status 有哪些行、socket 上講什麼還沒談；只是討論、沒開工 |
