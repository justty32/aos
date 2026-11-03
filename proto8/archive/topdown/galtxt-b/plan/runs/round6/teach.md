# round6 示範：難例 → teach → 梯度（真腦，10-25）

← [round6 §2、§3、§7 第 4～5 項](../../round6.md)｜留檔 [teach/](teach/)｜程式 [train/init](../../../train/init/_entry)、[train/record](../../../train/record/_entry)、[train/apply](../../../train/apply/_entry)、[train/pick](../../../train/pick/_entry)（`pick_subtree`）｜測試 `proto8/tests/test_topdown_galtxt_b_round6.py`（假腦 7 個）

## 怎麼跑的

訓練場（scratchpad，不在 repo）：`train/init` 把 galtxt-b 複製成 `tree/`（`symlinks=True`，排除 train／plan／human），set 多放一題 [新書_宮澤_主角先_舊車票](teach/新書_宮澤_主角先_舊車票.json)（set 第一題的複本，`switches.prop="舊車票"`、`must_mention` 第二組 `["舊車票"]`）。

1. 第 1 輪：跑這題一次（真腦）→ `train/score` → `train/record`：小格的難例收進 `tree/draft/tools/director/hard_cases.jsonl`（補 id、round、status、run、brief），`_metainfo.hard_cases.counter_open` 0→1。
2. `changes/1.json` 寫一條 `{"kind": "teach"}`（手寫，代替還沒做的優化器）→ `train/apply`：難例的稿紙交給 `versions/v0_agent`（真腦 1 次）→ plan_lint 一次就過 → 專名換回佔位 → 寫進 `plans.json#/plans/主角|舊車票` → plan_template 核對命中＋plan_lint 過 → 難例 resolved。
3. 第 2 輪：同題再跑一次（真腦）→ score → record：算 `changes/1.json.gradient`、各被動工具的 `gradient_share["1"]`、`gain`。

## 數字

| | degraded | total／6 | val | 反差 | 承接 | 含蓄 | 文筆 | token | 秒 |
|---|---|---|---|---|---|---|---|---|---|
| 第 1 輪（default 表） | `plan_template: 主角\|舊車票 不在表上，用 default` | 5 | good | 0.7 | 0.8 | 0.5 | 0.7 | 25,259 | 17.2 |
| teach（v0_agent 1 次） | — | — | — | — | — | — | — | 3,477 | — |
| 第 2 輪（教出來的表列） | **空** | **5** | good | 0.8 | 0.6 | 0.6 | 0.4 | 27,518 | 19.3 |

- **驗收**：第 2 輪 `degraded` 空 ✓；分數不低於四題平均 −0.58：基準取 [round4 round0](../round4/rounds/0.json) 的 `total_mean` 4.333（四題 6 次，A 段 director 是腦的樹），門檻 3.75，第 2 輪 5 ✓。單次樣本、σ 約 0.58（[noise](../round4/noise.md)），反差 +0.1／承接 −0.2／文筆 −0.3 都在雜訊內，不當結論。
- **花費**：25,259＋3,477＋27,518＝**56,254 token**（份額 6 萬內）。
- 教出來的表列：[taught_row.json](teach/taught_row.json)（9 拍；`{hero}`／`{heroine}`／`{m0}`／`{prop}` 佔位，`taught` 註記 round、case id、teacher）。腦在 `do` 裡寫的是「柚葉」（短名）不是 display「宮澤柚葉」，所以留成字面——這個場景只有她一個女主角，無害；換人物要再加一條短名對照。
- 第 1 輪 writer 有一次 `lint: ArgumentsBad`（腦叫 lint 沒帶 brief，錯誤回給腦、它自己補上）——writer 的事，不是本項，記著。

## 梯度（[gradient.json](teach/gradient.json)，真實一例）

```
draft/tools/director/tools/plan_template  rollup.counter_rows 4→5（+1）、rollup.measured.counter_degraded 1→0（−1）
draft/tools/director                      hard_cases.counter_open 1→0（−1）、counter_resolved 0→1（+1）
.（根）                                    ratings.傲嬌.counter_degraded 1→0、反差 0.7→0.8、承接 0.8→0.6
```

- 只算 touched（apply 寫的：plan_template、director）與往上一路；`draft`、`draft/tools` 沒有變的 key 就不列。略過 `*_at`、`round`、`gradient_share`。
- share：兩個被動的節點都沒有 `contribution` → 平分（plan_template 自己那層全給它 1.0；director 與根的變化各 0.5）。
- `gain`＝好變化 ÷ 千 token（下限 1）：好變化＝counter_open −1、counter_resolved +1、counter_degraded −1（plan_template 與根各一）＋反差 +0.1 ＝ 4.1（承接 −0.2 是壞變化、不扣；counter_rows 沒方向、不算）→ 4.1 ÷ 3.477 ＝ **1.179**。分到工具：plan_template good 2.55／gain 0.733、director 1.55／0.446（見檔）。
- `train/pick` 的 `pick_subtree` 用 `λ_gain × gain/(1+gain)`（[pick_rule.json](../../../train/pick/pick_rule.json)，λ_gain 0.2）。

## 代定與沒做

- **train/init 只做最小版**（複製 tree、補 set）；沒寫 round.json，輪數由呼叫者給（`$AOS_STACK/round.json`，同 score／pick）。train/run、optimize 沒做，示範用 scratchpad 的 `demo.py` 串。
- **record 存快照** `rounds/<輪>.metainfo.json`（整棵樹、不含 versions/），下一輪拿它當「改前」；梯度寫在 `changes/<輪-1>.json`（改動那一輪的檔，跟 round4 的 effect 同位置）。
- **degraded、分數這些不在 `_metainfo` 的結果**：record 寫進根的 `ratings.<風格>`（total_mean、反差、承接、counter_degraded）與降級工具的 `rollup.measured`，所以梯度看得到；表的列數經 director 的 `teach.table` 宣告寫成 `rollup.counter_rows`。
- **share 的候選只有這一步動到的工具**（不含沒動的兄弟）；有貢獻時按 |dims[d]|，部分有部分沒有時缺的用已知的平均補。
- **gain 只加好變化**、不扣壞變化（照 §3b 字面）；要扣就把 `shares` 的 `max(0, …)` 拿掉。
- 方向表 [polarity.json](../../../train/record/polarity.json) 是我定的；評級字 bad<ok<good 也算。
- apply 的其他 kind 一律 rejected（白名單、extract_tool、freeze_order 還沒做）。
