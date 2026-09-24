← [收尾隊報告](README.md)｜[回報](review-astra.md)

# 審查任務書：第一波收尾隊（T5）（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_*.py'`；會開真 daemon 的 `test_team_post_live.py`、`test_team_init.py` 的整合測試可略過）。繁體中文、白話。

**只審這次的改動**：`git diff 75eadc0 HEAD -- proto5`（收尾隊的幾個 commit）。前四隊的審查（`proto5/notes/2026-09-24-tool-era/review-*.md`）已修，不用重提。

## 這次做了什麼

1. `aos-team score`（`lib/aos_team_score.py`、`spec/team/score.md`）：讀成員家 `log/events*.jsonl`、`usage*.jsonl`、`team/post/sent/`、`team/tasks/`，照 `notes/2026-09-24-tool-era/axes.md` 的團隊門檻填六軸表（L、S、R、F；H、B 留給人），只讀不寫。
2. 接第 4 隊五件：模板 `"notes": true` → init 內建掛 `notes` → `team/notes/<名>/`（rw，保留名，繞過「多掛的可寫資料夾不准碰 team/」那條檢查）、舊家重跑 init 補掛；worker／lead 的 `may` 加 `compact`；`tools/task/compact_me`（只能縮自己）；`Layout.events()` 改指成員家 `log/events.jsonl`；layout.md 寫的人表。
3. 門房：`routes.json` 的 `do: tool` 的 `run` 也換 `{群組}`（`aos_team_route.ask`）；例子加 `count-md`（`每 2m 數一次 md 檔` → `routine add … --every {every}`）與導入規則的內容檢查。
4. `tools/wf/wf_doc`：關牢時 `AOS_TOOL_FENCE=/work` 讓快照（`/opt/tool/snapshot`）一律 `OutsideRoot`，改成 wf_doc 只看快照本身（`_common._FENCE = None`）；讀 `IMPORT.md` 開頭先加一段「手冊的腳本＝哪支工具」。
5. `aos_team_task.render_review` 帶上父單的 `facts`；`aos-team ls` 多兩行郵差／心跳在 kernel 的狀態（`machine_lines`）。
6. 三個模板人格（`templates/{lead,worker,reviewer}/system.md`）照真跑改；教程 `tutorials/08-team.md`。

## 請回答

1. **邊界**：`notes` 內建掛載有沒有開出新的洞（名冊或模板能不能借 `notes` 這個名字掛到別處、`notes: true` 給非團隊模板、舊家補掛會不會覆蓋人手改過的掛載、兩個成員同名目錄、`rm` 後同名重建接回舊筆記是否該擋）。`compact_me` 能不能縮別人、參數驗證跟郵差那邊的範圍一致嗎。
2. **wf_doc 拿掉 fence** 後，還擋得住讀快照外（符號連結、`..`、絕對路徑、`/proc/self/…`）嗎？`open_regular` 的打開後再驗是不是也跟著用 snap 而不是 fence。
3. **門房 `run` 換群組值**：群組值能不能注入成額外的子命令參數（例如值裡有空白、`--to`、`--target`）；`fullmatch` 與群組的正規式在 `count-md` 這條夠不夠緊；`run` 還是只能跑 aos-team 子命令嗎。
4. **score**：L／R／F 的算法與門檻有沒有對錯 axes.md；`--task` 的時間窗、起點推定（人信→領隊開單）、事件去重（ev＋id）、輪換舊檔、壞行跳過；`--runs` 不到 10 筆不給分；有沒有 Traceback 的路徑；大量檔案時會不會很慢。
5. **machine_lines**：帳本讀法跟 `aos_agent_status` 一致嗎；`ls --json` 沒變（刻意）是否合理。
6. 規範（`spec/team/score.md`、`layout.md`、`templates.md`、`route.md`、`mail.md`）與程式、教程 08 的指令與輸出對不對得上。

## 格式

**必修**（不改會做錯、可被濫用、或規範與程式不符的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
