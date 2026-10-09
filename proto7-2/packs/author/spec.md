# author 包 spec（第一刀：CSV 固定工具作者，假候選）

← [author 包](README.md)｜[藍圖 llm1](../../notes/blueprint-llm1.md)｜[step spec](../step/spec.md)｜[核心 spec](../../spec.md) §4.1／§4.3

寫的是規則；理由在[藍圖](../../notes/blueprint-llm1.md)與 [llm-author 報告](../../notes/reviews/2026-10-05/llm-author.md) §三／§四。路徑未特別說明時都相對 node（命令的 cwd）。核心、step、budget、adapt、history.py 零改動；作者只讀 step 的檢查器與核心的任務項驗證。

## 1. 帳與檔數

`<node>/author/`：

| 檔 | 內容 |
|---|---|
| `author.lock` | 所有作者寫者共用的一把鎖（常數檔；不每 rid 一鎖） |
| `req/<rid>/request.json` | 需求原文（§2），不回填雜湊 |
| `req/<rid>/candidate.json` | `{"v":1,"active":sha,"versions":{sha:{"raw"｜"raw_b64","size"}}}`：候選原文（壞 JSON 也存） |
| `req/<rid>/verdict.json` | `{"v":1,"versions":{sha:{ok,validated,job,issues,payload_sha,manifest,steps_sha256,answer}}}` |
| `req/<rid>/intent.json` | `{"v":1,"versions":{sha:{rid,request_sha,candidate_sha,owner,job,payload_sha,steps_sha256,task}}}` |
| `req/<rid>/receipt.json` | `{"v":1,"rid","request_sha","closed","versions":{sha:回條}}` |

- 版本鍵＝`candidate_sha`（候選原始 bytes 的 SHA-256），都放在固定檔內；不隨候選、回合增檔。
- 每 rid 同時**一個待審候選**（`active`）：新候選換掉沒登記過的舊待審（連同它已寫的 `jobs/<job>/`，含「編譯完、verdict 未存就被殺」的殘留；前 8 碼與新候選相同＝conflict）；已發布版本保留。同一份候選重送回原審查、不增檔。
- 已發布版本上限 `MAX_VERSIONS=2`：達上限再 propose＝`full`，先 close。因此 `jobs/` 夾數 ≤ 2×需求數。
- 一版的固定來源在 `<node>/jobs/<job>/`：`steps.json`、`convert.py`、`stats.py`、`data.csv`；`frame.json`、`results/`、`error.json`、`out/` 屬 step，作者不碰。

## 2. 需求與 rid

`request.json`＝`{"v":1,"rid","goal","inputs":[{"path","sha256"}],"tools":[...]}`，欄位恰為這五個（嚴格 UTF-8 JSON：重複鍵、NaN 拒，不修復）。

- `rid`：英數與 `_`，1～23 字（`job=<rid>_<sha8>` ≤32 字，合 step 命名）；路徑分隔、NUL、`..` 自然不合。
- `inputs[].path`：相對 node、不收絕對／`..`／空段；要是一般檔（不跟 symlink、不逃出 node），SHA-256 與宣告相符；檔名互異。輸入複製成 `jobs/<job>/<檔名>`，檔名不得撞腳本、step 控制檔（`steps.json`、`frame.json`、`error.json`、`results`、`out`）或以 `.` 開頭（編譯時 `rule: source`）。
- `tools`：互異、每個都在工具卡。
- 登記：`author/req/<rid>/request.json` 已有相同 bytes＝`dup`（不增檔）；不同＝`conflict`，不覆寫。`request_sha`＝原文 bytes 的 SHA-256，記進 verdict／intent／receipt。

## 3. 工具卡（`toolcards/csv.json`）

`{"v":1,"answer_checker","tools":{id:{script:{src,as,sha256},argv,params,finite,idempotent,writes,artifacts}}}`。

- `argv` 是陣列（不經 shell），`{參數}` 換成候選的參數值；`${job}`、`${out}`、`${request}`、`${req:X}` 留給 step 展開。
- `params` 每項 `{type, role, value?, tool?}`：role `input`（`${job}/<需求輸入檔名>`）、`read`（`${out}/…`）、`write`（`${out}/…`；工具同目錄的 `<dst>.tmp` 也算寫路徑，見 §4 路徑）、`request`、`req`（`${req:<步>}`，該步工具＝`tool`）；有 `value` 的值要完全相等。
- `finite`／`idempotent`／`expect`（＝`artifacts`）**只由卡決定**；候選宣告這些（或 `argv`、`run` 等 step 欄）一律 invalid，不靜默改寫。
- 腳本從 `packs/<src>`（step 的 CSV 範例）原樣複製，雜湊要等於卡的 `sha256`。

## 4. 候選與三層驗證

候選＝`{"v":1,"mode":"keep","intent","start","steps":[{id,tool,args,ok,fail}],"ends":{名:"ok"|"failed"}}`，≤64 KiB、≤16 步。

**第一層（格式與展開）**，issue 的 `rule`：
`size`、`json`（不是嚴格 JSON）、`schema`（缺欄、多欄、型別、id 重複）、`attr`（宣告 finite／idempotent／argv 等）、`nul`、`mode`（只收 keep；each／once 拒）、`tool`（不在卡或需求白名單）、`param`（多餘、缺少、型別、值不等）、`path`（寫路徑不在這一版 `${out}`：絕對、`..`、空段、其他展開、已存在段經 symlink 逃出 `jobs/<job>/out`；`<dst>` 與 `<dst>.tmp` 都查）、`graph`（start／跳轉目標不存在、走不到的步）、`dep`（跳轉成環；`${req:X}` 在某條可達路徑上 X 還沒成功採用，或 X 不是指定工具的步）。

**第二層（工具卡契約）**：套卡生成 step 步驟表（`options.wake=false`、`restart_on_end=false`），交 `aos7_step.check` 檢查（`rule: step`），表項交核心 `check_item`（`rule: task`）；腳本與輸入雜湊不符＝`rule: source`。

**第三層（實際成果）**：發布後 step 跑完、close 之前由 `answer` 驗（§7）。發布前不假稱已驗答案（`answer: "pending"`）。

前兩層在記憶體完成；任何一條不過＝`invalid`，verdict 記 issues，**不建 `jobs/<job>/`、不碰 tasks.json**。過了才寫 `jobs/<job>/`（steps.json 最後寫）：已有同雜湊的檔重用，異雜湊＝`conflict`；同 job 名（前 8 碼撞）但完整 sha 不同的版本＝`conflict`，絕不覆蓋。

**steps.json** 用排序鍵、`indent=1`、UTF-8 輸出，同輸入同 bytes。

**payload**：manifest＝`{v,rid,request_sha,candidate_sha,job,files:{名:sha256},toolcards:{path,sha256},task}`（task 的 `x.author` 不含 payload_sha，避免循環），以排序鍵、`(",",":")`、UTF-8 序列化取 SHA-256＝`payload_sha`。manifest 存在 verdict，不另建檔。

**表項**：`{"name":"author-<job>","mode":"keep","max_live":1,"argv":["python3","<step/bin/aos7-step 絕對路徑>","run","jobs/<job>"],"x":{"author":{owner:"author",rid,candidate_sha,payload_sha}}}`。

## 5. 發布與恢復

`publish <rid> [--sha S] [--resend]`（省略 sha 取 active），全程在 `author.lock` 內：

1. 已有該版回條＝回原回條（`dup`），**不補表**，不復活已被移除／disabled 的工作；結案後也一樣。
2. 已有該版 intent（上次中斷）＝走恢復（下表），不重新登記。
3. 驗證沒過＝invalid；達版本上限＝full。
4. `jobs/`、`jobs/<job>`、`out/` 本身或 `out/` 裡有 symlink＝invalid（發布前再查一次逃逸）。從磁碟重算 payload（`jobs/<job>/` 固定來源＋目前工具卡＋需求），與 verdict 不同＝invalid（`payload_changed`）。
5. 寫 intent（`test_point author:after-intent`）。
6. 拿 `tasks.json.lock`（2 秒）重讀：**只有檔不存在**才從空表起；讀不到／壞／內容是 `null`／不是 `{"tasks":[…]}`＝unknown、不寫。只比自己那一名：完全相符＝不追加；同名異內容或 `enabled:false`＝conflict、保留現況；不在＝追加。其他項、`launch`、`mount_allow` 等頂層原樣（不比整份表雜湊）。（`author:after-merge`）
7. 寫回條 `{v,rid,request_sha,candidate_sha,payload_sha,job,task_name,registered:true,evidence,closed:false}`（`author:after-receipt`）。

**恢復**（有 intent、無回條；只讀表、不改表）：

| 證據 | 動作 |
|---|---|
| 有回條 | 回原條，不補表 |
| 表上有完全相符的項 | 補回條（evidence `table`），不追加 |
| 表項不在，但槽 `birth.json` 的 name／argv／`x.author` 相符，或 `frame.json` 的 `job`＋`table` 綁得上 steps，且 `jobs/<job>/` 固定來源全部等於 intent 記的 `files` 雜湊 | 補回條（evidence `birth`／`frame`），表仍不存在 |
| 只有 intent | `unknown`，不補加 |
| 同名改過／disabled | `conflict`，保留現況 |

- 只有 job 名、或固定來源已被換過的 frame 不算正證據。讀不到（OSError、壞 birth、鎖逾時）＝unknown，保留證據。
- 「意圖後被殺」與「登記後被人移除、無正證據」證據相同，一律 unknown；續發只靠人手 `publish <rid> --resend`：只接受恢復結果是 unknown 的版本，丟舊 intent、重走首次發布（人負責，仿 step `resume --resend`）。
- 回條只證明登記過，不證明 CSV 正確。

## 6. 執行

step 不改：表項起 `aos7-step run jobs/<job>`（keep、`max_live:1`、`restart_on_end:false`，跑完 ended 後再起也立刻退出、不開新 inst）。rid 是作者需求；step 的 inst／request／attempt、核心 `slot#run` 照原語意，作者不把 attempt 當新需求。frame／results／out 不在 payload 內。

## 7. 答案與 close

- `answer <rid> [--sha S]`：step 已 ended、**`aos7-step close` 之前**跑。核 `jobs/<job>/steps.json` 與 `jobs/<job>/data.csv`（工具實際讀的快照）雜湊＝verdict，再跑工具卡的 `answer_checker`（`examples/csv-request/check_answer.py jobs/<job> jobs/<job>/data.csv`；步名照 argv 裡的腳本找，不綁 convert／stats 字面），結果 `{ok,issues,checker_sha256}` 寫進 verdict 的 `answer`。
- `close <rid>`：人明示結案。條件：沒有結果不明的 intent（否則 unknown、一檔不刪）；至少一版已發布；沒有待審的合法（或 verdict 不見的）候選；每個已發布版 `frame.json` 為 `ended`＋`closed:true`、`answer` 已驗（否則 conflict）。先把各版 hashes、證據、答案、`closed` 寫進 receipt，再刪 candidate／verdict／intent，清作者夾的死暫存檔。剩 `request.json`＋`receipt.json`。中途被殺：receipt 已 closed，重送接著清。
- close 不 retire、不 kill、不刪 `jobs/<job>/`、不改表項；step 的 `results/` 由 step close 清。

## 8. 退出碼與錯誤

CLI 印 JSON `{ok, why, ...}`。`0` 成功（含 dup）、`2` invalid（候選、需求、驗證、`payload_changed`）、`3` conflict（rid 異內容、同名表項改過／disabled、job 撞名、已結案、close 條件不足）、`4` unknown（帳或表讀不到／壞、鎖逾時、只有 intent）、`5` full（版本上限）。本刀不發 events、不接模型、無自動 JSON 修復。

## 9. 明確不管

人手改 `author/` 帳、不拿表鎖改 tasks.json、同 node 兩套作者帳、執行中換版、自動 retire 舊版、真模型與 token 帳（第二刀）。
