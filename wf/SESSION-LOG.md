# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **frame 與工作區分開、`AOS_WS`（10-16 夜）已寫進概念與規範，程式待改**：原本叫「工作區」的 cwd 改叫 frame，「工作區」留給使用者的成品區；新 C-65～C-67、[N-55、N-56](../proto8/NORMS/10-基礎設施-定義與工作區.md)，N-45 改（`$env` 可當正式機制，選 A）、C-48 改、abbr 加 `ws`。**open**：程式全部待改；新待定 5 條在 [NORMS 待定](../proto8/NORMS/08-待定.md) 末段 → [10-16](session_logs/2026-10/2026-10-16.md#frame-與工作區分開10-16-夜)。
- **KISS 重審五件已拍板、已寫進概念與規範，程式待改**（10-16）：Fable 重審稿 [kiss-recheck](../proto8/thinking/2026-10-16-kiss-recheck.md) 的五個拍板點使用者逐件回答（原話在[稿末尾](../proto8/thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）——N-10 指令資料夾刪（子項改寫在 daemon ctl 的 `children`＝新 N-54）；daemon 接回子 loop 做成開關 `adopt` 預設開、table 窗併進 state 窗（N-28 改）；收到 SIGTERM＝優雅收工退 0（新總則 N-52，N-43 改）；agent＝被外面 loop 驅動的狀態機、定義不含 loop、連錯不數（新 C-62、N-53）；兩種 kernel 不併（N-42 維持）。**open**：程式全部待改（批次 A～E 照稿的新順序）；頂層整理時挖出的 5 條邊緣進 [NORMS 待定](../proto8/NORMS/08-待定.md)（SIGINT 比照與否、agent 當工具誰包 loop、`ctl_seq` 回音還 open；「退 0 後分不出被叫停」「兩人同時改 `children`」10-16 使用者已答＝新 C-63 結束碼只是參考、C-64 用檔案為了借 Linux 權限，另記新待定「tasks 用 `code` 決定往哪走要不要調整」，[thinking](../proto8/thinking/2026-10-16-exitcode-perm.md)）；稿其餘項「照推薦、之後再看」→ [10-16](session_logs/2026-10/2026-10-16.md#kiss-重審五件拍板寫進概念與規範10-16)。
- **定義與工作區（食譜與廚房）10-16 定、已寫進概念與規範，程式待改**：使用者定了七件事（[稿 § 四](../proto8/thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）——stdin 是正規入口、argv 是語法糖；agent 的 stdin 只放定義、這次的話放工作區；`.aos` 捷徑接定義、互指 `.aos/x`；一律 `aos exec 工作區 定義`、推廣到所有東西；不用 PATH、工具＝定義資料夾、參數走門房 stdin（兩層）；不造 args.json／ret.json／frame.json。落成 C-57～C-61、C-46／C-50 改字、[N-46～N-51](../proto8/NORMS/10-基礎設施-定義與工作區.md)（草稿），N-27 後半被取代、N-21～N-24 歸語法糖、N-35／N-36／N-44／N-28 加註；AI 提案沒點頭的 10 條進 [NORMS 待定](../proto8/NORMS/08-待定.md)。**open**：程式全部待改（`aos exec`、`.aos` 捷徑、門房、agent 去 frame）；待定 10 條等使用者看；KISS 批次 2～6 已由 Fable 依新設計重看、五件拍板已答（見上一條）→ [10-16](session_logs/2026-10/2026-10-16.md)。
- **KISS 大掃除暫停、等使用者重看**（10-16）：使用者撤回 10-15 深夜的「都照推薦」（「那是我昨天在打遊戲懶得思考的情況下說的，我後悔惹QQ，等一下我想要重新看過」）。批次 1 已做（commit 見[彙整總表](../proto8/thinking/2026-10-15-kiss/README.md)）可逐項翻案（1.2 `*_inherit` 已於 10-16 翻案還原，C-56 補「寫什麼就做什麼」→ [10-16](session_logs/2026-10/2026-10-16.md)）；**批次 2～6 暫停**。同日 C-56 本條改寫成「KISS 是最高原則，也是最後原則」（使用者：不算子原則、合併進本條；[10-16 稿](../proto8/thinking/2026-10-16-kiss-last.md)）。
- **KISS 批次 1「純刪」已做完、已推**（10-15 深夜，使用者「C-50 選 a，其他都按照推薦」、PLAN「刪掉」）：彙整總表 1.1～1.18 與 6.10 全做（四個 commit cb20249a、fa6629ee、7d833687、a0c7214d），C-50 改成「一張 inst 是正本」、PLAN 刪、proto8-1 併進 proto8/lib；lib 測試 173→169、ctest 全綠。自定點 8 條在 [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)（最要看的：`aos-demo` 的 AOS_DEMO 留到批次 2）。~~下一步批次 2～6~~ **暫停**（10-16 使用者撤回「都照推薦」，見上一條）。
- **inst 路徑／stdin／TARGET 重設計（10-15 深夜）**：提案稿**第四版** [inst-exec-v4](../proto8/thinking/2026-10-15-inst-exec-v4.md)（使用者答了第三版 A～L：A 必填、D 要另一個 key、G 不用 sh、H 不濫用內嵌／指示詞只拆檔，再追加「後續都默認沒有指示詞能用，但不用擔心 json 太大」→ 新規範 **N-45**；「少用 sh」記進 user.md）。已定不變：aos-inst 只吃 stdin；`cwd`／串流從 aos-inst 的 cwd 算；`aos-exec TARGET` 語法糖、TARGET 必填；JSON 裡 TARGET 全拿掉；`$ref` 從所在檔算；刪 aos_tree；不 `$abs_path`。第四版核心：**一個 agent 的定義＝一張 inst（一份大 JSON）**，跑在哪 cwd 就是 frame，零指示詞也成立，資料夾形只是 `$ref` 拆檔；aos-exec＝讀檔→一張 inst→aos-inst；`stdin_inline: true` 時 `stdin` 才是內嵌 JSON；工具一律走 frame（`work/<n>/` 的 args.json 進、ret.json 出，agent 不碰工具的 stdin／stdout），agent 當工具＝工具 inst 的 argv 直接 `aos loop`，零 sh。矛盾與未決 C～P 10-15 深夜已定（「C-50 選 a，其他都按照推薦」）；程式實作＝KISS 批次 2。
- **compact 後自動讀回**：`.claude/settings.json` SessionStart(compact) hook → [wf/tools/compact_reload.sh](tools/compact_reload.sh)，交接寫 [HANDOFF](HANDOFF.md)（10-15 深夜）。
- **意見 1～7 程式兩批都做完**（＋格沒輸出、同 frame 續聊、第二批 6 個自定點都已拍板並照做，N-44 新增）；真腦已用本機 LiteLLM 實跑（畫家 demo 見 [paint-live](../proto8/thinking/2026-10-15-paint-live.md)；LM Studio 未跑）→ [10-15 § 拍板](session_logs/2026-10/2026-10-15.md#第二批自定點的拍板10-15使用者派去處理吧都按照推薦45-用主控的推薦)。
- **10-15 收工**：使用者說「先大致到這邊……接下來是我要來做理解」→ 下一步等使用者讀完再開口。今日成果：主題分檔、fsm 規範＋實作、agent（工具＝inst、思考介面、系統提示、函數＋binding、當工具）、C-47／N-42 兩種 kernel 原型、C-48 JSON 規矩＋同像性；五份網頁已更新（https://claude.ai/artifact/<id>）：概念 QJjGNnKFhKeS7r1f5bHzu7、實作 ATizWpsmAa2qutXWZ2owjm、58 題 DKBifn39yRtYDGjwGEAzC5、inst/loop/daemon HGkzKJKAsEAwhv1dQPQX8d、aos-llm與fsm K2aQ7KCad1u3dFTfDvArda。等使用者看：各 thinking 的「動工自定點」（[llm-kernel](../proto8/thinking/2026-10-15-llm-kernel.md#動工自定點)、[general-kernel](../proto8/thinking/2026-10-15-general-kernel.md#動工自定點)、[json-families](../proto8/thinking/2026-10-15-json-families.md)、[topics/04-agent當函數](../proto8/thinking/2026-10-15-topics/04-agent當函數.md)、[judge-live2](../proto8/thinking/2026-10-15-judge-live2.md)）。open 候選：對話太長、agent 收信、標準實作、規範草稿定稿。細節 → [10-15](session_logs/2026-10/2026-10-15.md)。
- **總原則（10-15）**：C-56 KISS 最高原則、C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的已寫進設計理念；盤點第 1、3、8、9 條與「正常退出」S1～S5、新的待定 A～C 已拍板並照做（10-15 晚）；第 2、4、5、6 條深夜使用者**跟推薦相反**拍板「切乾淨」並已照做（daemon add 不驗子項裡面、fsm 不讀格 stderr、`next: null`＝留原狀態讓外層不必知道格是 fsm、agent 只看到工具清單；[thinking 原則 § 深夜拍板](../proto8/thinking/2026-10-15-principles.md#10-15-深夜使用者拍板切乾淨kiss)，[§ 實作](session_logs/2026-10/2026-10-15.md#切乾淨kiss-最高原則10-15-深夜使用者拍板跟推薦相反)）。open：稿裡「自定的小地方」四條等使用者看；工具叫 agent 的寫法留給 inst-exec 稿；「kernel 評估納入錯誤路徑」記在 NORMS 待定。
- **命名（10-15）**：C-54、C-55、[縮寫表 abbr.json](../proto8/CONCEPTS/abbr.json)；盤點 P1～P7、M1～M9 與原值 `val` 使用者「都按照推薦」，10-15 晚全照做（4 個 commit）；改名批次 AI 自定的 5 個小地方使用者「都走推薦」（維持現狀）→ [盤點 § 拍板與實作](../proto8/thinking/2026-10-15-naming/盤點.md#拍板與實作10-15-晚)。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)。PLAN 已刪（10-15 深夜使用者「刪掉」）。**「先做 demo」已開工**：畫家 demo [demo/paint](../proto8/demo/paint/README.md)（使用者 3g.10 的例子），自定點與 LiteLLM 實跑 5 題已拍板並做完 → [10-15 § 畫家 demo](session_logs/2026-10/2026-10-15.md#畫家-demo10-15-晚使用者先做-demo開工)；restart §4 列了他停在半路的幾處。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- 已搬走（open 已解）：10-14 收工交棒、10-13 `檔#/位置`／kernel-agent、10-12 thinking 精簡與清帳 → [10-14](session_logs/2026-10/2026-10-14.md)、[10-13](session_logs/2026-10/2026-10-13.md)、[10-12](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
