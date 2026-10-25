# B 段交接（opus 實作者 → 下一個實作者，10-25）

← [round6 §7](round6.md)（照它的有序清單做）｜[round5](round5.md)（五區、貢獻、照樹走）｜A 段結果 [round4 §11](round4.md)

隊長要求在段落點停下交接（context 太長）。**停在：director 固化做完、writer 抽 trim 做完（程式＋假腦測試），還沒跑任何真腦量測、train/ 的 B 段格一個都還沒做。**

## 已做（程式都在 repo 的 galtxt-b，假腦全綠）

| round6 §7 | 做了什麼 | 檔 |
|---|---|---|
| 1 五區（宣告部分） | 根加 `tree_id`、`subtrees`、空的 `rollup`／`contribution`；各節點加 `subtrees`、`uses_llm`、`responsible_for`、`ablation`、`frozen`（judge、critic、lib/lint、plan_lint）、`lifecycle`（director pure、plan_template pure、writer tools、trim pure、critic agent） | 各 `_metainfo`（一次性腳本改的，key 順序保留） |
| 2 director 走完 | `draft/tools/director/`：`_entry` 單子 → `run.py`（順序固化）→ `tools/plan_template/`（純函數，查 `plans.json`：2×2＋`default`，佔位 `{hero}{heroine}{m0}{m1}{prop}`）。舊版 `versions/v0_agent/`（原單發腦函數整份，含 `.env`）、`versions/v1_script/`（run.py `FALLBACK="agent"`，查不到叫 `tools/agent`→捷徑到 v0_agent）。表外開關＝default＋答案帶 `degraded`＋小格 `$AOS_STACK/hard_cases.jsonl` 一行；judge 把 plan.json 的 `degraded` 抄進 score.json | director/、judge/_entry |
| 3 writer 抽 trim | `draft/tools/writer/tools/trim/`（純函數，stdin `{text, brief|brief_path}` → `{text, changes}`；三條：旁白超量刪後面、她的「！」超量換「。」、口癖超量換「哼」；不改台詞句數）、`tool.json`、system.txt 第 8 條（自檢完交 trim、原樣交它回的 text）；writer `loop.json` max 10→20（多一次工具來回）；假腦開關 `GALTXT_FAKE_TRIM=1` | writer/ |
| （round5 B2 開關） | `GALTXT_OFF_DIRECTOR`（director 一律 default、不記難例）、`GALTXT_OFF_SELF_LINT`／`GALTXT_OFF_TRIM`（brain 不給、act 也不執行該工具）、`GALTXT_OFF_REDRAFT`（check 第一稿定稿）、`GALTXT_OFF_SAMPLES`（brief.samples 空） | director/run.py、writer/brain.py＋act.py、check、brief |
| 測試 | 新 `proto8/tests/test_topdown_galtxt_b_lifecycle.py` 9 個；改舊 `test_topdown_galtxt_b.py`（director 不問腦：q01 calls 3→2、q08 4→3、PlanBad 兩個案例改拿 `versions/v0_agent` 換進樹的複本跑） | tests/ |

## 未做（照 round6 §7 的順序）

1. **真腦量測（還沒花 B 段的預算；只有跑全套測試時 `test_q01_real` 每次約 2 萬）**：
   - director 前後：「前」＝A 段基準 `plan/runs/round4/round0/`（director 是腦）；「後」＝現在的樹但**拿掉 trim**（`GALTXT_OFF_TRIM=1` 就等於沒抽 trim）跑 4 題 × 1 ≈ 8 萬，加第一題再 2 次量確定性 ≈ 4 萬。
   - trim 前後：「前」＝上一行；「後」＝現在的樹跑 4 題 × 1＋第一題再 2 次 ≈ 12 萬。驗收：`narration_max`／`exclaim` 違規 0、`deterministic_score`（1 − 總分 σ÷2）≥ 0.9。注意真腦**不一定會叫 trim**（只是 system.txt 叫它叫）——要數 writer history 裡 `tool_calls: trim` 的比例並寫進報告；叫不到的比例高就是該走 `freeze_order`（act 交稿前一律過 trim）的理由。
   - 跑法：scratchpad 有一支 `runset.py`（每題一個工作區、並行 6、`AOS_BRAIN_URL` 設好），用它或寫 `train/run`；每次記 measure.json 的 `counter_tokens`。
2. **難例 → teach**（§7-4）：`train/record` 收 `runs/**/.stack/director/hard_cases.jsonl` 進 `tree/draft/tools/director/hard_cases.jsonl`、更新 `_metainfo.hard_cases`；`train/apply` 的 `teach`：把難例的 brief 放進 `versions/v0_agent` 的工作區 `new/1.json`（`{"attempt":1,"brief":…,"feedback":[]}`）、`aos-exec --ws … versions/v0_agent`（真腦 1 次）→ plan_lint 過 → 把名字換回佔位（`宮澤柚葉`→`{heroine}`、`主角`→`{hero}`、道具→`{prop}`、第一組必提→`{m0}`）→ 寫進 `plans.json#/plans/主角|舊車票` → 難例標 resolved。示範題：`set` 第一題改 `switches.prop="舊車票"`、`must_mention` 第二組 `["舊車票"]`（測試裡有現成的寫法）。
3. **梯度**（§7-5）：record 對改動前後兩份 `_metainfo` 做結構化 diff（數值 delta／非數值 from-to／集合 added-removed）、`gradient_share`（有貢獻按比例、沒有就全給被動到的工具）。
4. **判斷器**（§7-6）`train/arbiter/`（critic 形的單發腦函數）、優化器一步提 2 條；**這輪沒有人評**（使用者在外面）——只用自動分＋錨，`human_agreement` 留空。
5. **漂移**（§7-7）、**train/ 其他格**（idle、init、run、record、optimize、apply、verify、tune、measure；round4 §4a＋round5 §5 B1～B3）、`plan/metainfo_rollup.py`、`train/record/rollup.py`。
6. hand_over（預算夠才做）、文件（README 生命週期一段、`plan/runs/round6/`、lessons.md）。

## 坑

- **worktree 隔離擋複合指令**：`cd X && for …`、heredoc 餵 python、`python3 -`、`$變數` 當參數都會被擋；改成「Write 一支腳本到 scratchpad、`python3 腳本` 跑」。`python3 -` 會卡在讀 stdin。
- **全套測試會花真腦**：`test_topdown_galtxt_b.RealBrain.test_q01_real` 每跑一次全套約 2 萬 token，要算進 60 萬預算。
- **`_entry` 當模組 import 會在樹裡留 `__pycache__`**，`test_metainfo_everywhere` 會因那層沒 `_metainfo` 而紅；import 前設 `sys.dont_write_bytecode = True`（`test_topdown_galtxt_b_train.load_entry` 有）。
- **q01／q08（examples）現在一定走 default**：它們不是固定場景、沒有 switches → score.json 有 `degraded`、director 小格有難例。這是誠實的（表外的題）；回歸分要看的話記得它們用的是通用 default 表。
- **v1_script 的 `tools/agent` 是相對捷徑**（→ `../../v0_agent`）；整棵複製要 `symlinks=True`，或像 lifecycle 測試那樣用 `symlinks=False` 展開。
- **trim 只靠 system.txt 叫**：真腦可能不叫、或叫完又改字；`deterministic_score` 若沒到 0.9，下一步就是 `freeze_order`（把「最後過 trim」寫進 act.py），那才是第 2 階 script。
- 驗收量法：`deterministic_score.score`＝1 − 總分樣本 σ÷2；`.text`＝1 − 兩兩字元 3-gram Jaccard 距離平均（train/score 的 `diversity` 函數＝1 − 這個，可以直接拿來用）。

## 測試數字（交接時）

`test_topdown_galtxt_b_lifecycle` 9 OK；全套 `python3 -m unittest discover -s proto8/tests` 552 OK（skip 2）；`demo.sh` 三段結束碼 0。
