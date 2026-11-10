← [入口](README.md)｜涵蓋：使用者 11-10 補的分級約束（lv1～lv6）、各項動到哪一級、lv6 受影響清單、override 放更低層的思考、現行快選題｜上一份 [06-施工單](06-施工單.md)

> **11-10 改口（以這段為準）**：使用者「等等，null表示拿掉...不用，null就是null，我們不做rm功能」；對底檔帶來的工具下 rm 選「寫成 null，讀的人當它不是工具」。陣列與合併深度：「都按你的建議」＝照順序一份一份疊、後面蓋前面、補丁式往下合。本檔下文所有「`null`＝拿掉」「rm 功能」的說法都改讀成「合併沒有刪除、null 只是值；值是 null 的那格不算工具」。施工結果在 [08](08-施工結果.md)。

> **使用者 11-10 裁 K1＝A**（「現在就寫 $override」）：key 名定為 `$override`。**另加（頂層轉達原話）**：「$override希望能支援array，比如"$override":["a.json", "b.json"]，跟$ref一樣」→ 值可以是陣列，照順序疊、後面蓋前面，最後疊自己的。施工結果與跟 `$ref` 陣列的差異在 [08](08-施工結果.md)。

# 分級範圍、lv6 受影響清單、override 沉到低層（思考）

## 使用者原話（11-10，頂層轉達）

- 「我們的aos repo，程式碼資產分等級，lv1是最基礎的aos inst/ aos-exec，lv2是同樣的基礎：aos-loop/daemon，lv3是基礎標準庫：fsm/lock...，lv4是kernel與llm相關，lv5是aos agent相關，包括tools, eca, mcp等，lv6才是那些memory之類的雜七雜八東西。」
- 「這次改動主要以lv5為主，盡量別碰lv1~4。然後lv6那些太多太雜，假如因為lv5的改動致使lv6那些出問題，先別去動他們。override那個確實感覺可以放在更低層，也就是lv1的指示詞那樣，可以去思考一下。對啦，$env/$ref是lv0」

## 結論

1. **這次施工一行 lv0～lv4 都不用碰**。全部落在 lv5（aos-tools、aos-agent、aos-mcp、agent-fsm 範本、eca 的 `cli_session.py`）。
2. **lv6 有四支程式、一批知識庫文字會受影響，照你說的先不修**（清單在下）；[06](06-施工單.md) 步 4 原本列的 `shell_report`、`self_tools`、`agents` 改成不動。
3. **override 其實 lv0 已經有一半**：`$ref` 陣列今天就會「幾份照順序合成一份、後面的蓋前面的」。缺的只有三樣：「拿掉」的寫法、`rm` 不能去改底檔、檔案上看得出「我是覆蓋檔」。所以現在在 lv5 做的版本，只要把形狀選成「補丁」（物件往下合、`null`＝拿掉），之後沉到 lv0 檔案不用改。這讓原本的 N1 有了明確答案方向，併成新的 M1 給你選。
4. **分級有沒有寫成條文**：六級（lv0～lv6）這套編號**沒有**。最接近的是 [C-74](../../../../docs/CONCEPTS/01-設計理念/02-C-51.md)（10-22 你定的三層：基礎層〔核心 aos-exec＋loop、daemon〕→ 標準庫〔fsm、tasks〕→ agent／kernel），`wf/workflows/common/conventions.md` 的「單向分層」引用它。C-74 沒有把 kernel 與 agent 分開、沒有 lv6、沒有說指示詞是 lv0。`wf/`、`proto8/docs/`、`proto8/README.md` 搜 `lv1`～`lv6` 都沒有。

## 我對「誰是哪一級」的判斷（照 repo 現況；拿不準的另列）

| 級 | 我歸進去的 |
|---|---|
| lv0 | 指示詞 `$env`／`$ref`：`impls/aos-directive`、`impls/aos-json`、`lib/directive_value.py` |
| lv1 | `impls/aos-inst`、`impls/aos-exec`、`impls/aos-util` |
| lv2 | `impls/aos-loop`、`impls/aos-daemon`、`cmd/aos-daemon-ctl` |
| lv3 | `impls/aos-fsm`、鎖、`aos-post` 信箱 |
| lv4 | `impls/aos-llm*`、`impls/aos-kernel-llm`、`kernel/` |
| lv5 | `cmd/aos-tools`、`cmd/aos-agent`、`cmd/aos-mcp`、`cmd/aos-eca`、`templates/agent-fsm`、`templates/eca-claude`、`lib/agent/cli_session.py` |
| lv6 | `lib/agent/memory*`、`lib/agent/{self_tools,agents,thought,json_rewrite}`、`lib/aos/*`（shell_report、promote、rollback、review_round、measure…）、`lib/base/*`（給腦的小工具）、`cmd/aos-grow`、`cmd/aos-sandbox`、`cmd/aos-feedback`、`knowledge/` |

**拿不準的**：`lib/agent/{self_tools,agents,thought}`（是「agent 相關」還是「雜七雜八」；我先當 lv6、不動）；`lib/aos/judge`（判官，可能算 lv4）；`py/aos_flags.py`、`lib/tool_io.py`（全家共用，不屬單一級；這次不動）；`templates/{reviewer,judge-llm,copy-out}`；`cmd/aos-sweeper`、`cmd/aos-clock`。

## 各項動到哪一級

| 項（見 [06](06-施工單.md)） | 動的檔 | 級 |
|---|---|---|
| 步 1 甲級小修 | `cmd/aos-tools/bin/aos-tools`、它的 tests | lv5 |
| 步 2 快取搬 stack | 同上＋`cmd/aos-agent/stack.gitignore`、`docs/05-gitignore指南` | lv5 |
| 步 3 `env_file` | `cmd/aos-tools/` | lv5 |
| 步 4 override | `cmd/aos-tools/`、`cmd/aos-agent/aos_agent/tools.py`、`cmd/aos-agent/aos_agent/ctl/state.py`（第 73 行直接讀覆蓋檔的 `add`／`rm` 印摘要，06 漏列）、`templates/agent-fsm/{brain,act}.py`、`lib/agent/cli_session.py`、`cmd/aos-mcp/bin/aos-mcp` | lv5 |
| 步 5 help 與文件 | 上述各支的 help、`cmd/*/README`、`cmd/docs`、`templates/docs`、`docs/NORMS/附錄4`、`P-44` 加註 | lv5 的說明＋條文（不是程式） |

**非碰 lv1～lv4 不可的：沒有。** 用到下層的地方都是照現成介面用，不改它們：`aos-json get --follow --resolve`／`set --follow`／`del --follow`（lv0）、`aos-exec`（lv1）。N2 選 A 時要**讀** daemon 表的 `as_written`（lv2 寫的資料），只讀不改；表上取不到就退成相對寫法。

## lv6 受影響清單（施工時不動）

| 哪支 | 怎麼壞 | 壞到什麼程度 | 之後怎麼修 |
|---|---|---|---|
| `lib/aos/shell_report/report.py`（第 69-72 行） | stack 有覆蓋檔時它會傳 `--overlay`，改後是 `FlagUnknown` → 它報「cannot list effective tools」 | 只有改過工具的 agent 會壞；沒覆蓋檔的照常。它的測試若有覆蓋層情節會紅 | 換成「stack 那份在就用它、否則用定義那份，只傳 `--file`」，三行 |
| `lib/agent/self_tools/_entry` | 經 `aos-agent tools add [--override]`／`rm`／`ls` 轉手；旗標已裁改名 `--replace`（N3） | 一般的 add／rm／ls 照常；只有腦帶 `override: true`（蓋掉同名）那條路變 `FlagUnknown` | 跟著改旗標名一處 |
| `lib/agent/agents/_entry`（第 394、432 行） | ① `tools add --override` 同上；② 複製定義時只會改寫登記格的 `path`，不認得新的 `env_file` | ①**每次都壞**：它生子 agent 帶工具時固定傳 `--override`（第 432 行），改名後整個 add 步驟 `FlagUnknown`、收回那隻；②複製出來的定義若有相對的 `env_file` 且指到定義外，位置會錯（叫工具時 `PathMissing`） | ①改旗標名；②把 `env_file` 納入同一段改寫 |
| `lib/agent/thought/_entry`（第 12 行） | 對子 agent 下 `tools add --override` | 同 self_tools | 同上 |
| `knowledge/aos/cli/{tools,tool_env,flags}.md`、`knowledge/aos/me` | 文字還在教 `--overlay`、`--env-file` 抄內容 | 不會壞程式；agent 查知識庫會拿到舊用法 | 重寫這幾頁 |
| 既有 stack 裡的舊覆蓋檔（資料，不是程式） | 舊形狀讀不了，那隻的腦每格 `ToolsBad` 停下 | 每隻改過工具的 agent | `aos-agent tools reset` 後重加 |

查過不受影響的：memory 工具（`lib/agent/memory*`、`templates/agent-fsm/tools/memory`——登記成資料夾工具，只用到 `env` 的 `AOS_MEMORY`，形狀沒變）、`cmd/aos-sandbox/examples`（只列指令名）、`cmd/aos-grow`（grep 不到 aos-tools／tools.json）。`lib/base/ls`、`lib/base/stat` grep 有提到但沒細看，標未查。以上都沒實跑。

## override 放更低層（思考，不是現在施工）

### lv0 現在已經有什麼

`{"$ref": ["a.json", "b.json#/c/d"]}`＝幾份照順序合成一份：都是物件就合 key、**同名後面的蓋前面的**、只合一層（`impls/aos-directive/docs/01-用法等.md` 第 13 行；10-23 你定的寫法）。`aos-json set --follow` 會把新值寫進陣列的最後一份。aos-tools 的登記檔從 10-28 起就吃這個（「可以被指示詞分開」）。

所以今天不改任何程式就能寫出「定義那份＋這隻自己的」：

```json
{"tools": {"$ref": ["../../defs/bob/tools.json#/tools", "mine.json"]}}
```

**缺的三樣**：① 沒有「拿掉」的寫法；② `rm` 一個底檔才有的名字時，`aos-json del --follow` 會去改底檔；③ 檔案上看不出「我是覆蓋檔、我覆蓋誰」（你這次要的那個 key）。另外 `$ref` 所在的物件「其餘 key 忽略」（N-45，10-20 你的話：「至於那個obj value裡面的其他東西，就不管」），所以自己的內容得放另一份檔或另一格，不能跟指標寫在同一個物件裡。

### 如果做成 lv0 的東西，會長怎樣

一個新指示詞，意思是「這個物件疊在另一份上」。例（名字待定）：

```json
{"$override": "../../defs/bob/tools.json", "tools": {"math": {"path": "../lib/math"}, "clock": null}}
```

| 題目 | 選項與後果 |
|---|---|
| 合併語意 | (a) **補丁式**：物件往下一路合、同名後蓋前、`null`＝拿掉、陣列與純值整個換（就是通行的 JSON Merge Patch）。通用、好講；代價是「蓋掉同名工具」變成「合進去」，要整項換得把不要的 key 寫 `null`。(b) 只合一層（跟 `$ref` 陣列一致）：那指示詞就得放在要合的那一層（`tools` 裡面），不能放檔案頂層 |
| 陣列怎麼加減 | 補丁式不能對陣列加減一項，只能整個換。要加減就得把那份資料改成物件（名字當 key）——tools 本來就是物件，沒問題；`llm.json` 也是 |
| 刪除 | `null`。代價：真的想存 `null` 值的地方不能用它（tools、llm 目前都沒有這種值） |
| 鏈與環 | 底檔可以再有 `$override`；環的判法沿用 `$ref` 的「往上那幾層」 |
| 跟 `$ref` 的關係 | `$override` ＝「`$ref` 陣列＋`null` 拿掉＋自己的 key 算數」。最後一點違反 N-45「其餘 key 忽略」，要為它開例外（現在只有 `$path`／`$prefix` 兩個修飾欄算數） |
| 誰來解 | `impls/aos-directive`（C++ lib）一處；aos-exec、aos-json 連它，Python 經 `aos-json get --follow --resolve` 或 `lib/directive_value.py`，所以不用各語言各寫一份。寫入（`aos-json set --follow`）要多一條規則：寫進「你指的那份」而不是底檔 |
| 沉下去之後誰受益 | `llm.json` 在 stack「只放改過的鍵」可以改用同一套；任何 aos 讀的 JSON 都能疊 |

### 現在在 lv5 做的版本，怎麼設計才不用之後再改檔案格式

- **形狀選補丁式**：`{"override": 指標, "tools": {"名": {…}, "名": null}}`。這跟沉下去之後的語意一致；`add`／`rm` 陣列那種（原 N1 的 B）是 tools 專用，沉不下去。
- **指標三寫法照 `$ref` 的習慣**：相對（從這份檔的資料夾算）、絕對、指示詞物件；也收 `檔#/指標`。
- **key 的名字**是唯一會卡住的：lv0 的指示詞都以 `$` 開頭。現在寫 `"override"`（你舉的例子），之後沉下去要嘛 lv0 也認不帶 `$` 的 `override`（破例），要嘛改檔。現在就寫 `"$override"` 則不用改——lv0 目前只認 `$ref`／`$env`，看到 `$override` 會原封不動放著（照 N-45 的寫法推的，沒實測），由 aos-tools 自己解。
- 合併只由 aos-tools 做、只認檔案頂層那一個指標；不在 lv5 做「任何位置都能寫」。

## 使用者答 N1～N4（11-10，頂層轉達，原文）與給施工隊的結論

- N1：「跟一般清單同形狀。想要rm的話，就是指定的key : null」→ 覆蓋檔＝`{"override": 指標, "tools": {"名": {…}, "名": null}}`。
- N2：「跟你加 agent 時的寫法走」→ aos-agent 自動寫的指標照 `ctl add` 給定義的寫法（絕對／`$env`／相對轉成相對覆蓋檔）。
- N3：「旗標改叫 --replace」→ `add --override` 改名 `--replace`（aos-tools 與 `aos-agent tools add` 都改）；key 叫 `override`。
- N4：「報錯不跑」→ `call` 時 env 檔不在＝`PathMissing`。

### 照這樣做在 lv5，之後沉到 lv0 當指示詞，檔案格式要不要再改？

> **11-10 改口後補**：null 不再是「拿掉」，只是普通的值（照順序疊、後面蓋前面），「不算工具」是 aos-tools 讀清單時的解讀。所以沉到 lv0 時，低層只需要「照順序合」（補丁式往下合），**不需要任何刪除規則**；下表 `null` 那列的「拿掉」改讀成「被 null 蓋過」。

**結論：只有一處會要改——key 的名字；其餘都可以原樣沉下去，前提是現在就把合併語意定成下面這樣。**

| 項 | 沉下去會不會衝突 | 現在怎麼做就不用再改 |
|---|---|---|
| 同形狀 | 不會 | 照 N1 |
| `null`＝拿掉 | 不會，但要現在講死三件事 | ① `null` 一律是「這裡沒有這個 key」：在覆蓋檔＝從底檔拿掉；在沒有 `override` 的一般登記檔＝當它不存在（不報錯）。② 合併是**往下一路合**（補丁式）：同名工具的登記格是「合進底檔那一格」，不是整格換——因為 lv0 的通用規則不可能是「只合到第二層」這種 tools 專用的深度。③ 所以 `add --replace` 要整格換時，由 aos-tools 把底檔有、新登記沒有的 key 寫成 `null`。手寫覆蓋檔的人只寫 `{"path": …}` 會沿用底檔的 `env`。 |
| 路徑三寫法 | 不會 | 相對（從這份檔算）、絕對、指示詞物件，跟 `$ref` 的習慣一致 |
| 跟 `$ref` 拆檔並用 | 不衝突 | 覆蓋檔的 `tools` 可以是 `{"$ref": […]}`：先照 lv0 解完，再做 override 合併；`null` 在 `$ref` 陣列裡照 lv0 規則只是「後蓋前」的一個值，最後由 override 這一層當成拿掉。寫入照舊走 `aos-json set／del --follow`（`rm` 底檔的名字＝`set …/名 null`） |
| 鏈與環 | 不衝突 | 照 [04](04-改裁後設計.md) 的報法 |
| **key 名 `override`（不帶 `$`）** | **會** | 見下題 |

為什麼 key 名會衝突：lv0 的規則是「帶 `$ref` 或 `$env` 的物件就是指示詞」，認的是 `$` 開頭的字。沉下去之後若認不帶 `$` 的 `override`，任何剛好有個叫 `override` 的 key 的 JSON 物件都會被當成指示詞——repo 裡現成就有：`self_tools` 收的參數是 `{"op": "add", …, "override": true}`。所以沉到 lv0 那天，這個 key 幾乎一定得叫 `$override`。

### 還要你選的一題（步 4 在等）

**K1　覆蓋檔那個 key，現在要寫 `override` 還是 `$override`？**（**使用者 11-10 裁 K1＝A**：「現在就寫 $override」）
- A（推薦）現在就寫 `"$override"`。後果：之後沉到 lv0 檔案一個字都不用改；跟你舉的例子差一個 `$`；aos-tools 自己解它，lv0 目前不認這個字、會原封不動放著（照 N-45 條文推的，施工第一件事先實測）。
- B　照你說的寫 `"override"`，沉下去那天再改名。後果：現在最直白；到時每份覆蓋檔要改一個 key（覆蓋檔本來就少、`aos-agent tools reset` 重建也行），讀它的程式都在 aos-tools 一處，改動很小。
- C　寫 `"override"`，沉下去之後 lv0 也破例認這個不帶 `$` 的字，但只認「檔案最上層」那一個。後果：檔案永遠不用改；lv0 多一條「只有它不帶 `$`、只有最上層算」的例外，一段話要多講一句。

（步 4 可以先照 N1～N4 動工，key 名在程式裡收成一個常數，K1 答了只改那一個字。）

## 答案到之前的快選題（M1～M4；M1＝N1 已答 A、M3＝N2 已答 A、M4＝N4 已答 A，M2 改由上面的 K1 取代）

**M1　override 做在哪一層、長什麼樣？**
- A（推薦）現在做在 lv5，但長成之後能原樣沉到 lv0 的樣子：`{"override": 指標, "tools": {"math": {…}, "clock": null}}`——物件往下合、同名後蓋前、`null`＝拿掉。後果：這次不碰 lv0～lv4；通訊錄只有一種形狀；手寫要知道 `null`；蓋同名工具是「合進去」不是「整項換」（aos-tools 的 `add` 會替你把不要的 key 寫成 `null`）。
- B　不加新 key，直接用 lv0 現成的 `$ref` 陣列，aos-tools 只補「`null`＝拿掉」與「rm 不改底檔」。後果：零新概念、改動最少；但檔案上沒有你說的那個「表明他是覆蓋檔案」的 key，寫法也比較醜。
- C　這次就做成 lv0 的新指示詞。後果：一次到位、`llm.json` 也能用；但要動 aos-directive／aos-json，跟「盡量別碰 lv1~4」衝突，也要為 N-45「其餘 key 忽略」開例外。
- D　lv5 專用、沿用現在的 `add`／`rm` 兩格，只加 `override` 一行。後果：改動小；之後要沉到低層就得再改一次檔案格式。

**M2　那個 key 要不要帶 `$`？**（M1 選 A 或 C 才有這題）
- A（推薦）`"$override"`。後果：跟 `$ref`／`$env` 同一家，之後沉到 lv0 檔案不用改；跟你舉的例子差一個 `$`。
- B　`"override"`（你舉的例子）。後果：現在最直白；之後沉下去要嘛 lv0 破例認不帶 `$` 的字，要嘛再改一次檔。

**M3　aos-agent 自動幫某隻建覆蓋檔時，指標寫哪一種？**（原 N2，原文不變）
- A（推薦）跟你當初 `ctl add` 給定義的寫法走：給絕對就寫絕對、給 `$env` 就寫指示詞、給相對就寫成相對覆蓋檔。後果：你怎麼擺專案它就怎麼跟；定義搬家仍要自己 `tools reset` 或改這一行（指錯時 aos-agent 會提醒）。
- B　一律寫相對覆蓋檔。後果：最簡單；stack 與定義一起搬沒事，分開擺、兩台相對位置不同就斷。
- C　一律寫 `{"$env": "AOS_CD", …}`（跑起來時 aos 設的「定義資料夾」）。後果：永遠跟著 daemon 表、不會過期；但手動 `aos-tools --file` 看這份時要自己設那個變數，eca 那條路每層的 `AOS_CD` 不同、要另外處理。

**M4　叫工具時，登記的 env 檔不在，怎麼辦？**（原 N4，原文不變）
- A（推薦）報錯不跑（`PathMissing`，訊息說是哪個工具、哪個檔）。後果：另一台忘了放金鑰檔會馬上知道；那個工具在放好之前叫不動。
- B　印 warning 照跑。後果：工具自己缺金鑰時才失敗，錯誤訊息是工具的、比較難看懂。

## 因為分級約束而改掉的代定

| 項 | 原本 | 現在 |
|---|---|---|
| 原 N3（`add --override` 旗標改名） | 推薦改成 `--replace` | **使用者 11-10 答「旗標改叫 --replace」，照改**。代價：lv6 的 `self_tools`（`override: true`）、`agents`、`thought` 仍傳 `--override`，會變 `FlagUnknown`；照「lv6 先別動」不修，記在受影響清單 |
| 步 4 的呼叫者 | 含 `shell_report`、核對 `self_tools`／`agents` | 這三支是 lv6，不動，列進受影響清單；補上漏列的 `cmd/aos-agent/aos_agent/ctl/state.py` |
| 步 5 的文件 | 含 `knowledge/aos/cli/*` | `knowledge/` 是 lv6，不動，列進受影響清單 |
| 蓋掉同名工具 | 整項換 | M1 選 A 時是補丁式；`add --override` 由 aos-tools 把底檔有、新登記沒有的 key（`env`、`env_file`、`cache`）寫成 `null`，效果仍是整項換 |

## 哪些可以先動工、哪些要等

- **不用等**：[06](06-施工單.md) 步 1（甲級小修）、步 2（快取搬 stack）、步 3（`env_file`，「檔不在」那一支先照 M4 的 A 寫）。全在 `cmd/aos-tools/`，lv5。
- **步 4（override）現在也可以動工**：N1～N4 都答了（同形狀＋`null`、指標跟 `ctl add` 的寫法走、旗標 `--replace`、env 檔不在報錯）；只剩 K1（key 帶不帶 `$`），程式裡收成一個常數，答了改一個字。
- 步 5 跟著步 4。

## 沒驗的

- 「lv0 看到 `$override` 會原封不動」是照 N-45 條文推的，沒實測 aos-directive／aos-json。
- `$ref` 陣列拿來疊 tools（M1 的 B）沒實跑；只確認了文件寫的合併規則與 aos-tools 既有的 `set --follow`「寫進最後一份」。
- lv6 受影響清單是 grep＋讀相關行得出的，沒實跑；`lib/base/ls`、`stat` 未細看。
- 分級歸屬是我照你那兩句話對 repo 現況的判斷，「拿不準的」那一列要你或另一位補條文時定。
- **11-10 補測**：在 /tmp 實跑 `aos-json get --follow --resolve`，檔案頂層有 `$override` key 時原封不動留著、同層其他 key 裡的 `$env` 照解、`null` 值照留（退 0）。所以「lv0 現在不認 `$override`、交給 aos-tools 自己解」成立；上面兩處寫「沒實測」的以這條為準。
