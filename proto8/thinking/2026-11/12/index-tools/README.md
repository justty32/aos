# index 工具（只看、不改）：使用者 11-12 原話與決定，設計稿已出、沒施工

← [11-12 日索引](../README.md) ・ 前情：[index](../index.md)（原話一～十、index 的定義）、[json-tools](../json-tools/README.md)（json 工具一族，改 index 用它）、knowledge-removal（另一條線，出廠內容只給太大的補 index）

## 使用者原文

全文在 [index](../index.md) 原話段；跟工具直接有關的四段：

> 「那我這邊簡單說一下index工具的初步想法。就是說，_index.json/_index本身是agent想要看到的對於該節點的，自己的視角(天然位置的話就是適用於各agent的通用視角)。如果想要真正客觀，那就乖乖用shell ls或是aos json ls。所以我們要提供工具，方便agent透過這個視角看節點，以及修改這個視角。ps.我記得以前還有_metainfo, _tooldef那些，搞不好_index,_tooldef也會被整合進metainfo....啊，或許可以這樣說，_metainfo就是一個天然的，蒐集那些同節點下散落的(aos體系中的)各種_*」

頂層問：改天然位置那份要不要明講才改；看的時候預設看哪一份。

> 「改通用視角這塊就是有權限就能改，不用明講，風險自己承擔。看的時候可以自己指定要用啥index，沒指定的話就預設用通用視角。metainfo這塊就是搬進去，_index進去後就是index，去掉_。現在先不用做，這是後續想法。_entry確實不能搬進去，所以就是有些能搬有些不能搬，我們就是開了metainfo這個口子，要用不用都可以。json檔案也一樣。_metainfo整合應該會是一兩個禮拜後的事情了。」

> 「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」

> 「反正最基礎的就是這樣。後續什麼agent自己存、更新啥的，或是除了description外還要加啥，就後續再說」

## 決定

- index 是**視角**不是事實：天然位置那份＝各 agent 的通用視角；要真正客觀用 `ls`／`json_ls`。
- 工具**只做「透過視角看節點」**；改 index＝直接用 json 工具（`json_set`／`json_add`／`json_del`）。
- 改通用視角：有權限就能改、不用明講，風險自己承擔（落在 json 工具與檔案權限上）。
- 看的時候可以指定用哪份 index；沒指定＝通用視角（天然位置）。
- `_metainfo` 整合（index 搬進去、改名 `index`；`_entry` 搬不進去；開口子、用不用都可以，json 檔也一樣）：一兩週後，現在不做。
- 名字、格式、天然位置、陣列與別人的檔放外面、cache 不做、太大才補：照 [index](../index.md) 的決定。

## 結論（設計稿，fable 規劃、opus 補全；待使用者看）

圖紙在 [01-圖紙](01-圖紙.md)：

- **只有一支 `index_view`**：給節點就印它那份 index（`鍵<TAB>description` 一行一項）；`index` 參數可改看指定的那份；`key` 只看一項。不查節點在不在、不附型別大小、不合併別份（不做第二個 ls）。
- 「index 放哪」只寫在一個函數 `spot()` 裡（新模組 `lib/aos_index.py`），搬進 `_metainfo` 時只改它。
- 跟既有原則**沒有衝突**；原則推不出的方向題**沒有**；代定 I1～I19 可翻，最可能翻的是 I4（`path`／`index` 二選一）與 I10（了解 X＝看父節點加 `key`，不自動往上找）。
- json 工具改 index 的卡點四個，列成 json 工具小修建議 J1～J4（不在這條線施工）。
