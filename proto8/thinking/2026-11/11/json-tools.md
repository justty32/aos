# json 工具：路徑一整串、給值直接換（11-11 晚，只記錄、沒施工）

← [11-11 日索引](README.md) ・ 相關：[playground 04](playground/04-修與第二輪實測.md)（json_write 引號、root 三種形狀）、指示詞條文 [NORMS N-45](../../../docs/NORMS/06-基礎設施-命令列與指示詞.md)

## 使用者原文

前情（頂層轉述）：使用者說 json 路徑照指示詞條文，json 檔內的根是 `#/`，檔案系統的根是 `/`，「json write的時候，比如他要改xxx.json#/aaa/bbb，那他就是給這一整串。」

原話一：

> 「關於引號，就是說，我原本以爲，就是指定路徑後，agent給出一個json value，可以是object/array/int...任意類型，然後就直接替換那個。」

頂層問了六題：
1. 刪除怎麼辦？
2. 一次只改一格，要改多格就叫多次或替換上一層？
3. 那一格、中間層或檔案不存在時，自動建還是報錯？
4. 陣列尾巴加一筆，要不要認 `#/list/-`？
5. 換整份檔寫 `xxx.json` 還是 `xxx.json#/`？
6. 小模型把值包成字串（要寫物件卻送 `"{\"a\":1}"`），照字面存成字串、工具不幫拆？

另外問了 json_read 是否同樣給一整串、回那一格的值。

原話二：

> 「1.刪除，那就json_delete。順便可以有json_add,json_list,json_search，增刪查改都有。json_read也要跟json_write一樣，就是給路徑，然後拿到一個json value。好吧，其實這應該算是json_set/get。2.對。有需要的話，可以提供工具json_multi_get/set。3.可選，類似mkdir那樣。4.可以。5.兩者都可。6.就是字串。沒辦法正確處理這些的小模型本身也不適合aos體系」

使用者再補一句：

> 「json_len」

## 決定

- **路徑**：一律照 N-45 寫成一整串 `檔#/位置`。`#/` 是檔內的根，`/` 開頭是檔案系統。
- **寫**：給路徑加一個任意型別的 json 值，直接替換那一格。
- **讀**：給路徑，拿到那一格的值。
- **刪除**：另做一支 json_delete。另外可以有 json_add、json_list、json_search，增刪查改都齊；再加一支 json_len，回某一格的長度。
- **一次一格**：要改多格就叫多次，或替換上一層。需要時可以再提供 json_multi_get、json_multi_set。
- **不存在時**：自動建是可選的，類似 mkdir 的 `-p`。
- **陣列尾巴**：認 `#/list/-`。
- **整份檔**：`xxx.json` 和 `xxx.json#/` 都收。（**11-12 註**：使用者改照標準寫法「原來$ref用的是標準寫法。那我們還是按照標準寫法好了。」——整份只有 `xxx.json`（`xxx.json#` 不收，11-12 代定、可翻），`xxx.json#/` 是空字串 key，見 [11-12 json-tools 01 Q3](../12/json-tools/01-規劃.md#10-待使用者裁)。）
- **值照字面**：字串就是字串，工具不幫拆。原話：「沒辦法正確處理這些的小模型本身也不適合aos體系」。

## 待裁（明天要問，不代定）

1. 工具名要不要從 json_read／json_write 改成 json_get／json_set？使用者說過「其實這應該算是json_set/get」。
2. json_add、json_list、json_search 各自的確切行為；json_len 的細節（物件算鍵數，還是只收陣列；字串算不算）。
3. 現行 json_write 的 `set` 表與 `del` 表兩種寫法，是否整個拿掉。
4. knowledge_*（明天改回 memory_*）跟這套 json 工具是什麼關係。

**什麼時候做**：明天跟 knowledge 改回 memory、root 收三種形狀一起排。
