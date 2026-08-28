# M1 loop 側立法＋便宜機械件 — 實作 plan

← [spec](spec.md)｜[build-cycle](../README.md)｜[SPEC](../../../../docs/SPEC.md)｜[code map](../../common/code-map.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 roadmap 衝刺模式，見 spec 開頭）。
本 plan 只講「怎麼」；「什麼」以 [spec.md](spec.md) 為準。spec 的「明確不做」一律出範圍。

**驗證一律**：從 repo 根目錄、在 WSL 跑
`cmake --build --preset default && ctest --preset default`。
手動煙霧測試用建出來的執行檔 `./build/bin/aos`（default preset 的 binaryDir 是
`build/`；若 bin 位置不同以實際產出為準）。

---

## 零、總覽與相依圖

```text
S0 裁決清點（主線）
  └─→ S1 SPEC B／D／E 條款起草（主線；帶 planned 標記入法）
        ├─→ S2 handoff_fs 基礎件（fsync／排他發布／唯一檔名）   ←可與 S1 平行動工，
        │     ├─→ S3 彙整改造：header sidecar＋批 id 去重＋崩潰窗口   但吃 S0 的裁決
        │     └─→ S4 aos deliver（庫層＋CLI）
        │           └─→ S5 deliver C ABI
        ├─→ S6 .aos/turn（init 建立＋release 後遞增）   ←與 S3／S4 平行
        └─→ S7 fsync 掃尾（exec.cpp／capi_io.cpp）     ←等 S3／S4／S6 落地後收尾
              └─→ S8 文件＋code map＋gotchas／verdicts 更新
                    └─→ S9 收尾：SPEC 摘 planned 標記、驗收清單總跑、roadmap／SESSION-LOG
```

- **立法先行**：S1 先入法（未實作的條款帶 `(planned, M1)`），程式照條款寫；S9 兌現後摘標。
  這樣任何一步中斷，SPEC 與現實的落差都有標記可查（SPEC「三向標記」規則）。
- **可平行**：S3、S4、S6 互相獨立（不同檔），可並行；S5 等 S4；S7 收尾掃全域；S8/S9 串行。
- **每步一個檢查點**：每步結束時 ctest 全綠＋該步驗證項通過，才進下一步；每步照
  [feature-dev](../../feature-dev/README.md) 各自 commit（含 code map 同步）。

### 本 plan 不碰的（硬性）

- spec「明確不做」：exec_loop 搬遷、loop 讀 header、`timeout_ms` 搬遷、節流／退避
  （`run_loop.cpp` 的 `--loop 0` 與 `did_work` 兩條 gotchas **不修**，留 M2）、
  `status`／`recover`／`check`、§25／§26／§29、SIGINT 續跑（已知未決 #1 原樣保留）。
- [keep.md](../../ideas/call-format/keep.md) 保護項：argv 陣列、未知 key 拒絕、無上限、
  三 stream 檔案化——**格式層（`core/inst/src/format*.cpp`、`resolve.cpp`、`inst.cpp`）
  本階段零改動**，deliver 的驗證直接呼叫既有 `read_all`／`write_all`（唯一 parser）。
- `.runi` 不是鎖（TOCTOU）那條 gotcha：不在 spec 的 bug 清單內（spec 只點名 fsync 與
  彙整崩潰窗口），**不動**。
- repo 根目錄的 `.gitignore`：維持現狀（整包 `.aos/` 不進）。E 區的 `.gitignore` 政策
  是**給世界（world）的規範**，本 repo 是原始碼 repo、不是世界，兩者無關。

---

## 一、需主線裁決的清單（S0 一次裁完，動工前）

plan 依 spec 硬性約束不自行決定新欄位／新命名／新輸出面。以下各附建議案；
裁定記入 verdicts＋對應 SPEC 條款（由主線起草，見 S1 條款清單）：

| # | 問題 | 建議案 | 進哪條 |
|---|---|---|---|
| 裁-1 | 投遞檔名確切格式（spec 裁決 4 只給方向） | `<pid>-<seq>.json`，`seq` 為行程內單調計數（atomic）；發布用排他 rename 兜底 pid 重用。維持 `<名字>.<副檔名>.<狀況>` 標準（名字＝`<pid>-<seq>`，無點）。 | D 區（投遞檔名） |
| 裁-2 | `aos deliver` 的 machine-readable 輸出格式 | stdout 單行 JSON：`{"delivery":"<檔名>","count":N,"target":"<inbox 相對路徑>"}`（T5 要求 id／count／target 三項）。 | D 區（deliver） |
| 裁-3 | header sidecar 確切檔名（§C-8 說「隨 B 區收編定案」） | 照 §C-8 建議：`<名字>-head.json`，核心 CPU 即 `.aos/inst-head.json`。 | B 區（版面）＋§C-8 摘註 |
| 裁-4 | 批 `id` 的形式 | **確定性摘要**：對「排序後的（投遞檔名＋內容）」算 64-bit FNV-1a，寫成 16 位 hex 字串。它同時就是去重依據（§C-8「id＝去重的依據」）；若改用隨機 id，去重需另存投遞名冊＝manifest，與「manifest 留 v2」的既裁衝突。 | D 區（彙整／去重） |
| 裁-5 | 舊世界沒有 `.aos/turn` 時 exec 的語意 | 視為 `0`、於首次遞增時建立（不 bump `.aos/version`、不拒絕）。理由：turn 是純新增，拒絕會把所有既有世界變磚；版面版本仍為 1。 | B 區（turn） |
| 裁-6 | 去重兜底的**覆蓋範圍**怎麼寫進條款 | 保證的是：**同一組投遞（同名同內容、恰好整組）在發布後殘留於 inbox 時，不會再發布第二次**（即 spec 驗收 3 的場景，含「全部 unlink 失敗」）。**不保證**：部分 unlink 失敗的殘留混入新投遞後的重複（殘留子集摘要不同）。條款照實寫，不誇大。 | D 區（彙整／去重） |
| 裁-7 | deliver 發布的位元組：canonical（`read_all`→`write_all` 往返後）還是原文 | canonical。與彙整的「每份投遞完整往返格式層一次」（§C-4）同一條約束，行為一致、指示詞保原樣。 | D 區（deliver） |

裁-1／裁-2／裁-7 擋 S4；裁-3／裁-4／裁-6 擋 S3；裁-5 擋 S6。S2 不被任何裁決擋。
（依 build-cycle 常備規則 3：沒裁完也可動工，碰到那行就停下來裁。）

---

## 二、SPEC B／D／E 區條款起草清單（**保留給主線**，S1）

plan 不起草條文，只列「各區需要哪些條款、來源在哪」。位階（MUST/SHOULD）與措辭由主線定，
每條附來源；未實作前帶 `(planned, M1)`，S9 摘標。

### B 命名與版面（來源主體：`docs/aos-folder.md` 二／三／九）

| 條款 | 來源 |
|---|---|
| 命名標準 `<名字>.<副檔名>.<狀況>`；副檔名表（`.json`／`.d`／`.tempd`）；狀況表（`.temp`／`.runi`／**`.bad` 正名收編**）；「不加第三個字表達同一件事」 | aos-folder 二；verdicts D 表（`.bad` 是標準外第三種狀況→正名） |
| `.aos/` 版面樹：`version`、`inst.json`（核心 CPU 特權位）、`inst.json.temp`／`.runi`、`inst.tempd/`、`insts/`；**新增 `turn` 與 `inst-head.json`**（裁-3） | aos-folder 三；spec 成品 1 |
| `.aos/turn`：init 建為 `0`；loop（CLI 回合層）持有；release 成功時遞增；讀不到的語意（裁-5） | spec 本階段裁決 1（§27 三小裁決，已裁）；verdicts |
| 版面版本完整條款（F-2 收攏）：讀不到 `version`＝拒絕；不認得（比自己新）＝拒絕；現行版面＝1 | aos-folder 九；§F-2 |
| （視主線取捨）路徑基準一律 `<folder>` 也可放 B 或 E | aos-folder 四（實作已落地：`run_exec.cpp` 的 CwdGuard） |

### D 交接協定（來源主體：`docs/aos-folder.md` 六／八＋T5）

| 條款 | 來源 |
|---|---|
| 三步交接：投遞→彙整→取件，每步一次 rename；`.runi` 語意（存在⟺有一回合沒跑完；正常返回就刪、不論退出碼；解析失敗也算正常返回；已存在拒絕啟動退出碼 3；每顆 CPU 各鎖各的） | aos-folder 六 |
| 彙整規則：只收無狀況後綴；順序不保證（字典序實作、投遞者不得假設）；`inst.json` 未被讀走則本輪不發布；無效投遞隔離 `.bad` 續行；發布成功後才刪投遞 | aos-folder 六 |
| **彙整耐久性與去重**（新）：寫檔→fsync→rename→fsync 目錄的順序；header sidecar 由彙整層寫（四欄位，§C-8 落地）；批 id 去重兜底＋覆蓋範圍（裁-4／裁-6）；`.temp` 殘檔的 roll-forward 語意（見 S3 機制） | gotchas handoff 節；spec 成品 4／5 |
| **`.bad` 誰清**：彙整者 MUST NOT 自動刪；清理歸人或 `aos recover`（M3） | spec 本階段裁決 3（已裁） |
| **`deliver`**：驗證用唯一 parser、temp＋rename 內建、不暴露直寫捷徑、不覆蓋既有名、輸出格式（裁-2）、canonical 位元組（裁-7） | T5 subcommand-specs |
| **投遞檔名唯一化**（裁-1） | spec 本階段裁決 4；gotchas「pid 不唯一」 |
| 退出碼表：對齊實作後照實收編（0/1/2/3 各自涵蓋什麼、`aos exec` 不反映子行程成敗）——**由實作端實測每個失敗模式後提交對照表給主線**，收編時把「已知未決 #2」消掉 | aos-folder 八；gotchas「退出碼」；`docs/usage.md` |

### E 世界與 git（來源主體：`docs/aos-folder.md` 四／十＋debts §2）

| 條款 | 來源 |
|---|---|
| 路徑基準一律 `<folder>`（若不放 B 區） | aos-folder 四 |
| footprint 宣告（SHOULD，§24）：轉移函數有自由變數，git 拍的集合≠機器改的集合 | instruction §24；debts §2 第十輪補記 |
| **`.gitignore` 政策**（取代 aos-folder 十「整包不進」）：`.runi`／`inst.tempd/`（含各 CPU `*.tempd/`）／`.bad` 不進 git；`.aos/turn` 與 `.aos/version` 進；`inst.json`／`inst-head.json` 進不進由主線在條款裡明說（debts §2 指出回滾復原舊批次是「選的、不是副作用」） | spec 本階段裁決 2（已裁）；debts §2 |
| 快照／回滾語意：git 當快照；回滾含 `.runi` 的 commit＝死鎖世界（所以 `.runi` 不進 git） | debts §2；handoff-and-world |

**同一步（S1）**：`docs/SPEC.md` 已知未決 #3（pid 不唯一）在 D 區投遞檔名條款落地後消掉
（S9 執行）；#1 SIGINT **原樣保留**；#4（timeout_ms）不動。

---

## 三、逐步實作

### S0 裁決清點（主線，半小時級）

- 過一遍第一節七項裁決，記入 `wf/workflows/ideas/verdicts.md`（A 表）＋對應 ideas 檔。
- **驗**：verdicts 檔 diff 可讀；七項各有結論。

### S1 SPEC B／D／E 條款起草（主線）

- 動：`docs/SPEC.md`（B／D／E 佔位→條款，未實作帶 `(planned, M1)`）。
- **不動** `docs/aos-folder.md`（降級留 S8，避免立法期間兩份都在改）。
- **驗**：`grep -n "planned, M1" docs/SPEC.md` 列出的每一條都對應 S2–S7 的某一步
  （拿本 plan 的驗收對照表核）；SPEC 無殘留「本區待收編」字樣。

### S2 handoff_fs 基礎件（機械，可轉派）

- 動（皆 `core/inst/src/`）：
  - `handoff_fs.cpp`／`handoff_fs.hpp`：
    1. `write_file` 補 `fsync(fd)`（close 前；失敗照 errno 回報）。
    2. 新增 `fsync_dir(path)` helper（open O_DIRECTORY→fsync→close，EINTR-safe）。
    3. 新增排他發布 helper：優先 `renameat2(RENAME_NOREPLACE)`，`EINVAL`/`ENOSYS`/`ENOTSUP`
       時退 `link()`＋`unlink()`（deliver 用；aggregate 的發布仍是覆蓋語意的 `rename`，不變）。
    4. 新增投遞唯一名產生器（裁-1 格式；`static std::atomic` 計數）。
- 既有呼叫者（aggregate 的 temp 寫入）自動獲得 fsync，行為不變。
- **驗**：`cmake --build --preset default && ctest --preset default` 全綠（不加新測試也可，
  helpers 由 S3／S4 的測試覆蓋；若先行加 helper 單測放 `tests/test_handoff.cpp`）。

### S3 彙整改造：header sidecar＋批 id 去重＋崩潰窗口（判斷型，Opus）

- 動：
  - 新檔 `core/inst/src/handoff_header.cpp`＋內部標頭 `handoff_header.hpp`：
    - header 編碼：手寫產生四欄位 JSON（`{"version":1,"id":"<hex>","origin":"aggregated","result":null}`）。
      值全是受控常量＋hex 字串，無跳脫問題，**不動格式層**（格式層只管 inst schema）。
    - header 讀取：只需抽出 `id` 欄（小型定點解析；解析失敗＝視為 header 不存在＋
      記 warning issue）。
    - 批 id：裁-4 的 FNV-1a 摘要（輸入＝排序後每份投遞的 檔名＋'\0'＋內容＋'\0'）。
  - `core/inst/src/handoff.cpp` 的 `aggregate_instructions` 重排：
    1. 掃 inbox、讀投遞、隔離無效（不變）→ 得 accepted 集合＋摘要 id。
    2. **去重檢查**：`<名字>-head.json` 存在且其 `id` == 本輪摘要時——
       - `inst.json.temp` 存在且完整可解析 → **roll forward**：rename temp→base、刪投遞
         （上次崩在兩個 rename 之間，批次沒丟）。
       - temp 不存在 → 上次已發布且已跑完（或正在跑）→ **只刪投遞、不發布**
         （spec 驗收 3 的場景；含 unlink 全數失敗的重試）。
    3. 正常發布順序改為：寫批 `.temp`（含 fsync）→ 寫 header `.temp`（含 fsync）→
       rename header（**去重承諾的提交點**）→ `fsync_dir` → rename 批 → `fsync_dir` →
       刪投遞 → `fsync_dir`。
       （順序論證：header 先 rename，崩在兩 rename 之間留下「header 新＋temp 在」＝
       roll-forward 可辨識；反過來批先 header 後，崩掉會重演雙重執行。）
  - `core/inst/include/aos/inst.hpp`：`HandoffIssueKind` 尾端追加（如 `HeaderWriteFailed`、
    `HeaderInvalid`）；`HandoffState` 如需新值也**只在尾端加**。deliver 用的宣告留 S4。
  - `core/inst/CMakeLists.txt`：SOURCES 加 `src/handoff_header.cpp`。
  - 測試 `core/inst/tests/test_handoff.cpp`：
    - 既有六案過帳：凡枚舉目錄內容的斷言補「`llm-head.json` 存在」的預期；
      「不發布時不寫 header」「空投遞消化不寫 header」明確斷言。
    - 新增：header 四欄位齊（讀檔驗字面）；**崩潰窗口重播**——aggregate→備份投遞→
      claim＋release→放回同名同內容投遞→再 aggregate→斷言**沒有**發布、投遞被清掉；
      **roll-forward**——手工佈置「header 已 rename＋批 temp 在＋投遞在」現場→aggregate→
      斷言批發布、投遞清掉。
  - `core/inst/tests/test_run_handoff.cpp`：補 `.aos/inst-head.json` 出現的預期（若有
    目錄枚舉斷言）。
- **驗**：建置＋ctest 全綠；`grep -rn "fsync" core/inst/src/handoff*.cpp` 顯示寫檔與三處
  rename 後都有目錄 fsync。

### S4 `aos deliver`：庫層＋CLI（判斷型，Opus；CLI 骨架可轉派）

- 動：
  - 新檔 `core/inst/src/handoff_deliver.cpp`（庫層，依 handoff 分層規矩只靠 inst＋format）：
    `deliver_instructions(instruction_path, document, DeliverOutcome&)`——
    ① `read_all` 驗整批（空批次合法照 §C-2）；② `write_all` 得 canonical 位元組（裁-7）；
    ③ inbox 不存在→依 T5 精神回錯（不自動建世界；`aos init` 已建 `inst.tempd/`）；
    ④ 唯一名（S2 helper）＋ `O_CREAT|O_EXCL` 建 `.temp`、寫入＋fsync；
    ⑤ 排他 rename 成 `<名>.json`（S2 helper；EEXIST→換名重試上限 N 次）；⑥ `fsync_dir`；
    ⑦ 回傳檔名／筆數。
  - `core/inst/include/aos/inst.hpp`：公開宣告（`AOS_API`）＋回傳型別；`HandoffState`
    尾端追加 deliver 需要的值（如 `DeliverPublishFailed`）。
  - 新檔 `core/inst/src/run_deliver.cpp`（CLI 層）：argv 解析
    `aos deliver [folder] [-f FILE|-]`（預設 stdin；folder 預設 `.`，與 init/exec 慣例同）；
    比照 `run_exec_once`：chdir、驗 `.aos` 與 `version`；呼叫庫層對 `.aos/inst.json`；
    stdout 印裁-2 的單行 JSON；退出碼 0／1／2 比照現行慣例。進入點
    `extern "C" aos_deliver_cli_main`。`src/run_internal.hpp` 加宣告。
  - `core/inst/CMakeLists.txt`：`aos_inst_cli` 加 `src/run_deliver.cpp`；
    `aos_add_subcommand(NAME deliver ENTRY aos_deliver_cli_main LIBRARY aos_inst_cli SUMMARY …)`
    （`app/` 不用動，分派表自動長出來）。
  - 測試：新檔 `core/inst/tests/test_run_deliver.cpp`（CMakeLists 的測試 SOURCES 同步加）——
    同 process 連續投遞 N 次得 N 份（spec 驗收 2）；投遞後 exec 一回合真的執行；
    無效 JSON 拒收（inbox 無殘檔）；`-`／`-f` 兩種輸入；缺 `.aos` 報錯；
    輸出 JSON 三欄位可解析。庫層案例加進 `test_handoff.cpp` 或併入本檔。
- **驗**：建置＋ctest 全綠；WSL 手動煙霧（實跑並留存輸出，供 S8 寫進 usage.md）：
  ```bash
  cd "$(mktemp -d)" && "$OLDPWD/build/bin/aos" init . \
    && printf '{"argv":["touch","a"]}' | "$OLDPWD/build/bin/aos" deliver \
    && printf '{"argv":["touch","b"]}' | "$OLDPWD/build/bin/aos" deliver \
    && ls .aos/inst.tempd/   # 兩份、名字不同
  ```

### S5 deliver 的 C ABI（機械偏設計，Opus 定簽名後可轉派）

- 動：
  - `core/inst/include/aos/inst.h`：新 enum `aos_handoff_state`（鏡射 C++ `HandoffState`
    含新值；新型別不受既有 enum 凍結影響，之後同樣凍結）；新函式（草案，定名於實作時）：
    `aos_deliver_buffer(const char *instruction_path, const char *data, size_t size, char *name, size_t name_size, size_t *needed)`、
    `aos_deliver_file(const char *instruction_path, const char *path, …)`、
    `aos_handoff_state_string()`。緩衝區慣例照 `aos_instruction_write_buffer` 的
    `needed` 模式。
  - 新檔 `core/inst/src/capi_handoff.cpp`：實作＋開頭 `static_assert` 串對齊兩邊 enum
    （慣例見 `src/capi.cpp`）；CMakeLists SOURCES 加入。
  - `core/inst/tests/test_capi.c`：C 編譯器下的 deliver 案例（投遞→檔案存在→名字回傳）。
- **驗**：建置＋ctest 全綠（`aos_inst_capi_tests` 是 C 語言 target，混入 C++ 直接編不過）。

### S6 `.aos/turn`（機械，可轉派）

- 動：
  - `core/inst/src/run_init.cpp`：建 `turn`（內容 `0\n`，`O_EXCL`＋fsync）；失敗清理路徑
    （`unlinkat` 串）加 `.aos/turn`。
  - `core/inst/src/run_exec.cpp`：`run_exec_once` 在 `release_instruction` 成功後遞增——
    讀 `.aos/turn`（缺檔照裁-5 視為 0）、寫 `.aos/turn.temp`＋fsync、rename、fsync 目錄。
    遞增失敗＝印錯誤回 1（回合已完成、鎖已釋放，誠實報錯即可）。**只動 `run_exec_once`
    一處，`--loop` 與單發自然同軌**；`run_loop.cpp` 不碰。
  - 測試：`core/inst/tests/test_run_init.cpp` 補 `turn == "0\n"`（三個既有案的檔案清單
    斷言處）；`test_run_handoff.cpp` 或新檔補——一回合後 `1`（spec 驗收 4）、兩回合後
    `2`、無 `inst.json` 的空轉**不**遞增、缺 turn 的舊世界跑一回合後出現 `1`（裁-5）。
- **驗**：建置＋ctest 全綠；煙霧：`aos init w && cat w/.aos/turn`（`0`）→ 投遞＋
  `aos exec w` → `cat w/.aos/turn`（`1`）。

### S7 fsync 掃尾（機械，可轉派）

- 動：spec 成品 5「`core/inst/src/` 寫檔全補 fsync」的殘餘寫點——
  - `core/inst/src/exec.cpp`：`write_exit_status` close 前補 fsync（`exit` 檔正是
    崩潰後要對帳的證據）。
  - `core/inst/src/capi_io.cpp`：`aos_instruction_write_file` 路徑補 fsync；
    `write_fd` 是呼叫者的 fd，**不**代呼叫者 fsync（記進 doc，見風險 3）。
  - `core/inst/src/run_init.cpp`：`version` 寫入補 fsync＋目錄 fsync（S6 已動此檔，
    這裡收齊）。
  - 盤點命令（掃遺漏面）：`grep -rn "O_CREAT\|fopen\|ofstream" core/inst/src/` 逐點確認
    「寫檔者 fsync、child stream 檔除外（內容是子行程寫的，管不到）」。
- **驗**：建置＋ctest 全綠；上述 grep 的每個寫點在 commit message 或 PR 描述逐條交代。

### S8 文件＋導航同步（機械為主，可轉派；usage.md 的命令要實跑）

- 動：
  - `docs/usage.md`：命令表加 `deliver`；新節「`aos deliver` —— 投遞一批 instruction」
    （用法、輸出 JSON、與 exec 的合奏範例）；init/exec 節補 `turn` 一句。
    **每條命令與輸出都貼實跑結果**（S4／S6 煙霧留存的；feature-dev 鐵律，spec 驗收 7）。
  - `docs/aos-folder.md`：開頭聲明**全檔為說明、以 SPEC 為準**；二／三／六／九／十各節
    加導流到對應 SPEC 條款；十的「整包不進 git」改指 E 區新政策；十二「投遞那一步
    沒有實作」段落更新（deliver 已落地）。
  - `core/inst/docs/handoff.md`：補 deliver、header sidecar、fsync 順序、去重與
    roll-forward、覆蓋範圍（裁-6 同款措辭）。
  - `core/inst/docs/capi.md`：新 C ABI 條目。
  - code map（對照現況逐冊）：
    - `wf/workflows/common/code-map/inst/library.md`：`handoff_header.cpp/.hpp`、
      `handoff_deliver.cpp` 新列；`handoff_fs` 職責描述補排他發布／fsync。
    - `wf/workflows/common/code-map/inst/cli.md`：`run_deliver.cpp` 新列；
      `run_exec.cpp` 職責補 turn 遞增。
    - `wf/workflows/common/code-map/inst/capi.md`：`capi_handoff.cpp` 新列。
    - `wf/workflows/common/code-map/inst/tests.md`：`test_run_deliver.cpp`（及新增測試檔）
      新列。
    - `code-map.md`／`code-map/inst.md`：路由模式（`handoff*.cpp`→library、`run*.cpp`→cli、
      `capi*.cpp`→capi）已涵蓋新檔，只需在 inst.md 總述提一句 deliver 子命令。
      （依 conventions：**code map 同步跟該步程式碼同一個 commit**——S3~S7 各自帶自己的
      code map 列，S8 只做總檢查與文檔。）
  - `wf/workflows/common/gotchas.md` handoff 節：fsync／崩潰窗口／pid 檔名三條改記
    「已修（M1，改法一句話＋指 SPEC 條款）」；`.runi` 非鎖那條**保留**（未修）。
  - `wf/workflows/ideas/verdicts.md` D 表同步；本階段新裁決（S0 七項）落 A 表。
- **驗**：文件裡每條命令照貼實跑輸出；`grep -rn "deliver" docs/usage.md` 有節；
  code map 四冊 diff 與新增檔一一對應。

### S9 收尾（主線）

- 動：
  - `docs/SPEC.md`：S1 埋的 `(planned, M1)` 全數摘掉或改標（§C-8、§F-1、§F-2 一併——
    header 已產生、格式版本已住進 header、版面版本條款已入 B 區）；已知未決 #2／#3 消掉、
    #1 原樣保留、#4（timeout_ms，M2）改指 M2。
  - 驗收清單總跑（見下節對照表，逐條打勾）；`ctest --preset default` 最終全綠。
  - `wf/workflows/roadmap.md` M1 記完成；`wf/SESSION-LOG.md` 一行。
  - 本項目資料夾依 build-cycle 移 `archive/`（閘門 ③ 完成後）。
- **驗**：`grep -n "planned, M1" docs/SPEC.md` 零筆；spec 驗收七條全過。

---

## 四、動哪些檔（總表，對照 code map 現況）

| 檔（repo 相對路徑） | 動作 | 步 | code map 落點 |
|---|---|---|---|
| `core/inst/src/handoff_fs.cpp`／`.hpp` | 改：fsync、fsync_dir、排他發布、唯一名 | S2 | inst/library.md（既有列，改職責描述） |
| `core/inst/src/handoff.cpp` | 改：aggregate 重排（header＋去重＋roll-forward＋fsync 順序） | S3 | inst/library.md（既有列） |
| `core/inst/src/handoff_header.cpp`＋`.hpp` | **新**：header 編解＋批 id 摘要 | S3 | inst/library.md（新列） |
| `core/inst/src/handoff_deliver.cpp` | **新**：deliver 庫層 | S4 | inst/library.md（新列） |
| `core/inst/src/run_deliver.cpp` | **新**：CLI＋進入點 | S4 | inst/cli.md（新列） |
| `core/inst/src/run_internal.hpp` | 改：宣告 | S4/S6 | inst/cli.md |
| `core/inst/src/run_init.cpp` | 改：建 turn＋fsync | S6/S7 | inst/cli.md（既有列） |
| `core/inst/src/run_exec.cpp` | 改：release 後遞增 turn | S6 | inst/cli.md（既有列） |
| `core/inst/src/exec.cpp` | 改：exit 檔 fsync | S7 | inst/library.md（既有列） |
| `core/inst/src/capi_io.cpp` | 改：寫檔路徑 fsync | S7 | inst/capi.md（既有列） |
| `core/inst/src/capi_handoff.cpp` | **新**：deliver C ABI＋static_assert | S5 | inst/capi.md（新列） |
| `core/inst/include/aos/inst.hpp` | 改：deliver API、Handoff 枚舉尾端新值 | S3/S4 | inst/library.md |
| `core/inst/include/aos/inst.h` | 改：`aos_handoff_state`＋`aos_deliver_*` | S5 | inst/library.md（標頭列） |
| `core/inst/CMakeLists.txt` | 改：SOURCES＋subcommand deliver＋測試檔 | S3–S6 | code-map/build.md 不需動（機制未變） |
| `core/inst/tests/test_handoff.cpp` | 改＋新案（header／去重／roll-forward） | S3 | inst/tests.md |
| `core/inst/tests/test_run_handoff.cpp` | 改（header 預期）＋turn 回合案 | S3/S6 | inst/tests.md |
| `core/inst/tests/test_run_init.cpp` | 改（turn 斷言） | S6 | inst/tests.md |
| `core/inst/tests/test_run_deliver.cpp` | **新** | S4 | inst/tests.md（新列） |
| `core/inst/tests/test_capi.c` | 改：C ABI deliver 案 | S5 | inst/tests.md |
| `docs/SPEC.md` | 改：B／D／E 條款（主線）＋摘標＋已知未決 | S1/S9 | — |
| `docs/aos-folder.md` | 改：整份降為說明＋導流 | S8 | — |
| `docs/usage.md` | 改：deliver 節＋turn（實跑輸出） | S8 | — |
| `core/inst/docs/handoff.md`／`capi.md` | 改 | S8 | — |
| `wf/workflows/common/gotchas.md` | 改：已修三條過帳 | S8 | — |
| `wf/workflows/ideas/verdicts.md` | 改：S0 裁決＋D 表 | S0/S8 | — |
| `wf/workflows/common/code-map/inst/{library,cli,capi,tests}.md` | 改：新列（各隨該步 commit） | S3–S7 | — |
| `wf/workflows/roadmap.md`、`wf/SESSION-LOG.md` | 改：收尾 | S9 | — |

**明確不動**：`core/inst/src/format*.cpp`、`resolve.cpp`、`inst.cpp`、`spawn_prep.*`、
`wait.*`、`run_loop.cpp`、`run_batch.cpp`（除非 S7 盤點發現寫點，屆時只補 fsync）、
`run.cpp`（deliver 解析自帶於 run_deliver.cpp）、`app/`、根 `.gitignore`、
`test_run_loop.cpp` 的節流兩案（M2）。

---

## 五、風險與退路

1. **彙整崩潰窗口修法改變 handoff 順序 → 既有測試**。
   影響面：`test_handoff.cpp` 六案與 `test_run_handoff.cpp` 中凡枚舉目錄／斷言檔案集合
   的案子會多出 `*-head.json`；「不發布」語意多了去重分支。
   對策：S3 一次過帳所有斷言，**只放寬檔案清單、不放寬語意斷言**（發布內容、順序、
   隔離行為的斷言原樣保留）；aggregate 的公開簽名不變，外部呼叫者零波及。
   退路：header 寫入與去重是 aggregate 內的兩段獨立邏輯，出問題可各自 revert 該段
   （S3 是獨立 commit）；最壞回到「發布後刪投遞」的現狀，只損失驗收 3。
2. **header sidecar 對既有消費者的無害性**。
   論證：`inst-head.json` 住在 `.aos/` 根、不在 inbox；`is_delivery_name` 只掃 `.tempd/`；
   `aos exec` 不枚舉 `.aos/`；`derive_paths` 不認識它。純新增檔，沒有人讀它（loop 讀
   留 M2），刪掉即回復。風險殘量：外部使用者若自己 `glob .aos/*.json` 會多看到一個檔
   ——寫進 usage.md／handoff.md 說明。
3. **fsync 補全的性能與遺漏面**。
   性能：fsync 只落在「有工作的回合」（彙整發布 3 次目錄同步＋每投遞一次、turn 一次、
   每筆 exit 檔一次），對照一回合本來就有 fork/exec，量級可忽略；**空轉路徑
   （`--loop` 睡醒沒事做）零 fsync**，實測方式：跑 `--loop 100` 空世界 60 秒，
   `strace -c -e fsync` 計數為 0。
   遺漏面：S7 的 grep 盤點逐點交代；已知豁免——子行程的 stdout/stderr 檔（內容是
   child 寫的）、`aos_instruction_write_fd`（fd 是呼叫者的，文件言明）。
   退路：fsync 集中在 handoff_fs 的 helpers，若量測出問題可在單點調整策略。
4. **`.aos/turn` 與既有 `aos init` 測試的相容**。
   影響面：`test_run_init.cpp` 三案斷言 `.aos` 內容物；init 失敗清理路徑要多刪一檔。
   對策：S6 同步過帳；缺 turn 的舊世界照裁-5 視為 0 續跑（不 bump `.aos/version`，
   `run_exec` 的 `version == "1\n"` 檢查不動），並補一案鎖住這個相容行為。
   退路：turn 純新增，revert S6 即回復；驗收 4 隨之放棄。
5. **去重兜底的殘洞**（裁-6 的另一面）：部分 unlink 失敗的殘留混入新投遞後仍可能重複
   執行；內容相同、檔名相同的「新」投遞若恰好湊成與上一批完全相同的集合會被誤判重播
   ——但經 deliver 投遞的檔名帶單調序號、必不重複，只有繞過 deliver 手寫固定檔名才會
   踩到。對策：條款照實寫覆蓋範圍（S1）、handoff.md 說明；不擴 header 欄位（manifest
   是 v2 的既裁）。
6. **排他發布的檔案系統相容**：`renameat2(RENAME_NOREPLACE)` 在 WSL ext4 可用，但世界
   若放在 drvfs（/mnt/c）9p 掛載上可能 `ENOSYS`／`EINVAL`——S2 的 helper 內建
   `link()+unlink()` 退階，再不行報錯（不退回覆蓋語意）。測試都在 `/tmp`（ext4），
   drvfs 行為記進 gotchas 一行即可。
7. **C ABI 面**：新 enum／函式一經釋出即凍結（conventions 的 ABI 規則）。對策：S5 簽名
   先給主線過目（隨閘門 ③ 的 commit review），`static_assert` 鎖兩邊枚舉對齊；退路：
   M1 未釋出前仍可改名，發現不妥在 S9 前修。
8. **測試模擬崩潰的可行性**：不真的 kill 行程，用「佈置崩潰後的檔案現場」重現
   （備份／放回投遞、手工擺 header＋temp），全部確定性、無 sleep、無 race。

---

## 六、外包切分（誰做哪步、驗收怎麼收）

依 [delegate-simple-work-to-sonnet 記憶]：判斷型給 Opus 實作 agent，機械型由 Opus 轉派
sonnet；**SPEC 條款起草與一切 `docs/SPEC.md` 修改保留給主線**（AI 不得自行修憲，條款
清單見第二節）。

| 步 | 給誰 | 性質 | 驗收怎麼收 |
|---|---|---|---|
| S0、S1、S9 | **主線** | 裁決／修憲 | 使用者概括授權下，verdicts＋SPEC diff 自查 |
| S2 | Opus→**sonnet** | 機械（helpers） | ctest 綠＋diff review |
| S3 | **Opus** | 判斷型（順序論證、去重、roll-forward、測試設計） | ctest 綠＋新測試逐案對 spec 驗收 3／5；主線抽查 aggregate 順序與論證 |
| S4 | **Opus**（CLI 骨架與機械測試可轉 sonnet） | 判斷型＋機械 | ctest 綠＋煙霧輸出留存（供 S8）；驗收 2 的 N 次投遞案必在 |
| S5 | Opus 定簽名→**sonnet** 實作 | 機械（static_assert／wrapper） | ctest 綠（C target 編譯即把關）＋簽名主線過目 |
| S6 | Opus→**sonnet** | 機械 | ctest 綠＋驗收 4 案必在＋舊世界相容案必在 |
| S7 | Opus→**sonnet** | 機械（掃尾） | grep 盤點清單逐點交代＋ctest 綠 |
| S8 | Opus→**sonnet**（usage.md 實跑部分 Opus 把關） | 機械＋鐵律驗證 | 文件內命令逐條實跑核對；code map 四冊 diff 對表 |

任務書共通條款（發包時附上）：本 plan 對應步驟全文＋spec「明確不做」＋keep.md 保護項
＋conventions 的分層鐵律與 300 行門檻＋「每步 ctest 綠才交件、code map 同 commit」。
背景等待期間不輪詢（記憶：offload 時別插話）。

---

## 七、驗收對照（spec 七條 ↔ plan 步驟）

| spec 驗收 | 對應步驟 | 機械檢查 |
|---|---|---|
| 1. SPEC B／D／E 逐條有編號位階來源；無「planned, M1」殘留 | S1＋S9 | `grep -n "planned, M1" docs/SPEC.md` 零筆；佔位段消失 |
| 2. deliver 與 D 區一致；同 process N 次投遞得 N 份 | S4（條款對齊靠 S1 先行） | `test_run_deliver.cpp` N 次案；煙霧兩投遞兩檔 |
| 3. 崩潰窗口：刪投遞前中斷，重啟不執行第二次 | S3 | `test_handoff.cpp` 重播案＋roll-forward 案 |
| 4. turn：init 後 0、一回合後 1 | S6 | `test_run_init.cpp`／turn 回合案；煙霧 cat |
| 5. 批旁有 header sidecar，四欄位齊 | S3 | `test_handoff.cpp` header 欄位案 |
| 6. ctest 全綠（含新測試）；code map 同步；usage.md 補 deliver | 每步＋S8 | `ctest --preset default`；code map 四冊 diff；usage.md deliver 節 |
| 7. 文件中每條指令與輸出都真的跑過 | S4／S6 煙霧留存→S8 | S8 驗收時逐條重跑核對 |
