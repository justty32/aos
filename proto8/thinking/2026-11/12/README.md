# proto8 討論紀錄：2026-11-12

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [eca-file-tools](eca-file-tools.md) | 已施工：eca 範本不給 aos 的基礎檔案與 shell 工具（35→20 支，trash 也拿掉，只留 json_read／json_write 等 aos 專屬的）；claude 開內建 Read／Write／Edit／Glob／Grep／Bash（dontAsk＋白名單，不全繞過），codex 改 `workspace-write`；三條代定使用者「可以先定這樣」；haiku、gpt-6-luna 真腦各驗一題 |
| [line-k-leftovers](line-k-leftovers.md) | 已施工（線 K）：gitignore 分類表補 `subagents.json`（取代舊名 `children.json`）與 fork 的 `tools/fork/children/<分身>/state`（代定進 git）；實跑確認 do_task end／self_history 的結果行會把 `history_removed.jsonl` 的絕對路徑寫進 history，改成相對 stack；順帶修 fork 分身 `exec.json` 帶絕對定義路徑；代定 4 條 |
| [index](index.md) | 只記錄、沒施工：knowledge 不改回 memory、knowledge 工具拿掉（排 json 工具線之後）；檔案系統＋json 一條路徑尋址（fs 根 `/`、json 根 `#/`）；description 與 index 合一叫 `_index`／`_index.json`，格式 `{名: {description: …}}`，天然位置＝上一層的 index（客觀），agent 自己存的是主觀；陣列與別人的檔放外面、鍵寫路徑；未決：cache、路徑相對誰、過時、專屬工具 |
| [json-tools](json-tools/README.md) | json 工具做成一個 aos_json、兩套（A：簡單組只收路徑＋值、照字面；複雜組另名才有 `$ref`／`$env` 解開與否、解析文字等加料）：get／set／ls（附型別大小、像 ls 給選項）／del／add（已有報錯或塞進 array，可選）／search（不做 regex）；get 太大只回型別＋大小（可選、預設開，上限工具定義預設、agent 可 override）；同時寫不上鎖；description／index 另做、knowledge 改回 memory 撤銷 |
