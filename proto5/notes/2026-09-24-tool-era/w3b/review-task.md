← [第三波 W3-2 隊報告](README.md)｜[回報](review-astra.md)

# 審查任務書：第三波 W3-2 隊（多叫一次模型的四個工具）（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_agent_tools_wrapcli.py'`，同樣可跑 `test_compact_summarize.py`、`test_team_crystal.py`、`test_llm_ask.py`、`test_agent_tools_dev.py`、`test_agent_memory.py`、`test_team_route.py`）。繁體中文、白話。

**只審這次的改動**：`git diff d6603b9 HEAD -- proto5`。以前的審查已修，不用重提。

## 背景

第三波的原則：每個工具都是「多叫一次模型」。模型版一律**預設關**、只留旗標，而且要有**機械檢查兜底**、**人確認才寫入**（或檢查不過就退回機械版）。

## 這次做了什麼

1. `lib/aos_llm_ask.py`：不需要 agent 家的「問一次模型」（讀 `AOS_LLM_CONFIG`、temperature 0、`parse_json` 從回話抽 JSON）。`aos_agent_context.last_usage` 略過 batch 以 `compact-summarize` 開頭的那筆。
2. `aos-agent tools wrap-cli CMD`（新檔 `lib/aos_agent_tools_wrapcli.py`，規範 `spec/aos-agent/tools-wrapcli.md`、`tools-llm.md`）：`.py` 有 argparse＝`ast` 靜態讀 `add_argument`；其他＝讀 `--help-file` 或跑 `CMD --help`（10 秒逾時、不經 shell）用規則解。產工具包，`run` 把 JSON arguments 組成 argv、不經 shell 跑指令。`--describe-with-llm`：模型回參數表，機械檢查（旗標要在 help 原文出現…），只寫提案檔；`--spec FILE` 照人看過的表產包（核 help 的 sha256）。
3. `tools wrap-py FILE --describe-with-llm`／`--describe FILE`（`lib/aos_agent_tools_dev.py`）：沒 docstring 的函式請模型補描述，只寫提案檔；`--describe` 照提案檔產包（核原檔 sha256，不覆蓋已有 docstring）。
4. `aos-agent compact --summarize [--model A]`（`lib/aos_agent_compact.py`，規範 `spec/agent/compact-summarize.md`）：機械壓縮照舊，只把封存摘要的本體請模型濃縮；每段檢查（比原本短、關鍵詞還在、不含 `[aos`），不過退回機械摘要；模型壞了整次退回機械版照樣縮。tick 自動壓縮與 compact 申請絕不叫模型。叫模型時持著 tick 鎖。
5. `aos-team crystal`（新檔 `lib/aos_team_crystal.py`，規範 `spec/team/crystal.md`）：讀 `team/route.log`＋任務單＋投遞紀錄，列落穿句型、機械產候選規則＋回測，只寫提案檔（人 `route test --file`→`route save` 批）。`--suggest-with-llm` 請模型歸納規則，機械檢查（編得過、例句全過、回測不誤觸）。`aos_team_route` 在落穿那行 route.log 多記 `letter`。

## 請回答

1. **wrap-cli 的邊界**：靜態讀 argparse 真的不執行使用者程式碼嗎？跑 `CMD --help` 會不會經 shell、會不會卡住、環境有沒有清？產的 `run` 組 argv 能不能被 arguments 注入成別的旗標（值以 `-` 開頭、位置參數、陣列、count、choices 外的值）？指令路徑怎麼解析、關牢時跑不跑得到？`--out`／`--name`／提案檔路徑能不能寫到奇怪的地方、蓋掉東西？
2. **「人確認才寫入」是真的嗎**：`--describe-with-llm` 模式有沒有任何路徑會直接產包或改既有包？`--spec`／`--describe` 的 sha 核對、欄位驗證有沒有漏（人改壞的提案檔、模型亂回的名字／型別、超長描述、描述裡塞控制字元或 prompt）？
3. **compact --summarize**：崩潰恢復規則（archive 先寫、記憶後換、重跑空轉）還成立嗎？機械檢查（關鍵詞的定義）會不會讓丟了關鍵事實的摘要過關、或讓正常的全部退回？失敗時是否一定退回機械版而不是不縮或半寫？auto／申請路徑是否絕不叫模型？dry-run 真的不寫檔嗎？usage 記錄與事件欄位對不對？
4. **crystal**：句型歸類與候選規則是否決定性；產的 pattern 會不會過寬（吃到不該吃的、`..`、絕對路徑）或吃到有否定詞的句子；候選是否真的不會自動生效（有沒有寫 `team/routes.json`）；提案檔的例句跑 `run_tests` 全過才寫；舊 log 沒 `letter` 時的對法會不會對錯單；route.log 多一格是否弄壞既有讀者（score、mail、route try）。模型版的機械檢查有沒有漏。
5. `aos_llm_ask`：錯誤代號、api_key 會不會外洩到訊息、`parse_json` 會不會把奇怪的東西當成 JSON。
6. 規範與程式、CLI 用法（`aos-agent tools -h`、`compact -h`、`aos-team crystal -h`）對不對得上；`runs/*/README.md`、`runs/*/table.md` 的數字與同資料夾的原始結果（jsonl／json）對不對得上。

## 格式

**必修**（不改會做錯、可被濫用、或規範與程式不符的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
