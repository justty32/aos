# step 任務包（步驟表直譯器）第一版

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)｜細部規則：[spec.md](spec.md)｜依據：[第六輪綜合](../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md)、[第五輪骨架](../../../proto7/notes/thinking/2026-10-04-r5-synthesis.md) §4

**一個普通 `keep` 任務照步驟表一步步派子工作（`once`），子工作把結果寫到槽外，直譯器靠結果檔推進、被殺後接回同一嘗試。** 通用任務包（原則 5、8）：不帶 LLM、帳、資源；daemon／tick 核心零新增，只用核心公開的檔（tasks.json 拿表鎖三態寫、槽 birth／exit、round.json、tock.json、槽 ctl.json、daemon 的 wake 控制檔）。

| 項目 | 內容 |
|---|---|
| 分類 | 通用任務包（`layer: kernel`），單 node |
| 接法 | A 普通 keep 任務：`{"name": "step-<job>", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/step/bin/aos7-step", "run", "jobs/<job>"]}` |
| 預設 | 不裝就不存在；選項預設與可逐步覆蓋的選項見 spec §2 |
| 依賴 | 工具包（`aos7_taskside.wait_tock`、`aos7_ctl`）、核心 `aos7_fs`（`edit_json`、`fact`） |
| 程式 | `aos7_step.py`（直譯器、檢查器、人手指令）、`aos7_step_result.py`（子工作包裝程式）、`bin/aos7-step`、`bin/aos7-step-result` |
| 範例 | `examples/minimal/`（一步，入門用，見下「第一次跑」）、`examples/csv/`（CSV→JSON→統計報表，兩步都冪等）、`examples/backup/`（dump→verify→rotate→notify，rotate 不冪等） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py` 預設就收 `packs/*/tests`；只跑本包給 `packs/step/tests`） |

## 第一次跑（最小範例，已實跑）

範例整份放進 `<node>/jobs/<job>/`（步驟表裡的路徑相對 node）；人手指令（`check` 以外）都在 **node 目錄**下執行，路徑寫 `jobs/<job>`。`<proto7-2>` 換成原型目錄的絕對路徑。

```sh
P=<proto7-2>
mkdir -p <root>/<node>/jobs && cp -r $P/packs/step/examples/minimal <root>/<node>/jobs/minimal
python3 $P/packs/step/bin/aos7-step check <root>/<node>/jobs/minimal/steps.json   # 印 []、退出 0
python3 $P/bin/aos7-ctl daemon <root> register <node>
python3 $P/bin/aos7-ctl add <root>/<node> '{"name": "step-minimal", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/step/bin/aos7-step", "run", "jobs/minimal"]}'
python3 $P/bin/aos7-daemon <root> &
cd <root>/<node> && python3 $P/packs/step/bin/aos7-step status jobs/minimal   # 等到 "phase": "ended"、"end": "ok"（約兩回合）
cat jobs/minimal/out/hello.txt                                                   # hello
python3 $P/bin/aos7-ctl daemon <root> stop --kill
```

`examples/minimal/steps.json` 是一步 `run`（`finite`、`idempotent`、`expect` 產物、`ok`→`done`）；csv、backup 是多步範例，裝法相同。

## 四個組件（契約卡，細節在 spec.md）

**直譯器 `aos7-step run <工作資料夾>`**
- 職責：啟動時先推進一圈，之後每觀察到新的 tock 再推進一圈（spec §5）：讀框架、查槽外結果、推進 `pc`；一次最多登記一個子工作的 `once`。框架 `frame.json` 只放接續狀態與把手。
- 前置條件：自己是 `max_live: 1` 的 keep（同一工作同時只有一個直譯器，核心保證 keep 不雙開）；步驟表過了檢查器；`frame.json`、`results/` 只有本包寫；改 tasks.json 的人都拿表鎖。
- 保證：同一嘗試不派第二次；同一結果只推進一次；步拿不到結果（槽結束沒結果、過期 intent）與拿到 `unknown_codes` 裡的退出碼都走 `on_unknown`；預設空時退出碼非 0 一律是失敗結果；證據不足停在 `unknown`，不自動重送（除非步宣告冪等且選了 `on_unknown: resend`，最多 `max_resends` 次、預設 1）；壞表拒寫；框架壞了不前進、記錯、等人；耐性用本地回合（pause 時不走）：`wait` 從進入該步的 `frame.since` 起算，`run` 從當次 `pending.since` 起算，建立新嘗試或人手 `resume` 時重設相應起點——不是整個步驟不可重設的總期限；工作進行中步驟表被改＝停（版本固定）。
- 明確不管：子工作做的事對不對、外部效果（只看結果檔與它宣告的產物）；人手改 `frame.json`／`results/`；派工以外的資源、帳、鄰居。

**子工作包裝程式 `aos7-step-result`**
- 職責：跑實際命令、等它結束、檢查宣告的產物，原子發布一份結果檔（帶 job／inst／step／request／attempt 與核心 `slot#run`）。退出碼照抄命令的。
- 前置條件：由直譯器登記的 once 起（argv 由直譯器展開）；結果檔路徑這次嘗試獨有。
- 保證：結果檔要嘛完整、要嘛不存在（先寫完暫存檔，再以 hard link 發布）；目的檔已存在就拒絕、不覆寫；被殺就沒有結果（不假報）。`ok` 要退出碼 0，且 `expect` 列的都是讀得完、算得出 SHA-256 的檔（目錄、讀不了的都算 missing）。
- 明確不管：命令本身的冪等與副作用；結果寫好之後才發生的事。

**結果檔 `results/<step>/<attempt>.json`**：工作交付的依據；`exit.json` 只是旁證。到工作結案（`aos7-step close`）才清。

**檢查器 `aos7-step check <steps.json>`**：先驗欄位型別（壞型別也回 JSON 診斷、不拋例外）、結構錯誤（選項限制查套預設後的有效值）＋三條（等結束只等有限工作；重試要冪等或先查回條；時間值標線——v1 只有本地回合）。不執行、不改檔；有錯退出碼 1。

## 人手指令

- `aos7-step status <工作資料夾>`：印框架摘要（`pc`、等誰、停在哪、最近錯誤）。
- `aos7-step resume <工作資料夾> [--resend]`：只接受 `halted`，清掉停住（`halt`）。`pending` 還在時：不加 `--resend` 保留那次嘗試、重新查證（結果已到就照結果走）；加 `--resend` 丟掉舊 `pending`，用同一個 request、新 attempt 重派，不先採用舊嘗試遲到的結果（人負責）。**`failed` 停點（結果 `ok: false`、表上沒寫 `fail`）已經清掉 `pending`，普通 `resume` 也會派新 attempt——`idempotent: false` 的步一樣會再跑一次。** 工作已 `ended` 不能 `resume`。
- `aos7-step close <工作資料夾>`：工作已結束才可以：清 `results/`，框架標 `closed`。

## 界線

- 框架與 tasks.json 不是同一筆交易（派工與中斷恢復順序見 spec §5 第 4 步）；第一版不做交易，跨回合說不清的一律 `unknown`。
- 回合耐性是「這個 node 的回合」，不是牆鐘；`until_round` 是啟動准入，不是完成期限，本包不用它。
- 核心只保證 once 最多一次、once 槽報完再留一回合。已發布的結果檔在槽外，不受槽刪除影響；但派工中斷後能不能補加，仍依賴 tasks.json、槽 birth 證據；補加只准同回合，下一回合走 on_unknown（spec §5 第 4 步）。
