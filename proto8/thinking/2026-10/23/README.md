# proto8 討論紀錄：2026-10-23

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-23 命名統合](naming.md) | 使用者「都先幫我統合」：不一致照 C-54、C-55、C-48、N-45 統一，對照表在 csv（後面的列取代前面的）；四條規則（副檔名 `.json`／`.jsonl`／`.txt`、時間點 `<發生了什麼>_at`、計數 `counter_<被數的東西>`、錯誤代號四種）；入口名 `_entry`、沒有「`_` 開頭＝附註」、不認得的 key 一律忽略；stack 預設 `.stack/`、題目 `new/`／`cur/`／`done/`、產出 `out/`；「要跑什麼」一律 `exec`；state 計數 `counter_runs`、時間 `recorded_at` |
| [2026-10-23 命名方法](naming-method/README.md) | 使用者提的取名步驟（先一句話說程式做什麼、加功能先一句話、每格一句白話、挑字、簡化到同檔同主題仍唯一）＋Unix／Linux 老慣例 → R1～R12（C-54）；八題選定（`<事件>_at`、`started_at_ticks`、`idx`、ctl `stopped`、不加 `last_code`、時間留 ISO、留 `_entry`、`AOS_CF/CD/CO` 留）；計數不用 `nr_`；條文用「次」不用「拍」；撞名就換角度（R9） |
| [2026-10-23 daemon 壓測後的六個問題](daemon-bench.md) | 使用者「都修都處理」、只修 C++（「python版本可以刪掉了。aos-exec/loop/daemon都用C++」）：收子項不阻塞（那列與頂層 `stopping`、滿 10 秒才 SIGKILL）；被 SIGKILL 的子 loop 自己的 state 不改（N-09），死活看 pid＋`started_at_ticks`；表改雜湊、沒 `exec` 時一圈一份 state；aos-loop／daemon 不自己建 `$AOS_STACK` |
| [2026-10-23 daemon 的 ctl 只寫變動、`$ref` 切檔、指示詞全面](daemon-ctl-ref/README.md) | ctl 維持宣告式、可以只寫變動（`loops_added`／`loops_removed`）；`$ref` 可以寫成陣列（照順序合成一份），`loops` 拆檔與 state 超過 100 列自動切都用它、主檔改名是唯一提交點；aos 讀的 JSON 全部支援指示詞、每支只解自己讀的格；刪 `$at`、位置只認 `#/`（「把$at刪掉，就都只認#/。」） |
| [2026-10-23 在 fsm 上做 aos-agent 與 aos-kernel](agent-kernel.md) | 使用者定：aos-agent＝範本（只產生標準 agent 資料夾，跑時靠 aos-loop＋aos-fsm）；未決（頂層提議）：kernel＝一個 loop 每次跑一台 fsm 做決定再寫 daemon 的 ctl，順序 `tool_calls` → 真 agent → kernel |
| [2026-10-23 腦的工具呼叫](tool-calls/README.md) | 使用者「litellm我開了，去做吧。」「盡量都用gpt的」；代定、可翻案：工具資料夾的 `tool.json` 給模型看（工具名＝資料夾名）、`arguments` 從 stdin 進、stdout 是結果、對話落在 `$AOS_STACK/history.jsonl`、三態不變、範本自己的 `brain.py` 問腦；範本 demo/agent-dan、慣例 P-41；叫工具出的問題回給腦、環境壞了才停（10-24）；未決：agent 當腦的工具時題目怎麼交、對話太長 |
