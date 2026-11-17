← [回入口 命名-續-概念搬來的檔名](../命名-續-概念搬來的檔名.md)｜段落：agent 的固定名、`AOS_HOME`、搬檔｜上一份：[02-設定檔-窗-時鐘-份額](02-設定檔-窗-時鐘-份額.md)｜下一份：[04-index](04-index.md)

## 工具登記表 `tools.json`、`_tooldef.json`、小格 `tools/<名>/`

規範旁：[N-50～N-53](../10-基礎設施-定義與工作區/06-N-50～N-53.md)；做法在 CONVENTION P-17、P-25、P-33、P-41；格式見 [附錄4 持久檔](../附錄4-持久檔.md)。

- agent 的工具由自己資料夾的 `tools.json` 登記（`aos-tools add`；使用者 10-28 aos-tools，[thinking](../../../thinking/2026-10/28/aos-tools/README.md)）：路徑照給的存——絕對的留絕對，相對的存成從註冊檔的資料夾算（範本裡手寫的 `tools.json` 也是）；要靠環境變數就寫指示詞，原樣存、每次用到才解。
- 沒經 `tools.json` 的叫法：工具放在呼叫它的那一格自己的資料夾裡，格裡寫 `aos-exec tools/<名>`——從自己 cwd 算的相對路徑、永遠零個 `..`（P-25、P-33）。
- 腦可以叫的工具另有 `_tooldef.json`（給模型看的說明），`arguments` 從 stdin 進、stdout 出（P-41）。
- 工具的小格是 `<agent 的 stack>/tools/<名>/`（＝`$AOS_STACK/tools/<名>/`，P-17）；工具裡 `aos-agent ctl who` 拿這個小格查 daemon 的表就認出叫它的那隻——`self_tools` 靠它改那隻的 `tools.json` 覆蓋層（登記照上面的存法）（[feat-proto 01](../../../thinking/2026-11/05/feat-proto/01-self-tools.md) 代定 1）。
- 共用工具的函式庫：引用＝登記進 `tools.json` 指到庫裡那處，沒經 `tools.json` 的叫法就在 `tools/<名>` 放一條捷徑指過去（[thinking 10-24 tool-lib](../../../thinking/2026-10/24/tool-lib/README.md)；使用者 11-12 裁 Q16「a」）。
- binding：工具＝定義裡的 `tools.json`；stack 裡同名副本（`$AOS_STACK/tools.json`）蓋過定義（P-23、P-15）。

例：bob 的 `act/tools/cathy/`（格裡寫 `aos-exec tools/cathy`）；範本用 `$override` 疊 `lib/packs/` 的分包。

（無條號，從 [C-61](../../CONCEPTS/05-agent/02-agent-的工具與agent-就是一台狀態機.md)、[C-46](../../CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md)、[用詞框](../../CONCEPTS/03-基礎設施/02-資料夾程式-工作區與-stack.md) 搬來。）原話：使用者 11-10「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」（[aos-tools-cli](../../../thinking/2026-11/10/aos-tools-cli/README.md)）。

## 腦設定 `llm.json`

格式見 [附錄4 持久檔](../附錄4-持久檔.md)；換腦的做法在 CONVENTION P-23、P-15、P-39。

- 腦＝定義裡的 `llm.json`（`model`＝llm kernel 的能力包代號；包就是能力，換模型＝換代號，P-23；brain 把它填進請求信 body 的 `endpoint`）。llm 設定包成代號：細節 fable 代定、可翻案（[thinking 11-04 think-as-function](../../../thinking/2026-11/04/think-as-function/README.md)）。
- stack 裡同名副本（`$AOS_STACK/llm.json`）蓋過定義，所以呼叫方給它的 stack 放副本就換得了（P-23、P-15）。
- 要換子 agent 的腦，一律給它的 stack 放 `llm.json` 副本換代號（P-39）；`AOS_LLM_KERNEL` 只當 hub、不拿來換腦。

（無條號，從 [C-46](../../CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md) 搬來。）原話：使用者 11-04 晚選「只留 llm.json 代號」（[think-as-function 07](../../../thinking/2026-11/04/think-as-function/07-實作結論.md#使用者裁定11-04-晚選項)）；鍵名 `model` 出自使用者 11-10 晚「3.把fsm認的endpoint這個key，也改名爲model吧...麻煩的話就算了。」（[self-tools 05](../../../thinking/2026-11/10/self-tools/05-llm設定改名與ls.md)、[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md) 第 8 題）。

## stack 與工作區裡的固定名字

規範旁：[N-55](../10-基礎設施-定義與工作區/06-N-50～N-53.md)（stack 與工作區）；各檔格式、誰寫誰讀全在 [附錄4 持久檔](../附錄4-持久檔.md)。

- stack 預設值是 `$AOS_WS/.stack/`（隱藏資料夾，跟 `AOS_STACK` 同字，使用者 10-23 選，[thinking 10-23 naming](../../../thinking/2026-10/23/naming.md)）（C-65）。
- 題目資料夾那四格：`new/`＝還沒做、`cur/`＝已認領處理中、`done/`＝做完，答案放 `out/`（P-11、P-14）；是舊協議，只有舊範本在用（C-65）。這次的話放工作區，慣例 `new/`（P-11，C-46）。
- 對話落成 `$AOS_STACK/history.jsonl`（P-41，C-46）。
- history 改掉的原文預設搬到旁邊（`history_removed.jsonl`），可選搬到哪或不留（C-90）；`do_task` 的 `end` 把紀錄點之後換成總結時，原文照舊留在 `history_removed.jsonl`（C-42）。
- 一隻 agent 一個目標，存在自己的 stack（`goal.json`）（C-91）。
- 帳沿呼叫樹往上收：收掉子 agent 的工具之前，把子公開宣告的帳抄進自己小格的 `observed/<子名>/`（C-42；11-07 使用者裁定，傍晚選項框 ltn-5 選推薦，[lift-to-norms](../../../thinking/2026-11/07/lift-to-norms/README.md)）。

例：fsm 的 `stage.txt`、對話的 `history.jsonl` 都在 stack。

（無條號，從 [C-65](../../CONCEPTS/03-基礎設施/02-資料夾程式-工作區與-stack/01-stack與工作區分開.md)、[C-46](../../CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md)、[C-42](../../CONCEPTS/05-agent/01-續-C-42.md)、[C-90、C-91](../../CONCEPTS/05-agent/06-C-90～C-92-self一家與goal.md) 搬來。）原話：四格名，使用者 10-23 選「改成一致的階段名」（[thinking 10-23 naming](../../../thinking/2026-10/23/naming.md)）；`history_removed.jsonl`，使用者「1.全給，風險自己擔。2.可以。3.可選，默認搬到旁邊(可以選要搬到哪) 4.接受縮水版。5.對」（第 3 點；C-90 的出處 [self-family](../../../thinking/2026-11/10/self-family/README.md)）。

## 範本外的路徑經 `AOS_HOME`

- 範本裡指到範本外的路徑經 `AOS_HOME` 給，`AOS_HOME` 用相對、絕對、環境變數三種給法、不設捷徑。

（無條號，從 [C-51](../../CONCEPTS/01-設計理念/02-C-51.md) 搬來；規範旁：[N-63（`AOS_` 變數的四種性質）](../10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md)。）原話：使用者 11-10「盡量支援相對路徑」「會頻繁遷移，透過github」、午「要用相對位置、絕對位置、環境變數指定都可」（[templates/docs/02](../../../templates/docs/02-agent-fsm.md)）。

## 指示詞寫法、搬檔時改哪些值

指示詞（`$env`、`$path`、`$ref` 與陣列合成、argv 裡的指示詞）全在 [N-45](../06-基礎設施-命令列與指示詞.md)，這裡不重複（從 C-48 搬來）。

- 搬了跑起來要一樣：先寫新的、最後才改呼叫方（N-05）；只改位置相關的值，讓它們指回原處——單子的 `cwd`（沒寫＝入口所在的資料夾，搬進資料夾就補 `".."`）、相對的 `$ref` 檔名（`"#/…"` 補上原檔名）、`{"$env": "AOS_CD", "$path": …}`；伴隨檔搬進去時，argv 裡那一項改成 `{"$env": "AOS_CD", "$path": "/檔名"}`。單子用了 `$env AOS_CF`／`AOS_CO` 的不搬（每跳重設，N-57）。錯誤訊息裡的「誰」會跟著變（只有字，結束碼一樣）。

（無條號，從 [C-55 函數成長](../../CONCEPTS/01-設計理念/05-續-C-55-函數成長.md) 搬來；規範旁：[N-61](../10-基礎設施-定義與工作區/05-N-61～N-62.md)、N-57。）
