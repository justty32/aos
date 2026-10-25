# galtxt-a 第二輪：反向收攏方案（fable，2026-10-25）

← 盤點 [round2-optimize.md](round2-optimize.md)｜第一輪 [round1.md](round1.md)、[round1-measure.md](round1-measure.md)｜依據：[fn-grow 六級與「怎麼搬才不改行為」](../../../thinking/2026-10-24-fn-grow.md)、[`_metainfo` M1 三處](../../../thinking/2026-10-24-metainfo/01-位置與格式.md#1-放哪三處同一個名字)、[aos-grow](../../../grow/README.md)、C-72（JSON＝單檔的檔案系統）、P-33／P-41（工具放 `<格>/tools/<名>`、腦靠 `tools/` 列工具）、N-59／N-61／N-62（aos-exec 怎麼找入口、`檔#/指標`）｜題目：[thinking 10-25 top-down](../../../thinking/2026-10-25-top-down.md)（「嵌套太深要收攏、尾端葉片縮成 json、要考慮權限等檔案系統特性」）

給實作者照做。只寫規劃、不改程式。目標：**收攏前後同一題假腦跑出的 `out/` 與 `score.json` 一樣（抹掉時間）、測試照樣全綠**。

---

## 1. 判準（先寫，之後讓 metatable 半自動判）

條件盡量用 `_metainfo` 欄位（`kind`、`grow_level`、`fs_needs`、`callers`、`time_ms`、`interrupt`）加兩個掃資料夾就有的事實（`_entry` 有沒有 `+x`、資料夾裡還有哪些檔）。**「不縮」的條件先看，命中任一條就停，再看「併」「縮」。**

| 代號 | 條件（全部成立才動） | 動作 | 出處 |
|---|---|---|---|
| **N-1 不縮** | `fs_needs` 含 `own_stack`（自己的 loop／fsm／history）、`tool_json`（腦要靠資料夾＋`tool.json` 列到它，P-41）、`isolation`（沙箱邊界靠資料夾）、`mount`（要被 `--ws` 掛別的工作區跑）、`lock`／flock、`git_tracked` 且要**單檔 diff**（人手各自改的表）、大檔或二進位、要被別的行程獨立寫、捷徑掛點（捷徑本身留、只改目標）、要權限／擁有者 | 留著 | 使用者 10-25「要考慮權限等檔案系統特性」 |
| **N-2 不縮** | 伴隨檔 ≥ 2（prompt、`.env`、第二支腳本）或 `grow_level` ≥ 4 | 留著 | fn-grow 第 4 級 |
| **N-3 不縮** | `interrupt` 是 `resumable` 且自己保管狀態（`writes` 有 `stack:` 自己的檔），或 `callers` ≥ 2 且入口是腳本 | 留著（共用的真身） | fn-grow 第 5 級、第 2 級「被 ≥ 2 處叫」 |
| **A-1 併容器** | 資料夾**沒有** `_metainfo`、沒有 `_entry`，底下只有一個子資料夾（純中間層） | 子資料夾上提一層；指進去的捷徑改目標 | 10-25「中間層糅合成一個資料夾」 |
| **A-1 例外** | 容器叫 `tools/` 而且底下至少一個子項有 `tool.json` | 留（act.py／brain.py 靠列 `tools/` 找工具，P-41） | P-33、P-41 |
| **A-2 併 glue** | `kind=glue`、只做「開小格叫一個 agent、收結果」、那隻 agent `callers`＝1 且只有它叫 | glue 照 B-2 縮成呼叫方的伴隨腳本；agent 搬到 glue 原來的位置 | O-3、實測偏離 5（agent 不是腦的工具） |
| **B-1 縮成 JSON** | `_entry` 是單子（沒 `+x`）、資料夾只有 `_entry`＋`_metainfo`、`fs_needs` 空 | `callers`＝1 且呼叫方在同一份檔 → 第 0 級內嵌（`_metainfo` 進單子）；`callers` ≥ 2 → 第 2 級 `x.json` | fn-grow 縮回；aos-grow `down` 的範圍 |
| **B-2 縮成內嵌單子＋腳本** | `_entry` 是腳本（`+x`）、資料夾只有 `_entry`＋`_metainfo`、`fs_needs` 空、`callers`＝1、呼叫方是同一隻 agent 的 fsm 格 | 腳本改名 `<名>.py`／`.sh` 搬到呼叫方 fsm.json 旁邊（成為那隻 agent 的伴隨檔，跟 agent-dan 的 `brain.py`／`act.py` 一樣），那格改成 `{"argv": ["python3", "<名>.py"], "timeout_ms", "_metainfo"}`；腳本裡 `__file__`、`sys.path` 重算 | fn-grow「縮回：觸發點都沒了就往回併一級」；第 3 級的觸發「只有它用的非 JSON 檔」在 agent 裡**不算**——那是 agent 的伴隨檔（範本 agent-dan 就是這樣放） |
| **B-3 資料夾縮成單檔表** | `kind=data`、`fs_needs` 只有 `git_tracked`、裡面全是小 JSON（合計 < 8 KB、< 300 行）、讀者只有一個程式 | 併成 `<名>.json`，key＝原檔名去 `.json`，頂層加 `source`；原資料夾的 `_metainfo` 併進上一層 `_metainfo` 的 `children` | C-72（JSON＝資料夾）；STRUCTURE 門檻；超過門檻就再拆回（降級也成立） |
| **B-4 去重** | ≥ 2 個葉片內容一樣（`_entry` 同 hash、`_metainfo` 同） | 留一份真身，其餘換相對捷徑 | C-61「相對捷徑、兩份一起搬也不斷」 |

半自動：B-1～B-4、A-1 只要 `_metainfo`＋掃資料夾就能判；A-2 要看 `summary`（或日後加 `role: glue_fanout`）；N-1 的「要單檔 diff」「別的行程寫」要人說（`fs_needs` 寫 `git_tracked`、`shared_write` 就行）。

---

## 2. 逐節點裁決

實際的樹（25 個資料夾含根；真資料夾最深 4 層，捷徑 `write/tools/writer/tools/lint` 5 層）。「縮完長相」給出 JSON 全文或單子。

| 節點 | 判準 | 裁決 | 縮完長相／理由 | 要改的呼叫方 |
|---|---|---|---|---|
| `.` | N-1 `own_stack`、`git_tracked` | 留 | 多 5 個伴隨腳本（`brief.py`、`write.py`、`check.py`、`judge.py`、`pick.py`）；根共 10 個檔、用途單一（STRUCTURE 觸發 B 是 >10 且混用） | — |
| `idle/` | N-3：收攏後 `callers`＝3（根 fsm＋兩隻 agent）、入口是 sh 腳本 | 留，當**真身** | 單子寫不出「cur/ 或 new/ 有檔」這件事（要用 `sh -c`，使用者 10-15「少用 sh」），所以不縮成 JSON；改由兩隻 agent 的 `idle` 捷徑指過來（B-4） | `writer/idle → ../idle`、`grader/idle → ../idle`（捷徑） |
| `brief/` | B-2：`+x` 腳本、只有 `_entry`＋`_metainfo`、`fs_needs` 空、`callers` 1 | 縮成 `brief.py`＋內嵌單子 | fsm.json：`"brief": {"exec": {"argv": ["python3", "brief.py"], "timeout_ms": 10000, "_metainfo": {…brief/_metainfo 原文，加 "grow_level": 0…}}, "next": "write"}`；`DATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")`（少一層 `dirname`） | fsm.json 那格；`data/` 讀法照 B-3 改（見下） |
| `write/` | A-2＋B-2：glue、只開小格叫 writer、writer 只有它叫 | 縮成 `write.py`＋內嵌單子；`writer/` 上提到根 | `"write": {"exec": {"argv": ["python3", "write.py"], "timeout_ms": 2400000, "_metainfo": {…write/_metainfo…}}, "next": "check"}`；`sys.path` 從三個 `..` 改兩個（`proto8/lib/agent`）；`run_agent(NAME, "writer", …)` | fsm.json 那格 |
| `write/tools/` | A-1：純容器、沒 `_metainfo`、唯一子項 writer 沒 `tool.json` | 併掉 | writer 不是腦的工具（實測偏離 5），不該住 `tools/` | — |
| `write/tools/writer/` | N-1 `own_stack`、N-2（`.env`、`system.txt`、`brain.py`、`act.py`）、N-3 resumable | 留，**搬到 `writer/`** | 檔案一個不動（brain.py／act.py 只用 cwd 與環境變數，不用 `__file__`，fn-grow 邊緣狀況已查） | `write.py` 的目標字串 |
| `write/tools/writer/idle/` | B-4（跟根 `idle/` 一字不差） | 換捷徑 | `writer/idle → ../idle`；fsm.json 的 `"exec": "idle"` 不改（aos-exec 走捷徑進資料夾，N-61） | — |
| `write/tools/writer/tools/` | A-1 例外（底下 lint 有 `tool.json`） | 留 | brain.py 列 `tools/` 才看得到 lint | — |
| `write/tools/writer/tools/lint`（捷徑） | N-1 捷徑掛點 | 留、改目標 | `writer/tools/lint → ../../tools/lint` | — |
| `check/` | B-2（同 brief） | 縮成 `check.py`＋內嵌單子 | `"check": {"exec": {"argv": ["python3", "check.py"], "timeout_ms": 30000, "_metainfo": {…, "grow_level": 0, "fs_needs": []}}}`；程式碼一字不改（`aos-exec --ws stack tools/lint` 從 cwd＝根算 → 根的 `tools/lint`，P-33「內嵌單子格的工具就是 agent 根下的 `tools/<名>`」） | fsm.json 那格 |
| `check/tools/` | A-1 例外 | 留，**上提到根 `tools/`** | 它是 check 格（現在內嵌在根）的工具容器 | — |
| `check/tools/lint/` | N-1 `tool_json`、`mount`；`callers` 2 | 留，搬到 `tools/lint/` | 檔案不動（只讀 `$AOS_WS/rules.json`、stdin） | check.py 不改；writer 的捷徑改目標；測試的 `LINT` 路徑 |
| `judge/` | A-2＋B-2 | 縮成 `judge.py`＋內嵌單子；agent 上提到根、**改名 `grader/`**（避免 `judge.py` 與 `judge/` 同名混淆；aos-exec 分得開、人分不開） | `"judge": {"exec": {"argv": ["python3", "judge.py"], "timeout_ms": 960000, "_metainfo": {…}}}`；`run_agent(NAME, "grader", …)`；小格名照舊 `fresh_cell(stack/"judge")`（stack 長相不變） | fsm.json 那格 |
| `judge/tools/` | A-1 | 併掉 | 同 write/tools | — |
| `judge/tools/judge/` | N-1、N-2、N-3 | 留，搬到 `grader/` | brain.py／act.py 的錯誤前綴 `judge:` 是字面、**不改**（證明時 stderr 才比得一樣） | judge.py 的目標字串 |
| `judge/tools/judge/idle/` | B-4 | 換捷徑 | `grader/idle → ../idle` | — |
| `pick/` | B-2 | 縮成 `pick.py`＋內嵌單子 | `"pick": {"exec": {"argv": ["python3", "pick.py"], "timeout_ms": 10000, "_metainfo": {…}}}`；`DATA` 少一層 `dirname`；讀 `data/bench/<編號>.json` 不變 | fsm.json 那格 |
| `data/` | N-1 `git_tracked`＋`isolation` | 留 | `_metainfo.children` 改寫成：`{"cast.json": "人物卡 {名: 卡}", "places.json": "地點卡 {名: 卡}", "samples.json": "範例句 {名: {source, lines}}", "bench/": "評測題一題一檔，含正解——只有 pick 讀"}` | — |
| `data/bench/` | N-1 `isolation`；而且會長（corpus 二十幾題 × 1.5 KB > 8 KB） | 留 | 正解只給 pick；日後要用檔案系統隔離（寫手沙箱看不到這個資料夾）靠的就是這個邊界 | — |
| `data/cast/` | B-3（2 張卡、1.4 KB、只有 brief 讀） | 縮成 `data/cast.json` | `{"source": "corpus/人物/*.md、固化/01、02（各卡自己的 source 在卡裡）", "佐伯悠": {…原 佐伯悠.json 全文…}, "森下晴子": {…}}`；brief：`cards.append(load(DATA/"cast.json")…).get(who)`，沒有 → `CastMissing`。> 8 KB 或 > 5 個人時拆回資料夾 | brief.py 三處 `load(...)` |
| `data/places/` | B-3（1 張、0.5 KB） | 縮成 `data/places.json` | `{"source": "corpus/世界/日和町地誌/*.md", "河鹿堂": {…}}` | brief.py |
| `data/samples/` | B-3（2 檔、0.4 KB） | 縮成 `data/samples.json` | `{"source": "corpus 場景（各角色的 source 在各自那格）", "佐伯悠": {"source": …, "lines": […]}, "森下晴子": {…}}` | brief.py（`os.path.exists` 改成 `in`） |
| `data/*.json` 三張（address、forbidden、styles） | N-1 要單檔 diff（人手各自改） | 留，不併成一份 `data.json` | 三張表來源不同的 corpus 檔、改的人與時機不同；併成一份 diff 會混 | — |
| `meta/`、`meta/metatable/` | `callers` 0、開發期工具，會長（§ 5 要加 `--suggest`） | 留 | — | — |
| `plan/`、`plan/examples/` | 範例是要被 `cp` 單獨拿的題目檔（檔的身分就是用途） | 留 | 併成一份 JSON 反而要工具才拆得出來 | — |

**不在這輪做的**（寫進 round2-optimize 的 O-5）：`write.py`、`judge.py` 併成一支 `fanout.py`——那是改程式不是搬，證明會被弄髒；收攏完、證明過了再做。

---

## 3. 收攏前後兩棵樹

**前**（25 個資料夾含根；真資料夾最深 4、含捷徑 5；metatable 24 列）：

```
galtxt-a/
├─ _entry _metainfo loop.json fsm.json README.md
├─ idle/                       _entry _metainfo
├─ brief/                      _entry _metainfo
├─ write/                      _entry _metainfo
│  └─ tools/
│     └─ writer/               _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│        ├─ idle/              _entry _metainfo
│        └─ tools/
│           └─ lint → ../../../../check/tools/lint
├─ check/                      _entry _metainfo
│  └─ tools/
│     └─ lint/                 _entry _metainfo tool.json
├─ judge/                      _entry _metainfo
│  └─ tools/
│     └─ judge/                _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│        └─ idle/              _entry _metainfo
├─ pick/                       _entry _metainfo
├─ data/                       _metainfo address.json forbidden.json styles.json
│  ├─ bench/                   _metainfo Q01.json
│  ├─ cast/                    _metainfo 佐伯悠.json 森下晴子.json
│  ├─ places/                  _metainfo 河鹿堂.json
│  └─ samples/                 _metainfo 佐伯悠.json 森下晴子.json
├─ meta/                       _metainfo table-round1.md
│  └─ metatable/               _entry _metainfo
└─ plan/                       _metainfo round1.md round1-measure.md round2-*.md
   └─ examples/                _metainfo Q01.json scene.json
```

**後**（13 個資料夾含根；真資料夾最深 2、含捷徑 3；metatable 21 列，其中捷徑 3）：

```
galtxt-a/
├─ _entry _metainfo loop.json fsm.json README.md
├─ brief.py write.py check.py judge.py pick.py        ← 五格的身體；fsm.json 五格是內嵌單子、各帶 _metainfo
├─ idle/                       _entry _metainfo（真身；callers 3）
├─ tools/
│  └─ lint/                    _entry _metainfo tool.json（check.py 與寫手都叫它）
├─ writer/                     _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│  ├─ idle → ../idle
│  └─ tools/
│     └─ lint → ../../tools/lint
├─ grader/                     _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│  └─ idle → ../idle
├─ data/                       _metainfo address.json forbidden.json styles.json cast.json places.json samples.json
│  └─ bench/                   _metainfo Q01.json
├─ meta/                       _metainfo table-round1.md table-round2.md
│  └─ metatable/               _entry _metainfo
└─ plan/                       _metainfo round1.md round1-measure.md round2-*.md lessons.md side-mcp.md
   └─ examples/                _metainfo Q01.json scene.json
```

| | 前 | 後 |
|---|---|---|
| 資料夾（含根） | 25 | 13 |
| 真資料夾最大深度 | 4（`judge/tools/judge/idle`） | 2（`tools/lint`、`writer/tools`、`data/bench`） |
| 含捷徑最大深度 | 5 | 3 |
| metatable 列 | 24 | 21（5 列從資料夾列變成 `fsm.json#/states/*/exec` 列） |
| 執行一題的 aos-exec 跳數 | 根 1＋五格各 1＋寫手 3＋評審 3＋lint 6 | 五格那 5 跳沒了（內嵌單子在 fsm 行程內跑） |

收攏後的 `fsm.json`（全文；`_metainfo` 內容＝原各資料夾那份原文，只加 `"grow_level": 0`、`fs_needs` 照舊）：

```json
{"_entry": ["aos-fsm", {"$env": "AOS_CF"}],
 "start": "idle",
 "states": {
   "idle":  {"exec": "idle", "next": "brief"},
   "brief": {"exec": {"argv": ["python3", "brief.py"], "timeout_ms": 10000,   "_metainfo": {"summary": "認領一題…", "kind": "program", "grow_level": 0, "time_ms": {"val": 50, "max": 10000}, "…": "原 brief/_metainfo 其餘 key"}}, "next": "write"},
   "write": {"exec": {"argv": ["python3", "write.py"], "timeout_ms": 2400000, "_metainfo": {"…": "原 write/_metainfo"}}, "next": "check"},
   "check": {"exec": {"argv": ["python3", "check.py"], "timeout_ms": 30000,   "_metainfo": {"…": "原 check/_metainfo，grow_level 4 → 0"}}, "next": "judge"},
   "judge": {"exec": {"argv": ["python3", "judge.py"], "timeout_ms": 960000,  "_metainfo": {"…": "原 judge/_metainfo"}}, "next": "pick"},
   "pick":  {"exec": {"argv": ["python3", "pick.py"], "timeout_ms": 10000,    "_metainfo": {"…": "原 pick/_metainfo"}}, "next": "idle"}}}
```

---

## 4. 搬法（照 fn-grow「怎麼搬才不改行為」）

**順序：先寫新的、最後才改呼叫方（fsm.json）；每一步都能回頭。**

1. **複製兩份**：`cp -r galtxt-a ~/code/try/galtxt-collapse/before`、`…/after`，只動 `after`。
2. **資料表**（B-3）：寫 `data/cast.json`、`places.json`、`samples.json`；改 `brief/_entry` 讀法（三處 `load`、samples 的 `exists` → `in`）；跑 `aos-exec --ws ws after/brief` 一次（`AOS_STACK` 手給），`diff brief.json rules.json` 跟 `before` 的一樣後才 `git rm` 三個資料夾。`data/_metainfo.children` 改寫。
3. **lint 上提**：`git mv check/tools tools`（連 `lint/` 一起）。`check/_entry` 一字不改——它從 cwd 算 `tools/lint`，cwd 會在第 5 步從 `check/` 變成根。
4. **agent 上提**：`git mv write/tools/writer writer`、`git mv judge/tools/judge grader`；刪 `writer/idle/`、`grader/idle/`，各放捷徑 `ln -s ../idle idle`；`writer/tools/lint` 捷徑改成 `ln -s ../../tools/lint`。agent 內的檔**一個不動**。
5. **五格縮成腳本＋內嵌單子**：`git mv brief/_entry brief.py`（其餘四個同），**位置相關的值只改這幾處**：
   - `brief.py`、`pick.py`：`DATA` 少一層 `dirname`。
   - `write.py`、`judge.py`：`sys.path.insert` 的 `"..", "..", ".."` → `"..", ".."`；`run_agent` 的目標 `"tools/writer"` → `"writer"`、`"tools/judge"` → `"grader"`。
   - `check.py`：不改。
   - 不用 `__file__` 找旁邊檔的只有 check／write／judge（fn-grow 邊緣狀況）；五支都沒讀 `AOS_CF`／`AOS_CD`／`AOS_CO`（grep 過），沒有 `.env`，所以少掉的那一跳 aos-exec 沒有可觀察的差別（N-59 第 4 件讀 `.env`＝沒檔就什麼都不做；`AOS_STACK` 外層已設、沿用）。
   - 五個 `_metainfo` 的內容搬進 fsm.json 對應那格的單子（M1 第三處），`grow_level` 改 0，再刪五個資料夾。
6. **最後改呼叫方**：fsm.json 五格 `["aos-exec", "X"]` → `["python3", "X.py"]`（先寫 `.fsm.json` 再改名，N-05）。cwd 不變（aos-fsm 跑內嵌單子時 cwd＝fsm.json 的資料夾＝原本 `aos-exec X` 的呼叫 cwd），所以單子不必補 `cwd`。
7. **證明**（兩份各跑、假腦）：
   - `Q01.json`、`scene.json` 各一次、兩題一起放一次（換題清舊草稿那條）；`AOS_BRAIN_URL=http://127.0.0.1:9/v1` 失敗那條一次。
   - 比：`diff -r before/ws/out after/ws/out`（answer.txt、score.json 全同——假腦是模板，確定性）；`diff -r` 兩邊 `.stack/` 但略過 `trace.jsonl`、`usage.jsonl`、`state.txt` 以外含時間的檔（`brief.json`、`rules.json`、`drafts/*`、`checks.json`、`judge.json`、`writer/runs/*/stack/history.jsonl`、`judge/runs/*/stack/history.jsonl` 都要一樣）；`trace.jsonl` 抹掉 `elapsed_ms`、`started_at` 後 `state`／`code`／`signal` 序列一樣；結束碼一樣；失敗那條 stderr 的兩行（`writer: BrainFailed`、`galtxt-a write: AgentFailed`）一樣、`state.txt` 都是 `write`。
   - 不保證一樣、要記進 README 的：trace 裡五格的「誰」沒變（本來就是內嵌單子）；但 aos-exec 找不到 `brief/` 那種環境錯以前是 `aos-exec: EntryMissing`，現在是 python 的 `can't open file`——只有字不同。
8. **測試**（`proto8/tests/test_topdown_galtxt_a.py`）只改路徑與讀法，斷言不改：`LINT = G/"tools"/"lint"`；捷徑斷言改成 `writer/tools/lint → ../../tools/lint`、`writer/idle`、`grader/idle → ../idle`；`test_metainfo_consistent` 的 `self.meta("write")` 五格改讀 `fsm.json#/states/<名>/exec/_metainfo`、agent 路徑改 `writer`／`grader`、「fs_needs 空的資料夾只有 `_entry`＋`_metainfo`」那條改成「fs_needs 空的格一律是內嵌單子」；`test_write_skips_existing_drafts` 單獨跑一格改用 `aos-exec G/fsm.json#/states/brief/exec`（N-62，cwd＝根）；metatable 測試的「有捷徑列」照舊。
9. **文件**：README 的樹、`meta/table-round2.md`（收攏後重收一次表）、code map（鐵律 3）。

---

## 5. 工具缺口

**aos-grow `down` 現在一件都做不到**（讀了 `proto8/grow/aos-grow` 的 `down()`）：

| 要做的 | aos-grow down | 卡在哪 |
|---|---|---|
| 資料夾（`_entry`＋`_metainfo`）→ 單檔／內嵌 | ✗ | 「`X/` 裡不只 `_entry`（`_metainfo`），縮不回單檔」＝`TargetBad`——它不認 `_metainfo` |
| `_entry` 是腳本的資料夾 → 腳本＋內嵌單子（B-2） | ✗ | 「`_entry` 是可執行檔，不是單子」＝`TargetBad` |
| 併純容器 `tools/`（A-1）、改捷徑目標 | ✗ | 沒這功能 |
| 資料表資料夾 → 一份 JSON（B-3） | ✗ | 沒這功能 |
| 去重成捷徑（B-4） | ✗ | 沒這功能 |

不能改共用的 `proto8/grow`（本輪範圍）。**決定：在 `galtxt-a/meta/` 做兩個小原型**，都是 Python 標準庫、錯誤照 C-54 一行一代號、退 1：

1. **`metatable --suggest`**（加在現有 `meta/metatable/_entry`）：收完表之後套 § 1 的判準，多印一張「候選表」：`| path | 判準 | 動作 | 理由 | 要改的呼叫方 |`。要多掃三樣：`_entry` 有沒有 `+x`、資料夾裡還有哪些檔、同內容葉片（`_entry`＋`_metainfo` 的 hash）。`callers` 先讀 `_metainfo` 手填的，之後再改成掃 argv／`exec`／`run_agent` 字串。`--json` 時候選表放 `summary.suggest`。範圍：只列、不做；N-1 的條件缺資訊時列成「要人判」。
2. **`meta/collapse`**（新資料夾程式）：`collapse [--dry-run] inline fsm.json#/states/X/exec`（B-2：資料夾 `X/` → `X.py`＋那格內嵌單子＋`_metainfo` 併入；腳本裡出現 `__file__`、`AOS_CF`／`AOS_CD`／`AOS_CO` 就印「手改清單」而不是拒絕）、`collapse [--dry-run] unwrap X/tools`（A-1：上提、找整棵樹裡指進去的捷徑改相對目標）、`collapse [--dry-run] table data/cast`（B-3：併成 `cast.json`、頂層 `source`、`_metainfo` 併進上一層 `children`）、`collapse [--dry-run] dedupe idle writer/idle grader/idle`（B-4）。`--dry-run` 印新檔全文、diff、搬／刪清單（同 aos-grow）。做法照 fn-grow：先寫 `.名字` 暫存再改名、最後才改呼叫方。**不做**：改腳本裡的 `sys.path`／`DATA`（只印清單）、改測試。
   驗收：對 `before` 跑四個子命令得到的樹，跟手搬的 `after` `diff -r` 一樣（捷徑比目標字串）。

共用 aos-grow 該不該學這些（給頂層的建議，不在本輪做）：`down` 應該**吃 `_metainfo`**（縮時併進單子，就是 fn-grow「長大時留在單子裡」的反向）與**吃可執行入口**（當伴隨檔搬）——不然任何照規範寫了 `_metainfo` 的資料夾它都縮不回去，等於白做。

---

## 6. 收攏後 `_metainfo` 怎麼跟著走

| 原來在哪 | 收攏後在哪 | 規則 |
|---|---|---|
| `brief/_metainfo` 等五份（資料夾那處） | fsm.json 對應那格單子裡的 `_metainfo` key（M1 第三處） | fn-grow「長大時留在單子裡」反過來：縮回時整份搬回單子；內容原文、只改 `grow_level` 0。kernel 第一版本來就只讀單子裡的（metainfo 02），所以對 kernel 來說反而更直接 |
| `write/tools/writer/_metainfo`、`judge/tools/judge/_metainfo` | `writer/_metainfo`、`grader/_metainfo`（跟著資料夾搬） | 不改內容；`callers` 1 照舊（叫它的是 write.py／judge.py） |
| `check/tools/lint/_metainfo` | `tools/lint/_metainfo` | 不改；`callers` 2 照舊 |
| `writer/idle/_metainfo`、`judge/idle/_metainfo` | 刪（捷徑指到根 `idle/_metainfo`） | M1 § 2「沿路遇到的第一份就是它的」：aos-exec 走捷徑進去看到的是真身那份；`callers` 1 → 3 |
| `data/cast/_metainfo` 等三份 | 併進 `data/_metainfo.children`（它本來就有這個 key） | 資料表不是函數，不在表裡放 `_metainfo` key（會跟資料混；C-72 的 `js["_metainfo"]` 留給「JSON 當資料夾程式」的情形） |
| 根 `_metainfo` | 不動；建議加 `companion_files: ["brief.py", …]`（round2-optimize § 2.4 提的 key，選填） | 讓 metatable 看得出根的第 4 級伴隨檔是哪些 |

metatable 已經會收 fsm.json 內嵌單子的 `_metainfo`（路徑列成 `fsm.json#/states/brief/exec`），所以收攏後不用改它就能出 `table-round2.md`；彙總那行「fs_needs 為空（收攏候選）」應該會變成只剩 `idle`（而它是 N-3 的真身）——這就是「收攏做完」的判準。
