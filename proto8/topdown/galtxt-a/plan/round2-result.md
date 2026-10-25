# galtxt-a 第二輪：收攏結果（實作者 opus，2026-10-25）

← 規劃 [round2-collapse.md](round2-collapse.md)｜背景 [round2-optimize.md](round2-optimize.md)｜表 [收攏前候選](../meta/suggest-round1.md)、[收攏後的表](../meta/table-round2.md)｜經驗 [lessons.md](lessons.md#實作者第二輪opus2026-10-25)

只寫事實與數字。試驗場在 `~/code/try/galtxt-collapse/`（`before/`、`after/`＝工具收的、`manual/`＝照規劃字面手搬的對照組；`do_collapse.py`、`do_manual.py`、`run_compare.py`、`compare_trees.py`、`count.py`）。

## 1. 數字

| | 收攏前（commit 2967009e） | 收攏後 |
|---|---|---|
| 資料夾（含根） | 25 | 14（13＋本輪新增的 `meta/collapse/`） |
| 真資料夾最大深度 | 4（`judge/tools/judge/idle`） | 2（`tools/lint`、`writer/tools`、`data/bench`、`meta/*`） |
| 捷徑數／含捷徑最大深度 | 1／5 | 3／3 |
| 檔數 | 68 | 60（含本輪新增的 collapse、suggest.py、兩張表、本檔） |
| metatable 列 | 24 | 22（21＋`meta/collapse`） |
| `--suggest` 候選 | 12 | 0 |
| git（暫存區、`-M`） | — | 24 R、18 D、11 A、8 M |

## 2. 前後兩棵樹

前：見 [round2-collapse.md § 3](round2-collapse.md#3-收攏前後兩棵樹)「前」，實際一致。

後：

```
galtxt-a/
├─ _entry _metainfo loop.json fsm.json README.md
├─ brief.py write.py check.py judge.py pick.py        ← fsm.json 五格是內嵌單子 ["python3", "X.py"]，各帶 _metainfo（grow_level 0）
├─ idle/                       _entry _metainfo（callers 1 → 3）
├─ tools/
│  └─ lint/                    _entry _metainfo tool.json
├─ writer/                     _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│  ├─ idle → ../idle
│  └─ tools/
│     └─ lint → ../../tools/lint
├─ grader/                     _entry _metainfo .env fsm.json loop.json brain.py act.py system.txt
│  └─ idle → ../idle
├─ data/                       _metainfo address.json forbidden.json styles.json cast.json places.json samples.json
│  └─ bench/                   _metainfo Q01.json
├─ meta/                       _metainfo table-round1.md table-round2.md suggest-round1.md
│  ├─ metatable/               _entry _metainfo suggest.py
│  └─ collapse/                _entry _metainfo
└─ plan/                       _metainfo round1.md round1-measure.md round2-*.md lessons.md side-mcp.md
   └─ examples/                _metainfo Q01.json scene.json
```

## 3. 工具

| 工具 | 介面 | 做到 | 做不到（印成手改清單或拒絕） |
|---|---|---|---|
| `meta/metatable --suggest` | `metatable [--json] [--suggest] [ROOT]`；候選表 `\| path \| 判準 \| 動作 \| 理由 \| 要改的呼叫方 \|`，`--json` 放 `summary.suggest` | N-1、N-2、N-3、A-1（含 tools/ 例外）、B-1、B-2（含 A-2 註記）、B-3（讀者從所有 `reads` 算）、B-4（整個資料夾 hash，先合計 callers） | 「要單檔 diff」「別的行程寫」只能靠 `fs_needs` 有人寫；`mount` 分不出掛別人／被掛，標「要人判」 |
| `meta/collapse inline CFG#/指標` | 那格 `"X"` 或 `["aos-exec", "X"]` → `["python3", "X.py"]`（sh 腳本 → `X.sh`），`_metainfo` 併進那格、`grow_level` 0；`X/` 還有子資料夾就留著並提示 unwrap | 5 格全做 | 腳本裡的 `__file__`、讀 `AOS_CF／CD／CO`、相對 cwd 的路徑字串：只列；agent、有伴隨檔、`fs_needs` 擋、`callers ≥ 2`、捷徑：拒絕 |
| `meta/collapse unwrap C [--name N]` | 只裝一個子資料夾的容器拿掉，子資料夾上提一層；整棵樹相對捷徑（連被搬的捷徑本身）改目標 | 5 次（`write/tools`、`judge/tools --name grader`、`write`、`judge`、`check`） | 一次只上提一層；腳本裡寫著舊路徑的字串只列 |
| `meta/collapse table D [--source S]` | `D/` → `D.json`（頂層 `source`），`_metainfo.summary` 併進上一層 `children`，所有 `reads` 的 `<上層>:<D>/…` → `<上層>:<D>.json` | 3 次（cast、places、samples） | 腳本裡拿資料夾名拼路徑的地方只列；`children` 的說明是原 summary 原文（「一人一張（<名>.json）」講的是舊長相） |
| `meta/collapse dedupe REAL COPY...` | COPY 跟 REAL 整個資料夾一樣 → 換相對捷徑，`callers` 加到真身 | 1 次（idle ×3） | — |

四個子命令都有 `--dry-run`（印搬／新檔全文／diff／刪／捷徑／手改清單，什麼都不寫）；錯 `collapse: 代號 原因` 退 1 什麼都不寫。`do_collapse.py` 每一步先 `--dry-run`、比對整棵樹沒變，再真的做。

## 4. 實際步驟（`~/code/try/galtxt-collapse/do_collapse.py`）

1. `table data/cast`、`table data/places`、`table data/samples`（`--source` 照規劃 § 2）＋手改 brief 讀法、`data/_metainfo` 的 children 說明
2. `unwrap write/tools`、`unwrap judge/tools --name grader`
3. `dedupe idle write/writer/idle judge/grader/idle`
4. `inline fsm.json#/states/{brief,write,check,judge,pick}/exec`
5. `unwrap write`、`unwrap judge`、`unwrap check`
6. 手改：`__file__` 兩處、`sys.path` 兩處、agent 目標字串兩處、註解五處

W 裡用同一支腳本收（輸出跟試驗場那次逐字一樣），`compare_trees.py` 比 `after/` 與 W：一樣；`git add` 後 git 認出 24 個 R。

## 5. 手改清單（工具做不到、人改的）

| 檔 | 改了什麼 | 工具有沒有列出來 |
|---|---|---|
| `brief.py` | `places/<名>.json` → `places.json` 的 key（找不到＝`PlaceMissing`） | 有（table） |
| `brief.py` | `cast/<名>.json` → 先讀 `cast.json`、再取 key（找不到＝`CastMissing`） | 有（table） |
| `brief.py` | `samples/<名>.json` 的 `exists` → `samples.json` 的 `in` | 有（table） |
| `brief.py`、`pick.py` | `DATA` 少一層 `dirname` | 有（inline，`__file__`） |
| `write.py`、`judge.py` | `sys.path` 的 `"..", "..", ".."` → `"..", ".."` | 有（inline，`__file__`） |
| `write.py` | `run_agent` 目標 `"tools/writer"` → `"writer"` | 有（unwrap、inline 各一次） |
| `judge.py` | `run_agent` 目標 `"tools/judge"` → `"grader"` | 有（unwrap、inline 各一次） |
| `check.py` | 不改程式（`tools/lint` 從 cwd＝根算正好對）；只改註解 | 有列（相對 cwd 的路徑），人判不用改 |
| `brief.py`、`pick.py`、`write.py`、`judge.py` | 註解裡的舊位置（`../data`、`tools/writer`、`tools/judge`） | 沒有（註解不掃） |
| `data/_metainfo` | `children` 三條改成規劃 § 2 的字（「人物卡 {名: 卡}」…）、`bench` → `bench/` | 沒有 |

## 6. 證明

**同題假腦（`run_compare.py`，before 對 after，也對 W 跑過一次）**：比結束碼、stderr（路徑換成 `<RUN>`、`<TREE>`）、`ws/` 底下每個檔（含 `.stack/` 整棵與寫手、評審的小格；JSON／JSONL 只拿掉 `started_at`、`elapsed_ms`，其餘逐字）。

| 情境 | 結束碼 前／後 | ws 檔數 前／後 | 結果 |
|---|---|---|---|
| Q01 | 0／0 | 46／46 | 一樣 |
| scene | 0／0 | 52／52 | 一樣 |
| 兩題連放（Q01＋scene） | 0／0 | 88／88 | 一樣 |
| 腦掛掉（`AOS_BRAIN_URL=http://127.0.0.1:9/v1`） | 1／1 | 12／12 | 一樣；stderr 四行一樣（`writer: BrainFailed`、`galtxt-a write: AgentFailed`…），`state.txt` 都是 `write` |

**比對會變紅**：after 複本把 `write.py` 的 HINTS 換順序，Q01 抓出 11 個檔不同（drafts、checks、judge、score…）。

**工具對照手搬**（§ 5 驗收）：`compare_trees.py after manual`（捷徑比目標字串、JSON 比值）只差一處：`fsm.json` 裡 brief 的 `_metainfo.reads`——工具把 `data:cast/*`、`data:places/*`、`data:samples/*` 改成 `data:*.json`，照規劃字面手搬的沒改。W 用的是工具版。

**測試** `proto8/tests/test_topdown_galtxt_a.py`：12 → 19 個，全綠（含 `test_real_model`：這次 LiteLLM 連得上、跑的是收攏後的樹，結束碼 0）。

- 原 12 個只改路徑與讀法：`LINT`、捷徑兩條（另加 `writer/idle`、`grader/idle` → `../idle`）、`brief`／`write` 單跑改 `fsm.json#/states/<名>/exec`、五格 `_metainfo` 改讀 `fsm.json` 那格、agent 路徑 `writer`／`grader`。
- 新 7 個：`CollapseT`（`--dry-run` 四個子命令都不寫檔、inline 後同一格跑出的 `out.txt`／`state.txt`／trace 序列一樣、unwrap＋dedupe＋table 的結果、五種錯都退 1 不寫檔）、`SuggestT`（從 git 拿 2967009e 的樹：brief／pick／write／check／judge＝B-2、cast／places／samples＝B-3、兩個 tools/＝A-1、兩份 idle＝B-4、idle／data／bench／lint／agent 不列；小樹的候選；收攏後的樹 0 個）。
- 變紅：`--dry-run` 改成照做 → `test_dry_run_writes_nothing` 紅；拿掉 A-1 的 tools/ 例外 → `test_after_tree_lists_nothing`、`test_before_tree_lists_candidates` 紅。改回全綠。

## 7. 偏離規劃的地方

1. **順序**：規劃 § 4 是 資料表 → lint 上提 → agent 上提 → 五格縮 → 改 fsm。用工具時 unwrap 一次只能上一層、而且只收「只裝一個子資料夾」的容器，所以變成 資料表 → 拆 `write/tools`、`judge/tools` → 去重 → 五格 inline（每格當下就改 fsm.json 那一格）→ 拆 `write/`、`judge/`、`check/`。中間狀態跑不起來（例：inline check 後、unwrap check 前，`tools/lint` 還在 `check/tools/`），只看最後結果。
2. **check 的 `_metainfo`**：§ 2 表寫收攏後 `fs_needs: []`，§ 6 寫「內容原文、只改 grow_level」；照 § 6，`fs_needs` 仍是 `["mount"]`（write、judge 也是）。
3. **brief 的 `reads`**：規劃沒寫，工具 `table` 順手改了（見 § 6 工具對照手搬）。
4. **判準的兩處解讀**（`--suggest`）：N-1 的 `mount` 只在 agent 或有 `tool.json` 時擋，其餘標「要人判」——照字面 write／check／judge 都會被擋，跟 § 2 的裁決打架；N-2 只數伴隨檔、不看 `grow_level`——check 的 `grow_level` 4 是因為底下有 `tools/`，照字面會不縮。
5. **「收攏做完」的判準**：§ 6 預期 metatable 舊彙總「fs_needs 為空」只剩 idle；實際是 `fsm.json#/states/brief/exec`、`…/pick/exec`、`idle`（內嵌單子也被數進去）。改用 `--suggest` 候選 0 當判準；舊彙總沒動。
6. **測試 `test_metainfo_consistent`**：§ 4 第 8 步說把「fs_needs 空的資料夾只有 `_entry`＋`_metainfo`」改成「fs_needs 空的格一律是內嵌單子」；但 idle 這格 `fs_needs` 空、是資料夾，改了會不成立，所以原條保留（現在只驗到 idle）。
7. **數字**：資料夾 13 → 14、metatable 21 → 22 列，多的是本輪新增的 `meta/collapse/`。
8. **沒做**：根 `_metainfo` 的選填 `companion_files`；code map（galtxt-a 本來就不在 code map，留給 commit 時補）；O-5（write／judge 併成一支）照規劃不在本輪。
9. **證明環境**：複本不在 repo 裡，write／judge 的 `sys.path` 相對路徑指不到 `proto8/lib/agent`，`run_compare.py` 兩邊都補 `PYTHONPATH`；W 裡的樹不需要（測試裡跑的就是）。

## 8. 事故

`run_compare.py` 第一次對 W 跑時把 W 的絕對路徑當成 side，`os.path.join(runs, 情境, 絕對路徑)` 得到那棵樹本身，`shutil.rmtree` 把 W 的 galtxt-a 整棵刪了。收攏結果已在 git 暫存區，`git restore --worktree` 救回、`compare_trees.py` 比 `after/` 一樣；暫存之後的 README 與兩份 `_metainfo` 重做。`run_compare.py` 已改成跑處固定在 `runs/<情境>/{before,after}`、跑前 assert 不在受測的樹裡。
