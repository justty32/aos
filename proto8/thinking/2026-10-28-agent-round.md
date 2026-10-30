# 2026-10-28 agent 的一輪（round）：掛勾點、單位、endpoint 介面、引用、落地步驟

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-28 agent-ops](2026-10-28-agent-ops.md)（決定 1～10：各單位都是 aos 函數、六題的回答；本份是它的「結論／代定」）、[10-28 hub-kernel](2026-10-28-hub-kernel.md)（決定 11 prompt＝queue、13 插話不訂死）、[10-28 aos-tools](2026-10-28-aos-tools.md)、[10-28 hub-adapter](2026-10-28-hub-adapter.md)（信箱協議）、[10-24 compact](2026-10-24-compact.md)（agent-hal 的土法 compact）、[10-24 tool-lib](2026-10-24-tool-lib.md)（捷徑指到庫）｜相關條文：[CONVENTION P-11～P-26、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32～P-39](../docs/CONVENTION/06-巢狀.md)、[C-61](../docs/CONCEPTS/05-agent.md)、[N-43](../docs/NORMS/01-總則.md)、[N-57～N-61](../docs/NORMS/10-基礎設施-定義與工作區.md)

規矩見 [thinking/README](README.md)。這份**全部是照原則代定、可翻案**，使用者定的在 agent-ops 的「決定」；文末原本要使用者看的七條，使用者 10-28 回「照新做法」，已定（agent-ops 決定 11）；之後再定粒度看 `_entry`、round 是零件庫的語法糖、aos 歸 aos、round 列入外部接口（決定 12～15）、格全部走註冊檔、捷徑只是方便用（決定 16），對應的結論已改。只寫文件、程式沒改、這次不動手做。

## 白話版

一隻 agent 就是一個資料夾，裡面每一格都是一個小程式（aos 函數）：收題的 `queue`、記對話的 `history`、問腦的 `endpoint`、跑工具的 `act`，加上幾個可以不裝的插座 `hook/`。`round` 是把這些格照順序叫一遍的那支骨架，也是 aos 函數（零件庫裡的語法糖）；`_entry` 寫 aos-loop 就一格一格跑、寫 round 就一次跑完一輪。外面的人也能直接叫一次 round 同步問一題（外部接口）。格多半是共用標準件，**agent 資料夾裡的 `parts.json`（格的通訊錄）記每一格指到哪裡**，用 `aos-parts add` 登記；要換哪一格，就重新登記那一格。通訊錄沒寫的格，就去 agent 資料夾找同名的東西——放一條捷徑（symlink）或一個真的資料夾都行，這就是「捷徑方便使用」；兩邊都沒有，掛勾就當沒掛。給模型看的工具清單另外一份（`tools.json`），只認通訊錄。執行中的東西全在 `$AOS_STACK`。

## 1. 佈局

```
agent-x/
  _entry        ["aos-loop", "loop.json"]                                   P-05
  loop.json     {"exec": {"argv": ["aos-exec", "round", {"$env": "AOS_CD"}], "timeout_ms": 600000}, "max": 40}
  .env          agent 層的設定（可無）
  system.txt    system 訊息（P-41 照舊）
  tools.json    腦能叫的工具，aos-tools 管（10-28 aos-tools）
  parts.json    格的註冊檔（槽名 → 絕對路徑），aos-parts 管（決定 16；下面「格怎麼找」）
  （以下各格都是「註冊檔沒寫時的固定名字」，可有可無：捷徑、真的資料夾或檔都行）
  round/        _entry → ../../lib/agent/round/_entry（捷徑）
  queue/        _entry → …/lib/agent/queue/_entry
  history/      _entry → …/lib/agent/history/_entry
  act/          _entry → …/lib/agent/act/_entry；.env 可寫 MAX_PARALLEL
  endpoint/     <名>/：每個候選一個小資料夾（_entry 捷徑＋.env）；default → 其中一個（捷徑）
  hook/         （可無）pre_round/ pre_think/ post_think/ pre_tool/ post_tool/ post_round/ on_error/ on_interrupt/ pause/
```

- **一格＝一個小資料夾：`.env`（這格的設定）＋ `_entry`（捷徑指到共用件的入口）**。aos-exec 走進這格時先讀這格的 `.env`，入口是捷徑就 cd 到共用件那邊、那邊的 `.env` 不讀（N-59 第 4 件）——所以設定留在 agent 這邊、程式在庫那邊，不用發明設定檔。整格捷徑（`queue → lib/agent/queue`）也行，只是那格就沒地方放自己的 `.env`。
- **格跟工具的界線**：上面這些格是 agent 自己的格，**共用同一個 `$AOS_STACK`**（P-16：同一台狀態機）；`tools.json` 登記的工具是「別人」，每個一個小格 `$AOS_STACK/<名>/`（P-17），由 aos-tools call 給。
- **round 跟每一格都拿 agent 資料夾的絕對路徑當第一個參數**（`loop.json` 用 `{"$env": "AOS_CD"}` 給 round，round 再原樣給每一格）。理由：aos-exec 解開捷徑後 cwd 是庫的位置（10-24 tool-lib 已知），共用件靠 cwd 找不到引用它的 agent 的其他格；用參數明給，跟 `aos-fsm fsm.json`「設定檔是唯一的位置參數」、`"_entry": ["aos-fsm", {"$env": "AOS_CF"}]` 同一個樣子。這跟 P-33「不給程式根變數」字面相撞，見文末第 1 條。
- **共用件放 `proto8/lib/agent/<名>/`**（round、queue、history、act）與 **`proto8/lib/endpoint/<名>/`**（fake、openai；LiteLLM 就是 openai 那個加一份 `.env`）。10-24 已定庫在 `lib/<層>/<名>/`，agent 層的件放 `lib/agent/`（現在已有 cli_session、pyfix）。
- **捷徑**（決定 16 起降為方便用）：固定名字的格可以是捷徑；repo 內用相對捷徑、repo 外用絕對捷徑，只管 Linux（10-24 已知）。捷徑目標裡的 `..` 跟 P-25／C-61 字面相撞，使用者已定照新做法走（決定 10）；正式機制改走註冊檔後，這個衝突只剩在可有可無的捷徑裡。
- **跟 tools.json 的對照**：原本代定「兩套並存」已由決定 16 取代——格也走註冊檔，但是**另一份**（`parts.json`），見下。

### 格怎麼找：註冊檔 → 固定名字 → 預設（決定 16）

照原則代定、可翻案：

- **另一份檔 `parts.json`，不跟 tools.json 合一**。形狀照 tools.json：`{"parts": {"<槽>": {"path": "/絕對/路徑", "env": {名: 值}}}}`。理由：tools.json 是給模型與 aos-mcp（外部 CLI）看的清單，混進格就會被列給模型（C-52 各管各的）；兩邊的檢查也不同（工具要 `_tooldef`、格不用）。要一處看全用 `aos-parts ls`。
- **管理指令另一支 `aos-parts`**，用法照 aos-tools：`add [--override] [--env K=V]… 槽 XXX`、`rm 槽`、`ls [--json]`、`get 槽`，加一個 **`which 槽`**——照「註冊檔 → 固定名字」查，印路徑；都沒有退 10。查找順序只寫在這一處（C-52）。不擴充 aos-tools：aos-tools 的 `call`、`--tooldef` 對格沒意義。實作可以共用程式碼。
- **槽名**＝固定名字的相對路徑：`round`、`queue`、`history`、`act`、`endpoint/<名>`、`hook/<點>`。只檢查格式（小寫、底線、最多一層 `/`），不檢查槽的清單——round 可以換成別人的、用別的槽（C-52）。XXX 要是 aos-exec 跑得動的東西（資料夾、可執行檔、JSON），不是就報錯（同 aos-tools 決定 4）。
- **迴圈怎麼叫格**：round 每叫一格先 `aos-parts --file <agent>/parts.json which <槽>`，再 `aos-exec <路徑> <agent 資料夾> …`；註冊檔有 `env` 就放進那次的環境（取代原本「這格的 `.env`」放設定，例 endpoint 的 `AOS_BRAIN_MODEL`、act 的 `MAX_PARALLEL`、compact 的 `MAX_BYTES`；值可用 `$env` 指示詞，金鑰不必寫死，N-45）。固定名字那條路照舊用那格自己的 `.env`。
- **找不到怎麼辦**：註冊檔寫了但路徑壞了＝報錯（`PartBad`），**不**退去找固定名字（報錯不猜）。註冊檔沒寫、固定名字也沒有：掛勾＝沒掛的預設行為（§ 3 表）；round、queue、history、act、endpoint 這些必要的格＝`PartMissing`、round 退 1（P-20）；不退去用 lib 的標準件（10-28 晚代定、可翻案，見文末「實作時代定」第 1 條）。
- **endpoint 的候選**＝註冊檔裡 `endpoint/<名>` 與資料夾 `endpoint/` 底下同名的聯集（同名以註冊檔為準）；`endpoint.txt` 照舊寫名字，沒有＝`endpoint/default`。
- **工具清單不套這條**：工具只認 tools.json（aos-tools 現狀），不退去掃 `tools/<名>/`——那正是使用者嫌「太土太粗暴」的做法（aos-tools 決定 7），給模型看的清單要明白登記。
- **共用件怎麼登記、搬家**：照 aos-tools 結論第 6 點——`add` 存絕對路徑；手寫的相對路徑從 parts.json 所在資料夾算，所以 git 裡的範本 `parts.json` 手寫 `../../lib/agent/queue` 這種相對路徑、整個 repo 搬家不斷；`add` 寫的絕對路徑搬家要重新 add（使用者選的代價）。
- **「捷徑方便使用」具體是**：不想登記時，在 agent 資料夾放一個固定名字的捷徑（或真的資料夾）就能用；`aos-parts add` 收捷徑路徑也行（照 aos-tools 存 abspath、不解開捷徑）。不另做「產生捷徑」的指令。

## 2. round：一輪本身

> **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round](2026-10-30-aos-round.md#決定10-30)）：順序搬到 `lib/agent/round/fsm-*.json`、現在在哪看 fsm 的 `state.txt`、`--step` 與 `hook/pause` 退場、trace 看 fsm 的行。

- **粒度看 `_entry`**（agent-ops 決定 12、13）：格只有一套。`_entry` 寫 aos-loop、每次只做下一格（照下面「從哪接著做」判）＝一格一格跑；寫 round＝一次跑完一輪。round 是**語法糖**：等於 aos-loop 加上「這一輪結束就停」的條件，留在零件庫 `lib/agent/round/`、不升成 aos 指令。§ 1 的 `loop.json` 是「loop 反覆叫 round」那種寫法，只是其中一種設定。
- **叫法**：`aos-exec round <agent 資料夾>`；loop 每次叫一次，或外面直接叫一次（§ 6 外部接口）。結束碼照 P-19：`0`＝這輪好了（或中途 yield，狀態在 stack，下次接著）、`10`＝沒題目、其他＝失敗停下等人（P-20）。
- **從哪接著做**（不另設狀態檔，看 `cur/` 跟 `history.jsonl` 最後一則就夠，agent-dan 的 brain 現在就是這樣判）：`cur/` 與 `new/` 都空 → 10；`cur/` 空 → `queue claim`；最後一則是 user／tool → 問腦；最後一則是 assistant 且有 `tool_calls` → `act`；最後一則是 assistant 沒 `tool_calls` → `queue finish`。
- **順序**（每一步都是 `aos-exec <格> <agent 資料夾> [子命令]`，stdin／stdout／結束碼是介面）：

```
round:
  hook/pre_round
  queue claim                          沒題 → 退 10
  loop:
    hook/pre_think                     compact 掛這裡
    tools  = aos-tools --file <agent>/tools.json ls --json
    system = <agent>/system.txt
    msg    = endpoint/<目前的>  stdin={"messages": system+history read, "tools": tools}
      失敗 → hook/on_error  stdin=那一行錯 → stdout stop／retry／switch；沒掛＝stop → 退那個碼
    hook/post_think   stdin=msg → stdout 非空就取代 msg
    history append    stdin=msg
    queue emit        stdin=msg
    沒 tool_calls → queue finish stdin=msg.content → hook/post_round → 退 0
    act               stdin=msg → stdout 一行一則 tool 訊息（act 內部跑 pre_tool／post_tool、插話檢查）
    history append    每一則
    hook/pause        退 10 → 退 0（yield）；0 或沒掛 → 繼續
```

- **每叫一格在 `$AOS_STACK/trace.jsonl` 追加一行** `{"started_at", "unit", "code", "elapsed_ms"}`（跟 fsm 的 trace 同形、多 `unit` 少 `state`；P-38 看樹就看這份）。
- **格失敗（非 0）＝round 失敗**，round 以那個碼退、stderr 不轉述（P-21 誰的錯誰講；格自己已經寫了一行）；只有 endpoint 的失敗先問 `hook/on_error`。
- **逾時**：整輪的 `timeout_ms` 寫在 `loop.json` 的單子（P-22、P-36 打整棵子樹）；endpoint 自己那次的逾時寫在 endpoint 格的 `.env`（`TIMEOUT_MS`），由 endpoint 自己守。
- **插話**：round 不管；由 act 在兩個工具之間問 `queue peek` 與 `hook/on_interrupt`（見 § 5）。
- 用 round 時一個行程跑完一輪；要一次一格，`_entry` 改用 aos-loop（決定 12，取代原本「掛 `hook/pause` 永遠退 10」的代定；`pause` 仍可用來在一輪中途 yield）。N-53／C-25 見文末第 3 條。

## 3. 掛勾（hook）

> **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round](2026-10-30-aos-round.md#決定10-30)）：順序搬到 `lib/agent/round/fsm-*.json`、現在在哪看 fsm 的 `state.txt`、`--step` 與 `hook/pause` 退場、trace 看 fsm 的行。

| 點 | 何時 | stdin | stdout／結束碼 | 沒掛時 |
|---|---|---|---|---|
| `pre_round` | 認領前 | 空 | 0 繼續；非 0＝round 失敗 | 什麼都不做 |
| `pre_think` | 每次問腦前 | 空 | 同上 | 同上 |
| `post_think` | 腦回來、接進 history 前 | 那一則 assistant（一行 JSON） | stdout 非空＝取代那一則；0 繼續 | 原樣 |
| `pre_tool` | 每個工具叫之前（act 內） | 那個 `tool_call` 物件（一行 JSON） | 0 跑；**10＝不跑**，stdout 當那次的 tool 訊息 content（例「policy 不准」）；其他＝act 失敗 | 跑 |
| `post_tool` | 每個工具回來、接進 history 前（act 內） | 那一則 tool 訊息 | stdout 非空＝取代（例截長）；0 繼續 | 原樣 |
| `post_round` | 答案寫進 `out/` 之後 | 最後那一則 assistant | 0；非 0＝round 失敗（答案已寫） | 什麼都不做 |
| `on_error` | endpoint 退非 0 | endpoint 的 stderr 那一行 | stdout 一個字：`stop`／`retry`／`switch`；非 0 或別的字＝stop | stop（P-20） |
| `on_interrupt` | act 兩個工具之間，`queue peek` 說 `new/` 有東西 | `new/` 的題名清單（一行一題） | stdout `interrupt`／`wait`；非 0＝wait | wait（hub-kernel 決定 13：各 agent 自己設） |
| `pause` | 每批工具接進 history 之後 | 空 | **10＝yield**（round 退 0、狀態在 stack）；0 繼續 | 不 yield |

- **名字**：`pre_`／`post_`＋動作（git hook 的老慣例：pre-commit／post-commit；C-54 命名方法查過 Unix 老慣例就用），決定型的叫 `on_`＋事件，`pause` 是動作。都是小寫底線（C-54）。
- **同一點只能掛一個**：`hook/<點>/` 就是那一個 aos 函數；要掛好幾個，那個函數自己依序叫（C-41「元素要不要先算由 entry 決定」、C-70 aos 不管巢狀）。不另定順序規則。
- **掛勾看到的東西**：第一個參數是 agent 資料夾、`$AOS_STACK` 是 agent 的 stack（共用），要看 history、current、endpoint.txt 都在那裡；要叫別的格就 `aos-exec <agent>/<格> <agent>`。
- **結束碼 10 的意思統一**：「正常、但這一步不做／到此為止」（P-19 的 10＝正常停）——`pre_tool` 的 10＝不跑這個工具、`pause` 的 10＝這輪到此 yield。

## 4. 單位介面

每個單位：`aos-exec <格> <agent 資料夾> <子命令> [args]`，stdin／stdout 是資料、stderr 一行 `名: 代號 原因`、錯退 1（N-43）。

### queue（對到 P-11～P-14 的信箱，`$AOS_WS/new cur out done`）

| 子命令 | 做什麼 | stdin → stdout | 等不等 |
|---|---|---|---|
| `push [題名]` | 放一題（＝aos-say） | 題文 → 題名 | 不等；`--wait`＝接著 pop |
| `pop 題名` | 等答案（＝aos-listen） | — → `out/<題名>` 內容 | 等；`--timeout-s N` 逾時退 10 |
| `claim` | `cur/` 有沒做完的先接，沒有就把 `new/` 排序最前一題搬 `cur/`（P-12）；題名追加進 `$AOS_STACK/current.txt`；題文接成一則 user 寫進 history（round 叫它時這樣做） | — → 題名 | 不等；沒題退 10 |
| `peek` | 看排隊 | — → `new/` 題名一行一個 | 不等 |
| `current` | 看認領了的 | — → `cur/` 題名 | 不等 |
| `done` | 看做過的 | — → `done/` 題名 | 不等 |
| `emit` | 中間輸出：追加進 `$AOS_STACK/live.jsonl`（跟 hub 同名、只接不重寫） | 一則訊息 → — | 不等 |
| `finish` | 答案寫 `out/<題名>`、題目 `cur/` → `done/`；`cur/` 有幾題（插話進來的）就寫幾份同樣的答案 | 答案 → — | 不等 |
| `withdraw 題名` | 撤回：只刪 `new/` 裡的；已認領的不能撤（認領是界線，agent-ops 提案一） | — | 不等 |

寫檔照 N-05（先 `.` 開頭暫存再改名）；`push` 照 aos-say 用 link 不蓋。外部指令 aos-say／aos-listen 不改，它們本來就只碰這個信箱（hub-adapter 結論一）；要經 agent 的 queue 格叫也可以，一樣的檔。

### history（`$AOS_STACK/history.jsonl`，一行一則 OpenAI message，P-41）

| 子命令 | stdin → stdout |
|---|---|
| `append` | 一行 JSON → —；不是 JSON 物件＝`HistoryBad` |
| `read` | — → JSON 陣列（整份） |
| `compact [--expect-bytes N]` | 新的短版（一行一則）→ 印 `history_archive/<名>` 一行；怎麼壓是 compact 格的事（實作時代定 24） |

- **compact 怎麼觸發**：掛勾不收子命令，所以 `hook/pre_think/` 的 `_entry` 捷徑指到一支專門的 `lib/agent/compact/`，它看 `history.jsonl` 超過自己 `.env` 的 `MAX_BYTES`（例 65536）才 `aos-exec <agent>/history <agent> compact`。門檻、怎麼壓（摘要、刪舊、按意圖）是 compact 那格自己的事；agent-hal 的三步土法（10-24）搬進 `lib/agent/compact/` 當預設做法，問腦走 `endpoint/<目前的>`（或它自己 `.env` 指定的便宜一個）。
- **壓掉的原文去哪**：整份舊的 `history.jsonl` 先搬到 `$AOS_STACK/history_archive/<UTC 到毫秒>.jsonl`，新的短版再改名換上（agent-hal 現在就是 `os.replace` 換上）。副產物都留，不清（hub-adapter 使用者「反正就留著」；清理是人的事，P-14）。
- `compact` 是**唯一**可以改寫 `history.jsonl` 的；其他地方只附加。P-41「只附加、不改寫」那句要改成這樣，見文末第 4 條。

### endpoint（腦；假腦、LiteLLM、直連 OpenAI 都是這種資料夾）

- **叫法**：`aos-exec endpoint/<名> <agent 資料夾>`；目前用哪個：`$AOS_STACK/endpoint.txt` 一行名字；沒這個檔＝`endpoint/default`。
- **stdin**：一個 JSON 物件＝OpenAI chat completions 的請求體去掉認證：`{"messages": [...], "tools": [...]}`（`model` 可省，省了用這格 `.env` 的）。沿用 OpenAI 形狀＝P-23 原本的精神，只是從「環境變數指到 URL」變成「一個資料夾吃請求、吐回覆」。
- **stdout**：一行 JSON＝那一則 assistant message（OpenAI 的 message 原形：`role`、`content`、有工具時 `tool_calls`），round 原樣接進 history。模型想的內容不收（P-23）。
- **usage**：API 回的 `usage` 物件原樣追加一行進 `$AOS_STACK/usage.jsonl`：`{"answered_at", "endpoint", "model", "usage": {...}}`；環境裡有 `AOS_KERNEL_REPORT` 就照 P-23 也寫那份（kernel 的額度照舊管得到）。usage 不進 history。
- **串流**：第一版不串流（stdout 只在最後吐一則）。要串流的 endpoint 自己把片段追加進 `$AOS_STACK/live.jsonl`（`{"delta": "..."}` 一行一片），stdout 仍只吐最後那一則——round 不用知道有沒有串流（C-52）。
- **設定**（這格的 `.env`）：`AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`（沿用 P-23 的名字，現在只是某個 endpoint 資料夾自己的設定）、`TIMEOUT_MS`。`lib/endpoint/fake/` 不讀這些。
- **錯**：一律退 1、stderr 一行 `endpoint: 代號 原因`（N-43 不用結束碼分種類）；**分類靠代號**，`on_error` 看代號決定：

| 代號 | 什麼情況 | 預設建議 |
|---|---|---|
| `BrainFailed` | 連不上、逾時、5xx、429（原因裡帶 HTTP 碼） | 可 retry／switch |
| `KeyBad` | 401／403 | stop |
| `ModelUnknown` | 404 模型不存在 | switch 或 stop |
| `RequestBad` | 其他 4xx（我們送的東西不對） | stop |
| `ReplyBad` | 2xx 但不是 OpenAI 的形狀 | stop |

  代號照 C-54 四種結尾；要分 429 跟 503，看原因裡的數字。範本不掛 `on_error`＝一律 stop（P-20 照舊）。
- **換手**：`switch`＝round 把 `endpoint/` 底下排序在目前那個之後的名字寫進 `endpoint.txt`（繞一圈），再問一次；外面的人要換就寫 `endpoint.txt`（N-05），下次問腦前生效。**註冊＝在 `endpoint/` 多一個小資料夾**，不另做註冊檔（C-54 結構本身就是說明；C-71 資料夾＝table）。之後要做 `aos-endpoint ls／set／get` 只是 `ls endpoint/` 跟寫 `endpoint.txt` 的糖。

### act（照腦的決定跑工具）

- **stdin**：那一則 assistant message；**stdout**：一行一則 tool 訊息，照 `tool_calls` 原順序。
- 每個 call：`hook/pre_tool` → `aos-tools --file <agent>/tools.json call <名>`（arguments 從 stdin 進、`AOS_STACK=$AOS_STACK/<名>/`，P-41 照舊）→ `hook/post_tool`。`ToolUnknown`、`ArgumentsBad`、工具退非 0 都接成 tool 訊息回給腦、不停（P-41 現狀）；aos-tools 自己起不來＝`ToolsBad`、act 失敗（P-20）。
- **平行或依序交給 act 這格**（使用者六題之 5）：act 的 `.env` `MAX_PARALLEL`（C-54 R6 上限 `max_*`），沒設或 1＝依序；N＝最多 N 個一起跑，結果仍照原順序吐。要別的策略（看工具種類決定）就把 `act/` 換成自己的。
- **插話檢查**：依序模式在兩個 call 之間看 `new/`（實作時代定 18），有東西就問 `hook/on_interrupt`；`interrupt`＝剩下的 call 不跑（各接一則 tool 訊息「被打斷」）、照樣全部吐完、**act 退 10**；act 不認領新題，由 round 把 tool 訊息接進 history 後叫 `queue claim --more` 把新題接進來、再問腦（實作時代定 20、21）；平行模式一批跑完才檢查。

### tools 生效時間點（使用者六題之 1：「變成掛在哪個點」）

不另定三種模式：round 每次問腦前 `aos-tools ls`、act 每次叫工具 `aos-tools call`，都現讀 `tools.json`。所以 `aos-tools add` 下次問腦就看得到、`rm` 之後腦還叫＝`ToolUnknown` 回給腦。要「這一輪固定」或「只對這一題有效」，掛 `pre_round`／`post_round` 自己改 `tools.json`（或改成指到題目資料夾的 `$ref`，aos-tools 已支援）。中途改清單 prompt cache 會失效，是掛的人自己的代價。

## 5. stack 裡有什麼

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `current.txt` | queue claim | 認領中的題名，一行一題（插話多題） |
| `history.jsonl` | history append／compact | 對話（P-41） |
| `history_archive/<UTC>.jsonl` | history compact | 壓掉的原文整份 |
| `compact/` | compact 格 | 壓到一半的半成品（`run/`）與每次的報告（`<run>/report.json`、`log.jsonl`；實作時代定 25） |
| `endpoint.txt` | round（switch）、外面的人 | 目前用的 endpoint 名；沒有＝default |
| `usage.jsonl` | endpoint | 每次問腦的 usage |
| `live.jsonl` | queue emit、endpoint 串流 | 中間輸出；只接不重寫 |
| `trace.jsonl` | loop、round | 每次、每格一行 |
| `<工具名>/` | aos-tools call | 工具的小格（P-17） |

都在 `$AOS_STACK`（預設 `$AOS_WS/.stack/`，N-57）；定義資料夾不被寫（P-15）。沒有別的狀態檔：round 從哪接著做看 `cur/` 跟 history 就夠。

## 6. 外部指令對內部單位

| 外面打的 | 對到 | 備註 |
|---|---|---|
| `aos-say` | `queue push` | 現成，不改 |
| `aos-listen` | `queue pop`；`--follow` 讀 `live.jsonl` | 現成；follow 改讀 live.jsonl |
| `aos-tools add／rm／ls／get／call` | `tools.json`；act 用 `call` | 現成 |
| （未來）`aos-endpoint ls／set／get` | `ls endpoint/`、`endpoint.txt` | 先不做，手打就行 |
| `aos-hub`（外部 CLI：claude code、codex、pi） | 外部 CLI 跟 aos 接入的接口；**不納入 round**、不另做東西 | agent-ops 決定 14；「黑盒子當 round」已否決 |
| `aos-exec <agent>/round <agent>`（外部接口） | 同步問一題、等答案：先 `queue push` 一題，叫一次 round 認領、跑完一輪、答案在 `out/<題名>`；不需要 agent 常駐 | agent-ops 決定 15；例：claude code 的 tools.json 登記「問 agent-xxx」，背後 push＋round＋讀答案，經 aos-mcp 叫到 |
| loop 的 ctl.json | 外部停、暫停 | 現成（N-06），round 不另做 |

- **外部接口四種並列**：hub、aos-mcp、say／listen 協議、round（決定 14、15）。say／listen 是非同步（要有 agent 開著收信）；round 是同步（叫一次跑完一題）。
- **搶信箱是呼叫者自己的風險**：同一個工作區如果另有 aos-loop 在收信，外面叫的 round 會搶同一個信箱；工具不另加保護（決定 15、C-53），要避開就照 P-18 給各自的工作區或 stack。

<a id="7-怎麼落地做一隻新範本-agent這次不做"></a>

## 7. 怎麼落地：做一隻新範本 agent（10-28 晚實作中）

1. **`lib/endpoint/fake/`、`lib/endpoint/openai/`**：從 agent-dan 的 brain.py 把「問腦」那段抽出來；驗：`echo '{"messages":[…]}' | aos-exec lib/endpoint/fake X` 吐一則 assistant；openai 接 LiteLLM 吐真的、`usage.jsonl` 多一行；拔掉 key 看到 `KeyBad`、指錯埠看到 `BrainFailed`（用 tests/dead_brain.py）。
2. **`lib/agent/queue/`**：從 brain.py 的認領段＋aos-say／listen 抽；驗：push → peek 看得到 → claim 搬到 cur/、current.txt 有 → finish 寫 out/、done/ 有；withdraw 已認領的報錯。
3. **`lib/agent/history/`**：append／read／compact；compact 搬 agent-hal 的三步；驗：塞一份大的 history 跑 compact，`history_archive/` 多一份、新的能被 read。
4. **`lib/agent/act/`**：從 act.py 抽；驗：餵一則有兩個 tool_calls 的 assistant，吐兩則 tool、順序對；`MAX_PARALLEL=2` 結果順序仍對；掛一個 pre_tool 退 10 看到那次不跑。
5. **`lib/agent/round/`**（零件庫、語法糖＝aos-loop 加「這一輪結束就停」，不升成 aos 指令，決定 13）：照 § 2 寫骨架，「從哪接著做」那段要能單獨做一格（給 aos-loop 一格一格跑用，決定 12）；驗：假腦跑完一題退 0、沒題退 10；endpoint 壞掉退 1 且 state／history 不動；掛 `on_error` 印 switch 看到 `endpoint.txt` 換名字再成功。
6. **範本 `demo/agent-nia/`**（人名接 meg、pip…）：照 § 1 擺捷徑與 `.env`；`demo/run.sh` 加一段；驗：WSL 上假腦一題、LiteLLM 一題，`tree -a .stack` 看得到 § 5 的檔。（10-28 晚做了：照第 0 步改成手寫相對路徑的 `parts.json`、不擺捷徑；LiteLLM 那題這台連不上沒跑，見文末 39～41）
7. **aos-ai spawn**：多一種範本（捷徑複製後改絕對）。（10-28 晚做了：複製後把 `parts.json`、`tools.json` 指出範本的相對路徑改成絕對，見文末 42）
8. **測試** `tests/test_round.py`：以上各驗各一案；跑 proto8 全套不退。（10-28 晚做了：範本與 spawn 的案在 `tests/test_nia.py`）
9. **條文**：P-23、P-41 改寫（agent-ops 決定 3；P-41 含「只有 compact 可改寫」）、P-25／C-61 加註（決定 10）、P-20 改「預設」、P-33／C-52 加「round 的參數」一句、N-43 加「分類靠代號」、N-53／C-25 加「一格一次用 aos-loop、一輪用 round，看 `_entry`」（決定 12）；NORMS 待定加這份的代定；code map、demo README、artifact 同步。
10. 黑盒子（claude code）那條：hub 已做，round 不碰（決定 14：aos 歸 aos）。
11. **round 當外部接口**（決定 15）：做一個「問 agent-xxx」的工具（push 一題＋叫一次 round＋印 `out/` 答案），登記進 claude code 用的 tools.json；驗：claude code 經 aos-mcp 問一題拿到答案、agent 不常駐；搶信箱不加保護。（10-28 晚做了：`lib/aos/ask_round`，見文末 43～47；claude -p〔haiku〕經 aos-mcp 問 agent-nia 一題拿到假腦答案）

0. （決定 16，排在第 1 步前）**`proto8/bin/aos-parts`**：add／rm／ls／get／which；驗：註冊的優先、沒註冊走固定名字（捷徑與真資料夾各一）、都沒有退 10、註冊了但路徑壞＝`PartBad`。之後第 5 步 round 叫格一律經 `which`；第 6 步範本改成手寫相對路徑的 `parts.json`（不必擺捷徑）；第 7 步 aos-ai spawn 改成 `aos-parts add`（不複製捷徑）；第 9 步 P-25／C-61 的加註改成「格也走註冊檔，同 aos-tools 的加註；`..` 只在方便用的捷徑」。

每步各一個 commit，每步結尾在 WSL 實跑一次。

<a id="要使用者看的只這一節"></a>

## 已定（原本要使用者看的七條，10-28）

頂層白話地問：四條衝突照新做法直接走、另外三題沒意見就照代定。使用者 10-28 回「照新做法」——七條全部定案（[agent-ops 決定 11](2026-10-28-agent-ops.md#決定10-28)）。四條衝突照新做法走；另外三題使用者沒另外表示，照代定走（依 [user.md「沒回答的邊緣狀況」](../../wf/workflows/common/user.md) 通則）。條文一樣**待實作時改**（§ 7 第 9 步；待辦在 [SESSION-LOG](../../wf/SESSION-LOG.md)）。

(a) 跟既有原則的衝突（照新做法走）：

1. **每格拿 agent 資料夾當第一個參數**，P-33「不給程式根變數」／C-52 加例外——落在 [§ 1 佈局](#1-佈局)（round 跟每一格的參數）與 [§ 2](#2-round一輪本身)（叫法）。理由照舊：aos-exec 解開捷徑後 cwd 在庫那邊，共用件靠 cwd 找不到引用者的其他格；這是跟 fsm 拿 fsm.json 同一種參數、不是環境變數。
2. ~~**兩套引用並存**（照代定）~~——**已由決定 16 取代**：格也全部走註冊檔（另一份 `parts.json`），捷徑只是註冊檔沒寫時的固定名字、方便用——落在 [§ 1 格怎麼找](#格怎麼找註冊檔--固定名字--預設決定-16)。
3. **粒度看 `_entry`**（原本代定「預設一個行程跑完一輪」，改由 agent-ops 決定 12 取代）：`_entry` 寫 aos-loop 就一格一格跑、寫 round 就一次跑完一輪；N-53／C-25 的衝突改寫成「一格一次仍然可用，用 aos-loop」——落在 [§ 2](#2-round一輪本身)（第一條與最後一條）。
4. **只有 compact 可以改寫 history**，其餘只附加（P-41 改寫；壓掉的整份搬 `history_archive/`）——落在 [§ 4 單位介面](#4-單位介面) 的 history。
5. **錯誤分類靠 stderr 代號**（`BrainFailed`／`KeyBad`／`ModelUnknown`／`RequestBad`／`ReplyBad`），結束碼照 N-43 一律 1，`on_error` 讀代號——落在 [§ 4 單位介面](#4-單位介面) 的 endpoint（錯）。
6. **`on_error` 預設停**：能回 retry／switch，沒掛＝stop；P-20 改成「預設」而不是「一律」——落在 [§ 3](#3-掛勾hook)（`on_error`）與 [§ 4](#4-單位介面) 的 endpoint（換手）。

(b) 原則推不出的方向題（照代定）：

7. **round 留在 `lib/agent/round/` 當庫的資料夾程式、用捷徑引用，不升成 aos-round**；它是語法糖＝aos-loop 加「這一輪結束就停」（agent-ops 決定 13）。另外 round 列入外部接口、外部 CLI 不納入 round（決定 14、15），落在 [§ 6](#6-外部指令對內部單位)——本條落在 [§ 1 佈局](#1-佈局)（共用件放 `proto8/lib/agent/<名>/`）與 [§ 7](#7-怎麼落地做一隻新範本-agent10-28-晚實作中) 第 5、10、11 步。

## 實作時代定（10-28 晚，照原則代定、可翻案）

使用者 10-28 晚授權照 § 7 實作；沒定的照原則代定、寫在這裡，不回頭問。

1. **必要的格找不到，不退 lib 標準件，報 `PartMissing`**（原本標未定的那題）。理由：報錯不猜（aos-tools 決定 4、hub-kernel 決定 10「`AOS_HUB` 沒設＝報錯」同調）；KISS「寫什麼就做什麼，不讓特定值偷偷變成另一種行為」（C-56）——退 lib 等於多一層看不見的預設，換掉一格忘了登記時會默默跑標準件、不會發現；查找順序只寫在 aos-parts 一處（C-52）。「零設定就能跑」改由範本自帶手寫的 `parts.json`（相對路徑指 lib）、`aos-ai spawn` 照抄來給。翻案的話只要改 aos-parts 的 `which` 一處。
2. **aos-parts 多兩個用法**（照 aos-tools 的 `call` 那個理由：怎麼找、env 怎麼給只寫在一處，C-52）：
   - `which --json 槽`：一行 JSON `{"slot", "path", "from": "parts"|"fixed", "env": {…}}`，`env` 已解指示詞（`$env`／`$ref` 交給 aos-json，同 aos-tools）。round 叫格前用它——分得出「沒掛」（退 10）與「格自己退 10」（例 `pre_tool` 的 10＝不跑）。
   - `run 槽 [args…]`：找到＝帶上 `env` 換成 `aos-exec 路徑 args…`（結束碼就是那格的）；找不到＝`PartMissing` 退 1（叫你跑卻沒有，是錯）。給 `loop.json` 叫 round 用：`{"argv": ["aos-parts", "run", "round", {"$env": "AOS_CD"}]}`，不用 sh（user/03 少用 sh）；單子的 cwd 是 agent 資料夾，預設的 `./parts.json` 剛好就是那份。
3. **`add` 的形狀**＝`add [--override] [--env K=V]… 槽 XXX`：槽名必給（格不像工具有「預設取檔名」的需要）。槽已登記＝`PartExists`，`--override` 蓋掉（同 aos-tools 決定 11）。
4. **叫格的環境**：註冊檔的 `env` 疊在 round 自己的環境上（同名以註冊檔為準）；`AOS_STACK`、`AOS_WS` 原樣傳（P-16 同一台狀態機）。固定名字那條路沒有 `env`，那格自己的 `.env` 照 aos-exec 的規則讀（預設不蓋，N-58）。
5. **`queue claim` 的寫入順序**：先接 user 訊息進 history（經 `history append`；最後一則已經是 user／tool 就不接）、再寫 `current.txt`、最後才把題目搬進 `cur/`。這樣任何一步中途當掉，重跑都接得上、不會把上一題的答案當成這題的（`cur/` 是空的就重新認領同一題，history 不會接兩次）。

### 做 aos-parts 時再代定的（10-28 晚，第 0 步，代定、可翻案）

6. **指示詞只解要用的那一格**：`parts` 是普通物件時，which／run／get 只把那一格交給 aos-json 解（`parts.json#/parts/<槽>`）；`parts` 本身（或整份檔）是 `$ref` 才整份解。理由：endpoint/openai 的 `env` 寫 `{"$env": "OPENAI_API_KEY"}`，跑假腦時沒設這個變數，不該連 `which round` 都擋（報錯只報自己的，C-56）。`ls` 看全部，所以任何一格解不開都報錯（同 aos-tools 的 ls）。
7. **固定名字在但壞也是 `PartBad`**：壞掉的捷徑、沒 `+x` 又不是 JSON 的檔——有人放了東西，就不當「沒有」（報錯不猜）。
8. **XXX 驗到哪**：資料夾、`+x` 的檔、沒 `+x` 但能當 JSON 讀的檔（第一行 `#!` 跳過，同 aos-exec）就收；`_entry` 對不對不驗，交給 aos-exec（C-52 不替下層驗）。不存在＝`PathMissing`，不是這三種＝`PathBad`（新代號）。
9. **ls／get 只看登記了的**：固定名字不列（槽不設清單，列不出來）；`get` 沒登記＝`PartMissing`；`ls --json`／`get` 的 `env` 印解開後的值（同 aos-tools 的 get 印解開的）。
10. **`--env K=V` 只收字面字串**：要 `$env` 就手寫進 parts.json，或 `aos-json env`；不另開旗標。

### 做 endpoint、act 時再代定的（10-28 晚，第 1、4 步，代定、可翻案）

11. **usage.jsonl 的 `endpoint` 名**＝環境變數 `ENDPOINT_NAME`（註冊檔的 `env` 給，例 `endpoint/litellm` 那格寫 `"ENDPOINT_NAME": "litellm"`）；沒設＝那支 `_entry` 實際所在的資料夾名（`openai`）。理由：endpoint 不知道自己被登記成哪個槽（C-52），資料夾名只分得出種類、分不出同一種的兩份設定，所以要分的人自己寫一個名字；round 叫 `endpoint/<名>` 時要不要順手設，留給第 5 步。
12. **endpoint 的設定缺了就報錯、不偷用預設**：沒設 `AOS_BRAIN_URL`＝`UrlMissing`；stdin 沒給 `model`、也沒設 `AOS_BRAIN_MODEL`＝`ModelUnknown`（agent-dan 原本偷填 `"default"`，C-56「寫什麼就做什麼」不照抄）；`TIMEOUT_MS` 沒設＝120000（同 brain.py 的 120 秒），不是正整數＝`TimeoutBad`。stdin 不是請求體＝`RequestBad`（「我們要送的東西不對」，跟 4xx 同一類）。`tools` 是空陣列就不送（有些 server 收到空 tools 會報錯）；stdin 的其他 key 原樣送。失敗時 stdout 不吐、`usage.jsonl` 不寫。
13. **usage.jsonl 每次問成功都寫一行**，API 沒回 `usage`＝`"usage": null`（行數＝問了幾次）；`model` 記「送出去的」那個（不是回覆裡 server 換過的名字）；`answered_at` 是 UTC 到毫秒。**假腦不寫** usage.jsonl（沒有 API、沒有 usage，不造假數字）。
14. **假腦答「最後一則 user」**（原本 agent-dan 是「這一題」；history 有好幾題時第一則 user 是很早的舊題，最後一則才是現在這題）；messages 裡沒有 user＝`RequestBad`。
15. **endpoint 的第一個參數（agent 資料夾）收下不用**：同一叫法才收；多於一個參數＝`ArgumentsBad`。act 要用它找 `tools.json`、`parts.json`，所以 act 一定要給、要是絕對路徑（aos-exec 走進格以後 cwd 在庫那邊，相對路徑會算錯），不合＝`AgentBad`。
16. **act 吐東西是全有或全無**：一路跑完才一次吐；中途自己這層出錯（`HookFailed`、`ToolsBad`、`PartsBad`）＝stdout 什麼都不吐、退 1，已跑的工具不算（round 照 P-20 停、history 不動，重跑會再跑一次）。`pre_tool` 退 0／10 以外、`post_tool` 退非 0、`post_tool` 的 stdout 不是一個 JSON 物件，都算 `HookFailed`（§ 3 表「其他＝act 失敗」，post_tool 比照）。`post_tool` 的 stdout＝整則取代的 tool 訊息（不是只有 content）。
17. **找掛勾一律經 `aos-parts which --json hook/<點>`**（實作時代定 2）：退 10＝沒掛；退 0／10 以外（例：登記了但壞，`PartBad`）＝`PartsBad`、act 失敗，不當沒掛。拿到就 `aos-exec 路徑 <agent>`，註冊檔的 `env` 疊上去（實作時代定 4）。每個點一次 act 只問一次。
18. **插話看 `$AOS_WS/new/`，不經 queue 格的 `peek`**：信箱的版面是 P-11 的慣例、不是 queue 的內部，直接看最少依賴（queue 格跟 act 同時在做、act 的測試不必先有 queue）；`.` 開頭的不算（N-05）。之後要改走 `queue peek` 只動 act 的 `waiting()` 一處。
19. **平行＝一批一批跑**：`MAX_PARALLEL=N` 就每 N 個一批一起跑、一批跑完才看插話（§ 4「平行模式一批跑完才檢查」）；依序＝一批一個。最後一批後面不看（沒有剩下的可以不跑）。`MAX_PARALLEL` 不是正整數＝`ParallelBad`。
20. **打斷之後**：剩下的 call 各接一則 content「`act: Interrupted 有新題（題名…），這個工具沒跑`」，全部照原順序吐完、**退 10**（「正常、但到此為止」，同 `pre_tool` 的 10），讓 round 分得出「這批被打斷」。**act 不認領新題**（§ 4 原本寫 act 做 `queue claim`，但 act 不寫 history，改由 round 管）：round 看到 act 退 10，先照常把 act 吐的 tool 訊息全部接進 history，再叫 queue 把 `new/` 的新題接進來（題文接成一則 user、題名加進 `current.txt`，`finish` 時一起答，§ 4 queue），然後回去問腦。這個「把新題接進來」的子命令叫什麼、怎麼做由 queue 與 round（第 2、5 步）定。`on_interrupt` 每個空檔都重問（`new/` 還有題、上次說 wait，下一個空檔再問一次）。

### 做 queue、history、compact 時再代定的（10-28 晚，第 2、3 步，代定、可翻案）

21. **插話時再認領一題＝`queue claim --more`**（接上面第 20 條）：`cur/` 有沒有題都取 `new/` 排序最前一題，照第 5 條的三步做；第 ① 步只在 history 最後一則**已是 user** 時不接（被打斷後最後一則是 tool，要接；當掉重跑時最後一則已是這題的 user，不接兩次）；`current.txt`＝`cur/` 原有的再加這題；stdout 這題題名；`new/` 空＝退 10。round 看到 act 退 10、接完 tool 訊息後叫它。
22. **一般 `claim` 遇到 `cur/` 已有題**＝不搬、不碰 history，只把 `cur/` 的題名重寫進 `current.txt`、全部印出來。理由：照第 5 條順序，題目進了 `cur/` 就代表前兩步已做完；這時去看 history 最後一則反而猜不準（可能正在跑工具）。
23. **`finish` 的順序**：先把 `cur/` 每一題的 `out/<題名>` 都寫好（N-05），再一題一題搬 `done/`，最後刪掉 `current.txt`（交完就沒有認領中的題）；中途當掉重跑同樣的答案再寫一次就接上。`cur/` 空＝`QuestionMissing`。答案沒換行結尾就補一個（同 agent-dan 的 act）。
24. **「壓」放在 compact 格，history 的 `compact` 只管換檔**：`history compact` 的 stdin＝新的短版（一行一則，每行都要是 JSON 物件，否則 `HistoryBad`、什麼都不動）；舊的整份用 hard link 收進 `history_archive/<UTC 到毫秒>.jsonl`（不成才複製），再把新的暫存檔改名換上——`history.jsonl` 一刻都不會不見；stdout 印 `history_archive/<名>` 一行（§ 4 表原寫「— → —」，多印這行讓 compact 格記進報告）。加 `--expect-bytes N`：現在不是 N bytes（壓的期間有人接了）＝`HistoryChanged`、不換。理由：§ 4 寫「門檻、怎麼壓是 compact 那格自己的事」，history 只管檔（C-52）；換壓法只換 compact 格、history 不動。
25. **compact 格從 agent-hal 搬來時改的**：設定是這格自己的 env（註冊檔的 `env`），所以拿掉 `COMPACT_` 字首（`MAX_BYTES` 沒設＝65536、`SEG_KB`、`KEEP_TURNS`…）；問腦走 endpoint 格（`ENDPOINT` ＞ `$AOS_STACK/endpoint.txt` ＞ `default`），`MODEL_NOTE／SEG／FINAL` 有設才帶 `model`；agent-hal 自己連網址、內建假腦、token 統計都拿掉（假腦是 endpoint 的事、usage 由 endpoint 寫 `usage.jsonl`），報告只記問了幾次、走了幾次退路。原文改收在 `history_archive/`（不再是 `compact/<run>/orig.jsonl`）；做到一半的產物與報告仍在 `$AOS_STACK/compact/`（§ 5 表要多一列）。換上之後、改名之前當掉：下次那份半成品收成 `compact/stale-<時間>/`，不丟東西。endpoint 退非 0＝`EndpointFailed`、history 不動。
26. **三格的小規矩**：都收 agent 資料夾當第一個參數（history 用不到也收，共通介面），不是資料夾＝`AgentMissing`；queue 的 `pop` 逾時退 10、什麼都不印；`push --wait` 先印題名一行、再印答案，`--timeout-s` 只能跟 `--wait` 一起；`emit` 的 stdin 要是 JSON 物件（`MessageBad`），原樣接一行；題目是資料夾（P-13）就讀裡面的 `prompt.txt`。

### 做 round 時再代定的（10-28 晚，第 5 步，代定、可翻案）

27. **一格一格跑＝`round <agent> --step`**：只做「從哪接著做」判出的下一步就退 0（沒題仍退 10），一步＝認領／問腦／跑工具／交卷四種之一，步裡面的掛勾與 history append 跟著同一步做（問腦＝pre_think＋endpoint＋post_think＋append＋emit；跑工具＝act＋每則 append＋必要時 claim --more＋pause；交卷＝finish＋post_round）。aos-loop 一格一格跑寫 `{"exec": {"argv": ["aos-parts", "run", "round", {"$env": "AOS_CD"}, "--step"]}}`；不加 `--step`＝一個行程跑完一輪。理由：格只有一套（決定 12），「下一步是什麼」只寫在 round 一處（C-52），不另做一支只會判斷的程式。
   > **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round](2026-10-30-aos-round.md#決定10-30)）：順序搬到 `lib/agent/round/fsm-*.json`、現在在哪看 fsm 的 `state.txt`、`--step` 與 `hook/pause` 退場、trace 看 fsm 的行。
28. **`pre_round` 只在認領那一步叫**（`cur/` 空、要認領新題時）；yield 或失敗修好後接著做的那一輪不再叫（§ 3 表寫「認領前」）。
29. **「跑工具」看最後一則 assistant 的 tool_calls 有沒有都回了**，不只看最後一則：act 吐的 tool 訊息是一則一則 append，接到一半當掉，重跑只把還沒回的那幾個交給 act（已回的不重跑）。act 退 10 之後、`claim --more` 之前當掉：重跑看到 tool 都回了＝直接問腦，新題留在 `new/`、下一輪當一般題認領（不追補）。
30. **`cur/` 有題、history 卻是空的**（或最後一則的 role 不認得）＝`round: HistoryBad`、退 1：不猜從哪接著做（正常的 claim 一定先接 user 再搬 `cur/`，第 5 條）。
31. **endpoint 怎麼選、怎麼換**：`endpoint.txt` 去掉頭尾空白，空的＝`default`。switch 的候選＝`parts.json` 裡 `endpoint/<名>` 的槽（`parts` 是指示詞時才經 `aos-parts ls --json` 整份解，免得別格的 `$env` 沒設就擋，同第 6 條）與 `<agent>/endpoint/` 底下不是 `.` 開頭的名字，聯集排序；目前那個之後的下一個、繞一圈（只有一個＝等於 retry），先寫暫存再改名（N-05）。叫 endpoint 時環境先放 `ENDPOINT_NAME=<名>`、註冊檔的 `env` 再疊上去（第 11 條留給這一步的那題：round 順手設，註冊檔寫了以它為準）。
32. **retry／switch 的上限＝round 這格的 `MAX_RETRIES`**（parts.json 裡 round 的 `env` 或 round 格的 `.env`；預設 3，≥0 的整數，不是＝`SettingBad`；C-54 上限 `max_*`）：一次問腦最多重來幾次，retry 與 switch 合算、問成功就歸零；用完＝`round: EndpointFailed`、退 1，`endpoint.txt` 停在最後換到的那個。
33. **on_error 的 stdin＝endpoint stderr 的最後一行**：round 收下 endpoint 的 stderr 只為了給 on_error，收下的原樣印到自己的 stderr（人照樣看得到，不轉述不改寫，P-21）。
34. **格退了它不該退的 10**（history、emit、finish、post_think、pre_round、pre_think、post_round、endpoint〔on_error 說 stop 時〕）＝`round: UnitFailed`、退 1，不把 10 原樣往外傳——免得 loop 當成「沒題」正常停（P-19）。`pause` 退 0／10 以外＝round 以那個碼退。
35. **trace 的 `unit`＝槽名，有子命令就接一個空格再子命令**（`queue claim`、`queue claim --more`、`history append`、`endpoint/default`、`hook/pause`）；沒掛的掛勾、`aos-parts which`、`aos-tools ls` 不記（不是格）；`code`＝那格的結束碼。
36. **問腦前讀一次 history；有掛 `pre_think` 就叫完再讀一次**（compact 可能換掉了）。system＝`<agent>/system.txt`，每次從檔讀、有才帶、不進 history（同 agent-dan）。送給 endpoint 的請求體一行結尾帶換行。
37. **交卷的 stdin＝那則 assistant 的 content**：字串照用、`null`＝空字串、其他形狀＝它的 JSON。
38. **round 收的 agent 資料夾要是存在的絕對路徑**（同 act 第 15 條，`AgentBad`）；`AOS_WS` 要是資料夾（`WsMissing`，要看 `cur/`、`new/`）；`AOS_STACK` 沒設＝`StackMissing`。

### 做範本 agent-nia 時再代定的（10-28 晚，第 6 步，代定、可翻案）

39. **`endpoint/default`＝假腦（`lib/endpoint/fake`）**，LiteLLM 另登記成 `endpoint/litellm`（openai＋`AOS_BRAIN_URL` localhost:4000、`AOS_BRAIN_MODEL` chatgpt-gpt-6-luna-low、`TIMEOUT_MS` 120000）。要用就在 stack 寫 `endpoint.txt`＝`litellm`（§ 4 換手原本的做法，不另開設定）。理由：demo、測試、spawn 出來的第一題零設定就跑得動，不連網；真腦只差一行檔。沒掛 `on_error`，LiteLLM 連不上＝stop（P-20 預設停）。
40. **`hook/pre_think` 預設掛 compact**（`MAX_BYTES` 65536，寫在 parts.json 的 `env`）：§ 4 說 compact 掛這裡；沒超過門檻時只多一格 trace、什麼都不動。代價：每次問腦多叫一格、多讀一次 history（第 36 條）。不要就從 parts.json 拿掉那一列。
41. **範本只有 `_entry`（JSON `["aos-loop", "loop.json"]`）、`loop.json`、`system.txt`、`tools.json`、`parts.json` 五個檔**：沒有 `.env`（設定都在 parts.json 的 `env`）、沒有捷徑（決定 16）。`tools.json` 手寫相對路徑指 `../../lib/base/`（clock、math），同 parts.json 搬家不斷。loop 的 `max` 40＝一次最多答 40 題（每題 round 退 0 一次，最後沒題退 10 停）。

### 做 aos-ai spawn 時再代定的（10-28 晚，第 7、8 步，代定、可翻案）

42. **spawn 改寫註冊檔、不改用 `aos-parts add` 重登記**：複製後 `parts.json`、`tools.json` 每一格的 `path` 若是相對、從範本資料夾算指到範本外面，就換成那個絕對路徑（`normpath`、不解開捷徑，同 `add` 存 abspath）；指在範本裡面的（例 agent-dan 的 `tools/clock`）照舊相對、跟著複製；`env`、其他 key、指示詞（`$ref`／`$env`）原樣；沒有要改的就不寫檔（agent-dan 這類範本一個 byte 都不動）。理由：重登記會把 `env` 拆成 `--env K=V` 再組回去（`$env` 指示詞組不回去，第 10 條），改寫只動 `path` 最少；兩份註冊檔同一種規則（手寫相對＝從檔所在資料夾算）一起處理，跟範本相對捷徑改絕對（10-24）同一個想法。

### 做「問 agent」工具時再代定的（10-28 晚，第 11 步，代定、可翻案）

43. **工具名 `ask_round`、放 `lib/aos/`**：動 aos 自己的東西（別隻 agent 的信箱），是中層；名字跟隔壁的 `ask_agent`（經 aos-ai  spawn＋run 的那支）同一種「動詞_對象」，對象寫 round 分得出走的是哪條路。不併進 `ask_agent`：那支照 aos-ai 的 `agents/<名>/` 佈局、會先 spawn，這支只吃一個已有的 agent 資料夾（C-52 各管各的）。
44. **agent 怎麼給**：參數 `agent`（絕對路徑）＞ 環境變數 `ASK_AGENT`；都沒有＝`AgentMissing`。「問 agent-xxx」固定一隻＝一個工具小資料夾（`.env` 寫 `ASK_AGENT`，`_entry`／`_tooldef.json`／`_metainfo` 捷徑指庫）——§ 1「一格＝`.env`＋`_entry` 捷徑」同一招，tools.json 不必多一種 `env` 欄。`_tooldef.json` 也可自己寫一份（拿掉 agent 參數、改說明）。
45. **被問的 agent 的工作區**＝`ASK_WS` ＞ `$AOS_STACK/<agent 資料夾名>/`（這個工具的小格，P-17；經 act 是 `$AOS_STACK/<工具名>/`，經 aos-mcp 是 `<stack>/<工具名>/`），信箱四個資料夾沒有就建；它的 stack＝`<工作區>/.stack/`（N-57 預設，明寫，不讓外面的 `AOS_STACK`〔工具的小格〕漏進去）。理由：預設不碰叫它的人自己的信箱（放進 `$AOS_WS/new/` 會變成問自己）；同一個工具小格問同一隻，history 接著累積（agent 有記憶）；要跟常駐的那隻共用信箱就設 `ASK_WS`，搶信箱是呼叫者的風險（決定 15）。
46. **重叫 round 的規則**：每次 round 退回來先看 `out/<題名>`，有就收（round 之後的格失敗也照收——答案已寫）；退 0 沒答案＝yield、再叫；退 10＝`AnswerMissing`（題目被別人收走）；其他＝`RoundFailed`（題目留在工作區，再叫一次 round 會接著做）。最多 `ASK_MAX_ROUNDS` 次（預設 20，≥1，`SettingBad`），總時間 `timeout_s`（預設 120、上限 600，跟 bash 一樣寫在 `_tooldef.json`），到了＝收掉正在跑的那群（TERM、2 秒後 KILL）、`AnswerMissing`。放題與叫 round 都經 `aos-parts --file <agent>/parts.json run`（註冊檔的 env 照帶，C-52 怎麼找只在 aos-parts）。
   > **10-30 起由 aos-round 取代**（[thinking 10-30 aos-round § C](2026-10-30-aos-round.md#c-換過去的路結論)）：ask_round 改成重叫 `aos-round`（一次一格）直到 fsm 的 state 回到 `idle` 且 history 有比題目新的 assistant；`ASK_MAX_ROUNDS` 改名 `ASK_MAX_STEPS`（預設 200）。
47. **stdout＝答案原文**（`out/<題名>` 整份），不包 JSON：契約 2「文字工具印文字」，外面的 CLI 直接看得懂；`ask_agent` 印 JSON 是它轉 aos-ai 的歷史形狀，這支不跟。

**10-29 註**：使用者 10-29 傍晚定 agent 的輸入是 queue（對話）、不是信箱；接單以後放在 tools 裡，agent 做完事自己用 tool 去看信箱 → [10-28 medium 決定 32](2026-10-28-medium.md#十七agent-的輸入是-queue不是信箱10-29-傍晚)。本檔 round 從工作區 `new/` 收題（P-11）、`ask_round` 把題放進對方 `new/`，都是信箱形狀，要不要改等之後再看，現在不動。
