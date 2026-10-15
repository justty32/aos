# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **10-15 收工後使用者意見（只記、未動工；下次開工先處理）**：
  1. fsm 要很單純：「當現在是A狀態的時候，執行指定inst，就這樣，那個狀態內部、inst內部的東西，fsm不該管。」（牽動 N-36～N-41、`aos_fsm.py`：running／error_from／max_fails／halted／last_error、格的 stdin 帶 fsm_state、N-40 外層 cfg 當預設，這些哪些該移出 fsm 待使用者定）
  2. agent 同理：「程式方面的實作可以擠在一坨，共用一些lib，但是在實際的資料夾布局和json那塊仍要保持單純」（牽動 `aos_agent_call.py`／`bob/` 定義＋frame＋cwd、tools／tools_append、`_tool`、system.md、clerk/ 等的資料夾與 JSON 是否太複雜，待重看）
  3. agent 結構：「agent基於狀態機，在某狀態下跑某個inst，所以複雜度主要集中在那些inst。然後agent call,binding那塊，我也希望不要用程式去實作，而是應該用現有的這套json+資料夾+inst機制去實現」（牽動 C-46、`aos_agent_call.py`、`aos_agent_lib.py ask`：call／binding 改成純 json＋資料夾＋inst 表達，不靠專用程式）
  4. 理由：「json加上資料夾，他就是lisp了，用lisp做binding更加舒服」（呼應 C-48 值＝純值或 obj 如 3 與 (+ 1 2)、[同像性](../proto8/thinking/2026-10-15-homoiconic.md)：binding 當 Lisp 式環境／let 來想）
  5. 檔案系統⇄json 互通：「檔案系統和json是可以互通的，資料夾可以當作object，資料夾名稱就是key，而json本身就是.json內部就是一個小型的檔案系統，所以在此情況下，不只是我們的inst體系，也包括其他各類格式，都可以用這套概念去套。但是我會覺得，建議不要濫用，因為雖然可以互通，但畢竟在細節上有差異」（呼應 N-35 `檔#/位置`、aos tree inline；aos tree 本身仍不入規範）
  6. json schema：「json schema，在我們現在這套大量依賴json的體系狀況下，想必會有更多的施展空間」（呼應[同像性](../proto8/thinking/2026-10-15-homoiconic.md)裡 schema 當 class／interface、驗證選用；可往 inst、state 窗、工具 `_tool` 說明等延伸）
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
