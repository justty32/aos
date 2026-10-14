# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜語法糖：[lib/](lib/README.md)、[proto8-1](../proto8-1/README.md)

**比起實作，更重要的是規範**（C-45）。三層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文在 NORMS/ 分檔） |
| 語法糖 | 符合規範、方便用，**不要求一定用** | proto8/lib（inst、loop、daemon）、proto8-1（tasks、aos-tick） |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-定了的-N01至N13.md](NORMS/01-定了的-N01至N13.md) | 定了的：時空 N-01～N-03、inst.json N-04、控制 N-05～N-11、呼叫程式的 stdio N-12、內部狀態的外顯 N-13 |
| [02-窗的族譜-N14至N17.md](NORMS/02-窗的族譜-N14至N17.md) | 定了的（續）：窗的族譜 N-14 總則、N-15 鎖、N-16 信箱、N-17 心跳（10-14 草稿） |
| [03-實作分級-N18至N20.md](NORMS/03-實作分級-N18至N20.md) | 定了的（續）：N-18 基礎實作／標準實作兩級與錯誤歸類、N-19 loop／daemon 的 state／ctl 與 fsm 的 state 必填、N-20 巢狀重跑不保證冪等（10-14 夜草稿） |
| [04-待定.md](NORMS/04-待定.md) | 待定（AI 整理的候選，使用者還沒定）；a～f 暫定預設也記在這（h 已拍板，移到 06／lib） |
| [05-命令列與daemon-N21至N28.md](NORMS/05-命令列與daemon-N21至N28.md) | 定了的（續）：N-21～N-27 命令列與參數（D-1～D-6）、N-28 daemon.json＝loop.json 超集、inst＝daemon 每拍的身體（10-14 夜草稿） |
| [06-實作細則-N29至N34.md](NORMS/06-實作細則-N29至N34.md) | 定了的（續）：10-14 夜動工細則（原待定 h）——N-29 stderr 形狀、N-30 inst 結果與 exit 選填、N-31 loop／daemon stdout、N-32 心跳細則、N-33 ctl seq、N-34 tasks 讀 stdout（10-14 深夜草稿） |
