# 2026-10-15 同像性：inst 也是「純值或物件」的大號版

← [討論紀錄](README.md)｜前情：[JSON 格式族](2026-10-15-json-families.md)（值的雙形）、[Lisp 組合子](2026-10-14-json-entry/10-lisp組合子.md)｜概念：[C-48](../CONCEPTS/01-設計理念.md)、[C-22](../CONCEPTS/05-agent.md)、[C-42](../CONCEPTS/05-agent.md)｜規範：[N-35](../NORMS/01-總則.md)、[N-30](../NORMS/03-基礎設施-inst.md)、[N-36](../NORMS/07-基礎設施-組合子.md)｜程式：lib fsm.md（已刪，見 git 歷史 5546be29）、agent.md、aos_methods.cell

## 原文（10-15，照記）

「然後剛剛那個純值和物件那塊，其實我們這個aos inst也是一個大號的類似感覺，也就是同樣照lisp來：(daemon inst-a), (daemon (fsm inst-b inst-c))，這是同相性，除去路徑可以共用外，也可以讓fable去思考這樣的性質還有哪裡可利用。」

使用者補充（同日）：「json schema在此也就跟著變得重要了，想想看，所謂的C++ class，其實也可以用json schema來表述。相關的interface等概念也是」

## 決定（使用者 10-15 定）

- inst 的「寫路徑或整張內嵌」跟 C-48 的「值是純值或物件」是同一件事，是 aos 的同像性（程式長得跟資料一樣）。路徑可以共用是第一個好處；其他用法交 AI 想。
- JSON schema 跟著變重要：class、interface 這類東西都能用 schema 描述。（驗證仍照先前「有需要再用 json schema 去限制」，[LLM kernel](2026-10-15-llm-kernel.md)）

## 結論（10-20 使用者確認：留性質與 schema 的角色）

**性質一句話**：凡是要放一張 inst 的地方（loop 的 `inst`、daemon 的 `children`、fsm 的格、閘門的 `target`、agent 的 `brain`／`tools`、kernel 的判官），都可以寫**名字**（路徑、資料夾、`檔#/位置`）或**整張貼進去**（物件）；貼進去的那張自己也可以是組合子（fsm／loop／daemon／gate），它的零件又是名字或整張。所以一棵 aos 程式樹就是一份 JSON 資料——跟 Lisp 的 `3`／`(+ 1 2)`、`(daemon (fsm b c))` 一樣，程式＝資料。現況已經做到：aos_inst／fsm／daemon／gate／agent 都收兩種（N-25、N-36、daemon.md、gate、agent.md），內嵌格的 id＝外層 id 接 `#/states/<名>`（aos_methods.cell）。（10-20 註：loop 放身體的 key 10-19 晚改叫 `run`〔[ideas § 22](2026-10-19-ideas.md)〕；閘門、gate 是舊說法——閘門與 kernel 的舊程式連同 aos_methods 等 lib 10-19 整套刪〔git 歷史 5546be29〕，kernel 現無實作〔N-42〕；`檔#/位置` 現行寫法見 N-62。）

（AI 列的 8 個可利用處 10-20 使用者決定刪；已落成決定的見下方「決定」段，舊版見 git 歷史）

**JSON schema 的角色**：schema 就是「這份 JSON 長什麼樣」的說明書，所以它能當**型別**用——C++ class 的欄位＝`properties`，Go interface 的方法集合＝「stdin 收什麼、stdout 吐什麼」各一份 schema。schema 本身也是 JSON，所以也同像：可以放進 inst、`$ref` 拆檔、被 agent 讀與改。

- (a) 已經有：工具的 `_tool.parameters` 就是 schema（OpenAI tool 參數），腦直接拿它決定怎麼叫。
- (b) **簽名**：一格、一個 agent、閘門、判官的 stdin／stdout 形狀各附一份 schema，就是 C-42「工具＝標頭檔」的落實；判官回話的形狀（run／defer／reject）現在只寫在文件，寫成 schema 就能驗。（10-20 註：`defer` 已被 KISS 1.8 刪，判官只回 `{run, reject}`，見 [KISS 彙整](2026-10-15-kiss/README.md)。）
- (c) **interface＝一份 schema**：凡 stdin／stdout 符合同一份 schema 的 inst 可以互換——「換腦只改一個 TARGET」的道理就在這（腦的介面＝chat completions 那塊的 schema）。（10-20 註：TARGET 是舊說法，10-15 [第三版](2026-10-15-inst-exec-v3.md)、[第四版](2026-10-15-inst-exec-v4.md)拿掉。）
- (d) 值的雙形在 schema 裡就是 `oneOf: [純值, 物件]`，`priority`、fsm 的格都能這樣寫。
- (e) 驗證選用：基礎實作不驗（只處理認得的 key，C-48）；標準實作或某張 inst 想驗再開。

## 決定（10-15 使用者「都照建議」，原 7 個未決）

1. **內嵌的身分**：有路徑就接 `#/位置`，沒有就內容雜湊（`sha256:…`），不留 null。（10-15 使用者「都照建議」）
2. **內嵌子樹裡的相對路徑**：找子 inst 的名字一律從那份檔所在的資料夾算；從 stdin／dict 來的從呼叫者 cwd 算。葉子自己的 argv／cwd 不動（照 aos_inst 是執行時 cwd）。（同上）
3. **循環**：攤平記走過的 realpath，重複就停、留名字、stderr 回警告。（同上）
4. **樹太大**：攤平只到指定深度（預設 16），其餘留名字；id 照 1。（同上）
5. **資料或要跑的 inst**：只看位置（`inst`／`target`／格／`brain`／`tools`／`judge`／`children`），不看形狀；要當資料傳就放別的 key。（同上）
6. **schema 放哪**：inst 上私有 key `_schema`（`{"stdin", "stdout"}`，值可以是普通路徑拆檔）；`_tool.parameters` 不動，兩邊都寫以 `_tool` 為準。（同上）
7. **`allOf`／`$ref` 與不做繼承**：方法表仍不繼承；schema 可用 `$ref` 拼，`allOf` 不禁止但自家先不用。（同上）

## 動工（10-15）

〔10-15 使用者：aos_tree 只是看看狀況的小工具，不納入規範；它的 id／inline 行為是工具自己的做法。〕 `aos_tree.py`（`print`／`inline`，不跑任何東西）與 `test_tree.py`（兩檔 10-15 深夜 KISS 批次 1 刪，見 git 歷史 7ea404ea） 做好了；`outline`（物件攤成資料夾）還沒做。判官 schema 放 judge.schema.json（已刪，見 git 歷史 5546be29），`judge-rules.json` 用普通路徑 key `_schema` 指它；測試用手寫最小驗證器驗 `judge_rules.py` 的輸出，執行期不驗。
