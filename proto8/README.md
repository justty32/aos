# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 [proto7](../proto7/README.md)、[proto7-2](../proto7-2/README.md)

2026-10-11 開。起因：使用者看完 proto7-2 之後說「整個都不對，太繁複」，又回頭看了八月到十月的沿革，結論是**做得太快**——像遙控飛機，兩次操作之間已經飛了好長一段。方向其實一直在他手上，只是目標一直在變；這兩個月的程式當探針有價值，但不是成品。

## 頂層一覽（2026-10-26 整理結構）

| 資料夾 | 收什麼 |
|---|---|
| [docs/](docs/README.md) | 使用者條文：[CONCEPTS](docs/CONCEPTS.md)（概念）、[NORMS](docs/NORMS.md)（規範）、[CONVENTION](docs/CONVENTION.md)（agent 慣例） |
| [impls/](impls/README.md) | 主實作：aos-exec、aos-loop、aos-fsm、aos-daemon 等 C++ 專案（各自 CMake；`build/`、`bin/`、`lib/` 是建置產物、不進 git） |
| [bin/](bin/README.md) | aos-tick（唯一留著的 Python 版） |
| [lib/](lib/README.md) | 工具庫：agent 用的工具（底層原語 → 動 aos 的 → 整隻 agent），demo 用相對捷徑引用 |
| [extras/](extras/README.md) | 周邊工具：給人用的 say／listen、給 AI 用的 aos-ai、aos-grow、Janet／Lua 寫 aos、nvim 外掛、aos-sandbox |
| [demo/](demo/README.md) | 範例 agent 與 `run.sh` |
| [topdown/](topdown/README.md) | 10-25 由上而下拆的試驗（甲隊 galtxt-a、乙隊 galtxt-b） |
| `tests/` | `python3 -m unittest discover -s proto8/tests`（先建 impls） |
| [thinking/](thinking/README.md) | 討論紀錄（使用者原文、決定、結論） |
| [notes/](notes/README.md) | AI 寫的參考筆記（不算數） |
| `user-advice/` | 使用者自己的意見稿 |

舊紀錄裡 proto8 頂層的 CONCEPTS／NORMS／CONVENTION 現在在 `docs/`，human／ai_tools／grow／langs／editors／sandbox 現在在 `extras/`；讀舊紀錄時照這張表換路徑。

**以 [CONCEPTS.md](docs/CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-73，作廢的號只留在表上；只收使用者說過的）。圖解兩頁（10-20 的狀態）：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。實作上的想法在 [restart §3g](thinking/2026-10-11-restart.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環）。

## 現況

- **資料夾＝程式**（使用者 10-19 定）：入口 `$AOS_ENTRY`（預設 `_entry`，[ideas § 13](thinking/2026-10-19-ideas.md)）；aos 只訂環境變數——`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO` 六個（N-57）——和一支 `aos-exec [--ws WS] XXX [args...]`（[ideas 10-21](thinking/2026-10-21-ideas.md)）；巢狀由程式自己訂子 stack；這次要做啥隨意。10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，原話與裁定在 [thinking/2026-10-19-ideas.md](thinking/2026-10-19-ideas.md)（使用者：「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」）。範例：agent-bob 叫 cathy 叫 stamp 四層、agent-ann 全內嵌對照。
- **入口與尋址**（[ideas § 14～§ 21](thinking/2026-10-19-ideas.md)）：入口四種（可執行檔、inst 單子、argv 陣列、`js[$AOS_ENTRY]` 的值——單子、陣列或字串路徑；C-73）；`aos-exec XXX` 的 XXX 可為資料夾、檔、`檔#/指標`，找不到補 `XXX.json`（N-58、N-61）；`#/` 尋址（N-62）；inst 是 C lib、JSON 不進 C 庫（§ 20）；`+x` 但沒 `#!` 的檔——入口兩種與單子的 `argv[0]`——三處一致用 `/bin/sh` 跑（§ 21「不擋」、§ 22「乙」）。
- **實作**：[impls/](impls/README.md) 是唯一實作（使用者假日寫的 C／C++ 參考實作；使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也用 C++、tick 先留 Python，[bin/](bin/README.md) 只有 aos-tick），命令列有 aos-exec、aos-loop、aos-fsm、aos-daemon 等（全表見它的 README）；刻意沒有 aos-inst 命令列，也沒有 aos-tick。impls 在子行程呼叫 `run_cli`，使用者接受（[NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md) 開頭）；錯誤一行帶代號。loop／daemon／fsm 格「要跑什麼」那一格叫 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」，[thinking](thinking/2026-10-23-naming.md)）。
- **舊 lib 已刪進 git 歷史**（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick；27 支模組＋說明＋169 個測試＋六組 demo＋舊 `bin/aos`）：要找回用 `git show 5546be29:proto8/lib/README.md`（5546be29 是刪除前最後一個有它的 commit）。kernel、tasks 現在**沒有實作**，概念與規範留著、標「現無實作」，等照新做法重寫（[NORMS 待定](docs/NORMS/08-待定.md)）；daemon 是 impls 的 `aos-daemon`，tick 是 `bin/aos-tick`，腦的工具呼叫範本是 [demo/agent-dan](demo/README.md)、慣例 [P-41](docs/CONVENTION.md)。

## 入口

- **[CONCEPTS.md](docs/CONCEPTS.md)**：概念——aos 怎麼看世界（C-01～C-73）。
- **[NORMS.md](docs/NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；程式符合規範但不強制。底在 [NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62：六個環境變數、`aos-exec XXX`、找入口、`#/` 尋址）。
- **[CONVENTION.md](docs/CONVENTION.md)**：aos agent 慣例（P-05～P-41）——我們自己人寫 agent 時照抄的標準形狀，不要求別人守。
- **[demo/](demo/README.md)**：`sh proto8/demo/run.sh`，跑 agent-bob、agent-ann、agent-dan（假腦叫一次 clock 工具）與 daemon、tick 等段。
- **10-24 一天的嘗試**（使用者「我隨便說，你隨便做，反正只是嘗試」；代定都可翻案，一覽在 [session log 10-24](../wf/session_logs/2026-10/2026-10-24.md)）：[lib/](lib/README.md)（工具＝函式庫；跟上面「舊 lib」是不同的東西）、[human/](extras/human/README.md)（給人用的 say／listen）、[ai_tools/](extras/ai_tools/README.md)（給 AI 用的 aos-ai）、[grow/](extras/grow/README.md)（函數成長 aos-grow）、[langs/](extras/langs/README.md)（Janet、Lua 寫 aos）、[editors/nvim/](extras/editors/nvim/README.md)、[sandbox/](extras/sandbox/README.md)（Linux 權限與沙箱）；demo 多了十幾隻 agent 與 talk、self-improve、kernel-llm 等，見 [demo/](demo/README.md)。
- **tests/**：`python3 -m unittest discover -s proto8/tests`。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- **[notes/](notes/README.md)**：AI 寫的參考筆記（不是規範、不算數）：拿外面現成的東西跟 aos 對照，例如 [跟 s6、runit 的對照](notes/s6-runit.md)。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 [proto7 核心 spec](../proto7/spec/core.md) 與 [設計原則](../proto7/notes/principles.md)。
- 使用者自己的草稿：[thinking/（repo 頂層）](../thinking/)（2026-09-19～24）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10-11-restart.md](thinking/2026-10-11-restart.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS、NORMS 與 CONVENTION 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 C-48（指示詞只剩 $env）、C-68～C-70（資料夾＝程式、aos 只訂環境變數）、KISS、層徹底切割、少用 sh，不合的打回；跟原則相撞的帶著衝突來問使用者（wf user.md「規劃交給 fable、只把衝突帶給他」），不原樣端給使用者。
