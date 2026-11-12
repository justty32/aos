# 檔案系統＋json 當 memory、index（description 與 index 合一）（11-12 公司，只記錄、沒施工）

← [11-12 日索引](README.md) ・ 前情：[11-11 json-tools](../11/json-tools.md)、[11-11 playground 04](../11/playground/04-修與第二輪實測.md)（knowledge 改回 memory、root 三種形狀）、指示詞條文 [NORMS N-45](../../../docs/NORMS/06-基礎設施-命令列與指示詞.md)

## 使用者原文（依時間）

原話一：

> 「對了，關於knowlege這個工具，昨天說要改名回memory。我後來想想不用了，因為knowledge這個工具搞不好就直接沒了。」

原話二：

> 「就是說，整個檔案系統+json，本來就可以作為agent的memory了，有需要啥就去讀啥，天然的分層。缺的是啥？」

使用者自答：

> 「description, index」

原話三：

> 「description, index這兩個之後要做專屬工具，等等談。公司不建proxy，只用eca。先說說檔案系統和json這塊，對於檔案系統的存取這沒啥好說的，aos和eca的基礎工具+shell就能夠包攬一切，……」

（後面講 json 工具的那段原話由 json 工具線記在 proto8/thinking/2026-11/12/json-tools/，這裡不重抄；該夾 json 線合併後才有。）

原話四：

> 「代定都OK。json_read/write之後會被我們的json替代。knowledge沒用了，可以拿掉。然後關於description,index，我先給一些白話定義：我們用一條路徑來統一檔案系統與json的尋址，如aaa.json#/xxx/yyy，檔案系統的根目錄是/，.json檔案的根(也就是整份檔案)則是#/。而aaa.json#/xxx/yyy可以視為一棵樹上的aaa.json節點下的xxx節點...他底下的yyy節點，我們透過這個路徑去取得yyy這個節點的值。那，yyy這個節點的值客觀上可能是任何json value如obj/arr/int...等，而description，就是讓agent能在主觀上對yyy這個節點(含其值)有所理解，比如yyy節點的值是一個bool，而description可能會記錄說，他是一個用於表現某開關狀態的值。而descrition不是一定要待在哪個位置，反正他就是"路徑":{"description":"..."}這樣(之所以用json obj，是因為obj裡面以後不只會有純文字description)，放哪都可，只是說天然的情況下，agent可以假設自己會在xxx/_description中，看到yyy的介紹。比如{xxx:{yyy:true, _description:{yyy:"present the state of switch A"}}}，這是json內部，如果是檔案系統的話，可能會是在bbb/_description.json中看到bbb/aaa.json的介紹，而_description.json內的格式會是{aaa.json:"store some values"}」

原話五：

> 「而index的用途，我用白話說，就是一個透鏡，agent可以透過他看到自己想看到的東西」

> 「等等，我先把index講完。就是說，agent當然可以透過ls/json_ls去列出某個節點下有哪些子節點，但那個有時候東西太多，或是有些東西agent懶得知道，那他就可以改成直接讀那個節點下的_index.json/_index，其格式會是{"xxx":"store some values", "zzz":"just a string"}，而aaa.json下實際上有多個節點如{"xxx":{...}, "zzz":"...", "qqq":false,...}，只是說agent覺得對於aaa.json，他只需要知道他底下有xxx/zzz就好。」

原話六：

> 「description和index是可以合起來的，或者說，本來就該合起來，統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。當然，這個_index.json/_index有其天然位置，這個天然的意思是，在沒有指定位置的時候，agent如果想要了解某個節點的狀況，就會去看其上方節點的index。ps.想到了，agent自己本身的memory會存一些cache，用於知道一些常用節點的狀況，然後可以定期更新，或是在存取該節點的時候看看其index，再決定要不要更新。」

頂層問：陣列塞不了 `_index` 鍵、別人的 json 檔不能亂加鍵，是否都用「放外面、鍵寫路徑」解；最頂層沒有上一層，誰講它；沒列到的節點讀 index 時要不要提示。

原話七：

> 「2,3的確如此。然後我會覺得，放在天然位置的index，其實會是所謂的客觀index，而agent自己存的則是主觀。cache這塊之後再說。最頂層本來就沒有...。沒列到的就不管」

## 決定

- **knowledge 不改回 memory**：撤回 11-11 晚「整套改回」。
- **knowledge 工具拿掉**（「knowledge沒用了，可以拿掉。」）：施工排在 json 工具線之後，還沒做。
  - 範圍是頂層擬的、已告知使用者、**使用者尚未回應（頂層擬、未確認）**：拿掉工具、`AOS_KNOWLEDGE`、旗標、錯誤代號、包，以及開場查知識庫的指示詞；出廠內容檔 `aos/*.json` 先留著當普通 json。
- **json_read／json_write 之後被我們的 json 工具替代**。
- **公司不建 proxy，只用 eca**。
- **尋址一條路徑**：如 `aaa.json#/xxx/yyy`；檔案系統的根是 `/`，json 檔的根（整份檔）是 `#/`。
- **description 與 index 合一**，統一叫 `_index`（json 內）／`_index.json`（資料夾裡），＝agent 自己對這個節點的理解。
- **格式**：`{名: {description: …}, …}`，值用物件，因為以後不只純文字 description。
- **天然位置＝上一層的 index**：沒指定位置時，agent 想了解某節點就去看它上方節點的 index。
- **陣列、別人的 json 檔**：放外面、鍵寫路徑（原話七「2,3的確如此」）。
- **客觀與主觀**：放在天然位置的是客觀 index，agent 自己存的是主觀 index。
- **最頂層本來就沒有**上一層的 index。
- **沒列到的節點不管**。
- **description／index 之後要做專屬工具**，還沒開工。

## 未定／之後再說

- cache（「cache這塊之後再說」）。
- 「放哪都可」時，鍵裡的路徑相對誰；同一節點多處有 index 時聽誰的。
- index 過時（節點已不在）怎麼辦。
- 鍵能不能跨層。
- 專屬工具長什麼樣。
