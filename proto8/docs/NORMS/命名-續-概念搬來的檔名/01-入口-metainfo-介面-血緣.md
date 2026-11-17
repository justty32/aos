← [回入口 命名-續-概念搬來的檔名](../命名-續-概念搬來的檔名.md)｜段落：入口、`_metainfo`、宣告介面、血緣｜上一份：—｜下一份：[02-設定檔-窗-時鐘-份額](02-設定檔-窗-時鐘-份額.md)

## 入口 `_entry`、`_` 開頭的 key、`.env`

規範在 [N-57](../10-基礎設施-定義與工作區/01-N-57.md)（`AOS_ENTRY` 預設 `_entry`）、[N-59 第 4 件](../10-基礎設施-定義與工作區/03-N-59.md)（`.env`），命名在 [命名](../命名.md)「入口名 `_entry`」；這裡只放概念那邊搬來的句子。

- 入口的位置由環境變數 `AOS_ENTRY` 指（預設 `_entry`，C-68）；aos-exec 進資料夾後找的入口叫 `_entry`（C-54 R11），跟「要跑什麼」的 `exec` 兩者不混。一個 agent 的定義＝一個資料夾，入口 `_entry`（`$AOS_ENTRY`）。
- `_` 開頭的 key 是普通 key，沒有附註或 `_notes` 慣例；入口預設名 `_entry` 只是入口的名字。
- `.env` key 是為了跟資料夾的 `.env` 檔對上（C-51），檔名照 dotenv 生態。隱藏檔一律略過，一個例外：aos-exec 讀入口資料夾裡的 `.env` 設環境變數（N-59 第 4 件、[ideas 10-21 § 4](../../../thinking/2026-10/21/ideas/02-4-aos-exec-支援-env.md#4-aos-exec-支援-env10-21)）。

（無條號，從 [C-48](../../CONCEPTS/01-設計理念/01-C-01～C-48.md)、[C-51](../../CONCEPTS/01-設計理念/02-C-51.md)、[C-55](../../CONCEPTS/01-設計理念/05-布局成長與檔案權限.md)、[C-50](../../CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md) 搬來；規範旁：N-57、N-59。）原話：使用者「_開頭=附註這個概念刪掉」（[thinking 10-23 naming](../../../thinking/2026-10/23/naming.md)）。

## `_metainfo`（節點描述自己的抽屜）

放哪、怎麼找、內容、誰讀全在 [N-69](../10-基礎設施-定義與工作區/11-N-69.md)、[N-69（續）](../10-基礎設施-定義與工作區/11-續-N-69.md)，這裡不重複。概念那邊說的「節點描述自己的抽屜」就是它：資料夾裡的 `_metainfo.json`、JSON 裡的 `_metainfo` key。下面是概念搬來、帶這個名字的句子：

- inst 的 JSON 裡多放東西（九軸特性、traits、標籤、工具…）的那個抽屜叫 `_metainfo`（C-42b，[thinking 10-13 §3](../../../thinking/2026-10/13/json-path/README.md)）。
- `_metainfo` 裡的公式 key（`cal`／`lua`／`py`／`aos`）不是指示詞，是普通 key，只有讀 metainfo 的人算，aos-exec 不碰，見 [N-68](../10-基礎設施-定義與工作區/10-N-68.md)（C-48；11-07 使用者裁定 ltn-6 選推薦，[lift-to-norms](../../../thinking/2026-11/07/lift-to-norms/README.md)）。
- 任意執行工具在 `_metainfo` 宣告 `arbitrary_exec`（C-22）。
- 函數可以在 `_metainfo` 寫一格 `sandbox`（同 aos-sandbox 那一套設定 key）宣告自己需要什麼，呼叫方要照它關就明寫 `aos-sandbox _metainfo.json#/sandbox …`（C-64）。
- `_metainfo` 跟著單子走：搬的時候整張單子跟著走，單子裡的 `_metainfo` key 也在裡面；長到資料夾以後，讀資料夾的人只看 `_metainfo.json`，要給讀者看就自己拆成檔（C-55 函數成長）。
- index 也可以寫進 `_metainfo`：`_metainfo` 是節點描述自己的子節點、什麼都能放，index 是其中一種；`_metainfo` 本身不算 index（C-88；N-69 已有同一句）。

（無條號，從 [C-42b](../../CONCEPTS/03-基礎設施/01-inst至fsm.md)、[C-48](../../CONCEPTS/01-設計理念/01-C-01～C-48.md)、[C-22](../../CONCEPTS/05-agent/01-續-C-22.md)、[C-64](../../CONCEPTS/01-設計理念/05-布局成長與檔案權限.md)、[C-55 函數成長](../../CONCEPTS/01-設計理念/05-續-C-55-函數成長.md)、[C-88](../../CONCEPTS/05-agent/04-C-88-記憶與index.md) 搬來；規範旁：N-69、N-68。）

## 宣告介面 `interfaces.json`

- 資料夾宣告自己遵守哪些介面的那份檔叫 `interfaces.json`，是全體系第二個固定名；其餘檔名由它指定（`screen`、`tools`、`llm` 的值）。
- 上層可以依賴下層公開宣告的介面（對外標頭、schema、`interfaces.json`）（C-52）。
- 對方在 `interfaces.json` 宣告的覆蓋層照舊是給外面寫的地方，檔名只寫在宣告一處（C-81）。
- 誰寫、誰讀、壞了怎樣見 [附錄4 持久檔](../附錄4-持久檔.md)。

例：`{"aos-agent": {…}}`；子介面資料夾裡 `{"aos-agent/screen": {}}`。

（無條號，從 [C-51](../../CONCEPTS/01-設計理念/02-C-51.md)、[C-52](../../CONCEPTS/01-設計理念/03-續-C-52-例外.md)、[C-81](../../CONCEPTS/03-基礎設施/02-資料夾程式-工作區與-stack/02-體系的基礎與proc的地盤.md) 搬來。）原話：使用者 11-04 晚「一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。」「程式語言中定義class/struct的後，也會宣稱說自己繼承於/遵守於某些介面，比如golang interface之類。」（[thinking 11-04 aos-agent 03](../../../thinking/2026-11/04/aos-agent/03-種類與契約.md)）；覆蓋層：使用者 11-06 選項框「宣告過的覆蓋層可寫 (Recommended)」（[apply-ideas 02](../../../thinking/2026-11/06/apply-ideas/02-排程.md#11-06-special-cases-排程k-隊)）。

## 血緣紀錄 `lineage`、定義樹 `defs/`、退休樹 `retired/`

- 定義出生時寫一次的血緣紀錄叫 `lineage`：`agent_def` 的 new 在新定義的 `_metainfo.json` 記 `lineage`（[agent-def-fine-lineage](../../../thinking/2026-11/12/agent-def-fine-lineage.md)），之後不回寫。
- 定義裡的 `lineage` 是原始碼出處、不是執行時的上層，aos-exec、fsm、agent 都不讀它（C-46、C-89）。
- 狀態看所在位置：在 `defs/` 樹裡＝可用；搬進同深度的 `retired/` 樹＝退休；`_metainfo` 不加狀態欄（C-89）。演化出的定義樹放工作區 `$AOS_WS/defs/`（ad-5）。
- 執行時誰生的誰不另記：父的 `subagents.json` 有、子 rm 掉就消失（C-42）；`subagents.json` 的格式見 [附錄4 持久檔](../附錄4-持久檔.md)。

（無條號，從 [C-89](../../CONCEPTS/05-agent/05-C-89-不同質與族譜.md)、[C-42](../../CONCEPTS/05-agent/01-續-C-42/01-工具.md)、[C-46](../../CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md) 搬來；傍晚選項框 ad-1～ad-5 選推薦，[agent-diversity](../../../thinking/2026-11/07/agent-diversity/README.md)。）原話：ad-5 備註「可以定期將定義提取出來。之後其他工作，比如我要拆另一個遊戲時，可以運用。」；使用者 11-12「執行時誰生的誰不用另外記。」（[small-rulings](../../../thinking/2026-11/12/small-rulings.md)）。
