# aos agent 慣例（proto8-2，2026-10-19 結論版）

← [proto8-2](README.md)｜原話與拍板：[thinking/ideas](thinking/2026-10-19-ideas.md)｜跟 proto8 原則相撞、使用者已全部裁定：[CONFLICTS.md](CONFLICTS.md)｜proto8 原則：[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)

**aos 本身只保證三個環境變數和一支 `aos-exec`**（使用者 § 4）。其餘全是慣例：我們自己人寫 agent 時照抄的標準形狀，照抄的人不用想、看別人的 agent 一眼就懂（C-54）。**agent-bob 現在的樣子就是標準，stack 裡面自由**（拍板點 1）。

每條後面括號是依據：§ 幾＝[ideas](thinking/2026-10-19-ideas.md) 裡使用者原話的段號；拍板點 1～3＝ideas § 8；C-xx／N-xx＝proto8 的概念與規範；引不到的、這份自己定的，標「本稿定」。程式還沒照這份改的地方列在第十節。**10-19 第二輪**（§ 10）：範本改成混合寫法（第二、三、八節改寫）、巢狀層層疊疊的規則（第十二節 P-32～P-39）。

## 一、aos 保證的（不是慣例，是底）

- **P-01** aos 只訂三個環境變數：`AOS_ENTRY`＝入口在資料夾裡的相對位置，預設 `.aos/exec`，**是可執行檔，或旁邊的 `$AOS_ENTRY.json` 單子**（兩個都在用可執行檔；P-28 (B)）；`AOS_WS`＝工作區（使用者的檔與成品在哪）；`AOS_STACK`＝執行中狀態放哪，預設 `$AOS_WS/.aos/`。（§ 1、§ 2、§ 3；N-55）
- **P-02** `aos-exec DIR [WS [args...]]`＝「在 WS 這個工作區，執行 DIR 這個程式」。WS 省略＝`-`；`-`＝沿用現有 `$AOS_WS`，沒設才用 `.`。慣例用法：`cd workspace && aos-exec ../agent-bob`。（§ 4、§ 5）
- **P-03** aos-exec 只做五件事：把 WS 轉絕對路徑設成 `AOS_WS`；`AOS_STACK` 沒設就設預設值、建資料夾；把自己的 `bin/` 加進 PATH（入口才找得到 `aos-loop`、`aos-exec`）；`cd DIR`；`exec` 入口（可執行檔，或沒有它時交給 aos-inst 跑 `$AOS_ENTRY.json`），多的 args 與 stdin 原樣交給它。**起跑時 cwd＝DIR**；之後程式愛 cd 去哪、「這次要做啥」怎麼收，都是它自己的事。（§ 1、§ 4）
- **P-04** DIR 或 WS 不存在、入口缺或不可執行：aos-exec 非 0 結束、stderr 一行原因。（N-43、N-29 精神；aos 自己的錯一律退 1）

## 二、佈局（每檔一句）

混合寫法（§ 10 使用者「好主意」）：狀態表一律寫在 `fsm.json`；一行講完的格內嵌單子；有真邏輯的格 `val` 寫子資料夾名；留 `trace.jsonl`。程式還沒照這張改，見第十節。

```
agent-bob/                 一個 agent＝一個資料夾程式（§ 1）
  .aos/exec                入口，兩行：#!/bin/sh、exec aos-loop loop.json（§ 4、P-05）
  loop.json                {"run": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}：每圈拍一次 fsm、最多幾圈（P-06）
  fsm.json                 整張狀態表（P-07、P-27）：idle→"idle"（資料夾）、think→單子、act→"act"（資料夾）
  idle/.aos/exec           格：inbox 有題→0 往下走；沒題→10 請 loop 停（P-19）
  brain.py                 think 格的身體（單子 python3 brain.py，stdout 導到 $AOS_STACK/plan、逾時 120 秒）：
                           取一題（P-12）、題名寫 stack 的 current、問腦（假腦或 OpenAI 相容端點，P-23），答案印 stdout
  act/.aos/exec            格：把 plan 當題目交給 tools/cathy，拿她的答案寫 $AOS_WS/out/、題目搬 done/（P-24、P-32）
  act/tools/cathy/         act 的工具＝另一隻完整 agent，同一套範本（.aos/exec、loop.json、fsm.json、idle/、brain.py、act/）；
                           act 裡寫 aos-exec tools/cathy（P-33）
  act/tools/cathy/act/tools/stamp/   cathy 的 act 的工具：stdin 前面加一行時間戳印出來、自己 stack 裡 runs 計次

workspace/                 ＝$AOS_WS，使用者的（§ 2）
  inbox/<題名>             題目：純文字、一題一檔（拍板點 2）
  out/<題名>               答案：跟題目同名
  done/<題名>              做完的題目搬來這
  .aos/                    預設 $AOS_STACK（§ 2）＝bob 的 stack：state、current、plan、trace.jsonl（P-16）
  .aos/cathy/              cathy 的小格＝她的 stack（P-32）：state、current、plan、trace.jsonl
  .aos/cathy/ws/           cathy 的工作區（bob 備好題目、拿答案的地方）：inbox/ out/ done/
  .aos/cathy/stamp/runs    stamp 的小格（P-17）
```

stack 樹就是呼叫樹：`.aos/cathy/stamp/` 一眼看出「bob 叫了 cathy、cathy 叫了 stamp」（P-38）。

## 三、入口、loop、fsm

- **P-05** 入口 `.aos/exec` 一定帶 shebang（`#!/bin/sh`），下一行 `exec aos-loop loop.json`。（§ 4 原話「#usr/bin/sh aos-loop loop.json」。沒有 `#!` 的檔只有從 sh 叫才跑得起來，從 Python、C++ 直接 exec 會失敗，不合 § 1「目標必須是可執行檔」；`exec` 少一層行程、訊號直達 loop——本稿定）
- **P-06** `loop.json` 只有兩個欄位：`run`＝每圈 `aos-exec` 誰（字串，子資料夾），或每圈跑哪張單子（物件，行程內直接跑，結束碼取它的 `code`）、`max`＝最多幾圈。loop 每圈起一次 `run`，看它的結束碼決定下一步（P-19）。（§ 1；拍板點 1；欄位名為原型自訂）
- **P-07** fsm 一拍只跑一格：讀 `$AOS_STACK/state`（沒有＝`start`），跑那格；那格 0 才寫下一個狀態、退 0；非 0 就不換狀態、以原碼退。每拍之間狀態都落在 stack，人看得到。**標準＝`bin/aos-fsm fsm.json`**（§ 10）：表長 `{"start","states":{名:{"val","next"}}}`，`val` 字串＝`aos-exec` 那個子資料夾（相對 cwd＝agent 資料夾）、物件＝單子（行程內跑）；每拍在 `$AOS_STACK/trace.jsonl` 追加一行 `{"at","state","code","signal","timed_out","ms"}`（`at`＝這拍開始的 UTC 時間，第二輪加，P-38）。shell 版 fsm（自己讀 state、`case` 換狀態，原 `agent-bob/fsm/.aos/exec`）是對照寫法，state 檔同一個檔、同一格式，兩種可互換；原檔靠 git 歷史。（C-62、N-53 agent 是被外面 loop 一拍一拍驅動的狀態機；N-36 一拍一格、表一定明寫）
- **P-08** 標準三態 `idle → think → act → idle`。要加狀態＝`fsm.json` 加一格（資料夾格就再加一個子資料夾）；表一定明寫、不靠慣例檔名。`idle` 既是起點也是終點：inbox 空了退 10 時 state 停在 `idle`，所以跑完的 agent 再被叫一次是從頭開始（P-34 靠這點）。（拍板點 1；N-36 表一定明寫）
- **P-09** 每一格都是資料夾程式。fsm 只看格的結束碼，不讀格的 stderr、不管格裡面怎麼做（同步等腦、或丟請求下一拍再看，都行）。（C-52、N-38、N-41）
- **P-10** 格之間要傳的東西寫成 stack 裡的檔（agent-bob：`current`＝正在做哪題、`plan`＝腦的草稿），不走 stdout。（N-37「格之間要傳的東西由格自己寫成檔」；§ 2）

## 四、題目與答案

- **P-11** 題目＝`$AOS_WS/inbox/<題名>`，純文字、一題一檔；答案＝`$AOS_WS/out/<題名>`，跟題目同名；做完把題目搬到 `$AOS_WS/done/<題名>`。**結果＝工作區內容，沒有別的結果通道。**（拍板點 2；C-65 工作區只放交辦的東西與成果；C-34 求值＝空間狀態的變化。這是 agent-bob 的做法；「agent 之間傳題目走 inbox」當共同形狀，inbox 先不管〔使用者 10-19〕，不當規則）
- **P-12** 一次做一題：取 inbox 裡檔名排序最前面的那個，題名寫進 `$AOS_STACK/current`。（原型現狀；拍板點 1）
- **P-13** 需要附檔時升級成資料夾：`inbox/<題名>/` 裡題文叫 `prompt`、其餘檔是附檔；答案 `out/<題名>/` 也是資料夾、主答案叫 `answer`。一個 agent 認哪種形狀寫在它自己的說明；agent-bob 只認一題一檔。（拍板點 2「需要附檔再升級成資料夾」；檔名本稿定，照 C-54 小寫單數）
- **P-14** agent 只動 `inbox/`、`out/`、`done/` 與 `$AOS_STACK`，工作區其他東西不碰。`done/` 只進不出，清理是人的事。（C-65 工作區保持乾淨；C-56 不為清理加機制）

## 五、stack

- **P-15** 執行中的一切（狀態、草稿、紀錄、小格）只寫 `$AOS_STACK`，**定義資料夾不被寫**；所以同一個 agent 可以同時被兩個工作區跑。（C-65；§ 2；原型測試已驗）
- **P-16** agent 自己的格（idle／think／act）共用同一個 `$AOS_STACK`——它們是同一台狀態機。stack 裡放什麼、叫什麼，agent 自訂；agent-bob 的 `state`、`current`、`plan`、`trace.jsonl` 是例子不是規範。（拍板點 1「stack 內部自由」；§ 2「剩下的你自己想」；§ 3）
- **P-17** 叫**別的**資料夾程式（工具、另一個 agent）時，給它自己的 stack（**小格**）：`sub=$AOS_STACK/<名>/`、`AOS_STACK=$sub aos-exec tools/<名>`（例：cathy 的 act 用 `AOS_STACK=$sub aos-exec tools/stamp`，工具的 `runs` 落在 `$AOS_STACK/stamp/`）。小格名＝工具資料夾名（P-38 靠這點）。被叫的只看到自己的 stack、不知道上面有誰。叫完不自動收——留著給人看；要收由呼叫方自己 `rm`。巢狀時小格怎麼給、被叫者的工作區放哪，見第十二節 P-32。（§ 3「子程式的 stack 由 agent-bob 自己訂，有可能他會是 AOS_STACK/think, /act」；C-52 子 agent 只看自己的 stack；C-65 stack＝「叫工具時開的小格」；C-67 stack 放哪由呼叫方決定；拍板點 3「人來看」。這是原討論稿拍板點 4 的答案）
- **P-18** 一個工作區同時跑兩個 agent 時，呼叫方給不同的 `AOS_STACK`（例 `$AOS_WS/.aos/bob/`）；預設值只保證「一個工作區一個 agent」不撞。（C-67；C-53 入口默認正常、誤用不歸組件管）

## 六、停與錯

- **P-19** 結束碼三種：`0`＝這圈好了、下一圈；`10`＝正常停（idle 看 inbox 空了）；其他非 0＝失敗。loop 收到 10 以 0 結束；收到其他非 0 以那個碼結束；跑滿 `max` 以 0 結束並在 stderr 提一句。（拍板點 1；原型現狀。與 C-63 相撞，使用者 10-19 定：照用，見 [CONFLICTS 4](CONFLICTS.md)）
- **P-20** 任一格失敗＝整個 agent 停下來等人：fsm 不換狀態、loop 以那個碼結束；人修好後再 `aos-exec` 一次，從 `$AOS_STACK/state` 接著做同一格、同一題。不自動重試、不數連錯。（拍板點 3；N-53 腦出錯那拍 phase 不動；N-38）
- **P-21** 誰的錯誰自己講：格的錯寫在格自己的 stderr；fsm 什麼都不轉述；loop 只說「第幾圈、誰、結束碼幾」。（C-53；N-43 每層只說自己）
- **P-22** 逾時：shell 版沒人管——某格卡住（模型沒載入、網路不通）loop 只會等，也殺不到孫程式。要逾時就把那格換成 inst 版、寫 `timeout_ms`（P-29）。（N-41「靠那張 inst 的 timeout_ms 守」；inst 討論的結論）

## 七、腦與工具

- **P-23** 腦＝OpenAI 相容的 chat completions 端點，由環境變數 `AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY` 指定；`AOS_BRAIN_URL` 沒設＝假腦（demo 預設）。只取回覆的 `content`（有工具時加 `tool_calls`），模型想的內容不收、不存。這台電腦不跑本機模型。（原型現狀；[lib agent.md](../proto8/lib/agent.md) 使用者 10-15「維持 openai 格式」「模型想的內容丟掉」；§ 6；變數名照 C-54 全大寫底線）
- **P-24** 想跟做分開：think 問腦、只把「要做什麼」寫進 `$AOS_STACK/plan`；act 照 plan 動手、不問腦。能寫死的步驟（搬檔、寫檔）放在 act 這種程式格，不交給模型。（C-22 能寫死的節點換成程式；C-25）
- **P-25** 工具＝`tools/<名>/` 子資料夾程式，**放在叫它的那一格的資料夾裡**（`act/tools/cathy/`），格裡寫 `aos-exec tools/<名>`：地址是從自己 cwd 起算的相對路徑、永遠零個 `..`、不靠 PATH；`AOS_WS` 自然傳下去（要換工作區見 P-32）；工具要不要碰工作區、怎麼碰，是工具自己的事、風險設計者自管；工具裡是不是另一個 agent，呼叫者不知道也不管。stack 照 P-17。細節與理由見 P-33。（C-61 不用 PATH、地址在自己資料夾裡；N-55；C-66；C-52）
- **P-26** 工具的參數怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；aos-exec 保證 args 與 stdin 原樣送到。（§ 4）

## 八、shell 版與 inst 版

- **P-27** 標準範本＝**混合寫法**，就是第二節 agent-bob 的樣子：入口 `#!/bin/sh`＋`exec aos-loop loop.json`；`loop.json` 內嵌單子拍 `aos-fsm fsm.json`；**狀態表一律寫在 `fsm.json`**；一行講完的格（think：跑哪支程式、輸出導去哪、多久逾時）內嵌單子；有真邏輯的格（idle 看 inbox、act 叫工具搬檔）`val` 寫子資料夾名、裡面是 shell；留 `trace.jsonl`。要頻繁改的東西（流程、逾時、誰接誰）全在一份 `fsm.json` 裡；要寫邏輯就開資料夾、用 shell，不用把 shell 塞進 JSON。（§ 10 使用者「好主意」；拍板點 1；§ 7「想要簡單直接，那就上 shell 指令」「單子是資料……在不希望資料夾佈局太複雜的時候很好用」。改掉 10-19 早上的「標準＝shell 版 fsm」）
- **P-28** inst 單子（`{"argv", "cwd", "stdin", "stdout", "timeout_ms", …}`，key 表與跟 proto8 不同的兩處見 [README 的 `bin/aos-inst`](README.md)）是可選的升級，四種用法都行、可以在同一個 agent 裡混用：(1) `.aos/exec` 是 shebang 小殼、讀旁邊的 `exec.json`；(2) loop／fsm 的設定裡直接內嵌單子（**已做**，`aos-loop`／`bin/aos-fsm`、`demo/agent-ann`）；(A) `.aos/exec` 第一行 `#!/usr/bin/env aos-inst`、後面接 JSON（**已做**，`bin/aos-inst`）；(B) aos-exec 認 `.aos/exec.json`，入口＝可執行檔或單子（**已做**；(1) 小殼＝`#!/bin/sh`＋`exec aos-inst .aos/exec.json "$@"`，也已有測試）。（§ 7「1 跟 2 都要」「接法 3 感覺也是 OK 的」「AB 都可以」；四種都做完了）
- **P-29** 範本給的是 (2)：`fsm.json` 裡內嵌單子（think 那格），範本就是 `demo/agent-bob/fsm.json`（見下面範例）。(A)、(1)、(B) 仍都能用——一個資料夾格自己想要逾時、想用單子寫入口時用 (A)（`.aos/exec` 第一行 `#!/usr/bin/env aos-inst`）——但不是範本。資料夾格要逾時，更直接的寫法是在 `fsm.json` 把那格寫成 `{"argv": ["aos-exec", "act"], "timeout_ms": 600000}`（P-36）。（§ 10；§ 7「AB 都可以」。改掉 10-19 早上的「範本先給 (A)」；這是原討論稿拍板點 5 的答案）
- **P-30** 用 inst 換到的是四樣：argv 是陣列、不靠 sh 拼字串；`timeout_ms` 逾時收尾、不留孫程式；結果是結構化的（結束碼、訊號、有沒有逾時、毫秒）；單子是資料、可內嵌進別的 JSON。「不走 sh 更快」實測不成立：單獨起一個 aos-inst（Python）比一層 sh 慢 5～6 倍，agent-bob 一圈殼的開銷對一輪 LLM 不到千分之二；省得到的只有 loop／fsm 在行程內直接 `run()` 那種。（§ 7 使用者「都還好。主要是單子是資料這塊……結果是結構化的這塊也很舒服」；10-19 在 WSL 實量的結論）
- **P-31** 單子要指到 stack 或工作區底下的檔，寫 `{"$env": "AOS_STACK", "path": "plan"}`：意思是「那個環境變數指的資料夾底下的 `plan`」，照 `os.path.join` 接（`AOS_STACK` 結尾有 `/`、`AOS_WS` 沒有，兩種都對；`path` 寫絕對路徑就是絕對路徑）。不帶 `path` 就是整個變數值。**只有 `$env`，沒有 `$ref`**（單子本來就能內嵌，不必拆檔）；變數沒設＝aos-inst 自己的錯、退 1。不用字串內插（`"$AOS_STACK/plan"`）：那是把規則埋進字串的暗規則。（本稿定；PLAN 第一節決定 3；C-48／C-55 值長成物件、同層加屬性；C-56 寫什麼就做什麼；N-45 `$env` 是正式機制）

### 範例：同一隻 agent 的三種寫法

**混合（標準範本，`demo/agent-bob/fsm.json`、cathy 同款）**——表一份、think 是單子、idle／act 是資料夾：

```json
{"start": "idle",
 "states": {
   "idle":  {"val": "idle", "next": "think"},
   "think": {"val": {"argv": ["python3", "brain.py"],
                     "stdout": {"$env": "AOS_STACK", "path": "plan"},
                     "timeout_ms": 120000},
             "next": "act"},
   "act":   {"val": "act", "next": "idle"}}}
```

格寫成 `{"val", "next"}` 照 N-36。挑題、寫 `current`、問腦這種動態的事由 `brain.py` 做，單子是靜態資料，只負責「跑誰、輸出導去哪、多久逾時」。act 的身體（`act/.aos/exec`，bob 的）示範叫一隻 agent 當工具（P-32、P-35）：

```sh
#!/bin/sh
# act：把 plan 當題目交給 tools/cathy（另一隻 agent），拿她的答案寫 $AOS_WS/out/<題名>，題目搬 done/
[ -n "$AOS_STACK" ] || { echo "agent-bob: 沒設定 AOS_STACK" >&2; exit 1; }
name=$(cat "$AOS_STACK/current")
sub=$AOS_STACK/cathy/                          # cathy 的小格＝她的 stack；她的工作區＝$sub/ws/
mkdir -p "$sub/ws/inbox" "$AOS_WS/out" "$AOS_WS/done"
cp "$AOS_STACK/plan" "$sub/ws/inbox/$name"     # 照 cathy 的說明備題：inbox 一題一檔
AOS_STACK=$sub aos-exec tools/cathy "$sub/ws" || { echo "agent-bob act: cathy 失敗" >&2; exit 1; }
cp "$sub/ws/out/$name" "$AOS_WS/out/$name"     # 答案從她的 out/ 拿
mv "$AOS_WS/inbox/$name" "$AOS_WS/done/$name"
```

**全內嵌（對照，`demo/agent-ann`）**——零子資料夾、零 `aos-exec` 層：三格都是單子，各指一支小腳本（`idle.py`：inbox 空退 10；`brain.py`；`act.py`：plan 寫 out、題目搬 done）。資料夾裡只有 `.aos/exec`、`loop.json`、`fsm.json` 和三支 `.py`。適合「格全是一行、不叫工具」的小 agent；一旦某格要叫工具、要用 sh 搬檔，就回到混合寫法開資料夾。

```json
{"start": "idle",
 "states": {
   "idle":  {"val": {"argv": ["python3", "idle.py"]}, "next": "think"},
   "think": {"val": {"argv": ["python3", "brain.py"],
                     "stdout": {"$env": "AOS_STACK", "path": "plan"},
                     "timeout_ms": 120000},
             "next": "act"},
   "act":   {"val": {"argv": ["python3", "act.py"]}, "next": "idle"}}}
```

**全 shell（對照，10-19 早上的 agent-bob，原檔靠 git 歷史）**——`loop.json` 是 `{"run": "fsm", "max": 20}`，`fsm/.aos/exec` 自己讀 state、`aos-exec "$state"`、`case` 換狀態，每格是 `fsm/<格>/.aos/exec`。沒有逾時、沒有 `trace.jsonl`（只有自己 `echo` 的 `trace.log`）；表藏在 `case` 裡。想完全不碰 JSON 時可以這樣寫，state 檔同格式、跟 aos-fsm 可互換（P-07）。

```sh
#!/bin/sh
# fsm/.aos/exec（節錄）
state=$(cat "$AOS_STACK/state" 2>/dev/null || echo idle)
aos-exec "$state" || exit $?
case $state in idle) next=think;; think) next=act;; *) next=idle;; esac
echo $next > "$AOS_STACK/state"
```

三種的 stack 長相一樣（`state`、`current`、`plan`），人看的地方不變。demo 之間重複的小檔（`brain.py`、`idle/`）是 demo 的代價，不跨 agent 互指（P-33）。

## 九、慣例不管的

stack 裡的檔名與格式；腦的接頭怎麼寫；工具裡面怎麼做；入口怎麼收「這次要做啥」；一格同步還是非同步；agent 當工具時題目與答案走什麼形狀（看那隻 agent 自己的說明，P-32）；巢狀多深（P-37）。（§ 2、§ 4、§ 9「inbox 先不管」；拍板點 1；N-41）

## 十、程式還沒照這份改的地方

第一輪四項已全部做完（10-19），做法見 [PLAN.md](PLAN.md) 第一輪。**第二輪**（本稿 10-19 定、步驟 1（行程群組、`at`、PATH 去重）、步驟 2（bob 混合範本）、步驟 3（ann 全內嵌）、步驟 4（cathy）已做，其餘（P-36 的整合測試、收尾）還沒做，步驟見 [PLAN 第二輪](PLAN.md#第二輪混合範本與巢狀2026-10-19-fable-規劃)）：

## 十一、要使用者決定的

第一輪六條已全部裁定（使用者 10-19）。第二輪多一條衝突（N-52「SIGTERM 退 0」↔ P-36「被外層逾時殺掉＝失敗」）與一個方向問題（agent 當工具時題目怎麼交），見 [CONFLICTS.md](CONFLICTS.md) 第 7 條與「方向問題」。

## 十二、巢狀：層層疊疊（10-19 第二輪）

使用者 § 10：「以後會是巢狀嵌入，層層疊疊，act 中所使用的工具可能又是另一個 agent-cathy，一層一層這樣。」底下每條都照同一把尺：**每一層只管自己這一層、同一條規則在每層重複**（C-52）。aos 本身仍然只管三個環境變數（§ 4），這一節全是慣例。

- **P-32 被叫者的工作區在呼叫方的小格裡。** 叫另一隻 agent 當工具，跟叫工具一樣先開小格 `sub=$AOS_STACK/<名>/`（P-17）；它若需要自己的工作區（它自己的說明會說，例如 cathy 認 `inbox/` 一題一檔），工作區就是 **`$sub/ws/`**：呼叫方照它的說明在那裡備好題目、叫它、再從那裡拿答案。一行寫完：`AOS_STACK=$sub aos-exec tools/<名> "$sub/ws"`——**stack 與工作區兩個都明給**（`AOS_STACK` 已經有值，aos-exec 不會替巢狀給預設；只給工作區不給 stack，被叫者會把 `state`／`current` 寫進呼叫方的 stack，把呼叫方的狀態機弄壞）。不需要工作區的工具（stamp 這種吃 stdin 吐 stdout 的）工作區省略（`-`，沿用），只給 stack。被叫者沿用呼叫方的 `AOS_WS` 只有一種情況正當：它的說明說它就是要動呼叫方的工作區（C-66 工具拿指標改外部變數）。使用者的工作區因此只多出 bob 自己的 `out/`、`done/`，cathy 的題目與答案全在 `.aos/cathy/ws/` 裡。**這不是「agent 之間走 inbox」的規則**：bob 寫 cathy 的 `inbox/` 是因為 cathy 的說明這樣寫（P-26 參數怎麼進由工具說明定）；換一隻吃 stdin 的 agent 就照它的。（§ 10；§ 9「inbox 先不管」；C-65 工作區只放使用者的東西、stack 放「叫工具時開的小格」；C-66；C-67 stack 放哪由呼叫方決定；C-52 被叫者不知道上面有誰；P-14 工作區其他東西不碰；P-17）
- **P-33 工具放在叫它的那一格的資料夾裡：`<格>/tools/<名>/`，格裡寫 `aos-exec tools/<名>`，永遠零個 `..`。** 相對路徑從 cwd 算，而格起跑時 cwd 就是格自己的資料夾（P-03），所以不管這格被埋在第幾層，路徑都一樣長、一樣對。bob 的 act 叫 `tools/cathy`，cathy 的 act 叫 `tools/stamp`——`agent-bob/act/tools/cathy/act/tools/stamp/` 這條路徑就是呼叫鏈本身（P-38）。內嵌單子格（think）的 cwd 是 agent 資料夾，它若要工具就是 agent 根下的 `tools/<名>`，同一條規則。**不給程式根變數**（aos 只訂三個變數，§ 4；而且 aos-exec 對每一格都是「一個資料夾程式」，不知道哪一層算「agent 的根」）；**不用 PATH**（C-61）。幾格共用一個工具、幾隻 agent 共用一隻 cathy：複製一份（demo 的做法，P-25 不跨 agent 互指），或在自己的 `tools/` 放一條捷徑指過去（C-61「相對捷徑、兩份一起搬也不斷」；Linux 才有，§ 9 先只考慮 Linux。本 repo 在 Windows checkout，所以 demo 不 commit 捷徑）。改掉 10-19 早上的 `../../tools/stamp`。（C-61 地址在自己資料夾裡、不用 PATH；N-50；C-56 KISS；§ 4）
- **P-34 小格不收、不清，連叫也用同一個；要全新就換名。** 第二題再叫 cathy 時，她的小格裡還有上一題的 `current`、`plan`、`trace.jsonl`、`ws/done/`——這是正常的：標準範本正常結束時 state 停在 `idle`（P-08），所以她從頭開始，`current`／`plan` 被新題蓋掉、`trace.jsonl` 與 `done/` 累積給人看。她若上次**失敗**停在半路（state＝`act`），呼叫方修好後再叫，她正是從那格接著做——這就是 P-20 要的。所以呼叫方**不在開工前 `rm`**（那會把 P-20 的接續抹掉）、**不用題名開新小格**（小格會跟著題目長、stack 樹不再等於呼叫樹）。真要全新：呼叫方給另一個小格名或自己 `rm`（C-67 呼叫方的自由）。被叫者的義務只有一條：**正常結束時自己的 stack 要停在起點**。（P-17 叫完不自動收；P-20 失敗停下、修好接著做；P-08；C-65「續聊＝同一個 stack 再跑，要忘記＝換一個」；C-67；拍板點 3 人來看）
- **P-35 格可以是一整隻 agent，不可以是別人 fsm 的一拍；10 只有 idle 退。** 當工具的 agent 入口一定是它自己的 loop（P-05），被叫一次就從現在的 state 跑到它的 idle 退 10 為止才回來；它的 loop 收到 10 退 0，所以呼叫它的格看到的是 0，上層的 loop 不會被誤停——cathy 的 10 到不了 bob。**不要**把另一隻 agent 的 `fsm.json` 直接拿來當自己的一格（`{"argv": ["aos-fsm", "tools/cathy/fsm.json"]}`）：那一拍她退 0 只代表「她走了一格」，你的 fsm 卻會換狀態、她還沒做完；她退 10 又會把你的 loop 停掉。proto8 N-40 的「階層式 fsm、內層沒完回 `next: null`」靠的是 stdout JSON，proto8-2 只看結束碼（CONFLICTS 4），做不到，也不需要——要巢狀就整隻叫。格叫工具時**工具的非 0 一律當失敗、自己 `exit 1`**（`|| { echo "act: cathy 失敗" >&2; exit 1; }`），不把工具的碼原樣 `exit`——工具若退 10 會被 fsm→loop 當成「停」。（P-19；P-21 誰的錯誰講；C-52 上層不知道下層是 fsm；N-53 整隻 agent 由自己的 loop 驅動；CONFLICTS 4）
- **P-36 逾時打整棵子樹；外層包內層。** 現況：aos_inst 逾時只 SIGTERM／SIGKILL 它直接起的那一個程式；格是 `#!/bin/sh` 時 sh 被殺、sh 底下的 `aos-exec tools/cathy`→cathy 的 loop→她的格全變孤兒繼續跑（sh 收到 SIGTERM 直接死、不轉給前景子程式）。**定**：單子起的程式自成一個行程群組（`start_new_session`），逾時與轉來的 SIGINT／SIGTERM／SIGHUP 都打整個群組（`killpg`），grace 到了 SIGKILL 整個群組；中間沒隔單子的那幾層（sh 格、`subprocess.call` 起的 aos-exec）本來就跟起它們的程式同一個群組，所以一刀下去整棵子樹一起收，下一層單子再轉給它自己的群組，層層往下。被殺的那格＝**失敗**（碼 128＋訊號、`trace.jsonl` 那行 `timed_out: true`），上面照 P-20 停下來等人，不當正常收工（跟 N-52「SIGTERM 退 0」不同，CONFLICTS 7）。寫法：逾時寫在最靠近會卡的那格（think 問腦 120 秒）；要包住整隻子 agent，呼叫它的格在 `fsm.json` 寫成 `{"argv": ["aos-exec", "act"], "timeout_ms": …}`；**外層 ≥ 內層一圈各格逾時之和 × 內層 `max`**，不然外層會先殺人；`grace_ms` 外 ≥ 內。aos 不替人算這個。代價：新群組沒有控制終端，格裡的程式不能去讀終端（agent 本來就不該，N-41）。（N-41 靠 `timeout_ms` 守；P-22；P-30 逾時收尾不留孫程式；C-52 每層只管自己直接起的；proto8 待定「巢狀 grace：外層宜大於內層」；N-52／C-63 見 CONFLICTS 7）
- **P-37 不設深度上限、沒有人管遞迴。** 照 P-33 工具在呼叫者自己的資料夾裡、不用捷徑時，「cathy 又叫 bob」根本寫不出來（bob 不在 cathy 底下）；寫得出來的只有捷徑或絕對路徑，那是設計者自己選的。真遞迴下去，每層小格路徑多一段，撞到路徑長度上限時 `mkdir` 失敗、aos-exec 退 1、一路失敗往上停；或被最外層的 `timeout_ms` 一刀收掉（P-36）。不加深度計數、不加環境變數數層。（N-39「表裡的格指回自己（遞迴）fsm 不擋，卡死不防護」；C-53 誤用不歸組件管；C-56 不為邊緣狀況加機制）
- **P-38 stack 樹＝呼叫樹＝tools 資料夾樹；看全貌就看那棵樹。** 每層照 P-17 用工具名開小格，所以 `$AOS_STACK` 底下長出來的就是這次誰叫了誰：`.aos/{state,trace.jsonl,cathy/{state,trace.jsonl,ws/,stamp/runs}}`。每個 fsm 層有自己的 `trace.jsonl`；為了把各層的 trace 對到同一條時間線，每行加 `at`（這拍開始的 UTC 時間，ISO 格式）。看法：`find "$AOS_STACK" -name trace.jsonl | xargs cat | sort`（照 `at` 排就是整棵樹的時間順序）、`tree -a "$AOS_STACK"`；`demo/run.sh` 跑完印整棵樹。不另做彙整工具、不做跨層的 trace id。（拍板點 3 人來看；C-54 結構本身就是說明；C-56；N-39「標準實作要不要每拍記時間未定」→ 這裡定要）
- **P-39 往下只流環境變數，別的都明給。** `AOS_WS`、`AOS_STACK` 每次叫別人都明寫（P-32）；`AOS_ENTRY`、`AOS_BRAIN_*` 一路繼承、整棵樹一致——所以**巢狀裡的 agent 不改 `AOS_ENTRY`**（上面改了名，底下每一格都要跟著有那個檔），demo 全用預設 `.aos/exec`；腦要換端點就在叫它那一行覆寫。stdin 一路繼承到最底層，所以**agent 類工具不讀 stdin**（會卡在終端上），要餵東西就 `<` 明給（stamp 那種）。stderr 一路繼承，每層出錯只說自己一行（P-21），三層就是三行、由下往上，人看得出是哪層。`PATH`：aos-exec 每層都把 `bin/` 加到前面，改成已在就不加（純整潔，不影響行為）。（§ 4 aos 只訂環境變數；N-55 環境變數自然往下傳；P-21；C-53）
