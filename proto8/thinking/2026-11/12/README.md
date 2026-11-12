# proto8 討論紀錄：2026-11-12

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [eca-file-tools](eca-file-tools.md) | 已施工：eca 範本不給 aos 的基礎檔案與 shell 工具（35→20 支，trash 也拿掉，只留 json_read／json_write 等 aos 專屬的）；claude 開內建 Read／Write／Edit／Glob／Grep／Bash（dontAsk＋白名單，不全繞過），codex 改 `workspace-write`；三條代定使用者「可以先定這樣」；haiku、gpt-6-luna 真腦各驗一題 |
| [line-k-leftovers](line-k-leftovers.md) | 已施工（線 K）：gitignore 分類表補 `subagents.json`（取代舊名 `children.json`）與 fork 的 `tools/fork/children/<分身>/state`（代定進 git）；實跑確認 do_task end／self_history 的結果行會把 `history_removed.jsonl` 的絕對路徑寫進 history，改成相對 stack；順帶修 fork 分身 `exec.json` 帶絕對定義路徑；代定 4 條 |
