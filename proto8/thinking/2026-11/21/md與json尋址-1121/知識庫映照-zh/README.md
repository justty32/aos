# 知識庫的中文映照版（給使用者審；正本仍是 `proto8/knowledge/` 的 json）

← [md與json尋址-1121](../README.md)｜做法與代定見 [09-知識庫中文映照版](../09-知識庫中文映照版.md)

`proto8/knowledge/` 裡每一份 `.json` 在這裡對一份同名的 `.md`（`aos/me.json` → [aos/me.md](aos/me.md)，`_index.json` → `_index.md`），共 156 份，來源 commit `fad6bef74`。內容一對一照 json：每一塊前面的粗體 `#/…` 是它在 json 裡的位置；英文說明譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；原文本來是中文的（`wf/` 那一庫）照抄。

**要改內容請改 json**，這裡會用腳本重新轉，手改這邊會被蓋掉（要不要改成「這邊手修、再回寫 json」是你審完再說的事）。每個子夾的 `README.md` 是腳本加的；子夾裡若出現 `_index.json`，是 repo 的 index 生成器替 thinking 夾產的，都不是知識庫的東西。

從這裡看起：

| 先看 | 是什麼 |
|---|---|
| [_description.md](_description.md) | 整個知識庫的一段簡介 |
| [aos/_description.md](aos/_description.md) | aos 一頁說完：八個詞、五條規則 |
| [aos/_index.md](aos/_index.md) | aos 這一庫每頁一句話 |
| [aos/cli/_index.md](aos/cli/_index.md)、[aos/tools/_index.md](aos/tools/_index.md) | 指令、工具各一句話 |
| [wf/_description.md](wf/_description.md) | wf 那一庫（本來就是中文） |
