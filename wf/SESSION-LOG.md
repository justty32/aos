# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-10（家機，頂層；使用者要 compact 後換 Fable 做頭腦風暴）：今天進 main 並 push：AP5（學徒讀自己技能書**證明有效**）、FX1（astra-8 前四項）、FX2（daemon 存檔失敗不推進）、MN1（選單包 packs/menu）、MN4（選單 README／ADVANCED、新手過）、MN2（學徒改走選單，冒煙 3/3）；抽屜與信件方向題使用者已答（[ideas 末段](../proto7-2/notes/intents/drawers-and-mail-ideas.md)）；代定全在 [decisions-2026-10-10](../proto7-2/notes/decisions-2026-10-10.md)。**還在背景跑的三條**：① MN3（分支 loop14/MN3，worktree ../aos-wt/MN3；切題機制已 commit 0419274e，A／B 30 組在 ../aos-wt/MN3.ab 跑，上限 300 萬 token）→ 完成後 `../aos-wt/merge.sh loop14/MN3`；② 三張狀況頁 ELI5 重寫（產出在 scratchpad/pages/{today,arch,status}.html＋可能的分頁）→ 發布到原網址：今日戰況 https://claude.ai/artifact/7EYfkiF2J2A5gR5najZ1Je 、時空架構圖解 https://claude.ai/artifact/2xGg4szocuGaRrpQHpt2W5 、現況圖解 https://claude.ai/artifact/UYJCNJfx5XfcP7bda7gzHK （新分頁另發，連結占位 `#PAGE-<檔名>` 發布後替換再重發）；③ 新的「程式架構」系列（scratchpad/pages/code*.html：總覽＋核心／包目錄／工具包／功能選項分頁）→ 新發布並替換占位。使用者要求：讓他掌握全局、多用圖、ELI5、要有資料夾佈局與 JSON 格式、裝不下就拆多張。發布完把所有連結給使用者。scratchpad＝/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/0fed37b2-da4e-4eb9-b5b2-4f5659a08058/scratchpad 。**下一步候選**：選單 A／B 結論後決定選單走向；抽屜做成標準工具包（排序與 kernel 規則一起設計）＋Fable 提的 12 封信 A／B 小實驗；astra-8 剩下的 B／C 條目。
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
