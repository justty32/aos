← [回入口](../2026-10-24-metainfo.md)｜上一份：[01-位置與格式](01-位置與格式.md)

> 以下全部是使用者 10-24「都按建議做」之後照推薦定的（可翻案），條文還沒落。

<a id="1-誰讀"></a>
## 1. 誰讀

- **aos-exec 不讀**：10-13 D4「aos inst 與所有標準實作一律當它不存在」；現況 `run_inst` 只驗 10 個 key、其他忽略（N-04）。寫了 `_metainfo` 不改任何執行行為（C-56 寫什麼就做什麼：該強制的寫在 `timeout_ms` 這種 inst key 裡）。
- **loop、fsm、daemon 不讀**：它們只管跑（N-36 fsm 不碰格的內容），格的特性跟它們無關。
- **閘門（aos-gate）只搬不看**：`_metainfo` 是單子的一個 key，閘門寄的信本來就帶整張單子，不用多做事。
- **kernel 讀**：LLM kernel 拿來排順序（§ 5）；通用 kernel 照 `resource` 佔 `slots`、把 `summary` 等交給判官看（10-15）；要不要跑、怎麼排，是 kernel 自己的演算法（10-13「隨便」）。
- **agent 與腦不讀**：agent 不知道有 kernel（C-20）；模型看的是 `tool.json`（P-41），`_metainfo` 不進 prompt——使用者 10-15「小 LLM 模型的判斷力不足，會被這個搶走注意力」。`tool.json` 與 `_metainfo` 不合併（M10）。
- **人與 AI 工具**：當函數的 `ls -l` 看；屬性統一後可以查（「列出所有 `side_effect: true` 的工具」，10-13 對照表最後一列）。

<a id="2-宣告與強制time_ms-與-timeout_ms"></a>
## 2. 宣告與強制：`time_ms` 與 `timeout_ms`

- `timeout_ms`（inst key）＝**強制**：aos-exec 到時間就收掉，是唯一會殺人的。
- `_metainfo.time_ms`＝**宣告**：作者說「通常多久、最多多久」，只給 kernel 規劃。kernel **不照宣告殺人**。
- 兩個都寫、數字不同：照 D5「重疊管他呢」，各管各的；實際停在 `timeout_ms`。
- `time_ms.max` 沒寫時，kernel 可以拿單子的 `timeout_ms` 當上限參考（那是事實，不是猜）。

<a id="3-宣告與實測"></a>
## 3. 宣告與實測

- 10-13「自報給規劃、實測給驗證」：實測**放 kernel 自己的 `$AOS_STACK`**，絕不回寫使用者寫的 `_metainfo`（那是作者的契約）。
- kernel 每跑完一封，在它已經在寫的那行紀錄（LLM kernel 的 `$AOS_STACK/served.jsonl`）記實際花了多久（`elapsed_ms`）與宣告的 `time_ms`；統計（平均、最大）誰要誰自己從 jsonl 算，不另開檔。
- 要按函數累積統計，得知道信是哪個函數的：請閘門在信裡多帶單子的位置（`檔#指標`），見 § 5 第二步。

<a id="4-邊緣狀況"></a>
## 4. 邊緣狀況

- **宣告錯**（說 1 秒、跑了 1 小時）：只有 `timeout_ms` 收得掉它；kernel 被騙排到前面，代價由等待的人付，aging（每等 10 次升一級，10-15）保證別人不會一直等。照 10-15「濫用：先信任」，kernel 只在實測紀錄裡記 `elapsed_ms` 超過宣告 `max`，不處罰（N-18 入口默認正常）。
- **沒寫**：就是沒說。LLM kernel 同級同時限時，有寫 `time_ms` 的排在沒寫的前面（短的先）；通用 kernel 照 KISS 1.8，`resource` 沒寫＝`ResourceUnknown`。
- **寫壞**（`time_ms` 是字串、`resource` 是數字）：kernel 把**那一個 key** 當沒寫、在實測紀錄記一筆，照樣跑——`_metainfo` 是參考，不該擋事（M8）。例外：閘門寄信前會解整張單子的指示詞，`_metainfo` 裡的 `$ref` 指不到＝`DirectiveBad`、信寄不出去（N-45 真的解不開＝錯，不另開例外）。
- **巢狀**（外層要不要彙總內層，M6）：外層作者寫了就用外層的；沒寫，kernel 第一版不往下找。10-15 照建議「沒寫的由子葉加總」留給通用 kernel，而且**只在子葉寫在 JSON 裡看得到**時做（fsm 各格的內嵌單子、`tools/*/_metainfo`）——入口是腳本就打不開，算沒說，不去猜腳本會叫誰。彙總法：`time_ms` 加總、`mem_mb` 取最大、`resource` 取聯集、`llm_*` 加總、`idempotent`／`deterministic` 全部 `true` 才 `true`、`side_effect` 有一個 `true` 就 `true`；通用 kernel 動工時，有 3 個以上包了子程式的函數沒寫外層 `_metainfo` 才做彙總。
- **兩份並存**（`_metainfo` 與 `_metainfo.json`）：`_metainfo` 贏、不合併（同 N-61）。
- **`.env` 改了 `AOS_ENTRY`**：不讀 `.env` 的讀者會走錯路（[01 § 2](01-位置與格式.md#2-怎麼找跟找入口同一條路)）；照預設 `_entry` 走，接受偶爾找不到。
- **宣告了 kernel 沒有的資源**（例 `resource: "gpu"` 的信進了 LLM kernel）：LLM kernel 只有一種格，不看 `resource`，照跑。
- **版本**：舊的 `_metainfo` 寫了現在沒定義的 key＝不認得、忽略（C-48），不報錯。

<a id="5-給-llm-kernel-實作者的接法"></a>
## 5. 給 LLM kernel 實作者的接法

對象：`proto8/impls/aos-kernel-llm`、`aos-gate`（信＝`{"inst": 單子（指示詞已解）, "env", "priority"}`）。讀法集中在 `priority_of` 一個函式。

**第一步（閘門不用動；已做，見 [llm-kernel](../2026-10-24-llm-kernel.md) 結論 8、9、15）**：

1. **讀**：在 `priority_of` 讀 `letter["inst"]["_metainfo"]`。只認兩個 key：`time_ms`（數字＝`val`；物件取 `val`、`max`）、`llm_tokens`（同）。不是物件、key 形狀不對＝那個 key 當沒寫，**不回 `LetterBad`**（M8）。指示詞閘門已經解過了，kernel 不用再解。
2. **排**：在 `order` 裡、「時限近的先」之後、「等得久的先」之前，加一層「`time_ms.val` 小的先；有寫的排在沒寫的前面」。級數與時限照舊壓過它（10-15：`_metainfo` 從不蓋過 `level`）。aging 不動，所以宣告短的插隊有上限。
3. **記**：`served.jsonl` 每行有兩個欄位：`elapsed_ms`（`run_inst` 回的 `Result.ms`）、`time_ms`（宣告的 `val`，沒寫＝`null`）。不寫任何使用者的檔。
4. **測**：兩封同級、沒時限、`time_ms` 一短一長且長的先寄 → 短的先跑；`_metainfo` 形狀壞的信照樣跑完；拿掉第 2 步那層比較 → 測試要紅。

**不要做**：kernel 照 `time_ms.max` 殺人（M4）；為了 `_metainfo` 去讀單子以外的檔（資料夾的 `_metainfo`、子葉）；把 `_metainfo` 塞進給腦的 prompt。

**第二步（有需要再做）**：

- **token 額度**：`budget` 照回信的 `usage` 結帳（已做，[llm-kernel token 回報與額度](../2026-10-24-llm-kernel.md#token-回報與額度10-24-下午)）；拿 `llm_tokens` 預估先擋沒做（10-15「見底就擋」；未決：拿 `max` 還是 `val`）。
- **按函數的實測統計**：閘門寄信時多帶 `"from": "單子檔的絕對路徑#指標"`（它已經把 `AOS_CF`／`AOS_CO` 設成單子的位置），kernel 照抄進 `served.jsonl`；要統計的人照 `from` 分組。
- **資料夾程式也要排隊**：閘門現在只收單子檔；之後要包整個資料夾程式時，才需要照 [01 § 2](01-位置與格式.md#2-怎麼找跟找入口同一條路) 找 `_metainfo`，那時推薦把「找」寫在 aos-exec 的公開庫（跟找入口共用 N-61 的程式），閘門找到後放進信裡；kernel 照樣只看信。
