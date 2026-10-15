# 2026-10-15 同像性：inst 也是「純值或物件」的大號版

← [討論紀錄](README.md)｜前情：[JSON 格式族](2026-10-15-json-families.md)（值的雙形）、[Lisp 組合子](2026-10-14-json-entry/10-lisp組合子.md)｜概念：[C-48](../CONCEPTS/01-設計理念.md)、[C-22](../CONCEPTS/05-agent.md)、[C-42](../CONCEPTS/05-agent.md)｜規範：[N-35](../NORMS/01-總則.md)、[N-30](../NORMS/03-基礎設施-inst.md)、[N-36](../NORMS/07-基礎設施-組合子.md)｜程式：[lib fsm.md](../lib/fsm.md)、[agent.md](../lib/agent.md)、[aos_methods.cell](../lib/aos_methods.py)

## 原文（10-15，照記）

「然後剛剛那個純值和物件那塊，其實我們這個aos inst也是一個大號的類似感覺，也就是同樣照lisp來：(daemon inst-a), (daemon (fsm inst-b inst-c))，這是同相性，除去路徑可以共用外，也可以讓fable去思考這樣的性質還有哪裡可利用。」

使用者補充（同日）：「json schema在此也就跟著變得重要了，想想看，所謂的C++ class，其實也可以用json schema來表述。相關的interface等概念也是」

## 決定（使用者 10-15 定）

- inst 的「寫路徑或整張內嵌」跟 C-48 的「值是純值或物件」是同一件事，是 aos 的同像性（程式長得跟資料一樣）。路徑可以共用是第一個好處；其他用法交 AI 想。
- JSON schema 跟著變重要：class、interface 這類東西都能用 schema 描述。（驗證仍照先前「有需要再用 json schema 去限制」，[LLM kernel](2026-10-15-llm-kernel.md)）

## 結論（AI 整理，待使用者確認）

**性質一句話**：凡是要放一張 inst 的地方（loop 的 `inst`、daemon 的 `children`、fsm 的格、閘門的 `target`、agent 的 `brain`／`tools`、kernel 的判官），都可以寫**名字**（路徑、資料夾、`檔#/位置`）或**整張貼進去**（物件）；貼進去的那張自己也可以是組合子（fsm／loop／daemon／gate），它的零件又是名字或整張。所以一棵 aos 程式樹就是一份 JSON 資料——跟 Lisp 的 `3`／`(+ 1 2)`、`(daemon (fsm b c))` 一樣，程式＝資料。現況已經做到：aos_inst／fsm／daemon／gate／agent 都收兩種（N-25、N-36、daemon.md、gate、agent.md），內嵌格的 id＝外層 id 接 `#/states/<名>`（aos_methods.cell）。

**可利用的地方**（按「收益／成本」排，前面最划算）：

1. **攤平／收攏工具**：一棵樹可以存成一份 JSON，也可以存成資料夾（每格一檔）；兩者等價，一支小工具就能互轉（10-14 拍板已說「需要時攤成資料夾」）。給人看用一份、要各自落 state／work 用資料夾。
2. **把 inst 當資料傳而不跑它＝quote**：閘門已經在做（把 target 整張連 `_metainfo` 塞進信，kernel 之後才跑）；判官拿到的 queue、agent 的工具說明 `_tool`，都是「看一張 inst 但不跑」。規則定一句：放在 `inst`／`target`／格的位置才是要跑的，放在別的 key（信的內容、stdin）就是資料。
3. **樹走一遍就能彙總 `_metainfo`**（C-22、C-13、kernel 截流）：kernel 不用問人，照樹往下走、把葉子的 `resource`／確定性收上來；名字＝去讀那檔，物件＝直接看。一棵樹的「可預測度」就是葉子的函數。
4. **巨集＝吃一棵樹、吐一棵樹的小程式**：retry、timeout、race、foreach 這些組合子（10-lisp §25）不必都做成執行期功能，有些可以是「改寫樹」：`retry 3` 就是把那格包成一個小 fsm（跑→失敗回同格→數到 3 進 error）。做成 inst，給人也給 agent 用。
5. **agent 改自己的樹＝自我改進**（C-42、10-13 kernel/agent）：agent.json 既是資料又是程式，agent 用工具改它（換腦、加工具、改 next）就是改自己；一步一落檔、改壞靠 git 回頭。同像性讓「改程式」退化成「改 JSON」，小模型也做得到。
6. **內容雜湊當身分**：內嵌的那張沒有路徑，就拿整張的雜湊當 id——相同的樹就是同一個東西，可以快取結果（確定性高的葉子）、去重排隊的信。
7. **印樹／比對／重播**：同一支 tree printer 可以把任何一棵樹畫成 `(daemon (fsm b c))` 這種一行 S 式；兩棵樹 diff 就是 JSON diff；重播＝把當時的樹連 stdin 一起存起來再跑一次。
8. **綁定＝填幾個 key**（bob／frame）：agent 的 bob/ 是函數、frame 是這次的綁定；同像性下「部分套用」就是拿一棵樹、填進幾個 key（state 窗位置、cwd、stdin）吐出另一棵樹，跟上面的巨集是同一招。

**JSON schema 的角色**：schema 就是「這份 JSON 長什麼樣」的說明書，所以它能當**型別**用——C++ class 的欄位＝`properties`，Go interface 的方法集合＝「stdin 收什麼、stdout 吐什麼」各一份 schema。schema 本身也是 JSON，所以也同像：可以放進 inst、`$ref` 拆檔、被 agent 讀與改。

- (a) 已經有：工具的 `_tool.parameters` 就是 schema（OpenAI tool 參數），腦直接拿它決定怎麼叫。
- (b) **簽名**：一格、一個 agent、閘門、判官的 stdin／stdout 形狀各附一份 schema，就是 C-42「工具＝標頭檔」的落實；判官回話的形狀（run／defer／reject）現在只寫在文件，寫成 schema 就能驗。
- (c) **interface＝一份 schema**：凡 stdin／stdout 符合同一份 schema 的 inst 可以互換——「換腦只改一個 TARGET」的道理就在這（腦的介面＝chat completions 那塊的 schema）。
- (d) 值的雙形在 schema 裡就是 `oneOf: [純值, 物件]`，`priority`、fsm 的格都能這樣寫。
- (e) 驗證選用：基礎實作不驗（只處理認得的 key，C-48）；標準實作或某張 inst 想驗再開。

## 未決（≤7）

1. **內嵌那張的身分**：有外層 id 時已經接 `#/位置`（aos_methods），完全從 stdin 來的樹才是 null；log／lock／state 窗要穩定名字。建議預設：有路徑就接位置，沒有就用內容雜湊，不留 null。
2. **內嵌子樹裡的相對路徑算誰的**：N-35 說窗不是切下來，建議預設：一律從**那份檔所在的資料夾**算（agent 前端已照 bob/ 算）；從 stdin 來的從呼叫者 cwd 算。
3. **把名字攤成物件時碰到循環**（a 指 b、b 指 a）：建議預設：攤平工具記走過的 realpath，重複就停、留名字不攤、回警告。
4. **樹太大**：daemon 底下全攤開會很長。建議預設：攤平只到使用者指定的深度，其餘留名字；id 照 1。
5. **一個物件何時算「資料」何時算「要跑的 inst」**：建議預設：只看位置（`inst`／`target`／格／`brain`／`tools`／`children` 才跑），不看形狀；要把 inst 當資料傳就放別的 key。
6. **schema 放哪**：建議預設：inst 上加私有 key `_schema: {"stdin": …, "stdout": …}`（值可以是 `$ref` 拆檔）；`_tool.parameters` 不動（它是給腦看的 OpenAI 形狀），等於 `_schema.stdin` 的特例，兩邊都寫時以 `_tool` 為準。
7. **schema 的 `allOf`／`$ref` 像繼承，跟「不做繼承」（[thinking 08 第 3 題](2026-10-14-json-entry/08-fsm拍板與改寫.md)）怎麼調和**：建議預設：方法表仍不繼承（每張 agent 寫整張）；schema 可以用 `$ref` 拼（那是拆檔，C-48 允許），`allOf` 不禁止但自家 schema 先不用——interface 只講「符合」，不講「是誰的子類」。

## 最輕下一步

- 一支 `aos_tree.py`：`print`（畫成一行 S 式）、`inline`（名字攤成物件，記循環、限深度）、`outline`（物件攤成資料夾）。先只做 print 與 inline，拿 demo 的 agent 樹試。
- 寫法跟 aos_cli 一樣收 TARGET（可接 `#/位置`）；不改任何執行期程式。
- schema 先只做一件：給判官回話寫一份 `_schema.stdout`，用現成的 jsonschema 套件在判官測試裡驗，執行期不驗。
