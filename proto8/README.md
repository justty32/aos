# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 [proto7](../proto7/README.md)、[proto7-2](../proto7-2/README.md)

2026-10-11 開。起因：使用者看完 proto7-2 之後說「整個都不對，太繁複」，又回頭看了八月到十月的沿革，結論是**做得太快**——像遙控飛機，兩次操作之間已經飛了好長一段。方向其實一直在他手上，只是目標一直在變；這兩個月的程式當探針有價值，但不是成品。

**程式**在 [lib/](lib/README.md)（Python）：inst、loop、daemon、fsm、agent 格庫、kernel、tasks（seq／par／if）、時鐘 tick。圖解版兩頁：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。**現在以 [CONCEPTS.md](CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-61、兩個例子的邊緣、16 條還沒接起來的；只收使用者說過的）。實作上的想法在 [restart §3g](thinking/2026-10-11-restart.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環），還沒變成程式。PLAN（實作層提案，10-11 擱置）10-15 深夜使用者「刪掉」，已刪（在 git）。

## 入口

- **[NORMS.md](NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；語法糖符合規範但不強制。
- **10-16 新設計（程式還沒改）**：定義（食譜，一個 `.aos/` 資料夾）＋stack（廚房，cwd；10-16 夜改名，原叫工作區）用 `.aos` 捷徑接，一律 `aos exec stack 定義`；10-16 夜 stack 與使用者的工作區分開、工作區位置＝環境變數 `AOS_WS`（C-65～C-67、N-55、N-56）；stdin 是正規入口、argv 是語法糖；agent 不造 args.json／ret.json／frame.json；工具＝定義資料夾、地址是相對捷徑、不用 PATH → [C-57～C-61](CONCEPTS.md)、[N-46～N-51](NORMS/10-基礎設施-定義與工作區.md)。
- **[lib/](lib/README.md)**：函式庫（inst、loop、daemon、fsm、agent、kernel、tasks、tick；10-15 深夜 proto8-1 併進來）。
- **[bin/](bin/aos)**：薄入口 `aos`（`aos <名> …`＝`python3 lib/aos_<名>.py …`、`aos agent …`、`aos brain openai …`）；放進 PATH，inst 的 argv 就寫指令名（C-50；10-16 起定義之間互指不靠 PATH，C-61）。跟 C++ 的 aos 執行檔同名不相干。
- **[demo/](demo/README.md)**：`python3 proto8/demo/run.py`，daemon 從起到收走一遍、每條指令和回覆都印出來。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 [proto7 核心 spec](../proto7/spec/core.md) 與 [設計原則](../proto7/notes/principles.md)。
- 使用者自己的草稿：[thinking/（repo 頂層）](../thinking/)（2026-09-19～24）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10-11-restart.md](thinking/2026-10-11-restart.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS 與 NORMS 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 N-12、C-48（指示詞只是拆檔便利）、KISS、層徹底切割、少用 sh，不合的打回，不原樣端給使用者。
