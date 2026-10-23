# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 [proto7](../proto7/README.md)、[proto7-2](../proto7-2/README.md)

2026-10-11 開。起因：使用者看完 proto7-2 之後說「整個都不對，太繁複」，又回頭看了八月到十月的沿革，結論是**做得太快**——像遙控飛機，兩次操作之間已經飛了好長一段。方向其實一直在他手上，只是目標一直在變；這兩個月的程式當探針有價值，但不是成品。

**程式**：10-23 起 aos-exec、aos-loop、aos-fsm、aos-daemon 只有 C++ 版 [impls/](impls/README.md)（使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python；Python 版刪了，C++ 是唯一實作）；[bin/](bin/README.md) 只剩 aos-tick（Python）；範例在 [demo/](demo/README.md)（agent-bob、agent-ann；daemon、tick）。〔10-23 前：程式在 bin/（aos-exec、aos-loop、aos-fsm；inst 是庫，aos-inst 命令列 10-22 刪；10-19 從 proto8-2 併進來；aos-daemon 10-20、aos-tick 10-21 晚）。〕圖解版兩頁（2026-10-20 已更新到現況）：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。**現在以 [CONCEPTS.md](CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-73，作廢的號只留在表上；只收使用者說過的）。實作上的想法在 [restart §3g](thinking/2026-10-11-restart.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環）。

## 現況（2026-10-19 併入 proto8-2 後）

使用者 10-19 定：**資料夾＝程式**，入口 `$AOS_ENTRY`（預設 `_entry`；10-19 晚改，原 `.aos/exec`；10-23 改名，原 `_exec`；[ideas § 13](thinking/2026-10-19-ideas.md)），aos 只訂環境變數（早上三個：`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`；下班前加 `AOS_CF`、`AOS_CD` 成五個；10-21 晚加 `AOS_CO` 成六個）和一支 `aos-exec`（早上 `aos-exec DIR [WS]`，下班前放寬成 `aos-exec XXX [WS [args...]]`；10-21 改收旗標 `aos-exec [--ws WS] XXX [args...]`，[ideas 10-21](thinking/2026-10-21-ideas.md)）；巢狀由程式自己訂子 stack；這次要做啥隨意。10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，原話與裁定在 [thinking/2026-10-19-ideas.md](thinking/2026-10-19-ideas.md)（使用者：「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」）。程式照這個做完：agent-bob 叫 cathy 叫 stamp 四層、agent-ann 全內嵌對照（早上那版測試 65 個，晚上改完 93 個）。

**10-19 下班前～晚再定**（[ideas § 14～§ 21](thinking/2026-10-19-ideas.md)）：入口放寬成四種（可執行檔、inst 單子、argv 陣列、`js[$AOS_ENTRY]` 的值——單子、陣列或字串路徑；C-73）、`aos-exec XXX`（XXX 可為資料夾、檔、`檔#/指標`，找不到補 `XXX.json`；N-58、N-61）、環境變數加 `AOS_CF`／`AOS_CD` 成五個（N-57）、`#/` 尋址（N-62）；impls 只提供 `aos-exec` 一支命令列（§ 23 之後也有 aos-loop、aos-fsm，10-21 加 aos-daemon）、inst 是 C lib、JSON 不進 C 庫（§ 20）；`+x` 但沒 `#!` 的檔——入口兩種與單子的 `argv[0]`——三處一致改用 `/bin/sh` 跑（§ 21「不擋」、§ 22「乙」）。**兩版實作都做完了**：`proto8/impls/aos-exec`（使用者假日寫的 C++ 參考實作，10-23 起進 git；45 組測試）與 `proto8/bin`（Python；aos-exec 10-19 晚從 sh 改寫成 Python，使用者 § 21「舊版一起改」；測試 93 個，§ 24 補 loop／fsm 轉訊號與 PATH 原樣後 100 個）。兩版仍不同的只有（10-22 後 aos-inst 已不是差異，代號待補；impls 在子行程呼叫 `run_cli` 使用者接受，見 NORMS/10 開頭）：impls 有 aos-exec、aos-loop、aos-fsm 三支命令列（§ 23；10-21 加 aos-daemon 成四支）、沒有 aos-inst、單子交給 C lib；bin 版原本另保留 aos-inst 命令列（10-22 刪，同 impls 只剩庫）、單子在行程內呼叫 `aos_inst.run()`；錯誤一行兩版都帶代號（10-22 使用者要 bin 也帶，10-23 照 impls 補齊）；10-21 的改動 impls 10-21 晚都對齊了，bin 版 10-21 晚新做的 aos-tick impls 沒有（[NORMS/10](NORMS/10-基礎設施-定義與工作區.md) 開頭）。〔10-23 註：bin 版 aos-exec、aos-loop、aos-fsm、aos-daemon 刪了（使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python），只剩 impls 一版。〕

**舊 lib 已刪進 git 歷史**（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick；27 支模組＋說明＋169 個測試＋六組 demo＋舊 `bin/aos`）：要找回用 `git show 5546be29:proto8/lib/README.md`（5546be29 是刪除前最後一個有它的 commit）。kernel、tasks、tick、腦的工具呼叫現在**沒有實作**（daemon 10-20 已照新做法重寫，10-23 起只剩 impls 的 `aos-daemon`；tick 10-21 晚也重寫了，`bin/aos-tick`），概念與規範留著、標「現無實作」，等照新做法重寫（[NORMS 待定](NORMS/08-待定.md)）。

## 入口

- **[CONCEPTS.md](CONCEPTS.md)**：概念——aos 怎麼看世界（C-01～C-73）。
- **[NORMS.md](NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；程式符合規範但不強制。10-19 新的底在 [NORMS/10](NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62：六個環境變數（10-21 晚加 `AOS_CO`）、`aos-exec XXX`、找入口、`#/` 尋址）。
- **[CONVENTION.md](CONVENTION.md)**：aos agent 慣例（P-05～P-40）——我們自己人寫 agent 時照抄的標準形狀，不要求別人守。
- **[bin/](bin/README.md)**：10-23 起只剩 aos-tick（Python）；原本的 aos-exec、aos-loop、aos-fsm、aos-daemon 與 inst 庫 aos_inst.py 等 10-23 刪了（使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python；在 git 歷史）。**[impls/](impls/README.md)**：使用者假日的 C／C++ 參考實作（10-23 起進 git，也是 10-23 起唯一的實作），提供 aos-exec、aos-loop、aos-fsm、aos-daemon 四支命令列，10-21 已對齊 bin 版 10-20（daemon 照新做法重寫、指示詞與 argv D1～D15），10-21 晚再對齊 bin 版 10-21 傍晚（aos-exec 的旗標與 `.env`、設定檔是唯一參數、loop 的 `run`／fsm 格的 `val` 可以是陣列〔10-23 統合一度把 `run` 改名 `val`，同晚使用者改回（「只有 loop、daemon 用 run」），[thinking](thinking/2026-10-23-naming.md)〕、daemon 經 aos-exec、`$path` 字串拼接）；刻意沒有 aos-inst 命令列，也沒有 aos-tick。
- **[demo/](demo/README.md)**：`sh proto8/demo/run.sh`，agent-bob 與 agent-ann 各跑一遍。
- **tests/**：`python3 -m unittest discover -s proto8/tests`。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- **[notes/](notes/README.md)**：AI 寫的參考筆記（不是規範、不算數）：拿外面現成的東西跟 aos 對照，例如 [跟 s6、runit 的對照](notes/s6-runit.md)（2026-10-22）。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 [proto7 核心 spec](../proto7/spec/core.md) 與 [設計原則](../proto7/notes/principles.md)。
- 使用者自己的草稿：[thinking/（repo 頂層）](../thinking/)（2026-09-19～24）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10-11-restart.md](thinking/2026-10-11-restart.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS、NORMS 與 CONVENTION 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 C-48（指示詞只剩 $env）、C-68～C-70（資料夾＝程式、aos 只訂環境變數）、KISS、層徹底切割、少用 sh，不合的打回；跟原則相撞的帶著衝突來問使用者（wf user.md「規劃交給 fable、只把衝突帶給他」），不原樣端給使用者。
