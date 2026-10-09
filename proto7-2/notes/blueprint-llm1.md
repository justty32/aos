# LLM 作者第一版藍圖（llm1）：先用假候選走通 CSV 固定工具作者

依據：[llm-author][a] §三／§四／§九／§十、[prior-art](reviews/2026-10-05/prior-art.md) §9、[blueprint-ev1](blueprint-ev1.md)、[pm 計畫](plan-2026-10-09-pm.md)、[代定清單](decisions-2026-10-09.md) 下午節、[CSV 範例](../packs/step/examples/csv/)。A0 隊 10-09；今天只到藍圖。細項走 [items json](blueprint-llm1-items.json)（作者檔／介面皆新）。

## 1. 一句話

新包 `packs/author/`：需求＋候選（測試注入假候選）經三層驗證、確定性編譯成獨立版本 step 工作，以「意圖→表鎖內合併自己那一項→回條」發布；step 執行、獨立驗 CSV。模型不進排程迴圈、不碰核心。

## 2. 硬約束

- 核心零改動；step／budget／adapt／history.py 不改。真呼叫等使用者看過藍圖且第二刀契約到位；自動 JSON 修復＝0。
- user-advice：檔隨需求增、不隨回合增；清垃圾。每需求一個 `author/req/<rid>/`，固定 ≤5 檔：`request.json`、`candidate.json`、`verdict.json`、`intent.json`、`receipt.json`；加 `jobs/<job>/`。
- `aos7-author close <rid>`（step `close` 後）刪 candidate／verdict／intent，只留 request＋receipt；未解不刪。

## 3. 第一刀（A1-1～7）

1. 需求／ID：`request.json`＝`{"v":1,"rid":"csv1","goal":"部門統計","inputs":[{"path":"data.csv","sha256":"<實際雜湊>"}],"tools":["csv.convert","csv.stats"]}`。rid 由需求寫者給、記內容雜湊；同 rid 異內容＝conflict。
2. 工具卡：新 `toolcards/csv.json` 定 argv 樣板、參數型別、產物名，只寫 `${out}`；`finite`／`idempotent` 由卡決定，候選宣告無效。
3. 假候選：`aos7-author propose <rid> --candidate <file>`；第二刀換 gateway、介面不變。例：

```json
{"v":1,"mode":"keep","intent":"轉檔後統計","start":"convert","steps":[
{"id":"convert","tool":"csv.convert",
 "args":{"src":"${job}/data.csv","dst":"${out}/data.json","request":"${request}"},
 "ok":"stats","fail":"failed"},
{"id":"stats","tool":"csv.stats",
 "args":{"src":"${out}/data.json","request":"${req:convert}","dst":"${out}/report.json"},
 "ok":"done","fail":"failed"}],
 "ends":{"done":"ok","failed":"failed"}}
```

4. 驗證／編譯：格式／展開、工具卡契約、實際成果（步 7）。前兩層過才寫 `jobs/<job>/steps.json`；`job=<rid>_<候選雜湊前8碼>`（rid 英數 `_`、≤23 字，合 step 命名），每版 job／out 獨立，`options.restart_on_end:false`。tasks 一項：keep、`max_live:1`、argv 跑 `aos7-step run jobs/<job>`，`x.author={owner,rid,candidate_sha,payload_sha}`。verdict 綁 payload；不過不寫 jobs、不碰 tasks。
5. 發布：intent（含 payload_sha）→拿 `tasks.json.lock` 重讀、只比自己那項、合併→receipt。模型／驗證在鎖外；發布前重算 payload，異於 verdict 就拒。保留別項與頂層設定（[核心](../spec.md) §4.1／§4.3）。恢復（[作者 §4.3][a]）：

| 證據 | 動作 |
|---|---|
| 有回條 | 回原條，不補表 |
| 相符表項 | 補回條，不追加 |
| 表項消失、有相符 birth | 補回條，不補表 |
| 只有 intent | unknown，不補加 |
| 同名改過／disabled | conflict，保留現況 |

6. 執行：step 不改；CSV convert.py／stats.py 原樣複製入 job、記雜湊。
7. 答案：新 `examples/csv-request/check_answer.py` 自算 data.csv 的 by_dept 對 report.json；查 `results/convert`、`results/stats` 各1 attempt，close 前驗。

## 4. 第一刀驗收

- 合法候選：step `ended ok`、檢查器過、每步恰 1 attempt、steps 雜湊＝verdict。
- 六壞全拒：壞 JSON、錯參數（型別／多餘）、錯依賴（未採用 convert／環）、錯模式 each／once、假冪等、寫 `${out}` 外；tasks.json 位元組不變，無 `jobs/<job>/`。
- 三點各 SIGKILL ×3 後重跑同 rid：`author:after-merge`／`after-receipt` 表項、回條各 1；`after-intent` 回 unknown、表 0、不補加，人手 `publish <rid> --resend` 後恰 1。
- 回條前移除表項且無正證據→unknown、不補加；disabled／改過→conflict、保留現況。
- 驗證後換 steps→拒發布；同 rid 兩版不互蓋。
- 100 需求 close 後：`author/` 檔數＝2×100＋常數，無回合檔／暫存。

## 5. 十二題代定

照 [llm-author §十][a] 預設；「第一刀生效」＝明天就照做，〔記〕＝預設已記，第二／三刀開隊時頂層再核。

1. 作者或轉換先行→CSV 作者；第一刀生效。翻案：§3＋A1-1／A1-2 換題目。
2. 組工具或寫程式→只組可信工具；第一刀生效。翻案：A1-2 工具卡＋§8。
3. 自動發布？→預設 propose 出候選，人跑 `aos7-author publish <rid>`；自動僅測試與 `--auto` 明示固定試驗；第一刀生效。翻案：A1-3 `propose`／`publish`。
4. 執行中換版？→只新增獨立版本；第一刀生效。翻案：§3 步 4–5（另開換版交接）。
5. adapt 要最新？→非控制 within_age，須最新 current_only；〔記〕。翻案：第三刀 F-08。
6. 逐件或最新？→作者逐件接 ev1 must（§6），最新可合併；〔記〕。翻案：§6。
7. token 計量／上界？→一端點一計量，無已證上界為軟預算；〔記〕。翻案：第二刀 F-03。
8. 遠端不明？→留 R、不重送，新生成另記政策；〔記〕。翻案：第二刀 F-01。
9. usage 不明？→存／顯示有效候選、billing pending，留預留；〔記〕。翻案：第二刀 F-03。
10. adapt 語意驗收？→有限欄位、必要否定／例外、獨立答案；〔記〕。翻案：第三刀驗收。
11. 抗何種故障？→驗程序中斷，未結算／未確認消費資料不清；〔記〕。翻案：A1-8＋F-10。
12. 何時 agent？→作者與單次呼叫價值確認後；〔記〕。翻案：§8。

## 6. 與事件保存的最小交接

依 [ev1](blueprint-ev1.md) §3／§4：第一刀不接 events，只讀 request.json。之後需求寫者經 ev1 發布者送 must：`capture:"published"`、`event_id:"author/<rid>"`、payload 帶 request 內容雜湊。作者讀游標，**回條寫成後**才 `store.ack(events_dir, upto)`；讀到／LLM 看過不算消費；must 回 full 不算送出；adapt-llm 最新值走 obs／tock，不用 must。

## 7. 第二刀與第三刀（今天不排）

- 第二刀：單次 LLM gateway＋token 部分結算（[作者 §九][a] 六條；一端點一計量、非串流、先假傳輸）；依賴 budget 加部分結算，完成才把假候選換真 call。
- 第三刀：非控制 adapt-llm（固定來源版本、兩政策），依賴第二刀。故障矩陣見 items F-01～10。

## 8. 不做

真模型、gateway、token 帳、adapt-llm、任意程式／shell、執行中換版、自動 retire 舊版、完整 agent／多輪記憶、改核心或 step。

## 9. 分線

| 線 | 領地 | 件數 | done |
|---|---|---|---|
| A1 | 新 `proto7-2/packs/author/`：`aos7_author.py`、`aos7_author_pub.py`、`bin/aos7-author`、`toolcards/csv.json`、`examples/csv-request/`（需求、7 份候選、check_answer.py）、`spec.md`、`README.md`、`tests/test_author.py`；`INDEX.md` 一列 | A1-1～A1-8 | §4 全條 |

## 10. 隊長代定（細節，好反悔）

① 新包放 `packs/author/`（上層任務包），清單列在 [INDEX](../INDEX.md)；`bin/` 被 .gitignore 擋，要 `git add -f`（同 step）。
② job＝`<rid>_<sha8>`、表項名 `author-<job>`；短雜湊撞名以完整 sha 核，不符 conflict。
③ after-intent 死與「登記後被人移除」證據相同 → 一律 unknown；續發只靠人手 `--resend`（仿 step `resume --resend`，人負責）。
④ 每 rid 同時一個待審候選；已發布版本上限 2（`max_versions`），超過回 `full`，先 close。翻案：config 一處。
⑤ 候選帶 `finite`／`idempotent`／argv 一律 invalid，不靜默改寫。
⑥ 作者寫者共用一把 `author/author.lock`（常數檔），不每 rid 一鎖。

[a]: reviews/2026-10-05/llm-author.md
