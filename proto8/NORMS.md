# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜語法糖：[lib/](lib/README.md)、[proto8-1](../proto8-1/README.md)

**比起實作，更重要的是規範**（C-45）。三層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔 |
| 語法糖 | 符合規範、方便用，**不要求一定用** | proto8/lib（inst、loop、daemon）、proto8-1（tasks、aos-tick） |

本檔只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。

## 定了的

### 時空（來自 C-05、C-37、C-44）

- **N-01** 大家都要看 tick-tock 時鐘。（10-12）
- **N-02** 資料夾別亂弄。（10-12；「亂弄」具體指什麼還沒定，見待定）
- **N-03** 「tick 之間可以安全打包」是大家要遵守的規範，不強制；打包由 kernel 做。例：kernel 在公告欄說「大家，咱們第 1021 回合準備關機下線，在那之前所有人把狀態保存到檔案，逾時不候」。（10-12）

### inst.json（來自 C-42b）

- **N-04** inst.json 裡可以多放東西，inst 不認的別人可以讀。（3g.13b）

### 控制（來自 C-36；使用者 10-12 夜授權「ctl 規範你可以開 agent 去定」、拍板「沒寫的回初始值，其他都照建議」，條文照 [thinking 10-12 ctl 規範](thinking/2026-10-12-ctl-norms.md) 寫入）

- **N-05** 給別人讀的檔，先寫 `.` 開頭的暫存檔再改名蓋過去；讀的人不讀 `.` 開頭的檔。這是 N-02 的細則之一；ctl.json、state 檔、`.done`、save 檔、時鐘檔都照這條。（10-12）
- **N-06** 控制一個會反覆跑的東西（loop、daemon）＝改它的 ctl.json。ctl.json 寫的是「我要它現在怎樣」，不是一條條指令：整份就是全部的期望，寫幾次都一樣；沒寫的欄位＝回它起來時那份檔（loop.json／daemon.json）的初始值，不是維持上一版；讀的人只讀不寫；誰都可以寫，後寫的算。（10-12）
- **N-07** ctl.json 認兩個旗子——`paused`（不再起新的一次）、`stop`（這次跑完就結束）——各寫成 `{"val": 布林, "now": 布林}`，`now` 為 true＝不等這次跑完、當場收掉；只寫布林＝只給 `val`；`stop` 壓過 `paused`。加上能蓋過 loop.json 外層執行方式的那幾個 key（`times`、`interval_ms`、`interval_mode`）。不認的 key 照 N-04。（10-12）
- **N-08** 讀 ctl.json 的人定期看；讀到壞的、型別不對、檔不見了，整份不採用、維持上一次的好狀態、印一次、不退出。（10-12）
- **N-09** 要回報狀態，寫到另一個檔（state），不碰 ctl.json；一個 state 檔只有被控制的那個東西自己寫；選填。（10-12）
- **N-10** 指令式控制＝往資料夾放 `名字.json`，一個檔一條指令；處理完變成 `名字.json.done`，內容是一問一答 `{"request", "ok", "result"|"error": {"code", "msg"}}`；`.done` 只在終局才出現；`ok` 是唯一要看的，`code` 只供參考；`.done` 由丟指令的人清。（10-12）
- **N-11** 設定檔、ctl、state 是同一條線：設定檔（inst.json／loop.json／daemon.json）整份只在起來時讀一次（含 loop.json 裡的 `inst`），跑的途中要改只能走 ctl.json，ctl 蓋過設定檔，state 回報實際生效的值。三者裡節奏類的 key（跑幾次、隔多久、間隔怎麼算）同名；ctl 能蓋的只有這一類，位置、身體、收尾類的 key（`ctl`、`state`、`inst`、`grace_ms`…）不能從 ctl 改，要改就停了重起。state 的欄位、狀態值是慣例，見 [lib README](lib/README.md#ctl-與-state-的慣例)。（使用者 10-12 夜）

### 呼叫程式的 stdio（來自 [thinking 10-14 JSON 入口](thinking/2026-10-14-json-entry.md)）

- **N-12**（10-14 定，草稿）可供呼叫的程式回歸 POSIX 原始本意：stdin＝參數，stdout／stderr＝結果，exit＝輔助。在 aos 規範中三者都是 JSON 串流（放寬：一串 JSON 值接著一串，每份可單行或跨行；只有一份就是普通 JSON）。stdin 有多份時，整串是一次呼叫，意思由程式自己解讀、寫在它的說明裡，規範只管格式。跑完的判定＝exit 檔出現。JSON 串流視為省略最外層 `[]` 的陣列，`檔#/位置` 照陣列索引指。inst.json 格式不變（作為與舊時代的橋樑）；規範管的是 inst 所呼叫的 argv[0] 程式。aos-inst／loop／daemon 之後也照本條重做（10-14 使用者定，還沒動工）。（10-14）

## 待定（AI 整理的候選，使用者還沒定）

- **資料夾別亂弄的細則**：能不能動別人的資料夾、哪些檔是誰的。（「寫檔要不要先寫暫存再改名」已定＝N-05。）
- **argv[0] 程式的規矩**（10-12 做 tasks 時試出來，使用者同意「規範比實作重要」這個方向，細則沒定）：
  - 結束碼：0＝成功；自己的失敗用 1～123；124 以上有慣例意思（124 timeout、125～127 包裝程式自己出錯／不能執行／找不到、128＋N 訊號）。（10-12 夜使用者定：只有 0／非 0 是確定的，其他數字只供參考。aos_inst、aos_loop 的退出碼只說自己有沒有出錯，子程式的碼只寫進 inst.json 的 exit 檔；125～127、128＋N 只是參考用的慣例。）
  - 收到 SIGTERM：收好自己起的子程式再退出。
  - 不自己 setsid 跑出行程群組（不然 daemon 整群收收不到）。
  - 錯誤寫 stderr。
- **kernel 公告**：公告欄在哪、格式、看到的人要做什麼、「逾時不候」之後 kernel 怎麼處理沒存好的。
- **時鐘**：回合數怎麼讀（aos-tick 的檔＝十進位＋換行）算不算規範，還是只是 aos-tick 這個語法糖的格式。
- **路徑寫法 `檔#/位置`**（JSON pointer）要不要列成大家都遵守的規範——出處 [thinking 10-13](thinking/2026-10-13-json-path.md) §3、§3.2。
- **`_metainfo`**：inst.json 裡給 kernel 參考的抽屜（九軸、資源特性），inst 格式的可選 key（地位同 `argv`）、inst 與標準實作忽略；裡面格式自由，通用的寫法（含資源）之後規定——出處 [thinking 10-13 §3](thinking/2026-10-13-json-path.md)。
- ~~**ctl 格式**~~（**已定**，10-12 夜＝N-05～N-10；細節與慣例在 [thinking 10-12 ctl 規範](thinking/2026-10-12-ctl-norms.md)，出處 [thinking 10-12 loop／daemon](thinking/2026-10-12-loop-daemon.md)。兩種都算規範：宣告式 ctl.json N-06～N-09、指令式資料夾 N-10；「什麼時候用哪一種」沒定成規範。）
- ~~**巢狀 grace**~~（**已定：只當慣例，不進規範**，使用者 10-12 夜。NORMS 沒有放慣例的段落，慣例就記在這：`grace_ms` 建議值（也是程式的預設）inst 2000、loop 5000、daemon 10000；外層宜大於內層；設錯自己負責。不加進 argv[0] 規矩。）
