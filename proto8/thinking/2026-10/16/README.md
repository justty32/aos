# proto8 討論紀錄：2026-10-16

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-16 KISS 也是最後原則](kiss-last.md) | C-56 本條改寫成「KISS 是最高原則，也是最後原則」（不算子原則）——先滿足需求與其他原則，最後回頭清掉多餘的，不拿「最乾淨、規則最少」抄近路；撤回 KISS 彙整的「都照推薦」；C-56 補「寫什麼就做什麼」（`/dev/std*` 特判否決、三個 `*_inherit` 留著） |
| [2026-10-16 KISS 重審](kiss-recheck.md) | 使用者拍板五件：N-10 指令資料夾不留（子項改由 ctl 宣告）、daemon 重起「給選項，默認留」（`adopt`）、SIGTERM＝優雅收工（N-52 已作廢，現行 P-36）、agent＝被外面 loop 驅動的狀態機、定義不含 loop、連錯不數（C-62、N-53）、兩隻 kernel 不併；未決：批次 2～6 其餘各項，10-16 起暫停 |
| [2026-10-16 agent 繼承、當函數、食譜與廚房](agent-inherit/README.md) | 使用者：不要 args.json／ret.json（agent 當函數是概念上的）；stdin 是正規入口、argv 是語法糖；agent 的 stdin 只放食譜（定義）、這次的話放廚房（stack）；接法用捷徑；一律 `aos exec 廚房 食譜`；不用 PATH、工具＝食譜資料夾 → C-57～C-61、N-46～N-51；frame 與使用者的工作區分開、指標＝捷徑、一般工具入口寫 `"cwd": {"$env": "AOS_WS"}`、agent 工具站自己的 frame、frame 放哪由呼叫方決定、`$env` 可當正式機制（N-45 選 A）→ C-65～C-67、N-55、N-56（決定在 § 四） |
| [2026-10-16 結束碼只是參考、用檔案為了借權限](exitcode-perm.md) | 結束碼只是參考、是 Unix 時代的遺留，結果與狀態看 JSON（C-63）；用檔案是為了借 Linux 讀寫權限，例 kernel 當某 daemon ctl 的唯一寫者（C-64，兩人同時改 ctl 靠單一寫者解）；未決：tasks 用 `code` 決定往哪走要不要調整 |
