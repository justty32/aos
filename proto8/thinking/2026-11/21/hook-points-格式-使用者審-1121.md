使用者 11-21 審 hook_points.json 宣告格式時說的話（逐字，陸續追加）：硬性只要 id 與 input schema，其餘鍵想放啥放啥。

← [2026-11-21](README.md)｜前情：[aos-home-瀏覽筆記-1120 第 2、3 則](../20/aos-home-瀏覽筆記-1120.md)（「我要審過，並且會提出建議，比如直接拿json schema或許會更好」）、[宣告格式設計稿](../20/aos-hook-plan-1120/01-宣告格式.md)

只記錄，還沒派線、沒改程式。對應寫法是頂層的整理，原話以引號內為準。

## 第 1 則：一份只有一個 provider、預期更簡單

頂層簡述現行格式（一份檔＝一個 provider 的全部點；每點有 when、phase、fields、condition、subject、change、block、if_blocked、if_failed、key、fired_in、entry_keys）後，他說：

「hook_points.json只能有一個provider，是否有些不妥？我預期他這個會比較簡單一些，反正就是宣告，所以可能就是一個id，配上description，然後用json schema描述handler會收到啥這樣？」

## 第 2 則：硬性只有 id 與 input schema

頂層攤出「schema 只講得了 handler 收到什麼，block、change、condition、subject、entry_keys、key 沒地方放；change 可以改成 output schema」後，他說：

「一些雜七雜八的屬性比如block,if_blocked,if_failed，乃至於phase都可以寫，這些都不是硬性影響，他就是宣告說我大概會怎樣，阿具體實作怎麽應用就後續再說。change改output schema，然後condition,subject,entry_keys也都可以。我會覺得反正就是硬性規定要有id，要有input schema，剩下其他key就是想放啥放啥。然後你說aos-loop的點放在aos自己那邊...等等，這塊可以說清楚一些嗎？」

### 整理（頂層的理解）

- **硬性規定**：每個 hook 點要有 id、要有 input schema（JSON Schema，描述 handler 會收到什麼）。
- **其餘鍵想放什麼放什麼**：block、if_blocked、if_failed、phase、condition、subject、entry_keys 都可以寫，是「宣告說我大概會怎樣」，不是硬性影響；具體實作怎麼用，後續再說。
- **change 改成 output schema**。
- 一份只有一個 provider 妥不妥：他問了、還沒定；他接著要頂層把「aos-loop 的點放在 aos 自己那邊」說清楚。

### 還沒問的

- 「id」是點的名字（現在 `points` 底下的鍵）還是另外一欄；description 算不算硬性。
- 現在程式會讀 block、change、condition 等鍵來擋 handler 與檢查掛法（頂層的印象，沒逐行查證）；改成「想放啥放啥」後這些檢查留不留。

## 第 3 則：provider 寫 aos-loop，看不出哪來

他看了 ann 的 `interfaces.json` 寫 `"hook_points": [{"provider": "aos-loop"}, "hook_points.json"]` 之後說：

「尷尬，這個宣告我覺得不妥，hook_points:[...]這塊，你provider寫aos-loop，我哪知道這個aos-loop是哪來的。幫我派線去規劃，看看有沒有類似C語言#include那樣的感覺，或是類似指示詞那樣，並且兼容指示詞的」

已派線 top-1121-hpinclude 出規劃稿：[hook-points-引入寫法-1121](hook-points-引入寫法-1121/README.md)。

## 第 4 則：hook_points 寫檔名或直接寫內容

「然後interfaces.json中，應該是hook_points:"hook_points.json"這樣，當然，也可以直接hook_points:[...]，都可以。」

頂層的讀法（他在第 5 則確認了）：`hook_points` 的值是字串＝指到一份宣告檔；也可以直接把宣告內容寫在那裡，`[...]` 是一串 hook 點的宣告，不是現在「provider 名字＋檔名」的清單。別家的點怎麼進來，靠宣告內容裡的引入寫法，不靠 `interfaces.json` 並列。

## 第 5 則：也可以寫 {...}，就是 id 放哪

頂層問「直接寫 `[...]` 時，每個點的 id 是陣列每項自己帶，還是改成物件、用 id 當鍵」，他答：

「對，然後除了[...]之外也可以用{...}，就等於把id放哪。」

### 整理（頂層的理解）

- `hook_points` 的值三種都收：字串（指到宣告檔）、陣列 `[...]`（每項自己帶 id）、物件 `{...}`（id 當鍵）。

## 第 6 則：定案——新格式、檔名與 interfaces.json 的寫法

看過桌面頁（`~/Desktop/aos-hook點宣告-1121.html`）與 kernel 宣告那頁之後，他說：

「hook point這塊，我決定就是新格式，block,if_block那些都不用，有需要的自己在input schema裏面添加，或是另外自己隨便加key。然後interfaces.json中，我要改成"hooks":...，值可以是string, array of string，ps.interfaces.json必須支援指示詞，pss.應該改成hooks.json, hookeds.json，hooks表示有哪些鉤子，hookeds表示有哪些被勾着。然後hooks:...，那些string就是檔名，檔案就是一個obj，就是新格式。kernel你說的這塊我再想想」

### 整理（頂層的理解，原話以引號內為準）

- **格式定案＝新格式**：一份檔是一個物件，鍵是 hook 點的 id，值裡硬性要有 input schema。`block`、`if_blocked` 那些不是格式的一部分；有需要的自己寫進 input schema，或自己另外加鍵。
- **`interfaces.json`**：宣告 hook 點的鍵叫 `"hooks"`，值是字串或字串陣列；字串就是檔名，檔案內容就是上面那種物件。
- **`interfaces.json` 必須支援指示詞**（所以別家的點——例如 aos-loop 那四個——用指示詞寫出路徑放進陣列即可，不必另外發明引入寫法）。
- **檔名對調**：`hooks.json`＝有哪些鉤子（hook 點的宣告，現在叫 `hook_points.json`）；`hookeds.json`＝有哪些被勾著（掛上去的 handler 清單，現在叫 `hooks.json`）。
- **kernel 那邊**（宣告不在 `interfaces.json`、見 `kernel-宣告在哪-1121.md`）：他「再想想」，不動。

### 對照規劃稿的四題

1. 引入怎麼寫：不採甲～戊；`interfaces.json` 的 `hooks` 陣列＋指示詞。
2. `block`／`condition`／`entry_keys` 讀不讀：都不是格式的一部分（「都不用」）。
3. 動態或靜態連結：照陣列裡的檔名／指示詞執行時去讀，等於動態連結。
4. 物件寫法哪些鍵不是點：他沒提。

### 還沒問的

- 11-21 第 4、5 則說過 `hook_points` 的值也可以直接寫 `[...]`／`{...}`（內容直接寫在 `interfaces.json`）；這一則只說「string, array of string」。直接寫內容還收不收，沒問。
- `interfaces.json` 裡指到 `hookeds.json` 的那個鍵叫什麼（現在叫 `hooks`，這個名字被拿去指 hook 點了）。
- 程式現在靠 `block: true` 才准 handler 攔、靠 `change` 驗 handler 回的欄位、靠 `condition` 比對、靠 `entry_keys` 驗掛法；這些鍵不再是格式之後，引擎怎麼辦（一律交給發事件的那支程式自己決定？），沒問。
- `change` 改成 output schema（第 2 則）還算不算。
