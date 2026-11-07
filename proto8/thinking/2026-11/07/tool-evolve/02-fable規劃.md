# fable 規劃：shell 的三階段不另設欄位，由「工具清單＋沙箱宣告」推出來；轉階段就是改定義並 commit；確定性用同一把尺（重跑比對）量腳本步、LLM 步、整體三層

← [README](README.md)｜簡報 [01-簡報](01-簡報.md)

## 一、白話總結

使用者定的路是：agent 一開始可以隨便用 shell，接著只能用一小撮指令，最後完全不給 shell、只給專屬工具。這份規劃回答五件事：階段怎麼表示、怎麼轉、確定性怎麼量、跟沙箱怎麼接、降級階梯扮什麼角色。

**階段不用另外寫一個「我在第幾階段」的欄位。** 一隻 agent 在哪一階段，看它手上的工具清單就知道：清單裡有一支「什麼指令都能跑」的 bash，就是開放期；那支 bash 被關進沙箱、只看得到幾個白名單指令、只能寫自己的工作區，就是謹慎期；清單裡根本沒有這種工具，就是專屬工具期。這樣「寫什麼就是什麼」，不會出現欄位說一回事、工具清單又另一回事。

**要知道「哪些 shell 用法該變成工具」，讓 bash 自己記帳。** bash 每被叫一次，就在自己的小格子裡寫一行：時間、指令、內層退出碼。審視的人（現在是隊長，以後是審視 agent）跑一支統計腳本，把指令按「形狀」歸類（`rg -n <什麼> <什麼>` 算同一形狀），看哪個形狀連續兩個地點都出現、而且都成功，那就是該做成專屬工具的候選。做成工具後，白名單就少一個指令；白名單空了、或連續兩個地點 shell 一次都沒叫，就把 bash 從清單拿掉。每一次轉階段都是改 agent 的定義資料夾並 git commit，所以階段的歷史就是 git 的歷史。

**確定性只用一把尺：同樣的輸入重跑幾次，比對結果。** 差別只在「比什麼、怎麼比」。腳本步比到逐 byte，必須完全一樣，不一樣就是腳本有 bug（例如夾了時間戳）。LLM 步比「一條一條的判斷有幾成一樣」，因為措辭天生不會一樣。整體則是把整個流程當黑盒重跑，看有幾個檔案逐 byte 相同、哪幾個不同；不同的那幾個應該剛好就是 LLM 步的產物。實測結果不寫回工具自己的 `_metainfo`（那是工具的自我宣稱），而是記在觀測帳裡，並且按模型等級分開記，因為同一步換個模型，確定性就不一樣。

**沙箱只在謹慎期上場，而且照原本的規矩：誰叫就誰關。** 謹慎期的 bash 是 agent 自己定義資料夾裡的一個小包裝：`_entry` 第一個字就是 `aos-sandbox`，設定直接指向自己 `_metainfo.json` 裡的 `sandbox` 那一格，所以宣告跟強制是同一份資料。daemon 的 `--limits`（記憶體、CPU 秒數之類）管的是「用多少」，階段管的是「能跑什麼」，兩者不相干、不互相牽動。

**降級階梯是找工具化候選的探測器。** 把某一步固定輸入，在 sol、terra、luna、本機各跑三次，跟 sol 的結果比一致率，三次都過門檻的最低一級就選它。某一級過不了、改一次提示詞還是過不了，那一步就是該拆更細或做成腳本的候選。選出來的等級由審視者改進定義、commit，不在跑的時候自動換。

## 二、設計

### 2.1 概念

三個詞，各自只對應一樣東西：

| 詞 | 它是什麼 | 存在哪 |
|---|---|---|
| **任意執行工具** | 一支工具，呼叫者給什麼它就跑什麼（bash、run_python） | 工具自己的 `_metainfo` 宣告一個布林（建議 key `arbitrary_exec`；格式歸 evolve-design） |
| **沙箱宣告** | 任意執行工具說「我只需要這些」：看得到哪些指令、能寫哪裡、要不要網 | 工具自己的 `_metainfo.sandbox`（沙箱決定 S4 已定） |
| **階段** | 一隻 agent 的推導值，不是欄位 | 從 `aos-tools ls --json`（含 `_metainfo`）算出來 |

階段的推法（每隻 agent）：

- `open`：清單裡有任何一支 `arbitrary_exec: true` 且沒有 `sandbox` 的工具。
- `boxed`：有 `arbitrary_exec: true` 的工具，但每一支都帶 `sandbox`。
- `none`：沒有任何 `arbitrary_exec: true` 的工具。

工具沒有「階段」；工具只有「是不是任意執行」跟「有沒有關」。agent 的階段＝它最鬆的那支工具。

### 2.2 機制

**(a) 開放期：bash 自己記帳**

`lib/base/bash`（以及 `run_python`）每次呼叫，在自己的小格 `$AOS_STACK/tools/<名>/calls.jsonl` 追加一行。寫失敗就退 `LogFailed`、不跑指令（沿用試驗場 `bash_logged` 已驗證的做法，但收進 bash 本體，`bash_logged` 退場）。這一行是工具自己的公開介面，在 `_tooldef.json` 或 `interfaces.json` 寫明 schema，統計者照宣告讀（C-52 的「B 宣告、A 照宣告」）。

```json
{"time": "2026-11-07T10:12:03Z", "command": "rg -n 煮傘居士 source/", "timeout_s": 30, "exit": 1, "elapsed_ms": 42}
```

`exit` 是內層指令的退出碼。這同時把不足 #24 修在正確的層：observed 的 `code` 仍是工具碼，想知道指令成敗看這份 log。

**(b) 統計：`shell_report`（lib 工具）**

輸入：一組 agent stack 路徑（審視者給）。對每個 stack 跑 `aos-tools ls --json` 推階段、讀 `calls.jsonl` 歸形狀。

形狀規則（只這三條）：用 shlex 切字，不用正規表達式；每段管線分開；每段第一個字保留、以 `-` 開頭的保留、其餘換成 `<arg>`。

```json
{
  "agent": "place-manager",
  "shell_stage": "open",
  "units": ["poshan", "chernobog"],
  "binaries": ["rg", "python3"],
  "shapes": [
    {"shape": "rg -n <arg> <arg>", "count": 5, "exit_zero": 3, "units": ["poshan", "chernobog"]},
    {"shape": "python3 <arg>", "count": 2, "exit_zero": 2, "units": ["poshan"]}
  ]
}
```

`units` 是審視單位（試驗場就是地點），由呼叫者在 `calls.jsonl` 旁的 `unit` 欄或時間切分給；最簡單是審視者在每地點開工前把 `AOS_UNIT` 給進環境、bash 把它抄進那一行。

**(c) 工具化候選的三個訊號**（沿用 09，已在用）

- 輸出由輸入完全決定；
- 同一形狀連續兩個單位出現、且 `exit_zero == count`；
- 降一級就錯、提示詞修一次仍錯（由 (f) 階梯給）。

候選交 gpt／codex 寫成資料夾程式：`_entry` 是 argv 陣列（不走 `sh -c`）、`arguments` 從 stdin 進、`_tooldef.json`、`_metainfo.json`，收進 `lib/<層>/<名>/`。agent 的 `tools.json` 加一條捷徑。

**(d) 謹慎期：agent 自己的 `tools/bash/` 包裝**

在 agent 定義資料夾裡放一個資料夾 `tools/bash/`（同名自己的贏，蓋掉 lib 的）：

```
tools/bash/
  _entry            ["aos-sandbox", "_metainfo.json#/sandbox", "aos-exec", "inner"]
  inner  →          ../../../lib/base/bash（捷徑）
  _tooldef.json →   同 lib 那份（捷徑）
  _metainfo.json    下面這份
```

```json
{
  "summary": "沙箱內的 bash：只看得到白名單指令、只寫工作區、無網",
  "arbitrary_exec": true,
  "sandbox": {
    "commands": ["bash", "rg", "jq", "python3"],
    "ro": ["inner"],
    "rw": [{"$env": "AOS_WS"}],
    "net": false,
    "mem_mb": 1024,
    "cpu_s": 120,
    "file_mb": 100
  },
  "time_ms": {"val": 500, "max": 300000},
  "side_effect": true,
  "idempotent": false,
  "deterministic": false,
  "interrupt": "unsafe",
  "parallel": true
}
```

白名單就是 `shell_report.binaries` 減掉已經做成專屬工具的那些。白名單是「看得到哪些執行檔」（bwrap 綁進去哪些），不是指令字串的規則；管線、重導向、內建指令都還能用，但只能用這幾個程式、只能寫 `$AOS_WS`、沒有網。這同時修了不足 #25（寫到 `/tmp`）。

注意一件事實：daemon 的 stack 若放在工作區裡，`rw: $AOS_WS` 就把整台 daemon 綁進去了。謹慎期要求 stack 放工作區外，或 `rw` 只綁工作區底下的資料子資料夾。

**(e) 專屬工具期：拿掉**

審視者在定義資料夾執行 `aos-tools rm bash`（以及 `run_python` 等任意執行工具），commit。`shell_report` 回 `none`。沒有「緊急備援 bash」——使用者定的終點是全專屬工具；真的缺，git revert 回謹慎期再補工具。

**(f) 階段轉換規則**（審視五步裡的一條，由審視者執行、人定門檻）

- `open → boxed`：做過 ≥2 個單位，且最近 2 個單位 `binaries` 沒有新增 → 寫 `tools/bash/` 包裝，白名單＝用過的執行檔。
- `boxed → none`：最近 2 個單位 shell 呼叫數為 0，或剩下的形狀都已有專屬工具 → `aos-tools rm`。
- 回退：轉後下一單位錯誤數上升 → `git revert` 那一筆。

每一次轉換都是定義資料夾的改動＋一筆 commit；階段歷史＝`git log -- <定義>/tools.json <定義>/tools/`。執行中的 `self_tools` 覆蓋層不用來轉階段（那是 stack 裡的漂移，P-15）；`shell_report` 讀的是 `aos-tools ls --json` 看到的有效清單，所以漂移會被看見，但轉階段只在定義。

**(g) 確定性：`repeat_check`（lib 工具）——一把尺三種比法**

```json
{"target": "tools/kb_store", "input": {"slug": "poshan"}, "runs": 3, "compare": "bytes"}
```

- `bytes`：每次輸出逐 byte 比。給腳本步。回 `{"runs": 3, "identical": true}`。不同就是腳本有 bug（時間戳、dict 順序）——修腳本，不是放寬尺。
- `by_item`：輸出是 JSON 陣列，逐條與 `reference` 比相等，回每次的一致率。給 LLM 步。
  `{"target": "tools/kb_link", "input": {...}, "runs": 3, "compare": "by_item", "reference": "runs/sol-1/links.json"}` → `{"runs": 3, "agreement": [1.0, 0.9375, 1.0]}`
- `tree`：目標是整個單位的入口（例：`place_run`），在暫存資料夾重建，逐檔逐 byte 比，回 `{"files": 5, "identical": 4, "differ": ["links.json"]}`。給整體。`differ` 裡出現非 LLM 步的檔，就是腳本步漏了確定性。

三層就是同一支工具對三種目標。`place_run --check` 改成呼叫 `repeat_check`。

量到的數字去哪：不寫回 `_metainfo`（「實測不回寫」；`deterministic` 布林是工具自己的宣稱，C-13）；寫進觀測帳，**按模型等級分開記**（C-22b：節點＝函式＋環境）。建議 key `repeat`，總格式交 evolve-design：

```json
{"step": "kb_link", "model": "terra", "runs": 3, "agreement": [0.9412, 0.9412, 0.9412], "measured_at": "2026-11-07"}
```

不做一個合成分數。報三樣：腳本步全部 `identical`（期望 100%）、每個 LLM 步的 `agreement`、整體 `identical/files`。

**(h) 降級階梯：`ladder`（lib 工具，取代 `exp_run_ladder.py`）**

```json
{"step": "tools/kb_link", "input": {...}, "levels": ["sol", "terra", "luna", "local"], "runs": 3, "threshold": 0.9, "reference": "sol"}
```

```json
{
  "results": {
    "sol":   {"agreement": [1.0, 0.9375, 1.0], "tokens": 6635, "seconds": 9.5, "errors": 0},
    "terra": {"agreement": [0.9412, 0.9412, 0.9412], "tokens": 7107, "seconds": 22.3, "errors": 0},
    "luna":  {"agreement": [0.4375, 0.8824, 0.0], "tokens": 13453, "seconds": 13.6, "errors": 1}
  },
  "pick": "terra",
  "failed": ["luna"]
}
```

每級序列跑（本機一次只能 load 一個模型；誰負責切模型是排程，交 kernel-nest）。`failed` 裡的那一級就是訊號 (c)：這一步在這一級做不到 → 拆更細、或把能寫死的部分抽成腳本，再跑一次階梯。`pick` 由審視者改進步驟定義（例：`place_run` 的 linker 模型設定）並 commit，不在流程跑的時候自動換（C-50 精神：agent 不自己數、不自己換）。時間與 token 已在結果裡，成本怎麼算進優化目標交 evolve-design。

### 2.3 各層誰負責

| 層 | 要做什麼 | 不做什麼 |
|---|---|---|
| **aos-exec** | 一行不改（S2） | 不讀 `_metainfo`、不認階段 |
| **aos-sandbox** | 設定檔參數接受 `檔#/json指標`（S4 已定，若尚未實作要補） | 不新增 key；不管階段 |
| **daemon** | 照舊：`--limits` 份額、setrlimit／setuid（C-04、C-64） | 不知道工具、不知道階段；不足 #11 另案 |
| **aos-tools** | 不改；`add`／`rm`／`ls --json` 已夠 | 不加階段欄位 |
| **lib 工具** | `bash`、`run_python` 加自記帳＋`arbitrary_exec` 宣告；新增 `shell_report`、`repeat_check`、`ladder` | 不讀 agent 的 history／observed |
| **agent 範本** | 不改（observed.jsonl 已有工具行） | 不記工具參數、不數連錯 |
| **agent 定義** | 謹慎期放 `tools/bash/` 包裝；轉階段＝改 `tools.json`／`tools/`＋commit | 執行中不被寫（P-15） |
| **試驗場腳本** | `place_run --check` 改叫 `repeat_check`；`meta_observe` 把 `shell_report`／`repeat`／`ladder` 收進 `_observed.json`；每單位開工設 `AOS_UNIT` | 不自己再寫一套比對 |
| **隊長／審視 agent** | 每單位做完跑審視五步：`shell_report` → 挑候選 → 交 gpt 寫工具 → `ladder`／`repeat_check` 重驗 → 依 (f) 轉階段並 commit | 審視 agent 怎麼長出來、能不能自己改別人的定義：交 evolve-design |

## 三、與既有條文的衝突

1. **C-13 九軸固定 vs 新增 `arbitrary_exec`。** 階段推導需要工具自己說「我是任意執行」；九軸裡沒有這一軸。C-14 允許人任意附加特性，所以可以當附加屬性放進 `_metainfo`。後果：當附加屬性，就是 KISS 但沒有「每個工具都要填」的強制；當第十軸，就動到九軸的定義。**推薦**：先當附加屬性，只有 `bash`／`run_python` 這類工具填 `true`，不填視為 `false`；是否升成軸交 evolve-design 在定 metainfo 總格式時一併裁。

2. **C-52 只管自己 vs `shell_report` 讀多隻 agent 的 `calls.jsonl`。** 讀別人 stack 裡的檔，形式上像偷看下層。試驗場審查已因同一條把「統計讀 history」改成「工具自己記、統計讀 log」。本規劃的解法：`calls.jsonl` 是工具在 `_tooldef`／`interfaces.json` 宣告的公開介面，讀者照宣告讀；跟 `observed.jsonl` 被 `meta_observe` 讀是同一性質。後果：若不接受，統計只能靠 agent 範本在 observed 記下工具參數——那是 agent 層替工具層記帳，也不乾淨。**推薦**：接受「宣告過的 log 檔就是公開介面」這個讀法；若要把它寫成條文，加在 C-52 的 11-06 讀法後面一句。

3. **「工具＝函式庫」條：bash 內層退非 0 不算工具的錯 vs 想量指令成功率（不足 #24）。** 不改條文：工具碼仍只管工具自己；內層退出碼寫進工具自己的 log。後果：兩個數字兩個地方，但各歸其層。**推薦**：照這樣做，不動條文。

4. **P-15／C-46 定義不被執行中寫 vs 「審視 agent」要改別人的定義來轉階段。** 現在由隊長（人）做沒衝突；第 5 個地點起交審視 agent 就撞上「改定義是人有意的事」。後果：允許，就有 agent 寫 agent 定義的路，需要 git 當閘（commit 可 revert、人可看 diff）；不允許，審視 agent 只能產出「建議 diff」給人 apply。**推薦**：本題只定「轉階段一律是定義改動＋commit」；審視 agent 能不能自己 commit，交 evolve-design（它管自我改進怎麼成為系統一部分）。

5. **`_metainfo` 條「實測不回寫」＋`deterministic` 是布林 vs 使用者要「確定性分層量」的數字。** 不衝突，但要說清：布林留在 `_metainfo`（工具的自我宣稱，C-13 任務自己的屬性）；量到的一致率進觀測帳、按模型分列（C-21 觀察者的認識、C-22b 節點含環境）。後果：兩本帳——這正是 evolve-design 在處理的「自我宣稱 vs 他者觀測」。**推薦**：本題只定 key 名建議 `repeat` 與記錄內容（step、model、runs、agreement），其他交 evolve-design。

6. **沙箱 S6 `rw: $AOS_WS` vs daemon stack 放在工作區裡。** 不是條文衝突，是事實上的坑（簡報 §4 已點名）：謹慎期一旦綁 `AOS_WS`，整台 daemon 跟著進沙箱可寫範圍。後果：沙箱形同虛設。**推薦**：試驗場把 stack 放工作區外；或謹慎期 `rw` 只綁 `$AOS_WS/<資料子資料夾>`。這條要寫進落地步驟的完成條件。

## 四、方向題

1. **階段是「宣告欄位」還是「從工具清單推」？**
   - 宣告：`agent.json` 多一格 `shell_stage`。好懂、一眼看到；但跟 `tools.json` 可能不一致，要另做機制去強制或對帳。
   - 推導：沒有欄位，`shell_report` 算出來。單一事實來源、零新機制；但人要跑一次腳本才看得到（或看 `_observed.json`）。
   - **推薦：推導**（C-56「寫什麼就做什麼」，避免兩個事實來源）。

2. **shell 的指令 log 放哪？**
   - 工具自己的小格 `$AOS_STACK/tools/bash/calls.jsonl`：零設定；統計者要走訪多個 stack。
   - 呼叫者用環境變數指一個共用檔（試驗場現做法 `AOS_BASH_LOG`）：統計只讀一檔；多一個設定、多一個「指到哪都行」的風險（C-80）。
   - **推薦：工具自己的小格**，跟 `observed.jsonl` 同一套讀法。

3. **階梯選出的等級，誰套用？**
   - 流程跑的時候自動套（`place_run` 讀 `ladder.json` 選模型）：少一步人工；但一個壞樣本就會讓下個單位自動降錯級，且違背「agent 不自己數」的精神。
   - 審視者改定義＋commit：多一步；每次降級有 diff、可 revert。
   - **推薦：審視者套用**。等審視 agent 成形再談自動（交 evolve-design）。

4. **確定性要不要一個合成分數？**
   - 要：一個數字好排名、好畫曲線；但腳本步 100% 跟 LLM 步 94% 怎麼加權是人為的，數字會掩蓋「哪一步不穩」。
   - 不要：報三樣（腳本步全同、各 LLM 步一致率、整體相同檔比例）。
   - **推薦：不要**，三樣分開報；要畫曲線就畫 LLM 步一致率。

5. **轉階段的門檻數字。** 本規劃暫定「連續 2 個單位」（open→boxed：執行檔集合不再新增；boxed→none：shell 呼叫為 0）。這數字原則推不出來，沿用 09「連過兩個地點就降一級」的手感。選項：2 或 3。**推薦：2**，跟現有降級規則一致，錯了有 revert。

## 五、落地小步（交 gpt 照圖施工）

每步一句完成條件；順序可照做，1、2 無相依可並行。

1. **`lib/base/bash` 自記帳**：每次呼叫在 `$AOS_STACK/tools/bash/calls.jsonl` 追加一行 `{time, unit, command, timeout_s, exit, elapsed_ms}`（`unit` 抄環境變數 `AOS_UNIT`，沒有就空字串），寫失敗退 `LogFailed` 不跑指令；`_metainfo.json` 加 `"arbitrary_exec": true`；`_tooldef.json` 或 `interfaces.json` 寫明這一行的 schema；`run_python` 同樣處理。
   完成：叫三次（含一次內層 `exit 1`）後檔案剛好三行、`exit` 欄等於內層退出碼、`aos-tools ls --json` 看得到 `arbitrary_exec`。

2. **aos-sandbox 設定檔接受 `檔#/json指標`**（若已支援，寫一行確認即可）。
   完成：`aos-sandbox _metainfo.json#/sandbox true` 跑通，且 `ro`／`rw` 沒列的路徑在裡面 `ls` 不到。

3. **謹慎期包裝範本**：把 `cmd/aos-sandbox/examples/bash-boxed/` 改成 §2.2(d) 的樣子（`_entry` 指 `_metainfo.json#/sandbox`、`_metainfo` 帶 `arbitrary_exec` 與 `sandbox`、`sandbox.json` 刪掉）。
   完成：以它為 `tools/bash` 的 agent 跑 `rg` 成功、跑 `curl` 得「找不到指令」、寫 `/tmp/x` 失敗、寫 `$AOS_WS/x` 成功。

4. **`lib/<層>/shell_report`**：stdin `{"stacks": [路徑…]}`，對每個 stack 跑 `aos-tools ls --json` 推階段（§2.1 三條規則）、讀 `tools/*/calls.jsonl` 歸形狀（shlex、分管線、保留第一字與 `-` 開頭、其餘 `<arg>`），輸出 §2.2(b) 的 JSON。
   完成：用三份假 `tools.json`（lib bash／boxed 包裝／沒 bash）分別回 `open`／`boxed`／`none`，且對試驗場婆山鎮＋切爾諾伯格的 log 跑出含 `units` 兩項的 shapes。

5. **`lib/<層>/repeat_check`**：stdin §2.2(g) 格式，三種 `compare`（`bytes`、`by_item`、`tree`），每次在暫存資料夾跑目標、比完刪暫存。
   完成：`place_run --check <slug>` 改為呼叫它，對婆山鎮回 README／source／tags `identical`、`differ` 只有 LLM 連結檔，`by_item` 對 linker 回 15/16。

6. **`lib/<層>/ladder`**：stdin §2.2(h) 格式，每級序列跑 `runs` 次、對 `reference` 級第一次結果用 `by_item` 比、回 `results`／`pick`／`failed`；`exp_run_ladder.py` 與 `linker-ladder.json` 退場。
   完成：重跑婆山鎮 linker 梯，`pick` 為 `terra`、`failed` 含 `luna`，輸出存 `ladder.json`。

7. **`meta_observe` 收三樣**：每定義的 `_observed.json` 加 `shell_stage`（來自 `shell_report`）、`repeat`（來自 `repeat_check`，按 step×model 一筆）、`ladder`（最近一次 `pick` 與 `failed`）；key 名先佔位，總格式待 evolve-design。
   完成：地點主管與 linker 的 `_observed.json` 都有這三個 key 且值非空。

8. **試驗場第一次轉階段**：隊長依 `shell_report` 給地點主管寫 `tools/bash/` 包裝（白名單＝報告 `binaries`），stack 移出工作區或 `rw` 只綁資料子資料夾，commit 一筆。
   完成：`shell_report` 回 `boxed`、地點 3 跑通、`git log` 有這一筆、沙箱內寫 `/tmp` 失敗。

9. **審視五步補「階段轉換規則」三條**（§2.2(f)）進試驗場流程文件，並把 `bash_logged` 從試驗場 `tools.json` 與 `defs/` 移除。
   完成：文件連結齊、`wf-lint` 過、兩地點重跑 `repeat_check tree` 結果與第 5 步相同。
