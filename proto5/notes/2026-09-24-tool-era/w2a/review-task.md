← [第二波 A 隊報告](README.md)｜[回報](review-astra.md)

# 審查任務書：第二波 A 隊（造工具）（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_agent_tools_dev.py'`，同樣可跑 `test_tools_wf_fill.py`、`test_tools_wf.py`、`test_team_w2a.py`）。繁體中文、白話。

**只審這次的改動**：`git diff 12d67d4 HEAD -- proto5 wf`。第一波的審查已修，不用重提。

## 這次做了什麼

1. `aos-agent tools new／test／wrap-py`（`lib/aos_agent_tools_dev.py`、`lib/aos_agent_cli.py` 分派、規範 `spec/aos-agent/tools-dev.md`，規格來源 `notes/2026-09-24-tool-era/catalog.md` 的 T-toolnew／T-tooltest／T-wrap-py）：
   - new 生骨架（`_common.py` 是 base 的逐字副本、範例工具檔、`cases.json`）。
   - test 照工具檔描述自動生案例（正例、每個參數型別錯、缺必填、不是物件）＋`cases.json`，在拋棄式假家裡跑，預設用 `aos-jail`（bwrap）關牢，`--no-jail` 或沒 bwrap 才直接跑。
   - wrap-py 用 `ast` 靜態讀 Python 檔（不 import、不執行），有型別註解的頂層函式包成工具包（`run` 在執行時照記下的簽名驗型別、import 包裡的原檔副本、叫函式），印收／拒收表；產的工具不寫 `_jail`＝裝進有 `access.json` 的家就關牢。
2. `tools/wf/wf_fill`（`_fill.py`）：照事實 JSON 機械填 `{{…}}`（名字對應規則在 `_fill.py` 開頭：一樣 → 同義詞 → 包含，每層恰好一條才填）、刪〔模板說明〕、`drop_examples` 刪認得出範圍的範例、`drop_template_rows` 刪第一格是佔位的表格列；跟 `wf_init` 同一把專案鎖；每檔暫存＋rename。`wf_doc` 讀 IMPORT.md 的提示與 `wf_init` 的 next 提示加 wf_fill。
3. `templates/importer/`：導入工人模板，只裝 10 支工具。
4. `aos-team route try "一句話"`（`aos_team_route.try_text`）：只印判決，不跑、不開單、不寄信、不寫 route.log。
5. `aos-team mail` 改由新檔 `lib/aos_team_mail.py` 接手（分派表 `aos_team_cli.COMMANDS` 改指它；`aos_team_post.cmd_mail` 沒刪、不再被叫）：多列等人回答的題目（`ASK q-0001`，答完先顯示答案）；`--task` 連落穿給領隊的那封人寫的信一起列。
6. `aos_team._hooks`：start／stop 郵差、心跳那兩行開頭標 `郵差:`／`心跳:`。
7. `aos_team_task.render_handoff`：驗收那行改成「檔案在、含某段字不用你先 read 確認，有同名工具的檢查器可以先自己跑」。

## 請回答

1. **wrap-py 的邊界**：靜態讀真的不執行任何使用者程式碼嗎（`ast.parse` 之外有沒有 `eval`／`import`，字串註解怎麼解）？拒收表對 catalog 列的每一種（沒註解、`*args`／`**kwargs`、positional-only、自訂類別、async、decorator、非頂層）都對嗎？`run` 的型別驗證有沒有漏（bool 當 int、巢狀 list／dict、Literal 混型別、Optional 預設 null、多給參數）？例外、回傳不能 JSON、import 失敗會不會噴 Traceback？原檔副本與 `wrap.json` 的 sha256 有沒有在跑的時候核？產的包放在哪、`--out`／`--name` 能不能寫到奇怪的地方（`..`、絕對路徑、符號連結、蓋掉現有資料夾）？
2. **tools test 的邊界**：「預設關牢」是真的關嗎（掛了什麼、網路、cwd）？`--no-jail` 與「沒 bwrap 自動退回不關牢」有沒有明白印出來？拋棄式假家與 workspace 有沒有清乾淨？工具逾時、輸出巨大、工具殺不掉時會怎樣？`cases.json` 的 `files` 能不能寫到 workspace 外？
3. **tools new**：暫存＋rename 崩在半路會不會留半個包；`--force` 蓋掉的是什麼；NAME 驗證。
4. **wf_fill**：名字對應會不會填錯（包含那層的誤中、同義詞表、範本列判斷、表格列的第一格）；`drop_examples` 刪的範圍會不會超過（例如下一個標題的判斷、表格上方掃描停不下來）；只寫 `.md`、只在工作根目錄內、跳過符號連結嗎；鎖；`facts` 路徑能不能讀到根目錄外；「今天」與時區。
5. **mail／route try**：`fallthrough_letter` 挑法與 score 的 `task_start` 一致嗎；時間比較跨時區；`--json` 的形狀改了（題目是 `kind: ask`）會不會弄壞讀它的程式；`route try` 真的沒有副作用嗎。
6. 規範（`spec/aos-agent/tools-dev.md`、`spec/team/cli.md`、`route.md`、`templates.md`、`tools/wf/README.md`）與程式、教程 08 新加的兩段對不對得上。

## 格式

**必修**（不改會做錯、可被濫用、或規範與程式不符的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
