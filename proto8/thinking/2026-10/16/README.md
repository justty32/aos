# proto8 討論紀錄：2026-10-16

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-16 KISS 也是最後原則](kiss-last.md) | C-56 改寫成「KISS 是最高原則，也是最後原則」，撤回 KISS 彙整的「都照推薦」；C-56 補「寫什麼就做什麼」 |
| [2026-10-16 KISS 重審](kiss-recheck.md) | 五件拍板（N-10 不留、daemon 重起默認留 `adopt`、SIGTERM＝優雅收工、agent＝外面 loop 驅動的狀態機、兩隻 kernel 不併）；未決：批次 2～6 其餘暫停 |
| [2026-10-16 agent 繼承、當函數、食譜與廚房](agent-inherit/README.md) | agent 當函數是概念上的、stack 與工作區分開、stack 放哪由呼叫方定（C-57～C-61、C-65～C-67）；食譜／廚房那套 10-19 作廢 |
| [2026-10-16 結束碼只是參考、用檔案為了借權限](exitcode-perm.md) | 結束碼只是參考、結果看 JSON（C-63）；用檔案是為了借 Linux 權限（C-64）；未決：tasks 用 `code` 決定往哪走要不要調整 |
