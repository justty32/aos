# aos-json

`aos-json - 讀、改 aos 的 JSON 設定（檔#/指標、指示詞）`（NAME，C-54 R1）

**一句話：用 `檔#/指標` 讀或改一份 JSON 的某個位置；認得 `$ref`／`$env`：可以穿過 `$ref` 改被參照的檔、追一個值實際寫在哪、一層層看（漸進展開）、寫之前先驗形狀。**
一個 lib（`lib/libaos-json.a`，沒有公開標頭）加一支命令列（`bin/aos-json`），再加兩個給腦掛的工具（`tools/json/`、`tools/json_edit/`）。
嘗試性原型（使用者「做一套方便修改json的工具集，配合指示詞」），討論與代定見 [thinking 2026-10-24 aos-json](../../thinking/2026-10-24-aos-json.md)。

```sh
aos-json peek fsm.json                                   # 只看頂層，大的值摺起來
aos-json peek --follow fsm.json#/states/think            # 穿過 $ref 看下一層
aos-json get --resolve fsm.json#/states/think/exec       # 解開指示詞（跟 aos-fsm 讀的一樣）
aos-json where fsm.json#/states/think/next               # 這個值實際寫在哪份檔的哪裡（一站一行）
aos-json set --follow fsm.json#/states/think/next '"act"'    # 改被 $ref 的那份檔
echo '{"/max": 5, "/interval_ms": 100}' | aos-json batch loop.json   # 一次改很多個（全部成功才寫）
aos-json ref --move daemon.json#/loops daemon_loops.json # 把一塊拆成另一份檔，原地換成 $ref
aos-json check fsm.json                                  # $ref 指得到、寫法對、exec 形狀對
```

## 用法

`aos-json 子命令 [旗標...] 檔#/指標 [值]`——**旗標放在 `檔#/指標` 前面**（同 aos-util 的 `parse_cli`：第一個不是旗標的參數起都是原樣）。
`檔#/指標` 同 N-62：第一個 `#` 就切、`#` 後一定要 `/`、指標照 RFC 6901（`~1`＝`/`、`~0`＝`~`、陣列索引不收前導 0）；沒 `#`＝整份。
值：有給參數就用參數，沒給讀 stdin 整份；當 JSON 解（解不開＝`ValueBad`，要寫字串加 `--str`）。負數值要整個加引號或放 stdin（`--` 後面的會被當成多的參數）。

| 子命令 | 做什麼 | 旗標 |
|---|---|---|
| `get` | 印那個值（一行 JSON） | `--follow` 路上的 `$ref` 穿過去；`--resolve` 把值裡的指示詞解開（aos-directive）；`--str` 字串印字面 |
| `peek` | 漸進展開：第一行位置＋形狀，之後每個孩子一行 `key: 摘要`（字串超過 80 位元組截斷、物件 `{N} 前六個 key`、陣列 `[N]`、指示詞 `$ref "…"`）；指到純值＝整個印 | `--follow`（指到的 `$ref`／`$ref` 陣列照 aos-directive 合好展開）、`--depth N`（預設 1） |
| `where` | 一路穿過 `$ref`，每站一行 `檔#/指標`，最後一站＝值實際寫的地方；最後是 `$env` 多印 `$env 名字` | |
| `set` | 換掉那個值（單值或整棵子樹）；物件裡沒這個 key＝接在最後；陣列只換已有的索引；整份（沒 `#`）時檔可以還不在＝建新檔 | `--follow`、`--parents`（路上沒有的物件 key 建空物件）、`--str`、`--check` |
| `batch` | stdin `{"/指標": 值, …}` 照順序一個個 set，**全部成功才寫**（每份檔一次原子寫入） | `--follow`、`--parents`、`--check` |
| `del` | 刪 key／元素（不刪整份） | `--follow`（`$ref` 陣列合起來的 key：每一份有的都刪） |
| `append` | 陣列尾巴加一個 | `--follow`、`--str`、`--check` |
| `merge` | 物件淺層合 key（同 `$ref` 陣列：後蓋前、不往下合；`null` 照字面放） | `--follow`、`--check` |
| `env` | 換成 `{"$env": 名字}` | `--path`、`--prefix`、`--parents` |
| `ref` | 換成 `{"$ref": 目標}`（目標從這份檔的資料夾算） | `--move`：先把原本的值搬到目標（整份檔＝檔不能已在；`檔#/指標`＝那裡要還沒有），裡面的相對 `$ref` 跟著改；`--parents` |
| `check` | 驗：`$ref` 指得到（一路驗進被參照的檔）、繞圈、`$ref` 陣列合得起來、指示詞寫法不合、`exec` 形狀（最上層 `exec`、`states/<名>/exec`、`loops/<名>/exec`：非空字串、非空陣列、單子要有非空 `argv`）。問題每個一行 `位置: 代號 原因` 印 stdout、退 1；沒問題退 0 | `--env`：`$env` 現在沒設也報 |

**`--follow` 的規則**：沒加時，寫入的路上經過指示詞＝`FollowMissing`（往指示詞物件裡加 key，aos 不會看，是陷阱）；直接指著指示詞改＝原地換掉它。
加了＝穿過 `$ref` 改被參照的檔；`$ref` 陣列（幾份合成一份）：物件看「最後一份有這個 key 的」（生效的就是它），都沒有＝寫進最後一份；陣列照索引換算是哪一份；
`set --follow` 不能整個換掉合起來的值（`TargetBad`）；`$env` 穿不過去（`PointerMissing`）。`get`、`peek` 不加 `--follow` 時照原文走（跟 aos 讀設定檔一樣：`#/指標` 取原文）。

**`--check`**：寫之前把整份檔（含被 `$ref` 的）用 check 驗一次改完的樣子，**比原本多出問題**才擋（`CheckFailed`，一個都不寫）；原本就有的問題不擋。

**錯**：stderr 一行 `aos-json: 代號 原因`、退 1（同 aos-exec，N-60）。代號：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`FileMissing`、`FileBad`（讀不了、資料夾、不是 JSON）、
`SpecBad`、`PointerMissing`、`ValueMissing`、`ValueBad`、`TargetBad`（這個位置不能這樣改）、`FollowMissing`、`CheckFailed`、`DirectiveBad`（`$ref` 讀不到、指不到、繞圈、合不起來；`--resolve` 的 `$env` 沒設）、`WriteFailed`、`Internal`。
check 印的問題代號：`DirectiveBad`、`DirectiveFormBad`（帶 `$ref`／`$env` 但寫法不合，aos 會原封不動留著）、`ExecBad`。

## 寫回去：原子、只改變的那一塊

- **原子**（N-05）：同資料夾先寫 `.名字.<pid>.tmp`、設回原本的權限、fsync、再 rename 蓋過去；失敗清掉暫存檔。值沒變＝不寫（mtime 不動）。
- **捷徑**：寫到它指的那份檔，捷徑本身留著。**第一行 `#!`** 整行留著。
- **只重寫有變的那一塊**（`src/doc/splice.cpp`）：從根往下找到「只有一個孩子變了」的最深那一層；加一個 key／元素（接在最後）或少一個＝只插入或拿掉那一個成員；其他＝只換那一個值的原文。
  原本在一行裡的寫一行（`", "`、`": "`），跨行的照檔的縮排展開（看第一個有縮排的行猜每層幾格）。其他地方一個字都不動，所以 git diff 只有那幾行。
  做不到（變的是整份、物件裡有重複的 key、檔裡有奇怪的寫法）＝整份照猜到的縮排重排。

取捨：新寫進去的那塊是 nlohmann 的排版（多行時每個陣列元素一行）；數字照 nlohmann 印（`1e3` 會變 `1000.0`）、字串裡的 `é` 這種跳脫會變成原字——只發生在被重寫的那一塊。
沒保留：檔的擁有者（rename 換成新檔、擁有者是跑的人）、硬連結（rename 後斷開）。兩個人同時改同一份檔＝後寫的蓋掉先寫的（沒有鎖）。

## 給腦用的兩個工具（`tools/`）

照 agent-dan 的慣例（P-41：工具名＝資料夾名、`tool.json` 給模型看、arguments 從 stdin 進、stdout 是結果）。掛法：把資料夾複製或捷徑到範本的 `tools/` 底下、`aos-json` 放進 PATH（aos 的程式都不動 PATH，N-50）。
檔名只收工作區（`$AOS_WS`）裡的相對路徑（不收絕對路徑、不收 `..`；`--follow` 穿過的 `$ref` 不在這個限制裡）。

- **`tools/json/`**：一次一個動作——`{"cmd": peek|get|where|set|batch|del|append|merge|check, "target": "檔#/指標", "value": JSON, "depth": N}`。
  讀＝peek 一層層往下（帶 `--follow`）；寫＝直接收腦生成的 JSON 值（單值、整棵子樹、或 batch 一次很多個），一律帶 `--check --follow`。
  aos-json 的錯（指不到、形狀不對）是腦寫錯了：stdout 印 `錯：代號 原因`、退 0，讓腦看了重來；這支自己的錯（stdin 不對、aos-json 起不來）才 stderr 一行、退 1。
- **`tools/json_edit/`**：「小念頭」式兩步改——`{"file": "fsm.json", "want": "把 think 那格的逾時改成 30 秒"}`。
  一、**找到要修改的 key**：腦只看到頂層 peek，用 `peek` 一層層往下，`found` 交出一個或多個指標（最多 `JSON_EDIT_MAX_ROUNDS` 輪，預設 12）；
  二、**提供值**：每個指標各開一次新對話（不帶第一步），只給要做的事、那個位置現在的值、上一層的摘要，腦用 `give` 交出新值的 JSON 文字（解不開讓它重給，最多 3 次）；
  最後 `aos-json batch --check --follow` 一次寫進去。stdout：`看過：/ → /states → …`、`找到：…`、`改：檔#/指標 = 值`；寫不進去印 `沒改：…` 退 0。
  腦＝OpenAI 相容端點（`AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`（預設 `chatgpt-gpt-6-luna-low`）、`AOS_BRAIN_KEY`，同 agent-dan）；沒設 URL＝`BrainMissing`。

真腦跑一次（LiteLLM 開著時）：
```sh
cd proto8/impls/aos-json && mkdir -p /tmp/ws && cp ../../demo/agent-dan/fsm.json /tmp/ws/
echo '{"file": "fsm.json", "want": "把 think 那格的逾時改成 30 秒"}' | \
  PATH=$PWD/bin:$PWD/../aos-exec/bin:$PATH AOS_WS=/tmp/ws AOS_STACK=/tmp/ws/ AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec tools/json_edit
```

## 跟 aos-directive 的分工

`get --resolve` 與 `peek --follow` 指到的 `$ref` 直接交給 aos-directive（`resolve`、`resolve_shallow`），跟 aos-loop、aos-fsm 讀設定檔同一套；最外層的相對 `$ref` 從給的檔所在的資料夾算（沒解開捷徑，同 aos-loop 的 `load_cfg`）。
但改檔要的是「這個值在哪份檔的哪個位置」，aos-directive 的公開介面只回值，所以 `src/follow/` 照它的規則自己走一遍（寫法寬容、相對路徑從那份檔解開捷徑後的資料夾算、讀檔跳 `#!`、指標取原文、繞圈＝同一個檔＋指標又出現、陣列同名後蓋前）。
**兩份規則要一起改**：aos-directive 改了寫法或語意，`src/follow/kind.cpp`、`locate.cpp` 要跟著改。以後若 aos-directive 公開「取一份 `$ref` 的位置」（例如把 `fetch_ref` 的位置版開出來），這裡就能改用它。

## 元素

| 檔 | 做什麼 |
|---|---|
| `src/main.cpp` | 第一個參數挑子命令；錯印一行「aos-json: 代號 原因」、退 1 |
| `src/common/common.hpp` | 自己的錯誤代號 |
| `src/doc/doc.hpp` | 【doc】`File`（原文、排版、權限）、`Docs`（讀過的檔都留著，改完一起寫）、`Spec`、指標 |
| `src/doc/file.cpp` | 讀檔（記 `#!`、縮排、結尾換行、權限）、`render_body`、原子寫回 `save_file` |
| `src/doc/splice.cpp` | 只重寫有變的那一塊（自己掃 JSON 找起訖） |
| `src/doc/pointer.cpp` | `檔#/指標` 拆開、指標拆接、往下一格、印給人看的位置 |
| `src/follow/follow.hpp` | 【follow】`Kind`、`Cursor`、`Mode`、`Located` |
| `src/follow/kind.cpp` | 認指示詞（寬容規則同 aos-directive） |
| `src/follow/locate.cpp` | 往下走、穿 `$ref`（`fetch`、`settle`、`$ref` 陣列挑哪一份） |
| `src/cmd/cmd.hpp` | 【cmd】每個子命令一個函數；`problems_of`（check 的本體，`--check` 也用） |
| `src/cmd/read.cpp` | `get`、`where` |
| `src/cmd/peek.cpp` | `peek`（摘要怎麼寫） |
| `src/cmd/write.cpp` | `set`、`batch`、`del`、`append`、`merge`、`env`、`ref`；`Edit`（每一步更新原文、`--check`、只寫有變的） |
| `src/cmd/check.cpp` | `check` |
| `tools/json/` | 腦用：一次一個動作（`tool.json`、`_entry`） |
| `tools/json_edit/` | 腦用：兩步改（找 key → 提供值），自己問腦 |
| `tests/test_cli.py` | 命令列黑箱 |
| `tests/test_tool.py` | 兩個工具，經 `aos-exec` 跑、假 OpenAI 端點（`../aos-exec/bin/aos-exec` 沒建＝跳過） |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

依賴 aos-util、aos-directive（`add_subdirectory` 一起編）；`test_tool` 另外要 aos-exec 已經建好。
**共用建置**：`aos-json` 在 `wf/workflows/testing.md` 與 `impls/README.md` 的建置迴圈裡（放在 aos-exec 後面，test_tool 要 aos-exec 先建好）。
`proto8/tests/aos_bins.py` 把 `aos-json/bin` 放進 PATH（`lib/base/json_edit` 經 aos-json 寫檔）；`proto8/demo/run.sh` 只有範本真的掛上 `tools/json*` 時才要把它放進 PATH。
