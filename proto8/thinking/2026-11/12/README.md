# proto8 討論紀錄：2026-11-12

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [eca-file-tools](eca-file-tools.md) | 已施工：eca 範本不給 aos 的基礎檔案與 shell 工具（35→20 支，trash 也拿掉，只留 json_read／json_write 等 aos 專屬的）；claude 開內建 Read／Write／Edit／Glob／Grep／Bash（dontAsk＋白名單，不全繞過），codex 改 `workspace-write`；三條代定使用者「可以先定這樣」；haiku、gpt-6-luna 真腦各驗一題 |
| [line-k-leftovers](line-k-leftovers.md) | 已施工（線 K）：gitignore 分類表補 `subagents.json`（取代舊名 `children.json`）與 fork 的 `tools/fork/children/<分身>/state`（代定進 git）；實跑確認 do_task end／self_history 的結果行會把 `history_removed.jsonl` 的絕對路徑寫進 history，改成相對 stack；順帶修 fork 分身 `exec.json` 帶絕對定義路徑；代定 4 條 |
| [knowledge-removal](knowledge-removal.md) | 已施工：knowledge 工具整套拿掉（工具、包、`AOS_KNOWLEDGE`、`--knowledge` 開場讀根、代號），root 三種形狀一起撤；出廠內容 `proto8/knowledge/` 留著當普通 json；index 只給太大的補（代定門檻：夾超過 15 個東西、檔超過 8000 bytes 或頂層鍵超過 10 個）＝3 夾 `_index.json`＋`packs.json` 檔內 `_index`，其餘刪掉；agent 怎麼知道這批檔在哪「不管」；fsm 45、eca 24 支；待裁：加了 11-12 註的條文（P-46 最該裁）、內容裡講已拆工具的段落 |
| [index](index.md) | knowledge 不改回 memory、knowledge 工具拿掉（已施工，見 knowledge-removal）；cache 不做、主觀 index 不規定、index 只給太大的補；檔案系統＋json 一條路徑尋址（fs 根 `/`、json 根 `#/`）；description 與 index 合一叫 `_index`／`_index.json`，格式 `{名: {description: …}}`，天然位置＝上一層的 index（客觀），agent 自己存的是主觀；陣列與別人的檔放外面、鍵寫路徑；未決：路徑相對誰、過時、專屬工具 |
| [json-tools](json-tools/README.md) | 已施工（[02](json-tools/02-施工結果.md)；圖紙 [01](json-tools/01-規劃.md)，Q1～Q3 待裁）：json 工具做成一個 aos_json、兩套（A：簡單組只收路徑＋值、照字面；複雜組另名才有 `$ref`／`$env` 解開與否、解析文字等加料）：get／set／ls（附型別大小、像 ls 給選項）／del／add（已有報錯或塞進 array，可選）／search（不做 regex）；get 太大只回型別＋大小（可選、預設開，上限工具定義預設、agent 可 override）；同時寫不上鎖；description／index 另做、knowledge 改回 memory 撤銷 |
| [index-tools](index-tools/README.md) | 已施工（[02 施工結果](index-tools/02-施工結果.md)；圖紙 [01](index-tools/01-圖紙.md)）：index 工具只做「透過視角看節點」，改 index 直接用 json 工具；一支 `index_view`——只給 `path`＝天然那份、只給 `index`＝指定那份、兩個都給＝天然為底疊上指定那份、同名鍵以指定那份為準（使用者「path和index可以同時給，指定的那一份有的，會覆蓋掉天然那份。開工吧」）；index 放哪只寫在 `spot()`；json 小修 J2～J4 一起做；代定 I1～I19、K1～K6；`_metainfo` 整合一兩週後 |
| [kernel-norms](kernel-norms.md) | 已改條文（使用者「條文改寫也可以做。」）：照 11-11 kernel 03 的表改 C-47（資源管理＋排程、從寄件人看）、N-42、N-63、NORMS 08 ④、附錄1、kernel／cmd 文件與出廠內容檔，補 `knowledge/aos/kernel.json`；猜 `./.stack` 使用者裁「留」、照現行寫；框架、狀態位址標未實作；N-42「兩支不併」使用者「等圖紙」 |
| [wf-to-aos](wf-to-aos.md) | 只記原話、沒施工沒規劃：使用者想用 aos 體系把 wf/ 變成更適合 agent 的樣子，途中沒用的拿掉；他要先玩一玩 |
