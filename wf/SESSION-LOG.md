# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **proto8（主線）**：10-11 使用者三輪口述已記進 [restart](../proto8/thinking/2026-10-11-restart.md)（§3c～§3h、§3g.1～3g.14），定下的進 [CONCEPTS](../proto8/CONCEPTS.md)；圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。PLAN 擱置（[診斷](../proto8/thinking/2026-10-11-why-wrong.md)）。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。10-12 使用者說 AI 問的四題沒用，questions.md 已刪，不再追。10-12 照使用者選的「先看懂現有 code」做了一頁現況導覽（daemon／tick-tock／C++ loop，只描述不提改法）：https://claude.ai/artifact/LueXKAUcH7bAhYNjCKfwvz ，使用者看完說「就這樣」。10-12 使用者說 proto8 開工、用 Python：指示詞 lib 已從 proto7-2 拿進 [proto8/lib](../proto8/lib/README.md)，同日照使用者要求精簡成一檔：只留 $ref／$at／$env，入口 `resolve(doc, base_dir)` 解整份。接著 inst（[aos_inst.py](../proto8/lib/aos_inst.py)）：選項改平的 key、基準 `--base inst|cwd`、跑法最小；之後使用者改：拿掉 --base 一律呼叫者 cwd、cwd 沒寫就繼承、串流從 cwd 算；結束碼分工＝子程式的碼只進 exit 檔、命令列 0／1 只說 aos_inst 自己；exit 寫不進去不管；加 timeout_ms、timeout_grace_ms；被訊號停掉不代寫 exit；之後使用者要求 proto8 測試全刪（殘留過去的想法），目前沒有測試。還沒搬：process group、直接跑普通檔、-- 參數、起了就走、字串進出、_metainfo、AOS_DIRNAME，等他挑。
- 10-12 清帳（使用者說）：proto7-2 頭腦風暴題（抽屜／選單／32 份文件）忽略、不再追；WAIT_USER 舊帳全清；proto6 不管。10-10 留下的待辦候選（astra-8 剩項、包間互相 import、轉址 stub 等）屬 proto7-2，一併不追，原文見 [10-12 封存](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
