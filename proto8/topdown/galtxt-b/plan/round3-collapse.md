# galtxt-b 第 3 輪 B：反向收攏（只規劃、不實作；fable，2026-10-25）

← [galtxt-b](../README.md)｜前情：[round1](round1.md)、[round2](round2.md)、[optimize](optimize.md)（只看表的盤點）｜依據：[函數成長六級與縮回](../../../thinking/2026-10-24-fn-grow.md)、C-72（JSON＝單檔的檔案系統）、C-64（借檔案權限）、C-61／P-33（工具放在格自己的 `tools/<名>/`）、P-41（腦叫的工具要 `tool.json` 資料夾）、[`_metainfo` M1](../../../thinking/2026-10-24-metainfo.md)（三處同名）、[wf/STRUCTURE 門檻](../../../../wf/STRUCTURE.md)（8 KB、300 行、小檔太多就併）｜這次看了樹、程式與實跑數字（metainfo_table、runs/round2）。

使用者 10-25 原話：「資料夾嵌套太深太多層，需要將一些中間層糅合成一個資料夾，或者是尾端葉片縮成json（我們已經把資料夾和json綁在一起了，所以要考慮權限等檔案系統特性需求的情況下）」。

## 1. 判準（通用表，先定再套）

兩種動作：**併**（中間層太薄→併進上一層或兄弟）、**縮**（尾端葉片往 fn-grow 低一級退：5 有子函數的資料夾 → 4 資料夾有伴隨檔 → 3 只有入口的資料夾 → 2 單檔 `x.json` → 1 同檔具名 → 0 內嵌）。每個節點先問「要不要檔案系統特性」，要就停手；不要再問「夠不夠薄」。

| # | 要檔案系統特性的情況（**不縮、不併**） | 為什麼 JSON 給不了 |
|---|---|---|
| F1 | 入口是可執行檔（shebang 腳本、`+x`） | JSON 物件裡放不了可執行位；aos-exec 看到 `+x` 才 exec（N-61）；改寫成單子就得 `sh -c`（少用 sh） |
| F2 | 是捷徑的目標、或本身是捷徑 | 捷徑指向的是路徑；C-61「相對捷徑、兩份一起搬也不斷」靠的是資料夾 |
| F3 | 要被腦當工具叫 | P-41：工具＝`tools/<名>/` 資料夾＋`tool.json`，brain 掃資料夾組 tools 陣列 |
| F4 | 要借權限／擁有者（C-64）、沙箱綁路徑（lib 契約 4：`$AOS_WS`） | 權限是檔案與資料夾的屬性，JSON 的 key 沒有 |
| F5 | 要被別的行程獨立寫（flock、暫存檔改名 N-05）、或被 git 單獨追蹤／審閱 | 幾個寫者共用一份 JSON＝互相蓋掉；審閱時一檔一主題比一大檔的 diff 好看 |
| F6 | 大（> 8 KB 或 > 300 行）或二進位 | STRUCTURE 門檻反向：併回去會超標 |
| F7 | 自己要保管跨呼叫的東西（有自己的 stack／小格、要能續聊、要 resumable） | 那是 agent（第 5 級）成立的理由（fn-grow 觸發點） |
| F8 | 被 ≥ 2 處叫（函數成長第 2 級的觸發點） | 內嵌回去就得複製兩份 |

| # | 夠薄、該動的訊號（沒撞到 F1～F8 才看） | 動作 |
|---|---|---|
| T1 | 一層資料夾裡只有一個子項、自己沒有別的內容（純容器） | 併：子項上提一層 |
| T2 | 第 5 級（有 loop／fsm）但實際只走一次 think→act、沒有工具、不續聊 | 縮到第 4 級：一張 `_entry` 單子＋一支腳本 |
| T3 | 第 3／4 級但入口是單子、沒有伴隨檔 | 縮到第 2 級 `x.json`；只有一處叫就再縮到第 0 級內嵌 |
| T4 | 幾個 JSON 資料檔同主題、合起來 < 8 KB、同一個讀者、沒有權限分工 | C-72：縮成一份 JSON、檔名當 key |
| T5 | 兩個格一個只做「交給下一格」、程式 < 30 行、沒有自己的錯誤路徑 | 併進相鄰格 |
| T6 | 捷徑指到的 lib 函數只剩一個呼叫者 | 搬回呼叫者的 `tools/<名>/`（真資料夾），lib 少一項 |

`_metainfo` 跟著動（M1 三處同名）：資料夾縮成單子＝`X/_metainfo` 的內容併進單子的 `_metainfo` key；縮成 JSON 物件＝`js["_metainfo"]`；併層＝被併掉那層的 `_metainfo` 刪、上層 `summary` 補一句。`reads`／`writes`／`calls`／`callers` 改成新路徑。

## 2. 逐個套（現在的樹，38 個資料夾／檔案節點）

| 節點 | 現況（級、檔數、行數、實測） | 撞到哪條 F | 薄不薄（T） | 判定 |
|---|---|---|---|---|
| `galtxt-b/`（`_entry`＋`loop.json`＋`fsm.json`） | 第 5 級；`loop.json` 1 行、`fsm.json` 9 行 | F1（`_entry` 是 sh）、F7（頂層 agent） | — | **不動**。`loop.json` 與 `fsm.json` 兩個小檔是範本的形（P-05／P-06）；併成一份要改範本，不在這裡做 |
| `idle/`（sh 4 行） | 第 3 級 | **F1** | T3 像 | **不縮**：sh 邏輯縮成單子只能 `sh -c`。四個 idle（頂層、director、writer、critic）內容一樣，但各自的 agent 要能整隻搬走（C-61），不抽共用 |
| `brief/`（134 行＋`tables/`） | 第 4 級 | — | 不薄 | **不動** |
| `brief/tables/`（7 份 JSON、共 13.2 KB） | data | **F6**（併成一份 13 KB > 8 KB）、**F4 預留**（之後 distill 寫、writer 只讀，要分權限） | T4 不成立（超標） | **不縮**。若之後只剩 cast／places 兩份常改、其餘幾乎不動，再考慮分「常改」「不動」兩份 |
| `draft/`（108 行；叫三個工具） | 第 4 級黏合格 | — | 不薄（兩步、自己的錯誤路徑 9 種） | **不動** |
| `draft/tools/`（director、plan_lint→、writer） | 容器 | — | 三個子項，不是 T1 | **不動** |
| **`draft/tools/director/`**（第 5 級：loop／fsm／idle／brain 172 行／act 41 行／system／.env；實測每題問腦 1 次、無工具、一題結束就清小格） | 第 5 級 | F7？——它「續聊」只在 plan_lint 打回時（實測兩題 0 次）；history 與 llm.jsonl 仍要留在自己的小格，但那不需要 loop／fsm | **T2 成立** | **縮到第 4 級**：`director/_entry`＝單子 `{"argv": ["python3", "ask.py"], "timeout_ms": 120000, "_metainfo": …}`，`ask.py`＝brain 的 render＋ask＋record 加 act 的「寫 out/<n>.txt、cur→done」合成一支（brain 172＋act 41 → 約 170 行）；刪 `loop.json`、`fsm.json`、`idle/`、`act.py`。打回重出表照舊：draft 黏合格再叫一次同一個小格，`ask.py` 讀到 history 最後一則是 assistant 就接新的 user（feedback）。實測開銷 71 ms（5643−5572）會變 0，時間上無感；省 5 檔 1 資料夾 |
| `draft/tools/plan_lint`（捷徑 → `lib/plan_lint`，**只有這一個呼叫者**） | link | F2（捷徑本身） | **T6 成立** | **搬回**：`lib/plan_lint/` → `draft/tools/plan_lint/`（真資料夾，三個檔原樣），捷徑刪；`lib/_metainfo` 的 summary 改「現在只有 lint」。round2 讓它進 lib 是預期 director 會自檢，沒發生；director 縮成單發之後更不會 |
| **`draft/tools/writer/`**（第 5 級；實測每題問腦 2 次、有工具 lint、第 2 稿續聊） | 第 5 級 | **F7**（續聊、resumable）、**F3**（它叫工具） | — | **不縮**。它是這棵樹裡唯一名副其實的 agent |
| `draft/tools/writer/tools/`（只有 `lint` 一條捷徑） | 容器 | **F3**（P-41 要 `tools/<名>/tool.json`） | T1 像 | **不併**：這層是腦找工具的地址，慣例定死 |
| `draft/tools/writer/idle/` | 第 3 級 sh | F1 | — | 不縮（同頂層 idle） |
| `check/`（65 行） | 黏合格 | — | 薄：叫 lint、算 pass／final、寫檔；但有自己的錯誤路徑、trace 一行、`history` 累積 | **不併**（T5 不成立：它做的「pass／final 判定」是一條規則、不只是轉交）。併進 draft 尾巴會讓 draft 一格做「產」與「判」兩件事，之後要換判定規則得動 draft；留一格換來的是 45 ms 與一個 `check/_entry`，划算 |
| `check/tools/`（只有 `lint` 一條捷徑） | 容器 | F2／慣例 P-33 | T1 像 | **不併，但這是整棵樹唯一的方向性問題**（round1 §7-6）：格叫的純函數要不要免掉 `tools/` 這層（寫 `check/lint →` 捷徑、格裡 `aos-exec lint`）。P-33 是慣例不是規範；我的建議是**留**（一詞一義：`tools/` 永遠是「這格叫的東西」），等使用者定 |
| `judge/`（87 行）＋`judge/tools/`（只有 critic） | 黏合格＋容器 | 同上 | 同上 | **不併**（同 check／tools） |
| `judge/benchmarks/`（2 份 JSON、4.1 KB） | data | **F5**（一題一檔、之後會長到 19 題，一題一 commit、一題一審）；C-54「裝同類用複數資料夾」 | T4 看起來成立（< 8 KB） | **不縮**：合起來現在 4 KB，但它是「會長的清單」，縮了之後第 5 題就得再拆回來 |
| **`judge/tools/critic/`**（第 5 級；實測問腦 1 次、無工具、每次清小格、不續聊） | 第 5 級 | 無（連續聊都沒有） | **T2 成立，比 director 更乾淨** | **縮到第 4 級**：`critic/_entry` 單子＋`ask.py`（同 director 的做法）；刪 loop／fsm／idle／act。round1 就標了 `shrink_candidate` |
| `deliver/`（**134 行**：交件＋量測彙整） | 第 4 級 | — | 不薄了——round1、round2 說它「太薄、會被收」，第 2 輪加了 measure 之後它讀 9 種輸入、算 7 個 counter | **不併**；撤回 `shrink_candidate`。反而要問要不要**拆**：量測彙整（`measure()` 約 45 行）跟交件是兩件事——但只有 deliver 一個呼叫者（F8 反向），先不拆，`_metainfo.summary` 改掉「仍薄」那句 |
| `lib/`（lint、plan_lint） | 容器 | F8（lint 兩個呼叫者） | plan_lint 搬走後剩一項 | **留**：一個函數的函式庫仍是函式庫；兩條捷徑指著它 |
| `lib/lint/`（187 行，兩個呼叫者） | 第 4 級 | **F2、F3、F8** | — | **不動** |
| `examples/`（2 份 JSON） | data | — | T4：合成一份 `examples.json`？ | **不動**：它們是「複製到 `new/` 就能跑」的題目檔，一題一檔是題目的形狀（P-11），合併反而要先拆開才能用 |
| 三隻 agent 的 `.env`（2 行）、`system.txt` | 伴隨檔 | `.env` 是 dotenv 生態（C-51 例外）、system.txt 是 prompt 文字 | — | **不動**：`.env` 的 `AOS_BRAIN_MODEL` 搬進單子 `envs` 可以，但就不能從外面 `aos-exec --dotenv-override` 蓋了；system.txt 塞進 JSON 字串會讓多行 prompt 難改 |
| 各 `tools/_metainfo`（2 行）、`idle/_metainfo` | 資料 | 使用者「每個資料夾」 | — | 不動 |

**總結**：併 0 層（唯一的候選 `check/tools/`、`judge/tools/` 留給使用者裁）、縮 2 個（director、critic：5→4）、搬回 1 個（plan_lint 出 lib）、撤回 1 個預測（deliver）。整棵樹 23 個資料夾 → 21 個（少 2 個 idle）；檔案 76 → 66（少 2×loop.json、fsm.json、act.py、idle/_entry、idle/_metainfo；多 2 個 ask.py；plan_lint 三個檔搬家不增減）。沒有任何葉片縮成 JSON 物件：撞到的全是 F1（sh 入口）、F3（腦要叫）、F5／F6（資料檔）。

## 3. 收攏前後的樹

**前（第 2 輪實作後）**：

```
galtxt-b/
  _entry  loop.json  fsm.json  _metainfo  README.md  demo.sh
  lib/            lint/{_entry,tool.json,_metainfo}   plan_lint/{_entry,tool.json,_metainfo}
  idle/           _entry _metainfo
  brief/          _entry _metainfo  tables/{7 json,_metainfo}
  draft/          _entry _metainfo
    tools/        _metainfo  plan_lint → ../../lib/plan_lint
      director/   _entry loop.json fsm.json .env system.txt brain.py act.py _metainfo  idle/{_entry,_metainfo}
      writer/     _entry loop.json fsm.json .env system.txt brain.py act.py _metainfo  idle/{_entry,_metainfo}  tools/{_metainfo, lint → ../../../../lib/lint}
  check/          _entry _metainfo  tools/{_metainfo, lint → ../../lib/lint}
  judge/          _entry _metainfo  benchmarks/{q01,q08,_metainfo}
    tools/        _metainfo
      critic/     _entry loop.json fsm.json .env system.txt brain.py act.py _metainfo  idle/{_entry,_metainfo}
  deliver/        _entry _metainfo
  examples/       q01 q08 _metainfo
```

**後**：

```
galtxt-b/
  _entry  loop.json  fsm.json  _metainfo  README.md  demo.sh
  lib/            lint/{_entry,tool.json,_metainfo}                        ← plan_lint 搬走，只剩 lint（兩個呼叫者）
  idle/           _entry _metainfo
  brief/          _entry _metainfo  tables/{7 json,_metainfo}
  draft/          _entry _metainfo
    tools/        _metainfo
      plan_lint/  _entry tool.json _metainfo                                ← 真資料夾（原 lib/plan_lint）
      director/   _entry(單子，不 +x) ask.py .env system.txt _metainfo      ← 第 4 級：單發腦函數
      writer/     _entry loop.json fsm.json .env system.txt brain.py act.py _metainfo  idle/  tools/{lint →}   ← 不變
  check/          _entry _metainfo  tools/{_metainfo, lint → ../../lib/lint}
  judge/          _entry _metainfo  benchmarks/{q01,q08,_metainfo}
    tools/        _metainfo
      critic/     _entry(單子，不 +x) ask.py .env system.txt _metainfo      ← 第 4 級：單發腦函數
  deliver/        _entry _metainfo
  examples/       q01 q08 _metainfo
```

`director/_entry` 與 `critic/_entry`（JSON 單子，沒有 `+x`、沒有 shebang，P-40）：

```json
{"argv": ["python3", "ask.py"], "timeout_ms": 120000,
 "_metainfo": {"summary": "單發腦函數：工作區 new/<n>.json 的題目問腦一次、答案寫 out/<n>.txt；同一小格再叫＝接著 history 問",
               "time_ms": {"val": 5700, "max": 120000}, "resource": ["llm", "cpu"],
               "llm_calls": {"val": 1, "max": 1}, "llm_tokens": {"val": 3400, "max": 4500},
               "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
               "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "safe", "parallel": true,
               "reads": ["$AOS_WS/new/*.json", "$AOS_WS/cur/*.json", "$AOS_STACK/history.jsonl", "system.txt"],
               "writes": ["$AOS_WS/out/<n>.txt", "$AOS_WS/done/", "$AOS_STACK/{history.jsonl,current.txt,llm.jsonl}"],
               "grow_level": 4, "unit": "call"}}
```

資料夾的 `director/_metainfo` 保留（M1：資料夾那處優先、外層贏），內容同單子裡的那份（`shape` 改「單發腦函數（_entry 單子＋ask.py）」）；單子裡那份是給「直接叫 `aos-exec director/_entry`」的人看的——兩份一樣，實作者擇一也行（建議只留資料夾的，單子裡放 `{"$ref": "_metainfo"}`——`_metainfo` 可用 `$ref`，M 01 §5）。`interrupt` 從 `resumable` 改 `safe`：沒有 state.txt 了，殺掉重跑就是整個再問一次（history 不接半則：ask 失敗時不寫）。

## 4. 給實作者的工作清單（照 fn-grow「怎麼搬」四步）

每一步：**① 先寫新的、最後才改呼叫方；② 只改位置相關的值、指回原處；③ 伴隨檔一起搬；④ 複製兩份、只動一份，同題跑兩份對照。**

### 步驟 1：plan_lint 搬回 draft/tools/

1. `git mv lib/plan_lint draft/tools/plan_lint.real`（先放旁邊）；`rm draft/tools/plan_lint`（捷徑）；`git mv draft/tools/plan_lint.real draft/tools/plan_lint`。三個檔內容不動（它自成一格、不 import 隔壁，搬到哪都跑得動）。
2. `draft/tools/plan_lint/_metainfo`：`callers` 改 `["draft/（黏合格）"]`；`lib/_metainfo` summary 改「只有 lint」；`draft/tools/_metainfo` summary 把「相對捷徑指 lib/plan_lint」改成「真資料夾」。
3. `draft/_entry` 不用改（它寫的是 `aos-exec tools/plan_lint`，走進真資料夾跟走進捷徑一樣）。
4. 測試：`test_links` 的表拿掉 `draft/tools/plan_lint`；`test_plan_lint_*` 的路徑從 `lib/plan_lint` 改 `draft/tools/plan_lint`；`test_real_tree_runs` 的 `rows` 集合把 `lib/plan_lint` 換掉（若有）。

### 步驟 2：critic 5→4（先做這個，它最單純）

1. 新寫 `judge/tools/critic/ask.py`：把 `brain.py` 的 `ls`／認領／`render`／history 讀寫／`fake`／`ask`／`record` 原樣搬，加上 `act.py` 的尾巴（取 history 最後一則 assistant 的 content，寫 `out/<n>.txt`、`cur/→done/`）；`tool_calls`＝`ReplyBad`（critic 沒工具，照現在 act 的規則）。失敗（`BrainFailed`、`ReplyBad`）＝history 不接、不寫答案、退 1（同現在的 think 格）。
2. 新寫 `_entry`（上面那張單子；**不設 `+x`**、沒 shebang）。資料夾 `_metainfo` 照 §3 改。
3. 刪 `loop.json`、`fsm.json`、`act.py`、`brain.py`、`idle/`（最後才刪——先讓兩版並存跑對照）。
4. 呼叫方 `judge/_entry` 不改：它 `aos-exec --ws … tools/critic`，aos-exec 找到 `critic/_entry` 是沒 `+x` 的 JSON 單子就行程內跑（N-61）。小格裡不再有 `state.txt`／`trace.jsonl`，只有 `history.jsonl`、`current.txt`、`llm.jsonl`、`ws/`。
5. 量測：`deliver/_entry` 的 `measure()` 算 agents 的 `elapsed_ms` 是從小格 `trace.jsonl` 加總——critic 沒有 trace 了，改成：有 trace 用 trace，沒有就用 `llm.jsonl` 的 `elapsed_ms` 加總（＝`llm_elapsed_ms`）再加一個固定 0（或由 judge 黏合格量 `subprocess.run` 前後的時間寫進 `score.json` 的 `critic_elapsed_ms`，deliver 拿那個——後者準，建議這個）。
6. 測試：`test_q01`／`test_q08_redraft` 若有斷言 critic 小格的 `trace.jsonl` 行數或 `state.txt`，改成斷言 `history.jsonl` 兩則（user、assistant）與 `llm.jsonl` 一行；`test_metainfo_everywhere` 的 `seen > 20` 仍成立（23 → 21）。

### 步驟 3：director 5→4

同步驟 2，差別：
1. `ask.py` 要處理「同一小格被叫第二次」：history 最後一則是 assistant → 接新的 user（feedback）再問，跟現在 brain.py 的 `if not history or history[-1].role not in (user, tool)` 一樣，不用改邏輯。
2. `draft/_entry` 的 `make_plan()` 不改（它每次「沒 plan.json」清小格、打回時同小格再叫一次；對單子入口一樣成立）。
3. 假腦開關 `GALTXT_FAKE_BAD_PLAN=n` 原樣搬進 ask.py；`test_plan_bad_twice_then_resume`、`test_plan_bad_once_recovers` 照跑。
4. `draft/_metainfo` 的 `calls` 文字改「tools/director（單發腦函數）」。

### 步驟 4：deliver 與文件

1. `deliver/_metainfo` 刪 `shrink_candidate`、`summary` 去掉「仍薄」；`reads` 把 `{writer,director,critic}/{llm.jsonl,trace.jsonl}` 改成「writer 的 trace、三者的 llm.jsonl」。
2. `README.md` 的樹改成 §3「後」的樣子；`metainfo_table.py` 重跑，`plan/metainfo_table.{json,md}` 更新（表上 director／critic 的 `fsm.json#/states/think/exec` 兩列消失、改成 `director/_entry` 單子列——表的收單子邏輯要認「`_entry` 是單子」這種，現在只認 fsm.json 裡的）。
3. 所有改動都是「位置相關的值」：`ask.py` 用 cwd 相對路徑找 `system.txt`、`tools/`（現在 brain.py 就是這樣，不用 `__file__`），單子的 `cwd` 不寫＝入口所在資料夾（N-59）——所以 ② 沒有要改的值；`.env` 照舊被 aos-exec 讀（走進 `critic/` 那一跳）。

### 驗收

- `python3 -m unittest proto8/tests/test_topdown_galtxt_b.py`：23 條照過（改路徑的那幾條之外，斷言不變）。
- `sh proto8/topdown/galtxt-b/demo.sh`：三段結束碼 0（q01、q08 打回、q01 自檢）。
- **行為不變的證明（fn-grow 第 ④ 步）**：收攏前後各一份樹（`cp -a` 到暫存），同一個工作區複本、同一題、假腦、`GALTXT_FAKE_BAD_FIRST`／`GALTXT_FAKE_LINT`／`GALTXT_FAKE_BAD_PLAN=1` 各跑一次，比對 `out/<題名>/{answer.txt,check.json,score.json}` 逐位元相同（`measure.json` 抹掉時間欄位後相同）；`.stack/` 除了 director／critic 小格少了 `state.txt`、`trace.jsonl` 之外其餘檔逐位元相同。
- 真腦 Q01、Q08 各再跑一次，跟 `plan/runs/round2/` 對照：分數在 ±1 內（腦本來就不確定，不要求相同）、`counter_llm_calls` 相同（4／4）、`counter_tokens` ±10%、`agents.director.elapsed_ms`／`critic.elapsed_ms` 各少約 70 ms（流程開銷）。寫進 `plan/runs/round3/`。

## 5. `proto8/grow/aos-grow down` 夠不夠用

看了 `grow/README.md` 與 `grow/aos-grow`（377 行）。它的 `down` 只做一件事：`NAME/`（**只剩 `_entry` 且是單子**）→ `NAME.json` → 內嵌回呼叫方那格，而且只搬**單子**。對照這輪要做的四種動作：

| 這輪要做的 | aos-grow down 做得到嗎 | 缺什麼 |
|---|---|---|
| director／critic 5→4（有 loop／fsm／idle／act／brain 的資料夾 → `_entry` 單子＋一支腳本） | 不行：`rest` 非空就 `TargetBad`（「裡不只 _entry」） | ① 認得「agent 範本」的形（loop.json→fsm.json→idle／think／act）；② 把 fsm 的 think 單子升成資料夾的 `_entry`、act 的工作併進腳本——**併腳本是語意工作，工具做不了**，但刪範本檔、寫新 `_entry`、搬 `_metainfo`、dry-run diff 可以 |
| 捷徑 → 真資料夾（plan_lint 出 lib） | 不行：它不認捷徑（`os.path.isdir(fdir)` 會跟著捷徑走進 lib、然後說「裡不只 _entry」） | ③ `link` 動作：解開捷徑、複製（或 git mv）目標、改 `callers`、lib 空了就刪 |
| 併中間層（`check/tools/` 只有一個子項） | 不行 | ④ `layer` 動作：子項上提、改呼叫方字串（`tools/lint` → `lint`）——這輪沒用到，但使用者原話點名「中間層糅合」 |
| 資料夾→JSON 物件（C-72；`tables/` 7 檔 → 一份） | 不行：只搬單子，不碰資料檔 | ⑤ `pack` 動作：資料夾裡的 `*.json` 合成一份、檔名當 key；讀者是程式（brief/_entry 讀 `tables/x.json`）改不了，只能列出「誰讀了這些檔」（grep）讓人改 |
| `_metainfo` 跟著搬 | 不行：`rebase()` 只改 `cwd`、`$ref`、`$env AOS_CD`；`X/_metainfo` 檔整個被 `removes` 刪掉 | ⑥ M1 三處互轉：`X/_metainfo` ⇄ 單子的 `_metainfo` key ⇄ `js["_metainfo"]`；`reads`／`writes`／`callers` 裡的路徑跟著 rebase |
| 證明行為不變 | 不行（README 說「不保證一樣的地方」但沒有工具幫你跑對照） | ⑦ `verify`：兩棵樹同題跑、抹時間後 diff |

結論：**不夠用**；它是「up」的工具，`down` 只是 up 的逆運算（單子那條線）。要的是另一支小原型，**不改 proto8/grow**（它的六級與 rebase 規則照用，可以 `import` 或直接呼叫它做第 2→0 級那段）。

### `plan/aos-fold` 原型規格（給實作者；Python 純標準庫；放 `proto8/topdown/galtxt-b/plan/aos-fold`，不進 PATH）

`aos-fold - 把一個資料夾樹的節點往低一級收：縮 agent、解捷徑、併薄層、資料夾打包成 JSON；_metainfo 跟著走；先 dry-run、再 verify`

```
aos-fold [--dry-run] agent  DIR --script ask.py [--timeout-ms N]   # 5→4：留 --script 與伴隨檔，刪範本檔，寫 _entry 單子
aos-fold [--dry-run] link   LINK                                    # 捷徑 → 真資料夾；目標沒別的呼叫者就從 lib 搬走（git mv），有就複製
aos-fold [--dry-run] layer  DIR                                     # DIR 只有一個子項：子項上提到 DIR 的位置，呼叫方字串改掉（慣例衝突時要 --force）
aos-fold [--dry-run] pack   DIR                                     # 資料夾裡的 *.json（含 _metainfo）→ DIR.json，檔名當 key；印出誰讀了這些檔
aos-fold verify TREE_A TREE_B --ws WS --question Q.json [--env K=V]...   # 兩棵樹同題跑、抹掉時間欄位後 diff out/ 與 .stack/
```

- **`agent`**：檢查 DIR 是範本形（`_entry` 是 sh 兩行、`loop.json` 指 `fsm.json`、fsm 三態、`idle/` 存在）不是就 `TargetBad`；`--script` 必須已存在（人先寫好 ask.py，工具不合併程式）；think 單子的 `timeout_ms` 與 `_metainfo` 拿來組新的 `_entry` 單子（`argv` 換成 `["python3", 腳本]`）；資料夾 `_metainfo` 的 `grow_level` 改 4、`interrupt` 若是 `resumable` 改 `safe` 並印警告；刪 `loop.json`、`fsm.json`、`idle/`、原 think／act 指到的腳本（只刪 `--script` 沒列的）；`.env`、`system.txt` 留。dry-run 印新 `_entry` 全文、刪哪些、`_metainfo` diff。
- **`link`**：`os.readlink` 相對路徑；目標的 `_metainfo.callers` 減掉這個呼叫者，剩 0 個就 `git mv`（沒 git 就 `os.rename`）整個資料夾過來、目標上層的 `_metainfo.summary` 印提醒要人改；剩 >0 個就 `shutil.copytree(symlinks=True)`。呼叫方不用改（字串目標一樣）。
- **`layer`**：DIR 底下恰一個子項且 DIR 自己只有 `_metainfo`；子項搬到 DIR 的父層、名字照舊；掃父層的 `_entry`／`*.json`／`*.py`／`*.sh` 裡 `DIR名/子項名` 的字串改成 `子項名`（只改字串字面、印 diff）；若 DIR 名是 `tools`（P-33 慣例）沒 `--force` 就 `TargetBad` 並說明。
- **`pack`**：C-72——`DIR/*.json` 讀成物件，合成 `{"檔名去副檔名": 內容, "_metainfo": DIR/_metainfo 的內容}` 寫 `DIR.json`；合起來 > 8 KB 印警告（F6）；掃同一棵樹裡提到 `DIR/` 的程式字串，列出「這些讀者要人改」；不刪 DIR（人改完讀者、verify 過了再刪）。
- **`verify`**：`cp -a` 工作區兩份、各放同一題到 `new/`、各 `aos-exec --ws 複本 TREE`（PATH 照 `tests/aos_bins.py`）；比 `out/<題名>/*`（`measure.json` 抹掉 `elapsed_ms`、`*_at` 欄）與 `.stack/`（抹掉 `trace.jsonl`、`llm.jsonl`、`state.txt`——這些本來就會因級數改變而不同，列為「預期差異」印出來，不算失敗）；其餘逐位元比；有差＝退 1、印 diff。
- **`_metainfo` 跟著走**（每個動作共用）：路徑欄位（`reads`／`writes`／`calls`／`callers`）用 `os.path.relpath` 重算；`agent` 把 think 單子的 `_metainfo` 併進資料夾那份（資料夾的贏，M1 外層贏；衝突印出來）；`pack` 把 `DIR/_metainfo` 放進 `js["_metainfo"]`。
- **錯**：stderr 一行 `aos-fold: 代號 原因` 退 1、什麼都不寫；代號 `ArgumentsBad`、`FlagUnknown`、`TargetBad`、`NameBad`、`WriteFailed`、`VerifyFailed`。N-05 先寫暫存再改名；dry-run 什麼都不寫。
- **測試** `proto8/tests/test_fold.py`（放 plan/ 的工具也要有測試）：拿 galtxt-b 複本做——`agent` 縮 critic 後 demo 三段照過；`link` 解 plan_lint 後 `test_links` 的對應案例改掉照過；`layer` 對 `check/tools` 沒 `--force` 要紅；`pack` 對 `brief/tables` 要印 F6 警告與讀者清單；`verify` 對「收攏前 vs 後」綠、對「故意改一條 lint 規則的樹」紅。

這支原型做完，這輪 §4 的步驟 1～3 就是三條命令加人手寫兩支 `ask.py`；之後反向收攏不用再寫清單。

## 6. 實作結果（opus，10-25；照 §4 做完）

- **aos-fold**（`plan/aos-fold`，Python 純標準庫）：`agent`、`link`、`layer`、`pack`、`verify` 五個子命令都做了，測試 `proto8/tests/test_topdown_galtxt_b_fold.py` 6 個（五個子命令各一＋命令列的錯）。步驟 1～3 是三條命令（`link draft/tools/plan_lint`、`agent judge/tools/critic --script ask.py`、`agent draft/tools/director --script ask.py`）＋兩支 `ask.py`（brain.py 原樣＋act.py 的尾巴）；步驟 4 手動。
- **行為不變**：收攏前的樹複本 vs 收攏後，q01／q08 × 不開開關／`BAD_FIRST`／`LINT`／`BAD_PLAN=1`／`BAD_PLAN=2` 共 10 組全綠（`runs/round3/verify.txt`；只差 director、critic 小格的 `state.txt`、`trace.jsonl`）。樹：`runs/round3/tree_before.txt`（99 行）→ `tree_after.txt`（86 行）。
- **代定**（可翻案）：① 單子的 `_metainfo` 寫 `{"$ref": "_metainfo"}`（§3 建議那個；aos-exec 跑單子時會解它，`_metainfo` 壞了單子就跑不起來＝DirectiveBad，測試會先抓到）。② critic／director 的 `elapsed_ms`：沒有 trace 就用 llm.jsonl 的 `elapsed_ms` 加總（§4 步驟 2.5 的第一個做法），**沒**把 `critic_elapsed_ms` 寫進 score.json——寫了 score.json 就不能逐位元對照，而且 director 被叫兩次也沒有地方放。③ ask.py 沿用 brain.py「先接 user 再問腦」：問腦失敗時 history 會留下那則 user，重跑看到最後是 user 就直接再問（不重接），跟原本 think 格重跑一樣。④ `brief/tables/beats.json` 的 `_note` 還寫「lib/plan_lint」沒改：它會原樣進 brief.json，改了就破逐位元對照，留給之後動 tables 時一起改。
- **真腦**（chatgpt-gpt-6-luna-low，各一次；`runs/round3/`）跟 round2 對照：

| 題 | 輪 | 分數 (T0/T1/T2) | calls | tokens | 總時間 ms | director ms | critic ms | writer calls（自檢） |
|---|---|---|---|---|---|---|---|---|
| Q01 | round2 | 6（1/2/3） | 4 | 17115 | 14365 | 5643（腦 5572） | 1903（腦 1832） | 2（1） |
| Q01 | round3 | 5（1/2/2） | 5 | 23074 | 19321 | 7332（＝腦） | 2521（＝腦） | 3（2） |
| Q08 | round2 | 4（1/2/1） | 4 | 17379 | 18150 | 6446（腦 6375） | 2978（腦 2907） | 2（1） |
| Q08 | round3 | 5（1/2/2） | 4 | 17485 | 13748 | 4499（＝腦） | 2303（＝腦） | 2（1） |

分數都在 ±1 內。Q01 多 1 call、tokens +35%：writer 這次自檢了兩次（腦的選擇；director／critic 每次的 tokens 跟 round2 差 < 6%）；Q08 calls 相同、tokens +0.6%。director／critic 的流程開銷 round2 是 71 ms（trace − 腦），round3 的 `elapsed_ms` 改用腦的時間代替，看不到開銷（定義上是 0）；總時間的差幾乎全是腦的快慢。
