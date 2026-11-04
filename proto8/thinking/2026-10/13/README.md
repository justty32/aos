# proto8 討論紀錄：2026-10-13

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-13 JSON 路徑](json-path/README.md) | JSON 也是檔案系統：命令列 TARGET 吃 `檔#/位置`（N-35），`#/` 照檔案系統寫法；loop.json 排法不動；不做 AOS_INST_SELF；單檔自指是套娃、定兩個檔；`_metainfo`＝inst 跑下去的特性（九軸、資源），作者自報的契約、inst 忽略、給 kernel 參考、格式自由 |
| [2026-10-13 kernel／agent](kernel-agent/README.md) | kernel＝能操控東西被執行的就算（標準規範：基於 daemon、決定跑哪些 inst）；任務屬性＝行程／檔案屬性＋九軸，決定演算法隨便；agent＝記憶＋思考中心＋工具的狀態機，自我改進用 loop＋狀態切換（一步落檔、zip／git）；標準版三態等待／思考／工具；工具↔inst 10-15 定（`_tool`、OpenAI tool calling）；未決：agent 資料夾怎麼放、每步留什麼紀錄、daemon 管 daemon 的收工 |
