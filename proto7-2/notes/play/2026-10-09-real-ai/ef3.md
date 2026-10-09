# 依題難度選模型：author `--llm` 先便宜後升級（EF3 隊）

← [真 AI 第一圈](README.md)｜基線：[metrics-baseline](metrics-baseline.md)｜程式：[author ADVANCED](../../../packs/author/ADVANCED.md)（升級鏈一節）｜證據：[evidence/ef3/](evidence/ef3/)（驅動 [drive_ef3.py](evidence/ef3/drive_ef3.py)）

2026-10-09 EF3 隊寫。使用者出門，頂層全權代定。

## 改了什麼

`aos7-author propose … --llm`（**不給模型名**）＝升級鏈：

1. `chatgpt-gpt-6-luna-nothink` 先答；
2. 模型答了、但候選被拒（CSV 的三層驗證／aos 的三關沒過，`why=invalid`）才升 `chatgpt-gpt-6-sol-high`；
3. 再拒才升 `chatgpt-gpt-6-astra-high`；三級都拒就照最後一級回報（退 1）。

沒答成（HTTP 錯、逾時、unknown）、conflict、full 一律立刻停、不升級——升級只為「答得不好」，不為「沒送到」。回覆多一個 `rounds`（每級 model、call_id、why、usage）。aos 學徒升級時把上一級候選與檢查結果當重問交下一級（既有 `previous`／`feedback` 機制）；CSV 沒有重問欄，下一級拿同一份提示。給了模型名就跟以前完全一樣（回覆不帶 `rounds`）。README 沒動。

程式：`packs/author/aos7_author_llm.py`（`LADDER`、`climb`）、`aos7_author_aos.py`（原 propose 段搬成 `propose_one`）、`aos7_author.py`（`--llm` 值可省）；測試 `tests/test_author_ladder.py` 6 案（拿掉升級條件 3 案紅）。

## 前後：簡單題（R1 同題 csv1，一整圈到 close）

「前」＝固定 sol-high（R3 等處的預設用法）新跑 3 次；「後」＝`--llm` 不給模型跑 12 次（R1 的 12 圈）。秒數兩種：LLM＝`propose` 牆鐘（run.sh 記的，含 author 程序啟動）；收單→結案＝`aos7-metrics job`（同 E1 定義，含 LLM 之後約 4 秒的 step 等待，那段是 EF2 的）。

| 指標 | 前：sol-high ×3 | 後：升級鏈 ×12 | 變化 | 目標 |
|---|---|---|---|---|
| 每單 token | 2642 | 2545 | **−3.6%** | −3～7% ✔ |
| LLM 秒（propose） | 5.675 | 2.903 | **−48.8%** | −50% 左右（差 1.2 點） |
| 收單→結案秒 | 9.234 | 6.647 | −28.0% | （含 EF2 那 4 秒） |
| 通過（三層＋答案＋close） | 3／3 | 12／12 | 不降 ✔ | 不降 |
| 實際用到的級 | — | 12 次全停在 luna-nothink | 0 次升級 | — |

對 R1 原 12 圈（混六種模型，平均 2562 token／9.467 秒）：token −0.7%、收單→結案 −29.8%。R1 那次 sol-high 只跑 1 次（10.8 秒），這次 3 次平均 9.2 秒，代理今天較快；同日同時段比才公平，所以表用新跑的數。

## 前後：難題（S3 的三題 aos-tool：gap／runs／audit）

需求取自 S3 工作樹（`aos-wt/S3` 未提交的 examples，快照在 /tmp 跑，不改 S3 檔）。每題一單，`--context tests/run_all.py`、rules 審查、`--ref main`。「前」＝固定 sol-high，被拒帶 feedback 重問 ≤3 輪；「後」＝升級鏈。秒＝propose 牆鐘總和（含三關沙箱）。

| 題 | 前：sol-high | 後：升級鏈（每級 token） | 前 token／秒 | 後 token／秒 | 過 |
|---|---|---|---|---|---|
| gap | 1 輪過 | luna 拒 4293 → sol-high 過 10084 | 10301／82.9 | 14377／96.0 | 前後都過 |
| runs | 1 輪過 | luna 拒 4404 → sol-high 拒 11214 → astra-high 過 15101 | 11111／95.0 | 30719／223.1 | 前後都過 |
| audit | 1 輪過 | luna 拒 4162 → sol-high 過 10356 | 11240／119.8 | 14518／77.4 | 前後都過 |
| 平均 | — | — | 10884／99.2 | 19871／132.2 | 3／3 vs 3／3 |

- **luna-nothink 在 aos 題 3／3 直接拒答**：交 `files: {}`，REPORT 說「沒有檔案或指令工具，不捏造」（[原文](evidence/ef3/aos-auto/gap/luna-nothink-reply.json)）。每題白花約 4.3k token、3～10 秒，然後才升到 sol-high。疑似被提示詞那句「你沒有任何工具」帶偏（MC 為 sol 開場白加的），只對 nothink 小模型有這副作用；不在本隊領地，沒改。
- sol-high 本身不穩：gap 在第一次（[run1](evidence/ef3/aos-sol-high-run1/)，驅動 bug 沒接重問、作廢）第 2 關被測試擋；runs 在升級鏈裡也被擋一次。上表「前」都 1 輪過是運氣，3 題樣本太小，runs 的 30k 主要是這個變異，不全是鏈的錯。
- 結論：**難題上升級鏈比直接 sol-high 貴**（平均 token +83%、秒 +33%），通過率相同；省的只有「第一級就答對」的簡單題。

## 呼叫數

真 AI 26 次（≤60）：CSV 15、aos 前 4（含作廢 1）、aos 後 7。全走 llmcall／LiteLLM，只用 chatgpt-gpt-6-*。

## 給下一步的建議（使用者／頂層定）

1. ~~aos 學徒的鏈改從 sol-high 起~~ **已做**（頂層 10-09 定）：`APPRENTICE_LADDER`＝sol-high → astra-high，CSV 仍從 luna-nothink；「沒有工具」那句不改。
2. 或者改提示詞讓 luna-nothink 不拒答（把「沒有工具」改成「不用工具，直接寫出完整檔案」），再量一次——動到 MC 的開場白對策，要重測 sol。
3. 升級前的「拒」目前不分原因；若第一級是「拒答」（`files` 空）可直接跳級，省第 2 關沙箱時間（目前第 1 關就擋，代價小）。
