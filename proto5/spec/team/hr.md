← [team](README.md)｜報告：[HR 部 09-25](../../notes/2026-09-25-hr/README.md)｜流程樣板：[playbook 試用→評分→調薪](../../playbook/workflows/hr-trial.md)

# HR 部：薪資表、試用、調薪、名額、員工類型

一句話：**HR 決定「每個位子最低用得起哪顆模型」**：用試用換模型跑同一份任務集、同一支評分指令，分數沒掉太多就把那個位子「降薪」，證據留在紀錄裡。
公司路線是「強模型先做 → 換笨模型 → 換程式」，每往下走一步就是一次調薪，HR 管這件事的帳。

> 第 1 版，2026-09-25（HR 部段）。程式：[`lib/aos_team_hr.py`](../../lib/aos_team_hr.py)，指令 `aos-team hr …`。
> 董事當天追加的三條（名額、擴編、正式／臨時）一起寫在這份；原型做最小，沒做的標「留下一輪」。

## 1. HR 家與四個檔

HR 是全公司一份，放在 **HR 家**：`--hr DIR`，沒給看 `AOS_HR_HOME`，再沒有＝`$AOS_KERNEL_HOME/hr`（下面寫成 `K/hr/`）。

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `K/hr/salary.json` | 人（文字編輯器）＋`hr trial` 照規則改「最低通過」 | 薪資表（§2） |
| `K/hr/policy.json` | 人 | 政策：名額、調薪容差、擴編門檻（§5）；沒有這個檔＝內建預設 |
| `K/hr/trials.jsonl` | `hr trial`（只追加） | 試用紀錄，一行一次（§3） |
| `K/hr/teams.json` | `aos-team init`／`start`／`hr` 指令自動登記 | 登記過的團隊資料夾清單（數全公司正式員工用） |
| `K/hr/trials/tr-NNNN/` | `hr trial` | 每次試用的名冊副本 `roster.json`、團隊副本 `team/`、專案副本 `proj/` |

## 2. 薪資表 `salary.json`

```json
{
  "_metainfo": {"_type": "aos_hr_salary", "_version": 1},
  "tiers": {"chatgpt-gpt-6-astra": "強", "deepseek-chat": "笨"},
  "positions": {
    "worker": {"model": "chatgpt-gpt-6-astra", "tier": "強", "employment": "regular",
               "min_pass": {"model": "deepseek-chat", "tier": "笨", "trial": "tr-0002", "baseline": "tr-0001",
                            "at": "2026-09-25T12:00:00+08:00"},
               "evidence": ["tr-0001", "tr-0002"]}
  }
}
```

| 鍵 | 意思 |
|---|---|
| `tiers` | **llm.json 模型代號 → 等級**。等級四種，由便宜到貴：`程式`、`笨`、`中`、`強`。沒列的代號等級不明，試用只記錄、不調薪 |
| `positions` | **位子 → 一列**。位子＝模板名（`lead`、`worker`、`reviewer`、`importer`、`librarian`…）：同一個模板的成員做的是同一種事，薪資跟著位子走，不跟人走 |
| `.model`／`.tier` | 目前這個位子用的模型與等級（第一次試用時照名冊填；之後人改） |
| `.employment` | 員工類型 `regular`／`temp`（§6） |
| `.min_pass` | **最低通過**：試用過、照 §4 規則通過的最便宜那顆；**只有試用證據才填**，沒試過就沒有這個鍵 |
| `.evidence` | 支持 `min_pass` 的試用編號（基準那次＋通過那次） |

`hr trial` 只動 `min_pass`、`evidence`，第一次也補 `model`／`tier`／`employment`；其他全是人的。沒有這個檔＝空表加內建的 `tiers`。
**薪資表不會自動改名冊**：「最低通過」是證據，要不要真的換成那顆，人看過再 `hr set`（§7）。

## 3. 試用 `aos-team hr trial`

```
aos-team hr trial --member worker-1 --model deepseek-chat --taskset 任務集.json [--score-cmd "…"] [--out DIR] [--timeout 秒] [--note "…"] [--target 原團隊]
```

1. 讀原團隊的名冊（**原團隊一個檔都不動**），抄一份：`project` 改成 `../proj`、那個成員的 `model` 換成新的，寫到 `K/hr/trials/tr-NNNN/roster.json`。
2. 把任務集的 `project` 資料夾整份複製成 `proj/`（每次從同一個初始狀態開始）。
3. 在 `team/` `aos-team init`、有 `routes` 就 `route save`、`start`，照順序 `ask` 每一句。
4. 每 3 秒看一次 `task ls`：頂層單到了 `expect_tasks` 張、全部結束就停；有題目而任務集給了 `answer` 就用那句回。超過時限＝`timeout`。
5. `stop`，跑 `aos-team score --json` 拿六軸、token、think 次數；再跑**評分指令**。
6. 照 §4 判定，記一行到 `trials.jsonl`，印一張表。

**要用自己的 kernel**：kernel 用 `agent-<成員名>` 登記，試用副本的成員名跟原團隊一樣，**原團隊在同一個 kernel 上開著就會撞名**（`AlreadyExists`）。試用前停原團隊，或用另一個 kernel 家（建議：HR 自己一個試用 kernel）。
試用副本帶 `AOS_HR_TRIAL`：不登記進 `teams.json`、不算人頭、不過 init 的名額擋點；cpu 擋點照樣過。

### 任務集

```json
{"_metainfo": {"_type": "aos_hr_taskset", "_version": 1},
 "name": "ex1-worker", "project": "project", "routes": "routes.json",
 "asks": ["把 workflows 導入 p，照 facts.json"], "expect_tasks": 1, "timeout_s": 900,
 "answer": "事實表沒有的就照 facts.json 最接近的寫，不用再問", "score_cmd": ["python3", "score.py"]}
```

必填 `name`、`project`（相對任務集檔的資料夾）、`asks`；其他可省（`expect_tasks` 省略＝句數）。例子：[`examples/hr/ex1/`](../../examples/hr/ex1/)。

### 評分指令（可插）

任何指令都行，在任務集的資料夾跑，環境多四個變數：`AOS_HR_PROJECT`（專案副本）、`AOS_HR_TEAM`（團隊副本）、`AOS_HR_TRIAL`（編號）、`AOS_HR_STATUS`（done／failed／timeout）。
**stdout 最後一個非空行要是 JSON 物件**，至少 `score`（0～100）與 `mech_ok`（機械檢查全過＝`true`）；其他鍵原樣存進 `score_detail`。跑不起來、最後一行不是 JSON＝分數 `null`、`mech_ok: false`、原因記在 `score_detail.error`。

- 例子 1：[`examples/hr/ex1/score.py`](../../examples/hr/ex1/score.py) 在專案副本逐條跑 11 條機械檢查，分數＝過幾條／11×100。
- arknights 產線：評分指令指 `examples/arknights/eval/eval.sh`，外面包一層把它的總分換成 0～100、機械層全過換成 `mech_ok`（留下一輪，見報告）。

### 一行紀錄

`id`、`at`、`team`（原團隊）、`member`、`position`（模板名）、`from_model`、`model`、`tier`、`taskset`、`taskset_path`、`score_cmd`、`status`、`score`、`mech_ok`（評分指令說全過**而且**單子 done）、`score_detail`、`tokens`、`wall_s`、`think`、`think_by_member`、`axes`（`L S R F H B` 各一個分數或 null）、`dir`、`note`、`verdict`、`why`。

## 4. 調薪規則

同一個**位子**、同一份**任務集**才比：

| 情況 | 判定 | 薪資表 |
|---|---|---|
| 試的模型等級是 `強` | `基準` | 不動 |
| 等級不明（`tiers` 沒列） | `等級不明` | 不動 |
| 還沒有「強、機械全過」的試用 | `沒有基準` | 不動 |
| `mech_ok` 且 分數 ≥ 最近一次基準分數 − `margin` | `通過` | 比現在的 `min_pass` 便宜或同級＝`min_pass` 換成這顆，`evidence` 加兩個編號 |
| 其他 | `不通過` | 不動；紀錄照留（`why` 寫差多少） |

**`margin` 預設 5（滿分 100）**：例子 1 一條機械檢查＝9 分，5 分代表「一條都不能少」；給 arknights 這種有評審分的任務集，5 分約是評審同一份交付物打兩次的起伏。要更嚴或更鬆改 `policy.json`。
「機械全過」是硬門檻、不能用分數補：笨模型分數差不多、但少做一條機械檢查的，不通過。

**一次不算數**：規則只看最近一次基準與這一次。S 軸要 10 次才給分（[score.md](score.md)），所以薪資表的「最低通過」是**候選**，真的換模型前人看 `hr trials` 決定要不要多跑幾次。

## 5. 名額 `policy.json`

```json
{"_metainfo": {"_type": "aos_hr_policy", "_version": 1},
 "stage": "startup", "margin": 5,
 "expand": {"backlog_min": 3, "qc_below": 80}}
```

**階段 `stage`**（董事 09-25）：公司先當新創，擴張後才放大。寫 `stage` 選一組數字，另外寫了數字就蓋過那一組：

| stage | `regular_max` 正式員工 | `cpu_max` | `llm_cpu_max` |
|---|---|---|---|
| `startup`（預設） | 10 | 20 | 5 |
| `grown` | 100 | 200 | 20 |

例：`{"stage": "grown", "cpu_max": 50}`＝擴張後的人頭，但 cpu 先開 50。名額只放在 HR 的 `policy.json`，**不放名冊**（名冊的 `limits.max_members` 是一支團隊的人數，財務的 `budget` 是錢，三個不同的東西）。

兩種數字，分開數：

| 數什麼 | 上限 | 怎麼數 | 在哪擋 |
|---|---|---|---|
| **正式員工人頭** | `regular_max`（新創 10） | `teams.json` 登記的每支團隊，名冊裡 `employment: regular` 的成員加總（讀不到的團隊不算） | `aos-team init`（名冊加了人）、`hr set --employment regular`（轉正） |
| **同時開著的 cpu** | `cpu_max`、`llm_cpu_max`（新創 20、5） | `AOS_DAEMON_HOME` 登記的每個 kernel（沒設就只看 `AOS_KERNEL_HOME`）的池表 `count − skip` 加總；池名 `llm` 或 envs 有 `AOS_LLM_CONFIG` 的算 llm cpu | `aos-team start`、生新成員（`spawn_member` 的檢查）、`hr trial` 開跑前 |

臨時工不算人頭（像工具一樣，要多少生多少），但它跑起來要用 cpu，所以 cpu 上限照樣管得到它。
超了＝`TooMany`，白話說數到幾、上限幾、怎麼辦；找不到 HR 家（沒設 `AOS_KERNEL_HOME` 也沒 `AOS_HR_HOME`）＝不擋。
`aos-team hr cap` 印三個數字與上限、這隊的積壓與擴編理由。

## 6. 擴編規則（從小新創開始）

新團隊從最少人開始（一個領隊＋一個工人），**加人要有理由**，理由只有兩種、都是機械量得到的：

1. **積壓**：這隊還沒結束的頂層單 ≥ `expand.backlog_min`（預設 3）。
2. **品管分數**：這隊最近一次試用或品管評分 < `expand.qc_below`（預設 80）——做不好，多一個審查或換強一點的人。

`aos_team_hr.expand_reason()` 算這兩條、`hr cap` 印出來。**原型只算、不擋**：擋在 spawn 與 init 上要先定「理由寫在哪」（申請帶 `why`、還是名冊加人時寫進 `trials.jsonl`），列為要董事拍的題；留下一輪。
縮編反過來：臨時工做完就收（§6），正式員工閒著停車不佔 cpu，不自動裁。

## 7. 員工類型：正式員工與臨時工

名冊每個成員多一個鍵 `employment`：

| | 正式員工 `regular` | 臨時工 `temp` |
|---|---|---|
| 意思 | 工具齊全、**有跨任務的長期記憶**、家一直留著 | **像工具一樣被呼叫**：按單生、做完收、沒記憶 |
| 預設 | 人手寫進名冊的成員（沒寫 `employment`＝`regular`）：人寫進去的是打算長期用的，舊名冊行為不變 | `spawn_member` 生出來的一律寫 `temp`（生的人是模型，按單生，不該自己長出長期員工） |
| 人頭 | 算 `regular_max` | 不算 |
| 記憶 | 見下 | 不裝 notes、不 recall；單子結束就 `aos-team rm --purge` 收掉家（留下一輪：郵差收單時自動做） |
| 轉換 | — | 轉正要人：`aos-team hr set NAME --employment regular`，受 `regular_max` 限 |

**正式員工的記憶不另起一套**，用現有三樣（都在它自己的家或團隊資料夾，[notes.md](../agent/notes.md)、[compact](../agent/compact.md)、[persona.md](../agent/persona.md)）：

| 記什麼 | 放哪 | 誰寫 | 怎麼讀 |
|---|---|---|---|
| 做過的事的原文（被壓縮掉的舊回合） | 家 `prompts/archive/`（牢裡 `/work/mem` 唯讀） | `compact`／`compact_me` | `recall` 工具、`context` 工具看目前的上下文 |
| 跨單子的心得、事實、慣例 | `team/notes/<名>/notes.json`（牢裡 `/work/notes`） | 成員自己用 `note` 工具 | `note find／get` |
| 做事的方式（人格） | 家 `prompts/system.json` | 只有人（`persona_propose` 申請、人 `aos-agent persona append`） | 每次都在 system prompt |

「長期記憶」＝模板 `notes: true`（掛 `/work/notes` 與 `/work/mem`）＋家不刪。所以正式員工的模板要 `notes: true`；臨時工的家生完就刪，`notes` 有也帶不到下一張單。
「`memory/` 資料夾」這個名字不新開，指的就是上面兩個位置（`team/notes/<名>/` 與家的 `prompts/archive/`）。

## 8. 其他指令

| 指令 | 做什麼 |
|---|---|
| `aos-team hr ls [--json]` | 每個成員一行：位子（模板）、類型、模型（名冊 → 模板 `llm.model` → `default`）、等級、薪資表的最低通過與證據 |
| `aos-team hr set NAME --model X [--no-restart]` | 改名冊那一列的 `model`；家已在就改它 `info.json` 的 `llm.model`（init 不會改已生好的家）；登記著就 `aos-agent stop`＋`start` 重啟 |
| `aos-team hr set NAME --employment regular\|temp` | 改員工類型；轉正先數人頭 |
| `aos-team hr trials [--position P] [--json]` | 試用紀錄表 |
| `aos-team hr salary [--json]` | 薪資表 |
| `aos-team hr cap` | 名額（§5）與擴編理由（§6） |

退出碼照 [cli.md](cli.md)：0 好、1 資料錯（`NotFound`、`TooMany`、`FormatInvalid`、`TrialSetup`）、2 用法錯。`hr trial` 單子沒全 done 也退 1（紀錄照寫）。

## 9. HR 為什麼大半是程式

HR 的每個決定都是「讀數字、比門檻、改一格」：數人頭、數 cpu、比分數、改薪資表。這些不需要判斷，交給模型只會多花錢、多一種出錯的方式，還不能重跑出一樣的結果。
需要模型的只有三處，而且都不在 HR 裡：試用時**被試的那個成員**（本來就是模型）；評分指令裡的**評審**（arknights 的 judge 層，品管部的事）；「要不要加人」的**理由寫得通不通**（留給董事，不給模型）。

## 10. 六軸自評（原型）

| 軸 | 分 | 依據 |
|---|---|---|
| L 模型參與 | 5 | HR 自己 0 次；只有被試的團隊叫模型 |
| S 穩定 | —（單元測試固定輸入全過；真跑每配置 1 次，不給分） | 試用走 `aos-team` 子程序，崩了重跑一次就是新的 `tr-NNNN`，不會蓋舊紀錄 |
| R 資源 | 4 | HR 指令本身毫秒級；試用的成本＝一件任務的成本（見報告的表） |
| F 快 | 4 | 試用一次＝任務本身的時間＋每 3 秒輪詢一次的延遲 |
| H 人易懂 | 4 | 薪資表、政策是人能改的 JSON；`hr ls` 一人一行；判定帶白話 `why`。扣分：位子＝模板名，同模板不同職責分不開 |
| B 邊界 | 4 | 試用不動原團隊（有測）、副本不算人頭；`hr set` 只改名冊一列與那個家的 `llm.model`，拿名冊鎖。扣分：同 kernel 撞名要靠人記得分開 |
