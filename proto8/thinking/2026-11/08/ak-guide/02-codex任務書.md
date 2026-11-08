交給 codex gpt-6.1-sol 的施工任務書：照 01-內容稿把桌面入門頁做成單檔 HTML，並在 aos-arknights/index.html 頂端加一行連結。

# 任務：做桌面入門頁（照稿施工）

先讀：repo 根 `AGENTS.md`、`wf/workflows/common/user.md`（「artifact／說明頁風格」那格）。內容稿：`proto8/thinking/2026-11/08/ak-guide/01-內容稿.md`——**逐節照做，不增刪內容、不改結論句、不改數字**；稿沒寫到的只決定版面與視覺。

## 產出

1. `/home/lorkhan/Desktop/aos-arknights-入門.html`：單檔，CSS／JS 全 inline；圖全用 inline SVG（不要 mermaid、不要任何外部 URL、字型、CDN）。
   - 頂端：標題「aos × Arknights 入門」、一分鐘看懂三句、四色圖例、七節目錄、「全部展開／全部收合」兩鈕。
   - 七節：每節一張 SVG 圖 → 粗體結論一兩句 → 一或多個 `<details>`（摺疊內容照稿）。正文不寫大段文字。
   - 四色意思全頁固定：灰＝腳本、藍＝LLM、綠＝規則、橘＝閘／停下。淺色與深色主題都要看得清楚（`prefers-color-scheme`，SVG 用 CSS 變數或 class 上色，別寫死黑字）。
   - 手機 400px 寬不可橫向捲動：SVG 用 `viewBox`＋`width:100%; height:auto`；寬圖在手機上改直向版（可以畫兩份 SVG 用 media query 切換），或確保字在縮小後仍 ≥11px 可讀。
   - SVG 裡的中文字不要擠出框：每個框先算好字數再定寬，長句拆兩行。
   - 頁尾一行照稿，連 `aos-arknights/index.html`（相對路徑）。第 7 節的桌面網站路徑做成相對連結；repo 與試驗場路徑只寫成文字（`<code>`），不做連結。
2. `/home/lorkhan/Desktop/aos-arknights/index.html`：**只加一行**——在 `<header class="masthead">` 的 `<div class="shell">` 內、`<p class="eyebrow">` 之前加：
   `<p class="lead"><a href="../aos-arknights-入門.html">看不懂？先看入門頁（一頁看懂整套）→</a></p>`
   其他一個字都不要動（另一條線也在改這個站）。改之前先重讀檔案現況。

## 規矩

- 不寫測試、不產驗證／截圖／佐證檔；不改 repo 裡任何檔；不 commit。
- 完成條件：兩個檔都寫好；`python3 -m html.parser` 讀得過（或用 `python3 -c "import html.parser,sys; html.parser.HTMLParser().feed(open(sys.argv[1]).read())" <檔>`）；頁內相對連結指到存在的檔；內容與稿一致。
- 做完在回覆裡列：七節各畫了什麼、有沒有照稿做不到的地方。
