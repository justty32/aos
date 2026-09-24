← [工具大開發時代](../README.md)｜[notes 索引](../../README.md)｜計畫 [plan.md](../plan.md)｜目錄 [catalog.md](../catalog.md)｜審查 [任務書](review-task.md)／[回報](review-astra.md)

# 第二波 C 隊（申請類）報告（2026-09-24）

**一句話**：T-lock／T-access-req／T-persona／T-pool 四個工具都做完、都真跑過一次（模型寄申請→人 answer→生效）；順手修了審查子單編號跟父單對不起來的 bug，領隊改寫類的單子會機械補 `wf_lint_strict`；astra 唯讀審查必修 8 條全修。測試 86 檔 2370 條，全綠。開發基底：main `eacfcc2`（one-boot 之後）；收尾前 rebase 過第二波 A／B 隊與交接書更新，最終基底 `b6c9dfe`。

## 1. 做了什麼

| 項 | 做了什麼 | 在哪 |
|---|---|---|
| A `access_request` | 模型申請多掛一個資料夾／開網路：不開新 kind，直接借用 `kind: ask`——把 `{name, path_hint, mode, why}` 組成一句問句，走既有的 `aos-team wait／answer`。**答案不會自動生效**：問句裡已經寫好人同意後要自己跑的 `aos-agent access set`（既有指令，B 隊的） | `tools/task/access_request`、[spec/team/ask.md〈借用〉](../../../spec/team/ask.md) |
| B `persona_propose` | 同上的路子，改人格。新增 `aos-agent persona show／set／append`（讀寫 `prompts/system.json` 的 `content`，不叫模型、不進牢）給人同意後套用 | `tools/task/persona_propose`、`lib/aos_agent_persona.py`、[spec/agent/persona.md](../../../spec/agent/persona.md)（新） |
| C `lock` | 新的申請種類 `kind: lock`。短期獨佔一個檔或資料夾的名字，`team/locks/<名>.json` 只有郵差寫。**全部非同步**（跟其他工具同路，模型端沒有同步等待的機制）：`acquire` 拿不到就丟 `Busy`，郵差照共同規則退信說誰拿著、到期幾點；逾時自動放；同一持有者可以續租。人的指令 `aos-team lock ls／acquire／release` | `lib/aos_team_lock.py`、`tools/task/lock`、[spec/team/lock.md](../../../spec/team/lock.md)（新） |
| D `_pool`（T-pool） | 工具檔加一欄 `_pool`：寫了就走那個池，沒寫照舊用 `tool_pool`。給「好幾個 agent 共用一支工具、一顆卡」用。照 [priority-and-shared-cpu 提案](../../2026-09-24-priority-and-shared-cpu/README.md)，kernel 派工、daemon 沒動 | `aos_agent_home.py`（驗）、`aos_agent_batch.py`（選池）、`aos_kernel_check.py`（查池）、[spec/agent/info.md §3.3](../../../spec/agent/info.md)、[spec/aos-agent/send.md §5.2](../../../spec/aos-agent/send.md) |
| E `routine_propose` | T2 的 `on_routine` 郵差端本來就支援「成員提的例行開一題問人」，就是缺模型能叫的工具，補上 | `tools/task/routine_propose`、[spec/team/beat.md〈模型端〉](../../../spec/team/beat.md) |
| F 審查子單編號 | 審查子單的條目對外一律用**父單的原編號**（`review_of.indices`），不是子單裡 0 起算的位置——`render_review` 給審查員看的文字、`board show`、`review_result` 交回的 `i` 三處以前不一致，t5 試玩兩輪都踩到 | `lib/aos_team_task.py`、`tools/task/board`、`tools/task/review_result`、[spec/team/tasks.md](../../../spec/team/tasks.md) |
| G 自動補 `wf_lint_strict` | `handoff` 送件前，若 `goal／facts／workflow` 合起來同時有 `.md` 與一個改寫用詞（白話、改寫、更好懂、更易讀、講白話），且 `done_when` 還沒放 `wf_lint_strict` 就機械補一條。**代裁**：見 §4 | `tools/task/handoff`、[tools/task/README.md](../../../tools/task/README.md) 最後一段 |
| 模板 | `lead`、`worker` 的 `may`、`tools.only`、`system.md` 各加新工具的用法一句話 | `templates/lead/`、`templates/worker/` |
| H 真跑 | 見 §2 |  |
| 審查 | astra 唯讀審一輪 | [任務書](review-task.md)／[回報](review-astra.md) |

## 2. 真跑

**環境**：跟共用的 `$HOME/aos-try` 分開，另開一個隔離的 kernel＋daemon（`/tmp/…/scratchpad/w2c-try/{K,D}`），避免撞到其他並行的隊。模型 LiteLLM `localhost:4000` 的 `deepseek-chat`，不用 api_key。池：`default` 3 顆、`llm` 2 顆。名冊：`lead`、`worker-1`、`worker-2`、`reviewer` 四人（`worker-2` 是為了真跑 lock 的搶鎖）。

每種申請至少真跑一次，`aos-agent say` 指定只用一個工具（省模型呼叫、也讓每一步能對得上是哪支工具做的）：

| 申請 | 模型端 | 人 answer | 生效 | 結果 |
|---|---|---|---|---|
| `access_request` | worker-1：`{"name":"shared-notes","path_hint":"/tmp/w2c-try/shared-notes","mode":"ro","why":"想讀共用筆記"}` | `answer q-0001 同意` | 人跑 `aos-agent access set shared-notes <路徑> --ro` | `access ls` 看得到新掛載 `shared-notes ro` |
| `persona_propose` | worker-1：`{"text":"遇到殘留一律先跑 wf_residue","why":"省一次來回"}` | `answer q-0002 同意` | 人跑 `aos-agent persona append "…"` | `persona show` 看得到新句子接在人格最後一行 |
| `lock` | worker-1 `acquire shared-config`（ttl 300秒）→ worker-2 也 `acquire shared-config` | 不用（lock 不經問人） | 不用（立即生效／立即拒絕） | worker-1 拿到「取得鎖…到期 22:15:29」；worker-2 被退信「Busy…被 worker-1 拿著，到期 22:15:29」 |
| `routine_propose` | lead：`{"name":"count-md","every":"5m","to":"worker-1","goal":"數 ws 裡的檔案數量寫進 notes/count.txt","done_when":[{"kind":"file_exists","path":"notes/count.txt"}]}` | `answer q-0003 批准` | 不用另外跑指令——批准本身就讓 `authorized()` 判定為 true | `routine ls` 顯示「人批准了」；下一次到期（5 分鐘後）心跳真的派出 `t-0001` 給 worker-1，worker-1 做完回 DONE，`notes/count.txt` 真的寫出來（內容 `1`） |

**四種都走完「模型寄申請 → 人 answer → 生效」**（lock 例外：它本來就不經問人，acquire／release 是立即生效／立即拒絕，這是設計本身，見 §5）。

**意外發現**（沒預期到、值得記錄）：`access_request`／`persona_propose` 的問句裡寫了「同意的話麻煩你自己跑：`aos-agent access set …`」——這句話是寫給**人**看的，但 worker-1 的模型收到「同意」的回信之後，**自己**認真嘗試用 `bash` 工具跑那行指令（失敗：`aos-agent` 不在牢裡的 PATH、`access.json` 它也改不到），最後正確地回 `BLOCKED` 給人、講清楚卡在哪。模型的判斷本身沒問題（牢確實擋住了它，它也沒假裝成功），是問句的措辭可能該更明確地區分「這是講給人聽的」——已經寫進審查任務書請 astra 一併看。

## 3. 六軸自評（工具類，非團隊；每支工具都沒叫模型）

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | **5** | 四支工具本身都不叫模型（純讀寫檔）。真跑時「送出申請」這個動作都只用 1 次模型呼叫、當輪結束（設計如此：工具回「queued …, end this turn」）。上面〈意外發現〉的額外呼叫是**問句措辭**造成模型多想了幾步，不是工具本身多叫模型，不扣這軸的分 |
| 2 穩定 | **—（不給分）** | 每種申請只真跑 1 次，跑不到 10 次。單元測試覆蓋了主要分支：lock 15 條（acquire／release／ls／Busy／續租／過期／冪等／`may_send`／CLI）、persona 10 條、加上 handoff／board／review_result／task.json 的既有測試改動；但沒有「同一情境跑 10 次」的真跑重複 |
| 3 資源 | **?**（工具描述量得到，token／cpu 秒量不到） | 工具描述字元數：`lock` 530、`access_request` 501、`persona_propose` 327、`routine_propose` 1008（對照 axes.md 門檻，多數落在 300～<800＝4 分；`routine_propose` 因為欄位多落在 800～<2000＝3 分）。**送給模型的實際 token 用量量不到**：LiteLLM 這個 endpoint 的 `usage.jsonl` 全是 0（T5 已經記過這個現象，這次真跑再確認一次）；cpu 秒沒有另外用 `/usr/bin/time` 量，寫 null |
| 4 快 | **?**（沒精確計時，粗略看落在 4） | 真跑是手動輪詢確認結果，不是計時器量的。粗略觀察：`access_request`／`persona_propose`／`lock` 送出到回信都在同一個 tick 週期內（幾秒到十幾秒，對到 axes 1～<3 分鐘＝4）；`routine_propose` 從批准到心跳派出、worker 做完，約 2 分鐘內（心跳輪詢間隔本身就要等，不是工具慢） |
| 5 人易懂 | **4** | `aos-team wait ls`／`mail` 每一步都是人看得懂的一行；`lock` 的 Busy 退信直接講清楚「誰拿著、到期幾點」，不用猜。扣分：要翻三份新文件（`ask.md`〈借用〉、`lock.md`、`persona.md`）才拼得出全貌；沒有另外派一個乾淨的新手 agent 照 README 玩一輪（時間有限省了這步，見 §4） |
| 6 邊界 | **4** | 四支工具都只寫「自己的 outbox」，模型碰不到 `team/locks/`、`access.json`、`prompts/system.json` 本身——這三個都是「答案不自動生效」的設計（§5 決定），寫入動作永遠是人的指令做的。沒給滿 5 分：`lock` 的鎖名是模型自訂的字串（雖然有格式擋：英數與 `. _ - /`、擋 `..` 段與開頭 `/`、上限 200 字），語意上模型能拿任何名字「佔用」，不是完全固定路徑，算「會寫到固定用途的別處，但寫法原子、格式固定」那一檔（3～4 分之間，取 4） |

## 4. 我代裁的（附預設，翻案就回這條）

| # | 決定 | 理由 |
|---|---|---|
| 1 | **G 選在 `handoff` 工具層機械補 `wf_lint_strict`，不改門房規則** | 門房、`routes.json` 是 A 隊地盤（T-route），改規則風險較大；handoff 這一層改動範圍最小，且不管請求有沒有經過門房都補得到（領隊自己開單、心跳照例行開單一樣有效）。判法純文字比對（`.md` ＋ 改寫用詞），可能有假陽性／假陰性，見審查任務書題 5 |
| 2 | **T-access-req／T-persona 不開新 kind，借用 `kind: ask`** | 兩者都是「包成一題問人、答案不自動生效」，跟 `ask_human` 本質相同，開新 kind 只是多一層沒必要的間接。代價：這兩種申請跟一般問題混在 `aos-team wait ls` 裡（審查任務書題 3 問要不要加前綴分辨） |
| 3 | **T-lock 的三種操作全部非同步（含 `ls`）** | catalog 草案設想「acquire 立即回、不等」，但模型端沒有同步等待這種東西（工具送出這輪就結束，回信是下一輪的新輸入）。`ls` 若要同步讀（像 `board` 讀 `team/tasks/`），需要一個新的唯讀 mount，那是 B 隊 access.json 的地盤，這次不動 |
| 4 | **鎖逾時只看時間，不跨查 agent 的 `state.json`** | catalog 草案設想「郵差確認持有者已撤銷、沒有在途工具才收」，但那要跨到 agent 家去看 state；這一版先用「過期就是過期」，簡單、可預期，代價是持有者真的還在用、忘記續租時會被搶走（可以再 acquire 續租） |
| 5 | **T-persona 的 `aos-agent persona` 只做 show／set／append，不做結構化分段** | 人格是一段自由文字（`system.md` 沒有固定分節格式），沒有「改某一段」的結構可以定位；append／set 已經夠用，跟 `aos-agent notes`／`aos-json` 的「先給最小可用版」一致 |
| 6 | **不重新設計 `access_request`／`persona_propose` 的問句措辭去避免模型自己嘗試執行**（§2〈意外發現〉） | 模型的行為本身沒有壞：它試了、失敗了、老實回報卡在哪，這是牢起作用的證據，不是漏洞。改措辭是加分項不是必修，留給審查看要不要建議 |

## 5. 要使用者拍的（一題，預設列在後面；越少越好）

| # | 題目 | 我的預設 |
|---|---|---|
| 1 | `access_request`／`persona_propose` 這兩種「借用 `kind: ask`」的申請，要不要在問句前加一個固定前綴（例如 `[access_request]`），讓 `aos-team wait ls` 一眼分得出哪些是「一般問題」、哪些是「同意後你要接著跑一個指令」？ | **預設：先不改**——問句本文已經把要跑的指令寫得很清楚，多加前綴是錦上添花；真的常常翻不出來再加 |

## 6. 給其他隊

- **P 隊（kernel／daemon）**：沒動這塊，`aos_kernel_check.py` 多了 `_pool` 的檢查（讀而已，不改派工邏輯）。
- **A 隊（工具開發）**：G 的自動補 lint 判法如果覺得該改成門房規則，`wf_lint_strict` 這條檢查器名字跟現有的 `done_when` 格式沒衝突，可以直接接。
- **B 隊（牆）**：`lock` 的 `ls` 若之後要做成同步唯讀（像 `board`），需要一個新的保留 mount 名字（例如 `locks`），這次沒加。
- **第三波**：T-crystal（固化建議）如果統計到「領隊常常忘記放 `wf_lint_strict`」這種句型，這次的機械補應該已經把它蓋掉了，可以在真跑資料裡確認。
- **A 隊（導入工人模板 `importer`）**：主 rebase 時發現 A 隊新加的 `templates/importer/` 工具表刻意瘦身（約一半），只裝 `ask_human`、沒有 `compact_me`。**判斷：不把這次新增的 `lock`／`access_request`／`persona_propose` 加進去**——這個模板的設計目標就是壓低每次呼叫送的工具表大小（R 軸），申請類工具沒有已知的導入場景會用到，加了只是白佔 token；真的遇到「兩個導入工人搶同一個檔」再議。

## 7. 審查改了什麼

astra（gpt-6-astra）唯讀審查：必修 8 條、建議 4 條，**必修全修**（[任務書](review-task.md)／[回報](review-astra.md)）。

- **M1 鎖的到期時間被申請者控制**：`on_lock` 原本 `now = req.get('at') or now_iso(...)`，跟 `on_ask`／`on_routine` 一樣信任申請裡的 `at`；但鎖的 `expires_at` 是從 `now` 算出來的安全相關欄位，模型能自己在 outbox 塞一份帶未來時刻 `at` 的申請，把到期日推到很遠、繞過 `ttl_seconds` 上限。改成一律用郵差自己的時鐘（`now_iso(roster.get('tz'))`），不管 `req['at']`。
- **M2 合法鎖名不一定能落檔、`ls` 會漏列**：鎖名允許 `/`、中文，直接當檔名會撞「要先建子目錄」「`.hidden` 被排除」「檔名位元組長度上限」三個坑。改成 `Layout.lock()` 用 `sha256(名字)` 當固定長度、平面、非隱藏的檔名，原名存進 JSON 內容的 `name` 欄位，`ls`／`describe` 都讀內容不讀檔名。
- **M3 問句裡建議的指令直接嵌入未轉義的模型文字**：`persona_propose` 把提案文字原樣塞進雙引號組成 `aos-agent persona append … "…"`，提案含 `$(id)` 這種字串，人照抄執行時殼層會先做指令替換；`access_request` 的 `name` 完全沒驗證也沒引用。改成：`persona_propose` 用 `shlex.quote()` 包住 text；`access_request` 幫 `name` 加上跟 `aos_agent_access.NAME` 一致的格式驗證（`[a-z0-9_-]+`、擋保留字），格式對了才不需要引號、格式不對直接 `BadArguments` 擋掉，不會走到組指令那步。
- **M4 persona 指令與 runtime 對 `system` 的解析不一致**：`aos_agent_persona.py` 原本直接 `info.get('system')`，遇到指示詞物件（例如 `{"$env": "PERSONA_PATH"}`）會誤判成沒設定、退回預設檔，跟 runtime 實際讀的檔不是同一份，寫了也沒用還印成功。改成共用 `aos_agent_home` 的 `read_info_doc`／`resolve_field`／`aos_directives.Context`，明寫但解不出非空字串就報 `FieldTypeMismatch`，不再默默退回預設。
- **M5 人的 `task show` 漏改審查編號**：F 的編號修正漏了 `aos_team_task_cli.py` 的 `show()`（`aos-team task show` 這條人用指令），`board`、派工信、回報都已經用父單原編號，這裡卻還是 `enumerate` 從 0。已補上（跟 `board` 同一招：有 `review_of.indices` 就用它）。
- **M6 G 的文件宣稱涵蓋心跳，實際沒有**：原本文件／註解寫「心跳照例行開單一樣有效」，但 `aos_team_beat.py` 是自己組 `handoff` 申請直接送 `aos_team_requests.handle()`，根本不經過 `tools/task/handoff` 這支工具，`_wants_auto_lint` 完全碰不到。改成文件與註解都限縮成「只涵蓋模型叫 `handoff` 工具開的單」，不把邏輯複製進心跳（避免兩處判法各改各的）。
- **M7 `access_request` 對模型宣告能申請網路，實際無此介面**：description 寫「or turn networking on」，但 schema 逼填 `name／path_hint／mode`，填不出一個純開網路的申請。改成 description 與 docstring 都限縮成「只做資料夾」，網路需求另外用 `ask_human`。
- **M8 教程把四種申請的批准效果寫成同一種**：`access／persona` 要人另外套用指令、`routine` 批准後心跳自動生效、`lock` 根本不開問題（郵差直接處理）——原本開場白寫得像四種都一樣。改成逐條分開講清楚。
- **S1 G 收窄觸發條件**：重現兩種假陽性（否定句「不要把 README.md 改成更白話」、`goal=改寫 app.py` 搭配 `facts=參考 README.md`，後者其實是因為 `workflow` 欄位幾乎必是 `.md` 檔，混進判斷條件等於每件事都判「有 .md」）。改成只看 `goal` 一欄，加一張否定詞表（不要／別／不用／不准；刻意不放「不能」，因為真跑原句「意思不能變」本身就有這兩個字）。英文措辭仍會漏判，這版不做語言判斷。
- **S2／S3／S4（建議，已在 §4／§6 代裁／列給其他隊，這裡不重複展開）**：模型端 `lock ls` 要不要同步（列進 §6 給 B 隊）；問句加固定前綴分辨「需人手動套用」（列進 §5 待拍題的備選，這版先不做）；鎖名不是防留言板機制，過期紀錄不會自動清（記錄下來，這版不當漏洞處理，因為鎖本來就是合作式租約）。
- **確認沒問題的**：F 的兩次 `want` 檢查一致（工具本地檔＋伺服器各查一次，沒有二次轉換出錯）；T-pool 的 `_pool` 覆寫／回退／診斷都對得上；借用 `kind: ask` 這個設計本身可行；`acquire`／`release` 經郵差序列化合理（鎖是合作式租約，不強制擋持有者以外的人寫專案檔案）。

**跑了什麼確認修好**：`test_team_lock.py`（+3 條：偽造未來 `at`、含 `/` 與中文的鎖名、既有 15 條全過）、`test_agent_persona.py`（+2 條：`$env` 指示詞解析、解不出時報錯）、`test_team_init.py`（`access_request` 改成驗名字格式、`handoff` 的假陽性／假陰性案例）、`test_team_task_cli.py`（+1 條：審查子單 `show` 用原編號）。改完全套 2217 條再跑一次，全綠。

## 8. 數字

- **測試**：86 個測試檔、2370 條（開始時是第一波收尾隊的 78 檔 2177 條；中途第二波 A／B 隊各自合進 main，收尾前 rebase 到 main `b6c9dfe` 時是 84 檔 2330 條）；`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`，全綠。
  - 這隊新增：`test_team_lock.py` 17 條（含 astra 審查補的 2 條）、`test_agent_persona.py` 12 條（含 astra 補的 2 條）、`test_team_init.py`／`test_team_task_cli.py`／`test_agent_home.py`／`test_agent_tick.py`／`test_kernel_check.py`／`test_team_format.py` 各加幾條（新工具、`_pool`、審查編號、G 的假陽性／假陰性、`may`）。
- **改動範圍**：`git diff b6c9dfe HEAD -- proto5` 共 53 個檔（11 新、42 改，含兩輪 rebase 衝突手工合併）。
