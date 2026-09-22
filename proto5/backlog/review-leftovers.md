# fable 重審留下的（2026-09-22）

來源：[proto5.1/notes/review-fable.md](../../proto5.1/notes/review-fable.md)。R1～R3、R5～R9、R14～R27 在 proto5.1 第 5 段做掉；以下是使用者決定先不做的。

- **R4** aos-run 被 KILL 但子程式活著，kernel 重建 runner 會與孤兒重疊。發生率低；規範寫明在保證外。真要擋：run.json 加 `child` pid，kernel 重建前 `kill(child, 0)` 還活就不排。
- **R10** cpu 收到 TERM 主動寫 `ok:false` 被中止，讓 agent 不用等收屍期限。
- **R11** 工作 cpu 與 kernel tick 的 interval 分開（工作 cpu 100 ms 級），一次問答就不用 15 秒都在等輪詢。要先有 R5 的 `last_target`。
- **R12** idle.json 用 `["true"]` 代替 `python -c pass`，閒置 cpu 別每秒起直譯器。
- **R13** 收屍用 running 檔 mtime 對系統時鐘，NTP 跳時會提早或延後；先寫進規範限制。
