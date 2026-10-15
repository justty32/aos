# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **意見 1～7 程式兩批都做完**（＋格沒輸出、同 frame 續聊兩題）；**待使用者定 8 題**（aos 入口、`aos agent fsm`、AOS_DEMO、同 frame 再叫要刪 ctl/ret、ctl_poll_ms、args.taken.json、cells 重複、真腦未跑）→ [10-15 § 待使用者定](session_logs/2026-10/2026-10-15.md#待使用者定動工自定最小可逆)。
- **10-15 收工**：使用者說「先大致到這邊……接下來是我要來做理解」→ 下一步等使用者讀完再開口。今日成果：主題分檔、fsm 規範＋實作、agent（工具＝inst、思考介面、系統提示、函數＋binding、當工具）、C-47／N-42 兩種 kernel 原型、C-48 JSON 規矩＋同像性；五份網頁已更新（https://claude.ai/artifact/<id>）：概念 QJjGNnKFhKeS7r1f5bHzu7、實作 ATizWpsmAa2qutXWZ2owjm、58 題 DKBifn39yRtYDGjwGEAzC5、inst/loop/daemon HGkzKJKAsEAwhv1dQPQX8d、aos-llm與fsm K2aQ7KCad1u3dFTfDvArda。等使用者看：各 thinking 的「動工自定點」（[llm-kernel](../proto8/thinking/2026-10-15-llm-kernel.md#動工自定點)、[general-kernel](../proto8/thinking/2026-10-15-general-kernel.md#動工自定點)、[json-families](../proto8/thinking/2026-10-15-json-families.md)、[topics/04-agent當函數](../proto8/thinking/2026-10-15-topics/04-agent當函數.md)、[judge-live2](../proto8/thinking/2026-10-15-judge-live2.md)）。open 候選：對話太長、agent 收信、標準實作、規範草稿定稿。細節 → [10-15](session_logs/2026-10/2026-10-15.md)。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)。PLAN 擱置。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- 已搬走（open 已解）：10-14 收工交棒、10-13 `檔#/位置`／kernel-agent、10-12 thinking 精簡與清帳 → [10-14](session_logs/2026-10/2026-10-14.md)、[10-13](session_logs/2026-10/2026-10-13.md)、[10-12](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
