### 教學 flavor

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）| 分辨 |
|--------------|--------|-------------------|------|
| 「這個我完全看不懂，用白話講」「不要一堆縮寫」「先講為什麼」 | **plain-explain** | [workflows/plain-explain.md](workflows/plain-explain.md) | 產物是**文字**；讀者只要「讀懂」 |
| 「把這個主題做成互動網頁課程」「弄一個可以操作的教學網站」 | **study-site** | [workflows/study-site/README.md](workflows/study-site/README.md) | 產物是**可操作的網站**；讀者要「動手做出來」 |
| 「這門課的講解太薄，讀不懂」「幫既有的課加厚文字」 | **study-site / enrich** | [workflows/study-site/enrich-existing.md](workflows/study-site/enrich-existing.md) | 網站**已存在且互動能動**，只改文字，不動互動與版面 |
| 「把做好的課掛上去給人看」 | **study-site / publish** | [workflows/study-site/publish.md](workflows/study-site/publish.md) | 內容已驗收完；這步只處理**發布**，不改內容 |

例：「幫我讀懂資料庫索引」——只要我自己看懂 → knowledge 包的 digest；要寫成別人也讀得懂的講解 → plain-explain；要做成能改參數、看查詢成本跟著變的課 → study-site。plain-explain 的產物可直接當 study-site 的內容來源。
