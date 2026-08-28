# aos SPEC — normative 規格

← [docs](README.md)

## 本檔的地位

- **本檔是 aos 唯一的 normative 文件。** 其他一切——parser 的行為、各 `docs/` 的說明、
  餵給 LLM 的 prompt——都從本檔派生。任何其他文件與本檔不一致時，以本檔為準。
- **本檔與實作衝突時，以本檔為準，實作視為 bug**——除非該條款帶 `(planned)` 標記
  （見下方三向標記）。
- [wf/workflows/ideas/verdicts.md](../wf/workflows/ideas/verdicts.md) 是**判例索引**
  （裁決的出處與脈絡），本檔是**法典**（裁決的現行條文）。查「為什麼」去那邊，查
  「是什麼」看這裡。
- 位階詞沿用 RFC 2119 的英文原字：**MUST**／**MUST NOT**／**SHOULD**／**SHOULD NOT**／
  **MAY**。內文中文。
- 條款編號 `§<區>-<號>`。**編號永不重用**；廢止的條款標 `(deprecated)` 保留原文，不刪。

## 裁決如何進入本檔

- 實作或討論中下的**新裁決＝正式裁決**：同一 commit 內記回
  [ideas](../wf/workflows/ideas/README.md) 對應檔＋verdicts，**並在本檔補條款**。
- 條款的新增、修改、位階變更 **MUST 經使用者點頭**（走
  [build-cycle](../wf/workflows/build-cycle/README.md) 閘門）；AI 不得自行修憲。
- **三向標記**（規格與實作有落差時怎麼寫）：
  1. 已裁決且已實作 → 直接寫，無標記。
  2. 已裁決、未實作 → 條款帶 **`(planned, <階段>)`**。
  3. 規格與實作矛盾、**尚未拍板** → **不入條款**，列進文末「已知未決」。

---

## A 機器模型

- **§A-1** 真正的指令是**批**：造成一次狀態轉移的單位是一整批，一回合＝一整批，不是
  一次一筆。單筆 inst 是批內的一個 slot。
  來源：verdicts A 表「抽象 CPU 的回合」／instruction §1／aos-folder 五。
- **§A-2** 整批 **MUST** 先全部驗證通過，才開始執行其中任何一筆；任一筆驗證失敗，
  整批不執行。
  來源：aos-folder 五／format.md。
- **§A-3** **一個回合內沒有資料流**：整批在任何一筆執行之前完成全部指示詞求值，因此
  `$ref` **MUST NOT** 依賴同一批內另一筆指令的產物；一個回合是純粹的並行構造，任何
  資料鏈接 **MUST** 跨回合。
  來源：instruction §18（第九輪實測，2026-08-28 立法）。
- **§A-4** 沒有 `inst.json` ＝ 停留在目前回合，不是錯誤，`aos exec` 退出碼 0。
  來源：aos-folder 五。
- **§A-5** 回合邊界是硬的：回合內 **MAY** 並行（`parallel` 欄位），但執行器 **MUST**
  等所有執行（含並行 thread）結束才算回合結束。並行只發生在回合之內。
  來源：aos-folder 五。
- **§A-6 凍結的矽**：exec 層（fork/exec 執行機制本身）**MUST NOT** 增長新機制；演化
  只發生在指令內容與外圈（彙整、loop）。推論見 §C-8（exec 不認識 header）與 §C-9
  （`$ref` 不取指令）。
  來源：instruction §22（第十輪），裁於 2026-08-28。

## B 命名與版面

（本區待收編，`(planned, M1)`。現行敘述見 [aos-folder](aos-folder.md) 二／三；命名
標準、`.aos/` 版面、`.bad` 正名、版面 ownership 屆時進本區。）

## C 指令格式（序列化）

- **§C-1 嚴解析、鬆執行**：序列化層 **MUST** 嚴格（未知 key 拒絕、型別嚴驗），執行層
  刻意寬鬆（合法即執行，不做語意檢查）。這是刻意的，不是缺陷。
  來源：verdicts A 表。
- **§C-2** instruction 檔是**一份完整 JSON 文件**：頂層是單一指令物件，或指令物件組成
  的陣列（空陣列＝合法的空批次）。JSON Lines **MUST NOT** 接受。實作 **MUST** 先讀到
  EOF、再解析並驗證整份文件。
  來源：format.md。
- **§C-3 欄位表**（normative；本表**只在本檔**，說明與範例見
  [format.md](../core/inst/docs/format.md)）：

  | 鍵 | JSON 型別 | 必填 | 預設 | 意義 |
  | --- | --- | --- | --- | --- |
  | `argv` | array of strings/directives | yes | none | 指令及其引數。解析後此陣列與 `argv[0]` 都不得為空。 |
  | `stdin` | string | no | `""` | 以唯讀方式開啟、作為標準輸入的檔案；為空時繼承呼叫端的 stdin。 |
  | `stdout` | string | no | `""` | 作為標準輸出的檔案，必要時建立並截斷(清空)；為空時繼承 stdout。 |
  | `stderr` | string or directive | no | `""` | 字串會作為標準錯誤的檔案；`{"$opt":"merge"}` 併入 stdout，`{"$env":"X"}` 從環境取得路徑。 |
  | `exit` | string | no | `""` | 子行程結束後建立/截斷(清空)的檔案，寫入十進位狀態值加一個 LF；為空時捨棄。 |
  | `cwd` | string | no | `""` | 子行程的工作目錄；為空時使用 `<folder>`。相對路徑值從 `<folder>` 起算。 |
  | `env` | object, string values | no | `{}` | 在繼承的環境之上覆寫或新增變數；未提及的變數維持不變。 |
  | `timeout_ms` | unsigned integer | no | `0` | 執行時間上限（毫秒）；為零時無期限等待。（已裁決移出最內圈、改由 loop 層管——`(planned, M2)`，見已知未決） |
  | `parallel` | boolean | no | `false` | 為 `true` 時以獨立 thread 執行這一筆，不等它完成就啟動下一筆；整批結束前仍會等待它（§A-5）。 |

  來源：format.md（2026-08-28 搬入）。
- **§C-4 指示詞**：所有字串值位置（`argv` 元素、五個路徑欄位、`env` 的值）**MAY** 用
  `{"$env":"NAME"}` 或 `{"$ref":"file.json#/pointer"}`；`stderr` 另可用
  `{"$opt":"merge"}`。指示詞物件 **MUST** 恰好一個 key、值 **MUST** 是字串。`env` 的
  key 與 `timeout_ms` **MUST NOT** 接受指示詞。未解析的指示詞 **MUST** 能原樣寫回
  JSON（round-trip）——彙整會把每份投遞完整往返格式層一次，不滿足這條的指示詞會被
  無聲吃掉；任何新增指示詞都受此約束。
  來源：format.md／aos-folder 七。
- **§C-5** 未知 key **MUST** 拒絕（`UnknownKey`），不是忽略。舊執行檔遇新格式硬失敗
  是刻意的。
  來源：format.md／keep。
- **§C-6 驗證狀態表**（normative；本表**只在本檔**）：

  | 條件 | `InstState` / C 狀態 |
  | --- | --- |
  | 輸入指標為 null | `InvalidArgument` / `AOS_INST_INVALID_ARGUMENT` |
  | JSON 無效，包含單筆記錄的空緩衝區 | `JsonSyntax` / `AOS_INST_JSON_SYNTAX` |
  | 單筆值或陣列元素不是物件；批次頂層不是物件或陣列 | `NotAnObject` / `AOS_INST_NOT_AN_OBJECT` |
  | key 不在綱要(schema)內 | `UnknownKey` / `AOS_INST_UNKNOWN_KEY` |
  | 欄位型別錯誤、引數非字串，或環境（變數）值非字串 | `FieldTypeMismatch` / `AOS_INST_FIELD_TYPE_MISMATCH` |
  | `argv` 缺少/為空，或 `argv[0]` 為空 | `EmptyArgv` / `AOS_INST_EMPTY_ARGV` |
  | 環境（變數）key 為空，或 key 含有 `=` | `EnvKeyInvalid` / `AOS_INST_ENV_KEY_INVALID` |
  | 指示詞物件不是剛好一個 key | `DirectiveKeyCountInvalid` / `AOS_INST_DIRECTIVE_KEY_COUNT_INVALID` |
  | 指示詞的唯一 key 不是 `$opt`、`$env` 或 `$ref` | `UnknownDirective` / `AOS_INST_UNKNOWN_DIRECTIVE` |
  | 指示詞的值不是字串 | `DirectiveValueTypeMismatch` / `AOS_INST_DIRECTIVE_VALUE_TYPE_MISMATCH` |
  | `$opt` 的值不是已知的 `merge` | `UnknownOption` / `AOS_INST_UNKNOWN_OPTION` |

  上表是**全部**的拒絕條件；除此之外只要是合法 JSON 且符合綱要就 **MUST** 接受。
  來源：format.md（2026-08-28 搬入）。
- **§C-7 沒有任何上限**：位元組數、`argv` 元素數、`env` 條目數、JSON 巢狀深度
  **MUST NOT** 設上界（上限是猜出來的常數，資源自有更好的邊界：`ulimit`／cgroup／
  `ARG_MAX`）。代價：深層巢狀會讓解析器遞迴爆堆疊——指令檔等同可執行程式碼，
  **MUST NOT** 拿本執行器直接讀不可信的輸入。
  來源：format.md／keep。
- **§C-8 批 header** `(planned, M1)`：批的 metadata 住在**批檔旁的 sidecar 檔**
  （建議名 `<名字>-head.json`，核心 CPU 即 `.aos/inst-head.json`；確切檔名隨 B 區收編
  定案）。欄位 v1：

  | 欄位 | 意義 |
  |---|---|
  | `version` | 指令格式版本（整數；見 §F-1）。現行格式＝1 |
  | `id` | 批 id（唯一；去重的依據） |
  | `origin` | 指令來源：`"aggregated"`（經彙整祝福）或 `"direct"`（直接寫入） |
  | `result` | 彙總狀態欄；由 loop 於 writeback 寫回（值域於 M2 定義） |

  **exec 層 MUST NOT 讀取或認識 header**（§A-6 的推論）；header 由彙整層寫、loop 讀。
  環境指紋／manifest（instruction §23）留 v2。
  來源：verdicts B1／instruction §22・§23，裁於 2026-08-28。
- **§C-9** `$ref` 的值域是**資料值**：`$ref` **MUST NOT** 引用一筆 inst 或一個批
  （連結器不進 decode）。「程式／副程式」若要存在，屬於外圈（彙整或 loop），不屬於
  指令格式。
  來源：§A-6 的推論，封死 instruction §3 那條擴充；裁於 2026-08-28。

## D 交接協定

（本區待收編，`(planned, M1)`。現行敘述見 [aos-folder](aos-folder.md) 六；三步協定、
彙整規則、`deliver` 屆時進本區。）

## E 世界與 git

（本區待收編，`(planned, M1)`。現行敘述見 [aos-folder](aos-folder.md) 四／十；路徑
基準、footprint 宣告（instruction §24）、`.gitignore` 政策屆時進本區。）

## F 版本

- **§F-1 格式版本** `(planned, M1)`：指令格式（批＋inst schema）的版本住在批 header
  的 `version` 欄（§C-8）。現行格式＝v1；本檔對格式的任何不相容修改 **MUST** 遞增它。
  來源：verdicts B10／instruction §2，裁於 2026-08-28。
- **§F-2 版面版本**：`.aos/` 版面的版本住在 `.aos/version`（已存在）。**格式版本與
  版面版本是兩件不同的事**，MUST 分開存放與遞增。版面版本的完整條款（讀不到＝拒絕、
  不認得＝拒絕）隨 B 區收編 `(planned, M1)`；現行行為見 aos-folder 九。
  來源：verdicts B10／layout-and-spec §16。

---

## 已知未決（不入條款）

規格與實作矛盾、尚未拍板的事。收編到對應區時 **MUST** 先拍板或原樣移入本節。

1. **SIGINT 斷點續跑**：roadmap T5 的驗收條件（Ctrl-C 後從斷點繼續）與 aos-folder 六
   的 `.runi` 語意互相矛盾——單次 `aos exec` 被 SIGINT 中止會留 `.runi`、只能重播
   整批，外部作用可能已發生。哪邊改未拍板。（T5 實測，2026-08-25）
2. **退出碼表不完整**：aos-folder 八的四碼表與實作對不上（T5 實測）。D 區收編時對齊。
3. **`<pid>.json` 表達不了同一 process 的多次投遞**：投遞檔名 pid 不唯一。M1 修
   `deliver` 時一併裁。
4. **`timeout_ms` 已裁決移出最內圈**（由 loop 層管），實作未動；§C-3 保留現行欄位並
   標 planned，M2 搬遷時更新。
