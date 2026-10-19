# 2026-10-19 aos agent 的慣例——討論稿

← [proto8-2](../README.md)｜原話：[ideas § 7、§ 8](2026-10-19-ideas.md#8-aos-agent-的慣例)｜前兩稿：[entry](2026-10-19-entry.md)、[inst](2026-10-19-inst.md)｜proto8 對照：[CONCEPTS agent](../../proto8/CONCEPTS/05-agent.md)、[NORMS 定義與工作區](../../proto8/NORMS/10-基礎設施-定義與工作區.md)、[lib agent.md](../../proto8/lib/agent.md)

> **AI 提案，等使用者逐條點頭**。第二節每一條都標了「沿用使用者已定」或「AI 新提」；AI 新提的全部可否決。拍板後照 10-12 夜的規矩只留原話、決定、結論，其餘刪。程式都還沒改，例子只是形狀。

## 一、三分鐘看懂：「aos agent 慣例」要回答什麼

aos 本身只保證三件事：`AOS_ENTRY`（入口在哪，預設 `.aos/exec`）、`AOS_WS`（工作區在哪）、`AOS_STACK`（執行中狀態放哪，預設 `$AOS_WS/.aos/`）。aos-exec 設好這三個、cd 進程式資料夾、跑入口，就不管了（使用者 § 4）。**所以「agent 長什麼樣」aos 不管；慣例就是我們自己人寫 agent 時照抄的一套標準形狀**——照抄的人不用想，看別人的 agent 一眼就懂。

一份慣例要回答七個問題，拿 agent-bob 當例子：

1. **資料夾裡放什麼、叫什麼**：現在 agent-bob 是 `.aos/exec`（入口）、`loop.json`（跑幾圈）、`fsm/`（狀態機），`fsm/` 底下 `idle/`、`think/`、`act/` 三個子資料夾程式。每一層都是資料夾程式，各有自己的 `.aos/exec`。
2. **loop／fsm／狀態的標準形狀**：入口一行 `aos-loop loop.json`；loop 每圈 `aos-exec fsm`；fsm 讀 `$AOS_STACK/state`（沒有就 idle）、跑同名子資料夾、成功才寫下一個狀態（idle→think→act→idle）。這就是 proto8 定的「agent 是被外面 loop 一拍一拍驅動的狀態機」（C-62／N-53），每拍之間狀態都落在 stack、看得到。
3. **think／act 怎麼接腦和工具**：think 問腦（`brain.py`，OpenAI 相容端點，由 `AOS_BRAIN_URL` 等環境變數指定；沒設就假腦），把答案草稿寫進 `$AOS_STACK/plan`；act 照 plan 動手。工具這層原型還沒有；慣例要說它放哪、怎麼叫。
4. **題目從哪進、答案從哪出**：題目＝`$AOS_WS/inbox/<題名>`（一題一檔）；答案＝`$AOS_WS/out/<題名>`；做完的題搬到 `$AOS_WS/done/`。沒有別的結果通道。
5. **stack 裡放什麼**：`state`（現在哪一格）、`current`（正在做哪題）、`plan`（腦的草稿）、`trace.log`（走過哪些格）。agent-bob 的 fsm／think／act 共用同一個 stack（使用者 § 3：子程式的 stack 由 agent 自己訂）。
6. **停與錯**：idle 看 inbox 空就回結束碼 10，loop 收到 10 就停；任何一格非 0，fsm 不換狀態、也以非 0 退出，loop 跟著停。
7. **shell 版與 inst 版各長怎樣**：使用者 § 7 定了「簡單用 shell、複雜專案用 inst，可選並存」。慣例要給同一個 agent 的兩種寫法，證明資料夾形狀不變、只是格子裡面換寫法。

一句話：**慣例＝「agent-bob 的樣子」寫成文字，加上工具、子 agent、失敗這三件原型還沒碰到的事。**

## 二、候選慣例（AI 提案，等逐條點頭）

### 佈局樹

```
agent-bob/                 ← 一個 agent＝一個資料夾程式（沿用 § 1）
  .aos/exec                ← 入口；內容一行 aos-loop loop.json（沿用 § 2 入口名、§ 4 內容）
  loop.json                ← {"run": "fsm", "max": 20}：拍誰、最多拍幾圈（原型自訂；AI 新提：留成慣例）
  fsm/                     ← 狀態機：一拍跑一格（沿用 C-62／N-53）
    .aos/exec              ← 讀 $AOS_STACK/state、跑同名子資料夾、成功才換狀態
    idle/.aos/exec         ← inbox 有題→0 往下走；沒題→10 請 loop 停（AI 新提：狀態名與停止碼）
    think/.aos/exec        ← 取一題、問腦、把 plan 寫進 stack（AI 新提）
    think/brain.py         ← 腦的接頭：OpenAI 相容、只取 content（沿用 lib agent.md 10-15「維持 openai 格式」）
    act/.aos/exec          ← 照 plan 把答案寫 $AOS_WS/out/、題目搬 done/（AI 新提）
  tools/<名>/              ← 工具＝子資料夾程式，各有自己的 .aos/exec；act 用 aos-exec tools/<名> 叫（AI 新提，改寫 C-61「地址在自己資料夾裡、不靠 PATH 找工具」）

workspace/                 ← 使用者的工作區＝$AOS_WS（沿用 § 2、N-55）
  inbox/<題名>             ← 題目：一題一檔、純文字（AI 新提）
  out/<題名>               ← 答案：跟題目同名（AI 新提）
  done/<題名>              ← 做完的題目搬來這（AI 新提）
  .aos/                    ← 預設 $AOS_STACK（沿用 § 2）
    state current plan trace.log   ← agent-bob 自己的四個檔（AI 新提：檔名；§ 2 已定「內容 agent 自訂」）
```

### 條文（每條一句）

1. **一個 agent＝一個資料夾、入口 `.aos/exec`、起跑 cwd＝這個資料夾**。（沿用 § 1、§ 2）
2. **入口只做一件事：`aos-loop loop.json`**；loop.json 只有 `run`（拍誰）與 `max`（最多幾圈）。（§ 1 定入口內容；欄位名 AI 新提）
3. **`run` 指向 `fsm/`，fsm 一拍一格、狀態落在 `$AOS_STACK/state`、成功才換狀態**。（沿用 C-62／N-53「被外面 loop 驅動、每拍狀態落 stack」）
4. **三個標準狀態名 idle／think／act**，各是 `fsm/` 底下的子資料夾程式；要加狀態就加資料夾、改 fsm 那張表。（AI 新提）
5. **結束碼：0＝下一圈、10＝正常停、其他＝失敗**。（原型自訂；AI 新提：留成慣例）
6. **腦出錯那一拍以非 0 退出、state 不動**，下一拍重跑同一格；重試幾次是 loop 的事。（沿用 N-53；loop 的重試欄位見拍板點 3）
7. **題目與答案走工作區：`inbox/`→`out/`＋`done/`，一題一檔、同名**。agent 不動工作區裡別的東西。（AI 新提）
8. **執行中狀態只寫 stack，定義資料夾不被寫**，所以同一個 agent 可同時被兩個工作區跑。（沿用 C-65；原型已如此）
9. **腦＝環境變數指定的 OpenAI 相容端點**（`AOS_BRAIN_URL`／`AOS_BRAIN_MODEL`／`AOS_BRAIN_KEY`），沒設就假腦；只取 `content`／`tool_calls`，不收思考內容。（沿用 lib agent.md 10-15；變數名 AI 新提）
10. **工具＝`tools/<名>/` 子資料夾程式，用 `aos-exec tools/<名>` 叫**，`AOS_WS` 自然往下傳；工具自己決定要不要碰工作區。（AI 新提，改寫 C-61／N-56）
11. **自己的格（fsm／think／act）共用 `$AOS_STACK`；叫別的 agent 當工具時給它 `$AOS_STACK/<名>/`**。（§ 3 定「由 agent 自訂」；慣例值 AI 新提，見拍板點 4）
12. **慣例只管到這裡**：stack 裡的檔名、腦的接頭怎麼寫、工具裡面怎麼做，都是 agent 自己的事。（沿用 § 2「剩下的你自己想」）

### 同一個 agent 的兩種寫法

**shell 版**（＝現在的 agent-bob，每格一個資料夾、入口是 sh）：

```
agent-bob/.aos/exec             aos-loop loop.json
agent-bob/loop.json             {"run": "fsm", "max": 20}
agent-bob/fsm/.aos/exec         #!/bin/sh … state=$(cat "$AOS_STACK/state") ; aos-exec "$state" …
agent-bob/fsm/think/.aos/exec   #!/bin/sh … python3 brain.py "$f" > "$AOS_STACK/plan"
```

**inst 版**（用法 2：單子直接內嵌在 fsm 設定裡；資料夾變少，格子有逾時）：

```
agent-bob/.aos/exec             aos-loop loop.json
agent-bob/loop.json             {"run": "fsm", "max": 20}
agent-bob/fsm/.aos/exec         aos-fsm fsm.json
agent-bob/fsm/fsm.json          ↓
```

```json
{"start": "idle",
 "state": {"$env": "AOS_STACK", "path": "state"},
 "states": {
   "idle":  {"run": "idle/", "next": "think"},
   "think": {"run": {"argv": ["python3", "brain.py"],
                     "stdout": {"$env": "AOS_STACK", "path": "plan"},
                     "timeout_ms": 120000},
             "next": "act"},
   "act":   {"run": "act/", "next": "idle"}}}
```

idle、act 還是子資料夾（它們要看 inbox、搬檔，寫 sh 最順）；think 這格變成一張單子，拿到 `timeout_ms` 與結構化結果，不經 sh。brain.py 改成自己讀 `$AOS_STACK/current` 決定答哪題（單子是靜態資料，挑哪一題得有人做，見邊緣 4）。

**inst 版 A 寫法**（每格仍是資料夾，只把入口換成 shebang＋JSON 單檔）：

```
agent-bob/fsm/think/.aos/exec
  #!/usr/bin/env aos-inst
  {"argv": ["python3", "brain.py"], "stdout": {"$env": "AOS_STACK", "path": "plan"}, "timeout_ms": 120000}
```

資料夾佈局跟 shell 版一模一樣，只有 think 那個入口檔不同；aos-exec 不用改。兩種 inst 寫法與 shell 版可以同一個 agent 裡混用——這就是使用者 § 7「都可以、自由」的具體樣子。（`$env` 寫法照 proto8 N-45 選 A；aos-fsm、aos-inst 跳過 `#!` 行都還沒做。）

## 三、跟 proto8 對照（只列）

**可以直接搬**：

- **C-62／N-53** agent＝被外面 loop 驅動的狀態機；每拍狀態落 stack；腦出錯那拍退非 0、state 不動、重試看外面 loop。原型已照做。
- **C-50** 複雜度集中在格裡，資料夾佈局與 json 保持單純。
- **C-52** 徹底切割：fsm 只看格的結束碼、不讀格的 stderr；工具裡是不是另一個 agent，呼叫者不知道。
- **C-65** 執行狀態放 stack、定義不動、工作區保持乾淨。原型已照做（`AOS_STACK` 預設在工作區的 `.aos/`，是使用者 § 2 定的位置）。
- **N-55** 工作區＝環境變數 `AOS_WS`，自然往下傳。已實作。
- **lib agent.md** 腦的 stdin／stdout 用 OpenAI chat 格式、只留 `content`／`tool_calls`、aos 從不依賴思考內容、工具走 `tool_calls`。
- **C-61 的精神**：工具地址寫在自己資料夾裡、不靠 PATH 找工具（形式改成 `aos-exec tools/<名>`）。

**因為今天的決定作廢或改形**：

- **N-47／C-60** 門房 `aos exec stack 定義` → `aos-exec DIR [WS]`（§ 5）。
- **N-48／C-59** stack 裡掛 `.aos` 捷徑、`.aos/x` 從 stack 算 → 不掛捷徑，起跑 cwd＝程式資料夾（§ 1）。
- **N-46／C-57／C-58／N-49** stdin 放定義、「這次的話」放 stack → 定義就是資料夾本身；「這次要做啥」隨意（§ 4）。慣例補成「題目放工作區 inbox」。
- **N-50** 工具參數走門房 stdin、分兩層 → aos-exec 把 args／stdin 原樣透傳，沒有兩層。
- **N-53 的「定義不含 loop」** → 今天入口就是 `aos-loop loop.json`，loop.json 放在 agent 資料夾裡（§ 1）。精神不變（agent 本體仍是 fsm、被 loop 拍），形式改成 loop 是 agent 資料夾最外層的薄殼。
- **N-51** shebang stub → 入口本身就可執行，不需要 stub；shebang 改成 inst 版 A 寫法的用途。
- **N-44** `stop_on_end` → 停止碼 10。
- **fsm 的 state 窗是 JSON `{"phase"}`、格路徑從設定檔算** → 原型 state 是純文字一行、格就是子資料夾從 cwd 算。
- **inst.json 當入口（N-04、N-24～N-27）** → 可選（§ 7），不再是唯一入口。

## 四、邊緣狀況（會撞到的）

1. **兩個 agent 共用一個工作區**：預設 `AOS_STACK=$AOS_WS/.aos/`，兩個 agent 的 `state`、`plan` 會互寫；兩個 think 都 `ls inbox | head -1` 會搶同一題；`out/<題名>` 同名互蓋。慣例要說：共用工作區時呼叫方自己給不同的 `AOS_STACK`（例 `$AOS_WS/.aos/bob/`），還是乾脆規定「一個工作區一個 agent」。
2. **think 失敗怎麼重試**：現在任何一格非 0，aos-loop 直接以那個碼結束，整個 agent 停；N-53 說「state 不動、重試幾次看外面 loop」，但 loop.json 沒有重試欄位。`current` 已寫、題目還在 inbox，所以重跑確實會接同一題，只差「誰決定再拍一次」。
3. **agent 叫 agent 的 stack**：bob 的 act 寫 `aos-exec tools/brush`，環境變數原樣往下傳，brush 的 fsm 會讀寫同一個 `$AOS_STACK/state`，蓋掉 bob 的狀態。要 bob 自己寫 `AOS_STACK=$AOS_STACK/brush/ aos-exec tools/brush`（§ 3 說由 agent 自訂），慣例得把這一行寫成標準。
4. **題目與答案的格式**：純文字一檔一題很簡單，但「帶 system 提示」「多輪對話」「附檔」都放不進去；inst 單子是靜態資料，「挑哪一題」這種動態的事單子做不到，得有一支程式（idle 或 brain.py）先把題名寫進 `$AOS_STACK/current`。`done/` 只進不出，久了會堆。
5. **入口沒 shebang**：agent-bob 的 `.aos/exec` 第一行是 `aos-loop loop.json`、沒有 `#!`。從 sh 的 `exec` 跑會被當 sh 腳本救回來；從 python `subprocess` 或 C++ `execve` 直接跑會 ENOEXEC。慣例要不要規定「入口一定帶 `#!/bin/sh`」。
6. **逾時沒人管**：shell 版的 think 卡住（模型沒載入、網路不通），loop 只會等，而且殺不到孫程式；inst 版有 `timeout_ms`，shell 版只能靠 brain.py 自己寫（詳見 [inst 稿邊緣 4](2026-10-19-inst.md)）。這是「複雜專案用 inst」最實際的理由。

## 五、拍板點（最先該答的排前面；每條附背景、選項各一例、AI 傾向——全部可否決）

### 1. 慣例要寫到多細？

**背景**：aos 只保證三個環境變數，其餘都是慣例。現在 agent-bob 從入口到 stack 檔名每一層都有做法，但沒有一條寫成「標準」。寫得太薄，兩個人寫的 agent 長不一樣、互相看不懂；寫得太厚，就跟使用者 § 2「剩下的你自己想」打架。

- (a) **薄**：只定「`.aos/exec`＋題目進 `inbox/`、答案出 `out/`」，裡面怎麼做隨意。例：有人的 agent 沒有 fsm、入口直接一支 python 把 inbox 做完，也算合格的 aos agent。
- (b) **中**：加上「入口是 `aos-loop loop.json`、`fsm/` 一拍一格、三個狀態 idle／think／act、停止碼 10」。例：agent-bob 現在的樣子就是標準，照抄即合格；stack 裡放什麼仍自由。
- (c) **厚**：再加 stack 四個檔名、腦的三個環境變數、工具 `tools/<名>/`。例：換一個 agent，`cat $AOS_STACK/state` 一定看得到它在哪格。

**AI 傾向 (b)**：原型已經是這個形狀、照抄零成本；stack 內部留白符合 § 2。可否決。

### 2. 題目與答案用什麼形狀？

**背景**：現在題目是 `inbox/` 裡一檔純文字、答案是 `out/` 同名純文字檔。這個形狀決定了 think 怎麼讀題、act 怎麼交答案、別的 agent 怎麼把題丟給 bob；之後要改會動到每一個 agent。

- (a) **純文字一檔一題**（現狀）。例：`echo "幾點？" > ws/inbox/q1`，答案在 `ws/out/q1`。
- (b) **一題一資料夾**：`inbox/q1/prompt.md` 加附檔，答案 `out/q1/` 也是資料夾。例：題目附一張圖放 `inbox/q1/pic.png`。跟「資料夾＝程式」同一種味道，但 idle／think／act 都要改成處理資料夾。
- (c) **OpenAI messages JSON**：`inbox/q1.json` 是一段 messages，多輪、system 提示都放得進去，直接餵腦。例：`[{"role":"system",…},{"role":"user","content":"幾點？"}]`。

**AI 傾向 (a)**，需要附檔時再升級到 (b)；(c) 把腦的格式綁進工作區，與 C-52 切割的精神相反。可否決。

### 3. 一格失敗後，誰決定再拍一次？

**背景**：現在 fsm 任何一格非 0，aos-loop 就以那個碼結束，整個 agent 停下來等人。proto8 N-53 定了「出錯那拍 state 不動、重試幾次看外面 loop、agent 自己不數」，但 loop.json 現在只有 `run`／`max`，沒有重試這一格。

- (a) **現狀：失敗就停、人來看**。例：模型沒載入，agent 退 1，使用者修好再跑一次 `aos-exec ../agent-bob`，從 `$AOS_STACK/state` 接著做。
- (b) **loop.json 加 `retry`**：連錯幾次才停。例：`{"run":"fsm","max":20,"retry":3}`，think 連失敗三拍 loop 才退，state 不動所以重跑同一題。這是把 N-53 落成欄位。
- (c) **fsm 表上加 error 狀態**：失敗轉進 `error/` 子資料夾程式，由它決定回 idle 還是停。例：error 把題目搬到 `ws/failed/`、回 idle 做下一題。

**AI 傾向 (b)**：沿用使用者 10-16 已定的 N-53、改動最小；(c) 可以之後再加，不衝突。可否決。

### 4. agent 叫別的 agent 當工具時，子 agent 的 stack 放哪？

**背景**：使用者 § 3 定「子程式的 stack 由 agent 自己訂，可能是 `AOS_STACK/think`、`/act`」。agent-bob 選了自己的三格共用一個 stack。但 bob 若叫 brush（另一個完整的 agent）當工具，環境變數原樣往下傳，brush 會寫壞 bob 的 `state`（邊緣 3）。慣例要給一個標準寫法，不然每個人各寫各的。

- (a) **自己的格共用、外來的 agent 給子資料夾**：`AOS_STACK=$AOS_STACK/brush/ aos-exec tools/brush`。例：事後 `ls ws/.aos/` 看到 `state plan brush/`，一眼知道 bob 叫過 brush。
- (b) **每一格都給子資料夾**，連 think／act 也是 `$AOS_STACK/think/`。例：fsm 多一行設環境變數再 aos-exec；stack 比較整齊但 agent-bob 要改。
- (c) **每次呼叫開新號碼**：`$AOS_STACK/brush/1/`、`/2/`……，像 proto8 N-50 的「小格」。例：叫 brush 五次留五份 history，可回看，但要清。

**AI 傾向 (a)**：自己的格本來就是同一台狀態機、共用自然；外來 agent 是另一台狀態機、該有自己的 stack。可否決。

### 5. 慣例文件主推哪一種 inst 寫法當範本？

**背景**：使用者 § 7 已定 inst 四種用法全部可選、並存，這條不是要收掉任何一種，只是慣例文件要給一份「照抄用」的範本，總得挑一個放在最前面。第二節示範了用法 2（單子內嵌 fsm.json）與 A（每格入口＝shebang＋JSON）。

- (a) **主推 shell 版，inst 版給 A 當替換**：資料夾佈局跟 shell 版完全一樣，只是某一格的入口檔換成單子。例：think 要逾時，就把 `think/.aos/exec` 從 sh 換成 `#!/usr/bin/env aos-inst` 那兩行，其他不動。
- (b) **主推用法 2**：複雜 agent 一份 `fsm.json` 看完整張表與每格單子，資料夾少。例：十個狀態的 agent 只有 `fsm.json` 加兩三個真的需要資料夾的格。
- (c) **兩個都放範本、不排序**。

**AI 傾向 (a)**：使用者 § 7 說「想要簡單直接就上 shell」，而 A 保持同一套佈局、學一次就夠；用法 2 留給「不希望資料夾太複雜」的那種專案，照 § 7 原話。可否決。
