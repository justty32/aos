← [回入口 CONVENTION.md](../CONVENTION.md)｜段落：四～七｜上一份：[01-保證佈局入口](01-保證佈局入口.md)｜下一份：[03-shell版與inst版](03-shell版與inst版.md)

## 四、題目與答案

- **P-11** 題目＝`$AOS_WS/new/<題名>`，純文字、一題一檔；開始做時把題目搬到 `$AOS_WS/cur/<題名>`（認領）；答案＝`$AOS_WS/out/<題名>`，跟題目同名；做完把題目從 `cur/` 搬到 `$AOS_WS/done/<題名>`。階段名照 Maildir：`new/`＝還沒做、`cur/`＝已認領處理中、`done/`＝做完；`out/` 是產出放的地方、不是階段名（使用者 10-23 選「改成一致的階段名」）。**結果＝工作區內容，沒有別的結果通道。**（拍板點 2；C-65 工作區只放交辦的東西與成果；C-34 求值＝空間狀態的變化。這是 agent-bob 的做法；「agent 之間傳題目走 inbox」當共同形狀，inbox 先不管〔使用者 10-19；現行資料夾名是 `new/`〕，不當規則）
- **P-12** 一次做一題：取 `new/` 裡檔名排序最前面的那個、搬到 `cur/`，題名寫進 `$AOS_STACK/current.txt`；`cur/` 裡已經有認領了沒做完的（例如 think 的腦失敗、人修好重跑），先接著做那題、不從 `new/` 拿新的，idle 也把 `cur/` 算成還有題目（所以 P-20 的「接著做同一題」對 think 失敗也成立）。（原型現狀；拍板點 1）
- **P-13** 需要附檔時升級成資料夾：`new/<題名>/` 裡題文叫 `prompt.txt`、其餘檔是附檔；答案 `out/<題名>/` 也是資料夾、主答案叫 `answer.txt`。一個 agent 認哪種形狀寫在它自己的說明；agent-bob 只認一題一檔。（拍板點 2「需要附檔再升級成資料夾」；檔名本稿定，照 C-54 小寫單數）
- **P-14** agent 只動 `new/`、`cur/`、`out/`、`done/` 與 `$AOS_STACK`，工作區其他東西不碰。`done/` 只進不出，清理是人的事。（C-65 工作區保持乾淨；C-56 不為清理加機制）

## 五、stack

- **P-15** 執行中的一切（狀態、草稿、紀錄、小格）只寫 `$AOS_STACK`，**定義資料夾不被寫**；所以同一個 agent 可以同時被兩個工作區跑。（C-65；§ 2；原型測試已驗）
- **P-16** agent 自己的格（idle／think／act）共用同一個 `$AOS_STACK`——它們是同一台狀態機。stack 裡放什麼、叫什麼，agent 自訂；agent-bob 的 `state.txt`、`current.txt`、`plan.txt`、`trace.jsonl` 是例子不是規範。（拍板點 1「stack 內部自由」；§ 2「剩下的你自己想」；§ 3）
- **P-17** 叫**別的**資料夾程式（工具、另一個 agent）時，給它自己的 stack（**小格**）：`sub=$AOS_STACK/<名>/`、`AOS_STACK=$sub aos-exec tools/<名>`（例：cathy 的 act 用 `AOS_STACK=$sub aos-exec tools/stamp`，工具的 `runs.txt` 落在 `$AOS_STACK/stamp/`）。小格名＝工具資料夾名（P-38 靠這點）。被叫的只看到自己的 stack、不知道上面有誰。叫完不自動收——留著給人看；要收由呼叫方自己 `rm`。巢狀時小格怎麼給、被叫者的工作區放哪，見第十二節 P-32。（§ 3「子程式的 stack 由 agent-bob 自己訂，有可能他會是 AOS_STACK/think, /act」；C-52 子 agent 只看自己的 stack；C-65 stack＝「叫工具時開的小格」；C-67 stack 放哪由呼叫方決定；拍板點 3「人來看」。這是原討論稿拍板點 4 的答案）
- **P-18** 一個工作區同時跑兩個 agent 時，呼叫方給不同的 `AOS_STACK`（例 `$AOS_WS/.stack/bob/`）；預設值只保證「一個工作區一個 agent」不撞。（C-67；C-53 入口默認正常、誤用不歸組件管）

## 六、停與錯

- **P-19** 結束碼三種：`0`＝這次好了、下一次；`10`＝正常停（idle 看 `new/` 空了）；其他非 0＝失敗。loop 收到 10 以 0 結束；收到其他非 0 以那個碼結束；跑滿 `max` 以 0 結束、stderr 不寫（N-43 正常退出不噴 stderr；要知道有沒有跑滿看 `trace.jsonl` 行數）；loop 自己收到 SIGINT／SIGTERM／SIGHUP 時收完那次以 128＋N 結束（P-36）。（拍板點 1；原型現狀。跟 C-63 相撞處使用者 10-19 定照用、C-63 作廢，[ideas § 9](../../thinking/2026-10-19-ideas.md)；N-43）
- **P-20** 任一格失敗＝整個 agent 停下來等人：fsm 不換狀態、loop 以那個碼結束；人修好後再 `aos-exec` 一次，從 `$AOS_STACK/state.txt` 接著做同一格、同一題。不自動重試、不數連錯。（拍板點 3；N-53 腦出錯那次 phase 不動；N-38）
- **P-21** 誰的錯誰自己講：格的錯寫在格自己的 stderr；fsm 什麼都不轉述；loop 只說「第幾次、誰、結束碼幾」。（C-53；N-43 每層只說自己）
- **P-22** 逾時：shell 版沒人管——某格卡住（模型沒載入、網路不通）loop 只會等，也殺不到孫程式。要逾時就把那格換成 inst 版、寫 `timeout_ms`（P-29）：直接寫 `"exec": {"argv": …, "timeout_ms": …}`，fsm 行程內當監工收整群（[thinking 10-24](../../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）；或寫 `"exec": "fsm.json#/states/<名>/body"`、單子放 `body`，由 aos-exec 當監工收整群（P-07）。（N-41「靠那張 inst 的 timeout_ms 守」；inst 討論的結論）

## 七、腦與工具

- **P-23** 腦＝OpenAI 相容的 chat completions 端點，由環境變數 `AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY` 指定；`AOS_BRAIN_URL` 沒設＝假腦（demo 預設）。只取回覆的 `content`（有工具時加 `tool_calls`），模型想的內容不收、不存。這台電腦不跑本機模型。（原型現狀；使用者 10-15「維持 openai 格式」「模型想的內容丟掉」（[thinking 10-15 topics/02](../../thinking/2026-10-15-topics/02-agent工具與試146.md)）；§ 6；變數名照 C-54 全大寫底線）。腦的模型名放範本的 `.env`（`AOS_BRAIN_MODEL`；`.env` 不蓋外面已設的），端點 `AOS_BRAIN_URL` 由叫它的人給；家機走 LiteLLM `http://localhost:4000/v1`（不用 key），範本預設 `chatgpt-gpt-6-luna-low`（使用者 10-23「盡量都用gpt的」）。範本 [demo/agent-dan](../../demo/README.md)、P-41。經 LLM kernel 跑時（閘門 `aos-gate`），環境裡有 `AOS_KERNEL_REPORT`＝kernel 給的回報檔；腦願意就把 API 回覆的 `usage` 物件原樣寫進去（先寫暫存再改名），kernel 拿它記 token、算額度；不寫＝kernel 只算次數。usage 不進 history。範本 agent-dan 的 `brain.py` 有寫（約五行）；使用者 10-24「都按建議做」＝照 [rewrite-order 第 3 題](../../thinking/2026-10-19-rewrite-order.md)推薦，見 [thinking 10-24 llm-kernel](../../thinking/2026-10-24-llm-kernel.md#token-回報與額度10-24-下午)。
- **P-24** 想跟做分開：think 問腦、只把「要做什麼」寫進 `$AOS_STACK/plan.txt`；act 照 plan 動手、不問腦。能寫死的步驟（搬檔、寫檔）放在 act 這種程式格，不交給模型。agent-dan 沒有 `plan.txt`——腦的決定（`$AOS_STACK/history.jsonl` 最後一則 assistant）就是 plan，act 照它叫工具或交答案、不問腦（P-41）。（C-22 能寫死的節點換成程式；C-25）
- **P-25** 工具＝`tools/<名>/` 子資料夾程式，**放在叫它的那一格的資料夾裡**（`act/tools/cathy/`），格裡寫 `aos-exec tools/<名>`：地址是從自己 cwd 起算的相對路徑、永遠零個 `..`、不靠 PATH；`AOS_WS` 自然傳下去（要換工作區見 P-32）；工具要不要碰工作區、怎麼碰，是工具自己的事、風險設計者自管；工具裡是不是另一個 agent，呼叫者不知道也不管。stack 照 P-17。細節與理由見 P-33。（C-61 不用 PATH、地址在自己資料夾裡；N-55；C-66；C-52）
- **P-26** 工具的參數怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；aos-exec 保證 args 與 stdin 原樣送到。（§ 4）入口是單子時也成立：args 接在單子 `argv` 的尾巴，單子沒寫 `stdin` 就接呼叫者的（§ 20 使用者沒異議、照預設「串流沒寫＝接呼叫者的」）；單子自己寫了 `stdin: 檔` 是它自己選的，不算 aos-exec 沒送到。
- **P-41 腦的工具呼叫（`tool_calls`）**（範本 [demo/agent-dan](../../demo/README.md)；[thinking 2026-10-23-tool-calls](../../thinking/2026-10-23-tool-calls.md)）：
  - **工具說明**：腦可以叫的工具照舊是 `tools/<名>/` 資料夾程式（P-25），裡面多一份 `tool.json`＝給模型看的說明，內容就是 OpenAI tool 的 function 物件去掉 `name`（`{"description": …, "parameters": {JSON Schema}}`，外部 API 欄位名照原名）；**工具名＝資料夾名**，組 `tools` 陣列時由程式填；`tool.json` 裡其他 key 忽略（C-48）。沒有 `tool.json` 的資料夾不算腦可以叫的工具。
  - **10-28 起改成工具註冊檔**（使用者 10-28「像現在這樣掃tool.json，實在太土太粗暴，不夠靈活」「現有的...改吧」，[thinking 10-28 aos-tools](../../thinking/2026-10-28-aos-tools.md)）：腦能叫哪些工具＝**範本資料夾的 `tools.json`**（[aos-tools](../../bin/README.md) 管，`add／rm／ls／get`），brain 跑 `aos-tools ls --json` 組 `tools`、act 跑 `aos-tools call 名` 叫（arguments 照舊從 stdin 進、`AOS_STACK=$AOS_STACK/<名>/` 照舊）。說明檔改名 `tool.json` → `_tooldef.json`（資料夾裡 `_tooldef` 或 `_tooldef.json`，先找不帶副檔名的；JSON 檔用 `_tooldef` key；可執行檔用 `--tooldef`），內容不變；**工具名＝登記名**（預設資料夾名）。上一條與下面講 `tool.json`、`aos-exec tools/<名>` 的地方照這條讀。登記了但壞掉的工具＝brain／act 自己這層的錯 `ToolsBad`（停、人修好再跑）。topdown 的 agent 還沒換，照舊掃 `tools/*/_tooldef.json`。
  - **介面**：模型給的 `arguments`（JSON 字串）原樣從 stdin 餵進去，工具的 stdout 整段就是結果（像 stamp）；用 argv 陣列叫、不經 `sh -c`。每個工具一個小格：`AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>`（P-17）。要把另一隻 agent 給腦當工具，轉接寫在那個工具資料夾自己的 `_entry`，範本不管（C-52）。
  - **對話**：`$AOS_STACK/history.jsonl`，一行一則 OpenAI message（照 API 原形），只附加、不改寫；system 訊息每次從範本的 `system.txt` 讀、不存；模型想的內容不收（P-23）。
  - **三態不變**（P-08）：腦的決定就是 plan（P-24）。think 問腦、回覆接一行；act 看最後一則 assistant——有 `tool_calls` 就逐個跑工具、結果接回 history、退 0 回 idle，題目還在 `cur/`，所以 think 帶 history 再問（P-12）；沒有 `tool_calls` 才把 `content` 寫成答案、題目搬 `done/`。
  - **錯**：腦連不上或 HTTP 非 2xx＝`BrainFailed`、回覆不是 OpenAI 的形狀＝`ReplyBad`、叫工具時 aos-exec 起不來＝`ToolFailed`（範本另有 `StackMissing`、`QuestionMissing`〔new/ 與 cur/ 都空〕、`HistoryBad`〔history.jsonl 有一行不是 JSON、或沒有 assistant 可照做〕）。這些一律 stderr 一行 `agent-dan: 代號 原因`、退 1、state 不動、history 不接那一則；人修好再 `aos-exec` 一次從同一格接著做（P-20）。叫了 `tools/` 裡沒有的工具（`ToolUnknown`）、`arguments` 不是 JSON（`ArgumentsBad`）、工具退非 0（含 10，P-35）這三種不停：接成一則 tool 訊息回給腦（act 格沒失敗，工具的錯是那次呼叫的結果；P-20 不變；使用者 10-24「都隨意」，代定可翻案，[thinking tool-calls 文末](../../thinking/2026-10-23-tool-calls.md#10-24-定叫工具與小念頭的失敗回給腦)）。逾時是 think、act 各自單子的 `timeout_ms`（P-22）。history 不設上限，要忘記＝換 stack。
  - （C-19、C-46、C-52、C-61、N-50、P-17、P-23～P-26、P-33、P-35；使用者 10-23「範本」「litellm我開了，去做吧。」「盡量都用gpt的」；細節是照原則代定、可翻案）

