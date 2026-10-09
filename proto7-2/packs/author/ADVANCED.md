# author 進階

← [README](README.md)｜[spec](spec.md)｜[藍圖](../../notes/blueprint-llm1.md)｜[step](../step/README.md)

需求與候選驗證後編成 step 工作，意圖→表鎖內合併自己一項→回條；step 執行，獨立檢查器驗答案。核心與其他包不改。

| 項目 | 內容 |
|---|---|
| 分類 | 單 node 的上層任務包 |
| 接法 | CLI、llmcall、events must；發布 CSV 為 keep／max_live=1 的 step 表項 |
| 預設 | propose 不發布；auto 只給固定試驗 |
| 保存 | author 共用鎖、events.json、每 rid 五檔；CSV close 後剩 request／receipt |
| 依賴 | aos7_fs、aos7_tick.check_item、step.check／table_rev（唯讀） |
| 程式 | aos7_author.py（驗證／CLI）、aos7_author_pub.py（發布／events）、aos7_author_llm.py（CSV LLM）、aos7_author_aos.py（aos 學徒／審查／learn）；bin/aos7-author、bin/aos7-gates |
| 工具卡 | toolcards/csv.json、aos-tool.json、aos-module.json |
| 範例 | examples/csv-request（合法與六份壞候選）、[LLM](examples/llm-request/README.md)、[events](examples/events-request/README.md) |
| 測試 | tests/test_author*.py（升級鏈在 test_author_ladder.py）；repo 根 scope 內跑 tests/run_all.py packs/author/tests |

## 真 AI 產候選

先登記需求，再在 node 內執行（budget 可在另一個 node）：

```sh
python3 "$A/bin/aos7-author" propose csv1 --llm MODEL --budget ../llm/budget/llm --prompt-out prompt.json
python3 "$A/bin/aos7-author" propose csv1 --llm MODEL --budget ../llm/budget/llm
```

**升級鏈（`--llm` 不給模型）**：先 `chatgpt-gpt-6-luna-nothink`；模型答了（outcome answered）且候選確實被擋（CSV 前兩層驗證、aos 三關含審查、檢查器退 1）才升 `chatgpt-gpt-6-sol-high`，再擋才 `chatgpt-gpt-6-astra-high`，三級都擋就照最後一級回報。沒答成（HTTP 錯、逾時、unknown、審查模型沒答成）、檢查器參數錯（退 2）、conflict、full 一律立刻停、不升級。回覆多一個 `rounds`：每級的 model、call_id、why、usage；`--call X` 時各級是 `X`、`X-r1`、`X-r2`（超過 64 字改成截短加雜湊）。aos 學徒（aos-tool／aos-module）的鏈從 sol-high 起、少 luna-nothink 那級（它在這類題實測 3／3 拒答）；升級時把上一級的候選與檢查結果當 `previous`／`feedback` 交下一級（CSV 沒有重問欄，下一級拿同一份提示）；給了 `--out a.json` 時各級分寫 `a.json`、`a-r1.json`、`a-r2.json`；`--prompt-out` 只寫第一級；`learn` 用第一級。`propose --llm csv1` 這種寫法 csv1 仍當 rid。給了模型名（含字面 `auto`）就只用那一個，回覆不帶 `rounds`。實測：[ef3](../../notes/play/2026-10-09-real-ai/ef3.md)。

`--prompt-out` 只寫請求。提示只含需求、白名單卡、schema 與限制，不含答案、不設 max_tokens／temperature。call_id 按請求雜湊固定，重跑回原條；新生成用 `--call NEW_ID`。原文不剝圍欄、不修 JSON；預設另跑 publish。

[LLM 實跑](examples/llm-request/README.md)由人啟動 LiteLLM 後執行，不進測試套。

## aos 工具／模組

kind 為 `aos-tool`／`aos-module`：學徒交新增檔案、索引列與 REPORT，三關過後由人發布。原文存 `author/aos/<rid>/`，可用 `--out` 改。

- 學徒：`--llm` 指定寫候選的模型（不給＝上面的升級鏈），提示帶需求與工具卡。
- 技能：`propose --skills NODE` 從 NODE 的 skills/ 挑一本學徒先前留下的技能書，全文帶進提示；挑不到或書超過 8192 bytes 就略過，升級也用同一本。
- 審查人：`--review-llm` 指定讀碼模型，與學徒一樣經 llmcall 使用 budget。只因真錯誤（照需求寫明的行為在真實資料上答錯／當掉）、唯讀違規、越界改動退件；需求沒寫明的極端邊角列進 reasons 當「建議：」、不擋（只列建議的 reject 照 accept 算）。標準在檢查器的 `REVIEW_CRITERIA`，llmcall 與 astra 審查共用。第一關 size 會寫明哪個檔、實際 bytes、上限。
- 重問：用 `--previous`、`--feedback` 與 `--gotchas` 把上一份候選、檢查結果和踩坑交回學徒。
- 發布：重跑三關後只新增 apprentice 分支，合併由人處理。
- 技能學習：`learn --skill-into NODE --skill NAME [--candidate PATH]` 把踩坑和驗過的骨架改寫成整本 SKILL.md；驗過格式與 kind 觸發詞才替換，可再用 `--skills` 讀回。與 `--into` 恰選一個；只有技能學習允許 `--candidate` 與 `--llm` 共存。candidate 不存在或是資料夾時，呼叫模型前退 invalid／2；其他讀取故障退 unknown／3。格式檢查退 1 算拒收（invalid／1），其他非零碼算 unknown／3，保留模型回條與舊書。拿鎖後若書的 bytes／存在狀態與學習前不同，保留新版、退 conflict／1，提示重跑 learn。
- 學習：`learn` 讀歷次檢查結果，把下次該知道的事追加到既有踩坑檔。

`$A` 指 author 包；`$CANDIDATE`、`$REVIEW` 取 propose 回覆，`$REPO`／`$REF` 是發布位置與基準；先備好 history.json、GOTCHAS.md。

```sh
python3 "$A/bin/aos7-author" propose request.json --llm MODEL --review-llm REVIEW_MODEL --budget ../llm/budget/llm
python3 "$A/bin/aos7-author" publish request.json --candidate "$CANDIDATE" --reviewer "file:$REVIEW" --repo "$REPO" --ref "$REF"
python3 "$A/bin/aos7-author" learn request.json --llm MODEL --budget ../llm/budget/llm --history history.json --into GOTCHAS.md
```

propose 固定候選快照，兩次檢查與審查提示使用相同 bytes；publish 使用 `file:` 審查前仍先通過 rules，且不接受 `--review-llm`。learn 在寫入時鎖住既有檔案、重讀驗重，檔案消失就拒絕。學徒、審查、學習的 logical 分別為 `author/<rid>`、`author-review/<rid>`、`author-learn/<rid>`。

三關見下節；真 AI 學徒與重問實跑見 [apprentice-aos 報告](../../notes/play/2026-10-09-real-ai/apprentice-aos.md)。

## 五個組件（契約卡，細節在 spec.md）

**需求 `register`（`author/req/<rid>/request.json`）**
- 職責：嚴格讀需求、驗欄位與輸入雜湊、保存原文；`request_sha`＝原文雜湊，後續帳都記它。
- 前置條件：需求寫者給 rid（英數與 `_`、≤23 字）；輸入檔在 node 裡、是一般檔。
- 保證：同 rid 同 bytes＝dup、不增檔；不同內容＝conflict、不覆寫；輸入雜湊不符、路徑型 rid＝invalid。
- 明確不管：需求本身合不合理（人審）；事件收件由 send／intake 負責（spec §10）。

**候選與驗證 `propose`（`candidate.json`、`verdict.json`、`jobs/<job>/`）**
- 職責：保存候選原文（壞 JSON 也存、可審查），前兩層驗證（格式與展開、工具卡契約＋step 檢查器），過了確定性編譯出 `jobs/<job>/` 的固定來源與 payload 雜湊。
- 前置條件：需求已登記；每 rid 同時一個待審候選；已發布版本 <2。
- 保證：壞 JSON、參數、依賴、模式、冪等、寫 out 外全拒；不建 jobs、不動 tasks。finite／idempotent 由卡決定；同輸入同 steps bytes／payload，不修 JSON。
- 明確不管：答案對不對（第三層，發布後 `answer` 驗）；任意程式／shell（只組卡上的工具）。

**發布 `publish`（`intent.json`、`receipt.json`、tasks.json 一項）**
- 職責：重算 payload（與 verdict 不同＝拒）、寫意圖、拿表鎖只合併自己那一項、寫回條；中斷後照證據恢復。
- 前置條件：驗證過；改 tasks.json 的人都拿表鎖。
- 保證：spec §5 五列恢復：原條不補表；相符表項或 birth／frame 補條；只有意圖 unknown；同名改過／disabled conflict。別項與頂層不改、壞表不覆蓋，各版 job／out 獨立。
- 明確不管：執行中換版、自動 retire 舊版；unknown 後要不要重送（人手 `--resend`，人負責）。

**答案與結案 `answer`／`close`**
- 職責：step 結束、close 前跑獨立檢查器（自己由 CSV 算答案，核結果檔識別、各步恰 1 attempt、產物雜湊、steps 雜湊＝verdict）；結案時把 hashes、證據、答案寫進回條，刪 candidate／verdict／intent。
- 前置條件：每版 step 已 `aos7-step close`、答案已驗；沒有結果不明的意圖。
- 保證：未解意圖＝unknown、一檔不刪；中途被殺可重送接著清；close 後每需求恰 2 檔。
- 明確不管：retire／kill／刪 `jobs/<job>/`、改表項。

**收件 `send`／`intake`（`author/events.json`）**
- 職責：send 保存原文到 must；intake 登記需求、寫最後一筆回條，再 ack。
- 前置條件：node 名一致；對方 node 已有 `events/`（send 不替別人建夾，沒有就退 1，叫你用 aos7-up 起 node 或 `aos7-events pub --create`）；send 的寫者不必有 node 輸入檔。
- 保證：full 不算送出；同 rid 異文衝突；回條前重讀、回條後只補 ack；invalid／conflict 不阻塞後續；unknown 留待重試。
- 共用 must：intake 只收 `author.request`。遇別人的事件（如 `mail.request`），events 已確認到它就讓過；還沒確認就停下、不替它 ack，回 `conflict`＋`blocked:{seq,kind,event_id}`、退 1，stderr 一行說哪一筆擋住；它的主人處理並確認後再 intake。
- 明確不管：多消費者、窗口外去重、obs、自動 propose／publish（細節見 spec §10）。

## 錯誤與退出碼

退出碼照 [藍圖](../../notes/blueprint-errors.md) §2：0 做到、1 做不到（conflict／full；候選已收下但被拒＝驗證或某關沒過、模型回覆不能用、分支衝突）、2 你給的不對（參數、需求檔、找不到檔，什麼都沒動）、3 不確定（照原樣再跑會接續）。`why` 欄位照舊：被拒的候選仍是 `invalid`，靠退出碼 1 與「候選沒過：」那行和用法錯（2）分開。

| why | 何時 |
|---|---|
| invalid | 需求欄位／rid／輸入雜湊不合；候選沒過驗證（`issues` 的 `rule`：size／json／schema／attr／nul／mode／tool／param／path／graph／dep／step／task／source）；`payload_changed`；`--resend` 用在沒有 unknown 的版本 |
| conflict | 同 rid 異內容；表上同名項改過或 disabled；job 前 8 碼撞名或 `jobs/<job>/` 有不同內容；已結案；close 條件不足（step 未 close、答案未驗、還有待審的合法候選）；已有回條還 `--resend` |
| unknown | 作者帳或 tasks.json 讀不到／壞、鎖逾時、只有意圖沒有登記證據、有結果不明的版本時再 propose／close |
| full | must 滿、不算送出；已發布 2 版還 propose（先 close） |

## 界線

- 第二刀已接 llmcall 真傳輸（`--llm`）與 budget token 帳；仍可用 `--candidate` 注入，接收與驗證介面不變；adapt-llm 尚未接。
- 回條只證明「登記過」，不證明 CSV 正確；答案由 `answer` 另驗。
- 作者帳是單 node、合作式：同 node 只有一套作者帳，人不手改 `author/`。

## 三關 aos7-gates

入口是 `bin/aos7-gates`，成功只印 stdout（brief 是 BRIEF，check／publish 是單行 JSON），失敗另印 stderr 一行。

| 指令 | 用法 |
|---|---|
| brief | `aos7-gates brief request.json` |
| check | `aos7-gates check request.json candidate.json [--ref REF]` |
| publish | `aos7-gates publish request.json candidate.json --repo REPO [--ref REF]` |

`--reviewer rules|astra|file:PATH` 預設 rules（離線），astra 明示才呼叫 codex。ref 預設 HEAD；publish 必須明給 --repo，未給只回報預計 repo／分支，不跑三關、不建分支。測試預設包 user scope（TasksMax=300、RuntimeMaxSec=900），已在 scope 裡用 `--no-scope`。

| 關 | 檢查 |
|---|---|
| 1 | 嚴格 JSON、欄位、範圍、佈局、測試、大小、README、lint、索引連結 |
| 2 | run_all.py 至少跑一項測試，再用需求指定的獨立答案檢查器驗答案與唯讀；bwrap 白名單掛載、空環境與 HOME、斷網，只有暫存樹可寫 |
| 3 | rules 掃非 md／json 檔（含入口）；file:PATH 讀嚴格 verdict；astra 呼叫 codex exec |

題目在 examples/aos-tool-usage、aos-module-diag，卡在 toolcards/。從 ref 解原型，lint 用來源 repo 的 wf-lint.sh，無 checkout clone 也能驗。

界線：只新增 apprentice 分支，合併由人處理；用臨時 git index 從固定 ref 與候選 bytes 建樹，不動 HEAD、原 index、工作樹或其他分支。同名只比樹、異樹或 symbolic ref 不覆蓋。第一關只收 root 直下 tests/test_*.py；第二關獨立要求實際測試。索引列插在最後一個符合卡前綴的表格末列後；物化與發布共用插列函式。

### aos 結案標記

author 的 aos publish 成功（含 dup）後，用 Node 共用鎖與 write_json 寫 cwd 的 `author/req/<rid>/receipt.json`：`{v:1,rid,request_sha,closed:true,kind,closed_at,versions:{candidate_sha:{job,branch,commit}}}`。request_sha 是需求 bytes 的 SHA-256；closed_at 是 UTC 秒，保留第一次結案時間。新版本併入 versions；已有其他形狀（含 CSV 帳）保留原樣、加 close_skipped，成功碼不變。鎖忙或寫入故障回 unknown，明示分支已建；照原樣重跑可按 dup 接續。check／propose 不寫結案標記。
