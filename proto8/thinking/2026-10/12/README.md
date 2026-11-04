# proto8 討論紀錄：2026-10-12

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-12](tasks-ticktock.md) | tasks＝像 lisp 基礎函數的獨立程式（只做 seq／par／if／not）；tick-tock 選甲＝只是時鐘（`aos-tick FILE` 讀 n 寫 n＋1，C-44），打包是規範、在 kernel 做；規範比實作重要（C-45）；未決：「等到第 N 回合」的小程式 |
| [2026-10-12 loop／daemon](loop-daemon/README.md) | loop＝包一個 inst（次數、間隔），ctl 是一個宣告式 ctl.json；daemon＝管多個 loop 的表、ctl 是資料夾、自己也是 loop；三個 json 一個手感；loop 的退出碼表；daemon 底下的 loop 用子程序（包裝檔、改 ctl／讀 state、SIGTERM 收尾、save）；tasks 讀子程式 stdout 的 `code`；未決：loop 怎麼當場收掉 inst（見 inst 進 json Q-A） |
| [2026-10-12 inst 進 json](inst-json.md) | 結束碼只有 0／非 0 是慣例；inst 只回自己的碼、子程式的碼進 exit 檔；命令列與 `run()` 照 10-14 D-1～D-4；`timeout_ms`、`grace_ms` 進 inst.json；代理人＝一個 loop 跑切狀態機的 inst；未決：Q-A 監工參數去哪、Q-C 限時算不算 inst 出錯、Q5 防不防寫錯 key |
| [2026-10-12 ctl 規範](ctl-norms/README.md) | NORMS N-05～N-10 背後的細節：宣告式 ctl.json（`paused`／`stop` 各帶 `{"val","now"}`、讀的人壞檔維持上一次、state.json 格式）與指令式控制資料夾（`.done`、`ok` 唯一要看、丟的人清），各條分規範／慣例；未決：kernel 公告欄走哪種 ctl、兩個 loop 共用 ctl.json、ctl 檔名要不要固定 |
