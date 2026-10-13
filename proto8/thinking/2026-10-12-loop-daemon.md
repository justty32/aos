# 2026-10-12 loop／daemon：loop 包一個 inst，daemon 管多個 loop、自己也是一個 loop

← [討論紀錄](README.md)｜程式現況：[proto8/lib](../lib/README.md)｜規範：[NORMS](../NORMS.md)｜前一份：[tasks 與 tick-tock](2026-10-12-tasks-ticktock.md)｜同夜：[inst 進 json](2026-10-12-inst-json.md)、[ctl 規範](2026-10-12-ctl-norms.md)

> 10-12 夜照使用者要求精簡成「原文整理、決定、結論、未決」；AI 的現況分析、好處與坑、各題選項、被推翻的設計（loop 的 ctl 是資料夾、daemon 底下的 loop 是執行緒、`want()`、命令列旗標、`now` 獨立旗子）、轉述錯誤的段落都拿掉了。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-原文結論與三json](2026-10-12-loop-daemon/01-原文結論與三json.md) | 0. 使用者原文（語音轉文字，大意照記）；1. 結論：三層各一句；2. 決定：三個 json，一個手感 |
| [02-loop與daemon](2026-10-12-loop-daemon/02-loop與daemon.md) | 3. 決定：loop；4. 決定：daemon |
| [03-遷移與未決](2026-10-12-loop-daemon/03-遷移與未決.md) | 5. 遷移步驟（跟 inst-json 那份一起做）；6. 未決 |
