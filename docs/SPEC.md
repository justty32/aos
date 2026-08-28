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

- **§B-1 命名標準**：`<名字>.<副檔名>.<狀況>`。副檔名：`.json`（JSON 檔）、`.d`（一般
  資料夾）、`.tempd`（投遞匣資料夾）。狀況（**封閉清單**）：`.temp`（還在生成，別碰）、
  `.runi`（已被取走、正在跑）、`.bad`（內容無效，已被隔離）。**MUST NOT** 用新狀況字
  表達同一件事；新增狀況字＝修憲。本標準為 `.aos` 訂，但不限於 `.aos`。
  來源：aos-folder 二；`.bad` 正名收編（verdicts D 表漂移證據），裁於 2026-08-28。
- **§B-2 `.aos/` 版面樹**：

  ```text
  .aos/
      version              ← 版面版本（§B-4）
      turn                 ← 回合計數器（§B-3）
      turn.temp            ← turn 遞增用的中間檔（turn 沒有副檔名，狀況字直接接名字後）
      .gitignore           ← 由 aos init 建立，內容照 §E-4
      inst.json            ← 核心 CPU 待執行的批次（特權位）
      inst.json.runi       ← 已取走、正在跑
      inst-<pid>-<seq>.json.temp       ← 彙整寫批用的每行程唯一暫存（§D-5）
      inst-head.json       ← 批 header sidecar（§C-8）
      inst-head-<pid>-<seq>.json.temp  ← 彙整寫 header 用的每行程唯一暫存（§D-5）
      inst.tempd/          ← 投遞匣
      insts/               ← 其他 CPU，一顆一份（同名配 .temp/.runi/.tempd 與 -head.json）
  ```

  其他 CPU **SHOULD** 遵循同一套協定，不強迫。`aos init` **MUST** 建立 `.gitignore`；
  舊世界缺這個檔 **MUST NOT** 視為錯誤。
  來源：aos-folder 三；header 檔名裁於 2026-08-28（M1 裁-3）；中間檔、每行程唯一暫存名
  與 `.gitignore` 補列，裁於 2026-08-28（M1 審查修補 #14／#20／#23）。
- **§B-3 `.aos/turn`**：回合計數器（這台機器的 PC）。`aos init`
  **MUST** 建立、初值 `0` 加 LF；由 CLI 回合層（loop）持有；release 成功後 **MUST**
  遞增。讀不到（舊世界）**MUST** 視為 `0` 並於首次遞增時建立——**MUST NOT** 拒絕、
  **MUST NOT** 變動版面版本。
  來源：§27 三小裁決＋M1 裁-5，裁於 2026-08-28。
- **§B-4 版面版本**：`.aos/version` 住版面版本。讀不到 ＝ 不是合法 `.aos`，**MUST**
  拒絕；版本不認得（比自己新）＝ **MUST** 拒絕，不猜、不盡力而為。現行版面＝1；
  `turn` 與 `inst-head.json` 是純新增，**MUST NOT** 因此 bump。
  來源：aos-folder 九。

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
- **§C-8 批 header**：批的 metadata 住在**批檔旁的 sidecar 檔** `<名字>-head.json`
  （核心 CPU 即 `.aos/inst-head.json`，檔名定案於 §B-2）。欄位 v1：

  | 欄位 | 意義 |
  |---|---|
  | `version` | 指令格式版本（整數；見 §F-1）。現行格式＝1 |
  | `id` | 批 id（唯一；去重的依據） |
  | `origin` | 指令來源：`"aggregated"`（經彙整祝福）或 `"direct"`（直接寫入） |
  | `result` | 彙總狀態欄；由 loop 於 writeback 寫回（值域於 M2 定義） |
  | `swept` | 這一批的來源投遞清乾淨了沒（布林）。發布時寫 `false`；投遞全數刪除且目錄落盤後改寫成 `true` |

  **`swept` 是去重的閘門**：只有 `swept` 不成立的 header 才啟用 §D-6 的比對。已 swept
  ＝上一批的清理已經走完，**MUST NOT** 再擋任何投遞——同名同內容的**全新**投遞
  **MUST** 照常發布。缺 `swept` 欄（舊世界寫的 header）**MUST** 視為 `false`。
  **exec 層 MUST NOT 讀取或認識 header**（§A-6 的推論）；header 由彙整層寫、loop 讀。
  環境指紋／manifest（instruction §23）留 v2。
  來源：verdicts B1／instruction §22・§23，裁於 2026-08-28；`swept` 欄裁於 2026-08-28
  （M1 審查修補 #1：內容導出的 id 分不出「殘留」與「重投」，靠 sweep 標記界定射程）。
- **§C-9** `$ref` 的值域是**資料值**：`$ref` **MUST NOT** 引用一筆 inst 或一個批
  （連結器不進 decode）。「程式／副程式」若要存在，屬於外圈（彙整或 loop），不屬於
  指令格式。
  來源：§A-6 的推論，封死 instruction §3 那條擴充；裁於 2026-08-28。

## D 交接協定

- **§D-1 三步協定**：投遞 → 彙整 → 取件，每步一次 `rename`。
  ```text
  投遞  inst.tempd/<名>.json.temp ─rename─▶ inst.tempd/<名>.json
  彙整  併成 inst-<pid>-<seq>.json.temp ─rename─▶ inst.json（排他，§D-5 順序）
  取件  inst.json                  ─rename─▶ inst.json.runi
  ```
  來源：aos-folder 六。
- **§D-2 投遞**：生產者 **MUST** 先寫 `<名>.json.temp`、寫完才 `rename`（寫入不原子，
  共用檔名會互相蓋寫）。投遞檔名 **MUST** 唯一：`aos deliver` 用 `<pid>-<seq>`
  （`seq` 為行程內單調計數）；發布 **MUST** 排他（`RENAME_NOREPLACE` 或 `link`＋`unlink`
  退階），**MUST NOT** 覆蓋既有名——pid 會回收，唯一性最終由排他發布擔保。
  來源：aos-folder 六＋M1 裁-1，裁於 2026-08-28。
- **§D-3 `deliver`**：投遞是唯一由外部生產者執行的協定步驟，**MUST**
  有程式提供：`aos deliver [folder]`（吃 stdin 或檔案）＋ C ABI。驗證 **MUST** 走唯一
  parser（C 區）；發布的位元組 **MUST** 是 canonical（`read_all`→`write_all` 往返，
  與 §C-4 round-trip 同一條約束）；stdout **MUST** 輸出單行 JSON
  `{"delivery":"<檔名>","count":N,"target":"<inbox 相對路徑>"}`；inbox 不存在 **MUST**
  報錯，**MUST NOT** 自動建世界。
  來源：T5 subcommand-specs＋M1 裁-2／裁-7，裁於 2026-08-28。
- **§D-4 彙整規則**：只收**沒有狀況後綴**的投遞。順序不保證——投遞者 **MUST NOT**
  假設任何順序（實作 **MAY** 用字典序）；需要先後就排進同一份投遞。`inst.json` 已有
  一份沒被讀走時本輪 **MUST NOT** 發布（不覆蓋、不合併）。無效投遞：**MUST** 隔離
  （就地改名加 `.bad`）、噴 warning、繼續處理其餘。投遞 **MUST** 在**本輪處理完成之後**
  才刪——**發布成功**、**整批為空**（沒有東西可發布）、**去重命中**（§D-6）三者都算完成，
  除此之外 **MUST NOT** 刪。
  來源：aos-folder 六；「本輪處理完成」的三個例外照實寫明，裁於 2026-08-28（M1 審查修補 #16）。
- **§D-5 交接耐久性與提交點**：所有寫檔 **MUST** fsync。彙整的發布順序
  **MUST** 為：寫批 `.temp`（fsync）→ 寫 header `.temp`（fsync）→ rename header
  （**去重承諾的提交點**）→ fsync 目錄 → rename 批 → fsync 目錄 → 刪投遞 → fsync
  目錄 → 標記 header `swept`（§C-8）。header sidecar（§C-8 五欄）由彙整層寫。
  批與 header 的 `.temp` **MUST** 用**每行程唯一**的名字寫（§B-2 版面樹），且發布
  **MUST** 直接以那個唯一名為來源——彙整 **MUST NOT** 把批經過任何共用的固定暫存
  檔名。理由：共用檔名可被同儕在兩步之間換掉，於是一個彙整者會把**別人的批**發布到
  自己剛提交的 header 底下，投遞的清理與批的內容就對不起來（實測可導致一份投遞執行
  兩次）。批發布（唯一 `.temp` → `inst.json`）**MUST** 排他（`RENAME_NOREPLACE`，或
  `link`＋`unlink` 退階）：目的檔已存在＝別的彙整者先發布了，本輪 **MUST** 放棄——
  **不清投遞、不重寫 header**，並 **MUST** 刪掉自己那份唯一 `.temp`。
  **取件與釋放同受本條拘束**：取件的 rename（`inst.json` → `.runi`）之後 **MUST** fsync
  目錄；釋放的 unlink（`.runi`）之後 **MUST** fsync 目錄。耐久性失敗只記警告，
  **MUST NOT** 讓回合停擺。
  來源：gotchas handoff 節＋M1 plan S3 順序論證，裁於 2026-08-28；射程延伸到取件／釋放、
  唯一暫存名與排他發布，裁於 2026-08-28（M1 審查修補 #2／#5／#23）。
- **§D-6 批 id 與去重**：批 `id` ＝ 對排序後（投遞檔名＋內容）的
  確定性摘要（64-bit FNV-1a，16 位 hex）。彙整 **MUST** 在發布前比對現任 header 的
  `id`，且**只在該 header 的 `swept` 不成立時**啟用比對（§C-8）：同一組投遞（同名同內容、
  恰好整組）殘留於 inbox 時 **MUST NOT** 二次發布——**存在一份唯一 `.temp` 兄弟檔、
  且其位元組與本輪重算的 canonical 批位元組逐位元相同**才 roll-forward（排他 rename
  後清投遞），否則只清投遞。roll-forward 的錨**靠內容認身分、不靠檔名**：能通過逐位元
  比對的就是本輪這組投遞的批，不論它是自己上一輪崩掉留下的還是同儕正在飛的。清完投遞（且目錄落盤）之後 **MUST** 把 header 標成 `swept`。
  **覆蓋範圍**：只保證整組殘留；部分殘留混入新投遞後的重複不在保證內（條款照實寫，
  不誇大）。去重擋的是**投遞殘留**這一個方向；**併發雙重彙整**（兩個彙整者各自發布
  一次）不在去重射程內——後發布者讀 header 時前者還沒寫出去，比對本來就不可能命中，
  那個方向由 §D-5 的**排他發布**擋。
  來源：M1 裁-4／裁-6，裁於 2026-08-28；`swept` 閘門、逐位元比對與覆蓋範圍補述，
  裁於 2026-08-28（M1 審查修補 #1／#21／#23）。
- **§D-7 `.runi` 語意**：`.runi` 存在 ⟺ 有一回合沒跑完。回合正常返回 **MUST** 刪
  `.runi`——不論退出碼、**包含**整批解析失敗（壞批消失、stderr 留診斷，刻意取捨）；
  行程死掉（crash／kill／斷電）就留著。`.runi` 已存在 **MUST** 拒絕啟動（退出碼 3）；
  每顆 CPU 各鎖各的。回合內個別指令的成敗走各自 `exit` 欄位，**MUST NOT** 靠 `.runi`
  表達。
  來源：aos-folder 六。
- **§D-8 `.bad` 的清理**：彙整者 **MUST NOT** 自動刪 `.bad`；清理歸人或 `aos recover`
  （M3）。crash 之後要人來處理，一以貫之。
  來源：M1 階段裁決 3，裁於 2026-08-28。
- **§D-9 退出碼**：`aos` 全部子命令共用同一組碼，意義 **MUST** 照下表。分界是
  **「aos 自己有沒有把這一步做完」**：`aos exec` **MUST NOT** 反映子行程的成敗
  （那走 `exit` 欄位）。

  | 碼 | 意義 | 涵蓋（逐失敗模式實測，見來源） |
  |---|---|---|
  | 0 | 這一步做完了 | `aos exec`：回合跑完——**含無事可做**（§A-4）、**含子行程失敗**（非零 exit、找不到執行檔、重導向開檔失敗、逾時被砍）、**含無效投遞被隔離為 `.bad` 後續行**（§D-4）。`aos init`：世界建好。`aos deliver`：投遞落地（**含空批次**，§C-2）。`aos --help` |
  | 1 | aos 自己跑不動，或收不了尾 | 世界進不去／`.aos` 不存在或不是目錄／`.aos/version` 讀不到或不認得（§B-4）；彙整、取件、釋放失敗；整批解析或指示詞求值失敗；寫 `exit` 欄位的檔失敗；`.aos/turn` 遞增失敗（§B-3）；`aos init` 建不起來（目標不存在、`.aos` 已存在、權限不足）；`aos deliver` 的輸入讀不到、驗證不過（§C-6）或發布失敗 |
  | 2 | 用法錯誤 | 多餘參數、認不得的選項、`--loop` 的值不是正整數、未知子命令、沒給子命令。**MUST** 在碰檔案系統之前判定——所以「世界路徑打錯」是 1、不是 2 |
  | 3 | `.runi` 已存在，拒絕啟動 | 只有 `aos exec`（§D-7） |

  退出碼 1 **MUST NOT** 被讀成「這一回合沒有發生」：收尾階段的失敗（release 成功之後
  `turn` 遞增失敗）發生在回合已經推進之後。個別指令的結果一律讀 `exit` 欄位指到的檔。
  （實作註記，非條款：`aos exec --loop` 目前只有遇 3 才提早收工，回 1 的錯誤會被下一圈
  重試；loop 的錯誤政策屬 M2。）
  來源：aos-folder 八＋M1 S9 逐失敗模式實測
  （[m1-loop-side/smoke-notes](../wf/workflows/build-cycle/archive/m1-loop-side/smoke-notes.md)
  的 S9 節），收編於 2026-08-28。

## E 世界與 git

- **§E-1 世界與路徑基準**：`<folder>` ＝ 世界，`.aos/` ＝ 指令區，`aos exec <folder>`
  ＝ 推進一回合；沒有常駐狀態，世界在檔案系統上。路徑基準**一律 `<folder>`**、沒有
  例外：子行程預設 cwd、四個重導向路徑欄、`$ref` 的相對路徑；絕對路徑照字面。同一份
  instruction 從哪裡呼叫 **MUST** 是同一個意思（資料夾整包可搬）。
  來源：aos-folder 一／四（已實作：chdir 到 `<folder>`）。
- **§E-2 footprint 宣告**：一筆 inst **SHOULD** 只修改 `<folder>` 之內。實際轉移函數有
  自由變數（environ、PATH、絕對路徑、cwd 逃逸）——實作 **MUST NOT** enforce（權限與
  安全歸上層，verdicts A 表），但**越界的寫入不在 git 快照涵蓋範圍內，回滾不還原**；
  用絕對路徑逃逸者自擔後果。
  來源：instruction §24（第十輪），裁於 2026-08-28。
- **§E-3 快照與回滾**：快照、回滾、複製都用 git。回滾到含 `.runi` 的 commit ＝ 一個
  永久拒絕啟動的死鎖世界——所以機器暫態 **MUST NOT** 進 git（§E-4）。回滾含
  `inst.json` 的 commit 會重新執行舊回合（新的求值分支）——那 **MUST** 是選的，
  不是副作用（由 §E-4 讓使用者可選）。
  來源：verdicts A 表「世界沒有圍牆」＋debts §2。
- **§E-4 `.gitignore` 政策**（取代 aos-folder 十的「整包不進」）：**世界**的 gitignore
  **MUST** 排除機器暫態——`*.temp`、`*.runi`、`*.tempd/`、`*.bad`；**MUST** 納入
  `.aos/version` 與 `.aos/turn`（可攜的回合座標）。`inst.json` 與 `inst-head.json`
  （待執行批次）＝ **MAY**：納入則回滾會復原舊批次、重演回合——效果由使用者自選。
  本原始碼 repo 不是世界，其根 `.gitignore` 整包排除 `.aos/` 屬測試殘留處理，不受
  本條拘束。
  來源：M1 階段裁決 2（使用者於 roadmap 拍板）＋debts §2，裁於 2026-08-28。

## F 版本

- **§F-1 格式版本**：指令格式（批＋inst schema）的版本住在批 header
  的 `version` 欄（§C-8）。現行格式＝v1；本檔對格式的任何不相容修改 **MUST** 遞增它。
  來源：verdicts B10／instruction §2，裁於 2026-08-28。
- **§F-2 版面版本**：`.aos/` 版面的版本住在 `.aos/version`（已存在）。**格式版本與
  版面版本是兩件不同的事**，MUST 分開存放與遞增。版面版本的完整條款（讀不到＝拒絕、
  不認得＝拒絕、現行版面＝1）在 §B-4。
  來源：verdicts B10／layout-and-spec §16。

---

## 已知未決（不入條款）

規格與實作矛盾、尚未拍板的事。收編到對應區時 **MUST** 先拍板或原樣移入本節。

1. **SIGINT 斷點續跑**：roadmap T5 的驗收條件（Ctrl-C 後從斷點繼續）與 aos-folder 六
   的 `.runi` 語意互相矛盾——單次 `aos exec` 被 SIGINT 中止會留 `.runi`、只能重播
   整批，外部作用可能已發生。哪邊改未拍板。（T5 實測，2026-08-25）
2. **`timeout_ms` 已裁決移出最內圈**（由 loop 層管），實作未動；§C-3 保留現行欄位並
   標 `(planned, M2)`；**搬遷與新語意屬 M2**
   （[m2-loop-project](../wf/workflows/build-cycle/m2-loop-project/spec.md)），屆時更新
   §C-3 並移除本條。

> **已消掉的兩條**（2026-08-28，M1 S9）：原 #2「退出碼表不完整」由 §D-9 逐失敗模式
> 實測收編；原 #3「`<pid>.json` 表達不了同一 process 的多次投遞」由 §D-2 的
> `<pid>-<seq>`＋排他發布消掉。「編號永不重用」只管條款（§），本節是附錄，消掉即重排。
