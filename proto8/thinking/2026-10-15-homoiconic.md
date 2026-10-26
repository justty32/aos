# 2026-10-15 同像性：inst 也是「純值或物件」的大號版

← [討論紀錄](README.md)｜前情：[JSON 格式族](2026-10-15-json-families.md)（值的雙形）、[Lisp 組合子](2026-10-14-json-entry/10-lisp組合子.md)｜概念：[C-48](../docs/CONCEPTS/01-設計理念.md)、[C-22](../docs/CONCEPTS/05-agent.md)、[C-42](../docs/CONCEPTS/05-agent.md)｜規範：[N-35](../docs/NORMS/01-總則.md)、[N-30](../docs/NORMS/03-基礎設施-inst.md)、[N-36](../docs/NORMS/07-基礎設施-組合子.md)

## 原文（10-15，照記）

「然後剛剛那個純值和物件那塊，其實我們這個aos inst也是一個大號的類似感覺，也就是同樣照lisp來：(daemon inst-a), (daemon (fsm inst-b inst-c))，這是同相性，除去路徑可以共用外，也可以讓fable去思考這樣的性質還有哪裡可利用。」

使用者補充（同日）：「json schema在此也就跟著變得重要了，想想看，所謂的C++ class，其實也可以用json schema來表述。相關的interface等概念也是」

## 決定（使用者 10-15 定）

- inst 的「寫路徑或整張內嵌」跟 C-48 的「值是純值或物件」是同一件事，是 aos 的同像性（程式長得跟資料一樣）。路徑可以共用是第一個好處；其他用法交 AI 想。
- JSON schema 跟著變重要：class、interface 這類東西都能用 schema 描述。（驗證仍照「有需要再用 json schema 去限制」，[LLM kernel](2026-10-15-llm-kernel.md)）

## 結論（10-20 使用者確認：留性質與 schema 的角色）

**性質一句話**：凡是要放一張 inst 的地方（loop 的身體、daemon 的 `children`、fsm 的格、閘門的 `target`、agent 的 `brain`／`tools`、kernel 的判官），都可以寫**名字**（路徑、資料夾、`檔#/位置`，現行寫法見 N-62）或**整張貼進去**（物件）；貼進去的那張自己也可以是組合子（fsm／loop／daemon／閘門），它的零件又是名字或整張。所以一棵 aos 程式樹就是一份 JSON 資料——跟 Lisp 的 `3`／`(+ 1 2)`、`(daemon (fsm b c))` 一樣，程式＝資料。內嵌格的 id＝外層 id 接 `#/states/<名>`。kernel 現無實作（N-42）。

**JSON schema 的角色**：schema 就是「這份 JSON 長什麼樣」的說明書，所以它能當**型別**用——C++ class 的欄位＝`properties`，Go interface 的方法集合＝「stdin 收什麼、stdout 吐什麼」各一份 schema。schema 本身也是 JSON，所以也同像：可以放進 inst、`$ref` 拆檔、被 agent 讀與改。

- (a) 已經有：工具的 `_tool.parameters` 就是 schema（OpenAI tool 參數），腦直接拿它決定怎麼叫。
- (b) **簽名**：一格、一個 agent、閘門、判官的 stdin／stdout 形狀各附一份 schema，就是 C-42「工具＝標頭檔」的落實；判官回話的形狀（`{run, reject}`）寫成 schema 就能驗。
- (c) **interface＝一份 schema**：凡 stdin／stdout 符合同一份 schema 的 inst 可以互換——「換腦只換一張 inst」的道理就在這（腦的介面＝chat completions 那塊的 schema）。
- (d) 值的雙形在 schema 裡就是 `oneOf: [純值, 物件]`，`priority`、fsm 的格都能這樣寫。
- (e) 驗證選用：基礎實作不驗（只處理認得的 key，C-48）；標準實作或某張 inst 想驗再開。

## 決定（10-15 使用者「都照建議」，原 7 個未決）

1. **內嵌的身分**：有路徑就接 `#/位置`，沒有就內容雜湊（`sha256:…`），不留 null。
2. **內嵌子樹裡的相對路徑**：找子 inst 的名字一律從那份檔所在的資料夾算；從 stdin／dict 來的從呼叫者 cwd 算。葉子自己的 argv／cwd 不動（照 inst 是執行時 cwd）。
3. **循環**：攤平記走過的 realpath，重複就停、留名字、stderr 回警告。
4. **樹太大**：攤平只到指定深度（預設 16），其餘留名字；id 照 1。
5. **資料或要跑的 inst**：只看位置（`inst`／`target`／格／`brain`／`tools`／`judge`／`children`），不看形狀；要當資料傳就放別的 key。
6. **schema 放哪**：inst 上私有 key `_schema`（`{"stdin", "stdout"}`，值可以是普通路徑拆檔）；`_tool.parameters` 不動，兩邊都寫以 `_tool` 為準。
7. **`allOf`／`$ref` 與不做繼承**：方法表仍不繼承；schema 可用 `$ref` 拼，`allOf` 不禁止但自家先不用。

使用者 10-15：aos_tree（印樹、攤平的小工具）只是看看狀況用，不納入規範；它的 id／inline 行為是工具自己的做法。
