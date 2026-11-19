# proto8/py — aos agent 的函式庫的原始碼（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

**11-18 S3 起這夾是原始碼**：`python3 install.py` 把它抄成 `proto8/lib/`（不含各 `tests/` 與 `docs/`），執行期只認 `lib/`，改了這裡要重跑 `install.py` 才生效。工具收在 [`tools/`](tools/)（`base/`、`aos/`、`agent/`，指示詞寫 `/lib/tools/…`），共用模組收成一個套件 [`aos/`](aos/)（`from aos import flags, tool_io …`；原 `agent/` 的 `cli_*.py`、`hooks.py`、`cmd_call.py` 等在 [`aos/agentlib/`](aos/agentlib/)；11-18 S4）。下文的「lib」指這份函式庫。

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10/24/tool-lib/README.md)｜慣例：[P-41、P-25](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-33](../docs/CONVENTION/06-巢狀/01-P-33～P-34.md)｜特性：[`_metainfo`](../thinking/2026-10/24/metainfo/README.md)

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。aos 套件裡的 `aos.flags` 系列是給指令與範本用的，lib 的工具（`tools/` 的 `base/`、`aos/`、`agent/` 底下）不 import `aos.flags`；工具輸出共用 `aos/tool_io.py`，CLI 對話的共用模組在 `aos/agentlib/`（`cli_session.py` 與 `cli_*.py`），介面宣告讀法在 `aos/declared_files.py`（11-06 晚 K-5）。

共用記帳 [`observed.py`](aos/observed.py) 提供 `append(stack, record)`（失敗提醒）、`append_strict(stack, record)`（失敗拋出）與 `prepare_strict(stack)`（先初始化並開啟帳本，供執行前預檢）；首次寫入會補 `self` 行與 stack 的 `aos-observed` 介面。`call(name, target, stdin, stack=None)` 用工具小格呼叫 `aos-exec`、記時間與位元組，回傳 `(code, stdout_bytes, stderr_bytes)`；沒設 `AOS_STACK` 就照跑不記。提醒行的程式名（坑-88）：`append`／`call` 可給選填 `prog`；沒給＝叫過 `tool_io.start(名)` 的工具用那個名（measure、watch、review_round、judge-llm…），都沒有＝`agent-fsm`（四格）。[`observed_children.py`](aos/observed_children.py) 的 `copy_child` 跳過讀不了、宣告壞或指到子 stack 外的子帳時，用同一個名字印一行 `名: warning: skipped child observations declared in …`（open-16）。

給 AI 寫新工具用 [`tool_spec.py`](aos/tool_spec.py)（[tools-def](../thinking/2026-11/10/tools-def/README.md)）：一支 Python 裡宣告說明、參數（`ts.param`）、特性（`META`）和 `run(args)`，它產 `_tooldef`／`_metainfo`（資料夾的兩個檔，或 JSON 物件的兩個鍵）、執行時接 `tool_io` 驗參數；骨架在 [`templates/tool-python`](../templates/tool-python/README.md)，腦用 [`tools_def`](tools/agent/tools_def/) 的 `new`／`check`。現有工具不必遷移。

寫定義的名字 11-19 起叫 `defs`：`from aos.py.agent import defs`（＝`aos.agent_spec`，檔不搬；使用者 11-19「就 aos.py.agent.defs 吧」，線 aos-defs-rename-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)），本段的 `defs.xxx` 都是它。給人寫 agent 定義用 [`agent_spec.py`](aos/agent_spec.py)（[aos-compile-庚](../thinking/2026-11/19/aos-compile-庚/README.md) 第一刀、第三刀；各份檔怎麼算拆在 [`agent_spec_parts.py`](aos/agent_spec_parts.py)）：一支 `agent.py` 裡宣告 `DESCRIPTION`、`SYSTEM`、`TOOLS`（`std.pack`／`std.tool`／`defs.tool`／`defs.drop`，別的庫 `defs.lib`）、`LLM`、`FSM`（`defs.fsm`／`defs.state`／`std.fsm`），選填 `HOOKS`（`std.hooks`）、`FILES`、`META`、`INTERFACES`；不宣告 `FSM`＝只填現成定義夾（eca 版）的內容檔。`--compile` 編譯出整個定義夾、`--dry-run` 只印不寫；寫錯在動筆前報一行 `SpecBad`。產出後跟 `agent.py` 無關、重新編譯直接蓋（使用者 11-19「好比C語言和.o之間的關係」），不記指紋、不留記號。命名空間第一刀（線 aos-ns-cut1-1119，設計稿 [aos-ns-1119](../thinking/2026-11/19/aos-ns-1119/README.md)，紀錄 [aos-ns-第一刀](../thinking/2026-11/19/aos-ns-第一刀.md)）：庫在 [`agent_spec_lib.py`](aos/agent_spec_lib.py)——`std`＝隨 aos 發的庫（沒搬，根＝`$AOS_HOME`）、`defs.lib("名", 根)`＝別的庫（`<根>/packs`、`<根>/tools`）；包在編譯時讀出、展開成一支支工具靜態連結進 `tools.json`（編譯時複製進來）（不再寫 `$override`），別的庫的工具自動帶 `庫名_`、std 短名，展開後兩支同名又不同＝`SpecBad`；所以跑 `agent.py` 時要設 `AOS_HOME`。執行期沒動。繼承第一刀（線 aos-inherit-cut1-1119，設計稿 [aos-inherit-1119](../thinking/2026-11/19/aos-inherit-1119/README.md) 的乙，紀錄 [aos-inherit-第一刀](../thinking/2026-11/19/aos-inherit-第一刀.md)，規範 N-70）：[`agent_spec_load.py`](aos/agent_spec_load.py) 的 `defs.load(路徑)` 跑另一支 `agent.py`、它的 `defs.main` 只交出九個欄位；`TOOLS` 寫 `[base.TOOLS, defs.drop(…)]`（底是一個包，拿掉的留墓碑，菱形裡一邊拿掉一邊留著＝`SpecBad`）、`HOOKS` 寫 `[base.HOOKS, {名: {**base.HOOKS[名], 鍵: 值}}]`（`std.hooks()` 與 `base.HOOKS` 是帶標記的一組，兩組同名又不同＝`SpecBad`）、`defs.fsm(base.FSM, [defs.state(名, 只給要換的)], drop=[…])`；只在重新編譯時算，編出的 json 整份、不記上一層，執行期一行沒動；被普通 `import` 的 `agent.py` 其 `defs.main` 只印 warning、不做事。骨架在 [`templates/agent-python`](../templates/agent-python/README.md)，測試 [`tests/test_agent_spec.py`](tests/test_agent_spec.py)。`agent_def`、知識庫沒動（先只給人用）。 11-19 起用語照編譯器：指令 `--compile`（編譯＋寫）／`--dry-run`（只印不寫），Python `defs.compile(...)`（算出、不寫）／`defs.write(夾, 結果)`（使用者 11-19「要，可以參考那些程式語言的類似的功能的名字」，線 aos-defs-rename2-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)）。 工具包怎麼進 `tools.json` 是編譯選項（使用者 11-19「或者說，用選項吧，gcc那樣」、「預設靜態 (Recommended)」，[aos-ns-1119/07](../thinking/2026-11/19/aos-ns-1119/07-使用者裁定.md) 末節）：`--compile`＝`--static`（預設，複製進來）、`--compile --dynamic`（寫 `$override` 指包、執行時才讀），逐包 `std.pack(名, link="dynamic")`；要改名的包（別的庫預設帶前綴）、`defs.load` 的 TOOLS 只能靜態，整支 --dynamic 時改靜態並 warning。 11-19 起兩個名字照 C 改：`defs.no`→`defs.drop`（從繼承來的工具裡拿掉一支）、`defs.by_hand`→`defs.extern`（這份檔手寫，`agent.py` 只指到它，編譯時不寫不蓋，像 C 的 extern）；`defs.load` 不改（使用者 11-19 選項框選「改 defs.drop」「留 defs.load」「改 defs.extern」，線 aos-defs-rename3-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)）。

機讀的協議定義（JSON Schema，例如 comm/1）在 [`schema/`](schema/README.md)，不是工具；`aos/comm` 的 check 從自己的位置往上找它（11-17 從 proto8 頂層的 `schema/` 搬進來，活樹也跟著有了）。

跨 kernel 的問腦轉交用 [`aos/llm_forward`](tools/aos/llm_forward/README.md)：下一層位置寫在包的 `kernel`，成功用 `child` 串起兩本帳，失敗透明轉交。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-分層等](docs/01-分層等.md) | 分層（每層只依賴下層）；一個工具長什麼樣（契約）；怎麼引用（不複製） |
| [02-索引-base與索引-aos](docs/02-索引-base與索引-aos.md) | 索引：base；索引：aos（量測、換版、審視、shell 帳與關箱比對、定義樹） |
| [04-共用模組](docs/04-共用模組.md) | aos 套件裡給 cmd 用的共用模組：`aos.flags`、`aos.ws`、`aos.daemon_ctl`、`aos.clock_register`、`aos.sweep*` |
| [05-commands](docs/05-commands.md) | 人在終端打的 Python 指令（本體在 [`aos/apps/`](aos/apps/)，入口照 [`entries.json`](entries.json) 由 `install.py` 生進 `bin/`；原 proto8/cmd，11-18 S5） |
| [03-索引-agent等](docs/03-索引-agent等.md) | 索引：agent（self_tools：agent 改自己的工具；subagent 生、叫、調、收自己的子 agent，agents_ctl 管表上任何一隻，agent_def 造新定義與檢查、也直接改定義的工具／腦／system 並在新定義記血統）；外部 agent 的一輪（eca）；等回覆的期限（fork、subagent） |

<a id="分層每層只依賴下層"></a>
<a id="一個工具長什麼樣契約"></a>
<a id="怎麼引用不複製"></a>
<a id="索引base"></a>
<a id="索引aos"></a>
<a id="索引agent"></a>
<a id="外部-agent-的格eca不是工具"></a>
<a id="外部-agent-的一輪eca"></a>
<a id="測試"></a>

`subagent` 的 `ask`／`listen` 支援 `timeout_cycles`（與 `timeout_s` 擇一）；沒設 `AOS_CLOCK` 時，1 cycle＝`AOS_CLOCK_INTERVAL` 毫秒，預設 1000。有時鐘時停鐘不會讓時鐘期限到期；詳見 [agent 工具索引](docs/03-索引-agent等.md)。
