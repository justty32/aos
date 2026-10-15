# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 [proto7](../proto7/README.md)、[proto7-2](../proto7-2/README.md)

2026-10-11 開。起因：使用者看完 proto7-2 之後說「整個都不對，太繁複」，又回頭看了八月到十月的沿革，結論是**做得太快**——像遙控飛機，兩次操作之間已經飛了好長一段。方向其實一直在他手上，只是目標一直在變；這兩個月的程式當探針有價值，但不是成品。

**程式**在 [lib/](lib/README.md)（Python）：指示詞 lib、inst、loop、daemon。圖解版兩頁：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。**現在以 [CONCEPTS.md](CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-43、兩個例子的邊緣、16 條還沒接起來的；只收使用者說過的）。實作上的想法在 [restart §3g](thinking/2026-10-11-restart.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環），還沒變成程式。[PLAN.md](PLAN.md) 是實作層提案，10-11 擱置（高度錯，見 診斷（已刪：AI 產出，使用者 10-12 夜要求刪除））。

## 入口

- **[NORMS.md](NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；語法糖符合規範但不強制。
- **[lib/](lib/README.md)**：函式庫：指示詞 lib、inst、loop、daemon。
- **[bin/](bin/aos)**：薄入口 `aos`（`aos <名> …`＝`python3 lib/aos_<名>.py …`、`aos agent …`、`aos brain openai|ollama …`）；放進 PATH，inst 的 argv 就寫指令名（C-50）。跟 C++ 的 aos 執行檔同名不相干。
- **[proto8-1](../proto8-1/README.md)**：tasks——在 aos_inst 之上的小程式（aos-seq、aos-par、aos-if、aos-not），用這裡的 lib。
- **[demo/](demo/README.md)**：`python3 proto8/demo/run.py`，daemon 從起到收走一遍、每條指令和回覆都印出來。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 [proto7 核心 spec](../proto7/spec/core.md) 與 [設計原則](../proto7/notes/principles.md)。
- 使用者自己的草稿：[thinking/（repo 頂層）](../thinking/)（2026-09-19～24）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10-11-restart.md](thinking/2026-10-11-restart.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
