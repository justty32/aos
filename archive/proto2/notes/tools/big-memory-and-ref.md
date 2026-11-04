# 大型記憶庫與 JSON `$ref`

一句話：把很久才會用到的原文放到外面，對話裡只留找得回去的小指標。

## A. MongoDB 當大型記憶庫

`prompts.json` 是眼前這段對話。memory 包是個人小筆記與短期整理。
MongoDB 是大量、可查詢、可讓多個 agent 共用的長期倉庫。
### 建議架構

做一個獨立的記憶世界，例如 `examples/memory/`。它的 `.aos/inst` 只有 `aos-mem exec .`。
裡面有 `requests/`、`requests/running/`、`requests/done/`、`results/`、`logs/`。
agent 寫請求檔。記憶世界過幾格才寫回同名結果檔。
`aos-mem exec` 只派出背景工作，不在這一格等 MongoDB。
記憶世界自己有 `.venv/`，裡面裝 `pymongo`。agent 與 `proto2` 本體仍只用標準函式庫。
MongoDB 位址只寫環境變數的名字，不把密碼寫進檔案。
主路選 `pymongo`。它回來的資料與錯誤容易整理成 JSON。
`mongosh` 反而要處理字串跳脫與輸出，所以只留給人手動檢查。
不要讓 agent 直接連。否則每個 agent 都要裝相依、拿密碼，也可能讓一格卡太久。
請求檔固定是 `request`、`op`、`agent`、`args`。結果檔是 `request`、`ok`、`data` 或 `error`。
工具先回 `queued` 與請求編號。agent 每格收結果，再通知模型。

### 資料長相

建議共用一個 `memories` collection，也就是一張表，再加 `agent` 欄位。
不要每個 agent 開一張。那會讓跨 agent 查找與整理變麻煩。
每筆至少有 `_id`、`agent`、`time`、`kind`、`text`、`tags`、`source`。
`kind` 先用 `note`、`history`、`mail`、`tool`。`source` 記哪封信或哪次工具呼叫。
`agent`、`time`、`tags` 要有查找用的索引。
文字搜尋先用 MongoDB 的文字索引。embedding 先不做。
第一版同一個記憶世界裡的 agent 都能查。閱讀隔離以後再加。
### `mem_put(text, tags)`

參數是內文與標籤。agent 名、時間、種類、來源由系統補。
回記憶 id、實際標籤與 `queued` 或 `done`。
學到一件日後還會用到的事時用。
### `mem_find(query, limit)`

參數是搜尋字與筆數。預設 10 筆，最多 50 筆。
同時找 `text` 與 `tags`。先回 id、時間、種類、標籤與短摘錄。
覺得以前記過，但還不確定是哪一筆時用。
### `mem_get(id)`

參數是記憶 id。回完整一筆記憶。
先用 `mem_find` 找到，再用它讀全文。
### `mem_forget(id)`

參數是記憶 id。回有沒有刪到與被刪記憶的短摘要。
只刪大型記憶庫那一筆，不連帶刪原始信件或檔案。
使用者要求忘記，或內容確定錯誤時用。
### `mem_archive_history(from, to)`

參數是 `prompts.json` 的起訖序號，頭尾都算。
它把整段原文送進記憶世界。成功後才改本地對話。
回歸檔 id、訊息數與字數。
原位置只留一句 `已歸檔 id=…`，不能先刪再等結果。

### 自動歸檔

超過 40000 字時，先歸檔舊原文，確認成功，再讓 memory 包寫摘要。
摘要裡保留歸檔 id。最近 20 則不動。
超過 80000 字時，先停止送新的 LLM 請求。
把最舊一半歸檔。成功後立刻縮成一句，再恢復運作。
MongoDB 不通時，先落到退路，不能因歸檔失敗把原文弄丟。

### 沒有 MongoDB 時

請求與結果格式完全不變，只換記憶世界背後的存法。
先做 SQLite 退路。它在標準函式庫裡，也能查字與標籤。
純 JSON 只適合救急。資料一大，查找與同時寫入都很難收拾。

## B. 用 JSON `$ref` 控制 context

對話裡的大 JSON 改成 `{"$ref":"mem://<id>"}` 或
`{"$ref":"file://refs/<id>.json#/a/b"}`。需要內容時才展開。
### 摺疊規則

一個工具結果轉成 JSON 後超過 6000 字，就自動摺起來。
信件工具與檔案工具回來的大 JSON 也走同一條規則。
預設先存到 `<home>/refs/<id>.json`。這條路最快，也不靠 MongoDB。
要長期保存或跨 agent 共用時，再存 MongoDB，留下 `mem://`。
本地檔保存完整 JSON。檔名用新 id，不拿原始檔名來猜。
工具結果寫進 `prompts.json` 前，一律先做這個檢查。
一般工具不用知道 `$ref`。摺疊是 agent 的 `act` 那格負責。
檔案指標只能讀 agent 本體內的路徑，不能藉它讀外面的檔案。
展開時可以指定 `#/choices/0` 這種 JSON 路徑。
路徑不存在就回錯，不能偷偷改成展開整包。
沒指定時，最多展開 6000 字。呼叫者可以指定更少，硬上限 20000 字。
回傳要說原文總字數、這次回了多少、是否被截短。
截短的內容要標成文字片段，不能假裝仍是完整 JSON。
`ref_expand` 的結果只在下一次問模型時暫時展開。
模型看過一輪後，agent 自動把那則工具結果改回原指標。
這樣模型不會在後面每一輪都重吃同一大包內容。
`file://` 可以當格讀回。`mem://` 要丟請求，幾格後再通知模型。

### `ref_expand(ref, path?, max_chars?)`

參數是指標，可再給 JSON 路徑與最大字數。
回指定位置的內容、總字數與是否截短。
看到指標，而且眼前問題真的需要內文時才用。
### `ref_collapse(message_index)`

參數是對話序號。把那一則裡的 JSON 存走並換成指標。
回新指標、原字數與存放位置。
內容不是 JSON 就回錯，不偷偷改存普通文字。
自動門檻沒碰到，但模型已知道這包暫時用不到時用。
### `ref_list()`

沒有參數。只回最近 20 個指標、總數、大小、時間與一句來源。
忘了剛才收起哪些東西，或要挑一包展開時用。
工具包的預設 prompt 只要一句：
看到 `$ref` 就是「這裡有東西被收起來了，需要才展開」。

### 跟摘要怎麼配

`$ref` 是原文還在，只是不送進 context。摘要是原文被濃縮。
所以先把大 JSON 摺起來，再摘要剩下的對話。
摘要時保留有用的指標，不要為了摘要而把它全部展開。

`mem://<id>` 是 A 寫入的一端，也是 B 讀回的一端。
本地 `file://` 先解決眼前成本，MongoDB 再解決長期與共用。
## 跟現有程式怎麼接

實作時新增 `proto2/aos-mem`、`proto2/aos_memory.py`、
`proto2/packs/big_memory.py` 與 `proto2/examples/memory/`。
記憶世界再放 `config.json`、`requirements.txt` 與自己的 `.gitignore`。
`Ctx` 增加 `history_read`、`history_replace`、`mem_send`、`mem_take`、
`ref_save`、`ref_read`。工具包只走這些把手，不自己摸 agent 狀態。
`state.json` 增加待收的記憶請求與只展開一輪的指標清單。
agent 的 `tools.json` 加 `big_memory` 包。
`aos-agent` 在 `act` 寫工具結果前加自動摺疊，在每格開頭收記憶結果。
`.gitignore` 忽略 `.venv/`、`refs/`、請求結果、執行紀錄與 MongoDB 密碼檔。
空的範例設定可以進版控，真的連線字串不能進。

## 現在故意不做

- 向量搜尋與 embedding。
- 多個記憶世界互相同步。
- 細緻的跨 agent 閱讀權限。
- 同一請求重送時的去重。
- MongoDB 欄位改版與舊資料搬家。
- 備份、到期清除與保證徹底抹除。
- 兩個程序同時改 `prompts.json`。
- 循環 `$ref`、指標互相指來指去。
- 指標目標被搬走、刪掉或內容被改。
- 不是 JSON 的大檔、二進位檔與串流展開。

## 要使用者拍板

- **T-45**：先做 B，再做 A？建議是，先立刻省 context，也先定好共同指標。
- **T-46**：記憶世界用自己的 `venv + pymongo`？建議是，`mongosh` 只給人檢查。
- **T-47**：所有 agent 共用一個 collection，再用 `agent` 欄位區分？建議是。
- **T-48**：大 JSON 超過 6000 字就摺到本地，長期內容才進 MongoDB？建議是。
- **T-49**：40000 字先歸檔原文再摘要，80000 字停問模型並硬歸檔？建議是。
- **T-50**：沒有 MongoDB 時先做 SQLite 退路？建議是，先不做純 JSON 主庫。
