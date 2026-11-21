# 知識庫的中文映照版：給人審用，正本是 `proto8/knowledge/` 的 json

> **先看這段**：這一夾是給人審的**中文映照版**，正本是 `proto8/knowledge/` 裡的 `.json`（跟本夾並排在 `proto8/` 底下）。來源 commit `fad6bef74`。這一夾**不會自動跟著 json 更新**（json 改了要重跑映照腳本才會跟上），**改這裡也不會回寫 json**。給 agent 讀的仍是 json。這一夾放在 `knowledge/` 外面，是為了 agent 用 grep 查知識庫時不會撈到中文重複的一份（使用者 11-21 傍晚要求）。

← [proto8/knowledge](../knowledge/README.md)｜做法、拿不準的詞與代定見 [thinking 09-知識庫中文映照版](../thinking/2026-11/21/md與json尋址-1121/09-知識庫中文映照版.md)

`proto8/knowledge/` 裡每一份 `.json` 在這裡對一份同名的 `.md`（`aos/me.json` → [aos/me.md](aos/me.md)，`_index.json` → `_index.md`），共 156 份。內容一對一照 json：每一塊前面的粗體 `#/…` 是它在 json 裡的位置；英文說明譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；原文本來是中文的（`wf/` 那一庫）照抄。每個子夾的 `README.md` 是映照腳本加的，知識庫那邊沒有對應的 json。

從這裡看起：

| 先看 | 是什麼 |
|---|---|
| [_description.md](_description.md) | 整個知識庫的一段簡介 |
| [aos/_description.md](aos/_description.md) | aos 一頁說完：八個詞、五條規則 |
| [aos/_index.md](aos/_index.md) | aos 這一庫每頁一句話 |
| [aos/cli/_index.md](aos/cli/_index.md)、[aos/tools/_index.md](aos/tools/_index.md) | 指令、工具各一句話 |
| [wf/_description.md](wf/_description.md) | wf 那一庫（本來就是中文） |
