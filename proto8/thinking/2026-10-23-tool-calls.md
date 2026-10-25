# 2026-10-23 腦的工具呼叫（`tool_calls`）：範本的形狀

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前一份：[在 fsm 上做 aos-agent 與 aos-kernel](2026-10-23-agent-kernel.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。相關條文：[C-19、C-46、C-50、C-61](../docs/CONCEPTS/05-agent.md)、[C-52、C-54、C-56](../docs/CONCEPTS/01-設計理念.md)、[N-50、N-53](../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-36、N-38](../docs/NORMS/07-基礎設施-組合子.md)、[P-08、P-12、P-17、P-20、P-23～P-26、P-33、P-35](../docs/CONVENTION.md)；前情：[rewrite-order 第 4 題、② 腦的工具呼叫](2026-10-19-rewrite-order.md)、[NORMS 待定](../docs/NORMS/08-待定.md)。

## 使用者原文（整理版，10-23）

> 我原本想說是在fsm的基礎上去做aos-agent，乃至於aos-kernel。

（頂層問 aos-agent 是範本還是程式）

> 範本

（頂層提議：先定 `tool_calls` 的形狀，再從 demo 的 bob 改出一個真的會叫模型、會用工具的 agent，最後做 kernel；問要不要開始規劃 `tool_calls`）

> litellm我開了，去做吧。

之後補兩句：

> 盡量都用gpt的

> 試驗場放在~/code/try

## 決定（使用者定）

- aos-agent＝範本，不是一支包了邏輯的程式（[10-23 agent 與 kernel](2026-10-23-agent-kernel.md)）。
- 腦走本機 LiteLLM（`http://localhost:4000/v1`，不用 key），模型盡量用 gpt 系；模型名放設定、不寫死在程式裡。
- 真 agent 實跑的地方（工作區、題目、stack、log）放 `~/code/try/` 底下；範本、測試、條文照舊在 repo。

## 結論（fable 照原則定的細節；代定、可翻案）

### 1. 工具給模型看的說明＝工具資料夾裡的 `tool.json`

每個工具照舊是一個資料夾程式 `tools/<名>/`（C-61、N-50、P-25）。資料夾裡多一份 **`tool.json`**＝給模型看的說明，內容就是 OpenAI tool 的 function 物件去掉 `name`：`{"description": "一句話", "parameters": {JSON Schema}}`（外部 API 的欄位名照原名，C-54 例外）。**工具名＝資料夾名**（C-54 複數資料夾裝同類、裡面不重複類別），組 `tools` 陣列時由程式填進去；`tool.json` 裡其他 key 忽略（C-48）。沒有 `tool.json` 的資料夾不算腦可以叫的工具。

```
agent-dan/                 範本（混合寫法，接 agent-bob；idle 是資料夾，think／act 是內嵌單子）
  _entry                   #!/bin/sh、exec aos-loop loop.json
  loop.json                {"exec": "fsm.json", "max": 40}
  fsm.json                 三態不變：idle → think → act → idle（P-08）
  .env                     AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low（模型名在設定；URL 由叫它的人給，沒給＝假腦）
  system.txt               核心人格（C-19）：每次問腦時當 system 訊息送、不進 history；沒有這個檔＝不送
  idle/_entry              同 bob：cur/ 或 new/ 有題退 0，沒題退 10
  brain.py                 think 格：認領題目、把 tools/*/tool.json 組成 tools、帶 history 問腦、回覆一行接進 history
  act.py                   act 格：照腦的決定動手——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案
  tools/math/_entry        工具：stdin 收 {"expr": "17*23"}、stdout 印 391（python3，只做四則運算）
  tools/math/tool.json     {"description": "...", "parameters": {...}}
  tools/clock/_entry       工具：stdin 不讀、stdout 印 UTC 時間
  tools/clock/tool.json

$AOS_STACK/                stack（P-16）：state.txt、trace.jsonl、current.txt（P-12）
  history.jsonl            對話（C-46：history 累積在 stack；一行一則 OpenAI message）
  math/、clock/            工具的小格（P-17；工具自己的 stack）
```

### 2. 參數怎麼交給工具：stdin 進、stdout 出，不拼字串

act 對每個 `tool_call` 做同一件事：`AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>`，**模型給的 `arguments`（JSON 字串）原樣從 stdin 餵進去，工具的 stdout 整段就是結果**（像 demo 的 stamp）。用 `subprocess`＋argv 陣列，不經 `sh -c`（使用者 10-15「少用 sh」）。這是範本定的「腦可以叫的工具」的介面（P-26 說參數怎麼進由工具說明定——這裡的說明就是範本本身）；要把另一隻 agent（cathy 那種認 `new/` 的）給腦當工具，在那個工具資料夾自己的 `_entry` 裡做 stdin → `ws/new/`、`ws/out/` → stdout 的轉接，範本與 act 不知道、不管（C-52）。`tool.json` **不加** `input` 之類的 key（rewrite-order 第 4 題的 `input: stdin|inbox` 不採用，C-56 最後一步清掉）。

### 3. 結果怎麼回到腦、history 落在 stack

`$AOS_STACK/history.jsonl`，一行一則 OpenAI message，照 API 原形（`{"role": "user", "content"}`、`{"role": "assistant", "content", "tool_calls"}`、`{"role": "tool", "tool_call_id", "content"}`）；只附加、不改寫（像 `trace.jsonl`）。system 訊息不存（每次從 `system.txt` 讀）；模型想的內容不收（P-23）。

- brain.py：認領題目後，**history 最後一則不是 user／tool 時**（空的、或上一題已答完）才把題目接成一則 user；接著帶整份 history＋tools 問腦，回覆（`choices[0].message`，只留 `role`、`content`、`tool_calls`）接一行。腦失敗就什麼都不接、退 1（P-20）；重跑時 history 最後一則已是 user／tool，不會重複接題目。
- act.py：讀最後一則 assistant。**有 `tool_calls`**：每個還沒有對應 `tool` 訊息的 id 各跑一次工具（跑一個接一行；中途失敗重跑時只補沒回的），全部回完退 0。**沒有 `tool_calls`**：`content` 寫成 `$AOS_WS/out/<題名>`、題目 `cur/` → `done/`，退 0。
- 跑完一輪 act 退 0 → idle：題目還在 `cur/`＝接著做（P-12），think 帶 history 再問；腦不再叫工具時 act 才交答案。一題的 trace 就是 `idle think act idle think act idle …`。

### 4. fsm 不變：三態，不加 tool 格

`idle → think → act → idle` 照 P-08。fsm 一格只有一個 `next`（N-36），「叫工具還是交答案」由腦決定、act 照做（P-24「想跟做分開」：腦的決定就是 plan，act 不問腦），不另開一格、不讓格改寫 state。（rewrite-order ② 寫的「三態變四態」不採用，可翻案：要四態就是 act 拆成 tool 與 act 兩格，兩格都要「沒事做就退 0 直接過」。）

### 5. 呼叫 LLM 那一格由範本自己的 `brain.py` 跑

不新寫 aos 的指令、不動 repo 根 `core/llm`（舊一代，沒 tools）。brain.py 是範本的一部分、Python 純標準庫（`urllib`），跟 bob 的一樣每隻 agent 一份（P-25 不跨 agent 互指）。腦的位置照 P-23：`AOS_BRAIN_URL`（沒設＝假腦）、`AOS_BRAIN_MODEL`（範本 `.env` 給 `chatgpt-gpt-6-luna-low`，`.env` 不蓋外面已設的）、`AOS_BRAIN_KEY`（LiteLLM 不用；有設才帶）。假腦：history 最後一則是 user 且有 `clock` 工具就叫一次 `clock`，否則回 `FAKE ANSWER to: 題目`（demo／測試不連網也走得完「想 → 工具 → 想 → 答」）。

### 6. 錯、逾時、對話太長

- **逾時**：think、act 都是內嵌單子，各自 `timeout_ms`（think 120 秒、act 60 秒；P-22、P-36 逾時寫在最靠近會卡的那格）；aos-exec 到時 SIGTERM 整群，那格＝失敗、agent 停（P-20）。工具沒有自己的逾時 key；要的話工具自己的入口寫成單子（P-40）。
- **腦連不上、HTTP 非 2xx**＝`BrainFailed`；**回覆不是 OpenAI 的形狀**（沒有 `choices[0].message`）＝`ReplyBad`；**腦叫了 `tools/` 裡沒有的工具**＝`ToolUnknown`；**`arguments` 不是 JSON**＝`ArgumentsBad`；**工具退非 0**（含 10，P-35）＝`ToolFailed`。前兩種（自己這層連不上腦、腦回壞的）照 P-20 停：stderr 一行 `agent-dan: 代號 原因`、退 1、state 不動、history 不接那一則；人修好再 `aos-exec` 一次從同一格接著做（N-53，不自動重試、不數連錯）。後三種（叫工具出的問題）10-24 起接成一則 tool 訊息回給腦、不停（見文末「10-24 定」）。代號照 C-54（主詞＋Failed／Bad／Unknown）。
- **對話太長**：範本不管——history 像 trace 一樣不設上限（P-14 不為清理加機制）；要忘記＝換 stack（C-65）。「對話太長怎麼辦」是 10-15 留下的方向題（[SESSION-LOG](../../wf/SESSION-LOG.md)），這次不定。

### 7. 名字（C-54 R1～R12）

| 名字 | 一句白話 | 怎麼來 |
|---|---|---|
| `agent-dan` | 會問真模型、會用工具的問答 agent（範本） | demo 的 agent 用人名（bob、ann、cathy），接下一個 |
| `tool.json` | 這個工具給模型看的說明 | 主詞是工具；單一檔用單數；外部 API 欄位名照原名 |
| `history.jsonl` | 跟腦的對話，一行一則 | `history` 不可數照原樣；JSON Lines 帶 `.jsonl` |
| `system.txt` | 腦的核心人格（system 訊息） | 外部 API 的名字；純文字帶 `.txt` |
| `act.py` | act 格的身體 | 對應格名，同 ann 的 `act.py` |
| `tools/math`、`tools/clock` | 算四則運算、報 UTC 時間 | 都是整字、不是縮寫，不進縮寫表 |
| `BrainFailed`、`ReplyBad`、`ToolUnknown`、`ToolFailed`、`ArgumentsBad` | 見第 6 點 | 主詞＋四種結尾 |

### 8. 試驗場與驗證

- 真跑：`~/code/try/agent-dan/`（工作區 `ws/`、題目 `ws/new/`、stack `ws/.stack/`、log）；不刪裡面原有的東西。
- 測試（`proto8/tests`）：不連真模型的用一支假 server（`http.server`）照劇本回 `tool_calls`／答案，驗 tools 陣列、history 接法、工具失敗與未知工具回給腦、腦失敗重跑不重複接題；連真模型的那個 `localhost:4000/v1/models` 連不上就 skip。
- `demo/run.sh` 多跑一段 agent-dan（假腦、叫 clock）。

## 還沒定、要使用者看的（不擋實作）

- **agent 當腦的工具時題目怎麼交**（[NORMS 待定](../docs/NORMS/08-待定.md) 方向問題甲）：範本只定「stdin 進、stdout 出」；要把 cathy 那種給腦叫，轉接寫在那個工具自己的 `_entry`。另一條路是 `tool.json` 加 `input` key 讓 act 認兩種。推薦前者。
- **腦叫了不存在的工具**：10-24 定了，回給腦（見文末「10-24 定」）。
- **對話太長**：見第 6 點，方向題。

## 實作後補的結論（10-23，範本 `demo/agent-dan`、慣例 P-41；都是代定、可翻案）

- 真跑一次（`~/code/try/agent-dan/`，LiteLLM `chatgpt-gpt-6-luna-low`）：題目「請用工具算 17*23，並用工具查現在 UTC 幾點，最後用一句話回答。」→ 腦一次叫兩個工具（math、clock）→ 答「17×23 = 391，現在 UTC 時間是 2026-10-23 13:19:57。」；trace `idle think(2.5 秒) act idle think(2.0 秒) act idle(10)`，結束碼 0。
- 錯誤代號除第 6 點五種，範本另有 `StackMissing`、`QuestionMissing`（new/ 與 cur/ 都空）、`HistoryBad`（history.jsonl 有一行不是 JSON；act 找不到 assistant 可照做；call 缺 `id` 或 `function.name`）；math 工具自己的錯 `ExprBad`。
- `tool.json` 讀不懂或不是物件＝當作沒有（組 tools 時跳過，不報錯）；只帶有寫的 `description`／`parameters`。
- 腦回覆：沒 `role` 補 assistant；`content` 一定留（null 也留）；`tool_calls` 非空才留、每個只留 `id`／`type`／`function`。
- `arguments` 不是字串、或是空字串＝`ArgumentsBad`（空字串不是 JSON；有些模型叫無參數工具會給空字串，之後可能撞到）。
- 工具名只認 `tools/` 底下有 `tool.json` 的資料夾（`../` 之類一律 `ToolUnknown`）；`aos-exec` 起不來也算 `ToolFailed`。
- 答案先寫 `out/.<題名>` 再改名（N-05）。math 指數上限 1000、不吃 bool、`4/2` 印 `2.0`。
- `loop.json`、`fsm.json`、`tool.json` 是 JSON，沒有 R1 那行檔頭說明；其餘檔都有。
- 測試 `proto8/tests/test_dan.py` 14 個（10-24 晚改成回給腦後 15 個：工具失敗、未知工具、`../`、ArgumentsBad 改驗回給腦，多一個「aos-exec 不在 PATH 照舊停」，「只補沒回的」改成直接叫 act；以下是 10-23 的）（假 server 劇本：兩輪、不叫工具、工具失敗停住、未知工具、腦 500 後重跑不重複接題、第二個工具失敗後只補那一個；`../` 擋掉、ArgumentsBad、連不上、ReplyBad 兩種、三個代號、math 本體；真模型一個，LiteLLM 不在就 skip）；改掉 ToolUnknown 檢查會紅 2 個、改掉「已回過的 id 跳過」會紅 1 個。

## 10-24 補記

- think、act 兩格的 `exec` 從寫死的 `"fsm.json#/states/think/body"` 改成 `{"$env": "AOS_CF", "$path": "#/states/think/body"}`（act 同理）——使用者 10-24「先改成不寫死檔名的寫法」。aos-fsm 10-23 晚起會解格的 `exec` 指示詞，換出來是 fsm.json 的絕對路徑接 `#/states/think/body`。「相對於這格」的寫法還沒定，見 [2026-10-24](2026-10-24-exec-relative.md)。

## 10-24 定：叫工具與小念頭的失敗回給腦

使用者 10-24 對 WAIT_USER 兩題（「腦叫了不存在的工具是停下等人還是回給腦」「失敗時停下等人，還是把失敗交回給腦／上一層」）回：「都隨意」——交給我們照建議定，**代定、可翻案**。

**定的**：
1. **叫工具出的問題回給腦、不停**：工具退非 0（stdout 照收、尾巴加「(工具 X 結束碼 N)」，stderr 一行 `agent-dan: ToolFailed X 結束碼 N（回給腦）` 給人看）、腦叫了 `tools/` 裡沒有的工具（`act: ToolUnknown X（能叫的：…）`）、`arguments` 不是 JSON（`act: ArgumentsBad X：原因`），都接成一則 tool 訊息，腦下一輪自己決定（改參數、換工具、照實說）。做法照 agent-pip（10-24 pi-tools 代定 9），agent-dan 的 act 跟它只剩錯誤行開頭不同。
2. **環境壞了照舊停**（P-20）：工作區或 stack 不在（`StackMissing`）、history 壞（`HistoryBad`）、腦連不上或回壞的（`BrainFailed`、`ReplyBad`）、工具起不來（PATH 上沒有 aos-exec＝`ToolFailed …起不來`），stderr 一行、退 1、state 不動。
3. **小念頭失敗回給母體的腦**（agent-gus，[thoughts 定 10](2026-10-24-thoughts.md)）：小念頭退非 0、逾時、沒交答案，那一步的結論就是「小念頭 sN 失敗了（目標：…）：原因」，照樣接進母體 history、不停；needs 它的步不起，結論寫「沒起：要先拿到 sN 的結論，但它失敗了」。
4. **跟著改的**：從 agent-dan 抄的 eve、fay、hal、kai 三種都改；meg、talk 的 member、gus、pyfix-agent 原本只有「退非 0」回給腦，補上沒有的工具與 arguments 壞兩種。dan 自己的 `tools/math` 錯也印在 stdout（腦才看得到原因，照 lib 契約）。`aos-ai spawn` 的 `--tool-errors` 拿掉——範本本身就回給腦，原樣複製，不再換 act（不留兩套）。
5. **沒動的**：talk 的自動回信寄不成照舊寫在答案後面、環境壞了才停；agent-gus 的 `thought.json`（給別的程式叫的入口）照舊 `ThoughtFailed` 退 1——它是工具，停不停由叫它的 agent 決定；fay 的 `attach`（給人用的 `cli_session`）叫錯工具名照舊報錯；ann、bob 這類不問腦的 agent 照 P-20。

**原則上的對法**：P-20「任一格失敗＝停」不變——工具出錯時 act 格本身沒失敗，工具的錯是那次呼叫的結果，act 照實交給腦（C-52、C-53「錯誤只處理自己的」；lib/README「工具只報錯、停不停由 agent 決定」）。P-41 原寫「一律停」的那句加了 10-24 註。

**真跑**（10-24 晚，LiteLLM `chatgpt-gpt-6-luna-low`）：
- agent-dan（`~/code/try/agent-dan/ws-errors-1024/`）：題目「先用 math 算 1/0，再算 (17*23…」→ 腦叫 math 1/0，拿到「math: ExprBad 除以零 (工具 math 結束碼 1)」→ 自己再叫 17*23 → 答「1/0 計算失敗（除以零），17*23 的結果是 391。」結束碼 0，約 5 秒。叫不存在的工具（`ws-unknown-1024/`，題目硬要它叫 weather）：腦不肯叫清單外的工具、直接答「沒有 weather 工具」，ToolUnknown 只有假 server 測過。
- agent-gus（`~/code/try/thoughts/ws-real-fail-1024/`）：question2 三部分、`THOUGHT_TIMEOUT_S=4` 逼三個小念頭都逾時 → 三則「小念頭 sN 失敗了…逾時」接進母體 → 母體的腦自己叫一次 run_python 三部分一起做完、交報告。結束碼 0，約 17 秒。

**翻案位置**：agent-dan 改回停＝`demo/agent-dan/act.py` 那三處換回 `die(...)`（10-24 這筆 commit 之前的版本），抄它的幾隻同理；gus 改回停＝`demo/agent-gus/fork.py` 有失敗的步時 `die("ThoughtFailed", …)`、needs 照舊等。
