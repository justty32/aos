# llmkit → C++ 移植計畫

← [reference/](README.md)

把 `reference/llmkit/`（python，約 2100 行程式 + 1300 行文件）重寫成 aos 底下的
核心小專案。**執行者是 codex，驗收者是 claude。** 本檔是那份工單。

---

## 一、切成幾個小專案

**兩個核心小專案，加一份沒有程式碼的設定。**

| llmkit 的 | → | aos | 為什麼 |
|---|---|---|---|
| `tooljson/` | | `core/tooljson` | 一份跨語言契約 + 它的第二個實作 |
| `llms/` | | `core/llms` | OpenAI 相容端點的 client |
| `proxy/` | | `core/llms/proxy/` | 一份 litellm.yaml 加兩個啟動腳本，原樣搬，不建置 |

### 為什麼不併成一個 `core/llmkit`

1. **llmkit 自己就說它們單向獨立**：`proxy` 誰都不知道，`llms` 只是預設打 proxy，
   `tooljson` 產出的形狀剛好是 `llms` 收的。抽掉任一塊另外兩塊照樣能用。
2. **相依不對等。** `tooljson` 只要 nlohmann（已經在 `aos_common_private` 裡）；
   `llms` 要 libcurl，那是一顆真的 `.so`。併在一起的話，只想解析 tool spec 的人
   會被迫拖著 curl —— 這正是 [`docs/subprojects.md`](../docs/subprojects.md)
   「相依怎麼放」那節在防的事。
3. **aos 的慣例是「一個小專案 = 一條子命令 + 一顆 lib」。** `aos tooljson` 跟
   `aos llms` 是兩件不同的事，硬塞成一條子命令只會多一層 sub-sub-command。

兩個都是**核心**：拿掉 `tooljson`，aos 就沒有「把能力寫成設定檔」這件事；
拿掉 `llms`，aos 就不會說話。

---

## 二、不搬的東西（先講清楚，免得被當成漏做）

| 不搬 | 原因 |
|---|---|
| `tooljson/python_type.py`、`tool.py`、`_checks_python.py`、`PYTHON.md` 的實作 | `_type: "python"` **依規範就是 python 專屬**，別的語言讀到是壞檔。C++ 不登記它，讀到就報「不認得，目前登記的只有 [...]」——**這是正確行為，不是缺功能** |
| `llms/func_schema.py`、`jsontypes.py`、`docstrings.py` | 靠 `inspect.signature` + docstring 反射出 schema。C++ 沒有這種東西，硬做只會做出一個假的。C++ 這邊 schema 一律是手寫 JSON（`tooljson` 本來就是這樣） |
| `llms/interactive.py`（`bot.start()`）、`toolset.py` 收 callable 的那條路 | 相依 `agentloop`，那個 package **不在 llmkit 裡**，不在這次範圍 |
| `llms/__main__.py`、`tooljson/__main__.py`、`_checks_*.py`、`live_smoke.py` | 這些是「沒有 unit test，驗證靠實跑」的替代品。C++ 這邊改用 Catch2，**這是升級不是照抄** |

`toolset.py` 仍要移植它**真正在做的事**：驗證 schemas 與 dispatch 名稱完全配對、
撞名報錯。只是輸入形狀從「callable 或 (schemas, dispatch)」縮成後者。

---

## 三、兩個要使用者拍板的決策

### 決策 A：`tooljson` 的 exec 引擎自己寫，還是接 `aos::inst`？

看起來 `_type: "exec"` 跟 `core/inst` 是同一件事（argv、stdin/out/err、cwd、
timeout、exit code），應該直接複用。**實際上接不起來**，有兩個硬的理由：

1. **`stderr.mode: "merge"` 表達不出來。** EXEC.md 明講 merge 要「**真的**把 stderr
   導進 stdout 那條管子，時序才是實際發生的順序，不是事後把兩段字串接起來」。
   `inst` 的重導向是**檔案路徑**，`exec.cpp:97-100` 對 stdout 和 stderr 各開一次
   `O_WRONLY|O_CREAT|O_TRUNC`。同一個路徑給兩邊會得到兩個各自獨立 offset 的 fd，
   互相蓋寫 —— 不是 merge，是壞掉。
2. **tooljson 要的是記憶體裡的字串，不是檔案。** 而且要邊跑邊讀（pipe 緩衝區滿了
   子行程就卡住，得 `poll()`），還要在 timeout 時砍掉。`inst` 的 API 沒有這條路。

所以三選一：

| | 做法 | 代價 |
|---|---|---|
| **A1（建議）** | `core/tooljson` 自己寫一層 pipe-based spawn | 跟 `inst` 有約四成重疊（fork/setpgid/exec/waitpid-with-timeout），多約 200 行 |
| A2 | 在 `core/inst` **新增**一組記憶體捕捉 API | 要動到凍結的核心層，**需要你點頭** |
| A3 | 走暫存檔 | merge 仍然錯，等於沒解決 |

**建議 A1。** 重疊的是最單純的那四成，真正難的部分（`poll()` 迴圈、共用 fd、
NUL 偵測）兩邊本來就不一樣。A2 比較優雅但踩到 `inst` 核心凍結那條線。

### 決策 B：`core/llms` 的 HTTP 用什麼

**建議 vcpkg 的 `curl`（`CURL::libcurl`），列在 `PRIVATE_DEPS`。**

- 串流（SSE）需要 `CURLOPT_WRITEFUNCTION` 一片一片回呼。`cpr` 包了一層但沒多給
  什麼串流能力，反而多一顆相依。
- 絕對不能進 `aos_common_private` —— 那裡的准入規則寫明「curl、openssl、sqlite
  這類不該進來」，進去的話每個 `libaos_*.so` 都會多一條用不到的 `DT_NEEDED`。
- 公開標頭上不能出現 curl 的任何型別。

---

## 四、兩條貫穿全案的鐵律

### 1. 公開標頭上不出現 nlohmann，也不出現 curl

`core/inst` 已經定了這個調子：`read_all(const char *data, size_t size, ...)`，
JSON 以**字串**進出。`tooljson` 和 `llms` 照辦：

```cpp
// 好
AOS_API SpecState load_all(const char *data, std::size_t size,
                           const char *base_dir, std::vector<Spec> &out, ...);
AOS_API std::string run(const Spec &spec, const char *args_json, std::size_t size);

// 不行 —— 使用者被綁死在同一版 nlohmann 上
AOS_API std::string run(const Spec &spec, const nlohmann::json &args);
```

`Reply::calls` 裡的 `args` 也是**未解析的 JSON 字串**（python 版的 `args_raw`
本來就存在，因為模型很會吐不合法的 JSON）。

### 2. 錯誤契約要原封不動搬過來

llmkit 最重要的一條設計，兩邊方向相反，不要搞混：

| | 怎麼回 | 為什麼 |
|---|---|---|
| **壞掉的 spec** | 錯誤碼（python 是丟 `SpecError`）| 那是**人**寫錯設定，越早炸越好 |
| **工具的執行結果** | **永遠是字串，錯誤也是字串** | 那個字串會直接變成送回模型的 tool message。模型讀得懂 `Error: argument 'text' is 70000 bytes, over the 65536 limit` 就能自己重試，讀到例外只會整條斷掉 |
| **`bot.ask()`** | **永遠回一個 `Reply`**，錯誤在 `reply.err` | 同上 |

C++ 沒有例外的話怎麼表達「壞掉的 spec」？照 `inst` 的辦法：`enum class SpecState`
加一個 `to_string()`，並且回傳詳細訊息字串（python 那些錯誤訊息**很有價值，要照搬
內容**，不要簡化成一個列舉值）。

`inst` 對配置失敗的立場是「C++ API 會丟 `std::bad_alloc`，C ABI 不會」
（見 [`core/inst/docs/cxxapi.md`](../core/inst/docs/cxxapi.md)），這次沿用同一條。

---

## 五、分五階段做，每階段獨立驗收

不要一次寫完。每階段結束時 repo 必須是**能建、能跑、ctest 全綠**的狀態。

### S1 — `core/tooljson` 外殼（不執行任何東西）

FORMAT.md 那九條「一份實作要做到什麼」，加上 `args.py` 的 argv 展開。
**這階段完全離線、完全不 fork**，是整個移植裡契約最吃重、最該先做對的部分。

產出：
```
core/tooljson/
  include/aos/tooljson.hpp     Spec、SpecState、load/load_all/save、registry
  src/spec.cpp                 外殼：兩個保留鍵、schema 形狀驗證、相對路徑
  src/registry.cpp             _type → parser，開放登記
  src/args.cpp                 args JSON → argv + stdin（純函式，不碰 process）
  src/text.cpp                 decode（NUL → binary）、clip（head/tail）
  tests/                       Catch2
  docs/format.md               ← 從 FORMAT.md 改寫，講 C++ 版
  CMakeLists.txt
```

驗收（缺一不可）：
- `_version` 不是 `"0.1.0"` → 拒絕，不往下相容。
- `_type` 不認得 → 錯誤訊息**列出目前登記了哪些**。`"python"` 落在這裡。
- 相對路徑以 **.json 自己的位置**為中心（`exec[0]` 不含 `/` 的走 `$PATH` 例外）。
- 最外層 object 和 array 都收；同檔 `function.name` 撞名報錯；跨檔先到先贏。
- `schema` 剝掉 `_extra`。
- 載入期就驗 `properties` / `required` / `argv` 綁定 / `limits`，不留到第一次呼叫。
- **argv 排序**：`position` 小到大，同號照參數名的 **Unicode 碼位**排。這條是跨語言
  最容易分岔的地方，要有針對它的測試。
- 值 → 字串照 JSON 字面（`true`/`false`、`1.5`、字串不加引號不切）。
- `_coerce`：模型送 `"800"` 而 schema 說 `integer` 要轉得過去，轉不動回錯誤字串。
- 缺席的參數整條跳過；明確的 `null` 等同沒給；`repeat` 不是 `true` 卻收到 array 報錯。

### S2 — `core/tooljson` 的 exec 引擎 + 子命令

決策 A 定了才動。

產出：`src/exec_type.cpp`（解析 `_extra` 的 exec 那半）、`src/spawn.cpp`
（決策 A1 的話）、`src/invoke.cpp`（跑 + 收尾）、`src/run.cpp`（CLI 層）。

子命令：
```
aos tooljson list  <spec.json>              列出這份檔案裡有哪些工具
aos tooljson check <spec.json>              只驗證，不執行，給 exit code
aos tooljson run   <spec.json> <name> <args-json>
```

驗收：
- 沒宣告 stdin 時，子行程拿到的是**立刻關閉的空 stdin**，不是呼叫端的 stdin。
  （EXEC.md 特別標了這條：讓它繼承的話，會讀 stdin 的工具會安靜卡到 timeout。）
- `stderr.mode` 三種：`merge` 是真的共用一條管子、`ignore` 丟掉、`only` 只要 stderr。
- `ok_exit` 之外的結束碼才在最前面加 `exit N`。`grep` 沒找到是 1，那不是失敗。
- 輸出含 NUL → `(binary output, N bytes, not shown)`。
- 逾時要砍掉整個 process group，回 `Error: <name> timed out after Ns`。
- **不經過 shell**：值裡的 `;`、`$(...)`、空白只是字元。要有針對它的測試。
- 守門員 hook（`set_approver`）保留，預設全放行，**exec 專屬**。
- 單一 argv 項目超過 128KB 一律擋，不管有沒有宣告 `limits`。

### S3 — `core/llms` 非串流

產出：`Params`、`content`（url 正規化 / key 解析 / 圖片轉 base64 data URL）、
`usage`、`toolcalls`（raw ↔ history ↔ entries）、`caps`（打 `/model/info`，
**失敗一律吞掉當「不知道」**，以 root url + key 為單位快取）、`Reply`、`Bot`、
`LLM`、`presets`。

**HTTP transport 要能被抽換**，否則測試得連網。給一個
`using Transport = std::function<...>`，預設是 curl 的實作，測試塞假的。

驗收：
- `ask()` 永遠回 `Reply`，錯誤在 `err`，`bool(reply)` 是 `false`。
- **能力有三種值：true / false / 不知道**（proxy 沒說）。不知道一律放行。
- `LLM::check()` 只在能力**明確**是 false 時擋。
- **失敗時要把這一輪寫進 history 的東西收回來**（`checkpoint`）。少了它，歷史裡
  會堆一串沒人回答的問題，下次成功時整包送出，有些 API 不收連續兩則 user message。
- **`params.extra` 不能蓋掉 model / messages / stream**：那三個最後才寫。
- **只給圖不給文字要能送**（判斷式是「有 prompt **或** 有 images」）。
- `.text` 和 `.calls` **可以同時有東西** —— 模型常常一邊說「好我查一下」一邊叫工具。
  舊版只回 calls，那句話就人間蒸發了。
- 有 `tool_calls` 的那一輪，寫回 history 時要**連 tool_calls 一起**，形狀跟 API 收的
  一模一樣；只叫工具沒說話時 `content` 要是 `null` 不是空字串。
- 模型吐回不合法的 JSON 參數 → `args` 給空的、另外附 `args_raw`，不要炸。

### S4 — `core/llms` 串流 + 子命令

SSE 解析、`Accumulator`、串流專屬的收尾。

驗收：
- **tool_calls 在串流時是碎片**：`id`/`name` 通常只在第一片，`arguments` 是接起來的，
  要**依 `delta.index` 分組**（一次可能多個 call 交錯）。
- **串流的錯誤發生在 `ask()` 回來之後**，`ask()` 的 try 管不到，所以 `Reply` 自己
  要再包一層 —— 拆 chunk 的每一行都要在保護範圍內，不是只有讀取那行。
- **一個字都沒收到就斷線要退回 checkpoint**，判準是 `finish_reason` 還是空的
  （正常講完但內容是空的**不算**落空，這樣才分得開「模型沒話說」和「話還沒開始就斷了」）。
- 串流要拿 usage 得送 `stream_options={"include_usage": true}`，最後那片只帶 usage、
  沒有 choices。
- 疊代只吐**答案**的字，思考收在旁邊當屬性。

子命令：
```
aos llms ask [--model M | --preset P] [--stream] [--system S] <prompt>
aos llms models                 列出端點有哪些模型與能力
```

### S5 — 收尾

- 兩個小專案各自的 `docs/`（繁中）：`format.md`、`exec.md`、`cxxapi.md`、`usage.md`。
  **FORMAT.md / EXEC.md 是契約，要改寫成「C++ 實作」的版本，不是原文複製。**
- `docs/subprojects.md`、`docs/usage.md`、`wf/workflows/use-aos.md` 補上新的子命令
  與 target。
- 外部消費測試：`env -u VCPKG_ROOT`，`find_package(aos)` + `aos::tooljson`、`aos::llms`。
  （沒有 `env -u VCPKG_ROOT` 等於白測，見 [gotchas](../wf/workflows/common/gotchas.md)。）
- **刪掉整個 `reference/`。**

---

## 六、給 codex 的規矩

1. **`core/inst/src/` 的核心層與 C ABI 層不要動**，`run.cpp` 除外。要動 `inst`
   先問。
2. **`core/inst/` 是範本**，CMakeLists、目錄結構、docs 的寫法照抄。
3. 只能從 repo 根目錄 configure。子專案沒有自己的 `project()`。
4. 公開標頭裡每個函式都要標 `AOS_API`。漏了不會在編譯期爆，是**外部使用者**先撞到。
5. 一次做一個階段。階段結束時 `cmake --build --preset default && ctest --preset default`
   要全綠，然後停下來等驗收。
6. **文件用繁體中文寫。**
7. 遇到 `.py` 跟 `.md` 對不起來 → **以 `.md` 為準**，並把落差記下來回報。

## 七、已知會踩的坑

- **spec 常放在 `specs/` 子資料夾，這時 `exec` 是 `"../resize"` 不是 `"./resize"`**
  —— 中心是 .json 自己，不是工具所在的目錄。EXEC.md 說這是實作時真的踩到的第一個坑。
- **JSON object 無序。** 讀進 `std::map` 會照字母重排，argv 的順序**只能看
  `position`**，絕對不能看 key 的出現順序。
- **`_extra` 送給模型會被嫌。** OpenAI / LiteLLM / LM Studio 三邊各有各的嫌法，
  進 `tools=` 之前一定要剝掉。
- **不要安靜丟掉模型給的東西。** 不認得的參數要報錯，不要當作沒看到 ——
  litellm 的 `drop_params` 就是這個坑。
- **litellm 的能力宣告會說謊，兩個方向都會。** 說 `deepseek-reasoner` 不支援
  function calling（實際支援），說 DeepSeek 支援 `response_schema`（實際回 400）。
  所以 `caps` 的 override 機制不能省。
