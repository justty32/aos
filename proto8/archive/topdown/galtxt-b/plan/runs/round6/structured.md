# round6 結構化場景：人物／地點／事件拆成一格一事實（10-25）

← [round6](../../round6.md)｜使用者 10-25「場景條件，背景故事，人物設定，都可以用結構化來表示，也就是json，拆的愈散，後續愈方便。」｜程式 [brief/_entry](../../../brief/_entry)、[lib/lint](../../../lib/lint/_entry)｜表 [brief/tables/](../../../brief/tables/)｜比對 [structured/compare.py](structured/compare.py)（改前產出在 [structured/before/](structured/before/)）｜測試 `test_topdown_galtxt_b_round6.StructuredScene`（假腦 6 個）｜真腦 0

## 做法

- **cells/1 卡**（cast 的主角、宮澤柚葉；places 的河鹿堂；新表 events.json 的進新書日）：卡＝幾個組（`identity`、`facts`、`tone`、`patterns`、`habits`、`ng`、`budget`、`catchphrases`、`canon`、`hooks`、`senses`、`wrong_names`、`opening`、`beats`、`guards`、`props`），組＝`{鍵: 格}`；格是純量，或 `{"text"/"value", 標記…}`（`kind: 反差／洩底`、`step`）。`_layout` 是組回舊形狀的版面：`@g`＝整組依序成陣列、`@g/k`＝一格、含 `{g/k}` 的字串＝模板（`{g/$開關}` 代入題目 switches）、其餘照抄。
- **其他表**：address 每階 allowed／forbidden 與 rules、banned.rules 改成 `{鍵: 句}`；openers 每句加 `id`；banned A/B/C、beats、samples 本來就一項一格（詞／拍名／benchmark 當鍵），不改形。停用的森下晴子、木下柚葉不動（舊形狀，整張當一格 `cast/森下晴子`）。
- **格 id**＝`<表>/<路徑>`，段照 JSON 指標跳脫（`banned/A/~1~1~1`＝「///」）。
- **brief.json 多 `cells_used`**＝`{格 id: [落在稿紙的 JSON 指標…]}`（模板的格多個落在同一個指標）。其餘欄位**逐字不變**：compare.py 對四題＋examples 兩題＋關 samples 那次，`json.dump(indent=1)` 的文字 diff 為空 → 不必重跑真腦。
- **lint** 用 cells_used 反查：稱呼 forbidden、禁詞、穿幫詞、感嘆號／句長預算、口癖的違規多帶 `cell`（口癖另帶 `limit_cell`）；指標沒格就往上找（舊卡指到整張）。只加欄，violations 其餘一模一樣（測試比過）。
- **事件**：題目檔凍結、仍是散文。brief 拿同地點同兩人的事件卡照 switches 組一次，**逐字相同才記格**（4 題都對得上：15 格／題）；對不上＝表外散文，不記（表跟題目脫鉤看得見）。新題可寫 `"event": {"ref": "進新書日"}` 由格組出。

## 粒度與格數

判準：**拆到程式會單獨查／改／歸因的最小單位為止**；再細（一條 canon 裡的兩個子句、一個感官裡的三種氣味）沒有程式會分開用，只是噪音。

| 表 | 格數 | 這題用到 |
|---|---|---|
| cast 主角／宮澤柚葉 | 33／36 | 全用 |
| places 河鹿堂 | 29 | 全用 |
| events 進新書日 | 21（含 identity 4，不進稿紙） | 15 |
| address | 49 | 10（階 1 兩個方向＋rules 3） |
| banned | 52 | 52 |
| openers／beats／samples | 11／8／4 | 2／8／1 |
| **計** | **243** | 柚葉題 189、examples 139 |

## 哪些拆了有用

- **被程式查／歸因**：稱呼 forbidden（lint address → `address/heroine_to_hero/1/forbidden/surname_bare`）、禁詞與穿幫詞、`budget/*`（lint＋trim 讀）、`catchphrases/*`（lint＋trim）、identity（brief 代名字）。check 打回、record 算梯度時能說「這次扣分是哪一格」。
- **控制變量**：改一格只動引用它的欄位（測試：改口癖格 → 稿紙只變 `/cast/1/catchphrases/0`）；`opening/<誰先>`、`props/<道具>` 直接對上 switches 兩個開關，加題＝加一格。
- **留給下一步**：`tone/deny`→`yield`→`cover`（step 1～3）就是 round6 §1c `hand_over` 句式表的三段；`kind: 反差／洩底` 標記讓評分維度（反差、洩底）能指回人物卡哪幾格。

## 哪些拆了沒用或不該拆

- **profile 事實、tone 片段、patterns／habits／ng**：現在只有腦讀（拼回一段字），程式不單獨查；拆開的好處只在 ablation（關一格）與歸因，還沒被用到。
- **samples**：給腦的風格示範，整段才有節奏，拆句會毀掉它——整段一格。
- **canon 一條一格不再細分**、**senses 一種感官一格**：沒有程式分開用子句。
- **beats.constraints**（c1～c4）：plan_lint 整套照著寫在程式裡，不記格。

## 要不要長成資料夾（C-72）

留 JSON。判準是檔案系統特性：要不要單獨權限、單獨被寫、單獨 git 追蹤——現在只有人（之後是 distill/）整表改、brief 整表讀，一張卡沒有自己的寫者。哪天 teach／優化器要**只寫某張卡的某組**（例：柚葉的口癖由 train/apply 改），就把 `cast.json#/宮澤柚葉` 長成 `tables/cast/宮澤柚葉/{catchphrases,tone,…}.json`；格 id 不變（段一樣），brief 的讀法換成走資料夾。

## 偏離與限制

- 動了兩支別的測試（只為表示法換了）：`test_topdown_galtxt_b_train.Scope.test_card` 改看 brief 組回來的卡；`test_topdown_galtxt_b_fold.Fold.test_pack` 的表名集合加 `events`。
- lib/lint 宣告 `frozen: true`，這次只加輸出欄（cell、limit_cell），規則與分數不變。
- 模板格的位置是整段（`/cast/1/profile`），指不到段內第幾字。
