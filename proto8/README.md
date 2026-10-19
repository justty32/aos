# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 [proto7](../proto7/README.md)、[proto7-2](../proto7-2/README.md)

2026-10-11 開。起因：使用者看完 proto7-2 之後說「整個都不對，太繁複」，又回頭看了八月到十月的沿革，結論是**做得太快**——像遙控飛機，兩次操作之間已經飛了好長一段。方向其實一直在他手上，只是目標一直在變；這兩個月的程式當探針有價值，但不是成品。

**程式**：現在在 [bin/](bin/README.md)（aos-exec、aos-inst、aos-loop、aos-fsm；10-19 從 proto8-2 併進來）與 [demo/](demo/README.md)（agent-bob、agent-ann）。圖解版兩頁（舊，10-16 以前的想法）：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。**現在以 [CONCEPTS.md](CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-72，作廢的號只留在表上；只收使用者說過的）。實作上的想法在 [restart §3g](thinking/2026-10-11-restart.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環）。

## 現況（2026-10-19 併入 proto8-2 後）

使用者 10-19 定：**資料夾＝程式**，入口 `$AOS_ENTRY`（預設 `_exec`，必須是可執行檔；10-19 晚改，原 `.aos/exec`，[ideas § 13](thinking/2026-10-19-ideas.md)），aos 只訂三個環境變數（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`）和一支 `aos-exec DIR [WS]`；巢狀由程式自己訂子 stack；這次要做啥隨意。10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，原話與裁定在 [thinking/2026-10-19-ideas.md](thinking/2026-10-19-ideas.md)（使用者：「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」）。程式照這個做完：agent-bob 叫 cathy 叫 stamp 四層、agent-ann 全內嵌對照，測試 65 個。

**舊 lib 已刪進 git 歷史**（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick；27 支模組＋說明＋169 個測試＋六組 demo＋舊 `bin/aos`）：要找回用 `git show aa2fec1f:proto8/lib/README.md`（aa2fec1f 是刪除前最後一個有它的 commit）。daemon、kernel、tasks、tick、腦的工具呼叫現在**沒有實作**，概念與規範留著、標「現無實作」，等照新做法重寫（[NORMS 待定](NORMS/08-待定.md)）。

## 入口

- **[CONCEPTS.md](CONCEPTS.md)**：概念——aos 怎麼看世界（C-01～C-72）。
- **[NORMS.md](NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；程式符合規範但不強制。10-19 新的底在 [NORMS/10](NORMS/10-基礎設施-定義與工作區.md)（N-57～N-60：三個環境變數、`aos-exec`）。
- **[CONVENTION.md](CONVENTION.md)**：aos agent 慣例（P-05～P-39）——我們自己人寫 agent 時照抄的標準形狀，不要求別人守。
- **[bin/](bin/README.md)**：aos-exec、aos-inst、aos-loop、aos-fsm（10-19 從 proto8-2 併進來）。
- **[demo/](demo/README.md)**：`sh proto8/demo/run.sh`，agent-bob 與 agent-ann 各跑一遍。
- **tests/**：`python3 -m unittest discover -s proto8/tests`。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 [proto7 核心 spec](../proto7/spec/core.md) 與 [設計原則](../proto7/notes/principles.md)。
- 使用者自己的草稿：[thinking/（repo 頂層）](../thinking/)（2026-09-19～24）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10-11-restart.md](thinking/2026-10-11-restart.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS、NORMS 與 CONVENTION 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 C-48（指示詞只剩 $env）、C-68～C-70（資料夾＝程式、aos 只訂環境變數）、KISS、層徹底切割、少用 sh，不合的打回；跟原則相撞的帶著衝突來問使用者（wf user.md「規劃交給 fable、只把衝突帶給他」），不原樣端給使用者。
