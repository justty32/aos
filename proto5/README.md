# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix.md](spec/inst-posix.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；proto5 自己的 inst 實作還沒寫（proto4-3 是凍結的舊版參考） |

## 程式

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | `aos_directives.py`：指示詞機制的純函式庫（`resolve`／`resolve_located`／`split_option`／`option_names`），不知道 inst 是什麼；`cd proto5/lib && python3 -m unittest discover -s test` | 101 條測試全綠 |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
