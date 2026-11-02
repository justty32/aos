# 2026-11-02 aos-exec 一環套一環、共用 stack＝像繼承

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜同日：[小格改 tools/](2026-11-02-stack-tools.md)、[state 窗](2026-11-02-state-window.md)、[daemon 環境變數](2026-11-02-daemon-env.md)

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-02，逐字）

> 就是說，我們現在的aos體系，就是aos-exec一環套一環，用aos-exec跑一個資料夾，他可能會先執行一套，這一套在執行過程中又可能變成另一套，然後大家全都共用一個stack。這其實有點類似繼承，你要考慮你的base class做了啥，用了啥，並且斟酌決定是否要覆蓋，或是避開

> 是的，繼承的時候，base class和deriative class可能在宣告時，共用了同個變數名稱。C++的處理方式就是各自有各自的命名空間，不撞在一起，我們不做這樣的隱性操作，大家就是各自管好自己的手，一些常見的東西最好是加上自己的前綴，比如daemon_*, loop_*，或是自己開個資料夾放。當然，未來可以考慮弄一些契約或機制，但那是以後的事情。剛剛說的是宣告時候的撞名，除此之外還有函數執行的時候，可以選擇性呼叫base class的函數

## 結論（11-02，跟使用者討論後）

> **11-02 晚**：ctl／state 這一組例外——控制自身的不加前綴（`ctl.json`／`state.json`），見 [ctl-state-names](2026-11-02-ctl-state-names.md)；其他固定名照本節（那份方向題 2 使用者「好。」）。


- aos-exec 往下「變成」另一套＝共用同一個 stack（像繼承）；「叫」另一個程式＝給它小格（像組合，P-17）。
- 共用 stack 的撞名，aos **不做隱性的命名空間**（不像 C++ 自動各自分開）：各格自己管好，常見的名字加自己的前綴（`daemon_*`、`loop_*`），或自己開資料夾放。
- 契約或機制以後再考慮，現在不做。
- 另一面（使用者提）：執行時可以選擇性呼叫 base class 的函數——第三段使用者自己收回，呼叫沒有 base／derived 之分（見下）。

## 使用者原文（11-02 第三段，逐字）

> 呼叫base class函數這塊...啊，這個要看_entry是從哪裡開始，有從起始到終點，也有從終點，然後從終點往回呼叫。比如_entry呼叫loop.json，loop.json中說他要回去呼叫指定的exec.json，也有先從exec.json開始然後一路呼叫loop.json，所以在呼叫這塊，其實沒有base class, deriative class之分。

結論：繼承的比喻只用在**宣告時的撞名**（共用 stack 的名字各自加前綴或開資料夾）；**呼叫這塊沒有 base／derived 之分**——同一組檔可以從起點一路往下（`_entry` → `loop.json` → 回頭叫 `exec.json`），也可以從另一端開始（先 `exec.json` 再一路叫到 `loop.json`），誰叫誰看入口從哪裡進。
