# 檔案系統＋json 當 memory、index（description 與 index 合一）（11-12 公司；knowledge 拆除與出廠檔 index 已施工，[knowledge-removal](knowledge-removal.md)）

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

頂層擬 knowledge 拆除範圍：「拿掉工具本身和開場『先查知識庫』的指示詞，出廠那批內容檔先留著當普通 json 檔」「root 收三種形狀不做了，跟著 knowledge 一起撤」。使用者答：

> 「對，也可以順便給他們加上index。可以先做了吧」

拿掉後 agent 怎麼知道內容檔在哪，使用者答：

> 「4.不管。」

原話八：

> 「對了，剛剛那套index，我這邊有些想法：agent的cache這個機制先不用做，反正我們就是訂下index是這樣，客觀index是這樣，agent自己要記錄自己的主觀的東西，就自己想想要放哪，我們不規定。cache這東西以後可能會做工具吧，但現在我們就不管。json檔案要不要加上_index，就是說，index我覺得有幾個主要用途，一個是agent可能會有自己的看法(cache)(或是agent們的通用看法，天然位置)，另一個是當節點下的某些東西太龐大了，所以用index給他做一個簡介。所以現有aos知識庫中，如果有些東西太大，那就補index.json/_index。如果夠小，那其實也不用做看法了，直接讀就是了。」

原話九（index 工具的初步想法；最後「各種_*」是使用者補打的，原訊息尾巴打成亂碼）：

> 「那我這邊簡單說一下index工具的初步想法。就是說，_index.json/_index本身是agent想要看到的對於該節點的，自己的視角(天然位置的話就是適用於各agent的通用視角)。如果想要真正客觀，那就乖乖用shell ls或是aos json ls。所以我們要提供工具，方便agent透過這個視角看節點，以及修改這個視角。ps.我記得以前還有_metainfo, _tooldef那些，搞不好_index,_tooldef也會被整合進metainfo....啊，或許可以這樣說，_metainfo就是一個天然的，蒐集那些同節點下散落的(aos體系中的)各種_*」

頂層問兩題：改天然位置那份會影響所有 agent，要不要明講才改；看的時候預設看哪一份。使用者答：

> 「改通用視角這塊就是有權限就能改，不用明講，風險自己承擔。看的時候可以自己指定要用啥index，沒指定的話就預設用通用視角。metainfo這塊就是搬進去，_index進去後就是index，去掉_。現在先不用做，這是後續想法。_entry確實不能搬進去，所以就是有些能搬有些不能搬，我們就是開了metainfo這個口子，要用不用都可以。json檔案也一樣。_metainfo整合應該會是一兩個禮拜後的事情了。」

原話十（縮小範圍）：

> 「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」

## 決定

- **knowledge 不改回 memory**：撤回 11-11 晚「整套改回」。
- **knowledge 工具拿掉**（「knowledge沒用了，可以拿掉。」）：json 工具線之後施工，已做，[knowledge-removal](knowledge-removal.md)。
  - 範圍（頂層擬，**使用者已確認**「對，也可以順便給他們加上index。可以先做了吧」）：拿掉工具、`AOS_KNOWLEDGE`、旗標、錯誤代號、包，以及開場查知識庫的指示詞；出廠內容檔 `aos/*.json` 留著當普通 json，順便加上 index。
  - **root 收三種形狀**（11-11 規劃、未施工）跟著 knowledge 一起撤（同一句確認）。
  - **agent 怎麼知道內容檔在哪：不管**（「4.不管。」）：指示詞、工具說明都不提路徑。
- **cache 不做、主觀 index 不規定**（原話八）：agent 自己的看法自己想放哪；cache 以後可能做工具，現在不管。
- **index 只給太大的補**（原話八「如果有些東西太大，那就補index.json/_index。如果夠小……直接讀就是了」）：出廠內容檔照這條補，門檻與結果在 [knowledge-removal](knowledge-removal.md)。
- **json_read／json_write 之後被我們的 json 工具替代**。
- **公司不建 proxy，只用 eca**。
- **尋址一條路徑**：如 `aaa.json#/xxx/yyy`；檔案系統的根是 `/`，json 檔的根（整份檔）是 `#/`。（**11-12 稍後註**：使用者看到 `$ref` 照 RFC 6901 後改口「原來$ref用的是標準寫法。那我們還是按照標準寫法好了。」——整份檔只寫 `aaa.json`（`aaa.json#` 不收，11-12 代定、可翻），`aaa.json#/` 是名字為空字串的 key；json 工具已照改，見 [json-tools 01 Q3](json-tools/01-規劃.md#10-待使用者裁)。）
- **description 與 index 合一**，統一叫 `_index`（json 內）／`_index.json`（資料夾裡），＝agent 自己對這個節點的理解。
- **格式**：`{名: {description: …}, …}`，值用物件，因為以後不只純文字 description。
- **天然位置＝上一層的 index**：沒指定位置時，agent 想了解某節點就去看它上方節點的 index。
- **陣列、別人的 json 檔**：放外面、鍵寫路徑（原話七「2,3的確如此」）。
- **客觀與主觀**：放在天然位置的是客觀 index，agent 自己存的是主觀 index。
- **最頂層本來就沒有**上一層的 index。
- **沒列到的節點不管**。
- **description／index 之後要做專屬工具**，還沒開工。（原話九、十之後：設計稿已出、待使用者看，[index-tools](index-tools/README.md)。）
- **index 是視角，不是事實**（原話九）：天然位置那份＝各 agent 的通用視角；要真正客觀用 `ls`／`json_ls`。上面「客觀 index」的說法以此為準。
- **index 工具只做「透過視角看節點」**（原話十）：改 index 直接用 json 工具。
- **改通用視角**：有權限就能改、不用明講，風險自己承擔。
- **看的時候**可以自己指定用哪份 index，沒指定＝用通用視角（天然位置）。
- **`_metainfo` 整合**（index 搬進去、去掉 `_` 叫 `index`；`_entry` 搬不進去；開口子、用不用都可以，json 檔也一樣）：後續想法、一兩週後，現在不做。

## 未定／之後再說

- cache（「cache這塊之後再說」；原話八：現在不做、以後可能做工具）。
- 「放哪都可」時，鍵裡的路徑相對誰；同一節點多處有 index 時聽誰的。
- index 過時（節點已不在）怎麼辦。
- 鍵能不能跨層。
- 專屬工具長什麼樣。
