# 2026-10-28 agent 的一輪（round）：掛勾點、單位、endpoint 介面、引用、落地步驟

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-28 agent-ops](2026-10-28-agent-ops.md)（決定 1～10：各單位都是 aos 函數、六題的回答；本份是它的「結論／代定」）、[10-28 hub-kernel](2026-10-28-hub-kernel.md)（決定 11 prompt＝queue、13 插話不訂死）、[10-28 aos-tools](2026-10-28-aos-tools.md)、[10-28 hub-adapter](2026-10-28-hub-adapter.md)（信箱協議）、[10-24 compact](2026-10-24-compact.md)（agent-hal 的土法 compact）、[10-24 tool-lib](2026-10-24-tool-lib.md)（捷徑指到庫）｜相關條文：[CONVENTION P-11～P-26、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32～P-39](../docs/CONVENTION/06-巢狀.md)、[C-61](../docs/CONCEPTS/05-agent.md)、[N-43](../docs/NORMS/01-總則.md)、[N-57～N-61](../docs/NORMS/10-基礎設施-定義與工作區.md)

規矩見 [thinking/README](README.md)。這份**全部是照原則代定、可翻案**，使用者定的在 agent-ops 的「決定」；要使用者看的只有文末那一節。只寫文件、程式沒改、這次不動手做。

## 白話版

一隻 agent 就是一個資料夾，裡面每一格都是一個小程式（aos 函數）：收題的 `queue`、記對話的 `history`、問腦的 `endpoint`、跑工具的 `act`，加上幾個可以不裝的插座 `hook/`。`round` 是把這些格照順序叫一遍的那支骨架，也是 aos 函數；loop 反覆叫 round。格都是共用標準件，agent 資料夾裡只放捷徑（symlink）指過去；要換哪一格，就把那條捷徑換成自己的資料夾。執行中的東西全在 `$AOS_STACK`。

## 1. 佈局

```
agent-x/
  _entry        ["aos-loop", "loop.json"]                                   P-05
  loop.json     {"exec": {"argv": ["aos-exec", "round", {"$env": "AOS_CD"}], "timeout_ms": 600000}, "max": 40}
  .env          agent 層的設定（可無）
  system.txt    system 訊息（P-41 照舊）
  tools.json    腦能叫的工具，aos-tools 管（10-28 aos-tools）
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
- **捷徑用相對路徑**（repo 內，C-61「相對捷徑、兩份一起搬也不斷」、agent-liv 的做法）；repo 外的 agent 用絕對捷徑（aos-ai spawn 的做法）。只管 Linux；Windows checkout 捷徑變普通檔（10-24 已知）。捷徑目標裡的 `..` 跟 P-25／C-61「零個 `..`」字面相撞，使用者已定照新做法走（agent-ops 決定 10）。
- **跟 tools.json 的對照**：工具走註冊檔、存絕對路徑（10-28 上午定）；agent 自己的格走捷徑（10-28 下午定）。代定**兩套並存、照種類分**：腦叫的工具＝tools.json，agent 的格＝捷徑。要不要合一見文末第 2 條。

## 2. round：一輪本身

- **叫法**：`aos-exec round <agent 資料夾>`；loop 每次叫一次。結束碼照 P-19：`0`＝這輪好了（或中途 yield，狀態在 stack，下次接著）、`10`＝沒題目、其他＝失敗停下等人（P-20）。
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
- 一個行程跑完一輪，不是一次一格。要回到「一次一格」的粒度，掛 `hook/pause` 永遠退 10 就是（每做完一批工具就 yield）。預設不 yield——這跟 N-53／C-25 的「每次短促」怎麼對，見文末第 3 條。

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
| `aos-hub`（黑盒子 CLI） | 整個 round 換成 hub 包的一個 aos 函數 | agent-ops 附帶結論 |
| loop 的 ctl.json | 外部停、暫停 | 現成（N-06），round 不另做 |

## 7. 怎麼落地：做一隻新範本 agent（這次不做）

1. **`lib/endpoint/fake/`、`lib/endpoint/openai/`**：從 agent-dan 的 brain.py 把「問腦」那段抽出來；驗：`echo '{"messages":[…]}' | aos-exec lib/endpoint/fake X` 吐一則 assistant；openai 接 LiteLLM 吐真的、`usage.jsonl` 多一行；拔掉 key 看到 `KeyBad`、指錯埠看到 `BrainFailed`（用 tests/dead_brain.py）。
2. **`lib/agent/queue/`**：從 brain.py 的認領段＋aos-say／listen 抽；驗：push → peek 看得到 → claim 搬到 cur/、current.txt 有 → finish 寫 out/、done/ 有；withdraw 已認領的報錯。
3. **`lib/agent/history/`**：append／read／compact；compact 搬 agent-hal 的三步；驗：塞一份大的 history 跑 compact，`history_archive/` 多一份、新的能被 read。
4. **`lib/agent/act/`**：從 act.py 抽；驗：餵一則有兩個 tool_calls 的 assistant，吐兩則 tool、順序對；`MAX_PARALLEL=2` 結果順序仍對；掛一個 pre_tool 退 10 看到那次不跑。
5. **`lib/agent/round/`**：照 § 2 寫骨架；驗：假腦跑完一題退 0、沒題退 10；endpoint 壞掉退 1 且 state／history 不動；掛 `on_error` 印 switch 看到 `endpoint.txt` 換名字再成功。
6. **範本 `demo/agent-nia/`**（人名接 meg、pip…）：照 § 1 擺捷徑與 `.env`；`demo/run.sh` 加一段；驗：WSL 上假腦一題、LiteLLM 一題，`tree -a .stack` 看得到 § 5 的檔。
7. **aos-ai spawn**：多一種範本（捷徑複製後改絕對）。
8. **測試** `tests/test_round.py`：以上各驗各一案；跑 proto8 全套不退。
9. **條文**：P-23、P-41 改寫（agent-ops 決定 3）、P-25／C-61 加註（決定 10）、P-20 改「預設」、P-33 加「round 的參數」一句；NORMS 待定加這份的代定；code map、demo README、artifact 同步。
10. 黑盒子（claude code）那條：hub 已做，round 不碰。

每步各一個 commit，每步結尾在 WSL 實跑一次。

## 要使用者看的（只這一節）

(a) 跟既有原則的衝突：

1. **P-33「不給程式根變數」／C-52 徹底切割 ↔ 每一格拿 agent 資料夾當第一個參數**。aos-exec 解開捷徑後 cwd 在庫那邊，共用件靠 cwd 找不到引用者的其他格（compact 要找 endpoint、act 要找 tools.json），所以 round 把 agent 資料夾明給每一格。不給的後果：共用件只能複製、不能捷徑（demo 現在的做法）。給的後果：格知道「我是誰的格」，跟 fsm 拿 fsm.json 是同一種參數、不是環境變數，但 P-33 那句要加例外。
2. **兩套引用並存**：腦叫的工具走 `tools.json`（絕對路徑註冊檔，10-28 上午定）、agent 自己的格走捷徑（10-28 下午定）。一隻 agent 裡兩種寫法。合一的兩條路：格也進一份註冊檔（像 round.json），或工具也回到捷徑（10-24 tool-lib 的路，10-28 剛換掉）。我代定並存、照種類分，不合一。
3. **N-53／C-25「agent 每次被叫只走一格、短促」 ↔ round 一個行程跑完一輪**（問腦、跑工具、再問腦……到吐出答案）。agent 審視自己靠的 stack 檔每一步都還在，但「每次之間」變成「每輪之間」；要回到一格一次，掛 `hook/pause` 永遠退 10。預設要不要 yield，我定不 yield。
4. **P-41「history 只附加、不改寫」 ↔ compact 改寫**（壓掉的整份搬 `history_archive/`）。P-41 本來就要重寫（決定 3），這句要改成「只有 compact 可以改寫，其餘只附加」。
5. **N-43「錯一律退 1、不用結束碼分種類」 ↔ 六題之 3 要錯誤分類**。代定分類靠 stderr 的代號（`BrainFailed`／`KeyBad`／`ModelUnknown`／`RequestBad`／`ReplyBad`），`on_error` 讀代號、不看結束碼；429 跟 503 都歸 `BrainFailed`，要細分看原因裡的 HTTP 碼。
6. **P-20「出錯就停、不重試」**（agent-ops 已列）：`on_error` 能回 retry／switch；範本不掛＝照舊停。條文改成「預設」。

(b) 原則推不出的方向題：

7. **round 要不要升成 aos 的指令**（`aos-round`，像 `aos-fsm fsm.json`），還是留在 `lib/agent/round/` 當庫的資料夾程式、用捷徑引用？規範說 aos 只有四支指令、aos-agent 只做範本不包邏輯（10-23），但 aos-tools 已經是 bin 裡的第五支。我代定留在 lib、捷徑引用；差別是 PATH 上多不多一支。
