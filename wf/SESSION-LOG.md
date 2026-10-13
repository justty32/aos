# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **proto8（主線）**：已完成的（概念、inst／loop／daemon、tasks、aos-tick、NORMS）細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)；原文逐字在 [10-13 封存](session_logs/2026-10/2026-10-13.md)。PLAN 擱置。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。使用者說之後再說／不做：指定時間跑、Linux 權限、AOS_DIR、非同步啟動、retry／timeout／while／race。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- **proto8 10-12 夜 inst／loop／daemon 重做**：已 commit、測試全綠，定案見 [loop-daemon](../proto8/thinking/2026-10-12-loop-daemon.md)、[inst-json](../proto8/thinking/2026-10-12-inst-json.md)、[ctl-norms](../proto8/thinking/2026-10-12-ctl-norms.md)（原文在 [10-13 封存](session_logs/2026-10/2026-10-13.md)）。代理人想法記在 inst-json 稿，demo 今晚不做；「daemon 收工寫 stop」使用者說不管。**下一步等使用者開口。**
- **proto8 thinking 精簡**：10-12 夜使用者要求 thinking 只留原文整理、決策、結論、未決（規矩改在 [user.md](workflows/common/user.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。已刪 13 份整份 AI 產出、精簡其餘五份（[thinking 索引](../proto8/thinking/README.md)）；舊版見 git 22285099；10-12 三份精簡前的原版使用者說不留。
- **proto8 10-13**：`檔#/位置` 已做（D1；`#/` 統一照檔案系統 D1a）；`_metainfo` 格式自由、inst 的可選 key、通用寫法之後在規範定（D4、D5）；見 [json-path](../proto8/thinking/2026-10-13-json-path.md)。晚上做了重構拆檔＋tidy，報告 [tidy 10-13](workflows/tidy/reports/2026-10-13-proto8-wf.md)。之後改語音輸入（字可能聽錯，意思不明就確認），事情盡量派 agent 做、要思考的交 Fable agent。kernel／agent 概念見 [kernel-agent](../proto8/thinking/2026-10-13-kernel-agent.md)，細節等規劃 agent 時說。**下一步等使用者開口。**
- 10-12 清帳（使用者說）：proto7-2 頭腦風暴題（抽屜／選單／32 份文件）忽略、不再追；WAIT_USER 舊帳全清；proto6 不管。10-10 留下的待辦候選（astra-8 剩項、包間互相 import、轉址 stub 等）屬 proto7-2，一併不追，原文見 [10-12 封存](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
