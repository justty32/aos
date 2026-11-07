另一帳號對 arknights 第二輪三個地點節點的獨立抽查結論：原文、tag、成本數字都對，連結漏了一處「博士」，根因是找提及的腳本有個會吃掉短名字的毛病。

← [2026-11-07](../README.md)｜被查的設計 [arknights-kb/10](../arknights-kb/10-第二輪設計.md)｜請求信 G（20261107T1532-aos-a0-G-REQUEST）

## 白話總結

抽查的是 `~/code/playground-ak` 在 HEAD `836bd25` 時的知識庫 `ws/kb-ak2/`：婆山鎮、切爾諾伯格、龍門三個地點。查到一半 HEAD 前進到 `cce44ca`，但只多了一個 `runs/2/b4/final-checks.json`，被查的節點與報告都沒變。

原文存檔是對的。三個 `source.json` 的段落接起來，和語料原檔逐 byte 相同，sha256 也對得上。tag 用程式從語料的 `places/INDEX.md` 重新抽一遍，結果完全一樣。B2、B3、B4 三份報告裡的 token、呼叫次數、秒數，從最原始的觀測紀錄重新加總，也全部對得上，兩層 kernel 帳沒有重複相加。

真正的問題在連結。切爾諾伯格第一次出現的「博士」（「博士甦醒的起點」）沒有連到。原因是找提及的腳本 `defs/kb_mentions` 一律先挑最長的名字，而語料的證據資料夾裡剛好有一個檔名叫「博士甦醒」，就被它先挑走了。這個檔不屬於可連的類別，所以接著被丟掉，可是那四個字已經被跳過，裡面的「博士」就跟著漏掉。三個地點只有這一處中招，但地點越多，這種情形會越常見。

命名方面沒有撞名。不過英文名有三種寫法混在一起，而且有一個實體拿到兩個名字；單字人名用不帶聲調的拼音，日後一定會撞。

## 逐項結果

| 項 | 結果 | 問題數 |
|---|---|---:|
| 1 原文逐字 | 通過 | 0 |
| 2 連結 | 有問題 | 1 個漏連＋3 個小問題 |
| 3 tag | 通過 | 0 |
| 4 命名 | 有問題 | 3 個（無撞名） |
| 5 報告數字 | 通過 | 0（1 個欄名提醒） |

<details><summary>1 原文逐字：通過</summary>

腳本是 `a1_source.py`。它把 `"\n".join(paras)` 拿去和三個版本比較：語料磁碟檔、語料 git HEAD（`5d9bedd`）、playground 自帶的 `ws/corpus` 複本。三地都 `True`。

- `sha256` 欄與原檔相符。
- 原檔沒有 CRLF、沒有 BOM，結尾換行由最後一個空段保留。
- README 都是 `# 中文名 (slug)`。
- `runs/2/places/{poshan-b4,qieernuoboge-b4,longmen}/node/` 快照與現行節點的四個檔逐 byte 相同。

</details>

<details><summary>2 連結：1 個漏連＋3 個小問題</summary>

先用程式確認基本面：

- 每條 span 切出來的文字都等於連結名或已知別名。
- 所有 lore 目標檔都存在。
- `ok` 連結指向的節點（`ak/places/qieernuoboge`、`ak/places/longmen`）存在。
- 目標數與 span 數 5/12/15、16/19/24，與報告相同。
- 兩個別名照語料查證過，都正確：「煮傘居士」→夕（`characters/夕.md` 有寫）、「炎武」→魏彥吾（`characters/魏彥吾.md` 出現 2 次）。
- 「除夕」裡的「夕」、「四十年前」裡的「年」都沒有誤連。

**問題 2-1（漏連，最重要）**：切爾諾伯格 `paras/2` 位置 [20,22] 的「博士」沒有連，同一條連結的另外兩處（64、269）有連。

- 根因在 `defs/kb_mentions/kb_mentions.py` 第 146～200 行。字典用 `rglob` 收了全部 lore 檔名，包括 `lore/evidence/activities/act33side_巴别塔_2/博士甦醒.md`。比對時先取最長的名字，之後才過濾 `LINKABLE_CLASSES`。過濾掉之後執行 `offset += width`，四個字一起跳過，裡面的短名字就沒機會被比到。
- `a2_shadow.py` 把三地全部掃過一遍，只有這一處被長名字遮住。
- `runs/2/places/qieernuoboge-b4/mentions.json` 裡也確實沒有 [20,22]。所以這不是 linker 判錯，是 linker 根本沒拿到這個候選。

**問題 2-2（小）**：龍門的「陳暉潔」出現兩次，span 都只標了第一個字「陳」（at 186、317）。語料沒有 `陳暉潔.md`，所以腳本只比得到「陳」。這樣連的人是對的，但 span 沒有蓋住整個名字。

**問題 2-3（小）**：有兩處算是語意上的漏，字串比對本來就抓不到：

- 龍門的「近衛局」（語料有 `factions/龍門近衛局.md`）。
- 龍門的「大炎」（指炎國）。

這屬於設計裡 linker 該處理的「表外提及」，目前沒有處理。

**問題 2-4（格式，小）**：

- `by` 有時是字串、有時是 map（B4 報告說是刻意的）。
- pending 的 `to` 寫 `lore:characters/夕.md`，10 號設計原本要填 `ak/characters/xi`、lore 路徑另記。
- 別名表目標寫法不一：人物指 `lore/characters/X.md`，地點指 `places/<slug>`；地點表還把 README 標題字串收成別名。

</details>

<details><summary>3 tag：通過</summary>

腳本是 `a3_tags.py`。它從語料 `lore/places/INDEX.md` 的 `##` 小標重新抽 `group:`，類別資料夾則當 `class:`。三地的期望值與實際值完全相同，例如婆山鎮是 `class:places`、`group:炎國／歲`。檔裡沒有任何非機械抽出的 tag。

</details>

<details><summary>4 命名：無撞名，3 個問題</summary>

- names.tsv 有 47 列，slug 與中文名都沒有重複。資料夾名、README、`ok` 連結三處的 slug 一致。
- **4-1 同一實體兩個名字**：「煮傘居士」在別名表裡是夕的別名，但 names.tsv 又給了它自己的 slug `zhu-san-ju-shi`（`characters`，`llm:luna`）。日後如果照名字表建節點，會多出一個假人物。
- **4-2 拼法混三種**：
  - 地點是整詞拼音，只在通名前加連字號，例如 `poshan-zhen`、`dahuang-cheng`。但同樣以「姆」結尾，`lundinimu` 沒拆，`miliyaliu-mu` 卻拆了。
  - luna 新取的名字逐音節加連字號，例如 `hua-zhong-ren`、`zhu-san-ju-shi`。
  - `羅德島` 卻用英譯 `rhodes-island`。
- **4-3 單字人名必撞**：不帶聲調的拼音，讓語料裡現成的單字人名兩兩同音：黎／礫都是 `li`，吽／紅都是 `hong`，令／澪都是 `ling`。現在只建了黎，所以還沒撞；但目前沒有消歧規則，namer 只會把查不到的名字丟給便宜模型。

</details>

<details><summary>5 報告數字：通過</summary>

由 opus 子 agent 從各趟 `raw/*/observed.jsonl` 重新加總，再用信名逐筆對隊 kernel 的 `ledger.jsonl`。

- B4 正式三地 12,647 token／3 calls、階梯 15 趟 47,038 token、失敗 4,370 token、總計 64,055／19 calls、174.640682 秒，全部加得出來。
- 四個降幅（34.14%、53.32%、11.73%、62.31%）重算一致。
- B2、B3 主表與 curve.json、steps.json 一致。B2 kernel 快照的 113,160 token 由五項剛好加滿。
- 總機鏡像沒有被加進帳。
- luna-1、luna-3 判無效是對的：它們替只有 1 個候選的「陳」給了不存在的第 14、15 號。

唯一提醒是欄名：階梯表「含載入 wall 秒」在 gemma-12b-1、e4b-1 兩趟，是把 agent 的 time_s 加上顯式載入秒，不是 `task_wall_clock`。報告內文有說明，但欄名容易誤讀。

</details>

## 給隊長的建議

1. **先修 `kb_mentions`**：最長比對前就把不可連的類別排除，或者至少不要從 `evidence/` 收名字。被過濾的長命中不要整段跳過，要退回去試較短的名字。修完用 `place_run --check qieernuoboge` 確認多出 [20,22] 的「博士」。這會讓規則連結和快照不再相同，要照設計重做比較。
2. **namer 先查別名表**：查到就不另給 slug，並刪掉 `zhu-san-ju-shi`。
3. **slug 定一條拼法**：例如一律整詞拼音、只在通名前加連字號，不用英譯。同音時加類別或序號後綴，例如 `li-2`，寫進名字表的規則。
4. **小事可延後**：span 蓋住整個「陳暉潔」、pending 的 `to` 改照設計填 `ak/…`、`by` 統一型別、階梯表欄名改成「time_s（含載入）」。

稽核腳本在當次 session scratchpad 的 `audit-g/`（`python3 -I` 唯讀跑，不保證留存）；全程未寫 playground-ak、語料或 repo 其他檔。
