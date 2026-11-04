# proto8 討論紀錄：2026-10-12

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-12](tasks-ticktock.md) | tasks＝只做 seq／par／if／not 的獨立小程式；tick-tock 只是時鐘（C-44）、打包在 kernel 做；規範比實作重要（C-45）；未決：「等到第 N 回合」的小程式 |
| [2026-10-12 loop／daemon](loop-daemon/README.md) | loop＝包一個 inst、ctl 是宣告式 ctl.json；daemon＝管多個 loop 的表、自己也是 loop；未決：loop 怎麼當場收掉 inst |
| [2026-10-12 inst 進 json](inst-json.md) | 結束碼只有 0／非 0、子程式的碼進 exit 檔、`timeout_ms`／`grace_ms` 進 inst.json；未決：Q-A 監工參數去哪、Q-C 限時算不算 inst 出錯、Q5 防不防寫錯 key |
| [2026-10-12 ctl 規範](ctl-norms/README.md) | N-05～N-10 的細節（宣告式 ctl.json、指令式控制資料夾）；未決：kernel 公告欄走哪種 ctl、兩個 loop 共用 ctl.json、ctl 檔名要不要固定 |
