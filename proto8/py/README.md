# proto8/py — aos agent 的函式庫的原始碼（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

**11-18 S3 起這夾是原始碼**：`python3 install.py` 把它抄成 `proto8/lib/`（不含各 `tests/` 與 `docs/`），執行期只認 `lib/`，改了這裡要重跑 `install.py` 才生效。工具收在 [`tools/`](tools/)（`base/`、`aos/`、`agent/`，指示詞寫 `/lib/tools/…`），共用模組收成一個套件 [`aos/`](aos/)（`from aos import flags, tool_io …`；原 `agent/` 的 `cli_*.py`、`hooks.py`、`cmd_call.py` 等在 [`aos/agentlib/`](aos/agentlib/)；11-18 S4）。下文的「lib」指這份函式庫。

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10/24/tool-lib/README.md)｜慣例：[P-41、P-25](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-33](../docs/CONVENTION/06-巢狀/01-P-33～P-34.md)｜特性：[`_metainfo`](../thinking/2026-10/24/metainfo/README.md)

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。aos 套件裡的 `aos.flags` 系列是給指令與範本用的，lib 的工具（`tools/` 的 `base/`、`aos/`、`agent/` 底下）不 import `aos.flags`；工具輸出共用 `aos/tool_io.py`，CLI 對話的共用模組在 `aos/agentlib/`（`cli_session.py` 與 `cli_*.py`），介面宣告讀法在 `aos/declared_files.py`（11-06 晚 K-5）。

共用記帳 [`observed.py`](aos/observed.py) 提供 `append(stack, record)`（失敗提醒）、`append_strict(stack, record)`（失敗拋出）與 `prepare_strict(stack)`（先初始化並開啟帳本，供執行前預檢）；首次寫入會補 `self` 行與 stack 的 `aos-observed` 介面。`call(name, target, stdin, stack=None)` 用工具小格呼叫 `aos-exec`、記時間與位元組，回傳 `(code, stdout_bytes, stderr_bytes)`；沒設 `AOS_STACK` 就照跑不記。提醒行的程式名（坑-88）：`append`／`call` 可給選填 `prog`；沒給＝叫過 `tool_io.start(名)` 的工具用那個名（measure、watch、review_round、judge-llm…），都沒有＝`agent-fsm`（四格）。[`observed_children.py`](aos/observed_children.py) 的 `copy_child` 跳過讀不了、宣告壞或指到子 stack 外的子帳時，用同一個名字印一行 `名: warning: skipped child observations declared in …`（open-16）。

寫新工具用 [`aos.py.fn`](aos/py/fn.py)（[tools-def](../thinking/2026-11/10/tools-def/README.md)；11-20 起，使用者選「新名字 fn」，線 aos-pylib-k1-1120）：一個函數加 `@fn.tool`、最後一行 `fn.main(函數)`，說明取 docstring、參數取型別註記與 `Args:`，也收明寫的（`description=`、`fn.param`，明寫的贏），它編譯出 `_tooldef`／`_metainfo`（資料夾的兩個檔，或 JSON 物件的兩個鍵）、執行時接 `tool_io` 驗參數；本體在 [`fn_mark.py`](aos/fn_mark.py)、[`fn_run.py`](aos/fn_run.py)，說明書的零件留在 [`tool_spec.py`](aos/tool_spec.py)；骨架在 [`templates/tool-python`](../templates/tool-python/README.md)，腦用 [`tools_def`](tools/agent/tools_def/) 的 `new`／`check`。它跟下一段的 `agent_spec` 共用一支底 [`spec_base.py`](aos/spec_base.py)（例外、推名字、旗標殼、寫檔後端；線 aos-pylib-k0-1120，編出的檔一字不變）。11-20 第 3 刀起，同一個函數也能直接放進 `agent.py` 的 `tools=[…]`／`hooks=[…]`，編譯時抽成定義夾的 `fn/<名>.py`（本體 [`fn_spec.py`](aos/fn_spec.py)；線 aos-pylib-k3-1120）。

寫定義的名字 11-19 起叫 `defs`：`from aos.py.agent import defs`（＝`aos.agent_spec`，檔不搬；使用者 11-19「就 aos.py.agent.defs 吧」，線 aos-defs-rename-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)），本段的 `defs.xxx` 都是它。給人寫 agent 定義用 [`agent_spec.py`](aos/agent_spec.py)（[aos-compile-庚](../thinking/2026-11/19/aos-compile-庚/README.md) 第一刀、第三刀；各份檔怎麼算拆在 [`agent_spec_parts.py`](aos/agent_spec_parts.py)）：一支 `agent.py` 裡寫一個 `defs.Agent(說明, *, system, tools, llm, fsm=None, hooks=None, meta=None, interfaces=None, files=None)`（說明是第一個位置參數，其餘只收關鍵字、名字全小寫；`tools` 用 `std.pack`／`std.tool`／`defs.tool`／`defs.drop`，別的庫 `defs.lib`；`fsm` 用 `defs.fsm`／`defs.state`／`std.fsm`；`hooks` 用 `std.hooks`），最後一行 `defs.main(物件)`；不給 `fsm`＝只填現成定義夾（eca 版）的內容檔。建構時只收不驗，`--compile` 編譯出整個定義夾、`--dry-run` 只印不寫；寫錯在動筆前報一行 `SpecBad`。物件的 `.dry_run(folder=None, link="static")` 回 `{檔名: 內容}`、`.compile(夾, link="static")` 寫進夾並回寫了哪些，建置腳本可以不叫 `defs.main`、一支編好幾個夾；`defs.fsm(...)` 回的狀態機也有這兩個方法（只寫 `fsm.json`），`defs.main(狀態機)` 也行（不收 `--static`／`--dynamic`）。活的那隻的遙控器類別叫 `aos.py.agent.Attached`（`agent.attach(名)` 回的；11-21 從 `Agent` 改名、跟 `defs.Agent` 分開，使用者「那就Attached」，線 top-1121-attached）。產出後跟 `agent.py` 無關、重新編譯直接蓋（使用者 11-19「好比C語言和.o之間的關係」），不記指紋、不留記號。命名空間第一刀（線 aos-ns-cut1-1119，設計稿 [aos-ns-1119](../thinking/2026-11/19/aos-ns-1119/README.md)，紀錄 [aos-ns-第一刀](../thinking/2026-11/19/aos-ns-第一刀.md)）：庫在 [`agent_spec_lib.py`](aos/agent_spec_lib.py)——`std`＝隨 aos 發的庫（沒搬，根＝`$AOS_HOME`）、`defs.lib("名", 根)`＝別的庫（`<根>/packs`、`<根>/tools`）；包在編譯時讀出、展開成一支支工具靜態連結進 `tools.json`（編譯時複製進來）（不再寫 `$override`），別的庫的工具自動帶 `庫名_`、std 短名，展開後兩支同名又不同＝`SpecBad`；所以跑 `agent.py` 時要設 `AOS_HOME`。執行期沒動。繼承第一刀（線 aos-inherit-cut1-1119，設計稿 [aos-inherit-1119](../thinking/2026-11/19/aos-inherit-1119/README.md) 的乙，紀錄 [aos-inherit-第一刀](../thinking/2026-11/19/aos-inherit-第一刀.md)，規範 N-70）：[`agent_spec_load.py`](aos/agent_spec_load.py) 的 `defs.load(路徑)` 跑另一支 `agent.py`、回它交給 `defs.main` 的那隻 `defs.Agent`（新的一份，九個小寫欄位 `base.description`、`base.system`、`base.tools`、`base.llm`、`base.fsm`、`base.meta`、`base.interfaces`、`base.hooks`、`base.files`）；`tools=[base.tools, defs.drop(…)]`（底是一個包，拿掉的留墓碑，菱形裡一邊拿掉一邊留著＝`SpecBad`；換名字用 `base.pack(prefix=, rename=, exclude=)`）、`hooks=[base.hooks, {名: {**base.hooks[名], 鍵: 值}}]`（`std.hooks()` 與 `base.hooks` 是帶標記的一組，兩組同名又不同＝`SpecBad`）、`fsm=defs.fsm(base.fsm, [defs.state(名, 只給要換的)], drop=[…])`；只在重新編譯時算，編出的 json 整份、不記上一層，執行期一行沒動；被普通 `import` 的 `agent.py` 其 `defs.main` 只印 warning、不做事。骨架在 [`templates/agent-python`](../templates/agent-python/README.md)，測試 [`tests/test_agent_spec.py`](tests/test_agent_spec.py)。`agent_def`、知識庫沒動（先只給人用）。 11-19 起用語照編譯器：指令 `--compile`（編譯＋寫）／`--dry-run`（只印不寫），Python 裡是物件自己的 `.dry_run()`（算出、不寫）／`.compile(夾)`（算完寫進夾）（使用者 11-19「要，可以參考那些程式語言的類似的功能的名字」，線 aos-defs-rename2-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)）。 工具包怎麼進 `tools.json` 是編譯選項（使用者 11-19「或者說，用選項吧，gcc那樣」、「預設靜態 (Recommended)」，[aos-ns-1119/07](../thinking/2026-11/19/aos-ns-1119/07-使用者裁定.md) 末節）：`--compile`＝`--static`（預設，複製進來）、`--compile --dynamic`（寫 `$override` 指包、執行時才讀），逐包 `std.pack(名, link="dynamic")`；要改名的包（別的庫預設帶前綴）、`defs.load` 的 `tools` 只能靜態，整支 --dynamic 時改靜態並 warning。 11-19 起兩個名字照 C 改：`defs.no`→`defs.drop`（從繼承來的工具裡拿掉一支）、`defs.by_hand`→`defs.extern`；`defs.load` 不改（使用者 11-19 選項框選「改 defs.drop」「留 defs.load」「改 defs.extern」，線 aos-defs-rename3-1119，[aos-pylib-1119/07](../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)）。 11-20 編譯程式庫第 4 刀起 `defs.extern(路徑)` 換意思：那一欄編成一個連結（symlink）指到路徑、照字面存，編譯只重做連結、不碰目標，改目標不用重新編譯就生效；目標要在、不能繞回自己，`fsm` 只能連同一夾；手寫同夾的檔換個名字連過去（`defs.extern("system.hand.txt")`）；`--dry-run` 印 `{"$symlink": …}`；`defs.load` 的底連到夾外的照樣交出、連到夾內的接不上；`agent_def check` 報斷掉的連結。說明裡寫明別濫用（使用者 11-20「創建一個symlink…編譯的時候就是只生成symlink…註釋要說別濫用」；會被 `agent_def llm`／`tools` 寫穿，他選「接受，寫進「別濫用」」；線 aos-pylib-k4-1120）。

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
| [03-索引-agent等](docs/03-索引-agent等.md) | 索引：agent（self_tools：agent 改自己的工具；subagent 生、叫、調、收自己的子 agent，agents_ctl 管表上任何一隻，agent_def 造新定義與檢查、也直接改定義的工具／腦／system）；外部 agent 的一輪（eca）；等回覆的期限（fork、subagent） |

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
