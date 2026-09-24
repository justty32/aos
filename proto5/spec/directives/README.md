← [spec 總導航](../README.md)

# 指示詞：讓 JSON 的值「從別處來」

← [proto5 README](../../README.md)｜實作：[proto5/lib/aos_directives.py](../../lib/aos_directives.py)（[lib README](../../lib/README.md)）；proto4-3 的 `aos_inst_resolve.py` 是凍結的舊版參考

這份文件講的是**指示詞這套機制本身**，不是某一種 JSON 文件（例如 inst.json）該有哪些欄位。
規範先行：程式照本文做；程式跟本文對不上、又不是本文寫錯的地方，回來改本文。

一句話：**指示詞**是 JSON 文件裡「這一格的值不是字面寫死的，是從別處取來的」的統一寫法——
從解析者自己的環境變數取、拼一段字串、或去讀另一份 JSON 檔的某個位置。哪份文件用這套機制
（例如 inst.json）是那份文件自己的規範（「宿主規範」）決定的；本文只管機制本身怎麼運作。

## 8. 誰用這套

目前唯一的使用者是 [inst-posix.md](../inst-posix/README.md)：它定義了 `stdin`／`stdout`／`stderr`／
`exit`／`cwd`／`envs` 每個位置認得哪些 `$opt` 選項名、中心路徑（`$ref` 的 base）是解出來的
`cwd`。以後如果有別種 JSON 文件也想用指示詞，一樣是宿主規範自己定義「這個位置認得哪些
選項名」，機制本身（第 1～6 節）不用重寫。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [basics.md](basics.md) | §1 什麼算指示詞；§2 先解、再驗；巢狀 |
| [fmt.md](fmt.md) | §3 三種取值指示詞；§3.1 `$fmt` 字串模板 |
| [ref.md](ref.md) | §3.2 `$ref` + `$at`：讀另一份 JSON 的某個位置 |
| [opt.md](opt.md) | §4 選項物件：`$opt` / `$val` |
| [errors.md](errors.md) | §5 循環；§6 錯誤代號；§7 容易踩的 |
