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
- **找不到怎麼辦**：註冊檔寫了但路徑壞了＝報錯（`PartBad`），**不**退去找固定名字（報錯不猜）。註冊檔沒寫、固定名字也沒有：掛勾＝沒掛的預設行為（§ 3 表）；round、queue、history、act、endpoint 這些必要的格＝`PartMissing`、round 退 1（P-20）。是否改成「必要的格找不到就用 lib 的標準件」**未定**（來不及細想，見文末）。
- **endpoint 的候選**＝註冊檔裡 `endpoint/<名>` 與資料夾 `endpoint/` 底下同名的聯集（同名以註冊檔為準）；`endpoint.txt` 照舊寫名字，沒有＝`endpoint/default`。
- **工具清單不套這條**：工具只認 tools.json（aos-tools 現狀），不退去掃 `tools/<名>/`——那正是使用者嫌「太土太粗暴」的做法（aos-tools 決定 7），給模型看的清單要明白登記。
- **共用件怎麼登記、搬家**：照 aos-tools 結論第 6 點——`add` 存絕對路徑；手寫的相對路徑從 parts.json 所在資料夾算，所以 git 裡的範本 `parts.json` 手寫 `../../lib/agent/queue` 這種相對路徑、整個 repo 搬家不斷；`add` 寫的絕對路徑搬家要重新 add（使用者選的代價）。
- **「捷徑方便使用」具體是**：不想登記時，在 agent 資料夾放一個固定名字的捷徑（或真的資料夾）就能用；`aos-parts add` 收捷徑路徑也行（照 aos-tools 存 abspath、不解開捷徑）。不另做「產生捷徑」的指令。

## 2. round：一輪本身

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
| `compact` | — → —；太大就壓短 |

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
- **插話檢查**：依序模式在兩個 call 之間 `queue peek`，有東西就問 `hook/on_interrupt`；`interrupt`＝剩下的 call 不跑（各接一則 tool 訊息「被打斷」）、`queue claim` 把新題接進 history、吐出去讓 round 再問腦；平行模式一批跑完才檢查。

### tools 生效時間點（使用者六題之 1：「變成掛在哪個點」）

不另定三種模式：round 每次問腦前 `aos-tools ls`、act 每次叫工具 `aos-tools call`，都現讀 `tools.json`。所以 `aos-tools add` 下次問腦就看得到、`rm` 之後腦還叫＝`ToolUnknown` 回給腦。要「這一輪固定」或「只對這一題有效」，掛 `pre_round`／`post_round` 自己改 `tools.json`（或改成指到題目資料夾的 `$ref`，aos-tools 已支援）。中途改清單 prompt cache 會失效，是掛的人自己的代價。

## 5. stack 裡有什麼

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `current.txt` | queue claim | 認領中的題名，一行一題（插話多題） |
| `history.jsonl` | history append／compact | 對話（P-41） |
| `history_archive/<UTC>.jsonl` | history compact | 壓掉的原文整份 |
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

## 7. 怎麼落地：做一隻新範本 agent（這次不做）

1. **`lib/endpoint/fake/`、`lib/endpoint/openai/`**：從 agent-dan 的 brain.py 把「問腦」那段抽出來；驗：`echo '{"messages":[…]}' | aos-exec lib/endpoint/fake X` 吐一則 assistant；openai 接 LiteLLM 吐真的、`usage.jsonl` 多一行；拔掉 key 看到 `KeyBad`、指錯埠看到 `BrainFailed`（用 tests/dead_brain.py）。
2. **`lib/agent/queue/`**：從 brain.py 的認領段＋aos-say／listen 抽；驗：push → peek 看得到 → claim 搬到 cur/、current.txt 有 → finish 寫 out/、done/ 有；withdraw 已認領的報錯。
3. **`lib/agent/history/`**：append／read／compact；compact 搬 agent-hal 的三步；驗：塞一份大的 history 跑 compact，`history_archive/` 多一份、新的能被 read。
4. **`lib/agent/act/`**：從 act.py 抽；驗：餵一則有兩個 tool_calls 的 assistant，吐兩則 tool、順序對；`MAX_PARALLEL=2` 結果順序仍對；掛一個 pre_tool 退 10 看到那次不跑。
5. **`lib/agent/round/`**（零件庫、語法糖＝aos-loop 加「這一輪結束就停」，不升成 aos 指令，決定 13）：照 § 2 寫骨架，「從哪接著做」那段要能單獨做一格（給 aos-loop 一格一格跑用，決定 12）；驗：假腦跑完一題退 0、沒題退 10；endpoint 壞掉退 1 且 state／history 不動；掛 `on_error` 印 switch 看到 `endpoint.txt` 換名字再成功。
6. **範本 `demo/agent-nia/`**（人名接 meg、pip…）：照 § 1 擺捷徑與 `.env`；`demo/run.sh` 加一段；驗：WSL 上假腦一題、LiteLLM 一題，`tree -a .stack` 看得到 § 5 的檔。
7. **aos-ai spawn**：多一種範本（捷徑複製後改絕對）。
8. **測試** `tests/test_round.py`：以上各驗各一案；跑 proto8 全套不退。
9. **條文**：P-23、P-41 改寫（agent-ops 決定 3；P-41 含「只有 compact 可改寫」）、P-25／C-61 加註（決定 10）、P-20 改「預設」、P-33／C-52 加「round 的參數」一句、N-43 加「分類靠代號」、N-53／C-25 加「一格一次用 aos-loop、一輪用 round，看 `_entry`」（決定 12）；NORMS 待定加這份的代定；code map、demo README、artifact 同步。
10. 黑盒子（claude code）那條：hub 已做，round 不碰（決定 14：aos 歸 aos）。
11. **round 當外部接口**（決定 15）：做一個「問 agent-xxx」的工具（push 一題＋叫一次 round＋印 `out/` 答案），登記進 claude code 用的 tools.json；驗：claude code 經 aos-mcp 問一題拿到答案、agent 不常駐；搶信箱不加保護。

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

7. **round 留在 `lib/agent/round/` 當庫的資料夾程式、用捷徑引用，不升成 aos-round**；它是語法糖＝aos-loop 加「這一輪結束就停」（agent-ops 決定 13）。另外 round 列入外部接口、外部 CLI 不納入 round（決定 14、15），落在 [§ 6](#6-外部指令對內部單位)——本條落在 [§ 1 佈局](#1-佈局)（共用件放 `proto8/lib/agent/<名>/`）與 [§ 7](#7-怎麼落地做一隻新範本-agent這次不做) 第 5、10、11 步。

## 未定（決定 16 來不及細想的，10-28）

使用者下班前收尾，下面先標未定、照代定的寫法走：

- 必要的格（round、queue、history、act、endpoint）註冊檔和固定名字都沒有時：代定報錯 `PartMissing`；另一個做法是退去用 lib 的標準件（零設定就能跑，但等於多一層看不見的預設）。
