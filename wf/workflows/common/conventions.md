# 程式碼慣例 + 導航 index 維護鏈（碼相關工作流共用）

← [common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / specs / plans…）共用這套規矩。純文檔/調查類工作流用不到。結構整理原則（被動、按需取用）在 [STRUCTURE](../../STRUCTURE.md)；always-on 鐵律在 [AGENTS.md](../../../AGENTS.md)。

## 程式碼慣例

- **程式本體在 `proto8/`**（11-05 起；08～09 月那一代的 C++23／根目錄 CMake／`AOS_API`／C ABI 規矩隨 `archive/aos-v1/` 封存，不再適用）。C／C++ 在 `proto8/impls/`：**C++20**（各專案 `target_compile_features(… cxx_std_20)`），`aos-inst` 是 C11（`C_EXTENSIONS OFF`）；一個專案一夾、各自 CMake＋vcpkg。命名、標頭、元素、錯誤代號、三扇門、新專案照抄的清單都在 impls 自己的文件，這裡不重講：[02 從哪開始讀與慣例](../../../proto8/impls/docs/02-從哪開始讀與慣例.md)、[03 錯誤](../../../proto8/impls/docs/03-錯誤.md)、[04 命令列與新專案清單](../../../proto8/impls/docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md)；專案之間誰依賴誰在 [01](../../../proto8/impls/docs/01-現況與地圖與依賴.md)。
- **單向分層**：下層不可以知道上層存在（層名照 [C-74](../../../proto8/docs/CONCEPTS/01-設計理念/02-C-51.md#分層10-22-使用者定)）；Python 的 `py` 可 import `lib`，反之不行；impls 之間只透過對外標頭（`include/aos/…`）與 target 相依，不 include 對方的 `src/`。
- **KISS 是最高原則（也是最後原則：先滿足需求與其他原則，最後回頭清掉多餘的；寫什麼就做什麼——給的值照字面用，不讓特定值偷偷變成另一種行為，10-16）；巢狀只管自己這一層、錯誤只處理自己的**（使用者 10-15，proto8 起的總原則；10-15 深夜加嚴）：每一層只說自己的結果與錯誤，不替下層處理、不偷讀下層的 stderr、不替下層驗它的東西，上層不該知道下層是什麼（fsm 不知道格是 fsm、agent 不知道工具是 agent）；想看子層要另有機制，沒機制就不碰；對別人的錯明寫採「入口默認正常／入口檢查」「出口保證」「事先列出」哪一種；錯誤路徑濃縮成少數幾條。條文在 [proto8 C-56、C-52、C-53](../../../proto8/docs/CONCEPTS/01-設計理念.md)。
- **命名**（使用者 10-15，proto8 起）：資料夾、檔名、JSON key 全小寫加底線，主題放前面；對外指令名＝同名把底線換連字號；環境變數全大寫加底線；程式照語言規範（PEP8）並跟檔名固定對應（`NodePath` ⇄ `node_path`）；裝同類的資料夾用複數（`insts/a.json`）；新縮寫先進[縮寫表](../../../proto8/docs/CONCEPTS/abbr.json)。條文在 [proto8 C-54](../../../proto8/docs/CONCEPTS/01-設計理念/04-C-54.md)。
- **程式輸出一律英文**（使用者 11-05：「我發現我們做出來的程式，輸出的各種東西，裡面都有中文...全都用英文吧」）：stdout／stderr、usage／help、落檔文字、回信、log、給 LLM 的 prompt、persona、工具說明均用英文（11-07 使用者裁定 sol 審查 #34-2）。代號照舊；README／docs／thinking／wf 繁中，輸出範例英文，註解照原語言。
- **單檔行數門檻**：與 [STRUCTURE 觸發 A](../../STRUCTURE.md) 一致，程式碼單檔超過 300 行就該考慮拆。
- **`fork` 前後的界線**（`exec` 層專屬，但任何碰行程操作的程式碼都要守）：`fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的 POSIX 操作，不能有 C++ 記憶體配置、`setenv`、字串操作。所有準備工作（環境變數合併、PATH 解析、`argv`／`envp` 實體化）都要在 `fork` 之前做完（proto8 裡是 `aos-inst` 與 aos-util 的子程序）。
- **新增/改欄位或列舉值**要全域 grep 受影響處（C++ 型別、JSON 讀寫兩端、讀它的 Python／sh 與文件）並同一個 commit 更新，不要分批留下不一致的中間狀態。
- **特例**（11-07 sol 審查 #23）：認名型第一次就消；同型再現問「往後會更多嗎、好處遠大於壞處嗎」，是才升格；第 3 次、5 項或 3 天 2 項只提醒：[C-52 續](../../../proto8/docs/CONCEPTS/01-設計理念/03-續-C-52-例外.md#特例怎麼處理升格門檻11-06)

### 三扇門與結束碼（11-05）

aos 自己的程式（impls、cmd、lib 工具、kernel、templates 的格）的 stdio 與結束碼（使用者 11-05 裁四題，例「可以，固定格式："error:", "warning:"後面接你那個」；其餘照盤點推薦，[thinking stdio-unify](../../../proto8/thinking/2026-11/05/stdio-unify/README.md)）：

- stderr 只有錯誤行 `程式: error: 代號 原因` 與提醒行 `程式: warning: 句子`；有錯誤行不准退 0；10＝查了沒有，訊號 128＋N，Ctrl-C 130：[N-43](../../../proto8/docs/NORMS/01-總則/02-N-43.md)
- 每支都有英文 `--help`；不給參數＝`ArgumentsBad`；`FlagUnknown`／`CommandUnknown`；`(usage: …)` 放最後：[P-44](../../../proto8/docs/CONVENTION/02-題目stack停錯腦/07-P-44.md)
- 每層只說自己一行（開頭可以是 agent 名）：[P-21](../../../proto8/docs/CONVENTION/02-題目stack停錯腦/04-六-停與錯續-P-21～P-22.md)
- 不讀下層 stderr，明文例外四類：aos-mcp、aos-llm-kernel、agent-fsm 的 act、給腦用的工具轉接下層最後一行的代號與原因（agents、self_tools、aos_json、json_rewrite）（**11-06 註**：② aos-agent 隨 [no-pid P3](../../../proto8/thinking/2026-11/05/no-pid/10-P3實作結果.md) 作廢；④ act 隨 [json-argv J4](../../../proto8/thinking/2026-11/05/json-argv/10-J3到J7實作結果.md) 已實作，`2eb02ea4`；④ 與 ⑤ 都是使用者 11-06 選項框選推薦）：[C-52](../../../proto8/docs/CONCEPTS/01-設計理念/03-最高原則與兩條總原則.md)
- 給腦用的工具兩邊印同一行、退 1，`[exit code N]` 在最後一行：[lib/docs/01](../../../proto8/lib/docs/01-分層等.md)
- **輸出格式只在共用介面改，各程式不自己拼**（使用者 11-05：「……都會盡量把這種常見的功能，統一成單一介面，這樣只需要改介面，那就能好。」）：C++ 走 aos-util（`aos::fail`／`aos::warn`／`parse_cli`），Python 命令列走 `proto8/py/aos_flags.py`、lib 工具走 `proto8/lib/tool_io.py`（11-05 晚）；例外與待收斂的見 [stdio-unify § 使用者原則](../../../proto8/thinking/2026-11/05/stdio-unify/README.md#使用者原則11-05-傍晚)

## 導航 index（code map）維護鏈

三個面向構成維護鏈：**程式碼 → code map → 文檔**。三份真相的完整優先序（含 normative 規格）在 [code-map「真相層優先序」](code-map.md)。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則**（11-05 起逐檔表改生成，使用者裁「七題照推薦」，[thinking arch-refactor](../../../proto8/thinking/2026-11/05/arch-refactor/README.md)）：
1. **修改前**：先讀 code map 地圖，再到[生成冊](code-map/proto8/README.md)找相關的夾，只讀列出的檔——不要讀無關領域的檔案。
2. **檔頭一句話就是 code map 的來源**：每個程式檔第一行（腳本跳過 shebang 的第一行、Python 可以是 docstring 第一行；JSON 用 `description`）寫「它負責什麼」一句話。新增檔一定要寫；職責變了改那一句。
3. **commit 前跑 `python3 wf/tools/codemap_gen.py --apply`**，生成冊跟程式同一個 commit；不帶參數＝只檢查（`wf-lint` 的 CODEMAP，不一致算 broken）。生成冊不要手改；一句話空或只寫檔名會印 warning，順手補。
4. 手寫的只剩 [code-map](code-map.md) 地圖（夾一句話、常查表、真相層優先序）與各程式 README 的**行為**說明；README 不再放逐檔表。
5. 原始碼檔案本身**不加**「對應 code map」的註釋；反向查找 grep 生成冊。
