← [notes 索引](../README.md)｜規格 [spec/team/hr.md](../../spec/team/hr.md)｜流程樣板 [playbook/workflows/hr-trial.md](../../playbook/workflows/hr-trial.md)｜審查 [任務書](review-task.md)／[回報](review-astra.md)

# HR 部報告（2026-09-25）

**一句話**：HR 部做出來了：薪資表、`aos-team hr trial`（換一個成員的模型、跑同一份任務集、打分、記紀錄、照規則調薪）、名額與正式／臨時工。
例子 1 試了 4 個配置、各 1 次：**工人換 deepseek 通過**（100 分、33 秒），**領隊換 deepseek 不通過**（交付物對了，但單子卡住、900 秒逾時、38 萬 token）。
第一版薪資表只填了一格：`worker` 的最低通過＝`deepseek-chat`（證據 tr-0001、tr-0002）。

基底：main `843b17e`（開工時 `3c7da0d`，收尾前 rebase 三次）。測試：全套 99 檔 2784 條全綠（HR 新檔 38 條）。

## 1. 做了什麼

| 項 | 在哪 |
|---|---|
| 規格：薪資表、試用、任務集、可插評分指令、調薪規則、名額（新創／擴張兩段）、擴編規則、正式員工與臨時工、HR 為什麼大半是程式、六軸自評 | [spec/team/hr.md](../../spec/team/hr.md) |
| `aos-team hr ls／set／trial／trials／salary／cap` | [lib/aos_team_hr.py](../../lib/aos_team_hr.py)、`lib/aos_team_cli.py` 一行 |
| 名冊每個成員多 `employment: regular｜temp`（沒寫＝regular）；`spawn_member` 生出來的寫 `temp` | `lib/aos_team_format.py`、`lib/aos_team_spawn.py` |
| 擋點：`init` 數全公司正式員工（`regular_max`）並登記這隊；`start`、生成員、`hr trial` 前數全公司 cpu／llm cpu | `lib/aos_team.py` 的 `_hr_gate`、`aos_team_spawn.check()` 結尾 |
| 例子 1 任務集（試工人：門房直接派；試領隊：落穿給領隊）、評分指令（11 條機械檢查） | [examples/hr/ex1/](../../examples/hr/ex1/) |
| 測試 38 條 | [lib/test/test_team_hr.py](../../lib/test/test_team_hr.py) |
| 教程 08 第 11 節、spec/team README、cli.md、lib README、proto5 README 各一列 | |
| playbook：經驗 21～23、流程樣板 | [lessons.md](../../playbook/lessons.md)、[workflows/hr-trial.md](../../playbook/workflows/hr-trial.md) |

隊員分工：測試由一位 Sonnet 隊員寫（照我列的 12 項），cpu／記憶現況由一位 Explore 隊員查；其餘隊長做。

## 2. 設計重點（白話）

- **薪資跟著位子走，不跟著人走**：位子＝模板名（lead、worker…）。同一個模板的人做同一種事，試過一次就適用全公司這個位子。
- **試用不動原團隊**：抄名冊、`project` 改指專案副本、只換一個人的模型，在 `K/hr/trials/tr-NNNN/` 起一支全新的團隊。原團隊一個檔都不寫（有測）。
- **評分指令可插**：任何程式，最後一行印 `{"score": 0~100, "mech_ok": true/false}`。例子 1 是 11 條機械檢查；arknights 會是 `eval.sh`。
- **調薪是規則不是判斷**：同位子、同任務集，分數 ≥ 強模型基準 − 5，**而且**機械全過、單子 done，才把「最低通過」改成這顆。薪資表不會自動改名冊，要換人手動 `hr set`。
- **名額分兩種數**：正式員工人頭（跨所有團隊的名冊）與同時開著的 cpu（kernel 池表）。臨時工不算人頭。預設新創規模 10 人／20 cpu／5 llm cpu；`policy.json` 寫 `"stage": "grown"` 換 100／200／20。

## 3. 真跑：例子 1 試用結果

**環境**：獨立 daemon＋kernel `~/tmp/hr-try/aos`（default 池 3 顆、llm 池 2 顆），模型只走 LiteLLM `localhost:4000`。原團隊 `lead`＋`worker-1` 都用 `chatgpt-gpt-6-astra`（「強模型先做」）。每個配置 1 次、共 4 個。

| 試用 | 位子 | 模型 | 等級 | 任務集 | 單子 | 分數 | 機械 | 模型次數（領隊／工人／其他） | token | 秒 | L R F | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tr-0001 | worker | chatgpt-gpt-6-astra | 強 | ex1-worker | done | 100 | 過 | 8（0／8） | 63,717 | 45.9 | 3 3 5 | 基準 |
| tr-0002 | worker | deepseek-chat | 笨 | ex1-worker | done | 100 | 過 | 10（0／10） | 103,602 | 33.6 | 3 3 5 | **通過** |
| tr-0003 | lead | chatgpt-gpt-6-astra | 強 | ex1-lead | done | 100 | 過 | 11（3／8） | 74,285 | 55.0 | 3 3 5 | 基準 |
| tr-0004 | lead | deepseek-chat | 笨 | ex1-lead | **timeout** | 100 | 沒過 | 51（23／10／審查 18） | 384,882 | 902.5 | 1 2 — | **不通過** |

S、H、B 三軸每個配置只跑 1 次或要人填，都不給分。原始紀錄：[data/trials.jsonl](data/trials.jsonl)。

**tr-0004 發生了什麼**（[data/tr-0004-mail.txt](data/tr-0004-mail.txt)）：
1. deepseek 領隊先反問「專案裡找不到 IMPORT.md」（其實是工人 wf 工具裡的手冊），任務集的固定回答接住了。
2. 它開的單子放了「要審查員判」的條目，但名冊裡沒有審查員，郵差把單子標成 blocked。
3. 它自己用 `spawn_member` 生了 `reviewer-1`（名冊上是 `employment: temp`，這條新規則在真跑裡生效），另開一張審查單。
4. 原單一直 blocked，900 秒逾時。專案裡的導入其實 11 條全對，但**流程卡死要人解**，所以不通過（見經驗 23）。

**讀法**：
- 工人位子可以降薪：deepseek 分數一樣、還快 12 秒；但 token 多 6 成（多讀檔自己確認）。deepseek 單價遠低於 astra，錢還是省，但多出來的步數是下一步「換程式」的目標。
- 領隊位子不能降：錯在「寫單子」，一錯整條線卡住。要降先把單子寫法收成範本或門房規則。

## 4. 第一版薪資表

只填有試用證據的格（[data/salary.json](data/salary.json)，實際位置 `K/hr/salary.json`）：

| 位子 | 類型 | 目前模型 | 等級 | 最低通過 | 證據 |
|---|---|---|---|---|---|
| worker | regular | chatgpt-gpt-6-astra | 強 | **deepseek-chat（笨）** | tr-0001、tr-0002 |
| lead | regular | chatgpt-gpt-6-astra | 強 | —（deepseek 試過沒過：tr-0004） | tr-0003（基準） |

reviewer、importer、librarian 還沒試用，所以不列。每格只跑 1 次，是**候選**；真要換之前照 S 軸的規矩多跑幾次。

## 5. HR 部怎麼當一個 aos 團隊或機械員掛進公司

董事要公司本身在 aos 裡跑：部門＝aos 團隊、董事＝human、招人＝spawn、考核＝score。HR 的建議形狀：**HR 不是一支有模型的團隊，是掛在公司上的機械員**（跟郵差、心跳同一類），外加一份全公司共用的 HR 家。

| 問題 | 做法 |
|---|---|
| 薪資表放哪 | 全公司一份：`$AOS_KERNEL_HOME/hr/`（或 `AOS_HR_HOME`）。一個 kernel＝一間公司，各部門團隊共用 |
| 人頭怎麼數 | `K/hr/teams.json` 登記每個部門團隊（`aos-team init`／`start` 自動登記），加總各名冊 `employment: regular` 的成員 |
| 正式／臨時怎麼區分 | 名冊成員一個鍵 `employment`。人寫進名冊的預設 `regular`；spawn 生的一律 `temp`；轉正要董事 `aos-team hr set NAME --employment regular`（受上限擋） |
| 超額 spawn 怎麼擋 | 臨時工不算人頭，擋的是 cpu：`spawn_member` 的檢查裡數全公司 cpu／llm cpu，超 `policy.json` 就退件（`TooMany`）。正式員工超額在 `init` 與轉正時擋 |
| 考核 | `aos-team score`（六軸）＋`hr trial`（換模型試用）；試用紀錄 `trials.jsonl` 給財務算錢 |
| 要不要一個「HR 團隊」 | 暫時不要。HR 的決定都是讀數字比門檻；真要一個會想的 HR（例如寫擴編理由），加一個 `lead` 模板的成員，`mail_to: ["human"]`，只准它 `ask_human`，所有動作仍由人跑 `hr` 指令 |

最小片段（一個部門的名冊加兩個類型；HR 政策一份）：

```json
{"_metainfo": {"_type": "aos_team", "_version": 1}, "project": "../mfg", "tz": "Asia/Taipei",
 "members": {
   "lead":     {"template": "lead",   "employment": "regular", "mail_to": ["worker-1", "human"]},
   "worker-1": {"template": "worker", "employment": "regular", "model": "deepseek-chat", "mail_to": ["lead", "human"]}},
 "spawn": {"templates": ["worker", "reviewer"]}}
```

```sh
cat > $AOS_KERNEL_HOME/hr/policy.json <<'EOF'
{"_metainfo": {"_type": "aos_hr_policy", "_version": 1}, "stage": "startup", "margin": 5}
EOF
aos-team init --config mfg.json --target $W/mfg     # 數正式員工、登記進 K/hr/teams.json
aos-team hr cap --target $W/mfg                     # 階段 startup；正式員工 2／10；cpu 3／20、llm cpu 2／5
```

## 6. 代裁（我先定的，董事可以翻）

1. **HR 家放 `$AOS_KERNEL_HOME/hr/`**：一個 kernel 當一間公司。要跨 kernel 就設 `AOS_HR_HOME` 指同一個資料夾。
2. **位子＝模板名**：不另開「角色」欄。代價是同一個模板做兩種事的時候分不開（見要拍的題 4）。
3. **`margin` 預設 5**：例子 1 一條機械檢查就是 9 分，5 分＝一條都不能少；arknights 評審分的起伏大約這麼大。
4. **「通過」要單子 done**：交付物全對但流程卡死的，算不通過（tr-0004）。
5. **人寫的成員預設 `regular`、spawn 的預設 `temp`**：舊名冊行為不變；模型生的人不該自己長成長期員工。
6. **cpu 數的是池表的 `count − skip`**（要開幾顆），不是 daemon 真的開了幾顆：擋的是「打算開多少」，比較穩。財務的 cpu 行數的是 `aos-kernel ls` 的 want，同一個東西。
7. **試用要自己的 kernel**：kernel 用 `agent-<名>` 登記，副本跟原團隊同名會撞。原型不改名，規格寫明「先停原團隊或另開 kernel」。
8. **薪資表不自動改名冊**：「最低通過」只是證據，換人要董事 `hr set`。
9. **擴編理由只算不擋**（積壓 ≥ 3 或最近分數 < 80）：擋之前要先定理由寫在哪（要拍的題 3）。

## 7. 數字

- 測試：新檔 `test_team_hr.py` 38 條（含審查後補的 5 條）；全套 99 檔 2784 條全綠（main `843b17e` 上跑）。
- 真跑：4 個配置 × 1 次，共約 21 分鐘，token 合計約 63 萬（deepseek 49 萬、astra 14 萬）。

## 7.5 astra 唯讀審查

[任務書](review-task.md)／[回報](review-astra.md)。必修 7 條，修了 6 條、1 條改寫成「還沒做」：

| # | 問題 | 怎麼處理 |
|---|---|---|
| 1 | 試用副本保留原名冊的 `mounts`（可能可寫指原專案）；`--out` 可放進原團隊／原專案 | 副本拿掉所有 `mounts`；`--out` 重疊就 `BadProject`（有測） |
| 2 | `hr set` 改 `info.json` 沒拿鎖、先改才停 | 改成先停 → 拿 `info_lock`（跟 `tools add` 同一把）改 → 再開 |
| 3 | 評分指令退非 0 仍留分數、NaN／超範圍分數被收 | 退非 0、非有限、不在 0～100 一律 `score: null`、`mech_ok: false`（有測） |
| 4 | 試用副本連 cpu 擋點都跳過 | `_hr_home(cpu_only=True)`：試用只跳人頭與登記，start 與生成員的 cpu 照擋（有測） |
| 5 | 人頭檢查與寫名冊不在同一把鎖，兩隊同時轉正會一起過 | `hr set` 與 init／start 的擋點：數與寫都包在 HR 鎖裡（順序一律 HR → 名冊） |
| 6 | 臨時工建家仍裝 notes，跟規格「沒記憶」矛盾 | **沒做**，規格改寫成「原型還沒做」，列留下一輪 2 |
| 7 | 啟動後出例外，試用團隊不會停 | `try/finally` 一定 `stop` |

建議（同名任務集改了題目會混用舊基準、要記版本）列進留下一輪 8。

## 8. 留下一輪

1. **arknights 產線的試用怎麼接**：等製造部的 `examples/arknights/` 產線 `team.json` 合進 main 後：
   - 寫一份任務集 `examples/hr/arknights/taskset-*.json`：`project` 指基準集的初始狀態（15 人的空補檔資料夾），`asks` 是產線的那句開工話，`expect_tasks` 照產線開幾張單。
   - 評分指令包一層 `examples/arknights/eval/eval.sh`：把它的總分換成 0～100，機械層（格式、引文比對）全過換成 `mech_ok`。它的評審層會叫 claude，要算進品管額度。
   - `aos-team hr trial --target <產線團隊> --member <位子> --model deepseek-chat --taskset …`，先跑強模型當基準。
2. **臨時工沒記憶、做完自動收家**：規格寫了（不裝 notes、單子結束 → `aos-team rm --purge`），建家與郵差都還沒接（astra 必修 6）。
3. **擴編理由真的擋**：等題 3 拍板。
4. **試用副本自動改名**，免得同 kernel 撞名：要連帶改 routes 的 `assignee` 與 `mail_to`。
5. **finance 的 cpu 上限跟 HR 的 `policy.json` 合一**：現在兩邊各一份（財務 `budget.json` 的 `cpus` 只拿來顯示），數字相同但會分岔（要拍的題 5）。
6. S 軸：每格跑滿 10 次才正式給分。
7. `luna-nothink` 這次沒試（限 4 個配置，先把 lead 位子試完）。
8. 任務集要記版本（評分指令、題目的雜湊）：同名任務集改了內容，舊基準不能再拿來比（astra 建議）。

## 9. 要董事拍的題

1. **新創名額 10／20／5 是寫死在兩段（startup／grown）好，還是只留數字讓你直接改？** 我做了兩段加「數字蓋過」。
2. **`margin` 5 分**（滿分 100）可以嗎？要更嚴（0：一分都不能掉）還是更鬆？
3. **擴編理由寫在哪**：生成員申請帶一句 `why`（郵差照積壓／分數驗），還是名冊加人時寫進 `trials.jsonl` 一筆「擴編」紀錄？原型目前只算、不擋。
4. **位子＝模板名**夠嗎？還是要名冊加一個 `position` 欄（例如兩個 worker 一個寫程式一個寫文件，薪資分開算）？
5. **cpu 上限只放一份**：放 HR 的 `policy.json`（我的建議，財務來讀），還是財務的 `budget.json`？
6. **正式員工的「長期記憶」**：我沒另開 `memory/`，用現有的 notes（`team/notes/<名>/`）＋compact 封存（`recall`）＋人格。這樣算數嗎？還是要一個新的資料夾名？
7. **臨時工收家要不要留紀錄**（搬進 `.removed/`）還是直接刪（`--purge`）？規格寫了直接刪，因為它「像工具」。
8. worker 位子要不要**現在就換成 deepseek**？證據只有 1 次；我建議先跑滿 10 次再換。

## 10. 沉澱

**① 經驗（3 條，已放進 [playbook/lessons.md](../../playbook/lessons.md) HR 段 21～23）**：
- 降薪先試工人，領隊最後換：領隊錯在寫單子，一錯整條線卡住。
- 分數一樣不代表一樣好用：看 token 與步數，多出來的步數就是下一步要寫成程式的地方。
- 「通過」要同時看單子有沒有走到 done，不能只看交付物分數。

**② 團隊組織架構**：HR＝**程式＋規則**，掛在公司上的機械員，不是一支模型團隊。
- 程式：`aos-team hr`、`init`／`start`／spawn 的擋點。
- 規則：`policy.json`、`salary.json`，都由人改。
- 需要模型的只有三處，而且都不在 HR 裡：被試用的那個成員、評分指令裡的評審（品管部）、「要不要加人」的理由（留給董事）。
- 部門是團隊；正式員工寫在名冊上（`employment: regular`），臨時工由 spawn 生、像工具一樣用完就收。

**③ 工作流架構**（[playbook/workflows/hr-trial.md](../../playbook/workflows/hr-trial.md)）：

```text
試用 hr trial ─→ 評分（可插的評分指令）─→ 調薪（規則）─→ 人 hr set 真的換
 複製團隊只換一人     最後一行 {score, mech_ok}     ≥ 基準 − margin
 同一份任務集         例子 1：11 條機械              且機械全過、單子 done
```

降薪順序：工人 → 審查 → 領隊。每個位子先跑強模型當基準。

**④ 可複用工具**：
- `aos-team hr trial`：任何團隊、任何位子、任何任務集。
- 評分指令約定：最後一行 JSON。例子 [`examples/hr/ex1/score.py`](../../examples/hr/ex1/score.py) 可以照抄成別的機械評分。
- `aos_team_hr.count_cpus()`／`count_regular()`：全公司 cpu 與人頭，財務、組織設計都能直接叫。
- 任務集格式：`project`＋`routes`＋`asks`＋`answer`，一個資料夾就是一個可重跑的試用場。
