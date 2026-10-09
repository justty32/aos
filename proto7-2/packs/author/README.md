# author 任務包（LLM 作者第一刀：CSV 固定工具作者，假候選）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)｜細部規則：[spec.md](spec.md)｜依據：[藍圖 llm1](../../notes/blueprint-llm1.md)、[llm-author 報告](../../notes/reviews/2026-10-05/llm-author.md)｜執行：[step 包](../step/README.md)

**需求＋候選（第一刀由檔案注入，第二刀換 gateway、介面不變）經三層驗證、確定性編譯成一個獨立版本的 step 工作，以「意圖 → 表鎖內只合併自己那一項 → 回條」發布；step 執行，獨立檢查器驗 CSV 答案。** 模型不進排程迴圈、不碰核心；核心、step、budget、adapt、history.py 零改動。

| 項目 | 內容 |
|---|---|
| 分類 | 上層任務包（LLM 層，第一刀不接模型），單 node |
| 接法 | 人手 CLI（node 目錄下跑）；發布的表項是 `{"name": "author-<job>", "mode": "keep", "max_live": 1, "argv": ["python3", "<proto7-2>/packs/step/bin/aos7-step", "run", "jobs/<job>"], "x": {"author": {...}}}` |
| 預設 | `propose` 只產可審查候選、不發布；人另跑 `publish`。`--auto` 只給固定試驗與測試 |
| 保存 | `<node>/author/`：共用 `author.lock`＋每需求 `req/<rid>/` ≤5 檔；`close` 後只剩 `request.json`＋`receipt.json`（檔數隨需求數、不隨回合／候選數） |
| 依賴 | 核心 `aos7_fs`（`fact`、`write_json`、`edit_json`、`locked`、`test_point`、`sweep_tmp`）、`aos7_tick.check_item`（唯讀）；step 的 `check`／`table_rev`（唯讀） |
| 程式 | `aos7_author.py`（需求、工具卡、候選驗證與編譯、answer、close、CLI）、`aos7_author_pub.py`（發布與恢復）、`bin/aos7-author` |
| 工具卡 | `toolcards/csv.json`：`csv.convert`、`csv.stats`（腳本原樣取自 [step CSV 範例](../step/examples/csv/)、記 SHA-256） |
| 範例 | `examples/csv-request/`：`request.json`（rid `csv1`）、七份候選（`valid.json` 一份合法；`bad-json`／`bad-params`／`bad-dependency`／`bad-mode`／`bad-idempotent`／`bad-path` 六份壞）、`check_answer.py` |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py packs/author/tests`；全套預設就收） |

## 第一次跑（已實跑）

命令都在 **node 目錄**下執行（需求的 `inputs` 路徑相對 node）；作者的 bin 與 step 入口都用 `python3` 呼叫，表項裡的 step 入口是絕對路徑。`<proto7-2>` 換成原型目錄的絕對路徑。

```sh
P=<proto7-2>; A=$P/packs/author
mkdir -p <root>/<node>/.aos && cd <root>/<node>
cp $P/packs/step/examples/csv/data.csv .                                   # 需求的輸入（雜湊寫在 request.json）
python3 $A/bin/aos7-author register $A/examples/csv-request/request.json   # ok、dup false；再跑一次 dup true
python3 $A/bin/aos7-author propose csv1 --candidate $A/examples/csv-request/bad-path.json   # 退出 2，issues 的 rule 是 path
python3 $A/bin/aos7-author propose csv1 --candidate $A/examples/csv-request/valid.json      # ok、job csv1_32ac171d；表還沒動
python3 $A/bin/aos7-author publish csv1                                     # 回條 evidence table；.aos/tasks.json 多一項 author-csv1_32ac171d
python3 $P/bin/aos7-ctl daemon <root> register <node>
python3 $P/bin/aos7-daemon <root> &
python3 $P/packs/step/bin/aos7-step status jobs/csv1_32ac171d               # 等到 "phase": "ended"、"end": "ok"（約三回合）
python3 $A/bin/aos7-author answer csv1                                      # 獨立檢查器：answer.ok true（step close 之前跑）
python3 $P/packs/step/bin/aos7-step close jobs/csv1_32ac171d
python3 $A/bin/aos7-author close csv1                                       # author/req/csv1/ 只剩 request.json、receipt.json
python3 $P/bin/aos7-ctl daemon <root> stop --kill
```

job 名＝`<rid>_<候選 sha256 前 8 碼>`，候選 bytes 不變時就是上面的 `csv1_32ac171d`。報表在 `jobs/csv1_32ac171d/out/report.json`：eng `{n:2,sum:200,avg:100}`、ops `{n:2,sum:120,avg:60}`、sales `{n:1,sum:200,avg:200}`、rows 5。close 不移除表項：ended 的工作再被 keep 起來會立刻退出；要收掉表項由人 `aos7-ctl rm`。

## 四個組件（契約卡，細節在 spec.md）

**需求 `register`（`author/req/<rid>/request.json`）**
- 職責：嚴格讀需求、驗欄位與輸入雜湊、保存原文；`request_sha`＝原文雜湊，後續帳都記它。
- 前置條件：需求寫者給 rid（英數與 `_`、≤23 字）；輸入檔在 node 裡、是一般檔。
- 保證：同 rid 同 bytes＝dup、不增檔；不同內容＝conflict、不覆寫；輸入雜湊不符、路徑型 rid＝invalid。
- 明確不管：需求本身合不合理（人審）；本刀不發 events（之後經 ev1 must 接，見藍圖 §6）。

**候選與驗證 `propose`（`candidate.json`、`verdict.json`、`jobs/<job>/`）**
- 職責：保存候選原文（壞 JSON 也存、可審查），前兩層驗證（格式與展開、工具卡契約＋step 檢查器），過了確定性編譯出 `jobs/<job>/` 的固定來源與 payload 雜湊。
- 前置條件：需求已登記；每 rid 同時一個待審候選；已發布版本 <2。
- 保證：六類壞候選（壞 JSON、錯參數、錯依賴、錯模式、假冪等、寫 `${out}` 外）全拒，拒時不建 `jobs/<job>/`、tasks.json 位元組不變；`finite`／`idempotent` 只由卡決定；同輸入 steps.json bytes 與 payload 相同；自動 JSON 修復＝0。
- 明確不管：答案對不對（第三層，發布後 `answer` 驗）；任意程式／shell（只組卡上的工具）。

**發布 `publish`（`intent.json`、`receipt.json`、tasks.json 一項）**
- 職責：重算 payload（與 verdict 不同＝拒）、寫意圖、拿表鎖只合併自己那一項、寫回條；中斷後照證據恢復。
- 前置條件：驗證過；改 tasks.json 的人都拿表鎖。
- 保證：恢復五列（spec §5）——有回條回原條不補表；相符表項補回條；表項消失但 birth／frame 相符補回條、不補表；只有意圖＝unknown、不補加；同名改過／disabled＝conflict、保留現況。別的表項與頂層設定原樣；壞表不覆蓋。兩版各自 job／out，不互蓋。
- 明確不管：執行中換版、自動 retire 舊版；unknown 後要不要重送（人手 `--resend`，人負責）。

**答案與結案 `answer`／`close`**
- 職責：step 結束、close 前跑獨立檢查器（自己由 CSV 算答案，核結果檔識別、各步恰 1 attempt、產物雜湊、steps 雜湊＝verdict）；結案時把 hashes、證據、答案寫進回條，刪 candidate／verdict／intent。
- 前置條件：每版 step 已 `aos7-step close`、答案已驗；沒有結果不明的意圖。
- 保證：未解意圖＝unknown、一檔不刪；中途被殺可重送接著清；close 後每需求恰 2 檔。
- 明確不管：retire／kill／刪 `jobs/<job>/`、改表項。

## 錯誤與退出碼

CLI 印 JSON `{ok, why, ...}`：`0` 成功（含 dup）、`2` invalid、`3` conflict、`4` unknown、`5` full。

| why | 何時 |
|---|---|
| invalid | 需求欄位／rid／輸入雜湊不合；候選沒過驗證（`issues` 的 `rule`：size／json／schema／attr／nul／mode／tool／param／path／graph／dep／step／task／source）；`payload_changed`；`--resend` 用在沒有 unknown 的版本 |
| conflict | 同 rid 異內容；表上同名項改過或 disabled；job 前 8 碼撞名或 `jobs/<job>/` 有不同內容；已結案；close 條件不足（step 未 close、答案未驗、還有待審的合法候選）；已有回條還 `--resend` |
| unknown | 作者帳或 tasks.json 讀不到／壞、鎖逾時、只有意圖沒有登記證據、有結果不明的版本時再 propose／close |
| full | 已發布 2 版還 propose（先 close） |

## 界線

- 第一刀沒有模型、gateway、token 帳、adapt-llm；第二刀以 gateway 取代 `--candidate` 來源，接收與驗證介面不變。
- 回條只證明「登記過」，不證明 CSV 正確；答案由 `answer` 另驗。
- 作者帳是單 node、合作式：同 node 只有一套作者帳，人不手改 `author/`。
