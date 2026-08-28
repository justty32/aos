# M3 名冊補完：status／recover／check — 實作 plan

← [spec](spec.md)｜[build-cycle](../README.md)｜[SPEC](../../../../docs/SPEC.md)｜[code map](../../common/code-map.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 `/goal`，見 spec 開頭）。
本 plan 只講「怎麼」；「什麼」以 [spec.md](spec.md) 為準。spec 的「明確不做」一律出範圍。

**驗證一律**：從 repo 根目錄跑
`cmake --build --preset default && ctest --preset default`。
新增小專案期間**每一步都要另外驗合併版**：`cmake --preset merged && cmake --build --preset merged
&& ctest --test-dir build/merged`（`merged` **沒有** testPreset，只能用 `--test-dir`）。
手動煙霧用 `./build/bin/aos`。

> **本 plan 的檔名分兩類**：不帶標記的是**今天真的存在**的（已對照過程式碼與實跑）；
> 帶 **(M2 目標)** 的來自 [m2-loop-project/plan.md](../m2-loop-project/plan.md) 第五節
> 「動哪些檔」，**M3 開工時要先核對**（第零節）。
> 帶 **〔實測〕** 的是規劃期在 `build/bin/aos`（M1 之後、M2 之前）上跑出來的事實。

---

## 零、對 M2 落地結果的假設（**M2 做完後逐條核對，不符就改本 plan**）

M3 整份建立在下列假設上。**S0 的第一件事就是逐條打勾**；任何一條不符，先停下來改 plan
再動工（build-cycle 常備規則 3：碰到那個決定的那一行就得停下來裁）。

| # | 假設 | 怎麼核 | 不符的話影響哪裡 |
|---|---|---|---|
| A1 | `core/loop` 存在，公開標頭 `core/loop/include/aos/loop.hpp`，target `aos::loop` | `ls core/loop/include/aos/loop.hpp` | S2／S3／S9 的相依圖 |
| A2 | `core/loop` 對 `core/inst` 用 **`PUBLIC_DEPS aos::inst`**（M2 裁-14） | `grep -n 'PUBLIC_DEPS' core/loop/CMakeLists.txt` | S2（新專案照同一條走）；裁-A5 的退路 |
| A3 | `aos exec` 登記在 `core/loop/CMakeLists.txt`；`init`／`deliver` 仍在 `core/inst/CMakeLists.txt`（M2 裁-13 案 a） | `grep -rn 'aos_add_subcommand' core/*/CMakeLists.txt` | S8（`--control` 加在哪一冊）／驗收 1 |
| A4 | `core/inst/src/` 已無 `run_exec.cpp`／`run_loop.cpp`／`run_batch.cpp`；`run.hpp` 不再宣告 `run_exec` | `ls core/inst/src/run_*.cpp` | S3–S7 的測試 helper |
| A5 | 測試 helper 已拆：exec／loop 那半在 `core/loop/tests/test_loop_support.hpp`（M2 裁-15：loop 測試自己鋪 `.aos/`） | 讀那兩個檔的 `inline int *_world(...)` | S3–S7（`core/world/tests/` 看不到那些 helper，見風險 6） |
| A6 | `.aos/control.tempd/` 由 `aos init` 建立；**舊世界缺它＝視為空、不報錯、不自動建、不 bump 版面版本** | `aos init` 新世界後 `ls .aos/` | S3／S4／S5／S6／S8；`check` 那條驗證項的位階 |
| A7 | 控制記錄＝`{"op":"stop"}`（恰好一個 key）；檔名 `<pid>-<seq>.json`；三態 `.json`／`.json.temp`／`.json.bad`；解析器是**定點解析**、住 `core/loop/src/control.cpp`；**沒有 `control.json`**（不彙整成批） | 讀 `core/loop/src/control.cpp`；`grep -n 'control.json' docs/SPEC.md` 應零筆 | S5（`AOS-G7-*` 三條）／S8 |
| A8 | header `result` 四值字面＝`"ok"`／`"partial"`／`"failed"`／`"machine_failed"`，＋彙整寫的 `null`；唯一字面來源是 `aos::loop::to_string(BatchResult)`，**住 `core/loop`** | `grep -rn 'machine_failed' core/loop/` | S3 的防環規範／S4 的 enum／S5 的值域驗證 |
| A9 | **`result` 由回合層在 `release_instruction` 之前寫**（§G-2） | 讀 `core/loop/src/writeback.cpp` | **推論**：`.runi` 存在時 `result` **可能已非 `null`**（writeback 成功、release 崩了）。status MUST 容忍、check MUST NOT 判違規、recover 拿它當強證據。**M2 spec 沒點名這個組合**——不成立則 recover 矩陣的 R-1c 整格作廢 |
| A10 | SPEC 有 **§A-7／§A-8** 與 **G 區**（§G-1…§G-8）；§B-2 已含 `control.tempd/`；§B-4 已加「`control.tempd/` 純新增不 bump」；§C-3 摘標；已知未決 #4 消掉 | `grep -n '§G-\|§A-7\|control.tempd' docs/SPEC.md` | **S1 的編號整批**：H 是「G 之後的下一個字母」，§A-9 是「§A-8 之後」。M2 若改採替代案（不開 G 區），M3 的新區變 G、`§A-9` 要改號 |
| A11 | **§D-9 已有第 4 列**（loop 因連續庫層失敗停機，只在 `--loop` 模式） | `grep -n 'planned, M2' docs/SPEC.md` 應零筆；讀 §D-9 表 | 裁-B1（check 的碼從 5 起）。若 M2 最後沒加 4，check 從 4 起——但仍建議留空 |
| A12 | **§A-7 的窮舉表用「崩潰偵測」而不是「崩潰恢復」**（M2 spec 裁決 1 的字面），且條文形式是「判準＋窮舉表，衝突時表優先」 | 讀 §A-7 條文 | **裁-A2**：若寫成「崩潰**恢復**」（`machine-shape/loop.md` §25 的原文用詞），判準會把 `recover` 判給 loop，共用層的歸屬要重看 |
| A13 | `execute()` 不再施行 `timeout_ms`，且**逾時 ＝ 一次已完成的執行**（仍寫 `exit` 檔） | `grep -n 'timeout_ms' core/inst/src/exec.cpp` 零筆 | recover 矩陣裡「缺 `exit` ⟹ unknown effect」的偵測條件 |
| A14 | 版面路徑常數**仍在多處各抄一份**（M2 風險 11 認列的欠帳） | `grep -rn 'kAosDir' core/ \| wc -l` | 裁-A3（helper 升公開 API）／S9 的價值 |
| A15 | **已知未決 #1（SIGINT 斷點續跑）仍在**——M2 plan 把「順手裁掉」列為可選提案、預設不裁 | `grep -n 'SIGINT' docs/SPEC.md` | 裁-E2（M3 要不要接手裁） |
| A16 | M2 **沒有**做 `deliver --control`、**沒有**修 `.runi` 不是鎖、**沒有**開 `<aos/loop.h>` C ABI、**沒有**做多 CPU（`insts/` 仍無人建立） | `grep -rn 'insts' core/*/src/`；讀 M2 的封存 spec | S8（若 M2 順手做了，裁-D8 改成「條款補上」）／S5（`insts/` 驗證項的位階） |

---

## 一、總覽與相依圖

```text
S0 M2 假設核對（第零節 A1–A16）＋ 裁決清點（第二節 36 項）      ← 主線
  └─→ S1 SPEC 條款起草（主線；§A-9／§B-5／§B-6／§B-1・§B-2・§B-4・§C-8・§D-3・§D-9・§E-4
        │   修補／新開 H 區，未實作的帶 (planned, M3)）
        │
        └─→ S2 core/world 骨架（CMake＋空 lib＋三支只印 usage 的進入點；default 與 merged 都綠）
              ├─→ S2b core/inst 升一小組版面 helper 為公開 API（裁-A3；純新增，測試零改動）
              │     └─→ S3 WorldView 世界檢視層（唯讀掃描；防環規範落地）
              │           ├─→ S4 aos status（人讀＋--json）
              │           ├─→ S5 aos check（逐條驗證＋條款編號）        ←可與 S4 平行
              │           ├─→ S6 aos recover 偵測層（唯讀列出可修項）    ←可與 S4／S5 平行
              │           │     └─→ S7 aos recover 動作層（A 族三選一＋B 族三個）
              │           └─→ S9 還債：core/loop 改吃 world 的版面知識（**可選，建議延後**）
              └─→ S8 aos deliver --control（**條款 S1 就定；實作可排最後或延 M4**）
                    │
                    └─→ S10 文件＋code map＋gotchas／verdicts 同步 ←（吃 S4–S9 的實跑輸出）
                          └─→ S11 收尾：摘 planned 標記、驗收總跑、roadmap／SESSION-LOG、封存
```

- **立法先行**：S1 先入法（未實作的條款帶 `(planned, M3)`），程式照條款寫；S11 兌現後摘標。
  任何一步中斷，SPEC 與現實的落差都有標記可查（SPEC「三向標記」規則）。
- **先共用層、後三支命令**：`status`／`check`／`recover` 讀的是同一份版面。**版面知識的
  抄本今天已經有 2 份，M2 之後 3 份**；三支各寫一份會變成 6 份——而 `check` 的存在理由
  就是消滅漂移（layout-and-spec §12），**它不能自己是第 6 份真相**。
- **`check` 與 `status` 共用 `WorldView` 但不共用判斷**：status 報事實、check 報違規，
  兩者的**輸入**是同一個 struct，**輸出**互不引用（spec 裁決 3 的分界要在程式碼裡看得見）。
- **`recover` 拆兩步是刻意的**：S6 只做偵測與列印（唯讀、零風險、可獨立驗收，做完就已
  兌現 spec 驗收 7），S7 才動手；S7 炸掉可以單獨 revert 而不影響 S6。
- **S8 不擋主線**：`deliver --control` 的**條款**在 S1 就定（§29 的門檻今天就得裁），
  **實作**排最後；主線若要延到 M4，把條款標成 `(planned, M4)` 即可（spec 驗收 17 允許）。
- **每步一個檢查點**：每步結束 ctest 全綠（default ＋ merged）＋該步驗證項通過才進下一步；
  每步照 [feature-dev](../../feature-dev/README.md) 各自 commit（含 code map 同步）。

### 本 plan 不碰的（硬性）

- spec 的「明確不做」全部：`agent step`／`emit-context`、注入機制、回合歷史、
  機器可讀 JSON Schema、序列化拷問、B5、記憶體模型、doorbell、任何新子命令、
  `.runi` 不是鎖、**`aggregate` 在 `.runi` 存在時仍發布的根治**、`.runi` 帶 pid、
  `.aos` 第二個軸、`tooljson`／`llms` 的存廢、`core/inst` 改名、格式層與 §C-3 欄位表、
  退出碼不反映子行程成敗、並行度上限、`aos migrate`。
- [keep.md](../../ideas/call-format/keep.md) 保護項：argv 陣列、未知 key 拒絕、無上限、
  三 stream 檔案化——**格式層（`core/inst/src/format*.cpp`、`resolve.cpp`、`inst.cpp`）
  本階段零改動**。
- `core/inst/src/handoff*.cpp` 的**交接邏輯**：彙整／取件／釋放／去重／發布順序
  （§D-4／§D-5／§D-6）**一行不改**。S2b 只把既有的**內部宣告**搬進公開標頭，不改實作。
- `core/loop`（M2 目標）的回合編排、退避、control 掃描——**M3 只讀不改**；唯一例外是
  S9（可選）的純替換，行為零變化。

---

## 二、需主線裁決的清單（S0 一次裁完，動工前）

plan 依 spec 的硬性約束不自行決定新輸出面／新退出碼／新公開 API。以下各附建議案；
「進哪條」指它最後要落在 SPEC 的哪一條（條號提案見第三節）。

### A 組 — 架構與相依（擋 S2／S2b／S3／S9）

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| **裁-A1** | **共用「世界檢視」層與三支命令放哪** | **新開核心小專案 `core/world`**（`PUBLIC_DEPS aos::inst`），`status`／`check`／`recover` 三支子命令都登記在它底下；`core/loop` **這一輪不動** | (b) 三支都塞 `core/inst`；(c) 三支都塞 `core/loop`；(d) 三支各自在 CLI 層自己讀 | (b) 打掉一個**既有的正確設計**——`core/inst` 今天刻意不知道 `.aos/`（版面知識全在 CLI 層與 handoff 的路徑推導裡），塞進去等於讓「機制」那一層長出「診斷與修復政策」，跟 M2 剛做完的分家背道而馳；而且 `handoff.cpp` 已 333 行超門檻。(c) 讓三支**唯讀命令拖著整個回合編排**，方向與「它們存在是因為回合層可能壞了」相反，且違反 §A-7 的判準（它們不是「必須在沒有 inst 可跑的時刻運作」的控制流——它們**任何時刻**都能跑）。(d) 讓版面知識的抄本從 2 份變 5 份，而 `check` 的存在理由就是消滅漂移——**決定性缺點** | §H-1、code-map/build.md |
| **裁-A2** | **`recover` 跟不跟 `status`／`check` 一起** | **跟**（同住 `core/world`，`recover` 的**修復動作**放 world 的 CLI 層、**不進** world 的庫 API——那會讓一個叫「檢視」的層長出寫入面） | 放 `core/inst`（`src/run_recover.cpp`） | 兩案都成立，取決於 **A12**：M2 §A-7 的窮舉表若寫「崩潰**偵測**」（M2 spec 裁決 1 的字面），recover 不在表內 → 可以放任一處；若寫「崩潰**恢復**」（`machine-shape/loop.md` §25 的原文用詞），判準會把 recover 判給 loop。**建議跟 status／check 一起**：三支共用同一份掃描是 spec 裁決 6 的硬要求，分家就得跨小專案共用掃描＝又一次「升公開 API 還是抄第二份」。**放 `core/inst` 的唯一強論點（recover 要用 handoff 的 fs helper）由裁-A3 消解。** | §H-1、§H-4 |
| **裁-A3** | **版面路徑推導與檔案 helper 從哪來** | **從 `core/inst` 升一小組 C++ 公開 API**：`derive_paths`／`derive_header_paths`／`is_delivery_name`／`fsync_dir`／`publish_exclusive`／`read_file`／`write_file`（今天在 `src/handoff_fs.hpp`／`handoff_header.hpp` 這兩個**內部標頭**裡）。`core/world` 用它們 | (b) `core/world` 自己抄一份；(c) 不升，world 只做唯讀、recover 直接呼 POSIX | **方向是死的**：`core/inst` 不能相依 `core/world`（那是反向），而 inst 的 handoff 也需要路徑推導——所以**唯一能讓兩邊共用的位置就是 inst 的公開面**。(b) 就是第 N 份漂移，正是 M3 要消滅的東西。**成本很低**：這是 **C++ API 不是 C ABI**，conventions 只凍結 C ABI（`include/aos/<專案>.h` 的列舉與函式）；純新增、既有測試零改動。代價認列：公開面永久多出七個函式與兩個 struct（`HandoffPaths`／`HeaderPaths`） | §H-1、code-map/inst/library.md |
| **裁-A4** | **防環規範**：`core/world` 能不能解讀回合層語意 | **MUST NOT**：header 的 `result` 與 control 記錄的 `op` **一律原樣以字串傳遞**進 `WorldView`；`status --json` 直接吐出，`check` 依 **SPEC 條文裡的值域表**比對 | 把 `BatchResult`／`to_string` 從 `core/loop` 搬到 `world` 或 `inst` | 那兩份字面表的唯一來源在 `core/loop`（M2 plan 3.1 明寫「四個字串的唯一來源」）。world 一旦要解讀就產生 `world → loop` 的邊 ＝ **相依環**。搬它等於在 M3 翻 M2 剛落地的分層（`BatchResult` 是回合層**算出來的**，語意屬 loop）。而**值域住在條文裡不住在程式碼裡**，正是 §29 第三格「每份規範→validator」的直接應用 | §H-1 |
| **裁-A5** | **`core/loop` 要不要改成相依 `core/world`**（消掉版面常數的重複） | **要，但排 S9、建議延到 M3 之後**：相依圖 `inst ← world ← loop`（無環） | 立刻做（排在 S3 之後）；或永遠不做 | 消掉 M2 風險 11 認列的重複是對的，但它**動的是 M2 剛交付的碼**，而 M3 的主線價值（三支命令）不需要它。**M3-a（不動 loop）已經讓抄本從「會變 6 份」壓回「維持 3 份」**——先止血，再還債 | —（code-map/build.md） |
| **裁-A6** | **C ABI（`<aos/world.h>`）M3 要不要開** | **不開**：只出 C++ 公開標頭與三個 CLI 進入點 | 同步開，補 `LANGUAGE C` 的測試 | 照 M2 裁-2 的理由逐條對過：C ABI 一經釋出就凍結，而 `WorldView` 是 M3 **第一次定形**的結構、最可能改；**一個 C 消費者都沒有**；而且**對外唯讀介面已經有一個更好的**——`aos status --json`，它的相容性由**輸出 schema 版本**管（改起來便宜得多），不是由 ABI 凍結管 | —（記 ideas） |

### B 組 — 輸出面與退出碼（擋 S1／S4／S5）

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| **裁-B1** | **`check` 發現 MUST 違規時的退出碼**（本階段唯一非做不可的裁決） | **新增退出碼 `5` ＝「`aos check` 發現 MUST 違規」**（§D-9 加一列，比照碼 3 寫「只有 `aos check`」），並在 §D-9 的分界句補一個**明寫的例外**：「**驗證器的判決是它的產物**——`check` 的 5 表達判決結果，不是『aos 跑不動』；check 讀不到世界仍然是 1，兩者 MUST 分開」。SHOULD 違規（warning）→ 0；`--warnings-as-errors` 升成 5；`not-applicable` → 0，`--require-git` 升成 5 | (b) 用 1；(c) 一律回 0、判決只走 `--json`＋`jq`；(d) `--strict` 才回非零 | **5 與 1 必須分開，而那正是 check 存在的理由**：CI 要能分辨「**世界不合法**」與「**check 自己爛掉**（打錯路徑、readdir 失敗）」——(b) 讓一個打錯路徑的 job 被讀成「世界壞了」＝**假紅**，比沒有 check 更糟。(c) 概念最純、§D-9 一字不動，但把機械可用性外包給呼叫端（`jq` 不一定在），**若主線選它，要接受「check 的判決不是退出碼」並寫進條款，別讓後人以為是漏的**。(d) 預設不安全（CI 忘了加旗標＝靜默通過）。碼 4 已被 M2 佔，5 是下一個空號 | §D-9、§H-3 |
| **裁-B2** | **`status` 的狀態字集合**（偏離 T5 草案） | **五個封閉字**：`layout-invalid`／`runi`／`ready`／`pending`／`no-work`（判定順序即此）。相對 T5 六字：`running`＋`blocked-runi` **合併成 `runi`**、`unknown-effect` **裁掉**、`bad-delivery` **降成屬性**、**新增 `pending`** | 照 T5 原字 | `running` 與 `blocked-runi` 在今天是**同一個檔案條件**（`.runi` 存在），沒有任何可觀察量把它們分開——給同一個條件兩個名字＝status 在發明證據；而且 §G-7 明文 MUST NOT 另開 pid 檔，**M2 之後也不會變得可判定**。`unknown-effect` 見裁-B3。`bad-delivery` 是**屬性不是狀態**（躺著 `.bad` 的世界仍然可以是任一格）。**`pending` 是實測挖到的缺格**：「有 ready 投遞、還沒彙整」與「真的沒事做」是兩件事（下一次 `exec` 的行為不同），T5 六字會把它誤塞進 `no-work` | §H-2 |
| **裁-B3** | **`unknown-effect` 怎麼處理** | **裁掉判決欄位，換成純事實的 `exit_evidence` 七項計數**（`slots`／`declared`／`unresolved`／`undeclared`／`present`／`stale`／`missing`），mtime 比較只在**人讀版**印一行提示、`--json` 照實給數字。條款明文：**MUST NOT 出現任何叫 `effects_happened` 的欄位** | 保留 `unknown-effect` 狀態字 | 今天判定不出來、M2 之後也判定不出來，三個機械理由：`exit` 欄位**選填**（可以整批零證據）、值**可以是指示詞**（status MUST NOT 求值）、**檔在或不在兩邊都不是證明**〔實測：parent 被 SIGINT 後子行程照樣寫出 `done-*.txt`、`*.exit` 永遠缺〕。加上 §E-2 明說 footprint 不 enforce——**世界裡的作用本來就不是 `.aos/` 看得到的** | §H-2 |
| **裁-B4** | **`--json` 缺席欄位怎麼表示** | **所有宣告過的 key MUST 恆在，缺席用 `null`；陣列缺席用 `[]`，MUST NOT 用 `null`** | 省略 key | ① 與世界自己的慣例一致（§C-8 的 header 已用 `"result":null`〔實測〕），兩種缺席慣例＝第四份漂移。② `jq` 可用性：key 恆在才分得出「**沒有 header**」與「**有 header 但 result 是 null**」。③ schema 可以是靜態的。代價：乾淨世界約 40 行 pretty-print——`--json` 給機器吃，人讀走人讀版 | §H-2、§H-3 |
| **裁-B5** | **`--json` 要不要 `schema_version`** | **要**，MUST 是輸出的第一個 key，v1＝1。並在 §F-2 明說它與**版面版本**、**格式版本**是**三件不同的事**（互不相關、互不遞增、MUST NOT 被同一個決定同時動到；「三個同時是 1 是巧合，不是不變式」） | 不放，靠 `aos --version` | `--json` 是唯一給機器吃的介面，一份輸出可能被存檔、被貼進 issue、被另一支程式半年後讀。沒有版本它就是 layout-and-spec §12 說的**第四份會漂的真相**——而 §29 說 check 存在的理由正是「三份真相收斂」，status 自己再開一份沒版本的真相是自打嘴巴。**順手**：輸出同時鏡射另外兩個版本，一份 JSON 自帶三個版本號 | §F-2、§H-2、§H-3 |
| **裁-B6** | **`status` 的退出碼分界** | **「報告印出來了就是 0」**——含 `layout-invalid`（`.aos/version` 讀不到或不認得）、含 `.runi` 存在、含 `.bad` 存在。只有 status 自己拿不到資料（世界進不去／`.aos` 不存在或不是目錄／讀取失敗）才是 1；用法錯 2；**MUST NOT 用 3／4** | 遇 `.runi` 回 3；遇 `layout-invalid` 回 1 | 分界的操作型定義是「**有沒有印出一份完整的報告**」。`.aos/version` 是 `2` → **世界壞了、status 沒壞**（它讀到了、能印出來）；`.aos` 不存在 → **沒有可報告的內容**。這與 §B-4 不衝突——§B-4 的「MUST 拒絕」拘束的是**要對這個世界動手**的操作〔實測：`exec`／`deliver` 都回 1〕。**這句話要明寫進條款**，否則實作隊會照抄 `run_exec.cpp` 的版本檢查讓 status 回 1。碼 3 的意義是「拒絕啟動」而 status 沒有要啟動什麼；且 `set -e` 的腳本會在最需要讀 JSON 的時刻被 3 打斷 | §D-9、§H-2 |
| **裁-B7** | **`.gitignore` 政策（§E-4）在 check 裡驗到什麼程度** | **三態**：走 **`git check-ignore`**（不自己解析 gitignore），對六個樣本路徑逐一問——四個暫態樣本 MUST 被 ignore、`version`／`turn` MUST NOT 被 ignore，任一不符＝error；**世界不在 git 工作樹裡、或找不到 `git` ＝ `not-applicable`**，**MUST NOT 當成通過、也 MUST NOT 當成違規**；`--require-git` 才升 error | 一律驗、驗不到報 warning；或預設就升 error | 世界不一定是 git repo，規則可能來自 repo 根、`info/exclude`、全域 `core.excludesFile`。**自己 parse 必錯，而且錯的方向是假綠**；`check-ignore` 是 git 自己的答案。預設升 error 會讓玩具世界與 `/tmp` 底下的實驗世界（T5 全部在 `/tmp/aos-t5/`）永遠紅＝這支工具在最常見的用法下沒用 | §E-4、§H-3 |

### C 組 — `recover` 的形狀（擋 S6／S7）

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| **裁-C1** | **`recover` 唯讀模式與 `status` 的分工** | **status 報狀態、recover 報「可修項＋證據＋建議動作」**，兩支共用同一份掃描、呈現層不同。兩條機械分界：① `status` 的 `src/` **MUST NOT** 出現任何 recover 動作旗標名；② `recover --json` 的**每一個 finding MUST 帶 `action` 欄**（一行可複製的指令，或 `"none"` ＋一句為什麼不能自動修） | recover 不做唯讀模式，一律要旗標 | T5 原文明寫「它應**先唯讀列出**……**再要求明示選一個動作**」。而且「有哪些可修項」與「世界是什麼狀態」不是同一個問題（`.bad` 在 status 眼裡是一個計數，在 recover 眼裡是一列待人拍板的處置） | §H-4 |
| **裁-C2** | **`recover` 的退出碼** | 唯讀列完（**不管有沒有可修項**）→ **0**；動作成功（含本來就沒東西要修）→ **0**；**證據不足、拒絕動手** → **1**；用法錯（多餘參數／兩個 A 族旗標同時給／`--adopt` 沒給 RECEIPT／`--fix-turn` 的值不合法）→ **2**；**MUST NOT 回 3／4** | 「有可修項」回新碼 5 | §D-9 的分界是「**aos 自己有沒有把這一步做完**」，不是「世界健不健康」——`aos exec` 子行程全失敗也回 0 是同一條線。「證據不足」**結構上不可能是 2**：§D-9 明定 2 MUST 在碰檔案系統之前判定，而證據不足只有碰過之後才知道。**若主線要「非零＝需要人介入」的巡檢語意，請加在 `status` 而不是 recover**，並在 §D-9 明寫「只有 `aos status`」 | §D-9、§H-4 |
| **裁-C3** | **forensic 副本放哪、叫什麼** | **`.aos/recover.d/<turn>-<utc>-<seq>.d/`**，一次動作一個資料夾，內含 `manifest.json` ＋**原樣保留原檔名**的證物（`inst.json.runi`／`bbb.json.bad`／…）。`<turn>` 讀 `.aos/turn`，讀不到用 `unknown`；`<utc>` ＝ `YYYYMMDDTHHMMSSZ`；`<seq>` 撞名遞增，建目錄走 `mkdir` 的排他語意 | (b) 就地改名加新狀況字（`.old`／`.saved`）；(c) 沿用 `.bad`；(d) 搬到世界外（`$TMPDIR`） | **(a) 不是修憲**：`recover` 是**名字**、`.d` 是 §B-1 既有副檔名、證物**原樣保留原檔名**（連狀況字的用法都沒變，只是換了目錄），也不需要開 verdicts B7 的第二個軸（照 M2 對 `control.tempd/` 的同款論證）。(b) **是修憲**（§B-1 的狀況清單封閉）。(c) 語意污染（`.bad` 的定義是「**內容無效**」，但被放棄的批**內容通常完全有效**——無效的是情境）＋自噬（§D-8 說 recover 清 `.bad`，於是它會去清自己造的）。(d) 違反 §E-1「資料夾整包可搬」——世界搬一次證據就沒了。**子資料夾刻意用 `.d` 結尾**，才不會製造第四個命名例外 | §B-2、§B-5、§H-4 |
| **裁-C4** | **`recover.d/` 進不進 git** | **進**（§E-4 補一條 negation `!.aos/recover.d/**`，且順序 MUST 在暫態 pattern 之後） | 不進（維持 §E-4 字面） | §E-4 排除的是**機器暫態**，forensic 副本是**證據**——它不會被任何程式讀回（`derive_paths()` 永遠推導不到 `recover.d/` 底下的東西），所以不會造成 §E-3 那種「回滾到含 `.runi` 的 commit ＝死鎖世界」。**代價要認**：`*.runi`／`*.bad` 這些 pattern **不分目錄**，不補 negation 副本就進不去。反方：世界整包 clone 過去之後證據就沒了——而「世界在檔案系統上」正是這個設計的賣點 | §E-4 |
| **裁-C5** | **動作旗標集合** | **A 族（作用於 `.runi`，三選一互斥）**：`--replay`（要 `--force`）／`--abandon`／`--adopt RECEIPT`；**B 族（版面殘留，可與 A 族同時給）**：`--tidy`（孤兒 `.temp`）／`--drop-bad`（`.bad`，兌現 §D-8）／`--fix-turn N`；**全域**：`--json`／`--cpu <名>`／`--all`／`--force` | 把 B 族併成一個 `--clean` | `--tidy` 與 `--drop-bad` **分開**是因為 `.bad` 裡是**人可能想看的內容**（無效投遞的原始位元組），孤兒 `.temp` 是機器寫到一半的東西；§D-8 的精神（「crash 之後要人來處理，一以貫之」）要求 `.bad` 的清除是一個獨立的明示動作 | §H-4 |
| **裁-C6** | **`recover` 對「已經有人在修的東西」的界線** | 三條 MUST NOT：① **不重做彙整層的 roll-forward**（分工線＝「**投遞還在 → 彙整層；投遞不在 → recover**」，實測畫出來的）；② **孤兒批 `.temp` MUST NOT roll-forward**，只能列出或 `--tidy`；③ **MUST NOT 補 `.aos/version`**（唯讀 MAY 診斷，任何寫入 MUST 拒絕、退出碼 1） | 讓 recover 也做 roll-forward／補 version | ① 同一個殘留狀態有兩個修復者、兩套判準＝§28 說的「未來損壞的準確位置」；而且彙整層**每一圈都會跑**，recover 是人叫才跑。② 沒有投遞佐證就無法判定它跑過沒有，rename 它＝**重播一個來歷不明的批**。③ §B-4「不猜、不盡力而為」；補 ＝ 偽造證據，把「不認得」補成 1 ＝ 降版 ＝ 沉默損壞。**機械檢查**：`grep 'temp_holds_complete_batch\|roll_forward'` 零筆 | §H-4 |
| **裁-C7** | **`recover` 讀 header `result` 能不能解讀四個字面值** | **MUST NOT 解讀，只原樣轉印＋判斷是不是 `null`** | 可以解讀（把 `machine_failed` 當強證據） | 這是裁-A4 防環規範在 recover 上的應用，同時**保住 M2 驗收條件 5 的 grep**（四個字面值不得出現在 loop 以外）。功能零損失：recover 需要的資訊是「writeback 有沒有發生過」＝「是不是 `null`」，不是「是哪一種結果」 | §H-4 |
| **裁-C8** | **`--fix-turn` 的值** | **N MUST 由人給，recover MUST NOT 自己推算** | 自動推算（例如從 header 或歷史） | **PC 倒退比 PC 壞掉危險**（`machine-shape/loop.md` §27：turn 是歷史編號、兩顆 CPU 的排序基準、去重 epoch 的共同前提）；§B-3 只保證「讀不到視為 0」，沒有任何機制能算出「本來應該是幾」 | §H-4 |
| **裁-C9** | **`recover` 對未消化的**合法**控制記錄**（M2 目標） | **MUST NOT 動**，唯讀標 `pending`（不是殘留） | 當殘留清掉 | §G-7 的 at-least-once 語意明說「躺著」是被預期的；刪它＝**替人取消命令** | §H-4 |

### D 組 — 條款與版面（擋 S1／S5）

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| **裁-D1** | **M3 的條款放哪一區** | **§A-9**（名冊）進 A 區；**§B-5**（ownership table）／**§B-6**（bump 判準）進 B 區；三支命令**新開 H 區「檢視、驗證與修復」** | (b) 全塞 A 與 D；(c) 三支各給一個字母 | 名冊回答「這台機器由哪些**程式**構成」，與 §A-6（哪一層不長新機制）、§A-7（哪些事歸 loop）是同一個家族，讀起來是連續的三段論。ownership：§28 原話就是「**版面規格的內容**是 ownership table」，§B-2 說「有什麼」、§B-5 說「誰能動」。bump 判準獨立成條，是因為 §B-4 規定**讀者的義務**、bump 是**修改者的義務**，而且 §B-4 現行那份「純新增例外清單」會隨每次新增變長（M2 已要加一項）——獨立成條之後那份清單變成 worked example。三支命令**不參與交接**（D 區的主題句是「投遞→彙整→取件」）、**不跑回合**（G 區）、**不是模型**（A 區）；M2 已示範「新字母是免費的」 | — |
| **裁-D2** | **`.aos/turn` 與 `.aos/version` 的位元組格式入不入條款** | **入**：§B-3 補「`turn` ＝ ≥1 位十進位數字 ＋ 恰好一個尾 LF，無正負號，放得進 u64」；§B-4 補「`version` ＝ 位元組全等 `1\n`」 | 不補，check 只驗「解得出整數」 | **實作已經是這樣**〔實測：`5` 無 LF／空檔／`abc`／`-1`／23 位數五種壞法全部讓 `aos exec` 回 1；`version` 的 `1`（無 LF）／` 1 `／`2` 全被拒〕，但**條款沒有法源**——check 的期望值不能憑空生出來。純澄清，不改行為 | §B-3、§B-4 |
| **裁-D3** | **`insts/` 誰建、三支要不要掃** | **`aos init` MUST NOT 建**（不存在＝零顆其他 CPU，是合法狀態）；由外部 CPU 自建；**三支 MUST 掃（存在就掃）**，`status` 以**同構**的形狀報、`check` 的驗證項是 **SHOULD** | `aos init` 順手 `mkdir insts` | 〔實測〕`aos init` 只建 `version`／`turn`／`inst.tempd/`，**沒有任何程式建立或讀取 `insts/`**，但 §B-2 把它列進版面樹——一支「驗版面」的 `check` 不掃版面樹的一整支，是規格與實作的**新一處漂移**。建一個永遠空的目錄沒有意義（git 也不追蹤空目錄）。**位階必須是 SHOULD**：定成 MUST 的話**每一個 `aos init` 的世界上線第一天就紅**（spec 驗收 5 過不了） | §B-2、§H-3 |
| **裁-D4** | **§E-4 的兩個缺口** | 補兩句：① `insts/` 底下的 `<cpu>.json` 與 `<cpu>-head.json` **比照 `inst.json`／`inst-head.json` ＝ MAY**，其下暫態照前段排除；② `recover.d/` 的處置（裁-C4） | 不補 | §E-4 點名了 `*.temp`／`*.runi`／`*.tempd/`／`*.bad`（排除）、`version`／`turn`（納入）、`inst.json`／`inst-head.json`（MAY），**唯獨漏了 `insts/` 底下的同類**。成本一行，不動任何實作 | §E-4 |
| **裁-D5** | **三個命名例外的處置** | **承認為封閉的例外清單寫進 §B-1，不改檔名**：`version`／`turn` ＝ 單值標量檔（暫存器，不是文件）、`insts/` ＝ 命名空間目錄（不是 `.d` 這個資料格式）；**MUST NOT 再增加** | (b) 改名 ＋ bump 版面版本到 2 ＋ 提供 migration；(c) 擴充 §B-1 讓「標量檔」「命名空間」成為**規則**而非例外 | (b) 是 bump 判準的**教科書反例**：改 `version` 的檔名會讓每一個既有世界依 §B-4 立刻變成非法世界——拿「全世界都要 migrate」換「命名一致」不划算。(c) 不差（主線若偏好「規則優於清單」可選），但把封閉清單變成**開放規則**會稀釋 §B-1「狀況是封閉清單」那條的力量（下一個人會問「那 `.aos/pid` 算不算標量檔」），而且**只有三個實例，規則比例外貴** | §B-1 |
| **裁-D6** | **bump 判準的形式** | **三問任一為是就 MUST bump**（舊 aos 會把合法新版面判成非法或反過來／會按舊語意動一條語意已變的既有路徑／它的正常運作會破壞新版面的不變式）；**純新增的充要條件四條**（舊 aos 不讀／不寫／**它的動作最多只讓新機制降級、MUST NOT 產生新的錯誤狀態**／缺席時新 aos 有定義好的「視為預設值」行為）；`turn`／`inst-head.json`／`control.tempd/` 三個既裁的純新增**逐條過帳寫進條文當 worked example** | 只寫一句「不相容才 bump」 | 「降級」那條（(b′)）**必須單獨列**：`inst-head.json` 其實擦邊——舊 aos 發布批次時不寫 header，新 aos 下一輪去重找不到可比對的 id → **可能重複執行一批**。那不是「不一致」，是**保證降級成 M1 之前的行為**。(b′) 就是用來合法地把它留在「純新增」那一格，並且順便解釋了為什麼 | §B-6 |
| **裁-D7** | **`check` 讀哪個版本欄位** | 條款寫「**`check` MUST 依 `.aos/version` 決定套用哪一版的版面規則集；v1 是目前唯一的一版**；讀到 `1` 以外的值 MUST 依 §B-4 報告不認得」 | 只寫「MUST 驗 `.aos/version` 等於 1」 | **語意預留是零成本的**：今天的實作照樣是一個相等比較，差別只在條文說了「那是規則集的分派點」——**一行程式碼都不用多**。未來加 v2 是實作不是修憲；只寫「驗＝1」的話加 v2 就得改條文＝修憲＝還要等使用者點頭。條文要明寫「v1 是目前唯一的一版」，把「存在多版分派機制」的預期壓住 | §H-3 |
| **裁-D8** | **`inst-head.json` 的雙 writer 處置**（實測挖到的真實損壞窗口） | **§C-8 補一句**：回合層寫 `result` 之前 **MUST** 先讀回 header 的 `id` 與自己這一批比對，**不符 MUST NOT 寫、只記 warning**（`decode_header_id()` 已存在，成本近零）。並明說這**不是**「退避要先讀 header」——§G-2 已規定退避用回合層自己算的結果，讀 `id` 只為確認「這份 header 還是不是我的」。**同時：優先回報 M2 實作隊順手收掉** | (b) 根治：`aggregate_instructions()` 在 `.runi` 存在時 MUST NOT 發布；(c) 把 `result` 搬出 header | 窗口是**實際存在**的：`aggregate` 只 `lstat(inst.json)`、**不看 `.runi`**，而順序是 aggregate 先、claim 後 → 第二支 `aos exec` 會在批 N 還在跑時發布批 N+1 並覆蓋批 N 的 header，然後才退 3。今天的後果是 header 與 `.runi` 失聯（直接打到 status）；M2 之後是 `result` 蓋到錯的 header 上。(b) 才是根治，但**動的是 M1 剛凍結的彙整邏輯**、且會改變「投遞在回合跑的時候可以先排隊」這個現行行為——**M3 不做，記進 verdicts D 表與「`.runi` 不是鎖」一起排**。(c) 與 §C-8 既裁直接衝突 | §C-8、verdicts D 表 |
| **裁-D9** | **兩條「刻意不驗」要不要寫進條款** | **要**：① **check MUST NOT 宣稱驗過 header `id` 與批內容的對應**——§D-6 的 id 是對**排序後（投遞檔名＋內容）**的摘要，**不是批位元組的摘要**，投遞刪掉之後就算不回來，**機械上不可驗**；② **`.bad` 的內容 MUST NOT 驗**（`.bad` 的定義就是「內容無效」，驗它是同義反覆），check 只計數並列名 | 不寫（讓實作隊自己判斷） | 不寫的話下一個人一定會加一條**假的**驗證（「驗一下 id 對不對」），而它要嘛永遠通過、要嘛永遠失敗。**照實寫進條款，防後人加它** | §H-3 |
| **裁-D10** | header 的**未知 key** 與 **`id` 的字面形狀** 要不要入條款 | ① header 未知 key → check 先報 **warning**（§C-5 的「未知 key MUST 拒絕」字面只拘束 inst schema）；② `id` **MUST** 非空字串、**SHOULD** 16 位小寫 hex | ① 升 MUST；② 只驗非空 | ① 順著 keep.md「未知 key 拒絕而非忽略」的方向，但 §C-5 沒有法源涵蓋 header，升 MUST 是修憲——**列成提案不自行認定**。② §D-6 定了演算法（FNV-1a 16 位 hex）但 §C-8 沒定字面形狀 | §C-8、§H-3 |
| **裁-D11** | **`inst.json` 與 `inst.json.runi` 不得同時存在**要不要升 MUST | **升 MUST**（§D-7 或 §D-4 補一句），check 判 error | 維持 SHOULD | 〔實測〕這個狀態是**現行實作自己造出來的**（裁-D8 的同一個窗口），而它的後果很重：**人工 `mv .runi inst.json` 會靜默吃掉剛彙整的那一批**。升 MUST 之後 check 會抓到它，`recover --replay` 也有法源拒絕。**但注意**：在裁-D8 的根治（(b) 案）做掉之前，這個狀態仍可能自然出現——所以升 MUST 等於承認「出現它＝有一次不該發生的併發」，這是正確的訊號 | §D-7、§H-3 |

### E 組 — 流程與文件（擋 S1／S10）

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| **裁-E1** | **`deliver --control` 的實作排哪** | **條款在 S1 就定（帶 `(planned, M3)`）；實作排 S8、最後做**。主線若要延到 M4，把標記改成 `(planned, M4)` | 條款與實作都延到 M4 | §29 的門檻**今天就得裁**（不然 M3 之後每次有人想加旗標都要重問一次）；實作不擋三支主線。**代價認列**：沒有 `--control` 的話，M2 完成定義第三條（「Ctrl-C 之外有停在回合邊界的辦法」）對使用者而言是「照文件抄三行 shell」，而 M2 驗收條件 3 要求把那段輸出貼進 `docs/usage.md`——貼出來就是在教使用者手刻 | §D-3 |
| **裁-E2** | **要不要順手裁掉「已知未決 #1」（SIGINT 斷點續跑）** | **裁掉**：`recover` 落地後那個現場**有辦法收拾**了，矛盾的解法是**承認沒有斷點續跑**——§D-7 補一句「崩潰留下的 `.runi` 沒有批次內斷點續跑；處置 MUST 由人透過 `aos recover` 明示選擇」，roadmap 那句歷史驗收條件一併改寫 | 原樣保留（M2 也沒動它） | #1 從 M0 掛到現在，卡的正是「沒有安全的恢復命令」——T5 記錄第 4 條原話：「**不是違反規格，而是缺少能安全操作的 recovery 規格與命令**」。M3 補的就是那支命令，**這是它唯一該被裁掉的時機**。但它動到 roadmap 的歷史驗收條件，主線裁 | §D-7、已知未決 #1（刪） |
| **裁-E3** | **`docs/subprojects.md`／`add-subproject.md` 要不要補「跨小專案一律 `PUBLIC_DEPS`」** | **補**（M3 順手，各一句） | 只改 code map（M2 的計畫） | 那兩份的相依三層判準說「只有 `.cpp` 用到 → `PRIVATE_DEPS`」，與 M2 裁-14（跨小專案必須 `PUBLIC_DEPS`，否則合併版長出 `NEEDED libaos_inst.so.0`）**表面衝突**；M2 只打算把這句加進 `code-map/build.md`——**而那兩份才是下一個人開新小專案時會讀的**。M3 正好是第三個開新小專案的人 | —（docs） |

**擋關係**：裁-A1／A2／A3／A4／A6 擋 S2／S2b／S3；裁-A5 擋 S9；裁-B1 擋 S1 與 S5；
裁-B2／B3／B4／B5／B6 擋 S4；裁-B7／D3／D7／D9／D10／D11 擋 S5；
裁-C1～C9 擋 S6／S7；裁-D1～D8 擋 S1；裁-E1 擋 S8；裁-E2／E3 擋 S1／S10。
（依 build-cycle 常備規則 3：沒裁完也可動工，碰到那行就停下來裁。）

---

## 三、SPEC 條款起草清單（**保留給主線**，S1）

plan 不起草條文，只列「需要哪些條款、規定什麼、來源在哪」。位階（MUST／SHOULD）與措辭
由主線定，每條附來源；未實作前帶 `(planned, M3)`，S11 摘標。

### A 區 機器模型（接在 §A-8 之後）

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§A-9 程式名冊與封閉判準** | 判準（一件事需要子命令的充要條件＝必須由外部方執行、且它必須運作的時刻沒有可用的回合承載它，＝「做不成 inst」，§A-7 的外推）＋**五格窮舉表**（世界的存在／推進本身／外部方執行的協定步驟／靜態狀態的 inspector＋repairer／規範的 validator）＋**六支名冊**（`init`／`exec`／`deliver`／`status`／`recover`／`check`）＋**衝突時表優先**；**三條範圍句**（封閉的是會讀寫 `.aos/` 的子命令；`tooljson`／`llms` 進封閉的豁免清單、MUST NOT 增長、MUST NOT 被引為先例；**名冊是子命令名冊不是小專案名冊**——`loop` 是 `exec` 的實作，**新增小專案不是修憲**）；**修憲門檻四條**；代價認列（`deliver`／`status`／`check` 三支的「有邊緣」反例照實寫進來源註，別假裝判準是乾淨的） | layout-and-spec §29；M2 §A-7 的「判準＋窮舉表」手法；`aos --help` 實跑；spec 裁決 1 |

### B 區 命名與版面（修補 ＋ 新增兩條）

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§B-1 修補（命名例外）** | 加一段**封閉的例外清單**：`version`／`turn` ＝ 單值標量檔（暫存器，§B-3 已把 `turn` 稱為 PC）、`insts/` ＝ 命名空間目錄（不是 `.d` 這個資料格式）。**MUST NOT 再增加**；新增 `.aos/` 項目 MUST 落在命名標準內，除非同一次修憲加進本清單 | M2 plan §B-2 修補列；裁-D5 |
| **§B-2 修補** | ① 版面樹加 `recover.d/`（forensic 副本，`recover` 首次用到時才建、`aos init` **不建**）；② `insts/` 那列註明「**`aos init` MUST NOT 建立它**，由外部 CPU 自建；不存在＝零顆其他 CPU、是合法狀態；`status`／`check`／`recover` 遇缺 MUST 視為空、MUST NOT 報錯」；③ 加一句指向 §B-5 | 裁-C3／裁-D3；`run_init.cpp` 實測 |
| **§B-5 版面 ownership table**（新） | `.aos/` 每條路徑一列：**誰建／誰寫（唯一 writer）／誰讀／誰刪／進不進 git（指 §E-4）／對應條款**；角色詞彙封閉（`init`／彙整層／回合層／投遞者／控制者／人／`status`／`check`／`recover`／外部 CPU）；**「建立者」與「writer」是兩件事**；鐵律「每條路徑 MUST 有唯一 writer」；**已知唯一雙 writer ＝ `inst-head.json`**（處置見 §C-8 修補）；**雙刪除者兩處**（`*.bad`、`*.runi`）是刻意且冪等的；`inst.json` 那列 MUST 註明「唯一性靠 check-then-act 維持，見 verdicts D 表」（照實寫）；`.aos/version` 那列 MUST 註明「**未來的雙 writer、現在沒有擁有者**——aos MUST NOT 自動升級版面，升級由人執行；升級工具是否進名冊留待第一次真的要 bump 時走修憲程序」；並加一句「§B-5 不解決 verdicts B7（第二個軸）——ownership 解決正確性、第二個軸解決分類」 | layout-and-spec §28；現況 `handoff.cpp`／`handoff_fs.cpp`／`handoff_header.cpp`／`run_init.cpp` 實測 |
| **§B-6 版面版本的 bump 判準**（新） | 操作型定義（舊 aos 會不會**做錯事**，不只是看不懂）＋**三問**＋**純新增的四個充要條件**（含「最多只讓新機制降級、MUST NOT 產生新的錯誤狀態」）＋三個 worked example（`turn`／`inst-head.json`／`control.tempd/`）；並附一個教學例：**`.runi` 若要帶 pid ＝ MUST bump 到 2**（舊 aos 的 release 會 unlink 掉別人還在用的租約）——**但 M3 不做這件事** | layout-and-spec §16；verdicts B10；裁-D6 |
| **§B-3／§B-4 修補** | §B-3 補 `turn` 的位元組格式；§B-4 補 `version` 的位元組格式、加一句「本條規定**讀者的義務**，什麼時候該 bump 見 §B-6」（現行的純新增例外清單改為 §B-6 的 worked example，條文不必再逐項增長）、加**診斷豁免**（`status`／`check`／`recover` 的**唯讀面** MUST 能在 `version` 缺席或不認得時繼續運作並報告該事實、MUST NOT 據此拒絕啟動；**`recover` 的寫入動作 MUST 拒絕**）——**這是修憲，主線點頭才動** | 裁-D2；spec 裁決 4 |

### H 區 檢視、驗證與修復——**新開**（裁-D1）

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§H-1 三支的共用語意**（開區條款） | 三支 MUST 從**同一份**版面知識讀取（同一組路徑常數、同一份 `version`／`turn` 判定、同一份收件匣分類、同一份 header 讀取），**MUST NOT** 各自實作版面知識；三支 **MUST NOT** 推進回合、**MUST NOT** 觸發彙整；三支 **MUST** 掃 `insts/`（存在就掃）；**共用層 MUST NOT 解讀回合層語意**——header 的 `result` 與 control 記錄的 `op` 一律**原樣以字串傳遞**，值域住在條文裡（§G-2／§G-7），不住在程式碼裡；三支**不是**回合層的一部分（§A-7 的判準推不到它們——它們正好在**沒有 loop 在跑**的時候才有用） | spec 裁決 3／裁決 6；裁-A1／A4；conventions 單向分層 |
| **§H-2 `status`：唯讀投影** | **MUST NOT 改世界**（不建檔、不建目錄含 `control.tempd/`、不把不合法命名改成 `.bad`、不動 `.bad`、**不求值指示詞**）；**五個封閉狀態字**與判定順序；MUST 報告的欄位清單；`--json` 的**固定形狀**（key 恆在、缺席 `null`／`[]`）與 `schema_version`；**MUST NOT 宣稱它知道外部作用發生了沒**——只報 `exit_evidence` 的七項機械計數，**MUST NOT 出現任何叫 `effects_happened` 的欄位**（照實寫進條款，否則下一個人會加它）；**`inst-head.json` 描述的可能不是 `.runi` 裡那一批**（§C-8 修補的同一個窗口），status 的措辭 MUST 容忍這個組合；退出碼（裁-B6） | T5 subcommand-specs；裁-B2／B3／B4／B5／B6 |
| **§H-3 `check`：對 SPEC 驗版面與 schema** | **MUST NOT 改世界、MUST NOT 修（沒有 `--fix`）、MUST NOT 驗 repo、MUST NOT 驗 SPEC 本身、MUST NOT 驗 `.aos/` 以外的世界內容（§E-2 的 footprint 是 SHOULD 且不 enforce）、MUST NOT 對筆數／位元組／深度設上限（§C-7）、MUST NOT 執行 inst 或求值指示詞**；**每筆違規 MUST 帶 SPEC 條款編號**＋穩定違規碼＋路徑＋實際值＋期望值；MUST 違規（error）與 SHOULD 違規（warning）MUST 分開報；驗證項清單與各自位階（含 `insts/`／`control.tempd/` **必須是 SHOULD**）；**`.gitignore` 的三態**（裁-B7）；**依 `.aos/version` 決定套哪一版規則集，v1 是目前唯一的一版**（裁-D7）；**兩條刻意不驗**（裁-D9）；退出碼（裁-B1） | layout-and-spec §12／§29；verdicts B11；裁-B1／B7／D7／D9 |
| **§H-4 `recover`：偵測與修復** | 不帶動作旗標 **MUST 唯讀**（列出可修項＋證據＋**建議動作**）；**MUST NOT 自動重播批次、MUST NOT 猜子行程有沒有跑過**；**偵測／動作矩陣**（每列：偵測條件／代表什麼事故／動作與 fsync 順序／要不要 `--force`／不做什麼）；**與彙整層的分工線**（裁-C6①）；**孤兒批 `.temp` MUST NOT roll-forward**（裁-C6②）；**MUST NOT 補 `.aos/version`**（裁-C6③）；**MUST NOT 解讀 header `result` 的四個值**（裁-C7）；forensic 副本規則（裁-C3，**零新狀況字**）；**`.bad` 的清理在此兌現**（§D-8 從 M1 就指名 M3）；**MUST NOT 動未消化的合法控制記錄**（裁-C9）；退出碼與 **MUST NOT 回 3／4**（裁-C2）；**MUST** 在文件與動作模式的 stderr 寫明前提「**動手前先確定沒有 `aos exec` 在跑這個世界**」——`.runi` 不是鎖、且**沒有任何辨識活體的資訊**（無 pid／時間戳／心跳），recover **MUST NOT 假裝自己有互斥** | T5 subcommand-specs；§D-7／§D-8；gotchas handoff 節；裁-C1～C9 |

### C／D／E／F 的點狀修補

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§C-8 修補** | `result` 有**兩個 writer**（彙整層寫 `null`、回合層 writeback 覆寫）；**回合層寫 `result` 之前 MUST 先讀回 header 的 `id` 與自己這一批比對，不符 MUST NOT 寫、只記 warning**；明說這**不是**「退避要先讀 header」（§G-2 的兩件事分開寫）。另補 `id` 的字面形狀（裁-D10②） | 裁-D8／D10；§28；`handoff.cpp`／`run_exec.cpp` 實測 |
| **§D-3 修補（`deliver --control`）** | `--control` 投 `.aos/control.tempd/`；**驗證範圍 MUST 只驗「恰好一個 key `op`、值為字串的 JSON 物件」，MUST NOT 判動詞合法性**（動詞歸回合層 §G-7）；stdout **MUST** 是 `{"delivery":…,"target":"control.tempd"}`、**MUST NOT 帶 `count`**；其餘（唯一檔名、先 `.temp` 後 rename、排他發布、inbox 不存在報錯不自動建）比照 §D-2／§D-3 | spec 裁決 2；裁-E1 |
| **§D-7 修補** | ① `inst.json` 與 `inst.json.runi` **MUST NOT 同時存在**（裁-D11）；② 若裁-E2 通過：補「崩潰留下的 `.runi` **沒有**批次內斷點續跑；處置 MUST 由人透過 `aos recover` 明示選擇」 | 裁-D11／E2；T5 record 第 4 條 |
| **§D-8 修補** | 把 `(M3)` 改成規範的三向標記，指向 §H-4 的對應動作；M3 落地後摘標 | §D-8 現行文字；SPEC 開頭的三向標記 |
| **§D-9 修補（退出碼）** | ① 第 3 列涵蓋欄由「只有 `aos exec`」明確化為「**只有 `aos exec`（含 `--loop`）**」；② 補 `status`／`check`／`recover` 的涵蓋描述（裁-B6／B1／C2）；③ 若裁-B1 通過，加一列 **5 ＝ `aos check` 發現 MUST 違規**（只有 `aos check`）＋分界句的明寫例外「驗證器的判決是它的產物」。**0／1／2／3／4 的既有語意一字不改** | 裁-B1／B6／C2 |
| **§E-4 修補** | ① `insts/` 底下的 `<cpu>.json`／`<cpu>-head.json` ＝ **MAY**，其下暫態照前段排除；② `recover.d/` 的處置（裁-C4：若「進 git」，補 negation 並註明順序） | 裁-D4／C4 |
| **§F-2 修補（三個版本數字）** | 整段釘死：**版面版本／格式版本／輸出 schema 版本**是三件不同的事，互不相關、互不遞增、**MUST NOT 被同一個決定同時動到**；附四欄表（住哪／說的是什麼／誰寫誰讀／何時遞增）＋「**三個同時是 1 是巧合，不是不變式**」 | 裁-B5；verdicts B10 |

**S1 順手處理**：若裁-E2 通過，「已知未決 **#1**」在 §D-7 與 §H-4 落地後消掉（S11 執行）。
**M3 開工前的現況**：`grep -n "planned, M3" docs/SPEC.md` 目前零筆；M2 的
`(planned, M2)` 與已知未決 #4 應已在 M2 的 S11 清完——**S0 要先確認**（假設 A10／A11）。

---

## 四、設計提案（給實作隊的骨架，措辭與細節仍以 S1 的條款為準）

### 4.1 `core/world` 的分層與公開面（裁-A1／A2／A3）

```text
core/world/
    include/aos/world.hpp     公開：WorldView／scan／三支用得到的型別
    src/paths.cpp / .hpp      版面路徑常數與推導（吃 core/inst 升上來的 helper）
    src/view.cpp              掃描 .aos/ → WorldView（唯讀，不建任何東西）
    src/status.cpp            投影成人讀輸出與 --json
    src/check.cpp             逐條驗證 → 違規清單（帶條款編號）
    src/recover_scan.cpp      偵測矩陣 → 可修項＋證據＋建議動作（唯讀）
    src/recover_act.cpp       動作執行＋forensic 副本（CLI 層，不進庫的公開 API）
    src/run.cpp               argv ＋ aos_status_cli_main／aos_check_cli_main／
                              aos_recover_cli_main 三個進入點
    tests/  docs/world.md  CMakeLists.txt
```

- **內部分層**：`paths ← view ← {status, check, recover_scan} ← recover_act ← run`。
- **跨小專案相依**：`PUBLIC_DEPS aos::inst`（要用 `read_all`／`InstState` 驗投遞內容
  ——§C-6 是唯一的拒絕條件表，check **MUST NOT** 自己長第二套 schema；也要用 S2b
  升上來的路徑 helper）。**MUST NOT** 相依 `aos::loop`（裁-A4 的防環規範）。
- **`recover` 的寫入面刻意留在 CLI 層**：庫的公開 API 只出唯讀的 `scan`，一個叫
  「檢視」的層不該長出寫入面（裁-A2）。

### 4.2 `WorldView` 的形狀（提案，簽名由 S3 定案、主線過目）

```cpp
// core/world/include/aos/world.hpp（提案）
namespace aos::world {

enum class SlotState { Absent, Ready, Publishing, Running };  // 無／inst.json／.temp／.runi

struct FileView   { bool present=false; std::string path; long long bytes=0; double mtime=0; };
struct ParseView  { bool ok=false; std::string state; long long record=-1, count=-1; };
struct HeaderView { FileView file; bool readable=false; long long version=-1;
                    std::string id, origin, result;      // result 空字串＝JSON null
                    std::vector<std::string> unknown_keys; };
struct InboxView  { bool present=false; std::string path;
                    std::vector<std::string> ready, temp, bad, ignored; };
struct CpuView    { std::string name; bool core=false; SlotState slot=SlotState::Absent;
                    FileView batch, batch_temp, running, header_temp;
                    ParseView batch_parse, running_parse;
                    HeaderView header; InboxView inbox; };
struct WorldView  { bool aos_present=false;
                    bool version_present=false, version_recognized=false;
                    std::string version_raw;
                    bool turn_present=false, turn_valid=false;
                    unsigned long long turn=0; std::string turn_error;
                    CpuView core; std::vector<CpuView> others;
                    InboxView control; bool recover_dir_present=false;
                    std::vector<std::string> unknown_entries; };

AOS_API bool scan(const char *folder, WorldView &view, int &error);  // 唯讀，絕不建東西

}  // namespace aos::world
```

- **`scan` 對「壞掉」不回 false**：讀不到 `version`、`turn` 是垃圾、`.aos` 不存在——
  這些全是 `WorldView` 的**內容**，不是掃描失敗（spec 裁決 4 的診斷豁免在程式碼裡的樣子）。
  只有「連 `<folder>` 都進不去」才回 false。
- **`unknown_entries` 是 check 的主要武器**：版面樹是封閉的，`.aos/` 底下出現規範不認得
  的名字＝漂移的第一現場（`.bad` 當年就是這樣被發現的）。
- **`result` 用空字串代表 JSON `null`**，而且**只轉印不解讀**（裁-A4／C7）。
- **`turn_present` 與 `turn_valid` 分開**：§B-3 只說「**讀不到**（舊世界）MUST 視為 0」，
  **沒有**說「讀到壞內容也視為 0」——`run_exec.cpp` 的 `parse_turn` 就是這麼分的。

### 4.3 `status --json` 的形狀（提案）

固定形狀、key 恆在、缺席 `null`／`[]`，頂層第一個 key 是 `schema_version`：

```json
{
  "schema_version": 1,
  "world": "/abs/path",
  "state": "runi",
  "layout": {"version_raw":"1","version":1,"recognized":true,
             "turn":7,"turn_present":true,"turn_error":null},
  "cpus": [{"name":"inst","core":true,"state":"runi",
            "batch":null,"batch_temp":null,
            "running":{"path":".aos/inst.json.runi","bytes":120,"mtime":1.0,
                       "parse":{"ok":true,"state":"Ok","record":null,"count":2}},
            "header":{"path":".aos/inst-head.json","bytes":78,"mtime":1.0,
                      "readable":true,"version":1,"id":"c5e5a48a000b7dc3",
                      "origin":"aggregated","result":null,"unknown_keys":[]},
            "header_temp":null,
            "inbox":{"path":".aos/inst.tempd","present":true,
                     "ready":[],"temp":[],"bad":[],"ignored":[],
                     "counts":{"ready":0,"temp":0,"bad":0,"ignored":0}},
            "exit_evidence":{"slots":2,"declared":2,"unresolved":0,"undeclared":0,
                             "present":0,"stale":0,"missing":2}}],
  "others": [],
  "control": {"path":".aos/control.tempd","present":false,
              "ready":[],"temp":[],"bad":[],"ignored":[],
              "counts":{"ready":0,"temp":0,"bad":0,"ignored":0},"ops":[]},
  "notes": []
}
```

- **狀態字判定順序**：`layout-invalid` → `runi` → `ready` → `pending` → `no-work`。
- **`inbox.ignored[]`** 是實測挖到最有價值的一欄：`name.part.json`／`noext`／
  `x.json.runi`／子目錄今天全被**靜默忽略**、零 warning、那份工作永遠不會跑。
- **陣列一律字典序（`LC_ALL=C`）**——與 §D-4 的彙整順序同一個排序，讓 status 的順序
  就是 exec 的順序；但 §D-4 說投遞者 MUST NOT 假設順序，所以這是**方便不是承諾**，
  條文要寫明。**MUST NOT 對陣列長度設上限**（§C-7）。
- **`notes[]` 是人讀提示**（例如 mtime 啟發式的但書），**MUST NOT 被機器當判決用**。

### 4.4 `check` 的違規記錄與驗證項（提案）

違規碼格式 **`AOS-<區><號>-<序>`**（條款編號直接嵌在碼裡 ⇒ `grep -c 'AOS-B1'` 就能統計
「命名標準違規有幾筆」——**這就是「三份真相收斂的機械形式」**）：

```json
{"code":"AOS-B3-02","clause":"§B-3","level":"MUST","severity":"error",
 "path":".aos/turn","message":"turn 不是十進位整數加 LF",
 "actual":"abc\\n","expected":"^[0-9]+\\n$","truncated":false}
```

驗證項清單（**位階欄是本表最重要的一欄**——定錯位階，spec 驗收 5 當天就過不了）：

| 碼 | 檢查 | 條款 | 位階 |
|---|---|---|---|
| `AOS-B2-01` | `.aos/` 存在且是目錄 | §B-2 | MUST |
| `AOS-B4-01` / `-02` | `version` 存在且讀得到 ／ 內容是認得的版面版本 | §B-4 §F-2 | MUST |
| `AOS-B3-01` / `-02` | `turn` 存在（**SHOULD**——缺檔＝合法舊世界）／ 檔存在時格式合法 | §B-3 | SHOULD／MUST |
| `AOS-B2-02` | `inst.tempd/` 存在且是目錄 | §B-2 | **SHOULD**〔實測：刪掉它 `aos exec` 仍回 0，只有 `deliver` 回 1〕 |
| `AOS-B1-01` | inbox 每個項目命名合法且是普通檔 | §B-1 §D-4 | MUST（**最有價值的一條**，見 4.3） |
| `AOS-B1-02` / `-03` | 整棵 `.aos/` 無封閉清單外的狀況字 ／ inbox 裡沒有 `.runi` | §B-1 | MUST |
| `AOS-C2-01` / `AOS-C6-01` | 每份 ready 投遞是完整 JSON 文件 ／ 過**唯一 parser**（帶 `InstState` 與出錯筆序） | §C-2 §C-6 | MUST |
| `AOS-D3-01` | ready 投遞的位元組是 canonical | §D-3 §C-4 | **SHOULD**（§D-3 的 MUST 拘束的是 `aos deliver` 發布的位元組，手寫投遞不受拘束） |
| `AOS-C2-02` | `inst.json` 存在時過 parser | §C-2 §C-6 | MUST |
| `AOS-C8-01`…`-05` | header 合法 JSON 且四欄齊 ／ `version` ＝認得的格式版本 ／ `id` 非空 ／ `origin` ∈ {`aggregated`,`direct`} ／ `result` ∈ 五態 | §C-8 §F-1 ＋§G-2 (M2 目標) | MUST |
| `AOS-C5-01` | header 沒有未知 key | §C-5（哲學）§C-8 | **SHOULD**（裁-D10①） |
| `AOS-B2-03` | 每顆 CPU 的 header 檔名是 `<名>-head.json` | §B-2 §C-8 | MUST |
| `AOS-D1-01` | `inst.json` 與 `.runi` 不同時存在 | §D-7 | **MUST**（裁-D11） |
| `AOS-D5-01` / `-02` / `AOS-D2-01` | 沒有殘留的 `inst.json.temp` ／ `inst-head.json.temp` ／ `inst.tempd/*.json.temp` | §D-5 §D-2 | SHOULD |
| `AOS-B2-04` / `-05` | `insts/` 存在時遵循同一套命名 ／ `control.tempd/` 存在 | §B-2 ＋§G-7 (M2 目標) | **SHOULD**（**定成 MUST 的話乾淨世界當天就紅**） |
| `AOS-G7-01`…`-03` | control 記錄＝恰好一個 key 的 `{"op":…}` ／ `op` ∈ v1 封閉動詞集 ／ **`.aos/control.json` 不存在** | §G-7 (M2 目標) | MUST |
| `AOS-E4-01` | `.gitignore` 政策 | §E-4 | MUST，但**三態**（裁-B7） |

**兩條刻意不驗**（裁-D9，要寫進條款）：header `id` 與批內容的對應（**機械上不可驗**
——§D-6 的 id 是「投遞名＋內容」的摘要，投遞刪掉後就算不回來）；`.bad` 的內容
（同義反覆，且清理歸 §D-8）。

### 4.5 `recover` 的偵測／動作矩陣（骨架；完整矩陣 26 列在 S6 展開）

| 家族 | 偵測條件（純檔案存在性＋內容） | 動作 | 不做什麼 |
|---|---|---|---|
| **`.runi` 家族** | `.runi` 存在（× 批可否解析 × header `result` 是否 `null` × `inst.json` 是否也存在） | A 族三選一 | **MUST NOT** 遞增 `turn`（§B-3 是「release **成功後**」遞增）；`--adopt` **MUST NOT** 寫 header `result`（四值的定義是「回合層算出來的」，加第五值＝修憲）；`inst.json` 落點被佔時 `--replay` **MUST 拒絕**（退 1）——合併會造出一個**從未存在過的批**（§A-1／§A-3） |
| **彙整殘留**（§D-5 的五個崩潰點） | 批 `.temp` × header `.temp` × header 正式檔 的組合，**再乘上「投遞還在不在」** | 投遞還在 → **列出並說明「下一圈 `aos exec` 會自癒」**；投遞不在 → `--tidy` | **MUST NOT** roll-forward（裁-C6①②）。另：§D-6 有一條會**真的丟批**的路徑（header id 相符＋批 `.temp` 零長度 → `aos exec` 清投遞並丟棄這批），recover 只能**報「發生過」**，救不回——照實寫 |
| **投遞匣殘留** | 孤兒 `<x>.json.temp` ／ `.bad` ／ 不合法命名 | `--tidy` ／ `--drop-bad` ／ **只列出**（不合法命名是 check 的違規，recover MUST NOT 動——`.aos/` 沒有「只有 aos 能放東西」的規定） | — |
| **版面級** | `turn` 壞掉 ／ `version` 缺席或不認得 ／ 不認得的檔名 | `--fix-turn N`（N 由人給） ／ **拒絕寫入** ／ 標 `unknown` 只列出 | 裁-C6③；自動清理不認得的檔＝**刪別人的資料** |
| **control**（M2 目標） | 孤兒 `.temp` ／ `.bad` ／ **未消化的合法記錄** | `--tidy` ／ `--drop-bad` ／ **MUST NOT 動**（標 `pending`） | 裁-C9 |

### 4.6 `deliver --control` 的形狀（提案，裁-E1）

```text
aos deliver --control <動詞> [folder]
```

- 產生的位元組 ＝ `{"op":"<動詞>"}` ＋ LF（canonical）。
- **只驗「恰好一個 key `op`、值為字串」**，**不驗動詞**（spec 裁決 2 的三項限定之一
  ——這正是「`core/inst` 不需要知道 loop 的動詞集合」的機械保證，
  `grep -rn '"stop"' core/inst/` **零筆**就是它的驗收）。
- 檔名／`.temp`→rename／排他發布／inbox 不存在報錯，全部走既有的 `deliver` 路徑。
- **`run_deliver.cpp` 今天 249 行**，加分支會逼近 conventions 的 300 行門檻
  ——順手拆 `run_deliver_control.cpp`。

---

## 五、逐步實作

### S0 M2 假設核對 ＋ 裁決清點（主線，一小時級）

- 逐條打勾第零節 A1–A16；**任一條不符就停下來改本 plan**。特別是 **A9**（writeback
  順序）、**A10**（區與編號）、**A12**（「崩潰偵測」vs「崩潰恢復」）——這三條會動到
  規格本身而不只是實作。
- 過一遍第二節 36 項，記入 `wf/workflows/ideas/verdicts.md`（A 表）＋對應 ideas 檔
  （`machine-shape/layout-and-spec.md`、`core-layering.md`）。
- **順手回報 M2 實作隊**：裁-D8 的 header `id` 比對（若 M2 還在施工，成本近零、
  它收掉最省事）。
- **驗**：A1–A16 各有結論；36 項各有結論；verdicts diff 可讀。

### S1 SPEC 條款起草（**主線**，AI 不得自行修憲）

- 照第三節起草：§A-9、§B-5／§B-6（新）、§B-1／§B-2／§B-3／§B-4／§C-8／§D-3／§D-7／
  §D-8／§D-9／§E-4／§F-2（修補）、H 區 §H-1…§H-4（新）。未實作的帶 `(planned, M3)`。
- **驗**：`grep -n "planned, M3" docs/SPEC.md` 有輸出（＝法先立了）；新條款每條有位階詞
  與來源；`grep -o '§[A-H]-[0-9]*' docs/SPEC.md | sort | uniq -d` **零筆**（編號沒重用）。

### S2 `core/world` 骨架（**機械，可轉派 sonnet**）

- 照 [add-subproject](../../add-subproject.md) Step 1–5：建目錄、公開標頭（**每個函式
  標 `AOS_API`**）、`CMakeLists.txt`（抄 `core/inst/CMakeLists.txt`）、
  `core/CMakeLists.txt` 加 `add_subdirectory(world)`。**根 `CMakeLists.txt` 與 `app/`
  一行都不動。**
- 三支子命令先登記但只印 usage。
- **驗**：`ctest --preset default` 全綠（多一個 target）；`aos --help` 出現三支；
  `cmake --preset merged` configure＋build 成功；
  **`readelf -d build/merged/lib/libaos.so | grep NEEDED` MUST NOT 出現 `libaos_*.so`**；
  外部消費測試（`env -u VCPKG_ROOT`，add-subproject Step 6）通過；
  `grep -n 'aos::loop' core/world/CMakeLists.txt` **零筆**。

### S2b `core/inst` 升一小組版面 helper 為公開 API（**判斷型，Opus**；純新增）

- 把 `src/handoff_fs.hpp`／`handoff_header.hpp` 裡的 `derive_paths`／
  `derive_header_paths`／`is_delivery_name`／`fsync_dir`／`publish_exclusive`／
  `read_file`／`write_file`（＋`HandoffPaths`／`HeaderPaths` 兩個 struct）搬進
  `include/aos/inst.hpp`，**標 `AOS_API`**，實作**一行不改**、命名空間視需要調整。
- **不動 C ABI**（`inst.h` 零改動，`capi.cpp` 的 `static_assert` 不用碰）。
- **驗**：既有測試**一個都不用改**仍全綠（＝純新增的證據）；外部消費測試通過
  （漏標 `AOS_API` 只有從 repo 外才看得出來——gotchas 有這一條）；
  `code-map/inst/library.md` 同步。

### S3 世界檢視層 `WorldView`（**判斷型，Opus**）

- `src/paths.cpp`＋`src/view.cpp`：把 `.aos/` 掃成 `WorldView`（4.2 的形狀）。
- **唯讀是硬性**：整層 **MUST NOT** 出現 `mkdir`／`open(O_CREAT)`／`rename`／`unlink`。
- **防環規範落地**：`result`／`op` 只轉印不解讀。
- **驗**：每一種版面狀態各一個欄位斷言測試（含 `turn` 五種壞法、`version` 缺席／`2`、
  inbox 四類、崩潰現場）；
  `grep -n 'mkdir\|O_CREAT\|rename(\|unlink(' core/world/src/paths.cpp core/world/src/view.cpp`
  **零筆**；`grep -rn 'aos/loop\|aos::loop' core/world/` **零筆**。

### S4 `aos status`（**判斷型，Opus**）

- `src/status.cpp`＋`run.cpp` 的 argv；人讀輸出 ＋ `--json`（4.3 的形狀）。
- **驗**：spec 驗收 2／3；五個狀態字各一案；`jq -e` 逐欄位；
  `jq -S 'paths'` 的 key 集合在所有場景是同一個超集；
  `jq -e 'tostring | test("effect|did_run") | not'`；
  `grep -n 'running\|blocked-runi\|unknown-effect\|bad-delivery' core/world/src/status.cpp`
  **零筆**；`aos status --bogus` 回 2＋usage；`.runi` 存在時回 **0**；
  `version` ＝ `2` 時回 **0** 且 `state=="layout-invalid"`；`.aos` 不存在時回 **1**。

### S5 `aos check`（**判斷型，Opus**；可與 S4 平行）

- `src/check.cpp`：4.4 的驗證項，每筆違規帶條款編號。
- 投遞與批的驗證 **MUST** 走 `aos::read_all`（§C-6 是唯一的拒絕條件表）。
- `.gitignore` 走 `git check-ignore`（三態），**不自己解析**。
- **驗**：spec 驗收 4／5／6；每個違規碼一個「造違規→抓到」的案子；
  `jq -e '[.violations[].clause] | all(test("^§[A-H]-[0-9]+$"))'`；
  每個 `clause` 都能 `grep` 到 `docs/SPEC.md`；乾淨 init 零違規、退出碼 0；
  `turn` 壞掉 → 退出碼 **5**（裁-B1）；`inst.json.temp` 殘留 → warning ＋退出碼 **0**；
  `--warnings-as-errors` 讓它變 5；非 git 世界 → `not_applicable[]`、**不在**
  `violations[]`、退出碼 0，`--require-git` 後 5；`.aos` 進不去 → **1**（不是 5）；
  同一世界跑兩次 `--json` 的 `diff` 零輸出；
  `grep -n 'fix\|repair\|rename(\|unlink(' core/world/src/check.cpp` 零筆寫入呼叫；
  `grep -n 'max_files\|MAX_\|limit' core/world/src/check.cpp` 零筆。
- **S5 的第一個測試就寫「`version` ＝ `2`」**：check 該報**一筆**「不認得的版面版本」，
  **不是**把整棵樹的每個差異都報成違規（風險 5）。

### S6 `aos recover` 偵測層（**判斷型，Opus**；可與 S4／S5 平行）

- `src/recover_scan.cpp`：4.5 的矩陣展開成 26 列；唯讀列印＋`--json`；
  **每個 finding 帶 `action` 欄**。
- **驗**：spec 驗收 7；每一種殘留形態各一個「列得出來」的案子；唯讀快照測試；
  `grep 'temp_holds_complete_batch\|roll_forward'` **零筆**；
  `grep -n -- "--replay\|--abandon\|--adopt\|--tidy\|--drop-bad\|--fix-turn"
  core/world/src/status.cpp` **零筆**（裁-C1 的分界）。

### S7 `aos recover` 動作層（**判斷型，Opus**；最危險的一步）

- `src/recover_act.cpp`：A 族三選一互斥（`--replay` 要 `--force`）＋B 族三個；
  forensic 副本（裁-C3）；證據不足預設停住。
- **每個動作先建 forensic 副本、fsync，再動原檔。**
- **驗**：spec 驗收 8／9；每個動作一個測試；
  **`--replay` 之外的動作 MUST NOT 讓任何 inst 被執行**（用會寫檔的 inst 反證）；
  `grep 'return 3\|return 4'` 零筆且 `.runi` 存在時回 0；
  forensic 副本建不起來時原檔未動、退 1；
  `grep -E '\.(old|bak|orig|saved|backup)'` 零筆；
  副本目錄名 match `^([0-9]+|unknown)-[0-9]{8}T[0-9]{6}Z-[0-9]+\.d$`；
  `grep -rn '"ok"\|"partial"\|"machine_failed"' core/world/src/recover_*.cpp` **零筆**
  （裁-C7，保住 M2 驗收 5 的精神）。

### S8 `aos deliver --control`（**判斷型，Opus**；可延後或延 M4）

- `core/inst/src/run_deliver.cpp` 加 argv 分支（4.6）；超過門檻就拆
  `run_deliver_control.cpp`。
- **驗**：spec 驗收 12；`grep -rn '"stop"\|aos/world\|aos::world' core/inst/` **零筆**
  （沒有反向相依、沒有動詞清單）；不是「恰好一個 key `op`」的輸入退 1。

### S9 還債：`core/loop` 改吃 `core/world` 的版面知識（**可選，建議延後**；機械）

- 純替換、行為零變化。`core/loop` 加 `PUBLIC_DEPS aos::world`（`inst ← world ← loop`）。
- **驗**：ctest 全綠且**測試一個都不用改**；`grep -rn 'kAosDir' core/ | wc -l` 明顯下降；
  merged 的 `readelf` 守門仍過；CMake 無環。

### S10 文件＋導航同步（**機械為主，可轉派 sonnet**；usage.md 的命令要實跑）

- `docs/usage.md`：三支命令各一節（**貼實跑輸出**）、退出碼表更新、`--help` 重貼、
  `deliver --control` 範例（若 S8 做了）。
- `docs/aos-folder.md`：版面說明加 `recover.d/`，導流到 §B-5／§B-6。
- `docs/subprojects.md`／`add-subproject.md`：補「跨小專案一律 `PUBLIC_DEPS`」（裁-E3）。
- `code-map/`：多一冊 `world.md`、總圖加一列、`build.md` 反映 `add_subdirectory(world)`；
  `code-map/inst/library.md` 加 S2b 升上來的公開 API；`inst/cli.md`／`tests.md` 反映 S8。
- `wf/workflows/common/gotchas.md`：`.bad` 那條過帳（「歸人或 `aos recover`」→ 已有命令）；
  `.runi` 不是鎖那條補一句「`recover` 也沒有互斥，動手前先確定沒有 loop 在跑」；
  **新增一條**：`aggregate` 不看 `.runi` 造成的 header 失聯窗口（裁-D8 的根治留在這裡）。
- `wf/workflows/ideas/verdicts.md`：B9／B11（**部分**）／B12 的 §28・§29／D 表的 `.bad`
  各自過帳；A 表加 M3 的裁決；**D 表新增一條**「`aggregate` 在 `.runi` 存在時仍發布」。
- `wf/workflows/ideas/machine-shape/layout-and-spec.md`：§12／§17／§28／§29 加裁決註記。
- **驗**：文件內每條命令逐條實跑核對；code map diff 與新增檔一一對應。

### S11 收尾（主線）

- 摘 `(planned, M3)`（延後實作的改標 `(planned, M4)`）；若裁-E2 通過，消掉已知未決 #1。
- 驗收總跑（spec 的 18 條逐條）。
- `wf/workflows/roadmap.md`：M3 標 ✅ ＋結果段；**留一行**把三個症狀併起來
  （回合歷史／`agent step`＋`emit-context`／「崩潰後只有一個 `.runi`」＝**系統 inst
  注入機制**這一個缺件的三個症狀，MUST 一起排）；並註記 `check` 只讓「三份真相收斂」
  收斂了一半（機器可讀 schema 仍缺）。
- `wf/SESSION-LOG.md` 更新；項目整夾移進 `build-cycle/archive/m3-roster/`。

---

## 六、動哪些檔（總表，對照 code map 現況；行數為實測現值）

| 檔（repo 相對路徑） | 動作 | 步 | code map 落點 |
|---|---|---|---|
| `core/world/CMakeLists.txt` | **新** | S2 | build.md（新列） |
| `core/world/include/aos/world.hpp` | **新**：`WorldView`／`scan`／三支的型別 | S2/S3 | world.md（新冊） |
| `core/world/src/paths.cpp`／`.hpp` | **新**：版面路徑常數與推導 | S3 | world.md |
| `core/world/src/view.cpp` | **新**：掃描（唯讀） | S3 | world.md |
| `core/world/src/status.cpp` | **新** | S4 | world.md |
| `core/world/src/check.cpp` | **新**（驗證項多，破 300 行就按區拆 `check_layout.cpp`／`check_schema.cpp`） | S5 | world.md |
| `core/world/src/recover_scan.cpp` | **新**：偵測矩陣（唯讀） | S6 | world.md |
| `core/world/src/recover_act.cpp` | **新**：動作＋forensic 副本 | S7 | world.md |
| `core/world/src/run.cpp`／`run.hpp` | **新**：argv ＋ 三個 `aos_*_cli_main` | S2–S7 | world.md |
| `core/world/tests/test_world_support.hpp`／`test_view.cpp`／`test_status.cpp`／`test_check.cpp`／`test_recover_scan.cpp`／`test_recover_act.cpp` | **新** | S3–S7 | world.md |
| `core/world/docs/world.md` | **新** | S10 | —（同 inst/docs，不進 code map） |
| `core/CMakeLists.txt` | 改：`add_subdirectory(world)` 一行 | S2 | build.md |
| `core/inst/include/aos/inst.hpp` (215) | 改：**純新增**七個版面 helper ＋兩個 struct，標 `AOS_API` | S2b | inst/library.md |
| `core/inst/src/handoff_fs.hpp` (56)／`handoff_header.hpp` (44) | 改：搬走宣告，實作不動 | S2b | inst/library.md |
| `core/inst/src/run_deliver.cpp` (249) | 改：`--control` argv 分支 | S8 | inst/cli.md |
| `core/inst/src/run_deliver_control.cpp` | **新**（S8 頂到 300 行門檻時才拆） | S8 | inst/cli.md（新列） |
| `core/inst/tests/test_run_deliver.cpp` (270) | 改：`--control` 的案子 | S8 | inst/tests.md |
| `core/loop/CMakeLists.txt`／`src/*.cpp` (M2 目標) | 改：加 `PUBLIC_DEPS aos::world`＋版面常數純替換（**僅裁-A5 通過且不延後時**） | S9 | build.md／loop.md／world.md |
| `docs/SPEC.md` | 改：§A-9／§B-5／§B-6 新增；§B-1／§B-2／§B-3／§B-4／§C-8／§D-3／§D-7／§D-8／§D-9／§E-4／§F-2 修補；H 區新開；摘標（**主線**） | S1/S11 | — |
| `docs/usage.md` | 改：三支命令＋退出碼表＋`--help` 重貼＋`--control` 範例 | S10 | — |
| `docs/aos-folder.md` | 改：版面說明加 `recover.d/`，導流新條款 | S10 | — |
| `docs/subprojects.md`／`wf/workflows/add-subproject.md` | 改：補「跨小專案一律 `PUBLIC_DEPS`」 | S10 | — |
| `wf/workflows/common/code-map/world.md` | **新**（再多一冊） | S10 | — |
| `wf/workflows/common/code-map.md`／`code-map/build.md`／`code-map/inst/{library,cli,tests}.md` | 改 | S2–S10 | — |
| `wf/workflows/common/gotchas.md` | 改：兩條過帳＋一條新增 | S10 | — |
| `wf/workflows/ideas/verdicts.md`／`machine-shape/layout-and-spec.md`／`core-layering.md` | 改 | S0/S10 | — |
| `wf/workflows/roadmap.md`／`wf/SESSION-LOG.md` | 改：收尾 | S11 | — |
| 根 `CMakeLists.txt`、`app/`、`cmake/AosSubproject.cmake`、根 `.gitignore` | **不動** | — | — |

**明確不動**：`core/inst/src/` 的 `format*.cpp`／`resolve.cpp`／`inst.cpp`／`exec.cpp`／
`spawn_prep.*`／`wait.*`／`capi*.cpp`／`run.cpp`／`run_init.cpp`／`handoff*.cpp` 的**實作**
（S2b 只搬宣告）；`core/loop/src/` 的回合編排與退避（S9 的純替換除外）；
`core/tooljson/`、`core/llms/`。

---

## 七、風險與退路

1. **`core/world` 又踩一次 `PUBLIC_DEPS` 地雷**（M2 裁-14／風險 2 的原班人馬）。
   根 `CMakeLists.txt` 只把 `aos::<小專案>` 從 **public** 相依清單濾掉，private 那份原樣
   灌進 `target_link_libraries(... PRIVATE ...)`，寫成 PRIVATE 會讓 `libaos.so` 長出
   `NEEDED libaos_inst.so.0`——單檔部署破功。
   守門：S2 起每一步都跑 `readelf -d build/merged/lib/libaos.so | grep NEEDED`。
   退路：改回 `PUBLIC_DEPS`（一行）。**順帶**：裁-E3 要求把這句補進 `subprojects.md`
   ／`add-subproject.md`，免得第四個開小專案的人再踩一次。

2. **相依環**。`world → inst`、（S9 之後）`loop → world`。若有人手滑讓 `world → loop`
   （最可能的入口：想解讀 header `result` 的四值或 control 的動詞集合），CMake 會直接
   `strongly connected component (cycle)` configure 失敗——**那是好事，讓它失敗**。
   守門：`grep -rn 'aos/loop\|aos::loop' core/world/` **零筆**；
   `grep -rn 'aos/world\|aos::world' core/inst/` **零筆**。
   對策就是裁-A4 的防環規範（**值域住在條文裡，不住在程式碼裡**）。

3. **「唯讀」很容易被無聲破壞**：任何一次 `open(O_CREAT)`、一次 `mkdir` 補目錄、一次
   順手的 `std::filesystem::create_directories`。最容易破的場景恰好是**壞掉的世界**
   （「`control.tempd/` 不在？順手建一下」）。守門：S3 的 grep（零筆）＋每支命令對
   **十種世界**各跑一次指紋比對（spec 驗收 2 的 T1）＋ `chmod -R a-w` 的 T2。
   > **對照組**：〔實測〕今天的 `aos exec` **回 3 的那一次也改了世界**——`.runi` 在時
   > 它仍先彙整發布並覆蓋 `inst-head.json`，然後才撞 Busy。**這正是為什麼唯讀要寫成
   > 條款而不是靠實作自覺。**

4. **`recover` 與正在跑的 loop 撞車**。`.runi` 不是鎖，且**沒有任何辨識活體的資訊**，
   所以 `recover --replay` 有可能在 loop 正跑那一批時把 `.runi` 搬回 `inst.json`。
   **M3 不解決這個**（要解得先修 claim 的 check-then-act）；對策是**條款＋訊息**：
   §H-4 要求寫明前提，動作模式在 stderr 印一行警告。**照實認列，不要假裝有互斥。**

5. **`check` 對「未來的版面版本」誤判**。若 `.aos/version` 是 `2`，check 該報
   **一筆**「不認得的版面版本」，而不是把整棵樹的每個差異都報成幾十筆假違規。
   守門：S5 的第一個測試就是這個場景（裁-D7 的規則集語意在程式碼裡的樣子）。

6. **測試 helper 的落差**（假設 A5）。M3 的測試要「鋪一個世界、投一批、跑一回合、
   然後檢查」——跑回合的 helper 在 M2 之後住 `core/loop/tests/`，`core/world/tests/`
   **看不到**（跨小專案不能 include 對方的 `src/`／`tests/`）。
   **對策：M3 的測試不跑回合，直接手鋪殘留狀態**——`check`／`recover` 測的本來就是
   **檔案樹**，不是回合；`status` 也一樣。少數真的需要「跑過一回合」的案子就
   `fork`／`exec` 一次 `build/bin/aos`（測試已經在 build 樹裡）。
   代價：`core/world/tests/test_world_support.hpp` 自己鋪 `.aos/`（四行 mkdir＋寫檔），
   **版面若變兩處要改**——寫進 code map 的 world 分冊。

7. **`check` 變成「一個順手的 lint」**。它的立法目的是 verdicts B11 的結案手段，
   不是風格檢查。守門：**每筆違規必須帶條款編號**（spec 驗收 4）——帶不出編號的
   檢查項就不該存在，這條規則本身就擋住了功能膨脹。

8. **`check` 的驗證項位階定錯，乾淨世界當天就紅**。`insts/`（沒人建）、
   `control.tempd/`（舊世界沒有）、`inst.tempd/`（刪掉它 `aos exec` 仍回 0）
   **三條都必須是 SHOULD**，而且 SHOULD 違規**不改退出碼**。
   守門：spec 驗收 5（`aos init` 後零 error **零 warning**）——**這條要在寫程式之前確認**。

9. **`status --json` 的欄位一旦釋出就等於介面**。`schema_version`（裁-B5）是保險，
   但改欄位仍會打壞下游腳本。守門：欄位表寫進 §H-2 條款（改欄位＝修憲），
   S4 的測試寫成**逐欄位斷言**而不是「有輸出就好」。

10. **`recover` 的 forensic 副本把世界撐爆**。`recover.d/` 只增不減、沒有清理機制。
    M3 **刻意不加**自動清理（「crash 之後要人來處理」一以貫之），但文件要寫明
    「這個目錄由人清」。若裁-C4 選「進 git」，還要注意 `.gitignore` 的 negation
    **順序 MUST 在暫態 pattern 之後**，否則不生效。

11. **三支命令的行數會超門檻**。`check.cpp`（20+ 驗證項）與 `recover_*.cpp`
    （26 列矩陣 × 六個動作）最可能先破 300。對策：check 按 SPEC 分區拆
    （`check_layout.cpp`／`check_schema.cpp`）、recover 拆偵測與動作兩檔——後者正好
    對應「唯讀／動手」的分界。

12. **S2b 漏標 `AOS_API`**。gotchas 有這一條：**編譯過、`#include` 也過，連結時才找不到
    符號，而且通常是外部使用者先撞到**（repo 內的測試若連的是 OBJECT library 就繞過了
    可見度）。守門：S2b 的外部消費測試（`env -u VCPKG_ROOT`）**不可省**。

13. **`aos --help` 的清單順序又要變一次**（M2 已動過一次）。spec 驗收 1／9 的比對腳本
    **比集合、不比順序**；`docs/usage.md` 貼的輸出 S10 要重貼。

14. **§D-9 加碼的前置**。M3 動 §D-9 之前，M2 的第 4 列必須已經在（假設 A11）。
    若 M2 因故沒加 4，M3 的 5 會出現跳號——那不是錯，但要在條款註記，別讓下一個人
    以為漏了一列。

15. **裁-D8 的窗口在 M3 期間仍然存在**。M3 只做 header `id` 比對（治標），根治
    （`aggregate` 在 `.runi` 存在時不發布）留給後面的階段。所以 M3 的 `status` 與
    `check` **必須容忍**「header 描述的不是 `.runi` 裡那一批」這個組合——
    `AOS-C8-*` 系列 **MUST NOT** 因此判違規（那是併發的痕跡，不是版面違規）。

---

## 八、外包切分（誰做哪步、驗收怎麼收）

判斷型給 Opus 實作 agent，機械型由 Opus 轉派 sonnet；**SPEC 條款起草與一切
`docs/SPEC.md` 修改保留給主線**（AI 不得自行修憲，條款清單見第三節）。

| 步 | 給誰 | 性質 | 驗收怎麼收 |
|---|---|---|---|
| S0、S1、S11 | **主線** | 假設核對／裁決／修憲 | A1–A16 逐條打勾；36 項各有結論；verdicts＋SPEC diff 自查 |
| S2 | Opus→**sonnet** | 機械（抄 `core/inst` 的 CMake 範本） | ctest 全綠＋`--help` 出現三支＋merged 的 `readelf` 守門＋外部消費測試 |
| S2b | **Opus** | 判斷型（公開面一旦加就難收） | 既有測試**一個都不用改**仍全綠＋外部消費測試＋主線過目公開面清單 |
| S3 | **Opus** | 判斷型（`WorldView` 的形狀、唯讀是硬性、防環） | 每種版面狀態一個欄位斷言＋三組 grep 零筆＋簽名主線過目 |
| S4 | **Opus** | 判斷型（`--json` 是介面，一釋出就凍結） | spec 驗收 2／3；逐欄位斷言；五個狀態字各一案；三個退出碼場景 |
| S5 | **Opus** | 判斷型（位階定錯就全紅、條款編號要對得上） | spec 驗收 4／5／6；`clause` 都能 grep 到 SPEC；乾淨世界零 error 零 warning |
| S6 | **Opus** | 判斷型（矩陣的完整性） | spec 驗收 7；每種殘留一個「列得出來」的案子；分界 grep |
| S7 | **Opus** | 判斷型（動作的安全性，**最危險的一步**） | spec 驗收 8／9；`--replay` 之外不執行任何 inst 的反證測試**必在**；forensic 先建的注入測試 |
| S8 | **Opus**（拆檔可轉 sonnet） | 判斷型（相依方向） | spec 驗收 12＋`grep -rn '"stop"\|aos/world' core/inst/` 零筆 |
| S9 | Opus→**sonnet** | 機械（純替換） | ctest 全綠且**測試一個都不用改**＋`kAosDir` 計數下降＋merged 守門 |
| S10 | Opus→**sonnet**（usage.md 實跑部分 Opus 把關） | 機械＋鐵律驗證 | 文件內命令逐條實跑核對；code map 分冊 diff 對表 |

任務書共通條款（發包時附上）：本 plan 對應步驟全文 ＋ spec「明確不做」 ＋ keep.md 保護項
＋ conventions 的分層鐵律／300 行門檻／C ABI 規則 ＋ 「每步 ctest（default **與** merged）
綠才交件、code map 同 commit」 ＋ 風險節的第 1～4 條與第 8、12 條（那六條是會真的炸的）。
背景等待期間不輪詢。

---

## 九、驗收對照（spec 18 條 ↔ plan 步驟）

| spec 驗收 | 對應步驟 | 機械檢查 |
|---|---|---|
| 1. 三支存在且被登記 | S2／S10 | `aos --help` 集合 ＝ §A-9 窮舉表 ∪ 豁免清單；三支對認不得的選項回 2＋usage |
| 2. 唯讀四層（T1 指紋／T2 唯讀權限／T3 strace／T4 grep） | S3／S4／S5 | 十種世界各跑一次 `diff` 零輸出；`chmod -R a-w` 後輸出逐位元組相同 |
| 3. `status --json` 穩定 schema | S4 | 逐欄位斷言＋`jq -S 'paths'` 超集＋無 effect 欄位＋狀態字 grep |
| 4. `check` 每筆違規帶條款編號且編號存在 | S5 | `jq` 形式斷言 ＋ 逐一 `grep docs/SPEC.md` |
| 5. `check` 對乾淨世界零違規 | S5 | init 後、跑完一回合後各一次，零 error 零 warning、退出碼 0 |
| 6. 每個違規碼一個測試＋順序確定＋無寫入無上限 | S5 | 逐碼測試名 ＋ 兩次 `--json` 的 `diff` ＋ 兩組 grep |
| 7. `recover` 預設唯讀且每個 finding 帶 `action` | S6 | 快照測試 ＋ JSON 斷言 |
| 8. 每種殘留一個測試＋五條硬 grep | S7 | 逐列測試名 ＋ `return 3/4`／`roll_forward`／狀況字／forensic 注入／反證測試 |
| 9. `.bad` 清理兌現 §D-8 | S7 | 造 `.bad` → `--drop-bad` → 進副本並消失；彙整層仍不自動刪（回歸） |
| 10. status／recover 分界 | S6 | `status` 的 `src/` 無 recover 旗標名 |
| 11. ownership table 路徑集合完整 | S1／S10 | 煙霧腳本 `find .aos` 三種世界聯集 ⊆ §B-5 的路徑集合 |
| 12. `deliver --control` 落地 | S8 | 檔名／位元組／stdout 無 `count`／loop 停在邊界回 0／`core/inst` 無動詞 grep |
| 13. 無相依環＋合併版乾淨 | S2／S9 | 兩個 preset configure 成功 ＋ `readelf -d` ＋ 兩組 grep |
| 14. ctest 全綠、merged 可建、外部消費測試 | 每步 | 三條指令 |
| 15. code map 同步 | S2–S10 | 新冊 ＋ 總圖列 ＋ `build.md` 的 `add_subdirectory()` ＋ inst 分冊三處 |
| 16. usage.md 更新且實跑 | S10 | 逐條重跑核對；`--help` 重貼 |
| 17. `(planned, M3)` 零筆＋編號沒重用 | S1／S11 | 兩個 grep |
| 18. 既裁沒被翻 | 每步 | `"version":1` 仍在；格式層三檔零改動；§C-3 一字未改；四值字面在 `core/inst`／`core/world` 零筆 |
