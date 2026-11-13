# code map 各分冊導覽

← [code map 總圖](../code-map.md)（地圖、常查表、真相層優先序都在那裡）

這個資料夾是 code map 的逐檔表部分。**11-05 夜起逐檔表不手寫**：全部從 proto8 各檔的檔頭一句話生成（11-13 起主檔是 `wf/knowledge/code-map/proto8/<夾>.json`，本夾的 md 冊是過渡期並存、等刪），放在 [proto8/](proto8/README.md)（一個 proto8 頂層夾一冊，冊名＝夾名，太大切 `-2`、`-3`…；開頭有 generated 標記，不要手改）。

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [proto8/README](proto8/README.md) | proto8 每個進版控的程式檔一列（生成），含 impls 的 CMake 依賴表 | 要改 proto8 任何程式、想知道某個檔負責什麼 |

**新增、刪除檔或某檔職責變了**：改那個檔的檔頭一句話，commit 前跑 `python3 wf/tools/index_gen.py --apply`（json 逐檔表與本夾 md 冊一起重寫、刪掉已不對應任何夾的舊冊）。不帶參數只檢查、不一致退 1。

甲代（repo 根 `core/`、`app/`）的分冊 11-05 封存在 `common/archive/code-map/`（索引見 [common/archive](../archive/README.md)）。
