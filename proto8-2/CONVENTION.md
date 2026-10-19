# aos agent 慣例（proto8-2，2026-10-19 結論版）

← [proto8-2](README.md)｜原話與拍板：[thinking/ideas](thinking/2026-10-19-ideas.md)｜跟 proto8 原則相撞、使用者已全部裁定：[CONFLICTS.md](CONFLICTS.md)｜proto8 原則：[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)

**aos 本身只保證三個環境變數和一支 `aos-exec`**（使用者 § 4）。其餘全是慣例：我們自己人寫 agent 時照抄的標準形狀，照抄的人不用想、看別人的 agent 一眼就懂（C-54）。**agent-bob 現在的樣子就是標準，stack 裡面自由**（拍板點 1）。

每條後面括號是依據：§ 幾＝[ideas](thinking/2026-10-19-ideas.md) 裡使用者原話的段號；拍板點 1～3＝ideas § 8；C-xx／N-xx＝proto8 的概念與規範；引不到的、這份自己定的，標「本稿定」。程式還沒照這份改的地方列在第十節。

## 一、aos 保證的（不是慣例，是底）

- **P-01** aos 只訂三個環境變數：`AOS_ENTRY`＝入口在資料夾裡的相對位置，預設 `.aos/exec`，**是可執行檔，或旁邊的 `$AOS_ENTRY.json` 單子**（兩個都在用可執行檔；P-28 (B)）；`AOS_WS`＝工作區（使用者的檔與成品在哪）；`AOS_STACK`＝執行中狀態放哪，預設 `$AOS_WS/.aos/`。（§ 1、§ 2、§ 3；N-55）
- **P-02** `aos-exec DIR [WS [args...]]`＝「在 WS 這個工作區，執行 DIR 這個程式」。WS 省略＝`-`；`-`＝沿用現有 `$AOS_WS`，沒設才用 `.`。慣例用法：`cd workspace && aos-exec ../agent-bob`。（§ 4、§ 5）
- **P-03** aos-exec 只做五件事：把 WS 轉絕對路徑設成 `AOS_WS`；`AOS_STACK` 沒設就設預設值、建資料夾；把自己的 `bin/` 加進 PATH（入口才找得到 `aos-loop`、`aos-exec`）；`cd DIR`；`exec` 入口（可執行檔，或沒有它時交給 aos-inst 跑 `$AOS_ENTRY.json`），多的 args 與 stdin 原樣交給它。**起跑時 cwd＝DIR**；之後程式愛 cd 去哪、「這次要做啥」怎麼收，都是它自己的事。（§ 1、§ 4）
- **P-04** DIR 或 WS 不存在、入口缺或不可執行：aos-exec 非 0 結束、stderr 一行原因。（N-43、N-29 精神；aos 自己的錯一律退 1）

## 二、佈局（每檔一句）

```
agent-bob/                 一個 agent＝一個資料夾程式（§ 1）
  .aos/exec                入口，兩行：#!/bin/sh、exec aos-loop loop.json（§ 4、P-05）
  loop.json                {"run": "fsm", "max": 20}：每圈拍誰、最多幾圈（§ 1、P-06）
  fsm/.aos/exec            狀態機：讀 $AOS_STACK/state、aos-exec 同名子資料夾、成功才換狀態（P-07）
  fsm/idle/.aos/exec       inbox 有題→0 往下走；沒題→10 請 loop 停（P-19）
  fsm/think/.aos/exec      (A) 單子：跑 brain.py、stdout 導到 $AOS_STACK/plan、逾時 120 秒（P-12、P-24、P-29）
  fsm/think/brain.py       取一題（P-12）、題名寫 stack 的 current、問腦（假腦或 OpenAI 相容端點、只取 content，P-23），答案印 stdout
  fsm/act/.aos/exec        照 plan 把答案寫 $AOS_WS/out/、題目搬 done/（P-11、P-24）
  tools/<名>/              工具＝子資料夾程式，各有自己的 .aos/exec（P-25；原型還沒有）

workspace/                 ＝$AOS_WS，使用者的（§ 2）
  inbox/<題名>             題目：純文字、一題一檔（拍板點 2）
  out/<題名>               答案：跟題目同名
  done/<題名>              做完的題目搬來這
  .aos/                    預設 $AOS_STACK（§ 2）；裡面放什麼 agent 自訂（P-16）
```

## 三、入口、loop、fsm

- **P-05** 入口 `.aos/exec` 一定帶 shebang（`#!/bin/sh`），下一行 `exec aos-loop loop.json`。（§ 4 原話「#usr/bin/sh aos-loop loop.json」。沒有 `#!` 的檔只有從 sh 叫才跑得起來，從 Python、C++ 直接 exec 會失敗，不合 § 1「目標必須是可執行檔」；`exec` 少一層行程、訊號直達 loop——本稿定）
- **P-06** `loop.json` 只有兩個欄位：`run`＝每圈 `aos-exec` 誰、`max`＝最多幾圈。loop 每圈起一次 `run`，看它的結束碼決定下一步（P-19）。（§ 1；拍板點 1；欄位名為原型自訂）
- **P-07** fsm 一拍只跑一格：讀 `$AOS_STACK/state`（沒有＝`idle`），`aos-exec` 同名子資料夾；那格 0 才寫下一個狀態、退 0；非 0 就不換狀態、以原碼退。每拍之間狀態都落在 stack，人看得到。（C-62、N-53 agent 是被外面 loop 一拍一拍驅動的狀態機；N-36 一拍一格）
- **P-08** 標準三態 `idle → think → act → idle`。要加狀態＝加一個子資料夾、改 fsm 入口裡那張表；表一定明寫、不靠慣例檔名。（拍板點 1；N-36 表一定明寫）
- **P-09** 每一格都是資料夾程式。fsm 只看格的結束碼，不讀格的 stderr、不管格裡面怎麼做（同步等腦、或丟請求下一拍再看，都行）。（C-52、N-38、N-41）
- **P-10** 格之間要傳的東西寫成 stack 裡的檔（agent-bob：`current`＝正在做哪題、`plan`＝腦的草稿），不走 stdout。（N-37「格之間要傳的東西由格自己寫成檔」；§ 2）

## 四、題目與答案

- **P-11** 題目＝`$AOS_WS/inbox/<題名>`，純文字、一題一檔；答案＝`$AOS_WS/out/<題名>`，跟題目同名；做完把題目搬到 `$AOS_WS/done/<題名>`。**結果＝工作區內容，沒有別的結果通道。**（拍板點 2；C-65 工作區只放交辦的東西與成果；C-34 求值＝空間狀態的變化。這是 agent-bob 的做法；「agent 之間傳題目走 inbox」當共同形狀，inbox 先不管〔使用者 10-19〕，不當規則）
- **P-12** 一次做一題：取 inbox 裡檔名排序最前面的那個，題名寫進 `$AOS_STACK/current`。（原型現狀；拍板點 1）
- **P-13** 需要附檔時升級成資料夾：`inbox/<題名>/` 裡題文叫 `prompt`、其餘檔是附檔；答案 `out/<題名>/` 也是資料夾、主答案叫 `answer`。一個 agent 認哪種形狀寫在它自己的說明；agent-bob 只認一題一檔。（拍板點 2「需要附檔再升級成資料夾」；檔名本稿定，照 C-54 小寫單數）
- **P-14** agent 只動 `inbox/`、`out/`、`done/` 與 `$AOS_STACK`，工作區其他東西不碰。`done/` 只進不出，清理是人的事。（C-65 工作區保持乾淨；C-56 不為清理加機制）

## 五、stack

- **P-15** 執行中的一切（狀態、草稿、紀錄、小格）只寫 `$AOS_STACK`，**定義資料夾不被寫**；所以同一個 agent 可以同時被兩個工作區跑。（C-65；§ 2；原型測試已驗）
- **P-16** agent 自己的格（fsm／idle／think／act）共用同一個 `$AOS_STACK`——它們是同一台狀態機。stack 裡放什麼、叫什麼，agent 自訂；agent-bob 的 `state`、`current`、`plan`、`trace.log` 是例子不是規範。（拍板點 1「stack 內部自由」；§ 2「剩下的你自己想」；§ 3）
- **P-17** 叫**別的**資料夾程式（工具、另一個 agent）時，給它自己的 stack：`AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>`。被叫的只看到自己的 stack、不知道上面有誰。叫完不自動收——留著給人看；要收由呼叫方自己 `rm`。（§ 3「子程式的 stack 由 agent-bob 自己訂，有可能他會是 AOS_STACK/think, /act」；C-52 子 agent 只看自己的 stack；C-67 stack 放哪由呼叫方決定；拍板點 3「人來看」。這是原討論稿拍板點 4 的答案）
- **P-18** 一個工作區同時跑兩個 agent 時，呼叫方給不同的 `AOS_STACK`（例 `$AOS_WS/.aos/bob/`）；預設值只保證「一個工作區一個 agent」不撞。（C-67；C-53 入口默認正常、誤用不歸組件管）

## 六、停與錯

- **P-19** 結束碼三種：`0`＝這圈好了、下一圈；`10`＝正常停（idle 看 inbox 空了）；其他非 0＝失敗。loop 收到 10 以 0 結束；收到其他非 0 以那個碼結束；跑滿 `max` 以 0 結束並在 stderr 提一句。（拍板點 1；原型現狀。與 C-63 相撞，使用者 10-19 定：照用，見 [CONFLICTS 4](CONFLICTS.md)）
- **P-20** 任一格失敗＝整個 agent 停下來等人：fsm 不換狀態、loop 以那個碼結束；人修好後再 `aos-exec` 一次，從 `$AOS_STACK/state` 接著做同一格、同一題。不自動重試、不數連錯。（拍板點 3；N-53 腦出錯那拍 phase 不動；N-38）
- **P-21** 誰的錯誰自己講：格的錯寫在格自己的 stderr；fsm 什麼都不轉述；loop 只說「第幾圈、誰、結束碼幾」。（C-53；N-43 每層只說自己）
- **P-22** 逾時：shell 版沒人管——某格卡住（模型沒載入、網路不通）loop 只會等，也殺不到孫程式。要逾時就把那格換成 inst 版、寫 `timeout_ms`（P-29）。（N-41「靠那張 inst 的 timeout_ms 守」；inst 討論的結論）

## 七、腦與工具

- **P-23** 腦＝OpenAI 相容的 chat completions 端點，由環境變數 `AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY` 指定；`AOS_BRAIN_URL` 沒設＝假腦（demo 預設）。只取回覆的 `content`（有工具時加 `tool_calls`），模型想的內容不收、不存。這台電腦不跑本機模型。（原型現狀；[lib agent.md](../proto8/lib/agent.md) 使用者 10-15「維持 openai 格式」「模型想的內容丟掉」；§ 6；變數名照 C-54 全大寫底線）
- **P-24** 想跟做分開：think 問腦、只把「要做什麼」寫進 `$AOS_STACK/plan`；act 照 plan 動手、不問腦。能寫死的步驟（搬檔、寫檔）放在 act 這種程式格，不交給模型。（C-22 能寫死的節點換成程式；C-25）
- **P-25** 工具＝`tools/<名>/` 子資料夾程式，格裡用 `aos-exec tools/<名>` 叫：地址是相對路徑、不靠 PATH 找工具；`AOS_WS` 自然傳下去；工具要不要碰工作區、怎麼碰，是工具自己的事、風險設計者自管；工具裡是不是另一個 agent，呼叫者不知道也不管。stack 照 P-17。（C-61 不用 PATH、地址在自己資料夾裡；N-55；C-66；C-52）
- **P-26** 工具的參數怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；aos-exec 保證 args 與 stdin 原樣送到。（§ 4）

## 八、shell 版與 inst 版

- **P-27** 標準範本＝shell 版，就是 agent-bob 的樣子（第二節）；其中 think 這一格示範 (A)（單子），其餘格仍是 shell。（拍板點 1；§ 7「想要簡單直接，那就上 shell 指令」）
- **P-28** inst 單子（`{"argv", "cwd", "stdin", "stdout", "timeout_ms", …}`，key 表與跟 proto8 不同的兩處見 [README 的 `bin/aos-inst`](README.md)）是可選的升級，四種用法都行、可以在同一個 agent 裡混用：(1) `.aos/exec` 是 shebang 小殼、讀旁邊的 `exec.json`；(2) loop／fsm 的設定裡直接內嵌單子；(A) `.aos/exec` 第一行 `#!/usr/bin/env aos-inst`、後面接 JSON（**已做**，`bin/aos-inst`）；(B) aos-exec 認 `.aos/exec.json`，入口＝可執行檔或單子（**已做**；(1) 小殼＝`#!/bin/sh`＋`exec aos-inst .aos/exec.json "$@"`，也已有測試）。（§ 7「1 跟 2 都要」「接法 3 感覺也是 OK 的」「AB 都可以」；只剩 (2) 還沒做）
- **P-29** 範本先給 (A)：只換一格的入口檔、佈局跟 shell 版一模一樣，學一次就夠；資料夾開始太多時改用 (2)，一份 `fsm.json` 看完整張表與每格單子。範本就是 `demo/agent-bob/fsm/think/.aos/exec`（見下面範例）。(1) 與 (B) 是 (A) 的等價寫法，不另給範本。（拍板點 1 agent-bob 是標準、佈局不變最省；§ 7「單子是資料這塊……在不希望資料夾佈局太複雜的時候很好用」。這是原討論稿拍板點 5 的答案）
- **P-30** 用 inst 換到的是四樣：argv 是陣列、不靠 sh 拼字串；`timeout_ms` 逾時收尾、不留孫程式；結果是結構化的（結束碼、訊號、有沒有逾時、毫秒）；單子是資料、可內嵌進別的 JSON。「不走 sh 更快」實測不成立：單獨起一個 aos-inst（Python）比一層 sh 慢 5～6 倍，agent-bob 一圈殼的開銷對一輪 LLM 不到千分之二；省得到的只有 loop／fsm 在行程內直接 `run()` 那種。（§ 7 使用者「都還好。主要是單子是資料這塊……結果是結構化的這塊也很舒服」；10-19 在 WSL 實量的結論）
- **P-31** 單子要指到 stack 或工作區底下的檔，寫 `{"$env": "AOS_STACK", "path": "plan"}`：意思是「那個環境變數指的資料夾底下的 `plan`」，照 `os.path.join` 接（`AOS_STACK` 結尾有 `/`、`AOS_WS` 沒有，兩種都對；`path` 寫絕對路徑就是絕對路徑）。不帶 `path` 就是整個變數值。**只有 `$env`，沒有 `$ref`**（單子本來就能內嵌，不必拆檔）；變數沒設＝aos-inst 自己的錯、退 1。不用字串內插（`"$AOS_STACK/plan"`）：那是把規則埋進字串的暗規則。（本稿定；PLAN 第一節決定 3；C-48／C-55 值長成物件、同層加屬性；C-56 寫什麼就做什麼；N-45 `$env` 是正式機制）

### 範例：同一個 think 格的三種寫法

shell 版（原本的 think，節錄；現在的檔已換成 (A)，原檔靠 git 歷史）：

```sh
#!/bin/sh
# fsm/think/.aos/exec
f=$(ls "$AOS_WS"/inbox/* | head -n 1); basename "$f" > "$AOS_STACK/current"
python3 brain.py "$f" > "$AOS_STACK/plan"
```

inst 版 (A)（`demo/agent-bob/fsm/think/.aos/exec` 實際內容，只換這一個檔。挑題、寫 `current`、問腦這種動態的事由 `brain.py` 做，單子是靜態資料，只負責「跑誰、輸出導去哪、多久逾時」）：

```
#!/usr/bin/env aos-inst
{"argv": ["python3", "brain.py"],
 "stdout": {"$env": "AOS_STACK", "path": "plan"},
 "timeout_ms": 120000}
```

inst 版 (2)（`fsm/.aos/exec` 改成 `#!/bin/sh`＋`exec aos-fsm fsm.json`，表與單子合成一份；形狀示意，aos-fsm 還沒接 `$AOS_STACK`）：

```json
{"start": "idle",
 "states": {
   "idle":  {"val": {"argv": ["aos-exec", "idle"]}, "next": "think"},
   "think": {"val": {"argv": ["python3", "think/brain.py"], "timeout_ms": 120000}, "next": "act"},
   "act":   {"val": {"argv": ["aos-exec", "act"]}, "next": "idle"}}}
```

格寫成 `{"val", "next"}` 照 N-36；idle、act 仍是子資料夾（看 inbox、搬檔用 sh 最順），think 變成一張單子、拿到逾時。

## 九、慣例不管的

stack 裡的檔名與格式；腦的接頭怎麼寫；工具裡面怎麼做；入口怎麼收「這次要做啥」；一格同步還是非同步。（§ 2、§ 4；拍板點 1；N-41）

## 十、程式還沒照這份改的地方（之後另派）

- inst 還剩一種沒做：aos-loop／aos-fsm 內嵌單子 (2)；aos-fsm 的 state 檔落在 `$AOS_STACK`（P-28、P-29）。
- `tools/` 還沒有任何工具（P-25）。

## 十一、要使用者決定的

已全部裁定（使用者 10-19），見 [CONFLICTS.md](CONFLICTS.md)。
