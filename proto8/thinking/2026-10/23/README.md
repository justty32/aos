# proto8 討論紀錄：2026-10-23

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-23 命名統合](naming.md) | 不一致照 C-54、C-55、C-48、N-45 統一（對照表在 csv）；四條命名規則、入口名 `_entry`、「要跑什麼」一律 `exec`、stack 預設 `.stack/` |
| [2026-10-23 命名方法](naming-method/README.md) | 取名步驟＋Unix 老慣例 → R1～R12（C-54）；八題選定 |
| [2026-10-23 daemon 壓測後的六個問題](daemon-bench.md) | 只修 C++、Python 版刪：收子項不阻塞、死活看 pid＋`started_at_ticks`、不自己建 `$AOS_STACK` |
| [2026-10-23 daemon 的 ctl 只寫變動、`$ref` 切檔、指示詞全面](daemon-ctl-ref/README.md) | ctl 可以只寫變動、`$ref` 可寫成陣列、aos 讀的 JSON 全支援指示詞、位置只認 `#/` |
| [2026-10-23 在 fsm 上做 aos-agent 與 aos-kernel](agent-kernel.md) | aos-agent＝範本（跑時靠 aos-loop＋aos-fsm）；未決：kernel＝一個 loop 每次跑一台 fsm 再寫 daemon 的 ctl |
| [2026-10-23 腦的工具呼叫](tool-calls/README.md) | 工具資料夾的 `tool.json` 給模型看、對話落 `history.jsonl`、範本 agent-dan、慣例 P-41（代定可翻案）；未決：agent 當腦的工具時題目怎麼交、對話太長 |
