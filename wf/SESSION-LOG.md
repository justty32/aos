# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **意見 1～7 程式兩批都做完**（＋格沒輸出、同 frame 續聊、第二批 6 個自定點都已拍板並照做，N-44 新增）；剩真腦（LM Studio）實跑未做 → [10-15 § 拍板](session_logs/2026-10/2026-10-15.md#第二批自定點的拍板10-15使用者派去處理吧都按照推薦45-用主控的推薦)。
- **10-15 收工**：使用者說「先大致到這邊……接下來是我要來做理解」→ 下一步等使用者讀完再開口。今日成果：主題分檔、fsm 規範＋實作、agent（工具＝inst、思考介面、系統提示、函數＋binding、當工具）、C-47／N-42 兩種 kernel 原型、C-48 JSON 規矩＋同像性；五份網頁已更新（https://claude.ai/artifact/<id>）：概念 QJjGNnKFhKeS7r1f5bHzu7、實作 ATizWpsmAa2qutXWZ2owjm、58 題 DKBifn39yRtYDGjwGEAzC5、inst/loop/daemon HGkzKJKAsEAwhv1dQPQX8d、aos-llm與fsm K2aQ7KCad1u3dFTfDvArda。等使用者看：各 thinking 的「動工自定點」（[llm-kernel](../proto8/thinking/2026-10-15-llm-kernel.md#動工自定點)、[general-kernel](../proto8/thinking/2026-10-15-general-kernel.md#動工自定點)、[json-families](../proto8/thinking/2026-10-15-json-families.md)、[topics/04-agent當函數](../proto8/thinking/2026-10-15-topics/04-agent當函數.md)、[judge-live2](../proto8/thinking/2026-10-15-judge-live2.md)）。open 候選：對話太長、agent 收信、標準實作、規範草稿定稿。細節 → [10-15](session_logs/2026-10/2026-10-15.md)。
- **兩條總原則（10-15）**：C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的已寫進設計理念；跟現有規範／lib 不完全合的 9 處＋文件小矛盾列在 [thinking 原則](../proto8/thinking/2026-10-15-principles.md#未決跟兩條原則不完全合的地方ai-盤點附推薦等使用者看)，第 1、3、8、9 條與「正常退出」S1～S5 已拍板並照做（10-15 晚，[§ 實作](session_logs/2026-10/2026-10-15.md#兩條總原則的盤點拍板與實作10-15-晚使用者都同意都按照推薦)）；新的待定 A～C 也已定並照做（結束碼只剩 0／1、訊號記 `signal`）；其餘（2、4～7）等使用者看；「kernel 評估納入錯誤路徑」記在 NORMS 待定。
- **命名（10-15）**：C-54、C-55、[縮寫表 abbr.json](../proto8/CONCEPTS/abbr.json)；盤點 P1～P7、M1～M9 與原值 `val` 使用者「都按照推薦」，10-15 晚全照做（4 個 commit）；open：AI 實作時自定的 5 個小地方等使用者看 → [盤點 § 拍板與實作](../proto8/thinking/2026-10-15-naming/盤點.md#拍板與實作10-15-晚)。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)。PLAN 擱置。**「先做 demo」已開工**：畫家 demo [demo/paint](../proto8/demo/paint/README.md)（使用者 3g.10 的例子），自定點與 LiteLLM 實跑 5 題已拍板並做完 → [10-15 § 畫家 demo](session_logs/2026-10/2026-10-15.md#畫家-demo10-15-晚使用者先做-demo開工)；restart §4 列了他停在半路的幾處。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- 已搬走（open 已解）：10-14 收工交棒、10-13 `檔#/位置`／kernel-agent、10-12 thinking 精簡與清帳 → [10-14](session_logs/2026-10/2026-10-14.md)、[10-13](session_logs/2026-10/2026-10-13.md)、[10-12](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
