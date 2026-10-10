# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-10（家機，頂層；使用者要 compact 後換 Fable 做頭腦風暴）：今天全部進 main 並 push：AP5（學徒讀自己技能書**證明有效**）、FX1／FX2（astra-8 前四項＋daemon 存檔失敗不推進）、MN1／MN2／MN4（選單包、學徒選單、文件）、MN3（選單 A／B：**選單輸**，一次交整包 12/15 vs 選單 2/15、token 1.8 倍，機制收下不推進 brain）、TD1／TD2／TD3（程式拆檔＋共用 helper、proto7-2 文件索引與封存、wf 與工作區整理）。代定全在 [decisions-2026-10-10](../proto7-2/notes/decisions-2026-10-10.md)。狀況頁已 ELI5 重寫：今日戰況 https://claude.ai/artifact/7EYfkiF2J2A5gR5najZ1Je 、時空架構 https://claude.ai/artifact/2xGg4szocuGaRrpQHpt2W5 、現況 https://claude.ai/artifact/UYJCNJfx5XfcP7bda7gzHK 、資料夾佈局 https://claude.ai/artifact/QNNLmDa2ebRTxS7H1fZWR3 、JSON 樣本 https://claude.ai/artifact/VteK24uuTCMvkahn8YuJEC ；程式地圖系列：總覽 https://claude.ai/artifact/C91mwRAauXsPRAAuQWKmWq 、核心 https://claude.ai/artifact/R3ypmiVbskhC5WpUoorfp1 、包目錄 https://claude.ai/artifact/DH1FzuKmBfRHBZWQHNr3Tc 、工具包 https://claude.ai/artifact/LNrNJzC4Xbtu6z3pFh2Y1W 、功能選項 https://claude.ai/artifact/8ontywurM7NJ9DkTCngfGC （HTML 源在 scratchpad/pages，生成腳本 scratchpad/src-pages、code-src）。**頭腦風暴素材**：思想文件目錄 [thinking-catalog](../proto7-2/notes/thinking-catalog.md)（32 份，拆／封存等頭腦風暴後再決定；spec 疊 16 份屬歷史但連結數百）；抽屜與信件 [ideas＋使用者回覆](../proto7-2/notes/intents/drawers-and-mail-ideas.md)；選單走向（只用於修檔導航？切題機制留不留？）見 [menu-ab](../proto7-2/notes/play/2026-10-10-menu-ab/README.md)。**待辦候選**：抽屜做成標準工具包（排序與 kernel 規則一起設計）＋12 封信 A／B；astra-8 剩下 B／C 條目（含 up.json 重跑洗掉手加欄位 A10-05）；TD1 記下：包之間已有大量互相 import（違「只經檔案」原則）、三個轉址 stub 待排移除、mail INTERNALS.md:24 過時。下次開多隊時全套測試要排隊（今天四份同時跑拖慢）。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)，其餘已做完或併進上一條的下一步候選）：合併用 `../aos-wt/merge.sh <分支>`；數全套份數用 `ps -eo args | grep -c '^/usr/bin/python3 \(-B \)\?proto7-2/tests/run_all.py'`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。
- 10-04（proto7-2）等使用者看 W1～W12（程式照推薦，推薦不等於已確認），`proto7/user-advice.md` 使用者還會改、未 commit [→](session_logs/2026-10/2026-10-04.md#2026-10-04)
- 10-03（proto7-1）等使用者看：S-21 原文「daemon 核心不知道從屬」與新加的所有權句字面有點擰 [→](session_logs/2026-10/2026-10-03.md#2026-10-03)
- 10-02～10-03（proto6，已非主線）等使用者：thread-vs-process 五題、astra-alt 先做哪個實驗、plan 擱置題（node／peers／hooks／C++11）；使用者說之後再談 [→](session_logs/2026-10/2026-10-03.md#2026-10-03) [→](session_logs/2026-10/2026-10-02.md#2026-10-02)
- 已結或被取代（10-10 判定，全文已搬，不再追）：10-05、10-04 傍晚、10-03 深夜、10-02 超標檔、09-25、09-21／09-22、09-09、09-06～08、09-05、08-28 → [session_logs/2026-10](session_logs/2026-10.md)、[session_logs/](session_logs/README.md)

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
