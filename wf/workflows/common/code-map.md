# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

`aos` 是一個 **monorepo**：只有一個執行檔 `aos`，靠子命令把陸續長出來的各個「小專案」掛上去（例如 `aos exec world`）。第一個小專案是 `core/inst/`——一支讀 JSON instruction、`fork`/`exec` 跑起來的 POSIX 指令執行器。現在共有六個核心小專案；新長出的 `core/exec`＋`core/wire`＋`core/loop` 把 POSIX 執行、協定轉換與回合順序拆開，合起來是一個資料夾的回合機。

```
repo 根
  aos::common（common/，header-only，目前只有 <aos/export.h>）
       ▲ 每個小專案都連它
  aos::inst（core/inst/，核心小專案 → libaos_inst.so）
       │  C++ 分層，相依單向：inst ← format ← handoff；inst ← format ← resolve；inst ← exec
       │    inst    inst_t 資料結構、狀態列舉             （src/inst.cpp）
       │    format  唯一懂 JSON schema 的層                （src/format.cpp）
       │    resolve 以明示 context 解析 `$env`／`$ref`        （src/resolve.cpp）
       │    handoff instruction 檔案聚合／取件／釋放        （src/handoff.cpp）
       │    exec    唯一碰 fork/exec/waitpid 的層          （src/exec.cpp + spawn_prep.cpp + wait.cpp）
       │  外加兩層，各自只往下看：
       │    C ABI 包裝（src/capi*.cpp，對外標頭 <aos/inst.h>）
       │    CLI 世界／回合層（src/run*.cpp，進入點 aos_init_cli_main／aos_exec_cli_main）
       ▼
app/（唯一執行檔 aos，子命令分派）── `aos init`／`aos exec` 掛的就是上面這條

  aos::tooljson（core/tooljson/，核心小專案 → libaos_tooljson.so）
       │  spec／registry：驗證 tool spec 與開放的 _type 登記
       │  exec_type／args：只解析 exec 配方並展開 argv，不啟動行程
       ▼
app/ ── `aos tooljson list|check spec.json` 掛的就是這條

  aos::llms（core/llms/，核心小專案 → libaos_llms.so）
       │  LLM：端點、模型、Params、能力三態與可抽換 HTTP transport
       │  Bot／Reply：system、history、tools 與非串流 ask 的交易式收尾
       ▼
app/ ── `aos llms ask|models` 掛的就是這條（成功路徑會連網）

  aos::exec（core/exec/，核心小專案 → libaos_exec.so）       aos::wire（core/wire/，核心小專案 → libaos_wire.so）
       │  start／wait_all：整批 fork 後統一等完                 │  Inst／Outcome／State：三種協定 struct
       │  底層 spawn_prep／wait／tempfile／clock 互不相識        │  inst／outcome／state 各自只共用 json_io
       │  （純函式庫，無子命令）                                │  （純函式庫，無子命令）
       ▲                                                       ▲
       │                                                       │
       └──────────────────────────┬────────────────────────────┘
                                  │  aos::loop（core/loop/ → libaos_loop.so；只透過公開 API 相依上面兩者）
                                  │    fs 在最底層；layout／deliver／aggregate／state 分工檔案與版面
                                  │    turn 串起匯聚、並行執行、落檔與 state；CLI 再包住 turn／deliver
                                  ▼
app/ ── `aos run`／`aos deliver` 掛的就是這條
```

三個一直會用到的概念：

1. **單向相依是鐵律**：`inst ← format ← handoff`、`inst ← format ← resolve` 與 `inst ← exec`——handoff 與 resolve 使用 format，exec 只使用 inst，三者互相不知道對方存在。五組宣告目前併在同一個標頭 `include/aos/inst.hpp` 裡，**併在一起不代表可以互相引用**，標頭開頭那段註解就是講這件事。
2. **一個執行檔、多個子命令**：不會有第二個 `main`。新的小專案（未來的 `llm/`、`tooljson/`……）靠自己的 CMakeLists 呼叫 `aos_add_subcommand()` 把子命令掛進 `app/` 的分派表，不用改 `app/` 本身。
3. **每個小專案是一顆獨立的 shared lib**：`aos::inst` → `libaos_inst.so`。傘狀 target 有 `aos::core`（核心）、`aos::modules`（擴充，有擴充存在時才建）、`aos::aos`（全部）；`AOS_BUILD_MERGED_LIB` 開了才會多產出一顆合併的 `libaos.so`（`aos::merged`）。
4. **小專案分兩類，靠所在目錄決定**：`core/` 是 aos 的基本組成（一定會建），`modules/` 是可選的擴充（`-DAOS_BUILD_MODULES=OFF` 整批不建）。建置方式完全一樣，`core/CMakeLists.txt` 與 `modules/CMakeLists.txt` 各自 `set` 了 `AOS_SUBPROJECT_CATEGORY`，`aos_add_subproject()` 讀它來分類。判準：拿掉它 aos 就不再是 aos → core。

> **2026-08-24：`core/inst` 的凍結已由使用者解除。** `inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`／`capi*.cpp` 現在可以改。解凍是為了兩件已拍板的事：每筆 instruction 的 non-blocking 欄位，以及 JSON 的 `$ref`／`$env`／`$opt` 指示詞（設計見 [`docs/inst-directives.md`](../../../docs/inst-directives.md)、順序見 [`docs/roadmap.md`](../../../docs/roadmap.md) 的 T0）。解凍**不等於可以隨手改**——上述單向相依仍然是鐵律。

---

## 逐檔表格在哪：各小專案分冊

每個檔負責什麼，既有小專案與建置骨架拆成四冊放在 [`code-map/`](code-map/README.md)；新三個小專案直接指向各自的 README：

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [code-map/inst.md](code-map/inst.md) | `core/inst/`：公開標頭、五個核心分層、C ABI 包裝層、CLI 層、測試，以及「新增一個 instruction 欄位」的維護鏈（逐檔表格再按層拆在 [`code-map/inst/`](code-map/inst/README.md) 底下的 library／capi／cli／tests 四份） | 要改 instruction 結構、format／resolve／handoff／exec、C ABI 或 `aos init`／`aos exec` |
| [code-map/tooljson.md](code-map/tooljson.md) | `core/tooljson/`：公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI、測試 | 要改 tool spec 驗證、`_type` registry、argv 展開或 `aos tooljson` |
| [code-map/llms.md](code-map/llms.md) | `core/llms/`：公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI、測試 | 要改 LLM client、串流、toolset、presets 或 `aos llms` |
| [core/exec/README.md](../../../core/exec/README.md) | `core/exec/`：整批 POSIX 行程的啟動、等待、逾時、輸出與時間 | 要改 `start_all`／`wait_all`、行程群組、PATH／env 準備或暫存檔收拾 |
| [core/wire/README.md](../../../core/wire/README.md) | `core/wire/`：指令、結果與 loop state 三種協定的 C++ struct／JSON 邊界 | 要改協定欄位的解析、序列化、預設值或錯誤回報 |
| [core/loop/README.md](../../../core/loop/README.md) | `core/loop/`：`.aos/` 版面、投遞、匯聚、state 與一回合的推進順序 | 要改資料夾回合機、`aos run`／`aos deliver` 或它對 exec／wire 的接法 |
| [code-map/build.md](code-map/build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |

**新增或刪除一個原始碼／測試檔（或某個檔的職責變了）時，那一列去哪裡加**：
檔案在 `core/inst/` 底下 → `code-map/inst.md`，再照它的表選 `code-map/inst/` 的 library（標頭與五個核心分層）／capi／cli／tests 一份；在 `core/tooljson/` 底下 → `code-map/tooljson.md`；在 `core/llms/` 底下 → `code-map/llms.md`；在 `common/`／`app/`／`cmake/` 底下或是建置設定檔（含新增小專案要加的那行 `add_subdirectory()`）→ `code-map/build.md`。
`core/exec`、`core/wire`、`core/loop` 的逐檔表格放在小專案自己的 `README.md`，不另立分冊。
未來多一個小專案，就在 `code-map/` 多一冊，並在上面這張表加一列。**這一步跟程式碼改動同一個 commit**（AGENTS.md 的「改了程式碼就要同步 code map」）。

---

## 文件在哪

`docs/`（repo 根）放**整體**文件：[總覽](../../../docs/overview.md)、[建置](../../../docs/build.md)、[使用](../../../docs/usage.md)、[新增小專案](../../../docs/subprojects.md)。改了建置骨架、子命令機制或相依管理，那邊要跟著更新。

`core/inst/docs/` 放 inst 專屬的細節，不是 code map 的一部分，但改東西之前有時值得先看：

| 檔案 | 內容 |
|------|------|
| `architecture.md` | 分層為什麼這樣切、為什麼先把整份輸入讀完再執行、`fork` 兩側各自要做的工作（async-signal-safe 的界線在哪）|
| `handoff.md` | 投遞、彙整、取件、釋放的原因、路徑、錯誤資料與完整公開 API 範例 |
| `resolve.md` | resolve 分層的原因、未解析表示、`$env` context、`$ref` 路徑／pointer／巢狀與循環、驗證順序、錯誤位置與完整公開 API 範例 |
| `format.md` | JSON schema 細節 |
| `exec.md` | 執行語意細節 |
| `capi.md`／`cxxapi.md` | C ABI／C++ API 的使用說明 |

---

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| instruction 有哪些欄位、JSON 長什麼樣 | `core/inst/include/aos/inst.hpp` 的 `inst_t`；schema 細節在 `core/inst/src/format_decode.cpp` 的 `known_key`／`decode` 與 `format_encode.cpp` 的 `encode` |
| exit code、逾時、行程群組怎麼處理 | `core/inst/src/exec.cpp` |
| PATH 怎麼解析、環境變數怎麼合併 | `core/inst/src/spawn_prep.cpp` |
| C ABI 怎麼對應到 C++ API | `core/inst/src/capi.cpp` 開頭的 `static_assert` 一串 |
| instruction inbox 怎麼聚合／取件／釋放 | `core/inst/src/handoff.cpp`；路徑推導與檔案存取在 `core/inst/src/handoff_fs.cpp` |
| CLI 怎麼映射交接結果、怎麼跑一批 instruction | `core/inst/src/run_exec.cpp`／`run_batch.cpp`；argv 在 `run.cpp`，loop 在 `run_loop.cpp` |
| 子命令怎麼被登記、怎麼被分派 | `cmake/AosSubproject.cmake` 的 `aos_add_subcommand()` → `app/CMakeLists.txt` 產表 → `app/src/main.cpp` |
| 某個相依該放在哪一層 | [common/ 那節](code-map/build.md)的判準；完整說明在 [`docs/subprojects.md`](../../../docs/subprojects.md) |
| 為什麼要先把整份輸入讀完才開始執行 | `core/inst/docs/architecture.md`「為什麼要先把整份輸入讀完」|
| `fork` 前後各自能做什麼 | `core/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」；程式碼在 `core/inst/src/exec.cpp` 的 `run_child` |
| 新增一個小專案（像 inst 那樣）要照什麼模子 | [`docs/subprojects.md`](../../../docs/subprojects.md)；函式定義在 `cmake/AosSubproject.cmake` |
| 一批指令怎麼並行 fork、逾時怎麼殺整個 process group | `core/exec/src/start.cpp` 的 `start_all`／`run_child`；統一輪詢與 `kill(-pid, SIGKILL)` 在 `core/exec/src/wait_all.cpp` 的 `wait_all` |
| 協定的三種 JSON 長什麼樣、欄位怎麼對應 | struct 與公開轉換 API 在 `core/wire/include/aos/wire.hpp`；實作分在 `core/wire/src/inst.cpp`／`outcome.cpp`／`state.cpp`，共用取值在 `json_io.hpp` |
| `.aos/` 資料夾的版面（inbox／turn／batch／state.json） | 路徑推導在 `core/loop/src/layout.cpp`；協定版面在 [`PROTOCOL.md`](../dispatch/proto/PROTOCOL.md) §1 |
| 一回合的順序：匯聚 → 並行執行 → 落檔 → 更新 state | `core/loop/src/turn.cpp` 的 `run_turn`；running／done state 的組裝在 `core/loop/src/state.cpp` |
| `aos run`／`aos deliver` 的 CLI 怎麼解參數 | `core/loop/src/run.cpp` 的 `aos_run_cli_main`／`core/loop/src/deliver_cli.cpp` 的 `aos_deliver_cli_main` |
| 投遞與 state／turn 落檔怎麼保持原子 | `core/loop/src/fs.cpp` 的 `write_atomic`：先寫 `path + ".tmp"`，再以 `rename` 發佈 |

---

## 真相層優先序

三份真相（程式碼／規格文件／code map）衝突時的優先序，**必須明確**：

```text
code/tests > docs/aos-folder.md 這類 normative 規格 > schema/examples/fixtures > code map > 其他 docs > generated
```

- 上層與下層衝突時，**以上層為準並修正下層**；但規格與程式碼衝突時**先確認哪一邊是刻意的**（roadmap M0 之後 normative 在 SPEC，程式碼要跟規格走）——分不清就記 [WAIT_USER](../../WAIT_USER.md)。
- generated（產生出來的檔、build 產物）永遠不是唯一真相。
- code map 是**導航不是規格**；行為以 code/tests 為準，發現不對當場修 code map（維護鏈見 [conventions](conventions.md)）。

---

## core/llm 與 core/agent

這兩個核心小專案合起來，讓 agent 活在 loop 推進的回合世界裡：`aos agent` 保存人格、對話、狀態與工具往返，每回合結束前再把自己的下一次 `step` 投遞回 inbox；`aos llm` 則是它直接連結的思考引擎，向 OpenAI 相容端點做一次非串流補全。工具往返的關鍵節奏是：**回合 N 投遞 → N+1 執行 → N+2 讀得到結果**。
agent 本身不 fork／exec 工具，只把 instruction 交給 world inbox；loop 負責匯聚、執行與落結果。
因此 agent 與 loop 只靠 `.aos/` 版面協作，思考、執行與結果回收各自落在不同回合。
`aos agent` 不另開 `aos llm` 子行程，而是直接呼叫它的公開函式庫 API。

### `core/llm` 檔案表

| 檔案 | 負責什麼 |
|------|----------|
| `core/llm/include/aos/llm.hpp` | 公開 API：message／options／CLI options，以及環境設定、參數解析、request／response JSON 與 `complete()` 的介面。 |
| `core/llm/src/llm.cpp` | 函式庫實作：讀 `AOS_LLM_*`、組 OpenAI messages request、用 libcurl POST `<base>/chat/completions`，驗 HTTP 與抽出 `choices[0].message.content`。 |
| `core/llm/src/run.cpp` | `aos llm` CLI 層：stdin prompt 或 `--messages` 檔案進站，處理 `--system`／endpoint／model／timeout，將回覆印到 stdout。 |
| `core/llm/README.md` | 使用入口、預設 LM Studio endpoint／model、環境變數與錯誤語意。 |

### `core/agent` 檔案表與分層

相依只往下看：`paths ← store`；`paths + store ← deliver／tools`；`init／step` 再組合這些下層（`step` 另依賴公開的 `aos::llm`）；最上面的 `run` 只呼叫 `aos::agent` 公開 API。箭頭右邊知道左邊，**下層不知道上層存在**。

| 檔案 | 負責什麼 |
|------|----------|
| `core/agent/include/aos/agent.hpp` | 公開資料型別與 API：初始化、say／log／status／history／pending／tools、argv 展開、工具呼叫抽取及單步 `step()`；completion callback 讓測試可離線注入。 |
| `core/agent/src/internal.hpp` | 小專案內部契約：集中 `Paths`、儲存、prompt、投遞等下層宣告；不安裝、不是跨小專案 API。 |
| `core/agent/src/paths.cpp` | 最底層路徑規則：正規化 world folder、驗 agent 名稱，推導 `.aos/inbox` 與 `agents/<name>/` 全部檔位。 |
| `core/agent/src/store.cpp` | 儲存層：文字讀取、tmp＋rename 原子寫入、log 追加，以及 history／status／pending／tools 的 JSON 讀寫與驗證。 |
| `core/agent/src/deliver.cpp` | 投遞層：把 argv 包成 instruction 原子寫入 inbox；`deliver_self()` 建立下一個 `aos agent step`。 |
| `core/agent/src/tools.cpp` | 工具層：預設工具、system prompt、`tools.json` 登記表解析、`{args}` argv 模板展開，以及從 LLM 回覆抽工具呼叫。 |
| `core/agent/src/step.cpp` | 回合編排層：收工具結果與 say、更新 history／log／status、呼叫 LLM、投遞工具、記 pending，最後自我投遞；無新事件時不耗 LLM token。 |
| `core/agent/src/init.cpp` | 初始化層：建立 agent 版面與預設檔、必要的 world turn／state，寫入第一條自我投遞；`say()` 也在這裡原子放入訊息檔。 |
| `core/agent/src/run.cpp` | `aos agent init／step／say／listen／talk／state` CLI 分派；listen／talk 輪詢 log，pi 介面目前只導向說明文件。 |
| `core/agent/tests/fake_loop.py` | 測試用 loop 替身：依協定匯聚 inbox、並行跑 instruction、寫 out／state、鏡射 agent status 並推進 turn。 |
| `core/agent/tests/smoke.sh` | 端到端 smoke：初始化 bob、用替身推三回合，驗每回合自我投遞與 `state.json` 的 status 鏡射。 |
| `core/agent/README.md` | 回合 agent 的快速使用、工具往返節奏與函式庫入口。 |
| `core/agent/docs/pi-interface.md` | pi 0.84.2 實測、三種接法與尚未內建的 extension adapter 規劃；不是目前已完成的 CLI transport。 |

### `agents/<name>/` 版面

| 路徑 | 存什麼、誰寫 |
|------|--------------|
| `persona.md` | agent 人格；`aos agent init` 寫初值，使用者可直接編輯。 |
| `history.json` | 送給 LLM 的 user／assistant／tool messages；init 建空檔，`step` 讀寫。 |
| `status.json` | `status`／`detail`／`updated_at`／`turn`；init／step 原子寫，loop 唯讀鏡射進 world `state.json`。 |
| `say/*.md` | 等 agent 收取的使用者訊息；`say` 每則寫一個排序檔，`step` 讀入 history 後刪除。 |
| `log.md` | 逐回合 user／assistant／tool 可讀紀錄與投遞註記；init 建空檔，step 寫，listen／talk 讀。 |
| `tools.json` | 可用工具登記表；init 寫入 `sh`／`ls`／`cat` 預設值，使用者可改，step 每次要思考時讀。 |
| `pending.json` | 已投遞但尚未回收的工具 call ID、工具名、args 與投遞回合；init／step 寫，step 依它找結果。 |

### 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| 自我投遞在哪一行做的 | 正常 `step` 結尾在 `core/agent/src/step.cpp:192`；等工具時在 `:119`，例外重排在 `:91`／`:203`；實際 instruction argv 由 `core/agent/src/deliver.cpp:18-24` 組成。 |
| 工具登記表格式、`{args}` 模板怎麼展開 | `core/agent/src/tools.cpp:58-105`：根物件是 `{"tools":[...]}`，每項有字串 `name`／`description` 與字串陣列 `argv`；每個 argv 元素裡所有 `{args}` 都原樣替換成 args，不另做 shell 拆詞。 |
| 怎麼從 LLM 回覆裡抽出工具呼叫 | `core/agent/src/tools.cpp:107-147`：由回覆末行往上找完整 JSON 物件行，驗 `tool`／`args` 都是字串且工具已登記。 |
| 工具結果從哪裡讀回來 | `core/agent/src/step.cpp:110-132`：依 `pending.turn + 1` 讀 `.aos/batch/<turn>/out/<id>.json`；全數到齊才轉成 tool messages。 |
| LM Studio 端點與模型怎麼設 | `AOS_LLM_URL`（預設 `http://localhost:1234/v1`）與 `AOS_LLM_MODEL`（預設 `qwen/qwen3.5-9b`）；需要 bearer token 時另設 `AOS_LLM_KEY`，讀取處在 `core/llm/src/llm.cpp:71-76`。 |
| loop 替身在哪、怎麼跑 | `core/agent/tests/fake_loop.py`；repo 根執行 `python3 core/agent/tests/fake_loop.py <folder> --step N --interval 100`。完整 smoke 是 `bash core/agent/tests/smoke.sh`（使用 `build/bin/aos`）。 |

還沒拍板的自我投遞規劃見 [`wf/workflows/ideas/self-delivery-in-loop.md`](../ideas/self-delivery-in-loop.md)；pi 終端介面調查與建議接法見 [`core/agent/docs/pi-interface.md`](../../../core/agent/docs/pi-interface.md)。
