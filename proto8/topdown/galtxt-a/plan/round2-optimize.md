# galtxt-a 第二輪：只看 `_metainfo` 表做整棵樹的優化盤點（fable，2026-10-25）

← 上一輪規劃 [round1.md](round1.md)｜實測 [round1-measure.md](round1-measure.md)｜表 [meta/table-round1.md](../meta/table-round1.md)（由 [meta/metatable](../meta/metatable/) 收出）｜題目 [thinking 10-25 top-down](../../../thinking/2026-10-25-top-down.md)｜收攏方案 [round2-collapse.md](round2-collapse.md)

使用者要驗的是：**只憑 `_metainfo` 收出來的那張表**，能不能提出整棵樹怎麼優化（10-25 原文「這是後續對整個資料夾樹進行優化的參考」）。所以本檔分兩步、**順序不倒**：§ 1 寫的時候只開了 `meta/table-round1.md`，沒開任何程式、README 或實測；§ 1 存檔後才開 `round1-measure.md` 寫 § 2。§ 1 裡的錯判一律**留著不改**，§ 2 逐條對照——錯在哪裡本身就是「表缺什麼」的證據。

表的欄位：`path／depth／kind／grow_level／summary／time_ms／resource／llm_calls／llm_tokens／deterministic／idempotent／side_effect／interrupt／parallel／fs_needs／callers`，數值欄寫 `典型/上限`。下面用「`列.欄`」指一格，例如 `write.llm_calls`。

---

## 1. 只看表（§ 1 寫完才開其他檔）

### 1.1 先把表讀成幾個數字

| 看到 | 讀出 |
|---|---|
| `..time_ms` 90000；純程式列（brief 50、check 300、lint 40、idle 5、pick 30）加起來 **< 500 ms** | 整棵樹 **99% 以上的時間在腦**。優化純程式沒意義，只有三條路：少叫、叫短、同時叫。 |
| `write.llm_tokens` 18000／`..llm_tokens` 24000；`write.llm_calls` 6／`..llm_calls` 9 | **寫手吃 75% 的 token、2/3 的呼叫**；評審 25%。 |
| `write.time_ms` 45000 ＝ 3 × `write/tools/writer.time_ms` 15000；`judge.time_ms` 25000 ≈ 3 × 7000 + 4000 | 兩個 glue 都標 `parallel=true`，但**典型時間是子項的 N 倍**——宣告的是「可平行」，實際排法是**逐個跑**。 |
| `write/tools/writer.llm_calls` 2／`…think/exec.llm_calls` 1；writer summary「交稿前用…（lint）」；`check` summary「每份草稿用 tools/lint 過一次」；`check/tools/lint.callers` 2 | 每份草稿 **lint 跑兩次**（寫手自己當工具叫一次、check 再過一次），寫手**每份固定兩次腦**（寫 → 看 lint 結果 → 再回一次）。 |
| `deterministic=false` 的列只有 `.`、`write`、`judge`、兩個 agent、兩個 `think/exec` | 不確定性全集中在兩格 `think/exec`；其他全是確定的。可快取的對象也就是這兩格。 |
| `fs_needs` 空：brief、idle ×3、pick（彙總列也點出）；`（空）` 全是 `program`、`grow_level 3`、`callers 1` | 第 3 級（資料夾只有入口）而且沒有任何檔案系統需求、只被一處叫 → 照 fn-grow「觸發點都沒了就往回併一級」是**現成的縮回候選**。 |
| `write/tools/writer`（depth 3）、`judge/tools/judge`（depth 3）、`check/tools/lint`（depth 3）：表上**沒有** `write/tools`、`judge/tools`、`check/tools` 這三列 | 三個 `tools/` 是**沒有自己 `_metainfo` 的純中間層**——使用者說的「嵌套太深要收攏」的對象就是它們。最大深度 5 全靠它們撐出來（`write/tools/writer/tools/lint`）。 |
| 三個 `idle` 列 summary 一字不差、數值一樣 | **同一支程式抄了三份**。 |
| 彙總「llm_calls.val 總和（只加 agent）12」＝ `.` 9 ＋ writer 2 ＋ judge 1 | 彙總把**巢狀的 agent 重複加**了（根已經含子項）。真正的典型值就是根那格 9／24000。 |

### 1.2 建議（看到哪幾格 → 建議 → 預期效果）

編號給 § 2 對照用；**粗體**的是我認為最值得先做的五條。

**O-1 真的把寫手與評審平行跑**
- 看到：`write.parallel=true`、`judge.parallel=true`，但 `write.time_ms` 典型 45000 ＝ 3 × writer 15000；`judge.time_ms` 25000 ≈ 3 × 7000。`write/tools/writer.side_effect=true` 但 `write.side_effect=false`——每個寫手寫自己的小格、glue 本身不寫共用的東西，所以沒有共享狀態擋平行。
- 建議：glue 一次把 N 個小格都開出去再收（aos-loop／fsm 哪種方式開 N 個子行程，表看不出；至少是 `&`＋wait）。
- 預期：`write.time_ms` 45000 → ≈ 15000＋開殼；`judge` 25000 → ≈ 8000；根典型 90000 → **≈ 50000**（省 40%，token 不變）。腦 endpoint 若有併發上限（`resource` 只寫 `llm`，看不出配額），平行度要受 kernel-llm 的 `max_calls` 管。

**O-2 拆掉重複的 lint，寫手改成一次腦**
- 看到：`write/tools/writer.llm_calls` 2 vs 它底下 `think/exec.llm_calls` 1（寫 → lint → 再寫，固定兩輪）；`check` 對每份草稿**又**跑一次 lint；`check/tools/lint.callers` 2。
- 建議（二選一，看表傾向 b）：(a) 寫手留 lint 工具、拿掉 check（信寫手自己過的 lint）——不好，deterministic 的護欄應該在腦外面；**(b) 寫手拿掉 lint 工具、只叫一次腦**，check 當唯一護欄，**只對沒過的草稿**再開一個寫手小格重寫（帶 lint 原因）。而且 brief 把禁語與稱謂階直接寫進去，第一稿過護欄的機率就高。
- 預期：`write.llm_calls` 6 → 3＋沒過的份數（估 3～4）；`write.llm_tokens` 18000 → ≈ 10000～12000（第二輪腦帶 history 最貴，省掉的就是這一半）；根 `llm_calls` 9 → ≈ 6～7、`llm_tokens` 24000 → ≈ 16000～18000。寫手 `grow_level` 5 → 可降（沒有自己的 tools/ 了，只剩 fsm＋idle）。
- 風險：寫手少了「看到 lint 錯誤自己修」的回合，整體過護欄率可能掉；但從表看，check 本來就會砍，不會放壞稿出去。

**O-3 三個 `tools/` 中間層與三份 `idle` 收攏**
- 看到：`write/tools/writer`、`judge/tools/judge`、`check/tools/lint` 三列 depth 3，表上沒有 `*/tools` 列；三個 `idle` 列相同；`write/tools/writer/tools/lint` depth 5 是捷徑。
- 建議：`tools/` 只在「被腦當工具叫、要 tool.json」的那層才需要（`check/tools/lint.fs_needs` 有 `tool_json`——lint 是給腦叫的，它的上一層 `tools/` 有道理；但 writer、judge 是被 glue 開的 agent，不是腦的工具，`write/tools/`、`judge/tools/` 沒道理）。→ `write/tools/writer` → `write/writer`；`judge/tools/judge` → `judge/judge`（或直接 `judge/` 自己就是那隻 agent，見 O-5）。lint 的捷徑跟著改目標。三個 `idle`：留一份（根的）、另兩個改成捷徑或內嵌進各自 loop.json（`fs_needs` 空、5 ms、deterministic）。
- 預期：最大深度 5 → 3 或 4；節點 24 → ≈ 19；行為不變（純搬動）。

**O-4 `fs_needs` 空的第 3 級程式往回縮：brief、pick、idle**
- 看到：`brief／pick／idle.fs_needs=（空）`、`grow_level 3`、`callers 1`、`deterministic=true`、`side_effect` brief／pick 為 true（寫 cur/、out/）但沒有自己的伴隨檔。
- 建議：fn-grow 第 3 級 → 第 2 級（`brief.json`、`pick.json`）或第 0 級（內嵌進 loop.json 那格）。**但表上看不出 `_entry` 是一張單子還是一支腳本**：是單子就能縮成 JSON；是 Python 腳本，只有 `_entry` 一個檔的資料夾縮成 `x.json` 得把腳本搬去共用的 lib（或改成 `python3 -c`，不建議）。這格的判斷缺資訊，先列候選、§ 2 補。
- 預期：資料夾少 3～5 個；時間 token 都不變。

**O-5 write／judge 兩個 glue 長得一樣，併成一支「散出去收回來」**
- 看到：`write` 與 `judge` 兩列除了數字，`kind=glue`、`grow_level 3`、`deterministic=false`、`idempotent=true`、`side_effect=false`、`interrupt=resumable`、`parallel=true`、`fs_needs=mount`、`callers 1` 完全一樣；summary 都是「每份／每次一個新小格、收…」。
- 建議：一支純程式 `fanout`（參數：哪個 agent、幾份、輸入從哪來），`write`＝`fanout writer ×N`，`judge`＝`fanout judge ×每份草稿`。或至少同一支腳本兩個入口。O-1 的平行只要在這一支做一次。
- 預期：glue 程式碼減半、平行化只改一處；節點數不變或 −1。

O-6 評審結果快取
- 看到：`judge/tools/judge.deterministic=false` 但 `judge.idempotent=true`、`side_effect=false`；輸入只有「前後文＋一份草稿」。
- 建議：key＝hash(題目, 草稿全文) → 分數；同題重跑（換 pick 規則、debug 評分）時不再叫腦。寫手不快取（本來就要變化）。
- 預期：第二次跑同題 `judge.llm_calls` 3 → 0；第一次沒差。對「跑通後反覆調 pick／check 的開發期」最有用。

O-7 上限欄互相矛盾，先修宣告
- 看到：`..llm_tokens` 上限 200000 **<** `write` 150000 ＋ `judge` 60000 ＝ 210000（違反外層 ≥ 內層總和）；`judge/tools/judge.llm_tokens` 上限 10000 **<** 它自己 `llm_calls` 上限 2 × `think/exec` 上限 10000 ＝ 20000；`write.llm_calls` 上限 36 ÷ writer 上限 4 ＝ **9 份**，但 `write.llm_tokens` 上限 150000 ÷ writer 50000 ＝ **3 份**——兩欄隱含的 N 不同；`judge.llm_calls` 上限 12 ÷ 2 ＝ 6 份、`llm_tokens` 60000 ÷ 10000 ＝ 6 份（這對是自洽的，但跟 write 的 3 或 9 又不同）。`..time_ms` 上限 3,500,000（58 分鐘）＝ 把每層上限相乘出來的數，沒有用處。
- 建議：上限由 metatable 自動算（外層 ＝ Σ 內層上限 × 份數上限）並標出手寫值跟算出值不合的格；`time_ms` 上限改成「要用來設 `timeout_ms` 的那個數」，不然就刪。
- 預期：不省資源，但讓 O-1／O-2 的估算有依據；也讓 P-36（外層逾時 ≥ 內層總和）能半自動檢查。

O-8 彙總列的「總和」改成只加葉片
- 看到：彙總「llm_calls.val 總和（只加 agent）12」把根的 9 再加上子 agent 的 3。
- 建議：總和只加沒有 `llm` 子項的葉片（兩格 `think/exec` × 份數），或直接拿根那格；多一列「根宣告 vs 葉片加總」的差。
- 預期：表本身的可信度。

O-9 `data/` 下四個資料夾各縮成一份 JSON；`bench` 留
- 看到：`data/cast／places／samples.fs_needs=git_tracked`（只有這個）；summary「一人一張／一地一張／一個角色一檔」；`data/bench.fs_needs=git_tracked,isolation`、`data.fs_needs=git_tracked,isolation`。
- 建議：`git_tracked` 一份 JSON 同樣滿足（git 追蹤的是檔，不是資料夾），所以 cast → `cast.json`（`{名: 卡}`）、places → `places.json`、samples → `samples.json`；再併成一份 `data.json` 就過頭了——三張表是人手改的、diff 要看得出改哪張。`bench` 的 `isolation`（寫手不能看到正解）靠的是「寫手的沙箱看不到那個資料夾」，是檔案系統特性，**不縮**；`data/` 這層本身因為 `isolation` 也留著。
- 預期：資料夾 8 → 5，節點 −3；讀表的程式（brief）改讀法。

O-10 `meta/`、`plan/` 不算在執行樹裡
- 看到：`meta/metatable.callers 0`、`plan*.kind=data`、全部 `git_tracked`、沒有 time／llm 欄。
- 建議：metatable 加一欄或一個 `_metainfo` 旗標（例如 `role: dev`）把開發期的東西隔出來，彙總另算；不然「24 節點、深度 5」裡有 5 個是文件與工具。
- 預期：執行樹真實大小＝19 節點。

### 1.3 不確定、表上看不出的（§ 2 回頭補）

- `_entry` 是單子還是腳本（O-4 卡在這）。
- 寫手 `think/exec.llm_tokens` 3000 裡 prompt 佔多少、history 第二輪帶了多少（O-2 的省法對不對）。
- `parallel=true` 是「可以」還是「已經」（O-1 整條建立在「還沒」上）。
- `data.callers 2` 是誰（brief 一定讀；另一個是 judge 還是 writer？若 writer 直接讀 `data/`，O-9 的 isolation 判斷要重看）。
- 腦 endpoint 的併發配額（O-1 平行度）。
- 哪些 `max` 是算出來的、哪些是手填的（O-7）。
- 兩個 `think/exec` 列 `kind=—`、`grow_level=—`：metatable 不認 fsm 格；它們的 `fs_needs` 也是 `—`，所以「fs_needs 空＝縮回候選」那條彙總漏了它們（它們本來就是第 0 級內嵌，沒事，但表應該標成 `0`）。

---

## 2. 對照實跑（§ 1 存檔後才開 round1-measure.md）

實測來源：`round1-measure.md`（真腦 `chatgpt-gpt-6-luna-low`，Q01 與 scene 各跑一次、各 3 份草稿）。下面「倍數」＝宣告 `val` ÷ 實測。

### 2.1 估得準的

| 格 | 宣告 | 實測 | 評 |
|---|---|---|---|
| `llm_calls`（根 9、write 6、寫手 2、judge 3、評審 1） | 9／6／2／3／1 | 9／6／2／3／1 | **一格不差**。呼叫次數是由結構決定的（fsm 固定走幾格），不是估的，當然準。 |
| `llm_tokens`（根 24000、寫手 6000、評審 2000） | 24000／6000／2000 | 26824～28475／6627～7076／2235～2428 | 差 12～19%，偏低。偏低的原因是 prompt 估 2.5k、實際 3.1k～3.5k（tools schema＋brief 比想的長）。 |
| 純程式（brief 50、check 300、pick 30、idle 5） | 50／300／30／5 | 24～26／82～85／23～24／1 | 比例差 1～3.5 倍，但絕對值都 < 0.1 s；對整棵樹沒意義。 |

### 2.2 估不準的：所有腦的時間，一律高估 3～6 倍

| 格 | 宣告 | 實測 | 倍數 |
|---|---|---|---|
| 根 `time_ms` | 90000 | 15178／24025 | 3.7～5.9 |
| write | 45000 | 10440／18164 | 2.5～4.3 |
| 寫手每次 | 15000 | 3161～6551 | 2.3～4.7 |
| 寫手 think 每次 | 6000 | 1412～4064 | 1.5～4.2 |
| judge | 25000 | 4603／5728 | 4.4～5.4 |
| 評審每次 | 7000 | 1435～2595 | 2.7～4.9 |

為什麼錯、而且**越往上錯越多**：

1. 單次問腦估 6 s（按一般前沿模型），實際是 `-low` 推理檔、1.4～4 s。這是源頭的 1.5～4 倍。
2. 每往上一層我都再加一層安全邊際（寫手 15000 ＝ 2 × 6000 ＋ 3000；write ＝ 3 × 15000；根 ＝ write ＋ judge ＋ 20000），**邊際是乘上去的**，所以根 5.9 倍、think 只 1.5～4 倍。`val` 應該只在葉片手填、上面由 metatable 加總；現在每層手填一遍就是在堆邊際。
3. `max` 不是估的、是 P-36 反推的（實測 § 偏離 1：寫手一圈 think 120 s ＋ act 60 s × loop 上限 4 圈 ＝ 720 s，× 3 ＝ 2160 s → write 2,400,000）。它是**逾時上界**，不是資源預算；拿它去算「worst case 吃多少」只會得到 58 分鐘這種數。O-7 說對了方向，但原因猜錯——不是手填不一致，是 `max` 這一欄混了兩種意思（逾時上界 vs 資源上限）。
4. Q01 與 scene 差 60%（15 s vs 24 s），差的全在寫手 think：completion 107～111 vs 413～488。**時間跟 completion token 走、不跟 prompt 走**；表只有一個 `llm_tokens` 合計，看不出這點。

### 2.3 § 1 的建議被實測怎麼對待

| 建議 | 結果 | 依據 |
|---|---|---|
| **O-1 平行** | **加強**。省的不是 40%、是 **60%**。 | write 10440 ≈ 3 × 3161～3884 的和、judge 4603 ≈ 3 × 1466～1625 的和——確認是逐個跑。平行後 Q01 ≈ 3884 ＋ 1625 ＋ 200 ≈ **5.7 s**（原 15.2 s）、scene ≈ 9.4 s（原 24.0 s）。 |
| **O-2 拆重複 lint、寫手一次腦** | **強烈加強**。 | 「6 次寫手都叫了 1 次 lint、lint 都回 `pass: true`，沒有一次 lint 不過再改」——第二次問腦（prompt 3542，佔寫手 token 的 **50%**）完全是儀式：腦看一眼 `pass: true` 然後交稿。拿掉 → write token 21216 → ≈ 10600、根 28475 → ≈ **17900（−37%）**，時間每個寫手再省 1.4～2 s。而且 check 那邊本來就過一次 lint，護欄不少一層。保守做法：寫手 fsm 從 think → act(lint) → think → 交稿 改成 think → 交稿，lint 全交給 check；check 不過才開第二個寫手小格重寫（帶原因）。 |
| O-3 收攏 `tools/` 中間層與三份 idle | **加強**（實測 § 偏離 4、5）：實作者自己也發現 `tools/` 是「容器、不是節點」、沒放 `_metainfo`，而 writer／judge **不是**腦可以叫的工具、不該有 `tool.json`——那它們就更不該住在 `tools/` 底下。 | 偏離 4、5。 |
| O-4 brief／pick／idle 縮回 | **沒被推翻也沒被加強**；實測沒講 `_entry` 是什麼。從偏離 9（brief 有自己的錯誤代號 `QuestionMissing`／`StackMissing`、pick 有 `StateBad`）推測它們是**腳本**不是單子 → 縮回不能直接變 `x.json`，得走「腳本搬進共用 lib、資料夾縮成一行單子」。留給 B 看了程式再定。 | 偏離 9。 |
| O-5 併 glue | 沒直接證據。偏離 9 說 write、judge 的錯誤都由同一支 `agent_tool` 印（`galtxt-a write:`／`galtxt-a judge:`）——**實作者已經把共用部分抽出來了**，兩個 glue 大概只剩參數。B 看程式確認。 | 偏離 9。 |
| O-6 快取評審 | 沒推翻。但實測多給一條：Q01 三份草稿**同分 4、評審理由都差不多**；評審分數的分辨力低才是更大的問題，快取是其次。 | Q01 表。 |
| O-7 修 `max` 宣告 | **部分推翻**：不是「手填不一致」，是 `max` 一欄兩種意思（見 2.2 第 3 點）。`write.llm_calls` 上限 36 ＝ 3 × 12（**loop 圈數上限**，不是腦次數）、`judge` 12 同理；所以用 `max` 去反推份數 N 當然得出 3、6、9 三種答案。該拆成兩欄。 | 偏離 1。 |
| O-8 彙總只加葉片 | 不變。 | — |
| O-9 data 四夾縮 JSON、bench 留 | **加強**：偏離 3 說只有 brief 讀 `data/`（write 的 `reads` 沒有 `ws:`、pick 改成只讀 stack），寫手完全看不到 `data/` → `isolation` 成立；三張卡表縮成單檔只動 brief 一支。 | 偏離 3。 |
| O-10 meta／plan 另算 | 不變（偏離 4 證實 `plan/` 的 `_metainfo` 是為了「每個資料夾都要有」才放的）。 | 偏離 4。 |

**實測還多揭露、表上完全看不到的兩件事**（都是狀態／資料流，不是資源）：

- 偏離 2：**換題不清舊草稿**會把上一題的草稿當這題的（write「已有的不重寫」、judge「已評的不重評」）。`_metainfo` 有 `reads`／`writes`，但表沒把它們印出來，也沒有「這格的輸出被誰當輸入、key 是什麼」。
- 偏離 1：**逾時配置是從內往外手算的**（P-36），算錯一次就是外層先殺內層。這是可以純程式檢查的，但表上只有 `time_ms.max`、沒有實際設的 `timeout_ms`。

### 2.4 `_metainfo`／表缺什麼（只看表時想知道卻沒有的），各給 key

命名照 C-54：計數 `counter_*`、上限 `max_*`、時間點 `<事>_at`；量測值另立 `measured` 物件，不跟宣告混在一格。

| 缺的資訊 | 為什麼需要 | 建議的 key（放在 `_metainfo`） | 表上的欄 |
|---|---|---|---|
| **實測值** | 2.2 的 3～6 倍全靠 `round1-measure.md` 手抄才知道 | `measured: {measured_at, counter_runs, elapsed_ms: {p50, max}, counter_llm_calls, counter_llm_tokens}`（由 trace.jsonl／usage.jsonl 自動填） | `elapsed_ms(p50)`、`宣告÷實測` |
| **prompt／completion 分開** | 時間跟 completion 走、錢跟 prompt 走、快取只省 prompt（2.2 第 4 點） | `llm_prompt_tokens: {val, max}`、`llm_completion_tokens: {val, max}`（取代單一 `llm_tokens`）；量測 `measured.counter_prompt_tokens`、`measured.counter_completion_tokens` | 兩欄 |
| **快取** | O-2 兩次問腦共用 3.4k 前綴，provider 端 prompt cache 可能已經命中；O-6 結果快取 | 宣告 `cache: none\|prompt\|result`；量測 `measured.counter_cached_tokens`、`measured.counter_cache_hits` | 一欄 |
| **逾時上界 vs 資源上限分開** | O-7 的根本原因 | `time_ms.max` 只留「資源上限」；逾時另記 `timeout_ms`（就是單子裡設的那個）；metatable 檢查 P-36：父 `timeout_ms` ≥ Σ 子 `timeout_ms` × `max_rounds` | `timeout_ms`、P-36 ✓／✗ |
| **loop 圈數上限** | `write.llm_calls.max` 36 其實是 3 × 12 圈 | `max_rounds`（agent／glue 的 loop 上限，從 loop.json 讀） | 一欄 |
| **散出的份數** | glue 的 `max` 要能算（N × 子上限）；O-7 反推出 3／6／9 | `counter_children: {val}`、`max_children`（glue 一次開幾個小格） | 一欄；metatable 用它算父上限 |
| **平行：宣告 vs 實際** | O-1 整條靠猜 | `parallel` 拆成 `parallel_safe: bool`（宣告）＋ `max_parallel`（實際允許同時幾個；1 ＝ 逐個）；量測 `measured.counter_concurrent_max` | 兩欄 |
| **資料依賴** | 偏離 2、3 都是資料流的事；表沒印 `reads`／`writes` | `reads`／`writes` 已有，**metatable 印出來**；再加 `state_key`（這格靠哪個 key 判「做過了」，例如 `current.txt`），好檢查「換 key 要清什麼」 | `reads`、`writes` 兩欄；另出一張「誰寫→誰讀」表 |
| **錯誤率** | 哪格常失敗、重試幾次，表看不到 | 宣告 `errors: [代號]`（已有的話印出來）；量測 `measured.counter_failures`、`measured.counter_retries` | 一欄 |
| **`_entry` 是什麼** | O-4 卡住：單子能縮成 JSON、腳本不能 | `entry_kind: inst\|script\|argv\|dir`；`companion_files: [...]`（只有它用的伴隨檔，fn-grow 第 4 級的判準） | 兩欄 |
| **呼叫方是誰** | `callers 2` 看不出是誰；收攏要改呼叫方 | `callers` 從數字改成名單 `callers: ["check", "write/tools/writer/tools/lint"]`（metatable 掃出來，不手填） | 名單 |
| **用的模型／endpoint** | 2.2 第 1 點：`-low` 檔比估的快 2～4 倍；平行度受 endpoint 併發限 | `llm_model`、`llm_endpoint`（從 `.env` 讀）；endpoint 層 `max_concurrent_llm` | 一欄 |
| **角色** | O-10：meta／plan 不是執行樹 | `role: runtime\|dev\|doc` | 彙總分開算 |
| **哪些數是算出來的** | 2.2 第 2 點：手填會堆邊際 | `derived: ["time_ms.val", "llm_tokens.val", ...]`（由 metatable 寫回，標示這格是加總不是手填） | 格後加 `*` |
| **分辨力**（評審專用） | Q01 三份同分 | 不進 `_metainfo`（是結果不是特性）；進 `score.json` 的 `counter_ties` | — |

### 2.5 一句話結論

只看表，**該優化什麼**（平行、拆重複腦、收中間層、縮 fs_needs 空的葉片、data 縮單檔）全部指得出來，而且三條主建議（O-1、O-2、O-9）都被實測加強；**該優化多少**估不出來（時間 3～6 倍、第二次問腦是純儀式），要靠實測欄。表最大的洞不是數字、是**資料流**（`reads`／`writes`／狀態 key）——第一輪實作偏離規劃的兩件大事（逾時、換題不清）都在那裡。
